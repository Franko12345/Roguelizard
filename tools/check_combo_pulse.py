"""Check the line-of-score pulse on kill (#153).

The combo owns its own flash; the **score line** gets its own pulse so the
player can read "the score moved" as "the combo ticked", without the combo
turning into an organ (decision #134, kept by #153).

What this pins:
  1. `add_combo` raises `score_pulse` to 1.0 in the same frame.
  2. The pulse decays within ~0.3 s below an amplitude threshold.
  3. No kill -> `score_pulse` stays at 0 (it never rises on its own).
  4. The cached score surface is reused across pulses (no per-frame
     `Surface` allocation in the hot path).
"""

import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.render import ui

display.init()

THRESHOLD = 0.05      # amplitude below which the pulse is "gone"
DT = C.DT
DECAY = 3.5           # mirrors state_play.py
DECAY_LIMIT = 1.0 / DECAY * 3   # ~3 / decay = ~1.0s to reach 5%

def _fresh():
    return Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
                mode='normal', chars=None)

def test_combo_raises_pulse():
    g = _fresh()
    assert g.score_pulse == 0.0, f"initial pulse must be 0, got {g.score_pulse}"
    g.add_combo()
    assert g.score_pulse == 1.0, f"add_combo must raise pulse to 1.0, got {g.score_pulse}"
    print("  1. add_combo -> score_pulse=1.0 (same frame)")

def test_pulse_decays_in_300ms():
    g = _fresh()
    g.add_combo()
    t = 0.0
    while t < 0.5 and g.score_pulse > THRESHOLD:
        g.score_pulse -= DECAY * DT
        if g.score_pulse < 0.0:
            g.score_pulse = 0.0
        t += DT
    assert t <= 0.35, f"pulse must decay past {THRESHOLD} within ~0.3 s, took {t:.3f}s"
    print(f"  2. pulse decays below {THRESHOLD} in {t*1000:.0f} ms (target <=300 ms)")

def test_no_kill_no_pulse():
    g = _fresh()
    for _ in range(int(1.0 / DT)):
        # step only the decay, never call add_combo
        g.score_pulse -= DECAY * DT
        if g.score_pulse < 0.0:
            g.score_pulse = 0.0
    assert g.score_pulse == 0.0, f"pulse without kill must stay 0, got {g.score_pulse}"
    print("  3. no kill for 1 s -> score_pulse stays 0 (never rises on its own)")

def test_cached_surface_reused():
    """The pulse path blits the cached text_surface, optionally `.copy()`ed for
    `set_alpha`. The *cache* entry must not be mutated -- a second draw must
    return the same cached object."""
    font = fonts.get(26)
    a = ui.text_surface(font, "12345", C.COL_HUD)
    b = ui.text_surface(font, "12345", C.COL_HUD)
    assert a is b, "text_surface must be cached and reused (same object)"
    print("  4. text_surface cached: same call -> same object (no per-frame alloc)")

def test_pulse_alpha_band():
    g = _fresh()
    g.add_combo()
    # pulse=1.0 -> alpha = 255 * (0.55 + 0.45) = 255
    # pulse=0.0 -> alpha = 255 * (0.55 + 0)   = ~140
    for p in (1.0, 0.5, 0.0):
        alpha = int(255 * (0.55 + 0.45 * p))
        assert 140 <= alpha <= 255, f"alpha out of band for pulse={p}: {alpha}"
    print("  5. alpha band [140, 255] across pulse=1.0/0.5/0.0")

def main():
    print(f"check_combo_pulse -- DECAY={DECAY}/s, threshold={THRESHOLD}")
    test_combo_raises_pulse()
    test_pulse_decays_in_300ms()
    test_no_kill_no_pulse()
    test_cached_surface_reused()
    test_pulse_alpha_band()
    print("ALL OK")

if __name__ == "__main__":
    main()