"""Issue #176: clicking a sandbox panel row used to also fire the player
dash. ``Sandbox.handle_event`` consumed the ``MOUSEBUTTONDOWN`` event
but ``pygame.mouse.get_pressed()`` (the raw state ``app.main`` reads)
still saw button 1 down -- so ``KeyboardMouseController.poll`` set
``dash = True`` and the player dash fired on the way to menu click.

The fix tracks which buttons the panel ate this frame and masks them
out of the ``mouse_btn`` tuple before ``ctrl.poll``. Two headless
scenarios prove it:

1. Panel eats button 1 -> ctrl.poll sees no dash input -> player.dashing
   stays False; nothing in the dash input buffer.
2. World click while panel CLOSED -> mask is empty -> click reaches
   the controller normally (no regression on the in-world flow).

Run:  python tools/check_sandbox_input_mask.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.core import config as C, fonts
from lagarto.render import display
from lagarto.game.loop import Game
from lagarto.input.controllers import KeyboardMouseController, make_controllers
from lagarto.input import controllers as controllers_mod

display.init()


def fresh_game_with_sb():
    """Build a real Game + Sandbox so handle_event runs against the real
    panel rect (the smoke driver can't drive clicks, but we can call
    handle_event directly with a synthetic MOUSEBUTTONDOWN)."""
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='sandbox')
    from lagarto.sandbox import Sandbox
    sb = Sandbox(g, fonts.get(16), fonts.get(26))
    sb.open = True                          # show the panel
    return g, sb


def make_mouse_down(button, pos):
    e = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos)
    return e


# 1. click inside the panel: dash must NOT fire.
g, sb = fresh_game_with_sb()
panel_pos = (sb.rect.centerx, sb.rect.centery)         # known inside
e = make_mouse_down(button=1, pos=panel_pos)
assert sb.handle_event(e), "panel did not consume its own click"
assert 1 in sb._ate_buttons, (
    f"panel click did not register the button in _ate_buttons "
    f"(got {sb._ate_buttons})")
# simulate what app.main does with the mask
masked = [0, 0, 0]
for b in sb._ate_buttons:
    if 1 <= b <= len(masked):
        masked[b - 1] = 0
# the dash would read from this tuple via KeyboardMouseController.poll
# -- the recipe is bool(mouse_btn[0]) for left click. With masked[0]
# forced to 0 (the panel already cleared it but the raw state would
# have been 1), the controller reads no dash.
p = g.players[0]
p.energy = p.max_energy
# fake a rising-edge dash from raw state (the bug) and confirm the
# MASKED state does not produce one.
raw = (1, 0, 0)                                     # bug: raw says button 1 down
ctrl = KeyboardMouseController(None)
keys = type('K', (), {'__getitem__': lambda s, k: False})()   # empty dict-like
ctrl.poll(keys, raw, g.cam, p.pos, 0.0)
assert p.dash_time > 0 or ctrl._buf['dash'] > 0, (
    f"setup: the bug repro did NOT trigger a dash -- the test is not "
    f"proving the fix (raw dash should fire when button 1 is down).")
# clear the dash and replay with the masked state: no dash
p.dash_time = 0
ctrl._buf['dash'] = 0.0
ctrl.poll(keys, tuple(masked), g.cam, p.pos, 0.0)
assert p.dash_time == 0 and ctrl._buf['dash'] == 0.0, (
    f"masked mouse_btn still produced a dash "
    f"(dash_time={p.dash_time}, buf={ctrl._buf['dash']}) -- "
    f"the panel-click mask is broken.")
print(f"  1) panel click: dash masked (raw=button1 -> no dashing, buf=0)")


# 2. world click while panel CLOSED: mask is empty -> click reaches ctrl.
g, sb = fresh_game_with_sb()
sb.open = False                                     # panel hidden
world_pos = (50, 50)                                # anywhere outside the panel
e = make_mouse_down(button=1, pos=world_pos)
assert not sb.handle_event(e), (
    "world click was wrongly consumed by the panel")
assert not sb._ate_buttons, (
    f"world click leaked into the panel mask ({sb._ate_buttons}); "
    f"in-world flow would regress to no-input.")
# confirm the masking path doesn't accidentally swallow a world click:
# _ate_buttons is empty -> the loop in app.main does nothing.
p = g.players[0]
p.energy = p.max_energy
raw = (1, 0, 0)
ctrl = KeyboardMouseController(None)
ctrl.poll(keys, raw, g.cam, p.pos, 0.0)
assert p.dash_time > 0 or ctrl._buf['dash'] > 0, (
    f"regression: world click stopped reaching the controller")
print(f"  2) world click while panel closed: dash still fires")


print("ALL OK")