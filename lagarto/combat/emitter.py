"""The attack-pattern emitter: one implementation of every shot arrangement,
usable by ANY creature -- boss or common enemy.

A pattern is a plain function ``(shooter, game, target, dials) -> None`` that
spawns Projectiles through the existing ``game.spawn_projectile`` pipeline.
``dials`` is the caller's tuning dict (``PATTERNS[pid]`` for a boss, a species
entry for a common enemy) -- the patterns never look their own dials up, which
is what lets a plain ``AILizard`` fire a spiral without a ``boss_ai``.

Everything a pattern touches on the shooter, any creature already has:
``spine.joints[0]`` (the mouth), ``color``, ``pos``, ``max_r``, and itself as a
place to park continuous-pattern state (``_spiral_left``, ``_barrage_left``,
``_breath_left`` -- the same idiom the boss used, now creature-agnostic).

Continuous patterns come in pairs: a starter that arms the state and a
``_tick_*`` the owner's per-frame tick must call (it reads ``game.dt_last``).

See ``docs/adr/0012-shared-pattern-emitter.md``; the boss-side dial table lives
in ``lagarto.flow.boss.patterns``.
"""

import random
from pygame import Vector2

from ..audio import engine as audio
from ..core import config as C
from ..core import palette
from ..core.mathutil import safe_norm, vfrom_angle, random_dir, angle_of
from .projectile import spit as game_spit, bounce, leave_puddle, arc as arc_hook


def _launch(pr, game, dials):
    """Fire one shot, wearing the pattern's ONE movement modifier.

    ``dials['mod']`` is a plain ``on_update`` hook (``projectile.homing`` /
    ``projectile.bounce``), which is what lets a "new" boss pattern be a row of
    dials instead of a new function. One and no more: the player is the only
    side that stacks modifiers (see ``docs/concepts/projectile.md``).
    """
    mod = dials.get('mod')
    if mod is not None:
        pr.bounces_left = dials.get('bounces', 0)
        pr.bounce_damp = dials.get('bounce_damp', 0.8)
        pr.on_update.append(mod)
    game.spawn_projectile(pr)


def lead_point(shooter, target, dials):
    """Where the target WILL be when the shot arrives -- the single lead formula.

    Shared by the boss's barrage and the ANTECIPADOR's on-ground telegraph, so
    the marker the player reads cannot drift away from where the shots go.

    The lead time is the shot's FLIGHT time, not a constant. It used to be a
    fixed number of seconds, which meant the aim was only correct at the one
    distance where ``dist / shot_speed`` happened to equal that constant --
    measured, the ANTECIPADOR missed a straight-line runner by 44 px at 150 px
    of range and by 172 px at 450, against a 21 px body. The error grew with
    distance because the flight time did and the lead did not.

    ``lead`` is now how GOOD the prediction is, in [0, 1]: 1.0 leads perfectly,
    0.6 leads 60% of the way and can be beaten by holding a straight line. One
    refinement pass, because the first estimate uses the distance to where the
    target is standing rather than to where it is going.
    """
    quality = dials.get('lead', C.BOSS_BARRAGE_LEAD)
    speed = dials.get('shot_speed', C.BOSS_BARRAGE_SPEED)
    if speed <= 0:
        return Vector2(target.pos)
    origin = shooter.spine.joints[0]
    t = target.pos.distance_to(origin) / speed
    t = (target.pos + target.vel * t).distance_to(origin) / speed
    return target.pos + target.vel * (t * quality)


def radial_burst(shooter, game, target, dials):
    """A full ring of shots, all at once -- the "get away from me" pattern."""
    mouth = shooter.spine.joints[0]
    n = dials.get('count', C.BOSS_RADIAL_COUNT)
    for i in range(n):
        ang = (360.0 / n) * i
        aim = mouth + vfrom_angle(ang, 100)
        pr = game_spit(mouth, aim, shooter.color, dmg=dials.get('dmg', C.BOSS_RADIAL_DMG),
                       effect=None, speed=dials.get('shot_speed', C.BOSS_RADIAL_SPEED),
                       radius=dials.get('radius', 8))
        _launch(pr, game, dials)
    game.fx.ring(shooter.pos, shooter.color)
    game.fx.spark_burst(mouth, palette.lighten(shooter.color, 0.3), 16, 260)
    audio.play('w_spit', 0.5)


