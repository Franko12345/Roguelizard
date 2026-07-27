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
from lagarto.core import fonts, config as C, palette
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
# `squash` is what gets DRAWN: base.py consumes squat_bias into it through a
# smoothed approach, then decays squat_bias for the next frame. Reading
# squat_bias after update() therefore reports a post-decay value that nothing
# renders -- measure the thing on screen.
squat_min = p.squash                 # deepest compression actually drawn
while p.rolling and frames < 60:
    p.update(DT, g)
    peak = min(peak, spread(p))
    squat_min = min(squat_min, p.squash)
    frames += 1
want = round(C.ROLL_TIME / DT)
assert abs(frames - want) <= 2, f"roll lasted {frames} frames, expected ~{want}"
assert p.roll_cd > 0, "roll ended with no cooldown left to serve"
h0 = p.health
p.hit_flash = 0.0            # the hit above never landed, so nothing to clear
assert p.hurt(g, Vector2(1, 0), 10) is True, "i-frames outlived the roll"
assert p.health < h0, "hurt() said it landed but no health moved"

# 2. squash then stretch -- a spring, not a ball.
# The first version collapsed the spine into a spinning disc and this check
# asserted exactly that. Playtest read it as "it just curls you up": the body
# became a blob and you could not tell which way you had gone, which is the one
# thing a dodge has to show. So the assertions are inverted on purpose -- the
# body must compress WITHOUT losing its shape, and it must overshoot on release.
assert p.spine.link == p.spine.link0, \
    "the spine link is being scaled again -- that is the old ball collapse"
assert squat_min < 0.9, \
    f"the body barely compressed: drawn squash bottomed at {squat_min:.2f}"
assert peak > rest * 0.6, \
    f"the body curled into a {peak:.0f}px blob from {rest:.0f}px -- it should " \
    f"squash along its own length, not collapse"
print(f"  squash: drawn squash {squat_min:.2f} at the bottom (rest ~1.00), body "
      f"still {peak:.0f}px of {rest:.0f}px long")

# release: the drawn squash has to pass BACK THROUGH neutral and overshoot,
# then settle. Without the overshoot it is a return, not a spring.
squat_max = 0.0
for _ in range(180):
    p.update(DT, g)
    squat_max = max(squat_max, p.squash)
assert squat_max > 1.03, \
    f"the drawn squash never went past neutral on release (peaked at " \
    f"{squat_max:.2f}) -- that is a return, not a spring"
assert abs(p.squash - 1.0) < 0.03, \
    f"squash settled at {p.squash:.2f} instead of neutral"
assert p.roll_f == 0.0, f"roll_f never came back to 0 ({p.roll_f})"
assert spread(p) > rest * 0.8, "the body never came back to length"
print(f"  release: drawn squash overshoots to {squat_max:.2f}, settles at "
      f"{p.squash:.2f}")

# 2b. the colour has to SAY the i-frames are up, and give the body back after
g, p = fresh()
rest_col = tuple(p.color)
press(p)
p.update(DT, g)                      # the roll starts on this frame, not the press
apart = 0.0
while p.rolling:
    apart = max(apart, sum(abs(a - b) for a, b in zip(p.color, rest_col)))
    p.update(DT, g)
assert apart > 60, \
    f"the body only shifted {apart:.0f} in colour while invulnerable -- nothing " \
    f"on screen says the hit is going to miss"
# and it must not be the hit-flash tint, or "untouchable" reads as "just hurt"
assert tuple(p.color) != tuple(palette.lighten(rest_col, 0.8)), \
    "the i-frame tint is the hit-flash whitening -- the two states collide"
for _ in range(180):
    p.update(DT, g)
assert tuple(p.color) == rest_col, \
    f"the body kept the i-frame tint after the roll ({p.color} vs {rest_col})"
print(f"  i-frames: body shifts {apart:.0f} toward {C.ROLL_IFRAME_COLOR} while "
      f"invulnerable, back to {rest_col} after")

g, p = fresh()
press(p)
p.update(DT, g)
first = p.roll_f
assert 0.0 < first < 0.9, f"the compression snapped on frame 1 (roll_f={first:.2f})"
print(f"  eased: roll_f frame 1 = {first:.2f}")

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
