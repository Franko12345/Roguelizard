"""Shooter behaviours: every one of them fires through the shared emitter.

None of these ticks builds a projectile any more. They decide *when* to shoot
and *how to move*; WHAT comes out of the mouth is ``genome.shot`` -- an emitter
pattern plus its dials (see ``lagarto.combat.emitter`` and
``docs/adr/0012-shared-pattern-emitter.md``). Swapping the CUSPIDOR's single
spit for a radial burst or a spiral is a dict edit in ``species.py``, not code
here.

Five species live here: the telegraphed spitter, the burst gunner, the venom
lobber, and the two the rolamento (#103) created a habit for -- the
ANTECIPADOR, which shoots where you are GOING, and the MORTEIRO, which arms a
patch of ground late.
"""

import random
from pygame import Vector2

from ...core import config as C
from ...core import palette
from ...core.mathutil import safe_norm
from ...combat import emitter
from ...combat import weapons


def _dials(creature):
    return creature.genome.shot or {}


def _fire(creature, game, target):
    """Fire this creature's own pattern -- the one place a species' shot is
    turned into projectiles."""
    d = _dials(creature)
    d['fn'](creature, game, target, d)


def _keep_range(creature, target, near, far):
    """Back off / close in / strafe -- the kiting every shooter here shares."""
    to = safe_norm(target.pos - creature.pos)
    dist = target.pos.distance_to(creature.pos)
    if dist < near:
        return -to
    if dist > far:
        return to
    return Vector2(-to.y, to.x) * (1 if int(creature.wobble) % 2 else -1)


def ranged_tick(creature, game, dt, target):
    dist = target.pos.distance_to(creature.pos)
    to = safe_norm(target.pos - creature.pos)
    mouth = creature.spine.joints[0] + creature.spine.head_dir() * creature.max_r

    if creature.shoot_charge > 0:                 # telegraph -> gives time to dodge
        creature.shoot_charge -= dt
        creature.squat_bias = 0.88                # coiling to spit -- see integrate()
        if random.random() < dt * 26:
            game.fx.burst(mouth, palette.lighten(creature.color, 0.3), 1, 50)
        if creature.shoot_charge <= 0:
            _fire(creature, game, target)
        return to * 0.05, 0.0                 # brace while charging

    if creature.shoot_cd <= 0 and dist < 440:
        creature.shoot_cd = 2.3
        creature.shoot_charge = 0.45              # start the wind-up
    return _keep_range(creature, target, 260, 380), 0.75


def gunner_tick(creature, game, dt, target):
    """High rate of fire, low damage per shot: pressure, not burst.

    Holds mid-range and fires a burst, so the threat is a *stream* you have to
    break line with, unlike the spitter's single telegraphed spike.
    """
    dist = target.pos.distance_to(creature.pos)
    if creature.burst_left > 0 and creature.shoot_cd <= 0:
        creature.burst_left -= 1
        creature.shoot_cd = C.GUNNER_BURST_GAP
        _fire(creature, game, target)             # dispersion is a dial ('jitter')
    elif creature.burst_left <= 0 and creature.shoot_cd <= 0 and dist < 460:
        creature.burst_left = C.GUNNER_BURST
        creature.shoot_cd = C.GUNNER_RELOAD
    return _keep_range(creature, target, 240, 400), 0.8


def venom_tick(creature, game, dt, target):
    """Lobs venom that leaves a puddle where it lands -- area denial.

    The shot is aimed at where you *are* and its life is set so it lands
    there (``emitter.lob_shot``), which makes it a zoning tool rather than a
    hit: standing still is what punishes you, so it pushes the player to keep
    moving.
    """
    to = safe_norm(target.pos - creature.pos)
    dist = target.pos.distance_to(creature.pos)
    mouth = creature.spine.joints[0] + creature.spine.head_dir() * creature.max_r
    if creature.shoot_charge > 0:
        creature.shoot_charge -= dt
        if random.random() < dt * 30:
            game.fx.burst(mouth, (150, 240, 110), 1, 60)
        if creature.shoot_charge <= 0:
            _fire(creature, game, target)
        return to * 0.05, 0.0
    if creature.shoot_cd <= 0 and dist < 430:
        creature.shoot_cd = C.VENOM_CD
        creature.shoot_charge = C.VENOM_WINDUP
    return _keep_range(creature, target, 250, 390), 0.72


