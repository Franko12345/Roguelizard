# Item

An artifact that either fires on a button (**active**) or rewrites a
mechanic (**passive**). 4 actives + 16 mechanic-changing passives.
Quality 0-4, drawn from pools by origin (level/shop/nest/boss).

Defined in `lagarto/combat/items.py`.

## Why the split matters

Stat passives stay in [Mutation](./evolution.md) cards. `items.py`
carries the ones that **change a verb** — Isaac's rule: the memorable
items rewrite something (Spirit Sword swaps the tear for a sword), and
"+10% damage" is forgettable by construction. 16 mechanic-changers
against 4 actives.

## Actives fill a real socket

`Player.ability`/`ability_cd` were declared and decremented long before
anything used them — an empty socket. Actives filled it. Charge is by
**kill count**, which ties the resource to the combo loop the game
already runs.

**Charge counts in INTEGERS.** Summing `1/14` fourteen times gives
`0.9999999999999998`; the item read "full" on screen and refused to
fire. Fractions exist only for the ring.

## One hook, one place

- `Retaguarda` lives in `game.spawn_projectile` (the choke every
  projectile crosses — per-weapon would be 8 copies).
- `Adrenalina` lives in `Player.damage_mult()`, read by dash, whip, and
  weapons.

## Order matters for self-consuming effects

`Presa Marcada` marked the enemy _before_ the dash's own `take_hit`, so
the crit was spent on the hit that created it — the item did nothing
observable. Mark **after**.

## Related

- [Evolution](./evolution.md) — the level-up card system this sits next to.
- [Synergy](./synergy.md) — items feed `owned_tags`.
- [Weapon](./weapon.md) — actives and passives layer on top of weapons.
