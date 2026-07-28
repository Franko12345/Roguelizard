# Deployable

Something you leave on the ground that acts on its own. One concept, three
presentations: **turret** (fires from where it stands), **trap** (fires on a
trigger) and **persistent pet** (walks). Only the turret — the **Torreta** —
exists today; the other two are named here so nobody invents a second word for
them.

A Deployable is not a new entity type. It is a creature with a position, health
and a tick, so it is an `AILizard` like everything else that moves in this game
(and, in this one case, like the one thing that does not).

## Why it matters

Every level-up card is a scalar — more damage, more area, more shots. A
Deployable is the first choice whose consequence stays on the field: the weapon
is automatic, so what you decide is **where you were standing** when the
cooldown closed.

## Torreta

The first one. Lives in `lagarto/combat/weapons/torreta.py`, because
`Weapon.tick(player, game, dt, st, level)` already means "do something on a
cooldown, by yourself" — it just spends that cooldown on a body instead of a
bullet. Not a [Charm](./charm.md) (3 slots, one choice, no stacking) and not a
new [Card](../../CONTEXT.md) (`amount` already _is_ the summoning card).

| Piece | Where it comes from |
|---|---|
| The body | `AILizard(pos, 'turret', …)`, genome built in the weapon |
| Standing still | `genome.speed = 0` (`steer` early-outs) and the `turret` branch never picks a direction |
| Not being shoved | `genome.knockback = 0`, plus `collision._samples` skips it entirely — the same "absent from the whole system" treatment flyers get |
| The shot | `genome.shot` = an [Emitter](../adr/0012-shared-pattern-emitter.md) pattern + dials, exactly like every other shooter |
| Friendly bullets | one dial, `hostile=False`, read in `emitter._launch` ([ADR-0014](../adr/0014-bullet-colour-encodes-side.md)) |
| Dying | it has `hp`; enemy contact goes through `AILizard.take_hit` and `die` |
| Its list | `game.friends`, which already updates, draws and buries the dead |

### It is a target, not a damage stat

The distinctive work is the taunt, not the damage: when the turret fires at an
enemy it takes that enemy's aggro, the same two lines the egg-hatched ally uses
when it lands a hit (`foe.aggro = self; foe.aggro_t = C.AGGRO_TIME`). With ~100
bullets on screen a body that redirects attention is worth more than DPS — the
turret buys the space, the [Rolamento](./dodge.md) spends it.

That is also why it dies to enemy fire instead of expiring on a timer: a
Deployable that always dies the same way makes _where_ you planted it matter
less, and a cap with no death would mean the horde can never remove your
defence. Balance therefore has two dimensions (its damage against its health),
on purpose — that is the dimension that gives the enemy counter-play.

### The four passives scale the whole build

No new registry, no new card, no new charm: the global stats already read by
every [Weapon](./weapon.md) mean the obvious thing here.

| Passive | On a normal weapon | On the Torreta |
|---|---|---|
| `amount` | +1 projectile | **+1 turret** per cast |
| `cooldown_mult` | fires faster | **plants faster** |
| `might` | +shot damage | **the turret hits harder** |
| `area_mult` | +area | **the turret sees further** |

`might` and `area_mult` are baked into the turret's dials when it is planted: a
body already on the ground keeps the stats it was built with, and a card picked
afterwards shows up on the next one.

### Where it lands

At the player's own position when the cooldown closes — weapons in this game do
not aim ([Combat](./combat.md)), and giving this one a cursor would make it the
single skill-check in an automatic arsenal. Several at once ring the player so
`amount` widens the emplacement instead of stacking bodies on one point.

## Not done yet

- **Trap** — the cheapest next cut: `Puddle` already has a radius, a life, a
  tick and a drawing; what is missing is a trigger.
- **Persistent pet** — the egg-hatched ally without its `life` timer, plus a
  role of its own.

## Verification

`tools/check_turret.py` plants one and asserts it does not move, fires through
the emitter with `might` applied, answers to `amount`, dies to an enemy and
leaves `game.friends`, and that the enemy's aggro transferred to it.

## Related

- [Weapon](./weapon.md) — the weapon that plants it.
- [AI](./ai.md) — the `turret` kind in the dispatch.
- [Combat](./combat.md) — aggro, contact and separation.
- [Projectile](./projectile.md) — what leaves its mouth.
- [ADR-0012](../adr/0012-shared-pattern-emitter.md) — the shared emitter that
  makes "a creature that shoots anything" free.