def fan_shot(shooter, game, target, dials):
    """A cone of shots toward the player -- dodge sideways, not backward.
    Dials come from the caller (Primordial's Massive Fan reuses this with a
    wider/denser dial set instead of new code; the CUSPIDOR and the
    METRALHADOR reuse it with ``count=1``)."""
    mouth = shooter.spine.joints[0]
    n = dials.get('count', C.BOSS_FAN_COUNT)
    spread = dials.get('spread', C.BOSS_FAN_SPREAD)
    jitter = dials.get('jitter', 0.0)
    aim_at = lead_point(shooter, target, dials) if 'lead' in dials else target.pos
    base = safe_norm(aim_at - mouth)
    if jitter:                       # the gunner's dispersion: aim, not arrangement
        base = base.rotate(random.uniform(-jitter, jitter))
    for i in range(n):
        # a one-shot fan goes down the MIDDLE (it used to leave at -spread/2,
        # which only never showed because every boss fan had 5+ shots)
        t = 0.0 if n == 1 else (i / (n - 1)) - 0.5     # -0.5 .. 0.5
        aim = mouth + base.rotate(t * spread) * 100
        pr = game_spit(mouth, aim, shooter.color, dmg=dials.get('dmg', C.BOSS_FAN_DMG),
                       effect=None, speed=dials.get('shot_speed', C.BOSS_FAN_SPEED),
                       radius=dials.get('radius', 8))
        _launch(pr, game, dials)
    game.fx.spark_burst(mouth, shooter.color, 10, 240)
    audio.play('w_spit', 0.45)


def lob_shot(shooter, game, target, dials):
    """A shot that LANDS on the aim point and leaves its payload there.

    The ENVENENADOR's spit: ``life`` is cut to the travel time so the puddle is
    dropped where the telegraph pointed instead of flying past, and the payload
    rides ``on_death`` (see ``docs/concepts/projectile.md``). Area denial, not a
    hit -- what it punishes is standing still.
    """
    mouth = shooter.spine.joints[0]
    # `at` lands it on a point the caller already committed to -- the MORTEIRO's
    # marked patch -- instead of chasing the player. Without it the telegraph on
    # the ground and the thing in the air would disagree.
    land = dials.get('at') or target.pos
    flight = dials.get('flight')
    dist = mouth.distance_to(land)
    # `flight` pins the travel TIME instead of the speed, so a lob always takes
    # the same beat to land however far it was thrown -- which is what lets the
    # footprint's countdown and the shot's arrival be the same clock.
    speed = (dist / flight) if flight else dials.get('shot_speed', C.VENOM_SPIT_SPEED)
    pr = game_spit(mouth, land, shooter.color, dmg=dials.get('dmg', C.VENOM_SPIT_DMG),
                   effect=dials.get('effect', 'poison'), speed=max(1.0, speed),
                   radius=dials.get('radius', 7))
    travel = dist / max(1.0, speed)
    pr.life = max(0.12, min(travel, 2.6))
    payload = dials.get('puddle')
    if payload:
        pr.on_death.append(leave_puddle(**payload))
    height = dials.get('arc')
    if height:
        pr.on_update.append(arc_hook(height))
    _launch(pr, game, dials)
    game.fx.spark_burst(mouth, palette.lighten(shooter.color, 0.3), 6, 190)
    audio.play('w_spit', 0.4)


def aimed_barrage(shooter, game, target, dials):
    """A few shots aimed with lead at where the player is HEADING.

    Dials come from the caller: the ANTECIPADOR reuses this exact function with
    a longer lead and a shorter burst instead of a second implementation of
    "shoot where they are going".
    """
    shooter._barrage_left = dials.get('shots', C.BOSS_BARRAGE_SHOTS)
    shooter._barrage_aim = lead_point(shooter, target, dials)
    shooter._barrage_cd = 0.0
    shooter._barrage_gap = dials.get('gap', C.BOSS_BARRAGE_GAP)
    shooter._barrage_speed = dials.get('shot_speed', C.BOSS_BARRAGE_SPEED)
    shooter._barrage_dmg = dials.get('dmg', C.BOSS_BARRAGE_DMG)
    shooter._barrage_radius = dials.get('radius', 7)


