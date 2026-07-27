"""Assert the rolamento is a real second dodge (issue #103).

Four things have to be true or the verb is decoration:

1. it costs energy, runs on its own cooldown, and gives i-frames -- ``hurt()``
   must bounce while rolling and land once it is over;
2. it deals NO damage -- ``dashing`` stays False, which is what every contact
   damage site keys off (``loop._collisions``, the nest hit, the AI counter);
3. the body reads as a DISC -- the joints collapse inside the body's own
   thickness, get there EASED (never snapped), and give ``spine.link`` back;
4. both co-op control schemes own the button, on keys of their own.

Run:  python tools/check_roll.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from pygame import Vector2
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
display.init()
DT = 1 / 60


def fresh():
    g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
             mode='normal', chars=None)
    p = g.players[0]
    p.energy = p.max_energy
    return g, p


def press(p, held=True):
    """Fake the buffered edge the Controller would hand over."""
    p.ctrl._buf['roll'] = C.INPUT_BUFFER if held else 0.0


def spread(p):
    """Longest distance between any joint and the head -- the body's own size."""
    js = p.spine.joints
    return max(js[0].distance_to(j) for j in js)


# 1. cost, cooldown, i-frames
g, p = fresh()
rest = spread(p)
e0 = p.energy
press(p)
p.update(DT, g)
assert p.rolling, "roll did not fire on the press frame"
spent = e0 - p.energy                # net of one frame of regen, hence the window
assert C.ROLL_COST * 0.9 < spent <= C.ROLL_COST, \
    f"roll cost {spent}, expected ~{C.ROLL_COST}"
assert spent < C.DASH_COST, "the roll has to be the CHEAP dodge"
assert p.hurt(g, Vector2(1, 0), 10) is False, "rolling took damage"
assert not p.dashing, "the roll must not report as a dash (that IS the damage flag)"

# holding the button cannot chain a second roll before the cooldown
frames = 1
peak = spread(p)                     # tightest the body gets while the roll runs
while p.rolling and frames < 60:
    p.update(DT, g)
    peak = min(peak, spread(p))
    frames += 1
want = round(C.ROLL_TIME / DT)
assert abs(frames - want) <= 2, f"roll lasted {frames} frames, expected ~{want}"
assert p.roll_cd > 0, "roll ended with no cooldown left to serve"
h0 = p.health
p.hit_flash = 0.0            # the hit above never landed, so nothing to clear
assert p.hurt(g, Vector2(1, 0), 10) is True, "i-frames outlived the roll"
assert p.health < h0, "hurt() said it landed but no health moved"

# 2. the disc: collapsed to ~one vertebra, and eased into it
assert peak < rest * 0.55, \
    f"body did not collapse: {peak:.1f}px across vs {rest:.1f}px at rest"
assert peak < p.max_r * 2.4, \
    f"the disc is {peak:.1f}px across, wider than the body is thick " \
    f"({p.max_r * 2.0:.1f}px)"
print(f"  disc: {rest:.0f}px of body -> {peak:.0f}px, max_r {p.max_r:.0f}")

g, p = fresh()
press(p)
p.update(DT, g)
first = p.roll_f
assert 0.0 < first < 0.9, f"collapse snapped on frame 1 (roll_f={first:.2f})"
assert p.spine.link > p.spine.link0 * C.ROLL_LINK * 1.5, \
    "the link snapped straight to its collapsed value"
print(f"  eased: roll_f frame 1 = {first:.2f}, link "
      f"{p.spine.link:.1f} of {p.spine.link0:.1f}")

# 3. the collapse UNWINDS on its own, and gives the link back exactly
press(p, held=False)
for _ in range(180):
    p.update(DT, g)
assert p.roll_f == 0.0, f"roll_f never came back to 0 ({p.roll_f})"
assert p.spine.link == p.spine.link0, \
    f"link left shrunk: {p.spine.link} != {p.spine.link0}"
assert spread(p) > rest * 0.8, "the body never uncurled"

# 4. the cooldown really gates the frequency (energy aside)
g, p = fresh()
rolls = 0
for i in range(120):
    press(p)
    p.update(DT, g)
    if p.roll_time == C.ROLL_TIME:      # fired this frame
        rolls += 1
