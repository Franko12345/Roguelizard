"""Species = a genome template + gameplay metadata.

Spawning a species makes a colour/size-jittered variation of its genome, so every
lizard on screen looks a little different. ``role`` maps to the AI kind, ``grants``
is the body part the player gains by eating one (Phase 4 wires that up), and
``diet`` lets predators hunt other creatures for the living-ecosystem feel.
"""

import random as _random

from ..core import config as C
from ..combat import emitter
from .genome import Genome

SPECIES = {
    # ---- prey (wander / flee, feed the player and the predators) ---------- #
    'grazer': dict(role='prey', xp=3, score=15, grants=None,
                   genome=Genome(name='grazer', size=0.85, hue=95, sat=0.8, val=0.95,
                                 behavior='flee', hp=2,
                                 angular_damping=0.35, linear_damping=0.3, weight=1.3)),
    'critter': dict(role='prey', xp=2, score=10, grants=None,
                    genome=Genome(name='critter', size=0.62, leg_count=4, hue=190,
                                  behavior='flee', hp=1, speed=1.15,
                                  angular_damping=0.15, linear_damping=0.15, weight=0.6)),

    # ---- enemies ---------------------------------------------------------- #
    'runner': dict(role='enemy', xp=5, score=40, grants=None,
                   genome=Genome(name='runner', size=0.72, leg_count=4, hue=42,
                                 speed=1.5, behavior='chase', hp=4, diet=('prey',),
                                 angular_damping=0.1, linear_damping=0.1, weight=0.6)),
    'tank': dict(role='enemy', xp=9, score=70, grants='plates',
                 genome=Genome(name='tank', size=1.5, girth=1.25, leg_count=4, hue=6,
                               speed=0.68, plates=1, behavior='chase', hp=14, diet=('prey',),
                               angular_damping=0.6, linear_damping=0.5, weight=2.5)),
    'snake': dict(role='enemy', xp=6, score=50, grants=None,
                  genome=Genome(name='snake', size=0.95, length=1.9, leg_count=0, hue=282,
                                speed=1.2, behavior='chase', hp=6, diet=('prey',),
                                angular_damping=0.2, linear_damping=0.15, weight=0.7)),
    'horned': dict(role='enemy', xp=6, score=55, grants='horns',
                   genome=Genome(name='horned', size=1.12, leg_count=4, hue=20, horns=2,
                                 behavior='chase', hp=8, diet=('prey',),
                                 angular_damping=0.35, linear_damping=0.3, weight=1.2)),
    'spiky': dict(role='enemy', xp=6, score=55, grants='spikes',
                  genome=Genome(name='spiky', size=1.0, leg_count=4, hue=322, spikes=1,
                                behavior='chase', hp=8, diet=('prey',),
                                angular_damping=0.25, linear_damping=0.25, weight=1.0)),
    'spider': dict(role='enemy', xp=7, score=60, grants='legs',
                   genome=Genome(name='spider', size=1.05, radial=True, leg_count=8,
                                 hue=265, sat=0.55, val=0.7, speed=1.15,
                                 behavior='lunge', hp=6, diet=('prey',),
                                 angular_damping=0.15, linear_damping=0.2, weight=0.8)),
    # `shot` is the emitter pattern this species fires (ADR-0012): a single
    # aimed spit is just a one-shot fan, so widening the CUSPIDOR into a cone --
    # or into a radial burst, or a spiral -- is a dial edit here and no code.
    'spitter': dict(role='enemy', xp=7, score=60, grants=None,
                    genome=Genome(name='spitter', size=0.95, leg_count=4, hue=150,
                                  speed=0.85, behavior='ranged', hp=6, diet=('prey',),
                                  shot=dict(fn=emitter.fan_shot, count=1, spread=0,
                                            dmg=C.ENEMY_PROJ_DMG, shot_speed=230),
                                  angular_damping=0.3, linear_damping=0.25, weight=1.0)),
    'scorpion': dict(role='enemy', xp=8, score=65, grants='sting',
                     genome=Genome(name='scorpion', size=1.05, leg_count=6, hue=18,
                                   sat=0.7, tail='sting', speed=0.95, behavior='chase',
                                   hp=8, diet=('prey',),
                                   angular_damping=0.4, linear_damping=0.35, weight=1.4)),

    # ---- phase 2: enemies that change how you must MOVE ------------------- #
    # Each one attacks a different habit: the flyer beats hiding behind the
    # horde, the bomber beats standing still, the gunner beats open ground and
    # the venomer beats camping a spot.
    'wasp': dict(role='enemy', xp=5, score=45, grants=None,
                 genome=Genome(name='wasp', size=0.6, length=0.7, leg_count=0,
                               wings=True, antennae=True, hue=52, sat=0.95,
                               speed=1.55, behavior='fly', hp=3, diet=('prey',),
                               angular_damping=0.1, linear_damping=0.1, weight=0.5)),
    'bomber': dict(role='enemy', xp=7, score=65, grants=None,
                   genome=Genome(name='bomber', size=0.95, girth=1.45, length=0.7,
                                 leg_count=4, hue=28, sat=0.95, val=1.0,
                                 speed=1.0, behavior='bomber', hp=3,
                                 spore_sacs=True, diet=(),
                                 angular_damping=0.1, linear_damping=0.1, weight=0.5)),
    'gunner': dict(role='enemy', xp=7, score=60, grants=None,
                   genome=Genome(name='gunner', size=0.9, leg_count=4, hue=200,
                                 sat=0.85, speed=0.9, behavior='gunner', hp=5,
                                 extra_eyes=2, diet=('prey',),
                                 shot=dict(fn=emitter.fan_shot, count=1,
                                           jitter=C.GUNNER_SPREAD, dmg=C.GUNNER_DMG,
                                           shot_speed=300, radius=5),
                                 angular_damping=0.25, linear_damping=0.2, weight=0.9)),
    'venomer': dict(role='enemy', xp=8, score=70, grants='sting',
                    genome=Genome(name='venomer', size=1.05, leg_count=4, hue=100,
                                  sat=0.9, speed=0.8, behavior='venom', hp=6,
                                  spore_sacs=True, tail='sting', diet=('prey',),
                                  shot=dict(fn=emitter.lob_shot, dmg=C.VENOM_SPIT_DMG,
                                            shot_speed=C.VENOM_SPIT_SPEED, radius=7,
                                            puddle=dict(r=C.VENOM_PUDDLE_R,
                                                        dmg=C.VENOM_PUDDLE_DMG,
                                                        life=C.VENOM_PUDDLE_LIFE,
                                                        hue=100,
                                                        tick=C.VENOM_PUDDLE_TICK)),
                                  angular_damping=0.3, linear_damping=0.25, weight=1.0)),

    # ---- issue #104: os dois habitos que o rolamento (#103) criou ---------- #
    # ANTECIPADOR: mira liderando -> pune rolar por reflexo.
    # MORTEIRO: poca que arma com atraso -> pune investir na cara.
    'sniper': dict(role='enemy', xp=8, score=70, grants=None,
                   genome=Genome(name='sniper', size=0.92, length=1.15, leg_count=4,
                                 hue=172, sat=0.75, val=0.95, speed=0.9,
                                 behavior='lead', hp=6, extra_eyes=2, antennae=True,
                                 diet=('prey',),
                                 shot=dict(fn=emitter.aimed_barrage, lead=C.SNIPER_LEAD,
                                           shots=C.SNIPER_SHOTS, gap=C.SNIPER_GAP,
                                           shot_speed=C.SNIPER_SPEED, dmg=C.SNIPER_DMG,
                                           radius=6),
                                 angular_damping=0.35, linear_damping=0.3, weight=1.1)),
    'mortar': dict(role='enemy', xp=8, score=70, grants=None,
                   genome=Genome(name='mortar', size=1.1, girth=1.3, length=0.8,
                                 leg_count=6, hue=330, sat=0.8, val=0.9, speed=0.72,
                                 behavior='mortar', hp=8, spore_sacs=True, diet=(),
                                 # count/spread are read by emitter._select_arms_rain:
                                 # one patch, noised, picked at the START of the arm
                                 shot=dict(count=1, spread=C.MORTAR_SPREAD),
                                 angular_damping=0.45, linear_damping=0.4, weight=1.6)),

    # ---- phase B4: new procedural BODIES + their own mechanics ------------ #
    # CENTOPEIA: a segmented burrower (Isaac's Para-Bite/Moles). Dives, then
    # ambushes from a telegraphed spot -- punishes camping and straight lines.
    'centipede': dict(role='enemy', xp=7, score=60, grants='legs',
                      genome=Genome(name='centipede', plan='segmented', size=1.0,
                                    length=1.5, leg_count=2, hue=88, sat=0.85,
                                    val=0.92, speed=1.15, behavior='burrow', hp=6,
                                    diet=('prey',),
                                    angular_damping=0.3, linear_damping=0.2, weight=1.8)),
    # POLVO: a tentacle grappler (Gungeon's Gripmaster). Slow bruiser that reels
    # you in and slows you -- punishes lingering at its mid-range doorstep.
    'octopus': dict(role='enemy', xp=9, score=75, grants=None,
                    genome=Genome(name='octopus', plan='tentacle', size=1.15,
                                  leg_count=6, hue=315, sat=0.72, val=0.9,
                                  speed=0.82, behavior='grapple', hp=10,
                                  knockback=0.28,      # a shove barely nudges it
                                  angular_damping=0.7, linear_damping=0.6, weight=3.0,
                                  diet=('prey',))),

    # OLHO-SISMICO: a floating eyeball (plan='orbital'). Only ever spawned as a
    # boss (B9); the entry exists so species.make(key) works. Floating = heavy
    # weight + high damping (no run inertia, holds its spot).
    'olho_sismico': dict(role='enemy', xp=12, score=90, grants=None,
                         genome=Genome(name='olho_sismico', plan='orbital', size=1.1,
                                       leg_count=6, hue=280, sat=0.7, val=0.85,
                                       speed=0.6, behavior='chase', hp=12, diet=(),
                                       angular_damping=0.9, linear_damping=0.85, weight=4.0)),

    # A MURALHA (B10): plan='fixed' - static wall occupying right side of arena.
    # role='boss' keeps it OUT of ENEMY_SPECIES: the 'invasao' theme pool is
    # literally list(ENEMY_SPECIES), and the boss summon pattern falls back to
    # it, so with role='enemy' a normal wave could roll a wall as a mook -- and
    # a wall has speed 0, which used to divide by zero the moment it steered.
    'muralha': dict(role='boss', xp=15, score=120, grants=None,
                    genome=Genome(name='muralha', plan='fixed', size=1.2,
                                  leg_count=0, hue=15, sat=0.6, val=0.4,
                                  speed=0.0, behavior='chase', hp=15, diet=(),
                                  angular_damping=0.9, linear_damping=0.9, weight=10.0)),

    # ---- extra prey ------------------------------------------------------- #
    'frog': dict(role='prey', xp=3, score=18, grants=None,
                 genome=Genome(name='frog', size=0.7, leg_count=4, length=0.6, girth=1.3,
                               hue=110, behavior='hop', hp=2,
                               angular_damping=0.4, linear_damping=0.35, weight=1.5)),
    'fish': dict(role='prey', xp=3, score=15, grants=None,
                 genome=Genome(name='fish', size=0.75, leg_count=0, length=0.8, fins=1,
                               tail='fin', hue=195, behavior='flee', hp=1, speed=1.1,
                               angular_damping=0.15, linear_damping=0.15, weight=0.6)),
}

