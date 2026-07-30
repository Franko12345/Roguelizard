"""The shared procedural body every lizard is built from.

``Lizard`` wires a Spine to its legs (diagonal gait, radial for spiders, a
metachronal wave for centipedes) plus arms, squash & stretch, hit testing and
all the drawing. ``Player`` and ``AILizard`` reuse it unchanged, so any number
of them can be on screen animating procedurally at once.
"""

import math
import random
from pygame import Vector2
import pygame

from ..core import config as C
from ..core import palette
from . import parts
from .genome import basic_lizard
from ..core.mathutil import clamp, lerp, approach, vfrom_angle, safe_norm, angle_of, decay
from ..anim.spine import Spine, build_radii
from ..anim.leg import Leg
from ..anim.anim import Vector2Spring, SpringDamper

# A3 secondary-motion springs (issue #6). All three are 1D SpringDampers whose
# targets are re-set every sim step from body motion; the GAIN/MAX pairs are the
# tuning knobs -- raw accel/turn-rate are spiky, the spring is what smooths them.
PLATE_TILT_GAIN = 0.012         # forward-accel (px/s^2) -> chevron tilt degrees
PLATE_TILT_MAX = 10.0           # cap so a dash doesn't flip the plates flat
PLATE_SPRING_STIFF = 9.0
PLATE_SPRING_DAMP = 0.9         # returns smoothly to flat when accel stops
HORN_SWAY_GAIN = 0.012          # turn-rate (deg/s) -> horn sway degrees
HORN_SWAY_MAX = 9.0
HORN_SPRING_STIFF = 15.0        # bone-stiff: snaps to the sway and settles fast
HORN_SPRING_DAMP = 0.9
PUPIL_SPRING_STIFF = 7.0        # loose = a subtle drift/lag toward the target
PUPIL_SPRING_DAMP = 0.85

TAIL_SPRING_MAX_LAG = 0.45      # cap on overshoot, as a fraction of max_r -- a
                                # spring's steady-state lag scales with target
                                # speed with no ceiling, so an uncapped spring
                                # turns a dash (or any large jump, e.g. a menu
                                # backdrop lizard being repositioned) into a
                                # tail stretched way past the body's own length
TAIL_SPRING_STIFFNESS = 10.0

# Issue #8 -- the tail is a chain of N springs instead of one, so a sudden stop
# cascades down it rather than moving the whole tail as one lagging unit.
# Stiffness is expressed as a RATIO of the tip spring's, base -> tip, so the tip
# keeps behaving exactly as the old single spring did (ratio 1.0) and everything
# ahead of it is progressively stiffer. Damping falls toward the tip: the base
# settles almost at once, the tip rings on.
TAIL_CHAIN_LEN = 5
TAIL_CHAIN_STIFF_RATIO = [2.4, 1.9, 1.5, 1.2, 1.0]     # base -> tip
TAIL_CHAIN_DAMPING     = [0.90, 0.85, 0.80, 0.75, 0.70]

TAU = C.TAU


