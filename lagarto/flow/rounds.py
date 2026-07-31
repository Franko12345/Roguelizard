"""Round manager: themed waves that DRIP in from destructible nests, with telegraphs.

Instead of dumping every enemy at once, each round picks a **theme** (composition),
places 1-2 **Nests** (organic POIs) near the players, and the nests emit enemies one
at a time through a growing **SpawnMark** telegraph (so nothing spawns on top of you).
Destroying a nest cuts its flow -> agency. The round clears when the budget is spent
(or every nest is destroyed) and no enemies remain. Between rounds sits a short
intermission which Phase 3 turns into the camp (route + shop).
"""

import math
import random
from pygame import Vector2
import pygame

from ..audio import engine as audio
from . import boss as bossai
from ..creatures import champions
from ..core import config as C
from ..render import icons
from ..core import palette
from ..creatures import species
from ..render import ui
from ..core.mathutil import vfrom_angle, clamp, decay, random_dir

# theme -> (banner, enemy pool, budget multiplier, max alive at once)
THEMES = {
    'enxame':     dict(banner='ENXAME', pool=['runner', 'runner', 'spiky', 'snake'],
                       budget=1.3, cap=7),
    'cuspidores': dict(banner='CHUVA DE CUSPIDORES',
                       pool=['spitter', 'spitter', 'gunner', 'sniper', 'runner'],
                       budget=0.85, cap=5),
    'tanques':    dict(banner='MARCHA DOS TANQUES',
                       pool=['tank', 'horned', 'octopus', 'tank'],
                       budget=0.6, cap=4),
    'aranhas':    dict(banner='NOITE DAS ARANHAS',
                       pool=['spider', 'spider', 'scorpion', 'centipede'],
                       budget=0.85, cap=5),
    'toca':       dict(banner='A TOCA', pool=['centipede', 'centipede', 'octopus', 'runner'],
                       budget=0.9, cap=5),      # burrowers + a grappler: keep moving
    # phase-2 themes: each one attacks a different player habit
    'revoada':    dict(banner='REVOADA', pool=['wasp', 'wasp', 'wasp', 'runner'],
                       budget=1.2, cap=8),      # flyers ignore the horde -> you must
    'estouro':    dict(banner='CAMPO MINADO',   # keep moving, never body-block
                       pool=['bomber', 'bomber', 'runner', 'gunner'],
                       budget=0.9, cap=6),
    'praga':      dict(banner='PRAGA',
                       pool=['venomer', 'venomer', 'mortar', 'spitter', 'wasp'],
                       budget=0.8, cap=5),      # ground denial -> stop camping
    'invasao':    dict(banner='INVASAO', pool=list(species.ENEMY_SPECIES),
                       budget=0.9, cap=6),
}
THEME_KEYS = list(THEMES.keys())
BOSS_EVERY = 5          # a boss round every N waves

