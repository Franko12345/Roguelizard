"""Pure HUD drawing primitives -- no game state, no ``game`` argument.

Everything here is a function of ``(surf, ...)`` plus plain numbers/colours, so
it can be called from any state module without dragging the state machine in.
Anything that has to *read* the run (player health, wave, combo) belongs in the
state module that draws it, not here.

The ``CapsuleSpring`` and ``PlayerCapsule`` types live here too. Why they live
with the drawing primitives even though they are mutable state:

- A capsule IS a visual element + its tiny local anim state. Splitting the
  spring into its own module would force every drawing call to thread both
  shape arguments and a separate animation object, doubling the call sites
  with no benefit.
- Only the *drawing primitives* (bio_bar, dial, vignette, draw_offscreen,
  TopStack) stay pure. The mutable types here are the HUD's own bookkeeping,
  not game state.
- The amount of mutable state is one ``CapsuleSpring`` per capsule per
  player, with no global lookup. The conventional alternative (put it on
  the Game class) couples the spring's physics to the whole run object and
  prevents reusing ``CapsuleSpring.update`` from a sandbox or a check.

See ``docs/concepts/hud-anatomy.md`` for the metaphor and the budget.
"""

import math

import pygame
from pygame import Vector2

from ..core import config as C
from ..core.mathutil import decay, pulse, vfrom_angle
from ..core import palette
from ..render import ui


HEALTH_SAC_HP = 25.0
HEALTH_SACS_PER_ROW = 8
HEALTH_SAC_MAX_ROWS = 2
HEALTH_SAC_SIZE = 18
HEALTH_SAC_GAP = 4


def health_sac_fills(health, max_health):
    count = max(1, math.ceil(max(0.0, max_health) / HEALTH_SAC_HP))
    remaining = max(0.0, min(float(health), float(max_health)))
    return [max(0.0, min(1.0, (remaining - i * HEALTH_SAC_HP) / HEALTH_SAC_HP))
            for i in range(count)]


def health_sac_layout(max_health, width):
    count = max(1, math.ceil(max(0.0, max_health) / HEALTH_SAC_HP))
    rows = min(HEALTH_SAC_MAX_ROWS, math.ceil(count / HEALTH_SACS_PER_ROW))
    columns = math.ceil(count / rows)
    size = min(HEALTH_SAC_SIZE, (width - HEALTH_SAC_GAP * (columns - 1)) / columns)
    return count, rows, columns, max(6.0, size)


def health_panic_rate(frac):
    frac = max(0.0, min(1.0, frac))
    return 2.2 + (1.0 - frac) * 7.8


def health_sacs_bounds(x, y, max_health, width):
    count, rows, columns, size = health_sac_layout(max_health, width)
    used_columns = min(columns, count)
    used_width = used_columns * size + max(0, used_columns - 1) * HEALTH_SAC_GAP
    used_height = rows * size + max(0, rows - 1) * HEALTH_SAC_GAP
    return pygame.Rect(x, y - used_height + size, math.ceil(used_width), math.ceil(used_height))


def _draw_artery(surf, centers, color):
    if len(centers) < 2:
        return
    root = palette.darken(color, 0.35)
    for a, b in zip(centers, centers[1:]):
        distance = Vector2(b).distance_to(a)
        steps = max(2, int(distance / 3))
        for step in range(steps + 1):
            f = step / steps
            p = Vector2(a).lerp(b, f)
            pygame.draw.circle(surf, root, (round(p.x), round(p.y)), max(1, round(2.4 - f)))


