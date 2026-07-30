"""POLVO: the anti-kite grappler -- reach, root, snap, reel in."""

import random
from pygame import Vector2

from ...core import config as C
from ...audio import engine as audio
from ...core import palette
from ...core.mathutil import safe_norm


def grapple_tick(creature, game, dt, target):
    """POLVO: an anti-kite grappler (Gungeon Gripmaster). It closes to mid
    range, roots, and reaches ALL arms toward you (a >0.7s telegraph); if you
    are still in reach at the snap it reels you in and slows you. Fleeing the
    wind-up is the counter -- so it punishes lingering at its doorstep."""
    to = safe_norm(target.pos - creature.pos)
    dist = target.pos.distance_to(creature.pos)
    if dist < (creature.max_r + target.max_r) and creature.attack_cd <= 0:
        creature._contact(game, target)
    if creature.grapple_t > 0:                     # winding up: arms reach in
        creature.grapple_t -= dt
        creature.arm_target = Vector2(target.pos)
        if random.random() < dt * 20:
            game.fx.burst(creature.spine.joints[0], palette.lighten(creature.color, 0.3), 1, 60)
        if creature.grapple_t <= 0:
            creature.arm_target = None
            if dist < C.OCTO_GRAB_RANGE:        # snap!
                pull = min(C.OCTO_PULL_DIST, dist - creature.max_r)
                target.pos += safe_norm(creature.pos - target.pos) * max(0, pull)
                target.apply_slow(C.OCTO_SLOW_MUL, C.OCTO_SLOW_TIME)
                creature.grabbed = target
                creature.grab_show = C.OCTO_GRAB_SHOW
                game.fx.spark_burst(target.pos, creature.color, 12, 280)
                game.shake(5)
                audio.play('hit', 0.45)
        return to * 0.5, 0.0                   # rooted, mantle exposed
    creature.arm_target = None
    if creature.grapple_cd > 0:
        creature.grapple_cd -= dt
    elif dist < C.OCTO_GRAB_RANGE:
        creature.grapple_t = C.OCTO_WINDUP
        creature.grapple_cd = C.OCTO_CD
    return to, 1.0                              # commit to closing (it is slow anyway)
