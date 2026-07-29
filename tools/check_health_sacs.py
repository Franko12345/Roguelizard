"""Verify issue #131 health sacs through their public drawing seam."""
import inspect
import math
import os
import sys
import tempfile
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

pygame.init()

from lagarto.core import palette
from lagarto.creatures import ai
from lagarto.game import hud

WIDTH = 216
MAX_HEALTHS = (100, 130, 162, 250, 317)

for maximum in MAX_HEALTHS:
    probes = (0, 12, 24.5, maximum * 0.47, maximum - 0.5, maximum)
    for health in probes:
        fills = hud.health_sac_fills(health, maximum)
        represented = sum(fills) * hud.HEALTH_SAC_HP
        expected = max(0.0, min(health, maximum))
        assert math.isclose(represented, expected, abs_tol=1e-9), (maximum, health, represented)
        assert len(fills) == math.ceil(maximum / hud.HEALTH_SAC_HP)

for maximum in range(25, 1001):
    count, rows, columns, size = hud.health_sac_layout(maximum, WIDTH)
    bounds = hud.health_sacs_bounds(0, 60, maximum, WIDTH)
    assert rows <= hud.HEALTH_SAC_MAX_ROWS
    assert bounds.width <= WIDTH, (maximum, count, rows, columns, size, bounds)
    if count <= 16:
        assert columns <= hud.HEALTH_SACS_PER_ROW
    else:
        assert rows == 2 and size <= hud.HEALTH_SAC_SIZE

rates = [hud.health_panic_rate(frac) for frac in (1.0, 0.75, 0.5, 0.25, 0.0)]
assert all(a < b for a, b in zip(rates, rates[1:])), rates

enemy_source = inspect.getsource(ai.AILizard._draw_health)
assert 'palette.health_color(f)' in enemy_source
assert palette.health_color(0.0) == (240, 60, 60)
assert palette.health_color(0.5) == (250, 200, 60)
assert palette.health_color(1.0) == (110, 235, 110)

surface = pygame.Surface((900, 250), 0, 24)
surface.fill((9, 10, 17))
cases = ((100, 100, '100 HP cheio'), (7, 100, '100 HP quase morto'),
         (163, 250, '250 HP parcial'), (81, 130, 'coop P1'), (22, 162, 'coop P2'))
font = pygame.font.Font(None, 18)
for index, (health, maximum, label) in enumerate(cases):
    x = 20 + index * 175
    surface.blit(font.render(label, True, (230, 230, 240)), (x, 18))
    hud.draw_health_sacs(surface, x, 82, 155, health, maximum, 1.3 + index, impact=0.7)
shot = os.path.join(tempfile.gettempdir(), 'issue-131-health-sacs.png')
pygame.image.save(surface, shot)

perf = pygame.Surface((500, 180), 0, 24)
frames = 600
start = time.perf_counter()
for frame in range(frames):
    perf.fill((0, 0, 0))
    hud.draw_health_sacs(perf, 10, 70, WIDTH, 399, 400, frame / 60)
    hud.draw_health_sacs(perf, 264, 70, WIDTH, 399, 400, frame / 60)
elapsed_ms = (time.perf_counter() - start) * 1000 / frames
assert elapsed_ms < 1.0, elapsed_ms

print('health arithmetic:', ', '.join(str(value) for value in MAX_HEALTHS))
print('layout: 8 per row, 2 rows maximum, shrink after 16')
print('panic rates full->empty:', ', '.join(f'{rate:.2f}' for rate in rates))
print('enemy health ramp: byte-for-byte stops intact')
print(f'coop 32-sac draw: {elapsed_ms:.3f} ms/frame (<1.0 ms)')
print('screenshot:', shot)