def draw_health_sacs(surf, x, y, width, health, max_health, t, impact=0.0):
    fills = health_sac_fills(health, max_health)
    count, rows, columns, size = health_sac_layout(max_health, width)
    frac = max(0.0, min(1.0, health / max(0.001, max_health)))
    panic = 1.0 - frac
    rate = health_panic_rate(frac)
    beat = (0.5 + 0.5 * math.sin(t * rate)) * panic
    color = palette.mix((148, 54, 62), (255, 42, 58), min(1.0, panic * 0.85 + beat * 0.35))
    row_counts = [min(columns, count - row * columns) for row in range(rows)]
    centers = []
    positions = []
    index = 0
    for row in range(rows):
        row_width = row_counts[row] * size + max(0, row_counts[row] - 1) * HEALTH_SAC_GAP
        row_x = x + (width - row_width) / 2
        cy = y - row * (size + HEALTH_SAC_GAP) + size / 2
        row_centers = []
        for column in range(row_counts[row]):
            cx = row_x + column * (size + HEALTH_SAC_GAP) + size / 2
            sway = math.sin(t * 4.1 + index * 1.7) * impact * (1.5 + row * 0.5)
            row_centers.append((cx, cy + sway))
            positions.append((cx, cy + sway, index))
            index += 1
        centers.append(row_centers)
    for row_centers in centers:
        _draw_artery(surf, row_centers, color)
    shell = (52, 30, 38)
    empty = (25, 20, 29)
    rim = palette.lighten(color, 0.12)
    active = next((i for i, fill in enumerate(fills) if fill < 1.0), count - 1)
    for cx, cy, index in positions:
        fill = fills[index]
        neighbour = max(0.0, 1.0 - abs(index - active) / 2.0)
        bulge = impact * neighbour * 1.8 + beat * 0.8
        radius = max(3, round(size * 0.42 + bulge))
        center = (round(cx), round(cy))
        pygame.draw.circle(surf, shell, center, radius + 1)
        pygame.draw.circle(surf, empty, center, radius)
        if fill > 0:
            fluid_h = max(1, round(radius * 2 * fill))
            pygame.draw.circle(surf, color, center, radius)
            empty_h = radius * 2 - fluid_h
            if empty_h > 0:
                cover = pygame.Rect(center[0] - radius - 1, center[1] - radius - 1,
                                    radius * 2 + 2, empty_h + 1)
                pygame.draw.rect(surf, empty, cover)
            meniscus = pygame.Rect(center[0] - radius, center[1] + radius - fluid_h - 1,
                                   radius * 2, max(2, min(4, fluid_h)))
            pygame.draw.ellipse(surf, palette.lighten(color, 0.12), meniscus)
            if count <= 16 or index in {active - 1, active, active + 1}:
                pygame.draw.circle(surf, palette.lighten(color, 0.55),
                                   (center[0] - radius // 3, center[1] - radius // 3),
                                   max(1, radius // 4))
        else:
            residue = pygame.Rect(center[0] - radius // 2, center[1] + radius // 2,
                                  radius, max(1, radius // 4))
            pygame.draw.ellipse(surf, palette.darken(color, 0.55), residue)
        pygame.draw.circle(surf, rim if fill > 0 else (68, 48, 58), center, radius, 1)
        if panic > 0.55 and beat > 0.6 and index in {active - 1, active}:
            palette.glow(surf, center, radius * 2, color, 0.18 + beat * 0.12)


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


class Bellows:
    def __init__(self, fraction=1.0):
        self.fraction = fraction
        self.velocity = 0.0

    def update(self, target, dt):
        target = max(0.0, min(1.0, target))
        self.velocity += (target - self.fraction) * 110.0 * dt
        self.velocity *= math.exp(-12.0 * dt)
        self.fraction += self.velocity * dt
        self.fraction = max(0.0, min(1.08, self.fraction))


def draw_bellows(surf, rect, bellows, color=(96, 206, 240)):
    x, y, w, h = rect
    inflation = max(0.0, min(1.0, bellows.fraction))
    body_h = max(8, int(h * (0.42 + 0.58 * inflation)))
    top = y + (h - body_h) // 2
    body = pygame.Rect(x, top, w, body_h)
    pygame.draw.ellipse(surf, (16, 18, 28), body)
    inner = body.inflate(-4, -4)
    if inner.width > 0 and inner.height > 0:
        pygame.draw.ellipse(surf, palette.darken(color, 0.22), inner)
    folds = 7
    for i in range(1, folds):
        fx = x + int(w * i / folds)
        inset = int(2 + (1.0 - inflation) * 5)
        pygame.draw.line(surf, palette.lighten(color, 0.2),
                         (fx, top + inset), (fx, top + body_h - inset), 1)
    pygame.draw.ellipse(surf, palette.lighten(color, 0.18), body, 2)


class CranialFluid:
    POINTS = 16
    STEP = 1.0 / 30.0

    def __init__(self):
        self.heights = [0.0] * self.POINTS
        self.velocities = [0.0] * self.POINTS
        self.accumulator = 0.0
        self.last_fraction = 0.0

    def impulse(self, strength):
        mid = self.POINTS // 2
        self.velocities[mid] += strength
        self.velocities[mid - 1] += strength * 0.55

    def update(self, fraction, dt):
        fraction = max(0.0, min(1.0, fraction))
        delta = fraction - self.last_fraction
        if abs(delta) > 0.001:
            self.impulse(delta * 7.0)
        self.last_fraction = fraction
        self.accumulator += min(dt, 0.1)
        while self.accumulator >= self.STEP:
            accelerations = []
            for i, height in enumerate(self.heights):
                left = self.heights[i - 1] if i else height
                right = self.heights[i + 1] if i + 1 < self.POINTS else height
                accelerations.append((left + right - 2.0 * height) * 72.0)
            for i in range(self.POINTS):
                self.velocities[i] += accelerations[i] * self.STEP
                self.velocities[i] *= math.exp(-5.5 * self.STEP)
                self.heights[i] += self.velocities[i] * self.STEP
            self.accumulator -= self.STEP

    @property
    def amplitude(self):
        return max(abs(height) for height in self.heights)


def brain_size(level):
    return min(0.72, 0.42 + 0.045 * math.sqrt(max(0, level - 1)))


def brain_folds(level):
    return max(1, level * 2 - 1)


def draw_skull(surf, rect, level, xp_fraction, fluid):
    x, y, w, h = rect
    skull = pygame.Rect(x, y, w, h)
    bone = (210, 204, 176)
    pygame.draw.ellipse(surf, (18, 20, 30), skull)
    fluid_y = y + h - 4 - int((h - 8) * max(0.0, min(1.0, xp_fraction)))
    points = [(x + 3, y + h - 3)]
    for i, wave in enumerate(fluid.heights):
        px = x + 3 + (w - 6) * i / (fluid.POINTS - 1)
        points.append((px, fluid_y + wave * h * 0.18))
    points.append((x + w - 3, y + h - 3))
    if xp_fraction > 0:
        pygame.draw.polygon(surf, (174, 141, 38), points)
        pygame.draw.lines(surf, (245, 205, 84), False, points[1:-1], 2)
    size = brain_size(level)
    bw = int(w * size)
    bh = int(h * size * 0.68)
    brain = pygame.Rect(x + (w - bw) // 2, y + 5, bw, bh)
    pygame.draw.ellipse(surf, (190, 98, 132), brain)
    folds = brain_folds(level)
    for i in range(folds):
        angle = math.pi * (i + 1) / (folds + 1)
        cx = brain.centerx + int(math.cos(angle) * bw * 0.35)
        cy = brain.centery + int(math.sin(angle * 2.0) * bh * 0.18)
        pygame.draw.arc(surf, (112, 51, 82), (cx - 3, cy - 7, 7, 14),
                        -math.pi / 2, math.pi / 2, 1)
    pygame.draw.ellipse(surf, bone, skull, 2)


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
    """Low-frequency mass-spring-damper for one HUD capsule (the framed panel).

    The capsule is "massa rigida" in the HUD-anatomy metaphor -- it has its own
    overshoot on entry and its own tremble on damage / value change. The organs
    inside (bars, dials) animate on their own, faster rhythms; the spring gives
    the player something to read as "the container reacted" without naming which
    organ moved.

    State is a 2D displacement from the resting offset (0, 0) plus a decaying
    sinusoidal shake on top (the tremble). The two run at different scales:

    - Spring (mass-spring-damper) is stepped at ``C.HUD_SIM_HZ`` and rendered
      with linear interpolation between the prev and cur sub-step positions.
      30 Hz (instead of 60) halves the simulation cost -- the issue calls it
      out as the first knob. Render still shows a smooth glide because the
      offset interpolates between sub-steps each render frame.
    - Shake (sine envelope) runs on the wall clock, ticking every render
      frame at ``game.time`` so the tremor stays phase-locked to the player.
      Amplitude is gated by what's currently *visible* (envelope * amp), so a
      fresh small impulse never inherits the loudness of a prior large one.
    """

    __slots__ = ('x', 'y', 'vx', 'vy', 'prev_x', 'prev_y', '_sim_acc',
                 'shake_t', 'shake_amp')

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.prev_x = 0.0
        self.prev_y = 0.0
        self._sim_acc = 0.0
        self.shake_t = 0.0
        self.shake_amp = 0.0

    def impulse(self, ax, ay):
        """Add a velocity impulse -- multiple in one frame sum naturally."""
        self.vx += ax
        self.vy += ay

    def start_shake(self, amp):
        """Add (or upgrade) a decaying sinusoidal shake of peak ``amp`` px.

        Only upgrades ``shake_amp`` if the new impulse is louder than what's
        currently *visible* -- the raw amplitude multiplied by the remaining
        envelope. This is what stops a damage shake from sticking at its
        loudness across later value-change events.
        """
        dur = C.HUD_SHAKE_DUR
        f = self.shake_t / dur if dur > 0 else 0.0
        visible = self.shake_amp * f
        if amp > visible:
            self.shake_amp = amp
        self.shake_t = dur

    def update(self, frame_dt):
        """Advance the spring to the next frame, stepping at 30 Hz internally.

        Frame_dt is the wall-clock frame delta. The accumulator collects it and
        runs as many fixed 30 Hz sub-steps as fit. ``prev_x/y`` snapshot the
        position before the latest sub-step so render-time can interpolate.
        The shake envelope always ticks on every call -- it is not pegged to
        the sub-step grid because the perceived tremble is render-rate.
        """
        if frame_dt <= 0:
            return
        step_dt = 1.0 / C.HUD_SIM_HZ
        self._sim_acc += frame_dt
        # cap the accumulator at one sub-step: a long pause (hit-stop, drop)
        # does not double-run the spring -- the slow container is invisible
        # anyway, and back-filling tears the interpolation.
        if self._sim_acc > step_dt:
            self._sim_acc = step_dt
        while self._sim_acc >= step_dt and step_dt > 0:
            self.prev_x = self.x
            self.prev_y = self.y
            self._step(step_dt)
            self._sim_acc -= step_dt
        # The envelope is a render-side signal; it ticks every frame.
        self.shake_t = decay(self.shake_t, frame_dt)

    def _step(self, dt):
        # Semi-implicit Euler at 30 Hz is stable for k=38, c=9. The system is
        # under-damped (c < 2*sqrt(k*m)) -- which is what produces the issue's
        # "entra com overshoot" on entry, then settles within ~0.7s. A z-plane
        # eigenvalue check would be over-engineering for a 1-DOF spring.
        ax = -C.HUD_SPRING_K * self.x - C.HUD_SPRING_C * self.vx
        ay = -C.HUD_SPRING_K * self.y - C.HUD_SPRING_C * self.vy
        self.vx += ax * dt
        self.vy += ay * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    def settle_error(self):
        """Max of |x| and |y| -- how far the spring is from rest. Used by the
        check to assert the capsule actually settles after an impulse."""
        return max(abs(self.x), abs(self.y))

    def render_offset(self, t):
        """Render-time (ox, oy) offset. Linearly interpolates between the prev
        and cur 30 Hz sub-step positions so the glide stays smooth when render
        runs at 60 fps but the spring steps at 30."""
        step_dt = 1.0 / C.HUD_SIM_HZ
        if step_dt > 0:
            alpha = self._sim_acc / step_dt
            alpha = 0.0 if alpha < 0.0 else (1.0 if alpha > 1.0 else alpha)
        else:
            alpha = 1.0
        ox = self.prev_x + (self.x - self.prev_x) * alpha
        oy = self.prev_y + (self.y - self.prev_y) * alpha
        if self.shake_t > 0 and self.shake_amp > 0.01:
            # linear decay of the envelope; the sine runs on game.time so the
            # tremor stays phase-locked to the player, not the frame.
            f = self.shake_t / C.HUD_SHAKE_DUR
            ox += math.sin(t * 56.0) * self.shake_amp * f
            oy += math.cos(t * 47.0) * self.shake_amp * f * 0.6
        return ox, oy


class PlayerCapsule:
    """Per-player HUD state: TWO CapsuleSprings (vitais + cooldowns) plus last-frame vitals.

    Two springs because the issue's anatomy dictates two capsules -- the vitals
    frame and the cooldowns frame are distinct rectangles and have their own
    physics. Both still share the last-frame vitals so ``detect_changes`` only
    compares against the player once.

    Initialised empty -- the state module fills in the first frame. The state
    module also calls ``entry_overshoot`` once on entry to play so the spring
    kicks on the first render frame instead of needing to be primed.
    """

    __slots__ = ('vitals_spring', 'cooldowns_spring',
                 'last_hp', 'last_energy', 'last_xp', 'last_ability')

    def __init__(self):
        self.vitals_spring = CapsuleSpring()
        self.cooldowns_spring = CapsuleSpring()
        self.last_hp = None
        self.last_energy = None
        self.last_xp = None
        self.last_ability = None

    def entry_overshoot(self, player_index, n_players):
        """Fire the entry impulse on both springs.

        Plays the issue's "Entra com overshoot": a controlled kick when the
        capsule first appears (run start, levelup/camp -> play transition).
        Different X impulse per player so the two capsules don't move in
        unison; cooldowns get a softer kick because they read faster and a
        loud one would fight the dial pulses.
        """
        sign = 1 if player_index == 0 else -1
        self.vitals_spring.impulse(sign * C.HUD_IMPULSE_ENTRY_X,
                                   C.HUD_IMPULSE_ENTRY_Y)
        self.cooldowns_spring.impulse(sign * C.HUD_IMPULSE_ENTRY_X * 0.6,
                                      C.HUD_IMPULSE_ENTRY_Y * 0.6)


def detect_changes(capsule, player):
    """Compare the player's current vitals to the capsule's last frame and fire
    impulses + shakes on both springs when they differ.

    Returns True if anything moved -- the caller can drive per-organ animations
    off the same flag. A damage hit AND a value change in the same frame sum
    (impulses stack; shakes upgrade only above the visible envelope -- see
    CapsuleSpring.start_shake)."""
    anything = False
    vit = capsule.vitals_spring
    cd = capsule.cooldowns_spring

    last = capsule.last_hp
    if last is not None and player.health < last - 0.5:
        # damage: larger impulse -- vitals feels it more, cooldowns a touch so
        # the second capsule reads as having reacted without dominating.
        vit.impulse(0.0, C.HUD_IMPULSE_DMG)
        cd.impulse(0.0, C.HUD_IMPULSE_DMG * 0.4)
        vit.start_shake(C.HUD_SHAKE_HP)
        cd.start_shake(C.HUD_SHAKE_HP * 0.5)
        anything = True
    elif last is not None and player.health > last + 0.5:
        vit.impulse(0.0, C.HUD_IMPULSE_VALUE)
        cd.impulse(0.0, C.HUD_IMPULSE_VALUE * 0.3)
        vit.start_shake(C.HUD_SHAKE_VALUE)
        cd.start_shake(C.HUD_SHAKE_VALUE * 0.5)
        anything = True
    capsule.last_hp = player.health

    last = capsule.last_energy
    if last is not None and abs(player.energy - last) > 0.6:
        vit.impulse(0.0, C.HUD_IMPULSE_VALUE * 0.7)
        cd.impulse(0.0, C.HUD_IMPULSE_VALUE * 0.5)
        vit.start_shake(C.HUD_SHAKE_VALUE * 0.7)
        cd.start_shake(C.HUD_SHAKE_VALUE * 0.4)
        anything = True
    capsule.last_energy = player.energy

    last = capsule.last_xp
    if last is not None and player.xp > last + 0.5:
        vit.impulse(0.0, C.HUD_IMPULSE_VALUE * 0.4)
        vit.start_shake(C.HUD_SHAKE_VALUE * 0.4)
        anything = True
    capsule.last_xp = player.xp

    last = capsule.last_ability
    if last is not None and (player.ability_charge >= 1.0) != (last >= 1.0):
        # crossing the "ready" threshold is the loudest value change in the
        # cooldowns capsule -- the item sphere is on the same panel as the
        # dials, so cooldowns feels the hit, vitals gets a quieter copy.
        cd.impulse(C.HUD_IMPULSE_VALUE * 0.8, C.HUD_IMPULSE_VALUE * 0.8)
        vit.impulse(0.0, C.HUD_IMPULSE_VALUE * 0.3)
        cd.start_shake(C.HUD_SHAKE_HP * 0.6)
        anything = True
    capsule.last_ability = player.ability_charge
    return anything
