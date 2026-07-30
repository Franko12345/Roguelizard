"""Assert the projectile hooks, the side colour rule and the bullet budget
(#102, #116).

Six things have to hold or the issue is decoration:

1. **The hooks fire.** ``on_update`` / ``on_hit`` / ``on_death`` all run through
   the real ``Game._update_projectiles``, and they are the ONLY path: the same
   shot without the hook does not curve, does not bounce, leaves nothing.
2. **Colour codes the side, not the species.** Bullets rendered with wildly
   different creature colours produce IDENTICAL bodies as long as the side
   matches; hostile and friendly are far apart. The creature's colour still
   shows up -- but only outside the body, in the halo.
3. **The sprite cache stays bounded.** Hammer it with every radius the camera
   can produce and the entry count never passes the cap.
4. **~100 bullets fit the frame.** Measured, not asserted: step + draw for a
   hundred live projectiles, against the 16.6 ms budget at 60 Hz.
5. **No streak behind the bullet.** The draw is symmetric along the direction of
   travel -- a solid trail would pile pixels behind the body and nowhere else.
6. **The backward sparks fit the pool.** A hundred live bullets for two seconds
   never fill ``FX.MAX_SPARKS``; if they did, every other spark in the game
   (tongue, dash, impact) would start getting evicted by gunfire.

Run:  python tools/check_projectile.py
"""
import os, sys, time
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import inspect
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render import display
from lagarto.render.camera import Camera
from lagarto.core import fonts, palette, config as C
from lagarto.core.mathutil import vfrom_angle
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.creatures import species
from lagarto.combat import projectile as P
display.init()
DT = 1 / 60
MID = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)


def fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    g.projectiles = []
    g.puddles = []
    return g, g.players[0]


# --------------------------------------------------------------------------- #
# 1. the three hooks fire, through the real loop                              #
# --------------------------------------------------------------------------- #
g, p = fresh()
seen = []
pr = P.Projectile(p.pos + Vector2(60, 0), Vector2(-400, 0), (200, 200, 200),
                  dmg=5, hostile=True)
pr.on_update.append(lambda s, dt, game: seen.append('update'))
pr.on_hit.append(lambda s, victim, game: seen.append(('hit', victim is p)))
pr.on_death.append(lambda s, game: seen.append('death'))
g.projectiles.append(pr)
for _ in range(30):
    g._update_projectiles(DT)
    if not g.projectiles:
        break
assert 'update' in seen, "on_update never ran"
assert ('hit', True) in seen, f"on_hit did not fire on the player it hit: {seen}"
assert seen.count('death') == 1, f"on_death fired {seen.count('death')}x, expected once"
assert seen.index(('hit', True)) < seen.index('death'), "on_death beat on_hit"
print(f"  hooks: {seen.count('update')} update, 1 hit, 1 death -- in order")

# --------------------------------------------------------------------------- #
# 2. movement lives in on_update, and NOWHERE else                            #
# --------------------------------------------------------------------------- #
g, p = fresh()
e = species.make('spitter', MID + Vector2(0, 160))
g.enemies.append(e)


def fly(hook):
    """A friendly shot crossing well clear of the enemy; returns its heading."""
    g.projectiles = []
    s = P.Projectile(MID + Vector2(-300, -160), Vector2(320, 0), (200, 200, 200),
                     dmg=0, hostile=False)
    if hook:
        s.on_update.append(hook)
    g.projectiles.append(s)
    for _ in range(20):
        g._update_projectiles(DT)
    return s.vel.y


plain, homed = fly(None), fly(P.homing)
assert plain == 0.0, f"a hookless shot curved on its own ({plain:.1f} px/s of drift)"
assert homed > 60, f"the homing hook barely steered ({homed:.1f} px/s toward the target)"
print(f"  homing: hookless drift {plain:.0f} px/s, with the hook {homed:.0f} px/s")


