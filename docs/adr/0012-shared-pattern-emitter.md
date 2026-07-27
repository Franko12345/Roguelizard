# One pattern emitter shared by bosses and common enemies

**Context.** The ~20 bullet-hell arrangements (`radial_burst`, `fan_shot`,
`spiral_pattern`, `eye_laser`, `bouncing_bullets`, …) lived in
`lagarto/flow/boss/patterns.py` and were signed `(boss, game, target)`. Each one
that needed tuning opened `PATTERNS[boss.boss_ai.pattern_id]` *itself*, so
firing a spiral required a `BossAI` on the other end. No common enemy could
reach them: to make an ordinary enemy shoot a fan, someone would have written a
second fan.

**Decision.** The pattern functions move to `lagarto/combat/emitter.py` and are
signed `(shooter, game, target, dials)`. Dials arrive as an argument instead of
being looked up; `flow/boss/patterns.py` keeps `PATTERNS` and becomes what it
always was in practice — the boss-side dial table, whose rows point at the
emitter. `BossAI` hands the chosen row in as `dials`. Continuous patterns still
park their state on the shooter (`_spiral_left`, `_barrage_left`,
`_breath_left`) and still need their `_tick_*` called every frame by whoever
owns the creature.

**Why.** A pattern only ever touches `spine.joints[0]`, `color`, `pos`, `max_r`
and somewhere to keep state — which every `AILizard` has. The one real coupling
was the dial lookup, and the lookup was never the pattern's business. Doing this
as a pure refactor, before any enemy uses it, is deliberate: any boss regression
is attributable to this change and not to the content that follows.

**Consequences.**

- `lagarto/combat/` may not import `lagarto/flow/`. The emitter's three
  cross-layer needs (`species`, `rounds` themes, `weapons`) stay
  function-local, as they already were.
- The dial defaults are still `C.BOSS_*` / `C.MURALHA_*` / `C.EYE_*` constants.
  Keeping them was the price of "not one pixel changes"; a common enemy that
  wants different numbers passes dials, and the names read oddly until someone
  has a reason to rename them.
- `dials` is a plain dict and is required. A caller with nothing to tune passes
  `{}` — no default, because a silently-empty dial set is how a pattern ends up
  firing boss numbers by accident.
- The boss package no longer re-exports the pattern functions from
  `lagarto.flow.boss`; they are imported from `lagarto.combat.emitter`.
- Reversing this means re-coupling every pattern to `boss_ai`, and any enemy
  built on the emitter in the meantime loses its attack.

**Verification.** `tools/check_issues.py` (#101) asserts every `PATTERNS` `fn`
and `select` lives in the emitter with exactly that signature, that
`patterns.py` defines no pattern, and that the emitter never mentions
`boss_ai.pattern_id`. `tools/check_bosses.py` drives all eleven bosses through
every phase.

See also: [`Boss`](../concepts/boss.md) ·
[ADR-0010](./0010-single-file-per-module.md) — one responsibility per module.
