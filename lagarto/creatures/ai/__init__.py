"""AI lizards: prey / enemy / friend / turret, and the behaviour dispatch.

``AILizard`` owns the state every AI creature shares (aggro, wander, poison,
slow, champion/boss hooks) and the drawing that only enemies need. What each
species actually *does* per frame lives in a sibling module as a free function
``tick(creature, game, dt, target) -> (direction, speed)``, picked out of
``BEHAVIORS`` by ``genome.behavior``.
"""

import math
import random
from pygame import Vector2
import pygame

from ...core import config as C
from ...audio import engine as audio
from ...core import fonts
from ...core import palette
from ...render import ui
from ...core.mathutil import clamp, safe_norm, vfrom_angle, decay, pulse, random_dir
from ..base import Lizard, TAIL_SPRING_STIFFNESS
from ...world import puddles
from . import burrow, chase, fly, grapple, posing, ranged

# Personality via animation (plans/01 #11): a boss's mood (already computed by
# BossAI for pattern/speed choice) also tightens its own secondary-motion
# springs -- calm reads loose/idle, enraged/cornered reads tense/twitchy.
# Nothing new to draw, the same springs just react faster.
BOSS_MOOD_SPRING_MULT = {'calm': 1.0, 'agitated': 1.25, 'enraged': 1.6,
                         'frustrated': 1.15, 'cornered': 1.4}

# genome.behavior -> per-frame behaviour. 'melee' is the default: a species with
# no behaviour of its own just walks at you.
BEHAVIORS = {
    'melee': chase.melee_tick,
    'lunge': chase.lunge_tick,
    'ranged': ranged.ranged_tick,
    'gunner': ranged.gunner_tick,
    'venom': ranged.venom_tick,
    'lead': ranged.lead_tick,
    'mortar': ranged.mortar_tick,
    'fly': fly.fly_tick,
    'bomber': fly.bomber_tick,
    'burrow': burrow.burrow_tick,
    'grapple': grapple.grapple_tick,
}


def contact_damage(max_r, wave):
    """Melee damage an enemy of this size deals on wave ``wave``.

    Size still matters (a tank should hurt more than a runner), but the wave term
    is a *staircase*, not a ramp: the player can feel "runners started hurting"
    at a step boundary, whereas a smooth curve just reads as the game drifting.
    """
    step = max(0, int(wave)) // C.ENEMY_DMG_STEP
    return int(C.ENEMY_DMG_BASE + max_r * C.ENEMY_DMG_SIZE
               + step * C.ENEMY_DMG_PER_STEP)


