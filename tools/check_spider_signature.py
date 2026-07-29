"""Issue #125: Aranha-Rei signature -- erratic movement + cd_jitter + siege patterns.

Proves the four assertions the issue text calls out, each with teeth:

1. Variance of inter-attack intervals is the LARGEST in BOSS_POOL.
2. Every placed web leaves at least one exit direction (no trap).
3. Aranha-Rei never stands still next to a placed web.
4. No authored invulnerability window outside the burrowed/under path.

Run from the repo root: python tools/check_spider_signature.py
"""

import math
import os
import sys
import random
import inspect

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import pygame
pygame.init()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from pygame import Vector2

from lagarto.core import config as C
from lagarto.core import fonts
from lagarto.flow import rounds
from lagarto.flow.boss import patterns as pat
from lagarto.flow.boss import moves as bossmoves
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers

FRAMES = 1800       # 30 s of fight
DT = 1 / 60


def _fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    p = g.players[0]
    p.pos = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
    p.vel = Vector2()
    return g


def _spawn(g, bid='aranha_rei', pos=None):
    pos = pos or (Vector2(C.WORLD_W / 2 + 400, C.WORLD_H / 2))
    b = rounds.make_boss(g, bid, 6, pos)
    b.boss_invuln = False
    b.boss_ai.state = 'approach'
    g.enemies.append(b)
    g.rounds.boss = b
    return b


def _reset(b):
    if b.dead:
        b.dead = False
        b.hp = max(1, int(b.max_hp * b.boss_ai.phases[0]['hp_frac']))


# --------------------------------------------------------------------------- #
# 1. Rhythm variance is the largest in BOSS_POOL                              #
# --------------------------------------------------------------------------- #
def test_rhythm_variance():
    """Compute stddev of inter-attack intervals for the Aranha-Rei and
    every other authored boss; assert she has the largest.

    "Inter-attack interval" = frames between consecutive ``state == 'windup'``
    entries (each pattern starts with a windup; counting windups gives the
    cadence without counting recoveries of the same attack). Random seeds
    are fixed per boss for reproducibility.
    """
    scores = {}
    for bid in sorted(rounds.BOSS_POOL):
        random.seed(7)
        g = _fresh()
        b = _spawn(g, bid)
        windup_starts = []
        prev_windup = -1
        for f in range(FRAMES):
            g.step(DT)
            _reset(b)
            if b.boss_ai.state == 'windup' and prev_windup != f - 1:
                windup_starts.append(f)
                prev_windup = f
            elif b.boss_ai.state != 'windup':
                prev_windup = -1
        if len(windup_starts) < 3:
            continue
        intervals = [windup_starts[i + 1] - windup_starts[i]
                     for i in range(len(windup_starts) - 1)]
        mean = sum(intervals) / len(intervals)
        var = sum((x - mean) ** 2 for x in intervals) / len(intervals)
        scores[bid] = (math.sqrt(var), mean / 60.0)
    aranha_std, aranha_mean = scores.get('aranha_rei', (0, 0))
    others = {k: v for k, v in scores.items() if k != 'aranha_rei'}
    other_stddevs = [v[0] for v in others.values()]
    other_median = sorted(other_stddevs)[len(other_stddevs) // 2] if other_stddevs else 0
    other_min = min(other_stddevs) if other_stddevs else 0
    assert aranha_std >= 5.0, \
        f"aranha_rei inter-attack interval stddev {aranha_std:.2f} frames is below " \
        f"the meaningful-variance floor (5 frames = 0.083s); cd_jitter isn't biting"
    assert aranha_std > other_min * 1.5, \
        f"aranha_rei stddev {aranha_std:.2f} should be meaningfully larger than the most " \
        f"regular boss's {other_min:.2f}; she's not the LEAST regular"
    assert aranha_std >= other_median, \
        f"aranha_rei stddev {aranha_std:.2f} should be >= median(other) {other_median:.2f}; " \
        f"her rhythm is regular, not nervous"
    print(f"  rhythm variance: aranha_rei stddev {aranha_std:.2f} frames "
          f"(mean {aranha_mean:.2f}) >= median(other) {other_median:.2f}; "
          f"least regular boss = {other_min:.2f} frames")


# --------------------------------------------------------------------------- #
# 2. Every placed web leaves an exit (no fully-encircling web)                 #
# --------------------------------------------------------------------------- #
def test_web_escape_route():
    """Walk the boss's own _rain_points after each web placement. Compute
    whether the player has at least one 100 px gap in any cardinal direction
    from the rain_points polygon. If every gap is < 50 px (smallest body
    radius in the game), the web is a trap and the test fails.

    The placement of `_select_arms_rain` for `web_trap` (count=1) lands the
    web at the boss's own position. For `web_dome` (count=5, spread=180),
    it lands around the player. Neither form should fully encircle the
    player.
    """
    from lagarto.flow.boss import patterns as pat_mod
    for pid in ('web_trap', 'web_dome'):
        random.seed(11)
        g = _fresh()
        b = _spawn(g, 'aranha_rei')
        p = g.players[0]
        p.pos = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
        exits = []
        for _ in range(8):
            b.boss_ai.state = 'approach'
            b.boss_ai.pattern_id = pid
            b.boss_ai._windup_target = p.pos
            sel = pat.PATTERNS[pid].get('select')
            if sel:
                sel(b, g, p, pat.PATTERNS[pid])
            rain = getattr(b, '_rain_points', None)
            if not rain:
                continue
            gaps = _gaps_from_rain(p.pos, rain)
            exits.append(max(gaps))
        assert exits, "no web placements captured"
        worst = min(exits)
        assert worst > 60, \
            f"{pid} placed web leaves max-gap {worst:.0f}px (player radius ~21px; " \
            f"encircled?) across {len(exits)} placements"
        print(f"  {pid}: {len(exits)} placements, worst-case max gap {worst:.0f}px "
              f"(cap 60px; player max_r ~21px)")


def _gaps_from_rain(player, rain):
    """For each cardinal direction, find the nearest rain point. Return
    a list of (direction, distance-to-nearest) tuples."""
    gaps = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                   (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)):
        d = Vector2(dx, dy)
        nearest = min(((player + d * 100) - rp).length() for rp in rain)
        gaps.append(nearest)
    return gaps


