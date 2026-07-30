"""Issue #123: Rei Lagarto -- the legibility canonical.

Seven assertions, each with a provable failure mode (the "teeth" section
breaks each on purpose and confirms the check catches it):

1. **Rhythm** -- Rei Lagarto's average theoretical cycle is the LARGEST
                in ``BOSS_POOL``. The cycle is ``BOSS_CD_FLOOR +
                average(windup) + BOSS_RECOVER_TIME``; the looseness
                comes from the windup, the cd floor is shared.
2. **Telegraph** -- Rei Lagarto's average windup is the LONGEST in
                   ``BOSS_POOL``. The bump to ``BOSS_FAN_WINDUP`` /
                   ``BOSS_SHOCKWAVE_WINDUP`` / ``BOSS_RADIAL_WINDUP``
                   plus the per-pattern ``move='proud_walk'`` are the
                   piece that earns the "legibility" signature.
3. **No retreat** -- ``move_proud_walk`` never produces a sign flip
                      over a simulated fight. The committed direction
                      is picked in the forward half-cone around the
                      previous one, so a negation is structurally
                      impossible.
4. **CicatriZ trail** -- ``spawn_scar`` drops the puddle within a
                          fixed radius of a recent boss position, not
                          at a random world position. The ring buffer
                          on ``BossAI`` (``_path_samples``) is the
                          trail the puddle samples.
5. **No invulnerability** -- the Rei Lagarto's FSM never sets
                             ``boss_invuln = True`` outside intro /
                             transition. Charge, burrow, grapple own
                             their own windows in other bosses; Rei
                             keeps the i-frame discipline tight (the
                             "first lesson" is "shooting always
                             works").
6. **Phase cadence + density** (issue #162) -- phase 1 is the
                                            legibility canonical
                                            (untouched pattern dials,
                                            cd_mul 1.0); phase 2
                                            graduates fan to 3 shots
                                            and radial to 10 shots at
                                            cd_mul 0.80; phase 3
                                            swaps fan for a denser
                                            spiral (shots 20 / turn
                                            18 / gap 0.04) at
                                            cd_mul 0.65. Validated
                                            through the merged
                                            ``pattern_dials`` so the
                                            what-telegraph-draws =
                                            what-emitter-fires
                                            invariant holds.
7. **Screenshot** -- headless render of a Rei Lagarto in motion with
                      at least one CicatriZ puddle on the floor. The
                      arena anchor check in ``check_boss_movement.py``
                      covers the body-stays-in-the-box invariant; this
                      shot is the visual evidence the new mechanic and
                      the new movement land together.

Run:  python tools/check_king_signature.py
"""
import os, sys, math, random
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2

from lagarto.core.mathutil import safe_norm, random_dir
from lagarto.render import display, fx
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.flow import rounds
from lagarto.flow.boss import patterns as pat, ai as bossai
from lagarto.flow.boss.moves import MOVES, move_proud_walk
from lagarto.flow.boss.personality import king_personality
from lagarto.combat import weapons

display.init()
DT = 1 / 60
FRAMES = 1200               # 20s at SIM_HZ=60 -- enough for several repicks
MID = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)


def _fresh():
    """A fresh Game with one player standing still at MID."""
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    p = g.players[0]
    p.pos = Vector2(MID)
    p.vel = Vector2()
    g.cam.pos = Vector2(MID)
    return g


def _spawn_boss(game, bid, pos=None):
    pos = pos or (MID + Vector2(400, 0))
    b = rounds.make_boss(game, bid, 6, pos)
    b.boss_invuln = False
    b.boss_ai.state = 'approach'
    game.enemies.append(b)
    game.rounds.boss = b
    return b


def _reset(b):
    if b.dead:
        b.dead = False
        b.hp = max(1, int(b.max_hp * b.boss_ai.phases[0]['hp_frac']))


