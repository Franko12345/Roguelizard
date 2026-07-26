"""Assert the wave difficulty curve does what issue #23 asked.

Two claims worth pinning: the early game is untouched (so a new player is not
punished by a mid-game problem), and the late game actually ramps.
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.core import config as C
from lagarto.flow.rounds import wave_hp_bonus, wave_speed_mul, wave_budget, wave_cap

# the old curves, before #23
old_hp = lambda w: int(w * 0.7)
old_speed = lambda w: 1.0 + min(w * 0.02, 0.4)
old_budget = lambda w, b: int((3 + w * 1.1) * b)
old_cap = lambda w, c: c

print(" wave |    hp    |  speed  |  budget  |  cap")
for w in (1, 3, 5, 7, 10, 12, 15, 20, 30):
    print(f"  {w:3d} | {old_hp(w):3d}->{wave_hp_bonus(w):4d} | "
          f"{old_speed(w):.2f}->{wave_speed_mul(w):.2f} | "
          f"{old_budget(w,1.0):3d}->{wave_budget(w,1.0):4d} | "
          f"{old_cap(w,6)}->{wave_cap(w,6)}")

# 1. early game byte-identical -- the knees are at 8 and 10
for w in range(0, 8):
    assert wave_hp_bonus(w) == old_hp(w), f"hp changed at wave {w}"
    assert wave_budget(w, 1.0) == old_budget(w, 1.0), f"budget changed at wave {w}"
    assert wave_cap(w, 6) == old_cap(w, 6), f"cap changed at wave {w}"
# speed per-wave rate did rise (0.02 -> 0.025); it must still be gentle early
assert wave_speed_mul(5) - old_speed(5) < 0.03, "early speed ramp moved too much"
print("\nearly game (waves 0-7): hp/budget/cap identical to the old curve")

# 2. late game must actually ramp, and monotonically
for f in (wave_hp_bonus, wave_speed_mul):
    vals = [f(w) for w in range(1, 40)]
    assert vals == sorted(vals), f"{f.__name__} is not monotonic"
assert wave_speed_mul(40) > 1.7, f"speed should reach +75%, got {wave_speed_mul(40)}"
assert wave_speed_mul(40) <= 1.0 + C.WAVE_SPEED_MAX + C.WAVE_SPEED_POST_KNEE_MAX + 1e-9
assert wave_cap(40, 6) == 6 + C.WAVE_CAP_POST_KNEE_MAX, "cap bonus must saturate"
assert wave_hp_bonus(20) > old_hp(20) * 1.5, "wave 20 hp barely moved"
print(f"late game: wave 20 hp {old_hp(20)} -> {wave_hp_bonus(20)}, "
      f"speed caps at {wave_speed_mul(40):.2f}, cap saturates at {wave_cap(40, 6)}")

# 3. champions: steeper, and the cap is still a cap
from lagarto.creatures.champions import chance
assert chance(1) == C.CHAMP_CHANCE_BASE, "wave 1 odds must be untouched (#23 is a mid-game fix)"
assert chance(1000) <= C.CHAMP_CHANCE_MAX + 1e-9, "champion chance must respect its cap"
assert chance(10) > 0.012 * 10, "champion ramp did not get steeper"
print(f"champions: wave 10 {chance(10):.3f}, caps at {C.CHAMP_CHANCE_MAX}")
print("ALL OK")