# All authored bosses (plans/03_chefes_descricoes.md), keyed by id -- NOT by
# wave/tier. Isaac-style: a floor doesn't have ONE fixed boss, it has a POOL,
# and which one shows up is rolled per run. See BOSS_TIER_POOLS below for who
# is eligible where; a boss with no pool yet still just isn't picked (falls
# back to the old random-themed-giant), so adding one at a time never breaks
# the other boss waves.
BOSS_POOL = {
    'rei_lagarto': dict(species='horned', name='REI LAGARTO',
                        emblem='boss_rei_lagarto',
                        phases=lambda: bossai.king_phases(),
                        personality=lambda: bossai.king_personality(),
                        scar=[0.75, 0.5, 0.25],
                        overrides=dict(hue=98, sat=0.72, val=0.85, spikes=2,
                                      horns=3, tail='club')),
    'centopeiadeira': dict(species='centipede', name='CENTOPEIADEIRA',
                           emblem='boss_centopeiadeira',
                           phases=lambda: bossai.centipede_phases(),
                           personality=lambda: bossai.centipede_personality(),
                           on_phase=bossai.centipede_on_phase, scar=None,
                           overrides=dict(hue=15, sat=0.25, val=0.55, length=1.7)),
    'kraken_mor': dict(species='octopus', name='KRAKEN-MOR',
                       emblem='boss_kraken_mor',
                       phases=lambda: bossai.kraken_phases(),
                       personality=lambda: bossai.kraken_personality(),
                       scar=None, overrides=dict(hue=275, sat=0.75, val=0.5)),
    'primordial': dict(species='horned', name='PRIMORDIAL',
                       emblem='boss_primordial',
                       phases=lambda: bossai.primordial_phases(),
                       personality=lambda: bossai.primordial_personality(),
                       scar=None,
                       overrides=dict(hue=18, sat=0.85, val=0.65, spikes=3,
                                     horns=3, plates=2, tail='club',
                                     wings=True, extra_eyes=2)),
    'mae_escaravelho': dict(species='spider', name='MAE-ESCARAVELHO',
                            emblem='boss_mae_escaravelho',
                            phases=lambda: bossai.beetle_phases(),
                            personality=lambda: bossai.beetle_personality(),
                            scar=None, overrides=dict(hue=35, sat=0.6, val=0.45),
                            # ao morrer, racha em 6 filhotes (reusa o DIVISOR)
                            boss_attrs=dict(death_split=True, split_gen=1, split_count=6)),
    'aranha_rei': dict(species='spider', name='ARANHA-REI',
                       emblem='boss_aranha_rei',
                       phases=lambda: bossai.spider_king_phases(),
                       personality=lambda: bossai.spider_king_personality(),
                       scar=None,
                       overrides=dict(hue=260, sat=0.12, val=0.92, leg_len=1.6)),
    'serpente_cristal': dict(species='centipede', name='SERPENTE DE CRISTAL',
                             emblem='boss_serpente_cristal',
                             phases=lambda: bossai.crystal_phases(),
                             personality=lambda: bossai.crystal_personality(),
                             scar=None,
                             overrides=dict(hue=190, sat=0.45, val=1.0, length=2.0)),
    'terror_alado': dict(species='wasp', name='TERROR ALADO',
                         emblem='boss_terror_alado',
                         phases=lambda: bossai.wasp_phases(),
                         personality=lambda: bossai.wasp_personality(),
                         scar=None,
                         overrides=dict(hue=52, sat=0.95, val=1.0, length=0.9),
                         # flying=True: collision pula voadores (paira, nao empurra),
                         # mas hit_test continua acertando -- reuso do flag do wasp
                         boss_attrs=dict(flying=True)),
    'olho_sismico': dict(species='olho_sismico', name='OLHO-SISMICO',
                         emblem='boss_olho_sismico',
                         phases=lambda: bossai.eye_phases(),
                         personality=lambda: bossai.eye_personality(),
                         on_phase=bossai.eye_on_phase, scar=None,
                         # setup: liga a piscada (mecanica do Olho) + o tick por frame
                         setup=bossai.eye_setup,
                         overrides=dict(hue=280, sat=0.75, val=0.8)),
    # Built from the dedicated 'muralha' species, not a re-skinned 'horned':
    # that species is what carries plan='fixed', speed=0 and the wall-grade
    # damping/weight. Overriding a mobile species into plan='fixed' left the
    # wall walking at the player, which is not what a wall does.
    'muralha': dict(species='muralha', name='A MURALHA',
                     emblem='boss_muralha',
                     phases=lambda: bossai.muralha_phases(),
                     personality=lambda: bossai.wall_personality(),
                     scar=None,
                     overrides=dict(hue=0, sat=0.3, val=0.45)),
    # ANKH (B11, tier 7): "A Eterna". A re-skin of the horned lizard is the
    # RIGHT body here -- the design calls for a translucent golden lizard, and
    # the fight's identity is the 4-phase memory structure, not a new anatomy.
    # (Contrast A Muralha, which needed plan='fixed' because a wall is not a
    # lizard.) NOT the run's climax: the Primordial still closes NORMAL mode.
    'ankh': dict(species='horned', name='ANKH',
                 emblem='boss_ankh',
                 phases=lambda: bossai.ankh_phases(),
                 personality=lambda: bossai.ankh_personality(),
                 scar=None,
                 overrides=dict(hue=45, sat=0.35, val=1.0, spikes=0, plates=2)),
}