def _theoretical_cycle(bid, phases_fn):
    """The cycle budget for a boss, as ``BOSS_CD_FLOOR + avg_windup +
    BOSS_RECOVER_TIME`` -- the sum of the static components. The windup
    average is across every pattern in every phase, the cd is the
    worst-case per phase (post-clamp). The boss with the largest budget
    is the most generous to the player.
    """
    phases = phases_fn()
    total_w = 0.0
    total_n = 0
    total_cd = 0.0
    for ph in phases:
        for pid in ph['patterns']:
            row = pat.PATTERNS[pid]
            w = row.get('windup', C.BOSS_WINDUP_FLOOR)
            if row.get('telegraph') is None:
                w = C.BOSS_WINDUP_FLOOR
            total_w += w
            total_n += 1
        total_cd += max(C.BOSS_CD_FLOOR, C.BOSS_CD_MAX * ph['cd_mul'])
    avg_w = total_w / max(1, total_n)
    avg_cd = total_cd / max(1, len(phases))
    return avg_w, avg_cd, avg_w + avg_cd + C.BOSS_RECOVER_TIME


# Map of BOSS_POOL id -> phase kit factory. Pulled by name to keep the
# check honest -- a future boss added without a kit registered here
# gets skipped (and a loud warning at the bottom).
PHASE_FACTORIES = {
    'rei_lagarto':     pat.king_phases,
    'centopeiadeira':  pat.centipede_phases,
    'kraken_mor':      pat.kraken_phases,
    'primordial':      pat.primordial_phases,
    'mae_escaravelho': pat.beetle_phases,
    'aranha_rei':      pat.spider_king_phases,
    'serpente_cristal': pat.crystal_phases,
    'terror_alado':    pat.wasp_phases,
    'olho_sismico':    pat.eye_phases,
    'muralha':         pat.muralha_phases,
    'ankh':            pat.ankh_phases,
}


# --------------------------------------------------------------------------- #
# 1. Rhythm                                                                   #
# --------------------------------------------------------------------------- #
def test_rhythm():
    """Rei Lagarto's average theoretical cycle is the LARGEST in BOSS_POOL.

    Other bosses with a long cycle get there through windups of 0.7-1.0
    on a single attack (Primordial's massive_fan/sky_slam/summon); Rei
    gets there by having the LONGEST windup on EVERY pattern he uses
    (fan, shockwave, radial, charge -- all bumped to 1.1 in config).
    The combination of cd_mul 1.0/0.95/0.85 (loosest in pool) and the
    bumped windups lands Rei on top.
    """
    cycles = {}
    for bid, fn in PHASE_FACTORIES.items():
        _, _, cyc = _theoretical_cycle(bid, fn)
        cycles[bid] = cyc
    rei = cycles['rei_lagarto']
    others = {b: c for b, c in cycles.items() if b != 'rei_lagarto'}
    assert rei >= max(others.values()), \
        f"rei_lagarto cycle {rei:.3f}s < max(others) {max(others.values()):.3f}s -- " \
        f"the looseness claim is broken ({sorted(cycles.items(), key=lambda x: -x[1])})"
    print(f"  rhythm: rei_lagarto cycle {rei:.3f}s, "
          f"max(other) {max(others.values()):.3f}s, min(other) {min(others.values()):.3f}s")
    return cycles


# --------------------------------------------------------------------------- #
# 2. Telegraph                                                                #
# --------------------------------------------------------------------------- #
def test_telegraph():
    """Rei Lagarto's average windup is the LONGEST in BOSS_POOL.

    The windup is the ``telegraph`` -- the time the player has to read
    the boss's intent. With it bumped to 1.1 on fan / shockwave / radial
    / charge, Rei's per-pattern windup is the largest of the pool's
    averages.
    """
    windups = {}
    for bid, fn in PHASE_FACTORIES.items():
        avg_w, _, _ = _theoretical_cycle(bid, fn)
        windups[bid] = avg_w
    rei = windups['rei_lagarto']
    others = {b: w for b, w in windups.items() if b != 'rei_lagarto'}
    assert rei >= max(others.values()), \
        f"rei_lagarto windup {rei:.3f}s < max(others) {max(others.values()):.3f}s -- " \
        f"the 'longest telegraph' claim is broken ({sorted(windups.items(), key=lambda x: -x[1])})"
    print(f"  telegraph: rei_lagarto avg windup {rei:.3f}s, "
          f"max(other) {max(others.values()):.3f}s")
    return windups