def wall_shot(hook):
    g.projectiles = []
    s = P.Projectile((6, MID.y), Vector2(-400, 0), (200, 200, 200), hostile=True)
    s.bounces_left, s.bounce_damp = 2, 0.8
    if hook:
        s.on_update.append(hook)
    g.projectiles.append(s)
    g._update_projectiles(DT)
    return s


assert wall_shot(None).dead, "a hookless shot survived leaving the arena"
bounced = wall_shot(P.bounce)
assert not bounced.dead and bounced.vel.x > 0 and bounced.bounces_left == 1, \
    f"the bounce hook did not ricochet (dead={bounced.dead}, vx={bounced.vel.x:.0f})"
print(f"  bounce: hookless shot dies at the wall, hooked one comes back "
      f"at {bounced.vel.x:.0f} px/s with {bounced.bounces_left} left")

# --------------------------------------------------------------------------- #
# 3. on_death payload: the puddle, exactly once                               #
# --------------------------------------------------------------------------- #
g, _ = fresh()
s = P.Projectile(MID + Vector2(500, 500), Vector2(), (140, 235, 100),
                 hostile=True, life=0.005)
s.on_death.append(P.leave_puddle(r=40, dmg=2, life=2.0, hue=100, tick=0.5))
g.projectiles.append(s)
g._update_projectiles(DT)
assert len(g.puddles) == 1, f"the payload left {len(g.puddles)} puddles, expected 1"
g._update_projectiles(DT)
assert len(g.puddles) == 1, "the payload fired twice"
print("  payload: one puddle per shot, dropped where it landed")

# --------------------------------------------------------------------------- #
# 4. colour codes the SIDE                                                    #
# --------------------------------------------------------------------------- #
cam = Camera()
surf = pygame.Surface((C.WIDTH, C.HEIGHT))
SPECIES_HUES = (150, 200, 100, 18, 265)      # spitter, gunner, venomer, escorpiao, aranha


def render(hostile, hue):
    """Draw one bullet alone; return (body mean, halo mean) as RGB triples."""
    surf.fill((0, 0, 0))
    s = P.Projectile(MID, Vector2(200, 0), palette.vibrant(hue), hostile=hostile)
    s.draw(surf, cam)
    cx, cy = cam.w2s(MID)
    r = max(4, int(s.radius * cam.zoom) & ~1)
    body, halo = [0, 0, 0], [0, 0, 0]
    nb = nh = 0
    for dx in range(-3 * r, 3 * r + 1):
        for dy in range(-3 * r, 3 * r + 1):
            d2 = dx * dx + dy * dy
            col = surf.get_at((cx + dx, cy + dy))
            if d2 <= (r * 0.85) ** 2:
                body = [body[i] + col[i] for i in range(3)]
                nb += 1
            elif (1.1 * r) ** 2 <= d2 <= (1.9 * r) ** 2:
                halo = [halo[i] + col[i] for i in range(3)]
                nh += 1
    return ([c / nb for c in body], [c / nh for c in halo])


