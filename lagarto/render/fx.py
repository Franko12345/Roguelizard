"""Juice: pooled particles, velocity-stretched sparks, rings, floating text, shadows.

Particles and sparks are capped (oldest dropped) so a busy screen never blows up
allocation. Bright bits get an additive glow (see ``palette``) so the vivid look
reads even against the dark ground. Everything here is cosmetic and cullable.
"""

import math
import random
from pygame import Vector2
import pygame

from ..core import config as C
from ..core import palette
from ..core.mathutil import vfrom_angle, random_dir, angle_of

# Half-angle of a directional spark burst. Small on purpose: the whole point of
# a directional burst is that the angle IS the information, and a wide cone
# reads as the same puff the omnidirectional call already makes.
_CONE = 22.0


class FX:
    MAX = 700
    MAX_SPARKS = 260

    def __init__(self):
        # particle: [x, y, vx, vy, life, maxlife, r, color, grav, glow]
        self.parts = []
        # spark: [x, y, vx, vy, life, maxlife, color]
        self.sparks = []
        self.rings = []     # [x, y, age, life, color]
        self.floats = []    # [x, y, vy, age, life, text, color]

    # ---- spawn ---------------------------------------------------------- #
    def _add(self, x, y, vx, vy, life, r, color, grav, glow=False):
        if len(self.parts) >= self.MAX:
            self.parts.pop(0)
        self.parts.append([x, y, vx, vy, life, life, r, color, grav, glow])

    def burst(self, pos, color, n, speed):
        for _ in range(n):
            v = random_dir(random.uniform(0.3, 1.0) * speed)
            self._add(pos.x, pos.y, v.x, v.y, random.uniform(0.3, 0.6),
                      random.uniform(3, 6), color, 240, glow=True)

    def spark_burst(self, pos, color, n, speed, direction=None, life=0.5):
        """Sparks out of ``pos``. Omnidirectional by default -- an impact has no
        heading. Pass ``direction`` (a Vector2) and the burst becomes a narrow
        cone around it, which is what makes a bullet's backward sparks read as
        motion instead of a puff. ``life`` is the longest one lives; they die
        anywhere from half of it to all of it.
        """
        ang = angle_of(direction) if direction is not None else None
        for _ in range(n):
            if len(self.sparks) >= self.MAX_SPARKS:
                self.sparks.pop(0)
            mag = random.uniform(0.4, 1.0) * speed
            v = (random_dir(mag) if ang is None else
                 vfrom_angle(ang + random.uniform(-_CONE, _CONE), mag))
            self.sparks.append([pos.x, pos.y, v.x, v.y,
                                random.uniform(life * 0.5, life), life, color])

    def dust(self, pos):
        for _ in range(3):
            v = random_dir(random.uniform(6, 26))
            self._add(pos.x, pos.y, v.x, v.y - 10, random.uniform(0.25, 0.5),
                      random.uniform(2, 4), (150, 140, 180), 40)

    def trail(self, pos, color):
        self._add(pos.x + random.uniform(-6, 6), pos.y + random.uniform(-6, 6),
                  0, 0, 0.35, random.uniform(5, 9), color, 0, glow=True)

    def ring(self, pos, color):
        self.rings.append([pos.x, pos.y, 0.0, 0.4, color])

    def popup(self, pos, text, color=C.COL_WHITE):
        self.floats.append([pos.x, pos.y, -40.0, 0.0, 0.9, str(text), color])

    # ---- update --------------------------------------------------------- #
    def update(self, dt):
        alive = []
        for p in self.parts:
            p[4] -= dt
            if p[4] <= 0:
                continue
            p[3] += p[8] * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= math.exp(-2.0 * dt)
            alive.append(p)
        self.parts = alive

        live_s = []
        for s in self.sparks:
            s[4] -= dt
            if s[4] <= 0:
                continue
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[2] *= math.exp(-4.0 * dt)     # sparks brake fast
            s[3] *= math.exp(-4.0 * dt)
            live_s.append(s)
        self.sparks = live_s

        self.rings = [r for r in self.rings if (r.__setitem__(2, r[2] + dt) or r[2] < r[3])]

        alive_f = []
        for f in self.floats:
            f[3] += dt
            f[1] += f[2] * dt
            if f[3] < f[4]:
                alive_f.append(f)
        self.floats = alive_f

    # ---- draw ----------------------------------------------------------- #
    def draw(self, surf, cam, font):
        z = cam.zoom
        for p in self.parts:
            f = p[4] / p[5]
            sp = cam.w2s(Vector2(p[0], p[1]))
            if not (-20 < sp[0] < C.WIDTH + 20 and -20 < sp[1] < C.HEIGHT + 20):
                continue
            r = max(1, int(p[6] * f * z))
            if p[9] and r >= 2:
                palette.glow(surf, sp, r * 2.6, p[7], 0.45)
            pygame.draw.circle(surf, p[7], sp, r)

        for x, y, vx, vy, life, maxlife, color in self.sparks:
            sp = cam.w2s(Vector2(x, y))
            if not (-20 < sp[0] < C.WIDTH + 20 and -20 < sp[1] < C.HEIGHT + 20):
                continue
            speed = math.hypot(vx, vy)
            if speed < 1:
                continue
            f = life / maxlife
            dx, dy = vx / speed, vy / speed
            ln = (5 + speed * 0.05) * f * z
            wd = max(1.0, 2.2 * f * z)
            hx, hy = sp[0] + dx * ln, sp[1] + dy * ln
            tx, ty = sp[0] - dx * ln * 1.6, sp[1] - dy * ln * 1.6
            px, py = -dy * wd, dx * wd
            pygame.draw.polygon(surf, palette.lighten(color, 0.4),
                                [(hx, hy), (sp[0] + px, sp[1] + py), (tx, ty),
                                 (sp[0] - px, sp[1] - py)])

        for x, y, age, life, color in self.rings:
            f = age / life
            sp = cam.w2s(Vector2(x, y))
            w = max(1, int(4 * (1 - f) * z))
            pygame.draw.circle(surf, palette.lighten(color, 0.2 * (1 - f)), sp,
                               int((10 + 60 * f) * z), w)

        for x, y, vy, age, life, text, color in self.floats:
            sp = cam.w2s(Vector2(x, y))
            img = font.render(text, True, color)
            surf.blit(img, (sp[0] - img.get_width() // 2, sp[1] - img.get_height()))


_SHADOW_CACHE = {}


def shadow(surf, center, r):
    r = min(int(r), 90)
    if r < 1:
        return
    sh = _SHADOW_CACHE.get(r)
    if sh is None:
        sh = pygame.Surface((r * 2, r), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 80), (0, 0, r * 2, r))
        _SHADOW_CACHE[r] = sh
    surf.blit(sh, (center[0] - r, center[1] - r // 2))
