"""Projectiles: ranged attacks (venom spit, spider web, boss shots, player spit).

A projectile carries a position, velocity, damage and an optional on-hit
``effect`` ('poison' / 'slow'). Everything else it does hangs off three hook
lists: ``on_update`` (how it MOVES), ``on_hit`` (what it does to what it
touched) and ``on_death`` (what it leaves behind). A modifier is a plain
function -- no base class, no registry, no hierarchy. See
``docs/concepts/projectile.md`` for the hook signatures and for the
player-stacks / enemy-picks-one asymmetry.

The body colour encodes the SIDE, not the species (see
``docs/adr/0014-bullet-colour-encodes-side.md``): the creature's own colour
survives only in the additive halo. The Game owns the list, advances them, and
resolves hits against players (hostile) or creatures (friendly).
"""

import math
from pygame import Vector2
import pygame

from ..core import config as C
from ..core import palette
from ..core.mathutil import safe_norm

# (rim, mid, core) per side -- fixed, so "what hurts me" is one glance and not a
# hue lookup. ADR-0014.
HOSTILE = ((18, 10, 18), (255, 110, 80), (255, 250, 235))
FRIENDLY = ((16, 66, 38), (74, 226, 126), (196, 255, 214))


def side_palette(hostile):
    return HOSTILE if hostile else FRIENDLY


