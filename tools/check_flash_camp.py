"""Issue #172: the punch-driven screen flash must decay in EVERY state.

Before the fix, ``game.flash = decay(...)`` only ran inside
``state_play.update`` (the play state's body of ``Game.step``). ``boss.die()``
sets ``flash=0.9``; the moment the round cleared and ``state='camp'``
took over, no one ticked the timer down, so the white screen overlay
stayed on for the entire camp (clothing the tent, the doors and the
HUD until the next round or a quit).

The fix moves the decay to the top of ``Game.step`` so every state --
camp, levelup, pause, over, victory -- shares one decay source. The
check forces a high flash, switches to camp, steps the game for the
whole clearing, and asserts the flash is gone.

Also asserts the source change: ``state_play.update`` no longer owns
the decay line (the Game.step copy is now the single source of truth),
so nobody can quietly re-add a duplicate that re-introduces the bug.

Run:  python tools/check_flash_camp.py
"""
import os, sys, inspect, math
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.core import config as C
from lagarto.core import fonts
from lagarto.render import display
from lagarto.game import loop as gameloop, state_play, state_camp
from lagarto.input.controllers import make_controllers

display.init()
DT = 1 / 60


def fresh():
    return gameloop.Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
                         mode='normal')


# 1. source-of-truth: the decay moved OUT of state_play.update.
# If somebody quietly puts it back, this fails -- the whole point of the
# fix is that ONE place decays the flash, not two.
sp_src = inspect.getsource(state_play.update)
assert 'game.flash = decay' not in sp_src, (
    "state_play.update still owns a flash decay line; the fix moved it to "
    "Game.step so every state decays it. Restore the single-source rule.")

step_src = inspect.getsource(gameloop.Game.step)
assert 'self.flash = decay(self.flash' in step_src, (
    "Game.step no longer decays game.flash -- the camp/levelup/pause/over "
    "paths will freeze the white overlay again (issue #172 regression).")
print(f"  source: decay moved to Game.step, removed from state_play.update")


# 2. behaviour: a high flash in 'camp' decays within a reasonable window.
# camp lives 4-15s realistically (shop + door walk); the white overlay has
# to be GONE long before that -- the bug report said "persiste durante
# todo o acampamento". Boss flash decays at 3.2/s, so 0.9 -> < 0.05 in
# ~0.9s under the real curve.
g = fresh()
g.punch(flash=0.9)                                # what boss.die() does
assert g.flash == 0.9, f"punch() did not set flash to 0.9 (got {g.flash})"

# open the camp exactly the way state_play does when the round clears
g._enter_camp()
assert g.state == 'camp', f"camp did not engage (state={g.state!r})"

# step one frame so the decay sees a non-zero dt; capture peak AFTER
# the first step (the punch's own freeze frame is part of the punch feel
# and should NOT bleed past it -- the check is "does it EVER clear?").
for _ in range(5):
    g.step(DT)
post_freeze = g.flash
assert post_freeze < 0.9, (
    f"flash did not start decaying after the punch freeze "
    f"({post_freeze:.3f} == start 0.9)")
# by 1 second of camp (60 frames), flash is essentially gone
for _ in range(60 - 5):
    g.step(DT)
assert g.flash < 1e-3, (
    f"flash {g.flash:.6f} after 1s of camp -- overlay still visible "
    f"(issue #172 still active).")
# give it the full real-world camp lifetime to be sure nothing else
# re-fires it (drop-in impacts, shop purchases, door crossings).
for _ in range(int(30 / DT) - 60):
    g.step(DT)
assert g.flash < 1e-6, (
    f"flash did not fully decay (still {g.flash:.6f} after 30s of camp).")
print(f"  camp: flash 0.9 -> {post_freeze:.3f} (post-freeze) "
      f"-> <1e-3 in 1s, fully 0 after 30s of camp")


# 3. every other state also decays (levelup/pause/over/victory). This is
# what the move-to-Game.step buys: a one-line fix instead of a per-state
# copy that could be forgotten next time a state is added.
for name in ('levelup', 'pause', 'over', 'victory'):
    g2 = fresh()
    g2.punch(flash=0.9)
    g2.state = name                             # bypass the legit entry paths
    # skip the punch's own freeze so we measure the actual decay
    for _ in range(int(1 / DT)):
        g2.step(DT)
    assert g2.flash < 1e-3, (
        f"state={name!r}: flash {g2.flash:.6f} after 1s -- overlay still "
        f"visible. Issue #172 fix only covers the states it was moved for.")
print(f"  decay: flash 0.9 -> < 1e-3 in levelup/pause/over/victory (1s)")


# 4. a fresh punch during the camp doesn't combine with stale flash.
# This is the realistic failure mode the bug report named -- the punch
# from the boss kill (flash=0.9) lingers, then a drop-in impact or
# shop purchase triggers another punch on top, and the two never decay.
# After the fix, each punch's max-with-old still works AND the decay
# keeps ticking.
g = fresh()
g.punch(flash=0.9)
g._enter_camp()
for _ in range(int(2 / DT)):
    g.step(DT)
assert g.flash < 1e-3, (
    f"first punch's flash should be gone in 2s, got {g.flash:.6f}")
# now a smaller punch during the camp (drop-in tent impact)
g.punch(flash=0.4)
assert math.isclose(g.flash, 0.4, abs_tol=1e-6), (
    f"second punch should set flash to 0.4, got {g.flash}")
for _ in range(int(2 / DT)):
    g.step(DT)
assert g.flash < 1e-3, (
    f"second punch's flash should be gone in 2s, got {g.flash:.6f}")
print(f"  camp punches: each punch decays independently (0.9 then 0.4)")


print("ALL OK")