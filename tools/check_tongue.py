"""Drive the whole tongue cycle and assert it behaves (issue #21).

The invariant that must never break, because breaking it is what the tongue got
reported for: the DRAWN tip is the KINEMATIC tip. The shaft may whip, sag and
undulate as much as it likes, but the ends of the drawn path are the mouth and
the exact point the hit resolves against.

On top of that, the three-beat shape: explosive out, taut stick where the hit
lands, reel that carries the catch home.
"""
import os, sys, math
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.world.pickups import Bug
display.init()
DT = 1 / 60
TOTAL = C.TONGUE_OUT_T + C.TONGUE_STICK_T + C.TONGUE_REEL_T


def fresh(prey_at=None):
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    p = g.players[0]
    p.energy = p.max_energy
    p.aim = Vector2(1, 0)
    g.pickups.clear(); g.prey.clear(); g.enemies.clear()
    prey = None
    if prey_at is not None:
        prey = Bug(p.pos + Vector2(prey_at, 0))
        g.pickups.append(prey)
    return g, p, prey


# --- 1. the tip invariant, across the whole cycle ------------------------- #
g, p, prey = fresh(prey_at=130)
p._pending_tongue_target = prey
p._launch_tongue(g)
worst_tip = worst_mouth = 0.0
reach_at = {}
phases_seen = []
while p.tongue_t > 0:
    ph, u = p.tongue_phase()
    if ph and (not phases_seen or phases_seen[-1] != ph):
        phases_seen.append(ph)
    tip, mouth = p.tongue_tip()
    path = p.tongue_path()
    worst_tip = max(worst_tip, Vector2(path[-1]).distance_to(tip))
    worst_mouth = max(worst_mouth, Vector2(path[0]).distance_to(mouth))
    assert len(path) == C.TONGUE_SEGMENTS, f"shaft lost segments: {len(path)}"
    reach_at[round(p.tongue_t, 4)] = mouth.distance_to(tip)
    p._tongue_step(DT, g)

assert worst_tip < 1e-9, f"drawn tip drifts from the real tip by {worst_tip}"
assert worst_mouth < 1e-9, f"drawn base drifts from the mouth by {worst_mouth}"
print(f"tip drift {worst_tip:.2e} px   base drift {worst_mouth:.2e} px   "
      f"over {len(reach_at)} frames")
assert phases_seen == ['out', 'stick', 'reel'], f"beat order wrong: {phases_seen}"
print(f"beats in order: {' -> '.join(phases_seen)}  "
      f"({C.TONGUE_OUT_T*1000:.0f} / {C.TONGUE_STICK_T*1000:.0f} / "
      f"{C.TONGUE_REEL_T*1000:.0f} ms)")

# an idle tongue draws nothing at all
assert p.tongue_tip() is None and p.tongue_path() is None

# --- 2. it must SLINGSHOT: most of the reach in the first beat ------------ #
ts = sorted(reach_at)
peak = max(reach_at.values())
at_out_end = max(v for k, v in reach_at.items() if k <= C.TONGUE_OUT_T + 1e-6)
half_t = min(k for k in ts if reach_at[k] >= peak * 0.5)
assert at_out_end > peak * 0.9, \
    f"OUT should nearly reach full extension, got {at_out_end:.0f} of {peak:.0f}"
assert half_t < C.TONGUE_OUT_T * 0.55, \
    f"half the reach should be covered in the first half of OUT, took {half_t*1000:.0f} ms"
print(f"slingshot: half reach at {half_t*1000:.0f} ms, "
      f"{at_out_end/peak*100:.0f}% of full reach by the end of OUT ({peak:.0f} px)")

# and it must come all the way home, not be left hanging
assert reach_at[ts[-1]] < peak * 0.25, \
    f"tongue did not retract: ended at {reach_at[ts[-1]]:.0f} of {peak:.0f}"
print(f"retracts home: {reach_at[ts[-1]]:.0f} px left at the last frame")

# --- 3. the shaft must actually bend, and be pinned while doing it -------- #
g, p, prey = fresh(prey_at=180)
p._pending_tongue_target = prey
p._launch_tongue(g)
max_bow = 0.0
for _ in range(int(TOTAL / DT)):
    if p.tongue_t <= 0:
        break
    p._tongue_step(DT, g)
    path = p.tongue_path()
    if path is None:
        break
    a, b = path[0], path[-1]
    if a.distance_to(b) > 20:
        max_bow = max(max_bow, max(
            abs((q - a).cross(b - a)) / a.distance_to(b) for q in path[1:-1]))
assert max_bow > 20.0, f"shaft barely bends -- reads as a straight line ({max_bow:.1f} px)"
print(f"shaft bows up to {max_bow:.1f} px off the mouth->tip line")

