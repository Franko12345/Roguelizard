"""Issue #120: headless boss time-to-kill (TTK) harness.

Boss HP today is ``int((90 + 200 * tier) * (2.0 if is_final else 1.0))`` -- a
number nobody measured. This simulates a boss fight headlessly and reports
time-to-death, max phase reached, and distinct patterns fired -- per boss, per
DPS profile. The comparison across bosses and across commits is the data that
justifies (or dispenses with) an HP buff.

Three DPS profiles are tested:

- ``starting (~30 DPS)``   -- level-1 player, only the dash
- ``mid (~80 DPS)``        -- mid-run build, dash + a couple of weapons
- ``end-of-run (~150 DPS)`` -- stacked build, all weapons + items + crits

The point is NOT to simulate the real player: it is having a number
COMPARABLE across bosses and across commits. The boss is a stationary target
(no dodge, no roll, no positioning) so the only variable is the boss itself.

The check ASSERTS that with the mid profile, every boss in ``BOSS_POOL``
reaches its final phase (``phase_reached >= max_phase``). If that holds, the
fight is long enough to show each phase's kit; if it fails, the harness is the
artefact that justifies an HP change. The recorded numbers go to
``docs/concepts/balance.md`` as the third balancing pass.

Run:  python tools/check_boss_ttk.py
"""
import os, sys
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
from lagarto.flow import rounds
from lagarto.flow.boss import arena as ar

display.init()
DT = 1 / 60
MID = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)

# Per-fight frame budget: long enough to reach final phase at mid DPS, short
# enough to keep the full sweep under ~30s. The worst case is the ANKH at
# tier TIER_CAP (HP 2090, 4 phases): reaching phase 4 needs ~75% of HP at
# 80 DPS, plus 3 transitions (1.0s each) -> ~24s. 1500 frames = 25s leaves
# margin; reduce if the full sweep goes over the 30s target.
FRAMES = 1500

# Reference DPS profiles. The number is what the harness tests; the label
# documents what the number is supposed to represent in the run. A bot only
# moves measures friction, not difficulty (balance.md, 2nd pass) -- this is
# a friction yardstick too. Use it to compare before/after, not to pick HP.
PROFILES = {
    'starting (30 DPS)':    30,
    'mid (80 DPS)':         80,
    'end-of-run (150 DPS)': 150,
}


TIER_CAP = 8               # wave 40; "highest applicable" for the 7+ pool is unbounded
                             # in endless mode -- cap at 8 (wave 40, a long but not
                             # eternal run) so the mid-profile boss fits in the
                             # frame budget. Capping too low hides real balance
                             # pressure at higher tiers; cap too high and the
                             # mid-profile boss times out before reaching phase 3.

def _highest_tier(bid):
    """The highest ``wave // BOSS_EVERY`` this boss is eligible for.

    ``BOSS_TIER_POOLS`` is a list of (range, ids); a boss's highest tier is
    the upper bound of every range that contains its id, capped at
    ``TIER_CAP`` so an unbounded range (the 7+ endless pool) does not push
    HP into the millions. ``primordial`` is not in any pool -- it is the
    run's fixed ``is_final`` climax -- so it falls back to ``tier=4``
    (wave 20 // 5) with ``is_final=True``.
    """
    best = None
    for rng, ids in rounds.BOSS_TIER_POOLS:
        if bid in ids:
            best = max(best or 0, max(rng))
    return min(best, TIER_CAP) if best else None


def _spawn(bid, game):
    """Spawn ``bid`` east of the player, apply its arena, return the boss."""
    tier = _highest_tier(bid) or 4
    is_final = (bid == 'primordial')
    p = game.players[0]
    boss = rounds.make_boss(game, bid, tier, p.pos + Vector2(300, 0),
                            is_final=is_final)
    game.enemies.append(boss)
    game.rounds.boss = boss
    arena = ar.for_boss(bid)
    if arena is not None:
        arena.apply(game, boss.pos)
    return boss


def _fresh():
    """A fresh Game with one pinned player at MID.

    The player must be both immortal AND pinned: ``AILizard.update`` short-
    circuits the boss AI tick when ``target.pos.distance_to(self.pos) >= 700``,
    and without ``knockback_immune`` a single boss hit shoves the player
    past that radius in well under a second. With the boss no longer ticking,
    ``_maybe_advance_phase`` stops firing and the harness under-reports phases
    reached (the boss silently dies in phase 1).
    """
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    p = g.players[0]
    p.pos = Vector2(MID)
    p.vel = Vector2()
    p.max_health = 1e6
    p.health = 1e6
    p.knockback_immune = True
    g.cam.pos = Vector2(MID)
    return g


