"""Entry point: window setup, the menu -> match loop, and the fixed-timestep loop.

Simulation advances in fixed ``DT`` steps (frame-rate independent, deterministic,
online-friendly); rendering happens once per frame after catching up. ``--smoke N``
runs N frames and exits, for headless self-tests.
"""

import sys
import time

import pygame

from .audio import engine as audio
from .core import config as C
from .render import display
from .core import fonts
from .render import perf
from .render import ui
from .core import settings
from .input.controllers import (make_controllers, describe_joysticks, Pad, MenuNav,
                          KeyboardMouseController, GamepadController)
from .game.loop import Game
from .game.menu import run_menu
from .sandbox import (Sandbox, preset_exists as sandbox_preset_exists,
                      load_preset as load_sandbox_preset)


def _init_joysticks():
    # NOTE: never call pygame.joystick.quit() here -- doing it while the event
    # queue is being built (JOYDEVICEADDED) corrupts it (KeyError inside event.get).
    pygame.joystick.init()
    joysticks = []
    for i in range(pygame.joystick.get_count()):
        try:
            joysticks.append(Pad(i))
        except Exception as e:
            print(f"[gamepad] falha ao abrir o controle {i}: {e}")
    if joysticks:
        describe_joysticks(joysticks)
    else:
        print("[gamepad] nenhum controle detectado pelo SDL/pygame. "
              "Conecte via USB (ou pareie), verifique se o SO o reconhece "
              "(Linux: pacote 'joystick'/driver xpad; modo XInput no controle) "
              "e conecte antes/depois — o jogo redetecta ao plugar.")
    return joysticks


def _reattach(controllers, joysticks):
    """Point the current controllers at the (re)detected pad after a hot-plug."""
    for c in controllers:
        if isinstance(c, (KeyboardMouseController, GamepadController)):
            c.joy = joysticks[0] if joysticks else (c.joy if isinstance(c, GamepadController) else None)


def _camp_nav(game, left=False, right=False, up=False, down=False, confirm=False):
    """Navigation for the TENT'S menu (shop + charms) only -- routes are now
    physical doors in the clearing, walked through, not picked here. Used by both
    keyboard and gamepad while the shop is open.
    """
    camp = game.camp
    if not camp:
        return
    areas = ['shop', 'charms'] if game.camp_has_charms() else ['shop']
    if camp.get('focus') not in areas:
        camp['focus'] = 'shop'
    if up or down:
        step = 1 if down else -1
        # inside the charm grid, up/down walks the column and only leaves at its ends
        if not (camp['focus'] == 'charms' and game.camp_move_charm(0, step)):
            i = areas.index(camp['focus'])
            camp['focus'] = areas[max(0, min(len(areas) - 1, i + step))]
    f = camp['focus']
    if f == 'shop':
        if left:
            camp['shop_sel'] = max(0, camp['shop_sel'] - 1)
        if right:
            camp['shop_sel'] = min(len(camp['shop']) - 1, camp['shop_sel'] + 1)
        if confirm:
            game.camp_buy(camp['shop_sel'])
    elif f == 'charms':
        if left:
            game.camp_move_charm(-1, 0)
        if right:
            game.camp_move_charm(1, 0)
        if confirm:
            game.camp_equip_cursor()


def _camp_shop_open(game):
    return game.state == 'camp' and game.camp and game.camp.get('mode') == 'shop'


def _toggle_fs():
    display.toggle_fullscreen()
    settings.save_display(display, audio)


def _pause_pick(game, toggle_fs, meter):
    """Activate the focused pause item, then re-sync anything the options screen
    may have written to disk.

    Two things go stale otherwise: ``meter.level`` (menu._activate persists the
    perf level but has no handle on the running meter, so the toggle would look
    dead until you quit to the menu), and app.py's own ``cfg`` (the F3 handler
    writes it back wholesale, which would revert fullscreen/volume changes made
    from pause).
    """
    result = game.pause_activate(toggle_fs)
    cfg = settings.load()
    meter.level = cfg.get('perf', perf.OFF)
    return result, cfg


