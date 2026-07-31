"""Assert boss-death flash ends with combat, before camp starts (#172).

The real boss death path calls ``game.punch(..., flash=0.9)``.  Combat owns the
flash decay; camp does not, so carrying a non-zero value across ``cleared``
would veil every later camp frame.  This check kills a real wave-5 boss, drives
the round machine through ``cleared`` and into camp, then checks both state and
rendered pixels.

Run:  python tools/check_camp_flash.py
"""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

pygame.init()

from lagarto.core import config as C, fonts
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.render import display


display.init()
game = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='normal')

# Enter wave 5 through the real round lifecycle, so _spawn_boss and its mirror run.
game.rounds.wave = 4
game.rounds.start_round()
boss = game.rounds.boss
assert boss is not None, "wave 5 did not spawn a boss"
assert boss in game.enemies, "spawned boss never reached game.enemies"

# Real death feedback: this is the write that used to leak into camp.
boss.die(game)
assert game.flash > 0, "boss death stopped producing its intended combat flash"
death_flash = game.flash

# Make the dead boss the last threat and let RoundManager detect the clear.
game.rounds.budget = 0
game.rounds.marks = []
for nest in game.rounds.nests:
    nest.dead = True
game.rounds.update(C.DT)
assert game.rounds.state == 'cleared', "last boss death did not clear the round"
assert game.flash == 0.0, \
    f"cleared retained boss flash {game.flash:.3f} (death wrote {death_flash:.3f})"
print(f"cleared: boss flash {death_flash:.3f} -> {game.flash:.3f}")

# Enter the real camp and render one immediate frame.  A stale full-screen flash
# changes even a control pixel outside the camp furniture/UI.
game._enter_camp()
assert game.state == 'camp'
assert game.flash == 0.0, f"camp opened with flash {game.flash:.3f}"
surf = pygame.Surface((C.WIDTH, C.HEIGHT), 0, 24)
game.draw(surf)
clean_pixel = surf.get_at((2, 2))[:3]

game.flash = death_flash
game.draw(surf)
flashed_pixel = surf.get_at((2, 2))[:3]
assert flashed_pixel != clean_pixel, \
    "render control has no teeth: restoring the stale flash changed no pixel"
game.flash = 0.0
print(f"camp frame: control pixel clean={clean_pixel}, stale={flashed_pixel}")
print("ALL OK")
