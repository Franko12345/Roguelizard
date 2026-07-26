"""Boss framework (Fase 5): a phase-based attack-pattern engine layered on any
existing enemy body (``rounds._spawn_boss`` just scales up a themed species) --
so ten different "fights" can share one engine and differ only by DATA (which
patterns each phase rolls), the same split ``champions.py`` uses between
identity and mechanics.

Timeline, per boss:

    intro (invulnerable, ~1s) -> [approach -> windup -> attack -> recover] x N
        -> phase transition (invulnerable, ~1s, swaps the pattern list)
        -> ... -> death

Patterns are functions ``(boss, game, target) -> None`` that spawn Projectiles
through the existing ``game.spawn_projectile`` pipeline -- no new projectile
type, just new arrangements of the one every ranged enemy already uses. Every
pattern telegraphs (>=27 frames, drawn on screen, not just timed) before it
fires -- the phase-2 lesson ("telegrafo é tempo E visibilidade") applies here
at boss scale too.

A phase change swaps *at most two things* (its pattern list + one numeric
dial), so the player can attribute what changed instead of relearning a new
fight from scratch every threshold.
"""

from .ai import BossAI, spawn_scar
from .patterns import (
    PATTERNS,
    radial_burst, fan_shot, aimed_barrage, _tick_barrage, summon_adds,
    shockwave, spiral_pattern, _tick_spiral, charge_attack, pincha_bite,
    _select_arms_rain, arms_rain, sky_slam, web_trap,
    king_phases, centipede_phases, centipede_on_phase, kraken_phases,
    primordial_phases, beetle_phases, spider_king_phases, crystal_phases,
    wasp_phases, default_phases,
    eye_phases, eye_on_phase, eye_setup, eye_blink_tick,
    fire_breath, _tick_fire_breath, hand_slam, eye_laser, bouncing_bullets,
    grid_of_fire, muralha_phases, ankh_phases,
)
from .personality import (
    BossPersonality, default_personality,
    king_personality, centipede_personality, kraken_personality,
    primordial_personality, beetle_personality, spider_king_personality,
    crystal_personality, wasp_personality, eye_personality, wall_personality,
    ankh_personality,
)
