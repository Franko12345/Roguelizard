"""State 'play': the live simulation step and the in-run HUD.

``update`` is the whole play-state body of ``Game.step``; ``draw`` is the only
thing play adds to the shared world pass (the offscreen arrows). ``_draw_hud``
is called by ``Game.draw`` for every state that still shows the run readouts.
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
    bw = 216
    for i, p in enumerate(game.players):
        x = 16 if i == 0 else C.WIDTH - bw - 16
        y = 14
        col = p.colorset[0]
        ui.text(surf, game.font, f"P{i+1}", (x, y), col)
        ui.text(surf, game.font, f"Nv {p.level}", (x + bw, y), (226, 228, 244),
                align='right')

        hy = y + 26
        previous_health = getattr(p, '_hud_health', p.health)
        impact = min(1.0, abs(previous_health - p.health) / hud.HEALTH_SAC_HP)
        p._hud_health = p.health
        hud.draw_health_sacs(surf, x, hy, bw, p.health, p.max_health, game.time,
                             impact=impact)
        ui.text(surf, game.smallfont, f"{int(p.health)}/{int(p.max_health)}",
                (x + bw, hy + 2), (230, 210, 216), align='right')

        # energy + xp: slim sacs (no flagella -- too short to read)
        ey = hy + 42
        hud.bio_bar(surf, x, ey, bw, 8, p.energy / p.max_energy, (96, 206, 240),
                    game.time)
        xy = ey + 12
        hud.bio_bar(surf, x, xy, bw, 6, clamp(p.xp / p.xp_to_next, 0, 1),
                    (245, 205, 84), game.time + 1.7)
        # ability cooldown dials (dash / tongue) -> readable "can I act?" feedback
        dy = xy + 16
        # three dials in a 216px panel: 78px pitch overflowed, so 11px radius
        # on a 68px pitch, with short labels
        dash_frac = 1.0 - clamp(p.dash_cd / max(0.001, p.dash_cooldown), 0, 1)
        hud.dial(surf, (x + 12, dy + 14), 11, dash_frac, p.colorset[0],
                 game.smallfont, "DASH", game.time, enabled=p.energy >= C.DASH_COST)
        t_frac = 0.0 if p.tongue_t > 0 else 1.0
        hud.dial(surf, (x + 80, dy + 14), 11, t_frac, (235, 90, 120),
                 game.smallfont, "LING", game.time, enabled=p.energy >= C.TONGUE_COST)
        w_frac = 1.0 - clamp(p.whip_cd / max(0.001, p.whip_cooldown), 0, 1)
        hud.dial(surf, (x + 148, dy + 14), 11, w_frac, (250, 190, 90),
                 game.smallfont, "RABO", game.time, enabled=p.energy >= C.WHIP_COST)

        if p.down:
            ui.text(surf, game.font, f"CAIDO {p.revive:0.0f}s - toque p/ reviver",
                    (x, dy + 34), C.COL_ENEMY)
        # Active item: its own corner, not a fourth cooldown dial (the dial
        # row is a 216px panel at 68px pitch -- a fourth lands outside it).
        # Top-right when it is free; in co-op that corner IS P2's panel, so
        # each player gets it under their own dials instead.
        if p.ability:
            from ..combat import items as itemlib
            it = itemlib.ITEMS.get(p.ability)
            if it is not None:
                if len(game.players) == 1:
                    ix, iy = C.WIDTH - 52, 46
                else:
                    ix = (x + 20) if i == 0 else (x + bw - 20)
                    iy = dy + 62
                full = p.ability_charge >= 1.0
                col = it.color if full else (96, 100, 128)
                if full:
                    palette.glow(surf, (ix, iy), 30, it.color,
                                 0.28 + 0.2 * pulse(game.time, 6))
                icons.draw(surf, it.icon, (ix, iy), 13, col, glow=False)
                pygame.draw.circle(surf, (36, 40, 58), (ix, iy), 18, 3)
                if p.ability_charge > 0:
                    pygame.draw.arc(surf, col, (ix - 18, iy - 18, 36, 36),
                                    math.pi / 2,
                                    math.pi / 2 + p.ability_charge * C.TAU, 3)
                lbl = "E" if i == 0 else "U"
                if len(game.players) == 1:
                    ui.text(surf, game.smallfont, lbl, (ix, iy + 24), col,
                            align='center')
                    ui.text(surf, game.smallfont, it.name, (ix - 26, iy - 7),
                            col, align='right')
                else:
                    ui.text(surf, game.smallfont, lbl, (ix + 22, iy - 8), col)

        # equipped weapons live in the bottom corners so they never collide
        # with the health/energy bars or the cooldown dials
        wy = C.HEIGHT - 34
        for wi, (wid, lvl) in enumerate(p.weapons.items()):
            w = weapons.WEAPONS[wid]
            cxw = (x + 18 + wi * 46) if i == 0 else (x + bw - 18 - wi * 46)
            c = (cxw, wy)
            icons.draw(surf, wid, c, 14, w.color)
            lp = (c[0] + 13, c[1] + 11)
            pygame.draw.circle(surf, C.COL_INK, lp, 9)
            pygame.draw.circle(surf, w.color, lp, 9, 1)
            lh = game.font.get_height()
            ui.text(surf, game.font, str(lvl), (lp[0], lp[1] - lh // 2),
                    C.COL_WHITE, align='center')

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
