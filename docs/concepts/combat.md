# Combat

The core is automatic ([Weapons](./weapon.md)). The player has four
manual verbs on top:

- **Investida** (dash) — contact damage + i-frames + **chain** (dash-kill
  recharges dash and refunds energy).
- **Rolamento** — the other dodge: same i-frames, no damage, a quarter of the
  energy, and steerable. See [Dodge](./dodge.md).
- **Tongue** — auto-aims the nearest edible / enemy; enemy takes damage
  and is pulled; costs energy.
- **Whip (Rabada)** — tail sweep on a dedicated button.

Combo streak (`game.combo`) climbs on kills and decays if you break off.

## The three offensive verbs go through a gate, at zero duration

Each owns an `Anticipation` (`dash_antic` / `tongue_antic` /
`whip_antic`), and all three durations are **0** in config. The Rolamento has
no gate: it hits nothing, and the rising-edge buffer plus its own cooldown
already stop a held button from repeat-firing. That looks
pointless until you know what it buys: the action fires exactly once per
press, so holding the button cannot repeat-fire. That was the actual bug the
gate was added for.

Wind-up itself is deliberately not the player's. A boss telegraphing is
information you act on; your own dash stalling is latency, and 60–100 ms on
the three core verbs read as the whole game being sluggish. Raise any
`*_ANTIC_T` above 0 and the coil comes back with it — the code path and the
`*_ANTIC_SQUAT` values are still there. Enemy and boss wind-ups are a
separate system and untouched.

One trap, worth knowing before touching this: `Anticipation.update` returns
its action on the first call **after** the timer reaches zero, so there is one
frame where `is_active` is already False and the action is still pending. A
trigger guarded only on `not is_active` re-arms in that frame and the action
then never fires at all. Every trigger also checks `antic.action is None`.

## Tongue

A chameleon slingshot in three beats, all driven off one clock
(`Player.tongue_t`, elapsed seconds) so there is no second timer to drift out
of sync with the one the hit resolves against. `Player.tongue_phase()` carves
it up; the lengths are `C.TONGUE_OUT_T / _STICK_T / _REEL_T`.

| Beat | What it is |
|---|---|
| **out** | Thrown. Ease-out cubic, so it leaves the mouth explosively and decelerates into the target. Ballistic and near-straight. |
| **stick** | The frame it goes taut. Springs past the target and settles. **The hit lands here**, not when the tongue gets home, along with every bit of impact juice. |
| **reel** | Drags the catch back. The longest beat, because watching your food come in is the payoff. |

### The invariant

`Player.tongue_tip()` is the tongue's position, and **both the hit and the
drawing read it**. The tongue was once drawn from a spring that chased the tip
with a settle time longer than the entire cycle, so the drawn tongue never
reached the target and pointed somewhere the hit did not happen. Anything that
wants to bend the tongue bends the *shaft*; the ends stay pinned to the mouth
and to the true tip. `tools/check_tongue.py` fails if they drift by so much as
a float.

### The shaft

`Player.tongue_path()` returns mouth-first, tip-last. The interior points are
springs chasing an ideal curve made of a downward sag plus a wave travelling
toward the tip, both enveloped by `sin(s * pi)` so they vanish at the pinned
ends.

The amplitude is **absolute pixels from conserved material**, not a fraction of
the current length — that is the whole trick. A tongue that bows by a fraction
of its length has its smallest bow exactly when it is longest, which reads as a
stiff arc. Instead the tongue is as long as it reached (`_tongue_len`, frozen at
the taut frame) and stays that long: as the ends close on each other during the
reel, the excess has nowhere to go but sideways. That is what coiling *is*, and
it is why the retract bunches into the mouth instead of sliding in like a tape
measure. Measured bow: ~5 px on the throw, ~45 px on the reel.

Spring stiffness is a trap worth naming: a *low* `C.TONGUE_LAG` looks like it
should mean more lag and more whip, but the reel is only ~10 frames long, so a
soft spring simply never arrives at the coiled shape and the tongue stays
straight.

