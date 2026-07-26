"""Assert the tail spring chain actually cascades (issue #8).

One spring made the whole tail lag as a rigid unit. A chain only earns its
keep if, after a sudden stop, the base settles BEFORE the tip -- and if the
one public handle (``tail_spring``) still scales the whole chain, because the
boss telegraph and the posing layer write to it.
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.creatures import species
from lagarto.creatures.base import TAIL_CHAIN_LEN, TAIL_SPRING_STIFFNESS, TAIL_CHAIN_STIFF_RATIO

c = species.make('critter', Vector2(1000, 1000))
assert c.tail_chain and len(c.tail_chain) == TAIL_CHAIN_LEN

# the tip link IS the public handle, so existing writers keep working
assert c.tail_spring is c.tail_chain[-1]

# run, then stop dead: measure how long each link takes to catch its joint
c.vel = Vector2(400, 0)
for _ in range(90):
    c.pos += c.vel * (1 / 60)
    c.spine.resolve(c.pos)
    c.update_secondary_springs(1 / 60)
c.vel = Vector2()
# Record each link's lag against its own joint, frame by frame. Raw lag is NOT
# comparable across links -- each tracks a different joint, and a mid-body joint
# simply travels further than the tail tip -- so each link is scored against its
# OWN peak. That makes "how fast does this link stop lagging" the metric, which
# is exactly what a cascade is supposed to differ in.
hist = [[] for _ in range(TAIL_CHAIN_LEN)]
for f in range(240):
    c.spine.resolve(c.pos)
    c.update_secondary_springs(1 / 60)
    js = c.spine.joints
    n = len(js)
    for i, s in enumerate(c.tail_chain):
        hist[i].append((s.value - js[max(0, n - TAIL_CHAIN_LEN + i)]).length())

decay = []
for h in hist:
    peak = max(h)
    decay.append(next((f for f, v in enumerate(h) if v < peak * 0.10), len(h)))
print("frames to fall to 10% of own peak lag, base -> tip:", decay)
# The two stiffest links sit on mid-body joints that stop when the body stops,
# so both settle within a few frames and their relative order is noise. The
# claim worth asserting is about the tail proper: the ring-out travels outward
# and the tip is the last thing still moving.
assert decay[1:] == sorted(decay[1:]), f"the ring-out must travel outward, got {decay}"
assert decay[-1] == max(decay), f"the tip must be the last to settle: {decay}"
assert decay[-1] > 4 * decay[0], f"the tip must ring far longer than the base: {decay}"

# one write to the public handle must scale the WHOLE chain, not just the tip
c.tail_spring.stiffness = TAIL_SPRING_STIFFNESS * 2.0
c.update_secondary_springs(1 / 60)
got = [round(s.stiffness, 4) for s in c.tail_chain]
want = [round(TAIL_SPRING_STIFFNESS * 2.0 * r, 4) for r in TAIL_CHAIN_STIFF_RATIO]
assert got == want, f"stiffness did not propagate: {got} != {want}"
print("stiffness after doubling the handle, base -> tip:", got)

# non-'normal' body plans have no tail chain and must not crash
k = species.make('octopus', Vector2(900, 900))
assert k.tail_chain is None and k.tail_spring is None
k.update_secondary_springs(1 / 60)
assert k._cosmetic_joints() is None
print("ALL OK")
