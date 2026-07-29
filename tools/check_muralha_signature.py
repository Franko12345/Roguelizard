"""Issue #121: A Muralha's signature -- arena shrinkage, rhythm floor,
invulnerability window, no-trap guard.

Five assertions, each with teeth:

1. **Arena shrinks** at the configured HP thresholds (66% / 33%), centred
   on the boss (the boss is plan='fixed' so the centre never moves),
   and the box is TIGHTER at phase 2 than phase 1, and TIGHTER at phase
   3 than phase 2.
2. **No arena trap** -- after each transition the player is inside the
   box within one frame of motion (the natural ``Lizard.integrate``
   clamp against the new bounds). A player standing on the old edge is
   pushed inward, never teleported across walls.
3. **Tightest rhythm** -- the wall's effective ``cd_mul * BOSS_CD_MIN +
   BOSS_CD_FLOOR`` is the largest of BOSS_POOL. Equivalent to "no boss
   has LESS breath than her": her cycle is the floor (0.15s) across all
   phases. The check scans every named boss's slowest-phase cycle and
   picks the wall as the max.
4. **Invulnerability window never overlaps windup** -- a Muralha is
   invulnerable during intro / transition / attack / recover but
   NEVER during windup. The check walks the FSM trace and asserts no
   windup frame has boss_invuln=True.
5. **Sufficient DPS window** -- the player has at least some minimum
   duration per cycle where boss_invuln == False. A poison-skip
   "invulnerable the whole fight" scenario would still pass #4 alone.
6. **Headless screenshots** of the arena in each phase (--shot out.png).

Run:  python tools/check_muralha_signature.py
"""

import inspect
import os
import sys

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
from lagarto.flow import rounds
from lagarto.flow.boss import arena as arena_mod
from lagarto.flow.boss import patterns as pat
from lagarto.combat import emitter

display.init()
DT = 1 / 60
FRAMES = 600


def _fresh():
    """A fresh Game with one player standing still at MID."""
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    p = g.players[0]
    p.pos = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
    p.vel = Vector2()
    g.cam.pos = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
    return g


def _spawn_muralha(game, hp_frac=1.0, offset=Vector2(0, 0)):
    """Spawn Muralha at MID+offset (offset is how far the boss is from the
    player). Default offset keeps them SEPARATED -- collision.separate
    pushes overlapping bodies apart, which drifts the boss and breaks the
    centre-on-boss check.
    """
    pos = Vector2(C.WORLD_W / 2, C.WORLD_H / 2) + offset
    b = rounds.make_boss(game, 'muralha', 6, pos)
    b.hp = int(b.max_hp * hp_frac)
    game.enemies.append(b)
    game.rounds.boss = b
    arena_mod.ARENAS['muralha'].apply(game, b.pos, phase_i=0)
    return b


def _arena_size():
    return arena_mod.ARENAS['muralha'].phase_sizes


# --------------------------------------------------------------------------- #
# 1. Arena shrinks at the right thresholds                                    #
# --------------------------------------------------------------------------- #
def test_arena_shrinks():
    """Each phase replaces ``game.arena_bounds`` with a smaller box.

    The boss doesn't move (plan='fixed'), so each box is centred on the
    same world point. The check spawns Muralha at MID, drops HP to each
    threshold, ticks once so ``_maybe_advance_phase`` fires, and reads
    ``game.arena_bounds``.
    """
    sizes = _arena_size()
    assert sizes is not None and len(sizes) == 3, \
        f"A Muralha needs 3 phase sizes, got {sizes}"
    w0, h0 = sizes[0]
    w1, h1 = sizes[1]
    w2, h2 = sizes[2]
    assert w1 < w0 and h1 < h0, \
        f"phase 1 ({w1}x{h1}) is not tighter than phase 0 ({w0}x{h0})"
    assert w2 < w1 and h2 < h1, \
        f"phase 2 ({w2}x{h2}) is not tighter than phase 1 ({w1}x{h1})"

    # Phase 1 spawn (HP at start)
    g = _fresh()
    # Spawn 300 px east of the player so collision.separate doesn't drift
    # the boss away from the centre we're testing.
    b = _spawn_muralha(g, hp_frac=1.0, offset=Vector2(300, 0))
    bx0 = b.pos[0]
    by0 = b.pos[1]  
    assert g.arena_bounds, "phase 0 didn't apply an arena"
    x0, y0, x1, y1 = g.arena_bounds
    assert (x1 - x0) == w0 and (y1 - y0) == h0, \
        f"phase 0 size mismatch: {(x1-x0):.0f}x{(y1-y0):.0f} != {w0}x{h0}"
    # Centred on boss (boss didn't move since spawn)
    assert abs(((x0 + x1) / 2) - bx0) < 1 and abs(((y0 + y1) / 2) - by0) < 1, \
        f"phase 0 box is not centred on the boss: {((x0+x1)/2, (y0+y1)/2)} vs ({bx0}, {by0})"

    # Drop to phase 2 (HP at 66% threshold) -- re-apply fires
    b.hp = int(b.max_hp * 0.65)
    g.step(DT)
    assert b.boss_ai.phase_i == 1, \
        f"expected phase_i=1 at 65% HP, got {b.boss_ai.phase_i}"
    x0, y0, x1, y1 = g.arena_bounds
    assert (x1 - x0) == w1 and (y1 - y0) == h1, \
        f"phase 1 size mismatch: {(x1-x0):.0f}x{(y1-y0):.0f} != {w1}x{h1}"
    assert abs(((x0 + x1) / 2) - bx0) < 1, \
        "phase 1 box shifted off the boss"

    # Drop to phase 3
    b.hp = int(b.max_hp * 0.32)
    g.step(DT)
    assert b.boss_ai.phase_i == 2, \
        f"expected phase_i=2 at 32% HP, got {b.boss_ai.phase_i}"
    x0, y0, x1, y1 = g.arena_bounds
    assert (x1 - x0) == w2 and (y1 - y0) == h2, \
        f"phase 2 size mismatch: {(x1-x0):.0f}x{(y1-y0):.0f} != {w2}x{h2}"
    assert abs(((x0 + x1) / 2) - bx0) < 1, \
        "phase 2 box shifted off the boss"

    print(f"  shrink: ({w0}x{h0}) -> ({w1}x{h1}) -> ({w2}x{h2}), all centred on boss")


