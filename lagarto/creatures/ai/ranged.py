"""Shooter behaviours: the telegraphed spitter, the burst gunner, the venom lobber."""

import random
from pygame import Vector2

from ...core import config as C
from ...core import palette
from ...core.mathutil import safe_norm
from ...combat.projectile import spit as game_spit, leave_puddle


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
            game.spawn_projectile(game_spit(mouth, target.pos, creature.color,
                                            dmg=C.ENEMY_PROJ_DMG))
            game.fx.spark_burst(mouth, creature.color, 7, 200)
        return to * 0.05, 0.0                 # brace while charging

    if dist < 260:
        d = -to                               # back away
    elif dist > 380:
        d = to                                # close in
    else:
        d = Vector2(-to.y, to.x) * (1 if int(creature.wobble) % 2 else -1)  # strafe
    if creature.shoot_cd <= 0 and dist < 440:
        creature.shoot_cd = 2.3
        creature.shoot_charge = 0.45              # start the wind-up
    return d, 0.75


def gunner_tick(creature, game, dt, target):
    """High rate of fire, low damage per shot: pressure, not burst.

    Holds mid-range and fires a burst, so the threat is a *stream* you have to
    break line with, unlike the spitter's single telegraphed spike.
    """
    to = safe_norm(target.pos - creature.pos)
    dist = target.pos.distance_to(creature.pos)
    mouth = creature.spine.joints[0] + creature.spine.head_dir() * creature.max_r
    if creature.burst_left > 0 and creature.shoot_cd <= 0:
        creature.burst_left -= 1
        creature.shoot_cd = C.GUNNER_BURST_GAP
        spread = random.uniform(-C.GUNNER_SPREAD, C.GUNNER_SPREAD)
        aim = creature.pos + (target.pos - creature.pos).rotate(spread)
        game.spawn_projectile(game_spit(mouth, aim, creature.color,
                                        dmg=C.GUNNER_DMG, effect=None,
                                        speed=300, radius=5))
        game.fx.spark_burst(mouth, creature.color, 3, 150)
    elif creature.burst_left <= 0 and creature.shoot_cd <= 0 and dist < 460:
        creature.burst_left = C.GUNNER_BURST
        creature.shoot_cd = C.GUNNER_RELOAD
    if dist < 240:
        d = -to
    elif dist > 400:
        d = to
    else:
        d = Vector2(-to.y, to.x) * (1 if int(creature.wobble) % 2 else -1)
    return d, 0.8


def venom_tick(creature, game, dt, target):
    """Lobs venom that leaves a puddle where it lands -- area denial.

    The shot is aimed at where you *are* and its life is set so it lands
    there, which makes it a zoning tool rather than a hit: standing still is
    what punishes you, so it pushes the player to keep moving.
    """
    to = safe_norm(target.pos - creature.pos)
    dist = target.pos.distance_to(creature.pos)
    mouth = creature.spine.joints[0] + creature.spine.head_dir() * creature.max_r
    if creature.shoot_charge > 0:
        creature.shoot_charge -= dt
        if random.random() < dt * 30:
            game.fx.burst(mouth, (150, 240, 110), 1, 60)
        if creature.shoot_charge <= 0:
            pr = game_spit(mouth, target.pos, (140, 235, 100),
                           dmg=C.VENOM_SPIT_DMG, effect='poison',
                           speed=C.VENOM_SPIT_SPEED, radius=7)
            # land ON the aim point: life = travel time, so the puddle is
            # dropped where the telegraph pointed instead of flying past
            travel = mouth.distance_to(target.pos) / C.VENOM_SPIT_SPEED
            pr.life = max(0.12, min(travel, 2.2))
            # one movement-free modifier: the payload it leaves behind
            pr.on_death.append(leave_puddle(
                r=C.VENOM_PUDDLE_R, dmg=C.VENOM_PUDDLE_DMG,
                life=C.VENOM_PUDDLE_LIFE, hue=100, tick=C.VENOM_PUDDLE_TICK))
            game.spawn_projectile(pr)
            game.fx.spark_burst(mouth, (150, 240, 110), 6, 190)
        return to * 0.05, 0.0
    if creature.shoot_cd <= 0 and dist < 430:
        creature.shoot_cd = C.VENOM_CD
        creature.shoot_charge = C.VENOM_WINDUP
    if dist < 250:
        d = -to
    elif dist > 390:
        d = to
    else:
        d = Vector2(-to.y, to.x) * (1 if int(creature.wobble) % 2 else -1)
    return d, 0.72
