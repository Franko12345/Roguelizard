"""Boss telegraph drawing — one function per kind (issue #27).

The BossAI's ``draw`` method used to inline seven ``if kind == ...``
branches (radial / fan / line / horn / shockwave / spiral / rain), each
with its own pygame primitives. Adding a new telegraph kind meant
editing a 65-line method; the branches had no shared structure.

This module exposes one function per kind, plus a ``TELEGRAPHS`` registry
keyed by the same string the ``PATTERNS[pattern_id]['telegraph']`` field
uses. ``BossAI.draw`` becomes a thin dispatcher:

.. code-block:: python

    kind = PATTERNS[self.pattern_id]['telegraph']
    fn = TELEGRAPHS.get(kind)
    if fn is not None:
        fn(surf, cam, b, self, prog, col, blink)

Each function takes the same 7-arg signature so the dispatcher has no
special cases. The ``ai`` arg is the BossAI instance (so telegraphs can
read ``ai._windup_target`` etc.); the ``blink`` arg is the pulsing
factor the caller already computes from ``prog``.

Related: [Enemy behaviors](../../docs/concepts/enemy-behaviors.md) -- the
>= 27 frames rule for telegraphs.
"""

import math

import pygame

from ...core import config as C
from ...core import palette
from ...core.mathutil import safe_norm, vfrom_angle
from pygame import Vector2


def telegraph_radial(surf, cam, b, ai, prog, col, blink):
    """A growing circle around the boss -- 'get away from me' tell."""
    r = int(C.BOSS_RADIAL_SPEED * 0.9 * cam.zoom)
    pygame.draw.circle(surf, col, cam.w2s(b.spine.joints[0]), r,
                       max(1, int((1 + 2 * prog) * cam.zoom)))
    palette.glow(surf, cam.w2s(b.spine.joints[0]), r, col,
                 (0.12 + 0.2 * prog) * (0.5 + 0.5 * blink))


def telegraph_fan(surf, cam, b, ai, prog, col, blink):
    """Two lines fanning out from the mouth -- 'dodge sideways' tell.

    Issue #118: the aim is read LIVE from ``ai._windup_target``. The
    BossAI.zs tick updates that point every frame the boss is in windup,
    so a walking boss aims where the player is *now*, not where it was
    when the windup started. The fan rotates with the mouth as the
    body moves; the shot comes from the new position and the cone
    reflects that -- no ghost cone hanging in the air.
    """
    mouth = b.spine.joints[0]
    sp = cam.w2s(mouth)
    spread = C.BOSS_FAN_SPREAD
    base = safe_norm(getattr(ai, '_windup_target', mouth + Vector2(100, 0)) - mouth)
    for s in (-0.5, 0.5):
        edge = base.rotate(s * spread)
        far = mouth + edge * 340
        pygame.draw.line(surf, col, sp, cam.w2s(far),
                         max(1, int((1 + 2 * prog) * cam.zoom)))


def telegraph_line(surf, cam, b, ai, prog, col, blink):
    """A single line from mouth to target -- 'this is where I'm biting' tell.

    Same as telegraph_fan: the aim is read live from ``ai._windup_target``
    every frame, so a moving boss doesn't draw a stale line. Used by
    barrage, pincha, eye_laser, charging and other line telegraphs.
    """
    mouth = b.spine.joints[0]
    sp = cam.w2s(mouth)
    aim = getattr(ai, '_windup_target', mouth + Vector2(100, 0))
    pygame.draw.line(surf, col, sp, cam.w2s(aim),
                     max(1, int((1 + 3 * prog) * cam.zoom)))
    palette.glow(surf, cam.w2s(aim), int(14 * cam.zoom), col,
                 0.2 + 0.3 * prog)


