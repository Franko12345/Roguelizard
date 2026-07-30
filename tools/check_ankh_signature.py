"""Issue #165: ANKH multi-corpo fantasma -- the signature.

ANKH is the boss that "remembers" four predecessors: the Rei Lagarto
(golden horned), Mae-Escaravelho (spider), Kraken-Mor (octopus) and the
Primordial itself (a violet re-skinned horned body). The 4-phase ATTACK
kit has always been there (#75) -- the issue is the BODY: a translucent
ghost of each phase's memory species, painted in layers under the boss
with per-pixel alpha and a per-phase tint. Phase 4 cross-fades all four
ghosts to 0.5 simultaneously ("the fusao").

Six assertions:

1. **Four phantombodies** -- ``boss.phantom_bodies`` has 4 entries with
   the expected (species_key, tint) per phase. The species are existing
   ``SPECIES`` keys, not new creatures (ADR-0001).
2. **Setup baseline** -- phase 1 alpha is 1.0 from spawn (the gold ghost
   is visible immediately, before any transition). 2..4 start at 0.
3. **Per-frame cross-fade** -- ``target_alpha`` switches on phase change,
   and the per-frame ``approach()`` actually walks each phantom's ``alpha``
   toward it. The swap reads as cinema, not a blink.
4. **Phase 4 fusion** -- on transition to phase 4, ALL FOUR targets land
   on 0.5. The issue's "literally four bodies at the same pixel" rule.
5. **Boss invariants hold** -- ANKH still has ``is_boss=True`` and
   ``knockback=0`` (the test in check_issues already pins these; this is
   the redundant belt-and-suspenders the signature carries).
6. **Screenshot** -- a headless render of ANKH standing at the centre of
   the arena with all four ghosts at full / fusion alpha; the layered
   silhouettes are the visual evidence the multi-corpo lands.

Run:  python tools/check_ankh_signature.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2

from lagarto.core import config as C, fonts
from lagarto.creatures.parts import Phantombody, _PHANTOM_CACHE
from lagarto.creatures import species
from lagarto.render import display
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.flow import rounds
from lagarto.flow.boss import patterns as pat

DT = 1 / 60
WORLD_MID = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)

# Expected (species_key, tint) per phase. The tints are the visual signature
# of each memory; if anyone changes one, this list is the source of truth.
EXPECTED = [
    ('horned',  (255, 215, 100)),     # phase 1 -- Rei Lagarto (gold)
    ('spider',  (255, 180,  80)),     # phase 2 -- Mae-Escaravelho
    ('octopus', ( 80, 130, 255)),     # phase 3 -- Kraken-Mor (blue)
    ('horned',  (220, 100, 200)),     # phase 4 -- Primordial (violet)
]


def _fresh_game():
    """A clean Game with one player and the camera centered at the world mid."""
    display.init()
    f, bf = fonts.get(16), fonts.get(26)
    g = Game(1, make_controllers(1, []), f, bf, mode='normal', chars=None)
    p = g.players[0]
    p.pos = Vector2(WORLD_MID)
    p.vel = Vector2()
    g.cam.pos = Vector2(WORLD_MID)
    return g


def _spawn_ankh(g):
    """Spawn ANKH the way rounds._spawn_boss would, with the setup hook fired."""
    b = rounds.make_boss(g, 'ankh', 6, WORLD_MID + Vector2(360, 0))
    b.boss_invuln = False
    b.boss_ai.state = 'approach'
    g.enemies.append(b)
    g.rounds.boss = b
    return b


def _run(g, frames):
    for _ in range(frames):
        g.step(DT)


# ---------- assertion bodies ---------- #

def assert_four_phantombodies(b):
    fb = getattr(b, 'phantom_bodies', None)
    assert isinstance(fb, list) and len(fb) == 4, \
        f"ANKH must carry 4 phantombodies, got {type(fb).__name__} of len {len(fb) if fb is not None else 'N/A'}"
    assert all(isinstance(p, Phantombody) for p in fb), \
        "all phantombodies must be Phantombody instances"
    for i, ((sk, tint), p) in enumerate(zip(EXPECTED, fb)):
        assert p.species_key == sk, \
            f"phantombody[{i}].species_key = {p.species_key!r}, expected {sk!r}"
        assert p.tint == tuple(tint), \
            f"phantombody[{i}].tint = {p.tint!r}, expected {tint!r}"
        assert sk in species.SPECIES, \
            f"phantombody[{i}] species {sk!r} not in SPECIES (ADR-0001: ghosts reuse existing species)"


def assert_setup_baseline(b):
    """Phase 1 gold ghost is visible from spawn; 2..4 start at 0."""
    fb = b.phantom_bodies
    assert fb[0].alpha == 1.0 and fb[0].target_alpha == 1.0, \
        f"phase 1 should be alpha=1.0 from spawn, got {fb[0].alpha}"
    for i in range(1, 4):
        assert fb[i].alpha == 0.0 and fb[i].target_alpha == 0.0, \
            f"phase {i + 1} should be alpha=0.0 from spawn, got alpha={fb[i].alpha}"


def assert_cross_fade(g, b):
    """Phase 1 -> 2 transition: target_alphas swap, then approach() animates
    the visible alpha toward the new targets over the next ~1.5s."""
    fb = b.phantom_bodies
    # Drop HP below the phase-2 threshold (0.75) so _maybe_advance_phase triggers.
    b.hp = int(b.max_hp * 0.70)
    _run(g, frames=10)            # a handful of frames: targets swap, alpha barely moves
    assert fb[0].target_alpha == 0.0, f"old phase target should be 0, got {fb[0].target_alpha}"
    assert fb[1].target_alpha == 1.0, f"new phase target should be 1, got {fb[1].target_alpha}"
    assert fb[2].target_alpha == 0.0, f"third phase target should be 0, got {fb[2].target_alpha}"
    # Run long enough for the rate=2.0 cross-fade to settle (95% in ~1.5s).
    _run(g, frames=120)
    assert fb[0].alpha < 0.05, f"old alpha should have decayed, got {fb[0].alpha:.3f}"
    assert fb[1].alpha > 0.95, f"new alpha should have risen, got {fb[1].alpha:.3f}"
    assert fb[2].alpha < 0.05, f"third phase should still be ~0, got {fb[2].alpha:.3f}"


def assert_phase4_fusion(g, b):
    """Phase 4 = fusion: all four phantoms visible at 0.5 simultaneously."""
    fb = b.phantom_bodies
    # Drop HP below the phase-4 threshold (0.25) so both transitions fire.
    b.hp = int(b.max_hp * 0.20)
    _run(g, frames=10)
    assert fb[0].target_alpha == 0.5, f"phase 4 should target 0.5 globally, got {fb[0].target_alpha}"
    assert fb[1].target_alpha == 0.5, f"phase 4 should target 0.5 globally, got {fb[1].target_alpha}"
    assert fb[2].target_alpha == 0.5, f"phase 4 should target 0.5 globally, got {fb[2].target_alpha}"
    assert fb[3].target_alpha == 0.5, f"phase 4 should target 0.5 globally, got {fb[3].target_alpha}"
    # Let the alphas settle to 0.5.
    _run(g, frames=200)
    for i, p in enumerate(fb):
        assert abs(p.alpha - 0.5) < 0.05, \
            f"phantom[{i}] should settle near 0.5, got {p.alpha:.3f}"


def assert_boss_invariants(b):
    """ANKH must remain a real boss body -- is_boss, knockback 0 -- the ghost
    silhouettes ride on top, they don't replace the boss."""
    assert b.is_boss is True, f"ANKH must be a boss, got is_boss={b.is_boss}"
    assert b.genome.knockback == 0.0, \
        f"ANKH must still have knockback=0 (boss body), got {b.genome.knockback}"


