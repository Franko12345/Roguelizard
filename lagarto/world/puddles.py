"""Blood puddles — permanent-ish ground marks that scar the world on damage.

Issue #135: every fight leaves a trace. Player blood stays for the run; enemy
blood fades over LIFETIME seconds. Each puddle is a procedural polygon
(unique gaussian-noise shape), drawn on a separate alpha layer between ground
tiles and decor props.

Distinct from ``combat.weapons.Puddle``: that one is a *hazard* (acid, venom,
boss slams) that deals damage. This one is cosmetic -- no game effect, just
visual history. Same word, two unrelated systems; named here to mirror the
issue spec, not the existing weapon.
"""

import math
import random

import pygame
from pygame import Vector2


LIFETIME = 30.0                # enemy blood: alpha 200->0, radius 1->0 over this
ALPHA_START = 200              # initial alpha for every fresh puddle
COL_BLOOD = (180, 20, 20)      # player blood RGB (issue #135)
PUDDLE_CAP = 200               # hard cap on the world list
BASE_RADIUS = 6.0              # baseline puddle radius (world units)
RADIUS_PER_DMG = 0.4           # bigger hits make bigger puddles, capped


def darken_species_color(color):
    """Half-strength species colour, clamped so no channel collapses to black."""
    return tuple(max(30, int(c * 0.5)) for c in color[:3])


class Puddle:
    """A single blood decal. Geometry is generated once and reused.

    ``lifetime`` is -1 for permanent (player blood) and LIFETIME for enemy
    blood. ``age`` and ``alpha`` are ticked in ``update``; the polygon itself
    is pre-computed and only re-scaled at draw time.
    """

    __slots__ = ('pos', 'base_radius', 'color', 'vertices',
                 'lifetime', 'age', 'alpha')

    def __init__(self, pos, base_radius, color, vertices, lifetime=-1.0):
        self.pos = Vector2(pos)
        self.base_radius = base_radius
        self.color = color
        self.vertices = vertices
        self.lifetime = lifetime
        self.age = 0.0
        self.alpha = float(ALPHA_START)

    @classmethod
    def make(cls, pos, dmg, color, permanent=False):
        """Build a puddle of the right size at ``pos``.

        Bigger hits = bigger puddle; the random radius noise (gauss) keeps
        every shape unique. Vertices are pre-baked so the draw path stays
        cheap -- the only per-frame work is the alpha/radius lerp.
        """
        base_r = BASE_RADIUS + min(dmg, 30) * RADIUS_PER_DMG
        sigma = base_r * 0.15
        verts = []
        for i in range(10):
            ang = (i / 10) * math.tau
            r = random.gauss(base_r, sigma)
            verts.append((pos[0] + math.cos(ang) * r,
                          pos[1] + math.sin(ang) * r))
        return cls(pos, base_r, color, verts,
                   lifetime=-1.0 if permanent else LIFETIME)

    def update(self, dt):
        if self.lifetime < 0.0:               # permanent player blood: frozen
            return
        self.age += dt
        t = min(1.0, self.age / self.lifetime)
        self.alpha = (1.0 - t) * ALPHA_START

    def draw(self, surf, cam):
        """Draw onto an SRCALPHA surface (the world layer). Camera culled.

        Vertices are in world space; ``cam.w2s`` does the affine transform.
        Scale tracks the lifetime lerp so enemy puddles shrink as they fade.
        """
        if not cam.visible(self.pos, self.base_radius + 16):
            return
        if self.lifetime > 0.0 and self.age > 0.0:
            scale = 1.0 - min(1.0, self.age / self.lifetime)
        else:
            scale = 1.0
        verts = self.vertices
        cx, cy = self.pos.x, self.pos.y
        z = cam._z
        ox = cam._ox - cx * scale * z
        oy = cam._oy - cy * scale * z
        screen = [(int(vx * scale * z + ox), int(vy * scale * z + oy))
                  for vx, vy in verts]
        if self.alpha <= 0:
            return
        pygame.draw.polygon(surf, (*self.color, int(self.alpha)), screen)
