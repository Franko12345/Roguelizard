"""Per-boss arena modifiers (issue #26).

Each boss in ``rounds.BOSS_POOL`` can carry an ``arena`` field: a
``BossArena`` instance describing how the play area changes for that
fight. The infrastructure is shared -- the same descriptor powers
bounds-shrink, screen-tint, and (future) obstacle spawning -- so each
authored boss only fills in the modifiers it needs.

Two modifiers, both optional:

- ``size``: a (width, height) play box CENTERED ON THE BOSS for the
  duration of the fight, so the player can no longer kite forever
  across the 3200x3200 world. Applied via ``Game.arena_bounds``, which
  ``Lizard.integrate`` clamps against.
- ``tint``: a (color, alpha) screen tint applied each frame during the
  boss fight, so each boss has its own atmosphere (Rei Lagarto =
  warm gold, Kraken-Mor = deep blue, etc.). Applied via
  ``Game.draw``.

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

    A boss with no arena modifiers (the default for the 8 existing bosses
    as of issue #26) fights in the standard world. A boss WITH modifiers
    gets a tighter, more authored fight -- the shared infrastructure
    applies whatever the descriptor specifies, so each boss only fills
    in the modifiers it needs.
    """

    __slots__ = ('size', 'tint')

    def __init__(self, size=None, tint=None):
        # (width, height) of the play box, CENTERED ON THE BOSS. None = the
        # full world. Centering is the whole point: a box anchored to the
        # world's origin instead just shaves the far corners off a 3200x3200
        # map, which the player never touches -- the fight has to be tight
        # around the boss for the arena to be felt at all.
        self.size = size
        # (color, alpha) screen tint applied each frame; None = no tint.
        # Color is an (r, g, b) tuple; alpha is 0..255.
        self.tint = tint

    def apply(self, game, boss_pos):
        """Apply this arena's modifiers to the game state.

        Called by ``RoundManager._spawn_boss`` after the boss is placed.
        Stores the active arena on the game so ``Lizard.integrate`` and
        ``Game.draw`` can read it.
        """
        game.arena = self
        if not self.size:
            return
        w, h = self.size
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
# Each boss in BOSS_POOL can carry an `arena` field pointing at one of these.
# Bosses without an entry (None) fight in the standard world -- preserves
# existing behavior for the 8 current bosses while the infrastructure
# lands. Future authored bosses (#73 / #74 / #75) will set their own.

# Rei Lagarto: warm gold tint, mild bounds shrink (the king's arena is the
# desert clearing where he hunts -- tighter than the open world but not a
# cage).
REI_LAGARTO_ARENA = BossArena(
    size=(1500, 1500),
    tint=((220, 170, 90), 24),
)

# Centopeiadeira: rust-red tint, no bounds shrink (the centipede's length
# is the constraint, not the arena).
CENTOPEIADEIRA_ARENA = BossArena(
    tint=((140, 70, 50), 20),
)

# Kraken-Mor: deep blue tint, larger bounds shrink (the abyss is tight).
KRAKEN_MOR_ARENA = BossArena(
    size=(1200, 1200),
    tint=((40, 70, 130), 32),
)

# Primordial: purple tint, no bounds shrink (the final fight is in the
# open -- the player has earned the space).
PRIMORDIAL_ARENA = BossArena(
    tint=((180, 80, 200), 28),
)

# Mae-Escaravelho: amber tint (the hive glows).
MAE_ESCARAVELHO_ARENA = BossArena(
    size=(1800, 1800),
    tint=((220, 160, 40), 24),
)

# Aranha-Rei: pale web-white tint (the spider's parlor).
ARANHA_REI_ARENA = BossArena(
    size=(1500, 1500),
    tint=((220, 220, 230), 20),
)

# Serpente de Cristal: prismatic cyan tint.
SERPENTE_CRISTAL_ARENA = BossArena(
    tint=((140, 220, 230), 24),
)

# Terror Alado: no tint, no bounds shrink (the flyer hunts you across the
# whole world -- caging it would defeat the design).
TERROR_ALADO_ARENA = BossArena(
    tint=None,
)

# Olho-Sismico (issue #73): cyan tint, mild bounds shrink (the observer
# watches from a tight arena -- you can't escape its gaze by running).
OLHO_SISMICO_ARENA = BossArena(
    size=(1300, 1300),
    tint=((90, 200, 230), 28),
)

# A Muralha (issue #74): orange-red tint (the gate is hot) and the tightest
# box in the game -- a wide, short corridor. The wall occupies one side and
# there is nowhere to run to, which is the whole fight.
A_MURALHA_ARENA = BossArena(
    size=(900, 640),
    tint=((220, 80, 40), 32),
)

# ANKH (issue #75): golden tint (the eternal is golden), no bounds shrink
# (ANKH is the run's penultimate fight -- the player has earned the open
# space, and ANKH's 4 phases need room to swap bodies). The tint is the
# only arena modifier; the fight feels different because of the 4-phase
# memory structure, not the geometry.
ANKH_ARENA = BossArena(
    tint=((230, 200, 80), 32),
)


# Registry: boss id -> BossArena. Bosses not in this dict get no arena
# modifiers (preserves existing behavior). Adding a boss to this dict is
# the ONLY change needed to give it an arena.
ARENAS = {
    'rei_lagarto':      REI_LAGARTO_ARENA,
    'centopeiadeira':   CENTOPEIADEIRA_ARENA,
    'kraken_mor':       KRAKEN_MOR_ARENA,
    'primordial':       PRIMORDIAL_ARENA,
    'mae_escaravelho':  MAE_ESCARAVELHO_ARENA,
    'aranha_rei':       ARANHA_REI_ARENA,
    'serpente_cristal': SERPENTE_CRISTAL_ARENA,
    'terror_alado':     TERROR_ALADO_ARENA,
    'olho_sismico':     OLHO_SISMICO_ARENA,
    'muralha':          A_MURALHA_ARENA,
    'ankh':             ANKH_ARENA,
}


def for_boss(boss_id):
    """Return the BossArena for ``boss_id``, or None if it has none."""
    return ARENAS.get(boss_id)
