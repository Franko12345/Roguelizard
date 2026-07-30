"""Assert boss resistance (issue #119) and Kraken-Mor follow-up (issue #160).

Player bullets were reading as if they interrupted a boss. Two things did:

1. **`slow` had no resistance.** Every source funnels through
   ``Lizard.apply_slow``, and the stack combines with ``min``, so Feromonio at
   level 4 plus a slow projectile took a boss to 40% speed. With movement
   patterns in place that is not a debuff, it is an off switch. The cap lives in
   the shared function -- clamp each source to ``BOSS_SLOW_FLOOR`` and cut its
   duration by ``BOSS_SLOW_TIME_MULT`` -- so the answer cannot diverge per weapon.
2. **The body reaction sold a shove that never happened.** ``knockback = 0``
   turned ``vel = direction * 200 * knockback`` into ``vel = zero``: every chip
   hit killed the boss's momentum. Plus ``hit_flash = 1.0`` pinned under
   continuous fire kept it whitewashed and in the 'hurt' slump pose.

What this measures:

* the floor holds against a stack of every real source, in every order;
* the effective duration is the cut one, for one source and for a stack;
* the SAME stack on a common enemy still produces today's numbers exactly --
  compared against a re-implementation of the pre-#119 formula, value for value;
* the floor survives the real ``steer``/``integrate`` path: a maximally slowed
  boss still covers >=70% of the ground it covers clean, so a movement pattern
  stays legible (an orbit at 40% is not an orbit);
* a hit no longer zeroes a boss's velocity, still shoves a common enemy, and the
  boss's ``hit_flash`` peak stays under the 'hurt' pose threshold;
* the cap is in ONE place: no caller carries its own boss guard.

Run:  python tools/check_boss_resist.py
      python tools/check_boss_resist.py --shot boss_hit_body.png
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import inspect
import pygame
pygame.init()
from pygame import Vector2
from lagarto.core.mathutil import safe_norm
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto.creatures import base as cbase, species
from lagarto.creatures.ai import posing
from lagarto.combat.weapons.pheromone import Feromonio
from lagarto.flow.rounds import make_boss
display.init()
DT = 1 / 60
MID = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)

# Every real source of `slow` that can land on an enemy, worst level first.
# (Feromonio's four levels, the slow projectile in Game._update_projectiles,
# a hostile Puddle carrying Rei Lagarto's scar dials.)
SOURCES = [('feromonio l%d' % (i + 1), lv['slow'], 0.25)
           for i, lv in enumerate(Feromonio.levels)]
SOURCES += [('projetil-lento', 0.5, 1.6),
            ('cicatriz', C.KING_SCAR_SLOW, C.KING_SCAR_TIME)]


def old_apply_slow(mul_now, t_now, mul, dur):
    """The pre-#119 body of ``apply_slow``, verbatim -- the reference every
    non-boss creature must still match."""
    return (min(mul_now, mul) if t_now > 0 else mul), max(t_now, dur)


def fresh():
    return Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
                mode='normal', chars=None)


def boss_at(g, pos, bid='rei_lagarto'):
    b = make_boss(g, bid, 2, pos)
    b.boss_invuln = False           # out of the intro: hittable
    b.boss_ai.state = 'approach'
    return b


g = fresh()
boss = boss_at(g, MID + Vector2(400, 0))
mob = species.make('spitter', MID + Vector2(-400, 0))
g.enemies += [boss, mob]
assert boss.is_boss and not getattr(mob, 'is_boss', False)

# --------------------------------------------------------------------------- #
# 1. the floor holds, however many sources stack and in whatever order        #
# --------------------------------------------------------------------------- #
import itertools
worst = 1.0
for order in itertools.permutations(range(len(SOURCES))):
    boss.slow_mul, boss.slow_t = 1.0, 0.0
    for i in order:
        boss.apply_slow(SOURCES[i][1], SOURCES[i][2])
        assert boss.slow_mul >= C.BOSS_SLOW_FLOOR - 1e-12, \
            f"{SOURCES[i][0]} broke the floor: {boss.slow_mul} < {C.BOSS_SLOW_FLOOR}"
        assert boss._speed_scale() >= C.BOSS_SLOW_FLOOR - 1e-12, \
            f"_speed_scale() fell through the floor: {boss._speed_scale()}"
    worst = min(worst, boss.slow_mul)
raw_worst = min(s[1] for s in SOURCES)
assert worst == C.BOSS_SLOW_FLOOR, f"a full stack settled at {worst}, not the floor"
print(f"  floor: {len(SOURCES)} sources x {len(list(itertools.permutations(range(len(SOURCES)))))} "
      f"orders -> boss never under {worst:.2f} (uncapped stack would be {raw_worst:.2f})")

# --------------------------------------------------------------------------- #
# 2. the duration is the cut one                                              #
# --------------------------------------------------------------------------- #
for name, mul, dur in SOURCES:
    boss.slow_mul, boss.slow_t = 1.0, 0.0
    boss.apply_slow(mul, dur)
    want = dur * C.BOSS_SLOW_TIME_MULT
    assert boss.slow_t == want, f"{name}: boss timer {boss.slow_t} != {want}"
boss.slow_mul, boss.slow_t = 1.0, 0.0
for _, mul, dur in SOURCES:
    boss.apply_slow(mul, dur)
longest = max(d for _, _, d in SOURCES) * C.BOSS_SLOW_TIME_MULT
assert boss.slow_t == longest, f"stacked timer {boss.slow_t} != {longest}"
# and it really expires early: ticking for the UNCUT duration leaves it clean
boss.slow_mul, boss.slow_t = 1.0, 0.0
boss.apply_slow(0.4, 1.6)
for _ in range(int(1.6 * 0.75 / DT)):       # three quarters of the asked-for time
    boss.slow_t = max(0.0, boss.slow_t - DT)
assert boss.slow_t == 0.0 and boss._speed_scale() == 1.0, \
    f"boss still slowed at 75% of the uncut duration ({boss.slow_t:.3f}s left)"
print(f"  duration: every source cut x{C.BOSS_SLOW_TIME_MULT}; "
      f"longest stack {longest:.3f}s (asked {max(d for _, _, d in SOURCES):.2f}s), "
      f"gone before 75% of the uncut window")

# --------------------------------------------------------------------------- #
# 3. a common enemy is untouched -- value for value against the old formula    #
# --------------------------------------------------------------------------- #
for order in itertools.permutations(range(len(SOURCES))):
    mob.slow_mul, mob.slow_t = 1.0, 0.0
    ref_mul, ref_t = 1.0, 0.0
    for i in order:
        _, mul, dur = SOURCES[i]
        mob.apply_slow(mul, dur)
        ref_mul, ref_t = old_apply_slow(ref_mul, ref_t, mul, dur)
        assert mob.slow_mul == ref_mul and mob.slow_t == ref_t, \
            (f"a common enemy changed: got ({mob.slow_mul!r}, {mob.slow_t!r}), "
             f"pre-#119 was ({ref_mul!r}, {ref_t!r})")
        assert repr(mob.slow_mul) == repr(ref_mul) and repr(mob.slow_t) == repr(ref_t)
assert mob.slow_mul == raw_worst < C.BOSS_SLOW_FLOOR, \
    f"the same stack on a mob should still bottom out at {raw_worst}"
# the player is not a boss either: enemy slows keep biting
pl = g.players[0]
pl.slow_mul, pl.slow_t = 1.0, 0.0
pl.apply_slow(0.5, 1.6)
assert (pl.slow_mul, pl.slow_t) == (0.5, 1.6), "the player picked up boss resistance"
print(f"  mob: identical to the pre-#119 formula on every order, bottoming out at "
      f"{mob.slow_mul:.2f}; player unchanged at {pl.slow_mul:.2f}/{pl.slow_t:.2f}s")

# --------------------------------------------------------------------------- #
# 4. the floor survives the real steer/integrate path                         #
# --------------------------------------------------------------------------- #
def travel(creature, slow_mul, seconds=1.5):
    """Ground covered while steering flat out, at a given speed multiplier."""
    creature.pos = Vector2(MID)
    creature.vel = Vector2()
    creature.spine.resolve(creature.pos)
    creature.slow_mul, creature.slow_t = slow_mul, 99.0
    start = Vector2(creature.pos)
    for _ in range(int(seconds / DT)):
        creature.steer(Vector2(1, 0), DT, C.BOSS_APPROACH_SPEED)
        creature.integrate(DT)
    return creature.pos.distance_to(start)


clean = travel(boss, 1.0)
boss.slow_mul, boss.slow_t = 1.0, 0.0
for _, mul, dur in SOURCES:                 # the real worst case, through apply_slow
    boss.apply_slow(mul, dur)
capped = travel(boss, boss.slow_mul)
uncapped = travel(boss, raw_worst)          # what it used to be
ratio, was = capped / clean, uncapped / clean
assert ratio >= C.BOSS_SLOW_FLOOR - 0.05, \
    f"a maximally slowed boss only covered {ratio:.0%} of its ground -- pattern unreadable"
assert ratio <= 0.95, f"the slow stopped being felt at all ({ratio:.0%} of full speed)"
assert was < ratio - 0.1, "the cap made no measurable difference"
print(f"  movement: 1.5s of approach covers {capped:.0f}px vs {clean:.0f}px clean "
      f"({ratio:.0%}); uncapped it was {uncapped:.0f}px ({was:.0%})")

# --------------------------------------------------------------------------- #
# 5. the body reaction: massive, not staggering (cosmetic only)               #
# --------------------------------------------------------------------------- #
HURT_T = 0.5            # AILizard._pose_now's threshold for the 'hurt' slump
shove = Vector2(1, 0)


def hammer(creature, mode='live', hits=40):
    """Run a creature flat out for ``hits`` frames and report how far it got.

    ``mode``: 'live' takes a hit every frame, 'clean' takes none, 'old' replays
    the pre-#119 reaction (``vel = direction * 200 * knockback``, flash 1.0)
    verbatim. Returns (distance, peak hit_flash, slowest speed seen, frames spent
    in the 'hurt' slump pose).
    """
    creature.pos = Vector2(MID)
    creature.vel = Vector2(creature.max_speed, 0)
    creature.spine.resolve(creature.pos)
    creature.hit_flash = 0.0
    creature.slow_mul, creature.slow_t = 1.0, 0.0
    start = Vector2(creature.pos)
    flash, lowest, slumped = 0.0, creature.vel.length(), 0
    for _ in range(hits):
        creature.hp = creature.max_hp        # never let it die mid-run
        if mode != 'clean':
            creature.take_hit(g, shove, 1)
        if mode == 'old':
            creature.hit_flash = 1.0
            creature.vel = shove * 200 * creature.genome.knockback
        flash = max(flash, creature.hit_flash)
        lowest = min(lowest, creature.vel.length())
        slumped += creature._pose_now('hunt') == 'hurt'
        creature.steer(Vector2(1, 0), DT)
        creature.integrate(DT)
    return creature.pos.distance_to(start), flash, lowest, slumped


b_live, b_flash, b_low, b_slump = hammer(boss, 'live')
b_clean, _, _, _ = hammer(boss, 'clean')
b_old, o_flash, o_low, o_slump = hammer(boss, 'old')
# the strongest statement available: for a boss, taking a hit no longer touches
# the body's motion AT ALL, so a boss under continuous fire traces exactly the
# path an unhit one traces. The old reaction zeroed the momentum every frame.
assert b_live == b_clean, \
    f"fire still bends the boss's path ({b_live:.3f}px hit vs {b_clean:.3f}px clean)"
assert o_low == 0.0 and b_low > 0.0, \
    f"the pre-#119 reaction should zero the momentum (min speed was {o_low:.1f})"
assert b_live > b_old * 1.5, \
    f"the boss covers {b_live:.0f}px under fire, barely up from {b_old:.0f}px before"
assert b_flash < HURT_T, \
    f"boss hit_flash peaks at {b_flash} -- still trips the 'hurt' slump at {HURT_T}"
assert b_flash > 0.2, "hit_flash vanished -- there is no hit feedback left"
assert o_flash >= HURT_T > b_flash          # the flash is what changed, not its absence
assert posing.POSE_STATES['hurt'][0] < 1.0  # the slump we are staying out of
assert b_slump == 0 and o_slump == 40, \
    f"the boss slumped on {b_slump}/40 frames (pre-#119: {o_slump}/40)"
print(f"  body: 40 hits move the boss {b_live:.0f}px, same as unhit ({b_clean:.0f}px); "
      f"pre-#119 it managed {b_old:.0f}px. flash peaks {b_flash:.2f} < {HURT_T} 'hurt', "
      f"0/40 frames slumped")

mob_live = hammer(mob, 'live')
mob_old = hammer(mob, 'old')
assert mob_live == mob_old, \
    f"a common enemy's hit reaction changed: {mob_live} vs pre-#119 {mob_old}"
m_live, m_flash, m_low, m_slump = mob_live
assert m_flash == 1.0 and m_slump == 40, "a mob stopped flinching"
# and the shove itself: a mob's velocity is still REPLACED by the hit direction,
# a boss's is left alone
for c, shoved in ((mob, True), (boss, False)):
    c.vel = Vector2(0, -c.max_speed)         # heading away from the shove
    was = Vector2(c.vel)
    c.hp = c.max_hp
    c.take_hit(g, shove, 1)
    want = shove * 200 * c.genome.knockback if shoved else was
    assert c.vel == want, f"{'mob' if shoved else 'boss'} vel {c.vel} != {want}"
print(f"  mob: reaction byte-for-byte the old one ({m_live:.0f}px, flash {m_flash:.2f}, "
      f"{m_slump}/40 frames slumped, vel replaced by the shove)")

# damage, hitbox and hit_test are explicitly out of scope -- prove they moved not
hp0 = boss.hp = boss.max_hp
head = boss.hit_test(boss.spine.joints[0])
body = boss.hit_test(boss.spine.joints[len(boss.spine.joints) // 2])
assert head == 'head' and body == 'body', f"hit_test changed: {head!r}/{body!r}"
boss.take_hit(g, shove, 25)
assert boss.hp == hp0 - 25, f"a hit for 25 took {hp0 - boss.hp}"
print(f"  untouched: hit_test still head/body, 25 damage still costs 25 hp")

# --------------------------------------------------------------------------- #
# 6. one guard, in the shared function                                        #
# --------------------------------------------------------------------------- #
src = inspect.getsource
assert 'BOSS_SLOW_FLOOR' in src(cbase.Lizard.apply_slow), \
    "the cap left apply_slow -- that is the whole point of #119"
callers = ['lagarto/combat/weapons/pheromone.py', 'lagarto/combat/weapons/base.py',
           'lagarto/combat/emitter.py', 'lagarto/game/loop.py',
           'lagarto/creatures/ai/grapple.py']
for path in callers:
    text = open(path).read()
    assert 'apply_slow' in text, f"{path} stopped being a slow source -- update this list"
    assert 'BOSS_SLOW_FLOOR' not in text and 'BOSS_SLOW_TIME_MULT' not in text, \
        f"{path} grew its own boss guard; the cap belongs to apply_slow alone"
print(f"  one guard: apply_slow caps it, {len(callers)} call sites stay dumb")


def check_kraken_grapple_followup():
    g = fresh()
    b = boss_at(g, MID + Vector2(100, 0), bid='kraken_mor')
    p = g.players[0]
    b.boss_ai.state = 'windup'
    b.boss_ai.pattern_id = 'grapple'
    b.boss_ai.t = 0.0
    b.grapple_cd = 0.0
    b.boss_ai.tick(DT, g)
    assert b.boss_ai.state == 'grappling', "grapple pattern did not enter grappling state"
    b.boss_ai.tick(DT, g)
    assert b.grapple_t > 0, "grapple windup did not start"
    p.pos = MID + Vector2(500, 0)
    for _ in range(int(C.OCTO_WINDUP / DT) + 2):
        b.boss_ai.tick(DT, g)
        if b.boss_ai.state == 'recover':
            break
    assert b.boss_ai.state == 'recover', "missed grapple did not leave grappling state"
    shots = list(g.projectiles)
    assert 3 <= len(shots) <= 5, f"missed grapple fired {len(shots)} shots"
    aim = safe_norm(p.pos - b.spine.joints[0])
    errors = [abs(aim.angle_to(shot.vel)) for shot in shots]
    assert max(errors) <= 15.01, f"follow-up escaped 30-degree cone: {errors}"
    assert all(abs(shot.vel.length() - 180) < 1e-4 for shot in shots), \
        "follow-up speed changed"
    assert all(shot.dmg == 8 and shot.hostile and shot.effect is None for shot in shots), \
        "follow-up projectile dials changed"
    assert b.boss_ai._grapple_followup_fired, "follow-up was not marked fired"
    print(f"  grapple followup: {len(shots)} hostile shots at 180px/s, "
          f"max cone error {max(errors):.1f} degrees")


check_kraken_grapple_followup()

# --------------------------------------------------------------------------- #
# 7. optional: the before/after screenshot of a boss under continuous fire     #
# --------------------------------------------------------------------------- #
if '--shot' in sys.argv:
    out = sys.argv[sys.argv.index('--shot') + 1]
    W, H = C.WIDTH, C.HEIGHT // 2
    strip = pygame.Surface((W, H * 2), 0, 24)
    font = fonts.get(16)
    for row, damped in enumerate((False, True)):
        gg = fresh()
        b = boss_at(gg, MID)
        gg.enemies.append(b)
        gg.cam.pos = Vector2(MID)
        b.vel = Vector2(b.max_speed, 0)
        for _, mul, dur in SOURCES:
            b.apply_slow(mul, dur)
        if not damped:                     # replay the pre-#119 reaction verbatim
            b.slow_mul = raw_worst
        for i in range(90):
            b.hp = b.max_hp
            b.take_hit(gg, shove, 1)
            if not damped:
                b.hit_flash = 1.0
                b.vel = shove * 200 * b.genome.knockback
            posing.apply_state_pose(b, b._pose_now('hunt'), DT)
            b.steer(Vector2(1, 0), DT)
            b.integrate(DT)
            gg.fx.update(DT)
        # cam.w2s centres on the DISPLAY, so draw full-size and crop the middle
        # band -- a half-height surface would put the camera on its bottom edge
        full = pygame.Surface((C.WIDTH, C.HEIGHT), 0, 24)
        full.fill((22, 24, 32))
        gg.cam.zoom = 0.45                 # a boss body is 2.3x a normal one
        gg.cam.pos = Vector2(b.spine.joints[len(b.spine.joints) // 2])
        b.draw(full, gg.cam)
        strip.blit(full, (0, row * H), pygame.Rect(0, (C.HEIGHT - H) // 2, W, H))
        label = ("depois: mantem a velocidade, flash %.2f, sem pose 'hurt'" % b.hit_flash
                 if damped else
                 "antes: velocidade zerada a cada acerto, flash %.2f, pose 'hurt'" % b.hit_flash)
        strip.blit(font.render(label, True, (240, 240, 240)), (12, row * H + 10))
        strip.blit(font.render("vel %.0f px/s  |  slow x%.2f" % (b.vel.length(), b.slow_mul),
                               True, (190, 200, 215)), (12, row * H + 30))
    pygame.draw.line(strip, (90, 96, 110), (0, H), (W, H), 2)
    tmp = out + '.bmp'
    pygame.image.save(strip, tmp)          # dummy driver: BMP first, then convert
    pygame.image.save(pygame.image.load(tmp), out)
    os.remove(tmp)
    print(f"  shot: {out}")

print("ALL OK")
