"""Boss movement patterns (issue #118).

The boss FSM has a movement trail: every frame, it returns a
``(direction, speed)`` that drives the body's ``steer``. This module
holds the six background patterns (``orbit``, ``strafe``, ``retreat``,
``hover``, ``reposition``, ``proud_walk``), sibling to ``PATTERNS`` in
``patterns.py``.

Two bindings, with precedence **attack > phase > none**:

- **By phase** -- each phase kit carries a ``moves=[]`` slot. The active
  movement drives the boss when no attack is speaking. Unique per boss:
  A Muralha (``plan='fixed'``) declares ``moves=[]``; Olho-Sismico uses
  ``moves=['hover']`` (the observer); Rei Lagarto uses
  ``moves=['proud_walk']`` (the legibility canonical -- #123).
- **By attack** -- a ``PATTERNS`` row may carry ``move='orbit'`` /
  ``'strafe'`` / ``'retreat'`` / ``'proud_walk'`` / ``None``. Movement
  glued to that attack. Unique per attack. Charge / burrow / grapple
  keep vetoing everything (their own state machines own the motion).

Charge / burrow / grapple keep their current "veto movement" precedence;
they do not go through this module.

Each function is ``(boss, game, target, dials) -> (direction, speed)``.
``dials`` is whatever the caller passed -- the active ``PATTERNS[pid]``
row for an attack, the phase kit dict for the phase trail. Dials is
read-only; behaviour is selected by the function's own logic.

State the function may need (``committed_dir`` and similar) lives on the
``BossAI`` instance, not in module globals -- two bosses of the same
kind would stomp each other's state otherwise.

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


# --- Rei Lagarto's movement (#123) ----------------------------------------- #
# ``proud_walk`` is the legibility canonical -- the simplest, most telegraphed
# move in the pool. It commits to a direction and never reverses: a sign flip
# would mean the boss ran away from the player, and that's a different fight.
# Each new direction is picked forward of where the boss is already facing
# (within a 180-degree cone), so the walk reads as deliberate, not reactive.
#
# Per-pattern binding: ``PATTERNS[pid]['move'] = 'proud_walk'`` drives the
# walk during that pattern's windup/recover. Per-phase binding:
# ``moves=['proud_walk']`` keeps it the background between attacks.
#
# The committed direction and the timer that re-picks it live on the
# BossAI so two Rei Lagarto instances never step on each other. The
# ring buffer of recent positions (``BossAI._path_samples``) feeds
# ``spawn_scar`` -- the CicatriZ puddle lands where the boss WAS, not
# at random underfoot.

PROUD_WALK_COMMIT_FRAMES = 90   # 1.5 s at SIM_HZ=60 -- a long, deliberate stride
PROUD_WALK_REPICK_CONE = 140    # degrees, half-angle around current committed dir
PROUD_WALK_TURN_BIAS = 0.65     # weight of current dir when picking a new one
PROUD_WALK_SPEED = 0.45         # slower than orbit (0.5) -- more readable


def move_proud_walk(boss, game, target, dials):
    """Commit to a direction and walk it. Never retreats.

    The first call seeds the commit from the line to the target. After
    that, the boss walks the committed direction until either:
    (a) the commit timer expires (~1.5s, a long deliberate stride),
    (b) the player has circled behind the committed line by more than
        ``PROUD_WALK_REPICK_CONE`` (read as "the player just dodged
        behind me -- the committed path is no longer where the fight
        is", so a new direction is picked that points at the player
        but stays in the forward half-cone).

    A new direction is NEVER the negation of the previous one. The
    direction chosen is in the half-cone around the current committed
    line, biased toward the player's current position, so the walk
    reads as "advance" (or "swing around", never "retreat").

    Returns ``(Vector2(), 0.0)`` if there's no target (the boss halts
    instead of running blind).

    State lives on ``boss.boss_ai``: ``_pw_dir`` (Vector2, the committed
    direction), ``_pw_t`` (int, frames since the last repick). Both are
    initialised by ``BossAI.__init__`` so two Rei Lagarto instances
    don't stomp each other.
    """
    ai = boss.boss_ai
    if ai is None or target is None:
        return Vector2(), 0.0
    cd = ai._pw_dir
    if cd.length_squared() < 1e-4:
        to = target.pos - boss.pos
        if to.length_squared() < 1e-4:
            return Vector2(), 0.0
        cd = safe_norm(to)
        ai._pw_dir = cd
        ai._pw_t = 0
    ai._pw_t += 1
    to_target = target.pos - boss.pos
    if to_target.length_squared() < 1e-4:
        return cd, 0.0
    norm_target = safe_norm(to_target)
    # dot product: +1 = aligned, -1 = opposite (the "retreat" we'd forbid).
    align = cd.x * norm_target.x + cd.y * norm_target.y
    # expire the commit on a long timer OR when the player has clearly
    # slipped around behind the committed line. The repick fires when
    # align < cos(180 - PROUD_WALK_REPICK_CONE) -- the "player is in the
    # rear half-cone" case.
    rear_cos = math.cos(math.radians(180 - PROUD_WALK_REPICK_CONE))
    if ai._pw_t >= PROUD_WALK_COMMIT_FRAMES or align < rear_cos:
        # Pick a new direction in the forward half-cone around cd, biased
        # toward the player. The bias is a weighted sum (TURN_BIAS * cd
        # + (1 - TURN_BIAS) * norm_target); sign flips from norm_target
        # alone are absorbed by the cd weight, so a direction >90 deg
        # behind the previous one is structurally impossible.
        new = cd * PROUD_WALK_TURN_BIAS + norm_target * (1.0 - PROUD_WALK_TURN_BIAS)
        if new.length_squared() < 1e-4:
            new = cd
        cd = safe_norm(new)
        ai._pw_dir = cd
        ai._pw_t = 0
    return cd, PROUD_WALK_SPEED


# Registry: id -> move function. The id is the string you write in
# PATTERNS['foo']['move'] or in a phase kit's 'moves' list. Adding a
# move = one function + one entry, no editing of dispatch.
MOVES = {
    'orbit':      move_orbit,
    'strafe':     move_strafe,
    'retreat':    move_retreat,
    'hover':      move_hover,
    'reposition': move_reposition,
    'proud_walk': move_proud_walk,
}
