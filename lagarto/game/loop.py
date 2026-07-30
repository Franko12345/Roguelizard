"""Game: world state, spawning, waves, collisions and the fixed-step update.

Holds the players, AI lizards and pickups, resolves eating/combat, drives the
escalating predator waves and renders the shared world pass. Everything that is
specific to one ``game.state`` lives in a ``state_*`` module next door, and
``step``/``draw`` dispatch to it -- see ``_STATES``.
"""

import copy
import random
from pygame import Vector2
import pygame

from ..core import config as C
from ..core import fonts
from ..core.mathutil import clamp, safe_norm, decay, random_dir
from ..anim.spine import build_radii
from ..creatures.ai import AILizard
from ..creatures.player import Player
from ..creatures import species
from ..combat import evolution
from ..combat import projectile
from ..audio import engine as audio
from ..render import ui
from ..flow import progression
from ..core import palette
from ..creatures import characters
from ..combat import charms as charmlib
from ..world.pickups import Bug, Fruit, Egg
from ..render.fx import FX, shadow
from ..render.camera import Camera
from ..world.terrain import World
from ..flow.rounds import RoundManager
from . import hud
from . import state_camp
from . import state_levelup
from . import state_over
from . import state_pause
from . import state_play

# game.state -> the module that owns its update/draw. 'victory' and 'over' are
# the same screen module. Import direction is one-way: loop imports the states,
# never the other way round.
_STATES = {'play': state_play, 'camp': state_camp, 'levelup': state_levelup,
           'pause': state_pause, 'over': state_over, 'victory': state_over}


