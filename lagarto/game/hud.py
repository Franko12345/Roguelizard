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


HEALTH_SAC_HP = 25.0
HEALTH_SACS_PER_ROW = 8
HEALTH_SAC_MAX_ROWS = 2
HEALTH_SAC_SIZE = 18
HEALTH_SAC_GAP = 4


def health_sac_fills(health, max_health):
    count = max(1, math.ceil(max(0.0, max_health) / HEALTH_SAC_HP))
    remaining = max(0.0, min(float(health), float(max_health)))
    return [max(0.0, min(1.0, (remaining - i * HEALTH_SAC_HP) / HEALTH_SAC_HP))
            for i in range(count)]


def health_sac_layout(max_health, width):
    count = max(1, math.ceil(max(0.0, max_health) / HEALTH_SAC_HP))
    rows = min(HEALTH_SAC_MAX_ROWS, math.ceil(count / HEALTH_SACS_PER_ROW))
    columns = math.ceil(count / rows)
    size = min(HEALTH_SAC_SIZE, (width - HEALTH_SAC_GAP * (columns - 1)) / columns)
    return count, rows, columns, max(6.0, size)


def health_panic_rate(frac):
    frac = max(0.0, min(1.0, frac))
    return 2.2 + (1.0 - frac) * 7.8


def health_sacs_bounds(x, y, max_health, width):
    count, rows, columns, size = health_sac_layout(max_health, width)
    used_columns = min(columns, count)
    used_width = used_columns * size + max(0, used_columns - 1) * HEALTH_SAC_GAP
    used_height = rows * size + max(0, rows - 1) * HEALTH_SAC_GAP
    return pygame.Rect(x, y - used_height + size, math.ceil(used_width), math.ceil(used_height))


def _draw_artery(surf, centers, color):
    if len(centers) < 2:
        return
    root = palette.darken(color, 0.35)
    for a, b in zip(centers, centers[1:]):
        distance = Vector2(b).distance_to(a)
        steps = max(2, int(distance / 3))
        for step in range(steps + 1):
            f = step / steps
            p = Vector2(a).lerp(b, f)
            pygame.draw.circle(surf, root, (round(p.x), round(p.y)), max(1, round(2.4 - f)))


def draw_health_sacs(surf, x, y, width, health, max_health, t, impact=0.0):
    fills = health_sac_fills(health, max_health)
    count, rows, columns, size = health_sac_layout(max_health, width)
    frac = max(0.0, min(1.0, health / max(0.001, max_health)))
    panic = 1.0 - frac
    rate = health_panic_rate(frac)
    beat = (0.5 + 0.5 * math.sin(t * rate)) * panic
    color = palette.mix((148, 54, 62), (255, 42, 58), min(1.0, panic * 0.85 + beat * 0.35))
    row_counts = [min(columns, count - row * columns) for row in range(rows)]
    centers = []
    positions = []
    index = 0
    for row in range(rows):
        row_width = row_counts[row] * size + max(0, row_counts[row] - 1) * HEALTH_SAC_GAP
        row_x = x + (width - row_width) / 2
        cy = y - row * (size + HEALTH_SAC_GAP) + size / 2
        row_centers = []
        for column in range(row_counts[row]):
            cx = row_x + column * (size + HEALTH_SAC_GAP) + size / 2
            sway = math.sin(t * 4.1 + index * 1.7) * impact * (1.5 + row * 0.5)
            row_centers.append((cx, cy + sway))
            positions.append((cx, cy + sway, index))
            index += 1
        centers.append(row_centers)
    for row_centers in centers:
        _draw_artery(surf, row_centers, color)
    shell = (52, 30, 38)
    empty = (25, 20, 29)
    rim = palette.lighten(color, 0.12)
    active = next((i for i, fill in enumerate(fills) if fill < 1.0), count - 1)
    for cx, cy, index in positions:
        fill = fills[index]
        neighbour = max(0.0, 1.0 - abs(index - active) / 2.0)
        bulge = impact * neighbour * 1.8 + beat * 0.8
        radius = max(3, round(size * 0.42 + bulge))
        center = (round(cx), round(cy))
        pygame.draw.circle(surf, shell, center, radius + 1)
        pygame.draw.circle(surf, empty, center, radius)
        if fill > 0:
            fluid_h = max(1, round(radius * 2 * fill))
            pygame.draw.circle(surf, color, center, radius)
            empty_h = radius * 2 - fluid_h
            if empty_h > 0:
                cover = pygame.Rect(center[0] - radius - 1, center[1] - radius - 1,
                                    radius * 2 + 2, empty_h + 1)
                pygame.draw.rect(surf, empty, cover)
            meniscus = pygame.Rect(center[0] - radius, center[1] + radius - fluid_h - 1,
                                   radius * 2, max(2, min(4, fluid_h)))
            pygame.draw.ellipse(surf, palette.lighten(color, 0.12), meniscus)
            if count <= 16 or index in {active - 1, active, active + 1}:
                pygame.draw.circle(surf, palette.lighten(color, 0.55),
                                   (center[0] - radius // 3, center[1] - radius // 3),
                                   max(1, radius // 4))
        else:
            residue = pygame.Rect(center[0] - radius // 2, center[1] + radius // 2,
                                  radius, max(1, radius // 4))
            pygame.draw.ellipse(surf, palette.darken(color, 0.55), residue)
        pygame.draw.circle(surf, rim if fill > 0 else (68, 48, 58), center, radius, 1)
        if panic > 0.55 and beat > 0.6 and index in {active - 1, active}:
            palette.glow(surf, center, radius * 2, color, 0.18 + beat * 0.12)


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
