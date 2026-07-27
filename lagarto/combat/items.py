"""Items: actives you fire on a button, and passives that CHANGE how things work.

Two lessons drive this module, one from each reference.

**Isaac**: the items people remember modify a mechanic, they do not add a stat.
Spirit Sword replaces your shot with a sword; Terra turns tears into rocks. A
"+10% damage" pickup is forgettable by construction. So every passive here
rewrites a verb the player already owns -- the dash leaves poison behind, the
tongue throws instead of pulls, a kill detonates -- and the hooks live at exactly
one call site each, because the dash already taught us what happens when the same
rule is written in two places.

**Gungeon**: quality tiers and per-origin pools are what let a rare item stay
rare without hand-tuning every drop, and synergies must be *named and visible*
or the player never learns they exist.

`Player.ability` / `ability_cd` had been declared and decremented since long
before this module -- an empty socket. Actives fill it, charged by kills so the
resource ties into the combo loop the game already runs on.
"""

import random

from pygame import Vector2

from ..core import config as C
from ..core import palette
from ..core.mathutil import safe_norm
from ..core.registry import Registry

# Where an item can come from. A pool is just a tag; the shop, the nests and the
# level-up roll each ask for the ones they are allowed to offer.
POOL_LEVEL = 'level'      # level-up cards
POOL_SHOP = 'shop'        # the beetle's tent
POOL_NEST = 'nest'        # destroyed nests
POOL_BOSS = 'boss'        # boss reward


class Item:
    """One item. ``kind`` is 'active' or 'passive'.

    quality 0-4 (Isaac's scale): 0 = situational, 4 = run-defining. It biases
    how often an item is offered, so a strong item can exist without being
    common and a weak one can exist without being a trap.
    """

    def __init__(self, iid, name, desc, hue, kind='passive', quality=1,
                 pools=(POOL_LEVEL,), apply=None, activate=None, charge=None,
                 icon=None):
        self.id = iid
        self.name = name
        self.desc = desc
        self.hue = hue
        self.kind = kind
        self.quality = quality
        self.pools = tuple(pools)
        self.apply = apply              # passive: apply(player, game) once when acquired
        self.activate = activate        # active: activate(player, game) when the button fires
        self.charge = charge or C.ITEM_CHARGE_KILLS
        self.icon = icon or iid
        self.color = palette.vibrant(hue, 0.82, 1.0)

    def weight(self):
        """Offer weight from quality: rare items are rare, not absent."""
        return C.ITEM_QUALITY_WEIGHT[max(0, min(4, self.quality))]


# --------------------------------------------------------------------------- #
#  Actives -- fired with the item button, charged by kills                     #
# --------------------------------------------------------------------------- #

def _act_pulso(p, game):
    """Shockwave: damage + knockback in a ring. The panic button."""
    r = C.ITEM_PULSO_R * p.area_mult
    game.fx.ring(p.pos, (150, 220, 255))
    game.fx.spark_burst(p.pos, (190, 235, 255), 26, 460)
    game.shake(9)
    for e in list(game.enemies):
        if e.dead or e.pos.distance_to(p.pos) > r + e.max_r:
            continue
        away = safe_norm(e.pos - p.pos)
        e.take_hit(game, away, int(round(C.ITEM_PULSO_DMG * p.might)))
        e.vel += away * C.ITEM_PULSO_KNOCK


def _act_muda(p, game):
    """Shed your skin: full i-frames and a burst of speed to escape a pile."""
    p.hit_flash = 1.0                 # i-frames start now
    p.shed_t = C.ITEM_MUDA_TIME
    p.energy = min(p.max_energy, p.energy + 30)
    game.fx.burst(p.pos, palette.lighten(p.color, 0.5), 26, 300)
    game.fx.ring(p.pos, p.color)


def _act_chamado(p, game):
    """Call the swarm: temporary allies, on the same terms an egg hatches them."""
    from ..creatures.ai import AILizard
    for _ in range(C.ITEM_CHAMADO_COUNT):
        pos = p.pos + Vector2(random.uniform(-70, 70), random.uniform(-70, 70))
        f = AILizard(pos, 'friend', 0.9, C.COL_FRIEND)
        f.hp = C.FRIEND_HP
        f.sync_max_hp()
        f.life = C.FRIEND_LIFE
        game.friends.append(f)
    game.fx.ring(p.pos, C.COL_FRIEND)
    game.fx.spark_burst(p.pos, C.COL_FRIEND, 16, 300)


