"""Per-boss arena modifiers (issue #26, narrowed by #158).

Issue #158 removed the play-box from every boss except A Muralha. The
original 10 entries (Rei Lagarto through ANKH) all had a ``size``
shrunk below the 3200x3200 world, which capped the player's run -- the
box followed the boss, so the fight became a moving maze the player
could not read. Only A Muralha still holds a box: ``plan='fixed'``
keeps the boss planted, the corridor is the fight, and ``grid_of_fire``
anchors the cells to the arena (emitter.py:500).

The screen ``tint`` is per-boss identity (Rei Lagarto warm gold,
Kraken-Mor deep blue, etc.) and survived -- a tint applies via
``BossArena.apply`` even when ``size`` is None, so the 10 bosses that
used to have a box still carry their atmosphere and just fight in the
open world. The tint lives in ``BOSS_TINTS``; ``for_boss`` wraps it
in a ``BossArena`` so the rest of the system stays untouched.

Two modifiers, both optional:

- ``size``: a (width, height) play box CENTERED ON THE BOSS for the
  duration of the fight. Applied via ``Game.arena_bounds``, which
  ``Lizard.integrate`` clamps against. Only A Muralha sets it.
- ``tint``: a (color, alpha) screen tint applied each frame during the
  boss fight. Applied via ``Game.draw``.

Related: [Boss](../../docs/concepts/boss.md), [Round](../../docs/concepts/round.md).
"""

from ...core import config as C


def clamp_to_anchor(pos, direction, speed, max_r, bounds):
    """Re-point ``direction`` toward the arena centre if the next step
    would leave the box. Returns ``(direction, speed)`` ready to feed
    ``Lizard.steer`` / ``integrate``.

    The check is a one-frame lookahead so the clamp anticipates the
    want rather than correcting after the fact. ``Lizard.integrate``
    also clamps the position, so this is a guard against the boss
    queuing a ghost move that points out of the arena; the body itself
    never leaves the box.

    Returns ``(direction, speed)`` unchanged when:

    - there is no arena (``bounds`` is None);
    - the boss cannot move (``max_r`` only matters for the wall, but
      a creature with ``max_speed == 0`` will not steer in the first
      place -- still passed through);
    - the next step stays inside the box.

    ``pos`` is the boss's current world position. ``direction`` is the
    unit vector the move function returned. ``speed`` is the multiplier
    the move function returned (0..1 of ``max_speed``).
    """
    if not bounds or speed <= 0:
        return direction, speed
    lookahead = direction * speed * max_r * 0.1
    if lookahead.length_squared() < 1e-6:
        return direction, speed
    next_pos = (pos[0] + lookahead.x, pos[1] + lookahead.y)
    lo_x, lo_y, hi_x, hi_y = bounds
    if (next_pos[0] < lo_x + max_r or next_pos[0] > hi_x - max_r or
            next_pos[1] < lo_y + max_r or next_pos[1] > hi_y - max_r):
        cx = (lo_x + hi_x) * 0.5
        cy = (lo_y + hi_y) * 0.5
        from pygame import Vector2
        from ...core.mathutil import safe_norm
        inward = Vector2(cx - pos[0], cy - pos[1])
        if inward.length_squared() > 1e-6:
            return safe_norm(inward), speed
    return direction, speed