def main():
    smoke = 0
    if '--smoke' in sys.argv:
        i = sys.argv.index('--smoke')
        smoke = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 120
    sandbox = '--sandbox' in sys.argv       # dev-only debug overlay; skips the menu
    profile = '--profile' in sys.argv       # also writes ~/.lagarto/perf.csv

    pygame.init()
    pygame.joystick.init()
    # Everything draws to a fixed logical surface; display.present() scales it to the
    # window (letterboxed). That's what allows the 1x/2x/3x window-size presets.
    cfg = settings.load()
    screen = display.init(scale=cfg['scale'], fullscreen=cfg['fullscreen'],
                          vsync=cfg['vsync'])
    pygame.display.set_caption("Lagarto - procedural animation game")

    font = fonts.get(18)
    bigfont = fonts.get(32, bold=True)
    titlefont = fonts.get(62, bold=True)
    print(f"[fonte] usando '{fonts.name()}'")

    audio.init(sfx_vol=cfg['sfx_vol'], music_vol=cfg['music_vol'])

    joysticks = _init_joysticks()
    meter = perf.Perf(level=perf.FULL if profile else cfg.get('perf', perf.OFF),
                      log=profile)
    clock = pygame.time.Clock()
    nav = MenuNav()          # gamepad navigation for level-up / camp screens
    fade = ui.Fade()

    while True:
        if sandbox:
            num, mode, chars = 1, 'sandbox', None      # no menu, 1 player, no waves
        elif smoke:
            num, mode, chars = 1, 'normal', None
        else:
            chosen = run_menu(screen, font, bigfont, titlefont, joysticks)
            if chosen is None:
                break
            num, mode, chars = chosen
            if not profile:                  # the options screen may have changed it
                cfg = settings.load()
                meter.level = cfg.get('perf', perf.OFF)

        controllers = make_controllers(num, joysticks)
        game = Game(num, controllers, font, bigfont, mode=mode, chars=chars)
        sb = Sandbox(game, font, bigfont) if sandbox else None
        if sb is not None and sandbox_preset_exists():
            # A saved preset rebuilds the exact scene through the same spawn/grant
            # path the overlay uses; no preset -> the sandbox opens idle (SB7).
            sb.apply_preset(load_sandbox_preset())
        fade.start(0.35)                     # fade in from the menu
        prev_state = game.state
        acc = 0.0
        frames = 0
        running = True

        while running:
            # Two different numbers on purpose. `raw_dt` is how long the frame
            # really took; `frame_dt` is that clamped, because feeding a huge dt
            # into the fixed-step accumulator is the spiral of death.
            # They must NOT be conflated: the perf meter used to read the clamped
            # value, so it saturated at exactly 0.05s -> a permanent "50 ms /
            # 20 FPS" readout no matter how bad the real frame was, and its
            # 1-second window (fed by the same dt) stretched to 2+ real seconds.
            raw_dt = clock.tick(0 if smoke else C.RENDER_FPS) / 1000.0
            frame_dt = min(raw_dt, 0.05)
            frames += 1

            if sb is not None:
                sb.begin_frame()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); return
                if ev.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                    joysticks = _init_joysticks()          # hot-plug: redetect + reattach
                    _reattach(controllers, joysticks)
                if ev.type == pygame.VIDEORESIZE:
                    display.handle_resize()
                if sb is not None and sb.handle_event(ev):
                    continue                 # overlay ate it (toggle / panel click)
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        # ESC used to drop the whole run with no confirmation
                        if _camp_shop_open(game):
                            game.camp_close_shop()     # back to the clearing
                        elif game.state == 'pause' and game.pause_back():
                            pass                       # backed out of a sub-screen
                        else:
                            game.toggle_pause()
                    if ev.key == pygame.K_F3:
                        cfg['perf'] = meter.cycle()
                        settings.save(cfg)
                    if ev.key == pygame.K_F11:
                        display.toggle_fullscreen()
                        settings.save_display(display)
                    if game.state == 'pause':
                        if ev.key in (pygame.K_UP, pygame.K_w):
                            game.pause_move(-1)
                        elif ev.key in (pygame.K_DOWN, pygame.K_s):
                            game.pause_move(1)
                        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                            act, cfg = _pause_pick(game, _toggle_fs, meter)
                            if act == 'quit':
                                running = False
                    elif game.state in ('over', 'victory'):
                        if ev.key == pygame.K_RETURN:
                            game = Game(num, controllers, font, bigfont, mode=mode,
                                        chars=chars)                # ENTER: nova run
                        elif ev.key == pygame.K_ESCAPE:
                            running = False                          # ESC: volta ao menu
                    elif game.state == 'levelup' and not game.pick:
                        if ev.key == pygame.K_r:
                            game.reroll_cards()          # LAGARTO's hand reroll
                        elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                            game.choose_card(ev.key - pygame.K_1)
                        elif ev.key in (pygame.K_LEFT, pygame.K_a):
                            game.card_idx = max(0, game.card_idx - 1)
                        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                            game.card_idx = min(len(game.cards) - 1, game.card_idx + 1)
                        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                            game.choose_card(game.card_idx)
                    elif _camp_shop_open(game) and not game.pick:
                        # the tent's menu; in field mode WASD/arrows move the player instead
                        if ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                            game.camp_buy(ev.key - pygame.K_1)
                        else:
                            _camp_nav(
                                game,
                                left=ev.key in (pygame.K_LEFT, pygame.K_a),
                                right=ev.key in (pygame.K_RIGHT, pygame.K_d),
                                up=ev.key in (pygame.K_UP, pygame.K_w),
                                down=ev.key in (pygame.K_DOWN, pygame.K_s),
                                confirm=ev.key in (pygame.K_RETURN, pygame.K_SPACE))
                if ev.type == pygame.MOUSEBUTTONDOWN and not game.pick:
                    # window pixels -> logical pixels (the surface is scaled)
                    mp = display.to_logical(ev.pos)
                    if game.state == 'levelup':
                        for i, rect in enumerate(getattr(game, '_card_rects', [])):
                            if rect.collidepoint(mp):
                                game.choose_card(i)
                    elif _camp_shop_open(game):
                        for i, rect in enumerate(getattr(game, '_shop_rects', [])):
                            if rect.collidepoint(mp):
                                game.camp_buy(i)
                        for rect, cid in getattr(game, '_charm_rects', []):
                            if rect.collidepoint(mp):
                                game.camp_equip(cid)

            # gamepad navigation for the upgrade/camp screens (mirrors the keyboard)
            nav.poll(joysticks, frame_dt)
            # Start opens/closes pause with a controller (ESC is keyboard-only), so
            # a pad-only player can actually reach the pause menu. Mirrors the ESC
            # path: back out of a sub-screen first, else toggle.
            if nav.start and game.state not in ('over', 'victory', 'levelup', 'camp'):
                if game.state == 'pause' and game.pause_back():
                    pass
                else:
                    game.toggle_pause()
            if game.pick:                    # a choice is being absorbed: hands off
                pass
            elif game.state == 'levelup' and game.cards:
                if nav.left:
                    game.card_idx = max(0, game.card_idx - 1)
                if nav.right:
                    game.card_idx = min(len(game.cards) - 1, game.card_idx + 1)
                if nav.confirm:
                    game.choose_card(game.card_idx)
            elif game.state == 'pause':
                if nav.up:
                    game.pause_move(-1)
                if nav.down:
                    game.pause_move(1)
                if nav.cancel and not game.pause_back():
                    game.toggle_pause()
                if nav.confirm:
                    act, cfg = _pause_pick(game, _toggle_fs, meter)
                    if act == 'quit':
                        running = False
            elif game.state == 'camp' and game.camp:
                if game.camp.get('mode') == 'shop':
                    if nav.cancel or nav.start:
                        game.camp_close_shop()         # back to the clearing
                    else:
                        _camp_nav(game, left=nav.left, right=nav.right, up=nav.up,
                                  down=nav.down, confirm=nav.confirm)
                # field mode: the stick moves the player (handled in ctrl.poll)
            elif game.state in ('over', 'victory'):
                if nav.confirm:                          # A: nova run
                    game = Game(num, controllers, font, bigfont, mode=mode,
                                chars=chars)
                elif nav.cancel:                         # B: volta ao menu
                    running = False

            keys = pygame.key.get_pressed()
            mouse_btn = pygame.mouse.get_pressed()
            if sb is not None and sb.open and sb._ate_buttons:
                mouse_btn = list(mouse_btn)
                for button in sb._ate_buttons:
                    if 1 <= button <= len(mouse_btn):
                        mouse_btn[button - 1] = False
                mouse_btn = tuple(mouse_btn)
            for p in game.players:
                p.ctrl.poll(keys, mouse_btn, game.cam, p.pos, frame_dt)

            acc += frame_dt
            steps = 0
            _t = time.perf_counter()
            if game.hitstop > 0:                 # freeze frames: draw but don't simulate
                game.hitstop -= frame_dt
                acc = min(acc, C.DT)
            while game.hitstop <= 0 and acc >= C.DT and steps < C.MAX_STEPS:
                game.step(C.DT)
                acc -= C.DT
                steps += 1
            game.cam.follow(game.players, frame_dt)
            step_ms = (time.perf_counter() - _t) * 1000.0

            boss = getattr(game.rounds, 'boss', None)
            music_state = game.pause_prev if game.state == 'pause' else game.state
            if music_state == 'victory':
                # Victory is a one-shot fanfare, not a mix -- the stems loop
                # forever and would never "end" on the victory screen.
                audio.set_music('victory')
            else:
                # Adaptive stem mix (issue #24): one intensity dial drives which
                # layers are audible, so boss-enters / boss-dies crossfade
                # continuously instead of hard-swapping whole tracks.
                if music_state == 'camp':
                    target = 0.0
                elif boss is not None and not boss.dead:
                    target = 1.0
                elif game.state == 'play' and game.rounds.state == 'combat':
                    # scale with the wave so late combat reads tenser than early
                    target = 0.4 + 0.4 * min(1.0, game.rounds.wave / 15.0)
                else:
                    target = 0.2   # intermission / level-up: calm, not silent
                audio.set_music_intensity(target)
                audio.update_music(frame_dt)
            if game.state != prev_state:
                # play/level-up/camp animate themselves in and out (veil + dropdown +
                # absorption), so a blackout there would hide the impact we just built
                if not (prev_state in C.SOFT_TRANSITION_STATES
                        and game.state in C.SOFT_TRANSITION_STATES):
                    fade.start(0.22)
                prev_state = game.state
            fade.update(frame_dt)
            _t = time.perf_counter()
            game.draw(screen)
            if game.state == 'pause':
                game._draw_pause(screen, joysticks)
            fade.draw(screen)
            meter.draw(screen, font)
            if sb is not None:
                sb.draw(screen)              # debug overlay on top of everything
            draw_ms = (time.perf_counter() - _t) * 1000.0
            _t = time.perf_counter()
            display.present()
            present_ms = (time.perf_counter() - _t) * 1000.0
            meter.frame(raw_dt, step_ms, draw_ms, present_ms, game)

            if smoke and frames >= smoke:
                print(f"[smoke] {frames} frames ok  score={game.score} "
                      f"enemies={len(game.enemies)} friends={len(game.friends)} "
                      f"prey={len(game.prey)} pickups={len(game.pickups)}")
                meter.close()
                pygame.quit(); return

    meter.close()
    pygame.quit()


if __name__ == "__main__":
    main()
