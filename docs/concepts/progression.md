# Progression

DNA persists across runs in `~/.lagarto/save.json`. Two categories:

- **`UPGRADES`** — permanent stats (health, damage, cadence, speed, XP,
  pollen).
- **`UNLOCKS`** — weapons and [Charms](./charm.md) enter the run pool.

`apply_to_player` runs at run start; `finish_run` credits DNA on death.

## Where DNA is spent

Menu → **EVOLUCAO (DNA)**. `progression.unlocked` filters
`evolution._weapon_cards`, the shop, and nest drops so an
unlocked-only pool is enforced everywhere.

## Locked entries still show up

An unlocked-only pool with hidden entries is dead progression. Every
locked charm / character / weapon appears in the compendium with its
requirement — see [Character](./character.md).

`save()` persists everything in `DEFAULT`, so a new key needs
adding once. `load()`'s validation must keep up, otherwise the key
comes back as the default silently.

## Save file schema

`~/.lagarto/save.json`. Corrupt file → tolerant load, defaults, keep
running. Never wipe. See `progression.py`.

## Visible run level

Run level has a permanent representation in the [anatomical HUD](./hud-anatomy.md).
Brain size and folds only grow as level rises; XP fluid fills within each level
and drains when the next level begins.

## Related

- [Character](./character.md) — locked characters + achievement path.
- [Charm](./charm.md) — DNA-unlocked charms.
- [Game modes](./game-modes.md) — INFINITO unlocks via `beat_game`.
- [Balance](./balance.md) — the run-side stats DNA scales on top of.
