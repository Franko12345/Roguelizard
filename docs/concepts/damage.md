# Damage Model

Player HP is **continuous** (`Player.health` / `max_health`, base 100),
drawn as a bar on the HUD (green → orange → red), alongside energy and XP.

## `hurt(game, dir, dmg)`

Takes incoming damage.

- Melee scales with enemy size (`8 + max_r*0.4`).
- Projectile ~8.
- Contact damage per enemy comes from `lizard.contact_damage(max_r,
  wave)` with the wave step. See [Balance](./balance.md).

## Healing

- Fruit +25 (base; balance changed it to 12).
- Regen: continuous, `regen` mutation gives hp/s.
- Revive at 50% for the fallen coop partner.

## i-frames

Short (`hit_flash > 0.45`). **Do not touch** — they are what keeps the
game fair.

`hurt` is also where *every* other invulnerability is expressed — one condition,
no `invuln` field: both dodges (`self.dashing or self.rolling`, see
[Dodge](./dodge.md)), being downed, and the shed timer (Muda de Pele / Casulo).
Every damage source funnels through here, so this is the only place to add one.

## Telegraphed projectiles

Spitter has a wind-up (`shoot_charge`) with particles. Projectiles are
**slow** (~230) so the player can dodge. Visual style is Gungeon-ish:
core + additive halo + trail. See `projectile.py`.

## Related

- [Combat](./combat.md) — outgoing damage from the player side.
- [Hitbox](./hitbox.md) — body sampling and head crits.
- [Health HUD](./health-hud.md) — how HP is shown for player, enemies,
  bosses, and friends.
- [Balance](./balance.md) — the wave-step for enemy contact damage.
