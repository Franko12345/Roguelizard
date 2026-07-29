"""State 'play': the live simulation step and the in-run HUD.

``update`` is the whole play-state body of ``Game.step``; ``draw`` is the only
thing play adds to the shared world pass (the offscreen arrows). ``_draw_hud``
is called by ``Game.draw`` for every state that still shows the run readouts.

The HUD itself follows the "anatomy" metaphor from issue #130: vitals + cooldowns
live inside a framed *capsule* (the panel) anchored in the bottom corners; the
capsule has its own low-frequency spring (trembles on damage / value change)
while each *organ* inside animates on its own, faster rhythm. The top-centre
column is owned by ``TopStack`` -- player blocks no longer compete with it.
"""

import math
import random

import pygame

from ..audio import engine as audio
from ..combat import weapons
from ..core import config as C
from ..core import palette
from ..core.mathutil import clamp, decay, pulse
from ..render import icons
from ..render import ui
from ..world.collision import separate
from ..world.pickups import Bug
from . import hud


_HUD_ANATOMY = {}


def _anatomy_state(player):
    key = id(player)
    state = _HUD_ANATOMY.get(key)
    if state is None:
        state = (hud.Bellows(player.energy / player.max_energy), hud.CranialFluid())
        _HUD_ANATOMY[key] = state
    return state


def update(game, dt):
    # a queued level-up pauses the action for a card pick
    for p in game.players:
        if not p.dead and p.pending_levelups > 0:
            game._enter_levelup(p)
            return
    game.time += dt
    for p in game.players:
        if not p.dead:
            p.update(dt, game)
    # Sandbox pause-AI (SB6): while frozen, enemy/boss/prey/friend update is
    # skipped so the player can still walk around and inspect a held pose. A
    # queued Step lifts the freeze for exactly one tick, then re-arms it -- the
    # frame-by-frame tool for procedural animation. On a normal run ``mode`` is
    # never 'sandbox', so ``freeze_ai`` is always False and ``e.update`` runs
    # every group exactly as before -- byte-identical behaviour.
    freeze_ai = game.mode == 'sandbox' and game.pause_ai and not game.step_once
    game.step_once = False
    for group in (game.enemies, game.prey, game.friends):
        for e in group:
            if not e.dead:
                e.on_screen = game.cam.visible(e.pos)
                if not freeze_ai:
                    e.update(dt, game)
    for pk in game.pickups:
        if not pk.dead:
            pk.update(dt, game)
    game._update_projectiles(dt)
    for pud in game.puddles:
        pud.update(dt, game)
    game.puddles = [p for p in game.puddles if not p.dead]

    # keep creatures from stacking into one point
    movers = [p for p in game.players if not p.dead]
    movers += [e for e in game.enemies if not e.dead]
    movers += [e for e in game.prey if not e.dead]
    movers += [f for f in game.friends if not f.dead]
    separate(movers)

    game._collisions()
    game.rounds.update(dt)
    if game.rounds.state == 'cleared':
        if getattr(game.rounds, 'is_final', False):
            game.state = 'victory'              # final boss down -> run won
            audio.play('victory')
            game._bank_run(won=True)
        else:
            game._enter_camp()                  # otherwise: camp (route + shop)
    game.fx.update(dt)
    game.flash = decay(game.flash, dt, 3.2)
    game.world.update(dt)
    if game.combo_timer > 0:
        game.combo_timer -= dt
        if game.combo_timer <= 0:
            game.combo = 0
    game.combo_flash = decay(game.combo_flash, dt, 2)
    game._revive()

    if game.pending_enemies:        # children queued during this step's deaths
        game.enemies.extend(game.pending_enemies)
        game.pending_enemies = []
    game.enemies = [e for e in game.enemies if not e.dead]
    game.prey = [e for e in game.prey if not e.dead]
    game.friends = [f for f in game.friends if not f.dead]
    game.pickups = [p for p in game.pickups if not p.dead]

    if len(game.pickups) < 50 and random.random() < dt * 4:
        game.pickups.append(Bug(game._rand_world()))
    if len(game.prey) < 8 and random.random() < dt * 0.6:
        game.prey.append(game._spawn_prey())

    if not game.alive_players():
        game.state = 'over'
        game._bank_run()


def draw(game, surf):
    """Edge arrows pointing at enemies (and nests) you can't see -> find stragglers.

    Picking the targets is run state; the arrows themselves are hud. Drawn from
    inside the shared world pass (before the HUD), not as an overlay.
    """
    targets = [(e.pos, e.color) for e in game.enemies if not e.dead]
    targets += [(n.pos, (190, 130, 95)) for n in game.rounds.nests if not n.dead]
    hud.draw_offscreen(surf, targets, game.cam)


