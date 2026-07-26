"""Assert the drawn tongue ends exactly at the kinematic tip, at every phase."""
import os, math, pygame
os.environ.setdefault('SDL_VIDEODRIVER','dummy'); os.environ.setdefault('SDL_AUDIODRIVER','dummy')
pygame.init()
from lagarto.render import display
from lagarto.core import fonts
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
display.init(); font, bigfont = fonts.get(16), fonts.get(26)
g = Game(1, make_controllers(1, []), font, bigfont, mode='normal', chars=None)
p = g.players[0]

def bez(a, b, c, u):
    m = 1 - u
    return pygame.Vector2(m*m*a[0] + 2*m*u*b[0] + u*u*c[0],
                          m*m*a[1] + 2*m*u*b[1] + u*u*c[1])

worst_end = worst_start = 0.0
sag_at = {}
for step in range(1, 100):
    p.tongue_t = step / 100.0
    tip, mouth = p.tongue_tip()
    mo, mid, ti = p.tongue_path()
    # Bezier endpoints must BE the mouth and the true tip -- no drift, ever.
    worst_end = max(worst_end, bez(mo, mid, ti, 1.0).distance_to(tip))
    worst_start = max(worst_start, bez(mo, mid, ti, 0.0).distance_to(mouth))
    # how far the curve bows off the straight mouth->tip line
    straight = [mouth.lerp(tip, u / 10.0) for u in range(11)]
    sag_at[step] = max(bez(mo, mid, ti, u / 10.0).distance_to(straight[u]) for u in range(11))

assert worst_end < 1e-9, f"drawn tip drifts from the real tip by {worst_end}"
assert worst_start < 1e-9, f"drawn base drifts from the mouth by {worst_start}"
assert p.tongue_path() is not None
p.tongue_t = 0.0
assert p.tongue_tip() is None and p.tongue_path() is None, "inactive tongue must draw nothing"
peak = max(sag_at, key=sag_at.get)
print(f"tip drift max = {worst_end:.2e} px   base drift max = {worst_start:.2e} px")
print(f"bow: t=.10 {sag_at[10]:6.1f}px  t=.50 {sag_at[50]:6.1f}px  t=.90 {sag_at[90]:6.1f}px  peak at t={peak/100:.2f}")
assert sag_at[50] > sag_at[10] and sag_at[50] > sag_at[90], "arc must be flat at the mouth and bowed at full reach"
print("ALL OK")
