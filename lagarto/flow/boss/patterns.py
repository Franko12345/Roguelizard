"""Boss dial table and phase kits.

The pattern FUNCTIONS live in ``lagarto.combat.emitter`` -- shared with common
enemies (see ``docs/adr/0012-shared-pattern-emitter.md``). What lives here is
the boss-side DATA: ``PATTERNS`` maps a pattern id to the emitter function plus
the dials that function reads, and a phase kit is just a list of pattern ids per
HP threshold -- "boss is data" (see ``lagarto.flow.boss`` for the framework
overview).

``BossAI`` passes the whole ``PATTERNS[pid]`` dict to the emitter as its
``dials`` argument, so a variant of a pattern (Massive Fan, deathroll, Web Dome)
is one more row in this table and no new code.
"""

import random

from ...core import config as C
from ...combat import emitter
from ...combat import projectile as proj
from .personality import BossPersonality

PATTERNS = {
    # Issue #118: each pattern row may carry a ``move`` field -- the
    # Movement Trail binding for that attack. None means the phase's
    # ``moves`` slot drives the boss instead. Charge / burrow / grapple
    # veto by being ``None`` AND short-circuiting the FSM (their own
    # state machines own the motion).
    'radial': dict(fn=emitter.radial_burst, windup=C.BOSS_RADIAL_WINDUP, telegraph='radial'),
    'fan': dict(fn=emitter.fan_shot, windup=C.BOSS_FAN_WINDUP, telegraph='fan'),
    'barrage': dict(fn=emitter.aimed_barrage, windup=C.BOSS_BARRAGE_WINDUP, telegraph='line'),
    'summon': dict(fn=emitter.summon_adds, windup=C.BOSS_SUMMON_WINDUP, telegraph='horn'),
    'shockwave': dict(fn=emitter.shockwave, windup=C.BOSS_SHOCKWAVE_WINDUP, telegraph='shockwave'),
    'pincha': dict(fn=emitter.pincha_bite, windup=C.BOSS_PINCHA_WINDUP, telegraph='line'),
    # Kraken-Mor's tentacle swipe: same pincha_bite fn, just a longer/harder
    # reach via the dials -- no new logic for a longer arm. Bumped 0.5 -> 0.7
    # so the enraged (0.65) multiplier still leaves the windup at 0.455s.
    'swipe': dict(fn=emitter.pincha_bite, windup=0.7, telegraph='line', reach=2.4, dmg=19),
    'arms_rain': dict(fn=emitter.arms_rain, select=emitter._select_arms_rain,
                      windup=C.BOSS_ARMS_RAIN_WINDUP, telegraph='rain'),
    'sky_slam': dict(fn=emitter.sky_slam, select=emitter._select_arms_rain,
                     windup=C.BOSS_SKY_SLAM_WINDUP, telegraph='rain',
                     count=1, spread=0, radius=C.BOSS_SKY_SLAM_RADIUS,
                     dmg=C.BOSS_SKY_SLAM_DMG),
    'massive_fan': dict(fn=emitter.fan_shot, windup=C.BOSS_MASSIVE_FAN_WINDUP, telegraph='fan',
                        count=12, spread=70, shot_speed=220, dmg=20),
    'web_trap': dict(fn=emitter.web_trap, select=emitter._select_arms_rain,
                     windup=C.BOSS_WEB_TRAP_WINDUP,
                     telegraph='rain', count=1, spread=60),
    # Aranha-Rei's Web Dome: same web_trap fn/select, just more/bigger patches
    'web_dome': dict(fn=emitter.web_trap, select=emitter._select_arms_rain, windup=0.8,
                     telegraph='rain', count=5, spread=180, radius=70, life=9.0),
    # Aranha-Rei's poison bite: same pincha_bite, roots instead of poisoning
    # (the player has no poison status -- see pincha_bite's docstring). Bumped
    # 0.3 -> 0.7 for the 27-frame rule; the bite is still a bite, just with
    # the floor respected.
    'poison_bite': dict(fn=emitter.pincha_bite, windup=0.7, telegraph='line',
                        reach=1.6, dmg=15, slow=(0.5, 1.4)),
    # deathroll: bumped 0.5 -> 0.7 so the floor holds in enraged. The dense
    # spiral still reads as "bullet hell" -- the windup is the same as the
    # basic spiral, but the SHOTS dial is what makes it dense.
    'deathroll': dict(fn=emitter.spiral_pattern, windup=0.7, telegraph='spiral',
                      shots=C.BOSS_DEATHROLL_SHOTS, turn=C.BOSS_DEATHROLL_TURN,
                      gap=C.BOSS_DEATHROLL_GAP, shot_speed=260, shot_dmg=12),
    # burrow has no `fn`/instant fire -- BossAI.tick special-cases `burrow=True`
    # and delegates every frame to the boss's OWN ai.burrow.tick (the
    # regular centipede's dig/erupt state machine, telegraphs included for
    # free -- AILizard.draw() already checks self.burrowed/burrow_state)
    'burrow': dict(fn=None, windup=0.05, telegraph=None, burrow=True),
    # same idea as burrow: no `fn`, BossAI.tick delegates every frame to the
    # octopus's own ai.grapple.tick (reach/root/snap+pull+slow, telegraph
    # included -- Lizard.draw already shows the arms converging via arm_target)
    'grapple': dict(fn=None, windup=0.05, telegraph=None, grapple=True),
    'spiral': dict(fn=emitter.spiral_pattern, windup=C.BOSS_SPIRAL_WINDUP, telegraph='spiral'),
    'charge': dict(fn=emitter.charge_attack, windup=C.BOSS_CHARGE_WINDUP, telegraph='line',
                   charge=True),
    # Olho-Sismico. seismic_pulse = the existing 'shockwave' (reused in eye_phases).
    'gaze': dict(fn=emitter.gaze, windup=C.EYE_GAZE_WINDUP, telegraph='line',
                 shots=C.EYE_GAZE_SHOTS, turn=C.EYE_GAZE_TURN, gap=C.EYE_GAZE_GAP,
                 shot_speed=C.EYE_GAZE_SPEED, shot_dmg=C.EYE_GAZE_DMG, arc=C.EYE_GAZE_ARC),
    # tentacle sweep: same pincha_bite contact fn, longer reach via the dials
    'tentacle_swipe': dict(fn=emitter.pincha_bite, windup=C.EYE_SWIPE_WINDUP, telegraph='line',
                           reach=C.EYE_SWIPE_REACH, dmg=C.EYE_SWIPE_DMG),
    'spawn_orb': dict(fn=emitter.spawn_orb, windup=C.EYE_ORB_WINDUP, telegraph='horn',
                      count=C.EYE_ORB_COUNT),
    # bullet hell: a dense/fast spiral -- same spiral_pattern, denser dials
    'bullet_hell': dict(fn=emitter.spiral_pattern, windup=C.EYE_BULLET_WINDUP,
                        telegraph='radial',
                        shots=C.EYE_BULLET_SHOTS, turn=C.EYE_BULLET_TURN, gap=C.EYE_BULLET_GAP,
                        shot_speed=C.EYE_BULLET_SPEED, shot_dmg=C.EYE_BULLET_DMG),
    # A Muralha (B10, tier 6) -- plan='fixed'
    'fire_breath': dict(fn=emitter.fire_breath, windup=C.MURALHA_FIRE_WINDUP, telegraph='fan',
                        shots=C.MURALHA_BREATH_SHOTS, gap=C.MURALHA_BREATH_GAP,
                        shot_speed=C.MURALHA_BREATH_SPEED, shot_dmg=C.MURALHA_BREATH_DMG,
                        spread=C.MURALHA_FIRE_SPREAD),
    'hand_slam': dict(fn=emitter.hand_slam, select=emitter._select_hand_slam,
                      windup=C.MURALHA_HAND_WINDUP,
                      telegraph='line', radius=C.MURALHA_HAND_RADIUS, dmg=C.MURALHA_HAND_DMG),
    'eye_laser': dict(fn=emitter.eye_laser, windup=C.MURALHA_EYE_WINDUP, telegraph='line',
                      count=C.MURALHA_EYE_BEAMS, spread=45,
                      shot_speed=C.MURALHA_EYE_SPEED, dmg=C.MURALHA_EYE_DMG,
                      gap=C.MURALHA_EYE_GAP),
    'bouncing_bullets': dict(fn=emitter.bouncing_bullets, windup=C.MURALHA_BOUNCE_WINDUP,
                             telegraph='line', count=C.MURALHA_BOUNCE_COUNT,
                             shot_speed=C.MURALHA_BOUNCE_SPEED, dmg=C.MURALHA_BOUNCE_DMG,
                             spread=60, bounces=C.MURALHA_BOUNCE_BOUNCES),
    'grid_of_fire': dict(fn=emitter.grid_of_fire, windup=C.MURALHA_GRID_WINDUP, telegraph='rain',
                         cell=C.MURALHA_GRID_CELL, dmg=C.MURALHA_GRID_DMG,
                         tick=C.MURALHA_GRID_TICK, life=C.MURALHA_GRID_LIFE),
    # ---- issue #104: three more special attacks, ZERO new pattern code ------ #
    # Each is dials on a function that already existed, plus at most one
    # `mod` -- the single on_update movement hook the emitter attaches (#102).
    # Leque teleguiado: slow shots that CURVE, so backing off in a straight line
    # stops working and the answer becomes breaking line of sight or the roll.
    'homing_fan': dict(fn=emitter.fan_shot, windup=0.75, telegraph='fan',
                       count=3, spread=24, shot_speed=190, dmg=13,
                       mod=proj.homing),
    # Muralha de balas: a dense, SLOW ring -- density instead of speed, which is
    # the Serpente de Cristal's whole identity ("nao acelera, so fica mais densa").
    'radial_wall': dict(fn=emitter.radial_burst, windup=0.9, telegraph='radial',
                        count=22, shot_speed=150, dmg=11),
    # Leque antecipado: the cone aims where you are GOING (same lead formula as
    # the barrage and the ANTECIPADOR), so dodging sideways into it is the trap.
    'lead_fan': dict(fn=emitter.fan_shot, windup=0.7, telegraph='fan',
                     count=5, spread=30, shot_speed=280, dmg=15, lead=0.6),
}