# ...and the bend must come from the RETRACT, not be there all along. A thrown
# tongue is ballistic and straight; a gathered one has nowhere to put its length
# but sideways.
g, p, prey = fresh(prey_at=180)
p._pending_tongue_target = prey
p._launch_tongue(g)
bow_by_phase = {'out': 0.0, 'stick': 0.0, 'reel': 0.0}
while p.tongue_t > 0:
    ph, _u = p.tongue_phase()
    path = p.tongue_path()
    if ph and path is not None:
        a, b = path[0], path[-1]
        d = a.distance_to(b)
        if d > 20:
            bow_by_phase[ph] = max(bow_by_phase[ph], max(
                abs((q - a).cross(b - a)) / d for q in path[1:-1]))
    p._tongue_step(DT, g)
print("bow by beat: " + "  ".join(f"{k}={v:.1f}px" for k, v in bow_by_phase.items()))
assert bow_by_phase['out'] < 6.0, \
    f"the throw should be ballistic, bowed {bow_by_phase['out']:.1f} px"
assert bow_by_phase['reel'] > bow_by_phase['out'] * 3, \
    "the reel must coil visibly more than the throw"

# --- 4. the hit lands at full extension, not when the tongue gets home --- #
g, p, prey = fresh(prey_at=120)
p._pending_tongue_target = prey
p._launch_tongue(g)
hit_t = None
while p.tongue_t > 0:
    p._tongue_step(DT, g)
    if p._tongue_hit and hit_t is None:
        hit_t = p.tongue_t
assert hit_t is not None, "the tongue never connected"
assert hit_t <= C.TONGUE_OUT_T + C.TONGUE_STICK_T + DT, \
    f"hit landed at {hit_t*1000:.0f} ms, after STICK ended"
print(f"hit lands at {hit_t*1000:.0f} ms (OUT ends at {C.TONGUE_OUT_T*1000:.0f})")
assert prey.dead, "food that reached the mouth was not eaten"
print("food carried home and eaten")

# --- 5. carrying: the catch rides the tip ------------------------------- #
g, p, prey = fresh(prey_at=150)
p._pending_tongue_target = prey
p._launch_tongue(g)
gap_while_carrying = []
while p.tongue_t > 0:
    p._tongue_step(DT, g)
    ph, _u = p.tongue_phase()
    if ph == 'reel' and p.tongue_grabbed is not None and not prey.dead:
        tip, _ = p.tongue_tip()
        gap_while_carrying.append(prey.pos.distance_to(tip))
assert gap_while_carrying, "nothing was ever grabbed"
# Glued to the sticky pad on the way back only: during STICK the tip springs
# deliberately PAST the target, so measuring there would just report the
# overshoot. A soft follow instead of glue lags a ~900 px/s tip by tens of
# pixels, which reads as food trailing on a string rather than being caught.
assert max(gap_while_carrying) < 2.0, \
    f"the catch is not stuck to the pad: max gap {max(gap_while_carrying):.1f} px"
print(f"catch rides the pad: max gap {max(gap_while_carrying):.2f} px "
      f"over {len(gap_while_carrying)} frames")

# --- 6. a whiff must be harmless and still retract ----------------------- #
g, p, _ = fresh()
p._pending_tongue_target = None
p._launch_tongue(g)
n = 0
while p.tongue_t > 0 and n < 200:
    p._tongue_step(DT, g)
    n += 1
assert p.tongue_t == 0 and p.tongue_grabbed is None, "a whiff left the tongue stuck out"
print(f"whiff retracts cleanly in {n} frames")

# --- 7. an enemy is pulled, never teleported ---------------------------- #
from lagarto.creatures import species
g, p, _ = fresh()
foe = species.make('runner', p.pos + Vector2(140, 0))
g.enemies.append(foe)
p._pending_tongue_target = foe
foe.vel *= 0.0          # measure the drag, not whatever the spawn gave it
start = Vector2(foe.pos)
p._launch_tongue(g)
jumps = []
while p.tongue_t > 0:
    before = Vector2(foe.pos)
    p._tongue_step(DT, g)
    foe.pos += foe.vel * DT          # the world would integrate this
    jumps.append(before.distance_to(foe.pos))
assert max(jumps) < 40, f"an enemy was teleported {max(jumps):.0f} px in one frame"
assert foe.pos.distance_to(p.pos) < start.distance_to(p.pos), "the enemy was not pulled in"
print(f"enemy pulled by force: max {max(jumps):.1f} px/frame, "
      f"{start.distance_to(p.pos):.0f} -> {foe.pos.distance_to(p.pos):.0f} px away")
print("ALL OK")