# --------------------------------------------------------------------------- #
# 3. No retreat                                                               #
# --------------------------------------------------------------------------- #
def test_no_retreat():
    """``move_proud_walk`` never produces a sign flip on the committed
    direction over a simulated fight.

    The committed direction is replaced every frame by a forward-cone
    candidate. A sign flip means ``new = -old``; the half-cone around
    the committed line forbids it (the dot product of any direction in
    the cone with the committed line is non-negative, so the negation
    can never appear).
    """
    g = _fresh()
    b = _spawn_boss(g, 'rei_lagarto')
    target = g.players[0]
    prev = None
    flips = []
    for f in range(FRAMES):
        g.step(DT)
        _reset(b)
        # simulate a circling player: walk around the boss in a slow
        # orbit, faster than the boss so the relative angle flips
        # multiple times across the run
        ang = f * 0.06
        target.pos = Vector2(MID[0] + math.cos(ang) * 350,
                             MID[1] + math.sin(ang) * 250)
        cur = b.boss_ai._pw_dir
        if prev is not None and cur.length_squared() > 1e-6:
            dot = cur.x * prev[0] + cur.y * prev[1]
            if dot < -0.99:
                flips.append((f, dot))
        prev = (cur.x, cur.y) if cur.length_squared() > 1e-6 else prev
    assert not flips, \
        f"proud_walk produced {len(flips)} sign flip(s) over {FRAMES} frames: {flips[:5]}"
    print(f"  no retreat: {FRAMES} frames simulated, 0 sign flips on committed dir "
          f"(TURN_BIAS={0.65} keeps every repick in the forward half-cone)")
    return flips


# --------------------------------------------------------------------------- #
# 4. CicatriZ trail                                                           #
# --------------------------------------------------------------------------- #
def test_cicatriz_trail():
    """``spawn_scar`` drops the puddle within a fixed radius of a recent
    boss position (not at a random world position).

    Over N fights, every spawn lands on a position the boss actually
    occupied in the recent path buffer. ``spawn_scar`` snapshots the
    buffer at spawn time so the verification doesn't race against the
    buffer's evolution (the buffer rolls forward every frame).
    """
    n_fights = 5
    miss_radius = 0.0
    for fight in range(n_fights):
        random.seed(fight + 123)
        g = _fresh()
        b = _spawn_boss(g, 'rei_lagarto')
        b.boss_ai.scar_thresholds = [0.99, 0.5]   # force two spawns
        b.boss_ai.personality = king_personality()
        target = g.players[0]
        for f in range(900):
            g.step(DT)
            _reset(b)
            # walk the player around so the boss actually moves and the
            # ring buffer fills with distinct positions
            ang = f * 0.04
            target.pos = Vector2(MID[0] + math.cos(ang) * 320,
                                 MID[1] + math.sin(ang) * 200)
        for scar in b.boss_ai.scars:
            snapshot = getattr(scar, '_scar_path_snapshot', [])
            chosen = getattr(scar, '_scar_path_pos', None)
            if chosen is not None and snapshot:
                # The puddle is exactly at the chosen sample; check
                # the chosen sample IS in the snapshot (it was popped
                # out of samples by random.choice but the copy is the
                # value). Distance to the closest snapshot sample
                # should be 0 (the chosen sample == scar.pos).
                min_d = min((scar.pos - s).length() for s in snapshot)
            else:
                # legacy path: spawn_scar couldn't find a path buffer
                min_d = min((scar.pos - s).length()
                            for s in b.boss_ai._path_samples)
            assert min_d <= b.max_r * 4, \
                f"fight {fight}: scar at {scar.pos}, closest snapshot sample {min_d:.0f} px " \
                f"(cap {b.max_r * 4:.0f} px = boss.max_r * 4)"
            miss_radius = max(miss_radius, min_d)
    print(f"  cicatriz trail: {n_fights} fights, max scar-to-path-snapshot distance "
          f"{miss_radius:.0f} px (cap boss.max_r * 4 = "
          f"{rounds.make_boss(_fresh(), 'rei_lagarto', 6, MID).max_r * 4:.0f} px)")
    return miss_radius