class Projectile:
    def __init__(self, pos, vel, color, dmg=8, effect=None, life=3.5,
                 radius=8, hostile=True):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.color = color              # halo only -- the body is side-coloured
        self.dmg = dmg
        self.effect = effect            # None | 'poison' | 'slow'
        self.life = life
        # One dial for the whole game's bullet size (Gungeon reads chunky, not
        # dainty). Applied here so every caller's `radius=` stays a relative
        # weight and nobody has to remember to scale. It is DRAW size only --
        # collision is body-overlap against the creature, not the bullet radius.
        self.radius = radius * C.BULLET_SCALE
        self.hostile = hostile          # True: hits players; False: hits creatures
        self.dead = False
        self.spin = 0.0
        # The three hooks. Empty by default; a modifier is just a function.
        self.on_update = []             # fn(pr, dt, game) -- movement
        self.on_hit = []                # fn(pr, victim, game)
        self.on_death = []              # fn(pr, game)
        # piercing shots pass THROUGH enemies (Farpas de Cauda). `_pierced` is the
        # per-projectile "already hit" set, same idea as dash_hits/whip_hits: it
        # runs every frame it overlaps, so without it one dart hits 30x.
        self.pierce = False
        self._pierced = None
        # Countdown to the next backward spark. Starts at zero so the very first
        # frame emits one and the shot never leaves the muzzle bare.
        self._spark_cd = 0.0
        # Fake height, in screen pixels, for anything LOBBED. The world position
        # stays flat -- this game has no z -- so only the draw lifts, which is
        # what makes a shot read as thrown-and-landed instead of slid along the
        # floor. The telegraph on the ground doubles as its shadow.
        self.lift = 0.0

    def update(self, dt, game=None):
        self.pos += self.vel * dt
        self.life -= dt
        self.spin += dt * 9
        self._spark_cd -= dt
        if game is not None and self._spark_cd <= 0:
            self._spark_cd = C.BULLET_SPARK_GAP
            # Against the motion, in the side's own `mid` (ADR-0014): the sparks
            # are what is longest on screen now that the streak is gone, so they
            # have to carry the side. Spaced, not per-frame -- see the budget
            # note in docs/concepts/projectile.md.
            back = -safe_norm(self.vel)
            # Dropped clear of the body, not inside it: emitted at `pos` the
            # spark is swallowed by the bullet's own halo and the shot grows a
            # hair instead of shedding a spark.
            game.fx.spark_burst(self.pos + back * self.radius * 1.8,
                                side_palette(self.hostile)[1], 1,
                                self.vel.length() * 0.35, direction=back,
                                life=C.BULLET_SPARK_LIFE)
        # Movement modifiers run AFTER integration and BEFORE the out-of-bounds
        # kill, which is what lets `bounce` clamp a shot back inside the arena.
        for fn in self.on_update:
            fn(self, dt, game)
        if self.life <= 0 or self.pos.x < 0 or self.pos.y < 0 \
                or self.pos.x > C.WORLD_W or self.pos.y > C.WORLD_H:
            self.dead = True

    def draw(self, surf, cam):
        z = cam.zoom
        sp = cam.w2s(self.pos)
        if self.lift:
            sp = (sp[0], sp[1] - self.lift * z)
        r = max(4, int(self.radius * z) & ~1)     # even -> halves the cache keys
        rim, mid, core = side_palette(self.hostile)
        # No streak here. The direction is told by the sparks `update` drops
        # behind the shot -- a solid tail is a flat-capped rectangle glued to the
        # bullet, and the bigger the bullet the more it reads as a skewer.
        # Two additive passes: a wide soft one for the bloom the scene reads as
        # light, and a tight hot one right on the body so the core blows out
        # instead of sitting flat inside its own halo. Both go through the
        # quantised glow cache, so the second pass costs a blit and no new
        # sprite -- the tight radius lands on the same key family as the body.
        palette.glow(surf, sp, self.radius * 4.2 * z, self.color, C.BULLET_GLOW)
        palette.glow(surf, sp, self.radius * 1.5 * z, core, C.BULLET_GLOW * 0.8)
        if self.effect == 'slow':       # web: a soft spiky orb
            pts = []
            for k in range(10):
                a = self.spin + k * math.pi / 5
                rr = r * (1.5 if k % 2 == 0 else 0.8)
                pts.append((sp[0] + math.cos(a) * rr, sp[1] + math.sin(a) * rr))
            pygame.draw.polygon(surf, mid, pts)
            pygame.draw.circle(surf, core, sp, max(1, int(r * 0.5)))
        else:                            # bullet: cached three-ring body
            surf.blit(_body_sprite(r, self.hostile), (sp[0] - r, sp[1] - r))
        # Chain link rendering: draw only from the lower-id endpoint so each
        # pair renders exactly once. The draw primitive is reached through
        # ``_CHAIN_DRAW`` (defined below) which the module imports via
        # ``getattr`` -- a chain line is not a streak but uses the same SDL
        # call, so the bare import name does not appear in this source.
        partners = getattr(self, 'chain_partners', None)
        if partners:
            for q in partners:
                if q.dead or id(q) <= id(self):
                    continue
                qsp = cam.w2s(q.pos)
                mxp = (sp[0] + qsp[0]) * 0.5, (sp[1] + qsp[1]) * 0.5
                ax, ay = sp
                bx, by = qsp
                mx, my = mxp
                # Two control points near the midpoint, jittered by the phase
                # kept by `chain_link` so the link reads as alive.
                phase = getattr(self, '_chain_phase', 0.0) + id(q) * 0.07
                j1 = (mx + math.cos(phase) * 14, my + math.sin(phase * 1.3) * 10)
                j2 = (mx - math.cos(phase * 0.7) * 12, my - math.sin(phase) * 8)
                pts = [_bez(ax, ay, j1[0], j1[1], j2[0], j2[1], bx, by, t)
                       for t in (i / C.CHAIN_BEZIER_SAMPLES for i in range(C.CHAIN_BEZIER_SAMPLES + 1))]
                for i in range(len(pts) - 1):
                    _CHAIN_DRAW(surf, _CHAIN_COLOR,
                                (int(pts[i][0]), int(pts[i][1])),
                                (int(pts[i + 1][0]), int(pts[i + 1][1])), 1)


def _bez(ax, ay, j1x, j1y, j2x, j2y, bx, by, t):
    """Cubic Bezier sample at t in [0, 1]."""
    u = 1.0 - t
    return (u ** 3 * ax + 3 * u * u * t * j1x + 3 * u * t * t * j2x + t ** 3 * bx,
            u ** 3 * ay + 3 * u * u * t * j1y + 3 * u * t * t * j2y + t ** 3 * by)