def _act_ferrao(p, game):
    """A volley of homing stings -- the aimed answer to the pulse's panic."""
    from .projectile import Projectile, homing
    from ..core.mathutil import random_dir
    mouth = p.spine.joints[0] + p.spine.head_dir() * p.max_r
    for _ in range(C.ITEM_FERRAO_COUNT):
        pr = Projectile(mouth, random_dir(300),
                        (255, 210, 120),
                        dmg=int(round(C.ITEM_FERRAO_DMG * p.might)),
                        radius=6, hostile=False, life=3.2)
        pr.on_update.append(homing)     # the movement hook curves it to a target
        game.spawn_projectile(pr)
    game.fx.spark_burst(mouth, (255, 220, 150), 12, 340)


# --------------------------------------------------------------------------- #
#  Passives -- each one rewrites a verb, and reads at ONE call site            #
# --------------------------------------------------------------------------- #

def _p_rastro(p, g):    p.dash_trail = True
def _p_arremesso(p, g): p.tongue_throw = True
def _p_farpas(p, g):    p.whip_darts = True
def _p_estopim(p, g):   p.kill_blast = True
def _p_iman(p, g):      p.pollen_magnet = True
def _p_carnica(p, g):   p.kill_heal = True
def _p_ricochete(p, g): p.dash_chain_bonus = True
def _p_casulo(p, g):    p.shed_on_hurt = True
def _p_marcado(p, g):   p.dash_marks = True
def _p_contagio(p, g):  p.poison_spreads = True
def _p_retaguarda(p, g): p.amount_back = True
def _p_contragolpe(p, g): p.whip_reflect = True
def _p_adrenalina(p, g): p.adrenaline = True
def _p_sanguessuga(p, g): p.tongue_drain = True
def _p_segundo(p, g):   p.extra_life = True
def _p_espiral(p, g):   p.whip_full = True


