# Species

A named [Genome](./genome.md) template plus metadata: role, xp reward,
`grants`, diet. `species.make()` spawns a randomised variation.

Defined in `lagarto/creatures/species.py`.

## Roster

**Prey** (`role='prey'`, `diet=()`):

- **grazer** — chunky, slow, herbivore. Standard xp anchor.
- **critter** — small, skittish, fast.
- **frog** — hop AI, gives player the wind-up + `leg_pull` demonstration.
- **fish** — swim behaviour, water-tile bound.

**Enemies** (`role='enemy'`, `diet=('prey',)`):

- **runner, tank, snake, horned, spiky** — melee variants; each with a
  different combination of parts. Tank is heavy (`weight=2.5`); snake is
  long.
- **spider** — `radial=True`, `lunge` behaviour.
- **spitter, scorpion** — ranged and sting-based; scorpion applies slow.
- **wasp, bomber, gunner, venomer** — phase-2 arrivals that each attack
  a different player habit (see [CLAUDE.md](../../CLAUDE.md) hábito table).
- **sniper (ANTECIPADOR), mortar (MORTEIRO)** — the two habits the
  [Rolamento](./dodge.md) created: rolling on reflex, and charging in. See
  [Enemy behaviors](./enemy-behaviors.md).
- **centipede** — `plan='segmented'`, `behavior='burrow'`.
- **octopus** — `plan='tentacle'`, `behavior='grapple'`, `weight=3.0`.

Each entry declares `hp`, `speed`, part counts, and — when a part should
be transferrable to the player — a `grants` field. A species that shoots also
declares `shot`: the [emitter](../../CONTEXT.md) pattern it fires plus that
pattern's dials, e.g. `shot=dict(fn=emitter.fan_shot, count=1, spread=0, …)`.
Widening the CUSPIDOR into a cone, or swapping it for a ring, is that dict — no
AI code. Champions and bosses
[modify](./champion.md) genome fields on top of these bases.

## `make()`: randomised spawns

```python
gen = species.make('spider')  # returns Genome, not Lizard
```

`make` returns a fresh `Genome` with `random_variation` applied. Two
"spiders" always look different. Sim-relevant fields jitter within
ranges the behaviour tolerates; visual fields jitter more freely.

## Extending the roster

1. Pick a base genome shape (`plan`, `radial`, part counts).
2. Pick a `behavior` (already-implemented dispatch — inventing a new one
   is not "add a species", it's "add an AI"). A shooter also needs `shot`.
3. Add the entry to `SPECIES` with `hp`, `speed`, `grants`, `diet`.
4. Add to the theme table (`THEMES` in `rounds.py`) if it should appear
   in rounds.
5. Add to [`CONTEXT.md`](../../CONTEXT.md)? Only if the name introduces a
   new domain term. "runner_v2" does not; "centipede" did.

## Related

- [Genome](./genome.md) — what the template fills.
- [Champion](./champion.md) — how a species can promote at spawn.
- [Boss](./boss.md) — how a species can become a boss.
- [Round](./round.md) — the wave theme that pulls species names.

## Boss identity: `Genome.boss_id` (issue #159, ADR-0003)

A `Genome` may carry an optional `boss_id` — the boss slot id from
`BOSS_POOL`, set by `_spawn_boss` after `make_boss`. The field is `None`
for prey, common enemies, and champions; it is only populated for
authored bosses. It exists for **one** reason: to gate the
`boss_part(boss_id, part_name)` override path in `parts.draw_all`. No
other code reads it.

The override path is per-issue scoped: the PNG, when present, paints
*on top* of the procedural body. The boss's silhouette, motion,
hit-test, and physics stay procedural. See
[ADR-0003](../adr/0003-zero-assets-with-png-fallback.md) and
[Parts](./parts.md#optional-asset-overrides-for-bosses-159-adr-0003) for
the rule.
