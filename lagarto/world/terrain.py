"""World / environment: biome ground tiles, swaying procedural flora, ambient motes.

The arena used to be an empty dotted void. This fills it with a living ecosystem
(inspired by animal-evolution games): the ground is tiled into biomes with their
own colours, and each biome is scattered with its own props -- grass, flowers,
bushes, mushrooms, reeds, lily pads, rocks, cacti -- that sway procedurally.
Everything is culled to the visible area, so a full world stays cheap.

Issue #110: the ``static_lights`` list is the [Fonte de luz](../concepts/lighting.md)
pool that the ambient layer reads each frame. Built once at construction
(glow-capable props + firefly motes), reused forever.
"""

import math
import random
from pygame import Vector2
import pygame

from ..core import config as C
from ..core import palette
from ..core.mathutil import vfrom_angle, pulse
from ..render.lighting import Light

CELL = 128          # ground tile size (world units)
VOID = (14, 12, 26)

# Prop kinds that shed a soft static light at their position. Deliberately a
# subset: ~54 pickups are off the list on purpose (the print turns into a
# flicker) and rock/boulder/cactus are too hard-edged to read as glow. See
# docs/concepts/lighting.md.
_LIGHT_PROP_KINDS = frozenset(('mushroom', 'flower', 'lily', 'reed', 'bush'))

# vivid, saturated biome grounds (dark bg makes the glowing creatures pop)
BIOMES = {
    'meadow': dict(ground=(46, 116, 66), water=False,
                   props=['tuft', 'tuft', 'tuft', 'flower', 'flower', 'bush', 'mushroom'],
                   flora=(92, 214, 108),
                   flowers=[(255, 110, 168), (255, 224, 88), (168, 120, 255), (96, 214, 255)]),
    'sand':   dict(ground=(132, 104, 56), water=False,
                   props=['dtuft', 'dtuft', 'rock', 'rock', 'cactus', 'flower'],
                   flora=(196, 168, 84),
                   flowers=[(255, 190, 84), (255, 120, 110)]),
    'swamp':  dict(ground=(28, 108, 116), water=True,
                   props=['reed', 'reed', 'lily', 'mushroom', 'bush', 'tuft'],
                   flora=(70, 196, 168),
                   flowers=[(168, 120, 255), (96, 240, 210)]),
    'rock':   dict(ground=(86, 66, 128), water=False,
                   props=['rock', 'rock', 'boulder', 'dtuft', 'tuft'],
                   flora=(176, 140, 236),
                   flowers=[(220, 150, 255)]),
}
BIOME_KEYS = list(BIOMES.keys())