# tier (wave // BOSS_EVERY) -> which pool ids can be rolled there. Ranges,
# not single tiers, so late/infinite tiers can share a pool without listing
# every tier by hand. `range` end is exclusive, same as normal Python ranges.
BOSS_TIER_POOLS = [
    (range(1, 4), ['rei_lagarto', 'centopeiadeira', 'kraken_mor']),   # onda 5/10/15
    (range(4, 6), ['mae_escaravelho', 'aranha_rei', 'serpente_cristal',
                   'terror_alado', 'olho_sismico']),                  # onda 20/25 (so infinito)
    (range(6, 7), ['muralha']),                                         # tier 6 (onda 30)
    (range(7, 10_000), ['muralha', 'ankh']),                            # tier 7+ (onda 35+)
]
BOSS_FINAL = 'primordial'   # is_final always this one -- the run's fixed climax,
                           # not part of the roll (matches Isaac's true-final-boss)


def _boss_pool_for_tier(tier):
    for rng, ids in BOSS_TIER_POOLS:
        if tier in rng:
            return ids
    return None


class SpawnMark:
    """A growing ground marker; when it fills, the enemy erupts from it."""
    def __init__(self, pos, species_key, hp_bonus, speed_mul, delay=0.85):
        self.pos = Vector2(pos)
        self.species_key = species_key
        self.hp_bonus = hp_bonus
        self.speed_mul = speed_mul
        self.t = 0.0
        self.delay = delay
        self.done = False

    def update(self, dt, game):
        self.t += dt
        if self.t >= self.delay:
            e = species.make(self.species_key, self.pos)
            e.hp += self.hp_bonus
            e.sync_max_hp()
            e.max_speed *= self.speed_mul
            # champion roll happens *after* the wave scaling, so an elite is
            # elite relative to its own wave rather than to wave 1
            ch = champions.maybe_promote(e, game, game.rounds.wave)
            game.enemies.append(e)
            game.fx.ring(self.pos, e.color)
            game.fx.burst(self.pos, e.color, 10, 160)
            if ch is not None:                # champions announce themselves
                game.fx.ring(self.pos, ch.color())
                game.fx.spark_burst(self.pos, ch.color(), 14, 300)
            self.done = True

    def draw(self, surf, cam):
        f = clamp(self.t / self.delay, 0, 1)
        sp = cam.w2s(self.pos)
        r = int((14 + 26 * f) * cam.zoom)
        col = (255, 80, 90)
        pygame.draw.circle(surf, col, sp, r, max(1, int(2 * cam.zoom)))
        pygame.draw.circle(surf, col, sp, max(1, int(r * f * 0.7)))
        palette.glow(surf, sp, r * 1.3, col, 0.4 + 0.4 * f)


class Nest:
    """A pulsing organic mound that emits enemies; destroy it to stop the flow."""
    def __init__(self, pos, hp, pool):
        self.pos = Vector2(pos)
        self.hp = hp
        self.maxhp = hp
        self.pool = pool
        self.dead = False
        self.max_r = 34
        self.emit_cd = random.uniform(1.2, 2.6)
        self.pulse = random.uniform(0, C.TAU)
        self.hit_flash = 0.0

    def update(self, dt):
        self.pulse += dt * 3
        self.hit_flash = decay(self.hit_flash, dt, 3)
        self.emit_cd -= dt
        return self.emit_cd <= 0        # ready to emit?

    def reset_emit(self, faster):
        self.emit_cd = random.uniform(*( (0.7, 1.6) if faster else (1.4, 2.8) ))

    def take_hit(self, game, dmg):
        self.hp -= dmg
        self.hit_flash = 1.0
        game.fx.burst(self.pos, (170, 120, 90), 6, 150)
        if self.hp <= 0 and not self.dead:
            self.dead = True
            game.fx.burst(self.pos, (200, 150, 110), 30, 300)
            game.fx.spark_burst(self.pos, (255, 220, 160), 20, 360)
            game.fx.ring(self.pos, (220, 170, 120))
            game.shake(8)
            if random.random() < 0.5:
                game.spawn_fruit(self.pos)
            if random.random() < 0.22:              # rare: nests can drop a charm
                from ..combat import charms as CH
                p = game.nearest_player(self.pos) or (game.players[0] if game.players else None)
                if p and not p.dead:
                    from . import progression as PR
                    avail = [c.id for c in CH.CHARMS if c.id not in p.charms_owned
                             and PR.unlocked(game.meta, 'charm', c.id)]
                    if avail:
                        cid = random.choice(avail)
                        p.gain_charm(cid, game)
                        game.fx.popup(self.pos, f"CHARM: {CH.CHARMS[cid].name}", CH.CHARMS[cid].color)

    def draw(self, surf, cam):
        sp = cam.w2s(self.pos)
        breathe = 1.0 + 0.06 * math.sin(self.pulse)
        r = int(self.max_r * cam.zoom * breathe)
        base = (96, 66, 52)
        if self.hit_flash > 0:
            base = tuple(int(b + (255 - b) * self.hit_flash) for b in base)
        # lumpy mound
        for dx, dy, rr in ((-0.5, 0.1, 0.9), (0.5, 0.1, 0.9), (0, -0.4, 0.8), (0, 0.3, 1.0)):
            p = (sp[0] + int(dx * r), sp[1] + int(dy * r))
            pygame.draw.circle(surf, base, p, max(2, int(rr * r)))
        # glowing maw that brightens as it's about to emit
        heat = clamp(1.0 - self.emit_cd / 2.6, 0, 1)
        palette.glow(surf, sp, r * 1.1, (255, 120, 80), 0.3 + 0.5 * heat)
        pygame.draw.circle(surf, (30, 16, 14), sp, max(2, int(r * 0.42)))
        pygame.draw.circle(surf, palette.mix((60, 30, 24), (255, 140, 90), heat),
                           sp, max(1, int(r * 0.42 * (0.4 + 0.5 * heat))))
        # hp pip ring
        if self.hp < self.maxhp:
            f = clamp(self.hp / self.maxhp, 0, 1)
            pygame.draw.arc(surf, (120, 240, 120),
                            (sp[0] - r - 6, sp[1] - r - 6, 2 * (r + 6), 2 * (r + 6)),
                            -math.pi / 2, -math.pi / 2 + f * C.TAU, max(2, int(3 * cam.zoom)))


