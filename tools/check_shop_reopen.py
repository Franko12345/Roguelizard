"""Prove the tent only opens on the OUT->IN radius transition (#174).

The old code polled `player in radius` every step. Closing the shop set a
0.7 s cooldown, but the moment that elapsed with the player still inside
the radius the shop fired AGAIN -- a reopen loop you could only escape
by walking away.

The fix is an edge detector (`was_outside_tent`): the open trigger only
fires on the falling edge of the outside signal, i.e. the frame the
player crosses into the radius. Standing still inside, or closing and
waiting for the cooldown, cannot reopen it on its own.

This drives the real tent trigger from ``state_camp.update`` across
several scripted sequences and asserts the shop mode flips exactly when
the issue says it should (and never otherwise).
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.core import config as C
from lagarto.render import display
from lagarto.core import fonts
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers

display.init()
g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='normal')
g._enter_camp()

p = g.players[0]
tent = g.camp['tent']
R = C.CAMP_TENT_R
FAR = tent + Vector2(R * 3, 0)        # well outside the radius
IN  = tent + Vector2(2, 0)            # inside the radius


def place(v):
    p.pos = Vector2(v)


def open_count():
    return g.camp.get('shop_open_events', 0)


def reset():
    g.camp['mode'] = 'field'
    g.camp['reopen_cd'] = 0.0
    g.camp['was_outside_tent'] = True
    g.pick = None


def step(n=20):
    """A handful of fixed-dt steps so decay/landing have time to settle."""
    for _ in range(n):
        g.step(C.DT)


# bootstrap: tent must land before any of the scenarios matter
assert not g.camp['tent_landed'], "tent landed instantly? drop-in skipped"
step(80)
assert g.camp['tent_landed'], f"tent never landed after 80 steps (born={g.camp['born']})"


# --- scenario 1: approach from outside -> opens exactly once ----------------
reset()
place(FAR)
step(5)
assert g.camp['mode'] == 'field', "shop opened before player entered radius"

place(IN)
step(5)
assert g.camp['mode'] == 'shop', "edge detector missed the OUT->IN transition"
assert g.camp['was_outside_tent'] is False, \
    "was_outside_tent should be cleared once the shop is open"


# --- scenario 2: close shop, stay inside, wait past reopen_cd -> stays closed
reset()
place(IN)
step(5)
assert g.camp['mode'] == 'shop', "scenario 2 setup failed: shop did not open"

g.camp_close_shop()                   # simulate ESC / B
assert g.camp['mode'] == 'field'
assert g.camp['reopen_cd'] > 0, "closing the shop did not arm the cooldown"

step(120)                             # > CAMP_REOPEN_CD elapsed
assert g.camp['mode'] == 'field', \
    f"REGRESSION: shop reopened while player stood inside after " \
    f"reopen_cd ({C.CAMP_REOPEN_CD}s) elapsed (was_outside_tent=" \
    f"{g.camp['was_outside_tent']})"


# --- scenario 3: leave radius then re-enter -> opens again -----------------
reset()
place(IN)
step(5)
g.camp_close_shop()
step(2)
place(FAR)
step(80)                              # sit outside, well past CAMP_REOPEN_CD
assert g.camp['mode'] == 'field'
assert g.camp['was_outside_tent'] is True, \
    "leaving the radius did not re-arm the edge detector"

place(IN)
step(5)
assert g.camp['mode'] == 'shop', \
    "edge detector failed to re-fire after OUT->IN after closing once"


# --- scenario 4: close -> walk away -> walk back -> opens again ------------
# Mirrors scenario 3 but with a longer cooldown window to prove the
# detector is driven by the position transition, not by the reopen_cd timer.
reset()
place(IN); step(5)
assert g.camp['mode'] == 'shop'
g.camp_close_shop()
place(FAR)
step(200)                             # very long idle: reopen_cd is long gone
assert g.camp['mode'] == 'field'
assert g.camp['was_outside_tent'] is True

place(IN); step(5)
assert g.camp['mode'] == 'shop', "long-idle reopen after close failed"


# --- scenario 5: dead player inside the radius does not open the shop ------
reset()
p.dead = True
place(IN)
step(20)
assert g.camp['mode'] == 'field', \
    "dead player triggered the shop (should be ignored like before)"
p.dead = False                        # restore for any later inspection

print(f"CAMP_TENT_R={R}, CAMP_REOPEN_CD={C.CAMP_REOPEN_CD}")
print("all 5 scenarios pass: shop only opens on OUT->IN, never on a stale poll")
print("ALL OK")
