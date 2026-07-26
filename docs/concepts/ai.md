# AI

`AILizard` dispatches per `genome.behavior`. Each branch is a small
steer/attack loop — no state machine class hierarchy.

## Behavior branches

- **`chase`** — melee, straight approach.
- **`ranged`** — the spitter keeps distance and fires `projectile.spit`.
- **`lunge`** — the spider telegraphs and pounces.
- **`hop`** — frog.
- **`fly`** — [VESPA](./enemy-behaviors.md); skipped by collision samples.
- **`bomber`, `gunner`, `venom`** — phase-2 behaviors. See
  [Enemy behaviors](./enemy-behaviors.md).
- **`burrow`, `grapple`** — body-plan behaviors. See
  [Body plan](./body-plan.md).

## Ecosystem

Predators with `diet=('prey',)` hunt real prey; prey flees the player
**and** predators (`game.nearest_threat`).

## Status effects

- **`apply_slow`** — affects the steer.
- **`apply_poison`** — DoT on creatures.

The player's whip poisons; enemy stings slow. Divergence is on purpose
(see [Parts](./parts.md)).

## Posing: the state has to be readable before the attack

`creatures/ai/posing.py`, `apply_state_pose(creature, state, dt)`. A hunting
lizard and a fleeing one used to look identical — they moved but never changed
posture. This is the body-language layer: read the AI state and ease the
**resting** posture toward a target, so intent is legible before anything
lands.

| state | `squat_bias` | tail stiffness |
|---|---|---|
| idle / graze | 1.00 | 0.70 |
| alert | 1.10 | 1.70 |
| hunt | 0.88 | 1.30 |
| attack | 1.25 | 2.00 |
| hurt | 0.82 | 0.40 |
| flee | 1.15 | 0.90 |

Nothing new is drawn: it biases the two knobs the body already animates from
— `squat_bias` (the squash target) and the tail spring's stiffness (tight =
held high, loose = dragging). Same idiom as `_apply_mood_pose`.

Two rules make it safe to call every frame:

- **Eased, never snapped.** Targets go through `approach`, and the squash is
  smoothed again inside `integrate`.
- **Applied BEFORE the behaviour tick.** A transient wind-up telegraph (lunge
  crouch, hop gather, spit coil) writes `squat_bias` after this and wins for
  its window. Posing only sets the posture underneath.

Reads AI state only, so the game-logic layer is untouched. Guards a missing
tail spring, which is how centipede and kraken pose without crashing. Bosses
stay on `_apply_mood_pose`.

## Related

- [Species](./species.md) — roster of species per behavior.
- [Enemy behaviors](./enemy-behaviors.md) — phase-2 branches.
- [Body plan](./body-plan.md) — plan-specific behaviors.
- [Combat](./combat.md) — how AI hits and gets hit.
- [Procedural animation](./procedural-animation.md) — where posing sits in
  the Intent / Action / Reaction / Follow-through chain.