def _tick_barrage(shooter, game):
    """Called every frame while a barrage is in flight (set by aimed_barrage)."""
    if getattr(shooter, '_barrage_left', 0) <= 0:
        return
    shooter._barrage_cd -= game.dt_last
    if shooter._barrage_cd > 0:
        return
    shooter._barrage_left -= 1
    shooter._barrage_cd = shooter._barrage_gap
    mouth = shooter.spine.joints[0]
    pr = game_spit(mouth, shooter._barrage_aim, shooter.color, dmg=shooter._barrage_dmg,
                   effect=None, speed=shooter._barrage_speed,
                   radius=shooter._barrage_radius)
    game.spawn_projectile(pr)
    game.fx.spark_burst(mouth, shooter.color, 5, 200)
    audio.play('w_spit', 0.35)


def summon_adds(shooter, game, target, dials):
    """Call in reinforcements from the round's own theme pool (a real cost:
    it spends a window where the shooter does nothing else, and the adds count
    against the round's cap like anything else)."""
    from ..creatures import species
    from ..flow import rounds as roundslib
    pool = roundslib.THEMES.get(game.rounds.theme, {}).get('pool', species.ENEMY_SPECIES)
    for _ in range(C.BOSS_SUMMON_COUNT):
        key = random.choice(pool)
        pos = shooter.pos + random_dir(shooter.max_r * 1.6)
        e = species.make(key, pos)
        game.spawn_enemy(e)
        game.fx.ring(pos, shooter.color)
    game.fx.spark_burst(shooter.pos, palette.lighten(shooter.color, 0.4), 20, 300)
    audio.play('nest', 0.6)


def shockwave(shooter, game, target, dials):
    """Instant AoE centred on the shooter -- no projectile, just a ring of hurt.
    Tail-slam-style attacks (Rei Lagarto) use this: the telegraph already drew
    the exact radius, so at fire time it's a plain distance check."""
    for p in game.players:
        if p.dead or p.down:
            continue
        if p.pos.distance_to(shooter.pos) < C.BOSS_SHOCKWAVE_RADIUS + p.max_r * 0.4:
            p.hurt(game, safe_norm(p.pos - shooter.pos), C.BOSS_SHOCKWAVE_DMG)
    game.fx.ring(shooter.pos, shooter.color)
    game.fx.ring(shooter.pos, palette.lighten(shooter.color, 0.3))
    game.shake(8)
    audio.play('hit', 0.5)


def spiral_pattern(shooter, game, target, dials):
    """Kick off a rotating spray -- ticked per-frame by ``_tick_spiral`` like
    ``aimed_barrage``/``_tick_barrage``, so the spiral keeps turning while the
    shooter is free to do anything else (it's not a blocking loop).

    Dials come from the CALLER, not hardcoded config: ``deathroll`` reuses this
    exact function with a denser/faster dial set instead of duplicating the tick
    logic -- "boss is data" applies to variants of one pattern too.
    """
    shooter._spiral_left = dials.get('shots', C.BOSS_SPIRAL_SHOTS)
    shooter._spiral_ang = random.uniform(0, 360)
    shooter._spiral_cd = 0.0
    shooter._spiral_turn = dials.get('turn', C.BOSS_SPIRAL_TURN)
    shooter._spiral_gap = dials.get('gap', C.BOSS_SPIRAL_GAP)
    shooter._spiral_speed = dials.get('shot_speed', C.BOSS_SPIRAL_SPEED)
    shooter._spiral_dmg = dials.get('shot_dmg', C.BOSS_SPIRAL_DMG)


def _tick_spiral(shooter, game):
    if getattr(shooter, '_spiral_left', 0) <= 0:
        return
    shooter._spiral_cd -= game.dt_last
    if shooter._spiral_cd > 0:
        return
    shooter._spiral_left -= 1
    shooter._spiral_cd = shooter._spiral_gap
    mouth = shooter.spine.joints[0]
    aim = mouth + vfrom_angle(shooter._spiral_ang, 100)
    shooter._spiral_ang = (shooter._spiral_ang + shooter._spiral_turn) % 360
    pr = game_spit(mouth, aim, shooter.color, dmg=shooter._spiral_dmg,
                   effect=None, speed=shooter._spiral_speed, radius=7)
    game.spawn_projectile(pr)


def charge_attack(shooter, game, target, dials):
    """Not an instant fire -- it only aims. The owner's FSM is what turns the
    shooter itself into the hazard for a beat (see ``BossAI.tick``'s 'charging'
    state), Gurdy-Jr/Chub style."""
    shooter._charge_dir = safe_norm(target.pos - shooter.pos)