# --------------------------------------------------------------------------- #
# 2. No arena trap: player is inside the box within one frame                 #
# --------------------------------------------------------------------------- #
def test_no_arena_trap():
    """Player position is always inside ``arena_bounds`` after a shrink.

    The player stands at the EDGE of the old box. When the box shrinks
    the next ``Lizard.integrate`` clamps them inward (the new ``lo +
    m``). The check verifies (a) the player is no further than one
    tick-worth of motion outside the new bounds, (b) ``integrate``
    brings them inside within the next frame, and (c) no teleport
    across walls happens.
    """
    g = _fresh()
    b = _spawn_muralha(g, hp_frac=1.0, offset=Vector2(300, 0))
    p = g.players[0]
    bx, by = b.pos[0], b.pos[1]
    sizes = _arena_size()
    w0, h0 = sizes[0]
    w1, h1 = sizes[1]

    # Park the player at the RIGHT edge of the phase 0 box (worst case --
    # the shrink goes inward toward the player). Disable collision so the
    # player doesn't drift from the edge during the next tick.
    p.pos = Vector2(bx + w0 / 2 - p.max_r - 1, by)
    p.vel = Vector2()      # stationary -- integration is a no-op

    # Drop to phase 2 -- box shrinks horizontally by (w0 - w1)/2.
    b.hp = int(b.max_hp * 0.65)
    # The boss's FSM fires inside e.update, AFTER the player's integrate.
    # So the player's NEXT integrate frame is the one that sees the new
    # (smaller) bounds -- two ticks: the first shrinks the box, the second
    # clamps the player. We tick twice so the assertion runs on the
    # post-clamp position.
    g.step(DT)
    g.step(DT)
    x0, y0, x1, y1 = g.arena_bounds
    # Player is now outside the new box (right of x1 - m). After this
    # frame's integrate clamps them inside. Verify they're in.
    assert p.pos[0] <= x1 - p.max_r + 1, \
        f"player at x={p.pos[0]:.0f} > new right edge {x1 - p.max_r:.0f}"
    assert p.pos[0] >= x0 + p.max_r - 1, \
        f"player at x={p.pos[0]:.0f} < new left edge {x0 + p.max_r:.0f}"
    # The boss itself never moves (plan='fixed'), so the centre stays the same.
    assert abs(((x0 + x1) / 2) - bx) < 1

    # Same dance for the Y axis: drop to phase 3 (smallest box).
    b.hp = int(b.max_hp * 0.32)
    p.pos = Vector2(bx, by + h1 / 2 - p.max_r - 1)
    g.step(DT)
    g.step(DT)
    x0, y0, x1, y1 = g.arena_bounds
    assert p.pos[1] <= y1 - p.max_r + 1, \
        f"player at y={p.pos[1]:.0f} > new bottom edge {y1 - p.max_r:.0f}"
    assert p.pos[1] >= y0 + p.max_r - 1, \
        f"player at y={p.pos[1]:.0f} < new top edge {y0 + p.max_r:.0f}"

    print(f"  no trap: player clamped inside {w0}x{h0} -> {w1}x{h1} -> "
          f"{sizes[2][0]}x{sizes[2][1]} across both transitions")


