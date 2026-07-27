"""The player lizard: input, dash, tail whip, tongue, weapons and evolution.

Body/animation come from :class:`~lagarto.creatures.base.Lizard`; everything
here is the run state a human drives -- energy, charms, items, mutations, xp.
"""

import math
import random
from pygame import Vector2
import pygame

from ..anim.anim import Anticipation
from ..core import config as C
from ..audio import engine as audio
from ..core import palette
from ..combat import weapons
from ..core.mathutil import clamp, approach, vfrom_angle, safe_norm, angle_of, decay
from .base import Lizard


class Player(Lizard):
    def __init__(self, pos, controller, colorset, index, character=None):
        from . import characters
        char = character if character is not None else characters.get(characters.DEFAULT)
        # Shape comes from the character, HUE comes from the player slot: the
        # colourset is what tells P1 from P2, so letting a character own the hue
        # would make two players who picked the same one indistinguishable.
        super().__init__(pos, 'player', genome=char.make_genome(), color=colorset[0])
        self.character = char
        self.character_id = char.id
        self.colorset = colorset
        self.ctrl = controller
        self.index = index
        self.energy = 100.0
        self.max_energy = 100.0
        self.max_health = 100.0
        self.health = 100.0
        self.food = 0
        self.dash_time = 0.0
        self.dash_cd = 0.0
        # everything this dash already hit -- collisions run every frame, so
        # without this one dash lands ~10 hits on whatever it overlaps
        self.dash_hits = set()
        # rolamento (issue #103): the OTHER dodge -- cheap, frequent, no damage.
        # No hit set, on purpose: nothing about it touches an enemy.
        self.roll_time = 0.0
        self.roll_cd = 0.0
        self.roll_f = 0.0         # 0..1 eased envelope of the squash/release
        # Pristine colour to tint away from while the i-frames are up, same
        # idiom AILizard uses for a friend fading out. `color` is what the body,
        # the glow and the trail all read, so mutating it is the whole effect.
        self.base_color = self.color
        self.clog = 0.0           # how buried in enemy bodies we are (collision.py)
        self.clog_f = 0.0         # smoothed, so the drag eases in/out
        # tail whip ("rabada"): a lateral lunge whose follow-through swings the tail
        self.whip_t = 0.0         # 0 -> 1 over the swing
        self.whip_cd = 0.0
        self.whip_cooldown = 0.85
        self.whip_hits = set()    # one hit per enemy per swing (see dash_hits)
        self.whip_side = 1
        self.whip_dir = Vector2()
        # Tongue. ``tongue_t`` is elapsed SECONDS since the launch, 0 = idle, and
        # the three phase lengths in config carve it into out / stick / reel.
        # Everything visual is derived from it, so there is no second clock to
        # drift out of sync with the one the hit resolves against.
        self.tongue_t = 0.0
        self.tongue_target = None
        self.tongue_grabbed = None      # what the tip is carrying home
        self._tongue_anchor = Vector2()  # where the tip stuck; reel lerps from here
        self._tongue_hit = False         # the connect beat fires exactly once
        self._tongue_shaft = []          # interior shaft points (springs)
        self._tongue_shaft_v = []
        self._tongue_wave = 0.0          # travelling undulation phase
        self._tongue_len = 0.0           # reach at the taut frame (see _tongue_bulge)
        # Issue #5: every offensive verb goes through an Anticipation gate, so
        # `update` returns the action exactly once per press and holding a
        # button can never repeat-fire. The durations are 0 by default (see
        # config): the player fires on the press frame, and wind-up is left to
        # the things you fight. The choice made at the press (tongue target,
        # whip side) is parked here so a non-zero duration still aims at what
        # the player actually saw.
        self.dash_antic = Anticipation(duration=C.DASH_ANTIC_T)
        self.tongue_antic = Anticipation(duration=C.TONGUE_ANTIC_T)
        self.whip_antic = Anticipation(duration=C.WHIP_ANTIC_T)
        self._pending_tongue_target = None
        self._pending_whip_side = 1
        self.aim = Vector2(1, 0)
        self.down = False
        self.revive = 0.0
        self.xp = 0.0
        self.level = 1
        self.xp_to_next = 20.0        # level-ups pause the action: keep them meaningful
        self.pending_levelups = 0
        # evolution state
        self.mutations = []
        self.synergies = set()
        self.thorns = 0
        self.venom = False
        self.wings = False
        self.regen = 0.0
        self._regen_acc = 0.0
        self.xp_mult = 1.0
        self.speed_mult = 1.0
        self.dash_cooldown = 0.45
        self.tongue_range = 230
        # global weapon stats (Vampire-Survivors style; boosted by passives)
        self.might = 1.0             # damage multiplier
        self.area_mult = 1.0         # aura/range size
        self.cooldown_mult = 1.0     # <1 = faster
        self.amount = 0              # +projectiles / +orbitals
        # Stackable SHOT modifiers (issue #104). Both are counters, not flags:
        # the player stacks modifiers on one bullet, an enemy shot picks exactly
        # one (docs/concepts/projectile.md). Read at one place only --
        # Game.spawn_projectile, the choke point every friendly shot passes.
        self.shot_bounces = 0        # ricochets off the walls before dying
        self.shot_homing = 0         # how hard the shot curves toward a target
        self.pollen_mult = 1.0       # from meta-progression (Colheita)
        self.weapons = {}            # weapon id -> level
        self.weapon_state = {}       # weapon id -> per-weapon state
        # --- character-driven knobs (characters.py sets these via char.apply) ---
        self.weapon_cap = 6          # VIBORA caps at 2, LARVA grows 1 -> 6
        self.can_dash = True         # COURACADO cannot dash at all
        self.knockback_immune = False
        self.whip_mult = 1.0         # VIBORA's tail hits far harder
        self.rerolls_per_round = 0   # LAGARTO: rerolls of the level-up hand,
        # refilled once per ROUND (not per level-up: you level several times a
        # round, so refilling there made them effectively unlimited)
        self.rerolls = 0
        self.growth = 0              # LARVA: kills banked toward the next size step
        # --- items (items.py) ---
        self.items = []              # owned item ids, in pickup order
        self.ability = None          # equipped ACTIVE item id (the socket)
        self.ability_cd = 0.0
        self.ability_charge = 0.0    # 0..1, for the HUD ring
        self.ability_kills = 0       # the real counter (integers do not drift)
        self.shed_t = 0.0            # Muda de Pele / Casulo: extra i-frames
        self._trail_cd = 0.0         # spacing of the dash's corrosive puddles
        # mechanic-rewriting passives. Each is read at exactly ONE call site --
        # the dash taught us what happens when the same rule lives in two places.
        self.dash_trail = False      # dash leaves a corrosive puddle
        self.dash_marks = False      # dashing through marks the enemy
        self.dash_chain_bonus = False
        self.tongue_throw = False    # tongue throws instead of pulling
        self.tongue_drain = False
        self.tongue_shot = False     # Lingua-Dardo charm: the tongue also SHOOTS
        self.whip_darts = False      # whip fires darts from the arc tips
        self.whip_reflect = False    # whip bats enemy shots back
        self.whip_full = False       # whip sweeps the whole circle
        self.kill_blast = False
        self.kill_heal = False
        self.poison_spreads = False
        self.pollen_magnet = False
        self.amount_back = False     # weapons also fire backwards
        self.adrenaline = False
        self.extra_life = False
        self.used_extra_life = False
        self.shed_on_hurt = False    # Casulo: extra i-frames after being hit
        # charms (Hollow-Knight-style adaptations in 3 body slots)
        self.armor = 0.0             # fraction of damage blocked (carapaca)
        self.charm_slots = {'head': None, 'back': None, 'tail': None}
        self.charms_owned = []
        # LAST: the character reads and adjusts fields declared above (armour,
        # thorns, health, whip cooldown), so it cannot run any earlier.
        self.gain_weapon(char.weapon)
        if char.apply:
            char.apply(self)

    @property
    def dashing(self):
        return self.dash_time > 0

    @property
    def rolling(self):
        return self.roll_time > 0

    def gain_charm(self, cid, game=None):
        from ..combat import charms
        ch = charms.CHARMS.get(cid)
        if not ch or cid in self.charms_owned:
            return False
        self.charms_owned.append(cid)
        if self.charm_slots.get(ch.slot) is None:      # auto-equip an empty slot
            self.equip_charm(cid, game)
        return True

    def equip_charm(self, cid, game=None):
        from ..combat import charms
        ch = charms.CHARMS.get(cid)
        if not ch:
            return
        slot = ch.slot
        old = self.charm_slots.get(slot)
        if old == cid:
            return
        if old:
            charms.CHARMS[old].unapply(self, game)
        self.charm_slots[slot] = cid
        ch.apply(self, game)
        if game:
            game.fx.burst(self.pos, ch.color, 16, 200)
            game.fx.spark_burst(self.pos, palette.lighten(ch.color, 0.4), 10, 260)
            game.fx.ring(self.pos, ch.color)

    def damage_mult(self):
        """Every player damage source multiplies by this.

        Adrenalina lives here rather than in each weapon/dash/whip: a global rule
        written once cannot drift out of sync with the sources that read it.
        """
        m = self.might
        if self.adrenaline and self.health < self.max_health * C.ITEM_ADRENALINE_HP:
            m *= C.ITEM_ADRENALINE_MULT
        return m

    def dash_damage(self):
        """Damage one dash contact deals.

        Single source of truth on purpose: the nest call site in ``game`` read
        ``C.DASH_DAMAGE`` directly, so any scaling added at the enemy call site
        would have silently skipped nests -- the same "two places that must agree"
        shape as the whip's hitbox vs. its animation span.
        """
        return (C.DASH_DAMAGE * (C.DASH_WINGS_MULT if self.wings else 1.0)
                * self.damage_mult())

    def gain_weapon(self, wid):
        if wid not in self.weapons and len(self.weapons) < self.weapon_cap:
            self.weapons[wid] = 1
            self.weapon_state[wid] = weapons.WEAPONS[wid].new_state()
            return True
        return False

    def level_weapon(self, wid):
        w = weapons.WEAPONS.get(wid)
        if wid in self.weapons and w and self.weapons[wid] < w.maxlevel():
            self.weapons[wid] += 1
            return True
        return False

    def apply_mutation(self, mutation, game):
        mutation.apply(self, game)
        self.mutations.append(mutation.id)
        game.fx.burst(self.pos, mutation.color, 24, 260)
        game.fx.spark_burst(self.pos, palette.lighten(mutation.color, 0.4), 16, 340)
        game.fx.ring(self.pos, mutation.color)
        from ..combat.evolution import check_synergies
        for name in check_synergies(self, game):
            game.fx.popup(self.pos + Vector2(0, -40), name, C.COL_WHITE)
            game.fx.ring(self.pos, self.colorset[0])
            game.shake(5)

    def gain_xp(self, amount, game):
        if self.down or self.dead:
            return
        self.xp += amount * self.xp_mult
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            self.xp_to_next *= 1.42
            self.pending_levelups += 1     # game.step turns these into card picks

    def grant_part(self, part, game):
        g = self.genome
        if part == 'spikes':
            g.spikes += 1
        elif part == 'horns':
            g.horns = min(3, g.horns + 1)
        elif part == 'plates':
            g.plates += 1
        elif part == 'sting':
            g.tail = 'sting'
        elif part == 'legs':
            if g.leg_count >= 10:            # cap so legs don't pile up absurdly
                return
            g.leg_count += 2
            self.max_speed *= 1.05           # more legs = better locomotion
            self.speed_mult *= 1.05
            self.legs = self._build_legs(g, len(self.spine.joints), self.max_r)
            for leg in self.legs:
                leg.init_foot(self.spine)
        game.fx.popup(self.pos, "EVOLUIU!", C.COL_WHITE)
        game.fx.ring(self.pos, self.color)
        game.fx.ring(self.pos, palette.lighten(self.color, 0.4))
        game.fx.burst(self.pos, palette.lighten(self.color, 0.3), 20, 240)
        game.fx.spark_burst(self.pos, C.COL_WHITE, 14, 320)
        game.shake(4)

    def hurt(self, game, src_dir, dmg=10):
        """Take damage. Returns True only if it actually LANDED.

        The return value matters: side effects that ride along with a hit (the
        scorpion's slow) must not fire when the hit bounced off i-frames --
        otherwise you get a debuff with no damage number to explain it.
        """
        # Sandbox god mode (SB6): the player under test ignores all damage
        # application -- energy, movement and dash stay real. ``hurt`` is THE
        # single choke point every damage source funnels through (projectiles,
        # body contact, boss AoEs), so guarding it here covers them all with one
        # early-out. No-op on the normal path: the check short-circuits on
        # ``game.mode == 'sandbox'`` before ``god_mode`` is ever read, and only a
        # player (never an enemy) is in ``game.players``.
        if game.mode == 'sandbox' and game.god_mode and self in game.players:
            return False
        # Both dodges are invulnerable and this is the ONE place that says so:
        # the investida (dash) and the rolamento are two verbs, one i-frame rule.
        if self.dashing or self.rolling or self.hit_flash > 0.45 or self.down \
                or self.shed_t > 0:
            return False
        dmg *= (1.0 - self.armor)                       # carapaca charm blocks a %
        self.health -= dmg
        self.hit_flash = 1.0
        if not self.knockback_immune:   # COURACADO does not get moved, by anything
            self.vel = src_dir * (140 + dmg * 6)
        game.fx.burst(self.pos, self.color, 10 + int(dmg / 2), 200)
        game.fx.spark_burst(self.pos, C.COL_FX_SPARK, 8 + int(dmg / 3), 320)
        game.shake(4 + dmg * 0.4)
        if self.shed_on_hurt:
            self.shed_t = max(self.shed_t, C.ITEM_CASULO_TIME)
        if self.health <= 0 and self.extra_life and not self.used_extra_life:
            # Segundo Folego: one escape per run, and it has to be LOUD or the
            # player will not know it happened
            self.used_extra_life = True
            self.health = self.max_health * 0.5
            self.shed_t = C.ITEM_MUDA_TIME
            game.punch(0.12, 16, flash=0.5)
            game.fx.ring(self.pos, C.COL_FX_REVIVE)
            game.fx.spark_burst(self.pos, C.COL_FX_REVIVE, 34, 460)
            game.fx.popup(self.pos, "SEGUNDO FOLEGO!", C.COL_FX_REVIVE)
            audio.play('levelup', 0.9)
        elif self.health <= 0:
            self.health = 0
            self.down = True
            self.revive = 6.0
            # Drop the tongue. A downed player's update() early-outs before
            # _tongue_step, so anything left mid-flight would hang in the air
            # for the whole six seconds and then resume from a stale anchor.
            self._drop_tongue()
            game.fx.burst(self.pos, C.COL_WHITE, 26, 260)
            game.fx.ring(self.pos, self.color)
        return True

    def update(self, dt, game):
        if self.down:
            self.revive -= dt
            self.steer(Vector2(), dt)
            self.integrate(dt)
            self.squash = approach(self.squash, 0.7, 6, dt)
            if self.revive <= 0:
                self.dead = True
            return

        c = self.ctrl
        self.aim = safe_norm(c.aim_world - self.pos)

        # Soft collision: pushing through enemies costs speed instead of shoving you
        # around (collision.py fills `clog` with the overlap depth). Eased so it
        # doesn't stutter, and ignored mid-dash -- ploughing through is the point.
        # `clog` sums the overlap of 5x5 sample pairs, so ONE enemy already reached
        # ~25 against the old max_r*1.2 divisor -- the drag saturated on first
        # contact and read as binary (full speed or half speed, nothing between).
        # Scaling the divisor to CONTACT_FULL enemies restores the gradient: one
        # body slows you a little, being buried in the horde slows you a lot.
        full = max(self.max_r * 1.2 * C.CONTACT_FULL, 1.0)
        target_clog = clamp(self.clog / full, 0.0, 1.0)
        self.clog_f = approach(self.clog_f, target_clog, 9, dt)
        drag = 1.0 - C.CONTACT_DRAG * self.clog_f

        speed_mul = 1.0
        if self.dash_time > 0:
            self.dash_time -= dt
            speed_mul = 3.4 if self.wings else 2.9
            drag = 1.0
            game.fx.trail(self.pos, self.color)
            if self.dash_trail:
                self._trail_cd -= dt
                if self._trail_cd <= 0:
                    from ..combat import weapons as W
                    self._trail_cd = C.ITEM_TRAIL_DROP
                    # hostile=False -> `dmg` is DPS and hits ENEMIES (see Puddle)
                    game.spawn_puddle(W.Puddle(self.pos, C.ITEM_TRAIL_R,
                                               C.ITEM_TRAIL_DMG, C.ITEM_TRAIL_LIFE,
                                               hue=95))
        speed_mul *= drag
        self.dash_cd = decay(self.dash_cd, dt)

        # Issue #5: the press goes through an Anticipation gate. At DASH_ANTIC_T
        # = 0 (the default -- see config) it fires on this very frame, but still
        # exactly once per press, so holding the button cannot repeat-fire.
        # Raise the constant and the same code becomes a real wind-up with the
        # coil below.
        if c.dash_edge and self.can_dash and self.dash_cd <= 0 \
                and self.energy >= C.DASH_COST and not self.dash_antic.is_active \
                and self.dash_antic.action is None:
            c.consume('dash')
            self.dash_antic.trigger('dash')
        if self.dash_antic.is_active:
            self.squat_bias = C.DASH_ANTIC_SQUAT
        # Energy is re-checked here, not just at the press: a wind-up is real
        # time, and a weapon can spend the last of it while the coil plays.
        if self.dash_antic.update(dt) == 'dash' and self.dash_time <= 0 \
                and self.energy >= C.DASH_COST:
            move = c.move if c.move.length_squared() > 0.1 else self.facing
            self.vel = safe_norm(move) * self.max_speed * (3.5 if self.wings else 3.0)
            self.dash_time = 0.2 if self.wings else 0.16
            self.dash_hits.clear()          # fresh dash -> everyone is hittable again
            self.dash_cd = self.dash_cooldown * (0.8 if self.wings else 1.0)
            self.energy -= C.DASH_COST if self.wings else C.DASH_COST + 4
            audio.play('dash')
            game.fx.burst(self.pos, self.color, 14, 200)
            game.fx.spark_burst(self.pos, palette.lighten(self.color, 0.3), 12, 340)
            # Issue #9's kicked-up dust, moved off the wind-up and onto the
            # launch: at zero wind-up there is no window to spawn it in, and
            # dust leaving the feet as you go reads better than dust before.
            perp = Vector2(-self.facing.y, self.facing.x)
            for s in (-1, 1):
                game.fx.dust(self.pos + perp * (s * self.max_r * 0.5))
            game.shake(5)

        # --- rolamento: the second dodge (issue #103) ---------------------- #
        # Invulnerable like the investida, and it LAUNCHES like it too -- the
        # point of the roll is escaping a bullet, and escaping means covering
        # ground. It first shipped as a steer multiplier with no impulse; at
        # 1.9x for 0.15 s that moved the lizard about a third of its own body
        # and read as "tried to roll and did not dash".
        # What is left of the asymmetry is the part that matters: the roll deals
        # NO damage, hits nobody, costs a quarter of the energy and comes back
        # roughly twice as often. The investida is the attack, the roll is the
        # exit.
        self.roll_cd = decay(self.roll_cd, dt)
        self.roll_time = decay(self.roll_time, dt)
        if c.roll_edge and self.roll_cd <= 0 and self.energy >= C.ROLL_COST:
            c.consume('roll')
            move = c.move if c.move.length_squared() > 0.1 else self.facing
            self.vel = safe_norm(move) * self.max_speed * C.ROLL_SPEED
            self.roll_time = C.ROLL_TIME
            self.roll_cd = C.ROLL_TIME + C.ROLL_CD    # cd starts when the roll ends
            self.energy -= C.ROLL_COST
            audio.play('dash', 0.45)
            game.fx.dust(self.pos)
            game.fx.burst(self.pos, self.color, 8, 150)
        if self.rolling:
            game.fx.trail(self.pos, self.color)
        self._roll_pose(dt)

        self.steer(c.move, dt, speed_mul)
        self.integrate(dt, on_plant=game.fx.dust, bounds=game.arena_bounds)
        self._whip_arc(dt)

        # Issue #5/#9: same wind-up contract as the dash. The target is picked at
        # the PRESS so the aim is what the player saw, then held until the
        # tongue actually shoots.
        if c.tongue_edge and self.tongue_t == 0 and self.energy >= C.TONGUE_COST \
                and not self.tongue_antic.is_active and self.tongue_antic.action is None:
            c.consume('tongue')
            self.tongue_antic.trigger('tongue')
            # auto-aim at the nearest edible OR enemy, whichever is closer
            ed = game.nearest_edible(self.pos, self.tongue_range)
            en = game.nearest_enemy(self.pos, self.tongue_range)
            if ed and en:
                tgt = ed if self.pos.distance_to(ed.pos) <= \
                    self.pos.distance_to(en.pos) else en
            else:
                tgt = ed or en
            if tgt:
                self.aim = safe_norm(tgt.pos - self.pos)
            self._pending_tongue_target = tgt
        if self.tongue_antic.is_active:
            # jaw-open: stretch UP rather than coil down, so it reads as the
            # opposite gesture to the dash's crouch.
            self.squat_bias = C.TONGUE_ANTIC_SQUAT
        if self.tongue_antic.update(dt) == 'tongue' and self.tongue_t == 0 \
                and self.energy >= C.TONGUE_COST:
            self._launch_tongue(game)
        if self.tongue_t > 0:
            self._tongue_step(dt, game)

        # Iman de Polen: coletaveis (fruta/inseto/ovo) driftam ate voce. Pollen is
        # a counter, not a world pickup, so the magnet pulls the things you can
        # actually pick up -- and killing near them is how you bank pollen anyway.
        if self.pollen_magnet:
            for pk in game.pickups:
                if pk.dead:
                    continue
                d = pk.pos - self.pos
                dist = d.length()
                if 1.0 < dist < C.ITEM_MAGNET_R:
                    pk.pos += safe_norm(d) * -min(dist, C.ITEM_MAGNET_PULL * dt)

        # --- active item ------------------------------------------------- #
        # Same buffer/consume contract as dash and whip: the press survives a
        # frame that ran zero sim steps, and is eaten only when it actually fires.
        self.shed_t = decay(self.shed_t, dt)
        if c.item_edge and self.ability and self.ability_charge >= 1.0:
            from ..combat import items as itemlib
            if itemlib.use_active(self, game):
                c.consume('item')
                audio.play('levelup', 0.5)

        # --- tail whip ("rabada") ---------------------------------------- #
        self.whip_cd = decay(self.whip_cd, dt)
        # Issue #5/#9: the swing side is chosen at the PRESS so the wind-up can
        # already lean into it, and the shortest coil of the three -- the whip is
        # the panic button, so it stays the most responsive.
        if c.whip_edge and self.whip_cd <= 0 and self.energy >= C.WHIP_COST \
                and not self.whip_antic.is_active and self.whip_antic.action is None:
            c.consume('whip')
            self.whip_antic.trigger('whip')
            side = self.whip_side
            foe = game.nearest_enemy(self.pos, 280)
            if foe is not None:
                d = foe.pos - self.pos
                side = 1 if (self.facing.x * d.y - self.facing.y * d.x) > 0 else -1
            self._pending_whip_side = side
        if self.whip_antic.is_active:
            self.squat_bias = C.WHIP_ANTIC_SQUAT
        if self.whip_antic.update(dt) == 'whip' and self.whip_t == 0 \
                and self.energy >= C.WHIP_COST:
            self.whip_t = 0.001
            self.whip_cd = self.whip_cooldown
            self.energy -= C.WHIP_COST
            self.whip_hits.clear()          # fresh swing -> everyone hittable again
            side = self._pending_whip_side
            self.whip_side = -side
            # Sideways ARC, not a velocity impulse. An impulse got erased within a
            # few frames by steer() pulling velocity back to the input direction --
            # what survived was whatever pointed the way you were already going, so
            # the whip read as a forward lunge. Driving the head along the arc (and
            # muting steer while it runs) is what makes the tail crack sideways.
            self.whip_dir = Vector2(-self.facing.y, self.facing.x) * side
            if self.whip_darts:                 # Farpas: piercing barbs off the arc
                self._fire_whip_darts(game)
            audio.play('dash', 0.65)
            game.shake(3)
        if self.whip_t > 0:
            self.whip_t += dt / C.WHIP_TIME
            if self.whip_t >= 1:
                self.whip_t = 0.0
            else:
                game.fx.trail(self.spine.joints[-1], palette.lighten(self.color, 0.3))
                self._whip_hit(game)

        # --- auto-weapons (Vampire-Survivors style: they act on their own) ---
        self.ability_cd = decay(self.ability_cd, dt)
        for wid, lvl in self.weapons.items():
            weapons.WEAPONS[wid].tick(self, game, dt, self.weapon_state[wid], lvl)

        self.energy = clamp(self.energy + dt * 6, 0, self.max_energy)
        if self.regen > 0 and self.health < self.max_health:
            self.health = min(self.max_health, self.health + self.regen * dt)

    def _roll_pose(self, dt):
        """Squash on the launch, stretch on the release -- a spring, not a ball.

        This started life as a *fake roll*: shrink ``spine.link`` so the joints
        collapse into a disc, then spin that disc. It worked as an effect and
        failed as a read -- the lizard curled up and the gesture disappeared
        into a blob, which is exactly what a dodge must not do, since the whole
        point is seeing which way you went.

        Two beats instead:

        * **compress** while the roll is live -- ``squat_bias`` down to
          ``C.ROLL_SQUAT``, legs tucked out of the way.
        * **relax** when it ends -- ``squat_bias`` releases *past* neutral to
          ``C.ROLL_STRETCH`` and settles back. The overshoot is the difference
          between a spring letting go and a value returning to 1.0.

        ``roll_f`` is the same eased envelope as before (in AND out, never
        snapped), so the same knob still governs how sharp the whole thing is.
        The spine keeps its link, so the body stays a body.
        """
        # Fast in, slow out: the compression has to arrive inside a 0.15 s roll,
        # but the release is the half anyone actually watches, and letting it
        # decay at the same rate starves the overshoot (see ROLL_RELEASE_EASE).
        self.roll_f = approach(self.roll_f, 1.0 if self.rolling else 0.0,
                               C.ROLL_EASE if self.rolling else C.ROLL_RELEASE_EASE,
                               dt)
        if self.roll_f < 1e-3:
            self.roll_f = 0.0
            self.color = self.base_color
            return
        f = self.roll_f
        # Colour says "you cannot be hit right now". It rides the same envelope
        # as the pose, so it arrives and leaves with the squash instead of
        # needing a timer of its own, and it tints toward a COOL pale rather
        # than white -- `hit_flash` already whitens the body, and "I am
        # untouchable" must not read like "I just got hit".
        self.color = palette.mix(self.base_color, C.ROLL_IFRAME_COLOR,
                                 f * C.ROLL_IFRAME_MIX)
        if self.rolling:
            self.squat_bias = 1.0 - f * (1.0 - C.ROLL_SQUAT)
        else:
            # releasing: f now decays 1 -> 0, so the stretch decays with it
            self.squat_bias = 1.0 + f * (C.ROLL_STRETCH - 1.0)
        self.leg_pull = 1.0 - f * (1.0 - C.ROLL_LEG_PULL)
        # ``leg_pull`` alone is not enough: a foot is PLANTED and only takes a
        # step once the body has dragged its rest spot ``step_len`` away, which
        # over a 0.15 s roll never completes -- the legs trailed behind as four
        # straight sticks. Reel the feet in on the same ease, and cancel any
        # step in flight so the two don't fight.
        gather = min(1.0, C.ROLL_EASE * dt * f)
        for leg in self.legs:
            leg.stepping = False
            leg.lift = 0.0
            leg.foot = leg.foot.lerp(
                leg.rest_target(self.spine, self.vel, C.ROLL_LEG_PULL), gather)

    def _whip_span(self):
        """(pivot index, joint count) of the section that whips.

        Shared by the animation and the hitbox on purpose: the damaging joints
        MUST be the ones that visibly move, or you get the classic 'it looked
        like it hit' complaint. When only the last 3 joints were tested and the
        swinging section grew to 6, the tail swept right past enemies.
        """
        n = len(self.spine.joints)
        k = max(4, n // 2)                      # blend the bend over half the body
        pv = n - k - 1                          # pivot joint (behind the legs)
        return (pv, k) if pv >= 1 else (None, 0)

    def _whip_arc(self, dt):
        """Curl the TAIL sideways through the swing, leaving the head where it is.

        The spine is follow-the-leader, so it can only be *driven* from the head --
        which is exactly why an earlier version swung the whole player instead of
        the tail. Here the last few joints are rebuilt from a pivot with a
        per-segment angle offset: link distances stay exact, and the club/sting
        art follows for free because ``parts.draw_tail`` reads js[-1]/js[-2].

        This override survives to draw time only because player contact is soft
        (``collision.py``): the player is never pushed, so ``separate`` skips the
        re-resolve that would otherwise wipe it the same frame.
        """
        if self.whip_t <= 0 or self.whip_dir.length_squared() < 1e-6:
            return
        js = self.spine.joints
        pv, k = self._whip_span()
        if pv is None:
            return
        n = len(js)
        # Anchor the swing to the BODY (straight back from the pivot), not to last
        # frame's tail: spine.resolve rebuilds joint directions from their previous
        # positions, so anchoring to the tail fed the curl back into itself and the
        # swing cancelled out to a wobble.
        back = js[pv] - js[max(0, pv - 2)]
        if back.length_squared() < 1e-6:
            return
        cross = back.x * self.whip_dir.y - back.y * self.whip_dir.x
        side = 1.0 if cross > 0 else -1.0
        # A full period, not a half: the tail sweeps out one side, back through
        # the middle and out the other in a single press. Starts and ends at 0
        # with matching slope, so it eases in and out on its own.
        env = math.sin(self.whip_t * 2.0 * math.pi)
        sweep = C.WHIP_SWEEP * (C.ITEM_SPIRAL_MULT if self.whip_full else 1.0)
        total = side * sweep * env
        # Spread the bend across every joint instead of turning the whole section
        # at the pivot -- that hinge is what read as "a rigid chunk rotating".
        # The ramp toward the tip is GENTLE on purpose: a steep one (quadratic)
        # put ~80 deg into the last link, well past the spine's own bend limit
        # (26 deg), so it showed as a kink and then got clamped by the next
        # resolve. Near-uniform turns = near-circular arc = the lizard keeps its
        # natural curve while still whipping a little harder at the end.
        w = [0.6 + 0.8 * (idx / max(1, k - 1)) for idx in range(k)]
        inv = 1.0 / sum(w)
        ang = angle_of(back)
        for idx, i in enumerate(range(pv + 1, n)):
            ang += total * w[idx] * inv
            js[i] = js[i - 1] + vfrom_angle(ang, self.spine.link)

    def _fire_whip_darts(self, game):
        """Farpas de Cauda: a fan of PIERCING barbs thrown along the swing.

        Fired once at swing start (not per frame). Piercing so they read as the
        tail flinging shrapnel through the horde, not single-target pokes.
        """
        from ..combat.projectile import Projectile
        base = angle_of(self.whip_dir)
        tail = self.spine.joints[-1]
        for k in range(C.ITEM_DART_COUNT):
            off = (k - (C.ITEM_DART_COUNT - 1) / 2) * C.ITEM_DART_SPREAD
            v = vfrom_angle(base + off, C.ITEM_DART_SPEED)
            pr = Projectile(tail, v, (255, 210, 120),
                            dmg=int(round(C.ITEM_DART_DMG * self.damage_mult())),
                            radius=5, hostile=False, life=0.9)
            pr.pierce = True
            game.spawn_projectile(pr)
        game.fx.spark_burst(tail, (255, 220, 150), 8, 300)

    def _whip_reflect(self, game):
        """Contragolpe: the swinging tail bats enemy shots back at their owners."""
        from ..combat import projectile as proj
        js = self.spine.joints
        pv, _k = self._whip_span()
        tail = js[pv + 1:] if pv is not None else js[-3:]
        reach = self.max_r * 1.6
        for pr in game.projectiles:
            if not pr.hostile:
                continue
            if any(pr.pos.distance_to(j) < reach for j in tail):
                pr.hostile = False              # now it hits enemies
                pr.vel = -pr.vel
                # the body repaints itself off `hostile`; the halo has to follow
                # it, or a batted shot keeps glowing in the enemy's colour
                pr.color = proj.FRIENDLY[1]
                pr.dmg = max(pr.dmg, int(round(8 * self.damage_mult())))
                game.fx.spark_burst(pr.pos, (255, 240, 180), 5, 240)

    def _whip_hit(self, game):
        """The real tail joints are the hitbox -- what you see is what hits.

        The tip's own ``spine.radii`` is tiny (~0.22*max_r), so the swing uses an
        explicit reach instead. Gated by ``whip_hits`` for the same reason as
        ``dash_hits``: this runs every frame of the swing.
        """
        if self.whip_t < 0.06 or self.whip_t > 0.97:
            return                      # only the very start/end don't connect
        if self.whip_reflect:
            self._whip_reflect(game)
        js = self.spine.joints
        # Hitbox is the TIP end of the swing, not the whole animated span. The
        # span (half the body) still *moves* -- but damaging all of it hit ~7 of
        # 12 enemies in a full circle, which read as "the tail one-shots the room".
        # The last few joints are the fastest, most visible part of the sweep, so
        # concentrating damage there keeps "what you see hits" while shrinking the
        # area to the arc behind/beside you (measured 2-3 targets).
        tail = js[-C.WHIP_HIT_JOINTS:]
        reach = self.max_r * C.WHIP_REACH
        club = self.genome.tail == 'club'
        sting = self.genome.tail == 'sting'
        # scales with `might` like every auto-weapon does. Without this the whip
        # was a flat number for the whole run -- strong on wave 1, irrelevant by
        # wave 15 -- and no upgrade could ever improve it.
        dmg = (C.WHIP_DAMAGE * (C.WHIP_CLUB_MULT if club else 1.0)
               * self.damage_mult() * self.whip_mult)
        knock = C.WHIP_KNOCK_CLUB if club else C.WHIP_KNOCK
        for e in game.enemies:
            if e.dead or e in self.whip_hits:
                continue
            for j in tail:
                where = e.hit_test(j, reach)
                if not where:
                    continue
                self.whip_hits.add(e)
                d = dmg * (C.CRIT_MULT if where == 'head' else 1.0)
                if where == 'head':
                    game.crit_fx(e.spine.joints[0])
                away = safe_norm(e.pos - j)
                e.take_hit(game, away, int(round(d)))
                e.vel += away * knock   # take_hit ASSIGNS vel, so add afterwards
                if sting:
                    e.apply_poison(2.5, 2.5)
                game.fx.spark_burst(j, palette.lighten(self.color, 0.4), 9, 320)
                game.shake(6 if club else 3)
                if e.dead:
                    game.punch(0.05, 7)
                break

    # ---- tongue ---------------------------------------------------------- #
    # A chameleon slingshot in three beats. OUT throws the tip at the target and
    # decelerates into it, STICK is the frame it snaps taut (where the hit lands
    # and all the impact juice fires), REEL drags whatever it caught home. The
    # shaft is a spring chain pinned at both ends, so it whips and undulates
    # without ever moving the tip -- the tip is kinematic, and the hit and the
    # drawing read the same function for it.

    def _mouth(self):
        return self.spine.joints[0] + self.spine.head_dir() * self.max_r

    def _tongue_aim(self):
        """Where the tip is headed. Follows a live target, so the tongue tracks
        something that moves while the tongue is in the air."""
        t = self.tongue_target
        if t is not None and not t.dead:
            return Vector2(t.pos)
        return self.pos + self.aim * C.TONGUE_REACH_MISS

    def tongue_phase(self):
        """``(name, u)`` -- which beat, and progress 0..1 through it."""
        t = self.tongue_t
        if t <= 0:
            return None, 0.0
        if t < C.TONGUE_OUT_T:
            return 'out', t / C.TONGUE_OUT_T
        t -= C.TONGUE_OUT_T
        if t < C.TONGUE_STICK_T:
            return 'stick', t / C.TONGUE_STICK_T
        t -= C.TONGUE_STICK_T
        if t < C.TONGUE_REEL_T:
            return 'reel', t / C.TONGUE_REEL_T
        return None, 1.0

    def tongue_tip(self):
        """(tip, mouth) -- THE tongue's position, for hits and for the drawing.

        One function, read by both, so what you see is where the tongue is.
        Anything that wants to bend the tongue bends the SHAFT (see
        ``tongue_path``), never this endpoint.
        """
        if self.tongue_t <= 0:
            return None
        mouth = self._mouth()
        ph, u = self.tongue_phase()
        if ph == 'out':
            # ease-out cubic: leaves the mouth explosively, decelerates in
            return mouth.lerp(self._tongue_aim(), 1.0 - (1.0 - u) ** 3), mouth
        if ph == 'stick':
            # springs past the target and settles -- the slingshot snapping taut
            aim = self._tongue_aim()
            over = C.TONGUE_OVERSHOOT * math.sin(u * math.pi * 2.0) * (1.0 - u)
            return aim + (aim - mouth) * over, mouth
        # reel: from where it stuck back into the mouth, smoothstepped
        e = u * u * (3.0 - 2.0 * u)
        return self._tongue_anchor.lerp(mouth, e), mouth

    def tongue_path(self):
        """The tongue as a list of world points, mouth first, tip last.

        Interior points are springs (``_tongue_shaft``) chasing an ideal curve:
        a gravity sag plus a wave travelling toward the tip, both scaled by
        ``sin(s * pi)`` so they vanish at the pinned ends. The springs are what
        make it whip on the launch and slacken on the way back; the pinning is
        what keeps the tip honest.

        Only the segments still OUTSIDE the mouth are returned -- the rest have
        been swallowed (see ``_tongue_active``).
        """
        t = self.tongue_tip()
        if t is None or not self._tongue_shaft:
            return None
        tip, mouth = t
        n_in = self._tongue_active(self._tongue_material()) - 2
        return [mouth] + [Vector2(p) for p in self._tongue_shaft[:max(0, n_in)]] + [tip]

    def _tongue_material(self):
        """How much tongue is still OUTSIDE the mouth, in px.

        The mouth swallows the tongue as it reels: this is the length of the
        part that is still out. It runs out at the end of the reel, and it
        shrinks more slowly than the ends close on each other -- that difference
        is the slack, and the slack is the coil.
        """
        ph, u = self.tongue_phase()
        if ph is None:
            return 0.0
        if ph != 'reel':
            return self._tongue_len or C.TONGUE_REACH_MISS
        return self._tongue_len * (1.0 - u * u)

    def _tongue_active(self, material):
        """How many path points are still out of the mouth, ends included.

        THE fix for the knot. The shaft used to keep all its segments while only
        the tip came home, so segment spacing collapsed toward zero and the same
        number of points had to fit an ever-shorter span -- they had nowhere to
        go but sideways, folding the shaft over itself. Real segment spacing is
        fixed (it is a physical length of tongue); what changes is HOW MANY
        segments are still outside. Swallow them.
        """
        if self._tongue_len <= 1e-4:
            return C.TONGUE_SEGMENTS
        frac = clamp(material / self._tongue_len, 0.0, 1.0)
        return max(2, int(round(C.TONGUE_SEGMENTS * frac)))

    def _tongue_bulge(self, span, material):
        """Lateral amplitude in ABSOLUTE px -- how much tongue is spare.

        A thrown tongue is ballistic and nearly straight. A retracting one has
        more tongue out than the gap between its ends, and the excess bows to
        the side: that is what coiling is. Scaling the bow by the CURRENT span
        instead makes it vanish exactly when the tongue is longest, which reads
        as a stiff arc.
        """
        ph, _u = self.tongue_phase()
        if ph != 'reel':
            return span * C.TONGUE_TAUT_BOW
        return clamp(material - span, 0.0, self._tongue_len * C.TONGUE_COIL_MAX)

    def _tongue_ideal(self, i, mouth, tip, bulge, active):
        """Rest position of interior shaft point ``i``.

        ``active`` is how many points are still out of the mouth, so the ones
        that remain spread over the CURRENT span instead of being crammed
        together -- which is what stopped the shaft folding over itself.
        """
        s = (i + 1) / max(1.0, active - 1.0)
        d = tip - mouth
        length = d.length()
        if length < 1e-4:
            return Vector2(mouth)
        d = d / length
        env = math.sin(s * math.pi)          # 0 at both pinned ends
        down = Vector2(-d.y, d.x)
        if down.y < 0:                       # sag toward world down
            down = -down
        side = Vector2(-d.y, d.x)
        sag = bulge * C.TONGUE_SAG_SHARE * env
        wave = (bulge * C.TONGUE_WAVE_SHARE * env
                * math.sin(s * C.TONGUE_WAVE_CYCLES * C.TAU - self._tongue_wave))
        return mouth + d * (s * length) + down * sag + side * wave

    def _launch_tongue(self, game):
        """Fire the tongue: commit the target, seed the shaft, sell the launch."""
        self.tongue_t = 1e-4
        self.energy -= C.TONGUE_COST
        self.tongue_target = self._pending_tongue_target
        self._pending_tongue_target = None
        self.tongue_grabbed = None
        self._tongue_hit = False
        self._tongue_wave = 0.0
        self._tongue_len = 0.0
        mouth = self._mouth()
        # every shaft point starts AT the mouth, so the tongue visibly shoots
        # out of the head instead of appearing along its full length
        self._tongue_shaft = [Vector2(mouth) for _ in range(C.TONGUE_SEGMENTS - 2)]
        self._tongue_shaft_v = [Vector2() for _ in range(C.TONGUE_SEGMENTS - 2)]
        audio.play('tongue_out', 0.55)
        game.fx.dust(mouth)
        game.shake(1.5)
        if self.tongue_shot:            # Lingua-Dardo (#104): the ONE aimed shot
            self._fire_tongue_dart(game)

    def _fire_tongue_dart(self, game):
        """Lingua-Dardo: the tongue spits a dart along the same aim it grabs on.

        The only player attack the player themself aims -- every weapon stays
        automatic (`nearest_enemy`), so this is a verb, not a second aiming
        system. It goes through ``spawn_projectile`` like everything else, so
        the stacked shot modifiers (#104) ride it too.
        """
        from ..combat.projectile import spit as mk_spit
        mouth = self._mouth()
        aim = self.tongue_target.pos if self.tongue_target is not None \
            else mouth + self.aim * self.tongue_range
        game.spawn_projectile(mk_spit(
            mouth, aim, self.color, dmg=int(round(C.TONGUE_DART_DMG * self.damage_mult())),
            effect='poison' if self.venom else None, speed=C.TONGUE_DART_SPEED,
            radius=5, hostile=False))
        game.fx.spark_burst(mouth, palette.lighten(self.color, 0.3), 5, 220)

    def _tongue_connect(self, game):
        """The taut frame: resolve the hit and spend the impact juice."""
        self._tongue_hit = True
        tip, mouth = self.tongue_tip()
        self._tongue_anchor = Vector2(tip)
        # the material length, frozen here: the reel bulges by whatever of
        # this the closing endpoints no longer account for
        self._tongue_len = mouth.distance_to(tip)
        t = self.tongue_target
        if t is None or t.dead:
            game.fx.dust(tip)                # whiffed: a puff, nothing more
            return
        audio.play('tongue_hit', 0.6)
        game.punch(0.045, 5)
        game.fx.spark_burst(tip, C.COL_FX_SPARK, 9, 260)
        game.fx.ring(tip, getattr(t, 'color', C.COL_WHITE))
        # the line snaps taut and tugs the LIZARD toward its catch -- small, but
        # it is what makes the tongue feel attached to a body with mass
        self.vel += safe_norm(tip - self.pos) * C.TONGUE_RECOIL
        if getattr(t, 'kind', None) == 'enemy':
            away = safe_norm(t.pos - self.pos)
            t.take_hit(game, away, 2)
            if self.tongue_throw:            # Arremesso: fling OUT, never carried
                t.vel += away * C.ITEM_THROW_SPEED
            else:
                # A hit cannot knock away something on a leash. take_hit has
                # just pushed it outward; cancel that component and replace it
                # with a yank toward the mouth, or the knockback wins and the
                # reel spends its whole 170 ms undoing it.
                out = t.vel.dot(away)
                if out > 0:
                    t.vel -= away * out
                t.vel -= away * C.TONGUE_YANK
                self.tongue_grabbed = t
            if self.tongue_drain:            # Sanguessuga: steal life
                self.health = min(self.max_health, self.health + C.ITEM_DRAIN)
                game.fx.popup(self.pos, "+vida", (120, 240, 140))
        else:
            self.tongue_grabbed = t          # food rides the tip home

    def _tongue_step(self, dt, game):
        """Advance the tongue one sim step: phase beats, shaft springs, drag."""
        self.tongue_t += dt
        ph, u = self.tongue_phase()
        self._tongue_wave += dt * C.TONGUE_WAVE_SPEED

        if ph in ('stick', 'reel') and not self._tongue_hit:
            self._tongue_connect(game)       # crossed into STICK: land the hit
        if ph is None:                        # arrived home
            self._tongue_finish(game)
            return

        tip, mouth = self.tongue_tip()
        # Shaft springs. Critically damped so it whips without jittering, and
        # advanced with the sim step so the shape is timestep independent.
        k = C.TONGUE_LAG
        c = 2.0 * math.sqrt(k)
        span = mouth.distance_to(tip)
        material = self._tongue_material()
        active = self._tongue_active(material)
        bulge = self._tongue_bulge(span, material)
        # Only the segments still outside the mouth are simulated. The ones
        # behind them have been swallowed, and a swallowed segment has no shape
        # to hold -- it is what kept the shaft from having to fold up.
        n_in = max(0, active - 2)
        for i in range(n_in):
            p, v = self._tongue_shaft[i], self._tongue_shaft_v[i]
            ideal = self._tongue_ideal(i, mouth, tip, bulge, active)
            v.x += ((ideal.x - p.x) * k - v.x * c) * dt
            v.y += ((ideal.y - p.y) * k - v.y * c) * dt
            p.x += v.x * dt
            p.y += v.y * dt

        g = self.tongue_grabbed
        if g is not None and g.dead:
            self.tongue_grabbed = None       # it died mid-reel; drop it
        elif g is not None and ph == 'reel':
            # Only on the way back. During STICK the tip deliberately springs
            # PAST the target, so hauling the target onto the tip there would
            # drag it outward by the overshoot -- the wrong direction.
            if getattr(g, 'kind', None) == 'enemy':
                # heavy: pulled by force, so the world can still block it
                g.vel += safe_norm(tip - g.pos) * C.TONGUE_DRAG * dt
            else:
                # light: STUCK to the pad, so it rides the tip exactly. A soft
                # follow lags a tip moving ~900 px/s by tens of pixels, which
                # reads as food trailing on a string instead of being caught.
                # Its own velocity is cleared so fleeing cannot fight the glue.
                g.pos = Vector2(tip)
                if hasattr(g, 'vel'):
                    g.vel *= 0.0
                if random.random() < dt * 26:
                    game.fx.trail(g.pos, getattr(g, 'color', C.COL_BUG))

    def _draw_tongue(self, surf, cam):
        """Stroke the shaft twice -- ink underneath, tongue on top.

        Same ink boundary the body has, for ~2 * segments draw calls and no
        surface allocation. Two things carry the feel:

        - the shaft THINS as it extends, like something elastic under tension,
          and thickens again as it slackens on the way back;
        - the sticky tip swells when it is carrying something home.
        """
        path = self.tongue_path()
        if path is None:
            return
        pts = cam.w2s_many(path)
        n = len(pts) - 1
        z = cam.zoom
        ph, u = self.tongue_phase()
        # 1.0 at the mouth, 0 fully retracted: how much tongue is out there
        mouth, tip = path[0], path[-1]
        ext = min(1.0, mouth.distance_to(tip) / max(1.0, C.TONGUE_REACH_MISS))
        stretch = 1.0 - 0.35 * ext           # thin under tension
        shaft = max(2, int(3.4 * z * stretch))
        ink = max(1, int(2 * z))
        carrying = self.tongue_grabbed is not None and not self.tongue_grabbed.dead
        tip_r = max(3, int((6.5 if carrying else 5.0) * z))
        body_col = (230, 60, 90)
        for col, pad in ((C.COL_INK, ink), (body_col, 0)):
            for i in range(n):
                # taper toward the tip, where the sticky pad is
                w = int(shaft * (1.5 + 0.85 * (i / n))) + 2 * pad
                pygame.draw.line(surf, col, pts[i], pts[i + 1], max(1, w))
            pygame.draw.circle(surf, col, pts[-1], tip_r + pad)
        # wet highlight on the pad, offset toward the mouth so it reads as 3D
        hl = (pts[-1][0] + (pts[-2][0] - pts[-1][0]) * 0.28,
              pts[-1][1] + (pts[-2][1] - pts[-1][1]) * 0.28)
        pygame.draw.circle(surf, (255, 180, 200), (int(hl[0]), int(hl[1])),
                           max(2, int(2.6 * z)))
        if ph == 'stick':
            # the taut flash: a ring snapping outward at the moment of contact
            r = int((6 + 26 * u) * z)
            palette.glow(surf, pts[-1], r, (255, 210, 180), 0.5 * (1.0 - u))

    def _drop_tongue(self):
        """Retract everything with no payoff. The one place tongue state is
        cleared, so a new launch can never inherit half of an old one."""
        self.tongue_t = 0.0
        self.tongue_target = None
        self.tongue_grabbed = None
        self._tongue_hit = False
        self._tongue_len = 0.0
        self._tongue_shaft = []
        self._tongue_shaft_v = []

    def _tongue_finish(self, game):
        """Back in the mouth: swallow whatever made it home, then reset."""
        g = self.tongue_grabbed
        if g is not None and not g.dead and getattr(g, 'kind', None) != 'enemy':
            game.eat(self, g)                # eat() owns its own burst/popup
            self.squat_bias = 0.88           # the gulp
        self._drop_tongue()

    def _draw_slow_mark(self, surf, cam):
        """Show WHY you are slow.

        Two independent brakes multiply on the player (a sting's slow and the
        contact drag) and neither had any tell, so being at half speed looked
        like the game misbehaving. Cold rings under the body read as "something
        is holding you" without adding a HUD element.
        """
        if self.slow_t <= 0:
            return
        sp = cam.w2s(self.pos)
        f = clamp(self.slow_t / 0.4, 0, 1)
        r = int(self.max_r * 1.9 * cam.zoom)
        col = (120, 190, 255)
        palette.glow(surf, sp, r, col, 0.22 * f)
        pygame.draw.circle(surf, col, sp, r, max(1, int(2 * cam.zoom)))

    def draw(self, surf, cam):
        self._draw_slow_mark(surf, cam)
        for wid, lvl in self.weapons.items():        # auras behind the body
            w = weapons.WEAPONS[wid]
            if w.layer == 'under':
                w.draw(surf, cam, self, self.weapon_state[wid], lvl)
        self._draw_tongue(surf, cam)
        super().draw(surf, cam)
        for wid, lvl in self.weapons.items():        # orbitals in front
            w = weapons.WEAPONS[wid]
            if w.layer == 'over':
                w.draw(surf, cam, self, self.weapon_state[wid], lvl)