def pincha_bite(shooter, game, target, dials):
    """Quick short-range strike -- fast windup, no projectile, just a contact
    check at the reach the telegraph line showed. Dials come from the caller
    (default = Centopeiadeira's pincers); Kraken-Mor's tentacle swipe reuses
    this exact function with a longer reach, Aranha-Rei's poison bite with an
    optional `slow` (the player has no poison status to apply, so it
    substitutes the same "landed bite roots you" idea every sting in this
    game already uses) -- instead of new code either time."""
    reach = shooter.max_r * dials.get('reach', C.BOSS_PINCHA_REACH)
    dmg = dials.get('dmg', C.BOSS_PINCHA_DMG)
    if target.pos.distance_to(shooter.pos) < reach:
        landed = target.hurt(game, safe_norm(target.pos - shooter.pos), dmg)
        slow = dials.get('slow')
        if landed and slow:
            target.apply_slow(*slow)
        game.fx.spark_burst(shooter.spine.joints[0], shooter.color, 10, 260)
        game.shake(4)


def _select_arms_rain(shooter, game, target, dials):
    """Picks the slam points at WINDUP START (not fire time), so the
    telegraph can show them as growing circles for the whole windup -- called
    once by the FSM via the pattern's ``select`` hook (see ``BossAI.tick``).
    Dials from the caller: Primordial's Sky Slam reuses this with
    ``count=1, spread=0`` (a single point pinned on the target = a giant
    shadow, not a cluster) instead of new selection code."""
    n = dials.get('count', C.BOSS_ARMS_RAIN_COUNT)
    spread = dials.get('spread', C.BOSS_ARMS_RAIN_SPREAD)
    shooter._rain_points = [Vector2(target.pos) + random_dir(random.uniform(0, spread))
                            for _ in range(n)]


def arms_rain(shooter, game, target, dials):
    """Fires at windup end -- damages wherever ``_select_arms_rain`` marked."""
    radius = dials.get('radius', C.BOSS_ARMS_RAIN_RADIUS)
    dmg = dials.get('dmg', C.BOSS_ARMS_RAIN_DMG)
    for pt in getattr(shooter, '_rain_points', []):
        for p in game.players:
            if p.dead or p.down:
                continue
            if p.pos.distance_to(pt) < radius + p.max_r * 0.4:
                p.hurt(game, safe_norm(p.pos - pt), dmg)
        game.fx.ring(pt, shooter.color)
        game.fx.burst(pt, palette.lighten(shooter.color, 0.3), 14, 260)
    shooter._rain_points = []
    game.shake(6)
    audio.play('hit', 0.4)


def sky_slam(shooter, game, target, dials):
    """Primordial: the same single-point slam as ``arms_rain`` (the dials set
    count=1) plus a lingering magma puddle where it lands -- 'Sky Slam' and
    'Magma Spit' folded into one attack instead of two separate ones."""
    from . import weapons
    pts = list(getattr(shooter, '_rain_points', []))
    arms_rain(shooter, game, target, dials)
    for pt in pts:
        game.spawn_puddle(weapons.Puddle(pt, C.BOSS_SKY_SLAM_PUDDLE_R,
                                         C.BOSS_SKY_SLAM_PUDDLE_DMG,
                                         C.BOSS_SKY_SLAM_PUDDLE_LIFE, 18,
                                         hostile=True, tick=0.5))


def web_trap(shooter, game, target, dials):
    """Mãe-Escaravelho's Web Trap: a patch that roots (heavy slow, tiny
    damage) instead of hurting -- reuses the single-point select from
    ``sky_slam``/``arms_rain`` and ``weapons.Puddle``'s ``slow=`` param
    (added for Rei Lagarto's scar) instead of new hazard code. Dials come
    from the caller -- Aranha-Rei's Web Dome reuses this exact function with
    more points and a bigger radius via ``arms_rain``'s ``count``/``spread``
    select, no new selection or hazard code either."""
    from . import weapons
    radius = dials.get('radius', C.BOSS_WEB_TRAP_R)
    dmg = dials.get('dmg', C.BOSS_WEB_TRAP_DMG)
    life = dials.get('life', C.BOSS_WEB_TRAP_LIFE)
    slow = dials.get('slow', C.BOSS_WEB_TRAP_SLOW)
    for pt in getattr(shooter, '_rain_points', []):
        game.spawn_puddle(weapons.Puddle(pt, radius, dmg, life, 200, hostile=True,
                                         tick=0.4, slow=(slow, 1.2)))
    shooter._rain_points = []
    game.fx.burst(shooter.pos, (240, 240, 250), 8, 140)


