"""Synergies: named combos that fire when the player owns the right set.

Collecting the right mutations/weapons/items triggers a named ``Synergy`` for an
extra kick, the "just one more run" hook (Lake of Creatures).
"""

from ...core.registry import Registry


class Synergy:
    def __init__(self, sid, name, needs, desc, apply):
        self.id = sid
        self.name = name
        self.needs = needs        # set of mutation ids required
        self.desc = desc
        self.apply = apply


def _syn_arachnid(p, g): p.speed_mult *= 1.15; p.max_speed *= 1.15; p.venom = True
def _syn_fortress(p, g): p.thorns += 2; p.max_health += 30; p.health += 30
def _syn_glass(p, g): p.max_speed *= 1.2; p.dash_cooldown *= 0.7
def _syn_corrosao(p, g): p.area_mult *= 1.35
def _syn_metralha(p, g): p.amount += 1
def _syn_ceifador(p, g): p.might *= 1.25
def _syn_praga(p, g): p.venom = True; p.might *= 1.15
def _syn_bola(p, g): p.whip_mult *= 1.5; p.whip_cooldown *= 0.8
def _syn_fantasma(p, g): p.dash_cooldown *= 0.6; p.max_speed *= 1.1
def _syn_colmeia(p, g): p.amount += 1; p.cooldown_mult *= 0.85
def _syn_ultimo(p, g): p.armor = min(0.7, p.armor + 0.15); p.regen += 3.0
def _syn_chicote(p, g): p.whip_cooldown *= 0.7


# `needs` may name a mutation, a weapon, an ITEM or a character id -- see
# `owned_tags`. Gungeon's rule applies: every synergy is NAMED and shown in the
# compendium, because one the player never learns about may as well not exist.
SYNERGIES_LIST = [
    Synergy('arachnid', 'ARACNIDEO', {'legs', 'venom'},
            'pernas + peconha: velocidade e veneno', _syn_arachnid),
    Synergy('fortress', 'FORTALEZA', {'plates', 'thorns'},
            'placas + espinhos: reflete dano', _syn_fortress),
    Synergy('glass', 'RELAMPAGO', {'speed', 'wings'},
            'agilidade + membranas: dash brutal', _syn_glass),
    Synergy('corrosao', 'CORROSAO', {'rastro', 'acido'},
            'rastro do dash + poca de acido: area muito maior', _syn_corrosao),
    Synergy('metralha', 'METRALHA', {'retaguarda', 'cuspe'},
            'retaguarda + cuspe: mais um projetil por salva', _syn_metralha),
    Synergy('ceifador', 'CEIFADOR', {'estopim', 'carnica'},
            'estopim + carnica: cada abate alimenta o proximo', _syn_ceifador),
    Synergy('praga', 'PRAGA VIVA', {'contagio', 'venom'},
            'contagio + peconha: o veneno nunca para de se espalhar', _syn_praga),
    Synergy('bola', 'BOLA DE DEMOLICAO', {'clava', 'farpas'},
            'clava + farpas: a rabada vira arma de cerco', _syn_bola),
    Synergy('fantasma', 'FANTASMA', {'marcado', 'ricochete'},
            'presa marcada + ricochete: dash atras de dash', _syn_fantasma),
    Synergy('colmeia', 'COLMEIA', {'enxame', 'chamado'},
            'enxame + chamado: voce nunca luta sozinho', _syn_colmeia),
    Synergy('ultimo', 'ULTIMO SUSPIRO', {'segundo', 'adrenalina'},
            'segundo folego + adrenalina: mais forte a beira da morte', _syn_ultimo),
    Synergy('chicote', 'CHICOTE VIVO', {'vibora', 'espiral'},
            'vibora + cauda em espiral: a cauda nao para', _syn_chicote),
]
SYNERGIES = Registry(SYNERGIES_LIST)


def owned_tags(player):
    """Everything a synergy can key on: mutations, weapons, items, character,
    and equipped charms.

    One flat set on purpose -- a synergy should be able to say "this weapon plus
    that item" without caring which system each half comes from. Charms only
    count when equipped (slot-bound, like Hollow Knight); issue #22 moved the
    club tail here, so the BOLA synergy now keys on the ``clava`` charm instead
    of the removed ``club`` mutation.
    """
    tags = set(player.mutations) | set(player.weapons)
    tags |= set(getattr(player, 'items', ()))
    tags |= {cid for cid in player.charm_slots.values() if cid}
    cid = getattr(player, 'character_id', None)
    if cid:
        tags.add(cid)
    return tags


def synergy_progress(player):
    """[(synergy, owned_count, total)] -- what the compendium shows."""
    tags = owned_tags(player)
    return [(s, len(s.needs & tags), len(s.needs)) for s in SYNERGIES]


def check_synergies(player, game):
    """Fire any newly-completed synergy; returns names triggered this call."""
    owned = owned_tags(player)
    fired = []
    for s in SYNERGIES:
        if s.id not in player.synergies and s.needs <= owned:
            player.synergies.add(s.id)
            s.apply(player, game)
            fired.append(s.name)
    return fired
