"""Issue #173: BULLET_SCALE and BULLET_GLOW were too intense at 1.45/1.0.

The constants are DRAW-only (projectile.py:48, 112-113), so changing
them does not move collision or reach -- it only shrinks the visual
footprint of every projectile in the scene. This check asserts the
current values match the playtest decision (1.2 / 0.7) by measuring
the behaviour they drive: the constructed ``Projectile.radius`` is the
caller's ``radius`` argument multiplied by ``BULLET_SCALE``; revert
either constant and this fails.

Run:  python tools/check_bullet_scale.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.core import config as C
from lagarto.combat.projectile import Projectile

# The values the playtest picked (#173): small enough not to flood the
# scene, large enough that the tight hot pass still reads as a slug.
assert C.BULLET_SCALE == 1.2, (
    f"BULLET_SCALE reverted to {C.BULLET_SCALE}; playtest (#173) asked for 1.2 "
    f"to stop the halo eating every creature on screen.")
assert C.BULLET_GLOW == 0.7, (
    f"BULLET_GLOW reverted to {C.BULLET_GLOW}; playtest (#173) asked for 0.7 "
    f"so the bullets stop looking 'muito estranhos'.")

# Behaviour: constructed radius must equal caller arg * BULLET_SCALE
p = Projectile(pos=(0, 0), vel=(0, 0), color=(255, 200, 100), radius=10)
assert abs(p.radius - 10 * 1.2) < 1e-6, (
    f"Projectile.radius = {p.radius}, expected {10 * 1.2} (10 * BULLET_SCALE)")
print(f"  values: BULLET_SCALE=1.2, BULLET_GLOW=0.7; Projectile.radius = "
      f"{p.radius} for arg=10")

print("ALL OK")