"""State 'camp': the walkable clearing plus the beetle tent's shop menu.

``update`` is the clearing's own step (it owns its early returns, so Game.step
dispatches to it directly instead of running the shared UI clock first).
``draw`` picks between the tent menu and the light field HUD; the world-space
furniture is drawn by ``_draw_camp_pois``, called from Game.draw's world pass.
"""

import random

import pygame
from pygame import Vector2

from ..audio import engine as audio
from ..combat import charms as charmlib
from ..core import config as C
from ..core import palette
from ..core.mathutil import clamp, decay, pulse
from ..creatures.ai import AILizard
from ..flow import progression
from ..flow import rounds
from ..render import assets
from ..render import icons
from ..render import ui
from ..render.fx import shadow
from . import state_levelup


def update(game, dt):
    """The clearing. Shop mode is the old frozen menu; field mode lets the
    players actually WALK -- touch the tent to shop, cross a door to advance."""
    game.ui_t += dt
    game.ui_fx = decay(game.ui_fx, dt)
    if game.pick:                         # absorbing a purchase: everything frozen
        state_levelup._step_pick(game, dt)
        game.fx.update(dt)
        return
    if game.camp.get('mode') == 'shop':   # menu open: frozen, like the old camp
        game.fx.update(dt)
        return
    # ---- field mode: live movement + POI interaction ---- #
    game.time += dt
    for p in game.players:
        if not p.dead:
            p.update(dt, game)
    for f in game.friends:                # pets keep following you between rounds
        if not f.dead:
            f.update(dt, game)
    game.world.update(dt)
    game.fx.update(dt)
    game.combo_flash = decay(game.combo_flash, dt, 2)
    game.camp['reopen_cd'] = decay(game.camp.get('reopen_cd', 0.0), dt)
    _update_camp_drop(game)               # the pieces fall in with a slam
    # touch the tent -> open the shop (only once it has landed)
    if game.camp['reopen_cd'] <= 0 and game.camp['tent_landed']:
        for p in game.players:
            if not p.dead and p.pos.distance_to(game.camp['tent']) < C.CAMP_TENT_R:
                game.camp['mode'] = 'shop'
                game.camp['focus'] = 'shop'
                game.ui_t = 0.0           # replay the drop-in
                game._panels.clear()
                audio.play('ui', 0.6)
                return
    # cross a door -> take that route (Hades: doors commit, no menu)
    for i, dr in enumerate(game.camp['doors']):
        if not dr['landed']:
            continue
        for p in game.players:
            if not p.dead and p.pos.distance_to(dr['pos']) < C.CAMP_DOOR_R:
                game.fx.spark_burst(dr['pos'], C.COL_ENEMY, 18, 320)
                game.fx.ring(dr['pos'], C.COL_ENEMY)
                game._apply_route(i)
                return


def draw(game, surf):
    if game.camp and game.camp.get('mode') == 'shop':
        _draw_camp(game, surf)            # the tent's shop/charm menu
    else:
        _draw_camp_field_ui(game, surf)   # walking the clearing


def shop_price(base, perm, buys, wave):
    """Preco de uma oferta da loja: base x estagio da run x inflacao por compra.

    Os dois eixos sao ortogonais de proposito -- por isso o estado guardado e a
    contagem de compras, e nao o preco absoluto. Guardar o preco embutiria o
    multiplicador do tier em que a compra aconteceu e o comporia de novo no tier
    seguinte.
    """
    mult = C.SHOP_PRICE_MULT_PERM if perm else C.SHOP_PRICE_MULT
    return int(base * rounds.tier_price_mult(wave) * mult ** buys)


