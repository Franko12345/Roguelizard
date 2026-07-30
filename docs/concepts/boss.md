# Boss

A large enemy with an FSM, phase transitions, and a personality. Bosses
gate rounds — the round only `cleared`s when the boss dies. Not to be
confused with a [Champion](./champion.md), which lives inside a round.

Defined in `lagarto/flow/boss/`. Selection rules in
[ADR-0004](../adr/0004-boss-pool-per-tier.md).

## FSM

```
intro
  ├─ (invulnerable) ──► approach ──► windup ──► attack ──► recover
  │                        ▲                                 │
  │                        └─────────────────────────────────┘
  └─ (phase transition) ── invulnerable ── next phase
```

Bosses use a **catalogue of patterns** — each is a data-driven
`(shooter, game, target, dials) -> None`. There is no "attack class"
hierarchy.

## Patterns

The functions live in the [Emitter](../../CONTEXT.md)
(`lagarto/combat/emitter.py`), shared with common enemies
([ADR-0012](../adr/0012-shared-pattern-emitter.md)). What is boss-specific is
`PATTERNS` in `flow/boss/patterns.py`: id → the emitter function, its windup,
its telegraph kind, and the dials that function reads. A variant of a pattern
is one more row, not new code — `massive_fan` is `fan_shot` with a wider
spread, `deathroll` is `spiral_pattern` with a denser one.

`radial`, `fan`, `barrage`, `shockwave`, `spiral`, `charge`, `pincha`,
`swipe`, `arms_rain`, `sky_slam`, `deathroll`, `summon`, `web_trap`,
`massive_fan`. Each has a telegraph rule
([Telegraph](../../CONTEXT.md)): draw the footprint, not just a
warning icon.

Two patterns need state beyond a windup timer:

- **`charge`** — introduced the `'charging'` FSM state. Windup → dash
  along `_charge_dir` → N seconds of real motion with contact damage.
- **`arms_rain`** — introduced the `select` hook on the FSM (called
  when the pattern is chosen, not at end of windup) because the ground
  markers must exist for the whole telegraph, not just the impact frame.

## Phases

`on_phase` fires at HP thresholds (defaults 66%, 33%). The **rule of two**:
each transition changes at most _two_ things — one pattern in/out plus one
numeric dial. More than that and the player has to relearn the fight
instead of adapting.

## Personality

`BossPersonality` (`mood_speed`, per-mood pattern weights, glow-per-mood,
telegraph length multiplier). `_update_mood` derives current mood from
distance / HP / frustration; `_choose_pattern` weights by
personality × mood, not `random.choice`. Mood also scales
`tail_spring.stiffness` — calm bosses look loose, cornered bosses look
tense. Zero draw code new.

## Three things you must set for a boss

- **`gen.knockback = 0`** — projectiles used to punt bosses out of their
  own approach, effectively interrupting the fight for free.
- **`boss.is_boss = True`** — not just a HUD flag. It is what buys resistance
  to interruption: a floor under `apply_slow` (a slow stack can no longer
  switch the movement patterns off) and a damped body reaction to being hit, so
  the boss reads as massive instead of staggering. Both rules are in
  [Combat](./combat.md); a boss body without this flag is a big mook that any
  Feromônio can park.
- Body scale of ~2.3× (2.3 × 1.35 for the final tier). "4×" mentioned in
  design docs is flavour text — the numbers on the wire.

## Movement Trail and the `cd_mul` rhythm signature

The FSM's per-frame `(direction, speed)` is the **Movement Trail** —
the slot that says what the boss does *between* attacks. The trail
has two bindings, with precedence **attack > phase > none**:

- The active pattern's `move` field (`PATTERNS[pid]['move']`).
- The phase kit's `moves` slot (the background between attacks).
- The default `move_reposition` (move toward the target).

Charge / burrow / grapple keep their veto.

The phase kit's `cd_mul` is the **rhythm signature** now that
`BOSS_CD_MIN` / `MAX` collapsed to near zero. A Muralha fights
relentlessly (floor); Olho-Sismico uses a higher `cd_mul` for the
long pauses of the observer. The cycle drops from ~2.1s to ~1.0s
in calm and approaches 0.75s in enraged — the cadence by overlap,
not by cutting the tell.

