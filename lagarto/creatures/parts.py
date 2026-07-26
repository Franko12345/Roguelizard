"""Body-part drawing, driven by the genome.

Each function draws one appendage along a creature's spine, so the same code makes
an enemy look spiky and makes the player look spiky when it evolves. Everything is
built to read as *organic* (curved, tapered, alternating, gently swaying) rather
than geometric -- with a dark ink edge and a lighter rim to sit in the vivid style.
"""

import math
from pygame import Vector2
import pygame

from ..core import config as C
from ..core import palette
from ..core.mathutil import safe_norm, lerp
from ..anim.anim import PhaseOscillator


def _poly(surf, cam, pts, fill, edge_w=1):
    sp = cam.w2s_many(pts)
    if len(sp) >= 3:
        pygame.draw.polygon(surf, fill, sp)
        pygame.draw.polygon(surf, C.COL_INK, sp, max(1, int(edge_w * cam.zoom)))
    return sp


# --------------------------------------------------------------------------- #
# Per-part oscillator presets (issue #4 -- PhaseOscillator instances)          #
# --------------------------------------------------------------------------- #
# Every oscillating body part used to inline its own
# ``math.sin(creature.wobble * k + i * gap) * amp``. Each now reads from a
# PhaseOscillator on the creature, so per-species tuning is editing this table
# instead of hunting sin() calls through the draw code.
#
# The oscillators are driven by ``creature.wobble``, NOT by their own dt
# accumulator, which buys two things for free: the rate stays exactly what the
# inline sines had (wobble advances at dt*6, so a preset speed of 1.3 really is
# the old ``wobble * 1.3``), and creatures stay desynchronised, because wobble
# is seeded per creature at random. An oscillator ticking its own time from
# zero would put every creature's fins in lockstep.
OSC_PRESETS = {
    'spikes':     dict(speed=1.3, amplitude=0.18, phase_gap=0.5),
    'fins':       dict(speed=2.0, amplitude=0.30, phase_gap=1.0),
    'antennae':   dict(speed=3.0, amplitude=0.30, phase_gap=1.0),
    'wings':      dict(speed=7.0, amplitude=1.00, phase_gap=0.0),   # abs(sin) flap
    'spore_sacs': dict(speed=3.0, amplitude=0.16, phase_gap=1.0),
    'tail_ripple': dict(speed=2.2, amplitude=1.00, phase_gap=-0.9),  # wave runs tip->base
    'arms':       dict(speed=2.4, amplitude=1.00, phase_gap=-0.9),
}


def init_oscillators(creature):
    """Build the per-creature PhaseOscillator set.

    Called from ``Lizard.__init__`` and again from ``rebuild_body``, so a
    creature that mutates fins mid-run animates them. Idempotent: existing
    oscillators are kept so a rebuild does not reset a wave mid-swing.
    """
    existing = getattr(creature, 'osc', None) or {}
    creature.osc = {k: existing.get(k) or PhaseOscillator(**p)
                    for k, p in OSC_PRESETS.items()}


def update_oscillators(creature):
    """Point every oscillator at the creature's wobble clock.

    Called from ``Lizard.integrate`` after wobble advances. Sharing wobble is
    what keeps these byte-identical to the inline sines they replaced.
    """
    osc = getattr(creature, 'osc', None)
    if not osc:
        return
    for o in osc.values():
        o.time = creature.wobble


def _osc_offset(creature, key, i):
    """Read oscillator ``key`` at segment ``i``; 0.0 if the creature has none."""
    osc = getattr(creature, 'osc', None)
    if not osc or key not in osc:
        return 0.0
    return osc[key].offset(i)


