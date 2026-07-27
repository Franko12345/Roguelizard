"""Spine: a follow-the-leader chain with a bend limit, plus body-outline geometry.

Grown from the original ``procedural_animation.py``: joint[0] is the head and
leads; every following joint is pulled to a fixed distance behind the previous
one, and its direction is clamped so the body cannot kink onto itself.
"""

from pygame import Vector2

from ..core.mathutil import angle_of, clamp_angle, vfrom_angle, safe_norm, lerp, catmull_rom

SMOOTH_SUBDIV = 1   # extra points per segment for the smoothed outline (plans/01 #6)

# thickness profile sampled along the body (head -> tail); kept above zero at the
# tail so the two body rims never cross into a sharp "blade".
RADII_PROFILE = [0.56, 0.84, 1.0, 1.0, 0.95, 0.88, 0.79, 0.69,
                 0.60, 0.51, 0.43, 0.35, 0.28, 0.22]


def build_radii(n, maxr):
    prof = RADII_PROFILE
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(prof) - 1)
        lo = int(t)
        hi = min(lo + 1, len(prof) - 1)
        out.append(lerp(prof[lo], prof[hi], t - lo) * maxr)
    return out


class Spine:
    def __init__(self, pos, n, link, radii, bend=30.0):
        self.joints = [Vector2(pos) for _ in range(n)]
        self.link = link
        # Resting link. ``resolve()`` reads ``link`` fresh every frame, so a pose
        # can squeeze the whole chain for a few frames (the rolamento's disc) by
        # scaling off this instead of caching a base itself -- a cached copy goes
        # stale the moment ``rebuild_body`` grows the creature mid-pose.
        self.link0 = link
        self.radii = list(radii)
        self.bend = bend

    def resolve(self, head):
        j = self.joints
        j[0].update(head)
        for i in range(1, len(j)):
            a = angle_of(j[i] - j[i - 1])
            if i >= 2:
                prev = angle_of(j[i - 1] - j[i - 2])
                a = clamp_angle(a, prev, self.bend)
            j[i] = j[i - 1] + vfrom_angle(a, self.link)

    def head_dir(self):
        return safe_norm(self.joints[0] - self.joints[1])

    def _smooth_samples(self, joints=None):
        """Denser (pos, radius) samples via Catmull-Rom -- softens the visible
        polygon facets of a low-joint-count body without moving the physical
        joints themselves (hit-test/legs/eyes still read ``self.joints``)."""
        j = joints if joints is not None else self.joints
        rad = self.radii
        n = len(j)
        pts, radii = [j[0]], [rad[0]]
        for i in range(n - 1):
            p0, p1, p2 = j[max(0, i - 1)], j[i], j[i + 1]
            p3 = j[min(n - 1, i + 2)]
            for s in range(1, SMOOTH_SUBDIV + 1):
                t = s / SMOOTH_SUBDIV
                pts.append(catmull_rom(p0, p1, p2, p3, t))
                radii.append(lerp(rad[i], rad[i + 1], t))
        return pts, radii

    def body_render_smooth(self, scale=1.0, joints=None):
        """Everything ``Lizard.draw()`` needs for the 'normal' body, computed
        ONCE: quads for the fill (+ head/tail cap fans) and one ring for the
        outline stroke. Sharing the smoothed samples between the two matters
        -- computing them twice (quads from one pass, stroke from another)
        measured barely faster than an all-smooth quad strip despite far
        fewer quads, because the repeated Catmull-Rom pass was the real cost.

        Filled as a STRIP of small quads, not one big ring: a tight curl makes
        the ring self-intersect, and pygame's fill rule opens a hole exactly
        where it crosses itself (the body reads as transparent where it curls
        onto itself). Each quad is simple on its own, so filling them one at a
        time never hits that cancellation. The stroke can still use the single
        ring -- pygame strokes edge-by-edge, so self-crossing there is harmless.
        """
        pts, radii = self._smooth_samples(joints)
        m = len(pts)
        left, right = [], []
        for i in range(m):
            fwd = safe_norm(pts[i] - pts[i + 1]) if i < m - 1 else safe_norm(pts[i - 1] - pts[i])
            perp = Vector2(-fwd.y, fwd.x) * (radii[i] * scale)
            left.append(pts[i] + perp)
            right.append(pts[i] - perp)
        quads = [(left[i], left[i + 1], right[i + 1], right[i]) for i in range(m - 1)]
        head_fan = self.head_cap(scale)
        tail_fan = self.tail_cap(scale, joints)
        ring = left + tail_fan + right[::-1] + head_fan
        return quads, head_fan, tail_fan, ring

    def _cap(self, center, outward, r, reverse):
        """Semicircle of points around ``center`` opening along ``outward``."""
        base = angle_of(outward)
        angs = [-90, -55, -25, 0, 25, 55, 90]
        if reverse:
            angs = angs[::-1]
        return [center + vfrom_angle(base + a, r * (1.05 if abs(a) < 30 else 0.92))
                for a in angs]

    def head_cap(self, scale=1.0):
        """Rounded snout points, ordered right-rim -> front -> left-rim."""
        return self._cap(self.joints[0], self.head_dir(), self.radii[0] * scale, False)

    def tail_cap(self, scale=1.0, joints=None):
        """Rounded tail points, ordered left-rim -> back -> right-rim."""
        j = joints if joints is not None else self.joints
        n = len(j)
        back = safe_norm(j[n - 1] - j[n - 2])
        return self._cap(j[n - 1], back, self.radii[n - 1] * scale, True)