cycle = C.ROLL_TIME + C.ROLL_CD
assert abs(rolls - round(2.0 / cycle)) <= 1, \
    f"{rolls} rolls in 2s, expected ~{2.0 / cycle:.0f} at a {cycle:.2f}s cycle"
print(f"  frequency: {rolls} rolls in 2s ({cycle:.2f}s cycle), "
      f"vs a dash every {p.dash_cooldown:.2f}s")

# 4b. it has to actually CARRY you -- the point of a dodge is leaving where the
# bullet is going. This shipped as a steer multiplier with no impulse: 1.9x for
# 0.15 s moved about a third of a body length, and playtest read it as "tried to
# roll and did not dash". Distance is the thing the player feels, so measure it.
def travel(action):
    g2 = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26),
              mode='normal', chars=None)
    q = g2.players[0]
    q.energy = q.max_energy
    start = Vector2(q.pos)
    for i in range(60):                      # one second of holding a direction
        q.ctrl.move = Vector2(0, 1)
        if i == 0 and action:
            q.ctrl._buf[action] = C.INPUT_BUFFER
        q.update(DT, g2)
    return q.pos.distance_to(start), q


walked, q = travel(None)
rolled, _ = travel('roll')
dashed, _ = travel('dash')
body = q.max_r * 2
assert rolled - walked > body * 2, \
    f"a rolamento adds only {rolled - walked:.0f} px over walking ({body:.0f} px of body) " \
    f"-- it is not carrying you out of anything"
assert rolled < dashed, \
    f"the rolamento ({rolled - walked:.0f} px) covers as much ground as the investida " \
    f"({dashed - walked:.0f} px): the investida has to stay the bigger commitment"
roll_eff = (rolled - walked) / C.ROLL_COST
dash_eff = (dashed - walked) / (C.DASH_COST + 4)
assert roll_eff > dash_eff, \
    "the rolamento is not the cheaper way to cover ground, so nobody will press it"
print(f"  travel: +{rolled - walked:.0f} px per roll vs +{dashed - walked:.0f} px per "
      f"investida ({roll_eff:.1f} vs {dash_eff:.1f} px per energy point)")

# 5. co-op: BOTH control schemes own the button, on different keys
g = Game(2, make_controllers(2, []), fonts.get(16), fonts.get(26),
         mode='normal', chars=None)
p1, p2 = g.players


class Keys(dict):
    """Stands in for pygame's key-state wrapper (modifier keycodes are huge,
    so a flat list cannot index them)."""
    def __missing__(self, k):
        return False


keys = Keys()
keys[pygame.K_LCTRL] = True                  # P1 only
for p in (p1, p2):
    p.energy = p.max_energy
    p.ctrl.poll(keys, (0, 0, 0), g.cam, p.pos, DT)
assert p1.ctrl.roll_edge, "P1 (keyboard+mouse) has no roll button"
assert not p2.ctrl.roll_edge, "P1's roll key also rolls P2"
keys[pygame.K_LCTRL] = False
keys[pygame.K_o] = True                      # P2 only
for p in (p1, p2):
    p.ctrl.poll(keys, (0, 0, 0), g.cam, p.pos, DT)
assert p2.ctrl.roll_edge, "P2 (keyboard fallback) has no roll button"
for p in (p1, p2):
    p.update(DT, g)
assert p1.rolling and p2.rolling, "a buffered roll edge did not reach the player"
# the pad scheme reads it too -- P2 is a GamepadController when a pad is plugged in
from lagarto.input.controllers import GamepadController


class TriggerPad:
    """A pad with the trigger down and nothing else."""
    def move(self): return Vector2()
    def aim(self): return Vector2()
    def dash(self): return False
    def tongue(self): return False
    def whip(self): return False
    def item(self): return False
    def roll(self): return True


gc = GamepadController(TriggerPad())
gc.poll(keys, (0, 0, 0), g.cam, p1.pos, DT)
assert gc.roll_edge and not gc.dash_edge, "the gamepad scheme has no roll input"
print("  coop: P1 LCTRL, P2 O, pad LT/RT -- independent")
print("ALL OK")
