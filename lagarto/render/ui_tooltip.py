"""Reusable tooltip component with dwell-based activation.

First tooltip system in the game. Activated by the cursor dwelling on a
target rect for ``dwell_seconds`` (default 0.25s). Clamps to screen so it
never opens off the visible area. Used by the camp and play stat grids to
explain what each number means and where it came from.

Why dwell and not instant hover: during play the cursor IS the aim (dash
on left, tongue on right), so it crosses the stat column dozens of times
per second. Instant open would flicker the tooltip on every cross.

Usage:

    from . import tooltip as tt
    tt.manager.hover(rect)             # call every frame with the rects
    tt.manager.draw(surf)              # draw the active tooltip on top

Or, if you only need a one-shot tooltip:

    t = tt.Tooltip(rect, "Dano 1.72x -- Vigor x3", dwell_seconds=0.25)
    t.update(mouse_pos, dt)            # each frame
    if t.active: t.draw(surf)
"""

from __future__ import annotations

import pygame
from ..core import config as C


class Tooltip:
    """One tooltip bound to one target rect. State lives across frames.

    ``rect`` is the world/screen rect the cursor must rest inside.
    ``text`` is what gets drawn (single string, multi-line allowed).
    Dwell time defaults to 0.25s -- the value calibrated for play.
    """

    DWELL_DEFAULT = 0.25  # s

    def __init__(self, rect, text, dwell_seconds=None):
        self.rect = pygame.Rect(rect) if not isinstance(rect, pygame.Rect) else rect
        self.text = text
        self.dwell = dwell_seconds if dwell_seconds is not None else self.DWELL_DEFAULT
        self._hover_t = 0.0    # seconds the cursor has been over the rect
        self._was_inside = False
        self.active = False
        self._last_pos = None

    def update(self, mouse_pos, dt):
        """Advance dwell timer; activate when threshold passed; deactivate on exit.

        A "skim" (cursor enters then exits before ``dwell``) does NOT activate
        the tooltip -- the timer resets on exit, which is the whole point of
        the dwell.
        """
        inside = self.rect.collidepoint(mouse_pos)
        if inside:
            if self._was_inside:
                self._hover_t += dt
            else:
                self._hover_t = 0.0  # fresh entry, no credit yet
            self._was_inside = True
            if self._hover_t >= self.dwell:
                self.active = True
                self._last_pos = mouse_pos
        else:
            self._hover_t = 0.0
            self._was_inside = False
            self.active = False

    def force_close(self):
        """Used when the underlying state changes (e.g. charm equipped)."""
        self._hover_t = 0.0
        self._was_inside = False
        self.active = False

    def draw(self, surf, font=None):
        """Render the tooltip near the cursor, clamped to the screen.

        The tooltip is a small dark box with a thin border, white text,
        1-px padding. The box is placed to the right of the cursor by
        default, and flipped if that would clip the right edge.
        """
        if not self.active or not self.text:
            return
        if font is None:
            font = pygame.font.SysFont("monospace", 13)
        assert font is not None

        # Multi-line split
        lines = self.text.split("\n")
        # Wrap very long lines
        max_w_px = int(C.WIDTH * 0.45)
        wrapped = []
        for ln in lines:
            if font.size(ln)[0] <= max_w_px:
                wrapped.append(ln)
            else:
                # crude word-wrap
                words = ln.split(" ")
                cur = ""
                for w in words:
                    test = (cur + " " + w).strip()
                    if font.size(test)[0] <= max_w_px:
                        cur = test
                    else:
                        if cur: wrapped.append(cur)
                        cur = w
                if cur: wrapped.append(cur)

        line_h = font.get_linesize()
        pad = 5
        w = max(font.size(l)[0] for l in wrapped) + pad * 2
        h = line_h * len(wrapped) + pad * 2

        # Position: right of cursor by default
        cx, cy = self._last_pos
        x = cx + 14
        y = cy + 14
        if x + w > C.WIDTH - 4:
            x = cx - 14 - w  # flip to left
            if x < 4:        # still off, clamp
                x = max(4, C.WIDTH - w - 4)
        if y + h > C.HEIGHT - 4:
            y = max(4, C.HEIGHT - h - 4)

        # Box + text
        box = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(box, (18, 21, 32, 232), (0, 0, w, h), border_radius=4)
        pygame.draw.rect(box, (180, 188, 220), (0, 0, w, h), 1, border_radius=4)
        for i, ln in enumerate(wrapped):
            ts = font.render(ln, True, (232, 232, 240))
            box.blit(ts, (pad, pad + i * line_h))
        surf.blit(box, (x, y))


