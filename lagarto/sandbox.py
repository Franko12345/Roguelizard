"""Sandbox: dev-only debug overlay for spawning and testing entities live.

Isolated on purpose (ADR-0010: single-file-per-module). This one module owns the
sandbox controller and its mouse-driven, immediate-mode overlay; nothing in the
production UI knows it exists, and deleting this file plus the ``--sandbox`` branch
in ``app.main`` removes the feature whole.

Reached only via ``python lizard_game.py --sandbox`` -- a flag nobody passes on a
normal run. See ``plans/04_sandbox_debug.md`` for the full design. SB3 adds the
title feature: pick a category+target in the dropdown to *arm* a spawn, then
left-click in the world to drop it there (sticky -- each click drops another until
right-click / Esc cancels). SB4 hangs round control off the same spine. SB5 adds
the loadout tooling (plans/04 §9-10): the ``equip`` category grants any weapon /
item / charm / mutation FREE straight into the player via the real grant APIs, and
the ``store`` category stages the REAL camp shop -- a catalog of the five native
offers plus any weapon/item/charm wrapped as a shop entry -- with ``game.pollen``
set sky-high so the real ``camp_buy`` cost check never blocks. Nothing here
reimplements a grant or a buy; it only funnels into the existing paths. SB7 adds
the launch preset (plans/04 §12): the ``debug`` category's Save button serialises
the live scene to ``~/.lagarto/sandbox.json`` (character, toggles, hand-spawned
entities, loadout, active round, generated store) and Clear deletes it; at
``--sandbox`` launch a present preset is replayed through this same spawn/grant/
round/store path (``Sandbox.apply_preset``), else the sandbox opens idle.
"""

import json
import os
import random

import pygame
from pygame import Vector2

from .core import config as C
from .core import settings
from .core.mathutil import random_dir
from .creatures import champions
from .creatures import characters
from .combat import charms
from .render import display
from .combat import evolution
from .combat import items
from .creatures import species
from .render import ui
from .combat import weapons
from .world.pickups import Bug, Fruit, Egg
from .flow.rounds import BOSS_POOL, THEMES, THEME_KEYS, make_boss
from .game import state_camp


# Keys that toggle the panel open/closed. Backtick is the classic dev-console key;
# F1 is the fallback for keyboards where backtick is awkward.
TOGGLE_KEYS = (pygame.K_BACKQUOTE, pygame.K_F1)

# The spawn/round categories, in panel order: (key, short label). ``round`` is
# not a spawn -- picking it swaps the item list for the theme picker and reveals
# the round-control footer (SB4).
CATEGORIES = (('boss', 'Boss'), ('champion', 'Champ'),
              ('species', 'Spec'), ('pickup', 'Pick'), ('round', 'Rnd'),
              ('equip', 'Equip'), ('store', 'Loja'),
              ('debug', 'Dbg'), ('char', 'Pers'))
PICKUP_KEYS = ('bug', 'fruit', 'egg')
PICKUP_CTORS = {'bug': Bug, 'fruit': Fruit, 'egg': Egg}

# Debug staples (SB6, plans/04 §11): the two toggles + two one-shot actions the
# ``debug`` category lists as clickable rows. God/pause read live state so the
# label shows ON/OFF; kill-all and step fire once per click. ``char`` is its own
# category that lists CHARACTERS -- a click rebuilds the player as that one.
DEBUG_ACTIONS = ('god', 'killall', 'pauseai', 'step', 'save', 'clear')

# The loadout pools (SB5). ``equip`` grants any of the four free; ``store`` wraps
# the three purchasable kinds as shop entries (mutations are level-up cards, not
# shop stock, so the store leaves them out).
EQUIP_POOLS = (('weapon', 'Arma'), ('item', 'Item'),
               ('charm', 'Charm'), ('mutation', 'Mut'))
STORE_POOLS = (('weapon', 'Arma'), ('item', 'Item'), ('charm', 'Charm'))

# tier only scales a boss's hp/xp/score; the phase kit + name come from BOSS_POOL.
# A hand-spawned boss has no wave to derive a tier from, so pick a sane mid default.
SANDBOX_BOSS_TIER = 1

# Flat debug price on every wrapped store entry (plans/04 §9/§15: a fixed default
# is enough for v1). ``infinite_money`` sets pollen far above any price so the real
# ``camp_buy`` cost check (`pollen < cost`) can never block, even after _apply_buy
# marks the price up 1.6x per purchase.
SANDBOX_STORE_COST = 10
INFINITE_POLLEN = 10 ** 9


# ---- preset I/O (SB7, plans/04 §12) ------------------------------------- #
# The launch preset lives beside settings.json in ``~/.lagarto`` and is written
# through the same atomic tmp->rename primitive (``settings._atomic_write``), so
# there is one on-disk write pattern for the whole ``~/.lagarto`` folder. The file
# is authored only from the overlay's Save button and replayed at ``--sandbox``
# launch; a normal run never reads or writes it.
def preset_path():
    """``~/.lagarto/sandbox.json`` -- same dir handling as settings.py."""
    return os.path.join(settings._dir(), 'sandbox.json')


def preset_exists():
    return os.path.exists(preset_path())


