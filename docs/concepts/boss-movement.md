# Boss Movement

A boss has a **movement trail**: every frame, the FSM returns a
``(direction, speed)`` that drives the body's ``steer``. The trail
sits on the FSM next to the attack patterns: a boss stops doing
nothing during windup and recover, and the patterns' cadence gets
tightened to the 27-frame rule by overlap, not by cutting the tell.

The trail is the answer to the playtest feedback the issue captures
("our bosses are easy to dodge" -- one pattern at a time, with breath
between attacks). Gungeon bosses are frenetic and have a movement
pattern on top of attack patterns. This module is the slot for the
movement pattern.

## The two bindings

The trail has two sources, with precedence **attack > phase > none**:

- **By phase** -- each ``*_phases()`` kit carries a ``moves`` slot
  (``list[str]``). The active movement drives the boss when no
  attack is speaking. Unique per boss. A Muralha declares
  ``moves=[]`` (the wall); Olho-Sismico declares ``['hover']`` (the
  observer); most bosses default to ``['orbit']``.
- **By attack** -- a ``PATTERNS[pid]['move']`` field binds a movement
  to that attack. ``None`` means the phase's slot drives the boss
  during this attack (the common case). Specific binds ('orbit',
  'strafe', 'retreat') come from the per-boss signatures
  (#121-#125).
- **None** -- the fallback is ``move_reposition`` (move toward the
  target). A boss with no declared move keeps reactive.

Charge, burrow and grapple **veto** the trail: their own state
machines own the motion and the FSM's per-state branches return
their direction directly. The trail does not override them.

## Cadence

The dead time between attacks collapsed. The previous cycle
(~2.1s) was dominated by the cd pause (0.55-1.1s) and the recover
(0.5s); now the floor is 0.15s across both, and the per-boss
``cd_mul`` from the phase kit carries the rhythm signature.

- ``BOSS_CD_MIN`` / ``BOSS_CD_MAX`` are 0.0 / 0.05 (near zero).
- ``BOSS_CD_FLOOR`` is 0.15s -- the safety net so a ``cd_mul``
  of 0 (or a tiny one) cannot make the boss illegible.
- ``BOSS_RECOVER_TIME`` is 0.15s (default). Charged moves
  override.
- The per-boss ``cd_mul`` -- already in every phase kit -- is
  the rhythm signature. A Muralha (``cd_mul <= 1.0``) hits the
  floor and fights relentlessly; Olho-Sismico uses 3.0+ to
  stretch the pauses for the observer.

The cycle drops from ~2.1s to ~1.0s in calm; agitated/enraged
shrink the windup further (the mood multiplier is 0.8 / 0.65) and
the cycle approaches 0.75s. The "~0.8s" target in the issue is the
aspiration; the actual achievable floor is the windup + 0.15s of
cd + 0.15s of recover.

## The 27-frame rule

The windup floor is ``BOSS_WINDUP_FLOOR = 0.45s`` (27 frames at
``SIM_HZ=60``). Every real telegraph stays at >= 0.45s, before any
mood multiplier. The clamp lives in ``BossAI._eff_windup``; the
static check lives in ``tools/check_boss_movement.py``.

Burrow and grapple are exempt (their ``telegraph`` is ``None``--the
body IS the tell via the dig/grapple state machines). Every other
pattern in ``PATTERNS`` honors the floor.

The windup progression in the body telegraph (``apply_body_tell``)
and the on-screen telegraph (``draw``) reads the FLOORED duration
so the spring-driven tell matches the FSM's countdown.

## Re-aim live

Fan and line telegraphs read their aim from ``ai._windup_target``
live, not at windup start. ``BossAI.tick`` updates the point every
frame the boss is in windup, so a walking boss aims where the
player IS now, not where it was. The other kinds (radial, shockwave,
spiral, horn) already read the boss's own joints live and are
unaffected.

Decided: re-aim live. A moving boss that aims where you are is
more legible than a ghost cone hanging in the air.

## Arena anchor

``BossArena`` is a box centred on the boss at the start of the
fight. Movement that would step outside the box is re-pointed at
the box's centre by ``clamp_to_anchor`` in
``lagarto/flow/boss/arena.py``. ``Lizard.integrate`` keeps the hard
wall; the clamp is the soft guard against the boss queuing a ghost
move that points out of the arena.

## The five moves

The ``MOVES`` registry in ``lagarto/flow/boss/moves.py`` ships
five functions, each ``(boss, game, target, dials) -> (direction, speed)``:

- ``move_orbit`` -- circle around the target at a fixed radius
  (soft band: 0.7x-1.3x of the orbit radius).
- ``move_strafe`` -- perpendicular motion with a small inward bias.
- ``move_retreat`` -- move directly away.
- ``move_hover`` -- stay in place (the observer).
- ``move_reposition`` -- move toward the target (the default fallback).

Adding a move = one function + one entry in ``MOVES``. No dispatcher
to edit.

## Related

- [Boss](./boss.md) -- the FSM this trail sits inside.
- [ADR-0015](../adr/0015-cadence-by-overlap-not-tell-cut.md) -- why
  the cadence comes from overlap, not from cutting the tell.
- [Enemy behaviors](./enemy-behaviors.md) -- the 27-frame rule
  for telegraphs.
- [Patterns](./patterns.py) and [Arena](./arena.py) -- the
  slots the trail reads.
- [CONTEXT.md](../../CONTEXT.md) -- the canonical terms
  **Movement Pattern** and **Movement Trail**.
