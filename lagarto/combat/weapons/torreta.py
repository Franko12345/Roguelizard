"""Torreta -- the summoning weapon: it plants a body instead of firing a shot.

Every other weapon in this folder spits a projectile, an aura or a puddle. This
one spends its cooldown on a **Deployable** (see
``docs/concepts/deployable.md``): an ``AILizard`` of the stationary ``turret``
kind, planted where the player is standing at the moment the cooldown closes.

Nothing here is a new system. The turret is a creature with a genome whose
``speed`` is 0 (so it cannot steer) and whose ``knockback`` is 0 (so a hit
cannot shove it); it fires through the shared emitter (ADR-0012) from
``genome.shot`` like any other shooter; it lives in ``game.friends``, which
already updates, draws and buries its dead.

The four global stats read through exactly as they do on a normal weapon --
which is the whole reason the build scales without a card of its own:

    amount         -> +1 turret per cast
    cooldown_mult  -> plants more often
    might          -> the turret's shots hit harder
    area_mult      -> the turret sees further

``might`` and ``area_mult`` are baked into the turret's dials when it is
planted: a body already on the ground keeps the stats it was built with, and a
card picked later shows up on the next one.
"""

from ...audio import engine as audio
from ...core.mathutil import vfrom_angle
from .base import Weapon


class Torreta(Weapon):
    id = 'torreta'; name = 'Torreta'; hue = 190
    levels = [
        dict(dmg=2, hp=6, count=1, shots=3, spread=46, cd=9.0, range=300, gap=1.4,
             desc='planta uma torreta que atira em leque'),
        dict(dmg=3, hp=6, count=1, shots=3, spread=46, cd=9.0, range=320, gap=1.4,
             desc='+dano'),
        dict(dmg=3, hp=9, count=1, shots=4, spread=54, cd=8.0, range=320, gap=1.2,
             desc='+1 tiro, mais resistente'),
        dict(dmg=4, hp=9, count=1, shots=4, spread=54, cd=7.0, range=340, gap=1.2,
             desc='+dano, -recarga'),
        dict(dmg=4, hp=12, count=2, shots=4, spread=54, cd=7.0, range=340, gap=1.1,
             desc='+1 torreta'),
        dict(dmg=5, hp=12, count=2, shots=5, spread=62, cd=6.0, range=360, gap=1.0,
             desc='+1 tiro, -recarga'),
    ]

    def tick(self, player, game, dt, st, level):
        st['t'] -= dt
        if st['t'] > 0:
            return
        lv = self.lv(level)
        st['t'] = lv['cd'] * player.cooldown_mult
        n = lv['count'] + player.amount
        for k in range(n):
            # one turret lands on the player; a cast of several rings them, so
            # `amount` widens the emplacement instead of stacking bodies in one
            # point (which is the bug Acido already paid for once)
            self._plant(player, game, lv,
                        player.pos + vfrom_angle(k * (360.0 / n), (n - 1) * 18))
        audio.play('nest', 0.5)

    def _plant(self, player, game, lv, pos):
        """Build one turret and hand it to the game. Deferred imports: the
        creature package imports `combat` at module level, so a top-level import
        the other way round closes the loop (same idiom as `items._act_chamado`).
        """
        from ...creatures.ai import AILizard
        from ...creatures.genome import Genome
        from .. import emitter
        g = Genome(name='torreta', size=0.85, length=0.55, girth=1.6,
                   leg_count=4, leg_len=0.75, plates=1, spikes=1,
                   hue=self.hue, sat=0.7, val=0.95, hp=lv['hp'],
                   speed=0.0,          # cannot steer: `Lizard.steer` early-outs
                   knockback=0.0,      # a hit cannot shove it off its spot
                   angular_damping=0.9, linear_damping=0.9, weight=3.0,
                   shot=dict(fn=emitter.fan_shot, count=lv['shots'],
                             spread=lv['spread'], shot_speed=340, radius=6,
                             dmg=int(round(lv['dmg'] * player.might)),
                             hostile=False,        # a friendly bullet (ADR-0014)
                             # read by the `turret` branch of AILizard.update
                             range=lv['range'] * player.area_mult, gap=lv['gap']))
        game.friends.append(AILizard(pos, 'turret', color=self.color, genome=g))
        game.fx.ring(pos, self.color)
        game.fx.spark_burst(pos, self.color, 10, 220)
