# HUD reads as anatomy: capsule framing, organ rhythm, four beats

**Context.** The HUD was a stack of readouts that happened to live near
each other. There was no rule for where a new medidor went, no rule for
how the container around the readouts should feel, and the readouts
themselves were at three different rhythms in series with no shared
parent.

**Decision.** The HUD follows the **anatomy** metaphor from
`docs/concepts/hud-anatomy.md`:

- Every player block is wrapped in a framed **capsule** (`ui.panel`,
  the same primitive used by the menu and level-up screens).
- The capsule has its own low-frequency spring; each organ inside has
  its own, faster rhythm.
- Every element obeys the four beats of procedural animation:
  Intent / Action / Reaction / Follow-through.
- The capsule lives in the bottom corners (P1 left, P2 right). The
  top-centre column is owned by `TopStack`.

**Why.** The metaphor turns "where does this go?" into "what organ is
this?" — a decision rule that survives the next contributor. The
two-layer rhythm is the fix for the silent flagellum: an organ that
waves inside a container that does not react reads as decorative.
Framing every block in the same `ui.panel` is what makes the four
readouts look like one language instead of four fragments.

**Reversibility.** Hard. Reversing it means moving the player blocks
back to the top corners (collides with `TopStack`), unwiring the
per-player `CapsuleSpring` (kills the only feedback the capsule has),
and re-stating the rule in two ADR-shaped docs. Every future HUD
element written under this rule would also need to be re-thought.

**Surprise.** A reader who lands in `state_play._draw_hud` without
this doc will ask three questions:

- Why are the vitals at the bottom? (To give the top-centre column
  its own room — `TopStack` solves a problem that only exists when
  the player blocks are out of it.)
- Why does the panel shake on a value change but not on a `pulse`
  call? (Because `palette.health_color` was retired in favour of a
  per-organ palette; the capsule shake is the only thing that says
  "something inside you changed" without naming which one.)
- Why does the active item have its own corner? (Because a fourth
  dial would not fit the 216-px panel at the 68-px pitch — see
  the comment that lived at `state_play.py:156` before this
  refactor.)

**Trade-offs that were real.**

- *Identity vs scan speed.* The dark framed panel costs the player
  the first second of the run: "what is that?" Frameless, the
  block would scan instantly. The trade was made for the rest of
  the run, when a body that takes hits needs to read as a body.
- *Moldura vs orgânico.* The capsule is rectangular, not a
  bio_shape like the `bio_bar`. A biological capsule would be
  more on-brand; a rectangular capsule is faster to read at a
  glance and easier to put more organs inside. The bars themselves
  stay bio; the container is rect.
- *Slow vs fast rhythm.* Two rhythms in series costs a millisecond
  of sim time per frame (the 30 Hz sub-step + the per-frame
  organ updates). A single rhythm would be cheaper; the cost was
  made for "you can tell which organ fired" — the bar that fills
  is read alongside the panel that shakes, not as the same thing.

**Consequences.**

- `lagarto/game/hud.py` gains `CapsuleSpring` and `PlayerCapsule`;
  the state module owns one capsule per player via
  `Game.hud_capsules`. The sim is at 30 Hz, the draw is at 60 Hz,
  the spring interpolates between steps.
- `lagarto/core/config.py` exposes the layout numbers
  (`HUD_PANEL_W`, `HUD_PANEL_H`, the spring constants, the shake
  amplitudes) in one block.
- `tools/check_hud_anatomy.py` pins the four claims with teeth:
  capsule anchor, framing primitive, no TopStack collision, spring
  settling.
- `tools/check_issues.py` adds a row that runs the new check.
- `docs/concepts/hud-anatomy.md` is the rule; this ADR is the
  decision to adopt it.

**Status.** Adopted as part of issue #130.