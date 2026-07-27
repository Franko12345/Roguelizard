# Projectile

Every shot in the game is one class: `lagarto/combat/projectile.py`. It carries
a position, a velocity, damage, and an optional on-hit `effect`
(`'poison'` / `'slow'`). The Game owns the list, advances it in
`Game._update_projectiles`, and resolves hits against players (`hostile=True`)
or against creatures (`hostile=False`).

Everything past that is a **hook**.

## The three hooks

A modifier is a plain function. There is no base class, no registry, no
hierarchy — you append a function to one of three lists and it runs.

| Hook | Signature | Runs in | What belongs there |
|---|---|---|---|
| `on_update` | `fn(pr, dt, game)` | `Projectile.update` | **Movement.** How the shot travels. |
| `on_hit` | `fn(pr, victim, game)` | `_update_projectiles`, where the hit lands | What it does to what it touched. |
| `on_death` | `fn(pr, game)` | `_update_projectiles`, one sweep over the dead | What it leaves behind. |

Two axes, from the two references this game steals from:

- **Gungeon is movement.** How the bullet *travels* — curves, accelerates,
  ricochets. That is `on_update`.
- **Isaac is the modifier.** What the bullet *does* when it lands or dies, and
  they **stack**. That is `on_hit` / `on_death`.

`on_update` runs **after** the position integrates and **before** the
out-of-bounds kill. That ordering is what lets `bounce` clamp a shot back
inside the arena instead of watching it die one frame later.

`on_death` fires in a single sweep over everything that died this frame,
not at each `pr.dead = True`. A shot can die on four different paths (life
expiry, out of bounds, hitting a player, hitting a nest) and a fifth one added
later would otherwise silently skip the payload.

### What ships today

- `projectile.homing` — `on_update`; curves toward whoever is on the **other**
  side (`nearest_player` for a hostile shot, `nearest_enemy` for a friendly
  one). It used to hunt `nearest_enemy` unconditionally, which made a hostile
  shot wearing the hook chase its own horde; the side was already on the
  projectile. `pr.home_mult` (default 1) tightens the curve — that is how a
  stacked player modifier gets stronger without a second function. The Ferrão
  weapon, the ferrão item, the player's Rastreio, a boss's `homing_fan`.
- `projectile.bounce` — `on_update`; ricochets off the arena walls, losing
  speed each time. Reads `pr.bounces_left` / `pr.bounce_damp` off the shot, so
  a mirrored copy keeps its own count. A Muralha's bouncing bullets.
- `projectile.leave_puddle(**payload)` — `on_death`; drops a
  [Puddle](./weapon.md) where the shot ended, whether it connected or simply
  landed. The venomer's area denial.

`pierce` is not a hook: it changes how the collision loop itself iterates
(pass through, remember the enemy), not what happens on a hit.

## The asymmetry — the player stacks, the enemy picks one

The player may stack modifiers freely. An **enemy** shot chooses **one**
movement and stops there.

Both halves have exactly one implementation site:

- **Player.** `Game._stack_shot_mods`, called from `spawn_projectile` — the one
  choke point every friendly bullet already passes (the same reason Retaguarda
  lives there). The stacks are counters, not flags: `shot_bounces` /
  `shot_homing`, raised by the Rebote and Rastreio [mutations](./evolution.md).
  Two Rebotes are two ricochets.
- **Enemy.** `emitter._launch`, which appends `dials['mod']` — singular, by
  construction. A "new" boss pattern is dials plus at most that one hook
  (`homing_fan` is `fan_shot` + `homing`, and nothing else).

This is deliberate and it is the cheap defence against combinations nobody
tested: an enemy bullet that bounces *and* curves *and* splits is a
combinatorial space that no amount of playtesting covers, and the player is the
one who has to read it at ~100 bullets on screen. The player's side of the same
explosion is a build they opted into and can see coming.

Nothing enforces this in code — no validator, no registry. It is a rule the
emitter follows, written down here so it stays a rule.

