"""Assert a hand-spawned boss has a health bar in the sandbox.

Playtest feedback: you could not see the boss's health bar in the sandbox.
`Sandbox.spawn` appended the boss to `g.enemies` and stopped there, missing the
`g.rounds.boss = ent` that `RoundManager._spawn_boss` does on the very next
line. The failure mode is not "the wrong bar" -- it is **no bar at all**, and
that takes two collaborators to produce:

* `RoundManager.draw_boss_bar` reads `rounds.boss` and returns early on `None`;
* `AILizard._draw_health` (the small over-head bar) refuses to draw for
  anything with `is_boss` set, assuming the big one is already up.

Two bars, each deferring to the other. So the check has to pin the *mirror*,
not the drawing: the drawing was never broken.

What this measures:

* the sandbox's single spawn path leaves `rounds.boss` pointing at the boss it
  just made, and the bar then draws real pixels;
* with the mirror missing -- the pre-fix state, reproduced here -- the same
  frame draws NOTHING, in either bar. This is the control, so the check cannot
  pass vacuously;
* the bar tracks HP rather than merely existing (a full bar paints more than a
  quarter-full one);
* the cleanup paths still null the mirror, so a hand-spawned boss cannot leak
  its bar into the next scene;
* the real wave path agrees: a boss round fired through the machine leaves the
  same observable.

Run:  python tools/check_sandbox_boss_bar.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.sandbox import Sandbox
display.init()

BG = (0, 0, 0)
BOSS_ID = 'rei_lagarto'


def fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='sandbox', chars=None)
    g.sandbox = Sandbox(g, fonts.get(15), fonts.get(26))
    return g, g.sandbox


def bar_ink(g, surf):
    """Bright-warm pixels the boss bar paints on an empty surface. 0 = no bar.

    Draws the real `draw_boss_bar` against the real TopStack -- the exact code
    the sandbox frame runs, isolated only so particles and the world pass cannot
    pollute the count.

    Counts the FILL, not every non-background pixel: the bar's dark backing rect
    (40, 20, 26) is painted at full width whatever the HP is, so a plain non-BG
    count is nearly constant and cannot tell a full bar from an empty one. The
    fill and the name are the warm ink (R >= 200); the backing and outline are
    not.
    """
    surf.fill(BG)
    g.top.reset()
    g.rounds.draw_boss_bar(surf, g.font, g.bigfont)
    n = 0
    for y in range(0, 220):
        for x in range(0, C.WIDTH, 2):          # every other column: 2x faster, same signal
            if surf.get_at((x, y))[0] >= 200:
                n += 1
    return n


surf = pygame.Surface((C.WIDTH, C.HEIGHT), 0, 24)

# --------------------------------------------------------------------------- #
# 1. the mirror, and the bar it buys                                          #
# --------------------------------------------------------------------------- #
g, sb = fresh()
player = g.players[0]
boss = sb.spawn('boss', BOSS_ID, player.pos + Vector2(320, 0))
assert boss in g.enemies, "the boss never reached g.enemies"
assert g.rounds.boss is boss, \
    f"Sandbox.spawn did not mirror onto rounds.boss (it is {g.rounds.boss!r})"
assert getattr(boss, 'is_boss', False), "make_boss stopped setting is_boss"

with_mirror = bar_ink(g, surf)
g.rounds.boss = None                            # exactly the pre-fix state
without = bar_ink(g, surf)
g.rounds.boss = boss
assert without == 0, f"the control is not a control: {without} px with no mirror"
assert with_mirror > 2000, f"the bar drew only {with_mirror} px -- that is not a bar"
print(f"  mirror: rounds.boss is the spawned boss; bar paints {with_mirror} px "
      f"(pre-fix: {without})")

# --------------------------------------------------------------------------- #
# 2. the small over-head bar is NOT a fallback -- why the mirror is load-bearing #
# --------------------------------------------------------------------------- #
boss.hp = boss.max_hp // 2                      # hurt, so a normal enemy would show one
surf.fill(BG)
boss._draw_health(surf, g.cam)
head_ink = sum(1 for y in range(C.HEIGHT) for x in range(0, C.WIDTH, 4)
               if surf.get_at((x, y))[:3] != BG)
assert head_ink == 0, \
    f"the over-head bar now draws for a boss ({head_ink} px) -- re-read this check"
from lagarto.creatures import species
mob = species.make('spitter', player.pos + Vector2(-320, 0))
mob.hp = mob.max_hp // 2
surf.fill(BG)
mob._draw_health(surf, g.cam)
mob_ink = sum(1 for y in range(C.HEIGHT) for x in range(0, C.WIDTH, 4)
              if surf.get_at((x, y))[:3] != BG)
assert mob_ink > 0, "the over-head bar stopped drawing for a common enemy too"
print(f"  no fallback: over-head bar draws {head_ink} px for the boss vs "
      f"{mob_ink} px for a mob -- the big bar is the only one it gets")

# --------------------------------------------------------------------------- #
# 3. the bar tracks HP, it does not merely exist                              #
# --------------------------------------------------------------------------- #
boss.hp = boss.max_hp
full = bar_ink(g, surf)
boss.hp = max(1, boss.max_hp // 4)
quarter = bar_ink(g, surf)
assert full > quarter + 300, \
    f"the bar does not track hp: {full} px full vs {quarter} px at a quarter"
print(f"  tracks hp: {full} px at full, {quarter} px at a quarter")

# --------------------------------------------------------------------------- #
# 4. cleanup still nulls the mirror -- no bar leaks into the next scene        #
# --------------------------------------------------------------------------- #
for method in ('_kill_all', '_reset_round'):
    g, sb = fresh()
    b = sb.spawn('boss', BOSS_ID, g.players[0].pos + Vector2(320, 0))
    assert g.rounds.boss is b
    getattr(sb, method)()
    assert g.rounds.boss is None, f"{method} left rounds.boss dangling"
    assert bar_ink(g, surf) == 0, f"{method} left the bar on screen"
print("  cleanup: kill-all and reset-round both clear the mirror and the bar")

# --------------------------------------------------------------------------- #
# 5. the real wave path leaves the same observable                            #
# --------------------------------------------------------------------------- #
g, sb = fresh()
sb.round_wave = 5                               # wave 5 is a boss wave (BOSS_EVERY)
sb._start_round()
assert g.rounds.is_boss_round, "wave 5 stopped being a boss round"
for _ in range(240):                            # let the machine actually spawn it
    g.step(1 / 60)
    if g.rounds.boss is not None:
        break
assert g.rounds.boss is not None, "the real wave path never set rounds.boss"
wave_ink = bar_ink(g, surf)
assert wave_ink > 2000, f"the wave boss's bar drew only {wave_ink} px"
print(f"  wave path: {g.rounds.boss.boss_name} spawned by the machine, "
      f"bar paints {wave_ink} px -- same observable as the hand spawn")

print("ALL OK")