# --------------------------------------------------------------------------- #
#  Per-wave difficulty curve (issue #23)                                       #
# --------------------------------------------------------------------------- #
# Every wave-based dial lives here so the SHAPE of the curve is in one place
# instead of inline at each use site. The knee constants are in config.py.
# Below its knee each curve is byte-identical to the old linear one, so the
# early game is untouched -- the ramp only bites where the snowball started.

def wave_hp_bonus(wave):
    """HP added on top of an enemy's base HP, by wave.

    Pre-knee: the old linear ``WAVE_HP_BASE * wave``. Post-knee: plus a
    super-linear term, so late waves threaten a player who has stacked might.
    """
    bonus = wave * C.WAVE_HP_BASE
    if wave > C.WAVE_HP_KNEE:
        bonus += ((wave - C.WAVE_HP_KNEE) ** C.WAVE_HP_POST_KNEE_EXP
                  * C.WAVE_HP_POST_KNEE_MULT)
    return int(bonus)


def wave_speed_mul(wave):
    """Enemy speed multiplier by wave (1.0 = base). Caps at +75% late."""
    base = min(C.WAVE_SPEED_MAX, wave * C.WAVE_SPEED_PER_WAVE)
    post = 0.0
    if wave > C.WAVE_SPEED_KNEE:
        post = min(C.WAVE_SPEED_POST_KNEE_MAX,
                   (wave - C.WAVE_SPEED_KNEE) * C.WAVE_SPEED_POST_KNEE_PER_WAVE)
    return 1.0 + base + post


def wave_budget(wave, theme_budget):
    """Total enemies the wave may spawn, before the boss-round halving."""
    base = (3 + wave * 1.1) * theme_budget
    if wave > C.WAVE_BUDGET_KNEE:
        base += (wave - C.WAVE_BUDGET_KNEE) * C.WAVE_BUDGET_POST_KNEE_MULT * theme_budget
    return int(base)