## Colour codes the side, not the species

The bullet body is **fixed per side**: hostile is hot orange, friendly is the
player's green, each with a white-hot centre. The creature's own colour survives
only in the additive halo. See
[ADR-0014](../adr/0014-bullet-colour-encodes-side.md) for why this partially
overrides [ADR-0001](../adr/0001-genome-is-the-creature.md), and it applies to
bosses too, with no exception.

The whip's Contragolpe flips `pr.hostile`, so a batted-back shot repaints
itself; it only has to move `pr.color` to the friendly hue so the halo agrees
with the body.

**The side lives in the mid ring, not the core.** Both cores are near-white by
design, so growing one past about half the radius makes hostile and friendly
converge on the same white pill — which undoes the whole rule at exactly the
density it exists for. The dark rim is an *outline*, one pixel of ink to hold
the shape against a bright floor; filled to the full radius it puts a dark ring
between core and halo and the bullet reads as a bubble instead of a slug. The
streak is drawn in the mid colour for the same reason: it is the longest part of
the bullet on screen, so a white one throws the side away.

## Lobbed shots

`Projectile.lift` is a **fake height in screen pixels**. The world position
stays flat — this game has no z — so only the draw moves up, and the telegraph
already on the ground doubles as the shadow. The `arc(height)` hook rides
`on_update` and follows a sine over the shot's own lifetime, so the apex lands
halfway and the height is exactly zero when it dies.

`emitter.lob_shot` takes two dials that make this usable as a weapon:

| dial | what it does |
|---|---|
| `at` | land on a point the caller already committed to, instead of chasing the player |
| `flight` | pin the travel **time** rather than the speed, so the same beat elapses however far it was thrown |

Together they are what lets the MORTEIRO's footprint and its shell be one event:
the patch is drawn at the throw, `flight=C.MORTAR_ARM` makes the shell land as
the countdown ends, and the puddle arrives from the shell's own `on_death`. One
clock, one cause — instead of a timer conjuring a hazard out of nothing.

The streak has to be lifted with the body, or a lobbed shot draws a rigid spike
from its own height down to ground it has not reached yet.

## Size and glow

Two dials in `config.py`, both draw-only — collision is body overlap against the
creature, so neither changes what a bullet can reach:

| dial | what it does |
|---|---|
| `BULLET_SCALE` | multiplies every caller's `radius=`, which stays a relative weight |
| `BULLET_GLOW` | intensity of the additive halo |

The glow is **two** passes: a wide soft one the scene reads as light, and a
tight hot one on the body so the centre blows out instead of sitting flat inside
its own halo. Both go through the quantised glow cache. `palette._glow_sprite`
scales its step count with radius (10 / 18 / 26) — steps cost nothing per frame
because they only run on a cache miss, and ten of them banded visibly into
concentric rings once bullets got big enough to take the second pass.

## Budget

The body is a sprite cached on `(even radius, side)` — only affordable
*because* the body stopped carrying the creature's colour, which collapses it to
two colour variants. The trail is one line, not seven fading circles.

Measured at 92 bullets on screen: **0.87 ms** of the 16.6 ms frame, of which the
two glow passes are most of it (one pass alone measures 0.42 ms). The check
asserts under 4 ms. See [Performance](./performance.md).

## Verification

`tools/check_projectile.py` — the hooks fire and are the only path (a hookless
shot does not curve and dies at the wall), bullets of five different species
render byte-identical bodies within a side while the halo still varies, the
sprite cache stays under its cap, and ~100 bullets are timed against the frame.

## Related

- [Combat](./combat.md) — the verbs that fire and reflect shots.
- [Enemy behaviors](./enemy-behaviors.md) — the shooters.
- [ADR-0012](../adr/0012-shared-pattern-emitter.md) — the emitter that spawns
  boss and enemy patterns through `game.spawn_projectile`.
- [ADR-0009](../adr/0009-glow-cache-quantized-keys.md) — the cache-key rule the
  body sprite follows.
