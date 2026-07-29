"""Shared UI kit: panels, cards, chips, animated lists and tabs.

One visual language for the menu hub *and* the in-game screens (HUD, level-up
cards, camp), so everything feels like the same game. Drawing helpers return the
rects they used, which the caller stores for mouse hit-testing (positions are in
logical coordinates -- see ``display.to_logical``).
"""

import math
import pygame

from ..core import config as C
from ..core import palette
from ..core.mathutil import decay, pulse

INK = (12, 14, 22)
LINE = (68, 72, 104)
TEXT = (247, 248, 255)
DIM = (186, 190, 214)

# --- text with an outline -------------------------------------------------- #
# Everything is drawn on the fixed logical surface and then smoothscaled onto the
# window by display.present(), so every glyph is rasterised at logical size and
# *stretched bilinearly*. Thin anti-aliased strokes turn to mush that way -- which
# is why the UI read as weak even though anti-aliasing was on everywhere. A dark
# rim is the one thing that survives the filter: it keeps a hard edge at any
# scale, so the text holds its weight at 1x, 2x, 3x and in fullscreen.
_OUTLINE = ((-1, -1), (0, -1), (1, -1), (-1, 0),
            (1, 0), (-1, 1), (0, 1), (1, 1))
# Cached because an outline is 9 renders per string; without a cache the HUD alone
# would pay that every frame. Capped + cleared like palette._GLOW_CACHE: score,
# health numbers and timers are all *continuous* text, so the keyspace is
# unbounded and an uncapped dict is the same leak we already fixed once.
_TEXT_CACHE = {}
_TEXT_MAX = 700


def text_surface(font, s, color, outline=INK, width=2):
    """Text pre-rendered with a dark outline.

    The returned surface is **cached and shared** -- ``.copy()`` it before calling
    ``set_alpha``/``fill`` on it, or every later draw of the same string inherits
    the change (the round banner's fade hit exactly this).
    """
    key = (font, s, color, outline, width)
    im = _TEXT_CACHE.get(key)
    if im is None:
        body = font.render(s, True, color)
        if width <= 0:
            im = body
        else:
            dark = font.render(s, True, outline)
            w, h = body.get_size()
            im = pygame.Surface((w + width * 2, h + width * 2), pygame.SRCALPHA)
            for dx, dy in _OUTLINE:
                im.blit(dark, (width + dx * width, width + dy * width))
            im.blit(body, (width, width))
        if len(_TEXT_CACHE) >= _TEXT_MAX:
            _TEXT_CACHE.clear()
        _TEXT_CACHE[key] = im
    return im


def text(surf, font, s, pos, color, outline=INK, width=2, align='left'):
    """Draw outlined text. ``pos`` is where the *glyphs* land, so this is a drop-in
    replacement for ``surf.blit(font.render(...), pos)``. Returns the text rect,
    which callers use to stack elements without overlapping."""
    im = text_surface(font, s, color, outline, width)
    bw = im.get_width() - 2 * width
    bh = im.get_height() - 2 * width
    x, y = int(pos[0]), int(pos[1])
    if align == 'center':
        x -= bw // 2
    elif align == 'right':
        x -= bw
    surf.blit(im, (x - width, y - width))
    return pygame.Rect(x, y, bw, bh)


def text_size(font, s):
    """Size of the glyphs alone (outline excluded) -- for layout maths."""
    return font.size(s)