def lead_tick(creature, game, dt, target):
    """ANTECIPADOR: it does not shoot at you, it shoots at where you are going.

    The habit it exists to punish is the reflex rolamento (#103): the roll is
    cheap and frequent, so it gets pressed without looking -- and this aims at
    the point that reflex is about to put you on. Reusing
    ``emitter.aimed_barrage`` means the lead is the same formula the boss
    barrage already used, dialled longer.

    The telegraph is the lead point itself, drawn on the ground for the whole
    wind-up and re-aimed every frame, so it answers "am I inside?" *and* keeps
    the promise: what the marker shows at the trigger frame is where the shots
    go. The lead is LINEAR, so the counter is changing direction -- not
    freezing, which just makes the lead zero and the shot dead on (measured in
    docs/concepts/balance.md).
    """
    d = _dials(creature)
    to = safe_norm(target.pos - creature.pos)
    dist = target.pos.distance_to(creature.pos)
    emitter._tick_barrage(creature, game)         # a burst already in the air
    if creature.shoot_charge > 0:
        creature.shoot_charge -= dt
        creature.squat_bias = 0.9
        creature._rain_points = [emitter.lead_point(creature, target, d)]
        if creature.shoot_charge <= 0:
            emitter.aimed_barrage(creature, game, target, d)
            creature._rain_points = []
        return to * 0.05, 0.0                     # planted: the aim is the attack
    if creature.shoot_cd <= 0 and dist < C.SNIPER_RANGE:
        creature.shoot_cd = C.SNIPER_CD
        creature.shoot_charge = C.SNIPER_WINDUP
        creature.mark_total = C.SNIPER_WINDUP
        creature.mark_r = C.SNIPER_MARK_R
    return _keep_range(creature, target, 300, 430), 0.85


def mortar_tick(creature, game, dt, target):
    """MORTEIRO: area denial that arms LATE, closing the landing spot.

    The habit it punishes is charging in on top of it: the patch is picked at
    the start of the wind-up (``emitter._select_arms_rain``, the same
    commitment a boss's arms rain makes) and only becomes a real hazard a
    second later -- long enough that an investida aimed at the MORTEIRO ends
    inside it. Walking out always works; the point is choosing before you dash,
    not reacting after.

    ``MORTAR_LIFE < MORTAR_CD`` is not a taste call: an area effect that
    outlives the cooldown that reapplies it is permanent by construction (the
    Acido / venom-puddle / sting-slow bug, three times over).
    """
    d = _dials(creature)
    dist = target.pos.distance_to(creature.pos)
    if creature.shoot_charge > 0:
        creature.shoot_charge -= dt
        if creature.shoot_charge <= 0:
            for pt in getattr(creature, '_rain_points', []):
                game.spawn_puddle(weapons.Puddle(pt, C.MORTAR_R, C.MORTAR_DMG,
                                                 C.MORTAR_LIFE, 330, hostile=True,
                                                 tick=C.MORTAR_TICK))
                game.fx.ring(pt, creature.color)
            creature._rain_points = []
    elif creature.shoot_cd <= 0 and dist < C.MORTAR_RANGE:
        creature.shoot_cd = C.MORTAR_CD
        creature.shoot_charge = C.MORTAR_ARM
        creature.mark_total = C.MORTAR_ARM
        creature.mark_r = C.MORTAR_R
        emitter._select_arms_rain(creature, game, target, d)
    return _keep_range(creature, target, 230, 380), 0.7
