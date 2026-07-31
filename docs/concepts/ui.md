# UI — components and conventions

The game's UI is small but opinionated. This file is the canonical place
for "where does X live and how does it work"; concept docs reference it
when the convention is shared.

## Tooltip system (`lagarto/render/ui_tooltip.py`)

First tooltip system in the game. Issue #141 added it together with the
stat grid. Lives in `ui_tooltip.py` (not `ui/tooltip.py`) because the
existing `lagarto/render/ui.py` is a flat module and Python's import
system cannot tell `ui.tooltip` from `ui`.

### Behaviour

- **Dwell-based**: opens only when the cursor rests on the target rect
  for `0.25s`. Calibrated for play, where the cursor is also the aim
  (dash on left, tongue on right) and crosses the stat column dozens of
  times per second.
- **Skim-safe**: a 0.1s touch does NOT open. The timer resets on exit.
- **Screen-clamped**: the box flips to the left of the cursor if the
  right would clip, and clamps to the screen if neither side fits.
- **Reused across contexts**: works in the camp (shop + stat grid) and
  during play (stat grid). Any caller that has a `pygame.Rect` and a
  string can use it.

### Components

- `Tooltip(rect, text, dwell_seconds=0.25)` — one tooltip bound to one
  rect. State is per-instance. Call `update(mouse_pos, dt)` each frame
  and `draw(surf, font)` when active.
- `TooltipManager` — drop-in for the common "one tooltip on screen at a
  time" case. The module exposes a singleton `manager`. Pattern:
  1. `tooltip.manager.begin_frame(mouse_pos)` (or with `dt` explicitly)
  2. For each candidate target, `tooltip.manager.hover(rect, text)`
  3. `tooltip.manager.draw(surf, font)` once, after all UI is on the
     surface.

### Source text

`source_text(stat_label, player, game=None)` returns the line that
explains where a stat came from. Walks `Game.shop_buys` (the per-run
shop counter), the player's charms, and items. Returns "X: sem origem
rastreada" if nothing is found so the tooltip never shows an empty
line.

The mapping between HUD label (`DANO`, `VIDA`, etc.) and shop offer
name (`Vigor`, `Vitalidade`, etc.) is hard-coded because the grid is a
fixed 5-row set. A general "which effect changed which stat" map is
the next step (#140's declarative schema is the foundation).

## Stat grid (`lagarto/game/hud.py`)

`stat_grid(...)` returns `(block_rect, sub_rects)` where `sub_rects` is
`{"row": {label: rect}, "badge": {k: rect}}`. The tooltip system uses
those sub-rects to know which row the cursor is over. Old call sites
that unpacked only the rect need updating; both `state_camp.py` and
`state_play.py` were updated for #141.