A Muralha's `moves=[]` is the framework's signal that the slot is
intentionally empty (the wall). Every other boss declares a slot,
and the per-boss signatures (#121-#125) fill the rich moves over
time.

See [Boss Movement](./boss-movement.md) for the concept and
[ADR-0015](../adr/0015-cadence-by-overlap-not-tell-cut.md) for the
why.

## Boss vs generic

Named bosses live in `BOSS_POOL` with overrides (patterns per phase,
`on_phase`, `emblem`, `boss_attrs`, `setup`). Tiers without an authored entry
fall back to the generic "themed species scaled up" boss. This is not a
regression — it's "no authored content yet at this tier".

## The roster

Eleven authored fights. `BOSS_TIER_POOLS` decides who is eligible where; a
tier rolls one at random from its pool, **without replacement** (see
[Round](./round.md)), so a tier with five shows you all five before repeating.

| tier | wave | pool |
|---|---|---|
| 1–3 | 5 / 10 / 15 | Rei Lagarto · Centopeiadeira · Kraken-Mor |
| 4–5 | 20 / 25 | Mãe-Escaravelho · Aranha-Rei · Serpente de Cristal · Terror Alado · Olho-Sísmico |
| 6 | 30 | A Muralha |
| 7+ | 35+ | A Muralha · ANKH |

PRIMORDIAL is not in a tier pool: `is_final` picks it directly, so wave 20 in
NORMAL is always that fight. Tiers 6 and 7 are INFINITO-only in practice —
which is why `tools/check_bosses.py` exists, because reaching them by playing
takes half an hour and `--smoke` never reaches a boss round at all.

## Rei Lagarto (tier 1 — legibility canonical, graduated for #162)

Three phases at the 66 / 33 HP thresholds, each declaration in
`king_phases()` (`lagarto/flow/boss/patterns.py`). Phase 1 is the
"aula" (lesson) from issue #123; phases 2 / 3 graduate **density +
cadence** without shortening any tell — issue #162. The 27-frame
rule owns every windup across all three phases.

| phase | patterns | cd_mul | overrides |
|---|---|---|---|
| 1.0 | `fan`, `shockwave`, `charge` | 1.00 | — (canonical) |
| 0.66 | `fan`, `shockwave`, `charge`, `radial` | 0.80 | `fan(count=3, spread=24, dmg=8)`, `radial(count=10)` |
| 0.33 | `spiral`, `shockwave`, `charge`, `radial` | 0.65 | `spiral(shots=20, turn=18, gap=0.04)`, `radial(count=10)` |

Phase 1's `pattern_dials` slot is empty on purpose; the row IS the
dial, and a future editor who adds an override gets caught by
`tools/check_king_signature.py` (the "canonical must stay untouched"
gate). Phases 2 / 3 carry `pattern_dials`; `BossAI` shallow-merges
them onto `PATTERNS[pid]` once at pattern pick time, so the
telegraph draw, the windup, the move binding and the fire call all
see the same effective dict — the override never drifts between the
footprint the player reads and the bullets that fire.

Windups (`BOSS_FAN_WINDUP`, `BOSS_SHOCKWAVE_WINDUP`,
`BOSS_RADIAL_WINDUP`, `BOSS_CHARGE_WINDUP` — all 1.1s) are untouched.
What changes is the **count** (fan 3 / radial 10 / spiral 20 shots)
and the **cadence** (`cd_mul` going from 1.00 / 0.95 / 0.85 down to
1.00 / 0.80 / 0.65). The boss gets denser and faster; the tells
never shrink. `tell_mult = {}` on `king_personality` enforces it: a
mood multiplier cannot drag a real telegraph below the floor.

## Arena

A boss may carry a `BossArena` (`lagarto/flow/boss/arena.py`): a `size`
`(w, h)` play box **centred on the boss** for the length of the fight, plus a
screen `tint`. The box is what makes an arena felt — one anchored to the world
origin would only shave the far corners off a 3200x3200 map, which the player
never reaches. A boss with no entry in `ARENAS` fights in the open world.

The arena lives for the fight only: `BossArena.apply()` installs the bounds
when the boss spawns (`_spawn_boss`) and at every HP threshold (the per-boss
`on_phase` callback for #121's shrinking corridors), and `BossArena.clear()`
drops them the moment the round transitions to `cleared` — issue #157. Without
that clear, `game.arena_bounds` would still hold the dead boss's box across
the whole `cleared` and `camp` window, and the player's `integrate()` would
clamp them inside the box they just killed their way out of. The shop door is
unreachable through a 900x640 corridor that's still painted on the world. The
adds that some bosses spawn on death (Mãe-Escaravelho's larvas) don't use
`arena_bounds` — the arena is per-boss, not per-spawn — so clearing it the
moment the round clears does not punish the surviving adds.

A Muralha has the tightest box in the game (900x640, a corridor); the
Primordial and the Terror Alado have none, because both fights are about space.

A pattern that paints the **ground** reads `game.arena_bounds` and anchors its
cells to that box — never to the world origin. `grid_of_fire` measured its grid
from (0, 0) and therefore lit the map's top-left corner while the fight happened
2 000 px away: the attack existed, telegraphed, and hit nobody. The emitter is
shared, so the same function falls back to a box of the arena's size around the
shooter when there is no arena at all.

How much of the box a grid may light is capped twice: `Game.spawn_puddle` keeps
at most 40 puddles alive in the whole world (a cell size that asks for more
loses the far side of the arena, silently), and the fire's life must stay under
the shortest interval that can reapply it — recover + the attack cooldown +
the wind-up, ~1.4 s for A Muralha — or two grids overlap and the damage stacks.
Same rule as the enemy puddles ([Enemy behaviors](./enemy-behaviors.md)), on
the boss side. `tools/check_muralha.py` asserts all three.

## Body plan vs re-skin

Two ways to give a boss its look, and the choice is not cosmetic:

- **Re-skin** — reuse a species and push `overrides` (ANKH is a golden
  `horned`). Right when the fight's identity is its behaviour.
- **Own species with its own `plan`** — right when the creature is not a
  lizard. A Muralha is `plan='fixed'` with `speed=0`; it was briefly built as
  an overridden `horned` instead, and the result was a wall that walked at the
  player.

A boss-only species must use `role='boss'`, not `role='enemy'`: the `invasao`
theme pool is `list(ENEMY_SPECIES)` and the `summon` pattern falls back to it,
so `role='enemy'` lets a normal wave roll a boss body as a mook.

Serpente de Cristal uses its own boss-only `serpente_cristal` species: a long,
legless segmented body with cyan faceted segments and four eyes. Its procedural
head and segments are canonical when optional PNG parts are absent.

## Related

- [ADR-0004](../adr/0004-boss-pool-per-tier.md) — how a tier picks a boss.
- [ADR-0012](../adr/0012-shared-pattern-emitter.md) — where the patterns live
  and why they take `dials`.
- [Tier](../../CONTEXT.md) — the slot bosses fill.
- [Round](./round.md) — the wave a boss gates.
- [Species](./species.md) — the body a boss is scaled up from.
- [Champion](./champion.md) — sibling big-enemy concept.
- [Sandbox](./sandbox.md) — spawns any boss on demand via `make_boss`.
