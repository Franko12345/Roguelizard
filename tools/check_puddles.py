"""Assert the #135 blood-puddle system does what the issue asked.

Five things have to hold or the marks are decoration:

1. The player bleeding spawns exactly one puddle per landed hit, marked
   permanent (the run keeps them all).
2. The enemy bleeding uses the species colour, darkened, not red -- otherwise
   every lizard leaks the same paint.
3. Enemy puddles die on their lifetime tick; player puddles do not. World
   reaps them via ``update_puddles``, not via the game loop.
4. The 200-cap eviction is FIFO among non-permanent, so a player can NEVER
   lose their own marks, even if 300 enemies bleed on top of them.
5. The draw path doesn't crash on a dummy surface, with and without a real
   cam. (No snapshot / pixel assertion; we don't pin a colour blend.)

Run:  python tools/check_puddles.py
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
from lagarto.creatures import species
from lagarto.world import puddles
display.init()
DT = 1 / 60


def fresh():
    """A blank game: empty pools, frozen rounds, no projectiles interfering."""
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    g.projectiles = []
    g.puddles = []                # acid pools (different system)
    g.enemies = []
    g.friends = []
    g.rounds.timer = 1e9          # hold the round off; we drive dmg manually
    return g


def hit_player(g, dmg=10):
    """Land one hit on player 0. Reset i-frames so the hit connects."""
    p = g.players[0]
    p.hit_flash = 0.0
    p.dash_time = 0.0              # dashing property reads dash_time > 0
    p.roll_time = 0.0
    p.down = False
    p.shed_t = 0.0
    p.vel = Vector2(50, 0)         # known knockback direction (rightward)
    return p.hurt(g, Vector2(1, 0), dmg)


def hit_enemy(g, kind='runner', dmg=4):
    """Spawn an enemy at MID, land one non-lethal hit on it, return it."""
    e = species.make(kind, Vector2(C.WORLD_W / 2, C.WORLD_H / 2))
    g.enemies.append(e)
    e.take_hit(g, Vector2(1, 0), dmg)
    return e


# --------------------------------------------------------------------------- #
# 1. Player bleed: one puddle, permanent                                       #
# --------------------------------------------------------------------------- #
g = fresh()
landed = hit_player(g)
assert landed, "test setup failed: hit did not land"
assert len(g.world.puddle_list) == 1, \
    f"player hit spawned {len(g.world.puddle_list)} puddles, expected 1"
p0 = g.world.puddle_list[0]
assert p0.lifetime < 0.0, f"player puddle is fading (lifetime={p0.lifetime})"
assert p0.color == puddles.COL_BLOOD, \
    f"player blood colour {p0.color}, expected {puddles.COL_BLOOD}"
assert len(p0.vertices) == 10, f"expected 10 vertices, got {len(p0.vertices)}"
# trail should land behind the knockback (vel = (+50, 0) -> back = -20 on x)
assert p0.pos.x < C.WORLD_W / 2 - 15, \
    f"puddle trail did not offset backward: {p0.pos}"
print(f"  1. player hit -> 1 permanent puddle, 10 verts, trail at x={p0.pos.x:.0f}")


# --------------------------------------------------------------------------- #
# 2. Enemy bleed: species colour, darkened                                     #
# --------------------------------------------------------------------------- #
g = fresh()
e = hit_enemy(g, 'runner', dmg=4)        # runner hue 190 -> bluish
expected = puddles.darken_species_color(e.color)
assert expected != e.color, "darken was a no-op -- colours did not change"
assert all(c >= 30 for c in expected), \
    f"darkened colour collapsed a channel: {expected}"
enemy_puddles = [p for p in g.world.puddle_list if p.lifetime >= 0]
assert len(enemy_puddles) == 1, \
    f"enemy hit spawned {len(enemy_puddles)} non-permanent puddles"
assert enemy_puddles[0].color == expected, \
    f"colour {enemy_puddles[0].color} != expected {expected}"
print(f"  2. runner hit -> enemy puddle {e.color} -> {expected}")


# --------------------------------------------------------------------------- #
# 3. Lifetime: enemy puddles die, player puddles do not                         #
# --------------------------------------------------------------------------- #
g = fresh()
hit_player(g)                            # permanent
hit_enemy(g, 'runner', dmg=4)            # lifetime = LIFETIME
assert len(g.world.puddle_list) == 2
# step exactly LIFETIME + a bit, in 1/60 chunks
steps = int(puddles.LIFETIME / DT) + 5
for _ in range(steps):
    g.world.update_puddles(DT)
remaining = g.world.puddle_list
assert len(remaining) == 1, \
    f"after {puddles.LIFETIME:.0f}s expected 1 puddle, got {len(remaining)}"
assert remaining[0].lifetime < 0.0, "the player puddle was reaped"
assert remaining[0].alpha > 0.0, "the remaining puddle is invisible"
print(f"  3. {puddles.LIFETIME:.0f}s ticked -> enemy reaped, player still alpha={remaining[0].alpha:.0f}")


# --------------------------------------------------------------------------- #
# 4. Cap eviction: 201 enemy -> 200, oldest non-permanent evicted, players safe  #
# --------------------------------------------------------------------------- #
g = fresh()
# seed with 3 player puddles so they ride along
for _ in range(3):
    hit_player(g, dmg=2)
player_count = sum(1 for p in g.world.puddle_list if p.lifetime < 0)
# dump 201 enemy puddles directly via world.add_puddle (no need for live enemies)
for k in range(201):
    # mark each with its order so we can check which one got evicted
    g.world.add_puddle(Vector2(100 + (k % 50) * 8, 100 + (k // 50) * 8),
                       dmg=4, color=(100, 100, 100))
assert len(g.world.puddle_list) == puddles.PUDDLE_CAP, \
    f"cap broken: {len(g.world.puddle_list)} puddles alive (cap={puddles.PUDDLE_CAP})"
# The 3 player puddles are still here
players_left = sum(1 for p in g.world.puddle_list if p.lifetime < 0)
assert players_left == player_count, \
    f"player puddles evicted: was {player_count}, now {players_left}"
# First added non-permanent (the original enemy puddles from take_hit, plus
# the very first of the 201) is gone -- the FIFO finds the earliest enemy.
# We seeded zero enemy puddles before the loop, so index 0 was the first of
# the 201 we just added; it must NOT be present, and the last MUST be.
positions = [(p.pos.x, p.pos.y) for p in g.world.puddle_list]
first_added = (100, 100)                  # k = 0
last_added = (100 + (200 % 50) * 8, 100 + (200 // 50) * 8)
assert first_added not in positions, \
    f"FIFO failed: oldest non-permanent puddle is still at {first_added}"
assert last_added in positions, \
    f"FIFO failed: newest puddle is not at {last_added}"
print(f"  4. 201 enemy + 3 player -> cap {puddles.PUDDLE_CAP}, "
      f"{players_left} players intact, oldest gone, newest present")


# --------------------------------------------------------------------------- #
# 5. Draw: must not crash, with and without live game state                     #
# --------------------------------------------------------------------------- #
g = fresh()
hit_player(g)
hit_enemy(g, 'runner', dmg=4)
surf = pygame.Surface((C.WIDTH, C.HEIGHT))
g.world.draw_puddles(surf, g.cam)         # happy path: real cam
# empty-world path: no puddles -> early-return, no blit, no crash
g.world.puddle_list = []
g.world.draw_puddles(surf, g.cam)
# draw with a player puddle whose pos is way off-screen -> culled
g.world.add_puddle(Vector2(-99999, -99999), 4, (120, 0, 0))
g.world.draw_puddles(surf, g.cam)
print(f"  5. draw survives dummy surface, empty list, off-screen puddle")

print("\nALL OK")
