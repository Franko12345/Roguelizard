"""Generate head.png + segment.png for Serpente de Cristal (boss part assets).

Spec lives in issue #191. Output:

    assets/boss/serpente_cristal/head.png      512x512 RGBA, transparent
    assets/boss/serpente_cristal/segment.png   512x512 RGBA, transparent

Both are drawn at 64x64 logical resolution then upscaled by NEAREST-neighbour
replication so each "logical" pixel becomes an 8x8 block. This keeps the
assets editable as grid art -- the canonical source is the 64x64 logical grid,
the PNG is just its render.

Palette is hard-coded to the five colours the spec mandates; ``check_issues``
asserts the final PNG only uses them.

Idempotent: running again overwrites. Safe to commit alongside the PNGs.
"""

from __future__ import annotations

import os
import sys

from _png import write_rgba_png

# --- spec ----------------------------------------------------------------

PALETTE = {
    "outline":   (0x0A, 0x16, 0x28),
    "shadow":    (0x1B, 0x49, 0x65),
    "cyan":      (0x5F, 0xA8, 0xD3),
    "highlight": (0xBE, 0xE9, 0xE8),
    "white":     (0xFF, 0xFF, 0xFF),
}

LOGICAL = 64                  # 64x64 logical pixels
PIXEL_SIZE = 8                # 8x scale -> 512x512 final
FINAL = LOGICAL * PIXEL_SIZE  # 512

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "boss", "serpente_cristal",
)

TRANSPARENT = (0, 0, 0, 0)


# --- low-level helpers ---------------------------------------------------

def new_grid() -> list[list[tuple[int, int, int, int]]]:
    return [[TRANSPARENT] * LOGICAL for _ in range(LOGICAL)]


def put(grid, x, y, rgba):
    if 0 <= x < LOGICAL and 0 <= y < LOGICAL:
        grid[y][x] = _rgba(rgba)


def _rgba(c):
    """Promote a 3-tuple RGB palette entry to an opaque 4-tuple RGBA."""
    if len(c) == 4:
        return c
    return (c[0], c[1], c[2], 255)


def poly_outline(grid, pts, rgba):
    """Closed polygon outline, 1 logical pixel thick."""
    rgba = _rgba(rgba)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        # Bresenham
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            put(grid, x, y, rgba)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy


def poly_fill(grid, pts, rgba):
    """Even-odd scanline fill of a polygon on the integer grid."""
    rgba = _rgba(rgba)
    n = len(pts)
    ys = [p[1] for p in pts]
    ymin, ymax = min(ys), max(ys)
    for y in range(ymin, ymax + 1):
        xs = []
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                if y1 == y0:
                    continue
                t = (y - y0) / (y1 - y0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            xa = int(round(xs[j]))
            xb = int(round(xs[j + 1]))
            for x in range(xa, xb + 1):
                put(grid, x, y, rgba)


def fill_triangle(grid, tri, rgba):
    rgba = _rgba(rgba)
    xs = [p[0] for p in tri]
    ys = [p[1] for p in tri]
    for y in range(min(ys), max(ys) + 1):
        xs_at_y = []
        for i in range(3):
            x0, y0 = tri[i]
            x1, y1 = tri[(i + 1) % 3]
            if (y0 <= y < y1) or (y1 <= y < y0):
                if y1 == y0:
                    continue
                t = (y - y0) / (y1 - y0)
                xs_at_y.append(x0 + t * (x1 - x0))
        if len(xs_at_y) < 2:
            continue
        xs_at_y.sort()
        for x in range(int(round(xs_at_y[0])), int(round(xs_at_y[-1])) + 1):
            if 0 <= y < LOGICAL and 0 <= x < LOGICAL:
                if grid[y][x] != TRANSPARENT:
                    put(grid, x, y, rgba)


def _lerp(a, b, t):
    """Linear blend of two RGBA tuples. Alpha stays opaque (255).

    Kept around for callers that want a smooth interior; current generators
    use solid palette colours per facet so this stays unused -- but it's the
    same blend ``palette.py`` uses elsewhere, so the API is familiar.
    """
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
        255,
    )


# --- HEAD ----------------------------------------------------------------
#
# Hexagonal snake head, ~34 wide x 52 tall, centred at (32, 32).
# Faceted: 4 sub-shapes meet at the head's centre. Each facet uses a SINGLE
# palette colour (the spec restricts the palette to 5 fixed colours, so
# gradients-as-interpolation would break it -- the "facet gradient" reads
# as the 5-colour contrast between adjacent facets, plus a small highlight
# wedge in the top-left of each).
#
# Palette mapping per facet:
#   top    -> highlight (#BEE9E8)   brightest, catches the most light
#   left   -> cyan (#5FA8D3)        main colour, base of the silhouette
#   right  -> cyan  (#5FA8D3)
#   bottom -> shadow (#1B4965)      underside, in shadow
#
# A highlight wedge (#BEE9E8) sits in the top-left of the top facet for the
# "crystal facet" feel without leaving the palette.