def source_text(stat_label, player, game=None):
    """Build the 'where did this number come from' line for a stat.

    Walks the player's items, charms, and the run's shop_buys counter to
    give a one-line attribution. Multi-line only if there are several
    sources. Returns 'No source' when nothing relevant is found so the
    caller can still display SOMETHING (the line never looks empty).

    The mapping is hard-coded on purpose: the five HUD rows are a fixed
    set, and the shop is small. A general 'which effect changed which
    stat' introspection would need an effect system (#140's declarative
    schema is the first step) -- until then, this list is canonical.
    """
    from ..combat import charms as charmlib
    from ..combat import items as itemlib

    lines = []

    # Shop purchases
    if game is not None and getattr(game, 'shop_buys', None):
        label_to_offer = {
            "DANO":   "Vigor",
            "VIDA":   "Vitalidade",
            "RECAR":  "Cadencia",
            "VELOC":  "Agilidade",
            "AREA":   "Amplitude",
        }
        offer_name = label_to_offer.get(stat_label)
        if offer_name and offer_name in game.shop_buys:
            n = game.shop_buys[offer_name]
            if n > 0:
                lines.append(f"{offer_name} x{n}")

    # Charms (only when the charm description mentions the stat name)
    for cid in getattr(player, 'charms_owned', []):
        ch = charmlib.CHARMS.get(cid)
        if ch is None: continue
        if stat_label in (ch.desc or "") or stat_label in (ch.name or ""):
            lines.append(f"charm {ch.name}")

    # Items (same fallback)
    for iid in getattr(player, 'items', []):
        it = itemlib.ITEMS.get(iid)
        if it is None: continue
        if stat_label in (it.desc or "") or stat_label in (it.name or ""):
            lines.append(f"item {it.name}")

    if not lines:
        return f"{stat_label}: sem origem rastreada"
    return "  ·  ".join(lines)


class TooltipManager:
    """Owns the active tooltip and tracks cursor position over a frame.

    Drop-in for places with a single tooltip on screen at a time (most of
    the game). The manager handles only one active tooltip -- the newest
    one that called ``hover()`` this frame wins, so tooltips don't pile
    up when the cursor crosses from one row to another.
    """

    def __init__(self):
        self._tooltips = []    # all tooltips ever registered
        self._active = None    # currently shown
        self._mouse_pos = (0, 0)
        self._dt = 0.0
        self._font = None

    def register(self, rect, text, dwell_seconds=None):
        """Create (or reuse) a Tooltip for this rect+text, return it."""
        for t in self._tooltips:
            if t.rect == pygame.Rect(rect) and t.text == text and t.dwell == (dwell_seconds or t.DWELL_DEFAULT):
                return t
        t = Tooltip(rect, text, dwell_seconds)
        self._tooltips.append(t)
        return t

    def hover(self, rect, text, dwell_seconds=None):
        """One-call helper: register the tooltip and update it with the
        current mouse state. Returns the Tooltip so callers can read
        ``.active`` if they want."""
        t = self.register(rect, text, dwell_seconds)
        t.update(self._mouse_pos, self._dt)
        if t.active:
            self._active = t
        return t

    def begin_frame(self, mouse_pos, dt=None):
        """Call once per frame BEFORE the ``hover()`` calls. Resets the
        active tooltip so stale activations from the last frame don't
        linger. ``dt`` is the frame delta in seconds; if omitted, the
        manager derives it from ``pygame.time.get_ticks()`` (good enough
        for camp/grid where the frame rate is stable)."""
        if dt is None:
            now = pygame.time.get_ticks() / 1000.0
            if not hasattr(self, "_last_tick"):
                self._last_tick = now
            dt = max(0.0, min(0.1, now - self._last_tick))
            self._last_tick = now
        self._mouse_pos = mouse_pos
        self._dt = dt
        self._active = None

    def draw(self, surf, font=None):
        if self._active is not None:
            self._active.draw(surf, font)

    def reset(self):
        """Force-close every tooltip. Use on state transitions (e.g.
        leaving camp, opening menu)."""
        for t in self._tooltips:
            t.force_close()
        self._active = None


# Module-level singleton. HUD/state code uses this directly so we don't
# have to thread a manager through every callsite.
manager = TooltipManager()
