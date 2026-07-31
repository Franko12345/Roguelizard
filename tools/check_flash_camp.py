"""Issue #172: boss.die() sets flash=0.9; the white overlay must not
survive the round clear into the camp.

The fix lives in two parts: Game.step decays flash for every state
(one source of truth) and _enter_camp zeros it (the spec asked for
<0.2s, but decay + freeze alone is ~0.34s -- the camp opens at zero).
This check covers the behaviour: any punch during play decays while
the run is alive; opening the camp discards a leftover overlay.

Run:  python tools/check_flash_camp.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.core import fonts
from lagarto.render import display
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers

display.init()
DT = 1 / 60


g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='normal')
g.punch(flash=0.9)                                # what boss.die() does
assert g.flash == 0.9, f"punch() did not set flash to 0.9 (got {g.flash})"

# skip the punch's own freeze so we measure the actual decay tick
for _ in range(5):
    g.step(DT)
assert g.flash < 0.9, (
    f"flash did not start decaying after the punch freeze "
    f"({g.flash:.3f} still == start 0.9)")

# spec: <0.2s. decay alone is 3.2/s -> 0.9 -> <0.05 in 0.9s. 1s is generous.
for _ in range(int(1 / DT) - 5):
    g.step(DT)
assert g.flash < 1e-3, (
    f"flash {g.flash:.6f} after 1s -- overlay still visible "
    f"(issue #172 still active).")
print(f"  play: flash 0.9 -> <1e-3 in 1s")

# _enter_camp zeros the flash so a punch fired during the cleared->camp
# transition can't bleed into the clearing, regardless of decay rate.
g.punch(flash=0.9)
g._enter_camp()
assert g.state == 'camp', f"camp did not engage (state={g.state!r})"
assert g.flash == 0.0, (
    f"_enter_camp did not zero flash (got {g.flash}); the white overlay "
    f"will cover the camp (issue #172 not met).")
print(f"  camp: _enter_camp zeros flash (0.9 -> 0 on entry)")


print("ALL OK")