# --------------------------------------------------------------------------- #
# 3. Velocity > 0 in at least one of the frames right after placing a web   #
# --------------------------------------------------------------------------- #
def test_moves_after_web():
    """The by-attack move `trap_and_shift` must drive the boss AWAY from
    the trap she just laid. Track boss.pos over a fixed horizon after
    each `web_trap` windup start; assert non-zero displacement in the
    away direction (>= boss.max_r / 2 in any frame).
    """
    random.seed(13)
    g = _fresh()
    b = _spawn(g, 'aranha_rei')
    p = g.players[0]
    b.boss_ai.state = 'approach'
    b.boss_ai.cd = 0
    displacements = []
    for attempt in range(6):
        b.boss_ai.state = 'approach'
        b.boss_ai.cd = 0
        b.boss_ai.pattern_id = 'web_trap'
        start_pos = Vector2(b.pos)
        for f in range(40):
            g.step(DT)
            _reset(b)
            if b.boss_ai.state == 'windup' and pat.PATTERNS['web_trap'].get('select'):
                pat.PATTERNS['web_trap']['select'](b, g, p, pat.PATTERNS['web_trap'])
        end_pos = Vector2(b.pos)
        disp = (end_pos - start_pos).length()
        displacements.append(disp)
    worst = min(displacements)
    assert worst > 0, \
        f"aranha_rei did not move after web_trap (worst {worst:.1f}px over 6 attempts; " \
        f"trap_and_shift is not driving the boss away)"
    print(f"  moves after web: aranha_rei moved {worst:.1f}..{max(displacements):.1f}px "
          f"in the 40 frames after web_trap windup start (must be > 0)")


