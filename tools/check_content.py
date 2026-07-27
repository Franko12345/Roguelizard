"""Assert the #104 content: the emitter migration, the two new enemies, the
stackable player modifiers and the tongue charm.

Seven things have to hold or the issue is decoration:

1. **The three old shooters fire through the emitter.** Their tick calls
   ``genome.shot['fn']`` -- swap that dial for a recorder and the tick calls the
   recorder. No projectile is built in ``ranged.py`` any more.
2. **A species' shot is data.** Point the CUSPIDOR's dial at ``radial_burst``
   and it fires a ring, with no code touched.
3. **The ANTECIPADOR leads.** Its shots aim at where the target is GOING, its
   on-ground marker shows exactly that point, and against a still target the
   lead collapses to a plain aimed shot.
4. **The MORTEIRO telegraphs a footprint BEFORE it arms.** Pixels on the ground
   at the marked point, drawn away from its own body, while no puddle exists
   yet -- and exactly one puddle when the arm timer runs out.
5. **``MORTAR_LIFE < MORTAR_CD``.** The Acido / venom-puddle / sting-slow bug,
   asserted so it cannot come back a fourth time.
6. **The player's shot modifiers stack** (and an enemy's do not).
7. **The card table was re-tuned, not appended to.** Every card that was not
   deliberately trimmed keeps its share of the roll.

Run:  python tools/check_content.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render import display
from lagarto.render.camera import Camera
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.creatures import species
from lagarto.creatures.ai import BEHAVIORS
from lagarto.creatures.ai import ranged
from lagarto.combat import emitter, charms
from lagarto.combat.evolution import mutations as mut
display.init()
DT = 1 / 60
MID = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)


def fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    g.projectiles = []
    g.puddles = []
    g.enemies = []
    g.dt_last = DT
    p = g.players[0]
    p.pos = Vector2(MID)
    p.vel = Vector2()
    return g, p


def run(e, g, target, frames=600, stop=None):
    """Step one enemy's behaviour tick directly; stop when ``stop`` says so."""
    tick = BEHAVIORS[e.genome.behavior]
    for i in range(frames):
        tick(e, g, DT, target)
        g._update_projectiles(DT)
        for pud in g.puddles:
            pud.update(DT, g)
        g.puddles = [q for q in g.puddles if not q.dead]
        e.shoot_cd = max(0.0, e.shoot_cd - DT)
        if stop and stop(i):
            return i
    return None


# --------------------------------------------------------------------------- #
# 1. the three old shooters fire through the emitter and nowhere else          #
# --------------------------------------------------------------------------- #
src = open('lagarto/creatures/ai/ranged.py').read()
for bad in ('game_spit(', 'Projectile(', 'leave_puddle('):
    assert bad not in src, f"ranged.py still builds its own shot ({bad})"

for key, behav in (('spitter', 'ranged'), ('gunner', 'gunner'), ('venomer', 'venom')):
    dials = species.SPECIES[key]['genome'].shot
    assert dials and dials['fn'].__module__ == 'lagarto.combat.emitter', \
        f"{key}'s shot does not come from the emitter: {dials}"
    g, p = fresh()
    e = species.make(key, MID + Vector2(340, 0))
    seen = []
    e.genome.shot = dict(dials, fn=lambda *a: seen.append(a))
    run(e, g, p, stop=lambda i: seen)
    assert seen, f"{behav}_tick never called its own pattern"
    shooter, game, target, d = seen[0]
    assert (shooter is e and game is g and target is p), \
        f"{behav}_tick called the pattern with the wrong arguments"
    assert d is e.genome.shot, f"{behav}_tick passed dials that are not the genome's"
print(f"  emitter: spitter/gunner/venomer all fire genome.shot['fn'] "
      f"({', '.join(species.SPECIES[k]['genome'].shot['fn'].__name__ for k in ('spitter', 'gunner', 'venomer'))})")