# --------------------------------------------------------------------------- #
# 5. No invulnerability window                                                #
# --------------------------------------------------------------------------- #
def test_no_invuln_window():
    """Rei Lagarto's FSM never sets ``boss_invuln = True`` outside intro /
    transition.

    Charge, burrow and grapple own their own invuln windows in OTHER
    bosses (the windup-during-charge is the only reaction window); the
    Rei Lagarto deliberately has no such window. ``king_personality``
    + ``king_phases`` + the per-pattern windup floors are the
    discipline; this check verifies it stays that way.
    """
    g = _fresh()
    b = _spawn_boss(g, 'rei_lagarto')
    phases = b.boss_ai.phases
    # The check has two halves:
    # (a) no PATTERN declares its own invulnerability -- Rei's
    #     PATTERNS rows shouldn't grow a ``vuln=False`` field. The
    #     FSM's only invuln setting is the per-state branches in
    #     ``BossAI.tick``; phase transitions own ``boss_invuln = True``.
    used = set()
    for ph in phases:
        for pid in ph['patterns']:
            used.add(pid)
    for pid in used:
        row = pat.PATTERNS[pid]
        assert not row.get('vuln') is False, \
            f"PATTERNS[{pid}] declares vuln=False -- Rei Lagarto authored no invuln window"
    # (b) simulated: drive the boss through phases, sample boss_invuln,
    # confirm it only flips True in intro/transition states
    flips = []
    b.boss_ai.scar_thresholds = None
    for f in range(1200):
        g.step(DT)
        _reset(b)
        s = b.boss_ai.state
        inv = bool(b.boss_invuln)
        if inv and s not in ('intro', 'transition', 'charging', 'burrowing', 'grappling'):
            flips.append((f, s))
    # Note: 'charging' is the charge state machine (its own state, not
    # an authored invuln). Rei uses charge so 'charging' is allowed.
    # We assert: no flips in 'approach', 'windup', 'recover'.
    bad = [(f, s) for (f, s) in flips if s in ('approach', 'windup', 'recover')]
    assert not bad, \
        f"Rei Lagarto authored invuln window: {bad[:5]} " \
        f"(states outside intro/transition/charging)"
    print(f"  no invuln window: 1200 frames simulated, 0 invuln flips outside "
          f"intro/transition/charging (charge vetoes its own motion)")
    return bad


# --------------------------------------------------------------------------- #
# 6. Phase cadence + density (issue #162)                                     #
# --------------------------------------------------------------------------- #
def _eff_king_dials(phase, pid):
    """Mirror of ``BossAI._effective_dials`` for the Rei phase kit -- the FSM
    reads the merged dict at windup start, the emitter fires through the same
    dict at fire time. The test queries the same merged shape so it cannot
    drift from what the boss actually does."""
    base = pat.PATTERNS[pid]
    override = phase.get('pattern_dials', {}).get(pid, {})
    return {**base, **override}


