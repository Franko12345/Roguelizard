"""Boss movement patterns (issue #118, #125).

The boss FSM has a movement trail: every frame, it returns a
``(direction, speed)`` that drives the body's ``steer``. This module
holds the background patterns (``orbit``, ``strafe``, ``retreat``,
``hover``, ``reposition``) plus the Aranha-Rei's two moves
(``erratic_step``, ``trap_and_shift``), sibling to ``PATTERNS`` in
``patterns.py``.

Two bindings, with precedence **attack > phase > none**:

- **By phase** -- each phase kit carries a ``moves=[]`` slot. The active
  movement drives the boss when no attack is speaking. Unique per boss:
  A Muralha (``plan='fixed'``) declares ``moves=[]``; Olho-Sismico uses
  ``moves=['hover']`` (the observer); Aranha-Rei uses the
  ``['erratic_step', 'trap_and_shift']`` pair (the nervous-siege pair).
- **By attack** -- a ``PATTERNS`` row may carry ``move='orbit'`` /
  ``'strafe'`` / ``'erratic_step'`` / ``'trap_and_shift'`` / ``None``.
  Movement glued to that attack. Unique per attack. Charge / burrow /
  grapple keep vetoing everything (their own state machines own the
  motion).

Charge / burrow / grapple keep their current "veto movement" precedence;
they do not go through this module.

Each function is ``(boss, game, target, dials) -> (direction, speed)``.
``dials`` is whatever the caller passed -- the active ``PATTERNS[pid]``
row for an attack, the phase kit dict for the phase trail. Dials is
read-only; behaviour is selected by the function's own logic.

Related: ``BossAI.tick`` in ``ai.py`` (the trail is wired there),
the ``moves`` key in each ``*_phases()`` kit, and ``PATTERNS[pid]['move']``.
"""

import math
import random

from pygame import Vector2

from ...core.mathutil import safe_norm, vfrom_angle


def move_orbit(boss, game, target, dials):
    """Circle around the target at a fixed orbit radius.

    The radius is a soft band: closer than 0.7x, push out; further than
    1.3x, push in; otherwise slide perpendicular. Tangential speed wins
    inside the band so the orbit reads as circular, not as a chase.
    """
    if target is None:
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return vfrom_angle(0, 1.0), 0.0
    dist = to.length()
    rim = safe_norm(to)
    perp = Vector2(-rim.y, rim.x)
    radius = 280
    if dist < radius * 0.7:
        return -rim, 0.6
    if dist > radius * 1.3:
        return rim, 0.6
    return perp, 0.5


def move_strafe(boss, game, target, dials):
    """Sideways motion, perpendicular to the target, with a small inward bias.

    The bias keeps the strafe from drifting open into a wide arc; the
    perpendicular component is what gives the boss its "dodging" feel.
    """
    if target is None:
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return Vector2(1, 0), 0.0
    perp = Vector2(-to.y, to.x)
    if perp.length_squared() < 1e-4:
        perp = Vector2(1, 0)
    else:
        perp = perp.normalize()
    toward = safe_norm(to) * 0.1
    return (perp + toward).normalize(), 0.6


def move_retreat(boss, game, target, dials):
    """Move away from the target. The "create space" move."""
    if target is None:
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return Vector2(-1, 0), 0.0
    return -safe_norm(to), 0.5


def move_hover(boss, game, target, dials):
    """Stay in place. The observer (Olho-Sismico): the rest of the body
    is the threat, the position is not. Mood speed still applies
    through the BossAI multiplier so a cornered eye can still flinch."""
    return Vector2(), 0.0


def move_reposition(boss, game, target, dials):
    """Move toward the target. The default approach when no move is
    declared. Loses to the ``to`` direction in ``approach`` state when
    the boss is far; falls back on the phase's own choice when close."""
    if target is None:
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return Vector2(), 0.0
    return safe_norm(to), 0.6


