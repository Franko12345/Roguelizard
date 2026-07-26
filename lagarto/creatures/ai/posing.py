"""Procedural posing per AI state (#11).

A hunting lizard and a fleeing one used to look identical -- they moved but
never changed posture. This is the Rain World-style body-language layer: read
the creature's AI state and ease its steady-state posture toward a target so
intent is legible *before* an attack lands (an alert creature tenses and holds
its tail high; a hunting one crouches; a hurt one slumps and drags its tail).

It reuses the same idiom as ``AILizard._apply_mood_pose``: bias the knobs the
body already animates from -- ``squat_bias`` (the squash/crouch target) and the
tail spring's stiffness (tight = held, loose = dragging) -- nothing new to draw.

Two rules make it safe to call every frame:

* **Spring-smoothed.** Targets are eased with ``approach`` so switching states
  never snaps; the squash itself is further smoothed inside ``integrate``.
* **Applied before the behaviour tick.** A transient wind-up telegraph
  (lunge crouch, hop gather, spit coil) writes ``squat_bias`` *after* this and
  wins for its window -- posing only sets the resting posture underneath.

Boss body-telegraph (#13) can call ``apply_state_pose`` with its own state name;
that is the whole reusable entry point.
"""

from ...core.mathutil import approach
from ..base import TAIL_SPRING_STIFFNESS

# state -> (squat_bias target, tail-stiffness multiplier).
#   squat_bias < 1 crouches/compresses, > 1 stretches tall.
#   stiffness  < 1 lets the tail lag and drag, > 1 snaps it tight and held.
POSE_STATES = {
    'idle':   (1.00, 0.70),   # grazing: relaxed body, tail sways loosely
    'alert':  (1.10, 1.70),   # aware: stands tall, tail raised and rigid
    'hunt':   (0.88, 1.30),   # closing in: crouched and focused
    'attack': (1.25, 2.00),   # committed: lunging stretch, tail whip-tight
    'hurt':   (0.82, 0.40),   # struck: slumps and drags a loose tail
    'flee':   (1.15, 0.90),   # running: stretched out, tail streaming behind
}


def apply_state_pose(creature, state, dt):
    """Ease ``creature`` toward the posture for ``state`` (see ``POSE_STATES``).

    Call once per frame *before* the behaviour tick. Reads AI state only -- no
    game-logic touched. Guards a creature that lacks a tail spring (centipede /
    kraken) by skipping that channel instead of crashing.
    """
    squat_t, stiff_t = POSE_STATES.get(state, POSE_STATES['idle'])
    creature._pose_squat = approach(getattr(creature, '_pose_squat', 1.0), squat_t, 6, dt)
    creature._pose_stiff = approach(getattr(creature, '_pose_stiff', 1.0), stiff_t, 6, dt)
    creature.squat_bias = creature._pose_squat
    if getattr(creature, 'tail_spring', None) is not None:
        creature.tail_spring.stiffness = TAIL_SPRING_STIFFNESS * creature._pose_stiff


def _demo():
    """Smoothing converges toward the state target, and a tailless creature
    (tail_spring is None) poses without crashing."""
    class _Fake:
        squat_bias = 1.0
        tail_spring = None
    c = _Fake()
    for _ in range(400):                       # ~6.6s at 60fps
        apply_state_pose(c, 'hunt', 1 / 60)
    assert abs(c._pose_squat - POSE_STATES['hunt'][0]) < 1e-3, c._pose_squat
    assert abs(c.squat_bias - POSE_STATES['hunt'][0]) < 1e-3
    print('posing demo ok')


if __name__ == '__main__':
    _demo()
