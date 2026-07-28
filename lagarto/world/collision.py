"""Creature separation: stop long lizard bodies from passing through each other.

Each lizard is a long chain, so treating it as a single circle only keeps the
*heads* apart while the bodies still cross. Instead we sample several points along
every spine (head, quarters, tail) with their local body radius and push creatures
apart wherever *any* two samples overlap. A spatial hash over the samples keeps it
near-linear.

The accumulated push is applied to the creature's head (which drags the whole body
via the follow-the-leader chain), capped and eased so a tangled pile untangles over
a few frames instead of snapping. Affected spines are re-resolved so the drawn body
matches its corrected head the same frame.
"""

import math
import random

from ..core import config as C

CELL = 80          # world units; ~ two body samples touching
SQUISH = 0.9       # <1 lets squishy bodies sink into each other a touch
EASE = 0.6         # fraction of the correction applied per step (less jitter)
FRIENDLY = ('player', 'friend')   # allies pass through each other (no clunky bumping)
# Only these drag the player. Prey used to count too, so brushing past a grazer
# cut your speed in half -- with no visual cause a player would ever connect to
# "why am I slow?". They still get shoved aside; they just don't cost you speed.
DRAGS_PLAYER = ('enemy',)


def _samples(creatures):
    out = []
    for c in creatures:
        # Flyers are simply absent from the whole system: they neither push nor
        # are pushed, so they cross the horde in a straight line instead of
        # getting stuck behind it. Dropping them here (rather than filtering in
        # the pair loop) also keeps them out of the player's `clog` drag, which
        # is right -- you cannot be slowed by wading through something airborne.
        # A turret is absent for the opposite reason: it is planted (#111). If it
        # took a push it would drift, and a Deployable that slides is no longer
        # the thing the player chose a spot for -- so nothing shoves it and it
        # shoves nothing, exactly like the flyers above.
        if getattr(c, 'flying', False) or getattr(c, 'burrowed', False) \
                or c.kind == 'turret':
            continue
        js = c.spine.joints
        rs = c.spine.radii
        m = len(js)
        for i in {0, m // 4, m // 2, (3 * m) // 4, m - 1}:
            j = js[i]
            out.append((c, j.x, j.y, rs[i] * SQUISH))
    return out


def separate(creatures):
    if len(creatures) < 2:
        for c in creatures:
            c.clog = 0.0            # nothing to touch -> never leave stale drag
        return

    for c in creatures:
        c._px = 0.0
        c._py = 0.0
        c._clog = 0.0

    samples = _samples(creatures)
    grid = {}
    for si, (c, x, y, r) in enumerate(samples):
        grid.setdefault((int(x // CELL), int(y // CELL)), []).append(si)

    for si, (c, x, y, r) in enumerate(samples):
        gx, gy = int(x // CELL), int(y // CELL)
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                bucket = grid.get((gx + ox, gy + oy))
                if not bucket:
                    continue
                for sj in bucket:
                    if sj <= si:                 # each sample pair once
                        continue
                    o, x2, y2, r2 = samples[sj]
                    if o is c:                   # ignore self-overlap
                        continue
                    # allies don't collide with each other -> battles stay fluid
                    if c.kind in FRIENDLY and o.kind in FRIENDLY:
                        continue
                    dx = x - x2
                    dy = y - y2
                    min_d = r + r2
                    d2 = dx * dx + dy * dy
                    if d2 >= min_d * min_d:
                        continue
                    if d2 > 1e-6:
                        dist = math.sqrt(d2)
                        nx, ny, ov = dx / dist, dy / dist, min_d - dist
                    else:
                        a = random.uniform(0, C.TAU)
                        nx, ny, ov = math.cos(a), math.sin(a), min_d
                    # SOFT contact for the player: being physically shoved by every
                    # enemy read as pinball and was the single most frustrating thing
                    # in playtests. The player is never pushed -- they wade *through*,
                    # shoving the enemy aside, and pay for it in speed (see
                    # ``_clog`` -> Player.update).
                    cp, op = c.kind == 'player', o.kind == 'player'
                    if cp or op:
                        if cp:
                            if o.kind in DRAGS_PLAYER:
                                c._clog += ov
                            o._px -= nx * ov
                            o._py -= ny * ov
                        else:
                            if c.kind in DRAGS_PLAYER:
                                o._clog += ov
                            c._px += nx * ov
                            c._py += ny * ov
                        continue
                    wc = o.max_r / (c.max_r + o.max_r)   # bigger yields less
                    wo = 1.0 - wc
                    c._px += nx * ov * wc
                    c._py += ny * ov * wc
                    o._px -= nx * ov * wo
                    o._py -= ny * ov * wo

    for c in creatures:
        # how deeply this creature is buried in bodies it doesn't push against;
        # Player.update turns it into drag instead of a shove
        c.clog = c._clog
        px, py = c._px, c._py
        if px == 0.0 and py == 0.0:
            continue
        mag = math.hypot(px, py)
        cap = c.max_r * 1.5                       # don't teleport out of a pile
        if mag > cap:
            px *= cap / mag
            py *= cap / mag
        c.pos.x = min(max(c.pos.x + px * EASE, c.max_r), C.WORLD_W - c.max_r)
        c.pos.y = min(max(c.pos.y + py * EASE, c.max_r), C.WORLD_H - c.max_r)
        c.spine.resolve(c.pos)