def _roll_shop(game):
    def heal(g):
        for pl in g.players:
            pl.health = min(pl.max_health, pl.health + 40)

    def vitality(g):
        for pl in g.players:
            pl.max_health += 20; pl.health += 20

    def might(g):
        for pl in g.players:
            pl.might *= 1.15

    def haste(g):
        for pl in g.players:
            pl.cooldown_mult *= 0.9

    def egg(g):
        for pl in g.players:
            if pl.dead:
                continue
            f = AILizard(pl.pos, 'friend', 0.9, C.COL_FRIEND)
            f.hp = C.FRIEND_HP
            f.sync_max_hp()
            f.life = C.FRIEND_LIFE
            g.friends.append(f)

    def charm(g):
        for pl in g.players:
            if pl.dead:
                continue
            avail = [c.id for c in charmlib.CHARMS if c.id not in pl.charms_owned
                     and progression.unlocked(game.meta, 'charm', c.id)]
            if avail:
                pl.gain_charm(random.choice(avail), g)
    # ``base`` e o preco no tier 0 sem nenhuma compra; ``perm`` separa upgrade
    # permanente (recompra mais caro) de consumivel; ``preview`` declara o delta
    # numerico da oferta para a UI poder mostra-lo antes da compra -- Charm e Ovo
    # nao tem, porque o efeito deles nao e um numero.
    items = [
        dict(name='Nectar de Cura', desc='+40 vida', base=12, perm=False, preview=None,
             hue=140, icon='health', fn=heal),
        dict(name='Vitalidade', desc='+20 vida maxima', base=28, perm=True,
             preview=('max_health', 20, 'add'), hue=5, icon='health', fn=vitality),
        dict(name='Vigor', desc='+15% dano das armas', base=32, perm=True,
             preview=('might', 1.15, 'mul'), hue=0, icon='might', fn=might),
        # charms sao permanentes e fortes -> tem que doer no bolso (era 30)
        dict(name='Charm', desc='adaptacao p/ um slot', base=150, perm=True, preview=None,
             hue=280, icon='nectar', fn=charm),
        dict(name='Ovo de Amigo', desc='aliado temporario', base=40, perm=False,
             preview=None, hue=270, icon='legs', fn=egg),
    ]
    # o dict do camp e descartado a cada camp; a contagem de compras nao.
    # Game.shop_buys guarda quantas vezes cada oferta foi comprada nesta run
    # (Game._apply_buy escreve nela), e o tier atual entra pelo multiplicador.
    wave = game.rounds.wave
    for it in items:
        it['cost'] = shop_price(it['base'], it['perm'],
                                game.shop_buys.get(it['name'], 0), wave)
    return items


def _camp_drop_off(game, delay):
    """World-y offset of a camp piece as it falls in (negative = still up in
    the air). Ease-IN so it accelerates and SLAMS down."""
    t = (game.time - game.camp['born']) - delay
    if t <= 0:
        return -C.CAMP_DROP_H
    if t >= C.CAMP_DROP_DUR:
        return 0.0
    f = t / C.CAMP_DROP_DUR
    return -C.CAMP_DROP_H * (1.0 - f * f)


def _camp_impact(game, pos, big):
    """The juice when a piece hits the ground: shake + dust + sparks + ring."""
    game.shake(15 if big else 9)
    game.fx.burst(pos, (150, 120, 84), 30 if big else 18, 380)
    game.fx.spark_burst(pos, (224, 202, 150), 18 if big else 11, 400)
    game.fx.ring(pos, (214, 184, 124))
    if big:
        game.fx.ring(pos, (245, 232, 210))
    audio.play('hit', 0.65 if big else 0.45)


def _update_camp_drop(game):
    """Fire the landing juice once, as each piece touches down."""
    elapsed = game.time - game.camp['born']
    if not game.camp['tent_landed'] and elapsed >= game.camp['tent_delay'] + C.CAMP_DROP_DUR:
        game.camp['tent_landed'] = True
        _camp_impact(game, game.camp['tent'], big=True)
    for dr in game.camp['doors']:
        if not dr['landed'] and elapsed >= dr['delay'] + C.CAMP_DROP_DUR:
            dr['landed'] = True
            _camp_impact(game, dr['pos'], big=False)


