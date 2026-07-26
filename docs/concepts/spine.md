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

## The tail overshoot is a chain of 5

`tail_chain`, built in `rebuild_body` for `plan='normal'` only, advanced in
`update_secondary_springs`, read by `_cosmetic_joints`. Stiffness rises
toward the base and damping falls toward the tip, so a dead stop settles at
the base first and rings on at the tip.

`tail_spring` is still the public handle and **is** the tip link, so the
handful of places that write `tail_spring.stiffness` (boss body telegraph, AI
mood pose, per-state posing) keep writing one object — the chain's stiffness
is re-derived from the tip's as a set of ratios, so one write scales the whole
tail. See [Procedural animation](./procedural-animation.md).

## Other body plans do not use `Spine` the same way

Centipede (`segmented`) uses a chain of circle segments with metachronal
legs. Kraken (`tentacle`) uses a mantle with arm sub-chains. Olho-Sísmico
(`orbital`) collapses the joints into a ball with a tiny `link`. A Muralha
(`fixed`) is a short wide chain that never moves. All live in `Lizard`
alongside the spine path, chosen by [`Genome.plan`](./genome.md); none of
them gets a `tail_chain`.

## Related

- [Genome](./genome.md) — the `size` / `length` / `bend` inputs.
- [Leg](./leg.md) — reads spine joints for foot planting.
- [Parts](./parts.md) — draws spikes/plates/fins along joint indices.
- [Body plan](./body-plan.md) — the five plans and what each builds.
- [ADR-0007](../adr/0007-cosmetic-skeleton-for-tail.md) — the sim / draw split.