def draw_head() -> list[list[tuple[int, int, int, int]]]:
    g = new_grid()

    # silhouette hexagon. Slightly wider on top, tapers to a chin point.
    pts = [
        (32, 6),    # top
        (49, 20),   # upper-right
        (49, 42),   # lower-right
        (32, 58),   # chin
        (15, 42),   # lower-left
        (15, 20),   # upper-left
    ]

    # base fill (cyan, the dominant ~60-70% colour)
    poly_fill(g, pts, PALETTE["cyan"])

    # 4 facets along the X-diagonals through (32, 32).
    cx, cy = 32, 32
    top    = [(32, 6), (49, 20), (cx, cy), (15, 20)]            # top trapezoid
    right  = [(49, 20), (49, 42), (cx, cy)]                     # right triangle
    bottom = [(15, 42), (cx, cy), (49, 42), (32, 58)]           # bottom trapezoid
    left   = [(15, 20), (cx, cy), (15, 42)]                     # left triangle

    # each facet painted with ONE solid palette colour
    poly_fill(g, top,    PALETTE["highlight"])
    poly_fill(g, right,  PALETTE["cyan"])
    poly_fill(g, bottom, PALETTE["shadow"])
    poly_fill(g, left,   PALETTE["cyan"])

    # small highlight wedge in the top-left corner of the top facet
    # (within silhouette, 3x2 cluster so no 1x1 stranded pixels)
    for dy in range(2):
        for dx in range(3):
            x, y = 19 + dx, 11 + dy
            if 0 <= x < LOGICAL and 0 <= y < LOGICAL:
                if g[y][x] != TRANSPARENT:
                    put(g, x, y, PALETTE["highlight"])

    # eyes: 4 small 2x2 eyes, two pairs symmetric across cx. y=30..33.
    _eye_pair(g, cx=23, cy=31)
    _eye_pair(g, cx=39, cy=31)

    # mouth: a short 3-px dark notch on the chin facet
    _mouth(g, cx=32, cy=45)

    # 1px outline locks the silhouette last so nothing escapes it.
    poly_outline(g, pts, PALETTE["outline"])

    # white specular: budget is 4-6 px total. 2x2 cluster in the
    # highlight wedge only.
    put(g, 20, 11, PALETTE["white"])
    put(g, 21, 11, PALETTE["white"])
    put(g, 20, 12, PALETTE["white"])
    put(g, 21, 12, PALETTE["white"])

    return g


def _eye_pair(g, cx, cy):
    """Two stacked 2x2 eyes sharing a corner (reads as a single big eye)."""
    for dy in (0, 1):
        for dx in (0, 1):
            put(g, cx + dx, cy + dy, PALETTE["shadow"])
    # one tiny highlight pixel
    put(g, cx, cy, PALETTE["highlight"])


def _mouth(g, cx, cy):
    for dx in (-1, 0, 1):
        put(g, cx + dx, cy, PALETTE["shadow"])


# --- SEGMENT -------------------------------------------------------------
#
# Diamond / rhombus ~32 wide x 48 tall, centred at (32, 32). 4 facets split
# by the X-diagonals through (32, 32). No eyes, no mouth.

def draw_segment() -> list[list[tuple[int, int, int, int]]]:
    g = new_grid()

    pts = [
        (32, 8),   # top
        (48, 32),  # right
        (32, 56),  # bottom
        (16, 32),  # left
    ]

    poly_fill(g, pts, PALETTE["cyan"])

    cx, cy = 32, 32
    tl = [(32, 8), (cx, cy), (16, 32)]   # top-left triangle
    tr = [(32, 8), (48, 32), (cx, cy)]   # top-right triangle
    bl = [(16, 32), (cx, cy), (32, 56)]  # bottom-left triangle
    br = [(cx, cy), (48, 32), (32, 56)]  # bottom-right triangle

    fill_triangle(g, tl, PALETTE["highlight"])
    fill_triangle(g, tr, PALETTE["cyan"])
    fill_triangle(g, bl, PALETTE["cyan"])
    fill_triangle(g, br, PALETTE["shadow"])

    poly_outline(g, pts, PALETTE["outline"])

    # no white pixels on segments (they read as sober crystal links)
    return g


# --- output --------------------------------------------------------------

def grid_to_png(grid, path):
    """Upscale LOGICAL->FINAL via pixel replication and write 8-bit RGBA PNG."""
    buf = bytearray(FINAL * FINAL * 4)
    for y in range(LOGICAL):
        for x in range(LOGICAL):
            r, gr, b, a = grid[y][x]
            # replicate into an 8x8 block in the destination
            for dy in range(PIXEL_SIZE):
                yy = y * PIXEL_SIZE + dy
                for dx in range(PIXEL_SIZE):
                    xx = x * PIXEL_SIZE + dx
                    off = (yy * FINAL + xx) * 4
                    buf[off] = r
                    buf[off + 1] = gr
                    buf[off + 2] = b
                    buf[off + 3] = a
    write_rgba_png(path, FINAL, FINAL, bytes(buf))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    head_path = os.path.join(OUT_DIR, "head.png")
    seg_path = os.path.join(OUT_DIR, "segment.png")

    grid_to_png(draw_head(), head_path)
    grid_to_png(draw_segment(), seg_path)

    print(f"wrote {head_path}")
    print(f"wrote {seg_path}")


if __name__ == "__main__":
    sys.exit(main())
