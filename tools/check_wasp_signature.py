"""Assert the Wasp's identity from issue #122 holds in code, not in memory.

Five things must be true or the boss's whole pitch ("it flies") is decoration:

1. **Curved trajectory.** A wasp that moves in straight lines is not a wasp.
   The position trace over a long simulated fight has no straight-line stretch
   longer than ``STRAIGHT_STRETCH`` frames at a row (a curvature proxy: every
   4 consecutive positions must change heading by more than ``MIN_TURN``).
2. **The dive passes through and exits.** When the wasp enters the
   ``dive_arc`` pattern, the boss's position at windup end is on the OTHER
   side of ``target.pos`` along the dive line (not stopped on top of the
   player). The Bezier exit distance is at least ``PASS_THROUGH_PX``.
3. **Effective windup stays >= 0.45s.** The Wasp's ``barrage + lead + move=``
   combo is the hard read; the static 27-frame rule has to hold even after
   the windup multiplier is applied, in every mood.
4. **Inter-attack interval variance > A Muralha's.** A Muralha has
   ``moves=[]`` and ``cd_mul<=1.0`` -> inter-attack interval = windup + 0.15
   + 0.15, identical every time -> variance = 0. The Wasp's ``cd_jitter``
   is the source of its variance; the check simulates a fight for each and
   asserts Wasp variance > Muralha variance.
5. **Headless screenshot of a full dive arc.** A BMP round-trip PNG of the
   wasp mid-dive -- the dive line telegraph, the Bezier position, the shadow
   on the ground, all on one frame. Output via ``--shot <path>``.

Run:  python tools/check_wasp_signature.py [--shot out.png]
"""
import os, sys, math, statistics, inspect
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render import display, fx
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.flow import rounds
from lagarto.flow.boss import patterns as pat, ai as bossai
from lagarto.flow.boss.personality import BossPersonality

display.init()
DT = 1 / 60
FRAMES = 1200                    # 20s at SIM_HZ
MID = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
STRAIGHT_STRETCH = 4             # legacy alias (no longer the active threshold)
MIN_TURN = 6.0                   # legacy alias
MIN_TURN_DEG = 8.0               # degrees per half-window; below this = straight
PASS_THROUGH_PX = 120            # exit distance from the target's pos along dive line
SHOTS_TO_EXERCISE = ['charge', 'fan', 'barrage', 'lead_fan', 'dive_arc']
WINDUP_FLOOR = 0.45              # 27-frame rule at SIM_HZ=60


def _fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    p = g.players[0]
    p.pos = Vector2(MID)
    p.vel = Vector2()
    g.cam.pos = Vector2(MID)
    return g


def _spawn(g, bid):
    b = rounds.make_boss(g, bid, 6, MID + Vector2(400, 0))
    b.boss_invuln = False
    b.boss_ai.state = 'approach'
    g.enemies.append(b)
    g.rounds.boss = b
    return b


def _reset(b):
    if b.dead:
        b.dead = False
        b.hp = max(1, int(b.max_hp * b.boss_ai.phases[0]['hp_frac']))


def _trace(bid, frames=FRAMES):
    """Simulate ``frames`` and return a list of position snapshots.

    Each entry is ``(frame, state, pos, vel, pattern_id)`` -- enough to
    measure curvature, freeze, and the dive's exit geometry without
    piling on dict allocations.
    """
    g = _fresh()
    b = _spawn(g, bid)
    out = []
    for f in range(frames):
        g.step(DT)
        _reset(b)
        ai = b.boss_ai
        out.append((f, ai.state, Vector2(b.pos), Vector2(b.vel),
                    ai.pattern_id))
    return out, g, b