class Lizard:
    def __init__(self, pos, kind, scale=1.0, color=None, genome=None):
        self.kind = kind
        self.genome = genome or basic_lizard(scale)
        g = self.genome
        self.scale = g.size
        self.dead = False
        self.pos = Vector2(pos)          # head position (leads the body)
        self.vel = Vector2()
        self.facing = Vector2(1, 0)
        self.color = color or g.color()
        self.squash = 1.0
        self.leg_pull = 1.0      # anticipation hook, twin of squat_bias: < 1 pulls
                                 # legs in toward the body (a real crouch/coil),
                                 # > 1 reaches them out (the launch); same
                                 # decays-on-its-own contract, see integrate()
        self.squat_bias = 1.0    # anticipation hook (plans/01 #8): a caller sets
                                 # this < 1 every frame of its own wind-up window
                                 # (hop/lunge/ranged/dash); integrate() multiplies
                                 # it into the squash TARGET and decays it back to
                                 # 1.0 on its own once the caller stops touching it
                                 # -- composes with the speed-based squash instead
                                 # of fighting it frame-to-frame
        self.wobble = random.uniform(0, TAU)
        self.hit_flash = 0.0
        self.attack_cd = 0.0
        self.on_screen = True
        self.slow_t = 0.0
        self.slow_mul = 1.0

        self.max_speed = 0.0
        self._speed_base = 0.0
        self.rebuild_body(keep_pose=False)
        parts.init_oscillators(self)      # issue #4: one PhaseOscillator per part
        self.accel = 900.0
        self.target_dir = Vector2()
        # Issue #165: ANKH's phase-ghost bodies. Empty by default; only ANKH
        # populates (via ankh_setup). The for-loop in draw() is the only
        # cost when empty -- no surface allocated, no cache touched.
        self.phantom_bodies = []            # list[Phantombody]
        # A3 (#6): plates tilt on accel, horns sway on turns, pupils lag the target.
        self.plate_spring = SpringDamper(0.0, PLATE_SPRING_STIFF, PLATE_SPRING_DAMP)
        self.horn_spring = SpringDamper(0.0, HORN_SPRING_STIFF, HORN_SPRING_DAMP)
        self.pupil_x = SpringDamper(0.0, PUPIL_SPRING_STIFF, PUPIL_SPRING_DAMP)
        self.pupil_y = SpringDamper(0.0, PUPIL_SPRING_STIFF, PUPIL_SPRING_DAMP)
        self.crest_bias = 0.0    # anticipation hook, twin of squat_bias: extra
                                 # degrees added to the plate/horn spring targets
                                 # so crests bristle (boss body-telegraph, #13);
                                 # decays back to 0 on its own in integrate()
        self._prev_vel = Vector2()
        self._prev_heading = angle_of(self.facing)

    def rebuild_body(self, keep_pose=True):
        """Recompute everything derived from the genome -- and nothing else.

        Calling ``__init__`` again also wipes hp, weapons, level, aggro and the
        rest of the run state, which is why ``champions.py`` had to snapshot a
        list of fields around it. Three features need the *body* to follow a
        changed genome while the run continues: the LARVA growing, a champion
        being promoted, and (phase 5) a boss shedding armour between phases. They
        all go through here.

        ``max_speed`` accumulates multipliers from meta-progression and cards, so
        recomputing it from scratch would silently delete them; the ratio against
        ``_speed_base`` is carried across instead.
        """
        g = self.genome
        self.scale = g.size
        plan = getattr(g, 'plan', 'normal')
        if g.radial:                      # spider: compact body, few joints
            n = 3
            maxr = 15 * g.size * g.girth
            link = maxr * 0.7
        elif plan == 'tentacle':          # octopus: small soft mantle + arms
            n = 4
            maxr = 20 * g.size * g.girth
            link = maxr * 0.55
        elif plan == 'segmented':         # centipede: long thin chain of segments
            n = max(10, int(16 * g.size * g.length))
            maxr = 14 * g.size * g.girth
            link = maxr * 1.15
        elif plan == 'orbital':           # eye: a compact near-round sphere + arms
            n = 4
            maxr = 26 * g.size * g.girth
            link = maxr * 0.3             # tiny link so the joints cluster into a ball
        elif plan == 'fixed':             # Muralha: wall - wide, short chain
            n = 5
            maxr = 35 * g.size * g.girth
            link = maxr * 0.8
        else:
            n = max(6, int(11 * g.size * g.length))
            maxr = 17 * g.size * g.girth
            link = maxr * 1.05
        self.max_r = maxr
        head = Vector2(self.spine.joints[0]) if (keep_pose and hasattr(self, 'spine')) \
            else Vector2(self.pos)
        self.spine = Spine(head, n, link, build_radii(n, maxr), bend=26)
        self.spine.resolve(head)
        if plan == 'normal':
            js = self.spine.joints
            if keep_pose and getattr(self, 'tail_chain', None):
                # keep momentum across a rebuild: re-aim each link at its joint
                # in the NEW spine instead of snapping to a fresh pose.
                for i, s in enumerate(self.tail_chain):
                    s.target = js[max(0, len(js) - TAIL_CHAIN_LEN + i)]
            else:
                self.tail_chain = [
                    Vector2Spring(Vector2(js[max(0, len(js) - TAIL_CHAIN_LEN + i)]),
                                  stiffness=TAIL_SPRING_STIFFNESS * TAIL_CHAIN_STIFF_RATIO[i],
                                  damping=TAIL_CHAIN_DAMPING[i])
                    for i in range(TAIL_CHAIN_LEN)]
            # ``tail_spring`` stays the public handle and IS the tip link, so the
            # boss telegraph / mood pose / state posing keep writing one object.
            self.tail_spring = self.tail_chain[-1]
            # forces the stiffness fan-out on the next step (see
            # update_secondary_springs), whatever the chain was rebuilt from
            self._tail_stiff_seen = None
        else:
            self.tail_chain = None
            self.tail_spring = None
            self._tail_stiff_seen = None
        self.legs = self._build_legs(g, n, maxr)
        for leg in self.legs:
            leg.init_foot(self.spine)
        self.arms = self._build_arms(g, maxr) if plan in ('tentacle', 'orbital') else []
        # issue #4: re-seed after a rebuild so a creature that mutates fins or
        # antennae mid-run animates them (existing waves are kept, see init).
        parts.init_oscillators(self)

        base = 165 * (0.85 + 0.4 / g.size) * g.speed
        mult = (self.max_speed / self._speed_base) if self._speed_base else 1.0
        self.max_speed = base * mult
        self._speed_base = base

    def _build_legs(self, g, n, maxr):
        plan = getattr(g, 'plan', 'normal')
        if plan in ('tentacle', 'orbital', 'fixed'):   # arms/tentacles are not IK legs
            return []
        if g.leg_count <= 0:
            return []
        if plan == 'segmented':
            return self._build_centipede_legs(g, n, maxr)
        if g.radial:
            return self._build_radial_legs(g, n, maxr)
        seg = maxr * 1.35 * g.leg_len
        so = maxr * 1.7
        step_len = maxr * 1.5
        pairs = max(1, g.leg_count // 2)
        if pairs == 1:
            fracs = [0.35]
        elif pairs == 2:
            fracs = [0.22, 0.55]
        else:
            fracs = [0.18 + i * (0.52 / (pairs - 1)) for i in range(pairs)]
        legs = []
        for pi, frac in enumerate(fracs):
            idx = max(1, min(n - 2, int(n * frac)))
            fwd_off = maxr * lerp(0.3, -0.2, pi / max(1, pairs - 1))
            legs.append(Leg(idx, -1, so, fwd_off, seg, step_len, 0.14, maxr * 0.9))
            legs.append(Leg(idx, +1, so, fwd_off, seg, step_len, 0.14, maxr * 0.9))
        # diagonal gait: left of a pair steps with the right of the next pair
        for i in range(pairs):
            j = (i + 1) % pairs
            legs[2 * i].partner = legs[2 * j + 1]
            legs[2 * i + 1].partner = legs[2 * j]
        return legs

    def _build_radial_legs(self, g, n, maxr):
        """Spider-style legs: fixed angles around the body, IK reach outward."""
        count = max(4, g.leg_count)
        half = count // 2
        reach = maxr * 2.4 * g.leg_len
        seg = reach * 0.62
        step_len = maxr * 1.15
        idx = max(1, n // 2)
        legs = []
        for k in range(half):
            a = 38 + k * (118 / (half - 1)) if half > 1 else 90    # 38..156 deg
            legs.append(Leg(idx, +1, reach, 0, seg, step_len, 0.12, maxr * 0.7,
                            rest_angle=a, reach=reach))
            legs.append(Leg(idx, -1, reach, 0, seg, step_len, 0.12, maxr * 0.7,
                            rest_angle=-a, reach=reach))
        # opposite legs alternate so it never stands on all/none at once
        h = len(legs) // 2
        for i, leg in enumerate(legs):
            leg.partner = legs[(i + h) % len(legs)]
        return legs

    def _build_centipede_legs(self, g, n, maxr):
        """A short pair on (almost) every segment, phased down the body.

        The point is the *metachronal wave*: partnering each pair with the pair
        two segments back keeps neighbours from planting together, so the many
        tiny legs ripple front-to-back instead of marching in sync.
        """
        seg = maxr * 1.0 * g.leg_len
        so = maxr * 1.25
        step_len = maxr * 1.05
        legs = []
        for idx in range(1, n - 1):
            legs.append(Leg(idx, -1, so, 0.0, seg, step_len, 0.11, maxr * 0.5))
            legs.append(Leg(idx, +1, so, 0.0, seg, step_len, 0.11, maxr * 0.5))
        m = len(legs)
        for i, leg in enumerate(legs):
            leg.partner = legs[(i + 4) % m] if m > 4 else None
        return legs

    def _build_arms(self, g, maxr):
        """Octopus arms: each is a follow-the-leader sub-chain hung off the mantle.

        Not IK legs -- they don't plant. They sway/curl on their own and (in
        ``_resolve_arms``) trail the body, so a moving kraken whips its arms.
        """
        count = max(4, g.leg_count or 6)
        ajoints = 10
        link = maxr * 0.68 * g.leg_len
        base = Vector2(self.spine.joints[0])
        arms = []
        for k in range(count):
            arms.append({'a': (360.0 / count) * k,
                         'phase': k * 1.9,
                         'link': link,
                         'j': [Vector2(base) for _ in range(ajoints)]})
        return arms

    def _resolve_arms(self, dt):
        """Curl + trail the octopus arms. Each joint eases toward an outward,
        sine-curled target and then re-clamps to the link length, so the chain
        stays taut but whips when the body moves (soft follow-the-leader)."""
        mantle = self.spine.joints[0]
        base_ang = angle_of(self.spine.head_dir())
        trailing = -safe_norm(self.vel) if self.vel.length_squared() > 400 else Vector2()
        k = min(1.0, 18 * dt)
        # during a grab wind-up the arms all reach toward the target and straighten
        # -- that convergence IS the telegraph (see ai/grapple.py)
        reach = getattr(self, 'arm_target', None)
        reach_ang = angle_of(reach - mantle) if reach is not None else 0.0
        for arm in self.arms:
            js = arm['j']
            link = arm['link']
            if reach is not None:
                anchor_ang = reach_ang + arm['a'] * 0.14      # cluster toward target
                swirl, amp = 7.0, 9.0                          # nearly straight spears
            else:
                anchor_ang = base_ang + arm['a']
                swirl, amp = 24.0, 34.0
            js[0].update(mantle + vfrom_angle(anchor_ang, self.max_r * 1.35))
            m = len(js)
            for i in range(1, m):
                t = i / (m - 1)
                # a wave that travels down the arm (i term) + a constant swirl so
                # even a still arm hooks like a tentacle, not a straight spoke
                # Stays an inline sine: each arm carries its own phase offset
                # INSIDE the sine, and PhaseOscillator's (time, segment) API has
                # nowhere to put it -- sin(a) + sin(b) is not sin(a + b).
                wave = math.sin(self.wobble * 2.4 - i * 0.9 + arm['phase'])
                ang = anchor_ang + (swirl + wave * amp) * t
                desired = js[i - 1] + vfrom_angle(ang, link) + trailing * (link * 0.9 * t)
                js[i] += (desired - js[i]) * k
                off = js[i] - js[i - 1]
                L = off.length()
                if L > 1e-4:
                    js[i] = js[i - 1] + off * (link / L)

    # ---- hit testing ----------------------------------------------------- #
    def body_points(self):
        """Sample points along the spine: [(pos, radius, is_head), ...].

        Damage used to test a single circle at the head, so a 322px snake was only
        ~5% hittable. Same sampling idea as ``collision._samples``.
        """
        js, rs = self.spine.joints, self.spine.radii
        m = len(js)
        idx = sorted({0, m // 4, m // 2, (3 * m) // 4, m - 1})
        return [(js[i], rs[i], i == 0) for i in idx]

    def hit_test(self, pos, radius=0.0):
        """None if it misses; 'head' (weak point) or 'body' if it connects."""
        if getattr(self, 'burrowed', False):     # underground = untouchable
            return None
        if getattr(self, 'boss_invuln', False):  # boss intro / phase transition
            return None
        best = None
        for jp, r, is_head in self.body_points():
            dx = jp.x - pos[0]
            dy = jp.y - pos[1]
            reach = r + radius
            if dx * dx + dy * dy <= reach * reach:
                # Olho-Sismico: a blinking eye is shielded -- the head can't be
                # crit while the membrane is down (default False = every other
                # creature unchanged). The 75%-off is applied in take_hit.
                if is_head and not getattr(self, 'eye_shielded', False):
                    return 'head'            # weak point wins outright
                best = 'body'
        return best

    # ---- status --------------------------------------------------------- #
    def apply_slow(self, mul, dur):
        """Stack a speed multiplier: the strongest source wins, the longest timer wins.

        A boss resists it (issue #119). The cap lives HERE, in the one function
        every source funnels through -- Feromonio, the slow projectile, hostile
        puddles -- because three guards in three callers is how one of them ends
        up forgotten. Clamping each source to the floor is enough: the stack
        combines with ``min``, so the effective multiplier can never dip under it
        either. Not immunity -- slowing a boss still has to be worth building
        for; it just may not switch its movement patterns off.
        """
        if getattr(self, 'is_boss', False):
            mul = max(mul, C.BOSS_SLOW_FLOOR)
            dur *= C.BOSS_SLOW_TIME_MULT
        self.slow_mul = min(self.slow_mul, mul) if self.slow_t > 0 else mul
        self.slow_t = max(self.slow_t, dur)

    def _speed_scale(self):
        return self.slow_mul if self.slow_t > 0 else 1.0

    # ---- movement ------------------------------------------------------- #
    def steer(self, desired_dir, dt, speed_mul=1.0):
        speed_mul *= self._speed_scale()
        if desired_dir.length_squared() > 1e-4:
            self.target_dir = safe_norm(desired_dir)
            target_v = self.target_dir * self.max_speed * speed_mul
        else:
            target_v = Vector2()
        turn_resp = 1.0 - self.genome.angular_damping   # 1.0 = old behaviour unchanged
        if self.max_speed <= 0:
            return          # a creature that cannot move (A Muralha) never steers
        self.vel += (target_v - self.vel) * clamp(self.accel * dt * turn_resp / self.max_speed, 0, 1)

    def integrate(self, dt, on_plant=None, bounds=None):
        self.pos += self.vel * dt
        m = self.max_r
        # ``bounds`` is the per-boss arena box (issue #26) as
        # (min_x, min_y, max_x, max_y); None = the full world. Same bounce
        # either way, so an arena is just a tighter set of walls.
        if bounds is None:
            lo_x = lo_y = 0.0
            hi_x, hi_y = C.WORLD_W, C.WORLD_H
        else:
            lo_x, lo_y, hi_x, hi_y = bounds
        for ax, lo, hi in ((0, lo_x, hi_x), (1, lo_y, hi_y)):
            if self.pos[ax] < lo + m:
                self.pos[ax] = lo + m
                self.vel[ax] = abs(self.vel[ax]) * 0.5
            elif self.pos[ax] > hi - m:
                self.pos[ax] = hi - m
                self.vel[ax] = -abs(self.vel[ax]) * 0.5

        self.spine.resolve(self.pos)
        if self.vel.length_squared() > 1:
            self.facing = safe_norm(self.vel)
        for leg in self.legs:
            leg.update(self.spine, self.vel, dt, on_plant, self.leg_pull)
        if self.arms:
            self._resolve_arms(dt)
        self.update_secondary_springs(dt)
        self.leg_pull = approach(self.leg_pull, 1.0, 6, dt)  # decays if no one re-asserts it

        if self.genome.linear_damping > 0:
            self.vel *= math.exp(-self.genome.linear_damping * 3.0 * dt)

        spd = self.vel.length()
        w = self.genome.weight
        # max_speed 0 = a creature that cannot move (A Muralha): no run-squash,
        # just whatever squat_bias the animation layer is asking for.
        run = clamp(spd / self.max_speed, 0, 1.6) if self.max_speed > 0 else 0.0
        target_squash = (1.0 + run * 0.16 / w) * self.squat_bias
        self.squash = approach(self.squash, target_squash, 9 / math.sqrt(w), dt)
        self.squat_bias = approach(self.squat_bias, 1.0, 6, dt)  # decays if no one re-asserts it
        self.crest_bias = approach(self.crest_bias, 0.0, 6, dt)   # ditto (#13 telegraph)
        self.wobble += dt * 6
        parts.update_oscillators(self)     # issue #4: oscillators ride wobble
        self.hit_flash = decay(self.hit_flash, dt, 3)
        self.attack_cd = decay(self.attack_cd, dt)
        self.slow_t = decay(self.slow_t, dt)

    def update_secondary_springs(self, dt):
        """Advance every cosmetic spring that chases the physical body.

        A single choke point on purpose: this project has hit "a second call
        site forgot to update the new state" three times already (the menu's
        3 hand-rolled ``integrate()`` subsets all forgot ``tail_spring``, see
        CURRENT_PLAN.md). Any bypass of ``integrate()`` (menu backdrops,
        bestiary/char-select previews) MUST call this too, and adding a new
        spring later only means touching this one method.
        """
        if self.tail_chain:
            # Issue #8: the tail is a CHAIN, not one spring. Each link tracks its
            # own joint, and stiffness rises toward the base, so a sudden stop
            # cascades: the base settles first and the tip whips last.
            #
            # Every link's stiffness is derived from the tip's each step, so the
            # existing consumers that write ``tail_spring.stiffness`` (the boss
            # body telegraph, the AI mood pose, the per-state posing) keep
            # working untouched and now scale the WHOLE tail, not just its end.
            # The stiffness fan-out only has to be redone when someone actually
            # writes the tip -- which is a handful of frames per fight, not every
            # frame of every creature. Damping never changes at all, so it is
            # set once when the chain is built.
            chain = self.tail_chain
            tip_stiff = chain[-1].stiffness
            if tip_stiff != self._tail_stiff_seen:
                self._tail_stiff_seen = tip_stiff
                for i in range(len(chain) - 1):
                    chain[i].stiffness = tip_stiff * TAIL_CHAIN_STIFF_RATIO[i]
            js = self.spine.joints
            base_i = len(js) - len(chain)
            for i, s in enumerate(chain):
                s.target = js[base_i + i] if base_i + i >= 0 else js[0]
                s.update(dt)

        # A3 (#6): acceleration = change in velocity this step; turn rate = change
        # in heading. Both are derived locally from the previous-frame value.
        if dt > 0:
            fwd = self.facing
            accel_fwd = (self.vel - self._prev_vel).dot(fwd) / dt
            # #13: crest_bias bristles the crests on top of the motion lean --
            # same springs, biased target, so the wind-up tell is spring-smoothed.
            bristle = getattr(self, 'crest_bias', 0.0)
            self.plate_spring.target = clamp(accel_fwd * PLATE_TILT_GAIN,
                                             -PLATE_TILT_MAX, PLATE_TILT_MAX) + bristle
            ang = angle_of(fwd)
            d_ang = (ang - self._prev_heading + 180) % 360 - 180
            self.horn_spring.target = clamp((d_ang / dt) * HORN_SWAY_GAIN,
                                            -HORN_SWAY_MAX, HORN_SWAY_MAX) + bristle
            self._prev_vel = Vector2(self.vel)
            self._prev_heading = ang
        self.plate_spring.update(dt)
        self.horn_spring.update(dt)
        look = self._pupil_dir()
        self.pupil_x.target = look.x
        self.pupil_y.target = look.y
        self.pupil_x.update(dt)
        self.pupil_y.update(dt)

    def reset_secondary_springs(self):
        """Snap every cosmetic spring to the current pose -- call after
        teleporting/repositioning a creature outside of normal movement, or
        the spring spends its next few frames chasing a stale anchor."""
        if self.tail_spring is not None:
            self.tail_spring.value = self.tail_spring.target = Vector2(self.spine.joints[-1])

    def _cosmetic_joints(self):
        """Physical joints with the last few tail joints blended toward
        ``tail_spring`` (overshoot/lag) -- draw-only, so hit-test/legs/eyes
        (which read ``spine.joints`` directly) are never thrown off.

        Suppressed while the tail-whip is swinging (``whip_t`` > 0): that
        directly overwrites these same joints with a hand-tuned arc
        (``_whip_arc``), and the spring -- still chasing last frame's
        pre-whip position -- fought it, visibly dulling/glitching the swing.
        """
        chain = self.tail_chain
        if not chain or getattr(self, 'whip_t', 0.0) > 0:
            return None
        js = list(self.spine.joints)
        n = len(js)
        clen = len(chain)
        k = min(TAIL_CHAIN_LEN, n - 1)
        if k <= 0:
            return None
        cap = self.max_r * TAIL_SPRING_MAX_LAG
        cap2 = cap * cap
        wave_amp = self.max_r * 0.12    # traveling ripple (plans/01 #5), on top
        # This runs for every creature every frame, so the oscillator and the
        # chain length are bound once here rather than looked up per joint.
        osc = self.osc.get('tail_ripple') if getattr(self, 'osc', None) else None
        # Each of the last k joints follows its OWN link's lag (issue #8), so the
        # tail bends through the cascade instead of dragging as one rigid blob.
        for ci in range(clen - k, clen):
            i = n - clen + ci
            if i < 1:
                continue
            t = (ci + 1) / clen                # ramps toward the tip
            j = js[i]
            lag = chain[ci].value - j
            if lag.length_squared() > cap2:
                lag.scale_to_length(cap)
            fwd = safe_norm(j - js[i + 1]) if i < n - 1 else safe_norm(js[i - 1] - j)
            amp = wave_amp * t * (osc.offset(i) if osc is not None else 0.0)
            # perp * amp, inlined: this is the innermost line of the draw path
            js[i] = Vector2(j.x + lag.x * t - fwd.y * amp,
                            j.y + lag.y * t + fwd.x * amp)
        return js

    # ---- drawing -------------------------------------------------------- #
    def draw(self, surf, cam):
        # Issue #165: ghost bodies paint FIRST so the actual body and its
        # glow sit on top of the layered silhouettes. Empty list for every
        # non-ANKH creature = zero work, just the for-loop header.
        for pb in self.phantom_bodies:
            if pb.alpha > 0.005:
                parts.draw_phantom_body(surf, cam, pb.species_key,
                                        self.pos, self.facing, pb.alpha, pb.tint)
        squish = 1.0 / math.sqrt(self.squash)
        # soft glow behind the body so it pops off the ground (Animal Well vibe).
        # Bounded to the player (+ bosses via glow_body) so a horde stays cheap;
        # everyone else pops via rim light + vivid colour instead.
        if getattr(self, 'glow_body', self.kind == 'player'):
            mid = self.spine.joints[len(self.spine.joints) // 3]
            palette.glow(surf, cam.w2s(mid), self.max_r * 2.6 * cam.zoom, self.color, 0.34)

        plan = getattr(self.genome, 'plan', 'normal')
        leg_col = palette.darken(self.color, 0.3)
        thin = (plan == 'segmented')      # many little legs read better skinny
        legw = max(1, int(self.max_r * (0.18 if thin else 0.42) * cam.zoom))
        footr = max(1, int(self.max_r * (0.14 if thin else 0.28) * cam.zoom))
        # Issue #18: legs get the same dark ink boundary the body has, so they
        # stop reading as floating shapes from a different art style. A leg is
        # two lines and a circle, so the outline is those same primitives drawn
        # fatter in ink underneath -- no mask trace, no per-leg surface, six
        # extra draw calls. Solve each leg once and reuse for both passes.
        ink_w = max(1, int(2 * cam.zoom))
        solved = []
        for leg in self.legs:
            root = self.spine.joints[leg.idx]
            knee, foot = leg.solve(root)
            solved.append((cam.w2s(root), cam.w2s(knee), cam.w2s(foot)))
        for col, pad in ((C.COL_INK, ink_w), (leg_col, 0)):
            for r, k, f in solved:
                pygame.draw.line(surf, col, r, k, legw + 2 * pad)
                pygame.draw.line(surf, col, k, f, legw + 2 * pad)
                pygame.draw.circle(surf, col, f, footr + pad)

        if self.genome.radial:
            self._draw_spider(surf, cam)
            return
        if plan == 'tentacle':
            self._draw_tentacle(surf, cam)
            return
        if plan == 'orbital':
            self._draw_orbital(surf, cam)
            return
        if plan == 'fixed':
            self._draw_fixed(surf, cam)
            return
        if plan == 'segmented':
            self._draw_segmented(surf, cam)
            return

        cj = self._cosmetic_joints()
        base = self.color
        if self.hit_flash > 0:
            base = palette.lighten(base, self.hit_flash)
        quads, head_fan, tail_fan, ring = self.spine.body_render_smooth(squish, cj)
        for q in quads:
            pygame.draw.polygon(surf, base, cam.w2s_many(q))
        if len(head_fan) >= 3:
            pygame.draw.polygon(surf, base, cam.w2s_many(head_fan))
        if len(tail_fan) >= 3:
            pygame.draw.polygon(surf, base, cam.w2s_many(tail_fan))
        poly = cam.w2s_many(ring)
        if len(poly) >= 3:
            # rim light: a bright edge just inside the dark ink outline
            pygame.draw.polygon(surf, palette.lighten(base, 0.55), poly, max(1, int(3 * cam.zoom)))
            pygame.draw.polygon(surf, C.COL_INK, poly, max(1, int(2 * cam.zoom)))

        spot = palette.darken(self.color, 0.2)
        js = cj or self.spine.joints
        rad = self.spine.radii
        for i in range(2, len(js) - 2, 2):
            pygame.draw.circle(surf, spot, cam.w2s(js[i]),
                               max(1, int(rad[i] * 0.32 * cam.zoom)))
        parts.draw_all(surf, cam, self)
        self._draw_head(surf, cam)

    def _draw_spider(self, surf, cam):
        js = self.spine.joints
        base = self.color
        if self.hit_flash > 0:
            base = palette.lighten(base, self.hit_flash)
        ink_w = max(1, int(2 * cam.zoom))
        head = js[0]
        abdomen = js[-1]
        d = self.spine.head_dir()
        hc = cam.w2s(head)
        ac = cam.w2s(abdomen)
        ar = max(3, int(self.max_r * 1.5 * cam.zoom))
        hr = max(2, int(self.max_r * 0.85 * cam.zoom))
        # abdomen
        pygame.draw.circle(surf, base, ac, ar)
        pygame.draw.circle(surf, palette.lighten(base, 0.5), ac, ar, ink_w)
        pygame.draw.circle(surf, C.COL_INK, ac, ar, ink_w)
        # cephalothorax
        pygame.draw.circle(surf, palette.darken(base, 0.1), hc, hr)
        pygame.draw.circle(surf, C.COL_INK, hc, hr, ink_w)
        # cluster of eyes on the head
        perp = Vector2(-d.y, d.x)
        r = self.max_r
        for ex, ey in ((0.25, -0.3), (0.25, 0.3), (0.45, -0.12), (0.45, 0.12)):
            ep = head + d * (r * ex) + perp * (r * ey)
            pygame.draw.circle(surf, C.COL_WHITE, cam.w2s(ep), max(1, int(r * 0.16 * cam.zoom)))

    def _draw_segmented(self, surf, cam):
        """Centipede: overlapping ringed segments (the ink ring on each = the
        segmentation), head last so it sits on top, with mandibles + antennae."""
        js, rad = self.spine.joints, self.spine.radii
        n = len(js)
        base = self.color
        if self.hit_flash > 0:
            base = palette.lighten(base, self.hit_flash)
        seg = palette.lighten(base, 0.05)
        rim = palette.lighten(base, 0.5)
        ink_w = max(1, int(1.6 * cam.zoom))
        for i in range(n - 1, -1, -1):
            c = cam.w2s(js[i])
            rr = max(2, int(rad[i] * 1.2 * cam.zoom))
            pygame.draw.circle(surf, base if i == 0 else seg, c, rr)
            pygame.draw.circle(surf, rim, (c[0] - int(rr * 0.28), c[1] - int(rr * 0.3)),
                               max(1, int(rr * 0.36)))
            pygame.draw.circle(surf, C.COL_INK, c, rr, ink_w)
        head = js[0]
        d = self.spine.head_dir()
        perp = Vector2(-d.y, d.x)
        r = self.max_r
        for s in (-1, 1):                                   # mandibles
            b = head + d * (r * 0.7) + perp * (s * r * 0.42)
            tip = b + d * (r * 0.6) - perp * (s * r * 0.18)
            pygame.draw.line(surf, C.COL_INK, cam.w2s(b), cam.w2s(tip), max(2, int(2 * cam.zoom)))
        acol = palette.darken(base, 0.2)
        for s in (-1, 1):                                   # antennae
            b = head + d * (r * 0.5) + perp * (s * r * 0.5)
            wig = parts._osc_offset(self, 'antennae', s)
            tip = b + d * (r * 0.95) + perp * (s * r * (0.6 + wig))
            pygame.draw.line(surf, acol, cam.w2s(b), cam.w2s(tip), max(1, int(1.5 * cam.zoom)))
        look = self._pupil_offset()
        for s in (-1, 1):                                   # eyes
            ep = head + d * (r * 0.2) + perp * (s * r * 0.46)
            pygame.draw.circle(surf, C.COL_WHITE, cam.w2s(ep), max(2, int(r * 0.3 * cam.zoom)))
            pygame.draw.circle(surf, C.COL_INK, cam.w2s(ep + look * (r * 0.1)),
                               max(1, int(r * 0.15 * cam.zoom)))

    def _arm_polygon(self, cam, js, base_r):
        """Smooth tapering outline around an arm chain -- same left/right-rim +
        rounded-tip technique as the spine body, so arms read as continuous flesh
        (not a string of beads)."""
        m = len(js)
        radii = [base_r * (1.0 - 0.93 * (i / (m - 1))) for i in range(m)]
        left, right = [], []
        for i in range(m):
            fwd = safe_norm(js[i + 1] - js[i]) if i < m - 1 else safe_norm(js[i] - js[i - 1])
            perp = Vector2(-fwd.y, fwd.x) * radii[i]
            left.append(js[i] + perp)
            right.append(js[i] - perp)
        tip, tdir = js[-1], safe_norm(js[-1] - js[-2])
        base_a = angle_of(tdir)
        cap = [tip + vfrom_angle(base_a + a, radii[-1] * 1.1) for a in (-60, -25, 0, 25, 60)]
        return cam.w2s_many(left + cap + right[::-1])

    def _draw_tentacle(self, surf, cam):
        """Octopus/kraken: reaching arms drawn as smooth continuous tentacles
        behind a pulsing mantle bulb."""
        base = self.color
        if self.hit_flash > 0:
            base = palette.lighten(base, self.hit_flash)
        arm_col = palette.darken(base, 0.1)
        rim = palette.lighten(base, 0.5)
        spot = palette.darken(base, 0.2)
        rim_w = max(1, int(2 * cam.zoom))
        ink_w = max(1, int(2 * cam.zoom))
        arm_r = self.max_r * 0.62
        for arm in self.arms:
            js = arm['j']
            poly = self._arm_polygon(cam, js, arm_r)
            if len(poly) >= 3:
                pygame.draw.polygon(surf, arm_col, poly)
                pygame.draw.polygon(surf, rim, poly, rim_w)
                pygame.draw.polygon(surf, C.COL_INK, poly, ink_w)
            for i in range(2, len(js) - 2, 3):    # faint spots, like the lizard body
                t = i / (len(js) - 1)
                rr = max(1, int(arm_r * (1.0 - 0.93 * t) * 0.34 * cam.zoom))
                pygame.draw.circle(surf, spot, cam.w2s(js[i]), rr)
        head = self.spine.joints[0]
        mc = cam.w2s(head)
        pulse = 1.0 + 0.05 * math.sin(self.wobble * 2.4)
        mr = max(4, int(self.max_r * 1.7 * pulse * cam.zoom))
        pygame.draw.circle(surf, base, mc, mr)
        pygame.draw.circle(surf, rim, (mc[0] - int(mr * 0.3), mc[1] - int(mr * 0.34)),
                           max(1, int(mr * 0.42)))
        pygame.draw.circle(surf, palette.lighten(base, 0.55), mc, mr, max(1, int(3 * cam.zoom)))
        pygame.draw.circle(surf, C.COL_INK, mc, mr, max(1, int(2 * cam.zoom)))
        d = self.spine.head_dir()
        perp = Vector2(-d.y, d.x)
        r = self.max_r
        look = self._pupil_offset()
        for s in (-1, 1):
            ep = head + d * (r * 0.4) + perp * (s * r * 0.62)
            sp = cam.w2s(ep)
            pygame.draw.circle(surf, C.COL_WHITE, sp, max(2, int(r * 0.46 * cam.zoom)))
            pygame.draw.circle(surf, C.COL_INK, cam.w2s(ep + look * (r * 0.2)),
                               max(1, int(r * 0.22 * cam.zoom)))

    def _draw_orbital(self, surf, cam):
        """Olho-Sismico (plan='orbital'): a floating eyeball. 6 thin bone-tipped
        tentacles (the octopus arm chains drawn skinny, travelling-wave + trail
        for free via _resolve_arms), then a glowing sphere with pulsing veins, a
        vertical cat-slit iris that lags toward the player (the same pupil spring
        every eye uses -> it lags on a dash automatically), and a blink membrane.
        Float/veins ride self.wobble; the blink STATE that shields the eye lives
        in the sim (patterns.eye_blink_tick), this only reads it."""
        base = self.color
        if self.hit_flash > 0:
            base = palette.lighten(base, self.hit_flash)
        ink_w = max(1, int(2 * cam.zoom))
        # tentacles: thin, with a pale bone tip
        arm_r = self.max_r * 0.16
        arm_col = palette.darken(base, 0.15)
        bone = (232, 226, 212)
        for arm in self.arms:
            js = arm['j']
            poly = self._arm_polygon(cam, js, arm_r)
            if len(poly) >= 3:
                pygame.draw.polygon(surf, arm_col, poly)
                pygame.draw.polygon(surf, C.COL_INK, poly, ink_w)
            pygame.draw.circle(surf, bone, cam.w2s(js[-1]), max(2, int(arm_r * 0.95 * cam.zoom)))
        # eyeball -- floats: sine bob (~8px, ~1.5Hz via wobble) applied to the sphere
        c = cam.w2s(self.spine.joints[0])
        bob = 8.0 * math.sin(self.wobble * 1.57) * cam.zoom
        sc = (int(c[0]), int(c[1] + bob))
        R = max(4, int(self.max_r * cam.zoom))
        phase_i = self.boss_ai.phase_i if getattr(self, 'boss_ai', None) is not None else 0
        palette.glow(surf, sc, int(R * 1.6), base, 0.4)
        pygame.draw.circle(surf, (238, 236, 240), sc, R)          # sclera
        pygame.draw.circle(surf, C.COL_INK, sc, R, ink_w)
        # veins: heartbeat pulse, redder/denser each phase (agitated = faster)
        vein_col = palette.mix((190, 70, 70), (255, 24, 24), min(1.0, phase_i / 2))
        beat = 0.5 + 0.5 * math.sin(self.wobble * (2.5 + phase_i * 1.5))
        nveins = 5 + phase_i * 3
        for i in range(nveins):
            a = math.radians((360 / nveins) * i + self.wobble * 6)
            r0 = R * (0.45 + 0.1 * beat)
            p0 = (int(sc[0] + math.cos(a) * r0), int(sc[1] + math.sin(a) * r0))
            p1 = (int(sc[0] + math.cos(a) * R), int(sc[1] + math.sin(a) * R))
            pygame.draw.line(surf, vein_col, p0, p1, max(1, int((1 + beat) * cam.zoom)))
        # iris: coloured disc + vertical cat-slit pupil, lagged toward the player;
        # dilates (slit widens) each phase -- "iris mais aberta" / "arregalado"
        look = self._pupil_offset()
        ix = int(sc[0] + look.x * R * 0.42)
        iy = int(sc[1] + look.y * R * 0.42)
        iris_r = max(2, int(R * (0.34 + 0.05 * phase_i)))
        pygame.draw.circle(surf, palette.darken(base, 0.35), (ix, iy), iris_r)
        slit_w = max(2, int(iris_r * (0.4 + 0.22 * phase_i)))   # dilates per phase
        slit_h = max(2, int(iris_r * 1.7))
        pygame.draw.ellipse(surf, C.COL_INK, (ix - slit_w, iy - slit_h, slit_w * 2, slit_h * 2))
        # blink membrane: a lid over the whole sphere for the 0.1s it's shielded
        if getattr(self, 'eye_shielded', False):
            pygame.draw.circle(surf, palette.darken(base, 0.55), sc, R)
            pygame.draw.circle(surf, C.COL_INK, sc, R, ink_w)

    def _draw_fixed(self, surf, cam):
        """A Muralha (plan='fixed'): a wall occupying right side of arena.
        Central mouth with stalactite teeth, multiple independent eyes,
        pulsing veins from mouth to edges, 2 stone hands with spring-damper.
        Damage shows as falling stone chunks and surface cracks."""
        base = self.color
        if self.hit_flash > 0:
            base = palette.lighten(base, self.hit_flash)
        ink_w = max(1, int(2 * cam.zoom))
        js = self.spine.joints
        head = js[0]  # mouth center
        r = self.max_r

        # Phase for veins/animation
        phase_i = self.boss_ai.phase_i if getattr(self, 'boss_ai', None) is not None else 0
        hp_frac = self.hp / max(1, self.max_hp) if hasattr(self, 'max_hp') else 1.0

        # Wall body: large rect on right side
        wall_w = int(r * 3.5 * cam.zoom)
        wall_h = int(r * 6 * cam.zoom)
        hw = cam.w2s(head)
        wall_rect = pygame.Rect(hw[0] - wall_w // 2, hw[1] - wall_h // 2, wall_w, wall_h)

        # Base wall color - stone/flesh mix
        wall_col = palette.darken(base, 0.15)
        pygame.draw.rect(surf, wall_col, wall_rect, border_radius=max(2, int(6 * cam.zoom)))

        # Rim light on left edge (facing arena)
        rim_col = palette.lighten(base, 0.4)
        pygame.draw.line(surf, rim_col,
                         (wall_rect.left, wall_rect.top),
                         (wall_rect.left, wall_rect.bottom),
                         max(2, int(3 * cam.zoom)))

        # Pulsing veins from mouth outward
        vein_col = palette.mix((180, 60, 60), (255, 20, 20), min(1.0, phase_i / 2 + (1 - hp_frac) * 0.5))
        beat = 0.5 + 0.5 * math.sin(self.wobble * (2.5 + phase_i * 1.5) + (1 - hp_frac) * 3)
        nveins = 7 + phase_i * 2 + int((1 - hp_frac) * 5)
        for i in range(nveins):
            a = math.radians((180 / nveins) * i - 90 + self.wobble * 2)
            vx = math.cos(a)
            vy = math.sin(a)
            vx = abs(vx)  # veins go leftward (toward player)
            p0 = hw
            p1 = (int(hw[0] - vx * r * 2.5), int(hw[1] + vy * r * 2.5))
            w = max(1, int((1 + beat * 0.5) * cam.zoom))
            pygame.draw.line(surf, vein_col, cam.w2s(p0), cam.w2s(p1), w)

        # Mouth - central, opens/closes
        mouth_open = getattr(self, 'mouth_open', 0.5)  # 0=closed, 1=fully open
        mouth_w = int(r * 1.2 * cam.zoom)
        mouth_h = int(r * 1.8 * cam.zoom * (0.3 + 0.7 * mouth_open))
        mouth_rect = pygame.Rect(hw[0] - mouth_w // 2, hw[1] - mouth_h // 2, mouth_w, mouth_h)
        pygame.draw.ellipse(surf, (20, 10, 10), mouth_rect)  # throat
        pygame.draw.ellipse(surf, C.COL_INK, mouth_rect, max(2, int(3 * cam.zoom)))

        # Stalactite teeth on upper/lower lip
        nteeth = 6
        for i in range(nteeth):
            tx = hw[0] - mouth_w // 2 + (i + 0.5) * mouth_w / nteeth
            # Upper teeth
            ttop = (int(tx), int(hw[1] - mouth_h // 2 - 4 * cam.zoom))
            ttip = (int(tx), int(hw[1] - mouth_h // 2 - 18 * cam.zoom * (0.8 + 0.2 * math.sin(self.wobble * 2 + i))))
            pygame.draw.line(surf, palette.lighten(base, 0.2), cam.w2s(ttop), cam.w2s(ttip), max(1, int(2 * cam.zoom)))
            # Lower teeth
            tbot = (int(tx), int(hw[1] + mouth_h // 2 + 4 * cam.zoom))
            ttip2 = (int(tx), int(hw[1] + mouth_h // 2 + 18 * cam.zoom * (0.8 + 0.2 * math.sin(self.wobble * 2 + i + 1))))
            pygame.draw.line(surf, palette.lighten(base, 0.2), cam.w2s(tbot), cam.w2s(ttip2), max(1, int(2 * cam.zoom)))

        # Multiple independent eyes - they open where player is
        player_dir = getattr(self, '_player_dir', Vector2(-1, 0))  # default left
        for i in range(8 + phase_i * 2):
            eye_ang = math.radians(-70 + (140 / (7 + phase_i * 2)) * i)
            eye_dir = Vector2(math.cos(eye_ang), math.sin(eye_ang))
            # Eye opens if facing player direction
            eye_open = max(0.1, eye_dir.dot(-player_dir))  # player is to the left
            if eye_open > 0.3:
                ex = int(hw[0] + eye_dir.x * r * 1.3)
                ey = int(hw[1] + eye_dir.y * r * 1.3)
                er = max(2, int(r * 0.35 * eye_open * cam.zoom))
                esp = (ex, ey)
                pygame.draw.circle(surf, (240, 240, 250), esp, er)
                pygame.draw.circle(surf, C.COL_INK, esp, er, max(1, int(2 * cam.zoom)))
                # Pupil
                px = int(ex + -player_dir.x * er * 0.4)
                py = int(ey + -player_dir.y * er * 0.4)
                pygame.draw.circle(surf, C.COL_INK, (px, py), max(1, int(er * 0.3)))

        # Stone hands (spring-damper) - stored on boss
        if hasattr(self, 'hand_springs'):
            for side, spring in self.hand_springs.items():
                hand_pos = cam.w2s(spring.value)
                hr = max(4, int(r * 0.7 * cam.zoom))
                pygame.draw.circle(surf, palette.darken(base, 0.3), hand_pos, hr)
                pygame.draw.circle(surf, C.COL_INK, hand_pos, hr, max(2, int(3 * cam.zoom)))
                # Fingers
                for f in range(4):
                    fa = math.radians(-60 + f * 40)
                    fx = int(hand_pos[0] + math.cos(fa) * hr * 1.3)
                    fy = int(hand_pos[1] + math.sin(fa) * hr * 1.3)
                    pygame.draw.line(surf, C.COL_INK, hand_pos, (fx, fy), max(2, int(3 * cam.zoom)))

        # Damage cracks - more visible as hp decreases
        if hp_frac < 1.0:
            crack_col = palette.mix(C.COL_INK, (100, 100, 100), 0.5)
            ncracks = int((1 - hp_frac) * 12)
            for i in range(ncracks):
                cx = hw[0] - r * 1.2 + random.uniform(-r, r)
                cy = hw[1] - r * 2.5 + random.uniform(-r * 2, r * 2)
                ca = random.uniform(0, math.pi * 2)
                cl = r * random.uniform(0.3, 0.8)
                c0 = (int(cx), int(cy))
                c1 = (int(cx + math.cos(ca) * cl), int(cy + math.sin(ca) * cl))
                pygame.draw.line(surf, crack_col, cam.w2s(c0), cam.w2s(c1), max(1, int(2 * cam.zoom)))

    def _look_dir(self):
        if self.kind == 'player':
            return self.facing
        return safe_norm(self.vel) if self.vel.length_squared() > 1 else self.spine.head_dir()

    def _pupil_dir(self):
        """Unit direction the pupils *want* to point: the creature's target
        (aggro'd enemy for AI, tongue lock for the player) if there is one,
        else where it's looking. Springs lag the pupils toward this (A3, #6)."""
        tgt = getattr(self, 'aggro', None) or getattr(self, 'tongue_target', None)
        if tgt is not None and not getattr(tgt, 'dead', False):
            return safe_norm(tgt.pos - self.spine.joints[0])
        return self._look_dir()

    def _pupil_offset(self):
        """Lagged pupil direction (magnitude < 1 while drifting) -- read where an
        eye's pupil is drawn. Falls back to the instantaneous look if the springs
        aren't built yet (previews built before __init__ finishes)."""
        px = getattr(self, 'pupil_x', None)
        if px is None:
            return self._look_dir()
        return Vector2(px.value, self.pupil_y.value)

    def _draw_head(self, surf, cam):
        head = self.spine.joints[0]
        d = self.spine.head_dir()
        perp = Vector2(-d.y, d.x)
        r = self.max_r
        look = self._pupil_offset()
        eye_glow = getattr(self, 'glow_body', self.kind == 'player')
        for s in (-1, 1):
            ep = head + d * (r * 0.15) + perp * (s * r * 0.62)
            sp = cam.w2s(ep)
            if eye_glow:
                palette.glow(surf, sp, r * 0.9 * cam.zoom, (200, 200, 210), 0.5)
            pygame.draw.circle(surf, C.COL_WHITE, sp, max(2, int(r * 0.42 * cam.zoom)))
            pygame.draw.circle(surf, C.COL_INK, cam.w2s(ep + look * (r * 0.18)),
                               max(1, int(r * 0.2 * cam.zoom)))
