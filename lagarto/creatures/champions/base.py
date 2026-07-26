"""The champion template, the registry, and the promotion roll.

Splitting: the ``apply``/``tick`` bodies live in :mod:`variants` and
:mod:`modifiers`; this module imports both to assemble ``CHAMPIONS`` and keeps
``maybe_promote`` next to the pools it draws from. See the package docstring
for what the two layers *are*.
"""

import random

from ...core import config as C
from ...core import palette
from .variants import (_alfa, _alfa_tick, _apice, _espectro, _espectro_tick,
                       _filhote, _saltador, _saltador_tick)
from .modifiers import _blindado, _divisor, _explosivo, _gigante


class Champion:
    """One elite template. ``apply`` runs at spawn, ``tick`` every frame (optional)."""

    def __init__(self, cid, name, hue, apply, tick=None, hp_mult=1.0,
                 kind='variant'):
        self.id = cid
        self.name = name
        self.hue = hue
        self.apply = apply
        self.tick = tick
        self.hp_mult = hp_mult
        self.kind = kind            # 'variant' | 'modifier'

    def color(self):
        return palette.vibrant(self.hue, 0.85, 1.0)


CHAMPIONS = [
    Champion('filhote',  'FILHOTE',   205, _filhote,   hp_mult=1.0),
    Champion('alfa',     'ALFA',      48,  _alfa,      _alfa_tick,      hp_mult=1.5),
    Champion('espectro', 'ESPECTRO',  190, _espectro,  _espectro_tick,  hp_mult=1.2),
    Champion('saltador', 'SALTADOR',  178, _saltador,  _saltador_tick,  hp_mult=1.2),
    Champion('apice',    'APICE',     2,   _apice,     hp_mult=1.9),
    Champion('blindado', 'BLINDADO',  32,  _blindado,  hp_mult=1.3, kind='modifier'),
    Champion('gigante',  'GIGANTE',   290, _gigante,   hp_mult=1.8, kind='modifier'),
    Champion('explosivo', 'EXPLOSIVO', 18, _explosivo, hp_mult=1.1, kind='modifier'),
    Champion('divisor',  'DIVISOR',   135, _divisor,   hp_mult=1.2, kind='modifier'),
]
BY_ID = {ch.id: ch for ch in CHAMPIONS}
VARIANTS = [ch for ch in CHAMPIONS if ch.kind == 'variant']
MODIFIERS = [ch for ch in CHAMPIONS if ch.kind == 'modifier']


def chance(wave):
    """Champion odds ramp with the wave (Isaac: ~5% early, ~20% late)."""
    return min(C.CHAMP_CHANCE_MAX,
               C.CHAMP_CHANCE_BASE + C.CHAMP_CHANCE_PER_WAVE * max(0, wave - 1))


def maybe_promote(creature, game, wave, rng=random):
    """Roll a champion onto a freshly spawned enemy. Returns the Champion or None.

    A variant may additionally pick up one modifier, which is where the
    combinatorial variety comes from: APICE BLINDADO reads as a different fight
    from APICE, without a line of new behaviour code.
    """
    if getattr(creature, 'is_boss', False) or creature.kind != 'enemy':
        return None
    if rng.random() > chance(wave):
        return None
    promote_to(creature, rng.choice(VARIANTS).id, game)
    if rng.random() < C.CHAMP_MODIFIER_CHANCE:
        _promote(creature, game, rng.choice(MODIFIERS), extra=True)
    return creature.champion


def promote_to(creature, champ_id, game):
    """Apply a specific ``BY_ID`` Champion to ``creature`` and return it.

    The deterministic counterpart to ``maybe_promote`` (which rolls one at
    random): the sandbox and any test spawn name the champion outright. Both
    funnel through ``_promote``, so tint + scale + glow + hp multiplier + ticks
    are applied identically -- there is no second, lighter promotion path.
    """
    _promote(creature, game, BY_ID[champ_id])
    return creature.champion


def _promote(creature, game, ch, extra=False):
    if not (extra and creature.champion is not None):
        creature.champion = ch
        creature.champion_name = ch.name
        creature.champion_ticks = []
    ch.apply(creature, game)                  # may rebuild the body (see _KEEP)
    if extra and creature.champion is not ch:
        creature.champion_name = f"{creature.champion_name} {ch.name}"
    creature.hp = max(1, int(round(creature.hp * ch.hp_mult)))
    creature.max_hp = creature.hp
    if ch.tick:
        creature.champion_ticks.append(ch.tick)
    creature.base_color = creature.color
