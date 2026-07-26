# Hitbox

Whole body is hittable; the **head is the weak point**.

Before, damage only tested a single circle at the head (`e.pos` +
`e.max_r`), so a 322 px snake was hittable in ~5% of its body — the
player felt "I hit it but it didn't count".

## `Lizard.body_points()` + `hit_test(pos, radius)`

- `body_points()` samples the [Spine](./spine.md) (joints 0, ¼, ½, ¾,
  end, with the local radius). Same pattern as `collision._samples`.
- `hit_test(pos, radius)` returns `None` / `'body'` / `'head'`.

Used by **all** damage sources:

- Dash — `game._collisions`
- Projectiles — `_update_projectiles`
- Auras / orbitals / puddles — `weapons._enemies_in`

## Head crit

`config.CRIT_MULT` triggers on a `'head'` return. Effects:

- Golden spark
- `"CRITICO!"` popup via `game.crit_fx`

## Weak-point highlight (`AILizard._draw_weakpoint`)

A **soft halo** in the body's colour lightened, drawn **before** the
body (that is why `draw()` calls it before `super().draw`) — glows
around the silhouette without covering the eyes.

It was once a reticle / crosshair: read as UI stuck on the creature.
Keep it organic — colour and glow, never aim marks.

## Denying the crit, and softening a hit

Two attributes on the creature, both unset by default, so every creature
that does not use them behaves exactly as before:

| | |
|---|---|
| `eye_shielded` | `hit_test` returns `'body'` for what would be a head hit, so the caller never sees the weak point. |
| `dmg_taken_mult` | Multiplies incoming damage in `take_hit`. |

They exist for the Olho-Sísmico's blink (see
[Body plan](./body-plan.md)): while the eye is shut the crit is off the
table and a hit that lands anyway does 25%. Written as generic dials rather
than a boss-specific branch in `hit_test`, because `hit_test` is the single
choke point every damage source funnels through and one boss does not get to
put an `if` in it.

## Related

- [Combat](./combat.md) — dash / whip hit rules that use this.
- [Weapon](./weapon.md) — auras and puddles that use this.
- [Health HUD](./health-hud.md) — where the resulting damage shows up.
- [Spine](./spine.md) — the sample source.
- [Body plan](./body-plan.md) — the Olho-Sísmico blink that uses both dials.