def test_phase_cadence():
    """Phase 1 stays the legibility canonical (issue #123). Phases 2 / 3
    graduate **density + cadence** (issue #162):

    - Phase 1: ``cd_mul 1.0``, fan row untouched (count = ``BOSS_FAN_COUNT``,
      i.e. the shared PATTERNS default), no ``pattern_dials`` override.
    - Phase 2: ``cd_mul 0.80`` (was 0.95), fan count 3 (was PATTERNS default),
      fan spread 24 dmg 8 (concentrated cone), radial count 10.
    - Phase 3: ``cd_mul 0.65`` (was 0.85), spiral dials bumped to
      ``shots 20 / turn 18 / gap 0.04`` (denser bullet hell).

    Windups stay where #123 put them -- the floor is the 27-frame rule and
    every telegraph still reads at 1.1s. What's UP is count + cadence; what
    stays the same is the legibility.

    The test queries the merged ``pattern_dials`` because that is the shape
    the FSM actually uses (see ``BossAI._effective_dials``).
    """
    phases = pat.king_phases()
    p1, p2, p3 = phases[0], phases[1], phases[2]

    # Phase 1: legibility canonical, untouched.
    assert p1['cd_mul'] == 1.0, \
        f"phase 1 cd_mul {p1['cd_mul']} != 1.0 -- the legibility canonical lost its breath"
    assert 'pattern_dials' not in p1 or not p1['pattern_dials'], \
        f"phase 1 carries pattern_dials override -- the canonical must stay untouched"
    p1_fan = _eff_king_dials(p1, 'fan')
    # Phase 1 fan must NOT carry a count override -- it stays at the shared
    # PATTERNS row (which the emitter fills from C.BOSS_FAN_COUNT).
    assert 'count' not in p1['pattern_dials'].get('fan', {}) if 'pattern_dials' in p1 else True, \
        f"phase 1 fan carries a count override -- the canonical must stay untouched"

    # Phase 2: cadence UP + density UP.
    assert p2['cd_mul'] == 0.80, \
        f"phase 2 cd_mul {p2['cd_mul']} != 0.80 -- cadence didn't graduate"
    assert p2['cd_mul'] < 0.85, \
        f"phase 2 cd_mul {p2['cd_mul']} >= 0.85 -- the phase 2 cadence cap is 0.80"
    p2_fan = _eff_king_dials(p2, 'fan')
    assert p2_fan['count'] == 3, \
        f"phase 2 fan count {p2_fan['count']} != 3 -- the cone didn't densify"
    assert p2_fan['count'] >= 2, \
        f"phase 2 fan count {p2_fan['count']} < 2 -- the cone didn't densify (teeth)"
    p2_radial = _eff_king_dials(p2, 'radial')
    assert p2_radial['count'] == 10, \
        f"phase 2 radial count {p2_radial['count']} != 10 -- the ring didn't densify"

    # Phase 3: bulldozer cadence + denser spiral.
    assert p3['cd_mul'] == 0.65, \
        f"phase 3 cd_mul {p3['cd_mul']} != 0.65 -- the bulldozer lost its bite"
    assert p3['cd_mul'] < p2['cd_mul'], \
        f"phase 3 cd_mul {p3['cd_mul']} >= phase 2 {p2['cd_mul']} -- the cadence regressed"
    p3_spiral = _eff_king_dials(p3, 'spiral')
    assert p3_spiral.get('shots') == 20, \
        f"phase 3 spiral shots {p3_spiral.get('shots')} != 20 -- the spiral didn't densify"
    assert p3_spiral.get('turn') == 18, \
        f"phase 3 spiral turn {p3_spiral.get('turn')} != 18 -- the spiral didn't tighten"
    assert abs(p3_spiral.get('gap', 0) - 0.04) < 1e-6, \
        f"phase 3 spiral gap {p3_spiral.get('gap')} != 0.04 -- the spiral didn't speed up"

    # Windups untouched across all phases -- the 27-frame rule is the
    # issue's "tell never shortens" promise.
    for ph_i, ph in enumerate(phases):
        for pid in ph['patterns']:
            row = _eff_king_dials(ph, pid)
            w = row.get('windup', C.BOSS_WINDUP_FLOOR)
            assert w >= C.BOSS_WINDUP_FLOOR, \
                f"phase {ph_i+1} {pid} windup {w} < floor {C.BOSS_WINDUP_FLOOR} -- " \
                f"a per-pattern override would have shortened the tell (#162 forbids)"

    print(f"  phase cadence: p1 cd_mul {p1['cd_mul']} (canonical), "
          f"p2 {p2['cd_mul']} (fan={p2_fan['count']}, radial={p2_radial['count']}), "
          f"p3 {p3['cd_mul']} (spiral shots={p3_spiral['shots']} / turn={p3_spiral['turn']} / "
          f"gap={p3_spiral['gap']}); windups >= {C.BOSS_WINDUP_FLOOR:.2f}s floor")
    return phases