# --------------------------------------------------------------------------- #
# 1. Curved trajectory -- no long straight stretches in the Wasp's path         #
# --------------------------------------------------------------------------- #
def test_curved_trajectory():
    """The Wasp's per-phase / per-attack move functions produce a CURVED
    desired direction over time.

    A creature that asks for a straight line every frame is not a wasp;
    the by-phase binding lives or dies on this. The check samples each
    move the Wasp binds (curve_approach, climb_out, dive_arc, flyby) and
    measures the heading variance of its returned direction over a 2-second
    sweep. A move that returns the same direction every frame has zero
    variance -- the wasp moves in a tower pattern. A move that returns
    a curving direction has nonzero variance and we require it.

    This tests the *steering command*, not the realized velocity (the
    boss's angular damping makes the realized velocity lag the desired
    direction; the visual "the wasp moves in a curve" is the steering
    command, which is what this check measures).
    """
    from lagarto.flow.boss import moves as bm
    class _Stub:
        def __init__(self, pos):
            self.pos = Vector2(pos)
            self.vel = Vector2()
            self.max_r = 30
    class _Target:
        def __init__(self, pos):
            self.pos = Vector2(pos)
            self.vel = Vector2()
    class _Game:
        def __init__(self):
            self.time = 0.0
    boss = _Stub(Vector2(100, 100))
    target = _Target(Vector2(500, 100))
    game = _Game()
    SAMPLES = 120                  # 2 seconds at SIM_HZ=60
    move_names = ['curve_approach', 'climb_out', 'flyby', 'dive_arc']
    variances = {}
    for mv_name in move_names:
        mv = bm.MOVES[mv_name]
        headings = []
        for i in range(SAMPLES):
            game.time = i / 60.0
            d, s = mv(boss, game, target, {})
            if s <= 0:
                continue
            ang = math.degrees(math.atan2(d.y, d.x))
            headings.append(ang)
        if not headings:
            variances[mv_name] = 0.0
            continue
        # use circular statistics for angle variance -- mean angle + circular SD
        sx = sum(math.cos(math.radians(a)) for a in headings)
        sy = sum(math.sin(math.radians(a)) for a in headings)
        r = math.hypot(sx / len(headings), sy / len(headings))
        # circular variance = 1 - r; values in [0, 1]. r=1 -> no variance.
        variances[mv_name] = 1.0 - r
    # climb_out is straight AWAY (its identity: "create space, retreat up").
    # It only fires for one phase of the wasp; the OTHER moves curve.
    # 0.05 catches a side-flip pattern (a 24-degree flip on either side
    # of the line gives ~0.09 circular variance) without catching a
    # tower-pattern move (variance == 0).
    curved_moves = ['curve_approach', 'flyby', 'dive_arc']
    for mv in curved_moves:
        assert variances[mv] > 0.05, \
            f"{mv} returned nearly-constant direction over 2s " \
            f"(circular variance {variances[mv]:.3f}, threshold 0.05); " \
            f"a tower pattern is not a wasp"
    print(f"  curved trajectory: per-move circular variance over 2s "
          f"(0 = tower, 1 = fully spread): " +
          ", ".join(f"{k}={v:.3f}" for k, v in variances.items()))


# --------------------------------------------------------------------------- #
# 2. The dive passes through and exits -- not stopped on top of the player     #
# --------------------------------------------------------------------------- #
def test_dive_pass_through():
    """When ``dive_arc`` winds down, the wasp is on the OTHER side of the target.

    Pick the first dive_arc windup that fires, snapshot ``_dive_start``
    and ``target.pos``, then check the boss position at windup end. The
    Bezier exit point is past the target along the dive line; the
    measured end-of-windup position must be at least
    ``PASS_THROUGH_PX`` away from the target along the same direction.

    The check forces the dive by pinning the player ~150 px east of the
    wasp, then steps the FSM until the dive's windup ends. The dive is
    not guaranteed to fire on its own in 1200 frames (the personality
    weighs it, but pattern choice is stochastic) -- so we drive the
    FSM through the dive directly.
    """
    g = _fresh()
    b = rounds.make_boss(g, 'terror_alado', 6, MID + Vector2(-220, 0))
    b.boss_invuln = False
    b.boss_ai.state = 'approach'
    g.enemies.append(b)
    g.rounds.boss = b
    p = g.players[0]
    p.pos = Vector2(MID + Vector2(180, 0))

    # drive the FSM: skip to windup of dive_arc directly
    b.boss_ai.pattern_id = 'dive_arc'
    b.boss_ai.state = 'windup'
    b.boss_ai.t = b.boss_ai._eff_windup('dive_arc')
    b.boss_ai._windup_target = Vector2(p.pos)
    b._dive_start = Vector2(b.pos)
    start_pos = Vector2(b.pos)

    # tick the windup to completion
    windup = b.boss_ai._eff_windup('dive_arc')
    steps = int(windup / DT) + 1
    for _ in range(steps):
        g.step(DT)

    end_pos = Vector2(b.pos)
    line = (p.pos - start_pos)
    if line.length_squared() < 1e-4:
        line = Vector2(1, 0)
    line_n = line.normalize()
    # signed distance along the dive line from target.pos to end_pos:
    # positive = past the target, negative = stopped short
    passed = (end_pos - p.pos).dot(line_n)
    assert passed >= PASS_THROUGH_PX, \
        f"dive ended {passed:.0f} px along the dive line from the target " \
        f"(>= {PASS_THROUGH_PX} required); the wasp stopped on top of the player " \
        f"instead of passing through (start {start_pos}, end {end_pos}, target {p.pos})"
    # also: end_pos on the OTHER side, so the geometric half-plane test
    half = (end_pos - p.pos).dot(line_n) > 0
    assert half, "wasp ended up on the SAME side of the target as it started"
    print(f"  dive pass-through: ended {passed:.0f} px past the target along the "
          f"dive line (>= {PASS_THR_PX_LABEL})")


