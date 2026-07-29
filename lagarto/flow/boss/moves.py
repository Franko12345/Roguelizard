"""Boss movement patterns (issue #118).

The boss FSM has a movement trail: every frame, it returns a
``(direction, speed)`` that drives the body's ``steer``. This module
holds the five background patterns (``orbit``, ``strafe``, ``retreat``,
``hover``, ``reposition``), sibling to ``PATTERNS`` in ``patterns.py``.

Two bindings, with precedence **attack > phase > none**:

- **By phase** -- each phase kit carries a ``moves=[]`` slot. The active
  movement drives the boss when no attack is speaking. Unique per boss:
  A Muralha (``plan='fixed'``) declares ``moves=[]``; Olho-Sismico uses
  ``moves=['hover']`` (the observer).
- **By attack** -- a ``PATTERNS`` row may carry ``move='orbit'`` /
  ``'strafe'`` / ``'retreat'`` / ``None``. Movement glued to that
  attack. Unique per attack. Charge / burrow / grapple keep vetoing
  everything (their own state machines own the motion).

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


# Registry: id -> move function. The id is the string you write in
# PATTERNS['foo']['move'] or in a phase kit's 'moves' list. Adding a
# move = one function + one entry, no editing of dispatch.
MOVES = {
    'orbit':      move_orbit,
    'strafe':     move_strafe,
    'retreat':    move_retreat,
    'hover':      move_hover,
    'reposition': move_reposition,
}
