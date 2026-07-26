"""Assert each PhaseOscillator reproduces the inline sine it replaced (issue #4).

The refactor is only worth anything if it is behaviour-preserving. Each preset
below carries the exact expression that used to live in the draw code; the
oscillator must match it to floating-point equality at every wobble value.
"""
import os, math, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.creatures import species, parts

# key -> (segment indices to test, the original inline expression)
ORIGINALS = {
    'spikes':      (range(0, 12), lambda w, i: math.sin(w * 1.3 + i * 0.5) * 0.18),
    'fins':        (range(0, 12), lambda w, i: math.sin(w * 2 + i) * 0.3),
    'antennae':    ((-1, 1),      lambda w, s: math.sin(w * 3 + s) * 0.3),
    'wings':       ((0,),         lambda w, i: math.sin(w * 7) * 1.0),
    'spore_sacs':  (range(0, 12), lambda w, i: math.sin(w * 3 + i) * 0.16),
    'tail_ripple': (range(0, 12), lambda w, i: math.sin(w * 2.2 - i * 0.9)),
}

c = species.make('critter', pygame.Vector2(500, 500))
worst = 0.0
for wobble in [0.0, 0.37, 1.0, 2.5, 6.28, 40.0, 123.456]:
    c.wobble = wobble
    parts.update_oscillators(c)
    for key, (idxs, fn) in ORIGINALS.items():
        for i in idxs:
            got = parts._osc_offset(c, key, i)
            want = fn(wobble, i)
            worst = max(worst, abs(got - want))
            assert abs(got - want) < 1e-12, f"{key}[{i}] @wobble={wobble}: {got} != {want}"

# creatures must stay desynchronised: wobble is seeded at random per creature,
# and an oscillator with its own zeroed clock would put them all in lockstep.
vals = set()
for _ in range(20):
    d = species.make('critter', pygame.Vector2(500, 500))
    parts.update_oscillators(d)
    vals.add(round(parts._osc_offset(d, 'spikes', 3), 6))
assert len(vals) > 15, f"creatures are in lockstep: only {len(vals)} distinct phases in 20"

# a creature with no oscillators (never integrated) must read 0, not crash
class Bare: pass
assert parts._osc_offset(Bare(), 'spikes', 0) == 0.0

print(f"max deviation from the original inline sines: {worst:.2e}")
print(f"phase desync across 20 fresh creatures: {len(vals)}/20 distinct")
print("ALL OK")
