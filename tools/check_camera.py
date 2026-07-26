"""Assert the cached camera transform matches the naive one exactly.

w2s is the hottest function in the frame (~5,500 calls/frame), so it folds
zoom/pos/centre/shake into three floats refreshed by the setters of those four
properties. That is only safe if the cache can never go stale -- this pins both
halves: the maths agrees with the naive formula, and every mutation path
refreshes it.
"""
import os, sys, random
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render.camera import Camera
from lagarto.core import config as C

def naive(cam, world):
    cx, cy = cam.center
    return (int((world[0] - cam.pos.x) * cam.zoom + cx + cam.shake_off.x),
            int((world[1] - cam.pos.y) * cam.zoom + cy + cam.shake_off.y))

rng = random.Random(7)
cam = Camera()
pts = [(rng.uniform(-4000, 4000), rng.uniform(-4000, 4000)) for _ in range(200)]

# every setter must leave the cache correct
mutations = [
    ('pos',       lambda: setattr(cam, 'pos', Vector2(rng.uniform(0, 3200), rng.uniform(0, 3200)))),
    ('zoom',      lambda: setattr(cam, 'zoom', rng.uniform(0.4, 2.0))),
    ('center',    lambda: setattr(cam, 'center', (rng.uniform(0, 900), rng.uniform(0, 600)))),
    ('shake_off', lambda: setattr(cam, 'shake_off', Vector2(rng.uniform(-9, 9), rng.uniform(-9, 9)))),
]
for round_ in range(40):
    name, mut = mutations[round_ % len(mutations)]
    mut()
    for p in pts:
        assert cam.w2s(p) == naive(cam, p), f"w2s drifted after setting {name}"
print(f"w2s matches the naive transform after {len(mutations)} mutation kinds x 40 rounds")

# follow() writes all three at once through the private fields -- it must refresh too
class P:
    def __init__(self, x, y):
        self.pos, self.dead = Vector2(x, y), False
cam.add_shake(20)
for _ in range(30):
    cam.follow([P(rng.uniform(0, 3200), rng.uniform(0, 3200))], 1 / 60)
    for p in pts[:40]:
        assert cam.w2s(p) == naive(cam, p), "w2s drifted after follow()"
print("w2s matches after follow() (pos + zoom + shake all moved)")

# w2s_many must equal w2s pointwise
assert cam.w2s_many(pts) == [cam.w2s(p) for p in pts], "w2s_many disagrees with w2s"
print(f"w2s_many == w2s over {len(pts)} points")

# visible() must agree with the bounds test it replaced
for p in pts:
    s = cam.w2s(p)
    for margin in (0, 80, 300):
        want = (-margin < s[0] < C.WIDTH + margin and -margin < s[1] < C.HEIGHT + margin)
        assert cam.visible(p, margin) == want, f"visible() disagrees at {p}, margin {margin}"
print("visible() agrees with the w2s bounds test at 3 margins")

# s2w must still invert w2s
cam.zoom = 1.0
cam.shake_off = Vector2()
for p in pts[:50]:
    back = cam.s2w(cam.w2s(p))
    assert abs(back.x - p[0]) < 1.5 and abs(back.y - p[1]) < 1.5, "s2w no longer inverts w2s"
print("s2w still inverts w2s")
print("ALL OK")