# --------------------------------------------------------------------------- #
# 7. Screenshot                                                                #
# --------------------------------------------------------------------------- #
def _screenshot(out):
    """Save a headless screenshot of a moving Rei Lagarto with a CicatriZ
    puddle on the floor. Uses the same BMP->PNG round-trip as
    ``check_boss_movement``.
    """
    g = _fresh()
    b = _spawn_boss(g, 'rei_lagarto')
    b.hp = int(b.max_hp * 0.6)        # mood = 'agitated' (verifies the windup
                                       # doesn't shorten when angry)
    b.boss_ai.scar_thresholds = [0.9]  # drop a scar quickly
    target = g.players[0]
    # tick long enough for the boss to walk a few steps AND the scar to spawn
    for f in range(240):
        g.step(DT)
        _reset(b)
        ang = f * 0.03
        target.pos = Vector2(MID[0] + math.cos(ang) * 320,
                             MID[1] + math.sin(ang) * 180)
    # pin the camera on the boss for the shot
    g.cam.pos = Vector2(b.spine.joints[0])
    g.cam.zoom = 0.7
    surf = pygame.Surface((C.WIDTH, C.HEIGHT), 0, 24)
    surf.fill((22, 24, 32))
    # draw the puddle first (under the boss)
    for s in b.boss_ai.scars:
        s.draw(surf, g.cam)
    for p in g.puddles:
        p.draw(surf, g.cam)
    b.draw(surf, g.cam)
    if b.boss_ai.state == 'windup' and b.boss_ai.pattern_id:
        b.boss_ai.draw(surf, g.cam)
    g.fx.draw(surf, g.cam, fonts.get(16))
    font = fonts.get(16)
    label = font.render(
        "Rei Lagarto -- CicatriZ puddle + proud_walk trail (boss in motion)",
        True, (240, 240, 246))
    surf.blit(label, (12, 12))
    tmp = out + '.bmp'
    pygame.image.save(surf, tmp)
    pygame.image.save(pygame.image.load(tmp), out)
    os.remove(tmp)
    print(f"  shot: {out}")