def king_phases():
    """3 fases (66/33 -- doc's own thresholds for this boss). Fase 2 adds
    Radial Burst (1 thing); fase 3 swaps Fan for Spiral + faster cd (2 things).

    ``moves`` is the MOVES trail (issue #118) -- the BACKGROUND movement
    between attacks. The rich per-boss signatures (#121-#125) fill these
    in; today the slot exists so every phase kit compiles.
    """
    return [
        dict(hp_frac=1.0, patterns=['fan', 'shockwave', 'charge'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.66, patterns=['fan', 'shockwave', 'charge', 'radial'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.33, patterns=['spiral', 'shockwave', 'charge', 'radial'], cd_mul=0.7, moves=['orbit']),
    ]


# --------------------------------------------------------------------------- #
#  Centopeiadeira (onda 10 / tier 2): "Degradação" -- perde segmentos e        #
#  acelera a cada fase, reusando o dig/erupt do centipede comum como um       #
#  padrão a mais entre outros.                                                #
# --------------------------------------------------------------------------- #

def centipede_phases():
    return [
        dict(hp_frac=1.0, patterns=['burrow', 'spiral', 'pincha'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.6, patterns=['burrow', 'spiral', 'pincha', 'radial'], cd_mul=0.85, moves=['orbit']),
        dict(hp_frac=0.3, patterns=['spiral', 'pincha', 'radial', 'deathroll'], cd_mul=0.7, moves=['orbit']),
    ]


def centipede_on_phase(boss, phase_i):
    """Perde segmentos + acelera a cada transição (armadura quebra ao vivo,
    mesmo padrão de `champions.py`): menos corpo, mais velocidade, mais caos --
    e MENOS hitbox de corpo, então o jogador troca "mais perigoso" por "mais
    fácil de acertar em cheio", a decisão que o doc descreve."""
    boss.genome.length = max(0.5, boss.genome.length - C.CENT_BOSS_SHRINK)
    boss.genome.speed *= C.CENT_BOSS_SPEED_BUMP
    boss.rebuild_body(keep_pose=True)


# --------------------------------------------------------------------------- #
#  Kraken-Mor (onda 15 / tier 3): reels you in, then rains arms on the arena. #
# --------------------------------------------------------------------------- #

def kraken_phases():
    return [
        dict(hp_frac=1.0, patterns=['grapple', 'fan', 'swipe'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.66, patterns=['grapple', 'fan', 'swipe', 'arms_rain'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.33, patterns=['grapple', 'spiral', 'swipe', 'arms_rain'], cd_mul=0.75, moves=['orbit']),
    ]


# --------------------------------------------------------------------------- #
#  PRIMORDIAL (onda 20 -- chefe final do modo normal): tudo ao mesmo tempo,   #
#  cada fase soma em vez de trocar (a fase final do jogo ganha a licenca de   #
#  quebrar a "regra dos 2" -- ANKH tem a mesma exceção documentada no doc 03).#
# --------------------------------------------------------------------------- #

def primordial_phases():
    return [
        dict(hp_frac=1.0, patterns=['massive_fan', 'shockwave'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.66, patterns=['massive_fan', 'shockwave', 'sky_slam', 'summon'],
             cd_mul=0.85, moves=['orbit']),
        dict(hp_frac=0.33, patterns=['massive_fan', 'shockwave', 'sky_slam', 'summon',
                                     'deathroll', 'homing_fan'], cd_mul=0.5, moves=['orbit']),
    ]


# --------------------------------------------------------------------------- #
#  Mae-Escaravelho (endless, tier5+): a support, not a tank -- SHE barely     #
#  attacks directly, her adds do the damage. Explodes into larvae on death.  #
# --------------------------------------------------------------------------- #

def beetle_phases():
    return [
        dict(hp_frac=1.0, patterns=['summon', 'fan', 'shockwave'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.66, patterns=['summon', 'fan', 'shockwave', 'web_trap'], cd_mul=0.9, moves=['orbit']),
        dict(hp_frac=0.33, patterns=['summon', 'shockwave', 'web_trap', 'radial'], cd_mul=0.65, moves=['orbit']),
    ]


# --------------------------------------------------------------------------- #
#  Aranha-Rei (endless, tier5+): nervosa, para e dispara -- teia acumula.     #
# --------------------------------------------------------------------------- #

def spider_king_phases():
    return [
        dict(hp_frac=1.0, patterns=['charge', 'web_trap', 'summon'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.6, patterns=['charge', 'web_trap', 'summon', 'web_dome'], cd_mul=0.85, moves=['orbit']),
        dict(hp_frac=0.3, patterns=['poison_bite', 'web_trap', 'summon', 'web_dome'], cd_mul=0.6, moves=['orbit']),
    ]


# --------------------------------------------------------------------------- #
#  Serpente de Cristal (endless, tier5+): fria, nunca acelera, so fica mais   #
#  densa. Nota: o doc pede "Reflection" (espelha tiro do jogador de volta) e  #
#  "Fractal Burst" (projetil que se divide no meio do caminho) -- nenhum dos #
#  dois existe no motor de projeteis hoje (precisaria de logica nova de      #
#  colisao/split em voo); substituidos por padroes ja existentes (spiral/    #
#  deathroll) em vez de ficar pela metade -- decisao registrada no plano.    #
# --------------------------------------------------------------------------- #

def crystal_phases():
    return [
        dict(hp_frac=1.0, patterns=['barrage', 'fan'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.66, patterns=['barrage', 'fan', 'spiral'], cd_mul=1.0, moves=['orbit']),
        # "nao acelera, fica mais precisa" -- cd_mul quase intocado de proposito
        # (os outros chefes cortam pra 0.5-0.75; este so ganha 1 padrao a mais).
        # radial_wall e literalmente isso: mais denso, mais LENTO (issue #104).
        dict(hp_frac=0.33, patterns=['fan', 'spiral', 'radial_wall'], cd_mul=0.85, moves=['orbit']),
    ]


# --------------------------------------------------------------------------- #
#  Terror Alado (endless, tier5+): um voador. `flying=True` (via boss_attrs)  #
#  faz collision._samples pular ele -- paira sem ser empurrado, mas continua  #
#  atingivel por hit_test. Sadico, cacador aereo: mergulha e mira onde voce   #
#  VAI estar.                                                                 #
# --------------------------------------------------------------------------- #

def wasp_phases():
    return [
        dict(hp_frac=1.0, patterns=['charge', 'fan'], cd_mul=0.9, moves=['orbit']),
        dict(hp_frac=0.6, patterns=['charge', 'fan', 'barrage'], cd_mul=0.85, moves=['orbit']),
        # 'mergulha e mira onde voce VAI estar': lead_fan e o mesmo lead do
        # barrage aberto em leque -- so dials (issue #104)
        dict(hp_frac=0.3, patterns=['charge', 'barrage', 'lead_fan'], cd_mul=0.6, moves=['orbit']),
    ]


# --------------------------------------------------------------------------- #
#  Olho-Sismico (B9, tier 5): "O Observador" -- nao se move, so observa. Fase   #
#  1 vigia; fase 2 acrescenta seismic_pulse (=shockwave); fase 3 troca para o   #
#  bullet_hell. O olho pisca (mecanica unica) via eye_setup/eye_blink_tick.     #
# --------------------------------------------------------------------------- #

def eye_phases():
    return [
        # Olho-Sismico: hovers. The mood_speed already drops to 0.2-0.3 in
        # the calm/agitated states, so even an orbit reads as an observer;
        # 'hover' is the explicit signal that the body should not seek
        # distance -- the position is the threat, the pose is the tell.
        dict(hp_frac=1.0, patterns=['gaze', 'tentacle_swipe', 'spawn_orb'], cd_mul=1.0, moves=['hover']),
        # 66%: mantem gaze+spawn_orb, adiciona shockwave (=seismic_pulse) -- 2 mudancas
        dict(hp_frac=0.66, patterns=['gaze', 'spawn_orb', 'shockwave'], cd_mul=0.9, moves=['hover']),
        # 33%: mantem shockwave, adiciona bullet_hell + gaze simultaneo -- 2 mudancas
        dict(hp_frac=0.33, patterns=['gaze', 'shockwave', 'bullet_hell'], cd_mul=0.7, moves=['hover']),
    ]


def eye_on_phase(boss, phase_i):
    """A cada fase o olho pisca mais rapido (entediado -> constante). O <33% e um
    flip abrupto, nao uma rampa -- ver eye_personality (enraged salta o mood_speed)."""
    boss.blink_interval = C.EYE_BLINK_INTERVAL[min(phase_i, len(C.EYE_BLINK_INTERVAL) - 1)]


def eye_blink_tick(boss, dt, game):
    """Per-frame eye state (registered in champion_ticks by eye_setup -- that list
    is just 'the (self, dt, game) hooks run every frame'). Advances the random
    blink (2-5s apart, 0.1s long); while blinking the eye is shielded: it can't
    be crit (hit_test -> 'body') and takes 75% less (dmg_taken_mult). Also points
    the pupil spring at the player so the iris tracks it with lag."""
    b = boss
    if b._blink_t > 0:
        b._blink_t -= dt
        blinking = b._blink_t > 0
    else:
        b._blink_cd -= dt
        if b._blink_cd <= 0:
            lo, hi = b.blink_interval
            b._blink_cd = random.uniform(lo, hi)
            b._blink_t = C.EYE_BLINK_DUR
            blinking = True
        else:
            blinking = False
    b.eye_shielded = blinking
    b.dmg_taken_mult = C.EYE_BLINK_DMG_MULT if blinking else 1.0
    p = game.nearest_player(b.pos)
    if p is not None:                    # iris follows the player (via the pupil spring)
        b.aggro = p
        b.aggro_t = 1.0


def eye_setup(boss):
    """Wire the eye's blink state + register its per-frame tick. Called once at
    spawn (BOSS_POOL 'setup' hook)."""
    boss.blink_interval = C.EYE_BLINK_INTERVAL[0]
    boss._blink_cd = random.uniform(*boss.blink_interval)
    boss._blink_t = 0.0
    boss.eye_shielded = False
    boss.dmg_taken_mult = 1.0
    boss.champion_ticks.append(eye_blink_tick)


# --------------------------------------------------------------------------- #
#  A Muralha (B10, tier 6): plan='fixed', arena corridor                      #
# --------------------------------------------------------------------------- #

def muralha_phases():
    """3 fases (66/33). Fase 1: fire_breath, hand_slam, eye_laser.
    Fase 2: + bouncing_bullets, fire_breath mais frequente.
    Fase 3: + grid_of_fire, fire_breath+hand_slam simultaneos.

    ``moves=[]`` because A Muralha is ``plan='fixed'`` and ``speed=0``.
    The slot is declared so the FSM's precedence chain can short-circuit
    on the empty list and the framework doesn't special-case the wall.
    """
    return [
        dict(hp_frac=1.0, patterns=['fire_breath', 'hand_slam', 'eye_laser'], cd_mul=1.0, moves=[]),
        dict(hp_frac=0.66, patterns=['fire_breath', 'hand_slam', 'eye_laser', 'bouncing_bullets'], cd_mul=0.85, moves=[]),
        dict(hp_frac=0.33, patterns=['fire_breath', 'hand_slam', 'eye_laser', 'bouncing_bullets', 'grid_of_fire'], cd_mul=0.7, moves=[]),
    ]


# --------------------------------------------------------------------------- #
#  ANKH (B11, tier 7): "A Eterna" -- 4 phases, each the memory of a boss you    #
#  already beat. It is the penultimate fight, NOT the climax: the Primordial    #
#  is still the run's final boss.                                              #
# --------------------------------------------------------------------------- #

def ankh_phases():
    """4 fases (75/50/25) -- a excecao a regra das 3, porque a estrutura E a
    ideia: cada fase revive um chefe anterior, entao sao 3 memorias + a forma
    propria dela.

    Fase 1 = O Cacador (memoria do Rei Lagarto: investida e bote).
    Fase 2 = O Tanque (memoria da Mae-Escaravelho: area e ninhada).
    Fase 3 = O Tentaculo (memoria do Kraken-Mor: puxao e chuva de bracos).
    Fase 4 = A Eterna: tudo junto, ritmo de bullet hell.

    Todos os patterns ja existem -- e o ponto do chefe. ANKH nao traz ataque
    novo nenhum: ela devolve os que voce ja aprendeu a ler, sobrepostos.
    """
    return [
        dict(hp_frac=1.00, patterns=['charge', 'pincha', 'swipe'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.75, patterns=['radial', 'shockwave', 'summon'], cd_mul=0.95, moves=['orbit']),
        dict(hp_frac=0.50, patterns=['grapple', 'arms_rain', 'spiral'], cd_mul=0.85, moves=['orbit']),
        dict(hp_frac=0.25,
             patterns=['charge', 'radial', 'grapple', 'bullet_hell', 'spiral'],
             cd_mul=0.6, moves=['orbit']),
    ]


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


# --------------------------------------------------------------------------- #
#  Phase kits: which patterns are live at each HP threshold                    #
# --------------------------------------------------------------------------- #

def default_phases():
    """A generic 3-phase kit any boss body can use. Phase 2 adds 'summon' (one
    new thing); phase 3 adds 'barrage' and hands out shorter cooldowns (the
    other thing) -- never more than two changes per threshold."""
    return [
        dict(hp_frac=1.0, patterns=['radial', 'fan'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.66, patterns=['radial', 'fan', 'summon'], cd_mul=1.0, moves=['orbit']),
        dict(hp_frac=0.33, patterns=['fan', 'barrage', 'summon'], cd_mul=0.75, moves=['orbit']),
    ]
