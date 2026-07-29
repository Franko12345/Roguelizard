"""Boss movement patterns (issue #118, the Wasp's signatures in #122).

The boss FSM has a movement trail: every frame, it returns a
``(direction, speed)`` that drives the body's ``steer``. This module
holds the background patterns (``orbit``, ``strafe``, ``retreat``,
``hover``, ``reposition``) plus the Wasp's flight shapes
(``dive_arc``, ``flyby``, ``climb_out``, ``curve_approach``), sibling to
``PATTERNS`` in ``patterns.py``.

Two bindings, with precedence **attack > phase > none**:

- **By phase** -- each phase kit carries a ``moves=[]`` slot. The active
  movement drives the boss when no attack is speaking. Unique per boss:
  A Muralha (``plan='fixed'``) declares ``moves=[]``; Olho-Sismico uses
  ``moves=['hover']`` (the observer); the Wasp (``flying=True``, no
  arena) uses ``['curve_approach','climb_out']`` / ``['dive_arc']`` /
  ``['dive_arc','flyby']`` -- the per-phase binding is its
  identity.
- **By attack** -- a ``PATTERNS`` row may carry ``move='orbit'`` /
  ``'strafe'`` / ``'flyby'`` / ``None``. Movement glued to that
  attack. Charge / burrow / grapple keep vetoing everything (their
  own state machines own the motion).

Charge / burrow / grapple keep their current "veto movement" precedence;
they do not go through this module.

Each function is ``(boss, game, target, dials) -> (direction, speed)``.
``dials`` is whatever the caller passed -- the active ``PATTERNS[pid]``
row for an attack, the phase kit dict for the phase trail. Dials is
read-only; behaviour is selected by the function's own logic.

When a phase kit lists more than one move (``['dive_arc', 'flyby']``),
the FSM tries them in order and takes the first that returns a non-zero
speed. The dive only animates while its pattern is on, so a phase kit
that wants a dive followed by a different background picks the dive
first and the other move takes over the rest of the time.

Related: ``BossAI.tick`` in ``ai.py`` (the trail is wired there),
the ``moves`` key in each ``*_phases()`` kit, and ``PATTERNS[pid]['move']``.
"""

import math

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
#  Wasp (Terror Alado) movement shapes -- issue #122                           #
#  Flight has its own geometry: arcs, dives that pass THROUGH and exit the    #
#  other side, climbs out of reach, curved approaches. These are the per-     #
#  phase bindings that make the Wasp read as a hunter instead of an orbit-    #
#  with-shots. The Wasp owns the open world (no arena), so these moves are    #
#  allowed to cross the whole 3200x3200 map. ``Lizard.integrate`` clamps the  #
#  body to the world bounds either way.                                       #
# --------------------------------------------------------------------------- #

def _dive_exit_pt(start, target_pos, length=240, perp_off=110):
    """Control point for the dive Bezier: the exit point past + perpendicular
    to the dive line. ``length`` is how far past the target the wasp exits;
    ``perp_off`` is the lateral arc so the dive isn't a straight line.
    """
    delta = target_pos - start
    if delta.length_squared() < 1e-4:
        return Vector2(target_pos.x + length, target_pos.y)
    line = delta.normalize()
    perp = Vector2(-line.y, line.x)
    return target_pos + line * length + perp * perp_off


def _dive_arc_point(start, target_pos, exit_pt, t):
    """Quadratic Bezier sample at parameter ``t`` in [0, 1]."""
    u = 1.0 - t
    return start * (u * u) + target_pos * (2.0 * u * t) + exit_pt * (t * t)


def move_dive_arc(boss, game, target, dials):
    """Fly THROUGH the target and out the other side (Wasp's signature).

    The arc is a Bezier sampled by the dive windup's own countdown:
    ``start`` (snapshot when the dive windup began) -> ``target.pos``
    -> ``exit_pt`` (a perpendicular bend past the target). When the
    windup ends the wasp is on the OTHER side of the player, not on
    top of them -- that is the whole shape of a dive.

    Returns ``(0, 0)`` outside the dive windup, so a phase kit with
    ``moves=['dive_arc', 'flyby']`` falls through to ``flyby`` whenever
    the dive isn't on. ``Lizard.integrate`` clamps to world bounds --
    the wasp neither caged nor caged-out, just bounded.
    """
    if target is None:
        return Vector2(), 0.0
    ai = getattr(boss, 'boss_ai', None)
    if ai is None or ai.state != 'windup' or ai.pattern_id != 'dive_arc':
        return Vector2(), 0.0
    windup = ai._eff_windup('dive_arc')
    t = max(0.0, min(1.0, 1.0 - ai.t / max(1e-4, windup)))
    start = getattr(boss, '_dive_start', None)
    if start is None:
        return Vector2(), 0.0
    exit_pt = _dive_exit_pt(start, target.pos)
    pt = _dive_arc_point(start, target.pos, exit_pt, t)
    desired = pt - boss.pos
    if desired.length_squared() < 1e-4:
        line = (target.pos - start)
        if line.length_squared() < 1e-4:
            return Vector2(1, 0), 1.0
        return line.normalize(), 1.0
    return desired.normalize(), 1.2


def move_flyby(boss, game, target, dials):
    """Curved approach: tangential bias that bends the approach into an arc.

    The wobble phase rides ``game.time`` so each call traces a
    different point on the curve. A fan or barrage bound to flyby is
    the hard combo: the cone aims where you ARE (re-aim live from
    #118), and the wasp is simultaneously curving toward you.
    """
    if target is None:
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return Vector2(1, 0), 0.0
    line = to.normalize()
    perp = Vector2(-line.y, line.x)
    side = 1.0 if math.sin(game.time * 2.6) >= 0 else -1.0
    vec = line + perp * side * 0.55
    if vec.length_squared() < 1e-4:
        return line, 0.7
    return vec.normalize(), 0.7


def move_climb_out(boss, game, target, dials):
    """Retreat upward/away -- the Wasp gets out of reach for a beat.

    Straight retreat, scaled to ``max_speed``. Phase 1 of the Wasp's
    kit: it dips, retreats, dips again -- a hunting rhythm with
    air between strikes, not a metronome.
    """
    if target is None:
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return Vector2(-1, 0), 0.0
    return -to.normalize(), 0.55


def move_curve_approach(boss, game, target, dials):
    """Sinusoidal approach: oscillates side-to-side while closing in.

    The perpendicular wobble is the whole reason a barrage that ALSO
    moves is hard to read: the wasp traces a curve while the lead
    formula aims at where the player IS. Used by the Wasp's
    ``barrage`` attack (bound by ``PATTERNS['barrage']['move']``).
    """
    if target is None:
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return Vector2(1, 0), 0.0
    line = to.normalize()
    perp = Vector2(-line.y, line.x)
    wobble = math.sin(game.time * 3.0) * 0.6
    vec = line + perp * wobble
    if vec.length_squared() < 1e-4:
        return line, 0.75
    return vec.normalize(), 0.75


# Registry: id -> move function. The id is the string you write in
# PATTERNS['foo']['move'] or in a phase kit's 'moves' list. Adding a
# move = one function + one entry, no editing of dispatch.
MOVES = {
    'orbit':           move_orbit,
    'strafe':          move_strafe,
    'retreat':         move_retreat,
    'hover':           move_hover,
    'reposition':      move_reposition,
    'dive_arc':        move_dive_arc,
    'flyby':           move_flyby,
    'climb_out':       move_climb_out,
    'curve_approach':  move_curve_approach,
}
