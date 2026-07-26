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
- **centipede** — `plan='segmented'`, `behavior='burrow'`.
- **octopus** — `plan='tentacle'`, `behavior='grapple'`, `weight=3.0`.

Each entry declares `hp`, `speed`, part counts, and — when a part should
be transferrable to the player — a `grants` field. Champions and bosses
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
   is not "add a species", it's "add an AI").
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
