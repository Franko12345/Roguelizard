"""Assert the beetle shop's prices survive the camp they were raised in (#105).

The camp dict is rebuilt from scratch every time you enter a clearing, so the
price bump that ``_apply_buy`` writes used to die with it -- cheap Nectar
forever. This drives the REAL path (``camp_buy`` -> absorption -> ``_apply_buy``)
across two camps and asserts the second camp opens with the raised price, and
that two buys compound by SHOP_PRICE_MULT each.
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers

display.init()
g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='normal')

NECTAR, VIGOR = 0, 2          # indices into _roll_shop's offer list


def buy(idx):
    """One purchase through the real flow; returns (price paid, new price)."""
    g.ui_t = C.UI_READY       # skip the clearing's drop-in (ui_busy blocks input)
    g.pollen = 10_000
    paid = g.camp['shop'][idx]['cost']
    g.camp_buy(idx)
    assert g.pick is not None, "camp_buy did not start the absorption"
    for _ in range(1200):
        g.step(C.DT)
        if g.pick is None:
            break
    assert g.pick is None, "the purchase never landed (pick never finished)"
    assert g.pollen == 10_000 - paid, f"paid {10_000 - g.pollen}, price was {paid}"
    return paid, g.camp['shop'][idx]['cost']


g._enter_camp()
base = {it['name']: it['cost'] for it in g.camp['shop']}
print("base prices:", ", ".join(f"{n}={c}" for n, c in base.items()))

paid1, after1 = buy(NECTAR)
expect1 = int(base['Nectar de Cura'] * C.SHOP_PRICE_MULT)
assert paid1 == base['Nectar de Cura'], "first buy should cost the base price"
assert after1 == expect1, f"buy 1: expected {expect1}, got {after1}"

paid2, after2 = buy(NECTAR)
expect2 = int(expect1 * C.SHOP_PRICE_MULT)
assert paid2 == expect1, f"buy 2 charged {paid2}, the raised price was {expect1}"
assert after2 == expect2, f"buy 2: expected {expect2}, got {after2}"
print(f"same camp, 2 buys @ x{C.SHOP_PRICE_MULT}: "
      f"{base['Nectar de Cura']} -> {after1} -> {after2}")

# --- the point of the ticket: a brand new camp must NOT reset the price ---- #
g._enter_camp()
nectar = g.camp['shop'][NECTAR]
assert nectar['name'] == 'Nectar de Cura', "offer order moved; fix the indices"
assert nectar['cost'] > base['Nectar de Cura'], \
    f"camp 2 reset Nectar to {nectar['cost']} (base {base['Nectar de Cura']})"
assert nectar['cost'] == after2, f"camp 2 opened at {nectar['cost']}, expected {after2}"
untouched = g.camp['shop'][VIGOR]
assert untouched['cost'] == base[untouched['name']], \
    f"{untouched['name']} was never bought but moved to {untouched['cost']}"
print(f"camp 2: Nectar opens at {nectar['cost']} (persisted), "
      f"{untouched['name']} still {untouched['cost']} (never bought)")

# a third buy compounds on top of the persisted price, in the new camp
paid3, after3 = buy(NECTAR)
assert paid3 == after2, f"camp 2 charged {paid3}, expected the persisted {after2}"
assert after3 == int(after2 * C.SHOP_PRICE_MULT)
print(f"camp 2 buy: charged {paid3} -> now {after3}")

# and the whole thing is per-RUN: a fresh Game starts clean
g2 = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='normal')
g2._enter_camp()
assert g2.camp['shop'][NECTAR]['cost'] == base['Nectar de Cura'], \
    "prices leaked across runs"
print("new run: prices back to base")
print("ALL OK")
