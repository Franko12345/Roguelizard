# Spine

The follow-the-leader chain of joints that is the physical body of every
`plan='normal'` creature. Hit-tests, [Legs](./leg.md), and eyes read
`spine.joints` directly; drawing may read the parallel
[Cosmetic Skeleton](../../CONTEXT.md) instead.

Defined in `lagarto/anim/spine.py`. Constrained by
[ADR-0007](../adr/0007-cosmetic-skeleton-for-tail.md).

## How it works

Each joint is pulled to a fixed distance from the previous joint. Direction
is limited by `bend` so the body cannot double back on itself. `resolve()`
propagates the constraint from head to tail every frame.

- **`joints`** — list of `Vector2`, indexed head-to-tail.
- **`radii`** — parallel list. Roundest at the head, tapers toward the
  tail. `parts.py` reads this for spike/plate positioning.
- **`bend`** — max angle change between consecutive joints (degrees).
  Smaller = stiffer.

## Body polygon

`body_polygon()` walks the joints and produces the silhouette:

- Head cap and tail cap are rounded arcs.
- Middle is a strip of quads, not a single closed polygon. That's
  deliberate — a self-crossing ring gets a hole where the closed shape
  reads it as inside-out, producing "transparent body" bugs during
  dashes and tight turns.
- `body_polygon_smooth()` (with `SMOOTH_SUBDIV=3`) runs Catmull-Rom
  between joints for the outline while keeping physics joints unchanged.
  Same joint positions, more silhouette samples.

## Draw vs sim: the cosmetic joints

The last `TAIL_SPRING_JOINTS` joints are _also_ available through
`_cosmetic_joints()`, which returns a copy displaced by the tail spring
and the travelling wave. Draw reads cosmetic, sim reads
`spine.joints`. See [ADR-0007](../adr/0007-cosmetic-skeleton-for-tail.md).

## `plan='segmented'` and `plan='tentacle'` do not use `Spine`

Centipede uses a chain of circle segments with metachronal legs.
Kraken uses a mantle with arm sub-chains. Both live in `Lizard`
alongside the spine path, chosen by [`Genome.plan`](./genome.md).

## Related

- [Genome](./genome.md) — the `size` / `length` / `bend` inputs.
- [Leg](./leg.md) — reads spine joints for foot planting.
- [Parts](./parts.md) — draws spikes/plates/fins along joint indices.
- [ADR-0007](../adr/0007-cosmetic-skeleton-for-tail.md) — the sim / draw split.
