# Weapon

An automatic attack the player owns at a level. Fires every frame via
`weapons.WEAPONS[id].tick(...)`. There are 9 weapons. A player caps at
6 equipped ([VIBORA](./character.md) caps at 2 — its exclusive
mechanic).

Defined in `lagarto/combat/weapons/`. Damage scaling constrained by
[ADR-0008](../adr/0008-might-scales-all-damage.md).

## Global stats

Passives (from [Mutation](../../CONTEXT.md) cards and DNA) scale every
weapon:

- **`might`** — damage. Also scales dash and whip. See
  [ADR-0008](../adr/0008-might-scales-all-damage.md).
- **`area_mult`** — radius/reach.
- **`cooldown_mult`** — cadence.
- **`amount`** — extra projectiles or orbitals.

## The 9 weapons

| ID | Kind | Notes |
|---|---|---|
| Cuspe | projectile | starting weapon |
| Ferrão | homing | curved in `game._update_projectiles` |
| Teia | slow | applies `apply_slow` |
| Nuvem de Esporos | aura | tick DPS via `AILizard.damage` |
| Feromônio | slow aura | non-damaging crowd control |
| Sopro | knockback aura | pushes on tick |
| Enxame | orbitals | draws on `layer='over'` |
| Ácido | ground | drops `Puddle` on nearest **distinct** enemy |
| Torreta | deployable | plants a body instead of firing — see [Deployable](./deployable.md) |

Every weapon has a `levels` list with a per-level `desc` shown on the
card. What each level _does_ is specific, not "+10% damage".

## Fractional damage (`AILizard.damage`)

Auras / orbitals / puddles tick fractional damage into an accumulator
that keeps the fractional remainder. **`.damage()` is not a rate
limiter** — the caller must multiply by `dt`, otherwise it delivers
60× at 60Hz. Audited: spores, sopro, enxame, puddle all multiply.
The `dmg` field on Enxame and Ácido is _DPS_, not per-hit damage —
easy to misread when balancing.

## Ácido specifically

The multiplier `amount` used to mean "stack in the same spot": all
puddles fell on the same target because `Ácido.tick` re-queried
`nearest_enemy` inside the loop, without the world advancing. 60 px
spread against ~80 radius = near-complete overlap; and puddle `life`
was longer than cooldown, so they compounded. Puddles now aim at
**distinct** enemies and `life < cooldown`. Measured single-target at
level 5: acid 18.6, spores 23.4, swarm 18.5.

## The one that spits a body

`Torreta` spends its cooldown on a creature rather than on a projectile: an
`AILizard` of the stationary `turret` kind, planted where the player is
standing. It is a weapon and not a card or a charm because
`Weapon.tick(player, game, dt, st, level)` already means "act on a cooldown, by
yourself", and because the four global stats above scale the whole build with
nothing new added — `amount` plants an extra turret, `cooldown_mult` plants
more often, `might` arms it and `area_mult` extends its sight.
See [Deployable](./deployable.md).

## Layers

- **`layer='under'`** — auras drawn behind the body.
- **`layer='over'`** — orbitals in front.

## Related

- [ADR-0008](../adr/0008-might-scales-all-damage.md) — Might touches
  weapons _and_ dash/whip.
- [Charm](./charm.md) — the whip and dash also pay in the same
  currency, plus the tail-club charm.
- [Synergy](./synergy.md) — how weapons combine with parts and items.
- [Character](./character.md) — VIBORA cap, LARVA growth into slots.
- [Deployable](./deployable.md) — the Torreta, the one weapon whose output is
  a creature.