def load_preset():
    """Return the parsed preset dict, or None when absent/unreadable/corrupt."""
    try:
        with open(preset_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def write_preset(data):
    try:
        settings._atomic_write(preset_path(), data)
        return True
    except Exception:
        return False


def clear_preset():
    """Delete the preset file; a missing file already counts as cleared."""
    try:
        os.remove(preset_path())
        return True
    except FileNotFoundError:
        return True
    except Exception:
        return False


class Sandbox:
    """Per-frame debug overlay driven from ``app.main``'s sandbox branch.

    ``handle_event`` consumes the toggle key, panel clicks, and -- while a spawn is
    armed -- world clicks that place the entity, so none of those reach the live
    game. ``draw`` paints the panel on top when open plus a HUD line naming the
    armed spawn. The game keeps simulating underneath either way.
    """

    def __init__(self, game, font, bigfont=None):
        self.game = game
        self.font = font
        self.bigfont = bigfont or font
        self.open = False
        # Registry of hand-spawned things. The preset (SB later) walks this to
        # serialise the live scene. Every entity spawned by the sandbox is also
        # tagged ``_sb=(kind, key)`` so a scan of the game's lists can recover the
        # same tuples independently of this list.
        self.spawned = []
        # Panel geometry: a left-docked column, sized once.
        self.rect = pygame.Rect(16, 16, 300, C.HEIGHT - 32)
        # Dropdown state: which category is showing, the half-picked champion (the
        # champion category needs a champ *and* a species), and the armed spawn.
        self.cat = 'boss'
        self.champ_sel = None            # champ_id awaiting a species to pair with
        self.armed = None                # (kind, key) once a target is chosen
        # Round control (SB4): the theme + wave a manual start_round will fire.
        self.round_theme = THEME_KEYS[0]
        self.round_wave = 1
        # Loadout (SB5): which loadout pool the equip/store list is showing, the
        # set of (pool, id) staged for a "generate specific" store, the random-N
        # size, and whether infinite money is on (set once a store is generated).
        self.pool = 'weapon'
        self.store_pick = set()          # {(pool, id)} chosen for a specific store
        self.store_n = 5                 # size of a random-N store roll
        self.store_entries = []          # (pool, id) of the last generated store,
        # kept as the serialisable record the preset replays (the wrapped dicts
        # carry lambdas, so we remember the sources, not the entries)
        self.infinite_money = False
        self.msg = None                  # transient confirmation line
        self.msg_t = 0                   # frames left to show it (drawn frame-clock)
        # Scroll offset per list (issue #175). Each category keeps its own
        # viewport, so jumping Boss -> Spec does not lose the species scroll
        # position. ``champion2`` covers the second step of the champion flow
        # (species pick after the champ is chosen) -- otherwise the first
        # click would clobber the second step's offset.
        self.scroll = {key: 0 for key, _ in CATEGORIES}
        self.scroll['champion2'] = 0

    # ---- registry ------------------------------------------------------- #
    def track(self, entity, kind, key):
        """Tag ``entity`` as sandbox-spawned and remember it. Base for the preset."""
        entity._sb = (kind, key)
        self.spawned.append(entity)
        return entity

    # ---- spawn ---------------------------------------------------------- #
    def spawn(self, kind, key, pos):
        """Resolve one ``(kind, key, pos)`` tuple to the real factory and place it.

        The single spawn path (plans/04 §3): the menu, world clicks, and the preset
        all funnel through here so there is never a divergent second way to spawn.
        ``pos=None`` drops it near the player. Returns the tracked entity.

            ('boss',     '<boss_id>',              pos)
            ('champion', '<champ_id>:<species>',   pos)
            ('species',  '<species_key>',          pos)
            ('pickup',   'bug'|'fruit'|'egg',      pos)
        """
        g = self.game
        if pos is None:
            p = g.players[0] if g.players else None
            base = p.pos if p else Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
            pos = base + random_dir(random.uniform(120, 200))
        else:
            pos = Vector2(pos)

        if kind == 'boss':
            ent = make_boss(g, key, SANDBOX_BOSS_TIER, pos)
            g.enemies.append(ent)
            # Mirror onto rounds.boss, exactly as RoundManager._spawn_boss does.
            # Without this a hand-spawned boss has NO health bar at all: the big
            # top bar reads rounds.boss, and the small over-head bar refuses to
            # draw for anything with is_boss set (it assumes the big one is up).
            # ``_kill_all`` and the scene clear already reset this, and
            # ``start_round`` nulls it, so nothing leaks.
            g.rounds.boss = ent
        elif kind == 'champion':
            champ_id, species_key = key.split(':')
            ent = species.make(species_key, pos)
            champions.promote_to(ent, champ_id, g)
            g.enemies.append(ent)
        elif kind == 'species':
            ent = species.make(key, pos)
            role = species.SPECIES[key]['role']
            (g.prey if role == 'prey' else g.enemies).append(ent)
        elif kind == 'pickup':
            ent = PICKUP_CTORS[key](pos)
            g.pickups.append(ent)
        else:
            raise ValueError(f"unknown spawn kind: {kind!r}")
        return self.track(ent, kind, key)

    # ---- dropdown model ------------------------------------------------- #
    def _items(self):
        """(value, label) rows for the current category (and champion step)."""
        if self.cat == 'boss':
            return [(k, BOSS_POOL[k]['name']) for k in BOSS_POOL]
        if self.cat == 'pickup':
            return [(k, k.upper()) for k in PICKUP_KEYS]
        if self.cat == 'species':
            return [(k, species.info(k)[0]) for k in species.SPECIES]
        if self.cat == 'round':
            return [(k, THEMES[k]['banner']) for k in THEME_KEYS]
        if self.cat == 'equip':
            return self._pool_items(self.pool)
        if self.cat == 'store':
            # price rides in the label so it is visible in the picker itself
            return [(pid, f"{name}  {SANDBOX_STORE_COST}p")
                    for pid, name in self._pool_items(self.pool)]
        if self.cat == 'debug':
            return self._debug_items()
        if self.cat == 'char':
            return [(c.id, c.name) for c in characters.CHARACTERS]
        # champion: pick the champ first, then a species to apply it to
        if self.champ_sel is None:
            return [(cid, champions.BY_ID[cid].name) for cid in champions.BY_ID]
        return [(k, species.info(k)[0]) for k in species.SPECIES]

    # ---- loadout pools (SB5) -------------------------------------------- #
    def _pool_items(self, pool):
        """(id, name) rows for one loadout pool, straight off the real registry."""
        if pool == 'weapon':
            return [(wid, weapons.WEAPONS[wid].name) for wid in weapons.WEAPONS]
        if pool == 'item':
            return [(it.id, it.name) for it in items.ITEMS]
        if pool == 'charm':
            return [(c.id, c.name) for c in charms.CHARMS]
        if pool == 'mutation':
            return [(m.id, m.name) for m in evolution.MUTATIONS]
        return []

    def _flash(self, msg):
        """Show a one-line confirmation for a short while (frame-clocked in draw)."""
        self.msg = msg
        self.msg_t = 90

    def _equip(self, pool, pid):
        """Grant one loadout entry FREE to the player via the existing grant APIs.

        No grant is reimplemented (plans/04 §10): weapons/charms go through the
        player's own ``gain_*``; items through ``items.give``; mutations apply
        their own effect. The player at index 0 is the sandbox's test subject.
        """
        g = self.game
        p = g.players[0] if g.players else None
        if p is None:
            return
        if pool == 'weapon':
            p.gain_weapon(pid)
        elif pool == 'item':
            items.give(p, items.ITEMS.get(pid), g)
        elif pool == 'charm':
            p.gain_charm(pid, g)
        elif pool == 'mutation':
            evolution.MUTATIONS[pid].apply(p, g)
        self._flash(f"equip: {pid}")

    # ---- debug staples (SB6) -------------------------------------------- #
    def _debug_items(self):
        """(action, label) rows for the debug category; toggles show live state."""
        g = self.game
        got = 'sim' if preset_exists() else 'nao'
        return [('god', f"God mode: {'ON' if g.god_mode else 'OFF'}"),
                ('killall', 'Kill-all (hostis)'),
                ('pauseai', f"Pause-AI: {'ON' if g.pause_ai else 'OFF'}"),
                ('step', 'Step +1 tick'),
                ('save', 'Save preset'),
                ('clear', f'Clear preset ({got})')]

    def _debug_action(self, action):
        """Dispatch a click on a debug row (plans/04 §11)."""
        g = self.game
        if action == 'god':
            g.god_mode = not g.god_mode
            self._flash(f"god mode: {'ON' if g.god_mode else 'OFF'}")
        elif action == 'killall':
            self._kill_all()
        elif action == 'pauseai':
            g.pause_ai = not g.pause_ai
            self._flash(f"pause-AI: {'ON' if g.pause_ai else 'OFF'}")
        elif action == 'step':
            self._step()
        elif action == 'save':
            self.save_preset()
        elif action == 'clear':
            self.clear_preset()

    def _step(self):
        """Advance the frozen AI exactly one fixed tick (``C.DT``).

        Sets the one-shot the game's ``step`` consumes on its next tick, which
        lifts the pause for that tick only -- so the enemy/boss procedural
        animation folheia one frame at a time (the key inspection feature). Turns
        pause-AI on first, since stepping a running sim is meaningless.
        """
        g = self.game
        g.pause_ai = True
        g.step_once = True
        self._flash("step +1 tick")

    def _kill_all(self):
        """Clear enemies + boss + hostile projectiles/puddles + nests; keep prey,
        pickups, friends and the player (plans/04 §11).

        The boss lives in ``enemies`` *and* is mirrored on ``rounds.boss``, so both
        are cleared. Nests are enemy spawners -- left alone they would refill the
        field, so a "kill all hostiles" that spares them would read as broken.
        """
        g = self.game
        g.enemies = []
        g.pending_enemies = []
        g.projectiles = [p for p in g.projectiles if not p.hostile]
        g.puddles = [p for p in g.puddles if not getattr(p, 'hostile', False)]
        rm = g.rounds
        rm.boss = None
        rm.nests = []
        rm.marks = []
        # drop the hand-spawned hostiles from the registry, keep tracked survivors
        survivors = {id(x) for x in (g.prey + g.pickups + g.friends)}
        self.spawned = [e for e in self.spawned if id(e) in survivors]
        self._flash("kill-all: hostis limpos")

    def _swap_character(self, cid):
        """Rebuild player 0 as a different Character -- own body + initial weapon.

        Builds a fresh Player exactly as ``Game.__init__`` does (same slot,
        controller and colourset, at the current position), so ``Player.__init__``
        grants the character's starting weapon (``gain_weapon(char.weapon)``) and
        runs ``char.apply`` -- the new silhouette comes from its genome. Meta
        progression is re-applied to match the real build path.
        """
        from .creatures.player import Player
        from .flow import progression
        g = self.game
        if not g.players:
            return
        old = g.players[0]
        new = Player(Vector2(old.pos), old.ctrl, old.colorset, old.index,
                     character=characters.get(cid))
        progression.apply_to_player(g.meta, new)
        g.players[0] = new
        self._flash(f"swap: {characters.get(cid).name}")

    # ---- store (SB5) ---------------------------------------------------- #
    def _wrap_entry(self, pool, pid):
        """Wrap a weapon/item/charm as a camp shop entry dict (plans/04 §9).

        Shape matches ``state_camp._roll_shop``'s native offers: ``fn(game)`` runs
        the REAL grant on every player, so ``_apply_buy`` calls it unchanged.
        """
        if pool == 'weapon':
            w = weapons.WEAPONS[pid]
            return dict(name=w.name, desc='arma (debug)', cost=SANDBOX_STORE_COST,
                        hue=w.hue, icon=pid,
                        fn=lambda g, pid=pid: [pl.gain_weapon(pid) for pl in g.players])
        if pool == 'item':
            it = items.ITEMS.get(pid)
            return dict(name=it.name, desc=it.desc, cost=SANDBOX_STORE_COST,
                        hue=it.hue, icon=it.icon,
                        fn=lambda g, it=it: [items.give(pl, it, g) for pl in g.players])
        c = charms.CHARMS.get(pid)          # pool == 'charm'
        return dict(name=c.name, desc=c.desc, cost=SANDBOX_STORE_COST,
                    hue=c.hue, icon=pid,
                    fn=lambda g, pid=pid: [pl.gain_charm(pid, g) for pl in g.players])

    def _random_sources(self, n):
        """N random ``(pool, id)`` sources drawn across the three purchasable pools."""
        allpool = [(pool, pid) for pool, _ in STORE_POOLS
                   for pid, _ in self._pool_items(pool)]
        return random.sample(allpool, min(n, len(allpool)))

    def _generate_store(self, sources):
        """Stage the REAL camp shop from ``(pool, id)`` sources; infinite money on.

        Catalog = the five native ``state_camp._roll_shop`` offers + our wrapped
        entries. ``_roll_shop`` is a module function taking the game, not a
        ``Game`` method -- calling it as ``g._roll_shop()`` raises AttributeError.
        We reuse ``_enter_camp`` (it builds every camp field the shop UI needs),
        then override the shop list, open it in ``shop`` mode, and set pollen far
        above any price. From there the untouched camp path (app.main -> camp_buy
        -> _apply_buy) does the buying; nothing about the flow is special-cased.

        The ``(pool, id)`` sources are remembered on ``store_entries`` so the SB7
        preset can serialise and replay the store through this same path.
        """
        g = self.game
        sources = list(sources)
        self.store_entries = sources
        entries = [self._wrap_entry(pool, pid) for pool, pid in sources]
        catalog = state_camp._roll_shop(g) + entries
        g._enter_camp()
        g.camp['shop'] = catalog
        g.camp['shop_sel'] = 0
        g.camp['focus'] = 'shop'
        g.camp['mode'] = 'shop'
        g.pollen = INFINITE_POLLEN
        self.infinite_money = True
        self.open = False               # hide the panel so the shop is clickable
        self._flash(f"loja: {len(catalog)} itens - polen infinito")

    def _armed_label(self):
        """Human name of the armed spawn, for the HUD; None when nothing is armed."""
        if not self.armed:
            return None
        kind, key = self.armed
        if kind == 'boss':
            return f"BOSS {BOSS_POOL[key]['name']}"
        if kind == 'champion':
            champ_id, species_key = key.split(':')
            return f"{champions.BY_ID[champ_id].name} {species.info(species_key)[0]}"
        if kind == 'species':
            return species.info(key)[0]
        return key.upper()               # pickup

    def _select_cat(self, key):
        self.cat = key
        self.champ_sel = None
        # the store has no mutation stock, so bounce the pool back if we came from
        # equip with mutations showing
        if key == 'store' and self.pool == 'mutation':
            self.pool = 'weapon'
        # Reset the new category's scroll so a long list (e.g. 25 species) does
        # not open partway down when you switch to it from a short one.
        self.scroll[key] = 0

    def _select_item(self, value):
        if self.cat == 'boss':
            self.armed = ('boss', value)
        elif self.cat == 'species':
            self.armed = ('species', value)
        elif self.cat == 'pickup':
            self.armed = ('pickup', value)
        elif self.cat == 'round':
            self.round_theme = value         # pick the theme; START fires it
        elif self.cat == 'equip':
            self._equip(self.pool, value)    # click grants it free, right away
        elif self.cat == 'store':
            tup = (self.pool, value)         # toggle it in the specific-store set
            self.store_pick.discard(tup) if tup in self.store_pick \
                else self.store_pick.add(tup)
        elif self.cat == 'debug':
            self._debug_action(value)        # toggle / fire the debug staple
        elif self.cat == 'char':
            self._swap_character(value)      # rebuild the player as this character
        elif self.cat == 'champion':
            if self.champ_sel is None:
                self.champ_sel = value           # first click picks the champion
            else:
                self.armed = ('champion', f'{self.champ_sel}:{value}')
                self.champ_sel = None

    # ---- round control (SB4) -------------------------------------------- #
    def _round_layout(self):
        """Footer rects for the round controls; only live while ``cat == 'round'``.
        Computed the same for draw + hit-test so clicks never depend on a draw."""
        r = self.rect
        x, w, bh = r.x + 14, r.width - 28, 28
        reset_r = pygame.Rect(x, r.bottom - 14 - bh, w, bh)
        start_r = pygame.Rect(x, reset_r.y - 8 - bh, w, bh)
        wy = start_r.y - 12 - bh
        dec_r = pygame.Rect(x, wy, 34, bh)
        inc_r = pygame.Rect(x + w - 34, wy, 34, bh)
        wave_r = pygame.Rect(dec_r.right + 4, wy, inc_r.left - dec_r.right - 8, bh)
        return dict(dec=dec_r, inc=inc_r, wave=wave_r, start=start_r, reset=reset_r)

    def _start_round(self):
        """Fire the chosen theme+wave through the REAL wave machine.

        ``start_round`` does ``wave += 1`` and rolls a boss on ``wave % 5 == 0``,
        so setting ``wave = round_wave - 1`` first lands it exactly on the picked
        wave with the right budget/tier. Called directly (not via the frozen
        ``RoundManager.update`` sandbox path) so the manual start still runs.
        """
        rm = self.game.rounds
        rm.wave = self.round_wave - 1
        rm.start_round(self.round_theme)

    def _reset_round(self):
        """Clear the scene and zero the RoundManager -- but never touch the player.

        Empties the entity lists + the round's nests/marks/boss and returns the
        machine to a fresh intermission (plans/04 §8). The player's position, hp,
        loadout, and level are the test subject, so they are left alone.
        """
        g = self.game
        g.enemies = []
        g.pending_enemies = []       # drains into enemies each step -- clear too
        g.prey = []
        g.projectiles = []
        g.pickups = []
        g.friends = []
        g.puddles = []               # leftover ground hazards are scene, not subject
        rm = g.rounds
        rm.boss = None
        rm.nests = []
        rm.marks = []
        rm.wave = 0
        rm.state = 'intermission'
        rm.is_boss_round = False
        rm.is_final = False
        rm.budget = 0
        g.wave = 0                   # HUD mirror of rm.wave (start_round re-syncs it)
        self.spawned = []            # the hand-spawned registry is gone with the scene
        self.armed = None
        self.champ_sel = None

    # ---- preset (SB7, plans/04 §12) ------------------------------------- #
    def _serialize(self):
        """Snapshot the live scene as the JSON-able preset (plans/04 §12).

        Records only what the overlay can author: the player's character, the
        three toggles, every hand-spawned entity as ``(kind, key, pos)`` off
        ``self.spawned``, the player loadout (weapons+levels / items / charms),
        the active round descriptor ``(theme, wave)``, and the generated store as
        its ``(pool, id)`` sources. Round mobs are NOT serialised individually --
        only the descriptor, so replay re-runs ``start_round``.
        """
        g = self.game
        p = g.players[0] if g.players else None
        entities = []
        for e in self.spawned:
            tag = getattr(e, '_sb', None)
            if not tag:
                continue
            kind, key = tag
            entities.append([kind, key, [round(e.pos.x, 2), round(e.pos.y, 2)]])
        loadout = {}
        if p is not None:
            loadout = {'weapons': {wid: lvl for wid, lvl in p.weapons.items()},
                       'items': list(p.items),
                       'charms': list(p.charms_owned)}
        rm = g.rounds
        rnd = [rm.theme, rm.wave] if rm.wave > 0 else None
        return {'character': p.character_id if p else None,
                'toggles': {'god_mode': g.god_mode, 'pause_ai': g.pause_ai,
                            'infinite_money': self.infinite_money},
                'entities': entities,
                'loadout': loadout,
                'round': rnd,
                'store': [[pool, pid] for pool, pid in self.store_entries]}

    def save_preset(self):
        """Serialise the live scene and write it atomically to the preset file."""
        ok = write_preset(self._serialize())
        self._flash("preset salvo" if ok else "falha ao salvar preset")

    def clear_preset(self):
        """Delete the preset file so the next --sandbox launch opens idle."""
        clear_preset()
        self._flash("preset apagado")

    def apply_preset(self, data):
        """Rebuild a saved scene through the SAME spawn()/grant/round/store paths.

        Called once at ``--sandbox`` launch when a preset exists (plans/04 §12).
        Zero divergent reconstruction: character via ``_swap_character``, loadout
        via the player's ``gain_*``/``items.give``, entities via ``spawn``, round
        via ``_start_round`` (re-runs the wave machine), store via
        ``_generate_store``. Toggles are applied last.
        """
        if not isinstance(data, dict):
            return
        g = self.game

        def _try(what, fn):
            # A preset is dev-authored and may outlive the ids it names (a
            # weapon/species/character removed after the save). Skip a stale
            # entry with a warning instead of crashing the whole --sandbox
            # launch — the preset is a convenience, not a contract.
            try:
                fn()
            except Exception as exc:                    # noqa: BLE001
                print(f'[sandbox] preset: skipped {what}: {exc}')

        cid = data.get('character')
        if cid:
            _try(f'character {cid!r}', lambda: self._swap_character(cid))
        p = g.players[0] if g.players else None
        load = data.get('loadout') or {}
        if p is not None:
            weps = load.get('weapons') or {}
            for wid in weps:
                if wid not in weapons.WEAPONS:   # gain_weapon half-mutates then
                    print(f'[sandbox] preset: skipped weapon {wid!r}: unknown')
                    continue                     # crashes later at draw — reject up front
                def _wep(wid=wid):
                    p.gain_weapon(wid)
                    for _ in range(int(weps[wid]) - 1):   # replay the earned levels
                        p.level_weapon(wid)
                _try(f'weapon {wid!r}', _wep)
            for iid in load.get('items') or []:
                _try(f'item {iid!r}', lambda iid=iid: items.give(p, items.ITEMS.get(iid), g))
            for ch in load.get('charms') or []:
                if ch not in charms.CHARMS:
                    print(f'[sandbox] preset: skipped charm {ch!r}: unknown')
                    continue
                _try(f'charm {ch!r}', lambda ch=ch: p.gain_charm(ch, g))
        for ent in data.get('entities') or []:
            _try(f'entity {ent!r}', lambda ent=ent: self.spawn(ent[0], ent[1], ent[2]))
        rnd = data.get('round')
        if rnd:
            self.round_theme, self.round_wave = rnd[0], int(rnd[1])
            _try(f'round {rnd!r}', self._start_round)
        store = data.get('store') or []
        if store:
            _try('store', lambda: self._generate_store([(pool, pid) for pool, pid in store]))
        tg = data.get('toggles') or {}
        g.god_mode = bool(tg.get('god_mode', False))
        g.pause_ai = bool(tg.get('pause_ai', False))
        if tg.get('infinite_money'):
            g.pollen = INFINITE_POLLEN
            self.infinite_money = True

    # ---- store control (SB5) -------------------------------------------- #
    def _store_layout(self):
        """Footer rects for the store controls; only live while ``cat == 'store'``.
        Bottom-anchored like the round footer, so a long item list never collides."""
        r = self.rect
        x, w, bh = r.x + 14, r.width - 28, 28
        clear_r = pygame.Rect(x, r.bottom - 14 - bh, w, bh)
        rand_r = pygame.Rect(x, clear_r.y - 8 - bh, w, bh)
        spec_r = pygame.Rect(x, rand_r.y - 8 - bh, w, bh)
        ny = spec_r.y - 12 - bh
        dec_r = pygame.Rect(x, ny, 34, bh)
        inc_r = pygame.Rect(x + w - 34, ny, 34, bh)
        n_r = pygame.Rect(dec_r.right + 4, ny, inc_r.left - dec_r.right - 8, bh)
        return dict(dec=dec_r, inc=inc_r, n=n_r, spec=spec_r, rand=rand_r,
                    clear=clear_r)

    # ---- layout (shared by draw + hit-test) ----------------------------- #
    def _scroll_key(self):
        """Map the current panel state to its scroll slot.

        The champion category is two-step (champion then species), so the
        second step needs its own slot — the first step's ``scroll`` is held
        while the user picks a champion, then ``champion2`` carries the
        species list scroll. Mixing them would lose the species offset every
        time the user backed out to a different champion.
        """
        if self.cat == 'champion' and self.champ_sel is not None:
            return 'champion2'
        return self.cat

    def _layout(self):
        """Return (cat_rects, pool_rects, item_rects); computed the same way for
        draw + clicks so hit-testing never depends on a draw having run first.

        Categories wrap onto as many rows as the panel width needs (seven of them
        now). ``pool_rects`` is the loadout pool sub-row, live only for equip/store;
        equip/store items lay out in two columns so the longer pools still fit.

        Long lists are clipped to the visible window (issue #175): the sandbox's
        item rects used to draw every row of the registry, so the bottom of the
        panel overflowed. We now compute how many rows fit between the list
        origin and the nearest footer (round / store) or the panel bottom, take
        that slice of ``self._items()`` offset by ``self.scroll[cat]``, and clamp
        the scroll so a partial last page cannot over-scroll.
        """
        r = self.rect
        bw, bh = 52, 28
        x0, by = r.x + 14, r.y + 80
        per_row = max(1, (r.width - 28 + 2) // (bw + 2))
        cat_rects = []
        for i, (key, lbl) in enumerate(CATEGORIES):
            col, row = i % per_row, i // per_row
            rect = pygame.Rect(x0 + col * (bw + 2), by + row * (bh + 4), bw, bh)
            cat_rects.append((rect, key, lbl))
        iy = cat_rects[-1][0].bottom + 30    # leave a line for the breadcrumb/hint

        pool_rects = []
        if self.cat in ('equip', 'store'):
            pools = EQUIP_POOLS if self.cat == 'equip' else STORE_POOLS
            pw = (r.width - 28 - (len(pools) - 1) * 2) // len(pools)
            pool_rects = [(pygame.Rect(x0 + i * (pw + 2), iy, pw, 24), pk, pl)
                          for i, (pk, pl) in enumerate(pools)]
            iy += 24 + 8

        # visible area for the item list. round/store hang a footer off the
        # bottom of the panel, so the list must stop above it. Everything else
        # fills the panel down to the bottom edge.
        if self.cat == 'round':
            list_bottom = self._round_layout()['reset'].y - 8
        elif self.cat == 'store':
            list_bottom = self._store_layout()['clear'].y - 8
        else:
            list_bottom = r.bottom - 8
        list_h = max(0, list_bottom - iy - 4)

        rows = self._items()
        sk = self._scroll_key()
        if self.cat in ('equip', 'store'):   # two columns for the longer pools
            cols = 2
            row_h = 24
            per_col = max(1, list_h // row_h)
            per_page = per_col * cols
            cw = (r.width - 28 - (cols - 1) * 4) // cols
            max_scroll = max(0, len(rows) - per_page)
            self.scroll[sk] = max(0, min(self.scroll.get(sk, 0), max_scroll))
            s = self.scroll[sk]
            item_rects = []
            for vi, i in enumerate(range(s, min(len(rows), s + per_page))):
                col, row = vi % cols, vi // cols
                item_rects.append((pygame.Rect(x0 + col * (cw + 4), iy + row * row_h,
                                                cw, 22), rows[i][0], rows[i][1]))
        else:
            row_h = 26
            per_page = max(1, list_h // row_h)
            max_scroll = max(0, len(rows) - per_page)
            self.scroll[sk] = max(0, min(self.scroll.get(sk, 0), max_scroll))
            s = self.scroll[sk]
            item_rects = []
            for vi, i in enumerate(range(s, min(len(rows), s + per_page))):
                item_rects.append((pygame.Rect(x0, iy + vi * row_h, r.width - 28, 24),
                                   rows[i][0], rows[i][1]))
        return cat_rects, pool_rects, item_rects

    # ---- input ---------------------------------------------------------- #
    def handle_event(self, ev):
        """Return True if the event was consumed by the overlay (so app.main skips it)."""
        if ev.type == pygame.KEYDOWN:
            if ev.key in TOGGLE_KEYS:
                self.open = not self.open
                return True
            # '.' steps one tick regardless of the panel being open -- the
            # frame-by-frame animation tool wants a hotkey, not a menu round-trip.
            # Consumed so it never reaches the live game (sandbox-only anyway).
            if ev.key == pygame.K_PERIOD:
                self._step()
                return True
            # Esc cancels an armed spawn (sticky mode); only then, so a bare Esc
            # still reaches app.main's pause toggle when nothing is armed.
            if ev.key == pygame.K_ESCAPE and self.armed is not None:
                self.armed = None
                return True
            return False

        if ev.type == pygame.MOUSEBUTTONDOWN:
            mp = display.to_logical(ev.pos)
            # Panel clicks (only while open) never fall through to the world.
            if self.open and self.rect.collidepoint(mp):
                if ev.button == 1:
                    self._click_panel(mp)
                return True
            # Right-click anywhere in the world cancels an armed spawn.
            if ev.button == 3:
                if self.armed is not None:
                    self.armed = None
                    return True
                return False
            # Left-click in the world drops the armed entity there; stays armed
            # (sticky). Unarmed clicks fall through so the player controls normally.
            if ev.button == 1 and self.armed is not None:
                kind, key = self.armed
                self.spawn(kind, key, self.game.cam.s2w(mp))
                return True

        if ev.type == pygame.MOUSEWHEEL:
            # Mouse wheel over the open panel scrolls the active list. Consumed
            # so the live game never sees it (sandbox-only -- the world does
            # not use the wheel today, but if it ever did, the panel should
            # still win when the cursor is over it).
            if not self.open:
                return False
            mp = display.mouse_logical()
            if not self.rect.collidepoint(mp):
                return False
            sk = self._scroll_key()
            # ev.y is +1 for one notch up (toward the top of the list) and -1
            # for one notch down, in pygame-ce. Use a small step so a single
            # notch moves a couple of rows; the visible window is ~15-20 rows.
            self.scroll[sk] = self.scroll.get(sk, 0) + ev.y
            return True
        return False

    def _click_panel(self, mp):
        cat_rects, pool_rects, item_rects = self._layout()
        for rect, key, _ in cat_rects:
            if rect.collidepoint(mp):
                self._select_cat(key)
                return
        for rect, pk, _ in pool_rects:       # loadout pool sub-row (equip/store)
            if rect.collidepoint(mp):
                self.pool = pk
                # the pool drives the item list (weapon/item/charm/mutation
                # have very different sizes), so reset the scroll rather than
                # carrying an offset from the previous pool
                self.scroll[self.cat] = 0
                return
        if self.cat == 'round':
            rl = self._round_layout()
            if rl['dec'].collidepoint(mp):
                self.round_wave = max(1, self.round_wave - 1)
                return
            if rl['inc'].collidepoint(mp):
                self.round_wave += 1
                return
            if rl['start'].collidepoint(mp):
                self._start_round()
                return
            if rl['reset'].collidepoint(mp):
                self._reset_round()
                return
        if self.cat == 'store':
            sl = self._store_layout()
            if sl['dec'].collidepoint(mp):
                self.store_n = max(1, self.store_n - 1)
                return
            if sl['inc'].collidepoint(mp):
                self.store_n += 1
                return
            if sl['spec'].collidepoint(mp):
                self._generate_store(sorted(self.store_pick))
                return
            if sl['rand'].collidepoint(mp):
                self._generate_store(self._random_sources(self.store_n))
                return
            if sl['clear'].collidepoint(mp):
                self.store_pick.clear()
                return
        for rect, value, _ in item_rects:
            if rect.collidepoint(mp):
                self._select_item(value)
                return

    # ---- draw ----------------------------------------------------------- #
    def draw(self, surf):
        # HUD: the armed spawn's name, shown whether the panel is open or closed so
        # the sticky mode stays legible while you click around the world.
        label = self._armed_label()
        if label:
            ui.text(surf, self.font, f"[armado] {label}  -  dir/Esc cancela",
                    (C.WIDTH // 2, C.HEIGHT - 30), (255, 214, 110), align='center')
        # transient loadout confirmation (equip / store), frame-clocked here
        if self.msg_t > 0:
            self.msg_t -= 1
            ui.text(surf, self.font, self.msg, (C.WIDTH // 2, 8),
                    (150, 240, 170), align='center')
        if not self.open:
            ui.text(surf, self.font, "` sandbox", (C.WIDTH - 12, 8), ui.DIM,
                    align='right')
            return

        r = self.rect
        ui.panel(surf, r, alpha=205, accent=ui.LINE)
        ui.text(surf, self.bigfont, "SANDBOX", (r.x + 16, r.y + 14), ui.TEXT)
        ui.text(surf, self.font, "` / F1 fecha", (r.x + 16, r.y + 52), ui.DIM)

        cat_rects, pool_rects, item_rects = self._layout()
        for rect, key, lbl in cat_rects:
            cur = (key == self.cat)
            pygame.draw.rect(surf, (40, 46, 70) if cur else (22, 24, 38), rect,
                             border_radius=8)
            pygame.draw.rect(surf, (120, 150, 220) if cur else ui.LINE, rect, 2,
                             border_radius=8)
            ui.text(surf, self.font, ui.fit(self.font, lbl, rect.width - 6),
                    (rect.centerx, rect.y + 4),
                    ui.TEXT if cur else ui.DIM, align='center')

        mouse = display.mouse_logical()

        # Loadout pool sub-row (equip/store): highlights the current pool.
        for rect, pk, lbl in pool_rects:
            cur = (pk == self.pool)
            pygame.draw.rect(surf, (40, 46, 70) if cur else (22, 24, 38), rect,
                             border_radius=6)
            pygame.draw.rect(surf, (120, 150, 220) if cur else ui.LINE, rect, 2,
                             border_radius=6)
            ui.text(surf, self.font, lbl, (rect.centerx, rect.y + 2),
                    ui.TEXT if cur else ui.DIM, align='center')

        # Breadcrumb / hint line under the category row.
        hy = cat_rects[-1][0].bottom + 6
        if self.cat == 'champion' and self.champ_sel is not None:
            ui.text(surf, self.font,
                    f"{champions.BY_ID[self.champ_sel].name} > especie:",
                    (r.x + 14, hy), (255, 214, 110))
        else:
            hint = {'boss': 'escolha o chefe', 'champion': 'escolha o campeao',
                    'species': 'escolha a especie', 'pickup': 'escolha o item',
                    'round': 'escolha o tema da onda',
                    'equip': 'clique = equipa de graca',
                    'store': 'clique = marca p/ loja',
                    'debug': "clique alterna/dispara  ('.' = step)",
                    'char': 'clique = troca o personagem'}
            ui.text(surf, self.font, hint[self.cat], (r.x + 14, hy), ui.DIM)

        for rect, value, lbl in item_rects:
            if rect.collidepoint(mouse):
                pygame.draw.rect(surf, (44, 50, 76), rect, border_radius=6)
            # in round mode the picked theme reads as selected; in store mode the
            # entries staged for a "generate specific" store read as selected
            sel = (self.cat == 'round' and value == self.round_theme) or \
                  (self.cat == 'store' and (self.pool, value) in self.store_pick)
            ui.text(surf, self.font, ui.fit(self.font, lbl, rect.width - 8),
                    (rect.x + 6, rect.y + 2), (255, 214, 110) if sel else ui.TEXT)

        if self.cat == 'round':
            self._draw_round(surf, mouse)
        elif self.cat == 'store':
            self._draw_store(surf, mouse)

    def _draw_round(self, surf, mouse):
        """The round-control footer: wave scroller + START/RESET buttons."""
        rl = self._round_layout()

        def button(rect, label, col_on):
            hot = rect.collidepoint(mouse)
            pygame.draw.rect(surf, col_on if hot else (24, 26, 42), rect,
                             border_radius=8)
            pygame.draw.rect(surf, (120, 150, 220) if hot else ui.LINE, rect, 2,
                             border_radius=8)
            ui.text(surf, self.font, label, (rect.centerx, rect.y + 4),
                    ui.TEXT, align='center')

        button(rl['dec'], '-', (40, 46, 70))
        button(rl['inc'], '+', (40, 46, 70))
        wr = rl['wave']
        pygame.draw.rect(surf, (22, 24, 38), wr, border_radius=8)
        pygame.draw.rect(surf, ui.LINE, wr, 2, border_radius=8)
        boss = '  (chefe)' if self.round_wave % 5 == 0 else ''
        ui.text(surf, self.font, f"onda {self.round_wave}{boss}",
                (wr.centerx, wr.y + 4), ui.TEXT, align='center')
        start_lbl = ui.fit(self.font, f"START -> {THEMES[self.round_theme]['banner']}",
                           rl['start'].width - 12)
        button(rl['start'], start_lbl, (30, 60, 40))
        button(rl['reset'], 'RESET (limpa a cena)', (70, 34, 40))

    def _draw_store(self, surf, mouse):
        """The store footer: random-N scroller + generate/clear buttons."""
        sl = self._store_layout()

        def button(rect, label, col_on):
            hot = rect.collidepoint(mouse)
            pygame.draw.rect(surf, col_on if hot else (24, 26, 42), rect,
                             border_radius=8)
            pygame.draw.rect(surf, (120, 150, 220) if hot else ui.LINE, rect, 2,
                             border_radius=8)
            ui.text(surf, self.font, ui.fit(self.font, label, rect.width - 12),
                    (rect.centerx, rect.y + 4), ui.TEXT, align='center')

        button(sl['dec'], '-', (40, 46, 70))
        button(sl['inc'], '+', (40, 46, 70))
        nr = sl['n']
        pygame.draw.rect(surf, (22, 24, 38), nr, border_radius=8)
        pygame.draw.rect(surf, ui.LINE, nr, 2, border_radius=8)
        ui.text(surf, self.font, f"random N = {self.store_n}",
                (nr.centerx, nr.y + 4), ui.TEXT, align='center')
        button(sl['spec'], f"GERAR SELECIONADOS ({len(self.store_pick)})",
               (30, 60, 40))
        button(sl['rand'], 'GERAR RANDOM N', (30, 60, 40))
        button(sl['clear'], 'LIMPAR SELECAO', (70, 34, 40))
