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
from ...core.mathutil import safe_norm, vfrom_angle, clamp, decay, random_dir
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
#  every 25% HP lost, a scarred patch (slow + tick damage) appears underfoot;  #
#  it clears whenever the fight moves to the next phase.                      #
# --------------------------------------------------------------------------- #

def spawn_scar(boss, game):
    from ...combat import weapons
    pos = boss.pos + random_dir(boss.max_r * 0.6)
    p = weapons.Puddle(pos, boss.max_r * 0.9, C.KING_SCAR_DMG, C.KING_SCAR_LIFE,
                       22, hostile=True, tick=0.5,
                       slow=(C.KING_SCAR_SLOW, C.KING_SCAR_TIME))
    game.spawn_puddle(p)
    game.fx.burst(pos, (150, 90, 50), 10, 140)
    return p


# --------------------------------------------------------------------------- #
#  The FSM itself                                                             #
# --------------------------------------------------------------------------- #

class BossAI:
    def __init__(self, boss, phases=None, personality=None, name=None, on_phase=None):
        self.boss = boss
        self.phases = phases or default_phases()
        self.personality = personality or default_personality()
        self.name = name
        self.on_phase = on_phase   # optional (boss, phase_i) hook -- per-boss mechanics
        self.phase_i = 0
        self.state = 'intro'
        self.t = C.BOSS_INTRO_TIME
        self.cd = random.uniform(C.BOSS_CD_MIN, C.BOSS_CD_MAX)
        self.pattern_id = None
        self.summon_cd = 0.0
        self.mood = 'calm'
        self.no_hit_t = 0.0        # time since this boss last connected -- frustration
        self.scar_thresholds = None   # e.g. [0.75, 0.5, 0.25] -- opt-in (Rei Lagarto)
        self.scars = []
        boss.boss_invuln = True

    def phase(self):
        return self.phases[self.phase_i]

    def _maybe_advance_phase(self):
        b = self.boss
        frac = b.hp / max(1, b.max_hp)
        while self.phase_i + 1 < len(self.phases) and frac <= self.phases[self.phase_i + 1]['hp_frac']:
            self.phase_i += 1
            self.state = 'transition'
            self.t = C.BOSS_TRANSITION_TIME
            b.boss_invuln = True
            b.hit_flash = 1.0
            self.pattern_id = None
            if self.scars:                     # scars don't survive a phase change
                for s in self.scars:
                    s.dead = True
                self.scars = []
            if self.on_phase:
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
        """
        cd_raw = random.uniform(C.BOSS_CD_MIN, C.BOSS_CD_MAX) * self.phase()['cd_mul']
        return max(C.BOSS_CD_FLOOR, cd_raw)

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

    def _move(self, target, game):
        """The movement trail: ``(direction, speed)`` for the current frame.

        Precedence (issue #118): attack > phase > none.

        - If the active pattern has a ``move`` binding, it wins.
        - Else the phase kit's ``moves`` slot drives the boss.
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
        if self.pattern_id:
            pat = PATTERNS.get(self.pattern_id, {})
            mv = pat.get('move')
            if mv and mv in MOVES:
                d, s = MOVES[mv](b, game, target, pat)
                d, s = clamp_to_anchor(b.pos, d, s, b.max_r, game.arena_bounds)
                return d, s * mood_speed
        # phase's move (the BACKGROUND between attacks)
        phase = self.phase()
        moves = phase.get('moves') or []
        if moves:
            mv = moves[0]
            if mv in MOVES:
                d, s = MOVES[mv](b, game, target, phase)
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
        game.dt_last = dt          # aimed_barrage's/spiral's per-frame tick reads this
        _tick_barrage(b, game)
        _tick_spiral(b, game)
        _tick_fire_breath(b, game)
        self.summon_cd = decay(self.summon_cd, dt)
        self._maybe_advance_phase()
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
                b.boss_invuln = False
            return Vector2(), 0.0

        if self.state == 'transition':
            self.t -= dt
            if self.t <= 0:
                self.state = 'approach'
                b.boss_invuln = False
                self.cd = self._roll_cd()
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
                self.state = 'windup'
                # Issue #118: windup floor (0.45s, the 27-frame rule). The
                # clamp lives in _eff_windup, applied via the FSM so any
                # future mood multiplier respects the same floor.
                self.t = self._eff_windup(pid)
                self._windup_target = Vector2(target.pos)
                select = PATTERNS[pid].get('select')
                if select:
                    select(b, game, target, PATTERNS[pid])
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
            if self.pattern_id:
                pat = PATTERNS[self.pattern_id]
                if pat.get('telegraph') in ('fan', 'line'):
                    self._windup_target = Vector2(target.pos)
            if self.t <= 0:
                pat = PATTERNS[self.pattern_id]
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
            # Movement trail: the active pattern's move (if any) overrides
            # the phase's. charge/burrow/grapple already returned above.
            return self._move(target, game)

        if self.state == 'burrowing':
            # delegates every frame to the regular centipede's OWN dig/erupt
            # state machine (creatures.ai.burrow) -- one full surface->dig->
            # under->erupt cycle, then back to the normal pattern rotation
            d, speed = burrow_ai.burrow_tick(b, game, dt, target)
            if b.burrow_state == 'under':
                self._burrow_seen_under = True
            elif self._burrow_seen_under and b.burrow_state == 'surface':
                self.state = 'recover'
                self.t = self._eff_recover('burrow')
            return d, speed

        if self.state == 'grappling':
            # delegates every frame to the regular octopus's OWN reach/snap
            # cycle (creatures.ai.grapple) -- one windup-to-snap(or-miss)
            # cycle, then back to the normal pattern rotation
            d, speed = grapple_ai.grapple_tick(b, game, dt, target)
            if b.grapple_t > 0:
                self._grapple_seen_windup = True
            elif self._grapple_seen_windup:
                self.state = 'recover'
                self.t = self._eff_recover('grapple')
            return d, speed

        if self.state == 'charging':
            self.t -= dt
            if dist < (b.max_r + target.max_r) * 1.1 and b.attack_cd <= 0:
                b._contact(game, target)
                self.no_hit_t = 0.0
            if self.t <= 0:
                self.state = 'recover'
                self.t = self._eff_recover('charge')
                return Vector2(), 0.0
            return getattr(b, '_charge_dir', to), C.BOSS_CHARGE_SPEED_MULT

        if self.state == 'recover':
            self.t -= dt
            if self.t <= 0:
                self.state = 'approach'
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
        pat = PATTERNS[self.pattern_id]
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
        kind = PATTERNS[self.pattern_id]['telegraph']
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

