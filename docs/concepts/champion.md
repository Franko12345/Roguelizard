# Champion

A named variant of a [Species](./species.md) whose visual trait _explains_
its ability, plus an orthogonal **modifier** that can stack on top. Model
comes from Rain World's lizard subraces.

Defined in `lagarto/creatures/champions/`.

## Variants: name earns the trait

- **FILHOTE** — tiny, 1 HP, very fast. `CHAMP_FILHOTE_SPEED` sits between
  walk and dash: catches you walking, loses you dashing.
- **ALFA** — antennae because it commands the pack.
- **ESPECTRO** — pale because it ambushes. **Camouflage covers the
  label too**: the name and aura hide with the body.
- **SALTADOR** — tail-club because it launches from the club.
- **APICE** — the apex of a species.

The rule: the visual difference must be the mechanic. Adding a variant
whose trait is just "more HP" fails this test and should be a modifier
instead.

## Modifiers: orthogonal, purely mechanical, stackable

- **BLINDADO** — armour.
- **GIGANTE** — larger.
- **EXPLOSIVO** — explodes on death.
- **DIVISOR** — splits into `split_count` smaller copies on death.

An enemy can be `APICE BLINDADO` — a different fight from `APICE` with no
new behaviour line.

## Traps this concept walked into

Documented so nobody repeats them:

1. **`_rebuild` used to call `__init__`, which reset everything.** Meant
   metadata from `species.make` (species/xp/score/grants/hp) reverted to
   defaults, and stacking a modifier erased a previously-applied
   variant. `keep_pose=True` on `rebuild_body` is the fix. See
   [ADR-0001](../adr/0001-genome-is-the-creature.md).
2. **Variant speed is absolute, not a multiplier.** `max_speed` is
   `165 * (0.85 + 0.4/size) * speed`; shrinking already accelerates.
   Multiplying on top gave 5.75× the player's speed (undodgeable). And a
   "tank filhote" via multiplier would be _slower_ than the player,
   negating the only thing "filhote" means.

## DIVISOR: never mutate a list you're iterating

`die()` is called from inside `_collisions` / `_update_projectiles`,
which iterate `game.enemies`. Appending to `enemies` there would let the
same dash hit the fresh children in the same frame. The children go into
`game.pending_enemies` and are drained once per step, after
`_collisions`. `split_gen` limits depth: parents spawn with `split_gen=1`,
children inherit `split_gen-1`, `0` stops.

## Related

- [Species](./species.md) — what the champion is a variant of.
- [Boss](./boss.md) — the other big-enemy concept; distinct because a
  boss gates the round while a champion lives inside one.
- [Genome](./genome.md) — where variant traits and modifier flags land.