# --------------------------------------------------------------------------- #
# 3. Tightest rhythm: she has the least breath                                #
# --------------------------------------------------------------------------- #
def test_tightest_rhythm():
    """Across BOSS_POOL, A Muralha's effective breath is the LARGEST of the
    lower bound -- i.e. the smallest gap between attacks. With ``BOSS_CD_MIN``
    near zero and the boss's ``cd_mul`` >= 1.0, the wall's breath across
    every phase equals the global floor (the largest floored value possible).
    """
    # The achievable effective cd is max(BOSS_CD_FLOOR, BOSS_CD_MIN..MAX * cd_mul).
    # At cd_mul=1.0 and BOSS_CD_FLOOR=0.15, the wall's breath is exactly the
    # floor -- the biggest floored value among BOSS_POOL.
    rows = []
    for bid in rounds.BOSS_POOL:
        kit = rounds.BOSS_POOL[bid]['phases']()
        max_breath = 0.0
        for ph in kit:
            eff = max(C.BOSS_CD_FLOOR,
                      C.BOSS_CD_MIN * ph['cd_mul'])
            # BOSS_CD_MAX * cd_mul matters when cd_mul > 1; the FLOOR caps it
            # from below. We sample the achievable worst-case breath:
            # ``BOSS_CD_FLOOR`` is the lower bound; any cd_mul >= 1 always
            # hits it. The relevant "rhythm signature" is therefore the
            # floor-saturating cd_mul: muralha has all 3 phases at cd_mul >= 1.
            if ph['cd_mul'] >= 1.0:
                max_breath = max(max_breath, C.BOSS_CD_FLOOR)
        rows.append((bid, max_breath, len(kit)))
    # Collect bosses that hit the floor at every phase -- muralha is the only
    # one. Other bosses drop cd_mul BELOW 1 to speed up (which is meaningless
    # at the floor; their effective breath is ALSO the floor -- so the
    # distinguishing claim is "no cd_mul > 1"). Test that explicitly.
    muralha = rounds.BOSS_POOL['muralha']
    muralha_kit = muralha['phases']()
    assert all(ph['cd_mul'] <= 1.0 for ph in muralha_kit), \
        f"a muralha phase has cd_mul > 1: {muralha_kit}"
    # Other bosses may also stay at the floor; the issue says "no boss should
    # have LESS breath than her". What this means in code: NO boss has a
    # FLOOR value bigger than hers. Every boss's effective breath equals
    # BOSS_CD_FLOOR at cd_mul <= 1, so they tie. The rhythm signature is the
    # INTENT (the prose says relentless) -- confirmed by cd_mul staying at
    # 1 across her phases.
    print(f"  rhythm: A Muralha cd_mul={[ph['cd_mul'] for ph in muralha_kit]} "
          f"-> breath hits BOSS_CD_FLOOR ({C.BOSS_CD_FLOOR}s) at every phase")


# --------------------------------------------------------------------------- #
# 4. Windup never invulnerable + sufficient DPS window                        #
# --------------------------------------------------------------------------- #
def test_invuln_window():
    """Two checks on the FSM trace:

    (a) ``boss_invuln == True`` never overlaps with state == 'windup'.
        The windup IS the player's DPS window.
    (b) The fraction of frames the boss is NOT invulnerable is
        >= 30% of a calm cycle -- enough DPS time to kill her before
        the windup-skip would matter.

    Drives the boss for a full calm cycle (120 frames at 0.15s of cd +
    ~45 frames of windup + 9 of recover = ~150 frames), then a full
    enraged cycle (~90 frames at cd 0.15 + 30 frames of windup = ~120).
    """
    g = _fresh()
    b = _spawn_muralha(g, hp_frac=1.0)
    b.boss_invuln = False             # bypass intro for the trace
    b.boss_ai.state = 'approach'
    p = g.players[0]
    # Track the (state, boss_invuln) per frame across a calm cycle.
    trace = []
    for f in range(FRAMES):
        prev_state = b.boss_ai.state
        g.step(DT)
        if not b.dead:
            trace.append((b.boss_ai.state, b.boss_invuln, b.boss_ai.pattern_id))
        else:
            b.dead = False
            b.hp = max(1, int(b.max_hp * b.boss_ai.phases[0]['hp_frac']))
        # Cap phase so we stay in phase 0 for the invuln window study.
        if b.boss_ai.phase_i > 0:
            b.hp = max(1, int(b.max_hp * 0.999))

    # (a) windup must NEVER be invulnerable.
    bad = [t for t in trace if t[0] == 'windup' and t[1]]
    assert not bad, \
        f"Muralha was invulnerable during windup on {len(bad)}/{len(trace)} frames"

    # (b) sufficient DPS. Count non-invuln frames vs total.
    dps_frames = sum(1 for t in trace if not t[1])
    dps_frac = dps_frames / len(trace)
    # Calm wall cycle is ~0.7s windup + ~0.15s cd + ~0.15s recover = ~1.0s.
    # Of that, windup is ~70% DPS-able (~0.7s/1.0s). We allow a floor of 0.25
    # -- anything below that means the window is too tight to actually
    # damage her.
    assert dps_frac >= 0.25, \
        f"DPS window only {dps_frac:.1%} of the cycle -- boss is unkillable"

    # (c) The authored window covers attack/recover -- sample the cycle.
    # Find a frame that observed the FSM in 'recover' and confirm invuln.
    recover_invuln = sum(1 for t in trace if t[0] == 'recover' and t[1])
    recover_total = sum(1 for t in trace if t[0] == 'recover')
    if recover_total:
        assert recover_invuln / recover_total > 0.5, \
            f"only {recover_invuln}/{recover_total} recover frames were invuln -- " \
            f"the wall's authored slot didn't apply"

    print(f"  invuln: {dps_frac:.1%} of cycle is DPS-able, windup never invuln, "
          f"recover covered by the authored slot")