# --------------------------------------------------------------------------- #
# 2. the pattern is DATA: same species, different dial, different arrangement  #
# --------------------------------------------------------------------------- #
g, p = fresh()
e = species.make('spitter', MID + Vector2(340, 0))
run(e, g, p, stop=lambda i: g.projectiles)
one = len(g.projectiles)
g, p = fresh()
e = species.make('spitter', MID + Vector2(340, 0))
# count=7 on purpose: it is neither the fan's default nor the radial's, so a
# pattern that ignores the caller's dials cannot pass this by coincidence
e.genome.shot = dict(fn=emitter.radial_burst, count=7)
run(e, g, p, stop=lambda i: g.projectiles)
ring = len(g.projectiles)
assert one == 1 and ring == 7, \
    f"a dial edit did not change the arrangement ({one} -> {ring}, expected 1 -> 7)"
print(f"  data: the CUSPIDOR fires {one} shot on its own dials and {ring} on a "
      f"radial dial -- no code between the two")

# --------------------------------------------------------------------------- #
# 3. the ANTECIPADOR aims where the target is GOING                            #
# --------------------------------------------------------------------------- #
assert 'lead' in BEHAVIORS and 'mortar' in BEHAVIORS, "the new behaviours are not dispatched"


def sniper_shot(vel):
    """Fire one ANTECIPADOR at a target moving at ``vel``; return
    (marker point, first bullet's velocity, mouth, target)."""
    g, p = fresh()
    p.vel = Vector2(vel)
    e = species.make('sniper', MID + Vector2(360, 0))
    mark = []
    tick = BEHAVIORS['lead']
    for _ in range(600):
        p.pos = Vector2(MID)              # held still: only the VELOCITY leads
        p.vel = Vector2(vel)
        tick(e, g, DT, p)
        if e.shoot_charge > 0 and getattr(e, '_rain_points', None):
            mark = list(e._rain_points)
        e.shoot_cd = max(0.0, e.shoot_cd - DT)
        if g.projectiles:
            break
    assert g.projectiles, "the ANTECIPADOR never fired"
    return mark, g.projectiles[0].vel, e.spine.joints[0], p


class _At:
    """The only thing lead_point wants from a shooter is where its head is."""
    def __init__(self, pos):
        self.spine = type('S', (), {'joints': [Vector2(pos)]})()


mark, shot_vel, mouth, p = sniper_shot((0, 260))
want = emitter.lead_point(_At(mouth), p, {'lead': C.SNIPER_LEAD,
                                          'shot_speed': C.SNIPER_SPEED})
assert mark and mark[0].distance_to(want) < 1e-6, \
    f"the marker showed {mark} but the lead point is {want} -- the telegraph lies"
lead_dir = (want - mouth).normalize()
now_dir = (p.pos - mouth).normalize()
assert shot_vel.normalize().dot(lead_dir) > 0.999, \
    "the shot did not go where the marker said"
gap = shot_vel.normalize().angle_to(now_dir)
assert abs(gap) > 8, f"the 'lead' shot is aimed within {abs(gap):.1f} deg of the " \
                     f"target's CURRENT position -- it is not leading anything"
still_mark, still_vel, still_mouth, still_p = sniper_shot((0, 0))
assert abs(still_vel.normalize().angle_to((still_p.pos - still_mouth).normalize())) < 1e-3, \
    "a motionless target still got led -- standing still has to be an answer"

# The assertion that actually matters is not the formula, it is the OUTCOME: a
# straight-line runner at constant speed is the case a leading shot must hit,
# and the one the fixed-seconds lead missed at every range. Fly the shot and
# measure. The error has to stay flat across distance -- a lead that is a
# constant number of seconds instead of the flight time drifts linearly, which
# is exactly how this shipped broken (44 px at 150, 172 px at 450).
misses = []
for dist in (150, 250, 350, 450):
    g2, p2 = fresh()
    e2 = species.make('sniper', MID + Vector2(dist, 0))
    g2.enemies.append(e2)
    closest = 1e9
    for _ in range(900):
        p2.pos += Vector2(0, 190) * DT
        p2.vel = Vector2(0, 190)
        p2.spine.resolve(p2.pos)
        e2.update(DT, g2)
        for pr in list(g2.projectiles):
            pr.update(DT, g2)
            if pr.hostile:
                closest = min(closest, pr.pos.distance_to(p2.pos))
    misses.append(closest)
body_r = p.max_r
assert max(misses) < body_r * 1.5, \
    f"the ANTECIPADOR misses a straight-line runner by up to {max(misses):.0f} px " \
    f"against a {body_r:.0f} px body -- {[round(m) for m in misses]} by range"
