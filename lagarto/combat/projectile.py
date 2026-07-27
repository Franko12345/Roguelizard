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
        self.radius = radius
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
        r = max(4, int(self.radius * z) & ~1)     # even -> halves the cache keys
        rim, mid, core = side_palette(self.hostile)
        # trailing streak: ONE line. At ~100 bullets a seven-circle tail with a
        # per-frame palette.mix each was the most expensive thing on screen and
        # read as noise anyway.
        if self.trail:
            pygame.draw.line(surf, mid, cam.w2s(self.trail[0]), sp,
                             max(1, int(r * 0.5)))
        # additive halo -- the ONLY place the creature's own colour survives
        palette.glow(surf, sp, self.radius * 3.4 * z, self.color, 0.75)
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
    pygame.draw.circle(surf, rim, (r, r), r)
    pygame.draw.circle(surf, mid, (r, r), int(r * 0.8))
    pygame.draw.circle(surf, core, (r, r), max(1, int(r * 0.42)))
    _BODY_CACHE[key] = surf
    return surf


# --------------------------------------------------------------------------- #
#  Modifiers -- a hook is a plain function                                     #
# --------------------------------------------------------------------------- #

def homing(pr, dt, game):
    """on_update: curve toward the nearest enemy (Ferrão, the ferrão item)."""
    tgt = game.nearest_enemy(pr.pos, 520)
    if tgt:
        speed = pr.vel.length()
        desired = safe_norm(tgt.pos - pr.pos)
        pr.vel = safe_norm(safe_norm(pr.vel).lerp(desired, min(1, 7 * dt))) * speed


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