def _draw_hud(game, surf):
    """Draw each player's HUD capsule and the shared top-centre column.

    Per-player state lives in ``game.hud_capsules[i]`` -- a ``PlayerCapsule``
    that owns its two CapsuleSprings (vitais + cooldowns -- the two framed
    panels) and the last-frame vitals used to fire impulses/shakes. The
    top-centre column is owned by ``TopStack`` and no player block competes
    with it.

    This commit wires the new spring API; the layout keeps the single framed
    rectangle but BOTH springs are stepped every frame, so the upcoming split
    into vitais + cooldowns capsules is a no-op at the state-update level.
    """
    bw = C.HUD_PANEL_W
    bh = C.HUD_PANEL_H
    # grow the capsule list defensively in case num_players changes after init
    while len(game.hud_capsules) < len(game.players):
        game.hud_capsules.append(hud.PlayerCapsule())
    for i, p in enumerate(game.players):
        cap = game.hud_capsules[i]
        # detect value changes BEFORE drawing so the impulse lands this frame
        hud.detect_changes(cap, p)
        # step both springs now; once the layout splits, each capsule owns
        # one of them and reads render_offset() from the spring it owns
        cap.vitals_spring.update(game.dt_last)
        cap.cooldowns_spring.update(game.dt_last)

        base_x = C.HUD_MARGIN if i == 0 else C.WIDTH - bw - C.HUD_MARGIN
        base_y = C.HEIGHT - bh - C.HUD_MARGIN
        # temp: both springs drive the same rect, but cooldowns is silent
        # until the layout split happens. After split, vitais owns the upper
        # rect (header + bars) and cooldowns owns the lower (3 dials).
        ox, oy = cap.vitals_spring.render_offset(game.time)
        px, py = int(base_x + ox), int(base_y + oy)
        panel_rect = pygame.Rect(px, py, bw, bh)

        # the framed capsule (one ui.panel call per player; panel already
        # draws both the dark fill and the bright rim in the same primitive)
        ui.panel(surf, panel_rect)

        # explicit vertical layout: each band is laid out from py, so the
        # header / organs / dials / strip never collide even when the spring
        # is trembling. Sum of heights + gaps = HUD_PANEL_H.
        head_y = py + 4                         # P1 / Nv (18 px tall)
        bar_x = px + C.HUD_PAD
        bar_w = bw - 2 * C.HUD_PAD
        health_top = py + C.HUD_HEAD_H
        # draw_health_sacs takes a baseline: the bottom row sits on it and the
        # rows above grow upward, so the band spans health_top..+HUD_HEALTH_H
        hy = health_top + C.HUD_HEALTH_H - 18
        ey = health_top + C.HUD_HEALTH_H + 4    # energy bellows
        xy = ey + C.HUD_BELLOWS_H + 4           # xp skull
        dy = xy + C.HUD_SKULL_H + 4             # dials row
        dial_cx = bar_x + 12
        dial_pitch = 68

        # ---- header band: P1/P2 + level ---------------------------------
        col = p.colorset[0]
        ui.text(surf, game.font, f"P{i+1}", (bar_x, head_y), col)
        ui.text(surf, game.font, f"Nv {p.level}",
                (px + bw - C.HUD_PAD, head_y), (226, 228, 244), align='right')
        # HP number rides the header, not the sacs: the sac row is centred in
        # the capsule and any corner label collided with it.
        ui.text(surf, game.smallfont,
                f"{int(p.health)}/{int(p.max_health)}",
                (px + bw // 2, head_y + 3), (230, 210, 216), align='center')

        # ---- health: the sac row (organ reaction on the hit frame) ------
        previous_health = getattr(p, '_hud_health', p.health)
        impact = min(1.0, abs(previous_health - p.health) / hud.HEALTH_SAC_HP)
        p._hud_health = p.health
        hud.draw_health_sacs(surf, bar_x, hy, bar_w, p.health, p.max_health,
                             game.time, impact=impact)

        # ---- energy bellows + XP skull: one organ each ------------------
        bellows, fluid = _anatomy_state(p)
        energy_fraction = clamp(p.energy / p.max_energy, 0, 1)
        xp_fraction = clamp(p.xp / p.xp_to_next, 0, 1)
        bellows.update(energy_fraction, 1 / C.SIM_HZ)
        fluid.update(xp_fraction, 1 / C.SIM_HZ)
        hud.draw_bellows(surf, (bar_x, ey, bar_w, C.HUD_BELLOWS_H), bellows)
        hud.draw_skull(surf, (bar_x, xy, bar_w, C.HUD_SKULL_H), p.level,
                       xp_fraction, fluid)
        # ability cooldown dials (dash / tongue) -> readable "can I act?" feedback
        # three dials in a 216px panel: 78px pitch overflowed, so 11px radius
        # on a 68px pitch, with short labels
        dash_frac = 1.0 - clamp(p.dash_cd / max(0.001, p.dash_cooldown), 0, 1)
        hud.dial(surf, (dial_cx, dy + 14), 11, dash_frac, p.colorset[0],
                 game.smallfont, "DASH", game.time,
                 enabled=p.energy >= C.DASH_COST)
        t_frac = 0.0 if p.tongue_t > 0 else 1.0
        hud.dial(surf, (dial_cx + dial_pitch, dy + 14), 11, t_frac,
                 (235, 90, 120), game.smallfont, "LING", game.time,
                 enabled=p.energy >= C.TONGUE_COST)
        w_frac = 1.0 - clamp(p.whip_cd / max(0.001, p.whip_cooldown), 0, 1)
        hud.dial(surf, (dial_cx + dial_pitch * 2, dy + 14), 11, w_frac,
                 (250, 190, 90), game.smallfont, "RABO", game.time,
                 enabled=p.energy >= C.WHIP_COST)

        if p.down:
            ui.text(surf, game.font,
                    f"CAIDO {p.revive:0.0f}s - toque p/ reviver",
                    (bar_x, dy + 36), C.COL_ENEMY)

        # ---- bottom strip: weapons + active item, each in its own corner
        # the strip sits below the dials inside the same capsule; weapons
        # march toward the centre, the active item lives in the opposite
        # corner so a fourth dial could never have competed with it
        wy = py + bh - 24                # weapon / item vertical centre
        weapons_list = list(p.weapons.items())
        # P1: weapons left-to-right, item at the right edge.
        # P2: weapons right-to-left, item at the left edge.
        if i == 0:
            wx_start = bar_x + 16
            wx_step = 34
            item_cx = px + bw - C.HUD_PAD - 22
        else:
            wx_start = px + bw - C.HUD_PAD - 16
            wx_step = -34
            item_cx = bar_x + 22
        for wi, (wid, lvl) in enumerate(weapons_list):
            w = weapons.WEAPONS[wid]
            cwx = wx_start + wi * wx_step
            c = (cwx, wy)
            icons.draw(surf, wid, c, 11, w.color)
            lp = (c[0] + 10, c[1] + 8)
            pygame.draw.circle(surf, C.COL_INK, lp, 7)
            pygame.draw.circle(surf, w.color, lp, 7, 1)
            lh = game.font.get_height()
            ui.text(surf, game.font, str(lvl), (lp[0], lp[1] - lh // 2),
                    C.COL_WHITE, align='center')

        # Active item: dedicated corner of the strip. Co-op gives each player
        # the same corner of their own capsule, so they never share a slot.
        if p.ability:
            from ..combat import items as itemlib
            it = itemlib.ITEMS.get(p.ability)
            if it is not None:
                iy = wy
                full = p.ability_charge >= 1.0
                acol = it.color if full else (96, 100, 128)
                if full:
                    palette.glow(surf, (item_cx, iy), 22, it.color,
                                 0.28 + 0.2 * pulse(game.time, 6))
                icons.draw(surf, it.icon, (item_cx, iy), 10, acol,
                           glow=False)
                pygame.draw.circle(surf, (36, 40, 58), (item_cx, iy), 14, 2)
                if p.ability_charge > 0:
                    pygame.draw.arc(surf, acol,
                                    (item_cx - 14, iy - 14, 28, 28),
                                    math.pi / 2,
                                    math.pi / 2 + p.ability_charge * C.TAU,
                                    2)
                # button hint sits beside the icon (right for P1, left for P2)
                # so the icon's centre stays clean
                lbl = "E" if i == 0 else "U"
                if i == 0:
                    lbl_x = item_cx - 18
                    ui.text(surf, game.smallfont, lbl, (lbl_x, iy - 8),
                            acol, align='right')
                else:
                    lbl_x = item_cx + 18
                    ui.text(surf, game.smallfont, lbl, (lbl_x, iy - 8),
                            acol, align='left')

    # ---- top-centre column: every element reserves its own band ---- #
    cx = C.WIDTH // 2
    y = game.top.take(game.bigfont.get_height())
    ui.text(surf, game.bigfont, str(game.score), (cx, y), C.COL_HUD, align='center')

    y = game.top.take(game.font.get_height())
    ui.text(surf, game.font,
            f"Onda {game.wave}   Amigos {len(game.friends)}   Abates {game.kills}",
            (cx, y), (214, 217, 238), align='center')

    # combo / streak meter (rewards staying aggressive)
    if game.combo >= 2:
        heat = min(1.0, game.combo / 25.0)
        col = palette.mix((255, 214, 90), (255, 86, 86), heat)
        # composed first: the flash scales the *outlined* image, and the band
        # it reserves has to be the scaled height or the banner lands on it
        img = ui.text_surface(game.bigfont, f"x{game.combo}  COMBO", col)
        sc = 1.0 + game.combo_flash * 0.25
        if sc > 1.01:
            img = pygame.transform.rotozoom(img, 0, sc)
        cbar = 150                      # NB: not `bw`, which is the player panel
        y = game.top.take(img.get_height() + 9)
        surf.blit(img, (cx - img.get_width() // 2, y))
        by = y + img.get_height() + 2
        f = clamp(game.combo_timer / 3.2, 0, 1)
        pygame.draw.rect(surf, (50, 46, 60), (cx - cbar // 2, by, cbar, 5),
                         border_radius=3)
        pygame.draw.rect(surf, col, (cx - cbar // 2, by, int(cbar * f), 5),
                         border_radius=3)