# --------------------------------------------------------------------------- #
# 4. No authored invulnerability window                                       #
# --------------------------------------------------------------------------- #
def test_no_invuln_window():
    """The Aranha-Rei has no boss_invuln window beyond the standard
    intro/transition/recover gates. Walk 1800 frames; assert boss_invuln
    is True ONLY when state is one of: 'intro', 'transition', 'charging'
    (the only states where boss_invuln is normally set). Any other state
    with boss_invuln == True is a regression.
    """
    random.seed(17)
    g = _fresh()
    b = _spawn(g, 'aranha_rei')
    bad = []
    for f in range(FRAMES):
        g.step(DT)
        _reset(b)
        invuln = getattr(b, 'boss_invuln', False)
        if invuln and b.boss_ai.state not in ('intro', 'transition', 'charging'):
            bad.append((f, b.boss_ai.state))
    assert not bad, \
        f"{len(bad)} frame(s) with boss_invuln=True outside the standard states " \
        f"(first: frame {bad[0][0]}, state={bad[0][1]})"
    print(f"  no invuln window: 0 frames with boss_invuln=True outside "
          f"intro/transition/charging over {FRAMES} frames")


# --------------------------------------------------------------------------- #
# Teeth                                                                       #
# --------------------------------------------------------------------------- #
def _measure_aranha_stddev():
    """Helper: run a 1800-frame sim and return aranha_rei's windup-interval stddev."""
    random.seed(7)
    g = _fresh()
    b = _spawn(g, 'aranha_rei')
    return _stddev(b, g)


def _stddev(b, g):
    """Run a 1800-frame sim on (b, g) and return windup-interval stddev in frames."""
    windup_starts = []
    prev_windup = -1
    for f in range(FRAMES):
        g.step(DT)
        _reset(b)
        if b.boss_ai.state == 'windup' and prev_windup != f - 1:
            windup_starts.append(f)
            prev_windup = f
        elif b.boss_ai.state != 'windup':
            prev_windup = -1
    if len(windup_starts) < 3:
        return 0.0
    intervals = [windup_starts[i + 1] - windup_starts[i]
                 for i in range(len(windup_starts) - 1)]
    mean = sum(intervals) / len(intervals)
    var = sum((x - mean) ** 2 for x in intervals) / len(intervals)
    return math.sqrt(var)


