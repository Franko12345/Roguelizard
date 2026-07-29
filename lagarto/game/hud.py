"""Pure HUD drawing primitives -- no game state, no ``game`` argument.

Everything here is a function of ``(surf, ...)`` plus plain numbers/colours, so
it can be called from any state module without dragging the state machine in.
Anything that has to *read* the run (player health, wave, combo) belongs in the
state module that draws it, not here.
"""

import math

import pygame
from pygame import Vector2

from ..core import config as C
from ..core.mathutil import pulse, vfrom_angle
from ..core import palette
from ..render import ui


def bar_tail(surf, bx, by, h, color, phase, t):
    """A little lizard TAIL wagging off the top of the bar.

    Same vocabulary as the real body (``spine.RADII_PROFILE``): a curved chain
    that tapers to a point, not a stick with a bead on the end. Drawn as a run of
    filled circles shrinking base->tip; the sway grows toward the tip so the last
    segments whip like a follow-through.
    """
    n = 9
    length = h * 1.5                       # long and whippy, still clears the label row
    r0 = max(2.0, h * 0.32)                # slimmer root than a leaf
    core = palette.lighten(color, 0.3)
    for k in range(n):
        f = k / (n - 1)
        py = by - f * length
        # tip sways most; a phase per tail so they don't wag in unison
        px = bx + math.sin(t * 3.4 + phase + f * 2.6) * (h * 0.62) * f * f
        r = max(1, int(r0 * (1.0 - f) ** 1.3 + 0.8))   # curved taper -> pointed tip
        pygame.draw.circle(surf, color, (int(px), int(py)), r)
        if r > 2:                                   # top-left highlight = light source
            pygame.draw.circle(surf, core,
                               (int(px - r * 0.3), int(py - r * 0.3)), max(1, r // 2))


def bio_bar(surf, x, y, w, h, frac, color, t, flagella=0, glow=None):
    """An organic 'membrane sac' bar instead of a flat rectangle.

    Drawn entirely with primitives (no per-frame Surface -- the ui._tint rule),
    animated purely by ``t`` so it costs the same whether it moves or not:
      * a dark rounded capsule (the sac),
      * a fill whose leading edge bulges and breathes,
      * a soft inner highlight up top (a light source), and
      * optional flagella -- little cilia that sway off the fill's leading edge,
        which is what sells "biological" at a glance.
    """
    frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
    r = h // 2
    cap = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, (16, 18, 28), cap, border_radius=r)
    fw = int(w * frac)
    if fw > 1:
        fill = pygame.Rect(x, y, fw, h)
        pygame.draw.rect(surf, palette.darken(color, 0.25), fill, border_radius=r)
        # top meniscus: a lighter band with a slow breathing wobble
        band_h = max(2, h // 3)
        pygame.draw.rect(surf, palette.lighten(color, 0.35),
                         (x, y + 1, fw, band_h), border_radius=r)
        # leading-edge bulge, pulsing -- reads as fluid under pressure
        bulge = int(h * (0.55 + 0.12 * math.sin(t * 3.0)))
        tip = (x + fw, y + h // 2)
        palette.glow(surf, tip, bulge, color, 0.5)
        pygame.draw.circle(surf, palette.lighten(color, 0.5), tip, max(2, h // 3))
        for k in range(flagella):
            fx = x + int(fw * (k + 0.5) / max(1, flagella))
            bar_tail(surf, fx, y + 1, h, color, phase=k * 2.1, t=t)
    if glow:
        palette.glow(surf, (x + fw, y + h // 2), h, color, 0.25)
    # living rim
    pygame.draw.rect(surf, palette.lighten(color, 0.15) if frac > 0 else (40, 44, 60),
                     cap, 2, border_radius=r)


class Bellows:
    def __init__(self, fraction=1.0):
        self.fraction = fraction
        self.velocity = 0.0

    def update(self, target, dt):
        target = max(0.0, min(1.0, target))
        self.velocity += (target - self.fraction) * 110.0 * dt
        self.velocity *= math.exp(-12.0 * dt)
        self.fraction += self.velocity * dt
        self.fraction = max(0.0, min(1.08, self.fraction))


def draw_bellows(surf, rect, bellows, color=(96, 206, 240)):
    x, y, w, h = rect
    inflation = max(0.0, min(1.0, bellows.fraction))
    body_h = max(8, int(h * (0.42 + 0.58 * inflation)))
    top = y + (h - body_h) // 2
    body = pygame.Rect(x, top, w, body_h)
    pygame.draw.ellipse(surf, (16, 18, 28), body)
    inner = body.inflate(-4, -4)
    if inner.width > 0 and inner.height > 0:
        pygame.draw.ellipse(surf, palette.darken(color, 0.22), inner)
    folds = 7
    for i in range(1, folds):
        fx = x + int(w * i / folds)
        inset = int(2 + (1.0 - inflation) * 5)
        pygame.draw.line(surf, palette.lighten(color, 0.2),
                         (fx, top + inset), (fx, top + body_h - inset), 1)
    pygame.draw.ellipse(surf, palette.lighten(color, 0.18), body, 2)


class CranialFluid:
    POINTS = 16
    STEP = 1.0 / 30.0

    def __init__(self):
        self.heights = [0.0] * self.POINTS
        self.velocities = [0.0] * self.POINTS
        self.accumulator = 0.0
        self.last_fraction = 0.0

    def impulse(self, strength):
        mid = self.POINTS // 2
        self.velocities[mid] += strength
        self.velocities[mid - 1] += strength * 0.55

    def update(self, fraction, dt):
        fraction = max(0.0, min(1.0, fraction))
        delta = fraction - self.last_fraction
        if abs(delta) > 0.001:
            self.impulse(delta * 7.0)
        self.last_fraction = fraction
        self.accumulator += min(dt, 0.1)
        while self.accumulator >= self.STEP:
            accelerations = []
            for i, height in enumerate(self.heights):
                left = self.heights[i - 1] if i else height
                right = self.heights[i + 1] if i + 1 < self.POINTS else height
                accelerations.append((left + right - 2.0 * height) * 72.0)
            for i in range(self.POINTS):
                self.velocities[i] += accelerations[i] * self.STEP
                self.velocities[i] *= math.exp(-5.5 * self.STEP)
                self.heights[i] += self.velocities[i] * self.STEP
            self.accumulator -= self.STEP

    @property
    def amplitude(self):
        return max(abs(height) for height in self.heights)


def brain_size(level):
    return min(0.72, 0.42 + 0.045 * math.sqrt(max(0, level - 1)))


def brain_folds(level):
    return max(1, level * 2 - 1)


def draw_skull(surf, rect, level, xp_fraction, fluid):
    x, y, w, h = rect
    skull = pygame.Rect(x, y, w, h)
    bone = (210, 204, 176)
    pygame.draw.ellipse(surf, (18, 20, 30), skull)
    fluid_y = y + h - 4 - int((h - 8) * max(0.0, min(1.0, xp_fraction)))
    points = [(x + 3, y + h - 3)]
    for i, wave in enumerate(fluid.heights):
        px = x + 3 + (w - 6) * i / (fluid.POINTS - 1)
        points.append((px, fluid_y + wave * h * 0.18))
    points.append((x + w - 3, y + h - 3))
    if xp_fraction > 0:
        pygame.draw.polygon(surf, (174, 141, 38), points)
        pygame.draw.lines(surf, (245, 205, 84), False, points[1:-1], 2)
    size = brain_size(level)
    bw = int(w * size)
    bh = int(h * size * 0.68)
    brain = pygame.Rect(x + (w - bw) // 2, y + 5, bw, bh)
    pygame.draw.ellipse(surf, (190, 98, 132), brain)
    folds = brain_folds(level)
    for i in range(folds):
        angle = math.pi * (i + 1) / (folds + 1)
        cx = brain.centerx + int(math.cos(angle) * bw * 0.35)
        cy = brain.centery + int(math.sin(angle * 2.0) * bh * 0.18)
        pygame.draw.arc(surf, (112, 51, 82), (cx - 3, cy - 7, 7, 14),
                        -math.pi / 2, math.pi / 2, 1)
    pygame.draw.ellipse(surf, bone, skull, 2)


def dial(surf, center, r, frac, color, font, label, t, enabled=True):
    """Radial cooldown dial: fills as the ability recharges, pulses when ready.

    ``enabled=False`` (not enough energy) greys the whole thing out.
    """
    ready = frac >= 0.999 and enabled
    if not enabled:
        color = (78, 82, 104)
    pygame.draw.circle(surf, (34, 38, 54), center, r)
    if frac > 0:
        pts = [center]
        steps = max(3, int(frac * 22))
        for i in range(steps + 1):
            pts.append(center + vfrom_angle(-90 + 360 * frac * (i / steps), r))
        if len(pts) >= 3:
            pygame.draw.polygon(surf, color, pts)
    if ready:
        palette.glow(surf, center, r * 2.2, color, 0.35 + 0.25 * pulse(t, 6))
    pygame.draw.circle(surf, (96, 102, 136) if not ready else color, center, r, 2)
    ui.text(surf, font, label, (center[0] + r + 6, center[1] - font.get_height() // 2),
            (232, 234, 250) if ready else (146, 150, 178))


_VIGNETTE = None


def vignette(surf):
    """Smooth radial dark edges so the vivid centre pops (built once, then blitted)."""
    global _VIGNETTE
    if _VIGNETTE is None:
        s = 80
        small = pygame.Surface((s, s), pygame.SRCALPHA)
        cx = cy = (s - 1) / 2.0
        maxd = (cx * cx + cy * cy) ** 0.5
        for y in range(s):
            for x in range(s):
                d = (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / maxd
                a = 0 if d < 0.4 else int(150 * ((d - 0.4) / 0.6) ** 2)
                small.set_at((x, y), (0, 0, 0, min(150, a)))
        _VIGNETTE = pygame.transform.smoothscale(small, (C.WIDTH, C.HEIGHT))
    surf.blit(_VIGNETTE, (0, 0))


def draw_offscreen(surf, targets, cam, limit=22):
    """Edge arrows pointing at things you can't see -> find stragglers.

    ``targets`` is a sequence of ``(world_pos, colour)``; picking *what* deserves
    an arrow is the caller's business.
    """
    cx, cy = C.WIDTH / 2, C.HEIGHT / 2
    hw, hh = cx - 28, cy - 28
    shown = 0
    for pos, col in targets:
        sp = cam.w2s(pos)
        if -12 < sp[0] < C.WIDTH + 12 and -12 < sp[1] < C.HEIGHT + 12:
            continue
        d = Vector2(sp[0] - cx, sp[1] - cy)
        if d.length_squared() < 1:
            continue
        scale = min(hw / abs(d.x) if d.x else 1e9, hh / abs(d.y) if d.y else 1e9)
        c = Vector2(cx, cy) + d * scale
        ang = d.as_polar()[1]
        tip = c + vfrom_angle(ang, 12)
        b1 = c + vfrom_angle(ang + 138, 10)
        b2 = c + vfrom_angle(ang - 138, 10)
        palette.glow(surf, (int(c.x), int(c.y)), 16, col, 0.5)
        pygame.draw.polygon(surf, col, [tip, b1, b2])
        pygame.draw.polygon(surf, C.COL_INK, [tip, b1, b2], 1)
        shown += 1
        if shown >= limit:
            break


class TopStack:
    """Vertical layout for the top-centre column.

    Six things live there -- score, wave line, combo, theme banner, boss name and
    boss bar -- and each used to hardcode its own ``y`` with no idea of the others.
    On a boss wave with a live combo that was *three* overlaps at once, and the
    banner writes for 2.2s exactly when the boss spawns, so it was guaranteed to
    be seen. Now every element asks for the height it needs and gets the next free
    band, which also means new elements (boss phase bars, Phase 4) can never
    silently land on top of an existing one.

    Elements reserve in draw order, so the caller must draw top-down: HUD, then
    banner, then boss bar.
    """

    def __init__(self, top=10, gap=4):
        self.top = top
        self.gap = gap
        self.y = top

    def reset(self):
        self.y = self.top

    def take(self, h):
        """Reserve a band ``h`` tall and return its top ``y``."""
        y = self.y
        self.y += h + self.gap
        return y
