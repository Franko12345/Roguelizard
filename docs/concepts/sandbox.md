# Sandbox

The dev-only debug mode: a real `Game` you drive by hand to spawn any
entity and watch it behave in the actual world, collision, combat, HUD,
and camera. Reached only with `python lizard_game.py --sandbox`.

Not a player-facing [Mode](../../CONTEXT.md) — see also
[Game modes](./game-modes.md) for the two real modes.

## Gating

- `--sandbox` is parsed in `app.main` next to `--smoke`. No menu entry,
  no hidden button — a flag nobody passes on a normal run.
- **One player** only. The coop seams exist, so `--sandbox 2` is a
  trivial future add, but today the sandbox always builds a single
  player as the test subject.
- The [Round](./round.md) auto-spawner is frozen: with `mode == 'sandbox'`
  the wave machine never advances on its own. Waves only fire when you
  ask for one.

## The overlay

A left-docked panel drawn on top of the live game, driven by the mouse.
Backtick (`` ` ``) or `F1` toggles it open/closed. With the panel closed
the game runs normally and armed spawn clicks still land; a dim `` ` sandbox``
hint sits in the corner. The world keeps simulating either way.

The category row across the top switches what the panel lists:
**Boss** / **Champ** / **Spec** / **Pick** / **Rnd** / **Equip** /
**Loja** / **Dbg** / **Pers**. Dropdowns enumerate the real registry ids,
so you never type a name by hand.

Long lists are scrollable. Each category keeps its own offset on
`Sandbox.scroll`, and the mouse wheel over the panel scrolls the active
list (one notch ≈ one row). The list is clipped to the visible window
between the panel's top and the nearest footer (round/store) or the
panel bottom, so the full registry stays reachable even when a single
category holds more rows than fit. Switching category or loadout pool
resets that list's offset to 0; the champion two-step keeps the species
offset on a separate slot so backing out of a champion pick does not
clobber it.

## Spawn (click-to-place, sticky)

Picking a [Boss](./boss.md), [Champion](./champion.md),
[Species](./species.md), or pickup **arms** a spawn. The next left-click
in the world drops it there. It stays armed — each click drops another
until you cancel with right-click or `Esc`. A HUD line names what is
armed. A Champion needs two clicks: the champion first, then a species to
apply it to.

A hand-spawned Boss is mirrored onto `rounds.boss`, the same field
`RoundManager._spawn_boss` sets, because that is what the big health bar at
the top reads. Skipping the mirror leaves the boss with **no** bar at all —
the small over-head bar declines to draw for anything with `is_boss` set, on
the assumption that the big one is already up.

## Round control

The **Rnd** category picks a [Round](./round.md) theme and scrolls a wave
number, then **START** fires that theme+wave through the real wave machine
(the wave alone dictates budget, tier, and boss-every-fifth). **RESET**
empties the scene and returns the machine to a fresh intermission without
touching the player — position, HP, loadout, and level are the subject of
the test, so they are left alone.

## Loadout and store

- **Equip** grants any [Weapon](./weapon.md), [Item](./item.md),
  [Charm](./charm.md), or mutation ([Evolution](./evolution.md)) straight
  to the player for free, through the same grant APIs the real game uses.
- **Loja** stages the real [Camp](./camp.md) shop: a catalog of the native
  offers plus any weapon/item/charm you select (specific ids or a random
  N), with [Pollen](../../CONTEXT.md) set sky-high so the real buy path
  never blocks on cost. Buying then runs the untouched camp flow. The
  native offers come from `state_camp._roll_shop(game)`, a module
  function taking the game — the sandbox is one more caller of it, not a
  second way to roll a shop.

## Debug menu

The **Dbg** category lists the debug staples:

- **God mode** (toggle) — the player ignores damage.
- **Kill-all** — clears enemies, boss, hostile projectiles/puddles, and
  the round's nests/marks; keeps prey, pickups, friends, and the player.
- **Pause-AI** (toggle) + **Step** — freezes enemy/boss updates so you can
  walk around and inspect a pose. Step advances the whole sim exactly one
  fixed tick, to leaf through the procedural animation frame by frame.
  `.` steps from anywhere, panel open or not.
- **Save preset** / **Clear preset** — see below.

**Pers** rebuilds the player as any [Character](./character.md), with its
own starting weapon and body.

## Launch preset

Save writes the live scene to `~/.lagarto/sandbox.json` (character,
toggles, hand-spawned entities as `(kind, key, pos)`, loadout, active
round descriptor, generated store) through the same atomic write pattern
as the settings file. Clear deletes it.

At `--sandbox` launch a present preset is replayed automatically through
the same spawn/grant/round/store paths the overlay uses; with no preset
the sandbox opens idle. A preset is dev-authored and may outlive the ids
it names — a stale entry (a weapon or species removed since the save) is
skipped with a `[sandbox]` warning printed to the console rather than
crashing the launch.

## Related

- [Running](./running.md) — the `--sandbox` flag alongside `--smoke`.
- [Round](./round.md) · [Boss](./boss.md) · [Champion](./champion.md) ·
  [Species](./species.md) — what the spawner and round control invoke.
- [Camp](./camp.md) — the shop the store stages.
- [ADR-0010](../adr/0010-single-file-per-module.md) — why the whole
  feature lives in one deletable module.
