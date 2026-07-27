# Dodge — two verbs, one i-frame rule

The player has **two** dodges, and they are deliberately different verbs
rather than one tuned one:

| | **Investida** (`dash_*`) | **Rolamento** (`roll_*`) |
|---|---|---|
| Damage | `C.DASH_DAMAGE`, scaled by Might | **none** |
| Energy | `C.DASH_COST` (14, 18 net; 14 with Membranas) | `C.ROLL_COST` (5) |
| Cooldown | `Player.dash_cooldown` (0.45 s) | `C.ROLL_CD` (0.2 s, from the end of the roll) |
| i-frames | `0.16 s` (0.2 with Membranas) | `C.ROLL_TIME` (0.15 s) |
| Movement | velocity impulse, `3.0×` max speed (`3.5` with Membranas) | velocity impulse, `C.ROLL_SPEED` (`3.4×`) |
| Ground covered | **+223 px** over walking, per press | **+174 px** — 34.8 px per energy point against the investida's 12.4 |

Both are invulnerable, and `Player.hurt` is the single place that says so
(`if self.dashing or self.rolling or ...`). Every damage source funnels through
`hurt`, so there is exactly one condition to read — no `invuln` field, no
per-source guard.

## Why two buttons instead of a better dash

The investida is a *punctual* answer: 0.16 s of i-frames on a 0.45 s cooldown is
36% of the cycle in a burst and ~5% sustained once energy runs dry (100 energy,
6/s regen). At 5% you cannot raise bullet density without being unfair. The
rolamento buys the missing frequency — cheap and short — and pays for it by
dealing no damage and by covering less ground per press.

**Both launch.** The rolamento shipped without an impulse, on the theory that
"steerable but going nowhere" was a clean contrast to the investida's forward
commitment. In play it moved the lizard about a third of a body length and read
as a roll animation with no dodge attached. A dodge whose job is escaping a
bullet has to leave the place the bullet is going. What separates the two verbs
is damage and cost, not whether they move you.

Nothing about the investida changed. See
[ADR-0013](../adr/0013-two-dodge-verbs.md) for the decision, the measurements,
and how the registered risk actually played out.

## The pose: squash, then release

`Player._roll_pose` is two beats, not a roll:

- **Compress** while the roll is live — `squat_bias` down to `C.ROLL_SQUAT`,
  legs tucked with `leg_pull`.
- **Release** when it ends — `squat_bias` goes *past* neutral to
  `C.ROLL_STRETCH` and settles back. The overshoot is the whole difference
  between a spring letting go and a number returning to 1.0.

**Fast in, slow out.** `C.ROLL_EASE` (30) governs the compression, which has to
arrive inside 0.15 s; `C.ROLL_RELEASE_EASE` (8) governs the release, which is
the half anyone actually watches. With one rate on both sides the stretched
target decayed as fast as `squash` could chase it out of a deep compression, and
the visible overshoot died at 1.05 no matter how far `C.ROLL_STRETCH` was
pushed.

**`ROLL_SQUAT` and `ROLL_STRETCH` are filter inputs, not poses.** Nothing draws
`squat_bias`: `base.py` folds it into `squash` through
`approach(..., 9/sqrt(weight))`, and over a 0.15 s event that filter passes
roughly a third of what you ask for. `0.35` in the config draws as ~`0.62`. That
is why the constants look extreme, and why `tools/check_roll.py` asserts on
`p.squash` — the thing on screen — rather than on the value that was set.

**Legs.** `leg_pull` gathers the rest targets, but a foot is *planted* and only
steps once dragged `step_len` away, which never completes inside 0.15 s — the
legs trailed as four straight sticks. `_roll_pose` reels the feet in with the
body and cancels any step in flight. See [Leg](./leg.md).

### What this replaced, and why

The first version was a **fake roll**: shrink `spine.link` toward
`C.ROLL_LINK × spine.link0` so the joints fall into a disc about as wide as the
body is thick, then spin that disc around the head. It was a neat trick —
[Spine](./spine.md)`.resolve` reads `link` fresh every frame, so a pose can
squeeze the whole chain without a rebuild, exactly as the `orbital` body plan
does permanently. (A *real* coil is impossible either way: ~10 joints at the
spine's `bend=26` limit is ~260° of total curvature, so the ball stays an arc.)

It failed as a read. The lizard curled into a blob and you could no longer tell
which way you had gone — which is the one thing a dodge has to show. The trick
is documented here because it works and may be worth reusing elsewhere; it just
is not what this verb needed.

## Related

- [Combat](./combat.md) — the manual verbs, and dash damage.
- [Controls](./controls.md) — which button, per player.
- [Spine](./spine.md) — why shrinking `link` is enough.
- [Damage](./damage.md) — what the i-frames are protecting.
- `tools/check_roll.py` — the cost, the i-frames, the squash/release, the
  easing, and how far a press actually carries you.