class Game:
    def __init__(self, num_players, controllers, font, bigfont, meta=None,
                 mode='normal', chars=None):
        self.mode = mode                     # 'normal' (ends at the final boss) | 'endless'
        self.meta = meta if meta is not None else progression.load()
        self.run_banked = False
        self.font = font
        self.bigfont = bigfont
        # dial labels only: at 18pt "DASH" is 48px wide and ran into the next
        # dial's circle (68px pitch, 11px radius). They are secondary readouts,
        # so shrinking them fixes the collision *and* improves the hierarchy.
        self.smallfont = fonts.get(14)
        self.cam = Camera()
        self.fx = FX()
        self.world = World()

        cx, cy = C.WORLD_W / 2, C.WORLD_H / 2
        self.cam.pos = Vector2(cx, cy)
        self.players = []
        for i in range(num_players):
            off = Vector2(-80 if i == 0 else 80, 0)
            colorset = C.COL_PLAYER if i == 0 else C.COL_PLAYER2
            cid = (chars[i] if chars and i < len(chars) else characters.DEFAULT)
            pl = Player(Vector2(cx, cy) + off, controllers[i], colorset, i,
                        character=characters.get(cid))
            progression.apply_to_player(self.meta, pl)     # permanent upgrades
            self.players.append(pl)

        self.enemies = []
        self.pending_enemies = []     # spawned mid-step (e.g. DIVISOR split), drained safely
        self.friends = []
        self.prey = []
        self.pickups = []
        self.projectiles = []
        self.puddles = []

        self.score = 0
        self.kills = 0
        self.wave = 0
        self.wave_timer = 4.0
        self.time = 0.0
        self.state = 'play'
        self.combo = 0
        self.combo_timer = 0.0
        # Issue #26: per-boss arena state. `arena` is the active BossArena
        # descriptor (or None); `arena_bounds` is the (min_x, min_y, max_x,
        # max_y) box to clamp movement to instead of the full world, or None.
        self.arena = None
        self.arena_bounds = None
        # Sandbox debug staples (SB6). Inert unless ``mode == 'sandbox'``: every
        # read of these is guarded on the mode first, so a normal run never sees
        # them change behaviour. The sandbox overlay flips them from its menu.
        self.god_mode = False        # player ignores damage application (hurt early-out)
        self.pause_ai = False        # freeze enemy/boss/prey/friend update; player still walks
        self.step_once = False       # one-shot: advance the frozen AI exactly one tick
        self.combo_flash = 0.0
        self.score_pulse = 0.0       # line-of-score alpha pulse on each combo tick (#153)
        self.pollen = 0
        # per-RUN shop prices, keyed by item name: a purchase raises the price
        # and it stays raised in every later camp (see state_camp._roll_shop)
        self.shop_prices = {}
        self.hitstop = 0.0        # freeze frames on heavy impacts
        self.flash = 0.0          # brief white screen flash
        self.dt_last = C.DT       # boss.py's per-frame barrage tick reads this
        self.camp = None
        self.rounds = RoundManager(self)
        self.cards = []
        self.card_idx = 0
        self.levelup_player = None
        self.pause_mode = 'menu'  # 'menu' | 'options' | 'controls'
        self.pause_sel = 0
        self.pause_prev = 'play'  # state to return to (pause can open from camp too)
        self.ui_t = 0.0           # clock for the level-up / camp entry animation
        self.pick = None          # a choice being absorbed by the player (see _step_pick)
        self.ui_fx = 0.0          # keeps fx drawn over the veil just after an impact
        self._uilayer = None      # scratch surface so screen shake can move the whole UI
        self._panels = {}         # rendered card/shop/route panels, keyed by their state
        self.top = hud.TopStack()     # shared top-centre column (see TopStack)
        self.hud_capsules = [hud.PlayerCapsule() for _ in range(num_players)]
        self._card_rects = []
        self._shop_rects = []
        self._route_rects = []
        self._charm_rects = []

        for _ in range(46):
            self.pickups.append(Bug(self._rand_world()))
        for _ in range(5):
            self.pickups.append(Fruit(self._rand_world()))
        for _ in range(3):
            self.pickups.append(Egg(self._rand_world()))
        for _ in range(8):
            self.prey.append(self._spawn_prey())

    # ---- helpers -------------------------------------------------------- #
    def _rand_world(self, margin=120):
        return Vector2(random.uniform(margin, C.WORLD_W - margin),
                       random.uniform(margin, C.WORLD_H - margin))

    def _rand_edge_near(self, center, dist=560):
        return center + random_dir(dist)

    def shake(self, m):
        self.cam.add_shake(m)

    def crit_fx(self, pos):
        """Feedback for a weak-point (head) hit."""
        self.fx.spark_burst(pos, (255, 232, 150), 12, 380)
        self.fx.popup(pos, "CRITICO!", (255, 226, 120))
        audio.play('hit', 1.0)

    def punch(self, freeze=0.06, shake=6, flash=0.0):
        """Impact feedback: brief freeze + shake (+ optional screen flash)."""
        self.hitstop = max(self.hitstop, freeze)
        self.cam.add_shake(shake)
        if flash:
            self.flash = max(self.flash, flash)

    def add_score(self, n):
        self.score += int(n * self.combo_mult())

    def combo_mult(self):
        return 1.0 + min(self.combo, 30) * 0.08     # up to ~3.4x

    def add_combo(self):
        self.combo += 1
        self.combo_timer = 3.2
        self.combo_flash = 1.0
        self.score_pulse = 1.0       # line-of-score alpha pulse on each kill (#153)

    def add_pollen(self, n):
        mult = max((getattr(p, 'pollen_mult', 1.0) for p in self.players), default=1.0)
        self.pollen += int(n * self.combo_mult() * mult)

    def alive_players(self):
        return [p for p in self.players if not p.dead]

    def nearest_player(self, pos):
        best, bd = None, 1e9
        for p in self.players:
            if p.dead or p.down:
                continue
            d = p.pos.distance_to(pos)
            if d < bd:
                best, bd = p, d
        return best

    def nearest_enemy(self, pos, rng):
        best, bd = None, rng
        for e in self.enemies:
            if e.dead:
                continue
            d = e.pos.distance_to(pos)
            if d < bd:
                best, bd = e, d
        return best

    def nearest_prey(self, pos, rng):
        best, bd = None, rng
        for e in self.prey:
            if e.dead:
                continue
            d = e.pos.distance_to(pos)
            if d < bd:
                best, bd = e, d
        return best

    def nearest_threat(self, pos, rng):
        """Closest thing a prey should flee: a player or a predator."""
        best, bd = None, rng
        for p in self.players:
            if p.dead or p.down:
                continue
            d = p.pos.distance_to(pos)
            if d < bd:
                best, bd = p, d
        for e in self.enemies:
            if e.dead:
                continue
            d = e.pos.distance_to(pos)
            if d < bd:
                best, bd = e, d
        return best

    def give_xp(self, amount):
        for p in self.players:
            if not p.dead and not p.down:
                p.gain_xp(amount, self)

    def _enter_levelup(self, player):
        self.levelup_player = player
        self.cards = evolution.roll_cards(player, 3)
        self.card_idx = 0
        self.state = 'levelup'
        self.ui_t = 0.0
        self.pick = None
        self._panels.clear()
        audio.play('levelup')
        self.fx.popup(player.pos, f"NIVEL {player.level}!", C.COL_WHITE)
        self.fx.ring(player.pos, player.colorset[0])
        self.shake(4)

    def reroll_cards(self):
        """LAGARTO: redraw the level-up hand. Returns True if it happened.

        Rerolling is what turns a run from something that happens to you into
        something you build -- it is the whole reason to pick LAGARTO twice.
        Blocked while an absorption is playing (``ui_busy``) for the same reason
        picking is: the effect has not been applied yet.
        """
        p = self.levelup_player
        if self.state != 'levelup' or self.ui_busy() or not p or p.rerolls <= 0:
            return False
        p.rerolls -= 1
        self.cards = evolution.roll_cards(p, 3)
        self.card_idx = 0
        self._panels.clear()          # cards are cached by index+state
        audio.play('ui')
        self.fx.ring(p.pos, p.colorset[0])
        return True

    # ---- choosing: pick -> absorption animation -> effect ---------------- #
    def ui_busy(self):
        """True while a screen is still animating in or absorbing a choice."""
        return self.pick is not None or self.ui_t < C.UI_READY

    def choose_card(self, i):
        if self.state != 'levelup' or not self.cards or self.ui_busy():
            return
        i = max(0, min(len(self.cards) - 1, i))
        self.card_idx = i
        rect = (self._card_rects[i] if i < len(self._card_rects)
                else pygame.Rect(C.WIDTH // 2 - 120, C.HEIGHT // 2 - 150, 240, 300))
        state_levelup._start_pick(self, 'card', i, rect, self.cards[i].color,
                                  C.PICK_END, item=self.cards[i])

    def _apply_card(self, card):
        p = state_levelup._pick_player(self)
        if p is None:
            return
        if getattr(card, 'is_weapon', False) or getattr(card, 'is_item', False):
            card.apply(p, self)
            # items count toward synergies too (evolution.owned_tags), so the
            # check has to run for them as well, not only for mutations
            for name in evolution.check_synergies(p, self):
                self.fx.popup(p.pos, name, C.COL_WHITE)
        else:
            p.apply_mutation(card, self)
        p.pending_levelups = max(0, p.pending_levelups - 1)
        self.fx.popup(p.pos, card.name, card.color)
        self.cards = []
        self.state = 'play'          # step() re-enters if more level-ups are queued

    # ---- camp (route + shop between rounds) ----------------------------- #
    def _enter_camp(self):
        from ..flow.rounds import THEMES, THEME_KEYS
        picks = random.sample(THEME_KEYS, min(3, len(THEME_KEYS)))
        bonuses = ['cura', 'polen', 'carta']
        random.shuffle(bonuses)
        routes = [dict(theme=k, bonus=bonuses[i % 3], label=THEMES[k]['banner'])
                  for i, k in enumerate(picks)]
        # A PHYSICAL clearing (Hades): the shop is a tent you can walk up to and the
        # routes are three doors you walk through. Everything is placed around the
        # spot where the players cleared the wave, so no teleport is needed.
        alive = [p for p in self.players if not p.dead]
        center = Vector2()
        for p in (alive or self.players):
            center += p.pos
        center /= max(1, len(alive or self.players))
        center.x = clamp(center.x, 420, C.WORLD_W - 420)
        center.y = clamp(center.y, 420, C.WORLD_H - 420)
        tent = center + Vector2(*C.CAMP_TENT_OFF)
        n = len(routes)
        doors = []
        for i, r in enumerate(routes):
            dx = (i - (n - 1) / 2) * C.CAMP_DOOR_SPAN
            doors.append(dict(pos=center + Vector2(dx, -C.CAMP_DOOR_UP), route=r,
                              delay=C.CAMP_DOOR_DELAY + i * C.CAMP_DOOR_STAGGER,
                              landed=False))
        self.camp = dict(routes=routes, shop=state_camp._roll_shop(self), sel=0,
                         focus='shop', shop_sel=0, charm_col=0, charm_row=0,
                         mode='field', center=center, tent=tent, doors=doors,
                         reopen_cd=C.CAMP_REOPEN_CD,
                         born=self.time, tent_delay=C.CAMP_TENT_DELAY, tent_landed=False)
        self._route_rects = []
        self._shop_rects = []
        self._charm_rects = []
        self.state = 'camp'
        self.ui_t = 0.0
        self.pick = None
        self._panels.clear()
        # a clean clearing: drop leftover prey/hazards so nothing clutters a
        # doorway or lingers on the ground while you shop
        self.prey = []
        self.projectiles = []
        self.puddles = []
        for p in self.players:
            if not p.dead:
                p.health = min(p.max_health, p.health + p.max_health * 0.12)

    def camp_close_shop(self):
        """Leave the tent back to the clearing (with a re-open cooldown so a step
        standing on the tent does not instantly reopen it)."""
        if self.camp and self.camp.get('mode') == 'shop' and self.pick is None:
            self.camp['mode'] = 'field'
            self.camp['reopen_cd'] = C.CAMP_REOPEN_CD
            audio.play('ui', 0.5)

    def camp_equip(self, cid):
        if self.ui_busy():
            return
        if self.players and not self.players[0].dead:
            self.players[0].equip_charm(cid)

    # ---- charm grid: one column per slot, walked by keyboard/gamepad -------- #
    def camp_charms(self, col):
        """Owned charms in slot column ``col``, in the order they are drawn."""
        if not self.players:
            return []
        col = max(0, min(len(C.CHARM_SLOTS) - 1, col))
        slot = C.CHARM_SLOTS[col][0]
        return [c for c in self.players[0].charms_owned
                if charmlib.CHARMS[c].slot == slot]

    def camp_has_charms(self):
        return any(self.camp_charms(i) for i in range(len(C.CHARM_SLOTS)))

    def camp_move_charm(self, dcol, drow):
        """Walk the grid. Returns True if the cursor actually moved, so the caller
        knows whether up/down should instead leave the charm area."""
        if not self.camp:
            return False
        n = len(C.CHARM_SLOTS)
        col = self.camp.get('charm_col', 0)
        row = self.camp.get('charm_row', 0)
        if dcol:
            for _ in range(n):              # skip slots with nothing owned yet
                col = (col + dcol) % n
                if self.camp_charms(col):
                    break
            row = 0
        elif drow:
            owned = self.camp_charms(col)
            if not (0 <= row + drow < len(owned)):
                return False                # at an end -> let focus move on
            row += drow
        self.camp['charm_col'] = col
        self.camp['charm_row'] = max(0, min(row, len(self.camp_charms(col)) - 1))
        return True

    def camp_equip_cursor(self):
        if not self.camp:
            return
        owned = self.camp_charms(self.camp.get('charm_col', 0))
        row = self.camp.get('charm_row', 0)
        if 0 <= row < len(owned):
            self.camp_equip(owned[row])

    def camp_buy(self, i):
        if not self.camp or i < 0 or i >= len(self.camp['shop']) or self.ui_busy():
            return
        it = self.camp['shop'][i]
        if self.pollen < it['cost']:
            return
        # pay now (so the price can't be spent twice mid-animation), grant on impact
        self.pollen -= it['cost']
        self.camp['shop_sel'] = i
        # the 'buy' chime belongs on the impact, not here -- see _finish_pick
        rect = (self._shop_rects[i] if i < len(self._shop_rects)
                else pygame.Rect(C.WIDTH // 2 - 88, 164, 176, 132))
        state_levelup._start_pick(self, 'shop', i, rect,
                                  palette.vibrant(it['hue'], 0.8, 1.0),
                                  C.PICK_END, item=it)

    def _apply_buy(self, i):
        if not self.camp or i < 0 or i >= len(self.camp['shop']):
            return
        it = self.camp['shop'][i]
        it['fn'](self)
        it['cost'] = self.shop_prices[it['name']] = int(it['cost'] * C.SHOP_PRICE_MULT)
        self.camp['msg'] = it['name']
        self.camp['msg_t'] = 1.4

    def camp_pick_route(self, i):
        if not self.camp or self.ui_busy():
            return
        i = max(0, min(len(self.camp['routes']) - 1, i))
        self.camp['sel'] = i
        rect = (self._route_rects[i] if i < len(self._route_rects)
                else pygame.Rect(C.WIDTH // 2 - 125, 496, 250, 140))
        state_levelup._start_pick(self, 'route', i, rect, C.COL_ENEMY,
                                  C.PICK_ROUTE_END)

    def _apply_route(self, i):
        if not self.camp:
            return
        r = self.camp['routes'][max(0, min(len(self.camp['routes']) - 1, i))]
        if r['bonus'] == 'cura':
            for pl in self.players:
                pl.health = pl.max_health
        elif r['bonus'] == 'polen':
            self.pollen += 25
        elif r['bonus'] == 'carta':
            for pl in self.alive_players():
                pl.pending_levelups += 1
        self.camp = None
        self.state = 'play'
        self.rounds.request_next(r['theme'])

    def _spawn_prey(self):
        return species.make(random.choice(species.PREY_SPECIES), self._rand_world())

    def _spawn_enemy(self, pos, pool=None):
        key = random.choice(pool or species.ENEMY_SPECIES)
        return species.make(key, pos)

    def nearest_edible(self, pos, rng):
        """Nearest grabbable thing within range -> the tongue auto-aims at it."""
        best, bd = None, rng
        for group in (self.pickups, self.prey):
            for e in group:
                if e.dead:
                    continue
                d = e.pos.distance_to(pos)
                if d < bd:
                    best, bd = e, d
        return best

    def spawn_fruit(self, pos):
        self.pickups.append(Fruit(pos + random_dir(20)))

    def spawn_enemy(self, e):
        """Queue an enemy to join next drain -- safe to call while iterating
        ``self.enemies`` (a dying DIVISOR splitting inside _collisions)."""
        self.pending_enemies.append(e)

    def _stack_shot_mods(self, proj):
        """The player's stackable shot modifiers (#104), applied once per shot.

        Same reason Retaguarda lives in ``spawn_projectile``: this is the one
        choke point every friendly bullet already passes, and a per-weapon copy
        of the rule is how the dash ended up with two of them. Stacking is the
        point -- an enemy shot wears one modifier, the player's wears every one
        they own (docs/concepts/projectile.md).
        """
        alive = [p for p in self.players if not p.dead]
        if not alive:
            return
        bounces = max(getattr(p, 'shot_bounces', 0) for p in alive)
        homing = max(getattr(p, 'shot_homing', 0) for p in alive)
        if bounces:
            proj.bounces_left = bounces
            proj.bounce_damp = 1.0        # a player ricochet that limps is a dud
            proj.on_update.append(projectile.bounce)
        if homing:
            proj.home_mult = homing
            proj.on_update.append(projectile.homing)

    def spawn_projectile(self, proj, mirror=True):
        if mirror and not proj.hostile:   # mirror=False is the Retaguarda copy,
            self._stack_shot_mods(proj)   # which already carries the modifiers
        self.projectiles.append(proj)
        # Retaguarda mirrors every friendly shot backwards. It lives HERE because
        # this is the single choke point every weapon already goes through --
        # implementing it per-weapon would be eight copies of one rule.
        if not (mirror and not proj.hostile):
            return
        if not any(getattr(p, 'amount_back', False) for p in self.players if not p.dead):
            return
        back = copy.copy(proj)
        back.vel = -Vector2(proj.vel)
        back.pos = Vector2(proj.pos)
        self.spawn_projectile(back, mirror=False)      # mirror=False: no recursion

    def spawn_puddle(self, puddle):
        if len(self.puddles) < 40:
            self.puddles.append(puddle)

    def _update_projectiles(self, dt):
        for pr in self.projectiles:
            pr.update(dt, self)               # on_update hooks: homing, bounce, ...
            if pr.dead:
                continue
            if pr.hostile:
                for p in self.players:
                    if p.dead or p.down:
                        continue
                    if p.pos.distance_to(pr.pos) < p.max_r + pr.radius:
                        if pr.effect == 'slow':
                            p.apply_slow(0.5, 1.6)
                        if pr.dmg > 0:
                            p.hurt(self, safe_norm(pr.vel), pr.dmg)
                        self.fx.burst(pr.pos, pr.color, 8, 160)
                        self.fx.spark_burst(pr.pos, palette.lighten(pr.color, 0.3), 6, 200)
                        for fn in pr.on_hit:
                            fn(pr, p, self)
                        pr.dead = True
                        break
            else:
                for e in self.enemies:
                    if e.dead:
                        continue
                    if pr.pierce and pr._pierced is not None and e in pr._pierced:
                        continue                # piercing shot already went through
                    where = e.hit_test(pr.pos, pr.radius)
                    if where:
                        dmg = pr.dmg
                        if where == 'head':
                            dmg = int(round(dmg * C.CRIT_MULT))
                            self.crit_fx(e.spine.joints[0])
                        e.take_hit(self, safe_norm(pr.vel), dmg)
                        if pr.effect == 'poison':
                            e.apply_poison(3.0, 3.0)
                        elif pr.effect == 'slow':
                            e.apply_slow(0.5, 1.6)
                        for fn in pr.on_hit:
                            fn(pr, e, self)
                        if pr.pierce:           # pass through, remember this enemy
                            if pr._pierced is None:
                                pr._pierced = set()
                            pr._pierced.add(e)
                        else:
                            pr.dead = True
                            break
                if not pr.dead:                     # player shots also chip nests
                    for n in self.rounds.nests:
                        if not n.dead and n.pos.distance_to(pr.pos) < n.max_r + pr.radius:
                            n.take_hit(self, pr.dmg)
                            for fn in pr.on_hit:
                                fn(pr, n, self)
                            pr.dead = True
                            break
        # on_death fires in one sweep, because a shot can die on four different
        # paths above (expiry, out of bounds, hitting a player, hitting a nest)
        # and doing it at each `pr.dead = True` means a new death path can
        # silently skip it. The dead are dropped right after, so it fires once.
        for pr in self.projectiles:
            if pr.dead:
                for fn in pr.on_death:
                    fn(pr, self)
        self.projectiles = [p for p in self.projectiles if not p.dead]

    # ---- eating / growth ------------------------------------------------ #
    def eat(self, player, target):
        target.dead = True
        audio.play('eat', 0.7)
        color = getattr(target, 'color', C.COL_BUG)
        self.fx.burst(target.pos, color, 16, 220)
        self.fx.spark_burst(target.pos, color, 10, 300)
        self.fx.ring(target.pos, color)
        kind = getattr(target, 'kind', 'bug')
        if kind == 'bug':
            player.energy = clamp(player.energy + 8, 0, player.max_energy)
            player.food += 1
            self.add_score(5)
            self.fx.popup(target.pos, "+5")
        elif kind == 'fruit':
            player.energy = clamp(player.energy + 22, 0, player.max_energy)
            player.health = min(player.max_health, player.health + 12)
            player.food += 1
            self.add_score(10)
            self.fx.popup(target.pos, "+cura", (120, 240, 120))
        elif kind == 'egg':
            f = AILizard(target.pos, 'friend', 0.9, C.COL_FRIEND)
            f.hp = C.FRIEND_HP
            f.sync_max_hp()
            f.life = C.FRIEND_LIFE
            self.friends.append(f)
            self.add_score(20)
            self.fx.popup(target.pos, "AMIGO!", C.COL_FRIEND)
        elif kind == 'prey':
            player.energy = clamp(player.energy + 30, 0, player.max_energy)
            player.food += 2
            sv = getattr(target, 'score_value', 25)
            self.add_score(sv)
            player.gain_xp(getattr(target, 'xp_value', 6), self)
            # eating a trait-carrier grants its body part (comer-para-evoluir)
            if getattr(target, 'grants', None):
                player.grant_part(target.grants, self)
            self.fx.popup(target.pos, f"+{sv}")
        if player.food and player.food % 4 == 0:
            self._grow(player)

    def _grow(self, player):
        sp = player.spine
        if len(sp.joints) < 22:
            sp.joints.append(Vector2(sp.joints[-1]))
            sp.radii = build_radii(len(sp.joints), player.max_r)
        self.fx.ring(player.pos, player.color)

    # ---- main step ------------------------------------------------------ #
    def step(self, dt):
        if self.state == 'camp':
            # camp owns its own clock and early returns (frozen while shopping)
            state_camp.update(self, dt)
            return
        if self.state != 'play':
            # the UI screens have their own clock so the entry animation runs on
            # the same fixed timestep as everything else (FPS-independent).
            # It is shared by levelup/pause/over/victory -- only levelup has any
            # per-state work of its own (the absorption).
            self.ui_t += dt
            self.ui_fx = decay(self.ui_fx, dt)
            _STATES[self.state].update(self, dt)
            self.fx.update(dt)
            return
        state_play.update(self, dt)

    def _bank_run(self, won=False):
        """Convert the finished run into permanent DNA (once)."""
        if self.run_banked:
            return
        self.run_banked = True
        self.won = won
        self.dna_gained = progression.finish_run(self.meta, self.score,
                                                 self.rounds.wave, self.kills, won=won)

    def _revive(self):
        for p in self.players:
            if p.down and not p.dead:
                for q in self.alive_players():
                    if not q.down and q.pos.distance_to(p.pos) < 70:
                        p.down = False
                        p.health = p.max_health * 0.5
                        p.hit_flash = 1.0
                        self.fx.burst(p.pos, C.COL_WHITE, 20, 220)
                        self.fx.popup(p.pos, "REVIVIDO!", C.COL_WHITE)

    def _collisions(self):
        for p in self.players:
            if p.dead or p.down:
                continue
            eat_r = p.max_r * 1.4
            head = p.spine.joints[0]
            for group in (self.pickups, self.prey):
                for e in group:
                    if e.dead:
                        continue
                    er = getattr(e, 'max_r', getattr(e, 'r', 6))
                    if head.distance_to(e.pos) < eat_r + er:
                        self.eat(p, e)
            for e in self.enemies:
                if e.dead:
                    continue
                # one hit per enemy per dash: _collisions runs every frame, so
                # without dash_hits a single 0.16s dash landed ~10 hits (30 dmg)
                if not p.dashing or e in p.dash_hits:
                    continue
                where = e.hit_test(p.pos, p.max_r)
                if where:
                    p.dash_hits.add(e)
                    grant = getattr(e, 'grants', None)
                    if p.venom:
                        e.apply_poison(2.5, 2.5)
                    dmg = p.dash_damage()
                    if where == 'head':                 # weak point
                        dmg *= C.CRIT_MULT
                        self.crit_fx(e.spine.joints[0])
                    e.take_hit(self, safe_norm(e.pos - p.pos), int(round(dmg)))
                    # Marked AFTER the dash's own hit: marking first meant the
                    # dash spent the crit it had just created, so the item did
                    # nothing the player could ever observe.
                    if p.dash_marks and not e.dead:
                        e.marked = True
                    if e.dead:
                        self.punch(0.07, 8)          # dash-kill: crunchy freeze
                        # stealing a body part is now a rare treat, not every kill
                        if grant and random.random() < 0.12:
                            p.grant_part(grant, self)
                        # Ricochete turns the chain into a full refresh
                        p.dash_cd = 0.0 if p.dash_chain_bonus else p.dash_cd * 0.35
                        p.energy = min(p.max_energy, p.energy + 6)
                    self.shake(6)
            # dashing through a nest damages it
            if p.dashing:
                for n in self.rounds.nests:
                    if n.dead or n in p.dash_hits:
                        continue
                    if p.pos.distance_to(n.pos) < p.max_r + n.max_r:
                        p.dash_hits.add(n)
                        # a nest is a big stationary target: a full body slam lands
                        n.take_hit(self, int(round(p.dash_damage() * 2)))
                        self.shake(5)

    # ---- draw ----------------------------------------------------------- #
    def draw(self, surf):
        self._draw_bg(surf)
        self.world.draw_decor(surf, self.cam)
        for pud in self.puddles:                    # acid pools sit on the ground
            if self.cam.visible(pud.pos, 60):
                pud.draw(surf, self.cam)
        self.rounds.draw_world(surf, self.cam)
        if self.state == 'camp' and self.camp:
            # tent + doors, in world space: part of the world pass, not the overlay
            state_camp._draw_camp_pois(self, surf)
        for group in (self.pickups, self.prey, self.friends, self.enemies, self.players):
            for e in group:
                if getattr(e, 'dead', False):
                    continue
                pos = e.spine.joints[0] if hasattr(e, 'spine') else e.pos
                if not self.cam.visible(pos):
                    continue
                r = getattr(e, 'max_r', getattr(e, 'r', 6))
                sp = self.cam.w2s(pos + Vector2(0, r * 0.7))
                shadow(surf, sp, r * 1.1 * self.cam.zoom)
        for pk in self.pickups:
            if not pk.dead and self.cam.visible(pk.pos):
                pk.draw(surf, self.cam)
        for group in (self.prey, self.friends, self.enemies):
            for e in group:
                if not e.dead and self.cam.visible(e.pos, 120):
                    e.draw(surf, self.cam)
        for p in self.players:
            if not p.dead:
                p.draw(surf, self.cam)
        for pr in self.projectiles:
            if self.cam.visible(pr.pos, 40):
                pr.draw(surf, self.cam)
        self.world.draw_ambient(surf, self.cam)
        self.fx.draw(surf, self.cam, self.font)
        if self.flash > 0:
            ui._tint(surf, (255, 255, 255), int(150 * min(1.0, self.flash)))
        # Issue #26: per-boss arena screen tint (atmosphere). After the flash so
        # a hit-flash still reads; before the vignette so the corners darken the
        # tint too, matching the existing mood-lighting layering.
        if self.arena is not None and self.arena.tint is not None:
            tint_col, tint_alpha = self.arena.tint
            ui._tint(surf, tint_col, tint_alpha)
        hud.vignette(surf)
        if self.state == 'play':
            # offscreen arrows: play's own bit of the world pass, under the HUD
            state_play.draw(self, surf)
        # The top-centre column is shared and elements reserve their band in draw
        # order, so draw order == priority. Persistent readouts (HUD, boss bar)
        # claim their spot first and never move; the theme banner is a 2.2s
        # announcement and goes last, so it can no longer shove the boss bar down
        # into the play area for the exact seconds the boss is spawning.
        # 'levelup'/'camp' own the whole screen and have their own headers; the
        # HUD behind them was pure clutter competing with the panels.
        self.top.reset()
        if self.state not in ('victory', 'over', 'levelup', 'camp'):
            state_play._draw_hud(self, surf)
            self.rounds.draw_boss_bar(surf, self.font, self.bigfont)
            self.rounds.draw_banner(surf, self.font, self.bigfont)
        else:
            self.rounds.draw_boss_bar(surf, self.font, self.bigfont)
        if self.state != 'play':
            _STATES[self.state].draw(self, surf)      # the state's own overlay

    def _draw_bg(self, surf):
        surf.fill(C.COL_BG)
        self.world.draw_ground(surf, self.cam)
        z = self.cam.zoom
        tl = self.cam.w2s((0, 0)); br = self.cam.w2s((C.WORLD_W, C.WORLD_H))
        pygame.draw.rect(surf, (58, 54, 96), (tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]),
                         max(2, int(6 * z)))

    # ---- UI screen compositing ------------------------------------------ #
    def _layer(self):
        """Scratch full-screen surface: the UI is drawn here, then blitted with the
        shake offset, so a `punch()` kicks the *whole screen* -- the world behind
        is frozen on these screens, so shaking the camera alone reads as nothing."""
        if self._uilayer is None:
            self._uilayer = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        self._uilayer.fill((0, 0, 0, 0))
        return self._uilayer

    def _ui_fx(self, layer):
        """Particles are drawn with the world, i.e. *under* the veil, which mutes
        them ~80%. Around a choice, redraw them on top of the panels so the trail
        and the impact burst actually read."""
        if self.pick or self.ui_fx > 0:
            self.fx.draw(layer, self.cam, self.font)

    def _ui_dest(self, surf):
        """Where the screen's content should be drawn.

        Compositing through the scratch layer costs a full-screen per-pixel-alpha
        blit (~4 ms), so only pay it while a shake is actually displacing the UI;
        the rest of the time draw straight to the screen.
        """
        if abs(self.cam.shake_off.x) < 0.5 and abs(self.cam.shake_off.y) < 0.5:
            return surf
        return self._layer()

    def _blit_ui(self, surf, layer):
        if layer is not surf:
            surf.blit(layer, (int(self.cam.shake_off.x), int(self.cam.shake_off.y)))

    @staticmethod
    def _blit_card(dst, src, center, scale=1.0, alpha=1.0):
        """Blit a pre-rendered panel centred, scaled and faded (used by the entry
        animation and by the absorption)."""
        if alpha <= 0.01:
            return
        w = max(1, int(src.get_width() * scale))
        h = max(1, int(src.get_height() * scale))
        im = src if (w, h) == src.get_size() else pygame.transform.smoothscale(src, (w, h))
        if alpha < 1.0:
            im = im.copy()
            im.set_alpha(int(255 * alpha))
        dst.blit(im, (int(center[0] - w / 2), int(center[1] - h / 2)))

    def _panel(self, key, build):
        """Panels are redrawn only when their state changes -- rebuilding three
        text-heavy cards every frame cost ~8 ms on the paused screens."""
        s = self._panels.get(key)
        if s is None:
            s = self._panels[key] = build()
        return s

    def _veil(self, surf, color, target_alpha):
        """Background dim that fades in first -- phase 1 of every screen."""
        # plain surface + set_alpha, NOT an SRCALPHA fill: the per-pixel-alpha
        # full-screen blit was costing ~8 ms a frame on these screens
        f = clamp(self.ui_t / C.UI_VEIL, 0, 1)
        ui._tint(surf, color, int(target_alpha * f))
        return f

    # ---- pause ---------------------------------------------------------- #
    PAUSE_ITEMS = ('CONTINUAR', 'OPCOES', 'CONTROLES', 'SAIR PARA O MENU')

    def toggle_pause(self):
        """ESC. Pausing is just another non-'play' state, so game.step already
        freezes the whole simulation for us -- the run is never destroyed."""
        if self.state == 'pause':
            self.state = self.pause_prev
            self.ui_t = 99.0            # returning: don't replay the entry animation
            return False
        if self.state not in ('play', 'camp', 'levelup') or self.pick:
            return False                # not during an absorption or a run-over screen
        self.pause_prev = self.state
        self.state = 'pause'
        self.pause_mode = 'menu'
        self.pause_sel = 0
        self.ui_t = 0.0
        audio.play('ui')
        return True

    def pause_items(self, joysticks=None):
        from . import menu as menulib
        if self.pause_mode == 'options':
            return menulib._items_for('options', None, 0, None)
        if self.pause_mode == 'controls':
            return ['VOLTAR']
        return list(self.PAUSE_ITEMS)

    def pause_move(self, d):
        n = len(self.pause_items())
        self.pause_sel = (self.pause_sel + d) % max(1, n)

    def pause_back(self):
        """B / ESC inside a sub-screen: step back one level instead of resuming."""
        if self.pause_mode != 'menu':
            self.pause_mode = 'menu'
            self.pause_sel = 0
            self.ui_t = 0.0
            return True
        return False

    def pause_activate(self, toggle_fs):
        """Returns 'resume', 'quit' or None. Options reuse the menu's own actions."""
        from . import menu as menulib
        items = self.pause_items()
        sel = min(self.pause_sel, len(items) - 1)
        if self.pause_mode == 'controls':
            self.pause_back()
            return None
        if self.pause_mode == 'options':
            # same handler the main menu uses -> identical behaviour + persistence
            r = menulib._activate('options', sel, toggle_fs, len(items))
            if r is not None:                 # 'VOLTAR'
                self.pause_back()
            return None
        audio.play('ui')
        if sel == 0:
            self.toggle_pause()
            return 'resume'
        if sel == 1:
            self.pause_mode = 'options'
        elif sel == 2:
            self.pause_mode = 'controls'
        else:
            return 'quit'
        self.pause_sel = 0
        self.ui_t = 0.0
        return None

    def _draw_pause(self, surf, joysticks=None):
        """app.py redraws the pause overlay after game.draw() so the controls
        screen can name the pads it can see -- draw() itself has no handle on
        them. Kept as a method because that call site is public surface."""
        state_pause.draw(self, surf, joysticks)
