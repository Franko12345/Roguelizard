"""Drive every authored boss through every phase and draw it.

--smoke never reaches a boss round, so a crash in a boss's draw path (or in a
pattern's tick) ships unnoticed. This spawns each BOSS_POOL entry, forces it
through each of its phases by dropping hp, ticks the FSM long enough to fire
its patterns, and draws it every frame.
"""
import os, sys, traceback, pygame
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
pygame.init()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.flow.rounds import BOSS_POOL, make_boss

display.init()
font, bigfont = fonts.get(16), fonts.get(26)
surf = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)

fails = []
for bid in BOSS_POOL:
    g = Game(1, make_controllers(1, []), font, bigfont, mode='normal', chars=None)
    p = g.players[0]
    boss = make_boss(g, bid, 6, p.pos + pygame.Vector2(300, 0))
    g.enemies.append(boss)
    g.rounds.boss = boss
    n_phases = len(boss.boss_ai.phases)
    seen = set()
    try:
        for phase in range(n_phases):
            # drop hp to the next phase threshold and let the FSM notice
            boss.hp = int(boss.max_hp * boss.boss_ai.phases[phase]['hp_frac'] * 0.99) or 1
            for _ in range(900):
                g.step(1 / 60)
                if boss.dead:
                    boss.dead = False
                    boss.hp = max(1, int(boss.max_hp * boss.boss_ai.phases[phase]['hp_frac']))
                if boss.boss_ai.pattern_id:
                    seen.add(boss.boss_ai.pattern_id)
                surf.fill((20, 20, 30))
                boss.draw(surf, g.cam)
                boss.boss_ai.draw(surf, g.cam)
                g.fx.draw(surf, g.cam, font)
    except Exception:
        fails.append((bid, traceback.format_exc()))
        print(f"  FAIL {bid}")
        continue
    print(f"  ok   {bid:18s} phases={n_phases}  patterns fired: {', '.join(sorted(seen)) or '(none)'}")

if fails:
    for bid, tb in fails:
        print(f"\n=== {bid} ===\n{tb}")
    raise SystemExit(f"{len(fails)} boss(es) crashed")
print(f"ALL OK -- {len(BOSS_POOL)} bosses drawn through every phase")
