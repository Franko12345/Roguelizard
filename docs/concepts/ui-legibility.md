# UI Legibility

Text and the top-of-screen stack.

## Why the text was weak — antialiasing is not the problem

AA was already on at the ~68 render points. The blur comes from
`display.present()` running `smoothscale` on the whole screen: the glyph
is rasterised at 14 px on the logical surface and **stretched with
bilinear filtering** to 2× / 3×. A thin stroke does not survive that.
Two fixes, both matter:

- **`ui.text(surf, font, s, pos, cor, align=)`** draws a **dark outline**
  behind the glyph — the hard edge is the only thing that crosses the
  filter. `pos` is where glyphs land, so it is a drop-in for
  `surf.blit(font.render(...), pos)`, and it **returns the rect** of the
  text (used by layout).
  - _`ui.text_surface` returns a **cached, shared** surface — `.copy()`
    before touching `set_alpha`, otherwise every subsequent draw of that
    string inherits the tweak (the banner fade regressed exactly there)._
- **`fonts.get(size, bold=True)` by default** — thicker strokes survive
  the scale.

The text cache has a **cap (`_TEXT_MAX = 700`) with `clear()`** — same
pattern as `palette._GLOW_CACHE`: score, HP, and timers are **continuous**
text, so the keyspace is unbounded. Measured: stable at ~608 entries /
9.7 MB over 18 000 frames.

## No `→` (U+2192) in UI text

Base Noto Sans does not cover arrows (they live in Noto Sans Symbols) —
it came out as **tofu on every weapon upgrade card**. Worse:
`font.metrics('→')` **lies** — it reports the glyph and still fails to
rasterise. Test by rendering, not by querying. Use `->`. The em-dash `—`
renders fine.

## The top stack (`game.TopStack`)

Six elements — score, wave line, combo, theme banner, boss name, boss
bar — each used to hard-code its own `y`. On a boss wave with combo,
**three overlaps at once**, and the banner runs for 2.2 s exactly when the
boss spawns — guaranteed collision. Now each element requests the height
it needs (`top.take(h)`) and gets the next free strip.

- **Draw order = priority.** Permanents (HUD, boss bar) reserve first
  and never move; the banner is **transient** and goes last, otherwise
  it pushes the boss bar into the play area at spawn.
- `top.reset()` once per frame, in `game.draw`.
- The **HUD is hidden in `levelup` / `camp`** — those screens have their
  own header, and the HUD under the veil only competed with the panels.

## Related

- [Health HUD](./health-hud.md) — reads through this stack.
- [UI screens](./ui-screens.md) — where the HUD is hidden.
- [HUD anatomy](./hud-anatomy.md) — the metaphor behind the framed
  capsules in the bottom corners.
- [Performance](./performance.md) — cache caps, no per-frame full-screen
  `Surface`.
