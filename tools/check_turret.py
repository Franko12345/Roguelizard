"""Assert the #111 Deployable: the Torreta is a body you plant, not a shot.

Five things have to hold or the build is decoration:

(a) **It does not move.** Planted, it stays on the exact pixel it was planted
    on -- while it is shooting, while the player stands on top of it, and while
    an enemy is beating on it. A Deployable that drifts is no longer the thing
    the player chose a spot for.
(b) **It fires through the shared emitter and nowhere else** (ADR-0012): the
    tick calls ``genome.shot['fn']`` -- swap that dial for a recorder and the
    recorder is what runs -- and the bullet that comes out carries ``might``
    and reads as friendly (ADR-0014).
(c) **``player.amount + 1`` plants one more turret**, i.e. the VS passive that
    already means "+1 projectile" means "+1 body" here with no card of its own.
(d) **An enemy takes its HP to zero and it leaves ``game.friends``.** The
    turret is a target you offered in place of your own.
(e) **The enemy's aggro transfers to it** and the enemy walks at the turret
    instead of at the player -- the whole point is space, not damage.

Run:  python tools/check_turret.py
"""
import os, sys, time
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.game import state_play
from lagarto.input.controllers import make_controllers
from lagarto.creatures import species
from lagarto.combat import weapons
from lagarto.world.collision import separate
display.init()
DT = 1 / 60
MID = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
TORRETA = weapons.WEAPONS['torreta']


def fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    g.projectiles = []
    g.puddles = []
    g.enemies = []
    g.friends = []
    g.dt_last = DT
    # the round would otherwise start on its own 2.5s timer and spawn a wave on
    # top of the fight being measured; the loop itself is left untouched
    g.rounds.timer = 1e9
    p = g.players[0]
    p.pos = Vector2(MID)
    p.vel = Vector2()
    return g, p


def plant(g, p, level=1):
    """One cast of the weapon, at the player's feet. Returns the turrets."""
    TORRETA.tick(p, g, DT, TORRETA.new_state(), level)
    return [f for f in g.friends if f.kind == 'turret']


# --------------------------------------------------------------------------- #
# the weapon plants a body and builds no bullet of its own                     #
# --------------------------------------------------------------------------- #
src = open('lagarto/combat/weapons/torreta.py').read()
for bad in ('Projectile(', 'spawn_projectile', 'game_spit('):
    assert bad not in src, f"the weapon builds its own shot ({bad})"

g, p = fresh()
ts = plant(g, p)
assert len(ts) == 1, f"one cast planted {len(ts)} turrets"
t = ts[0]
assert t.kind == 'turret', f"planted a {t.kind!r}, not a turret"
assert t.pos == p.pos, f"planted at {t.pos}, not at the player ({p.pos})"
assert t.hp > 0 and t.max_hp == t.hp, "the turret has no health to lose"
print(f"  plant: one cast -> 1 turret at the player's own position, {t.hp} hp")

# --------------------------------------------------------------------------- #
# (a) it does not move -- not while shooting, shoved or beaten                 #
# --------------------------------------------------------------------------- #
g, p = fresh()
t = plant(g, p)[0]
start = Vector2(t.pos)
foe = species.make('runner', MID + Vector2(220, 0))
foe.hp = 10 ** 6                       # outlives the test: this measures motion
g.enemies.append(foe)
for _ in range(180):
    t.update(DT, g)
    # the player standing on its own turret, and the enemy body on top of it:
    # both would push any other creature (collision.separate). The spines are
    # re-resolved because separation samples JOINTS, not `pos` -- moving the
    # position alone would leave the bodies where they were and touch nothing.
    for other in (p, foe):
        other.pos = Vector2(t.pos)
        other.spine.resolve(other.pos)
    separate([p, foe, t])
    t.take_hit(g, Vector2(1, 0), 0)    # a hit's knockback must not slide it
fired = len(g.projectiles)
assert fired > 0, "the turret never fired -- (a) would pass on a dead object"
assert t.pos == start, f"the turret drifted {t.pos - start} over 180 frames"
assert t.spine.joints[0] == start, "the turret's body left its own position"
print(f"  (a) still: 0.00 px moved over 180 frames while firing {fired} shots, "
      f"with a player and an enemy standing on it")

# --------------------------------------------------------------------------- #
# (b) it fires through the emitter, and the bullet carries `might`             #
# --------------------------------------------------------------------------- #
g, p = fresh()
t = plant(g, p)[0]
assert t.genome.shot['fn'].__module__ == 'lagarto.combat.emitter', \
    f"the turret's shot does not come from the emitter: {t.genome.shot}"
foe = species.make('runner', MID + Vector2(150, 0))
foe.hp = 10 ** 6
g.enemies.append(foe)
seen = []
t.genome.shot = dict(t.genome.shot, fn=lambda *a: seen.append(a))
for _ in range(120):
    t.update(DT, g)
    if seen:
        break
assert seen, "the turret tick never called its own pattern"
shooter, game_, target, dials = seen[0]
assert shooter is t and game_ is g and target is foe, \
    "the turret called the pattern with the wrong arguments"
assert dials is t.genome.shot, "the turret passed dials that are not the genome's"
assert not g.projectiles, "a bullet appeared with the pattern replaced -- " \
                          "something else on this path builds one"