def wave_cap(wave, theme_cap):
    """How many enemies may be alive at once, before the boss-round halving."""
    bonus = 0
    if wave > C.WAVE_CAP_KNEE:
        bonus = min(C.WAVE_CAP_POST_KNEE_MAX,
                    (wave - C.WAVE_CAP_KNEE) // C.WAVE_CAP_POST_KNEE_PER_WAVES)
    return theme_cap + bonus


def make_boss(game, boss_id, tier, pos, is_final=False):
    """Build one boss at ``pos``, scaled to ``tier``, and return it (unspawned).

    ``boss_id`` is either a ``BOSS_POOL`` key -- an authored fight with its own
    phase kit + personality + emblem -- or a bare species key, which yields the
    original random-themed-giant fallback (no pool entry). This is the reusable
    core of a boss spawn: boss-scale body, hp/xp/score by tier, boss-grade
    damping, ``behavior='boss'``, and the ``BossAI``. Who/where/the spawn juice
    stay with the caller: ``_spawn_boss`` for a round, the sandbox for a
    deterministic one-off.
    """
    named = BOSS_POOL.get(boss_id)
    key = named['species'] if named else boss_id

    boss = species.make(key, pos)
    gen = boss.genome
    gen.size *= 2.3                      # rebuild the body at boss scale
    gen.sat = min(1.0, gen.sat + 0.15)
    if named:
        for k, v in named['overrides'].items():
            setattr(gen, k, v)
    # boss-scale weight/inertia (plans/01, table row "Chefe"): never lighter
    # than the underlying species already was (octopus is already 3.0)
    gen.angular_damping = max(gen.angular_damping, 0.5)
    gen.linear_damping = max(gen.linear_damping, 0.4)
    gen.weight = max(gen.weight, 3.0)
    # feedback: player shots were shoving bosses around mid-approach/attack,
    # which is a de-facto free interrupt on top of the damage -- a boss
    # commits to its own movement, it doesn't get knocked off it
    gen.knockback = 0.0
    # Fase 5: the FSM drives the fight now, not the species' own chase/
    # ranged/etc behavior -- 'boss' is a distinct dispatch (creatures/ai/).
    gen.behavior = 'boss'
    boss.__init__(pos, 'enemy', genome=gen)
    boss.species = key
    if is_final:
        gen.size *= 1.35                 # the final boss towers over the rest
        boss.__init__(pos, 'enemy', genome=gen)
        boss.species = key
    boss.hp = int((90 + 200 * tier) * (2.0 if is_final else 1.0))
    boss.max_hp = boss.hp
    boss.is_boss = True
    boss.glow_body = True                # bosses get the player-grade glow
    boss.xp_value = 40 + 15 * tier
    boss.score_value = 500 + 200 * tier
    boss.grants = species.SPECIES[key]['grants']
    boss.max_speed *= 0.82               # big and heavy
    if named:
        boss.boss_name = named['name']
        boss.emblem = named.get('emblem')
        boss.boss_ai = bossai.BossAI(boss, phases=named['phases'](),
                                     personality=named['personality'](),
                                     name=named['name'],
                                     on_phase=named.get('on_phase'))
        if named.get('scar'):
            boss.boss_ai.scar_thresholds = list(named['scar'])
        for k, v in named.get('boss_attrs', {}).items():
            setattr(boss, k, v)
        if named.get('setup'):        # per-boss wiring (Olho-Sismico's blink tick)
            named['setup'](boss)
    else:
        name, _ = species.info(key)
        boss.boss_name = f"{name} PRIMORDIAL" if is_final else f"{name} ALFA"
        boss.boss_ai = bossai.BossAI(boss, phases=bossai.default_phases())
    return boss


class RoundManager:
    def __init__(self, game):
        self.game = game
        self.wave = 0
        self.state = 'intermission'     # intermission | combat | cleared
        self.timer = 2.5                # short delay before round 1
        self.theme = 'invasao'
        self._next_theme = None
        self.banner_t = 0.0
        self.budget = 0
        self.nests = []
        self.marks = []
        self.boss = None
        self.is_boss_round = False
        self.is_final = False
        self._boss_bag = {}     # pool -> shuffled bag; sample bosses without replacement

    def _draw_boss_id(self, pool_ids):
        """Sorteia sem reposição: esvazia o saco antes de repetir qualquer chefe."""
        key = tuple(pool_ids)
        bag = self._boss_bag.get(key)
        if not bag:
            bag = list(pool_ids)
            random.shuffle(bag)
            self._boss_bag[key] = bag
        return bag.pop()

    # ---- lifecycle ------------------------------------------------------ #
    def start_round(self, theme=None):
        self.wave += 1
        g = self.game
        # Rerolls refill per ROUND, not per level-up. Refilling on every level-up
        # made them effectively unlimited -- you level several times a round, so
        # the resource never ran out and stopped being a decision.
        for p in g.players:
            p.rerolls = p.rerolls_per_round
        self.boss = None
        g.arena = None              # issue #26: last round's arena bounds/tint
        g.arena_bounds = None
        self.is_final = (self.game.mode == 'normal' and self.wave >= C.RUN_FINAL_WAVE)
        self.is_boss_round = self.is_final or (self.wave % BOSS_EVERY == 0)
        self.theme = theme or self._next_theme or self._pick_theme()
        self._next_theme = None
        spec = THEMES[self.theme]
        self.budget = wave_budget(self.wave, spec['budget'])
        if self.is_boss_round:
            self.budget = max(3, self.budget // 2)     # fewer mobs, one huge threat
        self.state = 'combat'
        self.banner_t = 2.2
        self.marks = []
        if self.is_boss_round:
            self._spawn_boss()
        # place nests near the players
        center = g.alive_players()[0].pos if g.alive_players() \
            else Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
        n_nests = 1 + (self.wave // 3)
        self.nests = []
        for _ in range(min(n_nests, 3)):
            pos = center + random_dir(random.uniform(360, 620))
            pos.x = clamp(pos.x, 80, C.WORLD_W - 80)
            pos.y = clamp(pos.y, 80, C.WORLD_H - 80)
            self.nests.append(Nest(pos, 6 + self.wave * 2, spec['pool']))
        g.wave = self.wave

    def _spawn_boss(self):
        """A giant, glowing variant of a themed species: the round's centrepiece.

        Isaac-style pool: a tier that has an entry in ``BOSS_TIER_POOLS`` rolls
        ONE authored fight at random from its pool (own phase kit + personality
        + mechanic) -- so the same wave can be a different boss run to run.
        Tiers with no pool yet fall back to the original random-themed-giant.

        Who/where and the spawn juice live here; the body itself is built by
        ``make_boss`` so the sandbox can spawn the exact same boss on demand.
        """
        g = self.game
        tier = self.wave // BOSS_EVERY
        if self.is_final:
            boss_id = BOSS_FINAL
        else:
            pool_ids = _boss_pool_for_tier(tier)
            boss_id = (self._draw_boss_id(pool_ids) if pool_ids
                       else random.choice(THEMES[self.theme]['pool']))
        center = g.alive_players()[0].pos if g.alive_players() \
            else Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
        pos = center + random_dir(620)
        pos.x = clamp(pos.x, 100, C.WORLD_W - 100)
        pos.y = clamp(pos.y, 100, C.WORLD_H - 100)

        boss = make_boss(g, boss_id, tier, pos, is_final=self.is_final)
        g.enemies.append(boss)
        self.boss = boss
        # Issue #26: per-boss arena (tighter bounds + screen tint) for the
        # duration of the fight. Cleared in start_round / reset.
        from .boss.arena import for_boss
        arena = for_boss(boss_id)
        if arena is not None:
            arena.apply(g, pos)
        g.fx.ring(pos, (255, 90, 90))
        g.fx.burst(pos, (255, 120, 90), 34, 320)
        g.shake(12)
        audio.play('nest')
        return boss

    def _pick_theme(self):
        if self.wave <= 1:
            return 'invasao'
        return random.choice(THEME_KEYS)

    def _alive_enemies(self):
        return sum(1 for e in self.game.enemies if not e.dead)

    def cleared(self):
        if self.boss is not None and not self.boss.dead:
            return False                     # the boss must fall first
        return (self.budget <= 0 and self._alive_enemies() == 0
                and not self.marks) or \
               (all(n.dead for n in self.nests) and self._alive_enemies() == 0
                and not self.marks)

    # ---- per-frame ------------------------------------------------------ #
    def update(self, dt):
        g = self.game
        self.banner_t = decay(self.banner_t, dt)
        self.nests = [n for n in self.nests if not n.dead]

        if self.state == 'intermission':
            self.timer -= dt
            if self.timer <= 0:
                self.start_round()
            return

        if self.state == 'cleared':
            # wait here; the game opens the camp (route + shop) and calls request_next.
            return

        if self.state == 'combat':
            spec = THEMES[self.theme]
            for m in self.marks:
                m.update(dt, g)
            self.marks = [m for m in self.marks if not m.done]
            # emit from nests up to the alive cap and remaining budget
            cap = wave_cap(self.wave, spec['cap'])
            if self.budget > 0 and self._alive_enemies() + len(self.marks) < cap:
                live = [n for n in self.nests if not n.dead]
                for n in live:
                    if n.update(dt) and self.budget > 0 and \
                            self._alive_enemies() + len(self.marks) < cap:
                        key = random.choice(spec['pool'])
                        pos = n.pos + random_dir(random.uniform(20, 70))
                        self.marks.append(SpawnMark(pos, key,
                                                    wave_hp_bonus(self.wave),
                                                    wave_speed_mul(self.wave)))
                        self.budget -= 1
                        n.reset_emit(self.wave > 4)
            else:
                for n in self.nests:
                    n.update(dt)         # keep pulse/flash advancing

            if self.cleared():
                self.state = 'cleared'
                # Screen flash belongs to the combat hit that produced it.  Camp
                # does not advance play-state decay, so carrying it past this
                # boundary would leave the boss-death white wash on every frame.
                g.flash = 0.0
                self.timer = 3.0
                if g.alive_players():
                    g.fx.popup(g.alive_players()[0].pos + Vector2(0, -140),
                               "ONDA LIMPA!", C.COL_WHITE)

    def request_next(self, theme=None):
        """Called after the camp to begin the next round (optionally a chosen theme)."""
        self._next_theme = theme
        self.state = 'intermission'
        self.timer = 0.6

    # ---- draw ----------------------------------------------------------- #
    def draw_world(self, surf, cam):
        for n in self.nests:
            if not n.dead and cam.visible(n.pos, 80):
                n.draw(surf, cam)
        for m in self.marks:
            if cam.visible(m.pos, 60):
                m.draw(surf, cam)

    def draw_boss_bar(self, surf, font, bigfont):
        """Big health bar at the top while the round's boss is alive."""
        b = self.boss
        if b is None or b.dead:
            return
        w, h = 620, 20
        cx = C.WIDTH // 2
        x = cx - w // 2
        f = clamp(b.hp / max(1, b.max_hp), 0, 1)
        name = getattr(b, 'boss_name', 'CHEFE')
        # name and bar each reserve a band in the shared top column (game.TopStack)
        # instead of the old fixed y=122 / y-40, which collided with the combo
        # meter and the theme banner on every boss wave.
        stack = self.game.top
        name_y = stack.take(bigfont.get_height())
        name_rect = ui.text(surf, bigfont, name, (cx, name_y),
                            (255, 132, 132), align='center')
        emblem = getattr(b, 'emblem', None)
        if emblem:
            er = max(10, name_rect.height // 2)
            icons.draw(surf, emblem, (name_rect.left - er - 8, name_rect.centery),
                      er, b.color)
        y = stack.take(h)
        pygame.draw.rect(surf, (40, 20, 26), (x, y, w, h), border_radius=10)
        if f > 0:
            col = palette.mix((255, 60, 60), (255, 170, 80), f)
            pygame.draw.rect(surf, col, (x, y, int(w * f), h), border_radius=10)
            palette.glow(surf, (x + int(w * f), y + h // 2), 26, col, 0.5)
        pygame.draw.rect(surf, (16, 12, 18), (x, y, w, h), 3, border_radius=10)
        ui.text(surf, font, f"{int(b.hp)}/{b.max_hp}", (cx, y + 1), (255, 236, 236),
                align='center')

    def draw_banner(self, surf, font, bigfont):
        if self.banner_t <= 0 or self.state != 'combat':
            return
        cx = C.WIDTH // 2
        txt = ui.text_surface(bigfont, THEMES[self.theme]['banner'], C.COL_ENEMY)
        sub = ui.text_surface(font, f"Onda {self.wave}", (230, 230, 246))
        y = self.game.top.take(txt.get_height() + sub.get_height())
        # the old code computed this alpha and never applied it, so the banner
        # vanished in one frame; fade it out over the last 0.6s instead
        a = clamp(self.banner_t / 0.6, 0, 1)
        if a < 1.0:
            # text_surface hands back a *cached, shared* surface -- copy before
            # touching its alpha or every later draw inherits the fade
            txt, sub = txt.copy(), sub.copy()
            txt.set_alpha(int(255 * a))
            sub.set_alpha(int(255 * a))
        surf.blit(txt, (cx - txt.get_width() // 2, y))
        surf.blit(sub, (cx - sub.get_width() // 2, y + txt.get_height()))
