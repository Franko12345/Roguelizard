# Lighting

The dark layer that turns a run into night. A screen-space `Surface` fills
with an ambient colour, gets additive light blits from registered
[Fontes de luz][1], and is composited back into the scene with
`BLEND_RGB_MULT` between the world pass and the danger pass. Anything drawn
**after** the layer blit is untouched -- that is the "never darken danger"
rule, enforced by [ADR-0015][2] and verified by
[`tools/check_lighting.py`](../../tools/check_lighting.py).

[1]: ../../CONTEXT.md#feel
[2]: ../adr/0015-ambient-darkness-with-additive-light.md

## The day→night scalar

`Game.dark_level()` returns the run's `[0..1]` scalar from the current wave.
Wave 1 is full day (0); wave `C.RUN_FINAL_WAVE` (20 in `normal` mode) is full
night (1); endless caps at 1.0 so the screen never goes pitch black. The
scalar is multiplied by `C.NIGHT_MAX`, the master knob: 0 disables the layer
entirely and every existing headless check stays pixel-identical to today.

## The layer

`LightingLayer.draw(surf, cam, dark, static_lights, players, fx_emissions, dt)`
is called once per frame from `Game.draw`, between `rounds.draw_world` and the
shadows loop:

1. **fill** the cached `Surface` with the ambient colour, quantised to 32
   buckets so similar waves share the same fill and the `palette.glow` cache
   stays bounded (see [ADR-0009][3]).
2. **additive blit** every [Fonte de luz][1] onto the surface -- player auras,
   static prop lights (mushroom / flower / lily / reed / bush), and FX
   emissions (bursts and spark bursts register a one-frame spill that ages
   out by `C.FX_EMISSION_LIFE`).
3. **multiplicative composite** the layer back onto the scene with
   `BLEND_RGB_MULT`.

[3]: ../adr/0009-glow-cache-quantized-keys.md

The surface is allocated lazily and reused -- a fresh `Surface(SRCALPHA)`
every frame costs ~6 ms and produces garbage, per the existing `ui._tint`
discipline in [Performance][4].

[4]: ./performance.md

## What gets darkened, and what doesn't

The "never darken danger" rule is just draw order:

| draws **before** the layer (darkened) | draws **after** the layer (untouched) |
|---|---|
| ground, flora, props | shadows |
| friendly puddles (player acid) | pickups |
| nests, marks (round telegraph) | prey / friends / enemies |
| camp POIs (tent + doors) | players |
| | **hostile puddles** |
| | projectiles |
| | world ambient motes |
| | FX (particles, sparks, rings, floats) |

The hostile puddle split is the canonical example of the rule: `Puddle(hostile=True)`
must draw **after** the layer, because the puddle is danger (it ticks damage)
and a danger source darkened by the layer is invisible against the dark
ground.

## Pickups stay off the layer

With ~54 pickups on the ground at any time, registering each one as a light
turns the screen into a flicker and the layer dissolves into the noise. The
layer reads `game.world.static_lights` (the glow-capable props) and
`game.fx.emissions`; pickups are intentionally excluded.

## What does a `Light` look like

```python
from lagarto.render.lighting import Light

# Static prop light (built once at world construction)
Light(pos=Vector2(x, y), color=(255, 226, 158),
      radius=C.PROP_LIGHT_R, intensity=0.5, kind='prop')

# One-frame FX emission (registered by fx.burst / fx.spark_burst)
Light(pos=..., color=..., radius=70, intensity=1.0,
      life=C.FX_EMISSION_LIFE, maxlife=C.FX_EMISSION_LIFE, kind='fx')
```

`kind` is metadata for diagnostics; the lighting layer treats all three
flavours (`player`, `prop`, `fx`) the same way -- one additive blit onto the
layer surface, with intensity scaled by the remaining life for `fx` lights.

## Performance

The declared ceiling is **1.5 ms** (see ADR-0015). `tools/check_lighting.py`
times the layer against the day-frame baseline at 0.9 ms typical on this
box, with the cache warm. If the ceiling is ever busted, halve the layer
resolution (1/2 or 1/4 of `C.WIDTH × C.HEIGHT`) and `smoothscale` up on the
blit -- borrows the soft edge anyway.

`NIGHT_MAX = 0` makes the layer a no-op (`lighting.blit_count` does not
advance, no surface is allocated), which is what every existing headless
check relies on.

## Related

- [ADR-0015](../adr/0015-ambient-darkness-with-additive-light.md) -- the
  decision: a screen-space `BLEND_RGB_MULT` blit, not a GPU shader; a run-wide
  scalar, not per-biome; draw order enforces the rule.
- [Performance](./performance.md) -- the cache discipline, the cost of a
  full-screen `Surface` per frame, and the `ui._tint` precedent for reusing
  one surface per colour.
- [Juice](./juice.md) -- the FX layer that registers emissive lights via
  `fx.burst` and `fx.spark_burst`.
- [`tools/check_lighting.py`](../../tools/check_lighting.py) -- the check
  with teeth: same scene at day vs night, hostile bullet pixel identical,
  ground pixel differs.