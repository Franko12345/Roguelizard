"""Ambient lighting: the darkening layer with additive light pools.

The dark layer (issue #110): a per-frame full-screen ``Surface`` that fills
with an ambient colour, gets additive light blits from registered
[Fonte de luz](../../CONTEXT.md) sources, and is composited back into the
scene with ``BLEND_RGB_MULT``. Anything drawn AFTER the layer is untouched --
the "never darken danger" rule is just draw order.

The layer is skipped entirely when ``C.NIGHT_MAX == 0`` or the run's dark
scalar is 0 (wave 1), so the cost is zero on the path every headless check
already exercises.
"""
import pygame

from ..core import config as C
from ..core import palette


# ----------------------------------------------------------------------- #
#  One registered light source                                            #
# ----------------------------------------------------------------------- #

class Light:
    """One light pool at a position with a colour and radius.

    Three flavours share this shape:

      * ``kind='player'`` - warm aura tied to a player; tracked by the
        lighting module from ``game.players`` every frame.
      * ``kind='prop'``   - static mushroom / flower / firefly; lives on
        ``world.static_lights`` for the whole run.
      * ``kind='fx'``     - one-frame spill from a burst or spark burst;
        aged out by ``life`` after ``FX_EMISSION_LIFE`` seconds.

    Only the data needed to draw one additive blit -- no per-kind subclass.
    """
    __slots__ = ('pos', 'color', 'radius', 'intensity', 'life', 'maxlife',
                 'kind')

    def __init__(self, pos, color, radius, intensity=1.0, life=None,
                 maxlife=None, kind='prop'):
        self.pos = pos                  # world-space Vector2
        self.color = color
        self.radius = radius
        self.intensity = intensity
        self.life = life                # None = infinite
        self.maxlife = maxlife if maxlife is not None else life
        self.kind = kind

    def alive(self):
        return self.life is None or self.life > 0


# ----------------------------------------------------------------------- #
#  The layer                                                               #
# ----------------------------------------------------------------------- #

# Quantise the dark scalar so similar waves share the same fill colour and
# the additive palette cache doesn't grow per frame (ADR-0009: the key MUST
# be coarse). 32 buckets is well below the 60 Hz eye and gives the same
# banding tolerance the existing glow quantiser does (4 bits/channel).
_NIGHT_QUANT = 32


def _quantise_dark(d):
    return int(d * _NIGHT_QUANT) / _NIGHT_QUANT


def _mix_warm(player_col, warm_col, t):
    """Tint a player hue toward the warm aura base.

    Keeps the per-player hue readable (so two co-op auras don't collapse into
    one colour) while pushing both toward the same warm pool look -- the
    print's "fire and muzzle flash" reading.
    """
    return tuple(int(player_col[i] * (1 - t) + warm_col[i] * t) for i in range(3))


def _step_emissive(lights, dt):
    """Age out FX-style lights with a finite life. Returns the survivors."""
    alive = []
    for lt in lights:
        if lt.life is None:
            alive.append(lt)
            continue
        lt.life -= dt
        if lt.life > 0:
            alive.append(lt)
    return alive


class LightingLayer:
    """The dark-with-light-pools layer, drawn once per frame.

    The surface is allocated lazily and reused -- a fresh ``Surface(SRCALPHA)``
    every frame costs ~6 ms and produces garbage (see
    [Performance](../../docs/concepts/performance.md)). With BLEND_RGB_MULT
    on a plain Surface the multiplicative blit of 1120x720 is the actual
    ceiling: 1.5 ms budget, drop to half or quarter resolution if it busts --
    the soft edge is what we want anyway.
    """

    def __init__(self):
        self.surf = None                # lazy: allocated on first non-day draw
        self.blit_count = 0             # diagnostics: how often the mult blit fired
        self.skipped_count = 0          #   "

    def _ensure_surf(self):
        if self.surf is None:
            self.surf = pygame.Surface((C.WIDTH, C.HEIGHT))
        return self.surf

    def draw(self, surf, cam, dark, static_lights, players, fx_emissions, dt):
        """Build and composite the layer for this frame.

        ``surf`` is the world-pass surface. ``cam`` is the live Camera.
        ``dark`` is the run's [0..1] day->night scalar. ``static_lights`` is
        the world's pre-registered pools; ``players`` is the list of alive
        players for the aura; ``fx_emissions`` is the list of FX-spilled
        lights with a finite life. ``dt`` is the step delta (so FX lights
        can be aged).

        Returns silently on day frames, and the surface is left dirty --
        a no-op frame touches no GPU surface at all, which is what the
        headless checks rely on.
        """
        if dark <= 0.0:
            self.skipped_count += 1
            return

        # cull aged-out FX lights; keep static + player lights intact
        fx = _step_emissive(list(fx_emissions), dt) if fx_emissions else ()

        # quantise ambient so two near-identical waves use the same fill
        d = _quantise_dark(dark)
        ambient = tuple(max(0, min(255, int(c * (1.0 - d) + 8 * d)))
                        for c in C.NIGHT_AMBIENT)
        s = self._ensure_surf()
        s.fill(ambient)

        # player auras: warm pool at each alive player; tinted toward the
        # player's own hue so two co-op pools read as distinct.
        for p in players:
            if p.dead:
                continue
            col = _mix_warm(p.color, C.PLAYER_AURA_COL, 0.45)
            palette.glow(s, cam.w2s(p.pos), C.PLAYER_AURA_R, col, 0.85)

        # static prop lights: mushroom / flower / firefly pools, dim and steady
        for lt in static_lights:
            sp = cam.w2s(lt.pos)
            if not (-120 < sp[0] < C.WIDTH + 120 and -120 < sp[1] < C.HEIGHT + 120):
                continue
            palette.glow(s, sp, lt.radius, lt.color, lt.intensity)

        # FX emissive: aged above; intensity fades with remaining life
        for lt in fx:
            f = (lt.life / lt.maxlife) if lt.maxlife else 1.0
            sp = cam.w2s(lt.pos)
            if not (-120 < sp[0] < C.WIDTH + 120 and -120 < sp[1] < C.HEIGHT + 120):
                continue
            palette.glow(s, sp, lt.radius, lt.color, lt.intensity * f)

        surf.blit(s, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        self.blit_count += 1