assert misses[-1] - misses[0] < body_r * 0.6, \
    f"the miss grows with distance ({misses[0]:.0f} px -> {misses[-1]:.0f} px): " \
    f"the lead is a fixed time again, not the flight time"
print(f"  lead: a target at 260 px/s is shot {abs(gap):.1f} deg ahead of itself; "
      f"a still one is shot dead on")
print(f"  lead hits: a straight-line runner is missed by "
      f"{'/'.join(f'{m:.0f}' for m in misses)} px at 150/250/350/450 px of range "
      f"(body is {body_r:.0f} px)")

# --------------------------------------------------------------------------- #
# 4. the MORTEIRO draws its footprint on the ground BEFORE it arms             #
# --------------------------------------------------------------------------- #
g, p = fresh()
e = species.make('mortar', MID + Vector2(330, 0))
tick = BEHAVIORS['mortar']
armed_at = None
saw_mark = False
for i in range(900):
    tick(e, g, DT, p)
    e.shoot_cd = max(0.0, e.shoot_cd - DT)
    if e.shoot_charge > 0 and getattr(e, '_rain_points', None):
        if not saw_mark:
            saw_mark = True
            mark_pt = Vector2(e._rain_points[0])
            assert not g.puddles, "the puddle existed before the footprint finished"
            # ... and it is drawn, on the ground, away from the creature's body
            cam = Camera()
            cam.pos = Vector2(mark_pt)
            surf = pygame.Surface((C.WIDTH, C.HEIGHT))
            surf.fill((0, 0, 0))
            e.on_screen = True
            e.draw(surf, cam)
            cx, cy = cam.w2s(mark_pt)
            ring_px = 0
            for k in range(72):
                a = Vector2(1, 0).rotate(k * 5)
                for rad in range(4, int(C.MORTAR_R) + 4):
                    x, y = int(cx + a.x * rad), int(cy + a.y * rad)
                    if 0 <= x < C.WIDTH and 0 <= y < C.HEIGHT and surf.get_at((x, y))[:3] != (0, 0, 0):
                        ring_px += 1
                        break
            assert ring_px > 60, \
                f"only {ring_px}/72 directions of the footprint are drawn -- " \
                f"'am I inside?' is unanswerable"
            assert mark_pt.distance_to(e.pos) > e.max_r * 2, \
                "the footprint is on top of the MORTEIRO, not on the ground it is denying"
    if g.puddles and armed_at is None:
        armed_at = i
        break
assert saw_mark, "the MORTEIRO never marked the ground"
assert armed_at is not None, "the MORTEIRO never armed"
assert len(g.puddles) == 1 and g.puddles[0].pos.distance_to(mark_pt) < 1e-6, \
    f"the puddle did not land on the marked spot ({len(g.puddles)} puddles)"
arm_frames = C.MORTAR_ARM / DT
assert arm_frames >= 27, f"the footprint only shows for {arm_frames:.0f} frames"
print(f"  footprint: {ring_px}/72 directions drawn for {arm_frames:.0f} frames "
      f"({mark_pt.distance_to(e.pos):.0f} px from its own body), then one puddle on the mark")

# --------------------------------------------------------------------------- #
# 5. an effect can never outlive the cooldown that reapplies it                #
# --------------------------------------------------------------------------- #
for life, cd, who in ((C.MORTAR_LIFE, C.MORTAR_CD, 'MORTEIRO'),
                      (C.VENOM_PUDDLE_LIFE, C.VENOM_CD, 'ENVENENADOR')):
    assert life < cd, f"{who}: puddle life {life} >= cooldown {cd} -- it stacks with itself"
print(f"  puddles: MORTEIRO {C.MORTAR_LIFE}s < {C.MORTAR_CD}s cd, "
      f"ENVENENADOR {C.VENOM_PUDDLE_LIFE}s < {C.VENOM_CD}s cd")

# --------------------------------------------------------------------------- #
# 6. the player STACKS shot modifiers; the enemy wears one                     #
# --------------------------------------------------------------------------- #
from lagarto.combat import projectile as P
g, p = fresh()


def player_shot():
    pr = P.spit(p.pos, p.pos + Vector2(100, 0), (200, 200, 200), hostile=False)
    g.spawn_projectile(pr)
    return pr