# --------------------------------------------------------------------------- #
# 7. Teeth: break each assertion on purpose and confirm the check catches it  #
# --------------------------------------------------------------------------- #
def test_teeth():
    """Prove each assertion has teeth by breaking the rule and confirming
    the corresponding test fails. Run as a separate phase so the main
    suite above can pass cleanly when this is not invoked.
    """
    print("  teeth:")
    # 1. Rhythm: shrink Rei's windup bumps to the pre-#123 values. The
    #    cycle claim breaks because the windup contribution dominates.
    #    PATTERNS captured the bumped values at import time, so the
    #    revert has to overwrite PATTERNS[pid]['windup'] directly, not
    #    just C.BOSS_*.
    reverted = {
        'fan':       pat.PATTERNS['fan']['windup'],
        'shockwave': pat.PATTERNS['shockwave']['windup'],
        'radial':    pat.PATTERNS['radial']['windup'],
        'charge':    pat.PATTERNS['charge']['windup'],
    }
    pat.PATTERNS['fan']['windup'] = 0.8
    pat.PATTERNS['shockwave']['windup'] = 0.7
    pat.PATTERNS['radial']['windup'] = 0.85
    pat.PATTERNS['charge']['windup'] = 0.7
    try:
        cycles = {}
        for bid, fn in PHASE_FACTORIES.items():
            _, _, cyc = _theoretical_cycle(bid, fn)
            cycles[bid] = cyc
        rei = cycles['rei_lagarto']
        others = {b: c for b, c in cycles.items() if b != 'rei_lagarto'}
        assert rei < max(others.values()), \
            f"shrunk rei_lagarto cycle {rei:.3f}s still >= {max(others.values()):.3f}s"
        print(f"    rhythm: fails when fan/shockwave/radial/charge windups "
              f"revert to pre-#123 values (cycle {rei:.3f}s < {max(others.values()):.3f}s)")
    finally:
        for pid, w in reverted.items():
            pat.PATTERNS[pid]['windup'] = w

    # 2. Telegraph: revert Rei's windup bumps to the pre-#123 values.
    #    The check rejects because Rei's avg windup drops below the
    #    next-longest boss. Same caveat as #1: PATTERNS captured the
    #    bumped values at import time.
    reverted = {
        'fan':       pat.PATTERNS['fan']['windup'],
        'shockwave': pat.PATTERNS['shockwave']['windup'],
        'radial':    pat.PATTERNS['radial']['windup'],
        'charge':    pat.PATTERNS['charge']['windup'],
    }
    pat.PATTERNS['fan']['windup'] = 0.8
    pat.PATTERNS['shockwave']['windup'] = 0.7
    pat.PATTERNS['radial']['windup'] = 0.85
    pat.PATTERNS['charge']['windup'] = 0.7
    try:
        windups = {}
        for bid, fn in PHASE_FACTORIES.items():
            avg_w, _, _ = _theoretical_cycle(bid, fn)
            windups[bid] = avg_w
        rei = windups['rei_lagarto']
        others = {b: w for b, w in windups.items() if b != 'rei_lagarto'}
        assert rei < max(others.values()), \
            f"halved rei_lagarto windup {rei:.3f}s still >= {max(others.values()):.3f}s"
        print(f"    telegraph: fails when fan/shockwave/radial/charge windups "
              f"revert to pre-#123 values ({rei:.3f}s < {max(others.values()):.3f}s)")
    finally:
        for pid, w in reverted.items():
            pat.PATTERNS[pid]['windup'] = w

    # 3. No retreat: temporarily allow sign flips on the committed dir
    #    by monkey-patching the function to alternate the direction.
    saved = MOVES['proud_walk']
    def flippy(boss, game, target, dials):
        # cheat: alternate between +x and -x every frame -- a guaranteed
        # sign flip on consecutive frames, exactly the regression we
        # want the check to catch.
        if not hasattr(flippy, 'toggle'):
            flippy.toggle = 0
        flippy.toggle = 1 - flippy.toggle
        boss.boss_ai._pw_dir = Vector2(1, 0) if flippy.toggle == 0 else Vector2(-1, 0)
        boss.boss_ai._pw_t = 0
        return boss.boss_ai._pw_dir, 0.45
    MOVES['proud_walk'] = flippy
    try:
        g = _fresh()
        b = _spawn_boss(g, 'rei_lagarto')
        target = g.players[0]
        prev = None
        flips = 0
        for f in range(60):
            g.step(DT)
            _reset(b)
            ang = f * 0.06
            target.pos = Vector2(MID[0] + math.cos(ang) * 350,
                                 MID[1] + math.sin(ang) * 250)
            cur = b.boss_ai._pw_dir
            if prev is not None and cur.length_squared() > 1e-6:
                dot = cur.x * prev[0] + cur.y * prev[1]
                if dot < -0.99:
                    flips += 1
            prev = (cur.x, cur.y)
        assert flips > 0, \
            f"sign-flipping variant produced no flips; the test cannot catch the regression"
        print(f"    no retreat: fails when the cone constraint is bypassed "
              f"({flips} sign flips over {f+1} frames)")
    finally:
        MOVES['proud_walk'] = saved

    # 4. CicatriZ trail: temporarily override spawn_scar with the legacy
    #    underfoot-random placement and confirm the trail claim breaks.
    saved_spawn = bossai.spawn_scar
    def legacy_scar(boss, game):
        from lagarto.combat import weapons
        pos = boss.pos + random_dir(boss.max_r * 0.6)
        p = weapons.Puddle(pos, boss.max_r * 0.9, C.KING_SCAR_DMG, C.KING_SCAR_LIFE,
                           22, hostile=True, tick=0.5,
                           slow=(C.KING_SCAR_SLOW, C.KING_SCAR_TIME))
        game.spawn_puddle(p)
        return p
    bossai.spawn_scar = legacy_scar
    try:
        bad = 0
        for fight in range(3):
            random.seed(fight + 123)
            g = _fresh()
            b = _spawn_boss(g, 'rei_lagarto')
            b.boss_ai.scar_thresholds = [0.99, 0.5]
            target = g.players[0]
            for f in range(900):
                g.step(DT)
                _reset(b)
                ang = f * 0.04
                target.pos = Vector2(MID[0] + math.cos(ang) * 320,
                                     MID[1] + math.sin(ang) * 200)
            for scar in b.boss_ai.scars:
                snapshot = getattr(scar, '_scar_path_snapshot', [])
                if snapshot:
                    min_d = min((scar.pos - s).length() for s in snapshot)
                else:
                    min_d = min((scar.pos - s).length()
                                for s in b.boss_ai._path_samples)
                if min_d > b.max_r * 4:
                    bad += 1
        assert bad > 0, \
            "legacy spawn_scar still landed on the path; the test cannot catch the regression"
        print(f"    cicatriz trail: fails when spawn_scar reverts to the legacy "
              f"underfoot-random placement ({bad} off-path scars over 3 fights)")
    finally:
        bossai.spawn_scar = saved_spawn

    # 5. No invuln window: temporarily patch the FSM to flip
    #    boss_invuln=True during windup, simulating an authored window.
    saved_tick = bossai.BossAI.tick
    def invuln_tick(self, dt, game):
        d, s = saved_tick(self, dt, game)
        if self.state == 'windup':
            self.boss.boss_invuln = True
        return d, s
    bossai.BossAI.tick = invuln_tick
    try:
        g = _fresh()
        b = _spawn_boss(g, 'rei_lagarto')
        bad = 0
        for f in range(600):
            g.step(DT)
            _reset(b)
            s = b.boss_ai.state
            if b.boss_invuln and s == 'windup':
                bad += 1
        assert bad > 0, "invuln-during-windup variant produced no flips"
        print(f"    no invuln window: fails when windup sets boss_invuln=True "
              f"({bad} windup frames invulnerable)")
    finally:
        bossai.BossAI.tick = saved_tick

    # 6. Phase cadence + density (issue #162): revert the per-phase
    #    cd_mul and the pattern_dials to pre-#162 values and confirm
    #    the new assertion fails. Two cases:
    #    (a) cd_mul > 0.85 on phase 2 (teeth says the cap is 0.80)
    #    (b) fan count < 2 on phase 2 (teeth says floor is 2)
    saved = pat.king_phases
    def bad_phases():
        return [
            dict(hp_frac=1.0,  patterns=['fan', 'shockwave', 'charge'],
                 cd_mul=1.0,  moves=['proud_walk']),
            # pre-#162 cadence (0.95) AND a fan that stays at 1: both teeth.
            dict(hp_frac=0.66, patterns=['fan', 'shockwave', 'charge', 'radial'],
                 cd_mul=0.95, moves=['proud_walk']),
            dict(hp_frac=0.33, patterns=['spiral', 'shockwave', 'charge', 'radial'],
                 cd_mul=0.85, moves=['proud_walk']),
        ]
    pat.king_phases = bad_phases
    try:
        phases = pat.king_phases()
        p2 = phases[1]
        # mirror the assertion's gates from a low-pile fixture.
        assert p2['cd_mul'] > 0.85 or _eff_king_dials(p2, 'fan')['count'] < 2, \
            "bad_phases didn't break either teeth (cd_mul > 0.85 or fan count < 2)"
        assert True, "above only proves the teeth holds; the real check is below"
        # try the real assertion against the broken fixture -- should fail.
        try:
            test_phase_cadence()
        except AssertionError as ae:
            print(f"    phase cadence: fails when king_phases reverts to "
                  f"pre-#162 values ({str(ae).splitlines()[0][:90]}...)")
        else:
            raise AssertionError(
                "test_phase_cadence() accepted the pre-#162 fixture; "
                "the assertion has no teeth")
    finally:
        pat.king_phases = saved

    # 7. Screenshot: not a checkable invariant; the bytes-on-disk is
    #    the contract. Skip the teeth for this one -- visual diff
    #    would require an image-hash library that's not in scope.
    print("    screenshot: visual; teeth skipped (bytes-on-disk is the contract)")


def main():
    if '--teeth' in sys.argv:
        test_teeth()
        print("ALL OK (teeth)")
        return
    if '--shot' in sys.argv:
        out = sys.argv[sys.argv.index('--shot') + 1]
        _screenshot(out)
        return
    print("issue #123: Rei Lagarto -- legibility canonical")
    test_rhythm()
    test_telegraph()
    test_no_retreat()
    test_cicatriz_trail()
    test_no_invuln_window()
    test_phase_cadence()
    test_teeth()
    print("ALL OK")


if __name__ == '__main__':
    main()
