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
    """Draw each player's two HUD capsules + weapon strip + the top-centre column.

    The issue (#130) wants vitals and cooldowns in their own framed capsules
    so a fast organ (energy) inside a slow container (capsule spring) reads
    as two things, not one. Each capsule has its own spring.

    Layout (bottom corner of the screen, per player):
        [ vitals capsule  : header + 3 bars      ]
        [ cooldowns capsule: 3 dials + labels    ]
        [ strip          : weapons + item, no frame ]

    Downed prompt swaps into the vitals header right edge instead of dropping
    over the strip (which would have collided with the tap targets)."""
    bw = C.HUD_PANEL_W
    # grow the capsule list defensively in case num_players changes after init
    while len(game.hud_capsules) < len(game.players):
        game.hud_capsules.append(hud.PlayerCapsule())
    for i, p in enumerate(game.players):
        cap = game.hud_capsules[i]
        # Entry overshoot: a fresh capsule (last_* all None) is the first
        # draw of the run -- kick both springs so the issue's "entra com
        # overshoot" plays once. detect_changes on the same frame seeds
        # last_* from current values, so the entry kick is the ONLY impulse
        # this frame and the impulse lands visible on the first render.
        if cap.last_hp is None and cap.last_energy is None:
            cap.entry_overshoot(i, len(game.players))
        # detect value changes BEFORE drawing so the impulse lands this frame
        hud.detect_changes(cap, p)
        # step both springs now; each capsule reads its OWN spring's offset
        cap.vitals_spring.update(game.dt_last)
        cap.cooldowns_spring.update(game.dt_last)

        # X anchor: shared by vitals + cooldowns + strip; P2 mirrors.
        base_x = C.HUD_MARGIN if i == 0 else C.WIDTH - bw - C.HUD_MARGIN
        # Y stack from the bottom: strip, gap, cooldowns, gap, vitals.
        strip_top = C.HEIGHT - C.HUD_MARGIN - C.HUD_STRIP_H
        cd_top = strip_top - C.HUD_BLOCK_GAP - C.HUD_COOLDOWNS_H
        vit_top = cd_top - C.HUD_BLOCK_GAP - C.HUD_VITALS_H

        # vitals: header + bars; each spring adds its own offset so the two
        # capsules move independently. Impulse direction matches the player's
        # slide direction so the spring always points "back to rest".
        vx, vy = base_x, vit_top
        cdx, cdy = base_x, cd_top

        # ---- vitals capsule ----
        # Two-capsule foundation (issue #130): vitals framed in its own panel
        # so the slow container (capsule spring) reads as one thing, while the
        # organs inside (sacs / bellows / skull from #131/#132) animate on
        # their own faster rhythms.
        vit_rect = pygame.Rect(vx, vy, bw, C.HUD_VITALS_H)
        ui.panel(surf, vit_rect)

        # explicit vertical layout inside the vitals capsule: each band is
        # laid out from vy, so the header / organs never collide even when the
        # spring is trembling. Sum of organ heights + gaps + header = vitais.
        head_y = vy + 4                                # P1 / Nv (HUD_HEAD_H = 20)
        bar_x = vx + C.HUD_PAD
        bar_w = bw - 2 * C.HUD_PAD
        health_top = vy + C.HUD_HEAD_H                 # baseline for sacs
        # draw_health_sacs grows upward from its baseline; bottom row sits on
        # it, rows above stack up. Bottom row y = health_top + HUD_HEALTH_H - 18.
        hy = health_top + C.HUD_HEALTH_H - 18
        ey = health_top + C.HUD_HEALTH_H + C.HUD_ORGAN_GAP    # bellows
        xy = ey + C.HUD_BELLOWS_H + C.HUD_ORGAN_GAP           # skull
        # dials live in the SEPARATE cooldowns capsule, not the vitals one;
        # the y for dials is computed below as cd_inner_y inside that capsule.

        col = p.colorset[0]
        ui.text(surf, game.font, f"P{i+1}", (bar_x, head_y), col)
        # downed prompt replaces the Nv label so it never lands on the strip
        # (issue #130 review finding 5).
        if p.down:
            ui.text(surf, game.font, f"CAIDO {p.revive:0.0f}s",
                    (vx + bw - C.HUD_PAD, head_y), C.COL_ENEMY, align='right')
            ui.text(surf, game.smallfont, "toque p/ reviver",
                    (vx + bw - C.HUD_PAD, head_y + game.font.get_height()),
                    C.COL_ENEMY, align='right')
        else:
            ui.text(surf, game.font, f"Nv {p.level}",
                    (vx + bw - C.HUD_PAD, head_y),
                    (226, 228, 244), align='right')
        # HP number rides the header, not the sacs: the sac row is centred in
        # the capsule and any corner label collided with it.
        ui.text(surf, game.smallfont,
                f"{int(p.health)}/{int(p.max_health)}",
                (vx + bw // 2, head_y + 3), (230, 210, 216), align='center')

        # ---- health: the sac row (organ reaction on the hit frame) ------
        # issue #131: discrete sacs of HEALTH_SAC_HP, not a bar.
        previous_health = getattr(p, '_hud_health', p.health)
        impact = min(1.0, abs(previous_health - p.health) / hud.HEALTH_SAC_HP)
        p._hud_health = p.health
        hud.draw_health_sacs(surf, bar_x, hy, bar_w, p.health, p.max_health,
                             game.time, impact=impact)

        # ---- energy bellows + XP skull: one organ each ------------------
        # issue #132: bellows for energy, cranial fluid for XP, both with
        # their own per-player animation state cached in _HUD_ANATOMY.
        bellows, fluid = _anatomy_state(p)
        energy_fraction = clamp(p.energy / p.max_energy, 0, 1)
        xp_fraction = clamp(p.xp / p.xp_to_next, 0, 1)
        bellows.update(energy_fraction, 1 / C.SIM_HZ)
        fluid.update(xp_fraction, 1 / C.SIM_HZ)
        hud.draw_bellows(surf, (bar_x, ey, bar_w, C.HUD_BELLOWS_H), bellows)
        hud.draw_skull(surf, (bar_x, xy, bar_w, C.HUD_SKULL_H), p.level,
                       xp_fraction, fluid)

        # ---- cooldowns capsule ----
        # issue #130 foundation: second framed capsule holds the dials so a
        # fast organ (energy) inside a slow container (vitals spring) reads as
        # two things, not one.
        cd_rect = pygame.Rect(cdx, cdy, bw, C.HUD_COOLDOWNS_H)
        ui.panel(surf, cd_rect)

        # 3 dials evenly spaced across the bar_w interior, with a single
        # label row above
        cd_inner_y = cdy + 4
        dial_pitch = bar_w // 3
        dial_cx = bar_x + dial_pitch // 2
        dash_frac = 1.0 - clamp(p.dash_cd / max(0.001, p.dash_cooldown), 0, 1)
        hud.dial(surf, (dial_cx, cd_inner_y + 14), 11, dash_frac, p.colorset[0],
                 game.smallfont, "DASH", game.time,
                 enabled=p.energy >= C.DASH_COST)
        t_frac = 0.0 if p.tongue_t > 0 else 1.0
        hud.dial(surf, (dial_cx + dial_pitch, cd_inner_y + 14), 11, t_frac,
                 (235, 90, 120), game.smallfont, "LING", game.time,
                 enabled=p.energy >= C.TONGUE_COST)
        w_frac = 1.0 - clamp(p.whip_cd / max(0.001, p.whip_cooldown), 0, 1)
        hud.dial(surf, (dial_cx + dial_pitch * 2, cd_inner_y + 14), 11, w_frac,
                 (250, 190, 90), game.smallfont, "RABO", game.time,
                 enabled=p.energy >= C.WHIP_COST)

        # ---- bottom strip: weapons + active item, each in its own corner
        # weapons step 28 -- with six weapons and the item circle (28 px wide)
        # the strip fits in 196 px (bw - 2*PAD) without overlap. Step was 34
        # and overflowed past the item zone on a six-weapon build.
        wy = strip_top + C.HUD_STRIP_H // 2
        weapons_list = list(p.weapons.items())
        if i == 0:
            wx_start = vx + C.HUD_PAD + 6
            wx_step = 28
            item_cx = vx + bw - C.HUD_PAD - 22
        else:
            wx_start = vx + bw - C.HUD_PAD - 6
            wx_step = -28
            item_cx = vx + C.HUD_PAD + 22
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
        # the same corner of their own strip, so they never share a slot.
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