plain = player_shot()
assert not plain.on_update, f"a shot with no modifiers owned still got {plain.on_update}"
mut.MUTATIONS['rebote'].apply(p, g)
mut.MUTATIONS['rebote'].apply(p, g)
mut.MUTATIONS['rastreio'].apply(p, g)
stacked = player_shot()
assert [f.__name__ for f in stacked.on_update] == ['bounce', 'homing'], \
    f"the modifiers did not stack on one bullet: {[f.__name__ for f in stacked.on_update]}"
assert stacked.bounces_left == 2, f"two Rebotes gave {stacked.bounces_left} bounces"
assert stacked.home_mult == 1, f"one Rastreio gave home_mult {stacked.home_mult}"
hostile = P.spit(p.pos, p.pos + Vector2(100, 0), (200, 200, 200), hostile=True)
g.spawn_projectile(hostile)
assert not hostile.on_update, "the player's modifiers leaked onto an enemy bullet"
print(f"  stacking: 2x Rebote + 1x Rastreio = {[f.__name__ for f in stacked.on_update]} "
      f"on one bullet ({stacked.bounces_left} bounces); enemy shots unaffected")

# --------------------------------------------------------------------------- #
# 7. the card table was re-tuned, not appended to                              #
# --------------------------------------------------------------------------- #
# The table exactly as it stood before #104 (18 cards). A new card is a share of
# this, never a free addition.
BEFORE = {'health': 1.0, 'speed': 1.0, 'dash': 1.0, 'energy': 1.0, 'regen': 0.8,
          'xp': 1.0, 'tongue': 1.0, 'thorns': 1.0, 'spikes': 1.0, 'plates': 1.0,
          'horns': 0.9, 'legs': 0.9, 'venom': 0.8, 'wings': 0.7, 'might': 1.2,
          'area': 1.1, 'haste': 1.1, 'amount': 0.9}
TRIMMED = {'tongue', 'spikes', 'plates', 'horns', 'legs'}   # paid for the new rows
now = {m.id: m.weight for m in mut.MUTATIONS_LIST}
assert set(BEFORE) - set(now) == set(), f"a card vanished: {set(BEFORE) - set(now)}"
new_ids = set(now) - set(BEFORE)
assert new_ids == {'rebote', 'rastreio'}, f"unexpected new cards: {new_ids}"
t0, t1 = sum(BEFORE.values()), sum(now.values())
worst, worst_id = 0.0, None
for cid, w in BEFORE.items():
    if cid in TRIMMED:
        assert now[cid] < w, f"{cid} is listed as trimmed but kept its weight"
        continue
    assert now[cid] == w, f"{cid} changed weight without being declared trimmed"
    drop = 1 - (now[cid] / t1) / (w / t0)
    if drop > worst:
        worst, worst_id = drop, cid
assert worst < 0.06, \
    f"{worst_id} lost {worst * 100:.1f}% of its share -- the new rows were appended, not paid for"
new_share = sum(now[c] for c in new_ids) / t1
assert new_share < 0.11, f"the two new cards took {new_share * 100:.1f}% of the table"
print(f"  weights: table {t0:.1f} -> {t1:.1f} over {len(BEFORE)} -> {len(now)} cards; "
      f"untouched cards lost {worst * 100:.1f}% of their share "
      f"(a bare append would have cost {(1 - t0 / (t0 + sum(now[c] for c in new_ids))) * 100:.1f}%)")

# --------------------------------------------------------------------------- #
# 8. the tongue power-up: exactly one, and it is a deliberate choice           #
# --------------------------------------------------------------------------- #
assert 'dardo' in charms.CHARMS, "the Lingua-Dardo charm is missing"
assert all(m.id != 'dardo' for m in mut.MUTATIONS_LIST), \
    "the tongue shot is also a random level-up card -- it is meant to be a choice"
g, p = fresh()
p.energy = p.max_energy
p._launch_tongue(g)
assert not g.projectiles, "the plain tongue fired a projectile"
p.tongue_t = 0.0
p.gain_charm('dardo', g)
p.equip_charm('dardo', g)
p._launch_tongue(g)
assert len(g.projectiles) == 1 and not g.projectiles[0].hostile, \
    f"the Lingua-Dardo did not fire ({len(g.projectiles)} shots)"
print(f"  tongue: charm-only (head slot, {charms.CHARMS['dardo'].cost} pollen), "
      f"one dart per launch, none without it")
print("ALL OK")
