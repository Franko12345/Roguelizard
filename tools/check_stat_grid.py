"""Assert the HUD's stat grid renders in 1P and 2P and that TAB's toggle persists.

Three things could silently break and none of them raises: the grid could stop
being drawn (nothing crashes when a block is missing), the block could be rebuilt
every frame (nothing crashes when a cache never hits), and the TAB preference
could be written and then clobbered by the next settings write (nothing crashes
when a toggle forgets). So each one is measured: pixels inside the expected rect,
the size of ``Game._panels`` across frames, and a reload of ``settings``.

HOME is redirected to a temp dir before anything imports ``settings``, because
this writes the preference file and must not touch the real ``~/.lagarto``.

Left for the tickets that own them: the dwell tooltip (#141) and the predicted
delta of the focused shop card (#140). Both need behaviour that does not exist
yet -- do not assert them here, extend this file when they land.

Run from the repo root:  python tools/check_stat_grid.py
"""
import os, shutil, sys, tempfile
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
_HOME = tempfile.mkdtemp(prefix='lagarto-check-stat-grid-')
os.environ['HOME'] = _HOME                 # settings.path() resolves '~' per call
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.render import display
from lagarto.core import fonts, settings, config as C
from lagarto.game import hud, state_play
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers

assert settings.path().startswith(_HOME), \
    f"settings would be written outside the temp HOME: {settings.path()}"
display.init()

ITEMS = ['casulo', 'iman', 'farpas']
CHARMS = ['carapaca', 'antenas', 'asas']


def new_game(num):
    g = Game(num, make_controllers(num, []), fonts.get(18), fonts.get(32, bold=True),
             mode='normal')
    for p in g.players:
        p.might, p.cooldown_mult, p.speed_mult, p.area_mult = 1.72, 0.86, 1.15, 1.30
        p.health = p.max_health * 0.62
        p.items = list(ITEMS)
        for cid in CHARMS:
            p.gain_charm(cid)
    return g


def ink(surf, rect):
    """How many pixels inside ``rect`` are not the background -- the block is
    drawn straight over the world, so 'something is there' is the only honest
    measure of 'it rendered'."""
    sub = surf.subsurface(rect)
    n = 0
    for y in range(0, rect.height, 3):
        for x in range(0, rect.width, 3):
            if sub.get_at((x, y))[:3] != (0, 0, 0):
                n += 1
    return n


# ---- 1. the grid renders, in 1P and in 2P --------------------------------- #
for num in (1, 2):
    g = new_game(num)
    surf = pygame.Surface((C.WIDTH, C.HEIGHT))
    rects = []
    for i, p in enumerate(g.players):
        rows, badges = state_play._stat_rows(p), state_play._stat_badges(p)
        assert len(rows) == 5, f"expected 5 stat rows, got {len(rows)}"
        labels = [r[0] for r in rows]
        assert labels == ['DANO', 'VIDA', 'RECAR', 'VELOC', 'AREA'], labels
        assert rows[0][1] == '1.72x' and rows[1][1].endswith(f"/{int(p.max_health)}")
        assert len(badges) == len(ITEMS) + len(CHARMS), \
            f"{num}P: {len(badges)} badges for {len(ITEMS)} items + {len(CHARMS)} charms"
        x = 16 if i == 0 else C.WIDTH - 216 - 16
        r = hud.stat_grid(surf, g.smallfont, (x if i == 0 else x + 216, 176),
                          rows, badges, g._panel, right=(i == 1))
        assert r.width == hud.GRID_W, f"block is {r.width}px wide, expected {hud.GRID_W}"
        assert 0 <= r.left and r.right <= C.WIDTH, f"{num}P block off-screen: {r}"
        assert ink(surf, r) > 200, f"{num}P block drew almost nothing ({ink(surf, r)} px)"
        rects.append(r)
    if num == 2:
        assert not rects[0].colliderect(rects[1]), "the two columns overlap"
        assert rects[0].left < C.WIDTH // 2 < rects[1].left, \
            "each column must sit on its own player's side"
    print(f"{num}P: {len(rects)} block(s) rendered, "
          f"{[tuple(r) for r in rects]}, {ink(surf, rects[0])} ink px in P1's")

# ---- 2. it is cached by value, not redrawn from scratch every frame ------- #
g = new_game(1)
p = g.players[0]
surf = pygame.Surface((C.WIDTH, C.HEIGHT))


def draw_once():
    hud.stat_grid(surf, g.smallfont, (16, 176), state_play._stat_rows(p),
                  state_play._stat_badges(p), g._panel)


g._panels.clear()
draw_once()
after_first = len(g._panels)
assert after_first == 1, f"first draw cached {after_first} panels, expected 1"
for _ in range(60):
    draw_once()
assert len(g._panels) == 1, \
    f"60 identical frames cached {len(g._panels)} panels -- the key is not quantised"
p.might += 0.25
draw_once()
assert len(g._panels) == 2, "a changed stat did not produce a new block"
p.health = int(p.health) + 0.5      # park it mid-integer first
draw_once()
n = len(g._panels)
p.health -= 0.01            # sub-integer drift must NOT reach the key
draw_once()
assert len(g._panels) == n, \
    f"a 0.01 HP change rebuilt the block ({len(g._panels)} panels) -- health is not rounded"
p.health = int(p.health) - 0.5      # crossing an integer SHOULD rebuild it
draw_once()
assert len(g._panels) == n + 1, "losing a whole HP did not rebuild the block"
print(f"cache: 60 identical frames -> 1 surface; a changed stat -> 2; "
      f"0.01 HP of drift -> still {n}; a whole HP -> {n + 1}")

# ---- 3. TAB toggles, and the state survives a restart -------------------- #
assert settings.DEFAULTS['stat_grid'] == 1, "the grid must be visible by default"
if os.path.exists(settings.path()):
    os.remove(settings.path())
g = new_game(1)
assert g.show_stat_grid is True, "a fresh run must open with the grid visible"
assert g.toggle_stat_grid() is False, "TAB did not turn the grid off"
assert settings.load()['stat_grid'] == 0, "the toggle was not persisted"

# a brand new Game is what a restart looks like from here
g2 = new_game(1)
assert g2.show_stat_grid is False, "the preference did not survive the restart"

# and the display/audio writer must not clobber it (F11 goes through save_display)
settings.save_display(display)
assert settings.load()['stat_grid'] == 0, "save_display clobbered the grid toggle"

assert g2.toggle_stat_grid() is True and settings.load()['stat_grid'] == 1
assert new_game(1).show_stat_grid is True, "turning it back on did not persist"
print("toggle: default on -> TAB off -> persisted across a new Game -> "
      "survives save_display -> TAB on again")

# ---- 4. hidden means hidden ---------------------------------------------- #
g = new_game(1)
g.show_stat_grid = False
g._panels.clear()
blank = pygame.Surface((C.WIDTH, C.HEIGHT))
state_play._draw_hud(g, blank)
assert not [k for k in g._panels if k[0] == 'statgrid'], \
    "the grid was built even with show_stat_grid off"
g.show_stat_grid = True
state_play._draw_hud(g, blank)
built = [k for k in g._panels if k[0] == 'statgrid']
assert len(built) == 1, f"_draw_hud built {len(built)} grid blocks for 1 player"
print("_draw_hud: skips the block when off, builds exactly one per player when on")
shutil.rmtree(_HOME, ignore_errors=True)
print("ALL OK")
