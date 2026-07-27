# Performance

Python game. These rules earned their spot — do not undo them without
measuring.

## Fixed timestep, decoupled render

`config.DT` = 60 Hz sim; the `app.py` accumulator drives it. Rendering
is separate. Animation stays stable regardless of FPS. A step cap
prevents the spiral of death. See
[ADR-0002](../adr/0002-fixed-timestep-decoupled-render.md).

## `RENDER_FPS = SIM_HZ` — do not raise

Sim is fixed at `SIM_HZ` and **drawing does not interpolate** between
states. Rendering above that only **redraws identical frames**: 120
render vs 60 sim was **2× the cost of `draw` + `smoothscale` + `flip`
for zero visual gain** (GPU pegged at 100% with low usage — many flips,
little work). If you ever want render > sim, **implement interpolation
first**.

## Vectors

`pygame.Vector2` + `math` (scalar numpy is slower per operation).

## Culling

`Camera.visible` culls creatures, flora, and particles.

## Particles

Pooled with a cap (`FX.MAX`). Shadows and tile colours are **cached**.

## Entity budget

Insects / prey repopulate by probability with a limit.

## Measured cost

~0.5 ms step + ~3.3 ms draw per frame on a full round (large headroom).
`display.present()` uses **smoothscale** so vector art stays crisp at
scale. It is CPU: 2.2 ms/frame at 2×, 3.8 ms at 3× — hence the
importance of render rate.

## `palette.glow` — the cache key MUST be coarse

`_GLOW_CACHE` stores one `Surface` per `(radius, colour)`. In practice
all three axes are continuous:

- Radius shrinks with particle lifetime and scales with zoom.
- Intensity is a pulsing sine on ~29 call sites.
- Each creature spawns with a random colour, and `fx` bursts inherit it.

Without quantising, the cache **grew without bound** — measured:
459 → 1843 entries and **24.6 → 115.7 MB** of surfaces over ~7 min of
play (RSS 364 → 470 MB), which stalled long sessions. Today:

- `_quantise_radius` (step 2 / 4 / 8 px by size) + colour in **4
  bits/channel** (`& 0xF0`) applied **after** the intensity multiply.
  Similar pulses / colours collapse to the same sprite; the additive
  gradient hides the banding.
- **Cap `_GLOW_MAX = 900`** with `clear()` on overflow (more predictable
  than LRU).
- Result: RAM flat at ~35-47 MB over 9 000 frames. **When you add a new
  glow, do not reintroduce continuous intensity / radius as a key.**

See [ADR-0009](../adr/0009-glow-cache-quantized-keys.md).

## The bullet body is a cached sprite — same key discipline

A bullet used to cost ~11 primitives: up to 7 trail circles, each with a
`palette.mix` recomputed every frame, one additive glow blit, and 3 body
circles. At the ~100 bullets a bullet-hell round puts on screen, that was the
most expensive thing being drawn.

- **The trail is one line**, from the oldest of 3 kept positions to the
  current one. At 100 bullets a seven-circle fading tail reads as noise
  anyway.
- **The body is a cached sprite**, keyed on `(even radius, side)` and capped at
  `_BODY_MAX = 96` with `clear()` on overflow. Two colour variants exist in
  total, because the body colour encodes the side and not the creature
  ([ADR-0014](../adr/0014-bullet-colour-encodes-side.md)) — that is the *only*
  reason this key is affordable. Do not reintroduce a continuous radius or a
  per-creature colour into it; that is the same trap
  [ADR-0009](../adr/0009-glow-cache-quantized-keys.md) is about.
- `projectile.body_stats()` returns `(entries, hits, misses, clears)`, the same
  diagnostics as `palette.glow_stats()`.

Measured with 92 live bullets (`tools/check_projectile.py`, steady state):
**draw 1.13 ms → 0.22 ms**, step 0.07 ms — 0.28 ms of the 16.6 ms frame. The
check fails if it ever passes 4 ms.

