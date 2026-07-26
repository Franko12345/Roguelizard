"""Assert the player action gates behave (issues #5, #9).

The durations are 0 by default: the player fires on the press frame, and
wind-up belongs to the things you fight, not to the thing you are. The gate is
still there at 0, and the half of issue #5 worth keeping is that it fires
exactly once per press.

This checks whichever regime config is in, so it stays honest if the durations
are raised again:
  duration == 0  -> fires on the press frame, no coil
  duration >  0  -> does NOT fire on the press frame, coils, fires once at the end
Either way: one action per press, never a repeat while the button is held.
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
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
    """A controller reporting one button held down forever, and whose consume()
    does nothing -- the worst case for a gate that must not repeat-fire."""
    def __init__(self, real, flag):
        self.__dict__['_r'], self.__dict__['_f'] = real, flag

    def __getattr__(self, k):
        return True if k == self._f else getattr(self._r, k)

    def __setattr__(self, k, v):
        setattr(self._r, k, v)

    def consume(self, *a):
        pass


VERBS = (
    ('dash',   'dash_edge',   C.DASH_ANTIC_T,   C.DASH_ANTIC_SQUAT,
     lambda p: p.dash_time > 0),
    ('tongue', 'tongue_edge', C.TONGUE_ANTIC_T, C.TONGUE_ANTIC_SQUAT,
     lambda p: p.tongue_t > 0),
    ('whip',   'whip_edge',   C.WHIP_ANTIC_T,   C.WHIP_ANTIC_SQUAT,
     lambda p: p.whip_t > 0),
)

for verb, flag, dur, squat, fired in VERBS:
    g, p = fresh()
    antic = getattr(p, f'{verb}_antic')
    p.ctrl = Held(p.ctrl, flag)

    p.update(DT, g)
    if dur == 0:
        # 1a. instant: the press frame IS the action frame
        assert fired(p), f"{verb}: zero wind-up must fire on the press frame"
        assert not antic.is_active, f"{verb}: zero wind-up must not stall"
        frames = 1
    else:
        # 1b. wind-up: the press opens a window and the body coils in it
        assert antic.is_active, f"{verb}: press did not open a wind-up"
        assert not fired(p), f"{verb}: fired instantly despite a wind-up"
        assert abs(p.squat_bias - squat) < 1e-6, \
            f"{verb}: no coil during wind-up ({p.squat_bias} != {squat})"
        # Anticipation returns its action on the first update AFTER the timer
        # reaches zero, so the real cost is duration + 1 frame.
        frames = 1
        while not fired(p) and frames < 60:
            p.update(DT, g)
            frames += 1
        assert fired(p), f"{verb}: never fired after {frames} frames"
        want = round(dur / DT) + 1
        assert abs(frames - want) <= 2, \
            f"{verb}: fired at frame {frames}, expected ~{want}"

    # 2. holding the button must never queue a second one behind the first
    retrig = 0
    for _ in range(6):
        p.update(DT, g)
        if antic.is_active or antic.action is not None:
            retrig += 1
    assert retrig == 0, f"{verb}: held button re-armed the gate {retrig}x"
    print(f"  {verb:7s} wind-up {dur * 1000:3.0f} ms  fires frame {frames}  "
          f"no repeat while held")

# 3. a press with nothing to spend must not arm the gate at all
g, p = fresh()
p.energy = 0.0
p.ctrl = Held(p.ctrl, 'dash_edge')
p.update(DT, g)
assert not p.dash_antic.is_active and p.dash_antic.action is None, \
    "dash armed with no energy to spend"
assert p.dash_time <= 0, "dash fired with no energy"
print("  broke energy: gate does not arm")

# 4. enemies and bosses keep THEIR wind-ups -- that is the half that stays
from lagarto.flow.boss.patterns import PATTERNS
windups = [p_['windup'] for p_ in PATTERNS.values() if p_.get('windup')]
assert windups and min(windups) > 0, "boss patterns lost their telegraph windows"
print(f"  boss telegraphs intact: {len(windups)} patterns, "
      f"windup {min(windups):.2f}-{max(windups):.2f}s")
print("ALL OK")
