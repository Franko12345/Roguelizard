# Parts

Additive decorations read from the [Genome](./genome.md) each frame:
spikes, plates, horns, tail tip (club or sting), fins, wings, antennae,
extra eyes. Drawn by `parts.draw_all` from `lagarto/creatures/parts.py`. Evolving a
part _is_ setting a genome number.

## Where each part is drawn

Along the [Spine](./spine.md):

- **Spikes** curve outward with a swayed alternation between the two sides.
- **Plates** stack as chevron scales.
- **Fins** ride the tail with a phase offset for swim animation.

At specific joints:

- **Horns** taper forward from the head. Rigid — no lag, no sway; the
  horn is bone. See the [ADR](../adr/README.md) index if you're tempted to
  re-add a spring here (there isn't one, and there is a reason).
- **Wings** hover at flyer shoulder joints; hover bob is a sine on the
  vertical offset.
- **Tail tip**:
  - **`'club'`** — a heavy ball drawn on the last cosmetic joint.
    Multiplies whip damage by `WHIP_CLUB_MULT`; boosts knockback and
    screen shake.
  - **`'sting'`** — a barb. Applies `apply_poison` on player whip,
    `apply_slow` on enemy sting (yes, they diverge on purpose).

## Read cosmetic joints, not spine joints

Every part that sits on the tail must read the
[Cosmetic Skeleton](../../CONTEXT.md) via `_cosmetic_joints()`, not
`spine.joints` directly. Missing this makes the part visually detach from
the tail during overshoot or wave. This regressed once (plates, fins,
spikes) and shipped as a bug; see
[ADR-0007](../adr/0007-cosmetic-skeleton-for-tail.md).

## Evolution

Two ways parts enter the player [Genome](./genome.md):

- **Eating** a carrier prey grants the part via `species.grants`.
- **Dash-killing** a carrier enemy has a ~12% chance. Rare on purpose;
  the drop rate is the pacing knob.

Also entered via [Mutation](../../CONTEXT.md) cards, which write directly
to the field.

## Related

- [Genome](./genome.md) — the numbers each part draws from.
- [Spine](./spine.md) / [Leg](./leg.md) — the anatomy parts hang off.
- [Charm](./charm.md) — the tail-club charm sets `tail='club'` for a run.