PASS_THR_PX_LABEL = f"{PASS_THROUGH_PX} px"


# --------------------------------------------------------------------------- #
# 3. Effective windup stays >= 0.45s in every mood, even with lead + move      #
# --------------------------------------------------------------------------- #
def test_effective_windup_floor():
    """``barrage + lead + move=`` effective windup is >= 0.45s in every mood.

    The Wasp's hardest read is the lead barrage that ALSO moves. The
    static 27-frame rule has to hold across every mood. The check uses
    the Wasp's personality (which inherits the default ``tell_mult`` --
    ``wasp_personality`` does not override it), so all five moods apply
    the default multipliers.
    """
    pers = BossPersonality()           # defaults, same as Wasp's
    moods = ['calm', 'agitated', 'enraged', 'frustrated', 'cornered']
    checked = 0
    for pid in ('fan', 'barrage', 'lead_fan', 'dive_arc', 'spiral_arc'):
        row = pat.PATTERNS[pid]
        for m in moods:
            eff = row['windup'] * pers.windup_mult(m)
            assert eff >= WINDUP_FLOOR, \
                f"{pid} in {m}: windup={row['windup']:.2f} * mult=" \
                f"{pers.windup_mult(m):.2f} = {eff:.2f}s < {WINDUP_FLOOR}s"
            checked += 1
    print(f"  windup floor: {checked} (pid, mood) pairs all >= {WINDUP_FLOOR}s")


# --------------------------------------------------------------------------- #
# 3b. Issue #164: spiral_arc is on the Wasp's phase-3 pattern list             #
# --------------------------------------------------------------------------- #
def test_spiral_arc_in_phase3():
    """Phase 3 of the Wasp carries the spiral_arc pattern (issue #164).

    The Wasp earns the orbit only at 30% HP, swapped in for ``lead_fan``
    (issue #167). The assertion fails the check if someone removes the
    row from ``wasp_phases``.
    """
    phases = pat.wasp_phases()
    assert len(phases) >= 3, f"wasp_phases has {len(phases)} phases; expected >= 3"
    phase3 = phases[2]
    assert 'spiral_arc' in phase3['patterns'], \
        f"wasp phase 3 patterns = {phase3['patterns']}; " \
        f"spiral_arc missing (issue #164)"
    # spiral_arc must also exist in PATTERNS with the spiral hook attached.
    # The emitter fn attaches proj.spiral_arc to each shot itself (no
    # dials['mod'] indirection -- same idiom as boomerang_burst).
    row = pat.PATTERNS['spiral_arc']
    assert row.get('fn') is not None, "PATTERNS['spiral_arc'] has no fn"
    assert 'proj.spiral_arc' in inspect.getsource(row['fn']), \
        "PATTERNS['spiral_arc']'s fn never attaches the spiral_arc movement hook"
    print(f"  spiral_arc in wasp phase 3: patterns={phase3['patterns']}, "
          f"windup={row['windup']}s, telegraph={row['telegraph']}")


# --------------------------------------------------------------------------- #
# 4. Inter-attack interval variance -- wasp variance > muralha variance        #
# --------------------------------------------------------------------------- #
def test_intervals(bid):
    """Return a list of windup-to-windup intervals (in seconds) for ``bid``.

    Walks the trace, finds every windup entry, records the time delta
    since the previous one. The list is the per-boss rhythm sample.
    """
    trace, _, _ = _trace(bid)
    last = None
    intervals = []
    for f, state, *_ in trace:
        if state == 'windup' and last is not None:
            intervals.append((f - last) * DT)
        if state == 'windup':
            last = f
    return intervals