def telegraph_horn(surf, cam, b, ai, prog, col, blink):
    """A pulsing yellow glow around the boss -- 'reinforcements incoming' tell.

    Yellow on purpose: summon is a different *category* of threat (adds,
    not a hit) and the colour shift is the only cue that you should
    reposition for a different reason than dodging a projectile.
    """
    sp = cam.w2s(b.spine.joints[0])
    r = int(b.max_r * (1.3 + 0.6 * prog) * cam.zoom)
    palette.glow(surf, sp, r, (255, 226, 90),
                 (0.2 + 0.3 * prog) * (0.5 + 0.5 * blink))
    pygame.draw.circle(surf, (255, 226, 90), sp, r, max(1, int(2 * cam.zoom)))


def telegraph_shockwave(surf, cam, b, ai, prog, col, blink):
    """A growing ring centred on the boss -- 'you have time to leave' tell."""
    sp = cam.w2s(b.spine.joints[0])
    r = int(C.BOSS_SHOCKWAVE_RADIUS * cam.zoom * (0.3 + 0.7 * prog))
    pygame.draw.circle(surf, col, sp, r,
                       max(1, int((1 + 2 * prog) * cam.zoom)))
    palette.glow(surf, sp, r, col,
                 (0.14 + 0.22 * prog) * (0.5 + 0.5 * blink))


def telegraph_spiral(surf, cam, b, ai, prog, col, blink):
    """Rotating spokes around the boss -- 'spray incoming, find a gap' tell.

    The spokes rotate as prog rises so the player can see where the
    spray will start and pick the gap they'll sit in.
    """
    mouth = b.spine.joints[0]
    sp = cam.w2s(mouth)
    n_spokes = 8
    rr = int(b.max_r * (1.5 + prog * 2) * cam.zoom)
    for i in range(n_spokes):
        ang = (360 / n_spokes) * i + prog * 300
        end = mouth + vfrom_angle(ang, rr / max(cam.zoom, 1e-4))
        pygame.draw.line(surf, col, sp, cam.w2s(end),
                         max(1, int(2 * cam.zoom)))


def telegraph_rain(surf, cam, b, ai, prog, col, blink):
    """Growing circles at the pre-picked slam points -- 'these spots will
    hurt' tell.

    The points are picked at windup START (see ``_select_arms_rain`` in
    patterns.py) so the telegraph can draw them for the entire windup --
    this is the >= 27 frames rule from enemy-behaviors.md.

    ``b.mark_r`` lets a non-boss borrow this drawer at its own size (the
    ANTECIPADOR's lead point, the MORTEIRO's patch); a boss leaves it 0 and
    gets the arms-rain radius it always had. That ring is drawn at FULL size
    from the first frame -- the growing circle understates the danger zone
    while it grows, and for a common enemy whose whole pitch is "you are
    standing in it" that is the one thing the mark may not do (same rule the
    bomber's fuse footprint follows). The urgency lives in the line and the
    glow, which already scale with ``prog``.
    """
    mark = getattr(b, 'mark_r', 0)
    r = int(mark * cam.zoom) if mark else \
        int(C.BOSS_ARMS_RAIN_RADIUS * cam.zoom * (0.3 + 0.7 * prog))
    for pt in getattr(b, '_rain_points', []):
        psp = cam.w2s(pt)
        pygame.draw.circle(surf, col, psp, r,
                           max(1, int((1 + 2 * prog) * cam.zoom)))
        palette.glow(surf, psp, r, col,
                     (0.12 + 0.2 * prog) * (0.5 + 0.5 * blink))


# Registry: kind string -> drawer function. The kind comes from
# PATTERNS[pattern_id]['telegraph']. None entries (burrow, grapple) are
# handled by the caller -- they have no on-screen telegraph because the
# boss's own body draw already shows the windup (the centipede's dig
# state, the octopus's arms converging).
TELEGRAPHS = {
    'radial':    telegraph_radial,
    'fan':       telegraph_fan,
    'line':      telegraph_line,
    'horn':      telegraph_horn,
    'shockwave': telegraph_shockwave,
    'spiral':    telegraph_spiral,
    'rain':      telegraph_rain,
}
