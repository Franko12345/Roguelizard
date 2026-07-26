"""Display probe: measures the REAL cost of presenting a frame, per display mode.

Why this exists: the game renders to a fixed logical surface and scales it to the
window every frame. That cost depends entirely on the output resolution, on
whether the scale factor is integer, and on how vsync interacts with the driver --
none of which can be measured on a headless machine. This runs on *your* hardware
and prints the number for each combination, so the fix targets the real cause.

Run:  python tools/probe_display.py
It opens a window briefly for each mode. Nothing is saved; your settings are
restored at the end.
"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from lagarto.core import config as C
from lagarto.render import display
from lagarto.core import fonts, settings
from lagarto.audio import engine as audio
from lagarto.creatures import species
from lagarto.input.controllers import Controller
from lagarto.game.loop import Game
from pygame import Vector2

FRAMES = 240


def build_scene():
    """A representative frame: player, a dozen creatures, particles, HUD."""
    import random
    random.seed(5)
    g = Game(1, [Controller()], fonts.get(18), fonts.get(32, bold=True))
    p = g.players[0]
    for key in ('runner', 'gunner', 'venomer', 'wasp', 'tank', 'spitter'):
        for _ in range(2):
            e = species.make(key, p.pos + Vector2(random.uniform(-300, 300),
                                                  random.uniform(-240, 240)))
            e.hp = e.max_hp = 500
            g.enemies.append(e)
    for _ in range(120):
        g.step(C.DT)
    return g


def timed(fn, n):
    fn()
    out = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1000.0)
    return out


def run_mode(g, label, scale, fullscreen, vsync):
    try:
        surf = display.apply(scale=scale, fullscreen=fullscreen, vsync=vsync)
    except Exception as e:
        print(f"  {label:34s} FALHOU: {e}")
        return
    pygame.event.pump()
    x, y, w, h = display._rect
    draw = timed(lambda: g.draw(surf), FRAMES)
    pres = timed(lambda: display.present(), FRAMES)
    k = w / C.WIDTH
    integer = abs(k - round(k)) < 1e-3
    print(f"  {label:34s} saida {w}x{h}  fator {k:.3f}"
          f"{' (inteiro)' if integer else ' (FRACIONARIO)'}")
    print(f"      draw {statistics.median(draw):6.2f} ms | "
          f"present {statistics.median(pres):6.2f} ms | "
          f"p95 present {sorted(pres)[int(len(pres) * .95)]:6.2f} ms")


def main():
    pygame.init()
    cfg = settings.load()
    display.init(scale=1, fullscreen=False, vsync=False)
    audio.init(sfx_vol=0.0, music_vol=0.0)
    print(f"tela: {pygame.display.Info().current_w}x{pygame.display.Info().current_h}")
    print(f"logico: {C.WIDTH}x{C.HEIGHT}   orcamento a 60 FPS: 16.67 ms\n")
    g = build_scene()

    for vs in (False, True):
        print(f"--- vsync {'LIGADO' if vs else 'DESLIGADO'} ---")
        for s in (1, 2, 3):
            run_mode(g, f"janela {s}x", s, False, vs)
        run_mode(g, "TELA CHEIA", 2, True, vs)
        print()

    display.apply(scale=cfg['scale'], fullscreen=cfg['fullscreen'], vsync=cfg['vsync'])
    pygame.quit()
    print("suas configuracoes foram restauradas (nada foi salvo).")


main()