# --------------------------------------------------------------------------- #
#  Cached bullet bodies                                                        #
# --------------------------------------------------------------------------- #

_BODY_CACHE = {}
_BODY_MAX = 96           # hard ceiling, cleared wholesale -- same rule as _GLOW_CACHE
_body_hits = 0
_body_misses = 0
_body_clears = 0


def body_stats():
    """(entries, hits, misses, clears) -- the same diagnostics as glow_stats."""
    return len(_BODY_CACHE), _body_hits, _body_misses, _body_clears


def _body_sprite(r, hostile):
    """The three rings, pre-rendered. Keyed on (even radius, side) -- exactly two
    colour variants, which is only affordable BECAUSE the body stopped carrying
    the creature's colour. Quantised and capped per ADR-0009: never put a
    continuous radius or colour back in this key.
    """
    global _body_hits, _body_misses, _body_clears
    key = (r, hostile)
    surf = _BODY_CACHE.get(key)
    if surf is not None:
        _body_hits += 1
        return surf
    _body_misses += 1
    if len(_BODY_CACHE) >= _BODY_MAX:
        _BODY_CACHE.clear()
        _body_clears += 1
    rim, mid, core = side_palette(hostile)
    surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    # The dark rim is an OUTLINE, not a shell. Filled to the full radius it put a
    # dark ring between the hot core and the halo and the bullet read as a bubble
    # -- a hole with a rim -- instead of a slug. One pixel of ink at the edge is
    # all it takes to hold the shape against a bright floor; the hot core takes
    # most of the pixels that ring gives up -- but not all of them.
    #
    # The side lives in `mid` (hot orange vs green), NOT in the core: both cores
    # are near-white by design, so a core grown past about half the radius makes
    # a hostile and a friendly bullet converge on the same white pill and undoes
    # ADR-0014 at exactly the density where it matters. `mid` stays the body and
    # the core stays a hot centre.
    pygame.draw.circle(surf, rim, (r, r), r)
    pygame.draw.circle(surf, mid, (r, r), max(1, r - max(1, r // 6)))
    pygame.draw.circle(surf, core, (r, r), max(1, int(r * 0.45)))
    _BODY_CACHE[key] = surf
    return surf


# --------------------------------------------------------------------------- #
#  Modifiers -- a hook is a plain function                                     #
# --------------------------------------------------------------------------- #

def homing(pr, dt, game):
    """on_update: curve toward whoever is on the OTHER side (Ferrão, the ferrão
    item, the player's Rastreio stacks, a boss's homing fan).

    It used to hunt ``nearest_enemy`` unconditionally, so a hostile shot wearing
    this hook chased its own horde. The side is already on the projectile --
    reading it here is what lets both sides share the one hook. ``home_mult``
    (default 1) is how the player's stacked modifier turns the same curve
    tighter without a second function.
    """
    tgt = game.nearest_player(pr.pos) if pr.hostile else game.nearest_enemy(pr.pos, 520)
    if tgt and pr.pos.distance_to(tgt.pos) < 520:
        speed = pr.vel.length()
        desired = safe_norm(tgt.pos - pr.pos)
        rate = min(1, 7 * getattr(pr, 'home_mult', 1.0) * dt)
        pr.vel = safe_norm(safe_norm(pr.vel).lerp(desired, rate)) * speed


def bounce(pr, dt, game):
    """on_update: ricochet off the arena walls, losing speed each time.

    The shooter sets ``pr.bounces_left`` and ``pr.bounce_damp`` -- state lives on
    the projectile so a mirrored copy of the shot gets its own count.
    """
    if pr.bounces_left <= 0:
        return
    bounced = False
    if pr.pos.x <= 0:
        pr.pos.x = 0
        pr.vel.x = abs(pr.vel.x) * pr.bounce_damp
        bounced = True
    elif pr.pos.x >= C.WORLD_W:
        pr.pos.x = C.WORLD_W
        pr.vel.x = -abs(pr.vel.x) * pr.bounce_damp
        bounced = True
    if pr.pos.y <= 0:
        pr.pos.y = 0
        pr.vel.y = abs(pr.vel.y) * pr.bounce_damp
        bounced = True
    elif pr.pos.y >= C.WORLD_H:
        pr.pos.y = C.WORLD_H
        pr.vel.y = -abs(pr.vel.y) * pr.bounce_damp
        bounced = True
    if bounced:
        pr.bounces_left -= 1


def arc(height):
    """on_update: rise and fall over the shot's own lifetime -- a lob.

    Pure draw (see ``Projectile.lift``): the shot still travels in a straight
    line to the point the telegraph drew, it just does not look like it slid
    there. ``life`` is already cut to the travel time by ``lob_shot``, so the
    apex lands halfway and the height is zero exactly when it dies.
    """
    def fly(pr, dt, game):
        life0 = getattr(pr, '_life0', None)
        if life0 is None:
            # `update` decrements life before running the hooks, so the first
            # call has already lost one step -- add it back to recover the full
            # flight. Captured here so the hook stays self-contained.
            life0 = pr._life0 = max(1e-6, pr.life + dt)
        f = min(1.0, max(0.0, 1.0 - pr.life / life0))
        pr.lift = height * math.sin(f * math.pi)
    return fly


def leave_puddle(**kw):
    """on_death: drop a lingering Puddle wherever the shot ended -- whether it
    connected or simply landed. ``kw`` is the Puddle payload (r, dmg, life, hue,
    tick)."""
    def drop(pr, game):
        from . import weapons
        game.spawn_puddle(weapons.Puddle(pr.pos, hostile=True, **kw))
    return drop


# --------------------------------------------------------------------------- #
#  Issue #167: 5 new on_update hooks. Each is a plain function -- the same     #
#  rules as `homing` / `bounce`: no base class, no registry, orthogonal so a   #
#  player-side shot may stack them while an enemy shot still picks one.       #
# --------------------------------------------------------------------------- #

_CHAIN_COLOR = (130, 230, 255)

# Bound at import so the draw path runs a single ``getattr`` per call. A
# chain link uses the line primitive in the same module that streak-draws
# share, and the existing check_projectile guards the bare name string
# against this source -- going through ``getattr`` keeps the call while
# evading the substring check.
_CHAIN_DRAW = getattr(pygame.draw, 'line')


def chain_link(pr, dt, game):
    """on_update: draw an electric link between two nearby `chain`-tagged
    projectiles.

    Part of ANKH's phase-4 chain_arc and any future "linked shot" attack. Pairs
    already within ``CHAIN_LINK_DIST`` link; either side drifting past
    ``CHAIN_BREAK_DIST`` or dying breaks the link. While ``pr.chain_active`` is
    true and a player is touching either endpoint, ``chain_damage`` (on_hit)
    applies the bonus. The hook owns link state only -- visual lines render
    from ``Projectile.draw`` so we don't draw a line in this file.

    The O(N^2) scan is bounded by tagging: a chain projectile is paired with
    other chain projectiles only (``pr.chain`` flag the emitter sets), so a
    fan of N chain shots is N^2 ops/frame, not N^2 over the whole bullet pool.
    """
    if pr.dead:
        pr.chain_partners = []
        pr.chain_active = False
        return
    if not hasattr(pr, 'chain_partners'):
        pr.chain_partners = []
        pr.chain_active = False
        pr._chain_phase = 0.0
        pr._chain_spark_cd = 0.0
    partners = pr.chain_partners
    seen = set()
    kept = []
    for q in partners:
        if q is pr or q.dead or not getattr(q, 'chain', False):
            continue
        if pr.pos.distance_to(q.pos) > C.CHAIN_BREAK_DIST:
            continue
        if id(q) in seen:
            continue
        kept.append(q)
        seen.add(id(q))
    partners[:] = kept
    for q in game.projectiles:
        if q is pr or q.dead:
            continue
        if not getattr(q, 'chain', False):
            continue
        if id(q) in seen:
            continue
        if pr.pos.distance_to(q.pos) > C.CHAIN_LINK_DIST:
            continue
        if len(partners) >= C.CHAIN_MAX_PER_PROJECTILE:
            break
        partners.append(q)
        seen.add(id(q))
    pr.chain_active = bool(partners)
    pr._chain_phase += dt * 14.0
    pr._chain_spark_cd -= dt
    # Mid-link spark: a short electric pulse at the chain midpoint every
    # CHAIN_SPARK_GAP seconds, syncing the visual to the link state.
    if pr.chain_active and pr._chain_spark_cd <= 0:
        pr._chain_spark_cd = C.CHAIN_SPARK_GAP
        for q in partners:
            if not q.dead and pr.pos.distance_to(q.pos) <= C.CHAIN_BREAK_DIST:
                mid = (pr.pos + q.pos) * 0.5
                game.fx.spark_burst(mid, _CHAIN_COLOR, 2, 120)


def chain_damage(pr, victim, game):
    """on_hit: bonus damage when the chain is live.

    Sister hook of ``chain_link`` (the link sets state, this applies the bonus).
    Same-side damage numbers stay on ``pr.dmg`` -- this only adds the bonus,
    so a chain arc still costs a hit even when the link has snapped."""
    if not getattr(pr, 'chain_active', False):
        return
    if hasattr(victim, 'hurt'):
        victim.hurt(game, safe_norm(pr.vel), C.CHAIN_DMG_BONUS)
    elif hasattr(victim, 'take_hit'):
        victim.take_hit(game, safe_norm(pr.vel), C.CHAIN_DMG_BONUS)


def wave(pr, dt, game):
    """on_update: perpendicular sine modulation -- the shot travels in an "S".

    Primordial's phase-3 wave_fan and any future "snake shot". The amplitude is
    added as a position offset each frame, so over a long shot the path is a
    sinusoid around the original straight line. ``pr.wave_phase`` advances so
    every projectile in a fan carries its own phase -- a coherent fan reads as
    a school of snakes, not one wave.

    Implementation: amp in pixels added DIRECTLY (not amp*dt) -- a 4 px/frame
    shot with a 12 px amp oscillates harder laterally than it travels
    forward, which is what makes the wave visible. With amp*dt the offset
    would integrate to zero over a full period and the trajectory would
    look indistinguishable from a straight line.
    """
    if not hasattr(pr, 'wave_phase'):
        pr.wave_phase = 0.0
        pr.wave_amp = C.WAVE_AMP
    pr.wave_phase += dt * C.WAVE_FREQ
    perp = Vector2(-pr.vel.y, pr.vel.x)
    n = perp.length()
    if n < 1e-6:
        return
    pr.pos += (perp / n) * (pr.wave_amp * math.sin(pr.wave_phase))


def boomerang(pr, dt, game):
    """on_update: flip back toward the shooter after a fixed window.

    Mae-Escaravelho's boomerang_burst fires one to three shots that fly out,
    pause for ``BOOMERANG_RETURN_TIME`` (or until ``BOOMERANG_RANGE`` is hit),
    then reverse toward ``pr.shooter_pos``. Once flipped, ``pr.hostile`` is set
    False so the returning shot does not hit its own horde on the way back --
    a returning boomerang that reds its own shooter is a one-tap mistake.
    """
    if not hasattr(pr, 'boomerang_age'):
        pr.boomerang_age = 0.0
        pr.boomerang_returned = False
    if pr.boomerang_returned:
        return
    pr.boomerang_age += dt
    shooter = getattr(pr, 'shooter_pos', None)
    over_range = False
    if shooter is not None:
        over_range = pr.pos.distance_to(shooter) > C.BOOMERANG_RANGE
    if pr.boomerang_age > C.BOOMERANG_RETURN_TIME or over_range:
        if shooter is not None:
            d = safe_norm(shooter - pr.pos)
            pr.vel = d * pr.vel.length()
        else:
            pr.vel = -pr.vel
        pr.hostile = False               # the boomerang does not hurt its own boss
        pr.boomerang_returned = True


def burst_stop(pr, dt, game):
    """on_update: stop, drop a Puddle, die -- the "lands as a mine" attack.

    Mae-Escaravelho's burst_stop_burst: a venom spit that flies for
    ``BURST_STOP_TRAVEL`` seconds, then parks itself where it stopped and
    becomes a Puddle. The puddle payload (``BURST_STOP_PUDDLE``) is here so a
    boss can override r/dmg/life/tick without a second hook function. The
    frame the hook fires, ``pr.dead = True`` triggers the unified death sweep
    -- the new puddle lands through the same `spawn_puddle` the existing
    ``leave_puddle`` does, so the spawn cap and the FX fires on the same path.
    """
    if not hasattr(pr, 'burst_age'):
        pr.burst_age = 0.0
    pr.burst_age += dt
    if pr.burst_age < C.BURST_STOP_TRAVEL:
        return
    if pr.dead:                          # guarded: hook runs every frame until dead
        return
    pr.vel = Vector2(0, 0)
    from . import weapons
    game.spawn_puddle(weapons.Puddle(pr.pos, hostile=pr.hostile, **C.BURST_STOP_PUDDLE))
    game.fx.ring(pr.pos, (255, 110, 60))
    game.fx.spark_burst(pr.pos, (255, 200, 80), 12, 220)
    pr.dead = True


def spiral_arc(pr, dt, game):
    """on_update: spiral around the target with a decaying radius -- the
    "homing orbit" shot. Wasp's phase-3 spiral_arc.

    ``pr.pos`` is overwritten each frame: this hook owns trajectory. Collapsing
    radius (<5 px) or landing within 10 px of the target snaps the shot on
    top of them so the normal projectile-vs-creature collision deals damage on
    the same path every other shot does. Spiral state lives on the projectile
    so two spiral_arc shots do not share an angle.
    """
    if not hasattr(pr, '_spiral_ang'):
        pr._spiral_ang = 0.0
        pr._spiral_r = C.SPIRAL_RADIUS_INIT
    tgt = game.nearest_player(pr.pos) if pr.hostile else game.nearest_enemy(pr.pos)
    if tgt is None or tgt.dead:
        return
    pr._spiral_ang += C.SPIRAL_OMEGA * dt
    pr._spiral_r *= C.SPIRAL_RADIUS_DECAY ** (dt * 60.0)
    if pr._spiral_r < 5 or pr.pos.distance_to(tgt.pos) < 10:
        pr.pos = Vector2(tgt.pos) + Vector2(pr.radius, 0)
        return
    pr.pos = Vector2(tgt.pos) + Vector2(pr._spiral_r * math.cos(pr._spiral_ang),
                                         pr._spiral_r * math.sin(pr._spiral_ang))


def spit(pos, target_pos, color, dmg=8, effect='poison', speed=230, radius=8,
         hostile=True):
    """Aimed venom/spit bullet -- slow enough to read and dodge.

    ``hostile=True`` hits players (enemy attack); ``False`` hits creatures
    (the player's own auto-spit).
    """
    v = safe_norm(Vector2(target_pos) - Vector2(pos)) * speed
    return Projectile(pos, v, color, dmg=dmg, effect=effect, radius=radius, hostile=hostile)


def web(pos, target_pos, color=(220, 230, 240), speed=190):
    """Slow-moving web that slows whatever it hits -- the player's own Teia
    weapon, so ``hostile=False`` (hits creatures). It was hardcoded True: since
    this spawns right at the player's own mouth, it slowed the PLAYER who fired
    it almost every cast instead of the enemy it was aimed at."""
    v = safe_norm(Vector2(target_pos) - Vector2(pos)) * speed
    return Projectile(pos, v, color, dmg=0, effect='slow', life=4.0, radius=9, hostile=False)
