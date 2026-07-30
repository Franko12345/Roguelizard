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
    # Per-attack ``move=`` binding (issues #122/#123/#124/#125): the row
    # carries ONE movement signature, applied per-attack. Shared rows
    # pick the canonical (king's proud_walk for radial/fan/shockwave);
    # the wasp's barrage keeps curve_approach; the centipede's pincha
    # and the spider's summon/web_trap/web_dome/poison_bite each carry
    # their own. Per-pattern cd_jitter was the wasp's first attempt and
    # was superseded by per-phase cd_jitter (issue #125) -- removed.
    'radial': dict(fn=emitter.radial_burst, windup=C.BOSS_RADIAL_WINDUP,
                   telegraph='radial', move='proud_walk'),
    'fan': dict(fn=emitter.fan_shot, windup=C.BOSS_FAN_WINDUP, telegraph='fan',
                move='proud_walk'),
    'barrage': dict(fn=emitter.aimed_barrage, windup=C.BOSS_BARRAGE_WINDUP,
                    telegraph='line', move='curve_approach'),
    'summon': dict(fn=emitter.summon_adds, windup=C.BOSS_SUMMON_WINDUP, telegraph='horn',
                    # issue #125: summons while moving. Adds spawn at one position,
                    # she's already at another.
                    move='erratic_step'),
    'shockwave': dict(fn=emitter.shockwave, windup=C.BOSS_SHOCKWAVE_WINDUP,
                      telegraph='shockwave', move='proud_walk'),
    'pincha': dict(fn=emitter.pincha_bite, windup=C.BOSS_PINCHA_WINDUP, telegraph='line',
                   move='lunge'),       # issue #124: per-attack lunge on pincha
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
                     telegraph='rain', count=1, spread=60,
                     # issue #125: by-attack move = trap_and_shift. The trap fires
                     # where the boss stands; the move leaves that spot for the
                     # side with more free space.
                     move='trap_and_shift'),
    # Aranha-Rei's Web Dome: same web_trap fn/select, just more/bigger patches.
    # ``move='trap_and_shift'`` again -- the centroid of the 5 rain points is
    # the "trap" the boss leaves (it sits near the player), so the move drives
    # around the blockage to the open side.
    'web_dome': dict(fn=emitter.web_trap, select=emitter._select_arms_rain, windup=0.8,
                     telegraph='rain', count=5, spread=180, radius=70, life=9.0,
                     move='trap_and_shift'),
    # Aranha-Rei's poison bite: same pincha_bite, roots instead of poisoning
    # (the player has no poison status -- see pincha_bite's docstring). Bumped
    # 0.3 -> 0.7 for the 27-frame rule; the bite is still a bite, just with
    # the floor respected. ``move='erratic_step'`` keeps the nervous pacing even
    # during the lunge windup.
    'poison_bite': dict(fn=emitter.pincha_bite, windup=0.7, telegraph='line',
                        reach=1.6, dmg=15, slow=(0.5, 1.4),
                        move='erratic_step'),
    # deathroll: bumped 0.5 -> 0.7 so the floor holds in enraged. The dense
    # spiral still reads as "bullet hell" -- the windup is the same as the
    # basic spiral, but the SHOTS dial is what makes it dense. Issue #124:
    # the body spins through the air during fire (move='spin_glide' --
    # forward + perpendicular wobble, the spin being the bullet pattern).
    'deathroll': dict(fn=emitter.spiral_pattern, windup=0.7, telegraph='spiral',
                      shots=C.BOSS_DEATHROLL_SHOTS, turn=C.BOSS_DEATHROLL_TURN,
                      gap=C.BOSS_DEATHROLL_GAP, shot_speed=260, shot_dmg=12,
                      move='spin_glide'),
    # burrow has no `fn`/instant fire -- BossAI.tick special-cases `burrow=True`
    # and delegates every frame to the boss's OWN ai.burrow.tick (the
    # regular centipede's dig/erupt state machine, telegraphs included for
    # free -- AILizard.draw() already checks self.burrowed/burrow_state).
    # Issue #124: burrow IS the locomotion. The full surface -> dig -> under
    # -> erupt -> surface cycle drives the body's position every frame;
    # burrow vetoes the movement trail because its own state machine owns
    # motion. The `under` segment is also the invulnerability window
    # (hit_test -> None while burrowed), emergent from movement.
    'burrow': dict(fn=None, windup=0.05, telegraph=None, burrow=True),
    # same idea as burrow: no `fn`, BossAI.tick delegates every frame to the
    # octopus's own ai.grapple.tick (reach/root/snap+pull+slow, telegraph
    # included -- Lizard.draw already shows the arms converging via arm_target)
    'grapple': dict(fn=None, windup=0.05, telegraph=None, grapple=True),
    # Issue #124: spiral's body is the bullet pattern. move='spin_glide' =
    # forward + perpendicular wobble, so the spiral reads as fired from a
    # curving body instead of a stationary spinner.
    'spiral': dict(fn=emitter.spiral_pattern, windup=C.BOSS_SPIRAL_WINDUP, telegraph='spiral',
                   move='spin_glide'),
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
    # ``move='dive_arc'`` is the Wasp's per-attack binding (issue #122) --
    # the lead cone dives WHILE it leads. The row above is the Wasp's slot;
    # the binding here keeps the same identity shared if another boss picks
    # it up later (the move is a no-op for non-flyers since dive_arc only
    # fires during a dive windup).
    'lead_fan': dict(fn=emitter.fan_shot, windup=0.7, telegraph='fan',
                     count=5, spread=30, shot_speed=280, dmg=15, lead=0.6,
                     move='dive_arc'),
    # Issue #122: the Wasp's signature pattern. Same ``pincha_bite`` (contact
    # damage on the reach), but the windup IS the dive -- ``move='dive_arc'``
    # flies the boss THROUGH the target and out the other side, and the
    # ``dive_line`` telegraph draws the Bezier the boss is actually flying
    # (curve in the air + ground shadow at the exit point). Windup respects
    # the 27-frame floor (0.7s -- same as charge, the windup IS the action).
    'dive_arc': dict(fn=emitter.pincha_bite, windup=0.7, telegraph='dive_line',
                     move='dive_arc', reach=1.6, dmg=18),
}


