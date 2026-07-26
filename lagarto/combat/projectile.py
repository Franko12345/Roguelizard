"""Projectiles: ranged attacks (venom spit, spider web, boss shots, player spit).

Kept deliberately small and data-driven: a projectile carries a position, velocity,
damage and an optional on-hit ``effect`` ('poison' / 'slow'). The Game owns the
list, advances them, and resolves hits against players (hostile) or creatures
(friendly). Rendering uses the additive glow so shots read against the ground.
"""

import math
from pygame import Vector2
import pygame

from ..core import config as C
from ..core import palette
from ..core.mathutil import safe_norm


class Projectile:
    def __init__(self, pos, vel, color, dmg=8, effect=None, life=3.5,
                 radius=8, hostile=True):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.color = color
        self.dmg = dmg
        self.effect = effect            # None | 'poison' | 'slow'
        self.life = life
        self.radius = radius
        self.hostile = hostile          # True: hits players; False: hits creatures
        self.dead = False
        self.spin = 0.0
        self.homing = False             # if set, the game curves it toward an enemy
        # piercing shots pass THROUGH enemies (Farpas de Cauda). `_pierced` is the
        # per-projectile "already hit" set, same idea as dash_hits/whip_hits: it
        # runs every frame it overlaps, so without it one dart hits 30x.
        self.pierce = False
        self._pierced = None
        self.trail = []                 # recent world positions -> a Gungeon streak
        # optional payload: dict(r, dmg, life, hue) -> the game drops a puddle
        # wherever this projectile ends, whether it connected or simply landed
        self.puddle = None

    def update(self, dt):
        self.trail.append((self.pos.x, self.pos.y))
        if len(self.trail) > 7:
            self.trail.pop(0)
        self.pos += self.vel * dt
        self.life -= dt
        self.spin += dt * 9
        
        # Bouncing off arena walls (for bouncing_bullets pattern)
        bounces = getattr(self, 'bounces_left', 0)
        if bounces > 0:
            damp = getattr(self, 'bounce_damp', 0.8)
            bounced = False
            if self.pos.x <= 0:
                self.pos.x = 0
                self.vel.x = abs(self.vel.x) * damp
                bounced = True
            elif self.pos.x >= C.WORLD_W:
                self.pos.x = C.WORLD_W
                self.vel.x = -abs(self.vel.x) * damp
                bounced = True
            if self.pos.y <= 0:
                self.pos.y = 0
                self.vel.y = abs(self.vel.y) * damp
                bounced = True
            elif self.pos.y >= C.WORLD_H:
                self.pos.y = C.WORLD_H
                self.vel.y = -abs(self.vel.y) * damp
                bounced = True
            if bounced:
                self.bounces_left = bounces - 1
        
        if self.life <= 0 or self.pos.x < 0 or self.pos.y < 0 \
                or self.pos.x > C.WORLD_W or self.pos.y > C.WORLD_H:
            self.dead = True

    def draw(self, surf, cam):
        z = cam.zoom
        sp = cam.w2s(self.pos)
        r = max(3, int(self.radius * z))
        # trailing streak (fades toward the tail)
        for i, (tx, ty) in enumerate(self.trail):
            f = i / len(self.trail)
            tsp = cam.w2s((tx, ty))
            pygame.draw.circle(surf, palette.mix((30, 28, 44), self.color, f),
                               tsp, max(1, int(r * f * 0.8)))
        # additive halo
        palette.glow(surf, sp, self.radius * 3.4 * z, self.color, 0.75)
        if self.effect == 'slow':       # web: a soft spiky orb
            pts = []
            for k in range(10):
                a = self.spin + k * math.pi / 5
                rr = r * (1.5 if k % 2 == 0 else 0.8)
                pts.append((sp[0] + math.cos(a) * rr, sp[1] + math.sin(a) * rr))
            pygame.draw.polygon(surf, self.color, pts)
            pygame.draw.circle(surf, palette.lighten(self.color, 0.5), sp, max(1, int(r * 0.5)))
        else:                            # bullet: bright core in a coloured shell
            pygame.draw.circle(surf, palette.darken(self.color, 0.15), sp, r)
            pygame.draw.circle(surf, self.color, sp, int(r * 0.8))
            pygame.draw.circle(surf, palette.lighten(self.color, 0.75), sp, max(1, int(r * 0.42)))


def spit(pos, target_pos, color, dmg=8, effect='poison', speed=230, radius=8,
         hostile=True):
    """Aimed venom/spit bullet -- slow enough to read and dodge.

    ``hostile=True`` hits players (enemy attack); ``False`` hits creatures
    (the player's own auto-spit).
    """
    v = safe_norm(Vector2(target_pos) - Vector2(pos)) * speed
    return Projectile(pos, v, color, dmg=dmg, effect=effect, radius=radius, hostile=hostile)


def web(pos, target_pos, color=(220, 230, 240), speed=190):
    """Slow-moving web that slows whatever it hits -- the player's own Teia
    weapon, so ``hostile=False`` (hits creatures). It was hardcoded True: since
    this spawns right at the player's own mouth, it slowed the PLAYER who fired
    it almost every cast instead of the enemy it was aimed at."""
    v = safe_norm(Vector2(target_pos) - Vector2(pos)) * speed
    return Projectile(pos, v, color, dmg=0, effect='slow', life=4.0, radius=9, hostile=False)
