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

## Related

- [Nest / SpawnMark / Wave / Theme](../../CONTEXT.md).
- [Boss](./boss.md) — every 5th round.
- [Species](./species.md) — where each theme's roster comes from.
- [Camp](./camp.md) — what follows a cleared round.