# --------------------------------------------------------------------------- #
#  Olho-Sismico's patterns: gaze/bullet_hell reuse the spiral tick;             #
#  tentacle_swipe reuses pincha_bite; seismic_pulse IS shockwave.               #
# --------------------------------------------------------------------------- #

def gaze(shooter, game, target, dials):
    """A slow sweeping beam from the iris. Reuses the spiral tick (a rotating
    stream of shots), just started ARC/2 *before* the player and turning slowly,
    so it reads as a laser sweeping ACROSS the player, not an omni spiral."""
    spiral_pattern(shooter, game, target, dials)   # sets up _spiral_* from the dials
    shooter._spiral_ang = angle_of(target.pos - shooter.spine.joints[0]) - dials.get('arc', 70) / 2


def spawn_orb(shooter, game, target, dials):
    """Spawns a few floating shooters around the eye. Reuses species.make +
    spawn_enemy: a ranged 'gunner' stands in for an orb (it hovers near the eye
    and streams shots) instead of a bespoke orb entity the engine doesn't have."""
    from ..creatures import species
    n = dials.get('count', C.EYE_ORB_COUNT)
    for _ in range(n):
        pos = shooter.pos + random_dir(shooter.max_r * 1.9)
        e = species.make('gunner', pos)
        game.spawn_enemy(e)
        game.fx.ring(pos, shooter.color)
    game.fx.spark_burst(shooter.spine.joints[0], palette.lighten(shooter.color, 0.4), 16, 280)
    audio.play('nest', 0.5)


# --------------------------------------------------------------------------- #
#  A Muralha's patterns: fire_breath, hand_slam, eye_laser, bouncing_bullets,   #
#  grid_of_fire.                                                               #
# --------------------------------------------------------------------------- #

def fire_breath(shooter, game, target, dials):
    """Continuous cone of fire from the mouth. Uses a per-frame tick like
    spiral_pattern. Telegrafo: mouth opens fully, red glow."""
    shooter._breath_left = dials.get('shots', C.MURALHA_BREATH_SHOTS)
    shooter._breath_cd = 0.0
    shooter._breath_gap = dials.get('gap', C.MURALHA_BREATH_GAP)
    shooter._breath_speed = dials.get('shot_speed', C.MURALHA_BREATH_SPEED)
    shooter._breath_dmg = dials.get('shot_dmg', C.MURALHA_BREATH_DMG)
    shooter._breath_spread = dials.get('spread', C.MURALHA_BREATH_SPREAD)
    # Set mouth to fully open for the attack
    shooter.mouth_open = 1.0


def _tick_fire_breath(shooter, game):
    if getattr(shooter, '_breath_left', 0) <= 0:
        return
    shooter._breath_cd -= game.dt_last
    if shooter._breath_cd > 0:
        return
    shooter._breath_left -= 1
    shooter._breath_cd = shooter._breath_gap
    mouth = shooter.spine.joints[0]
    # Fan of fire in fixed plan, mouth faces left (toward arena)
    base = Vector2(-1, 0)
    for i in range(3):  # 3 streams per tick
        t = (i / 2) - 0.5  # -0.5, 0, 0.5
        ang = base.rotate(t * shooter._breath_spread)
        aim = mouth + ang * 100
        pr = game_spit(mouth, aim, shooter.color, dmg=shooter._breath_dmg,
                       effect=None, speed=shooter._breath_speed, radius=10)
        game.spawn_projectile(pr)
    game.fx.spark_burst(mouth, (255, 120, 40), 8, 200)
    audio.play('w_spit', 0.3)