### What it catches

Set at **stick**. Food is glued to the sticky pad and rides the tip home, then
`game.eat` fires on arrival — a soft follow instead lags a ~900 px/s tip by tens
of pixels, which reads as food trailing on a string. Enemies are pulled by force
so the world can still block them, and the outward knockback `take_hit` applies
is cancelled first: a hit cannot knock away something on a leash. The
**Arremesso** item inverts this — it flings the target out instead, and nothing
is carried.

## Whip (Rabada)

`Player._whip_hit`. Manual tail strike. Buttons: **middle click / Q**,
P2 **RAlt**, gamepad **Y**. Costs `C.WHIP_COST`, cooldown
`Player.whip_cooldown`.

### How the tail moves (`Player._whip_arc`)

The **tail** sweeps, not the body. Since [Spine](./spine.md) is
follow-the-leader, the only way to _steer_ it is via the head — which is
why the first two attempts missed (impulse on velocity then arc on head:
both threw the **entire body** sideways). The fix: **rebuild the rear
half's joints** from a pivot (`_whip_span`), distributing `C.WHIP_SWEEP`
degrees of curvature across all of them.

- **Ramp must be soft.** Putting the full turn in the first joint reads
  as a hinge (a "rigid piece rotating"); a quadratic ramp toward the tip
  puts ~80° in one link, above the spine's own bend limit (`bend=26`) —
  the corner beaks and the following `resolve` clamps it. A near-uniform
  ramp gives a near-circular arc — the lizard **keeps its natural
  curvature**.
- **Full-period envelope** (`sin(t*2π)`): sweeps one side, passes through
  centre, sweeps the other — one strike, in and out smoothly at zero.
- Anchor the angle on the **body** (`js[pv] - js[pv-2]`), **never on last
  frame's tail**: `spine.resolve` derives direction from previous
  positions, so anchoring on the tail feeds the curve back and the swing
  cancels to a tremor.
- The override survives to draw only because player contact is **soft** —
  the player is never pushed, so `collision.separate` skips its
  re-resolve. If contact turns hard again, this breaks.

### Hitbox = the actual joints

`spine.joints[-3:]` with an explicit reach `max_r*1.15` (the tip radius
is ~0.22 × max_r, too small). What you see is what hits; enemy head still
crits.

`whip_hits` (set, cleared on fire) = **one hit per target per swing**,
same pattern as `dash_hits`. Without it the damage-per-frame bug returns.

Hitbox uses the **same span that moves** (`_whip_span` serves both).
When only the last 3 joints were tested and the moving span grew to 6,
the tail visibly swept over the enemy without hitting.

### Tail modifiers (were cosmetic)

- **`club`** → `WHIP_CLUB_MULT` damage + `WHIP_KNOCK_CLUB` knockback +
  bigger shake.
- **`sting`** → `apply_poison`. Enemy stings `apply_slow` — the divergence
  is on purpose.

### Damage scales with Might

`_whip_hit` multiplies by `player.might`. Naked whip is weak on purpose;
the damage comes from upgrades. **Vigor** (+20%/card) and **Potência**
(DNA, +6%/level) finally improve the strike. Values: 2 naked → 5 with
club → 12 with club + Vigor + DNA.

Dash gets the same treatment (`Player.dash_damage()`): base 5 → 4, ×
`DASH_WINGS_MULT` (1.5) with Membranas, × `might`. Membranas already
improved dash speed / duration / cooldown / cost but **not** damage,
despite the card saying "stronger dash" — now it does. 4 naked → 6
with membranas → 13 with membranas + Vigor + DNA.

The calc lives in a method because there were **two** call sites reading
`C.DASH_DAMAGE` directly (enemy and nest); scaling one would skip the
other silently. See [ADR-0008](../adr/0008-might-scales-all-damage.md).