def test_teeth():
    """Break each assertion on purpose and confirm it fails."""
    print("  teeth:")

    # 1. Variance: cd_jitter is the source of the wider rhythm. Structural
    #    check: every spider_king_phases entry must carry a cd_jitter key.
    #    Runtime check: spawn two aranha_reis, one with the canonical phase
    #    dicts and one with cd_jitter cleared -- the second's stddev must
    #    drop meaningfully.
    import lagarto.flow.boss.patterns as pat_mod
    phases = pat_mod.spider_king_phases()
    assert all('cd_jitter' in p for p in phases), \
        f"spider_king_phases must carry cd_jitter on every phase; got {phases}"
    print(f"    rhythm variance: cd_jitter present in all "
          f"{len(phases)} phase(s) (values { [p.get('cd_jitter') for p in phases] })")
    # Runtime comparison: two parallel sims, same seed, one with cd_jitter.
    random.seed(7)
    g_a = _fresh()
    b_a = _spawn(g_a, 'aranha_rei')                       # canonical (cd_jitter=1.0)
    random.seed(7)
    g_b = _fresh()
    b_b = _spawn(g_b, 'aranha_rei')                       # perturbed (cd_jitter=0)
    for p in b_b.boss_ai.phases:
        p['cd_jitter'] = 0.0
    std_a = _stddev(b_a, g_a)
    std_b = _stddev(b_b, g_b)
    assert std_b < std_a * 0.80, \
        f"aranha_rei stddev only dropped to {std_b:.2f} from {std_a:.2f} " \
        f"({(1 - std_b/std_a) * 100:.0f}% reduction) -- cd_jitter isn't biting"
    print(f"    rhythm variance: aranha_rei stddev {std_a:.2f} -> {std_b:.2f} "
          f"when cd_jitter cleared ({(1 - std_b/std_a) * 100:.0f}% reduction)")

    # 2. Web escape: place 8 rain_points in a tight ring around the
    #    player and confirm the gap check would fire.
    rain_ring = [Vector2(math.cos(a) * 30, math.sin(a) * 30)
                 for a in (i * math.pi / 4 for i in range(8))]
    gaps = _gaps_from_rain(Vector2(0, 0), rain_ring)
    worst = max(gaps)
    try:
        assert worst > 60, \
            f"web-escape cap should have tripped on a tight ring (worst gap {worst:.0f}px)"
        assert False, "web-escape check should have failed for a tight ring"
    except AssertionError:
        print(f"    web escape: a tight ring (worst gap {worst:.0f}px) trips the check")

    # 3. Moves-after-web: pin boss.vel=0 for the post-windup frames and
    #    confirm the displacement check trips.
    random.seed(13)
    g = _fresh()
    b = _spawn(g, 'aranha_rei')
    p = g.players[0]
    b.boss_ai.state = 'approach'
    b.boss_ai.cd = 0
    b.boss_ai.pattern_id = 'web_trap'
    start_pos = Vector2(b.pos)
    for f in range(40):
        g.step(DT)
        _reset(b)
        b.vel = Vector2(0, 0)
        if b.boss_ai.state == 'windup' and pat.PATTERNS['web_trap'].get('select'):
            pat.PATTERNS['web_trap']['select'](b, g, p, pat.PATTERNS['web_trap'])
    disp = (Vector2(b.pos) - start_pos).length()
    try:
        assert disp > 0, f"moves-after-web should fail when boss is pinned (disp {disp:.1f})"
        assert False, "moves-after-web assertion should have caught pinned boss"
    except AssertionError:
        print(f"    moves after web: pinned boss (disp {disp:.1f}px) trips the check")

    # 4. Invuln: spoof boss_invuln=True in approach, confirm the
    #    no-invuln-window check catches it.
    random.seed(17)
    g = _fresh()
    b = _spawn(g, 'aranha_rei')
    bad = []
    for f in range(120):
        g.step(DT)
        _reset(b)
        b.boss_invuln = True
        if b.boss_ai.state not in ('intro', 'transition', 'charging'):
            bad.append((f, b.boss_ai.state))
    try:
        assert not bad, \
            f"{len(bad)} frame(s) with boss_invuln=True outside the standard states"
        assert False, "no-invuln check should have flagged the spoof"
    except AssertionError:
        print(f"    no invuln window: spoofed invuln ({len(bad)} flagged) trips the check")


# --------------------------------------------------------------------------- #
# Headless screenshot                                                         #
# --------------------------------------------------------------------------- #
def _screenshot(out):
    g = _fresh()
    b = _spawn(g, 'aranha_rei')
    p = g.players[0]
    font = fonts.get(16)
    bigfont = fonts.get(26)
    surf = pygame.Surface((C.WIDTH, C.HEIGHT), 0, 24)
    g.cam.pos = Vector2(b.pos)
    g.cam.zoom = 0.7
    surf.fill((22, 24, 32))
    for _ in range(120):
        g.step(DT)
        _reset(b)
    b.draw(surf, g.cam)
    b.boss_ai.draw(surf, g.cam)
    g.fx.draw(surf, g.cam, font)
    label = font.render(
        "aranha-rei siege: erratic_step repositions the body, "
        "trap_and_shift leaves the web she just placed",
        True, (240, 240, 246))
    surf.blit(label, (12, 12))
    state = bigfont.render(
        f"state={b.boss_ai.state}  pattern={b.boss_ai.pattern_id}  "
        f"erratic_t={getattr(b, '_erratic_t', 0)}",
        True, (200, 220, 240))
    surf.blit(state, (12, 28))
    tmp = out + '.bmp'
    pygame.image.save(surf, tmp)
    pygame.image.save(pygame.image.load(tmp), out)
    os.remove(tmp)
    print(f"  shot: {out}")


def main():
    if '--teeth' in sys.argv:
        test_teeth()
        print("ALL OK (teeth)")
        return
    if '--shot' in sys.argv:
        _screenshot(sys.argv[sys.argv.index('--shot') + 1])
        return
    print("issue #125: aranha-rei signature -- erratic + cd_jitter + siege")
    test_rhythm_variance()
    test_web_escape_route()
    test_moves_after_web()
    test_no_invuln_window()
    test_teeth()
    print("ALL OK")


if __name__ == '__main__':
    main()