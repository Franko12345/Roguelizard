"""Camera: follows one player, or frames both in co-op (lerped pos + zoom).

Also owns screen shake. ``w2s`` / ``s2w`` convert between world and screen space.

``w2s`` is the hottest function in the whole frame -- around 5,500 calls per
frame with 30 creatures on screen, roughly 4 ms of a 12-16 ms draw. It is
therefore written as a plain affine transform over three cached floats:

    sx = wx * _z + _ox
    sy = wy * _z + _oy

``_z / _ox / _oy`` fold zoom, camera position, screen centre and shake offset
into one multiply-add per axis. They are recomputed by the setters of the four
things they depend on (``pos``, ``zoom``, ``center``, ``shake_off``), which are
properties for exactly that reason -- assigning any of them keeps the cache
correct without callers knowing it exists.

The one thing that would break it is mutating a vector IN PLACE
(``cam.pos.x = 5``) instead of assigning a new one. Nothing does; assign a new
Vector2 if you ever need to.
"""

import math
import random
from pygame import Vector2

from ..core import config as C
from ..core.mathutil import clamp, lerp, random_dir


class Camera:
    def __init__(self, center=None):
        self._pos = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
        self._zoom = 1.0
        self._shake_off = Vector2()
        self.shake_mag = 0.0
        # where world-space `pos` lands on screen; menus use this to render a
        # live creature inside a panel instead of the middle of the screen.
        self._center = center or (C.WIDTH / 2, C.HEIGHT / 2)
        self._refresh()

    # ---- cached transform ----------------------------------------------- #
    def _refresh(self):
        """Fold pos/zoom/center/shake into one multiply-add per axis."""
        z = self._zoom
        self._z = z
        self._ox = self._center[0] + self._shake_off.x - self._pos.x * z
        self._oy = self._center[1] + self._shake_off.y - self._pos.y * z

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, v):
        self._pos = v
        self._refresh()

    @property
    def zoom(self):
        return self._zoom

    @zoom.setter
    def zoom(self, v):
        self._zoom = v
        self._refresh()

    @property
    def center(self):
        return self._center

    @center.setter
    def center(self, v):
        self._center = v
        self._refresh()

    @property
    def shake_off(self):
        return self._shake_off

    @shake_off.setter
    def shake_off(self, v):
        self._shake_off = v
        self._refresh()

    # ---- movement -------------------------------------------------------- #
    def follow(self, players, dt):
        alive = [p for p in players if not p.dead]
        if not alive:
            return
        center = Vector2()
        for p in alive:
            center += p.pos
        center /= len(alive)

        target_zoom = 1.0
        if len(alive) > 1:
            span = max(alive[0].pos.distance_to(alive[1].pos), 1)
            target_zoom = clamp(min(C.WIDTH, C.HEIGHT) / (span + 380), 0.55, 1.05)

        self._pos = self._pos.lerp(center, clamp(6 * dt, 0, 1))
        self._zoom = lerp(self._zoom, target_zoom, clamp(4 * dt, 0, 1))

        if self.shake_mag > 0.2:
            self._shake_off = random_dir(self.shake_mag)
            self.shake_mag *= math.exp(-9 * dt)
        else:
            self._shake_off = Vector2()
        self._refresh()          # one refresh for all three, not three

    def add_shake(self, m):
        self.shake_mag = min(self.shake_mag + m, 26)

    # ---- transforms ------------------------------------------------------ #
    def w2s(self, world):
        z = self._z
        return (int(world[0] * z + self._ox), int(world[1] * z + self._oy))

    def w2s_many(self, points):
        """``[w2s(p) for p in points]`` with the transform bound once.

        For the draw code's hot list conversions (body quads, outline rings,
        leg chains): same result, but the three attribute lookups happen per
        LIST instead of per point.
        """
        z, ox, oy = self._z, self._ox, self._oy
        return [(int(p[0] * z + ox), int(p[1] * z + oy)) for p in points]

    def s2w(self, screen):
        cx, cy = self._center
        x = (screen[0] - cx - self._shake_off.x) / self._zoom + self._pos.x
        y = (screen[1] - cy - self._shake_off.y) / self._zoom + self._pos.y
        return Vector2(x, y)

    def visible(self, pos, margin=80):
        # Inlined rather than going through w2s: this runs ~800 times a frame
        # and does not need the int() rounding or the tuple.
        z = self._z
        x = pos[0] * z + self._ox
        if not (-margin < x < C.WIDTH + margin):
            return False
        y = pos[1] * z + self._oy
        return -margin < y < C.HEIGHT + margin
