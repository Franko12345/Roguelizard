# Balance

Two passes of balancing recorded here. The design rules are more
important than the specific numbers.

## 3rd pass — steeper mid/late-game scaling (issue #23)

The 2nd pass raised enemy damage but kept HP/speed/count scaling flat.
With Might/Area/Amount upgrades stacked by wave 10+, enemies died
before reaching the player and the run snowballed. The 3rd pass
**steepens the per-wave dials past wave-specific knees** so the
mid-game stays threatening without re-sponging the early game.

The dials now live in named helpers in `rounds.py`
(`wave_hp_bonus`, `wave_speed_mul`, `wave_budget`, `wave_cap`) —
inline formulas were a maintenance hazard (one of the three call sites
had already drifted). The knees are in `config.py` so they can be
tuned without touching `rounds.py`:

| Dial | Knee | Pre-knee (early game) | Post-knee (mid/late game) |
|------|------|----------------------|---------------------------|
| HP bonus | wave 10 | `wave * 0.7` (unchanged) | `+ (wave-10)^1.4 * 1.2` (super-linear) |
| Speed mul | wave 10 | `1.0 + min(wave * 0.025, 0.60)` | `+ min((wave-10) * 0.015, 0.15)` |
| Budget | wave 10 | `(3 + wave * 1.1) * theme_budget` | `+ (wave-10) * 0.6 * theme_budget` |
| Cap | wave 8 | theme cap (unchanged) | `+ min(4, (wave-8) // 2)` |
| Champion chance | wave 7 (ramp start) | `0.05 + 0.018 * (wave-1)`, cap 0.30 | (same ramp, hits cap at wave 21) |

Wave 20 numbers (enxame theme, before vs after): HP bonus 14 → 44,
speed mul 1.4 → 1.65, budget 32 → 40, cap 7 → 11, champion chance
22% → 30%. Waves 1-9 are within measurement noise of the old curve
by design — the early game is preserved.

Bot measurement + full before/after table in
[triage-issue-23.md](../agents/triage-issue-23.md). The bot is a
yardstick (no dash, per the issue spec); the deterministic curve in
`scripts/compare_scaling.py` is the authoritative before/after
artifact.

The 2nd-pass rule "raise DAMAGE, not HP" still holds for the
**per-enemy** dial (contact damage, projectile damage). The 3rd pass
raises **per-wave** HP because the snowball was about TTK at scale,
not about per-hit friction: a +14 HP enemy at wave 20 dies in one
tongue-flick to a stacked Might build, while a +44 HP enemy survives
long enough to close distance. Per-hit damage is unchanged.

## 2nd pass rule: raise DAMAGE, not HP

Coming out of Isaac / Gungeon / VS research: in an auto-attack game the
only player agency is **positioning**, so difficulty must be a
**consequence of position error**. More HP turns enemies into sponges
and makes the build feel weaker than it is.

- **Contact damage** comes from `lizard.contact_damage(max_r, wave)`, with
  the dials `ENEMY_DMG_BASE` (11), `ENEMY_DMG_SIZE` (0.5) and a
  **step-wise wave ladder** (`ENEMY_DMG_STEP` / `ENEMY_DMG_PER_STEP`).
  A continuous ramp is invisible; a step is felt. Runner 16 → 26 over
  waves 1 to 20; tank 26 → 36. Projectile: `ENEMY_PROJ_DMG` (10).
- **`ENEMY_HP_MULT`: 3.0 → 2.2 (measurement) → 3.5 (playtest).** The
  headless bot measured **weapon** TTK and said 2.2; the user plays with
  **dash + whip**, which are much faster, and enemies felt like paper.
  **Lesson: the bot measures friction, not difficulty** — use it to
  compare before/after, never to pick the final number.
- **Do not touch i-frames** (`hit_flash > 0.45`) — they are what keeps the
  game fair. See [Damage](./damage.md).

### Measurement (driven headless bot, `--smoke` is not this)

Two styles: `kite` (moves only, lets weapons work) and `aggro` (dash
hunter, how the user plays). After the rebalance: aggro went from median
wave 2.5 / 5.5 kills to **3.0 / 8 kills** in the same time-to-death —
kills faster, dies the same.

