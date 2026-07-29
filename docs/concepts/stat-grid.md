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

One column per player, glued to that player's own health bar
(`state_play._GRID_Y`, under the dial row). Single-player and co-op are
the same layout with no special case — only the anchor flips, because
P2's panel is right-aligned and so is P2's column. It lives under the
same rule as the rest of the HUD and is therefore hidden on the level-up
and camp screens (see [UI legibility](./ui-legibility.md)).

## Cached by value

The block is redrawn every frame but its numbers change rarely, so it
goes through `Game._panel` keyed on **the displayed strings themselves**.
That is the quantisation [ADR-0009](../adr/0009-glow-cache-quantized-keys.md)
requires, and the rounding happens in `state_play._stat_rows`, before the
strings exist: the four multipliers are formatted to two decimals and
`health` — the only continuous input — goes through `int`, which bounds
the keyspace by `max_health`.

Rounding in the caller and not in `hud` is deliberate. If `hud` rounded,
the key would be built from values the caller could still change without
the block noticing.

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

## Related

- [Health HUD](./health-hud.md) — the bars the column is glued to.
- [UI legibility](./ui-legibility.md) — the text primitive and the HUD's
  hide rule.
- [Item](./item.md) · [Charm](./charm.md) — what the icon row lists.
- [Damage](./damage.md) — what `might` multiplies.
- [Performance](./performance.md) — why a per-frame block has to be
  cached.