Card descriptions must tell the truth: `might` touches weapons **and**
dash **and** whip. Membranas' unkept promise went unnoticed for a long
time.

### Reach

The arc behind / beside the lizard (measured: 1-2 targets per strike),
not the whole screen. When the strike still moved the body it caught
4-5, and per-hit damage was lowered to compensate; with the tail alone
it went back near dash, and the cost is a longer cooldown.
No repeat hits on the same target (`whip_hits`), and the tail does not
hurt outside a strike.

`take_hit` **assigns** `vel`, so extra push comes **after** the call.

## Dash damage — one hit per lunge

`_collisions` runs **every frame**; while `p.dashing` (0.16 s ≈ 10
frames) the same enemy was hit 10× — **30 damage per dash instead of 3**
(60 with head crit). That, not HP balance, was the real cause of
"enemies die too easily". `Player.dash_hits` (set, cleared on dash
start) enforces one hit per target per dash; damage is `C.DASH_DAMAGE`
(5, crit 10; nest takes 2×).

**When you touch contact damage, always check if the source is
per-frame.**

## Collision: allies do not collide

`kind ∈ {player, friend}` never collide with each other
(`collision.FRIENDLY`) — fluid battles. Enemy ↔ enemy still separates
hard.

## Soft player↔enemy contact

Feedback: being pushed by every enemy felt like pinball. The player is
**never displaced**: passes through, **pushes the enemy** (full push, no
weight-by-size), and pays in **speed**. `collision.separate` accumulates
overlap depth in `creature.clog`; `Player.update` normalises, smooths
(`clog_f`, approach 9/s) and applies `C.CONTACT_DRAG`. Ignored during
dash (passing through is the point).

Enemy ↔ enemy still uses hard separation — otherwise the stacking bug
returns.

See [ADR-0006](../adr/0006-soft-player-contact.md).

### Two independent brakes that multiply

Sting slow × contact clog. Measured in a 6-enemy fight: 89% × 89% =
**80% average speed**, 40% of the time under 80%. Neither is bad alone;
together they explain "why am I slow?" — and neither had any on-screen
cue. `Player._draw_slow_mark` now draws cold rings under the body while
the slow lasts.

### Sting slow triggered even without a hit landing

`_contact` called `apply_slow` outside `hurt()`'s result — which exits
early on i-frames. So you took **50% slow with no damage number to
explain it**. Worse: duration 1.4 s vs `attack_cd` of 0.8 s — permanent
by construction. Measured: a scorpion kept the player slow **59% of the
time**. Today `hurt()` **returns whether the hit landed** and the sting
only slows on true. `STING_SLOW_TIME` (0.4) is much less than
`attack_cd`.

Third time this project trips on "effect lasts longer than the interval
that reapplies it" — Ácido, venom puddle, sting. See
[Enemy behaviors](./enemy-behaviors.md).

### Two more clog fixes

- **Prey braked like enemies.** `movers` includes prey, and the soft
  ramp fires for any non-ally pair with the player. A harmless grazer at
  30 px was leaving the player at 49% speed. Today only
  `collision.DRAGS_PLAYER` (= enemies) accumulates clog; prey still get
  pushed but do not cost speed.
- **Saturated with one enemy.** `clog` sums 5×5 sample pairs; a runner
  already hit ~25 against divisor `max_r*1.2` → binary brake
  (100% or 45%), no gradient. `C.CONTACT_FULL` (3.0) scales the divisor
  to "buried in ~3 bodies". Measured after: 1 enemy ≈ 90%, 4 ≈ 68%,
  6 ≈ 65%.

## Related

- [Weapon](./weapon.md) — the automatic core.
- [Hitbox](./hitbox.md) — body sampling + head crit.
- [Damage model](./damage.md) — player HP flow.
- [ADR-0006](../adr/0006-soft-player-contact.md) — soft contact.
- [ADR-0008](../adr/0008-might-scales-all-damage.md) — Might everywhere.
