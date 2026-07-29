# Ambient darkness via screen-space multiplicative layer

The day→night run is a single `BLEND_RGB_MULT` blit of a screen-space `Surface`
between the world pass and the danger pass; the layer fills with an ambient
colour and gets additive light blits from registered sources. Everything drawn
**after** the layer is untouched, and that is the contract.

## Considered options

- **GPU shader** with a `darkness` uniform per pixel. Ruled out by `set_mode`
  failing under the dummy driver (`OPENGL support is either not configured in
  SDL or not available in current SDL video driver (dummy)`) -- `--smoke` and
  every headless `tools/` check run under dummy, so opening GL would break
  `docs/agents/verification.md`. The CPU path is cheap enough that the
  compromise isn't worth the day.
- **Per-biome darkness** as a function of `world.biome_at`. Ruled out because
  the biomes **coexist in the same world** (`world.centres`, a jittered 3×3
  grid) -- the player walks from one to the next in seconds, and a biome blend
  would have to be spatially smooth and stay locked to the cell cache. A
  run-wide scalar dodges the whole problem.
- **Darken `world.draw_ground` directly** with the camera-relative `dark`
  factor. Ruled out because it cannot show light pools (a mushroom is invisible
  in pure darkness) and would couple `terrain.py` to the ambient module for no
  upside.
- **Darken the player / projectiles / FX pass** and re-draw danger on top.
  Same visual result, but per-frame the danger pass already costs ~0.4 ms with
  92 bullets; multiplying it would roughly double the cost and add no
  readability gain. The "draw after the layer" rule is free.

## Consequences

- **Hard to reverse.** The slice in `Game.draw` is the contract: anything new
  drawn **after** the layer blit stays bright, anything drawn **before** is
  darkened. Adding a new danger source means remembering to put it after the
  slice. Adding a new ambient source (flora, decor) means putting it before.
  The hostile puddle move (up out of the original line 709) is the canonical
  example of this rule being load-bearing: a hostile puddle drawn before the
  layer would get its damage footprint visually softened.
- **Surprising without context.** A future reader looking at `Game.draw` will
  ask "why does the hostile puddle draw loop split off?" and "why is the
  lighting draw wedged between rounds.draw_world and the shadows?" The ADR
  exists to answer both.
- **Real trade-off.** Per-frame the layer is `1 × fill + N additive blits + 1
  multiplicative blit` of 1120×720. Measured under `tools/check_lighting.py`:
  ~0.9 ms at the documented scope (player aura + ~220 prop lights + a handful
  of FX emissions). 1.5 ms is the declared ceiling, with halving to 1/2 or 1/4
  resolution the documented fallback -- borrows the soft edge anyway.

## Rule

**Darkness never darkens danger.** Enforced by draw order, not per-entity
logic: the lighting layer's `BLEND_RGB_MULT` blit sits between the world pass
and the danger pass, and anything drawn after it is painted on top at full
brightness.

## Status

Implemented for issue #110. `NIGHT_MAX` defaults to 0 so existing headless
checks stay pixel-identical to today; flipping it on turns the layer on.