PREY_SPECIES = [k for k, v in SPECIES.items() if v['role'] == 'prey']
ENEMY_SPECIES = [k for k, v in SPECIES.items() if v['role'] == 'enemy']

# Display name + lore for the bestiary screen (kept apart so the tables stay lean).
LORE = {
    'grazer':  ('PASTADOR', 'Herbivoro placido que rumina flores. Foge de tudo que se '
                            'move rapido. Alimento farto para quem sabe caçar.'),
    'critter': ('BICHINHO', 'Pequeno e nervoso, corre em zigue-zague. Pouca carne, mas '
                            'facil de abocanhar quando se esta com fome.'),
    'frog':    ('SAPO', 'Anfibio saltador: nunca anda em linha reta, so pula. Dificil '
                        'de acertar em movimento, mas indefeso quando pousa.'),
    'fish':    ('PEIXE', 'Nada em cardume nas aguas do pantano. Suas nadadeiras ondulam '
                         'mesmo fora d agua. Presa dos que ousam entrar no lago.'),
    'runner':  ('CORREDOR', 'Predador magro e veloz que ataca em bando. Sozinho e fraco; '
                            'em enxame, cerca a presa antes que ela perceba.'),
    'tank':    ('COURACADO', 'Massa lenta coberta de placas osseas. Aguenta muito castigo '
                             'e empurra tudo pela frente. Comer um concede sua carapaca.'),
    'snake':   ('SERPENTE', 'Corpo longo sem pernas que desliza em curvas. Persegue sem '
                            'descanso e e dificil de encurralar.'),
    'horned':  ('CHIFRUDO', 'Investe de cabeca baixa com dois chifres curvos. Devorar um '
                            'faz nascerem chifres no seu proprio cranio.'),
    'spiky':   ('ESPINHENTO', 'Coberto de espinhos dorsais que se eriçam ao atacar. '
                              'Abate-lo pode transplantar seus espinhos para voce.'),
    'spider':  ('ARANHA', 'Oito pernas radiais que a sustentam em qualquer terreno. '
                          'Telegrafa o bote e salta. Comer uma faz brotar mais pernas.'),
    'spitter': ('CUSPIDOR', 'Mantem distancia e lança veneno a jato. Prepara o cuspe '
                            'antes de disparar — da para desviar de quem repara.'),
    'scorpion': ('ESCORPIAO', 'Arrasta um ferrao curvo na cauda que envenena e retarda. '
                              'Quem sobrevive ao ferrao pode herda-lo.'),
    'wasp':    ('VESPA', 'Nao toca o chao: atravessa a horda em linha reta e vem '
                         'direto a voce. Esconder-se atras dos outros nao adianta.'),
    'bomber':  ('ESTOURADOR', 'Corpo inchado de gas. Ao chegar perto acende o pavio '
                              'e desacelera — dali em diante, o estouro sai onde ele '
                              'parar. Sempre da pra sair andando.'),
    'gunner':  ('METRALHADOR', 'Mantem distancia media e despeja rajadas curtas. '
                               'Pouco dano por tiro, muita pressao: quebre a linha.'),
    'venomer': ('ENVENENADOR', 'Cospe veneno onde voce esta e deixa uma poca que '
                               'corroi. Nao mira para acertar, mira para tomar o '
                               'terreno.'),
    'sniper':  ('ANTECIPADOR', 'Nao atira em voce: atira no lugar para onde voce '
                               'esta indo. A marca no chao mostra o ponto — quem '
                               'rola por reflexo rola pra dentro dela.'),
    'mortar':  ('MORTEIRO', 'Marca o chao e so depois a poca nasce. Fecha o ponto '
                            'de pouso: investir na cara dele e terminar dentro do '
                            'que ele armou.'),
    'centipede': ('CENTOPEIA', 'Corpo em aneis com dezenas de patas. Caça na '
                               'superficie, entao mergulha e reaparece embaixo de '
                               'quem fica parado. O anel no chao mostra onde vai aflorar.'),
    'octopus': ('POLVO', 'Bicho lento de bracos longos. Estica os tentaculos e, no '
                         'estalo, te fisga para perto e retarda. Fugir antes do bote '
                         'e a saida — de perto, ele te segura.'),
}


def info(key):
    """(display name, lore) for the bestiary; falls back to the raw id."""
    return LORE.get(key, (key.upper(), ''))


def make(species_key, pos, rng=_random):
    """Build a jittered instance of ``species_key`` at ``pos``."""
    from .ai import AILizard               # local import avoids a cycle
    spec = SPECIES[species_key]
    g = spec['genome'].random_variation(rng)
    c = AILizard(pos, spec['role'], genome=g)
    c.species = species_key
    c.xp_value = spec['xp']
    c.score_value = spec['score']
    c.grants = spec['grants']
    # ENEMY_HP_MULT compensa a hitbox de corpo inteiro (antes so a cabeca contava)
    mult = C.ENEMY_HP_MULT if spec['role'] == 'enemy' else 1.0
    c.hp = max(1, int(round(g.hp * mult)))
    c.sync_max_hp()
    return c
