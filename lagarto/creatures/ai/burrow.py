"""CENTOPEIA: the dive-and-ambush finite state machine.

The eruption point anticipates the player (issue #161): it's where the
target WILL be when the boss surfaces, modulated by ``lead_quality``
(sub-perfect so a player who brakes the dig telegraph still escapes).
Underground speed is ``centipede.max_speed * UNDER_MULT``; flight time
is ``distance / (max_speed * UNDER_MULT)``. A target with no velocity
falls back to where they stand + a small jitter (no direction to lead).
"""

import random
from pygame import Vector2

from ...core import config as C
from ...audio import engine as audio
from ...core.mathutil import safe_norm, vfrom_angle, random_dir, predict_target


UNDER_MULT = 2.4                             # buried travel speed / max_speed
LEAD_QUALITY = 0.85                          # sub-perfect: 15% margin brakes hard
ERUPT_JITTER = 30.0                          # eruption spot jitter (was 70: too loose)


def burrow_tick(creature, game, dt, target):
    """CENTOPEIA: hunt on the surface, then dive and ambush (Isaac Para-Bite).

    The dive is intangible, so you cannot chip it underground; it surfaces at
    a point locked in when it dove, drawn as a growing ring on the ground.
    Standing still = it erupts under you; the fair counter is to leave the
    ring. Punishes camping and running in a straight line."""
    to = safe_norm(target.pos - creature.pos)
    dist = target.pos.distance_to(creature.pos)
    creature.burrow_t -= dt
    dirt = (150, 112, 74)
    if creature.burrow_state == 'surface':
        if dist < (creature.max_r + target.max_r) * 1.1 and creature.attack_cd <= 0:
            creature._contact(game, target)
        if creature.burrow_t <= 0:                    # start the dig telegraph
            creature.burrow_state = 'digging'
            creature.burrow_t = C.CENT_DIG_TIME
            audio.play('nest', 0.35)
        return to, 1.2
    if creature.burrow_state == 'digging':
        # rooted, kicking up dirt: the body sinks into a hole (_draw_burrow),
        # so it reads as burrowing rather than blinking out
        if random.random() < dt * 55:
            game.fx.burst(creature.pos + random_dir(random.uniform(0, creature.max_r)),
                          dirt, 1, 150)
        if creature.burrow_t <= 0:
            creature.burrow_state = 'under'
            creature.burrowed = True
            creature.burrow_t = C.CENT_UNDER_TIME
            underground_speed = max(1, creature.max_speed * UNDER_MULT)
            flight_time = max(0.0, (target.pos - creature.pos).length()
                              / underground_speed)
            if target.vel.length() > 1e-3:
                dive_point = predict_target(target.pos, target.vel,
                                            flight_time, LEAD_QUALITY)
            else:
                dive_point = Vector2(target.pos)
            creature.dive_to = dive_point + vfrom_angle(
                random.uniform(0, 360), random.uniform(0, ERUPT_JITTER))
            game.fx.burst(creature.pos, dirt, 24, 280)
            game.fx.ring(creature.pos, (170, 128, 86))
        return Vector2(), 0.0
    # underground: race to the marked spot, leaving a dust trail, then erupt
    du = creature.dive_to - creature.pos
    if random.random() < dt * 34:
        game.fx.burst(creature.pos, dirt, 1, 90)
    if du.length() < 42 or creature.burrow_t <= 0:
        creature.burrow_state = 'surface'
        creature.burrowed = False
        creature.burrow_t = C.CENT_SURFACE_TIME
        _erupt(creature, game)
        return to, 0.0
    return safe_norm(du), UNDER_MULT


def _erupt(creature, game):
    pos = Vector2(creature.pos)
    game.fx.burst(pos, (150, 112, 74), 28, 340)
    game.fx.spark_burst(pos, (215, 185, 125), 15, 380)
    game.fx.ring(pos, (200, 150, 90))
    game.shake(8)
    audio.play('hit', 0.5)
    r = creature.max_r * 2.2
    for p in game.players:
        if p.dead or getattr(p, 'down', False):
            continue
        if p.pos.distance_to(pos) < r + p.max_r:
            p.hurt(game, safe_norm(p.pos - pos), C.CENT_ERUPT_DMG)
