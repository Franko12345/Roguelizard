"""Assert the player wind-up gates behave (issues #5, #9).

An Anticipation is only worth the input latency it costs if it actually gates:
one action per press, no repeat while held, and a visible coil in between.
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
display.init()
DT = 1 / 60


def fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    p = g.players[0]
    p.energy = p.max_energy
    return g, p


class Held:
    """A controller that reports the button held down forever."""
    def __init__(self, real, flag):
        self.__dict__['_r'], self.__dict__['_f'] = real, flag
    def __getattr__(self, k):
        return True if k == self._f else getattr(self._r, k)
    def __setattr__(self, k, v):
        setattr(self._r, k, v)
    def consume(self, *a):
        pass


for verb, flag, dur, fired in (
        ('dash',   'dash_edge',   C.DASH_ANTIC_T,   lambda p: p.dash_time > 0),
        ('tongue', 'tongue_edge', C.TONGUE_ANTIC_T, lambda p: p.tongue_t > 0),
        ('whip',   'whip_edge',   C.WHIP_ANTIC_T,   lambda p: p.whip_t > 0)):
    g, p = fresh()
    antic = getattr(p, f'{verb}_antic')
    p.ctrl = Held(p.ctrl, flag)

    # 1. the press must NOT fire the action on the same frame
    p.update(DT, g)
    assert antic.is_active, f"{verb}: press did not open a wind-up"
    assert not fired(p), f"{verb}: fired instantly, the wind-up gates nothing"

    # 2. the body must coil (or stretch) while the wind-up runs
    bias = p.squat_bias
    assert abs(bias - 1.0) > 0.01, f"{verb}: no visible coil during wind-up ({bias})"

    # 3. it must fire exactly once, at the end of the wind-up. Anticipation
    #    returns the action on the first update AFTER the timer hits zero, so
    #    the real cost is duration + 1 frame -- run until it fires, not until
    #    is_active drops.
    frames = 1
    while not fired(p) and frames < 60:
        p.update(DT, g)
        frames += 1
    assert fired(p), f"{verb}: never fired after {frames} frames"
    want = round(dur / DT) + 1
    assert abs(frames - want) <= 2, f"{verb}: fired at frame {frames}, expected ~{want}"

    # 4. holding the button must not re-trigger while the action is still running
    retrig = 0
    for _ in range(4):
        p.update(DT, g)
        if antic.is_active:
            retrig += 1
    assert retrig == 0, f"{verb}: held button re-triggered the wind-up {retrig}x"
    print(f"  {verb:7s} coil {bias:.2f}  fires at frame {frames} (~{dur * 1000:.0f} ms)  "
          f"no repeat while held")

# 5. a press with no energy must not open a wind-up at all
g, p = fresh()
p.energy = 0.0
p.ctrl = Held(p.ctrl, 'dash_edge')
p.update(DT, g)
assert not p.dash_antic.is_active, "dash wound up with no energy to spend"
print("  broke energy: no wind-up opens")
print("ALL OK")