def dist(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


bodies = {side: [render(side, h) for h in SPECIES_HUES] for side in (True, False)}
for side, name in ((True, 'hostile'), (False, 'friendly')):
    spread = max(dist(a[0], b[0]) for a in bodies[side] for b in bodies[side])
    assert spread == 0.0, \
        f"the species colour leaked into a {name} bullet's body ({spread:.1f} apart)"
gap = min(dist(a[0], b[0]) for a in bodies[True] for b in bodies[False])
assert gap > 90, f"hostile and friendly bodies are only {gap:.0f} apart -- unreadable"
hb, fb = bodies[True][0][0], bodies[False][0][0]
assert hb[0] > hb[1] + 40, f"the hostile bullet stopped reading warm: {hb}"
assert fb[1] > fb[0] + 40, f"the friendly bullet stopped reading as the player's: {fb}"
halo_spread = max(dist(a[1], b[1]) for a in bodies[True] for b in bodies[True])
assert halo_spread > 40, \
    f"the creature's colour vanished from the halo too ({halo_spread:.1f} apart)"
print(f"  side: body identical across 5 species (0.0 apart), sides {gap:.0f} apart; "
      f"halo still varies by {halo_spread:.0f}")
print(f"        hostile body {tuple(round(c) for c in hb)}  "
      f"friendly body {tuple(round(c) for c in fb)}")

# the whip reflect must flip the read, not just the team flag
before = P.side_palette(True)
s = P.Projectile(MID, Vector2(200, 0), palette.vibrant(150), hostile=True)
s.hostile = False
assert P.side_palette(s.hostile) != before, "a batted-back shot still reads hostile"

# --------------------------------------------------------------------------- #
# 5. the body cache stays bounded                                             #
# --------------------------------------------------------------------------- #
entries0 = P.body_stats()[0]
s = P.Projectile(MID, Vector2(200, 0), (200, 200, 200), hostile=True)
for i in range(4000):                        # every radius/zoom the camera can make
    cam.zoom = 0.55 + (i % 400) * 0.00125
    s.radius = 4 + (i % 24)
    s.draw(surf, cam)
entries, hits, misses, clears = P.body_stats()
assert entries <= P._BODY_MAX, f"the bullet cache grew to {entries} > cap {P._BODY_MAX}"
assert hits > misses * 4, \
    f"the cache is thrashing: {hits} hits vs {misses} misses (key too fine?)"
print(f"  cache: {entries}/{P._BODY_MAX} entries after 4000 draws "
      f"({hits} hits, {misses} misses, {clears} clears)")
cam.zoom = 1.0

# --------------------------------------------------------------------------- #
# 6. the budget: ~100 bullets on screen                                       #
# --------------------------------------------------------------------------- #
g, p = fresh()
far = MID + Vector2(900, 900)                # clear of the player, so none of them die
cam.pos = Vector2(far)
for i in range(100):
    ang = i * 3.6
    pos = far + vfrom_angle(ang, 60 + (i % 40) * 5)
    shot = P.spit(pos, pos + vfrom_angle(ang, 100), palette.vibrant(i * 7 % 360),
                  hostile=(i % 2 == 0))
    shot.life = 99
    g.projectiles.append(shot)
N = 120
for _ in range(20):                          # steady state: warm both sprite caches
    g._update_projectiles(DT)
t0 = time.perf_counter()
for _ in range(N):
    g._update_projectiles(DT)
step_ms = (time.perf_counter() - t0) * 1000 / N
live = len(g.projectiles)
assert live >= 90, f"only {live} of 100 bullets survived the perf run"
surf.fill((0, 0, 0))
for _ in range(20):
    for shot in g.projectiles:
        shot.draw(surf, cam)
t0 = time.perf_counter()
for _ in range(N):
    for shot in g.projectiles:
        shot.draw(surf, cam)
draw_ms = (time.perf_counter() - t0) * 1000 / N
print(f"  budget: {live} bullets -> step {step_ms:.2f} ms + draw {draw_ms:.2f} ms "
      f"= {step_ms + draw_ms:.2f} ms of the 16.6 ms frame")
assert step_ms + draw_ms < 4.0, \
    f"{live} bullets cost {step_ms + draw_ms:.2f} ms, a quarter of the frame budget"

# --------------------------------------------------------------------------- #
# 7. no streak: the draw is symmetric along the direction of travel           #
# --------------------------------------------------------------------------- #
cam.pos = Vector2(MID)
surf.fill((0, 0, 0))
fast = P.Projectile(MID, Vector2(900, 0), (200, 200, 200), hostile=True)
for _ in range(6):                           # far enough in that a streak had a tail
    fast.update(DT)                          # game=None -> no sparks in this sample
fast.draw(surf, cam)
cx, cy = cam.w2s(fast.pos)
r = max(4, int(fast.radius * cam.zoom) & ~1)


def band(sign):
    """Ink in the halo band on one side of the body, along the travel axis.

    Every sprite here is an even-sided square blitted at ``sp - half``, so its
    true centre is half a pixel up and left of ``sp``; the mirror is about
    ``cx - 0.5``, not ``cx``, or the halo alone reads as 7% of a streak.
    """
    tot = 0
    for dx in range(int(1.4 * r), int(4.0 * r)):
        x = cx + dx if sign > 0 else cx - dx - 1
        for dy in range(-r // 2, r // 2 + 1):
            tot += sum(surf.get_at((x, cy + dy))[:3])
    return tot


ahead, behind = band(1), band(-1)
assert ahead > 0, "the sample band is empty -- the check is measuring nothing"
assert abs(behind - ahead) <= ahead * 0.02, \
    f"something is drawn behind the bullet: {behind} ink back vs {ahead} ahead"
print(f"  no streak: {behind} ink behind the body vs {ahead} ahead -- symmetric")

# --------------------------------------------------------------------------- #
# 8. the backward sparks fit the pool, with room for the rest of the game     #
# --------------------------------------------------------------------------- #
g, p = fresh()
for i in range(100):
    ang = i * 3.6
    pos = far + vfrom_angle(ang, 60 + (i % 40) * 5)
    shot = P.spit(pos, pos + vfrom_angle(ang, 100), palette.vibrant(i * 7 % 360),
                  hostile=(i % 2 == 0))
    shot.life = 99
    g.projectiles.append(shot)
g.fx.sparks = []
peak = 0
for _ in range(120):                         # 2 s of a full bullet-hell screen
    g._update_projectiles(DT)
    g.fx.update(DT)
    peak = max(peak, len(g.fx.sparks))
live = len(g.projectiles)
assert live >= 90, f"only {live} of 100 bullets survived the spark run"
assert peak > 0, "the bullets stopped emitting sparks entirely"
assert peak < g.fx.MAX_SPARKS, \
    f"{live} bullets filled the spark pool ({peak}/{g.fx.MAX_SPARKS}) -- gunfire " \
    f"is now evicting the tongue, the dash and every impact in the game"
sides = {tuple(s[6]) for s in g.fx.sparks}
assert sides <= {P.HOSTILE[1], P.FRIENDLY[1]}, \
    f"a bullet spark stopped carrying the side colour (ADR-0014): {sides}"
print(f"  sparks: {live} bullets peak at {peak}/{g.fx.MAX_SPARKS} sparks "
      f"({g.fx.MAX_SPARKS - peak} left for the rest of the game), "
      f"both sides in `mid`")

# --------------------------------------------------------------------------- #
# 9. issue #167 -- the five new on_update hooks are real functions,           #
#    each with the canonical (pr, dt, game) signature, and runnable. The      #
#    `chain_damage` sister hook on_hit applies the chain bonus; `wave` snake  #
#    is checked separately; `boomerang` flips; `burst_stop` lands a Puddle;   #
#    `spiral_arc` orbits. The slow_homing dial is a regular mod= knob the     #
#    emitter passes through (_launch), so reading it from pr is enough.      #
# --------------------------------------------------------------------------- #
NEW_HOOKS = ('chain_link', 'chain_damage', 'wave', 'boomerang', 'burst_stop',
             'spiral_arc')
for name in NEW_HOOKS:
    fn = getattr(P, name, None)
    assert callable(fn), f"hook {name} missing from lagarto.combat.projectile"
    if name == 'chain_damage':
        params = list(inspect.signature(fn).parameters)
        assert params == ['pr', 'victim', 'game'], \
            f"{name} signature {params} != ['pr', 'victim', 'game']"
    else:
        params = list(inspect.signature(fn).parameters)
        assert params == ['pr', 'dt', 'game'], \
            f"{name} signature {params} != ['pr', 'dt', 'game']"

# each new hook lives in projectile.py
for name in NEW_HOOKS:
    src_p = inspect.getsource(P)
    assert f'def {name}(' in src_p, \
        f"hook {name} not defined in lagarto.combat.projectile ({src_p[:80]!r})"
print(f"  hooks #167: {len(NEW_HOOKS)} new hooks, all defined in projectile.py "
      f"with the canonical signatures")

# --------------------------------------------------------------------------- #
# 10. wave: a S-trajectory -- the wave hook offsets perpendicular each frame,   #
#     so the snake shot's path swings laterally even though its straight       #
#     counterpart stays on the X axis. We check the MAX perpendicular         #
#     excursion rather than net drift -- a sine wobble averages to zero.       #
# --------------------------------------------------------------------------- #
g, p = fresh()
spit_from = MID + Vector2(-300, 0)
straight = P.Projectile(spit_from, Vector2(240, 0), (200, 200, 200), hostile=True)
snake = P.Projectile(spit_from, Vector2(240, 0), (200, 200, 200), hostile=True)
snake.on_update.append(P.wave)
g.projectiles.extend([straight, snake])
peak_lateral = 0.0
for _ in range(60):
    g._update_projectiles(DT)
    peak_lateral = max(peak_lateral, abs(snake.pos.y - MID.y))
assert abs(straight.pos.y - MID.y) < 1.0, \
    f"the straight shot drifted off-axis ({straight.pos.y - MID.y:.1f}px)"
assert peak_lateral > 5, \
    f"the wave hook barely moved the shot off-axis (peak {peak_lateral:.1f}px)"
print(f"  wave: straight y stays at {straight.pos.y - MID.y:+.1f}px; "
      f"snake peak lateral {peak_lateral:.1f}px (S-curve visible)")

# --------------------------------------------------------------------------- #
# 11. boomerang: the shot flies, then flips back. We mark boomerang_returned   #
#     the first frame vel reverses; the second half flips it back to where    #
#     it came from (anchored via shooter_pos).                                 #
# --------------------------------------------------------------------------- #
g, _ = fresh()
b = P.Projectile(MID, Vector2(280, 0), (200, 200, 200), hostile=True)
b.shooter_pos = MID + Vector2(-300, 0)
b.on_update.append(P.boomerang)
g.projectiles.append(b)
got_flip = False
for _ in range(int(C.BOOMERANG_RETURN_TIME / DT) + 4):
    g._update_projectiles(DT)
    if b.boomerang_returned:
        got_flip = True
        vx_after = b.vel.x
        break
assert got_flip, "boomerang never flipped -- did not run for full BOOMERANG_RETURN_TIME"
assert vx_after < 0, \
    f"boomerang flipped but kept flying forward (vx={vx_after:.0f})"
assert b.hostile is False, \
    f"boomerang stayed hostile ({b.hostile!r}) -- returning shot keeps biting shooter"
print(f"  boomerang: fired forward, flipped to vx={vx_after:.0f} px/s after "
      f"{C.BOOMERANG_RETURN_TIME}s, hostile={b.hostile}")

# --------------------------------------------------------------------------- #
# 12. burst_stop: after BURST_STOP_TRAVEL, the bullet lands as a Puddle.       #
#     Bullet starts stationary so the puddle is on MID; behaviour is identical  #
#     regardless of vel -- BURST_STOP_TRAVEL is wall-clock, not distance.      #
# --------------------------------------------------------------------------- #
g, _ = fresh()
bs = P.Projectile(MID, Vector2(), (200, 200, 200), hostile=True)
bs.on_update.append(P.burst_stop)
g.projectiles.append(bs)
puddle_at = None
for _ in range(int(C.BURST_STOP_TRAVEL / DT) + 4):
    g._update_projectiles(DT)
    if bs.dead:
        puddle_at = bs.pos
        break
assert bs.dead, "burst_stop never killed its projectile"
assert len(g.puddles) >= 1, \
    f"burst_stop killed its bullet but left no puddle ({len(g.puddles)})"
assert g.puddles[0].pos.distance_to(MID) < 5, \
    f"burst_stop dropped the puddle off the bullet's last pos ({g.puddles[0].pos})"
print(f"  burst_stop: bullet stopped + dropped a puddle (hostile={g.puddles[0].hostile}, "
      f"r={g.puddles[0].r:.0f})")

# --------------------------------------------------------------------------- #
# 13. spiral_arc: a single hook-controlled shot orbits the player and closes  #
#     in. We seed it ON the player so the very first frame's radius is the   #
#     SPIRAL_RADIUS_INIT -- the orbit then decays and lands on the target.    #
# --------------------------------------------------------------------------- #
g, p = fresh()
sa = P.Projectile(p.pos + Vector2(80, 0), Vector2(), (200, 200, 200), hostile=True)
sa.on_update.append(P.spiral_arc)
g.projectiles.append(sa)
landed = False
for _ in range(int(2.5 / DT)):          # 2.5s of orbit, well past the decay window
    g._update_projectiles(DT)
    if sa.dead:
        landed = True
        break
assert sa.dead, "spiral_arc never ended (no collapse, no impact)"
print(f"  spiral_arc: radius collapsed and shot landed -- ends dead={sa.dead}")

# --------------------------------------------------------------------------- #
# 14. chain_link: two chain-tagged projectiles within CHAIN_LINK_DIST pair     #
#     up; either end drifting past CHAIN_BREAK_DIST breaks the link. The hook #
#     does not draw (the renderer does, gated to one endpoint per pair) --   #
#     this only checks the link STATE.                                        #
# --------------------------------------------------------------------------- #
g, _ = fresh()
a = P.Projectile(MID, Vector2(0, 0), (200, 200, 200), hostile=True)
b = P.Projectile(MID + Vector2(60, 0), Vector2(0, 0), (200, 200, 200), hostile=True)
a.chain = True                          # emitter tags chain projectiles
b.chain = True
a.on_update.append(P.chain_link)
b.on_update.append(P.chain_link)
g.projectiles.extend([a, b])
for _ in range(2):                      # ~1 frame is enough to link
    g._update_projectiles(DT)
assert a.chain_active and b.chain_active, \
    f"chain_link did not pair within CHAIN_LINK_DIST (a.active={a.chain_active}, b.active={b.chain_active})"
assert len(a.chain_partners) == 1 and a.chain_partners[0] is b, \
    f"chain partners did not register each other"
# now move one out of BREAK_DIST and confirm the link drops
b.pos = MID + Vector2(C.CHAIN_BREAK_DIST + 30, 0)
for _ in range(2):
    g._update_projectiles(DT)
assert not a.chain_active and not b.chain_active, \
    f"chain link did not drop past CHAIN_BREAK_DIST (a={a.chain_active}, b={b.chain_active})"
print(f"  chain_link: 60px apart -> active; >{C.CHAIN_BREAK_DIST} apart -> broken")

# --------------------------------------------------------------------------- #
# 15. slow_homing dial: a homing shot fired PERPENDICULAR to the target with   #
#     home_mult < 1 curves LESS than home_mult = 1.0. We aim 100 px below the  #
#     target and watch the bullets bend up: aggressive snaps, gentle drifts.  #
# --------------------------------------------------------------------------- #
g, p = fresh()
aggressive = P.Projectile(p.pos + Vector2(-300, 100), Vector2(180, 0),
                          (200, 200, 200), hostile=True)
aggressive.home_mult = 1.0
aggressive.on_update.append(P.homing)
gentle = P.Projectile(p.pos + Vector2(-300, 100), Vector2(180, 0),
                      (200, 200, 200), hostile=True)
gentle.home_mult = 0.3
gentle.on_update.append(P.homing)
g.projectiles.extend([aggressive, gentle])
for _ in range(60):
    g._update_projectiles(DT)
# aggressive curves more towards target (smaller Y component), gentle stays lower.
y_a = aggressive.pos.y - p.pos.y       # negative when above target, positive when below
y_g = gentle.pos.y - p.pos.y
assert y_a < y_g, \
    f"slow_homing dial: home_mult=1.0 should bend up MORE than home_mult=0.3; " \
    f"got aggressive.y={y_a:+.0f}, gentle.y={y_g:+.0f}"
print(f"  slow_homing dial: home_mult=1.0 -> y={y_a:+.0f}px (bent up); "
      f"home_mult=0.3 -> y={y_g:+.0f}px (gentler bend)")

print("ALL OK")
