# Stat grid

The run's numbers, on screen, all the time. `hud.stat_grid` draws one
compact column per player: five labelled stat rows, then a row of icons
for everything that player owns.

Before it existed, nothing on screen said how much damage or health a run
had accumulated — the [health HUD](./health-hud.md) showed current HP and
the cooldown dials showed "can I act?", but `might`, `cooldown_mult`,
`speed_mult` and `area_mult` were invisible. That made every priced
choice feel arbitrary: you paid for an upgrade and no readout moved.

## What it shows

| Row | Reads | Format |
|---|---|---|
| `DANO` | `might` | `1.72x` |
| `VIDA` | `health` / `max_health` | `76/124` |
| `RECAR` | `cooldown_mult` (<1 is faster) | `0.86x` |
| `VELOC` | `speed_mult` | `1.15x` |
| `AREA` | `area_mult` | `1.30x` |

Under the rows, one icon per owned item (in pickup order) then one per
owned charm, through the same drawers [icons & audio](./icons-audio.md)
already defines. An unknown id is dropped rather than drawn as the
fallback disc — an anonymous disc would read as "you own something" and
say nothing.

**The labels are words, not icons.** A gamepad has no cursor, so every
row has to read on its own without hovering anything.

## Where it sits

Two places, same block: the play HUD and the [camp](./camp.md)'s shop
screen.

**In play** — one column per player, glued to that player's own health bar
(`state_play._GRID_Y`, under the dial row). Single-player and co-op are
the same layout with no special case — only the anchor flips, because
P2's panel is right-aligned and so is P2's column. The rest of the HUD is
hidden on the level-up and camp screens (see
[UI legibility](./ui-legibility.md)), and so is this.

**In the camp's shop** — one column per player again, flanking the five
shop cards, riding in on the card row's own drop-in offset so it lands
with them. The purchase decision happens on that screen, so the numbers a
purchase moves have to be on it. It is **two columns and not one
aggregate** because in co-op the stats genuinely diverge: shop offers
apply to every player, but level-up cards and charms are per player. An
average would lie (1.4× damage when one player has 1.72× and the other
1.10×), and showing only whoever touched the tent would leave the other
blind to a purchase that spends shared pollen on them too.

The cards make room, not the columns — `state_camp._shop_layout` and the
regression it protects are described in
[Camp](./camp.md#the-shop-row-shares-the-screen-with-the-stat-grid).

## Cached by value

The block is redrawn every frame but its numbers change rarely, so it
goes through `Game._panel` keyed on **the displayed strings themselves**.
That is the quantisation [ADR-0009](../adr/0009-glow-cache-quantized-keys.md)
requires, and the rounding happens in `hud.stat_rows`, before the strings
exist: the four multipliers are formatted to two decimals and `health` —
the only continuous input — goes through `int`, which bounds the keyspace
by `max_health`.

`hud.stat_rows` / `hud.stat_badges` are the one thing in `hud` that reads a
player, against that module's own rule. They sit next to the primitive they
key on purpose: the strings *are* the cache key, so two states formatting
them separately would be two ways to key the same surface — the exact
duplication the grid exists to avoid.

## The toggle

**TAB** flips it, as a latch rather than a hold, and the preference
persists in `core/settings.py` next to the perf meter's. Default is
**on**: the grid is the HUD's normal state, not a hidden extra.

One toggle for the whole game, not one per player — in co-op both columns
are the same kind of readout, and a per-player toggle would only start an
argument about which half of the screen is right. `Game` owns the value
(`show_stat_grid` / `toggle_stat_grid`) so there is a single writer;
`app.py` only keeps its in-memory copy of settings in sync, because its
F3 handler writes that copy back wholesale.

TAB was free: P1 uses WASD/space/LSHIFT/Q/E/LCTRL, P2 uses
arrows/IJKL/RCTRL/RSHIFT/RALT/U/O, and the sandbox overlay uses
backquote/F1. See [Controls](./controls.md).

## Verification

`tools/check_stat_grid.py` renders the block headless in 1P and 2P
(asserting the two columns do not overlap and each sits on its own
player's side), counts `Game._panels` across 60 identical frames to prove
the cache hits, checks that 0.01 HP of drift does **not** rebuild the
block while a whole HP does, and round-trips the TAB preference through
`settings` including a `save_display` write.

It then draws the camp's shop screen in both player counts and asserts, in
pixels and in rects, that no column overlaps a `_shop_rect`, that neither
the row nor a column leaves the screen, and that turning the grid off puts
the row back at 176px cards from x=92.

## Related

- [Health HUD](./health-hud.md) — the bars the column is glued to.
- [Camp](./camp.md) — the shop screen the columns flank.
- [UI legibility](./ui-legibility.md) — the text primitive and the HUD's
  hide rule.
- [Item](./item.md) · [Charm](./charm.md) — what the icon row lists.
- [Damage](./damage.md) — what `might` multiplies.
- [Performance](./performance.md) — why a per-frame block has to be
  cached.
