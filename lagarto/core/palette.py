"""Colour + light helpers for a vivid, glowing look.

Two jobs:
  * generate saturated, randomised creature colours from HSV hue families;
  * fake the "glow / rim light" look (Animal Well) with cached additive sprites
    blitted with ``BLEND_RGB_ADD`` -- no shaders, cheap, and it makes bright
    elements pop off the ground so the palette never reads as "dead".
"""

import colorsys
import random

import pygame


def hsv(h, s, v):
    """h in [0,360], s/v in [0,1] -> (r,g,b) 0-255."""
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, max(0.0, min(1, s)), max(0.0, min(1, v)))
    return (int(r * 255), int(g * 255), int(b * 255))


def vibrant(hue, sat=0.82, val=1.0):
    return hsv(hue, sat, val)


# hue families for creature colours (centre hue, spread)
FAMILIES = {
    'green':   (128, 34),
    'lime':    (95, 22),
    'cyan':    (185, 26),
    'blue':    (215, 26),
    'purple':  (270, 30),
    'magenta': (315, 26),
    'red':     (2, 16),
    'orange':  (28, 18),
    'yellow':  (50, 16),
    'teal':    (165, 22),
}


def random_in_family(family, rng=random, sat=(0.7, 0.95), val=(0.85, 1.0)):
    hue_c, spread = FAMILIES.get(family, (0, 180))
    h = hue_c + rng.uniform(-spread, spread)
    return hsv(h, rng.uniform(*sat), rng.uniform(*val))


def lighten(color, t):
    return tuple(int(c + (255 - c) * t) for c in color[:3])


def darken(color, t):
    return tuple(int(c * (1 - t)) for c in color[:3])


def health_color(f):
    """Green -> yellow -> red ramp. A 2-stop red/green mix goes muddy olive at 50%."""
    f = 0.0 if f < 0 else (1.0 if f > 1 else f)
    red, yellow, green = (240, 60, 60), (250, 200, 60), (110, 235, 110)
    if f >= 0.5:
        return mix(yellow, green, (f - 0.5) * 2)
    return mix(red, yellow, f * 2)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# --------------------------------------------------------------------------- #
#  Additive glow (cached radial sprites, blitted with BLEND_RGB_ADD)           #
# --------------------------------------------------------------------------- #

_GLOW_CACHE = {}
_GLOW_MAX = 900          # hard ceiling: see the note in glow() about unbounded growth
# diagnostics (read by the perf overlay): misses are what cost -- each one is a
# surface allocation plus 10 filled circles. A steady stream of them means the
# cache is thrashing; entries climbing forever means it is leaking.
_hits = 0
_misses = 0
_clears = 0


def glow_stats():
    """(entries, bytes, hits, misses, clears) -- for the F3 perf overlay."""
    total = 0
    for s in _GLOW_CACHE.values():
        w, h = s.get_size()
        total += w * h * 4
    return len(_GLOW_CACHE), total, _hits, _misses, _clears


def _quantise_radius(radius):
    """Snap the radius to a step that grows with size (invisible, bounds the cache)."""
    r = int(radius)
    if r < 2:
        return 2
    step = 2 if r < 16 else (4 if r < 48 else 8)
    return max(2, (r // step) * step)


def _glow_sprite(radius, color):
    global _hits, _misses, _clears
    key = (radius, color)
    surf = _GLOW_CACHE.get(key)
    if surf is not None:
        _hits += 1
    else:
        _misses += 1
        if len(_GLOW_CACHE) >= _GLOW_MAX:
            # cheaper and more predictable than an LRU; the working set rebuilds
            # in a few frames and the common keys are hit again immediately
            _GLOW_CACHE.clear()
            _clears += 1
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        # Steps cost NOTHING per frame -- this runs on a cache miss only (measured:
        # 14 misses in 4000 bullet draws). Ten of them banded visibly once bullets
        # got big and took a second additive pass: the falloff showed as concentric
        # rings instead of a glow. Scale the count with the radius so a small
        # sprite does not pay for smoothness nobody can see.
        steps = 10 if radius < 20 else (18 if radius < 60 else 26)
        for i in range(steps, 0, -1):
            t = i / steps
            r = int(radius * t)
            # brighter toward the centre; additive so RGB is what matters
            fall = (1 - t) ** 1.6
            col = (int(color[0] * fall), int(color[1] * fall), int(color[2] * fall))
            pygame.draw.circle(surf, col, (radius, radius), r)
        _GLOW_CACHE[key] = surf
    return surf


def glow(surf, center, radius, color, intensity=1.0):
    """Additive radial glow, drawn from a cached sprite.

    The cache key MUST be coarse. All three inputs are effectively continuous in
    practice -- radius shrinks with particle life and scales with camera zoom,
    intensity is a sine pulse at many call sites, and every creature spawns with a
    random colour -- so keying on the raw values grew the cache without bound
    (measured: 115 MB of surfaces and still climbing after ~7 min of play, which is
    what made long sessions stutter). Quantising collapses those into families.
    """
    if intensity != 1.0:
        color = (color[0] * intensity, color[1] * intensity, color[2] * intensity)
    # 4 bits per channel: pulsing intensities and near-identical creature colours
    # collapse onto the same sprite, and additive glow hides the banding
    color = (int(color[0]) & 0xF0, int(color[1]) & 0xF0, int(color[2]) & 0xF0)
    radius = _quantise_radius(radius)
    sprite = _glow_sprite(radius, color)
    surf.blit(sprite, (int(center[0] - radius), int(center[1] - radius)),
              special_flags=pygame.BLEND_RGB_ADD)
