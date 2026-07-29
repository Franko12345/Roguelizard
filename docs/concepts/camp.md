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
  Contents: heal, max-HP, might, [Charm](./charm.md), egg. Charm's base
  is 150 pollen; the rest are cheap. See _The price has two axes_ below.
- **Three doors** — each shows a theme + bonus (heal / pollen / card).
  Crossing one commits — `_apply_route` calls `rounds.request_next(theme)`.
  The pollen bonus rides the same tier multiplier as the shop
  (`int(25 * rounds.tier_price_mult(wave))` → 25 / 42 / 60 / 77): a flat
  +25 was the obviously worst door in the late game, which cost the
  clearing one of its three real choices.

## Drops from the sky

Each POI **falls from `CAMP_DROP_H` above the ground** with an
ease-in that accelerates into impact. `_camp_impact` fires
shake + dust + sparks + a ring on landing. A **growing shadow** on the
ground telegraphs where it will land. Interaction is locked until the
POI touches the ground (`tent_landed` / `dr['landed']`) — entering a
mid-air door was a real bug.

## The price has two axes

Every offer in `_roll_shop` is a data row with a `base` price, a `perm`
flag, and an optional `preview` (the offer's numeric delta, e.g.
`('might', 1.15, 'mul')` — `Charm` and the egg have none, their effect is
not a number). `state_camp.shop_price(base, perm, buys, wave)` turns that
row into what the tent charges:

    price = int(base * rounds.tier_price_mult(wave) * mult ** buys)

- **The run's stage** — `tier_price_mult` is `1 + SHOP_TIER_STEP * tier`,
  so 1.0 / 1.7 / 2.4 / 3.1×. It steps on the boss wave and holds until
  the next boss, so the player reads the jump as "the boss raised the
  stakes", not as a slow creep. Tier 0 is 1.0× on purpose: the early
  game is untouched. Why it exists at all is in
  [Balance](./balance.md#4th-pass--shop-price-scales-with-the-run-stage-issue-137).
- **How often you bought it** — `C.SHOP_PRICE_MULT_PERM` (1.45) for a
  permanent upgrade (Vitalidade, Vigor, Charm), `C.SHOP_PRICE_MULT`
  (1.25) for a consumable (Néctar, Ovo). Buying nothing keeps an offer at
  its tier price forever.

Neither axis is capped. In `endless` income keeps growing too, and an
offer that priced itself out of reach is the anti-spam brake working.

## The purchase count persists for the whole run

The camp dict is thrown away when you leave the clearing, so what
survives is `Game.shop_buys` (`{item name: purchase count}`, per run,
in memory — no save to migrate). `_apply_buy` increments it and reprices
from `base`; `_roll_shop` reads it back when it builds the next tent.

It stores the **count**, not the price, because the two axes have to stay
orthogonal: a stored price would already have the tier multiplier of the
camp where the purchase happened baked in, and compose it a second time
in the next tier. The desired side effect is that a tier jump also raises
the price of something you already bought.

Before issue #105 the raised price lived in the throwaway camp dict at
1.6× and reset every clearing — Néctar was permanently 12 pollen and
cheap healing was infinite. Persisting it is why the per-purchase step
got gentler: it compounds across a whole run instead of one visit.

## The shop row shares the screen with the stat grid

The tent's menu shows the [stat grid](./stat-grid.md) too — one column per
player, flanking the five cards, because the purchase decision happens
here and a price means nothing without the numbers it moves.

Five 176px cards plus two 132px columns do not fit in 1120px, so **the
cards give up the width, not the columns**: `_shop_layout` reserves a side
band per column, centres the row in what is left, and narrows the card to
152px in co-op. The card's description drops a font size instead of
gaining an ellipsis at that width — a cut word says less than smaller
text. With the grid off (TAB) the arithmetic returns the layout that
predates it: 176px cards, row centred on the screen.

Single-player reserves only the left band, so the row keeps full-width
cards and simply sits further right — no hole where a second column would
have gone.

## Shop is choice, not toll

Walking straight to a door and skipping the tent is legal. The tent has
to earn the visit. `reopen_cd` prevents reopening the shop on the same
step it was closed. Closing during drop-in is _not_ blocked — the pick
absorption (`self.pick`) is the only lock, and only for its ~0.36 s
window.

## No prey / projectiles cross into camp

`_enter_camp` cleans up prey, projectiles, and puddles. Clean clearing:
no stray creature frozen against a door. Prey are not updated in camp.

## Related

- [ADR-0005](../adr/0005-camp-is-a-physical-clearing.md) — why camp is
  world state, not a menu.
- [Round](./round.md) — cleared rounds enter camp.
- [Charm](./charm.md) — the tent's priciest offer.
- [Stat grid](./stat-grid.md) — the columns beside the shop row.
- [Balance](./balance.md) — the income-vs-price arithmetic behind
  `SHOP_TIER_STEP`.
- [Route](../../CONTEXT.md) — what a door commits to.