ITEMS_LIST = [
    # ---- actives ---------------------------------------------------------- #
    Item('pulso', 'Pulso Sismico',
         'ativo: onda de choque que fere e empurra ao redor',
         200, 'active', quality=2, pools=(POOL_LEVEL, POOL_SHOP), activate=_act_pulso),
    Item('muda', 'Muda de Pele',
         'ativo: invulneravel por um instante e escapa em disparada',
         160, 'active', quality=3, pools=(POOL_LEVEL, POOL_BOSS), activate=_act_muda),
    Item('chamado', 'Chamado',
         'ativo: convoca aliados temporarios',
         270, 'active', quality=2, pools=(POOL_SHOP, POOL_NEST), activate=_act_chamado),
    Item('ferrao_ativo', 'Salva de Ferroes',
         'ativo: rajada de ferroes teleguiados',
         42, 'active', quality=3, pools=(POOL_LEVEL, POOL_BOSS), activate=_act_ferrao),

    # ---- passives that change a verb -------------------------------------- #
    Item('rastro', 'Rastro Corrosivo',
         'o dash deixa um rastro que corroi quem pisa',
         95, quality=3, pools=(POOL_LEVEL, POOL_BOSS), apply=_p_rastro),
    Item('arremesso', 'Lingua de Arremesso',
         'a lingua ARREMESSA o alvo em vez de puxar',
         320, quality=2, pools=(POOL_LEVEL, POOL_SHOP), apply=_p_arremesso),
    Item('farpas', 'Farpas de Cauda',
         'a rabada dispara farpas nas pontas do arco',
         30, quality=3, pools=(POOL_LEVEL,), apply=_p_farpas),
    Item('estopim', 'Estopim',
         'inimigo morto explode e fere os vizinhos',
         18, quality=3, pools=(POOL_LEVEL, POOL_BOSS), apply=_p_estopim),
    Item('iman', 'Iman Vital',
         'frutas e insetos vem ate voce sozinhos',
         50, quality=1, pools=(POOL_SHOP, POOL_NEST), apply=_p_iman),
    Item('carnica', 'Carnica',
         'cada abate devolve um pouco de vida',
         355, quality=2, pools=(POOL_LEVEL, POOL_SHOP), apply=_p_carnica),
    Item('ricochete', 'Ricochete',
         'matar com dash recarrega o dash por completo',
         190, quality=2, pools=(POOL_LEVEL,), apply=_p_ricochete),
    Item('casulo', 'Casulo',
         'levar dano concede um instante de invulnerabilidade extra',
         140, quality=2, pools=(POOL_SHOP, POOL_BOSS), apply=_p_casulo),
    Item('marcado', 'Presa Marcada',
         'atravessar de dash MARCA o inimigo: o proximo golpe e critico',
         285, quality=3, pools=(POOL_LEVEL,), apply=_p_marcado),
    Item('contagio', 'Contagio',
         'inimigo envenenado que morre contamina os vizinhos',
         110, quality=3, pools=(POOL_LEVEL, POOL_BOSS), apply=_p_contagio),
    Item('retaguarda', 'Retaguarda',
         'as armas disparam tambem para TRAS',
         215, quality=2, pools=(POOL_LEVEL, POOL_SHOP), apply=_p_retaguarda),
    Item('contragolpe', 'Contragolpe',
         'a rabada REBATE projeteis inimigos de volta',
         60, quality=4, pools=(POOL_BOSS,), apply=_p_contragolpe),
    Item('adrenalina', 'Adrenalina',
         'com pouca vida, seu dano sobe muito',
         0, quality=3, pools=(POOL_LEVEL, POOL_SHOP), apply=_p_adrenalina),
    Item('sanguessuga', 'Sanguessuga',
         'a lingua em inimigo drena vida para voce',
         340, quality=3, pools=(POOL_LEVEL,), apply=_p_sanguessuga),
    Item('segundo', 'Segundo Folego',
         'uma vez por run, escapa da morte com metade da vida',
         48, quality=4, pools=(POOL_SHOP, POOL_BOSS), apply=_p_segundo),
    Item('espiral', 'Cauda em Espiral',
         'a rabada varre o circulo INTEIRO ao redor',
         172, quality=4, pools=(POOL_BOSS,), apply=_p_espiral),
]
ITEMS = Registry(ITEMS_LIST)
ACTIVES = [i for i in ITEMS_LIST if i.kind == 'active']
PASSIVES = [i for i in ITEMS_LIST if i.kind == 'passive']


def in_pool(pool, owned=()):
    """Items from ``pool`` the player does not already have."""
    return [i for i in ITEMS.by(pools=pool) if i.id not in owned]


def roll(pool, owned=(), n=1, rng=random):
    """Weighted pick from a pool -- quality biases the odds, never gates them."""
    return ITEMS.roll(pool=pool, n=n, rng=rng,
                      filter=lambda it: it.id not in owned)


def give(player, item, game=None):
    """Grant an item. Actives go to the socket; passives apply once."""
    if item.id in player.items:
        return False
    player.items.append(item.id)
    if item.kind == 'active':
        player.ability = item.id
        player.ability_charge = 0.0        # earn the first use
        player.ability_kills = 0
    elif item.apply:
        item.apply(player, game)
    return True


def use_active(player, game):
    """Fire the equipped active if it is charged. Returns True if it went off."""
    if not player.ability or player.ability_charge < 1.0:
        return False
    item = ITEMS.get(player.ability)
    if item is None or item.activate is None:
        return False
    player.ability_charge = 0.0
    player.ability_kills = 0
    item.activate(player, game)
    return True


def add_charge(player, kills=1):
    """Kills charge the active -- ties the resource to the loop already running.

    Counted as INTEGER kills, then divided. Accumulating ``1/charge`` as a float
    lands on 0.9999999999999998 after exactly `charge` kills, so the item would
    sit there looking full and refuse to fire.
    """
    item = ITEMS.get(player.ability) if player.ability else None
    if item is None:
        return
    player.ability_kills = min(item.charge, player.ability_kills + kills)
    player.ability_charge = player.ability_kills / float(item.charge)