def king_phases():
    """3 fases (66/33 -- doc's own thresholds for this boss). Fase 2 adds
    Radial Burst (1 thing); fase 3 swaps Fan for Spiral + faster cd (2 things).

    Issue #123: Rei Lagarto is the **first boss of the game** and the
    legibility canonical. His signature is "the most readable of the
    five" -- the simplest movement (``proud_walk``, a committed walk that
    never retreats), the longest windups (see ``BOSS_FAN_WINDUP`` /
    ``BOSS_SHOCKWAVE_WINDUP`` / ``BOSS_RADIAL_WINDUP`` / ``BOSS_CHARGE_WINDUP``
    bumped in config), and the loosest rhythm of the pool -- the player's
    first encounter with cadence still has breath.

    Issue #162: fase 1 stays canonical (1.0 / untouched pattern dials);
    fases 2 + 3 graduate density + cadence UP without touching windups.
    The 27-frame rule still owns every telegraph -- the boss gets denser
    (count / shots) and faster (cd_mul), not faster tells. The ``cd_mul``
    ladder moves from 1.0 / 0.95 / 0.85 to 1.0 / 0.80 / 0.65; the
    per-pattern dials are bumped on phase 2 (fan=3 / radial=10) and
    phase 3 (spiral denser); the windups stay where #123 put them.

    The ``moves=['proud_walk']`` slot is the BACKGROUND between attacks;
    the per-attack ``move='proud_walk'`` (fan / shockwave / radial) keeps
    the boss walking through the windup so the player reads the
    direction the fight is going. Charge vetoes (its own dash owns the
    motion).

    Explicit and on purpose: Rei Lagarto has no authored invulnerability
    window. The authored slot of this boss lot is A Muralha's (#121);
    the Centopeiadeira's (#124) is emergent from ``burrow``. The first
    boss of the game doesn't teach "sometimes shooting doesn't work" --
    that's the second lesson, not the first.

    The ``pattern_dials`` slot is the phase-local override on top of the
    shared ``PATTERNS`` rows. ``BossAI`` merges the row + the override
    once, at pattern pick time, and every FSM read goes through the
    merged dict (the windup, the select, the fire call, the move
    binding) so count / spread / shots / turn / gap never drift between
    what the telegraph draws and what fires at fire time.
    """
    return [
        # Phase 1 -- legibility canonical. No overrides; the row IS the dial.
        dict(hp_frac=1.0,  patterns=['fan', 'shockwave', 'charge'],
             cd_mul=1.0,  moves=['proud_walk']),
        # Phase 2 -- count UP, cadence UP, windups untouched (#162).
        dict(hp_frac=0.66, patterns=['fan', 'shockwave', 'charge', 'radial'],
             cd_mul=0.80,
             pattern_dials={
                 'fan': dict(count=3, spread=24, dmg=8),
                 'radial': dict(count=10),
             },
             moves=['proud_walk']),
        # Phase 3 -- swap fan for spiral, dial the spiral denser, cadence UP.
        dict(hp_frac=0.33, patterns=['spiral', 'shockwave', 'charge', 'radial'],
             cd_mul=0.65,
             pattern_dials={
                 'radial': dict(count=10),
                 'spiral': dict(shots=20, turn=18, gap=0.04),
             },
             moves=['proud_walk']),
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


def centipede_on_phase(boss, phase_i, game=None):
    """Perde segmentos + acelera a cada transição (armadura quebra ao vivo,
    mesmo padrão de `champions.py`): menos corpo, mais velocidade, mais caos --
    e MENOS hitbox de corpo, então o jogador troca "mais perigoso" por "mais
    fácil de acertar em cheio", a decisão que o doc descreve.

    The ``game`` arg is reserved for the post-#121 callback contract
    (some on_phase calls reapply the arena). Older callers that still
    pass only two args are tolerated in the FSM via TypeError fallback.
    """
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
    """3 fases. Phase 1 learns the nervousness + the area-denial rhythm;
    phase 2 adds ``web_dome`` and tightens the cd; phase 3 swaps the
    commitment patterns (charge -> poison_bite) while keeping the
    irregular cd jitter at the same wide band.

    Per-phase ``moves`` is ``[erratic_step, trap_and_shift]`` -- the
    pair emitted by the issue's "movement **by attack**" framing: a
    short, frequent re-roll keeps the body moving between attacks,
    and ``trap_and_shift`` takes over when a web is being placed
    (see PATTERNS['web_trap']['move'] / 'web_dome' below). The two
    moves walk a single precedence chain -- one active at a time,
    whichever the FSM has higher precedence for.

    ``cd_jitter`` (#125) widens the inter-attack interval above the
    floor by drawing from [floor, floor + BOSS_CD_MAX * cd_mul] and
    multiplying by ``uniform(1 - jitter, 1 + jitter)``. A jitter of
    1.0 puts the per-roll cd across roughly [~0.15, ~0.40] s on phase
    1 and a tighter band on phase 3 -- the variance stays a clear
    first in ``BOSS_POOL``, which is the issue's "least predictable"
    promise. Tighter than A Muralha's relentless floor, looser than
    the Wasp's planned curves.
    """
    return [
        dict(hp_frac=1.0, patterns=['charge', 'web_trap', 'summon'],
             cd_mul=1.0, cd_jitter=1.0,
             moves=['erratic_step', 'trap_and_shift']),
        dict(hp_frac=0.6, patterns=['charge', 'web_trap', 'summon', 'web_dome'],
             cd_mul=0.85, cd_jitter=1.0,
             moves=['erratic_step', 'trap_and_shift']),
        dict(hp_frac=0.3, patterns=['poison_bite', 'web_trap', 'summon', 'web_dome'],
             cd_mul=0.6, cd_jitter=1.0,
             moves=['erratic_step', 'trap_and_shift']),
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
    """Terror Alado (B8, endless, tier 5+).

    Issue #122: ``moves`` is the by-phase binding the Wasp lives on. Three
    distinct shapes, each a phase:

    - **Phase 1 (calm)**: ``['curve_approach','climb_out']`` -- the wasp
      dips in and pulls back. A hunting rhythm, not a tower. Short burst
      followed by longer pause reads as hunting; uniform spacing reads as
      a metronome.
    - **Phase 2 (agitated)**: ``['dive_arc']`` -- dives start appearing.
      ``dive_arc`` only animates while its pattern is on; outside that
      windup the move returns zero and the FSM falls through to
      ``reposition`` (the default), which keeps the wasp approaching when
      no dive is in flight.
    - **Phase 3 (enraged)**: ``['dive_arc','flyby']`` -- the wasp becomes
      a hunter. ``dive_arc`` fires during its pattern's windup; between
      dives, ``flyby`` keeps it curving toward you.

    ``dive_arc`` is also added as a phase-3 pattern -- the dive is the
    Wasp's signature move, it appears in the pattern list at the same HP
    threshold as the movement kit that animates it.

    The Wasp owns the open world (no arena, see ``docs/concepts/boss.md``),
    so the dive and flyby are free to cross the whole 3200x3200 map.
    ``Lizard.integrate`` clamps to the world bounds; nothing caged or
    caged-out, just bounded.
    """
    return [
        dict(hp_frac=1.0, patterns=['charge', 'fan'], cd_mul=0.9,
             moves=['curve_approach', 'climb_out']),
        dict(hp_frac=0.6, patterns=['charge', 'fan', 'barrage'], cd_mul=0.85,
             moves=['dive_arc']),
        # 'mergulha e mira onde voce VAI estar': lead_fan e o mesmo lead do
        # barrage aberto em leque -- so dials (issue #104). Phase 3 adds
        # dive_arc as a pattern (the Wasp's signature -- the dive is the
        # movement, and the dive is the attack). The move kit couples
        # dive_arc (during its windup) with flyby (between dives).
        dict(hp_frac=0.3, patterns=['charge', 'barrage', 'lead_fan', 'dive_arc'],
             cd_mul=0.6, moves=['dive_arc', 'flyby']),
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


def eye_on_phase(boss, phase_i, game=None):
    """A cada fase o olho pisca mais rapido (entediado -> constante). O <33% e um
    flip abrupto, nao uma rampa -- ver eye_personality (enraged salta o mood_speed).

    The ``game`` arg is reserved for the post-#121 callback contract.
    """
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

    Issue #121: every ``cd_mul`` sits at 1.0 -- the wall NEVER has more
    breath than the global ``BOSS_CD_FLOOR`` (0.15s). Phase 1 0.85 ->
    1.0 and phase 2 0.7 -> 1.0 tighten the rhythm: "voce nao passa"
    reads as relentless across all three phases, not just the last
    one. No boss in BOSS_POOL ships with a smaller cd_mul than her
    (smaller cd_mul is meaningless at the floor; what matters is that
    she has the highest FLOOR, i.e. the LEAST breath, which means she
    hugs the floor at every phase).
    """
    return [
        dict(hp_frac=1.0, patterns=['fire_breath', 'hand_slam', 'eye_laser'], cd_mul=1.0, moves=[]),
        dict(hp_frac=0.66, patterns=['fire_breath', 'hand_slam', 'eye_laser', 'bouncing_bullets'], cd_mul=1.0, moves=[]),
        dict(hp_frac=0.33, patterns=['fire_breath', 'hand_slam', 'eye_laser', 'bouncing_bullets', 'grid_of_fire'], cd_mul=1.0, moves=[]),
    ]


def muralha_on_phase(boss, phase_i, game=None):
    """Issue #121: each phase NARROWS the arena. The wall closes in.

    The boss is plan='fixed' and never moves, so the centre never
    shifts -- only the (w, h) of the box changes. The arena still
    re-applies itself every phase transition (not just at spawn), so a
    grid_of_fire targeting ``game.arena_bounds`` fills the new box,
    not the old one.

    Game is required for the re-apply; the FSM's TypeError fallback
    handles the case where an older test or runner calls the 2-arg
    legacy form (regression test stays green).
    """
    if game is None:
        return                          # legacy 2-arg caller -- nothing to shrink
    from . import arena as arena_mod
    a = arena_mod.ARENAS.get('muralha')
    if a is not None:
        a.apply(game, boss.pos, phase_i=phase_i)


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
