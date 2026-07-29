"""Verify anatomical energy and XP HUD behavior for issue #132."""
import os
import sys
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from lagarto.game import hud

pygame.init()
DT = 1 / 60

sizes = []
previous = hud.brain_size(1)
for level in range(1, 101):
    size = hud.brain_size(level)
    assert size >= previous, f"brain shrank at level {level}: {size} < {previous}"
    sizes.append(size)
    previous = size
    if level > 1:
        gained = hud.brain_folds(level) - hud.brain_folds(level - 1)
        assert 1 <= gained <= 2, f"level {level} gained {gained} folds"
assert sizes[-1] >= sizes[0], "brain did not grow across the run"
print(f"  brain: {sizes[0]:.3f} -> {sizes[-1]:.3f}, never shrank")

fluid = hud.CranialFluid()
fluid.update(0.96, DT)
for _ in range(12):
    fluid.update(0.96, DT)
peak = fluid.amplitude
fluid.update(0.0, DT)
assert fluid.last_fraction == 0.0, "cranial fluid did not drain on level-up"
for _ in range(300):
    fluid.update(0.0, DT)
assert fluid.amplitude < 0.002, f"fluid never settled: {fluid.amplitude:.5f}"
print(f"  fluid: peak {peak:.4f}, settled {fluid.amplitude:.5f}, drained to zero")

bellows = hud.Bellows(1.0)
values = []
for _ in range(90):
    bellows.update(0.5, DT)
    values.append(bellows.fraction)
assert values[0] < 1.0, "bellows did not collapse on the spend frame"
assert min(values) >= 0.44, "bellows spring overshot too far"
for _ in range(90):
    bellows.update(0.9, DT)
assert bellows.fraction > values[-1], "bellows did not inflate with energy"
print(f"  bellows: spend frame {values[0]:.4f}, settled {values[-1]:.4f}, refilled {bellows.fraction:.4f}")

surf = pygame.Surface((960, 540))
start = time.perf_counter()
for frame in range(600):
    for player in range(2):
        f = hud.CranialFluid()
        f.update((frame % 100) / 100, DT)
        hud.draw_skull(surf, (16 + player * 728, 470, 216, 46), 8, 0.7, f)
elapsed_ms = (time.perf_counter() - start) * 1000 / 600
assert elapsed_ms < 1.0, f"two skulls cost {elapsed_ms:.3f} ms/frame"
print(f"  perf: two skulls {elapsed_ms:.3f} ms/frame")

if '--shot' in sys.argv:
    shot = pygame.Surface((720, 150), 0, 24)
    shot.fill((9, 11, 18))
    cases = ((1, 0.12, "LEVEL 1 / LOW XP"),
             (1, 0.92, "LEVEL 1 / NEAR LEVEL"),
             (8, 0.12, "LEVEL 8"))
    font = pygame.font.Font(None, 22)
    for i, (level, xp, label) in enumerate(cases):
        state = hud.CranialFluid()
        state.update(xp, DT)
        x = 14 + i * 238
        hud.draw_skull(shot, (x, 22, 216, 72), level, xp, state)
        shot.blit(font.render(label, True, (232, 234, 250)), (x, 112))
    pygame.image.save(shot, 'hud-anatomy-comparison.bmp')
    print("  screenshot: hud-anatomy-comparison.bmp")

print("ALL OK")
