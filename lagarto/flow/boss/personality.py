"""Boss personalities: how a boss REACTS (mood -> speed / pattern weight /
glow colour / tell length).

One factory per boss, in the same order as the phase kits in ``patterns.py``.
"""

from ...core import palette

# --------------------------------------------------------------------------- #
#  Personality: mood -> speed / pattern weight / glow colour / tell length     #
# --------------------------------------------------------------------------- #

class BossPersonality:
    """How a boss REACTS. A generic default works for any boss; a named boss
    (Rei Lagarto) can pass its own to bias which patterns it favours."""

    def __init__(self, pattern_weights=None, mood_speed=None):
        # mood_speed is overridable so a "calm observer" (Olho-Sismico) can barely
        # move without touching any other boss; default keeps today's values.
        self.mood_speed = mood_speed or {
            'calm': 1.0, 'agitated': 1.3, 'enraged': 1.6,
            'frustrated': 1.4, 'cornered': 0.8,
        }
        self.pattern_weights = pattern_weights or {}
        self.mood_colors = {
            'calm': None,
            'agitated': (255, 180, 50),
            'enraged': (255, 50, 50),
            'frustrated': (200, 50, 255),
            'cornered': (50, 100, 255),
        }
        self.tell_mult = {'enraged': 0.65, 'agitated': 0.8}

    def windup_mult(self, mood):
        return self.tell_mult.get(mood, 1.0)

    def glow_color(self, mood, base_color):
        mood_color = self.mood_colors.get(mood)
        return palette.mix(base_color, mood_color, 0.4) if mood_color else base_color

    def weight(self, pattern_id, mood):
        return self.pattern_weights.get(pattern_id, {}).get(mood, 1.0)


def default_personality():
    return BossPersonality()


def king_personality():
    """Orgulhoso: prefere a investida quando encurralado (não foge, comete);
    fica mais raivoso, não mais covarde.

    Issue #123: ``tell_mult`` is cleared so the windup NEVER shortens with
    mood. The first boss of the game teaches one thing -- "this is what a
    telegraph looks like" -- and the lesson has to survive the boss
    getting angry at you. Eye and ANKH do the same (see their
    docstrings); the difference is that Eye and ANKH use the cleared
    multiplier because their IDENTITY is "the tell is constant". Rei
    uses it because his role is the legibility canonical -- if the
    windup shrank as the boss got angrier, the player would never
    actually learn the language.
    """
    pers = BossPersonality(pattern_weights={
        'charge': {'cornered': 2.2, 'enraged': 1.6},
        'shockwave': {'agitated': 1.5, 'calm': 1.0},
        'spiral': {'enraged': 1.6},
    })
    pers.tell_mult = {}      # the language doesn't shrink as he gets angrier
    return pers


def centipede_personality():
    """Máquina sem propósito: não fica mais covarde nem mais confiante, só
    mais rápida e mais caótica conforme quebra -- pattern_weights ficam quase
    neutros de proposito (o texugo emocional é o `on_phase`, não o mood)."""
    return BossPersonality(pattern_weights={'deathroll': {'enraged': 1.4}})


def kraken_personality():
    """Paciente até doer: prefere fechar a distância (grapple) sempre que
    puder, e vira frenético (arms_rain/spiral) só quando raivoso."""
    return BossPersonality(pattern_weights={
        'grapple': {'calm': 1.6, 'agitated': 1.3},
        'arms_rain': {'enraged': 1.8, 'cornered': 1.5},
        'spiral': {'enraged': 1.4},
    })


def primordial_personality():
    """Deus primitivo: indiferente no início (pesos quase neutros), só
    "nota" você na fase 3 -- aí tudo pesa mais, inclusive o próprio glow
    (BossPersonality.mood_colors já vira vermelho em enraged de graça)."""
    return BossPersonality(pattern_weights={
        'deathroll': {'enraged': 2.0},
        'sky_slam': {'enraged': 1.5, 'cornered': 1.5},
    })