_A bot that only moves measures a game nobody plays_: at level 1 `cuspe`
does **1 damage every 1.05 s**, so almost all early damage comes from
the **dash**.

### Open, and it is a design decision, not a bug

Playing 100% passively **does not clear wave 1 in 6 minutes**. The
premise "attack is automatic, you only position" does not hold at the
start of the run. Raising base weapon damage would fix it — and make
the game easier, the opposite of what was asked. Needs a user call
before touching it.

## 1st pass — from user playtest

Feedback: _enemies died too easily, friends were disproportionate, too
much healing on the ground_. Numbers touched — **this is the place to
change them**:

- **Enemies ~2× tougher**: genome hp in `species.py` (runner 2 → 4, tank
  6 → 14, snake / spider / spitter 3 → 6, horned / spiky / scorpion
  4 → 8), and per-wave scale faster (`rounds`: `wave//3` →
  `int(wave*0.7)`).
- **Fewer enemies at once**: `THEMES[...]['cap']` down (11 → 7, 7 → 5,
  5 → 4, 8 → 6) and budget smaller (`(4 + wave*1.6)` → `(3 + wave*1.1)`).
- **Less healing**: fruit heals 25 → 12; starting fruits 12 → 5; enemy
  drop 40% → 15%; nest fruit drop 100% → 50%.
- **Friends temporary and weaker**: `config.FRIEND_LIFE` (45 s, blink
  the last 5 s and vanish), hp 3 → 2, attack every 0.6 s → 1.1 s; world
  eggs 6 → 3; shop egg 24 → 40 pollen.

## Where the two #104 shooters landed, measured

A new enemy is a new decision, not a new damage number — so the number is
what gets checked. 4 of each against an invulnerable-HP player, 30 s, headless:

| Species | Player standing still | Player circling at 190 px/s |
|---|---|---|
| ANTECIPADOR ×4 | 11.8 dmg/s | 8.7 dmg/s |
| MORTEIRO ×4 | 8.1 | 5.0 |
| METRALHADOR ×4 | 8.7 | 7.1 |
| ENVENENADOR ×4 | 9.0 | 14.8 |
| CUSPIDOR ×4 | 10.5 | 6.7 |

Both new ones sit inside the band the existing shooters already occupy, so
neither is a stealth difficulty bump.

The ANTECIPADOR number reads backwards until you see what it means: it hurts a
**still** player most, because a lead of zero is a shot dead on your head. Its
counter is not to freeze and not to walk in a straight line — it is to
**change direction** (the circling column is the same 4 enemies losing a third
of their damage) or to spend i-frames. That is the correction the measurement
forced on the design note: "standing still beats a lead shot" is false.

## Tracking — what this file asked for, and where it landed

Issue #28 asked for tracking of the requests raised in this file.
The table below maps each request to the issue/commit that addressed
it (or "OPEN" if still unresolved).

| Request | Source section | Status | Where |
|---------|---------------|--------|-------|
| Steeper HP scaling past wave 10 | (issue #23) | done | [triage-issue-23.md](../agents/triage-issue-23.md) |
| Steeper speed scaling past wave 10 | (issue #23) | done | [triage-issue-23.md](../agents/triage-issue-23.md) |
| Higher enemy count budget past wave 10 | (issue #23) | done | [triage-issue-23.md](../agents/triage-issue-23.md) |
| Higher live-enemy cap past wave 8 | (issue #23) | done | [triage-issue-23.md](../agents/triage-issue-23.md) |
| Faster champion ramp past wave 7 | (issue #23) | done | [triage-issue-23.md](../agents/triage-issue-23.md) |
| Passive-play can't clear wave 1 | "Open" | OPEN | design decision, needs user call |
| Boss HP scaling review | (implicit) | OPEN | boss HP `90 + 200 * tier` unchanged; not asked for in #23 |

When you add a new balance request to this file, add a row to the
tracking table in the same commit.

## Related

- [Damage](./damage.md) — player-side HP flow.
- [Combat](./combat.md) — dash / whip damage scaling.
- [Round](./round.md) — theme caps, wave scale.
- [Species](./species.md) — genome HP baselines.
- [triage-issue-23.md](../agents/triage-issue-23.md) — 3rd-pass scaling
  documentation + bot measurements.
