"""Ferrao -- homing projectile weapon."""

from ...audio import engine as audio
from ...core.mathutil import random_dir
from ..projectile import Projectile, homing
from .base import Weapon


class Ferrao(Weapon):
    id = 'ferrao'; name = 'Ferrão Teleguiado'; hue = 40
    levels = [
        dict(dmg=1, count=1, cd=1.5, desc='ferrao que persegue inimigos'),
        dict(dmg=1, count=2, cd=1.5, desc='+1 ferrao'),
        dict(dmg=2, count=2, cd=1.3, desc='+dano, -recarga'),
        dict(dmg=2, count=3, cd=1.2, desc='+1 ferrao'),
        dict(dmg=3, count=4, cd=1.0, desc='+1 ferrao, +dano'),
    ]

    def tick(self, player, game, dt, st, level):
        st['t'] -= dt
        if st['t'] > 0 or not any(not e.dead for e in game.enemies):
            return
        lv = self.lv(level)
        st['t'] = lv['cd'] * player.cooldown_mult
        mouth = player.spine.joints[0] + player.spine.head_dir() * player.max_r
        n = lv['count'] + player.amount
        for k in range(n):
            v = random_dir(240)
            pr = Projectile(mouth, v, self.color,
                            dmg=int(round(lv['dmg'] * player.might)),
                            radius=6, hostile=False, life=3.0)
            pr.on_update.append(homing)
            game.spawn_projectile(pr)
        game.fx.spark_burst(mouth, self.color, 3, 150)
        audio.play('w_homing', 0.28)
