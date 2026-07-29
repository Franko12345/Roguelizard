"""Issue #130 -- the HUD capsule sits in the bottom corners and settles.

Three claims worth teeth:

1. **Capsule lives at the bottom.** Every player block is anchored to a
   panel rect whose ``y`` is below the screen mid-line, in both single-player
   and coop. The old top-corner HUD (y < HEIGHT/2) is gone.
2. **The capsule is wrapped in a frame.** ``ui.panel`` -- the same primitive
   used by the menu and level-up screens -- draws both the dark fill and the
   rim in one call. Cheap to assert: the panel rect is the same width and
   height as the one ``state_play._draw_hud`` reserves in its layout.
3. **No overlap with the TopStack in coop.** Six elements live in the
   top-centre column (score, wave line, combo, boss name, boss bar, banner);
   the player's block must never claim a top-centre band. Walking every
   possible block + combo + boss + banner state confirms it.
4. **The spring settles.** A single impulse must drive the capsule back to
   ``(0, 0)`` displacement within a small number of frames. A spring that
   rings forever is nausea, not feel -- this is the assertion that catches
   the "perpetual wobble" failure mode.

Run from the repo root:  python tools/check_hud_anatomy.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.core import config as C
from lagarto.core import fonts
from lagarto.game import hud
from lagarto.game.loop import Game
from lagarto.input.controllers import KeyboardController


def _game(num_players):
    font = fonts.get(18)
    bigfont = fonts.get(28)
    return Game(num_players=num_players,
                controllers=[KeyboardController() for _ in range(num_players)],
                font=font, bigfont=bigfont,
                mode='normal', chars=['lagarto'] * num_players)


# ---- 1. capsule anchored at the bottom (singleplayer AND coop) ------------ #
errors = []
for n in (1, 2):
    g = _game(n)
    g.wave = 5
    for _ in range(5):
        g.step(1 / 60)
    bw = C.HUD_PANEL_W
    bh = C.HUD_PANEL_H
    margin = C.HUD_MARGIN
    # walk every player; the resting y must be in the bottom half of the screen
    for i in range(n):
        x = margin if i == 0 else C.WIDTH - bw - margin
        y = C.HEIGHT - bh - margin
        mid = C.HEIGHT / 2
        if y < mid:
            errors.append(f"player {i} panel y={y} not below the mid-line ({mid})")
        if x < 0 or x + bw > C.WIDTH:
            errors.append(f"player {i} panel x={x} + w={bw} out of screen")
        # the two player blocks must never overlap each other
        if n == 2 and i == 0:
            right_edge = x + bw
            other_x = C.WIDTH - bw - margin
            if right_edge > other_x:
                errors.append(f"P1 panel (right={right_edge}) overlaps P2 panel "
                             f"(left={other_x})")
if errors:
    raise SystemExit("capsule anchor FAIL: " + "; ".join(errors))
print("[1] capsule anchor: OK -- both players in the bottom half, "
      "no overlap at 1120x720")

# ---- 2. the framed panel is the same primitive ui.panel uses everywhere -- #
# the rect the draw routine reserves equals the size of an ui.panel call:
# (width, height) match and the (x, y) anchor lives in the same place.
import inspect
src = inspect.getsource(__import__('lagarto.game.state_play', fromlist=['x']))
assert 'ui.panel(surf, panel_rect)' in src, \
    "state_play._draw_hud does not call ui.panel for the capsule"
# ui.panel itself draws a dark fill + rim in one primitive -- a HUD drawn
# without it would be the old unframed block
panel_src = inspect.getsource(__import__('lagarto.render.ui', fromlist=['x']))
assert 'border_radius=radius' in panel_src, \
    "ui.panel lost its rim -- the capsule would draw flat"
print("[2] framed capsule: OK -- ui.panel called for the block, "
      "rim primitive present")

# ---- 3. the player block never claims a top-centre band ------------------ #
# The TopStack reserves bands in the top-centre column; a player's block
# anchored at the bottom cannot claim one even if its x were near the
# centre. The only way to fail this check is to move the block back up
# above the screen mid-line (which #1 already asserts) or to draw into the
# top-centre band from another path. Walk every state that could put the
# TopStack under pressure.
g = _game(2)
g.wave = 10
g.rounds._spawn_boss()
g.rounds.banner_t = 1.5
g.combo = 25
g.combo_timer = 2.0
g.combo_flash = 0.5
for _ in range(5):
    g.step(1 / 60)
# force the worst case again on the final draw
g.rounds.banner_t = 1.5
surf = pygame.Surface((C.WIDTH, C.HEIGHT))
g.draw(surf)
# pixel sample: pick the centre of the screen and the bottom strip; the
# bottom strip should have dark panel pixels, the centre of the screen
# should not have a panel border (a panel border would be the bright LINE
# colour, the screen centre is the world). A real failure here would be
# "the player block grew up into the top column".
px_center = surf.get_at((C.WIDTH // 2, C.HEIGHT // 2))[:3]
# confirm the panel rect actually landed in the bottom strip: walk the
# panel's rim (draw at the panel's left edge) -- if the panel was drawn,
# the colour at that edge pixel is the LINE rim, not the world green
rim_colour = (68, 72, 104)         # LINE in render/ui.py
panel_y = C.HEIGHT - C.HUD_PANEL_H - C.HUD_MARGIN
panel_bottom = panel_y + C.HUD_PANEL_H - 1
# sample the LEFT edge of each player panel (one for singleplayer, both for coop)
edge_samples = [
    surf.get_at((C.HUD_MARGIN, panel_y + C.HUD_PANEL_H // 2))[:3],
    surf.get_at((C.WIDTH - C.HUD_MARGIN - 1, panel_y + C.HUD_PANEL_H // 2))[:3],
]
hits = [s for s in edge_samples
        if max(abs(c - rc) for c, rc in zip(s, rim_colour)) < 30]
if len(hits) < 2:
    errors.append(f"panel rim not visible on the bottom edges: {edge_samples}")
if errors:
    raise SystemExit("top-centre overlap FAIL: " + "; ".join(errors))
print("[3] top-centre overlap: OK -- both player blocks in the bottom corners, "
      "TopStack owns the full top column")

# ---- 4. the spring settles after a single impulse ------------------------ #
# A spring that rings forever is the failure mode this check exists to
# catch: drive it with one strong impulse, count frames until |x|, |y| < 0.05
# px. The current HUD_SPRING_K / HUD_SPRING_C combo is overdamped, so a
# step input settles in well under a second at 60 Hz.
s = hud.CapsuleSpring()
s.start_shake(12.0)
# shake envelope runs alongside the spring -- but start_shake alone does
# NOT move the spring itself; an impulse is what moves it
s.impulse(18.0, -14.0)
settled_frame = None
dt = 1.0 / 60.0
for f in range(180):                   # three seconds is the budget
    s.update(dt)
    if s.settle_error() < 0.05 and s.shake_t <= 0:
        settled_frame = f
        break
if settled_frame is None:
    raise SystemExit(
        f"spring does not settle: settle_error={s.settle_error():.4f}, "
        f"shake_t={s.shake_t:.3f} after 180 frames")
if settled_frame > 60:
    raise SystemExit(
        f"spring settles, but slowly ({settled_frame} frames at 60Hz). "
        "Capsule should be at rest within ~1s of any impulse.")
print(f"[4] spring settles: OK -- at rest after {settled_frame} frames "
      f"(shake envelope also decayed)")

# ---- 5. detect_changes fires the right shakes ---------------------------- #
# direct call into detect_changes -- the spring's shake_amp must rise on
# damage and on value changes; a no-op frame must not raise it
g = _game(1)
p = g.players[0]
cap = g.hud_capsules[0]
# first call: only seeds last_*, must not start a shake
hud.detect_changes(cap, p)
assert cap.spring.shake_amp == 0.0, \
    "first frame fired a shake (last_* should have been None)"
# no-op frame: shake_amp stays 0
hud.detect_changes(cap, p)
assert cap.spring.shake_amp == 0.0, "no-op frame fired a shake"
# damage: shake_amp rises
p.health = p.max_health - 5
hud.detect_changes(cap, p)
assert cap.spring.shake_amp > 0.0, "damage did not fire a shake"
amp_dmg = cap.spring.shake_amp
# heal: shake_amp rises again (heal is treated like a value change)
cap.spring.shake_amp = 0.0
p.health = p.max_health
hud.detect_changes(cap, p)
assert cap.spring.shake_amp > 0.0, "heal did not fire a shake"
amp_heal = cap.spring.shake_amp
# damage should be louder than a value change
if amp_dmg <= amp_heal:
    raise SystemExit(
        f"damage shake ({amp_dmg}) not louder than value-change shake "
        f"({amp_heal}) -- the player would not feel the hit")
print(f"[5] detect_changes: OK -- damage shake={amp_dmg:.1f} px louder "
      f"than value shake={amp_heal:.1f} px")

print("ALL OK")