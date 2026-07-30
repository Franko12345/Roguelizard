# Procedural Animation

The lizard is 4 elements:

- **Intent** — head points at the target.
- **Action** — legs take the step.
- **Reaction** — [Spine](./spine.md) reacts.
- **Follow-through** — tail lags.

No keyframes. Every visible motion is the output of a physical or
kinematic rule.

## Spine

Each joint is pulled to a fixed distance from the previous joint.
Direction is limited by `bend` so the body cannot double back on itself.
See [Spine](./spine.md).

## Legs

The foot stays planted until the body drags its "rest point" past a
threshold. Then it steps in an arc to a target ahead of the body.
**Diagonal gait**: opposite pairs never step together (`Leg.partner`).
Drawn by two-bone IK. See [Leg](./leg.md).

## Squash & stretch

Derived from velocity — the body flexes without any authored animation.

## Oscillators

Every part that waves used to inline its own
`math.sin(creature.wobble * k + i * gap) * amp`. Each now reads a
`PhaseOscillator` from the `OSC_PRESETS` table in
[Parts](./parts.md) — per-species tuning is editing one table instead of
hunting sines through the draw code.

The oscillators are driven **by `creature.wobble`**, not by their own `dt`
accumulator. That is not a detail: `wobble` advances at `dt * 6`, so a
preset speed of 1.3 really is the old `wobble * 1.3`; and `wobble` is seeded
per creature at random, so creatures stay out of phase with each other. An
oscillator ticking its own clock from zero animates at 1/6 speed **and** puts
every creature's fins in lockstep — both were shipped once and both were
caught by `tools/check_oscillators.py`, which asserts each oscillator
reproduces the exact expression it replaced.

The octopus arm wave deliberately stays an inline sine: each arm carries its
own phase offset *inside* the sine, and `PhaseOscillator(time, segment)` has
nowhere to put it. `sin(a) + sin(b)` is not `sin(a + b)`.

## Follow-through is a chain, not a spring

The tail was one `Vector2Spring`, so it lagged as one rigid unit. It is now
5, stiffness rising toward the base and damping falling toward the tip, so a
dead stop **cascades outward**: measured 6, 3, 42, 45, 51 frames to settle
from base to tip.

Stiffness is stored as a **ratio** of the tip spring's and re-derived each
step, which keeps the tip behaving exactly as the old single spring did and
means the existing writers — the boss body telegraph, the AI mood pose,
per-state [posing](./ai.md) — keep writing one object (`tail_spring` *is* the
tip link) and now scale the whole tail instead of just its end.

## The lesson both of those taught

Spring stiffness is not a "how much lag" dial. A **low** stiffness looks like
it should mean more lag and more whip, but if the motion you are chasing is
shorter than the spring's settle time, the spring simply never arrives at the
shape at all and you get a stiff straight thing instead. The tongue's retract
is ~10 frames long and needed its stiffness **raised** to look loose. Measure
the shape, not the constant.

## Multi-body phantoms

A silhouette of a different species, painted under the live boss with
per-pixel alpha and a per-phase tint. Cheap because the ghost is paint
only — no AI, no hit-test, no collision, no integrate — and because the
creature code already draws the entire body from the genome
([Spine](./spine.md), [Leg](./leg.md), [Parts](./parts.md)), so a
phantom is "build that creature, draw it once, throw it away."

The trick is the layering: render each ghost on a per-game reusable
SRCALPHA scratch surface, then a single `fill(tint_color,
BLEND_RGBA_MULT)` tints per-pixel and multiplies the configured alpha
into every painted pixel, then `surf.blit(...)` over the live surface.
The destination needs no per-pixel-alpha flag — `blit` honours the
source's per-pixel alpha automatically. Cross-fading is just a
`approach()` lerp on each phantom's alpha every frame, with the phase
transition swapping `target_alpha` so the swap reads as cinema.

ANKH uses four phantombodies, one per phase memory (Rei Lagarto gold,
Mae-Escaravelho orange, Kraken-Mor blue, Primordial violet); phase 4
sets all four alphas to 0.5 simultaneously so four bodies overlap at
the same pixel. See `boss.md` ANKH multi-corpo and
`tools/check_ankh_signature.py` for the canonical example.

## Related

- [Spine](./spine.md) — the follow-the-leader chain.
- [Leg](./leg.md) — 2-bone IK + foot planting.
- [Parts](./parts.md) — decorations that ride the spine, and `OSC_PRESETS`.
- [AI](./ai.md) — per-state posing, the body-language layer.
- [Combat](./combat.md) — the tongue, a pinned spring chain.
- [ADR-0007](../adr/0007-cosmetic-skeleton-for-tail.md) — the sim vs
  draw split for tail.
