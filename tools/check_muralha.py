"""Assert A Muralha's grid of fire lands on the fight (issue #113).

Three things have to hold or the boss's signature attack is decoration:

1. **The grid is anchored to the arena.** ``game.arena_bounds`` is centred on
   the boss, which spawns anywhere in the 3200x3200 world; a grid measured from
   the world origin lands in the map's top-left corner and hits nobody. Every
   puddle has to fall inside the box, and the box has to be covered -- all four
   quadrants, nothing eaten by ``Game.spawn_puddle``'s 40-puddle cap.
2. **A shooter with no arena still gets a grid around itself.** The emitter is
   shared (ADR-0012), so it may be called by something that never got a
   ``BossArena``.
3. **``MURALHA_GRID_LIFE`` is under the interval that reapplies the grid.**
   The Acido / venom-puddle / sting-slow rule, on the boss side this time.

Run:  python tools/check_muralha.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.flow.rounds import make_boss
from lagarto.flow.boss import arena as ar, patterns as pat
from lagarto.combat import emitter
display.init()

# Far from the world origin on purpose: this is the whole bug. The old grid
# started at (cell // 2, cell // 2) and never came near a boss spawned here.
BOSS_AT = Vector2(2500, 2100)
DIALS = pat.PATTERNS['grid_of_fire']


def fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    g.puddles = []
    g.enemies = []
    p = g.players[0]
    p.pos = Vector2(BOSS_AT) - Vector2(200, 0)
    boss = make_boss(g, 'muralha', 6, Vector2(BOSS_AT))
    g.enemies.append(boss)
    return g, p, boss


# --------------------------------------------------------------------------- #
# 1. every puddle lands inside the arena, and the arena is covered             #
# --------------------------------------------------------------------------- #
g, p, boss = fresh()
ar.for_boss('muralha').apply(g, boss.pos)
assert g.arena_bounds, "A Muralha spawned without an arena -- nothing to anchor to"
x0, y0, x1, y1 = g.arena_bounds
emitter.grid_of_fire(boss, g, p, DIALS)
puddles = list(g.puddles)
assert puddles, "grid_of_fire spawned no puddle at all"
outside = [q for q in puddles if not (x0 <= q.pos.x <= x1 and y0 <= q.pos.y <= y1)]
assert not outside, \
    f"{len(outside)}/{len(puddles)} puddles landed outside the arena " \
    f"(first at {outside[0].pos}, arena {g.arena_bounds})"

cell = DIALS['cell']
cols, rows = int((x1 - x0) // cell), int((y1 - y0) // cell)
want = sum(1 for cx in range(cols) for cy in range(rows) if (cx + cy) % 3)
assert len(puddles) == want, \
    f"the grid asked for {want} cells and only {len(puddles)} exist -- " \
    f"Game.spawn_puddle's 40-puddle cap ate the rest of the arena"
# a grid that only reaches one corner is not a grid: all four quadrants lit
mx, my = (x0 + x1) / 2, (y0 + y1) / 2
quads = {(q.pos.x > mx, q.pos.y > my) for q in puddles}
assert len(quads) == 4, f"the grid only reached {len(quads)}/4 quadrants of the arena"
# the gaps are what makes it survivable -- a solid floor of fire is a fail too
assert want < cols * rows, "no cell was skipped -- the grid has no gaps to stand in"
print(f"  arena: {int(x1 - x0)}x{int(y1 - y0)} at ({int(x0)}, {int(y0)}), boss at "
      f"({int(boss.pos.x)}, {int(boss.pos.y)})")
print(f"  grid: {len(puddles)}/{cols * rows} cells lit ({cols * rows - want} gaps), "
      f"all inside the arena, all 4 quadrants covered")

# --------------------------------------------------------------------------- #
# 2. no arena -> a box around the shooter, not around the world origin         #
# --------------------------------------------------------------------------- #
g, p, boss = fresh()
assert g.arena_bounds is None
emitter.grid_of_fire(boss, g, p, DIALS)
assert g.puddles, "grid_of_fire spawned nothing without an arena"
far = max(max(abs(q.pos.x - boss.pos.x), abs(q.pos.y - boss.pos.y)) for q in g.puddles)
assert far <= 460, f"a puddle landed {far:.0f} px from a shooter that has no arena"
print(f"  no arena: {len(g.puddles)} cells, none further than {far:.0f} px from the shooter")

# --------------------------------------------------------------------------- #
# 3. the fire cannot outlive the cooldown that reapplies it                    #
# --------------------------------------------------------------------------- #
# Shortest possible gap between two grids: the recover state (0.5 s, hardcoded
# in BossAI.tick), the shortest roll of the attack cooldown scaled by the
# phase's cd_mul, and the wind-up as shortened by the angriest mood.
RECOVER = 0.5
cd_mul = min(ph['cd_mul'] for ph in pat.muralha_phases() if 'grid_of_fire' in ph['patterns'])
tell = pat.wall_personality().windup_mult('enraged')
reapply = RECOVER + C.BOSS_CD_MIN * cd_mul + DIALS['windup'] * tell
assert C.MURALHA_GRID_LIFE < reapply, \
    f"MURALHA_GRID_LIFE {C.MURALHA_GRID_LIFE}s >= the {reapply:.2f}s that can reapply " \
    f"the grid -- two grids overlap and the damage stacks"
ticks = int(C.MURALHA_GRID_LIFE / C.MURALHA_GRID_TICK)
print(f"  life: {C.MURALHA_GRID_LIFE}s < {reapply:.2f}s between casts "
      f"({ticks} ticks x {C.MURALHA_GRID_DMG} dmg for standing in one cell)")

print("ALL OK -- the grid of fire lands on the arena and does not stack with itself")
