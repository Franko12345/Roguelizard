"""Title hub: play (1/2 players), options (fullscreen/resize) and controls.

A navigable menu (arrows/mouse) over a live backdrop of procedurally-animated
lizards. Returns the chosen player count to `app`, or None to quit.
"""

import math
import random
from pygame import Vector2
import pygame

from ..audio import engine as audio
from ..creatures import characters
from ..combat import charms
from ..core import config as C
from ..render import display
from ..combat import evolution
from ..render import icons
from ..combat import items
from ..core import palette
from ..render import perf
from ..flow import progression
from ..core import settings
from ..creatures import species
from ..render import ui
from ..combat import weapons
from ..core.mathutil import approach, clamp, safe_norm, vfrom_angle, pulse
from ..creatures.ai import AILizard
from ..render.camera import Camera
from ..world.terrain import World


def _make_backdrop():
    demo = [AILizard(Vector2(0, 0), 'prey', random.uniform(0.7, 1.4),
                     random.choice([C.COL_PREY, C.COL_FRIEND, C.COL_BUG,
                                    C.COL_PLAYER[0], C.COL_PLAYER2[0], C.COL_ENEMY]))
            for _ in range(6)]
    cam = Camera()
    cam.pos = Vector2(C.WORLD_W / 2, C.WORLD_H / 2)
    cam.zoom = 1.0
    for d in demo:
        d.pos = cam.pos + Vector2(random.uniform(-420, 420), random.uniform(-280, 280))
        d.spine.resolve(d.pos)
        d.reset_secondary_springs()
    return demo, cam, World()


def _step_creature_for_display(c, dt, cam=None, wobble=True):
    """Run the canonical creature animation pipeline for a menu creature.

    Single source of truth for menu-side creature stepping (issue #19).
    Previously, `_step_backdrop`/`_preview_step`/`_char_preview_step` each
    open-coded ``pos += vel*dt`` → ``spine.resolve`` → leg update →
    ``update_secondary_springs`` → squash, and they had already drifted
    (one forgot ``wobble``, one synced the cam, one did not). Changing
    the in-game pipeline used to require editing all three; now it
    requires editing this one function.

    Caller responsibilities BEFORE calling this:
      - set ``c.on_screen`` if you want it drawn (caller already does)
      - call ``c.steer(dir, dt, speed_mul)`` so ``c.vel`` is fresh

    Caller responsibilities AFTER (optional):
      - sync ``cam.pos`` to ``c.pos`` if the cam should follow
      - bounce ``c.pos``/``c.vel`` against world bounds if needed

    ``world`` is NOT required: the menu has no enemies, no collisions, no
    pickups -- just a creature walking for display. ``integrate(dt)`` is
    skipped because it pulls contact-drag and dash physics that have no
    meaning here; the menu replicates only the animation half of the
    pipeline (the half that produces visible motion).
    """
    c.pos += c.vel * dt
    c.spine.resolve(c.pos)
    if c.vel.length_squared() > 1:
        c.facing = safe_norm(c.vel)
    for leg in c.legs:
        leg.update(c.spine, c.vel, dt, None)
    c.update_secondary_springs(dt)
    c.squash = approach(c.squash, 1 + clamp(c.vel.length() / c.max_speed, 0, 1) * 0.16,
                        9, dt)
    if wobble:
        c.wobble += dt * 6


def _step_backdrop(demo, cam, world, dt):
    world.update(dt)
    for d in demo:
        d.on_screen = True
        d.steer(d.wander_dir(dt), dt, 0.5)
        # bounce against the backdrop's invisible walls so the demo
        # creatures never wander off-screen -- caller-side because the
        # bounds are tied to the cam, not to the creature.
        for ax in (0, 1):
            if d.pos[ax] < cam.pos[ax] - 470:
                d.vel[ax] = abs(d.vel[ax])
            if d.pos[ax] > cam.pos[ax] + 470:
                d.vel[ax] = -abs(d.vel[ax])
        _step_creature_for_display(d, dt, cam=cam, wobble=False)


def _draw_backdrop(screen, demo, cam, world):
    screen.fill(C.COL_BG)
    world.draw_ground(screen, cam)
    world.draw_decor(screen, cam)
    for d in demo:
        d.draw(screen, cam)
    world.draw_ambient(screen, cam)
    veil = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
    veil.fill((12, 10, 24, 120))
    screen.blit(veil, (0, 0))