class World:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.time = 0.0
        # biome centres on a jittered grid so regions are coherent blobs
        self.centres = []
        grid = 3
        for gx in range(grid):
            for gy in range(grid):
                cx = (gx + 0.5) / grid * C.WORLD_W + self.rng.uniform(-360, 360)
                cy = (gy + 0.5) / grid * C.WORLD_H + self.rng.uniform(-360, 360)
                key = BIOME_KEYS[(gx * grid + gy + self.rng.randint(0, 3)) % len(BIOME_KEYS)]
                self.centres.append((Vector2(cx, cy), key))
        self._cell_cache = {}

        # scatter props across the world (~ one per 150px cell)
        self.props = []
        # Issue #110: glow-capable props register a [Fonte de luz][1] here so the
        # ambient layer can read them. Mushrooms, flowers, lilies, reeds, bushes
        # only -- the print lights up only what "glows" in the biome palette.
        # [1]: ../concepts/lighting.md
        self.static_lights = []
        n = int((C.WORLD_W / 150) * (C.WORLD_H / 150))
        for _ in range(n):
            p = Vector2(self.rng.uniform(40, C.WORLD_W - 40),
                        self.rng.uniform(40, C.WORLD_H - 40))
            b = BIOMES[self.biome_at(p)]
            typ = self.rng.choice(b['props'])
            size = self.rng.uniform(0.8, 1.5)
            phase = self.rng.uniform(0, C.TAU)
            if typ in ('flower',):
                color = self.rng.choice(b['flowers'])
            else:
                color = b['flora']
            self.props.append((p.x, p.y, typ, size, phase, color))
            if typ in _LIGHT_PROP_KINDS:
                # flower colour carries the bloom; everything else inherits
                # the biome flora tint (the ambient motes already do this)
                light_col = color if typ == 'flower' else (
                    min(255, int(color[0] * 1.4) + 18),
                    min(255, int(color[1] * 1.3) + 16),
                    min(255, int(color[2] * 1.0) + 8),
                )
                self.static_lights.append(
                    Light(Vector2(p.x, p.y), light_col, C.PROP_LIGHT_R,
                          intensity=0.5, kind='prop'))

        # ambient drifting motes (pollen / fireflies) near-uniform in world
        self.motes = [(self.rng.uniform(0, C.WORLD_W), self.rng.uniform(0, C.WORLD_H),
                       self.rng.uniform(0, C.TAU), self.rng.uniform(6, 14))
                      for _ in range(130)]

    # ---- biome lookup --------------------------------------------------- #
    def biome_at(self, pos):
        best, bd = 'meadow', 1e18
        for c, key in self.centres:
            d = (c.x - pos[0]) ** 2 + (c.y - pos[1]) ** 2
            if d < bd:
                bd, best = d, key
        return best

    def cell_color(self, cx, cy):
        """Returns (color, is_water). Cached per cell."""
        key = (cx, cy)
        entry = self._cell_cache.get(key)
        if entry is None:
            wx, wy = cx * CELL + CELL / 2, cy * CELL + CELL / 2
            if wx < 0 or wy < 0 or wx > C.WORLD_W or wy > C.WORLD_H:
                entry = (VOID, False)
            else:
                # blend biome grounds weighted by distance -> smooth region edges
                r = g = b = wsum = 0.0
                for c, ck in self.centres:
                    d2 = (c.x - wx) ** 2 + (c.y - wy) ** 2
                    w = 1.0 / (d2 + 9000.0) ** 2
                    gc = BIOMES[ck]['ground']
                    r += gc[0] * w; g += gc[1] * w; b += gc[2] * w; wsum += w
                h = (cx * 73856093) ^ (cy * 19349663)
                j = ((h >> 3) & 3) - 1.5      # faint texture only
                col = tuple(max(0, min(255, int(v / wsum + j))) for v in (r, g, b))
                entry = (col, BIOMES[self.biome_at((wx, wy))].get('water', False))
            self._cell_cache[key] = entry
        return entry

    def update(self, dt):
        self.time += dt

    # ---- drawing -------------------------------------------------------- #
    def draw_ground(self, surf, cam):
        z = cam.zoom
        t = self.time
        tl = cam.s2w((0, 0))
        br = cam.s2w((C.WIDTH, C.HEIGHT))
        c0, c1 = int(tl.x // CELL) - 1, int(br.x // CELL) + 1
        r0, r1 = int(tl.y // CELL) - 1, int(br.y // CELL) + 1
        size = int(CELL * z) + 2
        for cx in range(c0, c1 + 1):
            for cy in range(r0, r1 + 1):
                col, water = self.cell_color(cx, cy)
                sp = cam.w2s((cx * CELL, cy * CELL))
                surf.fill(col, (sp[0], sp[1], size, size))
                if water:
                    # animated shimmer bands -> the swamp reads as moving water
                    sh = int(10 + 9 * math.sin(t * 1.6 + cx * 0.9 + cy * 0.5))
                    if sh > 4:
                        band = max(2, size // 5)
                        yoff = int((math.sin(t * 0.8 + cx) * 0.5 + 0.5) * (size - band))
                        surf.fill((sh, sh, sh // 2), (sp[0], sp[1] + yoff, size, band),
                                  special_flags=pygame.BLEND_RGB_ADD)

    def draw_decor(self, surf, cam):
        t = self.time
        z = cam.zoom
        for x, y, typ, size, phase, color in self.props:
            if not cam.visible((x, y), 90):
                continue
            _PROP[typ](surf, cam, x, y, size * z, phase, color, t)

    def draw_ambient(self, surf, cam):
        z = cam.zoom
        t = self.time
        for mx, my, ph, spd in self.motes:
            x = mx + math.sin(t * 0.5 + ph) * 18
            y = my + math.cos(t * 0.4 + ph) * 18
            if not cam.visible((x, y), 30):
                continue
            sp = cam.w2s((x, y))
            g = pulse(t * 2 + ph)                         # twinkle
            palette.glow(surf, sp, (5 + 5 * g) * z,
                         (int(150 * g) + 40, int(150 * g) + 50, 40))
            surf.fill((250, 250, 210), (sp[0], sp[1], max(1, int(1.6 * z)), max(1, int(1.6 * z))))


# --------------------------------------------------------------------------- #
#  Prop drawing (top-down, with a gentle sway on anything with a stem)         #
# --------------------------------------------------------------------------- #

def _sway(size, phase, t, amt=0.28):
    return math.sin(t * 2.0 + phase) * size * amt


def _tuft(surf, cam, x, y, s, phase, color, t, dry=False):
    base = cam.w2s((x, y))
    sw = _sway(s, phase, t)
    col = color
    for i in (-1, 0, 1):
        tipx = x + i * s * 4 + sw + i * 1.5
        tip = cam.w2s((tipx, y - s * (10 if not dry else 7)))
        root = cam.w2s((x + i * s * 3, y))
        pygame.draw.line(surf, col, root, tip, max(1, int(2 * cam.zoom)))


def _dtuft(surf, cam, x, y, s, phase, color, t):
    _tuft(surf, cam, x, y, s, phase, color, t, dry=True)


def _flower(surf, cam, x, y, s, phase, color, t):
    sw = _sway(s, phase, t)
    root = cam.w2s((x, y))
    headw = (x + sw, y - s * 11)
    hp = cam.w2s(headw)
    pygame.draw.line(surf, (70, 150, 84), root, hp, max(1, int(2 * cam.zoom)))
    r = max(2, int(s * 3.4 * cam.zoom))
    for a in range(0, 360, 72):
        pp = cam.w2s((headw[0] + math.cos(math.radians(a)) * s * 2.4,
                      headw[1] + math.sin(math.radians(a)) * s * 2.4))
        pygame.draw.circle(surf, color, pp, r)
    pygame.draw.circle(surf, (250, 230, 120), hp, max(1, int(s * 1.8 * cam.zoom)))


def _bush(surf, cam, x, y, s, phase, color, t):
    sw = _sway(s, phase, t, 0.1)
    for dx, dy, rr in ((-3, 0, 5), (3, 0, 5), (0, -3, 6), (0, 1, 5)):
        p = cam.w2s((x + dx * s + sw, y + dy * s))
        pygame.draw.circle(surf, color, p, max(2, int(rr * s * cam.zoom)))
    hp = cam.w2s((x - s, y - s * 2 + sw))
    pygame.draw.circle(surf, tuple(min(255, c + 26) for c in color),
                       hp, max(1, int(2.4 * s * cam.zoom)))


def _mushroom(surf, cam, x, y, s, phase, color, t):
    root = cam.w2s((x, y))
    cap = cam.w2s((x, y - s * 5))
    pygame.draw.line(surf, (222, 214, 196), root, cap, max(2, int(3 * s * cam.zoom)))
    pygame.draw.circle(surf, (226, 92, 108), cap, max(2, int(4.4 * s * cam.zoom)))
    pygame.draw.circle(surf, (250, 240, 240), (cap[0] - int(2 * s * cam.zoom),
                       cap[1] - int(s * cam.zoom)), max(1, int(1.2 * s * cam.zoom)))


def _reed(surf, cam, x, y, s, phase, color, t):
    sw = _sway(s, phase, t, 0.4)
    for i in (-1, 0, 1):
        root = cam.w2s((x + i * s * 3, y))
        tip = cam.w2s((x + i * s * 3 + sw + i, y - s * 16))
        pygame.draw.line(surf, color, root, tip, max(1, int(2 * cam.zoom)))
        pygame.draw.circle(surf, (150, 110, 70), tip, max(1, int(1.6 * s * cam.zoom)))


def _lily(surf, cam, x, y, s, phase, color, t):
    p = cam.w2s((x, y))
    r = max(3, int(6 * s * cam.zoom))
    pygame.draw.circle(surf, (58, 122, 96), p, r)
    pygame.draw.circle(surf, (44, 100, 78), p, r, max(1, int(cam.zoom)))
    # wedge notch
    pygame.draw.polygon(surf, VOID, [p, (p[0] + r, p[1] - r // 2), (p[0] + r, p[1] + r // 2)])


def _rock(surf, cam, x, y, s, phase, color, t):
    p = cam.w2s((x, y))
    r = max(2, int(4.5 * s * cam.zoom))
    pts = [(p[0] + math.cos(a) * r * (0.8 + 0.3 * ((i * 7 + int(phase * 3)) % 3)),
            p[1] + math.sin(a) * r * 0.8)
           for i, a in enumerate([0, 1.1, 2.3, 3.4, 4.6, 5.6])]
    pygame.draw.polygon(surf, (108, 106, 128), pts)
    pygame.draw.polygon(surf, (70, 68, 90), pts, max(1, int(cam.zoom)))


def _boulder(surf, cam, x, y, s, phase, color, t):
    _rock(surf, cam, x, y, s * 2.1, phase, color, t)


def _cactus(surf, cam, x, y, s, phase, color, t):
    col = (72, 150, 92)
    p0 = cam.w2s((x, y))
    p1 = cam.w2s((x, y - s * 12))
    w = max(3, int(4 * s * cam.zoom))
    pygame.draw.line(surf, col, p0, p1, w)
    arm = cam.w2s((x + s * 5, y - s * 9))
    armup = cam.w2s((x + s * 5, y - s * 13))
    pygame.draw.line(surf, col, cam.w2s((x, y - s * 8)), arm, w)
    pygame.draw.line(surf, col, arm, armup, w)


_PROP = {
    'tuft': _tuft, 'dtuft': _dtuft, 'flower': _flower, 'bush': _bush,
    'mushroom': _mushroom, 'reed': _reed, 'lily': _lily, 'rock': _rock,
    'boulder': _boulder, 'cactus': _cactus,
}