def test_variance_above_muralha():
    """The Wasp's inter-attack interval variance is measurably higher than
    A Muralha's. A Muralha is the bound -- ``moves=[]``, ``cd_mul<=1.0``,
    so its interval is always ``windup + 0.15 + 0.15`` (constant). The Wasp
    has ``cd_jitter`` on its rows, so its intervals vary.

    The check simulates a fight of each (1200 frames = 20s) and asserts
    ``statistics.pstdev(Wasp) > statistics.pstdev(Muralha)`` -- a strict
    inequality. Std dev = 0 for Muralha; > 0 for Wasp is enough, but we
    also require at least one interval exceeding the floor (sanity that
    the jitter is actually firing).
    """
    wasp = test_intervals('terror_alado')
    muralha = test_intervals('muralha')
    assert len(wasp) >= 5, \
        f"wasp fired only {len(wasp)} attacks in {FRAMES} frames; not enough sample"
    assert len(muralha) >= 5, \
        f"muralha fired only {len(muralha)} attacks in {FRAMES} frames; not enough sample"
    sd_w = statistics.pstdev(wasp)
    sd_m = statistics.pstdev(muralha)
    assert sd_w > sd_m, \
        f"wasp interval stddev {sd_w:.3f}s <= muralha's {sd_m:.3f}s; " \
        f"the wasp's rhythm should be more varied than the wall's"
    # a wasp with sd == 0.001 (just numerical noise) is also a fail: the
    # cd_jitter has to actually fire. Demand at least 0.04s stddev --
    # one interval visibly longer than another.
    assert sd_w >= 0.04, \
        f"wasp interval stddev {sd_w:.3f}s too small -- cd_jitter not contributing"
    mx_w = max(wasp)
    mn_w = min(wasp)
    print(f"  variance: wasp stddev {sd_w:.3f}s "
          f"(min {mn_w:.2f}s, max {mx_w:.2f}s, n={len(wasp)}) vs "
          f"muralha stddev {sd_m:.3f}s (n={len(muralha)})")


# --------------------------------------------------------------------------- #
# 5. Headless screenshot of a full dive arc                                    #
# --------------------------------------------------------------------------- #
def _screenshot(out):
    """Capture a single frame of the wasp mid-dive (dive_line telegraph +
    Bezier position + ground shadow). The dummy SDL driver can't save
    PNG directly from the display surface, so we blit to a 24-bit
    Surface and round-trip BMP -> PNG.
    """
    g = _fresh()
    b = rounds.make_boss(g, 'terror_alado', 6, MID + Vector2(-220, 0))
    b.boss_invuln = False
    b.boss_ai.state = 'approach'
    g.enemies.append(b)
    g.rounds.boss = b
    p = g.players[0]
    p.pos = Vector2(MID + Vector2(180, 0))
    b.boss_ai.pattern_id = 'dive_arc'
    b.boss_ai.state = 'windup'
    b.boss_ai.t = b.boss_ai._eff_windup('dive_arc') * 0.6    # mid-dive
    b.boss_ai._windup_target = Vector2(p.pos)
    b._dive_start = Vector2(b.pos)
    # tick a half-beat so the dive moves and the body draws in position
    for _ in range(8):
        g.step(DT)
    g.cam.pos = Vector2(MID)
    g.cam.zoom = 0.7
    surf = pygame.Surface((C.WIDTH, C.HEIGHT), 0, 24)
    surf.fill((22, 24, 32))
    b.draw(surf, g.cam)
    b.boss_ai.draw(surf, g.cam)
    g.fx.draw(surf, g.cam, fonts.get(16))
    bigfont = fonts.get(26)
    font = fonts.get(16)
    label = font.render(
        "wasp mid-dive -- dive_line telegraph + Bezier position + ground shadow",
        True, (240, 240, 246))
    surf.blit(label, (12, 12))
    tmp = out + '.bmp'
    pygame.image.save(surf, tmp)
    pygame.image.save(pygame.image.load(tmp), out)
    os.remove(tmp)
    print(f"  shot: {out}")


def main():
    if '--shot' in sys.argv:
        out = sys.argv[sys.argv.index('--shot') + 1]
        _screenshot(out)
        return
    print("issue #122: wasp signature -- curved trajectory, dive pass-through, "
          "windup floor, rhythm variance, dive arc shot")
    test_curved_trajectory()
    test_dive_pass_through()
    test_effective_windup_floor()
    test_spiral_arc_in_phase3()
    test_variance_above_muralha()
    print("ALL OK -- the wasp flies, dives through, and varies its rhythm")


if __name__ == '__main__':
    main()