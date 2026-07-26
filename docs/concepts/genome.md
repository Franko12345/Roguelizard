# Genome

The bag of numbers that fully describes a creature. Every enemy, prey,
champion, boss, and playable character is a `Lizard` built from one.

Defined in `lagarto/creatures/genome.py`. Constrained by
[ADR-0001](../adr/0001-genome-is-the-creature.md).

## What it contains

Body shape and gait:

- **`size`, `length`** — physical dimensions of the [Spine](./spine.md).
- **`plan`** — `'normal'` (spine + [Legs](./leg.md)), `'segmented'`
  (centipede), `'tentacle'` (kraken). Forks `rebuild_body` and `draw`.
- **`radial`** — spider layout: legs use `rest_angle` instead of the
  partner-based diagonal gait.
- **`legs`** — how many.
- **`weight`, `linear_damping`, `angular_damping`** — inertia dials
  (default `1.0/0/0` = old behaviour bit-for-bit). Set by
  [species](./species.md) that want it; bosses force a minimum.

Colour and organs:

- **`hue`, `sat`, `val`** — HSV colour. `random_variation` jitters these
  at spawn so identical species look different.
- **`eyes`, `horns`, `spikes`, `plates`, `fins`, `wings`** — number-per-
  part; drawn additively by [`parts.py`](./parts.md).
- **`tail`** — `'normal' | 'club' | 'sting' | 'fin'`. Player-visible;
  charms flip it (e.g. the `clava` charm sets `tail='club'`). The club
  tail is charm-only since issue #22 — see [Charm](./charm.md).

Behaviour and role:

- **`behavior`** — which AI branch to run. See
  [Species](./species.md) for the roster.
- **`diet`** — tuple of prey categories. Predator/prey ecology in
  `game.nearest_threat`.
- **`hp`, `speed`** — base combat stats. Champions and bosses scale
  these; the base stays modest.

Meta:

- **`grants`** — a part id awarded when a portador is eaten or
  dash-killed by the player. Feeds evolution (rare, ~12% on dash-kill).
- **`knockback`** — multiplier <1 for bruisers that must not be
  interrupted (kraken 0.28). Zeroed for [bosses](./boss.md).
- **`split_gen`, `split_count`** — DIVISOR modifier fields. Non-zero
  means "split on death"; the count generalises the old 2-copy default.

## `random_variation`

Every spawn passes through `genome.random_variation(base)` — small
hue/sat/val jitter, size jitter, sometimes leg-count jitter. Two of the
same [Species](./species.md) never look the same. Sim-relevant fields
are jittered, but never past a range that would break the AI branch.

## `rebuild_body(keep_pose=True)`

Recomputes _only_ the genome-derived fields — spine, legs, `max_r`,
`max_speed`. Never re-`__init__`; that would erase hp, weapons, level,
and the champion/modifier stack. See
[ADR-0001](../adr/0001-genome-is-the-creature.md) for why the
`_KEEP` list disappeared.

## Related

- [Spine](./spine.md) — the physics chain built from `size`/`length`.
- [Species](./species.md) — genome templates that fill this shape.
- [Character](./character.md) — playable genomes.
- [Champion](./champion.md) — variants and modifiers that mutate a
  spawned genome in place.