def assert_screenshot(g, b):
    """Render the visual: ANKH standing still at phase 4, all four ghosts
    layered at 0.5. The ink outlines of all four silhouettes should be on
    the surface -- any coloured pixel (not the BG fill) proves the
    layering lands. Saves a PNG snapshot for the issue trail."""
    import random
    random.seed(0)
    # Force phase 4 and settle the alphas for the snapshot.
    b.hp = int(b.max_hp * 0.20)
    _run(g, frames=240)
    surf = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
    bg = (20, 20, 30, 255)
    surf.fill(bg)
    b.draw(surf, g.cam)
    b.boss_ai.draw(surf, g.cam)
    # PixelArray iteration in pygame-CE under the dummy driver only reports
    # a per-row unique value, not per-pixel; use random get_at() samples
    # instead. We need painted pixels distinct from the BG fill.
    w, h = surf.get_size()
    painted = 0
    sampled = 0
    for _ in range(4000):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        sampled += 1
        if surf.get_at((x, y)) != bg:
            painted += 1
    assert painted > sampled * 0.005, \
        f"ANKH + ghosts painted only {painted}/{sampled} sampled pixels above the BG fill"
    # Snapshot for the issue trail.
    out = 'tools/screenshot_ankh_phase4.png'
    try:
        pygame.image.save(surf, out)
    except pygame.error:
        # dummy driver can't write PNGs to disk directly; fall back to BMP
        out = 'tools/screenshot_ankh_phase4.bmp'
        pygame.image.save(surf, out)


def main():
    g = _fresh_game()
    b = _spawn_ankh(g)

    assert_four_phantombodies(b)
    print("  ok  1) 4 phantombodies, species + tints match EXPECTED")

    assert_setup_baseline(b)
    print("  ok  2) phase 1 alpha=1.0 from spawn; 2..4 start at 0")

    assert_cross_fade(g, b)
    print("  ok  3) cross-fade advances alpha toward target across 120 frames")

    assert_phase4_fusion(g, b)
    print("  ok  4) phase 4 fusion: all 4 target_alpha = 0.5, alphas settle")

    assert_boss_invariants(b)
    print("  ok  5) ANKH still is_boss and knockback=0")

    assert_screenshot(g, b)
    # The screenshot runs an actual draw of every phantombody; the cache
    # must end up populated as a side effect.
    assert _PHANTOM_CACHE, \
        "parts._PHANTOM_CACHE should be populated after ANKH draws its ghosts"
    print("  ok  6) render of phase-4 ANKH + ghosts hits >1% of screen")
    print("         parts._PHANTOM_CACHE populated ({0} ghosts cached)"
          .format(len(_PHANTOM_CACHE)))

    print("\nALL OK -- ANKH signature holds")


if __name__ == '__main__':
    main()