def draw_spikes(surf, cam, creature):
    """Curved, tapered spines alternating left/right down the back."""
    g = creature.genome
    if g.spikes <= 0:
        return
    js = creature._cosmetic_joints() or creature.spine.joints
    rad = creature.spine.radii
    n = len(js)
    hi = palette.lighten(creature.color, 0.35)
    body = palette.lighten(creature.color, 0.05)
    length = creature.max_r * (0.9 + 0.35 * g.spikes)
    step = max(1, n // (5 + g.spikes * 2))
    side = 1
    for i in range(1, n - 2, step):
        fwd = safe_norm(js[i] - js[i + 1])
        back = -fwd
        perp = Vector2(-fwd.y, fwd.x) * side
        sway = _osc_offset(creature, 'spikes', i)
        base = js[i]
        base_a = base + fwd * (rad[i] * 0.42)
        base_b = base + back * (rad[i] * 0.42)
        tip = base + perp * (length * (1.0 + sway)) + back * (length * 0.45)
        mid = base + perp * (length * 0.55) + back * (length * 0.12)
        # tapered, slightly curved spine (base -> curved mid -> tip)
        _poly(surf, cam, [base_a, mid, tip, base_b], body, 1)
        pygame.draw.line(surf, hi, cam.w2s(base_b.lerp(tip, 0.15)),
                         cam.w2s(tip), max(1, int(cam.zoom)))
        side = -side


def draw_plates(surf, cam, creature):
    """Armour = overlapping scale chevrons pointing forward along the back."""
    g = creature.genome
    if g.plates <= 0:
        return
    js = creature._cosmetic_joints() or creature.spine.joints
    rad = creature.spine.radii
    edge = palette.lighten(creature.color, 0.28)
    w = max(1, int((1 + g.plates) * cam.zoom))
    ps = getattr(creature, 'plate_spring', None)     # A3 (#6): lean into accel
    tilt = ps.value if ps is not None else 0.0
    for i in range(1, len(js) - 1):
        fwd = safe_norm(js[i] - js[i + 1]).rotate(tilt)
        perp = Vector2(-fwd.y, fwd.x)
        c = js[i]
        left = c + perp * rad[i] * 0.72
        right = c - perp * rad[i] * 0.72
        tip = c + fwd * rad[i] * 0.55
        pygame.draw.lines(surf, edge, False,
                          [cam.w2s(left), cam.w2s(tip), cam.w2s(right)], w)


def draw_horns(surf, cam, creature):
    """Smooth, curved, tapered horns sweeping forward from the head.

    Bone-stiff, not hair: they sway a few degrees against a sharp turn (A3, #6)
    via ``horn_spring`` and settle fast -- momentum of a rigid mass, not a
    floppy lag.
    """
    g = creature.genome
    if g.horns <= 0:
        return
    head = creature.spine.joints[0]
    hs = getattr(creature, 'horn_spring', None)
    d = creature.spine.head_dir().rotate(hs.value if hs is not None else 0.0)
    perp = Vector2(-d.y, d.x)
    r = creature.max_r
    fill = palette.lighten(creature.color, 0.25)
    for k in range(min(g.horns, 3)):
        spread = 0.3 + k * 0.24
        for s in (-1, 1):
            base = head + perp * (s * r * spread) - d * (r * 0.05)
            out = safe_norm(d * 0.85 + perp * (s * 0.4))
            mid = base + out * (r * 0.72)
            tipdir = safe_norm(d * 0.95 - perp * (s * 0.12))
            tip = mid + tipdir * (r * 0.7)
            wv = perp * (s * r * 0.17)
            _poly(surf, cam, [base + wv, mid + wv * 0.5, tip, mid - wv * 0.5, base - wv],
                  fill, 1)
            pygame.draw.line(surf, palette.lighten(fill, 0.4),
                             cam.w2s(base + wv * 0.6), cam.w2s(tip), max(1, int(cam.zoom)))


def draw_plates_body_tint(surf, cam, creature):
    pass


def draw_tail(surf, cam, creature):
    """Special tail tips: club (heavy ball) or sting (scorpion hook)."""
    g = creature.genome
    if g.tail not in ('club', 'sting'):
        return
    js = creature._cosmetic_joints() or creature.spine.joints
    tail = js[-1]
    d = safe_norm(js[-1] - js[-2])
    r = creature.max_r
    if g.tail == 'club':
        c = tail + d * r * 0.5
        cc = cam.w2s(c)
        rr = max(3, int(r * 0.95 * cam.zoom))
        pygame.draw.circle(surf, palette.lighten(creature.color, 0.08), cc, rr)
        pygame.draw.circle(surf, C.COL_INK, cc, rr, max(1, int(cam.zoom)))
        # little knobs so it reads as a mace, not a ball
        for a in range(0, 360, 60):
            k = c + Vector2(math.cos(math.radians(a)), math.sin(math.radians(a))) * r * 0.9
            pygame.draw.circle(surf, palette.lighten(creature.color, 0.25),
                               cam.w2s(k), max(1, int(r * 0.22 * cam.zoom)))
    else:  # sting
        base = tail
        curl = safe_norm(d + Vector2(-d.y, d.x) * 0.9)
        hook = tail + curl * r * 1.1
        tip = hook + safe_norm(Vector2(-d.y, d.x) * 0.4 - d) * r * 0.6
        col = palette.lighten(creature.color, 0.2)
        pygame.draw.line(surf, col, cam.w2s(base), cam.w2s(hook), max(2, int(r * 0.32 * cam.zoom)))
        pygame.draw.line(surf, col, cam.w2s(hook), cam.w2s(tip), max(2, int(r * 0.24 * cam.zoom)))
        pygame.draw.circle(surf, (255, 120, 130), cam.w2s(tip), max(2, int(r * 0.28 * cam.zoom)))


def draw_fins(surf, cam, creature):
    """Soft translucent fins along the sides (fish/aquatic)."""
    g = creature.genome
    if g.fins <= 0:
        return
    js = creature._cosmetic_joints() or creature.spine.joints
    rad = creature.spine.radii
    col = palette.lighten(creature.color, 0.3)
    n = len(js)
    for i in (n // 3, 2 * n // 3):
        if i + 1 >= n:
            continue
        fwd = safe_norm(js[i] - js[i + 1])
        perp = Vector2(-fwd.y, fwd.x)
        wob = _osc_offset(creature, 'fins', i)
        for s in (-1, 1):
            b1 = js[i] + perp * (s * rad[i])
            b2 = js[i + 1] + perp * (s * rad[i + 1])
            tip = js[i] + perp * (s * rad[i] * (2.3 + wob * s)) - fwd * rad[i]
            _poly(surf, cam, [b1, tip, b2], col, 1)


# --------------------------------------------------------------------------- #
#  Charm-driven parts (antennae, wings, extra eyes, spore sacs, nectar, fangs) #
# --------------------------------------------------------------------------- #

def draw_antennae(surf, cam, creature):
    head = creature.spine.joints[0]
    d = creature.spine.head_dir()
    perp = Vector2(-d.y, d.x)
    r = creature.max_r
    col = palette.darken(creature.color, 0.3)
    for s in (-1, 1):
        base = head + d * (r * 0.2) + perp * (s * r * 0.35)
        wig = _osc_offset(creature, 'antennae', s)
        mid = base + d * (r * 0.9) + perp * (s * r * (0.5 + wig))
        tip = mid + d * (r * 0.5) + perp * (s * r * (0.8 + wig))
        pygame.draw.line(surf, col, cam.w2s(base), cam.w2s(mid), max(1, int(2 * cam.zoom)))
        pygame.draw.line(surf, col, cam.w2s(mid), cam.w2s(tip), max(1, int(cam.zoom)))
        pygame.draw.circle(surf, palette.lighten(creature.color, 0.4), cam.w2s(tip),
                           max(1, int(2 * cam.zoom)))


def draw_wings(surf, cam, creature):
    js, rad = creature.spine.joints, creature.spine.radii
    i = max(1, len(js) // 4)
    if i + 1 >= len(js):
        return
    fwd = safe_norm(js[i] - js[i + 1])
    perp = Vector2(-fwd.y, fwd.x)
    flap = 0.5 + 0.5 * abs(_osc_offset(creature, 'wings', 0))
    col = palette.lighten(creature.color, 0.4)
    for s in (-1, 1):
        b1 = js[i] + perp * (s * rad[i] * 0.9)
        tip = js[i] + perp * (s * rad[i] * (2.7 * flap)) - fwd * rad[i] * 1.3
        b2 = js[i] - fwd * rad[i] * 1.9 + perp * (s * rad[i] * 0.7)
        _poly(surf, cam, [b1, tip, b2], col, 1)


def draw_extra_eyes(surf, cam, creature):
    n = creature.genome.extra_eyes
    head = creature.spine.joints[0]
    d = creature.spine.head_dir()
    perp = Vector2(-d.y, d.x)
    r = creature.max_r
    look = creature._pupil_offset()
    for k in range(n):
        s = -1 if k % 2 == 0 else 1
        row = k // 2
        ep = head + d * (r * (0.05 + row * 0.22)) + perp * (s * r * 0.38)
        pygame.draw.circle(surf, C.COL_WHITE, cam.w2s(ep), max(1, int(r * 0.24 * cam.zoom)))
        pygame.draw.circle(surf, C.COL_INK, cam.w2s(ep + look * (r * 0.08)),
                           max(1, int(r * 0.12 * cam.zoom)))


def draw_spore_sacs(surf, cam, creature):
    js, rad = creature.spine.joints, creature.spine.radii
    col = palette.vibrant(135, 0.7, 0.92)
    for i in range(2, len(js) - 2, 3):
        pu = 1 + _osc_offset(creature, 'spore_sacs', i)
        p = cam.w2s(js[i])
        rr = max(2, int(rad[i] * 0.5 * cam.zoom * pu))
        palette.glow(surf, p, rr * 2, col, 0.4)
        pygame.draw.circle(surf, col, p, rr)
        pygame.draw.circle(surf, C.COL_INK, p, rr, max(1, int(cam.zoom)))


def draw_nectar_sac(surf, cam, creature):
    js = creature.spine.joints
    tail = js[-1]
    d = safe_norm(js[-1] - js[-2])
    r = creature.max_r
    cc = cam.w2s(tail + d * r * 0.4)
    rr = max(2, int(r * 0.7 * cam.zoom))
    col = palette.vibrant(45, 0.85, 1.0)
    palette.glow(surf, cc, rr * 2, col, 0.5)
    pygame.draw.circle(surf, col, cc, rr)
    pygame.draw.circle(surf, palette.lighten(col, 0.4), cc, max(1, int(rr * 0.4)))
    pygame.draw.circle(surf, C.COL_INK, cc, rr, max(1, int(cam.zoom)))


def draw_fangs(surf, cam, creature):
    head = creature.spine.joints[0]
    d = creature.spine.head_dir()
    perp = Vector2(-d.y, d.x)
    r = creature.max_r
    for s in (-1, 1):
        base = head + d * (r * 0.7) + perp * (s * r * 0.28)
        tip = base + d * (r * 0.55) - perp * (s * r * 0.04)
        pygame.draw.line(surf, (245, 245, 252), cam.w2s(base), cam.w2s(tip),
                         max(1, int(2.4 * cam.zoom)))


def draw_all(surf, cam, creature):
    """Draw every part the genome declares (called from Creature.draw)."""
    g = creature.genome
    if g.wings:
        draw_wings(surf, cam, creature)
    if g.plates:
        draw_plates(surf, cam, creature)
    if g.spore_sacs:
        draw_spore_sacs(surf, cam, creature)
    if g.fins:
        draw_fins(surf, cam, creature)
    if g.spikes:
        draw_spikes(surf, cam, creature)
    if g.tail in ('club', 'sting'):
        draw_tail(surf, cam, creature)
    if g.nectar_sac:
        draw_nectar_sac(surf, cam, creature)
    if g.horns:
        draw_horns(surf, cam, creature)
    if g.antennae:
        draw_antennae(surf, cam, creature)
    if g.extra_eyes:
        draw_extra_eyes(surf, cam, creature)
    if g.fangs:
        draw_fangs(surf, cam, creature)
