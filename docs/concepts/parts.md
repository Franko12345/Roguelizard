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

## `OSC_PRESETS` — one table for every waving part

Each oscillating part reads a `PhaseOscillator` off the creature
(`creature.osc[key]`, built by `init_oscillators`, read by `_osc_offset`)
instead of inlining its own `math.sin`. Tuning how a species' fins move is
editing this table; the draw code never touches animation maths.

| key | speed | amplitude | phase gap |
|---|---|---|---|
| `spikes` | 1.3 | 0.18 | 0.5 |
| `fins` | 2.0 | 0.30 | 1.0 |
| `antennae` | 3.0 | 0.30 | 1.0 |
| `wings` | 7.0 | 1.00 | 0.0 |
| `spore_sacs` | 3.0 | 0.16 | 1.0 |
| `tail_ripple` | 2.2 | 1.00 | −0.9 |
| `arms` | 2.4 | 1.00 | −0.9 |

`update_oscillators` points every oscillator's clock at `creature.wobble`
rather than accumulating its own `dt` — see
[Procedural animation](./procedural-animation.md) for why that matters
(it is the difference between the old rate and 1/6 of it, and between
creatures being out of phase and in lockstep).

A negative `phase_gap` runs the wave tip-to-base instead of base-to-tip.

## Related

- [Genome](./genome.md) — the numbers each part draws from.
- [Spine](./spine.md) / [Leg](./leg.md) — the anatomy parts hang off.
- [Charm](./charm.md) — the tail-club charm sets `tail='club'` for a run.
- [Procedural animation](./procedural-animation.md) — the oscillator rule.

## Optional asset overrides for bosses (#159, ADR-0003)

The default path is procedural — every part is drawn from code, even for
bosses. For a small, scoped set of *personality* elements on bosses,
`parts.draw_all` accepts an optional `boss_id`. When present and a PNG
exists at `assets/boss/<boss_id>/<part_name>.png`, the helper
`boss_part(boss_id, part_name)` returns it and the drawer blits the asset
on top of the procedural layer. When the PNG is missing, the drawer
silently falls back to the procedural version — same rule as
[`icons.draw`](../../CONTEXT.md) and the rest of the zero-assets escape
hatch.

The override changes **only the look** of a single part. The spine, legs,
body polygon, motion, hit-test, and physics stay procedural. The boss's
body remains a `Genome`; the PNG is paint, not a substitute for the body.

Scope limit:
- Player, common enemies, prey: never load boss assets. `boss_id` is
  `None` for those; the override path short-circuits.
- Audio, world, particles: still 100% code. No PNGs here.
- "Personality elements" only — faceted segments, fangs, eye variants,
  ornamental layers. Never the silhouette or the procedural motion
  itself.

If a boss's PNG does not show up, the rule is the same as `icons.draw`:
path mismatch first, anything else second. See
[ADR-0003](../adr/0003-zero-assets-with-png-fallback.md).