Bullets were then made bigger and brighter on purpose (`C.BULLET_SCALE` /
`C.BULLET_GLOW`, see [Projectile](./projectile.md)), which bought back some of
that: **0.87 ms** at the same 92 bullets, against 0.42 ms with a single glow
pass. The second, tight glow pass is what makes the centre blow out, and 0.45 ms
for it was judged worth paying at 5% of the frame.

Two traps this surfaced, both worth remembering before optimising the glow
again:

- **Measure in steady state.** The first reading was 2.27 ms because it caught
  the sprite cache building. The same run warm reports 0.87 ms.
- **Sprite construction is free per frame.** `palette._glow_sprite` scales its
  falloff steps with radius (10 / 18 / 26) and that costs nothing at 60 Hz,
  because it only runs on a cache miss — measured at 14 misses per 4000 draws.
  Ten steps banded into visible rings once bullets got large; more steps fixed
  the look at no per-frame cost at all.

Collision is not the bottleneck and was left alone: a hostile bullet only tests
against 1-2 players.

## No full-screen `Surface` per frame

`ui._tint(surf, colour, alpha)` is the only path for darkening /
lightening the full screen: reuses **one cached surface per colour**
with `set_alpha` (blit faster than per-pixel alpha). Used by `ui.Fade`,
`ui.veil`, the game-screen veil (`game._veil`) and the white flash.
Allocating `Surface(SRCALPHA)` every frame cost ~6 ms **and** produced
garbage.

## Text cache

`_TEXT_MAX = 700` with `clear()` on overflow — same pattern. See
[UI legibility](./ui-legibility.md).

## The camera transform is the hottest thing in the frame

`Camera.w2s` runs ~5,500 times per frame with 30 creatures on screen —
around 4.7 ms of a ~13 ms draw, more than any drawing primitive. It was
doing ten attribute lookups per call to recompute a transform that only
changes when the camera does.

It is now three cached floats and one multiply-add per axis:

```
sx = wx * _z + _ox
sy = wy * _z + _oy
```

`_z / _ox / _oy` fold zoom, camera position, screen centre and shake
offset together. They are refreshed by the **setters** of the four things
they depend on — `pos`, `zoom`, `center`, `shake_off` are properties for
exactly that reason — so callers keep assigning `cam.pos` as before and
cannot leave the cache stale.

The one thing that would break it is mutating a camera vector **in place**
(`cam.pos.x = 5`) instead of assigning a new one. Nothing does; assign a
new `Vector2` if you ever need to.

Two follow-ons from the same profile:

- `w2s_many(points)` binds the transform once per **list** instead of per
  point, for the body quads / fans / outline ring / part polygons.
- `visible()` skips `w2s` entirely — it needs neither the `int()` rounding
  nor the tuple, and runs ~800 times a frame.

`tools/check_camera.py` pins correctness rather than trusting the speedup:
`w2s` must match the naive formula exactly after every mutation path,
`w2s_many` must agree with `w2s` pointwise, `visible()` must agree with the
bounds test it replaced, and `s2w` must still invert `w2s`.

### Measuring this is easy to get wrong

Two traps, both hit while doing it:

1. **Seed the scene.** Creature genomes are randomised per spawn, so two
   runs build different bodies and the numbers swing 30% for no reason.
2. **Interleave the trees and take a best-of-N.** Machine load moves the
   absolute numbers by 2x, which is enough to invert a comparison — an
   early "+31% regression" here was pure noise, and the real regression
   (a mask-based outline at 3.3x on the draw path) only showed up in a
   benchmark that actually exercised it.

## Related

- [ADR-0002](../adr/0002-fixed-timestep-decoupled-render.md) — the loop.
- [ADR-0009](../adr/0009-glow-cache-quantized-keys.md) — the glow key.
- [Projectile](./projectile.md) — what the bullet sprite cache draws.
- [Input buffer](./input-buffer.md) — the sim/render decoupling implies it.
- [UI legibility](./ui-legibility.md) — text cache follows the same rule.
