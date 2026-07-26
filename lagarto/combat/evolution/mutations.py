"""The mutation table: passive level-up cards that tweak stats or the genome.

Each ``Mutation`` is a small data object with an ``apply(player, game)``
callback. Picking one mutates the player (stats or a genome part -- the body
redraws itself). Rolled into a hand by ``cards.roll_cards``.
"""

from ...core import palette
from ...core.registry import Registry


class Mutation:
    def __init__(self, mid, name, desc, hue, apply, weight=1.0):
        self.id = mid
        self.name = name
        self.desc = desc
        self.color = palette.vibrant(hue, 0.8, 1.0)
        self.apply = apply
        self.weight = weight            # plain float -- Registry._default_weight handles it
        self.icon = mid                 # procedural icon id (see icons.py)


def _m(mid, name, desc, hue, fn, weight=1.0):
    return Mutation(mid, name, desc, hue, fn, weight)


# ---- stat mutations ------------------------------------------------------- #
def _health(p, g): p.max_health += 30; p.health += 30
def _speed(p, g): p.speed_mult *= 1.14; p.max_speed *= 1.14
def _dash(p, g): p.dash_cooldown *= 0.8
def _energy(p, g): p.max_energy += 30; p.energy = p.max_energy
def _regen(p, g): p.regen += 2.2  # era 4.0/s -- curava rapido demais
def _xp(p, g): p.xp_mult *= 1.25
def _tongue(p, g): p.tongue_range += 90
def _thorns(p, g): p.thorns += 1
def _venom(p, g): p.venom = True
def _wings(p, g): p.wings = True
# global weapon stats (Vampire-Survivors passives)
def _might(p, g): p.might *= 1.2
def _area(p, g): p.area_mult *= 1.18
def _haste(p, g): p.cooldown_mult *= 0.85
def _amount(p, g): p.amount += 1

# ---- part mutations (reuse Player.grant_part; body redraws itself) -------- #
# NOTE: the club tail is charm-only (issue #22 -- see charms.py). It used to
# live here as `_club`, but the design intent is a deliberate equipment choice,
# not a random level-up card, so the clava charm is the sole source.
def _legs(p, g): p.grant_part('legs', g)
def _spikes(p, g): p.grant_part('spikes', g)
def _horns(p, g): p.grant_part('horns', g)
def _plates(p, g): p.grant_part('plates', g)


MUTATIONS_LIST = [
    _m('health',  'Coracao Extra',   '+1 vida maxima',              5,   _health),
    _m('speed',   'Agilidade',       '+14% velocidade',             130, _speed),
    _m('dash',    'Arranco Rapido',  '-20% recarga do dash',        190, _dash),
    _m('energy',  'Folego',          '+30 energia maxima',          210, _energy),
    _m('regen',   'Regeneracao',     'cura vida lentamente',        150, _regen, 0.8),
    _m('xp',      'Metabolismo',     '+25% de XP',                  50,  _xp),
    _m('tongue',  'Lingua Longa',    '+alcance da lingua',          320, _tongue),
    _m('thorns',  'Espinhos',        'dano de contato + espinhos',  330, _thorns),
    _m('spikes',  'Placas Dorsais',  'mais espinhos afiados',       28,  _spikes),
    _m('plates',  'Carapaca',        'placas de armadura',          260, _plates),
    _m('horns',   'Chifres',         'chifres na cabeca',           20,  _horns, 0.9),
    _m('legs',    'Pernas Extras',   '+2 pernas (mais estavel)',    275, _legs, 0.9),
    _m('venom',   'Peconha',         'dash/bote envenena',          105, _venom, 0.8),
    _m('wings',   'Membranas',       'dash: +50% dano e mais rapido', 175, _wings, 0.7),
    _m('might',   'Vigor',           '+20% dano (armas, dash, rabo)', 0,   _might, 1.2),
    _m('area',    'Amplitude',       '+18% area/alcance das armas', 150, _area, 1.1),
    _m('haste',   'Frenesi',         '+15% cadencia das armas',     190, _haste, 1.1),
    _m('amount',  'Fecundidade',     '+1 projetil/orbital',         55,  _amount, 0.9),
]
MUTATIONS = Registry(MUTATIONS_LIST)
# 'club' used to be here -- removed in issue #22 (charm-only now).
_ONCE = ('venom', 'wings', 'thorns')          # don't offer twice once owned
