"""Procedural icons for weapons, mutations and charms.

The game ships no image files, so icons are *drawn* with the same vocabulary as
the rest of the art (filled shape + lighter rim + ink edge + a soft glow). Every
icon is a function that fills a circle of radius ``r`` around ``c``; unknown ids
fall back to a plain disc, so adding content never crashes the UI.
"""

import math
import pygame

from . import assets
from ..core import config as C
from ..core import palette
from ..core.mathutil import vfrom_angle

INK = C.COL_INK


def _disc(s, c, r, col):
    pygame.draw.circle(s, col, c, r)
    pygame.draw.circle(s, palette.lighten(col, 0.45), c, r, max(1, r // 6))
    pygame.draw.circle(s, INK, c, r, max(1, r // 8))


def _drop(s, c, r, col):
    """Teardrop pointing up-right (spit/venom)."""
    pts = [(c[0], c[1] - r), (c[0] + r * 0.72, c[1] + r * 0.35),
           (c[0], c[1] + r * 0.9), (c[0] - r * 0.72, c[1] + r * 0.35)]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, max(1, r // 8))
    pygame.draw.circle(s, palette.lighten(col, 0.5), (c[0] - r // 4, c[1]), max(1, r // 5))


def _star(s, c, r, col, spikes=8, inner=0.45):
    pts = []
    for k in range(spikes * 2):
        rad = r if k % 2 == 0 else r * inner
        pts.append(c + vfrom_angle(k * (180 / spikes) - 90, rad))
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, max(1, r // 9))


def _rings(s, c, r, col, n=3):
    for k in range(n):
        rr = int(r * (1 - k * 0.28))
        if rr > 1:
            pygame.draw.circle(s, palette.lighten(col, 0.15 * k), c, rr, max(1, r // 7))


def _bubbles(s, c, r, col):
    for dx, dy, f in ((-0.4, 0.25, 0.5), (0.35, 0.3, 0.42), (0.0, -0.25, 0.62),
                      (0.45, -0.3, 0.3)):
        pygame.draw.circle(s, col, (int(c[0] + dx * r), int(c[1] + dy * r)),
                           max(2, int(r * f * 0.6)))
        pygame.draw.circle(s, INK, (int(c[0] + dx * r), int(c[1] + dy * r)),
                           max(2, int(r * f * 0.6)), 1)


def _arrow(s, c, r, col, ang=-45):
    tip = c + vfrom_angle(ang, r)
    tail = c + vfrom_angle(ang + 180, r * 0.85)
    l = c + vfrom_angle(ang + 140, r * 0.6)
    rr = c + vfrom_angle(ang - 140, r * 0.6)
    pygame.draw.polygon(s, col, [tip, l, tail, rr])
    pygame.draw.polygon(s, INK, [tip, l, tail, rr], max(1, r // 9))


def _heart(s, c, r, col):
    pygame.draw.circle(s, col, (int(c[0] - r * 0.38), int(c[1] - r * 0.2)), int(r * 0.5))
    pygame.draw.circle(s, col, (int(c[0] + r * 0.38), int(c[1] - r * 0.2)), int(r * 0.5))
    pygame.draw.polygon(s, col, [(c[0] - r * 0.86, c[1] - r * 0.05),
                                 (c[0] + r * 0.86, c[1] - r * 0.05),
                                 (c[0], c[1] + r * 0.95)])


def _bolt(s, c, r, col):
    pts = [(c[0] - r * 0.15, c[1] - r), (c[0] + r * 0.55, c[1] - r * 0.1),
           (c[0] + r * 0.1, c[1] - r * 0.05), (c[0] + r * 0.35, c[1] + r),
           (c[0] - r * 0.55, c[1] + r * 0.05), (c[0] - r * 0.05, c[1])]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, max(1, r // 9))


def _clock(s, c, r, col):
    pygame.draw.circle(s, col, c, r)
    pygame.draw.circle(s, INK, c, r, max(1, r // 7))
    pygame.draw.line(s, INK, c, (c[0], c[1] - r * 0.6), max(2, r // 6))
    pygame.draw.line(s, INK, c, (c[0] + r * 0.45, c[1]), max(2, r // 7))


def _spikes_icon(s, c, r, col):
    for k, ang in enumerate((-120, -90, -60)):
        base_l = c + vfrom_angle(ang - 22, r * 0.55)
        base_r = c + vfrom_angle(ang + 22, r * 0.55)
        tip = c + vfrom_angle(ang, r * 1.05)
        pygame.draw.polygon(s, col, [base_l, tip, base_r])
        pygame.draw.polygon(s, INK, [base_l, tip, base_r], 1)
    pygame.draw.arc(s, palette.darken(col, 0.2),
                    (c[0] - r, c[1] - r * 0.35, r * 2, r * 1.3), math.pi, 2 * math.pi,
                    max(2, r // 5))


def _plates_icon(s, c, r, col):
    for k in range(3):
        y = c[1] - r * 0.5 + k * r * 0.5
        pygame.draw.lines(s, col, False,
                          [(c[0] - r * 0.75, y + r * 0.25), (c[0], y - r * 0.2),
                           (c[0] + r * 0.75, y + r * 0.25)], max(2, r // 5))


def _horns_icon(s, c, r, col):
    for sgn in (-1, 1):
        pts = [(c[0] + sgn * r * 0.15, c[1] + r * 0.7),
               (c[0] + sgn * r * 0.55, c[1] - r * 0.1),
               (c[0] + sgn * r * 0.85, c[1] - r * 0.9),
               (c[0] + sgn * r * 0.45, c[1] - r * 0.2),
               (c[0] + sgn * r * 0.05, c[1] + r * 0.55)]
        pygame.draw.polygon(s, col, pts)
        pygame.draw.polygon(s, INK, pts, 1)


def _legs_icon(s, c, r, col):
    pygame.draw.circle(s, col, c, int(r * 0.42))
    pygame.draw.circle(s, INK, c, int(r * 0.42), 1)
    for a in (-140, -100, -60, 140, 100, 60):
        mid = c + vfrom_angle(a, r * 0.72)
        tip = mid + vfrom_angle(a + (18 if a < 0 else -18), r * 0.5)
        pygame.draw.lines(s, col, False, [c, mid, tip], max(2, r // 6))


def _wings_icon(s, c, r, col):
    for sgn in (-1, 1):
        pts = [c, (c[0] + sgn * r, c[1] - r * 0.55), (c[0] + sgn * r * 0.85, c[1] + r * 0.5)]
        pygame.draw.polygon(s, col, pts)
        pygame.draw.polygon(s, INK, pts, 1)


def _orbit(s, c, r, col):
    pygame.draw.circle(s, palette.darken(col, 0.35), c, int(r * 0.85), max(1, r // 9))
    for a in (0, 120, 240):
        p = c + vfrom_angle(a, r * 0.85)
        pygame.draw.circle(s, col, (int(p.x), int(p.y)), max(2, r // 4))
        pygame.draw.circle(s, INK, (int(p.x), int(p.y)), max(2, r // 4), 1)


def _puddle(s, c, r, col):
    rect = pygame.Rect(c[0] - r, c[1] - r * 0.5, r * 2, r * 1.1)
    pygame.draw.ellipse(s, col, rect)
    pygame.draw.ellipse(s, INK, rect, max(1, r // 8))
    for dx, dy in ((-0.35, -0.05), (0.3, 0.1), (0.0, 0.2)):
        pygame.draw.circle(s, palette.lighten(col, 0.4),
                           (int(c[0] + dx * r), int(c[1] + dy * r)), max(1, r // 6))


def _fan(s, c, r, col):
    for a in (-40, 0, 40):
        pygame.draw.arc(s, col, (c[0] - r, c[1] - r, r * 2, r * 2),
                        math.radians(a - 18), math.radians(a + 18), max(2, r // 4))
    _arrow(s, (c[0] - r * 0.3, c[1]), int(r * 0.4), palette.lighten(col, 0.3), 0)


def _antennae(s, c, r, col):
    for sgn in (-1, 1):
        base = (c[0] + sgn * r * 0.2, c[1] + r * 0.7)
        mid = (c[0] + sgn * r * 0.55, c[1] - r * 0.1)
        tip = (c[0] + sgn * r * 0.9, c[1] - r * 0.75)
        pygame.draw.lines(s, col, False, [base, mid, tip], max(2, r // 6))
        pygame.draw.circle(s, palette.lighten(col, 0.4), (int(tip[0]), int(tip[1])),
                           max(2, r // 5))


def _eyes(s, c, r, col):
    for dx, dy, f in ((-0.45, -0.1, 0.42), (0.45, -0.1, 0.42), (0.0, 0.45, 0.3)):
        p = (int(c[0] + dx * r), int(c[1] + dy * r))
        pygame.draw.circle(s, (245, 245, 250), p, max(2, int(r * f)))
        pygame.draw.circle(s, INK, p, max(1, int(r * f * 0.45)))


def _fangs(s, c, r, col):
    for sgn in (-1, 1):
        pts = [(c[0] + sgn * r * 0.2, c[1] - r * 0.5),
               (c[0] + sgn * r * 0.6, c[1] - r * 0.45),
               (c[0] + sgn * r * 0.35, c[1] + r * 0.75)]
        pygame.draw.polygon(s, (245, 245, 250), pts)
        pygame.draw.polygon(s, INK, pts, 1)
    pygame.draw.circle(s, col, (c[0], int(c[1] - r * 0.72)), max(2, r // 4))


def _sac(s, c, r, col):
    rect = pygame.Rect(c[0] - r * 0.62, c[1] - r * 0.5, r * 1.24, r * 1.35)
    pygame.draw.ellipse(s, col, rect)
    pygame.draw.ellipse(s, INK, rect, max(1, r // 8))
    pygame.draw.circle(s, palette.lighten(col, 0.5),
                       (int(c[0] - r * 0.2), int(c[1] - r * 0.1)), max(1, r // 5))


def _club(s, c, r, col):
    pygame.draw.line(s, palette.darken(col, 0.25), (c[0] - r * 0.8, c[1] + r * 0.8),
                     (c[0] + r * 0.1, c[1] - r * 0.1), max(2, r // 4))
    pygame.draw.circle(s, col, (int(c[0] + r * 0.35), int(c[1] - r * 0.35)), int(r * 0.55))
    pygame.draw.circle(s, INK, (int(c[0] + r * 0.35), int(c[1] - r * 0.35)), int(r * 0.55), 1)
    for a in range(0, 360, 72):
        p = vfrom_angle(a, r * 0.62) + pygame.Vector2(c[0] + r * 0.35, c[1] - r * 0.35)
        pygame.draw.circle(s, palette.lighten(col, 0.3), (int(p.x), int(p.y)), max(1, r // 6))


def _sting(s, c, r, col):
    pygame.draw.lines(s, col, False,
                      [(c[0] - r * 0.8, c[1] + r * 0.6), (c[0], c[1] + r * 0.1),
                       (c[0] + r * 0.55, c[1] - r * 0.45)], max(2, r // 4))
    tip = (int(c[0] + r * 0.8), int(c[1] - r * 0.8))
    pygame.draw.circle(s, (255, 120, 130), tip, max(2, r // 4))
    pygame.draw.circle(s, INK, tip, max(2, r // 4), 1)


def _tongue(s, c, r, col):
    pygame.draw.lines(s, col, False,
                      [(c[0] - r * 0.85, c[1] + r * 0.5), (c[0], c[1]),
                       (c[0] + r * 0.7, c[1] - r * 0.55)], max(2, r // 5))
    pygame.draw.circle(s, palette.lighten(col, 0.3),
                       (int(c[0] + r * 0.75), int(c[1] - r * 0.6)),
                       max(2, r // 5))


def _plus_one(s, c, r, col, font=None):
    pygame.draw.line(s, col, (c[0] - r * 0.6, c[1]), (c[0] + r * 0.6, c[1]), max(2, r // 4))
    pygame.draw.line(s, col, (c[0], c[1] - r * 0.6), (c[0], c[1] + r * 0.6), max(2, r // 4))


def _expand(s, c, r, col):
    pygame.draw.circle(s, col, c, int(r * 0.32))
    pygame.draw.circle(s, col, c, int(r * 0.7), max(1, r // 8))
    pygame.draw.circle(s, palette.darken(col, 0.2), c, r, max(1, r // 9))


# ---- items (items.py) ------------------------------------------------------ #
# Twenty items all falling back to the same disc is worse than the shape
# collisions the compendium already has, so each gets its own silhouette.

def _ring_burst(s, c, r, col):          # pulso: expanding shockwave
    for k, f in enumerate((1.0, 0.66, 0.36)):
        pygame.draw.circle(s, col if k == 0 else palette.lighten(col, 0.3),
                           c, max(1, int(r * f)), max(1, r // 7))


def _shell(s, c, r, col):               # muda: a shed skin, split open
    pygame.draw.arc(s, col, (c[0] - r, c[1] - r, r * 2, r * 2), 0.6, 5.7,
                    max(2, r // 4))
    pygame.draw.circle(s, palette.lighten(col, 0.5), (c[0], c[1]), max(2, r // 3))


def _horn_call(s, c, r, col):           # chamado: a horn / summon cone
    pts = [(c[0] - r * 0.8, c[1] - r * 0.5), (c[0] + r * 0.8, c[1] - r * 0.9),
           (c[0] + r * 0.8, c[1] + r * 0.9), (c[0] - r * 0.8, c[1] + r * 0.5)]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, max(1, r // 8))


def _volley(s, c, r, col):              # salva: three darts fanning out
    for a in (-38, 0, 38):
        tip = c + vfrom_angle(a, r)
        tail = c + vfrom_angle(a + 180, r * 0.5)
        pygame.draw.line(s, col, tail, tip, max(2, r // 5))
        pygame.draw.circle(s, palette.lighten(col, 0.5), tip, max(1, r // 5))


def _trail(s, c, r, col):               # rastro: fading footprints
    for k, f in enumerate((1.0, 0.72, 0.48)):
        p = (int(c[0] - r * 0.7 + k * r * 0.7), int(c[1] + r * 0.3 - k * r * 0.3))
        pygame.draw.circle(s, palette.mix(INK, col, f), p, max(2, int(r * 0.42 * f)))


def _sling(s, c, r, col):               # arremesso: tongue flinging outward
    pygame.draw.arc(s, col, (c[0] - r, c[1] - r * 0.6, r * 1.6, r * 1.4),
                    2.2, 5.2, max(2, r // 5))
    pygame.draw.circle(s, palette.lighten(col, 0.5),
                       (int(c[0] + r * 0.6), int(c[1] - r * 0.5)), max(2, r // 3))


def _darts(s, c, r, col):               # farpas: barbs off an arc
    pygame.draw.arc(s, col, (c[0] - r, c[1] - r, r * 2, r * 2), 3.4, 6.0,
                    max(2, r // 5))
    for a in (200, 240, 280, 320):
        base = c + vfrom_angle(a, r * 0.75)
        pygame.draw.line(s, palette.lighten(col, 0.4), base,
                         c + vfrom_angle(a, r * 1.15), max(1, r // 7))


def _boom(s, c, r, col):                # estopim: a spiky detonation
    _star(s, c, r, col, spikes=7, inner=0.4)
    pygame.draw.circle(s, palette.lighten(col, 0.6), c, max(2, r // 3))


def _magnet(s, c, r, col):              # iman: horseshoe
    pygame.draw.arc(s, col, (c[0] - r * 0.85, c[1] - r * 0.9, r * 1.7, r * 1.7),
                    0.5, 2.65, max(3, r // 3))
    for sx in (-1, 1):
        pygame.draw.rect(s, palette.lighten(col, 0.45),
                         (c[0] + sx * r * 0.75 - r * 0.2, c[1] + r * 0.1,
                          r * 0.4, r * 0.6))


def _fang_drop(s, c, r, col):           # carnica: fang over a drop
    pts = [(c[0] - r * 0.5, c[1] - r * 0.7), (c[0] + r * 0.5, c[1] - r * 0.7),
           (c[0], c[1] + r * 0.15)]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, max(1, r // 8))
    pygame.draw.circle(s, palette.lighten(col, 0.5),
                       (c[0], int(c[1] + r * 0.6)), max(2, r // 4))


def _bounce(s, c, r, col):              # ricochete: a bouncing path
    pts = [(c[0] - r, c[1] + r * 0.5), (c[0] - r * 0.3, c[1] - r * 0.6),
           (c[0] + r * 0.3, c[1] + r * 0.5), (c[0] + r, c[1] - r * 0.6)]
    pygame.draw.lines(s, col, False, pts, max(2, r // 5))
    pygame.draw.circle(s, palette.lighten(col, 0.5),
                       (int(pts[-1][0]), int(pts[-1][1])), max(2, r // 4))


def _cocoon(s, c, r, col):              # casulo: wrapped oval
    pygame.draw.ellipse(s, col, (c[0] - r * 0.6, c[1] - r, r * 1.2, r * 2))
    for k in (-0.4, 0.0, 0.4):
        pygame.draw.line(s, INK, (c[0] - r * 0.6, c[1] + k * r),
                         (c[0] + r * 0.6, c[1] + k * r + r * 0.2), max(1, r // 8))


def _target(s, c, r, col):              # marcado: a brand, not a crosshair
    pygame.draw.circle(s, col, c, r, max(2, r // 5))
    pygame.draw.circle(s, col, c, max(2, int(r * 0.35)))


def _spread(s, c, r, col):              # contagio: one dot infecting others
    pygame.draw.circle(s, col, c, max(2, int(r * 0.42)))
    for a in (30, 150, 270):
        p = c + vfrom_angle(a, r * 0.8)
        pygame.draw.line(s, palette.darken(col, 0.2), c, p, max(1, r // 8))
        pygame.draw.circle(s, palette.lighten(col, 0.4), p, max(1, int(r * 0.24)))


def _two_way(s, c, r, col):             # retaguarda: arrows both ways
    for sx in (-1, 1):
        tip = (c[0] + sx * r, c[1])
        pygame.draw.line(s, col, (c[0] + sx * r * 0.2, c[1]), tip, max(2, r // 5))
        pygame.draw.polygon(s, palette.lighten(col, 0.4),
                            [tip, (tip[0] - sx * r * 0.38, c[1] - r * 0.32),
                             (tip[0] - sx * r * 0.38, c[1] + r * 0.32)])


def _deflect(s, c, r, col):             # contragolpe: shot bouncing off a bar
    pygame.draw.line(s, col, (c[0] - r * 0.2, c[1] - r), (c[0] - r * 0.2, c[1] + r),
                     max(3, r // 4))
    pygame.draw.lines(s, palette.lighten(col, 0.45), False,
                      [(c[0] + r, c[1] - r * 0.7), (c[0] - r * 0.1, c[1]),
                       (c[0] + r, c[1] + r * 0.7)], max(2, r // 6))


def _pulse_line(s, c, r, col):          # adrenalina: heartbeat spike
    pygame.draw.lines(s, col, False,
                      [(c[0] - r, c[1]), (c[0] - r * 0.35, c[1]),
                       (c[0] - r * 0.1, c[1] - r * 0.85),
                       (c[0] + r * 0.15, c[1] + r * 0.7),
                       (c[0] + r * 0.4, c[1]), (c[0] + r, c[1])], max(2, r // 5))


def _leech(s, c, r, col):               # sanguessuga: curved sucker
    pygame.draw.arc(s, col, (c[0] - r, c[1] - r, r * 2, r * 2), 1.0, 4.4,
                    max(3, r // 4))
    pygame.draw.circle(s, palette.lighten(col, 0.5),
                       (int(c[0] - r * 0.1), int(c[1] - r * 0.85)), max(2, r // 4))


def _second_wind(s, c, r, col):         # segundo folego: a rising feather
    pygame.draw.line(s, col, (c[0], c[1] + r), (c[0], c[1] - r), max(2, r // 6))
    for k in range(3):
        f = 0.9 - k * 0.26
        y = c[1] - r * (0.55 - k * 0.42)
        for sx in (-1, 1):
            pygame.draw.line(s, palette.lighten(col, 0.35), (c[0], y),
                             (c[0] + sx * r * f, y + r * 0.34), max(1, r // 8))


def _spiral(s, c, r, col):              # espiral: whip sweeping a full circle
    pts = []
    for k in range(26):
        a = k * 26
        rad = r * (0.15 + 0.85 * k / 25.0)
        pts.append(c + vfrom_angle(a, rad))
    pygame.draw.lines(s, col, False, pts, max(2, r // 6))


# ---- playable characters -------------------------------------------------- #
# Each one is a silhouette of the creature you actually get. A generic badge
# would tell the player nothing; the whole point of these four is that they look
# different on screen, so the icon has to promise the same thing.

def _blob(s, c, pts, col, w=None):
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, w or max(1, len(pts) // 6))


def _char_lagarto(s, c, r, col):
    """Four legs, medium body, tapering tail: the baseline shape."""
    body = [(c[0] - r * 0.7, c[1]), (c[0] - r * 0.2, c[1] - r * 0.42),
            (c[0] + r * 0.45, c[1] - r * 0.34), (c[0] + r * 0.8, c[1]),
            (c[0] + r * 0.45, c[1] + r * 0.34), (c[0] - r * 0.2, c[1] + r * 0.42)]
    for sx in (-1, 1):
        for lx in (-0.35, 0.3):
            pygame.draw.line(s, palette.darken(col, 0.25),
                             (c[0] + r * lx, c[1] + sx * r * 0.28),
                             (c[0] + r * (lx - 0.16), c[1] + sx * r * 0.78),
                             max(2, r // 7))
    pygame.draw.line(s, palette.darken(col, 0.2), (c[0] - r * 0.65, c[1]),
                     (c[0] - r * 0.98, c[1] - r * 0.3), max(2, r // 8))
    _blob(s, c, body, col)
    pygame.draw.circle(s, (250, 250, 255), (int(c[0] + r * 0.45), int(c[1] - r * 0.12)),
                       max(2, r // 6))
    pygame.draw.circle(s, INK, (int(c[0] + r * 0.48), int(c[1] - r * 0.12)),
                       max(1, r // 12))


def _char_vibora(s, c, r, col):
    """Legless S-curve ending in a heavy club: the tail IS the weapon."""
    pts = []
    for k in range(9):
        f = k / 8.0
        x = c[0] - r * 0.9 + f * r * 1.7
        y = c[1] + math.sin(f * math.pi * 1.7) * r * 0.5
        pts.append((x, y))
    for i in range(len(pts) - 1):
        w = max(2, int(r * (0.30 - 0.16 * (i / len(pts)))))
        pygame.draw.line(s, col, pts[i], pts[i + 1], w * 2)
    pygame.draw.circle(s, palette.lighten(col, 0.25),
                       (int(pts[-1][0]), int(pts[-1][1])), max(3, int(r * 0.3)))
    pygame.draw.circle(s, INK, (int(pts[-1][0]), int(pts[-1][1])),
                       max(3, int(r * 0.3)), max(1, r // 10))
    pygame.draw.circle(s, (250, 250, 255), (int(pts[0][0]), int(pts[0][1])),
                       max(2, r // 7))


def _char_couracado(s, c, r, col):
    """Wide plated shell -- reads as 'wall' before you read the label."""
    body = [(c[0] - r * 0.85, c[1] + r * 0.1), (c[0] - r * 0.5, c[1] - r * 0.6),
            (c[0] + r * 0.5, c[1] - r * 0.6), (c[0] + r * 0.9, c[1] + r * 0.1),
            (c[0] + r * 0.5, c[1] + r * 0.7), (c[0] - r * 0.5, c[1] + r * 0.7)]
    for sx in (-1, 1):
        for lx in (-0.4, 0.25):
            pygame.draw.line(s, palette.darken(col, 0.3),
                             (c[0] + r * lx, c[1] + sx * r * 0.5),
                             (c[0] + r * (lx - 0.1), c[1] + sx * r * 0.95),
                             max(3, r // 5))
    _blob(s, c, body, col)
    for k in range(3):                       # chevron plates down the back
        x = c[0] - r * 0.45 + k * r * 0.45
        pygame.draw.lines(s, palette.lighten(col, 0.45), False,
                          [(x, c[1] + r * 0.28), (x + r * 0.2, c[1] - r * 0.18),
                           (x + r * 0.4, c[1] + r * 0.28)], max(2, r // 9))


def _char_larva(s, c, r, col):
    """Small segmented grub. Deliberately the smallest icon of the four."""
    for k in range(4):
        f = k / 3.0
        rr = r * (0.42 - 0.09 * f)
        x = c[0] - r * 0.32 + f * r * 0.75
        pygame.draw.circle(s, col, (int(x), int(c[1])), int(rr))
        pygame.draw.circle(s, INK, (int(x), int(c[1])), int(rr), max(1, r // 12))
    pygame.draw.circle(s, (250, 250, 255),
                       (int(c[0] + r * 0.5), int(c[1] - r * 0.08)), max(2, r // 8))


def _boss_crown(s, c, r, col):
    """REI LAGARTO: a jagged 5-point crown -- procedural fallback so the boss
    bar never breaks without the PNG (see assets/icons/boss_rei_lagarto.png)."""
    band_y = c[1] + r * 0.35
    pts = [(c[0] - r * 0.85, band_y)]
    for k in range(5):
        t = k / 4.0
        x = c[0] + (-0.85 + 1.7 * t) * r
        pts.append((x, band_y - r * (0.55 if k % 2 == 0 else 1.1)))
    pts.append((c[0] + r * 0.85, band_y))
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, max(1, r // 9))
    for k in range(3):
        x = c[0] + (-0.55 + 0.55 * k) * r
        pygame.draw.circle(s, palette.lighten(col, 0.5), (int(x), int(band_y - r * 0.15)),
                           max(1, r // 7))


def _boss_gear(s, c, r, col):
    """CENTOPEIADEIRA: a rusted gear -- machine, not flesh."""
    pygame.draw.circle(s, col, c, int(r * 0.68))
    for a in range(0, 360, 45):
        base_l = c + vfrom_angle(a - 14, r * 0.62)
        base_r = c + vfrom_angle(a + 14, r * 0.62)
        tip_l = c + vfrom_angle(a - 16, r * 1.0)
        tip_r = c + vfrom_angle(a + 16, r * 1.0)
        pygame.draw.polygon(s, col, [base_l, tip_l, tip_r, base_r])
    pygame.draw.circle(s, INK, c, int(r * 0.68), max(1, r // 9))
    pygame.draw.circle(s, palette.darken(col, 0.35), c, int(r * 0.3))
    pygame.draw.circle(s, INK, c, int(r * 0.3), max(1, r // 10))


def _boss_kraken_eye(s, c, r, col):
    """KRAKEN-MOR: a wide eye with a curling tentacle underneath."""
    pygame.draw.circle(s, palette.darken(col, 0.2), c, int(r * 0.9))
    pygame.draw.circle(s, INK, c, int(r * 0.9), max(1, r // 9))
    pygame.draw.circle(s, (250, 250, 255), c, int(r * 0.55))
    pupil = (int(c[0]), int(c[1] - r * 0.05))
    pygame.draw.circle(s, INK, pupil, max(2, int(r * 0.28)))
    for sgn in (-1, 1):
        base = c + pygame.Vector2(sgn * r * 0.6, r * 0.75)
        mid = base + pygame.Vector2(sgn * r * 0.3, r * 0.5)
        tip = mid + pygame.Vector2(sgn * -r * 0.1, r * 0.4)
        pygame.draw.lines(s, col, False, [base, mid, tip], max(2, r // 6))


def _boss_hive(s, c, r, col):
    """MAE-ESCARAVELHO: a cluster of eggs (the swarm, not just the mother)."""
    offs = [(-0.42, -0.28), (0.42, -0.28), (0, -0.55), (-0.22, 0.32), (0.22, 0.32)]
    for i, (ox, oy) in enumerate(offs):
        rr = r * (0.5 if i < 3 else 0.42)
        p = (int(c[0] + ox * r), int(c[1] + oy * r))
        pygame.draw.circle(s, col if i else palette.lighten(col, 0.25), p, int(rr))
        pygame.draw.circle(s, INK, p, int(rr), max(1, r // 10))


def _boss_web(s, c, r, col):
    """ARANHA-REI: a pale spider crouched over its own web."""
    for a in range(0, 360, 45):
        pygame.draw.line(s, palette.darken(col, 0.3), c, c + vfrom_angle(a, r * 0.95), 1)
    for rr in (r * 0.4, r * 0.7, r * 0.95):
        pygame.draw.circle(s, palette.darken(col, 0.3), c, int(rr), 1)
    pygame.draw.circle(s, col, c, int(r * 0.4))
    pygame.draw.circle(s, INK, c, int(r * 0.4), max(1, r // 10))
    for sgn in (-1, 1):
        for k in range(3):
            a = sgn * (25 + k * 22)
            base = c + vfrom_angle(90 + a, r * 0.32)
            tip = c + vfrom_angle(90 + a, r * 0.85)
            pygame.draw.line(s, col, base, tip, max(1, r // 10))


def _boss_wing(s, c, r, col):
    """TERROR ALADO: a pair of insect wings framing a dripping stinger."""
    for sgn in (-1, 1):
        pts = [c, (c[0] + sgn * r * 1.05, c[1] - r * 0.7),
               (c[0] + sgn * r * 0.9, c[1] + r * 0.1),
               (c[0] + sgn * r * 0.35, c[1] + r * 0.15)]
        pygame.draw.polygon(s, palette.lighten(col, 0.35), pts)
        pygame.draw.polygon(s, INK, pts, max(1, r // 10))
        pygame.draw.line(s, palette.darken(col, 0.2), c,
                         (c[0] + sgn * r * 0.9, c[1] - r * 0.5), 1)
    # central stinger pointing down
    st = [(c[0], c[1] + r), (c[0] - r * 0.28, c[1] - r * 0.1),
          (c[0] + r * 0.28, c[1] - r * 0.1)]
    pygame.draw.polygon(s, col, st)
    pygame.draw.polygon(s, INK, st, max(1, r // 10))
    pygame.draw.circle(s, (120, 255, 140), (int(c[0]), int(c[1] + r * 0.85)), max(1, r // 8))


def _boss_crystal(s, c, r, col):
    """SERPENTE DE CRISTAL: a faceted diamond prism refracting light."""
    top = (c[0], c[1] - r)
    bot = (c[0], c[1] + r)
    lft = (c[0] - r * 0.7, c[1] - r * 0.2)
    rgt = (c[0] + r * 0.7, c[1] - r * 0.2)
    body = [top, rgt, (c[0] + r * 0.4, c[1] + r * 0.35), bot,
            (c[0] - r * 0.4, c[1] + r * 0.35), lft]
    pygame.draw.polygon(s, col, body)
    pygame.draw.polygon(s, INK, body, max(1, r // 9))
    # facet lines (the refraction)
    for p in (lft, rgt):
        pygame.draw.line(s, palette.lighten(col, 0.5), top, p, 1)
        pygame.draw.line(s, palette.darken(col, 0.3), p, bot, 1)
    pygame.draw.line(s, palette.lighten(col, 0.6), top, bot, 1)


def _boss_ankh(s, c, r, col):
    """ANKH: the loop-and-cross key of life -- the mark of the one that
    keeps coming back wearing the shapes you already killed."""
    w = max(1, r // 5)
    lw = max(1, r // 8)
    top = int(c[1] - r * 0.15)
    # the loop
    pygame.draw.circle(s, col, (int(c[0]), int(c[1] - r * 0.5)), int(r * 0.42), w)
    pygame.draw.circle(s, INK, (int(c[0]), int(c[1] - r * 0.5)), int(r * 0.42), lw)
    # the stem
    pygame.draw.line(s, col, (c[0], top), (c[0], c[1] + r * 0.9), w)
    # the crossbar
    pygame.draw.line(s, col, (c[0] - r * 0.55, c[1] + r * 0.12),
                     (c[0] + r * 0.55, c[1] + r * 0.12), w)


def _boss_primordial_flame(s, c, r, col):
    """PRIMORDIAL: an ancient flame/rune -- the final boss's mark."""
    pts = [(c[0], c[1] - r), (c[0] + r * 0.55, c[1] - r * 0.1),
           (c[0] + r * 0.32, c[1] + r * 0.15), (c[0] + r * 0.6, c[1] + r * 0.9),
           (c[0], c[1] + r * 0.5), (c[0] - r * 0.6, c[1] + r * 0.9),
           (c[0] - r * 0.32, c[1] + r * 0.15), (c[0] - r * 0.55, c[1] - r * 0.1)]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, INK, pts, max(1, r // 9))
    pygame.draw.circle(s, palette.lighten(col, 0.5), (int(c[0]), int(c[1] + r * 0.25)),
                       max(1, int(r * 0.22)))


ICONS = {
    # items (items.py)
    'pulso': _ring_burst, 'muda': _shell, 'chamado': _horn_call,
    'ferrao_ativo': _volley, 'rastro': _trail, 'arremesso': _sling,
    'farpas': _darts, 'estopim': _boom, 'iman': _magnet, 'carnica': _fang_drop,
    'ricochete': _bounce, 'casulo': _cocoon, 'marcado': _target,
    'contagio': _spread, 'retaguarda': _two_way, 'contragolpe': _deflect,
    'adrenalina': _pulse_line, 'sanguessuga': _leech, 'segundo': _second_wind,
    'espiral': _spiral,
    # playable characters
    'char_lagarto': _char_lagarto, 'char_vibora': _char_vibora,
    'char_couracado': _char_couracado, 'char_larva': _char_larva,
    # weapons
    'cuspe': _drop, 'ferrao': _arrow, 'ferrao_charm': _arrow,  # issue #25: charm vs weapon
    'teia': _star, 'esporos': _bubbles,
    'feromonio': _rings, 'sopro': _fan, 'enxame': _orbit, 'acido': _puddle,
    'torreta': _volley,          # the fan it plants, reusing the salva's darts
    # mutations / passives
    'health': _heart, 'speed': _bolt, 'dash': _arrow, 'energy': _bolt,
    'regen': _heart, 'xp': _star, 'tongue': _tongue, 'thorns': _spikes_icon,
    'spikes': _spikes_icon, 'plates': _plates_icon, 'horns': _horns_icon,
    'legs': _legs_icon, 'venom': _drop, 'wings': _wings_icon,   # 'club' -> charm-only (#22)
    'might': _bolt, 'area': _expand, 'haste': _clock, 'amount': _plus_one,
    'rebote': _bounce, 'rastreio': _target,      # #104 shot modifiers
    # charms
    'antenas': _antennae, 'olhos': _eyes, 'carapaca': _plates_icon,
    'asas': _wings_icon, 'nectar': _sac, 'glandula': _sac, 'presas': _fangs,
    'espinhos': _spikes_icon, 'clava': _club, 'dardo': _arrow,
    # boss emblems (rounds.draw_boss_bar) -- one recognisable mark per fight
    'boss_rei_lagarto': _boss_crown, 'boss_centopeiadeira': _boss_gear,
    'boss_kraken_mor': _boss_kraken_eye, 'boss_mae_escaravelho': _boss_hive,
    'boss_primordial': _boss_primordial_flame, 'boss_aranha_rei': _boss_web,
    'boss_serpente_cristal': _boss_crystal, 'boss_terror_alado': _boss_wing,
    'boss_olho_sismico': _boss_kraken_eye,   # an eye mark for the eye boss (reused)
    'boss_ankh': _boss_ankh,
}


def draw(surf, key, center, radius, color, glow=True):
    """Draw icon ``key`` centred at ``center`` with ``radius`` in ``color``.

    Tries the pixel-art PNG (Fase 7, ``assets/icons/``) first -- its colour is
    baked in per id, which is safe because every call site here passes the
    SAME fixed hue for a given id (a weapon/mutation/charm's own colour), never
    a per-instance tint. Falls back to the procedural drawer when no PNG ships
    (a stripped build, or an id with art not made yet) -- unknown ids never crash.
    """
    c = (int(center[0]), int(center[1]))
    r = int(radius)
    if glow:
        palette.glow(surf, c, r * 1.9, color, 0.35)
    png = assets.icon(key, r * 2)
    if png is not None:
        surf.blit(png, png.get_rect(center=c))
        return
    fn = ICONS.get(key)
    if fn is None:
        _disc(surf, c, r, color)
        return
    try:
        fn(surf, c, r, color)
    except Exception:
        _disc(surf, c, r, color)
