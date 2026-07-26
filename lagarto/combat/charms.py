"""Charms: Hollow-Knight-style adaptations equipped in 3 body slots.

Slots: head / back / tail (one charm each). Each charm has an ``apply`` and a
reversible ``unapply`` that tweak Player/Genome fields, plus a **visible part**
(set via genome flags, drawn by ``parts.draw_all``). Charms are a separate layer
from level-up mutations, bought at the camp shop or dropped by nests, and swapped
only at the camp.
"""

from ..core import palette
from ..core.registry import Registry


class Charm:
    def __init__(self, cid, slot, name, desc, hue, cost, apply, unapply, icon=None):
        self.id = cid
        self.slot = slot            # 'head' | 'back' | 'tail'
        self.name = name
        self.desc = desc
        self.hue = hue
        self.cost = cost
        self.color = palette.vibrant(hue, 0.82, 1.0)
        self.apply = apply
        self.unapply = unapply
        # Issue #25: charms can override the icon key so they don't
        # collide with weapons that share an id. The 'ferrao' charm
        # (rabada envenena) and the 'ferrao' weapon (Ferrão Teleguiado)
        # both default to icon key 'ferrao' -- the charm now overrides
        # to 'ferrao_charm' so each can have its own art. Falls back
        # to the cid if no override is set (preserves existing behavior).
        self.icon = icon or cid


def _c(cid, slot, name, desc, hue, cost, ap, un, icon=None):
    return Charm(cid, slot, name, desc, hue, cost, ap, un, icon=icon)


# ---- head ----------------------------------------------------------------- #
def _antenas_ap(p, g): p.tongue_range += 120; p.genome.antennae = True
def _antenas_un(p, g): p.tongue_range -= 120; p.genome.antennae = False
def _presas_ap(p, g): p.venom = True; p.genome.fangs = True
def _presas_un(p, g): p.venom = ('venom' in p.mutations); p.genome.fangs = False
def _olhos_ap(p, g): p.area_mult *= 1.2; p.genome.extra_eyes += 2
def _olhos_un(p, g): p.area_mult /= 1.2; p.genome.extra_eyes = max(0, p.genome.extra_eyes - 2)

# ---- back ----------------------------------------------------------------- #
def _carapaca_ap(p, g): p.armor = min(0.6, p.armor + 0.2); p.genome.plates += 1
def _carapaca_un(p, g): p.armor = max(0.0, p.armor - 0.2); p.genome.plates = max(0, p.genome.plates - 1)
def _espinhos_ap(p, g): p.thorns += 2; p.genome.spikes += 1
def _espinhos_un(p, g): p.thorns = max(0, p.thorns - 2); p.genome.spikes = max(0, p.genome.spikes - 1)
def _asas_ap(p, g): p.wings = True; p.genome.wings = True; p.max_speed *= 1.1
def _asas_un(p, g): p.wings = ('wings' in p.mutations); p.genome.wings = False; p.max_speed /= 1.1
def _glandula_ap(p, g): p.gain_weapon('esporos'); p.genome.spore_sacs = True
def _glandula_un(p, g): p.genome.spore_sacs = False       # weapon stays; sacs hidden

# ---- tail ----------------------------------------------------------------- #
# The club tail used to be a level-up mutation, so unequipping a tail charm
# used to peek at `player.mutations` to restore it. Issue #22 made the club
# charm-only, so 'club' can never be in player.mutations -- the only tail
# state to restore to is 'normal' (character-default tails come from the
# Genome, which a charm unequip should not erase).
def _tail_restore(p): return 'normal'
def _ferrao_ap(p, g): p.genome.tail = 'sting'
def _ferrao_un(p, g): p.genome.tail = _tail_restore(p)
def _clava_ap(p, g): p.genome.tail = 'club'
def _clava_un(p, g): p.genome.tail = _tail_restore(p)
def _nectar_ap(p, g): p.regen += 3.0; p.genome.nectar_sac = True
def _nectar_un(p, g): p.regen = max(0.0, p.regen - 3.0); p.genome.nectar_sac = False


CHARMS_LIST = [
    _c('antenas',  'head', 'Antenas',            '+alcance da lingua',       190, 30, _antenas_ap, _antenas_un),
    _c('presas',   'head', 'Presas de Veneno',   'ataques envenenam',        105, 34, _presas_ap, _presas_un),
    _c('olhos',    'head', 'Olhos de Cacador',   '+20% area das armas',       50, 34, _olhos_ap, _olhos_un),
    _c('carapaca', 'back', 'Carapaca',           'bloqueia 20% do dano',     260, 42, _carapaca_ap, _carapaca_un),
    _c('espinhos', 'back', 'Espinhos',           'dano de contato',          330, 32, _espinhos_ap, _espinhos_un),
    _c('asas',     'back', 'Asas de Besouro',    '+velocidade e dash',       175, 38, _asas_ap, _asas_un),
    _c('glandula', 'back', 'Glandula de Esporos', 'libera a arma de esporos', 135, 46, _glandula_ap, _glandula_un),
    _c('ferrao',   'tail', 'Ferrao',             'rabada envenena',           18, 34, _ferrao_ap, _ferrao_un,
       icon='ferrao_charm'),    # issue #25: distinct from the 'ferrao' weapon's icon
    _c('clava',    'tail', 'Cauda-Clava',        'rabada: +dano e empurrao',  15, 34, _clava_ap, _clava_un),
    _c('nectar',   'tail', 'Glandula de Nectar', 'regeneracao de vida',       45, 36, _nectar_ap, _nectar_un),
]
CHARMS = Registry(CHARMS_LIST)
