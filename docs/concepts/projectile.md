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
- `projectile.spiral_arc` — `on_update`; orbits the nearest player with a
  decaying radius (issue #164). State lives on the projectile (`pr.spiral_radius`
  / `pr.spiral_angle`); the shot converges in ~70 frames and the standard
  body-overlap collision applies the hit. The Wasp's `spiral_arc` pattern at
  phase 3.
- `projectile.leave_puddle(**payload)` — `on_death`; drops a
  [Puddle](./weapon.md) where the shot ended, whether it connected or simply
  landed. The venomer's area denial.
- `projectile.chain_link` — `on_update`; pairs two `chain`-tagged projectiles
  within `CHAIN_LINK_DIST` (px) and breaks on `CHAIN_BREAK_DIST` or death.
  `chain_damage` (on_hit) applies `CHAIN_DMG_BONUS` while a link is active.
  ANKH's `chain_arc` (issue #167). The hook owns link state only — the
  Bezier line is rendered from `Projectile.draw`, once per pair (gated to the
  lower-id endpoint so each pair draws exactly once).
- `projectile.wave` — `on_update`; a perpendicular sine offset applied each
  frame so the trajectory traces an "S" or zigzag rather than a line.
  Primordial's `wave_fan`.
- `projectile.boomerang` — `on_update`; after `BOOMERANG_RETURN_TIME` (or
  `BOOMERANG_RANGE` from `pr.shooter_pos`), flips the velocity and clears
  `pr.hostile` so the returning shot does not bite its own shooter. Mae-Escaravelho's `boomerang_burst`.
- `projectile.burst_stop` — `on_update`; after `BURST_STOP_TRAVEL`, parks the
  shot (zeroes `vel`), spawns a `Puddle` from the configurable
  `BURST_STOP_PUDDLE` payload, and marks the projectile dead. The "lands as a
  mine" attack. Mae-Escaravelho's `burst_stop_burst`.
- `projectile.spiral_arc` — `on_update`; overwrites `pr.pos` each frame to
  orbit the target with `SPIRAL_OMEGA` rad/s and a `SPIRAL_RADIUS_DECAY` per
  60-Hz frame (`SPIRAL_RADIUS_INIT` start). When the radius collapses below
  5 px or the shot lands within 10 px, the projectile snaps onto the target
  so the normal collision deals the hit. Wasp's `spiral_arc`.

The `home_mult` dial is what makes the original `homing` hook double as
"slow_homing": a value < 1 smooths the curve, a value > 1 tightens it. It
reads the same projectile attribute, so a fan pattern can ship a softer or
harder curve via a single dial without a second hook function.

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
backward sparks are emitted in the mid colour for the same reason: they are the
longest thing the shot leaves on screen, so white ones throw the side away.

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

`lift` is now the *only* thing the draw offsets. It used to have to lift the
trail line too, or a lobbed shot drew a rigid spike from its own height down to
ground it had not reached yet; with the line gone that special case went with
it. The sparks stay on the flat world position on purpose — they fall behind on
the ground the shell is arcing over, which is the shadow reading the telegraph
already gives.

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

## The trail is sparks, not a line

Nothing is drawn behind the bullet. What tells you where a shot is going is a
thin stream of sparks it sheds along the way: `Projectile.update` calls
`FX.spark_burst` with `direction=-vel`, so each spark flies *against* the
motion inside a narrow cone, brakes, and dies in `BULLET_SPARK_LIFE` seconds.
They are emitted a body-width behind the shot — emitted at `pos` they are
swallowed by the bullet's own halo, and the shot grows a hair instead of
shedding a spark.

The reference is Enter the Gungeon: the bullet is a clean glowing ball and the
heading comes from loose bits falling behind it. A solid tail is a flat-capped
rectangle glued to the body, and the bigger the bullet the more it reads as a
skewer — which is exactly what happened when `BULLET_SCALE` went to 1.45.

`FX.spark_burst` is shared with the whole game, so the directional cone is an
optional argument, not a second function: without `direction` the burst is
omnidirectional, which is what an impact wants. See [Juice](./juice.md).

## Budget

The body is a sprite cached on `(even radius, side)` — only affordable
*because* the body stopped carrying the creature's colour, which collapses it to
two colour variants. Nothing else in the draw scales with the shot's history.

**The sparks spend a pool, not a frame.** `FX.MAX_SPARKS` is 260 and
`spark_burst` drops the oldest on overflow, so a bullet emitting one spark per
frame is not a rendering cost — it is a hundred bullets evicting the tongue, the
dash and every impact in the game. Live sparks per bullet are
`BULLET_SPARK_LIFE * 0.75 / BULLET_SPARK_GAP`; the two dials are one budget and
have to be read together.

Measured with 100 live bullets for 2 s, peak pool occupancy:

| gap | life | peak sparks |
|---|---|---|
| every frame (0.017 s) | 0.2 s | **260 — the cap, evicting** |
| 0.05 s | 0.2 s | 252 |
| 0.09 s | 0.2 s | **188** ← shipped |
| 0.12 s | 0.2 s | 159 |
| 0.09 s | 0.5 s (the generic life) | **260 — the cap, evicting** |
| 0.16 s | 0.5 s | 257 |

So the short life is the real lever, not the spacing: keeping the generic 0.5 s
still fills the pool at a spacing so wide each bullet has barely one spark
alive. Shipped at 0.09 s / 0.2 s — 188 of 260, leaving ~70. That is enough,
because a 30-second instrumented run of the actual game peaks at **66** sparks
for everything else put together. The pool was never given its own bullet half:
spacing fits, and a second pool is a second update loop and a second draw loop
for a problem two constants already solve.

Frame cost at 92 bullets: **0.43-0.59 ms** of the 16.6 ms frame, down from
0.87 ms with the line — and ~1.1 ms once the sparks' own update and draw are
counted. The check asserts under 4 ms. See [Performance](./performance.md).

## Verification

`tools/check_projectile.py` — the hooks fire and are the only path (a hookless
shot does not curve and dies at the wall), bullets of five different species
render byte-identical bodies within a side while the halo still varies, the
sprite cache stays under its cap, and ~100 bullets are timed against the frame.

Two of its assertions guard this page's trail rules:

- **Nothing is drawn behind the bullet.** The draw is sampled in a band on each
  side of the body along the travel axis and the two have to match; a streak
  piles ink on one side only. Mirror about `cx - 0.5`, not `cx` — every sprite
  is an even-sided square blitted at `sp - half`, and the half-pixel alone reads
  as 7% of a streak.
- **The sparks do not fill the pool.** A hundred bullets for two seconds, and
  `len(fx.sparks)` must stay under `FX.MAX_SPARKS`. It also checks the sparks
  still carry the side's `mid`, so ADR-0014 cannot quietly leak out of the body
  into the trail.

## Related

- [Combat](./combat.md) — the verbs that fire and reflect shots.
- [Enemy behaviors](./enemy-behaviors.md) — the shooters.
- [ADR-0012](../adr/0012-shared-pattern-emitter.md) — the emitter that spawns
  boss and enemy patterns through `game.spawn_projectile`.
- [ADR-0009](../adr/0009-glow-cache-quantized-keys.md) — the cache-key rule the
  body sprite follows.
