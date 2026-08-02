# Camp

The physical clearing between [Rounds](./round.md). Two modes on the
same walkable state.

Constrained by [ADR-0005](../adr/0005-camp-is-a-physical-clearing.md).

## Two modes

- **`camp['mode'] = 'field'`** — WASD/stick walks around. Camera follows.
  Doors and the beetle tent are POIs the player can approach.
- **`camp['mode'] = 'shop'`** — menu open. Frozen world underneath.
  ESC / B closes the shop and drops back to field.

`app._camp_shop_open` gates whether menu input or WASD owns the frame.

## POIs in the clearing

- **Beetle tent** — the shop. Touching it opens `'shop'` mode.
  Contents: heal, max-HP, might, [Charm](./charm.md), egg. Charm starts
  at 150 pollen; the rest are cheap. See _Prices persist_ below.
- **Three doors** — each shows a theme + bonus (heal / pollen / card).
  Crossing one commits — `_apply_route` calls `rounds.request_next(theme)`.

## Drops from the sky

Each POI **falls from `CAMP_DROP_H` above the ground** with an
ease-in that accelerates into impact. `_camp_impact` fires
shake + dust + sparks + a ring on landing. A **growing shadow** on the
ground telegraphs where it will land. Interaction is locked until the
POI touches the ground (`tent_landed` / `dr['landed']`) — entering a
mid-air door was a real bug.

## Prices persist for the whole run

Buying an item multiplies its price by `C.SHOP_PRICE_MULT` (1.25), and
that price **stays raised in every later camp**. The camp dict is thrown
away when you leave the clearing, so the raised price lives on
`Game.shop_prices` (`{item name: cost}`, per run) and `_roll_shop` reads
it back when it builds the next tent. Buying nothing keeps an item at
its base price forever.

It used to be 1.6× stored in the throwaway camp dict, which reset every
clearing — Nectar was permanently 12 pollen and cheap healing was
infinite. Persisting the price is why the step per purchase got gentler:
it now compounds across a whole run instead of one visit.

## Shop is choice, not toll

Walking straight to a door and skipping the tent is legal. The tent has
to earn the visit. `reopen_cd` is just a debounce after `camp_close_shop`
— it stops the same frame that closes the shop from also counting as an
"encoste". The real open gate is the edge detector (`was_outside_tent`):
the shop fires only on the OUT→IN transition of the radius (#174). You
can stand on the tent, close, wait past the cooldown, walk around inside,
and none of that reopens the shop on its own — you must leave the radius
and re-enter. Closing during drop-in is _not_ blocked — the pick
absorption (`self.pick`) is the only lock, and only for its ~0.36 s
window.

## Shop offers declare their effect (issue #140)

The five beetle-shop offers are dicts in `_roll_shop` (see
`lagarto/game/state_camp.py`). Each offer may carry a declarative
`effect` triple: `(stat, mode, amount)` where:

- `stat` — a `Player` attribute (`health`, `max_health`, `might`,
  `cooldown_mult`, …)
- `mode` — `'add'` (sums) or `'mult'` (multiplies)
- `amount` — the same number the real effect function (`fn`) uses

`effect=None` means the offer has no numeric preview (Charms, Ovo de
Amigo). The UI skips the delta line for those.

The function `preview_delta(offer, player)` returns `(stat, cur, pred)`
or `None`. It is pure — no side effects, no I/O — so the focused-card
overlay can call it on every frame for every player. In 2P the overlay
shows both deltas side by side (the purchase affects both players, so
showing only one would lie by half).

The preview and the real effect must agree; `tools/check_shop_delta.py`
asserts that for every offer.

## No prey / projectiles cross into camp

`_enter_camp` cleans up prey, projectiles, and puddles. Clean clearing:
no stray creature frozen against a door. Prey are not updated in camp.

## Related

- [ADR-0005](../adr/0005-camp-is-a-physical-clearing.md) — why camp is
  world state, not a menu.
- [Round](./round.md) — cleared rounds enter camp.
- [Charm](./charm.md) — the tent's only fixed-price item.
- [Route](../../CONTEXT.md) — what a door commits to.
