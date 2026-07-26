# Leg

A two-bone IK limb with foot planting. Every `plan='normal'` creature has
`Genome.legs` of them. The gait is diagonal by default; the spider
(`Genome.radial=True`) uses angular rest positions instead.

Defined in `lagarto/anim/leg.py`.

## Foot planting

The foot stays where it is until the body drags its "rest point" past a
threshold. Then the foot steps in an arc to a target ahead of the body.
No frames, no keyframes — the arc parameters are the animation.

- **`rest_target`** — where the foot would sit if the body were still.
  Updated every frame from the [Spine](./spine.md).
- **`step_arc`** — height of the parabolic arc during a step.
- **`pull`** — a scalar the AI can push toward zero to draw the feet
  toward the body (the frog does this to sell the wind-up of a hop). Falls
  back to 1.0 on its own each frame.

## Diagonal gait: partners

`Leg.partner` points at the opposite leg — front-left partners with
back-right. A leg cannot start a step while its partner is stepping.
That's the entire "walk cycle": no timeline, just a constraint between
two feet.

## Radial mode

If `Genome.radial`, `Leg.rest_angle` replaces the partner mechanic. Each
leg has an assigned angular slot around the body. Foot planting still
works, but the walk becomes the spider's radial scuttle.

## IK: two-bone solve

The visible knee is the elbow of the two-bone IK. Given the shoulder
position (on the [Spine](./spine.md)) and the foot target, `solve()`
places the knee. Length constraints keep both bones honest.

## Related

- [Spine](./spine.md) — where the shoulders sit.
- [Genome](./genome.md) — how many legs, radial vs diagonal.
- [Species](./species.md) — spider is the current radial user.