def _shop_surface(game, it, i, focused):
    """One beetle-shop item, drawn at the origin (see _card_surface)."""
    cw, chh = 176, 132
    s = pygame.Surface((cw, chh), pygame.SRCALPHA)
    box = pygame.Rect(0, 0, cw, chh)
    afford = game.pollen >= it['cost']
    pygame.draw.rect(s, (34, 38, 56) if focused else (28, 32, 46), box, border_radius=12)
    edge = palette.vibrant(it['hue'], 0.8, 1.0) if afford else (70, 72, 92)
    if focused:
        edge = C.COL_WHITE
    pygame.draw.rect(s, edge, box, 4 if focused else (3 if afford else 2),
                     border_radius=12)
    icons.draw(s, it.get('icon'), (cw // 2, 34), 19, palette.vibrant(it['hue'], 0.8, 1.0))
    nm = game.font.render(ui.fit(game.font, it['name'], cw - 16), True, C.COL_WHITE)
    s.blit(nm, (cw // 2 - nm.get_width() // 2, 62))
    ds = game.font.render(ui.fit(game.font, it['desc'], cw - 16), True, (190, 190, 210))
    s.blit(ds, (cw // 2 - ds.get_width() // 2, 84))
    cc = C.COL_POLLEN if afford else (150, 120, 60)
    cost = game.font.render(f"{it['cost']}  polen", True, cc)
    s.blit(cost, (cw // 2 - cost.get_width() // 2, 106))
    s.blit(game.font.render(f"[{i + 1}]", True, edge), (8, 6))
    return s


def _route_surface(game, r, sel, focused):
    rw, rh = 250, 140
    s = pygame.Surface((rw, rh), pygame.SRCALPHA)
    box = pygame.Rect(0, 0, rw, rh)
    bonus_txt = {'cura': 'entra com vida cheia', 'polen': '+25 polen',
                 'carta': 'carta de evolucao'}
    bonus_col = {'cura': (120, 240, 140), 'polen': C.COL_POLLEN,
                 'carta': (150, 130, 245)}
    pygame.draw.rect(s, (28, 32, 50) if focused else (24, 28, 42), box, border_radius=14)
    pygame.draw.rect(s, C.COL_ENEMY if sel else (70, 72, 92), box,
                     4 if focused else (3 if sel else 2), border_radius=14)
    lbl = game.bigfont.render(r['label'], True, C.COL_ENEMY)
    if lbl.get_width() > rw - 16:
        lbl = game.font.render(r['label'], True, C.COL_ENEMY)
    s.blit(lbl, (rw // 2 - lbl.get_width() // 2, 26))
    s.blit(game.font.render("proxima onda", True, (180, 180, 200)), (rw // 2 - 46, 74))
    bt = game.font.render(bonus_txt[r['bonus']], True, bonus_col[r['bonus']])
    s.blit(bt, (rw // 2 - bt.get_width() // 2, 104))
    return s


def _label(game, layer, text, x, y, off, alpha, color=(200, 200, 220)):
    if alpha <= 0.01:
        return
    im = game.font.render(text, True, color)
    if alpha < 1.0:
        im = im.copy()
        im.set_alpha(int(255 * alpha))
    layer.blit(im, (int(x), int(y + off)))


def _draw_camp(game, surf):
    game._veil(surf, (10, 14, 22), 205)
    layer = game._ui_dest(surf)   # a scratch layer only while shaking
    cx = C.WIDTH // 2
    bought = game.pick if (game.pick and game.pick['kind'] == 'shop') else None
    taken = game.pick if (game.pick and game.pick['kind'] == 'route') else None

    # ---- header + pollen purse (rides in with the veil) ---- #
    hoff, halpha = ui.drop_in(game.ui_t, 0, 0.0, C.UI_VEIL, rise=22.0)
    if halpha > 0.01:
        head = pygame.Surface((C.WIDTH, 130), pygame.SRCALPHA)
        t = game.bigfont.render("ACAMPAMENTO", True, C.COL_WHITE)
        head.blit(t, (cx - t.get_width() // 2, 40))
        pol = game.bigfont.render(str(game.pollen), True, C.COL_POLLEN)
        pygame.draw.circle(head, C.COL_POLLEN, (cx - 70, 96), 12)
        pygame.draw.circle(head, (200, 160, 40), (cx - 70, 96), 12, 2)
        head.blit(game.font.render("POLEN", True, (210, 210, 226)), (cx - 54, 88))
        head.blit(pol, (cx + 12, 78))
        if halpha < 1.0:
            head.set_alpha(int(255 * halpha))
        layer.blit(head, (0, int(hoff)))

    # ---- shop (beetle merchant) ---- #
    shop = game.camp['shop']
    cw, gap = 176, 14
    x0 = cx - (len(shop) * cw + (len(shop) - 1) * gap) // 2
    y = 164
    game._shop_rects = []
    soff, salpha = ui.drop_in(game.ui_t, 1, C.UI_STAGGER, C.UI_DROP, rise=40.0)
    _label(game, layer, "LOJA DO BESOURO  (1-5 ou clique)", cx - 300, 138, soff, salpha)
    for i, it in enumerate(shop):
        rect = pygame.Rect(x0 + i * (cw + gap), y, cw, 132)
        game._shop_rects.append(rect)
        if bought is not None and bought['index'] == i:
            continue                      # drawn last, mid-absorption
        focused = (game.camp.get('focus') == 'shop' and game.camp.get('shop_sel') == i)
        off, alpha = ui.drop_in(game.ui_t, 1 + i * 0.4, C.UI_STAGGER, C.UI_DROP,
                                rise=40.0)
        if bought is not None:            # the ones you passed on dim away
            alpha *= 1.0 - clamp(bought['t'] / 0.18, 0, 1) * 0.8
        if focused and alpha > 0.5:
            palette.glow(layer, (rect.centerx, int(rect.centery + off)), 90,
                         palette.vibrant(it['hue'], 0.8, 1.0), 0.3 * alpha)
        src = game._panel(('shop', i, focused, it['cost'], game.pollen >= it['cost']),
                          lambda it=it, i=i, f=focused: _shop_surface(game, it, i, f))
        game._blit_card(layer, src, (rect.centerx, rect.centery + off), 1.0, alpha)
    if game.camp.get('msg') and bought is None and salpha > 0.9:
        m = game.font.render(f"comprado: {game.camp['msg']}", True, (120, 240, 140))
        layer.blit(m, (x0, y + 116))

    # ---- charms loadout ---- #
    p0 = game.players[0]
    coff, calpha = ui.drop_in(game.ui_t, 3, C.UI_STAGGER, C.UI_DROP, rise=40.0)
    game._charm_rects = []
    if calpha > 0.01:
        focus_ch = game.camp.get('focus') == 'charms'
        _label(game, layer, "CHARMS  (setas/controle ou clique p/ equipar)",
               cx - 300, 306, coff, calpha)
        block = pygame.Surface((C.WIDTH, 145), pygame.SRCALPHA)
        # One column per slot, owned charms listed under their own slot header:
        # makes it obvious what a charm replaces, and gives up/down + left/right
        # a real grid to walk (see app.py camp nav).
        sw = 168
        sx0 = cx - (len(C.CHARM_SLOTS) * sw + (len(C.CHARM_SLOTS) - 1) * 12) // 2
        for si, (slot, nm) in enumerate(C.CHARM_SLOTS):
            bx = sx0 + si * (sw + 12)
            box = pygame.Rect(bx, 0, sw, 32)          # block starts at y=328
            cid = p0.charm_slots.get(slot)
            col = charmlib.CHARMS[cid].color if cid else (62, 64, 88)
            pygame.draw.rect(block, (26, 30, 44), box, border_radius=10)
            pygame.draw.rect(block, col, box, 2, border_radius=10)
            lab = charmlib.CHARMS[cid].name if cid else '-'
            txt = ui.fit(game.font, f"{nm}: {lab}", box.width - 16)
            block.blit(game.font.render(txt, True, (218, 218, 232)), (bx + 8, 6))
            owned = [c for c in p0.charms_owned
                     if charmlib.CHARMS[c].slot == slot]
            for ri, ccid in enumerate(owned):
                ch = charmlib.CHARMS[ccid]
                rect = pygame.Rect(bx, 38 + ri * 25, sw, 24)
                game._charm_rects.append((rect.move(0, 328), ccid))
                equipped = (p0.charm_slots.get(slot) == ccid)
                cur = (focus_ch and game.camp.get('charm_col') == si
                       and game.camp.get('charm_row') == ri)
                pygame.draw.rect(block, (38, 44, 64) if cur else (30, 34, 50),
                                 rect, border_radius=7)
                edge = C.COL_WHITE if cur else ch.color
                pygame.draw.rect(block, edge, rect, 3 if (equipped or cur) else 1,
                                 border_radius=7)
                icons.draw(block, ch.icon, (bx + 14, rect.centery), 8, ch.color, glow=False)
                im = game.font.render(ui.fit(game.font, ch.name, sw - 40), True,
                                      (222, 222, 234))
                block.blit(im, (bx + 26, rect.centery - im.get_height() // 2))
        if calpha < 1.0:
            block.set_alpha(int(255 * calpha))
        layer.blit(block, (0, int(328 + coff)))

    # Routes are now physical DOORS in the clearing -- no route panel here.
    game._route_rects = []
    eoff, ealpha = ui.drop_in(game.ui_t, 4, C.UI_STAGGER, C.UI_DROP, rise=40.0)
    if ealpha > 0.01:
        _label(game, layer, "ESC / B: voltar a clareira  ->  atravesse uma porta p/ avancar",
               cx - 300, 512, eoff, ealpha)

    # ---- the item being absorbed, on top of everything ---- #
    if bought is not None:
        pos, scale, alpha = state_levelup._pick_pose(game)
        it = shop[bought['index']]
        src = game._panel(('shop', bought['index'], True, it['cost'],
                           game.pollen >= it['cost']),
                          lambda: _shop_surface(game, it, bought['index'], True))
        palette.glow(layer, (int(pos.x), int(pos.y)), int(100 * scale + 30),
                     bought['color'], 0.30 + 0.30 * (1 - alpha))
        game._blit_card(layer, src, pos, scale, alpha)
    game._ui_fx(layer)
    game._blit_ui(surf, layer)


_DOOR_HUES = (150, 45, 285)          # green (cura) / gold (polen) / purple (carta)
_BONUS_TAG = {'cura': '+ cura', 'polen': '+ polen', 'carta': '+ carta'}


def _near_player(game, pos, r):
    return any(not p.dead and p.pos.distance_to(pos) < r for p in game.players)


def _draw_camp_pois(game, surf):
    """The clearing's furniture, in world space: three route DOORS and the
    beetle's TENT. Both light up and prompt when a player is in reach."""
    cam, z, t = game.cam, game.cam.zoom, game.time
    # ---- doors (routes) ---- #
    for i, dr in enumerate(game.camp['doors']):
        pos = dr['pos']
        if not cam.visible(pos, 220):
            continue
        col = palette.vibrant(_DOOR_HUES[i % 3], 0.7, 1.0)
        off = _camp_drop_off(game, dr['delay'])       # falling in from the sky
        if off < -2:                                 # growing shadow marks the landing
            prog = 1.0 - min(1.0, -off / C.CAMP_DROP_H)
            shadow(surf, cam.w2s(pos), int(34 * z * (0.4 + 0.6 * prog)))
        sp = cam.w2s(pos + Vector2(0, off))
        hot = dr['landed'] and _near_player(game, pos, C.CAMP_DOOR_R * 2.4)
        beat = pulse(t * 3 + i)
        w, h = int(66 * z), int(108 * z)
        rad = int(w * 0.5)
        palette.glow(surf, sp, int(w * (1.5 if hot else 1.05)), col,
                     (0.34 if hot else 0.2) + 0.12 * beat)
        frame = pygame.Rect(sp[0] - w // 2, sp[1] - h, w, h)
        inner = frame.inflate(-int(14 * z), -int(12 * z))
        pygame.draw.rect(surf, (16, 18, 28), inner, border_top_left_radius=rad,
                         border_top_right_radius=rad)
        ew = max(2, int((5 if hot else 4) * z))
        pygame.draw.rect(surf, col, frame, ew, border_top_left_radius=rad,
                         border_top_right_radius=rad)
        pygame.draw.rect(surf, palette.lighten(col, 0.4), frame, max(1, int(2 * z)),
                         border_top_left_radius=rad, border_top_right_radius=rad)
        ui.text(surf, game.font, dr['route']['label'], (sp[0], frame.top - int(30 * z)),
                C.COL_WHITE, align='center')
        ui.text(surf, game.font, _BONUS_TAG[dr['route']['bonus']],
                (sp[0], frame.top - int(13 * z)), palette.lighten(col, 0.35), align='center')
        if hot:
            ui.text(surf, game.font, 'ATRAVESSE', (sp[0], sp[1] + int(8 * z)),
                    C.COL_WHITE, align='center')
    # ---- tent (shop) ---- #
    pos = game.camp['tent']
    if cam.visible(pos, 260):
        off = _camp_drop_off(game, game.camp['tent_delay'])
        if off < -2:
            prog = 1.0 - min(1.0, -off / C.CAMP_DROP_H)
            shadow(surf, cam.w2s(pos), int(64 * z * (0.4 + 0.6 * prog)))
        sp = cam.w2s(pos + Vector2(0, off))
        hot = game.camp['tent_landed'] and _near_player(game, pos, C.CAMP_TENT_R)
        gold = C.COL_POLLEN
        # Issue #25: prefer the PNG asset (assets/props/tent_beetle.png),
        # fall back to the procedural tent drawing if the PNG is missing
        # (stripped build, headless CI, etc.). The PNG is 640x640 -- a
        # full tent+beetle sprite -- so it replaces the entire procedural
        # block (counter + roof + valance + beetle + flag).
        tent_diam = int(160 * z)
        tent_png = assets.icon('tent_beetle', tent_diam)
        if tent_png is not None:
            palette.glow(surf, sp, int(tent_diam * (0.95 if hot else 0.72) * 0.6),
                         gold, (0.3 if hot else 0.17) + 0.1 * pulse(t, 2.4))
            surf.blit(tent_png, (sp[0] - tent_diam // 2, sp[1] - tent_diam // 2))
        else:
            w = int(120 * z)
            palette.glow(surf, sp, int(w * (0.95 if hot else 0.72)), gold,
                         (0.3 if hot else 0.17) + 0.1 * pulse(t, 2.4))
            counter = pygame.Rect(sp[0] - w // 2, sp[1] - int(4 * z), w, int(34 * z))
            pygame.draw.rect(surf, (120, 82, 54), counter, border_radius=int(6 * z))
            pygame.draw.rect(surf, (60, 40, 26), counter, max(1, int(2 * z)),
                             border_radius=int(6 * z))
            roof_h = int(48 * z)
            base_y = sp[1] - int(4 * z)
            left = (sp[0] - w // 2 - int(8 * z), base_y)
            right = (sp[0] + w // 2 + int(8 * z), base_y)
            peak = (sp[0], base_y - roof_h)
            pygame.draw.polygon(surf, (214, 74, 78), [left, right, peak])
            pygame.draw.polygon(surf, C.COL_INK, [left, right, peak], max(1, int(2 * z)))
            # scalloped valance: little triangles hanging under the awning base
            n = 5
            for k in range(n):
                x0 = left[0] + (right[0] - left[0]) * k / n
                x1 = left[0] + (right[0] - left[0]) * (k + 1) / n
                tip = ((x0 + x1) / 2, base_y + int(9 * z))
                shade = (214, 74, 78) if k % 2 == 0 else (245, 232, 210)
                pygame.draw.polygon(surf, shade, [(x0, base_y), (x1, base_y), tip])
            pygame.draw.circle(surf, gold, (sp[0], peak[1] - int(9 * z)), max(2, int(7 * z)))
            pygame.draw.circle(surf, (200, 160, 40), (sp[0], peak[1] - int(9 * z)),
                               max(2, int(7 * z)), max(1, int(2 * z)))
            # the beetle merchant behind the counter
            bc = (sp[0] - int(w * 0.26), base_y + int(6 * z))
            pygame.draw.circle(surf, (74, 62, 88), bc, max(2, int(11 * z)))
            for s in (-1, 1):                       # antennae
                pygame.draw.line(surf, (74, 62, 88), (bc[0], bc[1] - int(8 * z)),
                                 (bc[0] + s * int(7 * z), bc[1] - int(16 * z)),
                                 max(1, int(2 * z)))
        ui.text(surf, game.font, 'LOJA DO BESOURO', (sp[0], sp[1] + int(28 * z)),
                gold, align='center')
        if hot:
            ui.text(surf, game.font, 'ENCOSTE p/ abrir', (sp[0], sp[1] + int(45 * z)),
                    C.COL_WHITE, align='center')


def _draw_camp_field_ui(game, surf):
    """Light HUD while walking the clearing -- at the BOTTOM, so it never
    competes with the doors and their labels up top. Title, hint, pollen."""
    cx, y = C.WIDTH // 2, C.HEIGHT - 92
    ui.text(surf, game.bigfont, "ACAMPAMENTO", (cx, y), C.COL_WHITE, align='center')
    ui.text(surf, game.font,
            "encoste na barraca p/ a loja  -  atravesse uma porta p/ avancar",
            (cx, y + 38), (210, 214, 228), align='center')
    pygame.draw.circle(surf, C.COL_POLLEN, (cx - 54, y + 68), 11)
    pygame.draw.circle(surf, (200, 160, 40), (cx - 54, y + 68), 11, 2)
    ui.text(surf, game.font, "POLEN", (cx - 38, y + 60), (214, 214, 230))
    ui.text(surf, game.bigfont, str(game.pollen), (cx + 16, y + 52), C.COL_POLLEN)
