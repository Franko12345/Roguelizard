"""Optional PNG art (Fase 7). Loads lazily from ``assets/``, scaled + cached per
(key, diameter). Never raises: a missing file, a stripped build without
``assets/``, or a bad PNG all fall back to ``None`` silently -- callers keep the
procedural drawer as the real fallback, so the "no asset files" invariant still
holds for anyone without the directory (a stripped build, or a headless CI box).
"""

import os
import sys
import pygame

# ``_ROOT`` is the repo root (one level above the ``lagarto/`` package),
# so ``assets/`` resolves to ``<repo>/assets/`` -- where the PNGs actually
# live. The old calculation (dirname twice) pointed at ``lagarto/`` and
# silently never loaded any PNG; every caller fell back to the procedural
# drawer and the bug was invisible because the procedural art is the
# canonical source. Issue #25 fixed this so the PNGs (which exist for
# the boss bar emblems and the camp tent) actually load.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CACHE = {}          # key -> raw Surface (convert_alpha'd), or False if missing
_SCALED = {}         # (key, diameter) -> scaled Surface
_SCALED_MAX = 300    # bounded, same pattern as palette._GLOW_CACHE / ui._TEXT_MAX


def resource_path(*parts):
    """PyInstaller bundles data under ``sys._MEIPASS``; dev runs use the repo root."""
    base = getattr(sys, '_MEIPASS', _ROOT)
    return os.path.join(base, *parts)


def _load(key):
    if key in _CACHE:
        return _CACHE[key]
    surf = False
    for sub in ('icons', 'props'):
        p = resource_path('assets', sub, key + '.png')
        if os.path.exists(p):
            try:
                # convert_alpha() needs a display Surface -- only reached once an
                # icon is actually drawn, i.e. well after display.init() in the
                # game loop, so no explicit deferral is needed.
                surf = pygame.image.load(p).convert_alpha()
            except Exception:
                surf = False
            break
    _CACHE[key] = surf
    return surf


def icon(key, diameter):
    """Scaled PNG for ``key`` at ``diameter`` px, or ``None`` if unavailable --
    callers fall back to their procedural drawer in that case."""
    if not key:
        return None
    surf = _load(key)
    if not surf:
        return None
    diameter = max(1, int(diameter))
    ck = (key, diameter)
    cached = _SCALED.get(ck)
    if cached is not None:
        return cached
    if len(_SCALED) >= _SCALED_MAX:
        _SCALED.clear()
    scaled = pygame.transform.smoothscale(surf, (diameter, diameter))
    _SCALED[ck] = scaled
    return scaled
