# Cadence by overlap, not by cutting the tell

The boss FSM used to leave the boss standing still for ~1.3s of
every ~2.1s cycle: the cd pause (0.55-1.1s) plus the recover (0.5s)
with no movement. The playtest feedback was "easy to dodge" --
one pattern at a time, with breath between attacks. Fixing it by
cutting the tell would violate the 27-frame rule; the answer is
to fire more in parallel.

The cadence now comes from **overlap**, not from cutting the
tell. The windup floor (``BOSS_WINDUP_FLOOR = 0.45s``) is sacred.
The default ``BOSS_CD_MIN`` / ``BOSS_CD_MAX`` collapsed to near
zero and ``BOSS_CD_FLOOR`` (0.15s) is the global safety net. The
per-boss ``cd_mul`` -- already in every phase kit -- carries the
rhythm signature. The cycle drops from ~2.1s to ~1.0s in calm and
approaches 0.75s in enraged.

The "Movement Trail" is the new abstraction: a ``(direction, speed)``
returned every frame, with the precedence attack > phase > none.
The attack's ``move`` field beats the phase's ``moves`` slot beats
the default ``reposition``. Charge / burrow / grapple veto the
trail (their own state machines own the motion), the same way
they already did.

Two design choices inside:

1. **Re-aim live for fan / line.** The other telegraphs (radial,
   shockwave, spiral, horn) read the boss's own joints live and
   stay honest to the boss's position. Fan and line froze their
   aim at windup start, which made a walking boss draw a cone
   that rotated while the shot left from the new position. The
   clock updates ``_windup_target`` every frame the boss is in
   windup, so the cone follows the player. A moving boss that
   aims where you are is more legible than a ghost cone hanging
   in the air.

2. **The windup floor is enforced statically and at use.** The
   static check (``tools/check_boss_movement.py``) walks every
   ``(pid, mood)`` pair and asserts the pre-multiplier windup
   honours the floor. The runtime clamp (``BossAI._eff_windup``
   applies ``max(0.45, raw)``) is the safety net for any future
   pattern that violates the floor. The clamp is the rule; the
   check is the static guard.

## Trade-offs

The floor means a "fast" pincer (BOSS_PINCHA_WINDUP = 0.3s) can
no longer be 0.3s -- the cycle is 0.45s minimum. The pincha is
still a pincer; the player just reads the body posture, not
the snap. The pattern is dirtier at the design level but the
fight is the legible one.

The cycle is 1.0s in calm (not the issue's "~0.8s" target). The
floor on cd + recover (0.15s each) plus an untouched windup of
0.7s gives 1.0s. The aspirational target would require either a
lower floor or a smaller windup -- both of which violate the
invariant the rule is meant to protect. The check pins the
regression bar at 2.5s (the slowest case, the kraken's grapple),
which is the real improvement on the 2.1s baseline.