def beetle_personality():
    """Mãe protetora: prioriza chamar reforços; só fica de fato agressiva
    (radial/web_trap) quando raivosa ou encurralada -- ela evita a luta
    direta enquanto pode."""
    return BossPersonality(pattern_weights={
        'summon': {'calm': 1.6, 'frustrated': 1.8},
        'radial': {'enraged': 1.8, 'cornered': 1.6},
    })


def spider_king_personality():
    """Nervosa, quase TDAH: sem padrão dominante forte (varia sempre), mas
    trava (teia) quando frustrada em vez de insistir em perseguir, e vira
    bote/mordida quando encurralada -- reação de pânico, não de cálculo."""
    return BossPersonality(pattern_weights={
        'web_trap': {'frustrated': 1.7}, 'web_dome': {'frustrated': 1.6},
        'poison_bite': {'cornered': 1.8}, 'charge': {'cornered': 1.5, 'agitated': 1.3},
    })


def crystal_personality():
    """Sem rosto, sem emoção: pesos quase neutros de propósito (o doc é
    explícito -- ela não fica "com raiva", só mais dura de ler)."""
    return BossPersonality(pattern_weights={'deathroll': {'enraged': 1.3}})


def wasp_personality():
    """Sádica caçadora: mergulha (charge) sempre que pode, e quando frustrada
    passa a mirar por lead (barrage) em vez de insistir no mergulho -- ela
    'aprende' onde você vai estar."""
    return BossPersonality(pattern_weights={
        'charge': {'calm': 1.5, 'agitated': 1.4, 'cornered': 1.6},
        'barrage': {'frustrated': 2.0},
    })


def eye_personality():
    """Observador calmo: mal se mexe (mood_speed baixo em tudo). O pânico do
    <33% é um flip abrupto -- 'enraged' salta o mood_speed em vez de rampar. Os
    telegrafos NUNCA encurtam (tell_mult zerado), então o gaze fica sempre 36
    frames (a regra do telegrafo vale em qualquer mood)."""
    p = BossPersonality(
        pattern_weights={'bullet_hell': {'enraged': 1.8}, 'shockwave': {'enraged': 1.4}},
        mood_speed={'calm': 0.2, 'agitated': 0.3, 'enraged': 0.9,
                    'frustrated': 0.25, 'cornered': 0.2})
    p.tell_mult = {}
    return p


def wall_personality():
    """Implacavel: voce nao passa. A arena foi feita pra voce morrer aqui.
    Sem estado de frustracao: so calmo e enraivecido, sem meio-termo.
    Fase 3 e tudo ao mesmo tempo."""
    return BossPersonality(
        pattern_weights={
            'fire_breath': {'enraged': 2.0, 'calm': 1.2},
            'hand_slam': {'enraged': 1.8},
            'bouncing_bullets': {'enraged': 1.5},
            'grid_of_fire': {'enraged': 1.8},
        },
        mood_speed={'calm': 1.0, 'agitated': 1.0, 'enraged': 1.5,
                    'frustrated': 1.0, 'cornered': 1.0}
    )


def ankh_personality():
    """Antiga. Nao fala, nao reage, nao se irrita: cada fase e uma memoria de
    um chefe anterior, e uma memoria nao fica com raiva.

    Por isso ``tell_mult`` fica vazio -- o telegrafo dura o mesmo em todos os
    humores. Todo o resto dos chefes encurta o aviso quando enraivecido; ANKH
    nao, porque a leitura que voce aprendeu contra o chefe original tem que
    continuar valendo aqui. A dificuldade vem das fases se sobreporem, nao de
    voce perder tempo de reacao.

    O humor ainda muda a cor do brilho e a velocidade, so que de leve -- ela
    acelera de fase em fase, nao de raiva em raiva.
    """
    pers = BossPersonality(
        pattern_weights={
            'charge': {'cornered': 1.8},
            'summon': {'agitated': 1.4},
            'grapple': {'enraged': 1.5},
            'bullet_hell': {'enraged': 1.8, 'cornered': 1.6},
        },
        mood_speed={'calm': 1.0, 'agitated': 1.15, 'enraged': 1.3,
                    'frustrated': 1.15, 'cornered': 1.0},
    )
    pers.tell_mult = {}      # the memory never speeds up -- see docstring
    return pers