"""The boss FSM: intro -> [approach -> windup -> attack -> recover] x N ->
phase transition -> ... -> death.

Consumes ``patterns`` and ``personality``; neither may import this module.
"""

import math
import random
import pygame
from pygame import Vector2

from ...core import config as C
from ...core import palette
from ...creatures.ai import burrow as burrow_ai
from ...creatures.ai import grapple as grapple_ai
from ...core.mathutil import safe_norm, vfrom_angle, clamp, decay, random_dir, approach
from ...creatures.base import TAIL_SPRING_STIFFNESS
from ...combat.emitter import _tick_barrage, _tick_spiral, _tick_fire_breath
from .patterns import PATTERNS, default_phases
from .telegraph import TELEGRAPHS
from .personality import default_personality
from .moves import MOVES
from .arena import clamp_to_anchor

# --- #13 body telegraph: spring-driven tells fired DURING the windup. Each
# scales with windup progress (0->1) and the mood's speed (angrier = snappier),
# and biases a spring the body already animates -- nothing raw, nothing new to
# draw. These are the tuning knobs. ---
TELL_TAIL_RAISE = 1.1      # shockwave: extra tail-spring stiffness (x baseline)
TELL_CREST_BRISTLE = 14.0  # radial: degrees of plate/horn bristle at full kick
TELL_CREST_ENRAGED = 6.0   # steady crest bristle whenever enraged (x mood_speed)
TELL_REAR_UP = 0.45        # summon: squat_bias rise -- head tilts back / rears up
TELL_CROUCH = 0.4          # charge: squat_bias drop -- body lowers & squashes

# --------------------------------------------------------------------------- #
#  Rei Lagarto (plans/03, first authored boss, onda 5): CicatriZ mechanic --   #
#  every 25% HP lost, a scarred patch (slow + tick damage) appears on the     #
#  boss's recent path (issue #123), so the puddle is area denial that          #
#  interacts with his movement instead of decoration underfoot. Cleared at     #
#  phase transition.                                                          #
# --------------------------------------------------------------------------- #

# How many frames of the boss's recent path ``spawn_scar`` may sample
# from. The ring buffer ``BossAI._path_samples`` grows up to this length;
# picking from it (instead of ``boss.pos + random_dir(...)``) means the
# puddle lands where the boss was walking, not in a random radius
# around where he stands.
KING_SCAR_PATH_WINDOW = 30


def spawn_scar(boss, game):
    from ...combat import weapons
    # Issue #123: with movement, the puddle lands on the boss's RECENT
    # PATH, not at a random underfoot position. The ring buffer is
    # filled by ``BossAI.tick`` every frame; if it's empty (the very
    # first scar before the boss has walked anywhere) fall back to
    # the legacy underfoot placement so the mechanic still works on
    # spawn.
    ai = boss.boss_ai
    samples = getattr(ai, '_path_samples', None) if ai is not None else None
    if samples:
        chosen = random.choice(samples)
        pos = Vector2(chosen)
    else:
        chosen = None
        pos = boss.pos + random_dir(boss.max_r * 0.6)
    p = weapons.Puddle(pos, boss.max_r * 0.9, C.KING_SCAR_DMG, C.KING_SCAR_LIFE,
                       22, hostile=True, tick=0.5,
                       slow=(C.KING_SCAR_SLOW, C.KING_SCAR_TIME))
    # Snapshot the path buffer at spawn time so a check can verify the
    # puddle landed on a position the boss actually occupied. The buffer
    # itself rolls forward (oldest frame is popped), so without the
    # snapshot the verification would race against the buffer's
    # evolution.
    p._scar_path_snapshot = list(samples) if samples else []
    p._scar_path_pos = Vector2(pos) if chosen is None else Vector2(chosen)
    game.spawn_puddle(p)
    game.fx.burst(pos, (150, 90, 50), 10, 140)
    return p


# --------------------------------------------------------------------------- #
#  The FSM itself                                                             #
# --------------------------------------------------------------------------- #

