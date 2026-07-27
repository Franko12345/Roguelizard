# Dodge — two verbs, one i-frame rule

The player has **two** dodges, and they are deliberately different verbs
rather than one tuned one:

| | **Investida** (`dash_*`) | **Rolamento** (`roll_*`) |
|---|---|---|
| Damage | `C.DASH_DAMAGE`, scaled by Might | **none** |
| Energy | `C.DASH_COST` (14, 18 net; 14 with Membranas) | `C.ROLL_COST` (5) |
| Cooldown | `Player.dash_cooldown` (0.45 s) | `C.ROLL_CD` (0.2 s, from the end of the roll) |
| i-frames | `0.16 s` (0.2 with Membranas) | `C.ROLL_TIME` (0.15 s) |
| Movement | velocity impulse, `3.0×` max speed (`3.5` with Membranas) | velocity impulse, `C.ROLL_SPEED` (`2.6×`) |
| Ground covered | **+223 px** over walking, per press | **+133 px** — 26.6 px per energy point against the investida's 12.4 |

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

## The fake roll

The rolamento does not curl the body — it **collapses** it. `Player._roll_pose`
shrinks `spine.link` toward `C.ROLL_LINK` of `spine.link0`, so the joints fall
into a disc about as wide as the body is thick, and then spins that disc by
rotating every joint around the head.

- **No rebuild.** [Spine](./spine.md)`.resolve` reads `link` fresh every frame,
  so a pose can squeeze the whole chain per-frame. `spine.link0` is the resting
  value to scale off (a cached copy would go stale when `rebuild_body` grows the
  LARVA mid-roll). The `orbital` body plan does the same trick permanently.
- **Not a real coil, because one cannot close.** ~10 joints at the spine's
  `bend=26` limit is ~260° of total curvature — the ball would stay an arc.
- **Legs.** `leg_pull` gathers the rest targets, but a foot is *planted* and only
  steps once dragged `step_len` away, which never completes inside 0.15 s — the
  legs stayed behind as four straight sticks. `_roll_pose` reels the feet in with
  the body and cancels any step in flight. See [Leg](./leg.md).
- **Eased, never snapped**, in *and* out — same contract as `squat_bias`
  (`C.ROLL_EASE`). An instant collapse teleports the body.
- **Do not over-tighten** `C.ROLL_LINK`: below ~0.15 the body's quad strip and
  outline ring cross themselves and shed visible slivers for a couple of frames.

## Related

- [Combat](./combat.md) — the manual verbs, and dash damage.
- [Controls](./controls.md) — which button, per player.
- [Spine](./spine.md) — why shrinking `link` is enough.
- [Damage](./damage.md) — what the i-frames are protecting.
- `tools/check_roll.py` — the cost, the i-frames, the disc, and the easing.