class AILizard(Lizard):
    def __init__(self, pos, kind, scale=1.0, color=None, genome=None):
        super().__init__(pos, kind, scale, color, genome)
        self.wander = random_dir()
        self.wander_t = 0.0
        self.hp = int(self.genome.hp)
        self.max_hp = self.hp
        self.species = None
        self.xp_value = 3
        self.score_value = 15
        self.grants = None
        self.base_color = self.color   # pristine colour; friends fade from this
        self.aggro = None         # creature that pulled this enemy's attention
        self.aggro_t = 0.0
        self.life = None          # friends are temporary: seconds left before leaving
        self.poison_t = 0.0
        self.poison_dps = 0.0
        self._pacc = 0.0
        self._dmg_acc = 0.0          # fractional damage from auras/orbitals
        self.lunge_t = 0.0            # >0 telegraphing, <0 mid-lunge
        self.shoot_cd = 0.0
        self.shoot_charge = 0.0      # >0 = winding up a shot (telegraph)
        # --- behaviours added in phase 2 ---
        self.flying = self.genome.behavior == 'fly'   # collision.py skips flyers
        self.bob = random.uniform(0, C.TAU)           # flyer's hover wobble
        self.fuse = 0.0               # bomber: >0 = lit, counts down to the blast
        self._blown = False           # bomber: already detonated (recursion guard)
        self.burst_left = 0           # gunner: shots left in the current burst
        # A marked attack (ANTECIPADOR's lead point, MORTEIRO's patch) draws its
        # footprint from `_rain_points` while `shoot_charge` runs down; these two
        # are the size of the mark and the full wind-up it fills over.
        self.mark_r = 0.0
        self.mark_total = 0.0
        # --- phase B4 behaviours (new procedural bodies) ---
        self.burrowed = False         # centipede: intangible while underground
        self.burrow_state = 'surface'
        self.burrow_t = random.uniform(1.4, C.CENT_SURFACE_TIME)
        self.dive_to = Vector2(self.pos)   # where a burrower will surface
        self.grapple_t = 0.0          # octopus: >0 winding up a grab (arms reach)
        self.grapple_cd = random.uniform(0.4, 1.6)
        self.arm_target = None        # world point the arms reach toward (telegraph)
        self.grab_show = 0.0          # octopus: frames drawing the hooked arm
        self.grabbed = None
        # --- Fase 5: boss FSM (see boss.py; None on a non-boss spawn) ---
        self.boss_ai = None
        self.boss_invuln = False      # intro / phase-transition windows only
        # --- champion layer (see champions.py; None on a plain spawn) ---
        self.champion = None
        self.champion_name = ''
        self.champion_ticks = []      # per-frame hooks from the applied champions
        self.rally_t = 0.0            # ALFA's call: temporary speed boost
        # How strongly the champion advertises itself (aura + name). ESPECTRO
        # drops this while camouflaged -- otherwise its own label floats above it
        # in full colour and gives away the ambush the variant exists to make.
        self.champion_vis = 1.0
        self.marked = False       # Presa Marcada: next hit lands as a crit
        self.front_armor = 0.0        # BLINDADO: fraction blocked from the front
        self.death_blast = False      # EXPLOSIVO: parting AoE
        self.death_split = False       # DIVISOR: splits into smaller copies on death
        self.split_gen = 0             # remaining split generations
        self.split_count = 2           # copies per split (DIVISOR=2; a boss can override)

    def apply_poison(self, dps, dur):
        self.poison_dps = max(self.poison_dps, dps)
        self.poison_t = max(self.poison_t, dur)

    def sync_max_hp(self):
        """Call after spawn-time hp tweaks so the health bar scale is right."""
        self.max_hp = max(self.max_hp, self.hp)

    def damage(self, game, amount, direction=None):
        """Fractional damage (for auras/orbitals/puddles that tick every frame)."""
        self._dmg_acc += amount
        whole = int(self._dmg_acc)
        if whole > 0:
            self._dmg_acc -= whole
            self.hit_flash = max(self.hit_flash, 0.4)
            if direction is not None:
                self.vel += direction * 120 * self.genome.knockback
            self.hp -= whole
            if self.hp <= 0:
                self.die(game)
                return True
        return False

    def _tick_status(self, dt, game):
        if self.poison_t > 0:
            self.poison_t -= dt
            self._pacc += self.poison_dps * dt
            if random.random() < dt * 8:
                game.fx.burst(self.pos, (120, 240, 90), 1, 60)
            if self._pacc >= 1.0:
                d = int(self._pacc)
                self._pacc -= d
                self.hp -= d
                if self.hp <= 0:
                    self.die(game)
                    return True
        return False

    def wander_dir(self, dt):
        self.wander_t -= dt
        if self.wander_t <= 0:
            self.wander_t = random.uniform(0.6, 1.6)
            self.wander = random_dir()
        return self.wander

    def _fade_by_vitality(self):
        """Allies desaturate as they lose health OR run out of time -> readable at a glance."""
        hp_f = self.hp / max(1, getattr(self, 'max_hp', self.hp))
        life_f = 1.0 if self.life is None else clamp(self.life / C.FRIEND_LIFE, 0, 1)
        v = clamp(min(hp_f, life_f), 0, 1)
        self.color = palette.mix((116, 110, 138), self.base_color, v)

    def update(self, dt, game):
        if self.life is not None:                 # allies wander off after a while
            self.life -= dt
            self._fade_by_vitality()
            if self.life <= 0:
                self.dead = True
                game.fx.burst(self.pos, self.color, 14, 170)
                game.fx.ring(self.pos, self.color)
                return
        if self._tick_status(dt, game):
            return
        self.shoot_cd = decay(self.shoot_cd, dt)
        self.aggro_t = decay(self.aggro_t, dt)
        self.rally_t = decay(self.rally_t, dt)
        self.grab_show = decay(self.grab_show, dt)
        for hook in self.champion_ticks:
            hook(self, dt, game)
        if self.aggro is not None and (self.aggro.dead or self.aggro_t <= 0):
            self.aggro = None
        d = Vector2()
        speed = 1.0
        if self.kind == 'prey':
            # flee the nearest threat: a player or a predator (living ecosystem)
            threat = game.nearest_threat(self.pos, 230)
            posing.apply_state_pose(self, self._pose_now('flee' if threat else 'idle'), dt)
            if threat:
                d = safe_norm(self.pos - threat.pos); speed = 1.2
            elif self.genome.behavior == 'hop':
                d = chase.hop(self, dt); speed = 1.0
            else:
                d = self.wander_dir(dt); speed = 0.5
        elif self.kind == 'enemy':
            # a friend that hits us steals the aggro for a few seconds -> allies tank
            target = self.aggro if self.aggro is not None else game.nearest_player(self.pos)
            beh = self.genome.behavior
            if target and target.pos.distance_to(self.pos) < 700:
                if beh == 'boss' and self.boss_ai is not None:
                    # not a species behaviour: the boss FSM owns the frame, and
                    # only it feeds the mood back into the tail spring
                    d, speed = self.boss_ai.tick(dt, game)
                    self._apply_mood_pose()
                    self.boss_ai.apply_body_tell(dt)   # #13 windup body telegraph
                else:
                    # posture BEFORE the tick, so a wind-up telegraph (lunge/spit
                    # crouch) still overrides the resting pose during its window
                    posing.apply_state_pose(
                        self, self._pose_now(self._engaged_state(
                            target.pos.distance_to(self.pos))), dt)
                    tick = BEHAVIORS.get(beh, chase.melee_tick)
                    d, speed = tick(self, game, dt, target)
            elif 'prey' in self.genome.diet:
                prey = game.nearest_prey(self.pos, 480)
                posing.apply_state_pose(self, self._pose_now('hunt' if prey else 'idle'), dt)
                if prey:
                    d = safe_norm(prey.pos - self.pos); speed = 0.9
                    if prey.pos.distance_to(self.pos) < (self.max_r + prey.max_r) and self.attack_cd <= 0:
                        self.attack_cd = 0.7
                        prey.take_hit(game, safe_norm(prey.pos - self.pos), 3)
                        self.hp = min(int(self.genome.hp) + 2, self.hp + 1)
                else:
                    d = self.wander_dir(dt); speed = 0.45
            else:
                posing.apply_state_pose(self, self._pose_now('idle'), dt)
                d = self.wander_dir(dt); speed = 0.45
        elif self.kind == 'turret':
            # A Deployable (docs/concepts/deployable.md): the one kind that does
            # not move. There is no steering branch to write -- its genome has
            # speed 0, so the `steer` below is already a no-op -- only aim, taunt
            # and fire, and WHAT it fires is `genome.shot`, the same emitter
            # pattern + dials every shooter uses (ADR-0012).
            dials = self.genome.shot or {}
            foe = game.nearest_enemy(self.pos, dials.get('range', 320))
            posing.apply_state_pose(self, self._pose_now('attack' if foe else 'idle'), dt)
            if foe is not None:
                self.aggro = foe               # the pupils track what it shoots
                self.aggro_t = C.AGGRO_TIME
                if self.shoot_cd <= 0:
                    self.shoot_cd = dials.get('gap', 1.2)
                    dials['fn'](self, game, foe, dials)
                    # the same taunt the ally does when it lands a hit: what the
                    # turret buys is not damage, it is the horde walking at the
                    # body you planted instead of at you
                    foe.aggro = self
                    foe.aggro_t = C.AGGRO_TIME
        elif self.kind == 'friend':
            leader = game.nearest_player(self.pos)
            foe = game.nearest_enemy(self.pos, 360)
            if foe:
                d = safe_norm(foe.pos - self.pos); speed = 1.2
                if foe.pos.distance_to(self.pos) < (self.max_r + foe.max_r) and self.attack_cd <= 0:
                    foe.take_hit(game, safe_norm(foe.pos - self.pos), 1)
                    foe.aggro = self              # taunt: it now comes after us
                    foe.aggro_t = C.AGGRO_TIME
                    self.attack_cd = 1.1          # allies hit slower than the player
                    game.fx.burst(foe.pos, C.COL_FRIEND, 8, 160)
            elif leader:
                off = leader.pos.distance_to(self.pos)
                if off > 120:
                    d = safe_norm(leader.pos - self.pos)
                    speed = clamp(off / 200, 0.4, 1.3)
                else:
                    d = self.wander_dir(dt) * 0.3
        if self.rally_t > 0:               # roused by an ALFA's call
            speed *= C.CHAMP_ALFA_SPEED
        self.steer(d, dt, speed)
        self.integrate(dt, on_plant=game.fx.dust if self.on_screen else None,
                       bounds=game.arena_bounds)


    def _pose_now(self, base):
        """A fresh hit flinches the creature no matter what it was doing, so a
        recent ``hit_flash`` overrides the derived posture (see posing.py)."""
        return 'hurt' if self.hit_flash > 0.5 else base

    def _engaged_state(self, dist):
        """Posture name while a target is in range: winding up / just hit reads
        as 'attack', closing distance as 'hunt', still-far awareness as 'alert'."""
        if self.lunge_t != 0 or self.attack_cd > 0.5 or self.shoot_charge > 0:
            return 'attack'
        return 'hunt' if dist < 260 else 'alert'

    def _apply_mood_pose(self):
        """Personality via animation (plans/01 #11): bias the SAME tail spring
        that already draws the tail by the boss's current mood -- calm stays
        loose, enraged/cornered snap back faster and read tense, with zero
        new state or draw calls."""
        mult = BOSS_MOOD_SPRING_MULT.get(self.boss_ai.mood, 1.0)
        if self.tail_spring is not None:
            self.tail_spring.stiffness = TAIL_SPRING_STIFFNESS * mult

    def explode(self, game):
        """Bomber blast: one hit per victim, radius damage, then the bomber dies.

        ``_blown`` is set *first*: this ends by calling ``die``, and ``die``
        detonates unexploded bombers -- without the flag the two call each other.
        """
        if self._blown:
            return
        self._blown = True
        pos = Vector2(self.pos)
        r = C.BOMBER_RADIUS
        game.fx.burst(pos, (255, 180, 90), 34, 420)
        game.fx.spark_burst(pos, (255, 240, 180), 18, 480)
        game.fx.ring(pos, (255, 140, 70))
        game.shake(11)
        audio.play('hit', 0.7)
        for p in game.players:
            if p.dead or p.down:
                continue
            d = p.pos.distance_to(pos)
            if d < r + p.max_r:
                # falloff so the edge of the blast is a graze, not a full hit
                f = 1.0 - clamp((d - p.max_r) / max(1.0, r), 0, 1) * 0.55
                p.hurt(game, safe_norm(p.pos - pos), C.BOMBER_DMG * f)
        for e in game.enemies:      # friendly fire: bombers thin their own horde
            if e is self or e.dead:
                continue
            if e.pos.distance_to(pos) < r + e.max_r:
                e.take_hit(game, safe_norm(e.pos - pos), C.BOMBER_SPLASH)
        if not self.dead:
            self.die(game)


    def _draw_weakpoint(self, surf, cam):
        """Mark the head: it is the weak point (crit) and where aiming pays off.

        A crosshair read as UI stuck on the creature. This is purely organic
        instead: a warm halo that breathes *behind* the head, so it glows out
        around the silhouette without painting over the eyes.
        """
        if self.kind != 'enemy' or getattr(self, 'is_boss', False):
            return
        head = self.spine.joints[0]
        if not cam.visible(head, 40):
            return
        sp = cam.w2s(head)
        r = max(6, int(self.spine.radii[0] * 2.1 * cam.zoom))
        pulse = 0.55 + 0.45 * math.sin(self.wobble * 2.4)
        palette.glow(surf, sp, r, palette.lighten(self.color, 0.5),
                     0.30 + 0.16 * pulse)

    def draw(self, surf, cam):
        if self.life is not None and self.life < 5.0:
            # blink faster as the ally is about to leave
            if int(self.life * (12 if self.life < 2 else 6)) % 2 == 0:
                return
        if self.burrowed:                    # underground: only the mound + warning
            self._draw_burrow(surf, cam)
            return
        if self.fuse > 0:
            self._draw_fuse(surf, cam)
        if self.shoot_charge > 0 and getattr(self, '_rain_points', None):
            self._draw_mark(surf, cam)       # on the ground, before the body
        if self.burrow_state == 'digging':
            self._draw_dig_hole(surf, cam)   # behind the body: a growing pit
        if self.champion is not None:
            self._draw_champion_aura(surf, cam)
        if self.boss_ai is not None:
            self.boss_ai.draw(surf, cam)     # windup telegraph, behind the body
        self._draw_weakpoint(surf, cam)      # behind the body: reads as a halo
        super().draw(surf, cam)
        self._draw_health(surf, cam)
        if self.champion is not None:
            self._draw_champion_name(surf, cam)

    def _draw_dig_hole(self, surf, cam):
        """The pit opening under a diving centipede -- so the dive reads as
        burrowing, not a blink-out. Grows over the dig telegraph."""
        f = 1.0 - clamp(self.burrow_t / max(1e-4, C.CENT_DIG_TIME), 0, 1)   # 0->1
        sp = cam.w2s(self.pos)
        r = int(self.max_r * (1.4 + 0.9 * f) * cam.zoom)
        pygame.draw.circle(surf, (44, 32, 22), sp, r)                      # dark pit
        pygame.draw.circle(surf, (150, 112, 74), sp, r, max(1, int(2 * cam.zoom)))  # rim
        palette.glow(surf, sp, int(r * 1.2), (150, 112, 74), 0.18 + 0.2 * f)

    def _draw_burrow(self, surf, cam):
        """Underground: a traveling dirt mound + the ring where it will erupt.

        The ring is the fair telegraph -- it fills as the surfacing nears, so the
        player can read where to NOT be standing (the whole point of the ambush)."""
        sp = cam.w2s(self.pos)
        r = max(3, int(self.max_r * 0.9 * cam.zoom))
        bob = int(math.sin(self.wobble * 3.0) * self.max_r * 0.15 * cam.zoom)
        pygame.draw.circle(surf, (120, 90, 60), (sp[0], sp[1] + bob), r)   # mound
        pygame.draw.circle(surf, (150, 112, 74), (sp[0], sp[1] + bob), r,
                           max(1, int(2 * cam.zoom)))
        tp = cam.w2s(self.dive_to)
        f = 1.0 - clamp(self.burrow_t / max(1e-4, C.CENT_UNDER_TIME), 0, 1)   # 0->1
        rr = max(4, int(self.max_r * 2.2 * cam.zoom))
        warn = (220, 95, 70)
        blink = 0.55 + 0.45 * math.sin(f * f * 40)
        pygame.draw.circle(surf, warn, tp, rr, max(1, int((1 + 2 * f) * cam.zoom)))
        pygame.draw.circle(surf, warn, tp, max(1, int(rr * f)))            # fills in
        palette.glow(surf, tp, int(rr * 1.2), warn, (0.14 + 0.3 * f) * blink)

    def _draw_fuse(self, surf, cam):
        """Draw the blast footprint while the fuse burns.

        The timing rule (>=27 frames of warning) is only half of a telegraph --
        the first version had the time but nothing to *see*, just a few sparks,
        so the player had no way to act on it. Showing the actual radius on the
        ground answers the only question that matters: am I standing in it?
        """
        sp = cam.w2s(self.pos)
        r = int(C.BOMBER_RADIUS * cam.zoom)
        f = 1.0 - clamp(self.fuse / max(1e-4, C.BOMBER_FUSE), 0, 1)   # 0 -> 1
        # flashes faster the closer it gets: reads as urgency without a timer
        blink = pulse(f * f, 46)
        col = palette.mix((255, 170, 60), (255, 250, 220), f)
        palette.glow(surf, sp, r, col, (0.16 + 0.30 * f) * (0.55 + 0.45 * blink))
        pygame.draw.circle(surf, col, sp, r, max(2, int((1 + 2 * f) * cam.zoom)))
        # the body swells and whitens as it is about to go
        palette.glow(surf, cam.w2s(self.spine.joints[0]),
                     int(self.max_r * (1.6 + 1.4 * f) * cam.zoom), col,
                     0.35 + 0.4 * blink)

    def _draw_mark(self, surf, cam):
        """The footprint of a marked attack, filling in as it arms.

        Reuses the boss's own 'rain' telegraph drawer: a common enemy's area
        tell and a boss's say the same thing in the same shape, and the ring on
        the ground answers the only question a telegraph has to answer -- am I
        standing in it? (see docs/concepts/enemy-behaviors.md).
        """
        from ...flow.boss import telegraph
        prog = 1.0 - clamp(self.shoot_charge / max(1e-4, self.mark_total), 0, 1)
        telegraph.telegraph_rain(surf, cam, self, None, prog,
                                 palette.lighten(self.color, 0.4),
                                 pulse(prog * prog, 40))

    def _draw_champion_aura(self, surf, cam):
        """Behind the body, breathing: says 'elite' before you are in its range."""
        if self.champion_vis <= 0.02:
            return
        sp = cam.w2s(self.pos)
        r = max(10, int(self.max_r * 2.6 * cam.zoom))
        palette.glow(surf, sp, r, self.champion.color(),
                     (0.30 + 0.16 * pulse(self.wobble, 2.0)) * self.champion_vis)

    def _draw_champion_name(self, surf, cam):
        """A champion has to be *identifiable*, or the player cannot learn it.

        Sits above the health bar, and only on screen -- an off-screen name would
        just be text floating at the edge of the world.
        """
        if not self.on_screen or cam.zoom < 0.5 or self.champion_vis <= 0.05:
            return
        head = self.spine.joints[0]
        sp = cam.w2s(head + Vector2(0, -self.max_r * 2.0))
        # fade the label by mixing toward the ground, not with alpha: ui.text
        # hands back a shared cached surface, so set_alpha would tint every other
        # champion drawing the same string this frame
        col = palette.mix((48, 52, 62), self.champion.color(), self.champion_vis)
        ui.text(surf, fonts.get(13), self.champion_name,
                (sp[0], sp[1] - 16), col, align='center')

    def _draw_health(self, surf, cam):
        """Small bar above the head, only while hurt -- keeps the screen clean."""
        if getattr(self, 'is_boss', False):      # bosses have the big bar up top
            return
        mx = max(1, getattr(self, 'max_hp', self.hp))
        if self.hp >= mx or self.hp <= 0:
            return
        f = clamp(self.hp / mx, 0, 1)
        head = self.spine.joints[0]
        sp = cam.w2s(head + Vector2(0, -self.max_r * 2.0))
        w = max(16, int(self.max_r * 2.2 * cam.zoom))
        h = max(3, int(4 * cam.zoom))
        x = sp[0] - w // 2
        col = palette.health_color(f)
        pygame.draw.rect(surf, (18, 16, 26), (x - 1, sp[1] - 1, w + 2, h + 2),
                         border_radius=3)
        pygame.draw.rect(surf, col, (x, sp[1], int(w * f), h), border_radius=2)

    def _contact(self, game, target):
        self.attack_cd = 0.8
        if getattr(target, 'dashing', False):
            self.take_hit(game, safe_norm(self.pos - target.pos), 3)
            return
        away = safe_norm(target.pos - self.pos)
        if not hasattr(target, 'hurt'):           # an allied creature, not the player
            target.take_hit(game, away, 2 if self.max_r > 25 else 1)
            if self.genome.tail == 'sting':
                target.apply_slow(C.STING_SLOW, C.STING_SLOW_TIME)
            return
        else:
            landed = target.hurt(game, away, contact_damage(self.max_r, game.wave))
            # The sting only slows on a hit that CONNECTED. It used to fire even
            # when hurt() bounced off i-frames, and its 1.4s duration was longer
            # than the 0.8s attack cooldown -- so a single scorpion kept the
            # player at 50% speed 59% of the time, with no damage number to
            # explain why. Same shape as the Acido and venom-puddle bugs:
            # an effect that lasts longer than its own reapplication interval
            # is permanent by construction.
            if landed and self.genome.tail == 'sting':
                target.apply_slow(C.STING_SLOW, C.STING_SLOW_TIME)
            thorns = getattr(target, 'thorns', 0)
            if thorns:                            # attacker gets pricked
                self.take_hit(game, safe_norm(self.pos - target.pos), thorns)

    def _death_item_fx(self, game):
        """On-death effects owned by player items (Estopim, Contagio).

        One place, not one per item: both need "who died, where, and was it
        poisoned", and splitting that across call sites is how the dash ended up
        with two copies of its damage rule.
        """
        blast = any(p.kill_blast for p in game.players if not p.dead)
        spread = any(p.poison_spreads for p in game.players if not p.dead)
        if not (blast or spread):
            return
        pos = Vector2(self.pos)
        if blast:
            game.fx.burst(pos, (255, 170, 90), 18, 300)
            game.fx.ring(pos, (255, 150, 80))
        poisoned = self.poison_t > 0
        for e in game.enemies:
            if e is self or e.dead:
                continue
            d = e.pos.distance_to(pos)
            if blast and d < C.ITEM_KILL_BLAST_R + e.max_r:
                e.take_hit(game, safe_norm(e.pos - pos), C.ITEM_KILL_BLAST_DMG)
            if spread and poisoned and d < C.ITEM_SPREAD_R + e.max_r:
                e.apply_poison(self.poison_dps, 2.6)

    def take_hit(self, game, direction, dmg):
        # Olho-Sismico: 75% off while the eye is blinking (default 1.0 = everyone
        # else unchanged). hit_test already denies the crit during the blink.
        dmg *= getattr(self, 'dmg_taken_mult', 1.0)
        if self.marked:                  # Presa Marcada, consumed on use
            self.marked = False
            dmg *= C.CRIT_MULT
            game.crit_fx(self.spine.joints[0])
        if self.front_armor > 0 and direction.length_squared() > 1e-6:
            # `direction` is the knockback, i.e. it points AWAY from the attacker,
            # so the attacker sits at -direction. Blocking the front makes going
            # around (or dashing straight through) the counter-play -- which is
            # what the dash already wants you to do.
            if self.spine.head_dir().dot(-safe_norm(direction)) > 0.25:
                dmg = dmg * (1.0 - self.front_armor)
                game.fx.spark_burst(self.spine.joints[0], (215, 225, 255), 5, 180)
        if getattr(self, 'is_boss', False):
            # Issue #119, cosmetic only: a boss has to read as massive, not
            # staggering. Two things were selling "it took a shove" on a creature
            # that takes none. (1) `knockback = 0` turned the line below into
            # `vel = zero`, so every chip hit KILLED the boss's momentum -- a free
            # interrupt mid-approach/charge, the opposite of what zeroing
            # knockback was for. A boss keeps its velocity and finishes the move.
            # (2) hit_flash pinned at 1.0 under continuous fire kept the body
            # whitewashed and (off the boss FSM path) held it in the 'hurt' slump
            # pose. A softer peak still flashes per hit and stays under that
            # threshold. Damage, hitbox and hit_test are untouched -- the head is
            # still the weak point.
            self.hit_flash = max(self.hit_flash, C.BOSS_HIT_FLASH)
        else:
            self.hit_flash = 1.0
            self.vel = direction * 200 * self.genome.knockback   # heavy bruisers barely budge
        game.fx.burst(self.pos, self.color, 10, 180)
        game.fx.spark_burst(self.pos, C.COL_FX_SPARK, 9, 300)
        self.hp -= dmg
        # Issue #135: bleed on every successful hit. Darkened species colour
        # so a green/yellow enemy leaves greenish ichor, not red paint.
        game.world.add_puddle(self.pos, dmg, puddles.darken_species_color(self.color))
        if self.hp <= 0:
            self.die(game)

    def die(self, game):
        self.dead = True
        # A bomber killed before its fuse runs out still goes off -- otherwise the
        # safe play is to shoot it from range and its whole threat evaporates.
        # `_blown` guards the recursion: explode() ends by calling die().
        if self.genome.behavior == 'bomber' or self.death_blast:
            self.explode(game)          # no-op if it already went off (_blown)
        if getattr(self, 'is_boss', False):
            game.punch(0.22, 20, flash=0.9)      # boss death: big stop + flash
            game.fx.spark_burst(self.pos, C.COL_FX_SPARK, 46, 520)
            game.fx.ring(self.pos, (255, 200, 140))
        audio.play('kill', 0.8)
        game.fx.burst(self.pos, self.color, 22, 240)
        game.fx.spark_burst(self.pos, palette.lighten(self.color, 0.4), 18, 380)
        game.fx.ring(self.pos, self.color)
        # Issue #135: death splatter -- two small puddles offset from the body,
        # so the kill leaves a visible mark, not just one disc.
        blood = puddles.darken_species_color(self.color)
        game.world.add_puddle(self.pos + Vector2(8, -4), 6, blood)
        game.world.add_puddle(self.pos + Vector2(-6, 6), 6, blood)
        if self.kind == 'enemy':
            game.add_combo()
            game.add_score(self.score_value)
            game.add_pollen(max(1, self.score_value // 12))
            game.kills += 1
            game.give_xp(self.xp_value)
            from .. import characters
            from ...combat import items as itemlib
            for p in game.players:            # LARVA feeds on the whole run
                if p.dead:
                    continue
                characters.larva_growth(p, game)
                itemlib.add_charge(p)         # kills charge the active item
                if p.kill_heal:
                    p.health = min(p.max_health, p.health + C.ITEM_KILL_HEAL)
            # A kill trickles energy back to the NEAREST player (not all, in co-op),
            # so an aggressive combo self-sustains its dash/tongue/whip a little.
            killer = game.nearest_player(self.pos)
            if killer is not None and not killer.dead:
                killer.energy = min(killer.max_energy,
                                    killer.energy + C.KILL_ENERGY)
            self._death_item_fx(game)
            if random.random() < 0.15:
                game.spawn_fruit(self.pos)
        # DIVISOR (Blobulon/Fistula): burst into two smaller copies. Queued, not
        # appended, so it can't extend the loop that is killing this one.
        if self.death_split and self.species and self.split_gen > 0:
            self._do_split(game)

    def _do_split(self, game):
        from .. import species as splib
        game.fx.ring(self.pos, self.color)
        for k in range(self.split_count):
            child = splib.make(self.species, self.pos)
            child.genome.size = max(0.4, self.genome.size * C.CHAMP_SPLIT_SIZE)
            child.rebuild_body()
            child.hp = max(1, int(self.max_hp * C.CHAMP_SPLIT_HP))
            child.max_hp = child.hp
            child.split_gen = self.split_gen - 1
            child.death_split = child.split_gen > 0
            child.base_color = child.color
            child.pos = self.pos + vfrom_angle(k * 180 + random.uniform(-40, 40), self.max_r)
            child.vel = random_dir(child.max_speed * 0.8)
            game.spawn_enemy(child)