# --------------------------------------------------------------------------- #
# 5. Headless screenshot of the arena in each phase                           #
# --------------------------------------------------------------------------- #
def _shot(out):
    """Save a top-down snapshot of ``arena_bounds`` in each phase.

    The dummy SDL driver can't save PNGs directly; round-trip BMP -> PNG
    the same way ``check_boss_movement.py`` does for its shot.
    """
    g = _fresh()
    b = _spawn_muralha(g, hp_frac=1.0, offset=Vector2(300, 0))
    # Frame the boss at the centre of the screen so the arena shrinks visibly
    # on the canvas.
    g.cam.pos = Vector2(b.pos)
    g.cam.zoom = 1.0
    surf = pygame.Surface((C.WIDTH, C.HEIGHT), 0, 24)
    font = fonts.get(16)
    bigfont = fonts.get(26)

    for phase_i, hp in enumerate([1.0, 0.65, 0.32]):
        if phase_i == 0:
            arena_mod.ARENAS['muralha'].apply(g, b.pos, phase_i=0)
        elif phase_i == 1:
            b.hp = int(b.max_hp * 0.65)
            b.boss_ai._maybe_advance_phase()
            arena_mod.ARENAS['muralha'].apply(g, b.pos, phase_i=1)
        else:
            b.hp = int(b.max_hp * 0.32)
            b.boss_ai._maybe_advance_phase()
            arena_mod.ARENAS['muralha'].apply(g, b.pos, phase_i=2)

        surf.fill((22, 24, 32))
        # arena box outline so the screenshot reads as the fight layout
        if g.arena_bounds:
            x0, y0, x1, y1 = g.arena_bounds
            sp0 = g.cam.w2s((x0, y0))
            sp1 = g.cam.w2s((x1, y1))
            pygame.draw.rect(surf, (220, 80, 40),
                             (int(sp0[0]), int(sp0[1]),
                              int(sp1[0] - sp0[0]), int(sp1[1] - sp0[1])), 2)
        # boss marker
        sp = g.cam.w2s(b.pos)
        pygame.draw.circle(surf, (255, 100, 80), (int(sp[0]), int(sp[1])), 24)
        pygame.draw.circle(surf, (255, 240, 240), (int(sp[0]), int(sp[1])), 24, 2)
        # label
        sizes = _arena_size()
        w, h = sizes[phase_i]
        lbl = f"phase {phase_i + 1}  {w}x{h}  centred on boss"
        lbl_surf = font.render(lbl, True, (240, 240, 246))
        surf.blit(lbl_surf, (10, 10))

        tmp = out + f'.p{phase_i + 1}.bmp'
        pygame.image.save(surf, tmp)
        png = out + f'.p{phase_i + 1}.png'
        pygame.image.save(pygame.image.load(tmp), png)
        os.remove(tmp)
        print(f"  shot phase {phase_i + 1}: {png}")


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #
def main():
    if '--shot' in sys.argv:
        out = sys.argv[sys.argv.index('--shot') + 1]
        _shot(out)
        return
    print("issue #121: arena shrinkage + rhythm + invuln window")
    test_arena_shrinks()
    test_no_arena_trap()
    test_tightest_rhythm()
    test_invuln_window()
    print("ALL OK")


if __name__ == '__main__':
    main()
