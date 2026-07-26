# Character

A player-selectable [Genome](./genome.md) template plus one exclusive
mechanic. Four characters exist. Zero new art was written to add them —
the same [Parts](./parts.md) drawing pipeline runs for each.

Defined in `lagarto/creatures/characters.py`. Constrained by
[ADR-0001](../adr/0001-genome-is-the-creature.md).

## Roster

| Character | Body | Exclusive mechanic |
|---|---|---|
| **LAGARTO** (default) | standard | `rerolls_per_level`: rerolls the level-up card hand (`R`) |
| **VIBORA** | long, no legs | `weapon_cap=2` + fast strong whip — the cap _is_ the mechanic |
| **COURACADO** | large, plated | `can_dash=False` + armour + spikes + `knockback_immune` |
| **LARVA** | tiny | `characters.larva_growth`: grows every N kills, 1 → 6 weapon slots |

Two are locked at start: VIBORA and COURACADO cost DNA in the menu;
LARVA unlocks on the wave-8 achievement.

## Where the shape comes from

`char.apply(self)` is the **last** thing `Player.__init__` calls. It
reads `armor`, `thorns`, `max_health`, `whip_cooldown` — all declared
above the call, so a character can override them safely.

`Character.apply` is **1-arg** (`apply(player)`), not 2-arg like
`Charm.apply` / `Item.apply` which take `(player, game)`. Characters
run in `Player.__init__`, before `Game` exists, so there is no `game`
to pass. This is a documented asymmetry — do not "unify" it by passing
`None`: that either bypasses the contract or (worse) reorders stats
relative to `progression.apply_to_player`, silently changing
DNA-scaled `max_health` for multiplicative characters.

Body regeneration goes through `Lizard.rebuild_body(keep_pose=True)`,
_not_ `__init__`. Previously the only path to a new body was
`__init__`, which erased hp/weapons/level/aggro — champions kept an
11-entry `_KEEP` list to remember what to restore. That whole class of
bug disappeared when `rebuild_body` was extracted.

## Colour comes from the slot, not the character

Two players picking the same character in coop still look different.
`Player.__init__` passes `colorset[0]` explicitly, overriding whatever
hue the character genome carries. If a character defined its own
colour, both slots would end up identical.

## Locking

`UNLOCKS` entries with `kind='character'`. `cost=None` = achievement-
only, never for sale. Locked characters **appear in the character list**
with the requirement — invisible rewards are not rewards. See the
`check_achievements` path in `finish_run`.

## Related

- [Genome](./genome.md) — what a character _is_.
- [Champion](./champion.md) — the enemy-side equivalent of "genome +
  named exclusive".
- [Weapon](./weapon.md) — VIBORA's cap and LARVA's growth pass through
  weapon slots.
