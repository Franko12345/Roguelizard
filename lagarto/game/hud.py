"""Pure HUD drawing primitives -- no game state, no ``game`` argument.

Everything here is a function of ``(surf, ...)`` plus plain numbers/colours, so
it can be called from any state module without dragging the state machine in.
Anything that has to *read* the run (player health, wave, combo) belongs in the
state module that draws it, not here.

The ``CapsuleSpring`` and ``PlayerCapsule`` types live here too -- they are
HUD-specific state, owned by the player capsule (the framed panel that holds
vitals + dials), not by the run. See ``docs/concepts/hud-anatomy.md`` for the
metaphor and the budget.
"""

import math

import pygame
from pygame import Vector2

from ..core import config as C
from ..core.mathutil import decay, pulse, vfrom_angle
from ..core import palette
from ..render import ui


def bar_tail(surf, bx, by, h, color, phase, t):
    """A little lizard TAIL wagging off the top of the bar.

    Same vocabulary as the real body (``spine.RADII_PROFILE``): a curved chain
    that tapers to a point, not a stick with a bead on the end. Drawn as a run of
    filled circles shrinking base->tip; the sway grows toward the tip so the last
    segments whip like a follow-through.
    """
    n = 9
    length = h * 1.5                       # long and whippy, still clears the label row
    r0 = max(2.0, h * 0.32)                # slimmer root than a leaf
    core = palette.lighten(color, 0.3)
    for k in range(n):
        f = k / (n - 1)
        py = by - f * length
        # tip sways most; a phase per tail so they don't wag in unison
        px = bx + math.sin(t * 3.4 + phase + f * 2.6) * (h * 0.62) * f * f
        r = max(1, int(r0 * (1.0 - f) ** 1.3 + 0.8))   # curved taper -> pointed tip
        pygame.draw.circle(surf, color, (int(px), int(py)), r)
        if r > 2:                                   # top-left highlight = light source
            pygame.draw.circle(surf, core,
                               (int(px - r * 0.3), int(py - r * 0.3)), max(1, r // 2))


def bio_bar(surf, x, y, w, h, frac, color, t, flagella=0, glow=None):
    """An organic 'membrane sac' bar instead of a flat rectangle.

    Drawn entirely with primitives (no per-frame Surface -- the ui._tint rule),
    animated purely by ``t`` so it costs the same whether it moves or not:
      * a dark rounded capsule (the sac),
      * a fill whose leading edge bulges and breathes,
      * a soft inner highlight up top (a light source), and
      * optional flagella -- little cilia that sway off the fill's leading edge,
        which is what sells "biological" at a glance.
    """
    frac = 0.0 if frac < 0 else (1.0 if frac > 1 else frac)
    r = h // 2
    cap = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, (16, 18, 28), cap, border_radius=r)
    fw = int(w * frac)
    if fw > 1:
        fill = pygame.Rect(x, y, fw, h)
        pygame.draw.rect(surf, palette.darken(color, 0.25), fill, border_radius=r)
        # top meniscus: a lighter band with a slow breathing wobble
        band_h = max(2, h // 3)
        pygame.draw.rect(surf, palette.lighten(color, 0.35),
                         (x, y + 1, fw, band_h), border_radius=r)
        # leading-edge bulge, pulsing -- reads as fluid under pressure
        bulge = int(h * (0.55 + 0.12 * math.sin(t * 3.0)))
        tip = (x + fw, y + h // 2)
        palette.glow(surf, tip, bulge, color, 0.5)
        pygame.draw.circle(surf, palette.lighten(color, 0.5), tip, max(2, h // 3))
        for k in range(flagella):
            fx = x + int(fw * (k + 0.5) / max(1, flagella))
            bar_tail(surf, fx, y + 1, h, color, phase=k * 2.1, t=t)
    if glow:
        palette.glow(surf, (x + fw, y + h // 2), h, color, 0.25)
    # living rim
    pygame.draw.rect(surf, palette.lighten(color, 0.15) if frac > 0 else (40, 44, 60),
                     cap, 2, border_radius=r)


def dial(surf, center, r, frac, color, font, label, t, enabled=True):
    """Radial cooldown dial: fills as the ability recharges, pulses when ready.

    ``enabled=False`` (not enough energy) greys the whole thing out.
    """
    ready = frac >= 0.999 and enabled
    if not enabled:
        color = (78, 82, 104)
    pygame.draw.circle(surf, (34, 38, 54), center, r)
    if frac > 0:
        pts = [center]
        steps = max(3, int(frac * 22))
        for i in range(steps + 1):
            pts.append(center + vfrom_angle(-90 + 360 * frac * (i / steps), r))
        if len(pts) >= 3:
            pygame.draw.polygon(surf, color, pts)
    if ready:
        palette.glow(surf, center, r * 2.2, color, 0.35 + 0.25 * pulse(t, 6))
    pygame.draw.circle(surf, (96, 102, 136) if not ready else color, center, r, 2)
    ui.text(surf, font, label, (center[0] + r + 6, center[1] - font.get_height() // 2),
            (232, 234, 250) if ready else (146, 150, 178))


_VIGNETTE = None


def vignette(surf):
    """Smooth radial dark edges so the vivid centre pops (built once, then blitted)."""
    global _VIGNETTE
    if _VIGNETTE is None:
        s = 80
        small = pygame.Surface((s, s), pygame.SRCALPHA)
        cx = cy = (s - 1) / 2.0
        maxd = (cx * cx + cy * cy) ** 0.5
        for y in range(s):
            for x in range(s):
                d = (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / maxd
                a = 0 if d < 0.4 else int(150 * ((d - 0.4) / 0.6) ** 2)
                small.set_at((x, y), (0, 0, 0, min(150, a)))
        _VIGNETTE = pygame.transform.smoothscale(small, (C.WIDTH, C.HEIGHT))
    surf.blit(_VIGNETTE, (0, 0))


def draw_offscreen(surf, targets, cam, limit=22):
    """Edge arrows pointing at things you can't see -> find stragglers.

    ``targets`` is a sequence of ``(world_pos, colour)``; picking *what* deserves
    an arrow is the caller's business.
    """
    cx, cy = C.WIDTH / 2, C.HEIGHT / 2
    hw, hh = cx - 28, cy - 28
    shown = 0
    for pos, col in targets:
        sp = cam.w2s(pos)
        if -12 < sp[0] < C.WIDTH + 12 and -12 < sp[1] < C.HEIGHT + 12:
            continue
        d = Vector2(sp[0] - cx, sp[1] - cy)
        if d.length_squared() < 1:
            continue
        scale = min(hw / abs(d.x) if d.x else 1e9, hh / abs(d.y) if d.y else 1e9)
        c = Vector2(cx, cy) + d * scale
        ang = d.as_polar()[1]
        tip = c + vfrom_angle(ang, 12)
        b1 = c + vfrom_angle(ang + 138, 10)
        b2 = c + vfrom_angle(ang - 138, 10)
        palette.glow(surf, (int(c.x), int(c.y)), 16, col, 0.5)
        pygame.draw.polygon(surf, col, [tip, b1, b2])
        pygame.draw.polygon(surf, C.COL_INK, [tip, b1, b2], 1)
        shown += 1
        if shown >= limit:
            break


class TopStack:
    """Vertical layout for the top-centre column.

    Six things live there -- score, wave line, combo, theme banner, boss name and
    boss bar -- and each used to hardcode its own ``y`` with no idea of the others.
    On a boss wave with a live combo that was *three* overlaps at once, and the
    banner writes for 2.2s exactly when the boss spawns, so it was guaranteed to
    be seen. Now every element asks for the height it needs and gets the next free
    band, which also means new elements (boss phase bars, Phase 4) can never
    silently land on top of an existing one.

    Elements reserve in draw order, so the caller must draw top-down: HUD, then
    banner, then boss bar.
    """

    def __init__(self, top=10, gap=4):
        self.top = top
        self.gap = gap
        self.y = top

    def reset(self):
        self.y = self.top

    def take(self, h):
        """Reserve a band ``h`` tall and return its top ``y``."""
        y = self.y
        self.y += h + self.gap
        return y


class CapsuleSpring:
    """Low-frequency mass-spring-damper for the player HUD capsule.

    The capsule is "massa rigida" in the HUD-anatomy metaphor -- it has its own
    overshoot on entry and its own tremble on damage / value change. The organs
    inside (bars, dials) animate on their own, faster rhythms; the spring gives
    the player something to read as "the container reacted" without naming which
    organ moved.

    State is a 2D displacement from the resting offset (0, 0). One impulse at
    a time -- a damage hit AND a value change in the same frame sum into one
    impulse, capped by ``HUD_SHAKE_HP``. The tremble itself is a separate sine
    added on top of the spring displacement, gated by ``HUD_SHAKE_DUR``.
    """

    __slots__ = ('x', 'y', 'vx', 'vy', 'shake_t', 'shake_amp')

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.shake_t = 0.0
        self.shake_amp = 0.0

    def impulse(self, ax, ay):
        self.vx += ax
        self.vy += ay

    def start_shake(self, amp):
        """Start (or raise) a decaying sinusoidal shake of peak amplitude ``amp`` px."""
        self.shake_amp = max(self.shake_amp, amp)
        self.shake_t = C.HUD_SHAKE_DUR

    def update(self, dt):
        # Semi-implicit Euler at 60 Hz is stable for k=38, c=9 -- the system is
        # overdamped (c^2 > 4*k*m with m=1), so no z-plane is needed and the
        # spring returns to rest without ringing forever.
        ax = -C.HUD_SPRING_K * self.x - C.HUD_SPRING_C * self.vx
        ay = -C.HUD_SPRING_K * self.y - C.HUD_SPRING_C * self.vy
        self.vx += ax * dt
        self.vy += ay * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.shake_t = decay(self.shake_t, dt)

    def settle_error(self):
        """Max of |x| and |y| -- how far the spring is from rest. Used by the
        check to assert the capsule actually settles after an impulse."""
        return max(abs(self.x), abs(self.y))

    def offset(self, t):
        """(ox, oy) pixel offset to add to the panel's resting rect."""
        ox, oy = self.x, self.y
        if self.shake_t > 0 and self.shake_amp > 0.01:
            # linear decay of the envelope; the sine runs on game.time so the
            # tremor stays phase-locked to the player, not the frame.
            f = self.shake_t / C.HUD_SHAKE_DUR
            ox += math.sin(t * 56.0) * self.shake_amp * f
            oy += math.cos(t * 47.0) * self.shake_amp * f * 0.6
        return ox, oy


class PlayerCapsule:
    """Per-player HUD state: the panel spring plus last-frame vitals.

    ``last`` is what the capsule compares against to detect a value change
    inside the panel. ``spring`` is the CapsuleSpring for the panel position.
    Initialised empty -- the state module fills it in on the first frame.
    """

    __slots__ = ('spring', 'last_hp', 'last_energy', 'last_xp', 'last_ability')

    def __init__(self):
        self.spring = CapsuleSpring()
        self.last_hp = None
        self.last_energy = None
        self.last_xp = None
        self.last_ability = None


def detect_changes(capsule, player):
    """Compare the player's current vitals to the capsule's last frame and fire
    shakes on the spring when they differ. Returns True if anything moved -- the
    caller can use this to drive per-organ animations later."""
    anything = False
    last = capsule.last_hp
    if last is not None and player.health < last - 0.5:
        # damage: stronger tremble, direction taken from the hit normal if the
        # caller left one on the player; default is straight down
        capsule.spring.start_shake(C.HUD_SHAKE_HP)
        anything = True
    elif last is not None and player.health > last + 0.5:
        capsule.spring.start_shake(C.HUD_SHAKE_VALUE)
        anything = True
    capsule.last_hp = player.health

    last = capsule.last_energy
    if last is not None and abs(player.energy - last) > 0.6:
        capsule.spring.start_shake(C.HUD_SHAKE_VALUE * 0.7)
        anything = True
    capsule.last_energy = player.energy

    last = capsule.last_xp
    if last is not None and player.xp > last + 0.5:
        capsule.spring.start_shake(C.HUD_SHAKE_VALUE * 0.7)
        anything = True
    capsule.last_xp = player.xp

    last = capsule.last_ability
    if last is not None and (player.ability_charge >= 1.0) != (last >= 1.0):
        # crossing the "ready" threshold is the loudest value change in the
        # panel -- a different shake amplitude so the player can tell which
        # organ flipped.
        capsule.spring.start_shake(C.HUD_SHAKE_HP * 0.6)
        anything = True
    capsule.last_ability = player.ability_charge
    return anything
