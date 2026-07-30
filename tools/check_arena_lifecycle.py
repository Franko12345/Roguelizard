"""Assert the per-boss arena is cleared on round clear (issue #157).

The arena was cleared only in ``start_round``, which fires at the start of the
NEXT round -- so during the whole ``cleared`` + ``camp`` window of the round
where the boss died, ``game.arena_bounds`` still held the dead boss's box.
``Player.integrate`` and the AI update both clamp against it, so the player
could not walk to the camp shop's door -- the camp was unreachable through
the cleared clearing.

Four scenarios are exercised, in order of how much an arena was applied:

1. **Muralha (the case from the bug report)** -- bounds were live during the
   fight, must drop the instant the round clears, and the player must be
   able to walk past the old box.
2. **Primordial** -- arena sets a tint only (no bounds), so ``arena_bounds``
   stayed None the whole fight. The clear() must still wipe the tint
   descriptor.
3. **Non-boss round** -- ``boss_id`` stays None. The clear() branch must
   short-circuit on the ``is not None`` guard.
4. **Tier-with-no-pool fallback** -- ``boss_id`` is a bare species key, not
   a named fight, so ``for_boss(boss_id)`` returns None. The call must
   short-circuit on the ``arena is not None`` guard, not crash on
   ``None.clear(g)``.

Run:  python tools/check_arena_lifecycle.py
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
from lagarto.flow.rounds import BOSS_POOL, BOSS_EVERY, make_boss
from lagarto.flow.boss import arena as ar
display.init()
DT = 1 / 60


def fresh():
    return Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
                mode='normal', chars=None)


def drive_to_cleared(g, boss):
    """Spawn a boss round, force the win condition, step until cleared/camp.

    The whole point of #157 was a regression that ``--smoke`` couldn't see:
    the dummy driver never enters the camp, so the old ``check_muralha.py``
    was green while the box kept trapping the player in the cleared state.
    We kill the boss, drain enemies/budget/nests/marks, and step ``g`` once
    so ``state_play.update`` notices ``rounds.state == 'cleared'`` and calls
    ``_enter_camp``. After this:

    - ``g.rounds.state == 'cleared'`` (the round manager did its job)
    - ``g.state == 'camp'`` (the FSM walked forward -- the bit that broke)
    - ``g.arena_bounds is None`` (the fix -- what was missing before)
    """
    # wave 5 is the first BOSS_EVERY slot; that flags is_boss_round and
    # _spawn_boss runs. Bypassing the intermission timer the same way smoke
    # would, so the path is the real one. start_round() does wave += 1 first,
    # so seed wave=BOSS_EVERY-1 to land on a boss round.
    g.rounds.wave = BOSS_EVERY - 1
    g.rounds.start_round()
    boss = g.rounds.boss                   # the one start_round spawned
    assert boss is not None, "no boss spawned on a boss round -- harness is broken"
    # Kill the boss outright; boss-tier HP is small relative to a long burn.
    boss.hp = 0
    boss.dead = True
    # cleared() needs: boss dead (yes), budget spent, no alive enemies, no
    # marks, and either the budget path OR all nests dead with no enemies.
    # Both paths converge on the same single line that calls clear(), so we
    # drain everything to be sure.
    g.rounds.budget = 0
    g.rounds.marks = []
    g.enemies = []                         # every enemy drops with the boss
    g.rounds.nests = []                    # nests were already emptied
    # The actual transition we are checking: one update lands the round in
    # 'cleared' AND runs the new clear() branch.
    g.rounds.update(DT)
    assert g.rounds.state == 'cleared', \
        f"round never cleared (state={g.rounds.state!r}) -- check the cleared() predicate"
    # Now the FSM bit the old harness missed: state_play should open the
    # camp on this step, not just leave the player floating in 'play'.
    g.step(DT)
    assert g.state == 'camp', \
        f"the camp never opened (game.state={g.state!r}) -- the bounds leak " \
        f"would have hidden here, since the player couldn't reach the door"


# --------------------------------------------------------------------------- #
# 1. Muralha: a boss WITH an arena must drop the box the moment the round    #
#    clears -- this is the case the bug report was filed against.             #
# --------------------------------------------------------------------------- #
g = fresh()
drive_to_cleared(g, None)
assert g.arena is None, \
    f"game.arena still points at the dead boss's BossArena: {g.arena!r}"
assert g.arena_bounds is None, \
    f"game.arena_bounds still holds the dead boss's box: {g.arena_bounds!r} " \
    f"-- this is the exact regression from issue #157; the player is trapped"
# And the player can now actually WALK out of where the old box was. The
# boss died at some world position with a 900x640 box; step the player a
# long way in one direction and confirm ``integrate`` no longer clamps them.
g.rounds.state = 'combat'                  # pretend a new round began
g.rounds.budget = 999                      # so update doesn't clear again
pl = g.players[0]
pl.vel = Vector2(pl.max_speed, 0)
start = Vector2(pl.pos)
for _ in range(int(2.0 / DT)):            # 2 seconds flat out
    pl.integrate(DT, bounds=g.arena_bounds)
traveled = pl.pos.distance_to(start)
# Free-running ceiling is pl.max_speed * 2s (193.05 * 2 = 386.1px); a wall
# clamp would cut this well below that, not just graze it.
free_running = pl.max_speed * 2.0
assert traveled > free_running * 0.9, \
    f"player covered only {traveled:.0f}px in 2s of free running (ceiling " \
    f"{free_running:.0f}px) -- arena_bounds still clamping during play " \
    f"(bounds={g.arena_bounds!r})"
print(f"  muralha: arena cleared on round clear; player covered {traveled:.0f}px "
      f"in 2s of free run (no clamp from the dead boss's box)")

# --------------------------------------------------------------------------- #
# 2. Primordial: a boss whose arena sets only the tint (no bounds) must still  #
#    clear cleanly -- arena descriptor present, arena_bounds stayed None the   #
#    whole fight.                                                              #
# --------------------------------------------------------------------------- #
g = fresh()
# Primordial is_final=True picks it regardless of tier. RUN_FINAL_WAVE is 20
# in NORMAL mode, so seed wave=RUN_FINAL_WAVE-1 so the start_round() bump
# lands on the final wave and spawns Primordial -- no need to drive a full run.
g.rounds.wave = C.RUN_FINAL_WAVE - 1
g.rounds.start_round()                    # spawns Primordial, tint arena only
prim = g.rounds.boss
assert prim is not None and prim.is_boss, "Primordial did not spawn"
# Primordial's arena sets a tint but no bounds -- arena is set, bounds is None.
assert ar.for_boss('primordial') is not None, "Primordial lost its tint arena"
assert g.arena is not None and g.arena_bounds is None, \
    f"Primordial's apply() should tint without bounds; got arena={g.arena!r} " \
    f"bounds={g.arena_bounds!r}"
prim.hp = 0
prim.dead = True
g.rounds.budget = 0
g.rounds.marks = []
g.enemies = []
g.rounds.nests = []
g.rounds.update(DT)
assert g.rounds.state == 'cleared', \
    f"the tint-only round never cleared (state={g.rounds.state!r}) -- the " \
    f"new for_boss(boss_id).clear(g) call must work for any registered boss"
assert g.arena is None, \
    f"the tint descriptor survived: arena={g.arena!r} -- should have been cleared"
assert g.arena_bounds is None, \
    f"arena_bounds survived a tint-only fight: {g.arena_bounds!r}"
print(f"  primordial: tint-only arena cleared on round clear (no bounds to drop)")

# --------------------------------------------------------------------------- #
# 3. Non-boss round: the cleared transition must not crash when there was     #
#    never a boss in the first place.                                          #
# --------------------------------------------------------------------------- #
g = fresh()
g.rounds.start_round()                    # wave 1, no boss
g.rounds.budget = 0
g.rounds.marks = []
g.enemies = []
g.rounds.nests = []
g.rounds.update(DT)
assert g.rounds.state == 'cleared', "non-boss round never cleared"
assert g.arena is None and g.arena_bounds is None, \
    "non-boss round somehow ended with an arena applied"
print(f"  non-boss: cleared cleanly, arena stayed None throughout")

# --------------------------------------------------------------------------- #
# 4. Tier-with-no-pool fallback: boss_id is a bare species key, not a named   #
#    fight -- for_boss returns None. The clear() call must short-circuit so   #
#    this round still cleans up without crashing on None.clear(g).            #
# --------------------------------------------------------------------------- #
import lagarto.flow.rounds as _rounds_mod
saved = _rounds_mod._boss_pool_for_tier
_rounds_mod._boss_pool_for_tier = lambda t: None      # force the bare-species path
try:
    g = fresh()
    g.rounds.wave = 4
    g.rounds.start_round()
    bid = g.rounds.boss_id
    assert bid is not None, "no boss_id was set -- the test cannot exercise for_boss(None)"
    assert ar.for_boss(bid) is None, \
        f"expected bare-species fallback to leave ARENAS empty for {bid!r}"
    g.rounds.boss.hp = 0
    g.rounds.boss.dead = True
    g.rounds.budget = 0
    g.rounds.marks = []
    g.enemies = []
    g.rounds.nests = []
    g.rounds.update(DT)
    assert g.rounds.state == 'cleared', \
        f"bare-species round never cleared (state={g.rounds.state!r}) -- " \
        f"the new short-circuit on for_boss(bid) is None must let it through"
    print(f"  no-pool fallback: boss_id={bid!r}, for_boss=None, round cleared cleanly")
finally:
    _rounds_mod._boss_pool_for_tier = saved

print("ALL OK -- arena bounds are dropped the moment the round clears")
