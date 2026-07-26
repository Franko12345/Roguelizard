# Synergy

A named combo that fires when a set of tags is present. Tags flow from
[Mutation](../../CONTEXT.md) cards, [Weapon](./weapon.md) ownership,
[Item](../../CONTEXT.md) pickups, equipped [Charm](./charm.md)s, and the
current [Character](./character.md) — all flattened into one set via
`evolution.owned_tags`.

Defined in `lagarto/combat/evolution/`.

## Twelve synergies exist

Named, each one requiring a specific tag set. Examples:

- **ARACNIDEO** — legs + venom.
- **FORTALEZA** — plates + thorns.

Full roster in `SYNERGIES`. The single set means a synergy can require
"this weapon plus that item plus this part" without caring which
subsystem contributed which tag. If a new subsystem needs to feed
synergies, it exposes `owned_tags` — do not add per-source variants of
`SYNERGIES`.

## Synergy Factor: weight, not new pool

Gungeon's Synergy Factor. Not a new rolling system — `roll_cards` already
scales cards by weight; the factor multiplies the weight of a card that
would _complete_ a synergy. Measurement: the closing card appears
**117/600** rolls with the factor vs **43/600** without. Users notice
this without noticing what changed — that's the design intent.

## Invisible synergy does not exist

Every synergy is listed in the compendium (EVOLUCOES tab). A hidden
synergy players never learn about is worse than no synergy — it turns a
build system into RNG.

## Related

- [Weapon](./weapon.md) — one tag source.
- [Charm](./charm.md) — another tag source.
- [Character](./character.md) — the starting character adds its tag.
- [ADR-0004](../adr/0004-boss-pool-per-tier.md) — for parallel: weighted
  selection with published contents.