def title(surf, font, text, y, color, t=0.0, glow=True):
    cx = C.WIDTH // 2
    im = font.render(text, True, color)
    if glow:
        palette.glow(surf, (cx, y + im.get_height() // 2), im.get_width() * 0.55,
                     color, 0.22 + 0.10 * math.sin(t * 2))
    surf.blit(im, (cx - im.get_width() // 2, y))
    return im.get_height()


def chip(surf, font, text, x, y, color, filled=False):
    im = font.render(text, True, INK if filled else TEXT)
    r = pygame.Rect(x, y, im.get_width() + 26, im.get_height() + 10)
    if filled:
        pygame.draw.rect(surf, color, r, border_radius=999)
    else:
        pygame.draw.rect(surf, (24, 26, 40), r, border_radius=999)
        pygame.draw.rect(surf, color, r, 2, border_radius=999)
    pygame.draw.circle(surf, color if not filled else INK, (x + 13, r.centery), 5)
    surf.blit(im, (x + 22, y + 5))
    return r


def drop_in(t, i=0, stagger=0.07, dur=0.26, rise=30.0):
    """Staggered "drop down + fade in" entry for one item of a screen.

    ``t`` is a clock that starts at 0 when the screen opens; ``i`` is the item's
    index, so entries cascade instead of all landing at once. Returns
    ``(offset_y, alpha)`` -- add the offset to the item's resting y and use the
    alpha (0-1) to fade it in. Every screen shares this so the game has one
    single entry feel.
    """
    lt = (t - i * stagger) / (dur if dur > 1e-4 else 1e-4)
    lt = 0.0 if lt < 0.0 else (1.0 if lt > 1.0 else lt)
    ease = 1 - (1 - lt) ** 3                  # ease-out cubic: fast in, soft landing
    return -(1 - ease) * rise, ease


def list_menu(surf, font, items, sel, top, accent, t=0.0, width=440, gap=56):
    """Vertical list with an animated selection highlight. Returns item rects."""
    cx = C.WIDTH // 2
    rects = []
    for i, label in enumerate(items):
        y = top + i * gap
        rect = pygame.Rect(cx - width // 2, y, width, 46)
        rects.append(rect)
        chosen = (i == sel)
        if chosen:
            palette.glow(surf, rect.center, width * 0.42, accent, 0.20 + 0.14 * pulse(t, 5))
            pygame.draw.rect(surf, (26, 30, 46), rect, border_radius=12)
            pygame.draw.rect(surf, accent, rect, 3, border_radius=12)
            # sliding marker on the left edge
            bar = pygame.Rect(rect.x + 8, rect.y + 10, 5, rect.height - 20)
            pygame.draw.rect(surf, accent, bar, border_radius=3)
        im = font.render(label, True, TEXT if chosen else DIM)
        surf.blit(im, (cx - im.get_width() // 2, y + 8))
    return rects


def tabs(surf, font, labels, sel, y, accent):
    """Horizontal tab strip. Returns tab rects."""
    cx = C.WIDTH // 2
    ims = [font.render(l, True, TEXT if i == sel else DIM) for i, l in enumerate(labels)]
    w = sum(im.get_width() + 40 for im in ims)
    x = cx - w // 2
    rects = []
    for i, im in enumerate(ims):
        r = pygame.Rect(x, y, im.get_width() + 32, 38)
        rects.append(r)
        if i == sel:
            pygame.draw.rect(surf, (28, 32, 50), r, border_radius=10)
            pygame.draw.rect(surf, accent, r, 2, border_radius=10)
            pygame.draw.rect(surf, accent, (r.x + 10, r.bottom - 5, r.width - 20, 3),
                             border_radius=2)
        surf.blit(im, (r.centerx - im.get_width() // 2, y + 8))
        x += im.get_width() + 40
    return rects


def wrap(font, text, width):
    """Split ``text`` into lines that fit ``width`` pixels."""
    out, line = [], ''
    for word in text.split():
        test = (line + ' ' + word).strip()
        if font.size(test)[0] > width and line:
            out.append(line)
            line = word
        else:
            line = test
    if line:
        out.append(line)
    return out


def paragraph(surf, font, text, x, y, width, color=DIM, lh=24):
    for i, line in enumerate(wrap(font, text, width)):
        surf.blit(font.render(line, True, color), (x, y + i * lh))
    return y + len(wrap(font, text, width)) * lh


def fit(font, text, width, ellipsis='...'):
    """Shorten `text` until it fits `width` pixels (keeps UI text inside its box)."""
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + ellipsis)[0] > width:
        text = text[:-1]
    return text.rstrip() + ellipsis


def footer(surf, font, text):
    im = font.render(text, True, (168, 172, 198))
    surf.blit(im, (C.WIDTH // 2 - im.get_width() // 2, C.HEIGHT - 40))


_TINT = {}

# Cached framed-panel FILL surface. ui.panel used to allocate a
# `pygame.Surface(SRCALPHA)` per call per frame -- exactly the "no full-screen
# `Surface` per frame" rule the perf doc warns against. The HUD alone called
# it 2-4 times a frame, and the alpha-blit is the slow part. The rim is drawn
# on the target surface (one draw.rect, fixed colour, always cheap) so the
# panel's outer edge stays pixel-perfect against its neighbour blocks.
_PANEL_CACHE = {}
_PANEL_CACHE_MAX = 24


def panel(surf, rect, alpha=190, accent=None, radius=16):
    """Pre-rendered framed panel: cached dark fill, live rim, one blit.

    The cached surface is **shared** -- do not mutate it. The cap is small
    (24 entries) because panel sizes in this game are a known handful: the
    player HUD capsules plus the menu/level-up cards.
    """
    key = (rect.width, rect.height, alpha, radius)
    s = _PANEL_CACHE.get(key)
    if s is None:
        s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(s, (16, 18, 30, alpha),
                         (0, 0, rect.width, rect.height), border_radius=radius)
        if len(_PANEL_CACHE) >= _PANEL_CACHE_MAX:
            _PANEL_CACHE.clear()
        _PANEL_CACHE[key] = s
    surf.blit(s, (rect.x, rect.y))
    pygame.draw.rect(surf, accent or LINE, rect, 2, border_radius=radius)


def _tint(surf, color, alpha):
    """Full-screen colour wash, reusing one cached surface per colour.

    Allocating a fresh SRCALPHA screen every frame (which fades/veils/flashes all
    used to do) is both slow and allocation churn; a plain surface with
    ``set_alpha`` is also a faster blit path than per-pixel alpha.
    """
    if alpha <= 0:
        return
    s = _TINT.get(color)
    if s is None:
        s = pygame.Surface((C.WIDTH, C.HEIGHT))
        s.fill(color)
        _TINT[color] = s
    s.set_alpha(min(255, int(alpha)))
    surf.blit(s, (0, 0))


class Fade:
    """Short cross-screen fade. `start()` blacks out, then it lifts on its own."""

    def __init__(self, dur=0.28):
        self.dur = dur
        self.t = 0.0

    def start(self, dur=None):
        self.dur = dur or self.dur
        self.t = self.dur

    @property
    def active(self):
        return self.t > 0

    def update(self, dt):
        self.t = decay(self.t, dt)

    def draw(self, surf):
        if self.t <= 0:
            return
        # ease out: fully opaque at the start of the transition, clear at the end
        a = int(235 * min(1.0, (self.t / self.dur) ** 0.8))
        if a <= 0:
            return
        _tint(surf, (8, 8, 16), a)


def veil(surf, alpha=120, color=(12, 10, 24)):
    _tint(surf, color, alpha)
