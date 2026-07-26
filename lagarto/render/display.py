"""Display: a fixed logical surface scaled to the window (window-size presets).

The game always draws to a logical ``C.WIDTH x C.HEIGHT`` surface. Each frame
``present()`` scales that surface onto the real window, letterboxed so the aspect
ratio is preserved in fullscreen. This is what makes 1x/2x/3x window presets
possible -- ``pygame.SCALED`` would pin the logical size to the window size.

Because the window and the logical surface no longer share coordinates, every
mouse position must go through ``to_logical()`` (aim *and* UI clicks).
"""

import pygame

from ..core import config as C

SCALES = (1, 2, 3)

_screen = None          # the real window surface
_logical = None         # fixed-size surface everything draws to
_scaled = None          # cached scale buffer (None when 1:1)
_pixel_small = None     # downsampled buffer (pixelation, None when PIXEL_SCALE<=1)
_pixel_big = None       # nearest-upscaled buffer, window-rect sized
_scale = 2
_fullscreen = False
_vsync = True
_rect = (0, 0, C.WIDTH, C.HEIGHT)     # where the logical surface lands on screen


def init(scale=2, fullscreen=False, vsync=True):
    global _logical
    # the window must exist before .convert() can pick a pixel format
    apply(scale=scale, fullscreen=fullscreen, vsync=vsync)
    _logical = pygame.Surface((C.WIDTH, C.HEIGHT)).convert()
    return _logical


def apply(scale=None, fullscreen=None, vsync=None):
    """(Re)create the window. Returns the logical surface."""
    global _screen, _scale, _fullscreen, _vsync
    if scale is not None:
        _scale = scale if scale in SCALES else 2
    if fullscreen is not None:
        _fullscreen = bool(fullscreen)
    if vsync is not None:
        _vsync = bool(vsync)

    # RESIZABLE (windowed) lets tiling/compositing WMs push external resizes
    # through as VIDEORESIZE events -> handle_resize() -> _recompute() picks up
    # the true size and re-letters. Without it a WM that silently repositions
    # the window leaves _rect stale, so mouse clicks land at an offset.
    flags = pygame.FULLSCREEN if _fullscreen else pygame.RESIZABLE
    size = (0, 0) if _fullscreen else (C.WIDTH * _scale, C.HEIGHT * _scale)
    try:
        _screen = pygame.display.set_mode(size, flags, vsync=1 if _vsync else 0)
    except pygame.error:
        _screen = pygame.display.set_mode(size, flags)
    _recompute()
    return _logical


def _recompute():
    """Letterbox: largest fit that preserves the aspect ratio; cache the scale buffer."""
    global _rect, _scaled, _pixel_small, _pixel_big
    sw, sh = _screen.get_size()
    k = min(sw / C.WIDTH, sh / C.HEIGHT)
    w, h = max(1, int(C.WIDTH * k)), max(1, int(C.HEIGHT * k))
    _rect = ((sw - w) // 2, (sh - h) // 2, w, h)
    _scaled = None if (w, h) == (C.WIDTH, C.HEIGHT) else pygame.Surface((w, h)).convert()
    if C.PIXEL_SCALE > 1:
        pw = max(1, C.WIDTH // C.PIXEL_SCALE)
        ph = max(1, C.HEIGHT // C.PIXEL_SCALE)
        _pixel_small = pygame.Surface((pw, ph)).convert()
        _pixel_big = pygame.Surface((w, h)).convert()
    else:
        _pixel_small = None
        _pixel_big = None


def surface():
    return _logical


def screen():
    return _screen


def get_scale():
    return _scale


def is_fullscreen():
    return _fullscreen


def get_vsync():
    return _vsync


def toggle_fullscreen():
    return apply(fullscreen=not _fullscreen)


def cycle_scale():
    i = SCALES.index(_scale) if _scale in SCALES else 1
    return apply(scale=SCALES[(i + 1) % len(SCALES)], fullscreen=False)


def toggle_vsync():
    return apply(vsync=not _vsync)


def handle_resize():
    _recompute()


def present():
    """Scale the logical surface onto the window and flip.

    Normally ``smoothscale`` -- the art is vector-ish (polygons, circles,
    anti-aliased text), and nearest-neighbour made scaled-up text look jagged.
    With ``C.PIXEL_SCALE`` > 1 that's flipped on purpose, and BOTH steps use
    nearest (``scale``, not ``smoothscale``): the downsample first tried
    smoothscale so it would average detail into each block, but averaging an
    already-anti-aliased scene just blurs it into soft blobs -- the chunky
    upscale after that is then blowing up a blur, not chunking up crisp
    pixels, which read as "blurred" instead of "pixel art" (feedback: not
    sharp, outlines not well-defined). Point-sampling (nearest) on the
    downsample instead picks ONE source pixel per block -- ink outlines and
    flat fills survive as solid blocks; thin diagonal edges alias/step
    instead of blurring, which IS the retro pixel-art look. Pure post-process
    -- world/UI coordinates are untouched.
    """
    x, y, w, h = _rect
    if (x, y) != (0, 0):
        _screen.fill((0, 0, 0))              # letterbox bars
    if _pixel_small is not None:
        pygame.transform.scale(_logical, _pixel_small.get_size(), _pixel_small)
        pygame.transform.scale(_pixel_small, (w, h), _pixel_big)
        _screen.blit(_pixel_big, (x, y))
    elif _scaled is None:
        _screen.blit(_logical, (x, y))
    else:
        pygame.transform.smoothscale(_logical, (w, h), _scaled)
        _screen.blit(_scaled, (x, y))
    pygame.display.flip()


def to_logical(pos):
    """Window pixel -> logical pixel (undo letterbox + scale). Clamped in-bounds.

    Recomputes the letterbox rect from the *live* ``_screen.get_size()`` rather
    than trusting the cached ``_rect``. ``_rect`` is refreshed by ``_recompute()``
    on every ``VIDEORESIZE``, but mouse input is user-driven and can arrive
    before the matching resize event is pumped -- a stale ``_rect`` would then
    map clicks to the wrong logical pixel. ``present()`` is fine using the cache
    because it runs every frame and a resize always refreshes it by the next
    flip; only this user-input path needs the live check.
    """
    sw, sh = _screen.get_size()
    k = min(sw / C.WIDTH, sh / C.HEIGHT)
    w = max(1, int(C.WIDTH * k))
    h = max(1, int(C.HEIGHT * k))
    x = (sw - w) // 2
    y = (sh - h) // 2
    if w <= 0 or h <= 0:
        return (0, 0)
    lx = (pos[0] - x) * C.WIDTH / w
    ly = (pos[1] - y) * C.HEIGHT / h
    return (int(max(0, min(C.WIDTH - 1, lx))), int(max(0, min(C.HEIGHT - 1, ly))))


def mouse_logical():
    return to_logical(pygame.mouse.get_pos())