class BossAI:
    def __init__(self, boss, phases=None, personality=None, name=None, on_phase=None,
                 invuln_states=None):
        self.boss = boss
        self.phases = phases or default_phases()
        self.personality = personality or default_personality()
        self.name = name
        self.on_phase = on_phase   # optional (boss, phase_i, game) hook -- per-boss mechanics
        # Issue #121: extra FSM states during which ``boss.boss_invuln`` is
        # True. Empty by default (intro + transition are already invulnerable);
        # a Muralha declares ``('attack', 'recover')`` so the windup stays
        # punishable but the gap after the strike is not. ``windup`` is
        # FORBIDDEN to appear here -- the windup is the player's only DPS
        # window.
        self.invuln_states = frozenset(invuln_states or ())
        self.phase_i = 0
        self.state = 'intro'
        self.t = C.BOSS_INTRO_TIME
        # Issue #118: initial cd uses the same MIN..MAX window as the rest of
        # the cycle (NOT floored) -- the floor protects against later cycles
        # that hit zero, not against the very first one. The actual fight
        # cadence lands on the floor within one or two attacks anyway.
        self.cd = random.uniform(C.BOSS_CD_MIN, C.BOSS_CD_MAX)
        self.pattern_id = None
        self.summon_cd = 0.0
        self.mood = 'calm'
        self.no_hit_t = 0.0        # time since this boss last connected -- frustration
        self.scar_thresholds = None   # e.g. [0.75, 0.5, 0.25] -- opt-in (Rei Lagarto)
        self.scars = []
        # Issue #123: ``proud_walk`` keeps a committed direction and a
        # timer on the BossAI so the move never reverses (a sign flip
        # would read as retreat). Seeded empty; the first call to
        # ``move_proud_walk`` initialises from the line to the target.
        self._pw_dir = Vector2()
        self._pw_t = 0
        # Issue #123: ring buffer of recent boss positions. ``spawn_scar``
        # picks from this buffer so the CicatriZ puddle lands where the
        # boss WAS in the last ~30 frames, not at a random spot near
        # its current position. The trail makes the puddle interact
        # with the boss's movement; without movement, the puddle is
        # decoration.
        self._path_samples = []   # list[Vector2], newest at the end
        # Issue #162: per-instance cache of the merged dials for the
        # ACTIVE pattern (``PATTERNS[pid]`` shallow-merged with the
        # current phase's ``pattern_dials`` override). Built once at
        # pattern pick time so the windup, the telegraph draw, the
        # move binding and the fire call all see the same effective
        # dict -- the override never drifts between what the
        # telegraph draws and what fires at fire time. ``None`` when
        # no pattern is in flight.
        self.pattern_dials = None
        boss.boss_invuln = True
        self._last_game = None      # back-ref the per-frame hook keeps for on_phase

    def _apply_invuln(self):
        """Single source of truth for ``boss_invuln``. Called at every state
        change so we never accumulate stale flags when the FSM transitions
        and never set invuln on a state the per-boss slot wouldn't agree
        with. Issue #121: a Muralha's ``invuln_states={'attack','recover'}``
        keeps the windup punishable (the player's DPS window) but makes the
        gap right after a strike invulnerable (the boss's authored "can't be
        interrupted while it's recovering" slot).
        """
        self.boss.boss_invuln = (
            self.state in ('intro', 'transition')
            or self.state in self.invuln_states
        )

    def phase(self):
        return self.phases[self.phase_i]

    def _maybe_advance_phase(self):
        b = self.boss
        frac = b.hp / max(1, b.max_hp)
        while self.phase_i + 1 < len(self.phases) and frac <= self.phases[self.phase_i + 1]['hp_frac']:
            self.phase_i += 1
            self.state = 'transition'
            self.t = C.BOSS_TRANSITION_TIME
            self._apply_invuln()              # 'transition' is in the always-invuln set
            b.hit_flash = 1.0
            self.pattern_id = None
            # Issue #162: drop the cached dials so the next pattern pick
            # rebuilds them against the NEW phase's ``pattern_dials``
            # override (a phase transition is the only moment the
            # override set changes for an in-flight fight).
            self.pattern_dials = None
            if self.scars:                     # scars don't survive a phase change
                for s in self.scars:
                    s.dead = True
                self.scars = []
            if self.on_phase:
                # Backward compat: callbacks written before #121 take
                # (boss, phase_i). Callbacks written for arena shrinkage
                # take (boss, phase_i, game). Try the 3-arg form first;
                # fall back if a legacy on_phase didn't get updated.
                try:
                    self.on_phase(b, self.phase_i, self._last_game)
                except TypeError:
                    self.on_phase(b, self.phase_i)

    def _update_mood(self, dt, target):
        if target is None:
            self.mood = 'calm'
            return
        self.no_hit_t += dt
        dist = target.pos.distance_to(self.boss.pos)
        frac = self.boss.hp / max(1, self.boss.max_hp)
        if dist < C.BOSS_CORNERED_DIST:
            self.mood = 'cornered'
        elif frac < 0.33:
            self.mood = 'enraged'
        elif frac < 0.66:
            self.mood = 'agitated'
        elif self.no_hit_t > C.BOSS_FRUSTRATION_SEC:
            self.mood = 'frustrated'
        else:
            self.mood = 'calm'

    def _choose_pattern(self, pats):
        weights = [self.personality.weight(p, self.mood) for p in pats]
        return random.choices(pats, weights=weights, k=1)[0]

    def _roll_cd(self):
        """Cooldown between attacks, with the global floor.

        The default ``BOSS_CD_MIN``/``BOSS_CD_MAX`` collapsed to near zero
        so the per-boss ``cd_mul`` carries the rhythm signature. The
        ``BOSS_CD_FLOOR`` keeps a 0 ``cd_mul`` (or a tiny one) from making
        the boss spell out bullets illegibly.

        Per-phase ``cd_jitter`` (#125) widens the cd **above** the floor:
        the boss draws from ``[floor, floor + BOSS_CD_MAX * cd_mul]`` (no
        jitter so the lower half coincides with the floor), then multiplies
        by ``uniform(1 - jitter, 1 + jitter)``. The floor protects
        legibility against an unlucky zero; above the floor the rhythm is
        the persona's signature -- Aranha-Rei's 1.0 lands cds across
        [~0.15, ~0.40] s in calm and a tighter band in enraged, which is
        how she stays the LEAST regular boss in ``BOSS_POOL``. A boss with
        cd_jitter unset (default) rides the floor on every cycle: same as
        before #125, just a tighter band on top.
        """
        cd_mul = self.phase()['cd_mul']
        jitter = self.phase().get('cd_jitter', 0.0) or 0.0
        if jitter > 0:
            cd_base = C.BOSS_CD_FLOOR + random.uniform(0.0, C.BOSS_CD_MAX * cd_mul)
            cd = cd_base * random.uniform(1.0 - jitter, 1.0 + jitter)
        else:
            cd = random.uniform(C.BOSS_CD_MIN, C.BOSS_CD_MAX) * cd_mul
        return max(C.BOSS_CD_FLOOR, cd)

    def _eff_windup(self, pid):
        """Effective windup for ``pid``, clamped to the 27-frame floor.

        The floor is the 27-frame rule (0.45s at SIM_HZ=60) made code; a
        mood multiplier cannot drag a real telegraph below it. Burrow and
        grapple are exempt (``telegraph=None`` -- their body IS the tell).
        """
        pat = PATTERNS.get(pid, {})
        if pat.get('telegraph') is None:
            return pat.get('windup', C.BOSS_WINDUP_FLOOR)
        base = pat.get('windup', 0.0) * self.personality.windup_mult(self.mood)
        return max(C.BOSS_WINDUP_FLOOR, base)

    def _eff_recover(self, pid):
        """Per-pattern recover duration; the default lives in config."""
        pat = PATTERNS.get(pid, {})
        return pat.get('recover', C.BOSS_RECOVER_TIME)

    def _effective_dials(self, pid):
        """``PATTERNS[pid]`` shallow-merged with the current phase's
        ``pattern_dials`` override (issue #162).

        The phase kit may declare ``pattern_dials={pid: {...}}`` to bump
        count / spread / shots / turn / gap for that phase without
        mutating the shared ``PATTERNS`` table. The merge happens at
        pattern pick time and the result is cached in ``self.pattern_dials``;
        every FSM read (windup, select, fire, move binding, telegraph draw)
        goes through the cached dict, so what the telegraph draws and
        what the emitter fires are always the same.

        Returns ``PATTERNS[pid]`` unchanged when the phase has no
        override for ``pid`` -- the common case (including every boss
        that doesn't opt into the override) so the rest of the FSM
        keeps the cheap path.
        """
        base = PATTERNS.get(pid, {})
        override = self.phase().get('pattern_dials', {}).get(pid)
        if not override:
            return base
        return {**base, **override}

    def _move(self, target, game):
        """The movement trail: ``(direction, speed)`` for the current frame.

        Precedence (issue #118): attack > phase > none.

        - If the active pattern has a ``move`` binding, it wins.
        - Else the phase kit's ``moves`` slot drives the boss. A list of
          moves is tried in order (issue #122); the first that returns a
          non-zero speed drives the boss. ``dive_arc`` only animates
          during its own windup, so a kit with ``moves=['dive_arc',
          'flyby']`` falls through to flyby whenever the dive isn't on.
        - Else the default ``reposition`` (move toward the target) takes over.

        Mood speed multiplies the result everywhere. The arena (when
        present) is the hard wall: an intended move that would step
        outside the box is re-pointed at the box's centre. ``Lizard.integrate``
        also clamps, so this is a one-line guard against the boss painting
        the corner of the arena with ghost moves.
        """
        mood_speed = self.personality.mood_speed.get(self.mood, 1.0)
        b = self.boss
        # active attack's move (may be None if the pattern doesn't override)
        # Issue #162: read from the cached dials (PATTERNS + phase override
        # merged) so the move binding sees the same dial set the fire call
        # saw -- a future override that changes move-relevant fields
        # (reach, etc.) reaches the move fn automatically.
        if self.pattern_id:
            pat = self.pattern_dials if self.pattern_dials is not None \
                else PATTERNS.get(self.pattern_id, {})
            mv = pat.get('move')
            if mv and mv in MOVES:
                d, s = MOVES[mv](b, game, target, pat)
                d, s = clamp_to_anchor(b.pos, d, s, b.max_r, game.arena_bounds)
                return d, s * mood_speed
        # phase's moves (the BACKGROUND between attacks). The list is tried
        # in order -- the first non-zero wins, so a Wasp kit that says
        # ['dive_arc','flyby'] uses the dive only during its windup and
        # flyby for the rest.
        phase = self.phase()
        for mv in (phase.get('moves') or []):
            if mv in MOVES:
                d, s = MOVES[mv](b, game, target, phase)
                if s > 0:
                    d, s = clamp_to_anchor(b.pos, d, s, b.max_r, game.arena_bounds)
                    return d, s * mood_speed
        # none: default approach (move toward target at approach speed)
        if target is None:
            return Vector2(), 0.0
        d = safe_norm(target.pos - b.pos)
        d, s = clamp_to_anchor(b.pos, d, C.BOSS_APPROACH_SPEED, b.max_r, game.arena_bounds)
        return d, s * mood_speed

    def tick(self, dt, game):
        b = self.boss
        self._last_game = game      # issue #121: back-ref for on_phase(game)
        game.dt_last = dt          # aimed_barrage's/spiral's per-frame tick reads this
        _tick_barrage(b, game)
        _tick_spiral(b, game)
        _tick_fire_breath(b, game)
        self.summon_cd = decay(self.summon_cd, dt)
        self._maybe_advance_phase()
        # Issue #165: ANKH phase ghosts cross-fade. The on_phase callback
        # (ankh_on_phase) sets each phantom's target_alpha on transition;
        # this advances the visible alpha toward it every frame so the
        # swap reads as a 1.5-second cross-fade, not a blink. rate=2.0
        # is 90% in ~1.15s and 95% in ~1.5s at 60Hz. Empty list = no-op.
        if b.phantom_bodies:
            for p in b.phantom_bodies:
                p.alpha = approach(p.alpha, p.target_alpha, 2.0, dt)
        # Issue #123: ring buffer of recent boss positions for the
        # CicatriZ puddle. Sampling the buffer at ``spawn_scar`` time
        # means the puddle lands where the boss WAS walking (the trail
        # of his movement), not at a random underfoot position. The
        # buffer caps at ``KING_SCAR_PATH_WINDOW`` so a long fight
        # doesn't grow it unbounded.
        samples = self._path_samples
        if len(samples) >= KING_SCAR_PATH_WINDOW:
            samples.pop(0)
        samples.append(Vector2(b.pos))
        if self.scar_thresholds:
            frac = b.hp / max(1, b.max_hp)
            while self.scar_thresholds and frac <= self.scar_thresholds[0]:
                self.scar_thresholds.pop(0)
                self.scars.append(spawn_scar(b, game))
        target = game.nearest_player(b.pos)
        self._update_mood(dt, target)
        if target is None:
            return Vector2(), 0.0

        if self.state == 'intro':
            self.t -= dt
            if self.t <= 0:
                self.state = 'approach'
                self._apply_invuln()           # 'approach' is no longer invuln
            return Vector2(), 0.0

        if self.state == 'transition':
            self.t -= dt
            if self.t <= 0:
                self.state = 'approach'
                self._apply_invuln()           # 'approach' is no longer invuln
                self.cd = self._roll_cd()
                # Issue #122: phase change invalidates a snapshot dive
                # start (the new phase's dives begin fresh from the new
                # position). Without clearing, a transition mid-dive
                # would carry the stale start into the next phase.
                if getattr(b, '_dive_start', None) is not None:
                    b._dive_start = None
            return safe_norm(target.pos - b.pos) * 0.1, 0.15

        to = safe_norm(target.pos - b.pos)
        dist = target.pos.distance_to(b.pos)

        if self.state == 'approach':
            self.cd -= dt
            if self.cd <= 0:
                pats = list(self.phase()['patterns'])
                if 'summon' in pats and self.summon_cd > 0:
                    pats.remove('summon')          # on cooldown -- don't roll it
                pid = self._choose_pattern(pats) if pats else 'fan'
                self.pattern_id = pid
                # Issue #162: cache PATTERNS[pid] merged with the current
                # phase's ``pattern_dials`` override, once. Every FSM
                # read downstream (windup, select, fire, move binding,
                # telegraph draw) goes through this dict so the override
                # never drifts between what the telegraph draws and what
                # the emitter fires. Falls through to PATTERNS[pid] for
                # bosses that don't opt in (the common case).
                self.pattern_dials = self._effective_dials(pid)
                self.state = 'windup'
                # Issue #118: windup floor (0.45s, the 27-frame rule). The
                # clamp lives in _eff_windup, applied via the FSM so any
                # future mood multiplier respects the same floor.
                self.t = self._eff_windup(pid)
                self._windup_target = Vector2(target.pos)
                # Issue #122: snapshot the dive's start point so the
                # Bezier the wasp flies is anchored to where the dive
                # BEGAN (not where the boss is mid-windup). Without this
                # the dive_arc movement would re-sample every frame and
                # the wasp would arc around its current self, not its
                # original line of attack.
                if pid == 'dive_arc':
                    b._dive_start = Vector2(b.pos)
                select = self.pattern_dials.get('select')
                if select:
                    select(b, game, target, self.pattern_dials)
            # Movement trail: attack > phase > none. The approach vector
            # was the only "movement" before; now the phase's moves slot
            # drives the boss (the per-boss signatures (#121-#125) fill
            # in the rich moves).
            return self._move(target, game)

        if self.state == 'windup':
            self.t -= dt
            b.squat_bias = 0.85     # coiling for whatever's coming -- same
                                    # anticipation hook regular AI wind-ups use
            # Issue #118: fan/line telegraphs re-aim live. The other kinds
            # (radial, shockwave, spiral, horn) read the boss's own joints
            # live and stay honest to the boss's position; fan/line used
            # to freeze the aim at windup start, which made a walking
            # boss draw a cone that rotated while the shot left from the
            # new position. Now the aim tracks the player each frame.
            # Issue #162: read from the cached ``pattern_dials`` so a
            # ``pattern_dials`` override reaches the telegraph too.
            if self.pattern_id:
                pat = self.pattern_dials if self.pattern_dials is not None \
                    else PATTERNS[self.pattern_id]
                if pat.get('telegraph') in ('fan', 'line'):
                    self._windup_target = Vector2(target.pos)
            if self.t <= 0:
                pat = self.pattern_dials if self.pattern_dials is not None \
                    else PATTERNS[self.pattern_id]
                # Issue #122: the dive windup ended -- the dive Bezier
                # is done, clear the snapshot so a subsequent windup
                # snapshots its OWN start. The wasp stays past the
                # player; the phase's moves list drives the rest.
                if self.pattern_id == 'dive_arc' and getattr(b, '_dive_start', None) is not None:
                    b._dive_start = None
                if pat.get('burrow'):
                    self.state = 'burrowing'
                    self._burrow_seen_under = False
                    return Vector2(), 0.0
                if pat.get('grapple'):
                    self.state = 'grappling'
                    self._grapple_seen_windup = False
                    return Vector2(), 0.0
                pat['fn'](b, game, target, pat)   # the row IS the emitter's dials
                b.squat_bias = 1.4   # release the coil
                if self.pattern_id == 'summon':
                    self.summon_cd = C.BOSS_SUMMON_CD
                if pat.get('charge'):
                    self.state = 'charging'
                    self.t = C.BOSS_CHARGE_TIME
                else:
                    self.state = 'recover'
                    self.t = self._eff_recover(self.pattern_id)
                self._apply_invuln()   # 'recover' may now be invuln (Muralha)
            # Movement trail: the active pattern's move (if any) overrides
            # the phase's. charge/burrow/grapple already returned above.
            return self._move(target, game)

        if self.state == 'burrowing':
            # Issue #124: burrow IS the locomotion. Per the precedence from #118,
            # burrow vetoes the movement trail -- its state machine owns the
            # motion. The full surface -> dig -> under -> erupt -> surface
            # cycle is one continuous beat of the boss's body, and the
            # position updates every frame (the under segment travels to
            # ``dive_to`` at the body's speed; the surface segment walks
            # toward the target). What burrow adds on top of movement is the
            # recognition that the under segment is the BODY MOVING THROUGH
            # THE DIRT, not "standing still underground" -- and it is also
            # the invulnerability window (``hit_test`` returns ``None`` while
            # ``burrowed``), emergent from movement, not authored. No new
            # window; the existing one is paid for with locomotion.
            d, speed = burrow_ai.burrow_tick(b, game, dt, target)
            if b.burrow_state == 'under':
                self._burrow_seen_under = True
            elif self._burrow_seen_under and b.burrow_state == 'surface':
                self.state = 'recover'
                self.t = self._eff_recover('burrow')
                self._apply_invuln()
            return d, speed

        if self.state == 'grappling':
            # delegates every frame to the regular octopus's OWN reach/snap
            # cycle (creatures/ai/grapple) -- one windup-to-snap(or-miss)
            # cycle, then back to the normal pattern rotation
            d, speed = grapple_ai.grapple_tick(b, game, dt, target)
            if b.grapple_t > 0:
                self._grapple_seen_windup = True
            elif self._grapple_seen_windup:
                self.state = 'recover'
                self.t = self._eff_recover('grapple')
                self._apply_invuln()
            return d, speed

        if self.state == 'charging':
            self.t -= dt
            if dist < (b.max_r + target.max_r) * 1.1 and b.attack_cd <= 0:
                b._contact(game, target)
                self.no_hit_t = 0.0
            if self.t <= 0:
                self.state = 'recover'
                self.t = self._eff_recover('charge')
                self._apply_invuln()
                return Vector2(), 0.0
            return getattr(b, '_charge_dir', to), C.BOSS_CHARGE_SPEED_MULT

        if self.state == 'recover':
            self.t -= dt
            if self.t <= 0:
                self.state = 'approach'
                self._apply_invuln()        # 'approach' clears the recover invuln
                self.cd = self._roll_cd()
            # Movement trail: phase's move drives the boss during recover.
            return self._move(target, game)

        return Vector2(), 0.0

    def apply_body_tell(self, dt):
        """#13: spring-driven body telegraph during the windup. Biases the SAME
        cosmetic springs the body already animates (tail stiffness, plate/horn
        crest bristle, squat_bias) so each pattern reads distinctly BEFORE it
        fires; magnitude scales with windup progress and the mood's speed. Runs
        once per frame AFTER ``_apply_mood_pose`` so a shockwave tail-raise wins
        over the mood baseline. Guards a body with no tail/crests by skipping
        that channel (the bias just no-ops if the genome draws none)."""
        b = self.boss
        speed = self.personality.mood_speed.get(self.mood, 1.0)
        # enraged bosses bristle their crests all the time, not just on radial
        b.crest_bias = TELL_CREST_ENRAGED * speed if self.mood == 'enraged' else 0.0
        if self.state != 'windup' or not self.pattern_id:
            return
        # Issue #162: read from the cached ``pattern_dials`` (PATTERNS +
        # phase override merged) so body-tell and emitter both see the
        # same kind / dial set.
        pat = self.pattern_dials if self.pattern_dials is not None \
            else PATTERNS[self.pattern_id]
        # issue #118: progress is computed against the FLOORED windup to
        # match the FSM's countdown -- a pattern clamped to 0.45s reports
        # prog 0->1 across exactly 0.45s, not the table value
        windup = self._eff_windup(self.pattern_id)
        prog = 1.0 - clamp(self.t / max(1e-4, windup), 0, 1)   # 0 -> 1
        kick = clamp(prog, 0, 1) * speed
        if pat.get('charge'):
            b.squat_bias = 1.0 - TELL_CROUCH * kick            # lower & squash
        elif pat['telegraph'] == 'shockwave':
            if b.tail_spring is not None:                      # tail raises
                b.tail_spring.stiffness = TAIL_SPRING_STIFFNESS * (1.0 + TELL_TAIL_RAISE * kick)
        elif pat['telegraph'] == 'radial':
            b.crest_bias += TELL_CREST_BRISTLE * kick          # crests bristle
        elif pat['telegraph'] == 'horn':                       # summon
            b.squat_bias = 1.0 + TELL_REAR_UP * kick           # head tilts back / rears

    # ---- drawing: the telegraph IS the pattern's real hitbox preview ------- #
    def draw(self, surf, cam):
        b = self.boss
        base_color = self.personality.glow_color(self.mood, b.color)
        if self.state == 'intro' or self.state == 'transition':
            f = clamp(self.t / (C.BOSS_INTRO_TIME if self.state == 'intro'
                                 else C.BOSS_TRANSITION_TIME), 0, 1)
            sp = cam.w2s(b.pos)
            col = palette.lighten(base_color, 0.5)
            palette.glow(surf, sp, int(b.max_r * (2.2 + 1.4 * f) * cam.zoom), col, 0.35 + 0.25 * f)
            return
        if self.state == 'charging':
            sp = cam.w2s(b.spine.joints[0])
            aim = b.spine.joints[0] + getattr(b, '_charge_dir', Vector2(1, 0)) * 260
            col = palette.lighten(base_color, 0.4)
            pygame.draw.line(surf, col, sp, cam.w2s(aim), max(1, int(3 * cam.zoom)))
            return
        if self.state != 'windup' or not self.pattern_id:
            return
        # Issue #162: read from the cached ``pattern_dials`` (PATTERNS +
        # phase override merged) so the drawn telegraph kind matches the
        # emitter call below.
        pat_row = self.pattern_dials if self.pattern_dials is not None \
            else PATTERNS[self.pattern_id]
        kind = pat_row['telegraph']



        # None telegraph kind (burrow, grapple) -> the boss's own body already
        # shows the windup via its own tick (dig state, arms converging). No
        # on-screen telegraph to draw here.
        if kind is None:
            return
        # issue #118: progress matches the FSM's countdown (floored windup)
        windup_dur = self._eff_windup(self.pattern_id)
        prog = 1.0 - clamp(self.t / max(1e-4, windup_dur), 0, 1)   # 0 -> 1
        # blink pulses faster as prog approaches 1 -- the "any moment now" cue
        blink = 0.5 + 0.5 * math.sin(prog * prog * 40)
        col = palette.lighten(base_color, 0.35)
        # Issue #27: dispatch to the per-kind drawer in telegraph.py. Adding a
        # new telegraph kind = adding a function + a registry entry, not
        # editing this method.
        fn = TELEGRAPHS.get(kind)
        if fn is not None:
            fn(surf, cam, b, self, prog, col, blink)