# --------------------------------------------------------------------------- #
#  Aranha-Rei's two moves (issue #125). Nervous repositioning and siege.        #
# --------------------------------------------------------------------------- #

def move_erratic_step(boss, game, target, dials):
    """Small random direction, kept for ``step_freq`` frames before re-rolling.

    The Aranha-Rei's background movement: "nervosa, quase TDAH" -- no
    elegant arc, just short stuttering steps in random directions. The
    direction re-rolls on a timer (``step_freq``, default ~0.32 s) so
    she doesn't twitch every frame (which reads as a slide, not as
    pacing). ``step_radius`` is the *maximum* step speed (a fraction
    of ``max_speed`` -- 0..1); the direction itself is uniform on the
    unit circle.

    The current direction is parked on the boss as ``_erratic_dir``
    with a counter ``_erratic_t``; clean-up is the FSM's job on death,
    but a stale value would just face the same direction next fight.
    """
    step_freq = int(dials.get('step_freq', 19))      # frames between re-rolls
    step_radius = float(dials.get('step_radius', 0.55))
    cur_dir = getattr(boss, '_erratic_dir', None)
    cur_t = getattr(boss, '_erratic_t', 0)
    if cur_dir is None or cur_t >= step_freq:
        ang = random.uniform(0, 360)
        cur_dir = vfrom_angle(ang, 1.0)
        cur_t = 0
    cur_t += 1
    boss._erratic_dir = cur_dir
    boss._erratic_t = cur_t
    return cur_dir, step_radius


def move_trap_and_shift(boss, game, target, dials):
    """After placing a web, shift to the side that has more free space.

    The Aranha-Rei's by-attack move: bound to ``web_trap`` and
    ``web_dome`` (see ``PATTERNS[pid]['move']``). The web's own
    ``select`` hook (``_select_arms_rain``) populated
    ``boss._rain_points`` at windup start, so the move can read them:

    - ``web_trap`` is one point at the boss's position (spread=60), so
      the centroid equals the boss's own pos and "away" reads as the
      boss leaving the trap she just laid.
    - ``web_dome`` is five points around the player (spread=180,
      radius=70), so the centroid sits near the player and "away"
      reads as the boss repositioning around the new blockage --
      which is the side of the player that's still open.

    Falls back to ``move_erratic_step`` when the rain_points are
    missing (e.g. an unrelated caller used the same move by accident).
    A small inward bias toward the target keeps the boss from drifting
    out of the fight while it punishes.
    """
    rain = getattr(boss, '_rain_points', None)
    if not rain or target is None:
        return move_erratic_step(boss, game, target, dials)
    cx = sum(p.x for p in rain) / len(rain)
    cy = sum(p.y for p in rain) / len(rain)
    trap_c = Vector2(cx, cy)
    away = boss.pos - trap_c
    if away.length_squared() < 1e-4:
        # degenerate (boss sits exactly at the centroid); dodge sideways
        perp = Vector2(-(target.pos - boss.pos).y, (target.pos - boss.pos).x)
        if perp.length_squared() < 1e-4:
            perp = Vector2(1, 0)
        return safe_norm(perp), 0.6
    away_n = safe_norm(away)
    toward_n = safe_norm(target.pos - boss.pos)
    blend = away_n * 0.65 + toward_n * 0.35
    if blend.length_squared() < 1e-4:
        return toward_n, 0.6
    return safe_norm(blend), 0.6


# Registry: id -> move function. The id is the string you write in
# PATTERNS['foo']['move'] or in a phase kit's 'moves' list. Adding a
# move = one function + one entry, no editing of dispatch.
MOVES = {
    'orbit':         move_orbit,
    'strafe':        move_strafe,
    'retreat':       move_retreat,
    'hover':         move_hover,
    'reposition':    move_reposition,
    'erratic_step':  move_erratic_step,
    'trap_and_shift': move_trap_and_shift,
}
