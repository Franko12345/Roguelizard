# Top of screen is the lingua do mundo, not the lingua do corpo

**Context.** `#130`/`#131`/`#132`/`#133` built the rodape as the HUD's
anatomy metaphor: every readout is an organ inside a capsule, the
capsule has its own rhythm, the organ has its own. The metaphor
turns "where does this go?" into "what organ is this?" — a rule
that survives the next contributor. The `TopStack` (`lagarto/game/hud.py`)
still hosts six elements (score, wave line, combo, banner, boss name,
boss bar) with no metaphor at all, and issue #134 asks whether it
should adopt one and what happens if it does.

**Decision.** The HUD has **two declared languages**, not one:

- **Lingua do corpo** lives in the rodape. The metaphor is anatomy:
  tissue, air, brain, gland. Enforced by [ADR-0015](./0015-hud-anatomy.md).
  The check is `tools/check_hud_anatomy.py`.
- **Lingua do mundo** lives in the top-centre column. The metaphor
  is *the world the player is inside*: a run's score is not a body,
  a wave's progress is not a body, a boss's name is not a body, the
  boss's bar is the other body (and *not* yours). The `TopStack`
  stays the lingua do mundo; the rodape stays the lingua do corpo.
  The two languages are evaluated separately and mixed on purpose.

**Why.** Anatomy on the score fails the decision rule. "What organ is
the score?" has no honest answer, and forcing one produces an
arbitrary symbol — the original sin the rodape metaphor was written
to prevent. The split is **deliberate**, not a gap left by the four
fatias. Without one written decision, the top would look like the
old rodape by accident and someone would "fix" it with an organ the
metaphor does not actually cover.

The split is also what protects the boss bar. The boss's body **is**
anatomy, but it is not YOUR anatomy. If the boss bar became sacs
like the player, the eye would read "your body is on the line" —
true in the abstract, but the bar has to name the other body, not
your own. The rampa (`palette.health_color`) stays for the boss bar
and the enemy mini-bar, and the rationale is written in
[`docs/concepts/health-hud.md`](../concepts/health-hud.md).

**Reversibility.** The two-language split is **hard to reverse**
because the two layers are independent by design:

- The rodape's capsule spring (`CapsuleSpring`) has no
  counterpart in the top — `TopStack` reserves bands, it does not
  spring. Re-unifying the two means introducing a third verb
  ("spring? reserve? both?") that does not exist today.
- The `TopStack` has its own order-of-draw priority (permanents
  reserve first, banner transient last). Removing the lingua do
  mundo means re-stating the priority in the rodape's
  capsule/organ frame, which has no concept of "transient".
- The boss bar's palette choice (`palette.health_color`) is
  written separately in `health-hud.md`. Re-unifying means
  re-writing *that* doc to defend a single ramp.

**Surprise.** A reader who lands in `state_play._draw_hud` or
`lagarto/game/hud.py` without this doc will ask: "Why does the top
not look like the rodape?" The answer is here, the answer is
written, and the answer is not "we ran out of time".

**Trade-offs that were real.**

- *Two languages is more vocabulary than one.* A new contributor
  must learn that the rodape is anatomy and the top is not. The
  cost was made for the rule that survives the next contributor:
  "what organ is this?" is a complete answer for the rodape, and
  absent for the top, so the rodape gets the metaphor and the top
  gets the declaration.
- *Combo is the only top element that could verify as an organ,*
  and it does not. Pulling combo into the rodape would break the
  capsule's rule ("the capsule holds what you are"). Combo stays
  in `TopStack` and gets a louder pulse on the score line so the
  eye catches the moment without conflating "the run moved" with
  "the body moved".
- *The boss bar is the only place two readouts of "life" coexist,*
  and the asymmetry is the point. The rampa is the boss's own
  body weakening; the sacs are your own body weakening. Two
  visual treatments of the same fact, two complementary reads.

**Consequences.**

- [`docs/concepts/hud-anatomy.md`](../concepts/hud-anatomy.md)
  gains the "O que o topo e" section and links to this ADR.
- [`docs/concepts/health-hud.md`](../concepts/health-hud.md)
  declares the boss bar keeps `palette.health_color`, with the
  reason written.
- [`docs/concepts/ui-legibility.md`](../concepts/ui-legibility.md)
  declares the `TopStack` as the lingua do mundo's home and the
  reason it must not be retrofitted with the organ metaphor.
- [`CONTEXT.md`](../../CONTEXT.md) names the two languages
  canonically (**lingua do corpo**, **lingua do mundo**) and links
  back to this ADR.
- `tools/check_issues.py` adds a row that asserts the four
  decisive phrasings exist in the docs.

**Status.** Adopted as part of issue #134.