def _title(screen, titlefont, font, t):
    cx = C.WIDTH // 2
    glow = 0.6 + 0.4 * math.sin(t * 2)
    palette.glow(screen, (cx, 118), 240, C.COL_PLAYER[0], 0.25 + 0.15 * glow)
    title = titlefont.render("L A G A R T O", True, C.COL_PLAYER[0])
    screen.blit(title, (cx - title.get_width() // 2, 78))
    sub = font.render("roguelite de evolucao procedural", True, (205, 205, 225))
    screen.blit(sub, (cx - sub.get_width() // 2, 150))


def _panel(screen, rect):
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    s.fill((16, 18, 30, 180))
    screen.blit(s, (rect.x, rect.y))
    pygame.draw.rect(screen, (60, 64, 96), rect, 2, border_radius=16)


def _menu_list(screen, font, bigfont, items, sel, top, accent, anim=None, t=0.0):
    """Vertical list, Vampire-Survivors style: items drop in staggered and the
    highlight *glides* between entries instead of snapping.

    ``anim`` is a dict kept by the caller: {'t': seconds since this screen opened,
    'sel_f': smoothed selection index}.
    """
    cx = C.WIDTH // 2
    rects = []
    gap = 58
    if items:
        gap = max(40, min(58, (C.HEIGHT - top - 56) // len(items)))
    small = gap < 52
    w = 420
    at = anim['t'] if anim else 99.0
    sel_f = anim['sel_f'] if anim else float(sel)

    # gliding highlight, drawn under the labels so text stays crisp
    hy = top + sel_f * gap
    hrect = pygame.Rect(cx - w // 2, int(hy), w, gap - 10)
    if at > 0.05:
        palette.glow(screen, hrect.center, 150, accent, 0.22 + 0.16 * pulse(t, 5))
        pygame.draw.rect(screen, (26, 30, 46), hrect, border_radius=12)
        pygame.draw.rect(screen, accent, hrect, 3, border_radius=12)
        # little marker that rides along the left edge
        bar = pygame.Rect(hrect.x + 9, hrect.y + 9, 5, hrect.height - 18)
        pygame.draw.rect(screen, accent, bar, border_radius=3)

    for i, label in enumerate(items):
        # staggered drop-in: each row starts a bit after the previous one
        off, ease = ui.drop_in(at, i, stagger=0.045, dur=0.26, rise=26.0)
        lt = ease
        y = top + i * gap + off                        # slides down into place
        rect = pygame.Rect(cx - w // 2, int(top + i * gap), w, gap - 10)
        rects.append((i, rect))
        if lt <= 0:
            continue
        chosen = (i == sel)
        col = C.COL_WHITE if chosen else (150, 152, 172)
        f = font if small else bigfont
        im = f.render(label, True, col)
        if chosen and not small:                       # selected pops slightly
            grow = 1.0 + 0.06 * pulse(t, 5)
            im = pygame.transform.smoothscale(
                im, (int(im.get_width() * grow), int(im.get_height() * grow)))
        if ease < 1:
            im = im.copy()
            im.set_alpha(int(255 * ease))
        screen.blit(im, (cx - im.get_width() // 2,
                         int(y + (gap - 10) // 2 - im.get_height() // 2)))
    return rects


def _side_list(screen, font, items, sel, rect, accent, scroll=0):
    """Compact list inside `rect` (bestiary/compendium). Returns clickable rects."""
    _panel(screen, rect)
    rects = []
    row = 32
    visible = (rect.height - 16) // row
    top = max(0, min(sel - visible // 2, max(0, len(items) - visible)))
    for i in range(top, min(len(items), top + visible)):
        y = rect.y + 8 + (i - top) * row
        r = pygame.Rect(rect.x + 6, y, rect.width - 12, row - 3)
        rects.append((i, r))
        if i == sel:
            pygame.draw.rect(screen, (30, 34, 52), r, border_radius=8)
            pygame.draw.rect(screen, accent, r, 2, border_radius=8)
        im = font.render(items[i], True, C.COL_WHITE if i == sel else (152, 155, 178))
        screen.blit(im, (r.x + 10, r.y + 3))
    return rects


def _preview_step(c, cam, dt, t):
    """Walk the bestiary creature in a slow circle so its legs animate."""
    c.on_screen = True
    c.steer(vfrom_angle(t * 45), dt, 0.5)
    _step_creature_for_display(c, dt, cam=cam, wobble=True)
    cam.pos = Vector2(c.pos)


def _draw_bestiary(screen, font, bigfont, keys, sel, preview, cam):
    left = pygame.Rect(70, 200, 330, 452)
    right = pygame.Rect(420, 200, C.WIDTH - 490, 452)
    labels = [species.info(k)[0] for k in keys] + ['VOLTAR']
    rects = _side_list(screen, font, labels, sel, left, C.COL_PLAYER2[0])
    _panel(screen, right)

    if sel >= len(keys):
        im = font.render("voltar ao menu", True, (170, 172, 194))
        screen.blit(im, (right.centerx - im.get_width() // 2, right.centery))
        return rects

    key = keys[sel]
    spec = species.SPECIES[key]
    name, lore = species.info(key)
    # live procedural creature, clipped to the panel
    old = screen.get_clip()
    stage = pygame.Rect(right.x + 8, right.y + 8, right.width - 16, 210)
    screen.set_clip(stage)
    cam.center = (stage.centerx, stage.centery)
    if preview:
        preview.draw(screen, cam)
    screen.set_clip(old)
    pygame.draw.rect(screen, (54, 58, 88), stage, 1, border_radius=12)

    y = stage.bottom + 14
    screen.blit(bigfont.render(name, True, C.COL_WHITE), (right.x + 22, y))
    y += 44
    role = 'PREDADOR' if spec['role'] == 'enemy' else 'PRESA'
    rc = C.COL_ENEMY if spec['role'] == 'enemy' else C.COL_PREY
    ui.chip(screen, font, role, right.x + 22, y, rc)
    ui.chip(screen, font, f"XP {spec['xp']}", right.x + 150, y, (245, 210, 90))
    ui.chip(screen, font, f"PTS {spec['score']}", right.x + 250, y, (150, 200, 245))
    if spec['grants']:
        ui.chip(screen, font, f"concede: {spec['grants']}", right.x + 360, y, C.COL_FRIEND)
    y += 44
    ui.paragraph(screen, font, lore, right.x + 22, y, right.width - 44)
    return rects


def _draw_compendium(screen, font, bigfont, tab, entries, sel):
    tabs_r = ui.tabs(screen, font, ['ARMAS', 'EVOLUCOES', 'CHARMS', 'ITENS'], tab, 196,
                     C.COL_PLAYER[0])
    left = pygame.Rect(70, 246, 330, 400)
    right = pygame.Rect(420, 246, C.WIDTH - 490, 400)
    labels = [e['name'] for e in entries] + ['VOLTAR']
    rects = _side_list(screen, font, labels, sel, left, C.COL_PLAYER[0])
    _panel(screen, right)
    if sel >= len(entries):
        im = font.render("voltar ao menu", True, (170, 172, 194))
        screen.blit(im, (right.centerx - im.get_width() // 2, right.centery))
        return rects, tabs_r

    e = entries[sel]
    x, y = right.x + 22, right.y + 20
    icons.draw(screen, e.get('icon'), (x + 18, y + 18), 18, e['color'])
    screen.blit(bigfont.render(e['name'], True, C.COL_WHITE), (x + 50, y + 2))
    y += 56
    if e.get('tag'):
        ui.chip(screen, font, e['tag'], x, y, e['color'])
        y += 40
    y = ui.paragraph(screen, font, e['desc'], x, y, right.width - 44) + 12
    for line in e.get('levels', []):
        screen.blit(font.render(line, True, (186, 190, 214)), (x + 8, y))
        y += 24
    return rects, tabs_r



def _buy_meta(meta, entries, sel):
    """Confirm on a meta row = buy that upgrade/unlock. Returns True if bought."""
    if sel >= len(entries):
        return False
    e = entries[sel]
    if e['cost'] is None:
        return False
    ok = (progression.buy_upgrade(meta, e['id']) if e['kind'] == 'upgrade'
          else progression.buy_unlock(meta, e['id']))
    return ok

def _meta_entries():
    """Rows for the DNA screen: permanent upgrades then unlocks."""
    data = progression.load()
    out = []
    for uid, spec in progression.UPGRADES.items():
        lvl = progression.level(data, uid)
        cost = progression.upgrade_cost(data, uid)
        out.append(dict(kind='upgrade', id=uid, name=spec['name'], desc=spec['desc'],
                        hue=spec['hue'], level=lvl, maxlevel=spec['max_level'],
                        cost=cost))
    for uid, spec in progression.UNLOCKS.items():
        owned = uid in data['unlocks']
        out.append(dict(kind='unlock', id=uid, name=spec['name'], desc=spec['desc'],
                        hue=spec['hue'], level=1 if owned else 0, maxlevel=1,
                        cost=None if owned else spec['cost']))
    return out


def _draw_meta(screen, font, bigfont, entries, sel, dna):
    box = pygame.Rect(120, 196, C.WIDTH - 240, 460)
    _panel(screen, box)
    hdr = bigfont.render("EVOLUCAO PERMANENTE", True, C.COL_WHITE)
    screen.blit(hdr, (box.centerx - hdr.get_width() // 2, box.y + 12))
    dn = bigfont.render(f"{dna} DNA", True, (140, 240, 170))
    screen.blit(dn, (box.right - dn.get_width() - 22, box.y + 14))

    rects = []
    row_h = 50
    top = box.y + 62
    visible = (box.height - 80) // row_h
    start = max(0, min(sel - visible // 2, max(0, len(entries) + 1 - visible)))
    labels = entries + ['VOLTAR']
    for i in range(start, min(len(labels), start + visible)):
        y = top + (i - start) * row_h
        r = pygame.Rect(box.x + 14, y, box.width - 28, row_h - 6)
        rects.append((i, r))
        chosen = (i == sel)
        e = labels[i]
        if chosen:
            pygame.draw.rect(screen, (30, 34, 52), r, border_radius=10)
        if isinstance(e, str):                    # VOLTAR
            pygame.draw.rect(screen, (120, 124, 150) if chosen else (70, 72, 92),
                             r, 2, border_radius=10)
            im = font.render(e, True, C.COL_WHITE if chosen else (150, 152, 172))
            screen.blit(im, (r.centerx - im.get_width() // 2, r.y + 8))
            continue
        col = palette.vibrant(e['hue'], 0.8, 1.0)
        maxed = e['cost'] is None
        afford = (not maxed) and dna >= e['cost']
        edge = col if (chosen or afford) else (70, 72, 92)
        pygame.draw.rect(screen, edge, r, 3 if chosen else 1, border_radius=10)
        icons.draw(screen, e['id'].replace('weapon_', '').replace('charm_', ''),
                   (r.x + 26, r.centery), 13, col, glow=False)
        screen.blit(font.render(e['name'], True, C.COL_WHITE), (r.x + 50, r.y + 3))
        screen.blit(font.render(e['desc'], True, (168, 172, 196)), (r.x + 50, r.y + 21))
        # level pips
        px = r.right - 210
        for k in range(e['maxlevel']):
            c = col if k < e['level'] else (58, 60, 82)
            pygame.draw.circle(screen, c, (px + k * 18, r.centery), 6)
        txt = 'MAX' if maxed else f"{e['cost']} DNA"
        tc = (150, 240, 180) if afford else ((160, 200, 175) if maxed else (140, 120, 90))
        im = font.render(txt, True, tc)
        screen.blit(im, (r.right - im.get_width() - 14, r.centery - 9))
    return rects


def _compendium_entries(tab):
    out = []
    if tab == 0:
        for wid, w in weapons.WEAPONS.items():
            lv = [f"Nv{i+1}: {w.level_desc(i+1)}" for i in range(w.maxlevel())]
            out.append(dict(name=w.name, color=w.color, icon=wid, tag='ARMA AUTOMATICA',
                            desc='Ataca sozinha. Suba de nivel nas cartas para melhorar.',
                            levels=lv))
    elif tab == 1:
        for m in evolution.MUTATIONS:
            out.append(dict(name=m.name, color=m.color, icon=m.icon, tag='MUTACAO', desc=m.desc))
        for s in evolution.SYNERGIES:
            out.append(dict(name=f"SINERGIA: {s.name}", color=(255, 226, 120),
                            tag='COMBO', desc=s.desc,
                            levels=[f"requer: {', '.join(sorted(s.needs))}"]))
    elif tab == 3:
        for it in items.ITEMS:
            kind = 'ATIVO (tecla E)' if it.kind == 'active' else 'PASSIVO'
            where = ', '.join(it.pools)
            out.append(dict(name=it.name, color=it.color, icon=it.icon,
                            tag=f"{kind}  -  qualidade {it.quality}",
                            desc=it.desc,
                            levels=[f"aparece em: {where}"]))
    else:
        for c in charms.CHARMS.values():
            out.append(dict(name=c.name, color=palette.vibrant(c.hue, 0.8, 1.0), icon=c.id,
                            tag=f"SLOT: {c.slot.upper()}", desc=c.desc,
                            levels=[f"custo: {c.cost} polen"]))
    return out


def run_menu(screen, font, bigfont, titlefont, joysticks):
    from ..input.controllers import MenuNav
    clock = pygame.time.Clock()
    nav = MenuNav()
    fade = ui.Fade()
    fade.start(0.3)
    prev_mode = 'main'
    anim = {'t': 0.0, 'sel_f': 0.0}      # drop-in clock + smoothed selection
    demo, cam, world = _make_backdrop()
    t = 0.0
    mode = 'main'
    sel = 0
    rects = []            # menu item rects (from the previous frame, for mouse hits)
    # bestiary / compendium state
    bkeys = list(species.SPECIES.keys())
    preview = {'key': None, 'creature': None, 'cam': Camera()}
    preview['cam'].zoom = 1.0
    tab = 0
    tab_rects = []
    meta = progression.load()

    pending = None       # (num_players, game_mode) waiting on character picks
    picks = []           # one character id per player, filled in order
    charprev = {}        # live creature previews for the select screen

    def toggle_fs():
        display.toggle_fullscreen()
        settings.save_display(display, audio)

    def handle(r):
        """Resolve one activation. Returns ('go', value) to leave run_menu.

        All three input paths (keyboard, mouse, gamepad) used to repeat this
        block verbatim; character select added a second exit condition, and
        three copies of a two-exit rule is how they drift apart.
        """
        nonlocal mode, sel, pending, picks
        if r == 'quit':
            return ('go', None)
        if isinstance(r, tuple) and r[0] == 'pick':
            ch = characters.CHARACTERS.all()[r[1]]
            if characters.is_locked(ch, meta):
                audio.play('ui', 0.35)          # locked: refuse, don't advance
                return None
            picks.append(ch.id)
            audio.play('ui')
            if pending and len(picks) >= pending[0]:
                return ('go', (pending[0], pending[1], list(picks)))
            return None
        st = _start_for(r, meta)
        if st:
            # every start now routes through character select first
            pending, picks = st, []
            mode, sel = 'chars', 0
            return None
        if r is not None and r not in ('play1', 'play2', 'endless'):
            mode, sel = r, 0
            if r == 'main':
                pending, picks = None, []
        return None

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt
        # window px -> logical px, same as the click handler below. The hover
        # highlight and the click must share a coordinate space; reading raw
        # window pixels here left them in different spaces at any scale != 1x.
        mouse = display.to_logical(pygame.mouse.get_pos())

        items = _items_for(mode, bkeys, tab, meta)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return None
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_F11:
                    toggle_fs()
                elif ev.key in (pygame.K_DOWN, pygame.K_s):
                    sel = (sel + 1) % len(items); audio.play('ui', 0.5)
                elif ev.key in (pygame.K_UP, pygame.K_w):
                    sel = (sel - 1) % len(items); audio.play('ui', 0.5)
                elif ev.key in (pygame.K_LEFT, pygame.K_a) and mode == 'chars':
                    sel = (sel - 1) % len(items); audio.play('ui', 0.5)
                elif ev.key in (pygame.K_RIGHT, pygame.K_d) and mode == 'chars':
                    sel = (sel + 1) % len(items); audio.play('ui', 0.5)
                elif ev.key in (pygame.K_LEFT, pygame.K_a) and mode == 'compendium':
                    tab, sel = (tab - 1) % 4, 0; audio.play('ui', 0.5)
                elif ev.key in (pygame.K_RIGHT, pygame.K_d) and mode == 'compendium':
                    tab, sel = (tab + 1) % 4, 0; audio.play('ui', 0.5)
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if mode == 'meta' and _buy_meta(meta, items[:-1], sel):
                        audio.play('buy'); meta = progression.load(); continue
                    r = _activate(mode, sel, toggle_fs, len(items))
                    done = handle(r)
                    if done is not None:
                        return done[1]
                elif ev.key == pygame.K_ESCAPE:
                    if mode == 'main':
                        return None
                    if mode == 'chars':
                        pending, picks = None, []
                    mode, sel = 'main', 0
            if ev.type == pygame.VIDEORESIZE:
                display.handle_resize()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mp = display.to_logical(ev.pos)      # window px -> logical px
                for ti, trect in enumerate(tab_rects):
                    if trect.collidepoint(mp):
                        tab, sel = ti, 0
                for i, rect in rects:
                    if rect.collidepoint(mp):
                        sel = i
                        if mode == 'meta' and _buy_meta(meta, items[:-1], sel):
                            audio.play('buy'); meta = progression.load(); break
                        r = _activate(mode, sel, toggle_fs, len(items))
                        done = handle(r)
                        if done is not None:
                            return done[1]
                        break

        # gamepad navigation (same actions as the keyboard)
        nav.poll(joysticks, dt)
        if nav.down:
            sel = (sel + 1) % len(items); audio.play('ui', 0.5)
        if nav.up:
            sel = (sel - 1) % len(items); audio.play('ui', 0.5)
        if mode == 'compendium':
            if nav.left:
                tab, sel = (tab - 1) % 4, 0; audio.play('ui', 0.5)
            if nav.right:
                tab, sel = (tab + 1) % 4, 0; audio.play('ui', 0.5)
        elif mode == 'chars':               # cards are horizontal: stick L/R moves
            if nav.left:
                sel = (sel - 1) % len(items); audio.play('ui', 0.5)
            if nav.right:
                sel = (sel + 1) % len(items); audio.play('ui', 0.5)
        if nav.confirm and mode == 'meta' and _buy_meta(meta, items[:-1], sel):
            audio.play('buy'); meta = progression.load()
        elif nav.confirm:
            r = _activate(mode, sel, toggle_fs, len(items))
            done = handle(r)
            if done is not None:
                return done[1]
        if nav.cancel:
            if mode == 'main':
                return None
            if mode == 'chars':             # clear the pending pick, like ESC does
                pending, picks = None, []
            mode, sel = 'main', 0

        # input may have switched screens this frame -> refresh the item list so we
        # never draw one screen's items with another screen's layout
        items = _items_for(mode, bkeys, tab, meta)

        _step_backdrop(demo, cam, world, dt)
        _draw_backdrop(screen, demo, cam, world)
        _title(screen, titlefont, font, t)

        if mode == 'main':
            rects = _menu_list(screen, font, bigfont, items, sel, 250, C.COL_PLAYER[0], anim, t)
            legend = ("gamepad detectado" if joysticks else "gamepad: conecte p/ P2")
            foot = font.render(f"setas/mouse p/ navegar - ENTER p/ escolher - {legend}",
                               True, (170, 172, 194))
            screen.blit(foot, (C.WIDTH // 2 - foot.get_width() // 2, C.HEIGHT - 44))
        elif mode == 'options':
            _panel(screen, pygame.Rect(C.WIDTH // 2 - 300, 230, 600, 240))
            rects = _menu_list(screen, font, bigfont, items, sel, 268, C.COL_PLAYER2[0], anim, t)
            hint = font.render("arraste a janela p/ redimensionar - vsync ligado",
                               True, (180, 182, 202))
            screen.blit(hint, (C.WIDTH // 2 - hint.get_width() // 2, 420))
        elif mode == 'meta':
            rects = _draw_meta(screen, font, bigfont, items[:-1], sel, meta['dna'])
            tab_rects = []
            ui.footer(screen, font, "ENTER/A compra - ganhe DNA jogando - ESC/B volta")
        elif mode == 'bestiary':
            # keep a live creature of the highlighted species
            key = bkeys[sel] if sel < len(bkeys) else None
            if key != preview['key']:
                preview['key'] = key
                preview['creature'] = species.make(key, Vector2(C.WORLD_W / 2,
                                                                C.WORLD_H / 2)) if key else None
            if preview['creature']:
                _preview_step(preview['creature'], preview['cam'], dt, t)
            rects = _draw_bestiary(screen, font, bigfont, bkeys, sel,
                                   preview['creature'], preview['cam'])
            tab_rects = []
            ui.footer(screen, font, "setas p/ navegar - ESC/B volta")
        elif mode == 'compendium':
            entries = _compendium_entries(tab)
            rects, tab_rects = _draw_compendium(screen, font, bigfont, tab, entries, sel)
            ui.footer(screen, font, "setas cima/baixo: item - esquerda/direita: aba - ESC/B volta")
        elif mode == 'chars':
            who = ("ESCOLHA SEU LAGARTO" if not pending or pending[0] == 1
                   else f"JOGADOR {len(picks) + 1}: ESCOLHA")
            rects = _draw_chars(screen, font, bigfont, sel, meta, t, anim, who,
                                preview=charprev, dt=dt)
            tab_rects = []
        else:  # controls
            _panel(screen, pygame.Rect(C.WIDTH // 2 - 360, 220, 720, 300))
            lines = controls_lines(joysticks)
            for i, l in enumerate(lines):
                im = font.render(l, True, (206, 208, 226) if l else (150, 150, 170))
                screen.blit(im, (C.WIDTH // 2 - im.get_width() // 2, 250 + i * 32))
            rects = _menu_list(screen, font, bigfont, items, sel, 470, C.COL_PLAYER2[0], anim, t)

        if mode != prev_mode:
            fade.start(0.2)
            prev_mode = mode
            anim['t'] = 0.0                  # replay the drop-in on the new screen
            anim['sel_f'] = float(sel)
        anim['t'] += dt
        # ease the highlight toward the real selection (glide, not snap)
        anim['sel_f'] += (sel - anim['sel_f']) * min(1.0, dt * 16)
        fade.update(dt)
        fade.draw(screen)
        display.present()


def _start_for(r, meta):
    """Map a menu action to (num_players, mode), or None if it isn't a start."""
    if r == 'play1':
        return (1, 'normal')
    if r == 'play2':
        return (2, 'normal')
    if r == 'endless':
        return (1, 'endless') if progression.endless_unlocked(meta) else None
    return None


def _main_items(meta):
    endless = ('MODO INFINITO' if progression.endless_unlocked(meta)
               else 'MODO INFINITO (vença a run p/ liberar)')
    return ['JOGAR (1 JOGADOR)', endless, '2 JOGADORES (COOP)', 'EVOLUCAO (DNA)',
            'OPCOES', 'CONTROLES', 'BESTIARIO', 'COMPENDIO', 'SAIR']


CONTROLS = (
    "P1:  WASD mover  -  mouse mirar  -  clique/ESPACO dash  -  dir/SHIFT lingua",
    "P1:  clique-meio/Q rabada (golpe de cauda)  -  LCtrl rolamento",
    "P1 (gamepad):  sticks  -  A dash  -  X lingua  -  Y rabada  -  LT/RT rolamento   (no single-player)",
    "P2:  setas mover  -  IJKL mirar  -  RCtrl dash  -  RShift lingua  -  RAlt rabada  -  O rolamento",
    "P2 (gamepad):  sticks  -  A dash  -  X lingua  -  Y rabada  -  LT/RT rolamento",
    "",
    "armas atacam sozinhas - suba de nivel p/ evoluir  -  [R] rerrola as cartas - 1x por round (LAGARTO)",
    "F11 tela cheia  -  F3 medidor de FPS  -  ESC pausa",
)


def controls_lines(joysticks):
    """Shared by the menu and the in-game pause screen, so they can't drift."""
    pad = (f"gamepad: {joysticks[0].name}" if joysticks else
           "gamepad: nenhum detectado (conecte e ele e reconhecido na hora)")
    return list(CONTROLS) + ["", pad]


def _items_for(mode, bkeys, tab, meta):
    """The navigable item list for a screen (drives selection + hit-testing)."""
    if mode == 'main':
        return _main_items(meta)
    if mode == 'options':
        return [f'TELA CHEIA: {"LIGADA" if display.is_fullscreen() else "DESLIGADA"}  (F11)',
                f'ESCALA DA JANELA: {display.get_scale()}x',
                f'VSYNC: {"LIGADO" if display.get_vsync() else "DESLIGADO"}',
                f'VOLUME EFEITOS: {int(audio.volumes()[0] * 100)}%',
                f'VOLUME MUSICA: {int(audio.volumes()[1] * 100)}%',
                f'MEDIDOR DE FPS: {perf.LEVEL_NAMES[settings.load()["perf"]].upper()}  (F3)',
                'VOLTAR']
    if mode == 'meta':
        return _meta_entries() + ['VOLTAR']
    if mode == 'chars':
        return _char_entries(meta)   # sem VOLTAR: sao cartas lado a lado, ESC volta
    if mode == 'bestiary':
        return bkeys + ['VOLTAR']
    if mode == 'compendium':
        return _compendium_entries(tab) + ['VOLTAR']
    return ['VOLTAR']


def _char_entries(meta):
    """Labels only -- the real screen is `_draw_chars`. Kept so selection,
    hit-testing and gamepad nav share the generic index machinery."""
    return [c.name for c in characters.CHARACTERS]


def _char_previews(store):
    """One live creature per character, built once and kept walking.

    The whole premise of these four is that they *look* different because the
    body is generated from the genome -- so showing the real thing animating
    beats any icon: what you see on the card is literally what you will control.
    """
    if store.get('made'):
        return store['crea']
    store['made'] = True
    store['crea'] = []
    store['cam'] = Camera()
    # the stage is only ~116px tall and these bodies are up to 380px long, so it
    # has to be pulled well back or you see a close-up of one eye
    store['cam'].zoom = 0.62
    for c in characters.CHARACTERS:
        cr = AILizard(Vector2(C.WORLD_W / 2, C.WORLD_H / 2), 'prey',
                      genome=c.make_genome())
        # menu-only tint: in game the hue comes from the player slot, but here
        # each card needs its own identity and the accent is that identity
        cr.color = c.color()
        cr.base_color = cr.color
        cr.spine.resolve(cr.pos)
        cr.preview_phase = len(store['crea']) * 1.4    # so they don't move in lockstep
        # Fit-to-stage zoom, but clamped to a NARROW range on purpose: a true fit
        # would make every body the same on-screen size and throw away the fact
        # that the couracado is huge and the larva is tiny, which is half of what
        # the card is telling you.
        span = cr.spine.link * (len(cr.spine.joints) - 1)
        cr.preview_zoom = clamp(178.0 / max(span, 1.0), 0.42, 0.80)
        store['crea'].append(cr)
    return store['crea']


def _char_preview_step(c, cam, dt, t):
    """Walk the card creature in PROFILE, not in a circle.

    The bestiary spins its creature through every heading, which is fine when it
    fills half the screen. Here the whole point is comparing bodies -- leg count,
    length, girth -- and a creature pointed at the camera shows none of that. So
    it holds a sideways heading and just sways.
    """
    c.on_screen = True
    sway = math.sin(t * 0.7 + c.preview_phase) * 34
    c.steer(vfrom_angle(sway), dt, 0.55)
    _step_creature_for_display(c, dt, cam=cam, wobble=True)


def _draw_chars(screen, font, bigfont, sel, meta, t, anim, who, preview=None, dt=0.0):
    """Character select: a card per character, not a list of sentences.

    The list version put four long strings on top of each other and had no
    hierarchy at all -- you could not tell at a glance what any of them played
    like. Here the icon carries the silhouette, the accent colour carries the
    identity, and the modifiers are chips, so the eye lands on name -> shape ->
    traits in that order.
    """
    n = len(characters.CHARACTERS)
    cw, gap = 244, 16
    ch = 384
    x0 = C.WIDTH // 2 - (n * cw + (n - 1) * gap) // 2
    top = 228
    rects = []
    at = anim['t'] if anim else 9.0
    crea_all = _char_previews(preview) if preview is not None else None
    pcam = preview['cam'] if preview is not None else None
    if crea_all:                       # walk them so the legs actually animate
        for cr in crea_all:
            _char_preview_step(cr, pcam, dt, t)

    ui.text(screen, bigfont, who, (C.WIDTH // 2, 164), C.COL_WHITE, align='center')
    ui.text(screen, font, "setas/mouse escolhem  -  ENTER confirma  -  ESC volta",
            (C.WIDTH // 2, 198), (176, 180, 206), align='center')

    for i, c in enumerate(characters.CHARACTERS):
        locked = characters.is_locked(c, meta)
        off, alpha = ui.drop_in(at, i, stagger=0.05, dur=0.28, rise=30.0)
        rect = pygame.Rect(x0 + i * (cw + gap), top, cw, ch)
        rects.append((i, rect))
        if alpha <= 0.01:
            continue
        r = rect.move(0, int(off))
        accent = (92, 96, 122) if locked else c.color()
        chosen = (i == sel)

        if chosen:
            palette.glow(screen, r.center, cw * 0.78, accent, 0.20 + 0.14 * pulse(t, 5))
        body = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
        body.fill((20, 23, 38, 236) if chosen else (15, 17, 28, 208))
        screen.blit(body, r.topleft)
        pygame.draw.rect(screen, accent, r, 4 if chosen else 2, border_radius=16)

        # live creature, clipped to a stage inside the card (bestiary pattern)
        stage = pygame.Rect(r.x + 10, r.y + 12, r.width - 20, 128)
        pygame.draw.rect(screen, (11, 13, 22), stage, border_radius=12)
        crea = crea_all[i] if crea_all and i < len(crea_all) else None
        if crea is not None:
            old = screen.get_clip()
            screen.set_clip(stage)
            pcam.zoom = crea.preview_zoom
            pcam.center = (stage.centerx, stage.centery + 6)
            pcam.pos = Vector2(crea.pos)
            if locked:                        # silhouette only until you earn it
                crea.color = (74, 78, 98)
            else:
                crea.color = c.color()
            crea.draw(screen, pcam)
            screen.set_clip(old)
        pygame.draw.rect(screen, (48, 52, 78), stage, 1, border_radius=12)
        ui.text(screen, bigfont, c.name, (r.centerx, r.y + 152), accent, align='center')

        # modifiers as chips: the compressed "who is this" line
        cy = r.y + 202
        for m in c.mods[:3]:
            w = font.size(m)[0] + 18
            chip = pygame.Rect(r.centerx - w // 2, cy, w, 22)
            pygame.draw.rect(screen, (30, 34, 52), chip, border_radius=999)
            pygame.draw.rect(screen, accent, chip, 1, border_radius=999)
            ui.text(screen, font, m, (chip.centerx, cy + 2),
                    (222, 226, 244) if not locked else (140, 144, 166),
                    align='center')
            cy += 27

        # The blurb gets whatever vertical space is actually left, and no more.
        # Hardcoding its position collided with the lock block on exactly the
        # cards that need the lock text most -- same failure as the old HUD stack.
        cy += 10
        reserved = 78 if locked else 14          # the BLOQUEADO block at the bottom
        room = (r.bottom - reserved) - cy
        lines = ui.wrap(font, c.blurb, cw - 34)[:max(0, room // 21)]
        for li, line in enumerate(lines):
            ui.text(screen, font, line, (r.centerx, cy + li * 21),
                    (200, 204, 226) if not locked else (126, 130, 152),
                    align='center')

        if locked:
            veil = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            veil.fill((8, 9, 16, 150))
            screen.blit(veil, r.topleft)
            pygame.draw.rect(screen, (92, 96, 122), r, 2, border_radius=16)
            req = progression.unlock_hint('character', c.id)
            ui.text(screen, font, "BLOQUEADO", (r.centerx, r.bottom - 58),
                    (255, 190, 90), align='center')
            for li, line in enumerate(ui.wrap(font, req, cw - 34)):
                ui.text(screen, font, line, (r.centerx, r.bottom - 34 + li * 19),
                        (236, 208, 150), align='center')
    return rects


def _activate(mode, sel, toggle_fs, n_items=0):
    """Return 1/2 to start, a mode name to switch screen, or None for no-op."""
    if mode == 'chars':
        return ('pick', sel)
    if mode in ('bestiary', 'compendium'):
        return 'main' if sel >= n_items - 1 else None    # only VOLTAR does anything
    if mode == 'meta':
        return 'main' if sel >= n_items - 1 else None    # buying handled by the caller
    if mode == 'main':
        opts = ['play1', 'endless', 'play2', 'meta', 'options', 'controls',
                'bestiary', 'compendium', 'quit']
        return opts[sel] if sel < len(opts) else None
    if mode == 'options':
        if sel == 0:
            toggle_fs()
        elif sel == 1:
            display.cycle_scale()
            settings.save_display(display)
        elif sel == 2:
            display.toggle_vsync()
            settings.save_display(display, audio)
        elif sel == 3:
            sfx, mus = audio.volumes()
            audio.set_volumes(sfx=0.0 if sfx >= 0.99 else min(1.0, sfx + 0.1))
            audio.play('ui')
            settings.save_display(display, audio)
        elif sel == 4:
            sfx, mus = audio.volumes()
            audio.set_volumes(music=0.0 if mus >= 0.99 else min(1.0, mus + 0.1))
            settings.save_display(display, audio)
        elif sel == 5:
            cfg = settings.load()          # off -> fps -> detailed -> off
            cfg['perf'] = (cfg['perf'] + 1) % 3
            settings.save(cfg)
            audio.play('ui')
        else:
            return 'main'                 # VOLTAR
        return None
    return 'main'                         # controls/bestiary/compendium -> VOLTAR


