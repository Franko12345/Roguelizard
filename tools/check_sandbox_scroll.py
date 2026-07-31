"""Issue #175: long lists in the sandbox panel overflowed the bottom
edge, hiding the bottom half of species/items/charms/mutations. The
fix adds ``scroll`` (rows offset) to ``Sandbox`` and clamps it in
``_layout`` against the visible row count; the wheel over the panel
adjusts it.

Two headless scenarios prove the fix:

1. The species list is larger than the visible area: the bottom
   entries are produced by rects only when ``scroll > 0``. Without
   the fix every entry has a non-negative y -- with the fix only
   the entries from row ``scroll`` onwards do.
2. Wheel-up over the panel decreases ``scroll`` (clamped to 0);
   wheel-down increases it; wheel outside the panel is ignored.

Run:  python tools/check_sandbox_scroll.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.core import config as C, fonts
from lagarto.render import display
from lagarto.creatures import species as species_mod
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers

display.init()


def fresh_sb():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='sandbox')
    from lagarto.sandbox import Sandbox
    sb = Sandbox(g, fonts.get(16), fonts.get(26))
    sb.open = True
    sb.cat = 'species'
    return g, sb


# 1. species list overflows the panel: with scroll=0 only the first
# ``visible_rows`` rows appear; with scroll > 0 the bottom entries
# appear and the top entries vanish.
g, sb = fresh_sb()
rows_total = len(species_mod.SPECIES)
cat_rects, pool_rects, item_rects = sb._layout()
panel_top = item_rects[0][0].y if item_rects else 0
panel_bottom = sb.rect.bottom
visible_rows = sum(1 for r, _, _ in item_rects if r.y < panel_bottom - 16)
assert visible_rows < rows_total, (
    f"setup: panel fits all {rows_total} species -- the bug is not "
    f"reproducible in this run")
# scroll all the way down and re-layout: the bottom species should
# now be the last row in item_rects.
sb.scroll = 10**6
cat_rects, pool_rects, item_rects = sb._layout()
# the bottom-most rect must have y < panel_bottom - 16 (visible)
bottom_ys = [r.y for r, _, _ in item_rects]
assert bottom_ys and max(bottom_ys) < panel_bottom - 16, (
    f"scrolled-down list still overflows the panel: "
    f"max(bottom_ys)={max(bottom_ys) if bottom_ys else None}, "
    f"panel_bottom={panel_bottom}")
# and the scroll value was clamped to a finite number
assert 0 <= sb.scroll < rows_total, (
    f"scroll not clamped ({sb.scroll}); rows={rows_total}")
# scroll back to 0 and the first row returns
sb.scroll = 0
cat_rects, pool_rects, item_rects = sb._layout()
first_value_at_zero = item_rects[0][1] if item_rects else None
expected_first = next(iter(species_mod.SPECIES))
assert first_value_at_zero == expected_first, (
    f"scroll=0 should show first species '{expected_first}', "
    f"got '{first_value_at_zero}'")
print(f"  1) species overflow: {rows_total} rows -> scroll reveals bottom; "
      f"top returns at scroll=0")


# 2. wheel over the panel adjusts scroll; wheel outside does not.
g, sb = fresh_sb()
inside = (sb.rect.centerx, sb.rect.centery)
outside = (sb.rect.right + 50, sb.rect.bottom + 50)
# start with a known scroll
sb.scroll = 2

# wheel-up over panel -> scroll decreases (by 1; pygame MOUSEWHEEL y=+1)
# Note: MOUSEWHEEL events do not carry pos; the handler reads
# pygame.mouse.get_pos() at the moment of the event. We move the
# mouse to the panel's centre first.
pygame.mouse.set_pos(inside)
ev_up_in = pygame.event.Event(pygame.MOUSEWHEEL, y=1)
assert sb.handle_event(ev_up_in), "panel did not consume its wheel-up"
assert sb.scroll == 1, f"scroll={sb.scroll}, expected 1 after wheel-up"

# wheel-down over panel -> scroll increases (ev.y=-1 means wheel-down)
pygame.mouse.set_pos(inside)
ev_down_in = pygame.event.Event(pygame.MOUSEWHEEL, y=-1)
assert sb.handle_event(ev_down_in), "panel did not consume its wheel-down"
assert sb.scroll == 2, f"scroll={sb.scroll}, expected 2 after wheel-down"

# wheel-up outside panel -> ignored, scroll unchanged
# (the dummy driver reports a 2240x1440 surface and to_logical divides
# by scale, so raw coordinates far outside the panel work as a true
# "outside" hit-test)
pygame.mouse.set_pos((3000, 3000))
before = sb.scroll
ev_up_out = pygame.event.Event(pygame.MOUSEWHEEL, y=1)
assert not sb.handle_event(ev_up_out), "panel wrongly consumed outside wheel"
assert sb.scroll == before, f"scroll changed from outside wheel ({sb.scroll})"

# wheel-down at scroll=0 -> still 0 (clamped, not negative)
sb.scroll = 0
pygame.mouse.set_pos(inside)
ev_up_in2 = pygame.event.Event(pygame.MOUSEWHEEL, y=1)
sb.handle_event(ev_up_in2)
assert sb.scroll == 0, f"scroll went negative ({sb.scroll})"
print(f"  2) wheel over panel: scroll adjusts; outside/over-top clamped")


# 3. category switch resets scroll to 0 (no carry-over between lists).
g, sb = fresh_sb()
sb.scroll = 7
sb._select_cat('pickup')
assert sb.scroll == 0, (
    f"category switch did not reset scroll (still {sb.scroll})")
print(f"  3) category switch resets scroll=0")

print("ALL OK")