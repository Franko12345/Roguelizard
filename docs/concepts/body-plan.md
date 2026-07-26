# Body Plan

`Genome.plan` forks `rebuild_body` / `draw` / telegraph. Five values:

- **`'normal'`** — [Spine](./spine.md) + [Legs](./leg.md). Every classic
  creature.
- **`'segmented'`** — CENTOPEIA. Chain of ringed circles + metacronal legs.
- **`'tentacle'`** — POLVO/KRAKEN. Mantle + arm sub-chains.
- **`'orbital'`** — OLHO-SÍSMICO. Compact eyeball + bone-tipped tentacles.
- **`'fixed'`** — A MURALHA. A wall that does not move at all.

`plan` is a slot on `Genome.__slots__` — the trap of always. Missing it
means silent fallback to `'normal'`.

Both new plans follow the [Enemy behaviors](./enemy-behaviors.md) rule:
each attacks one player habit.

## CENTOPEIA (`plan='segmented'`, `behavior='burrow'`)

Body = chain of ringed circles (the ink ring on each segment _is_ the
segmentation) + tiny legs in **metacronal wave** (partner = pair 2
segments back, so it ripples instead of marching). Mechanic: **burrower**
(Para-Bite / Moles of Isaac): `surface → digging → under → erupt`.

### Diving cannot mean "vanishes"

`digging` is a rooted phase (`CENT_DIG_TIME`) that opens a growing hole
and throws dirt — telegraphs that it is about to submerge. Then
`burrowed=True`.

### Intangible while under — in one place

`hit_test` returns `None` and `collision._samples` skips creatures with
`burrowed` (same pattern as flyer). All damage flows through `hit_test`,
so this covers dash + projectile + aura in one spot. During `digging` it
is still vulnerable — that is the counter-attack window.

### Fair telegraph (`_draw_burrow`)

An **eruption ring** at `dive_to` (locked in on dive) fills as it
surfaces + the mound travels with a dirt trail. Same rule: draw the
radius, not just a warning.

## POLVO / KRAKEN (`plan='tentacle'`, `behavior='grapple'`)

Pulsing mantle + arms as sub-chains (`self.arms`, resolved in
`integrate`), with a travelling wave + swirl to undulate like a
tentacle, and trailing to whip when moving. Drawing is **continuous**
(same left/right-rim outline + spine cap — the user asked for smooth
flesh, not beads).

### Grapple mechanic

Gungeon Gripmaster: closes in slowly, roots, and **stretches all arms
toward you** (`arm_target` makes `_resolve_arms` converge/stretch —
that convergence _is_ the telegraph, `OCTO_WINDUP` > 27f). On the snap,
**pulls** you (`OCTO_PULL_DIST`) and **slows** you (`apply_slow`).
Escaping before the snap negates.

Arms are cosmetic: the hitbox is the mantle (`hit_test` samples the
short spine); the danger is the grapple, not the touch.

### Slow bruisers must ignore knockback

`take_hit` / `damage` assign / add velocity for knockback, so every spit
zeroed the approach and the octopus never arrived. `genome.knockback`
(multiplier <1, a new dial on `__slots__`) fixes it in one place —
octopus 0.28, everyone else 1.0. And it **commits to the approach**
(does not retreat "to keep distance"), because the only defence is you
**run** (top speed < player walk). Measured: closes from 430 px to
~16 px under fire, then grapples.

## OLHO-SÍSMICO (`plan='orbital'`, B9)

A boss body, not a species you meet in a wave. `rebuild_body` builds a
compact 4-joint ball (`link = maxr * 0.3`, so the joints cluster instead of
stretching into a spine), **zero** IK legs, and 6 arms reusing the octopus
arm chains — so the travelling wave and the trail come for free. Drawing is
a glowing sclera bobbing on `wobble`, veins that redden and beat faster per
phase, and a vertical cat-slit iris that dilates per phase. The iris reuses
the existing pupil spring: `eye_blink_tick` points `aggro` at the player so
`_pupil_dir` tracks and lags on a dash.

### The eye is the weak point, via two default-off attributes

The blink mechanic did not get its own code path in `hit_test`. It got two
generic attributes that every other creature leaves unset, so every other
creature stays byte-identical:

- `eye_shielded` — while true, `hit_test` returns `'body'` for a head hit,
  denying the caller-side head crit.
- `dmg_taken_mult` — 0.25 while blinking, so a hit that lands anyway does
  75% less.

`eye_blink_tick` rides the existing `champion_ticks` per-frame hook list, so
the boss FSM was not touched to add it.

## A MURALHA (`plan='fixed'`, B10)

A wall occupying one side of its [arena](./boss.md). 5 joints, wide and
short. It is the one body whose species carries `speed=0.0` — and that has
consequences the other plans never raised:

- `steer()` and `integrate()` both divided by `max_speed`, so a creature
  that cannot move raised `ZeroDivisionError` the instant it tried. Both are
  guarded now; a speed-0 creature simply never steers and never run-squashes.
- The species is `role='boss'`, **not** `role='enemy'`. `ENEMY_SPECIES` feeds
  `THEMES['invasao']['pool']` verbatim and the boss `summon` pattern falls
  back to it, so `role='enemy'` let a normal wave roll a wall as a mook.

### Own plan vs re-skin

A Muralha needs its own species and plan because a wall is not a lizard.
ANKH does not: it is a golden `horned` with overrides, because its identity
is its 4-phase structure. Overriding a mobile species into `plan='fixed'`
was tried and produced a wall that walked at the player — the plan changes
the drawing, the species carries the speed and the damping.

## Related

- [Genome](./genome.md) — where `plan` and `knockback` live.
- [Enemy behaviors](./enemy-behaviors.md) — the "attack a habit" rule
  these follow.
- [Boss](./boss.md) — the arena, and the re-skin-vs-own-plan rule.
- [Hitbox](./hitbox.md) — `eye_shielded` / `dmg_taken_mult`.