def _simulate(bid, dps, frames=FRAMES):
    """Simulate ``frames`` of fixed-step combat at ``dps`` and return a dict.

    Damage is applied as ``dps * DT`` per frame, only when the boss is
    vulnerable (``not boss_invuln``). ``take_hit`` is the boss's choke point
    for damage application; the boss FSM respects ``boss_invuln`` itself in
    ``hit_test``, but a direct ``take_hit`` does not -- so the harness checks
    the flag explicitly to mirror what the real game's ``hit_test`` does.

    Returns: ``{bid, dps, frames_alive, time, phase_reached, max_phase,
    patterns_seen, died}``. ``phase_reached`` is 1-indexed (so a 3-phase
    boss hitting phase 3 reports ``phase_reached=3``). ``patterns_seen`` is
    the count of distinct pattern ids the FSM actually fired.
    """
    g = _fresh()
    b = _spawn(bid, g)
    dmg_per_frame = dps * DT
    patterns = set()
    phase_reached = 1
    last_phase_i = 0
    frames_alive = frames
    for f in range(frames):
        # damage the boss while it is vulnerable; respect boss_invuln like
        # the real hit_test does (the FSM only sets it on intro/transition)
        if not b.boss_invuln and not b.dead:
            b.take_hit(g, Vector2(1, 0), dmg_per_frame)
        g.step(DT)
        if b.dead:
            frames_alive = f + 1
            break
        # record distinct patterns the FSM picked up
        pid = b.boss_ai.pattern_id
        if pid:
            patterns.add(pid)
        # phase_i can only increase (the FSM advances it on HP crossings)
        if b.boss_ai.phase_i != last_phase_i:
            phase_reached = b.boss_ai.phase_i + 1
            last_phase_i = b.boss_ai.phase_i
    return {
        'bid': bid,
        'dps': dps,
        'frames_alive': frames_alive,
        'time': frames_alive * DT,
        'phase_reached': phase_reached,
        'max_phase': len(b.boss_ai.phases),
        'patterns_seen': len(patterns),
        'died': b.dead,
        'max_hp': b.max_hp,
    }


def _run_sweep(dps):
    """Run every boss at ``dps``. Return a dict of bid -> result dict."""
    return {bid: _simulate(bid, dps) for bid in rounds.BOSS_POOL}


def main():
    print(f"issue #120: time-to-kill harness ({len(rounds.BOSS_POOL)} bosses x "
          f"{len(PROFILES)} profiles, {FRAMES} frames per simulation)")
    tables = {}
    for label, dps in PROFILES.items():
        rows = _run_sweep(dps)
        tables[label] = rows
        print(f"\n  {label}:")
        print(f"    {'boss':22} {'HP':>5} {'time':>7} {'ph':>3} "
              f"{'max':>4} {'pats':>4}")
        for bid, r in rows.items():
            ph = f"{r['phase_reached']}/{r['max_phase']}"
            print(f"    {bid:22} {r['max_hp']:>5} {r['time']:>6.2f}s {ph:>3} "
                  f"{r['max_phase']:>4} {r['patterns_seen']:>4}")
    # The assert: with mid profile, every boss reaches its final phase.
    mid_rows = tables['mid (80 DPS)']
    fails = [(bid, r) for bid, r in mid_rows.items()
             if r['phase_reached'] < r['max_phase']]
    if fails:
        print("\nFAIL: some boss(es) did not reach their final phase at "
              "mid DPS:")
        for bid, r in fails:
            print(f"  - {bid}: phase {r['phase_reached']}/{r['max_phase']} "
                  f"after {r['time']:.1f}s")
        raise SystemExit(1)
    # Tier-3 bosses still die in phase 1: surface the worst case explicitly.
    worst = min(r['time'] for r in mid_rows.values())
    best = max(r['time'] for r in mid_rows.values())
    print(f"\n  mid profile: every boss reaches its final phase; "
          f"TTK range {worst:.1f}s..{best:.1f}s")
    print("ALL OK")


if __name__ == '__main__':
    main()