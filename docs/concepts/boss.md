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

## Arena

A boss may carry a `BossArena` (`lagarto/flow/boss/arena.py`): a `size`
`(w, h)` play box **centred on the boss** for the length of the fight, plus a
screen `tint`. The box is what makes an arena felt — one anchored to the world
origin would only shave the far corners off a 3200x3200 map, which the player
never reaches. A boss with no entry in `ARENAS` fights in the open world.

A Muralha has the tightest box in the game (900x640, a corridor); the
Primordial and the Terror Alado have none, because both fights are about space.

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

## Related

- [ADR-0004](../adr/0004-boss-pool-per-tier.md) — how a tier picks a boss.
- [ADR-0012](../adr/0012-shared-pattern-emitter.md) — where the patterns live
  and why they take `dials`.
- [Tier](../../CONTEXT.md) — the slot bosses fill.
- [Round](./round.md) — the wave a boss gates.
- [Species](./species.md) — the body a boss is scaled up from.
- [Champion](./champion.md) — sibling big-enemy concept.
- [Sandbox](./sandbox.md) — spawns any boss on demand via `make_boss`.
