# Round

The unit of play between camps. `RoundManager` runs a themed wave:
enemies drip from **Nests** via **Spawn Marks** until the budget is spent,
then `cleared` opens the [Camp](./camp.md).

Defined in `lagarto/flow/rounds.py`.

## Themes

Each round picks a theme from `THEMES`:

- **enxame** — many small threats.
- **cuspidores** — ranged pressure.
- **tanques** — few, heavy targets.
- **aranhas** — spider-heavy.
- **invasao** — from all sides.
- **toca** — subterranean; centipedes.

Themes announced by banner (`draw_banner`). Each theme names a `cap`
(concurrent enemy limit) and a `budget` factor that scales with wave.

## Nest, Spawn Mark, Wave

- **Nest** — destructible POI with a glowing mouth that pulses before
  emission. Killing nests cuts the fill rate. Nests drop items and
  pollen.
- **Spawn Mark** — the growing telegraph on the ground that says
  "something is arriving here". Never spawns on the player.
- **Wave** — the integer index (`rounds.wave`).

## Boss rounds

Every `BOSS_EVERY` (= 5) waves, `_spawn_boss()` runs. The round only
`cleared`s when the boss dies, and the music switches to `boss` in
`app.py`. Selection: see [ADR-0004](../adr/0004-boss-pool-per-tier.md).

## `cleared` → camp

`rounds.state = 'cleared'` triggers `game._enter_camp()`. Enemies stop
spawning, existing ones are cleaned up, the clearing is generated where
the last enemy fell, and control passes to [Camp](./camp.md).

## Difficulty curve: four functions, one shape

Every wave-based dial lives in `rounds.wave_hp_bonus` / `wave_speed_mul` /
`wave_budget` / `wave_cap`, with the knee constants in `config` (`WAVE_*`).
They used to be inline at each use site, which meant the shape of the curve
was not written down anywhere.

Each curve is **byte-identical to the old linear one below its knee**. That
is deliberate: this fixed a mid-game snowball, and the early game should not
be changed to solve a mid-game problem. Past the knees:

| wave | hp bonus | speed | live cap |
|---|---|---|---|
| 10 | 7 → 7 | 1.20 → 1.25 | 6 → 7 |
| 15 | 10 → 21 | 1.30 → 1.45 | 6 → 9 |
| 20 | 14 → 44 | 1.40 → 1.65 | 6 → 10 |

`tools/check_difficulty.py` asserts both halves — waves 0–7 unchanged, and
the late game actually ramping and staying monotonic.

## A boss you already fought should not be next

`_draw_boss_id` samples the tier pool **without replacement**: a shuffled bag
per pool, refilled only once empty. So a tier with five authored bosses shows
you all five before repeating any. The bag lives on the `RoundManager`, which
is constructed per `Game`, so it dies with the run.

`_spawn_boss` keeps who/where and the spawn juice; the body itself is built
by `make_boss(game, boss_id, tier, pos, is_final)`, which the
[sandbox](./sandbox.md) reuses so there is no second way to build a boss.

## Related

- [Nest / SpawnMark / Wave / Theme](../../CONTEXT.md).
- [Boss](./boss.md) — every 5th round, and the per-boss arena.
- [Species](./species.md) — where each theme's roster comes from.
- [Camp](./camp.md) — what follows a cleared round.
- [Balance](./balance.md) — the passes this curve came out of.
- [ADR-0004](../adr/0004-boss-pool-per-tier.md) — how a tier picks a boss.