dmg = {}
for might in (1.0, 3.0):
    g, p = fresh()
    p.might = might
    t = plant(g, p)[0]
    foe = species.make('runner', MID + Vector2(150, 0))
    foe.hp = 10 ** 6
    foe.sync_max_hp()
    g.enemies.append(foe)
    hp0 = foe.hp
    for _ in range(120):
        t.update(DT, g)
        if g.projectiles:
            break
    assert g.projectiles, f"the turret fired nothing at might {might}"
    assert all(not pr.hostile for pr in g.projectiles), \
        "the turret's bullets are hostile: they would hit the player, not the horde"
    dmg[might] = g.projectiles[0].dmg
    for _ in range(120):                    # let them fly into the enemy
        g._update_projectiles(DT)
        if foe.hp < hp0:
            break
    assert foe.hp < hp0, "the turret's bullets never damaged an enemy"
assert dmg[3.0] == 3 * dmg[1.0], \
    f"might did not scale the turret's shot ({dmg[1.0]} -> {dmg[3.0]})"
print(f"  (b) emitter: the tick calls genome.shot['fn']; its bullet is friendly "
      f"and hits for {dmg[1.0]} at might 1.0 and {dmg[3.0]} at might 3.0")

# --------------------------------------------------------------------------- #
# (c) amount plants one more body; the other two passives read through too     #
# --------------------------------------------------------------------------- #
def cast(**stats):
    """One cast with the four global stats pinned (the meta save carries its own
    haste/might into a fresh Player, which would otherwise be the baseline)."""
    g, p = fresh()
    p.might, p.amount, p.area_mult, p.cooldown_mult = 1.0, 0, 1.0, 1.0
    for k, v in stats.items():
        setattr(p, k, v)
    st = TORRETA.new_state()
    TORRETA.tick(p, g, DT, st, 1)
    return [f for f in g.friends if f.kind == 'turret'], st['t']


base, slow = cast()
more, _ = cast(amount=1)
assert len(more) == len(base) + 1, \
    f"amount +1 planted {len(more)} turrets, expected {len(base) + 1}"
wide, _ = cast(area_mult=2.0)
narrow_r = base[0].genome.shot['range']
assert wide[0].genome.shot['range'] == 2 * narrow_r, \
    f"area did not scale the turret's reach ({narrow_r} -> {wide[0].genome.shot['range']})"
_, fast = cast(cooldown_mult=0.5)
assert fast == slow * 0.5, \
    f"cooldown_mult did not change the plant rate ({slow} -> {fast})"
print(f"  (c) passives: amount {len(base)} -> {len(more)} turrets, area "
      f"{narrow_r:.0f} -> {wide[0].genome.shot['range']:.0f} px of reach, "
      f"cooldown {slow:.1f}s -> {fast:.1f}s")

# --------------------------------------------------------------------------- #
# (d)+(e) the enemy takes the aggro, walks at the turret, and kills it         #
# --------------------------------------------------------------------------- #
g, p = fresh()
t = plant(g, p)[0]
p.pos = MID + Vector2(520, 0)              # the player is the OTHER option
foe = species.make('tank', MID + Vector2(200, 0))
foe.hp = 10 ** 6                           # it outlives the turret on purpose
foe.sync_max_hp()
g.enemies.append(foe)
assert foe.aggro is None, "the enemy started out already aggro'd"
for _ in range(240):
    state_play.update(g, DT)               # the REAL loop, not a hand-rolled one
    if foe.aggro is not None:
        break
assert foe.aggro is t, f"the turret did not steal the aggro (got {foe.aggro})"
start_d = 200.0
hp0 = t.hp
frames = 0
while frames < 2400 and not t.dead:
    state_play.update(g, DT)
    frames += 1
assert foe.pos.distance_to(MID) < start_d, \
    "the enemy never closed on the turret -- the taunt bought no space"
assert foe.pos.distance_to(MID) < foe.pos.distance_to(p.pos), \
    "the enemy ended up nearer the player than the turret it was taunted onto"
assert t.hp <= 0, f"the enemy could not kill the turret ({t.hp}/{hp0} left)"
assert t.dead and t not in g.friends, "the dead turret is still in game.friends"
print(f"  (d) mortal: {hp0} hp gone in {frames} frames of enemy contact, and the "
      f"body left game.friends")
print(f"  (e) aggro: the enemy walked from {start_d:.0f} px to "
      f"{foe.pos.distance_to(MID):.0f} px of the turret, with the player "
      f"{foe.pos.distance_to(p.pos):.0f} px away and ignored")

# --------------------------------------------------------------------------- #
# perf: a full emplacement, updated and drawn, against the frame budget        #
# --------------------------------------------------------------------------- #
g, p = fresh()
p.amount = 7                               # 8 turrets at once
p.pos = Vector2(MID)
ts = plant(g, p, level=TORRETA.maxlevel())
for k in range(6):
    e = species.make('runner', MID + Vector2(0, 150 + k * 20))
    e.hp = 10 ** 6
    g.enemies.append(e)
surf = pygame.Surface((C.WIDTH, C.HEIGHT))
t0 = time.perf_counter()
for _ in range(60):
    state_play.update(g, DT)
    g.draw(surf)
ms = (time.perf_counter() - t0) / 60 * 1000
budget = C.DT * 1000
print(f"  perf: {len(ts)} turrets at max level + {len(g.enemies)} enemies, "
      f"{len(g.projectiles)} bullets live -> {ms:.1f} ms/frame "
      f"(budget {budget:.1f} ms)")
assert ms < budget * 2, f"{ms:.1f} ms/frame is over twice the {budget:.1f} ms budget"

print("check_turret: OK")
