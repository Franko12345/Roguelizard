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
        self.trail = []                 # recent world positions -> a Gungeon streak
        # Fake height, in screen pixels, for anything LOBBED. The world position
        # stays flat -- this game has no z -- so only the draw lifts, which is
        # what makes a shot read as thrown-and-landed instead of slid along the
        # floor. The telegraph on the ground doubles as its shadow.
        self.lift = 0.0

    def update(self, dt, game=None):
        self.trail.append((self.pos.x, self.pos.y))
        if len(self.trail) > 3:
            self.trail.pop(0)
        self.pos += self.vel * dt
        self.life -= dt
        self.spin += dt * 9
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
        # trailing streak: ONE line. At ~100 bullets a seven-circle tail with a
        # per-frame palette.mix each was the most expensive thing on screen and
        # read as noise anyway.
        if self.trail:
            # A streak, not a stick: it starts at the body's own width and the
            # cap rounds it, so it reads as motion instead of a rectangle glued
            # to the front of the bullet. Drawn in `mid`, not `core`: a white
            # streak is a white stick, and it costs the side its colour on the
            # very part of the bullet that is longest on screen.
            tail = cam.w2s(self.trail[0])
            if self.lift:
                # lift the tail too, or a lobbed shot draws a rigid spike from
                # its own height down to the ground it has not reached yet
                tail = (tail[0], tail[1] - self.lift * z)
            pygame.draw.line(surf, mid, tail, sp, max(1, int(r * 0.85)))
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
