# Verification — an issue is closed when the code says so

Every claim in this repo is cheap to make and expensive to trust. Two agents
have now reported issues "resolved" that were not: a 198-line cosmetic skeleton
whose entry point had zero callers, a ground-adaptation layer whose every
function returned `0.0` unconditionally, `Anticipation` objects created and
updated but never read. All three would pass a reading of the diff. None
changed the game.

So the rule is: **a ticket is done when a runnable check says it is.**

## The checks

Each lives in `tools/`, needs no framework, and prints its own numbers so a
regression is visible rather than merely detected.

| Check | Pins |
|---|---|
| `check_issues.py` | Walks every open issue and asserts a concrete marker for it. The index. |
| `check_bosses.py` | Every `BOSS_POOL` entry, driven through all its phases and drawn. |
| `check_sandbox_boss_bar.py` | A hand-spawned boss is mirrored onto `rounds.boss`, so its health bar paints real pixels and tracks HP; without the mirror both bars draw nothing, which is the control. Cleanup clears it, and the real wave path leaves the same observable. |
| `check_boss_resist.py` | A stack of every slow source never puts a boss under the floor, in any order, and its duration is the cut one; the same stack on a common enemy still matches the pre-cap formula value for value; a maximally slowed boss still covers 70% of its ground through the real `steer`; a hit no longer touches a boss's velocity or trips the `'hurt'` pose. `--shot` writes the before/after body comparison. |
| `check_camera.py` | The cached `w2s` transform equals the naive one after every mutation path. |
| `check_tongue.py` | The drawn tongue tip IS the kinematic tip, at every phase. |
| `check_tail_chain.py` | The tail ring-out travels base → tip; one write to `tail_spring` scales the whole chain. |
| `check_oscillators.py` | Each `PhaseOscillator` reproduces the inline sine it replaced, exactly. |
| `check_windup.py` | The action gates fire once per press and never repeat while held. |
| `check_roll.py` | The Rolamento costs, gives i-frames, deals no damage, and collapses into a disc — eased, and it gives the resting `spine.link` back. |
| `check_projectile.py` | The three hooks fire and are the ONLY path; a bullet's body reads its side and never its species; the sprite cache stays capped; ~100 bullets are timed against the frame. |
| `check_content.py` | Every shooter fires `genome.shot['fn']` and builds no bullet of its own; a dial edit alone changes the arrangement; the ANTECIPADOR leads and its ground mark shows the same point it shoots; the MORTEIRO's footprint is on the ground before any puddle exists; puddle life stays under the cooldown that reapplies it; the player's shot modifiers stack and the enemy's do not; a new card is paid for by re-tuning the table's weights. |
| `check_muralha.py` | A Muralha's grid of fire lands on the arena it is fought in, not on the world origin: every puddle inside `arena_bounds`, all four quadrants lit, no cell eaten by the 40-puddle cap, and the fire's life under the interval that reapplies it. |
| `check_turret.py` | The planted Torreta does not move (not while firing, shoved or beaten), fires through the emitter with `might` on the bullet, answers to `amount`/`area_mult`/`cooldown_mult`, dies to an enemy and leaves `game.friends`, and takes that enemy's aggro off the player. |
| `check_music.py` | The stem mix, against a REAL mixer (the dummy audio driver no-ops every call). |
| `check_difficulty.py` | Early waves unchanged, late waves actually ramp. |
| `check_shop_prices.py` | A shop price raised in one camp is still raised in the next; tier 0 opens at the shipped prices while tiers 1 and 2 charge 1.7× and 2.4×; recompra compounds 1.45 on a permanent upgrade and 1.25 on a consumable; the count dies with the run and the `polen` route bonus rides the same tier multiplier. |
| `check_sandbox_store.py` | All three sandbox store paths (manual pick, random N, launch preset) stage a catalog of the native offers plus the wrapped ones. |
| `check_doc_paths.py` | No doc cites a source path that does not exist. |

Plus `python lizard_game.py --smoke 400`, which is the floor, not the ceiling:
it runs one player through 400 frames with no boss and few creatures, so it
catches import errors and hard crashes on the common path and nothing else.
Four of the five A Muralha crashes were invisible to it.

## Writing a new one

- **Assert the behaviour, not the implementation.** "The drawn tip equals the
  kinematic tip" survives a rewrite; "`tongue_tip_pos` exists" does not.
- **Normalise before comparing.** Raw tail lag is not comparable across links
  because each tracks a joint with a different travel; per-link peak is.
- **Prove the check has teeth.** Break the thing on purpose and confirm the
  check fails. `check_music.py` is honest partly because doing this showed the
  channel-theft bug it was written for did not exist.
- **A no-op is a failure.** If the feature can be deleted and the check still
  passes, the check is testing nothing.

## Related

- [Issue tracker](./issue-tracker.md) — where tickets live.
- [Triage labels](./triage-labels.md) — the five canonical labels.
- [Running](../concepts/running.md) — how to launch the game and the smoke test.
