# Charm

A permanent slot the player fills at the [Camp](./camp.md) shop. Persists
across level-ups within a run. Costs 150 pollen.

Defined in `lagarto/combat/charms.py`.

## What charms do

Each charm sets a genome or player field for the run. Some overlap with
[Mutation](../../CONTEXT.md) cards — the difference is charms **do not
compete** with level-up choices. A charm buys the trait without spending a
card slot.

- **`clava`** — sets `tail='club'`. See [Parts](./parts.md) for the
  damage/knockback multipliers. Explicitly moved to charms because it
  should not appear on the level-up card tree.
- **`dardo`** (Lingua-Dardo) — the tongue also fires a projectile, the player's
  only aimed shot. Charm and not a card for the same reason as the clava: it
  rewrites a verb, and that has to be a decision. See
  [Combat](./combat.md#lingua-dardo--the-one-aimed-shot).
- **`antenas`, `presas`, `olhos`, `carapaca`, `espinhos`, `asas`,
  `glandula`, `nectar`, `ferrao`** — see `charms.CHARMS`. Each has a
  distinct icon (`icons.draw` — the ferrão charm shares the id with the
  ferrão weapon, so the same PNG covers both).

## Slots

`C.CHARM_SLOTS` = number of concurrent charms. The shop UI arranges the
grid one column per slot; navigation only leaves a column at the ends
(`camp_move_charm` returns `False` mid-column).

## Unlocking new charms

Not every charm ships in every run. `progression.unlocked` filters
`charms.CHARMS` by DNA-spent entries. A locked charm still appears in the
list with its requirement — see the "invisible rewards are not rewards"
rule on [Character](./character.md).

## Related

- [Camp](./camp.md) — where charms are bought.
- [Parts](./parts.md) — what body change a charm produces.
- [Pollen](../../CONTEXT.md) / [DNA](../../CONTEXT.md) — the currencies
  charms cost (pollen to equip, DNA to unlock).
