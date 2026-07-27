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
| `check_camera.py` | The cached `w2s` transform equals the naive one after every mutation path. |
| `check_tongue.py` | The drawn tongue tip IS the kinematic tip, at every phase. |
| `check_tail_chain.py` | The tail ring-out travels base → tip; one write to `tail_spring` scales the whole chain. |
| `check_oscillators.py` | Each `PhaseOscillator` reproduces the inline sine it replaced, exactly. |
| `check_windup.py` | The action gates fire once per press and never repeat while held. |
| `check_roll.py` | The Rolamento costs, gives i-frames, deals no damage, and collapses into a disc — eased, and it gives the resting `spine.link` back. |
| `check_projectile.py` | The three hooks fire and are the ONLY path; a bullet's body reads its side and never its species; the sprite cache stays capped; ~100 bullets are timed against the frame. |
| `check_content.py` | Every shooter fires `genome.shot['fn']` and builds no bullet of its own; a dial edit alone changes the arrangement; the ANTECIPADOR leads and its ground mark shows the same point it shoots; the MORTEIRO's footprint is on the ground before any puddle exists; puddle life stays under the cooldown that reapplies it; the player's shot modifiers stack and the enemy's do not; a new card is paid for by re-tuning the table's weights. |
| `check_turret.py` | The planted Torreta does not move (not while firing, shoved or beaten), fires through the emitter with `might` on the bullet, answers to `amount`/`area_mult`/`cooldown_mult`, dies to an enemy and leaves `game.friends`, and takes that enemy's aggro off the player. |
| `check_music.py` | The stem mix, against a REAL mixer (the dummy audio driver no-ops every call). |
| `check_difficulty.py` | Early waves unchanged, late waves actually ramp. |
| `check_shop_prices.py` | A shop price raised in one camp is still raised in the next. |
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
