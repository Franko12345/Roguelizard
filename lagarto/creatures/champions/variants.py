"""Champion **variants**: named creatures with a colour, a visible tell and behaviour.

See the package docstring for why variants and modifiers are separate layers.
Each variant's ``tick`` sits right next to its ``apply`` -- reading a variant's
spawn-time trait and its per-frame behaviour side by side is the whole point.
"""

import random

from ...core import config as C
from ...core import palette
from ...core.mathutil import safe_norm


def _rebuild(c):
    """Rebuild the body after the genome changed.

    This used to re-run ``__init__`` behind a snapshot of ~11 fields, because
    ``__init__`` resets everything: species.make's metadata reverted to the raw
    genome defaults, and stacking a modifier onto a variant erased the variant.
    ``Lizard.rebuild_body`` only touches genome-derived state, so the snapshot --
    and the whole class of bug it was patching over -- is gone.
    """
    c.rebuild_body()


# --------------------------------------------------------------------------- #
#  Variants                                                                    #
# --------------------------------------------------------------------------- #

def _filhote(c, game):
    """Blue-lizard shape: the smallest and frailest, but genuinely fast.

    Dies to one touch, so it can be aggressive without being unfair -- the threat
    is the swarm arriving faster than you can turn, not any single one of them.
    """
    g = c.genome
    g.size *= 0.55
    g.hue = 205
    g.sat = 0.95
    g.angular_damping = 0.1        # tiny + darty: light on its feet, near-zero inertia
    g.linear_damping = 0.1
    g.weight = 0.5
    _rebuild(c)
    c.hp = 1
    c.max_hp = 1
    # Absolute, not a multiplier. max_speed is `165 * (0.85 + 0.4/size) * speed`,
    # so shrinking already accelerates it a lot -- multiplying on top of that
    # measured 5.75x the player, which nothing can dodge. And a *relative* boost
    # would make a "filhote of a tank" slower than the player, which contradicts
    # the one thing this variant is supposed to mean.
    c.max_speed = C.CHAMP_FILHOTE_SPEED
    c.xp_value = max(1, c.xp_value // 2)
    c.score_value = max(5, c.score_value // 2)


def _alfa(c, game):
    """Yellow-lizard shape: long antennae, and it hunts with a pack.

    The antennae are the tell -- they exist so the player can learn "that one
    makes the others dangerous" and prioritise it.
    """
    g = c.genome
    g.antennae = True
    g.size *= 1.15
    g.hue = 48
    g.sat = 0.95
    _rebuild(c)


def _alfa_tick(c, dt, game):
    c.rally_cd = getattr(c, 'rally_cd', 0.0) - dt
    if c.rally_cd > 0:
        return
    target = game.nearest_player(c.pos)
    if not target or target.pos.distance_to(c.pos) > C.CHAMP_ALFA_RANGE:
        return
    c.rally_cd = C.CHAMP_ALFA_CD
    roused = 0
    for e in game.enemies:
        if e is c or e.dead:
            continue
        if e.pos.distance_to(c.pos) < C.CHAMP_ALFA_RANGE:
            e.rally_t = C.CHAMP_ALFA_TIME
            roused += 1
    if roused:
        game.fx.ring(c.pos, (255, 226, 90))
        game.fx.spark_burst(c.pos, (255, 226, 90), 8, 240)


def _espectro(c, game):
    """White-lizard shape: an ambusher that is hard to see until it commits."""
    g = c.genome
    g.hue = 190
    g.sat = 0.12
    g.val = 1.0
    _rebuild(c)
    c.base_color = c.color


def _espectro_tick(c, dt, game):
    """Fade toward the ground until it is close, or until it has been hurt.

    Reuses the colour channel rather than real alpha: every part of the draw path
    reads ``self.color``, so body, legs, rim and glow all follow for free -- the
    same trick ``_fade_by_vitality`` uses for allies.
    """
    target = game.nearest_player(c.pos)
    dist = target.pos.distance_to(c.pos) if target else 9e9
    close = 1.0 - min(1.0, dist / C.CHAMP_ESPECTRO_REVEAL)
    hurt = 1.0 if c.hp < c.max_hp else 0.0
    vis = max(close, hurt, 0.12)
    c.color = palette.mix((58, 62, 74), c.base_color, vis)
    # the aura and the name obey the camouflage too, or the ambush is announced
    c.champion_vis = vis


def _saltador(c, game):
    """Cyan-lizard shape: covers ground in bursts instead of a steady walk."""
    g = c.genome
    g.hue = 178
    g.sat = 0.9
    g.tail = 'club'                 # the heavy tail it launches from: the tell
    _rebuild(c)


def _saltador_tick(c, dt, game):
    c.leap_cd = getattr(c, 'leap_cd', random.uniform(0.5, 1.6)) - dt
    if c.leap_cd > 0:
        return
    target = game.nearest_player(c.pos)
    if not target or target.pos.distance_to(c.pos) > C.CHAMP_SALTADOR_RANGE:
        return
    c.leap_cd = C.CHAMP_SALTADOR_CD
    c.vel = safe_norm(target.pos - c.pos) * c.max_speed * C.CHAMP_SALTADOR_POWER
    game.fx.spark_burst(c.pos, c.color, 7, 260)


def _apice(c, game):
    """Red-lizard shape: bigger, faster, relentless. The one you must respect."""
    g = c.genome
    g.size *= 1.3
    g.speed *= 1.2
    g.hue = 2
    g.sat = 1.0
    g.horns = max(1, g.horns)
    _rebuild(c)
    c.max_speed *= 1.15
    c.glow_body = True
    c.xp_value = int(c.xp_value * 1.6)
    c.score_value = int(c.score_value * 1.8)