class BossArena:
    """Per-boss play-area modifiers. All fields optional; unset = no change.

    A boss with no arena modifiers (the default for any boss with no
    entry in ``ARENAS`` or ``BOSS_TINTS``) fights in the standard world.
    A boss WITH modifiers gets a tighter, more authored fight -- the
    shared infrastructure applies whatever the descriptor specifies,
    so each boss only fills in the modifiers it needs. As of #158 only
    A Muralha sets a ``size``; the 9 other bosses with a tint set only
    that, and Terror Alado sets nothing.

    Issue #121: a fight can also change its modifiers MID-fight via
    ``phase_sizes`` -- a sequence of (w, h) entries parallel to the boss's
    ``phases`` list. A Muralha uses this to NARROW its corridor each phase
    (900x640 -> 800x540 -> 700x440), so the player's space shrinks
    while the boss itself stays planted. ``apply`` resolves which entry
    wins for the call (default = phase 0, the spawn size).
    """

    __slots__ = ('size', 'tint', 'phase_sizes')

    def __init__(self, size=None, tint=None, phase_sizes=None):
        # (width, height) of the play box, CENTERED ON THE BOSS. None = the
        # full world. Centering is the whole point: a box anchored to the
        # world's origin instead just shaves the far corners off a 3200x3200
        # map, which the player never touches -- the fight has to be tight
        # around the boss for the arena to be felt at all.
        self.size = size
        # (color, alpha) screen tint applied each frame; None = no tint.
        # Color is an (r, g, b) tuple; alpha is 0..255.
        self.tint = tint
        # Per-phase sizes (issue #121). Parallel to the boss's
        # ``BOSS_POOL[bid]`` ``phases`` list. Entry [i] wins during phase i;
        # None entries fall back to ``size`` so a single shrink can leave
        # some phases untouched. ``apply`` defaults to phase 0 and is
        # called again at every phase transition by the per-boss
        # ``on_phase`` callback.
        self.phase_sizes = phase_sizes

    def apply(self, game, boss_pos, phase_i=0):
        """Apply this arena's modifiers to the game state.

        Called by ``RoundManager._spawn_boss`` after the boss is placed
        (``phase_i=0``), and by the per-boss ``on_phase`` callback at every
        HP threshold with the new phase index. Stores the active arena on
        the game so ``Lizard.integrate`` and ``Game.draw`` can read it.

        A shrink mid-fight does NOT teleport the player out of bounds:
        ``Lizard.integrate`` already clamps against ``game.arena_bounds``
        on the next step, so a player standing at the old edge gets pushed
        inward by the integration frame. The shrink itself is the cue the
        player feels as "the corridor closes".
        """
        game.arena = self
        # Resolve the active size for this phase (issue #121):
        # phase_sizes[phase_i] wins; a None entry falls back to size.
        resolved = self.size
        if self.phase_sizes is not None:
            if phase_i < len(self.phase_sizes):
                ps = self.phase_sizes[phase_i]
                if ps:
                    resolved = ps
        if not resolved:
            return
        w, h = resolved
        # Centre the box on the boss, then push it back inside the world so a
        # boss spawned near an edge still gets its full arena instead of a
        # clipped sliver. Stored as (min_x, min_y, max_x, max_y).
        w = min(w, C.WORLD_W)
        h = min(h, C.WORLD_H)
        cx = min(max(boss_pos[0], w / 2), C.WORLD_W - w / 2)
        cy = min(max(boss_pos[1], h / 2), C.WORLD_H - h / 2)
        game.arena_bounds = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

    def clear(self, game):
        """Restore the default world state when the boss fight ends.

        Called by ``RoundManager.update`` when the boss dies / the round
        clears.
        """
        game.arena = None
        game.arena_bounds = None


# --------------------------------------------------------------------------- #
#  Per-boss arena descriptors                                                 #
# --------------------------------------------------------------------------- #
# A Muralha (issues #74 / #121): orange-red tint (the gate is hot) and the
# tightest box in the game -- a wide, short corridor. The wall occupies
# one side and there is nowhere to run to, which is the whole fight.
# Phase sizes (issue #121): the corridor NARROWS each threshold. Phase 1
# fights in the 900x640 corridor; phase 2 shrinks to 800x540 (the player
# has less room to flank the hand_slam); phase 3 to 700x440 (the wall is
# closing in). The boss doesn't move (plan='fixed'), so the anchor rule
# from #118 is trivially satisfied -- the box just gets smaller around
# the same point.
A_MURALHA_ARENA = BossArena(
    size=(900, 640),
    tint=((220, 80, 40), 32),
    phase_sizes=((900, 640), (800, 540), (700, 440)),
)


# Per-boss screen tints (issue #158). The arena box was a per-boss-labour
# that made the fight a moving maze; what's left is the visual identity
# the player reads as "a Kraken fight" vs "a Rei Lagarto fight". The
# tint applies via ``BossArena.apply`` even when ``size`` is None, so
# the 10 bosses below keep their atmosphere while fighting in the open
# world. Terror Alado has no tint -- the flyer hunts across the whole
# world with no colour signature.
BOSS_TINTS = {
    'rei_lagarto':      ((220, 170, 90), 24),
    'centopeiadeira':   ((140, 70, 50), 20),
    'kraken_mor':       ((40, 70, 130), 32),
    'primordial':       ((180, 80, 200), 28),
    'mae_escaravelho':  ((220, 160, 40), 24),
    'aranha_rei':       ((220, 220, 230), 20),
    'serpente_cristal': ((140, 220, 230), 24),
    'terror_alado':     None,
    'olho_sismico':     ((90, 200, 230), 28),
    'ankh':             ((230, 200, 80), 32),
}

# Pre-wrap the tints in BossArena instances so ``for_boss`` returns the
# same shape it always did (a BossArena, never a raw tuple). Constructed
# once at import; ``apply`` is idempotent and the descriptors are tiny.
_TINT_ARENAS = {bid: BossArena(tint=t) for bid, t in BOSS_TINTS.items() if t is not None}


# Registry: boss id -> BossArena. As of issue #158, only A Muralha
# carries a play box. The 10 tint-only bosses resolve via
# ``for_boss`` falling through to ``_TINT_ARENAS``; bosses without a
# tint entry (Terror Alado) fight with no arena descriptor at all.
ARENAS = {
    'muralha': A_MURALHA_ARENA,
}


def for_boss(boss_id):
    """Return the BossArena for ``boss_id``, or None if it has none.

    A Muralha returns its box-sized arena. The 10 bosses with an
    identity tint get a size-less BossArena that still applies the
    tint via ``apply()`` (the tint is the visual signature that
    survived #158). Terror Alado and any future untinted boss
    resolve to None.
    """
    return ARENAS.get(boss_id) or _TINT_ARENAS.get(boss_id)