def hand_slam(shooter, game, target, dials):
    """Stone hand emerges from side and slams down. Telegrafo: glow on side."""
    # hand_slam uses the select hook to pre-pick the slam position
    if not getattr(shooter, '_hand_slam_pos', None):
        return
    pos = shooter._hand_slam_pos
    radius = dials.get('radius', C.MURALHA_HAND_RADIUS)
    dmg = dials.get('dmg', C.MURALHA_HAND_DMG)
    for p in game.players:
        if p.dead or p.down:
            continue
        if p.pos.distance_to(pos) < radius + p.max_r * 0.4:
            p.hurt(game, safe_norm(p.pos - pos), dmg)
    game.fx.ring(pos, shooter.color)
    game.fx.burst(pos, palette.lighten(shooter.color, 0.3), 20, 280)
    shooter._hand_slam_pos = None
    game.shake(8)
    audio.play('hit', 0.5)


def _select_hand_slam(shooter, game, target, dials):
    """Select slam position at windup start for telegraph."""
    # Hand comes from left or right side of wall
    side = random.choice([-1, 1])  # -1 = left hand, +1 = right hand
    # Spawn near the side of the wall, at player's Y
    hand_x = shooter.pos.x + side * shooter.max_r * 1.2
    hand_y = target.pos.y
    shooter._hand_slam_pos = Vector2(hand_x, hand_y)


def eye_laser(shooter, game, target, dials):
    """Multiple eyes fire simultaneous beams. Telegrafo: eyes glow."""
    mouth = shooter.spine.joints[0]
    n = dials.get('count', C.MURALHA_EYE_BEAMS)
    spread = dials.get('spread', C.MURALHA_EYE_SPREAD)
    # Eyes are along the wall - fire leftward toward player
    base = Vector2(-1, 0)
    for i in range(n):
        t = (i / max(1, n - 1)) - 0.5
        ang = base.rotate(t * spread)
        aim = mouth + ang * 150
        pr = game_spit(mouth, aim, shooter.color, dmg=dials.get('dmg', C.MURALHA_EYE_DMG),
                       effect=None, speed=dials.get('shot_speed', C.MURALHA_EYE_SPEED), radius=8)
        game.spawn_projectile(pr)
    game.fx.spark_burst(mouth, (255, 255, 100), 12, 260)
    audio.play('w_spit', 0.4)


def bouncing_bullets(shooter, game, target, dials):
    """Projectiles that ricochet off arena walls. Telegrafo: yellow glow at mouth."""
    mouth = shooter.spine.joints[0]
    n = dials.get('count', C.MURALHA_BOUNCE_COUNT)
    base = safe_norm(target.pos - mouth)
    for i in range(n):
        t = (i / max(1, n - 1)) - 0.5
        spread = dials.get('spread', C.MURALHA_BOUNCE_SPREAD)
        ang = base.rotate(t * spread)
        aim = mouth + ang * 100
        pr = game_spit(mouth, aim, shooter.color, dmg=dials.get('dmg', C.MURALHA_BOUNCE_DMG),
                       effect=None, speed=dials.get('shot_speed', C.MURALHA_BOUNCE_SPEED), radius=7)
        pr.bounces_left = dials.get('bounces', C.MURALHA_BOUNCE_BOUNCES)
        pr.bounce_damp = 0.8
        # ONE movement modifier and no more: enemy shots pick a verb, the player
        # is the only side that stacks them (see docs/concepts/projectile.md).
        pr.on_update.append(bounce)
        game.spawn_projectile(pr)
    game.fx.spark_burst(mouth, (255, 255, 80), 14, 240)
    audio.play('w_spit', 0.4)


def grid_of_fire(shooter, game, target, dials):
    """Grid of fire cells on the ground with small gaps. Creates Puddle hazards."""
    from . import weapons
    cell = dials.get('cell', C.MURALHA_GRID_CELL)
    dmg = dials.get('dmg', C.MURALHA_GRID_DMG)
    tick = dials.get('tick', C.MURALHA_GRID_TICK)
    life = dials.get('life', C.MURALHA_GRID_LIFE)
    # Arena is 700x500, wall on right. Grid covers left portion
    cols = 700 // cell
    rows = 500 // cell
    for cx in range(cols):
        for cy in range(rows):
            # Leave small gaps - skip some cells
            if (cx + cy) % 3 == 0:  # 1/3 are gaps
                continue
            x = cx * cell + cell // 2
            y = cy * cell + cell // 2
            pos = Vector2(x, y)
            game.spawn_puddle(weapons.Puddle(pos, cell * 0.45, dmg, life, 180,
                                             hostile=True, tick=tick))
    game.fx.burst(shooter.pos, (255, 80, 40), 30, 200)
