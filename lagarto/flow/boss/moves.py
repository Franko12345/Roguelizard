"""Boss movement patterns (issue #118, signatures from #121-#125).

The boss FSM has a movement trail: every frame, it returns a
``(direction, speed)`` that drives the body's ``steer``. This module
holds the background patterns (``orbit``, ``strafe``, ``retreat``,
``hover``, ``reposition``, ``proud_walk``, ``spin_glide``, ``lunge``,
``erratic_step``, ``trap_and_shift``, plus the Wasp's flight shapes
``dive_arc`` / ``flyby`` / ``climb_out`` / ``curve_approach``),
sibling to ``PATTERNS`` in ``patterns.py``.

Two bindings, with precedence **attack > phase > none**:

- **By phase** -- each phase kit carries a ``moves=[]`` slot. The active
  movement drives the boss when no attack is speaking. Unique per boss:
  A Muralha (``plan='fixed'``) declares ``moves=[]``; Olho-Sismico uses
  ``moves=['hover']`` (the observer); the Wasp (``flying=True``, no
  arena) uses ``['curve_approach','climb_out']`` / ``['dive_arc']`` /
  ``['dive_arc','flyby']`` -- the per-phase binding is its identity;
  Rei Lagarto uses ``moves=['proud_walk']`` (the legibility canonical
  -- #123); Aranha-Rei uses ``['erratic_step', 'trap_and_shift']``;
  Centopeiadeira uses ``['orbit']`` with the remaining attacks
  (spiral/deathroll/pincha/radial) carrying per-attack moves.
- **By attack** -- a ``PATTERNS`` row may carry ``move='orbit'`` /
  ``'strafe'`` / ``'retreat'`` / ``'proud_walk'`` / ``'spin_glide'`` /
  ``'lunge'`` / ``'erratic_step'`` / ``'trap_and_shift'`` / ``'flyby'`` /
  ``'dive_arc'`` / ``None``. Movement glued to that attack. Unique per
  attack. Charge / burrow / grapple keep vetoing everything (their own
  state machines own the motion).

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

State the function may need (``committed_dir`` and similar) lives on the
``BossAI`` instance, not in module globals -- two bosses of the same
kind would stomp each other's state otherwise.

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


# --------------------------------------------------------------------------- #
#  Centopeiadeira (issue #124) -- per-attack moves glued to the attacks that   #
#  remain. Burrow IS the locomotion (veto per #118); these are the moves the  #
#  body uses while the OTHER patterns (spiral / pincha / radial / deathroll)  #
#  are in windup or recover -- per-attack binding from #118. The boss's long  #
#  segmented body reads as part of the bullet pattern when it spins, so the   #
#  movement is the bullets, in practice.                                       #
# --------------------------------------------------------------------------- #

def move_spin_glide(boss, game, target, dials):
    """Centopeiadeira: glide toward the target with a sin-wave perpendicular
    oscillation. The spiral/deathroll pattern fires from a body that is
    CURVING through space; the perpendicular wobble is what makes the spiral
    read as emitted-from-a-moving body instead of emitted-from-a-stationary
    spinner (the frozen-fight case the no-coil check from #118 catches).

    The phase of the oscillation rides ``boss.wobble`` (the per-creature
    clock the oscillators already read) so the body keeps its rate across
    phases -- phase 3 is the same machine running faster, not a different
    gait.
    """
    if target is None:
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return Vector2(1, 0), 0.0
    rim = safe_norm(to)
    perp = Vector2(-rim.y, rim.x)
    # amplitude ~0.3 of base speed; period via wobble (every creature has its own)
    amp = 0.32 * math.sin(boss.wobble * 1.6)
    v = rim + perp * amp
    if v.length_squared() < 1e-4:
        return rim, 0.0
    return v.normalize(), 0.7


def move_lunge(boss, game, target, dials):
    """Centopeiadeira: short forward commit on the bite windup, then stop.

    The lunge fires only while the FSM is in ``windup`` -- the body leans
    into the bite's reach. During recover the lunge releases (returns 0),
    so the body doesn't keep driving forward after contact. Outside an
    active windup the move is silent.
    """
    if target is None:
        return Vector2(), 0.0
    ai = getattr(boss, 'boss_ai', None)
    if ai is None or ai.state != 'windup':
        return Vector2(), 0.0
    to = target.pos - boss.pos
    if to.length_squared() < 1e-4:
        return Vector2(1, 0), 0.0
    return safe_norm(to), 0.85


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
    'orbit':           move_orbit,
    'strafe':          move_strafe,
    'retreat':         move_retreat,
    'hover':           move_hover,
    'reposition':      move_reposition,
    'proud_walk':      move_proud_walk,
    'dive_arc':        move_dive_arc,
    'flyby':           move_flyby,
    'climb_out':       move_climb_out,
    'curve_approach':  move_curve_approach,
    'spin_glide':      move_spin_glide,
    'lunge':           move_lunge,
    'erratic_step':    move_erratic_step,
    'trap_and_shift':  move_trap_and_shift,
}
