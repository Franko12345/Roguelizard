"""Shooter behaviours: every one of them fires through the shared emitter.

None of these ticks builds a projectile any more. They decide *when* to shoot
and *how to move*; WHAT comes out of the mouth is ``genome.shot`` -- an emitter
pattern plus its dials (see ``lagarto.combat.emitter`` and
``docs/adr/0012-shared-pattern-emitter.md``). Swapping the CUSPIDOR's single
spit for a radial burst or a spiral is a dict edit in ``species.py``, not code
here.

Three species live here: the telegraphed spitter, the burst gunner and the
venom lobber.
"""

import random
from pygame import Vector2

from ...core import config as C
from ...core import palette
from ...core.mathutil import safe_norm
from ...combat import emitter


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
