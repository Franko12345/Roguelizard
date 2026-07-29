"""Assert the beetle shop's price model: it survives the camp that raised it
(#105) and it scales with the run's tier (#137).

Two axes, kept orthogonal by storing a purchase COUNT instead of an absolute
price:

* the run's stage -- ``base * rounds.tier_price_mult(wave)``, a step of
  ``SHOP_TIER_STEP`` per tier, so tier 0 / 1 / 2 charge 1.0x / 1.7x / 2.4x;
* the per-item inflation -- ``SHOP_PRICE_MULT_PERM`` (1.45) for a permanent
  upgrade, ``SHOP_PRICE_MULT`` (1.25) for a consumable, raised to the number of
  times that offer was bought this run.

Everything below drives the REAL path (``camp_buy`` -> absorption ->
``_apply_buy``), because the bug behind #105 was that the camp dict is rebuilt
from scratch on every clearing and used to take the raised price with it.
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.render import display
from lagarto.core import fonts, config as C
from lagarto.flow import rounds
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers

display.init()


def new_game():
    return Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='normal')


g = new_game()

NECTAR, VITALITY, VIGOR, CHARM, EGG = 0, 1, 2, 3, 4   # indices into _roll_shop
# the prices the game shipped with, spelled out: tier 0 must stay byte-identical
BASE = {'Nectar de Cura': 12, 'Vitalidade': 28, 'Vigor': 32,
        'Charm': 150, 'Ovo de Amigo': 40}
PERM = {'Nectar de Cura': False, 'Vitalidade': True, 'Vigor': True,
        'Charm': True, 'Ovo de Amigo': False}


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


def expected(name, wave, buys):
    """The price the model owes for an offer, straight from the constants."""
    mult = C.SHOP_PRICE_MULT_PERM if PERM[name] else C.SHOP_PRICE_MULT
    return int(BASE[name] * rounds.tier_price_mult(wave) * mult ** buys)


def opened(game):
    return {it['name']: it['cost'] for it in game.camp['shop']}


# --- the tier curve itself: a step per tier, flat between bosses ------------ #
assert rounds.tier_price_mult(0) == 1.0, "tier 0 must not move the base price"
assert abs(rounds.tier_price_mult(5) - 1.7) < 1e-9, "tier 1 should charge 1.7x"
assert abs(rounds.tier_price_mult(10) - 2.4) < 1e-9, "tier 2 should charge 2.4x"
assert rounds.tier_price_mult(5) == rounds.tier_price_mult(9), \
    "the price must jump on the boss wave and hold until the next one"
print(f"tier mult (step {C.SHOP_TIER_STEP}): "
      + ", ".join(f"t{w // 5}={rounds.tier_price_mult(w):.1f}" for w in (0, 5, 10, 15)))

# --- tier 0 opens exactly at today's prices (early-game regression) --------- #
g._enter_camp()
assert g.rounds.wave == 0, "this run has not started a wave yet; tier must be 0"
assert opened(g) == BASE, f"tier 0 moved: {opened(g)} != {BASE}"
assert {it['name']: it['perm'] for it in g.camp['shop']} == PERM, \
    "the perm flags moved; the recompra multiplier follows them"
print("tier 0 base prices:", ", ".join(f"{n}={c}" for n, c in BASE.items()))

# --- a consumable compounds at 1.25, from the base, inside the same camp ---- #
paid1, after1 = buy(NECTAR)
assert paid1 == BASE['Nectar de Cura'], "first buy should cost the base price"
assert after1 == expected('Nectar de Cura', 0, 1), \
    f"buy 1: expected {expected('Nectar de Cura', 0, 1)}, got {after1}"

paid2, after2 = buy(NECTAR)
assert paid2 == after1, f"buy 2 charged {paid2}, the raised price was {after1}"
assert after2 == expected('Nectar de Cura', 0, 2), \
    f"buy 2: expected {expected('Nectar de Cura', 0, 2)}, got {after2}"
print(f"same camp, 2 buys @ x{C.SHOP_PRICE_MULT}: "
      f"{BASE['Nectar de Cura']} -> {after1} -> {after2}")

# --- the point of #105: a brand new camp must NOT reset the price ----------- #
g._enter_camp()
nectar = g.camp['shop'][NECTAR]
assert nectar['name'] == 'Nectar de Cura', "offer order moved; fix the indices"
assert g.shop_buys['Nectar de Cura'] == 2, "the purchase count died with the camp"
assert nectar['cost'] == after2, f"camp 2 opened at {nectar['cost']}, expected {after2}"
untouched = g.camp['shop'][VIGOR]
assert untouched['cost'] == BASE[untouched['name']], \
    f"{untouched['name']} was never bought but moved to {untouched['cost']}"
print(f"camp 2: Nectar opens at {nectar['cost']} (persisted), "
      f"{untouched['name']} still {untouched['cost']} (never bought)")

paid3, after3 = buy(NECTAR)
assert paid3 == after2, f"camp 2 charged {paid3}, expected the persisted {after2}"
assert after3 == expected('Nectar de Cura', 0, 3), \
    f"camp 2 buy: expected {expected('Nectar de Cura', 0, 3)}, got {after3}"
print(f"camp 2 buy: charged {paid3} -> now {after3}")

# --- a permanent upgrade compounds harder: 1.45 instead of 1.25 ------------- #
vpaid1, vafter1 = buy(VIGOR)
assert vpaid1 == BASE['Vigor'], "Vigor's first buy should cost the base price"
assert vafter1 == expected('Vigor', 0, 1), \
    f"Vigor buy 1: expected {expected('Vigor', 0, 1)}, got {vafter1}"
vpaid2, vafter2 = buy(VIGOR)
assert vpaid2 == vafter1, f"Vigor buy 2 charged {vpaid2}, expected {vafter1}"
assert vafter2 == expected('Vigor', 0, 2), \
    f"Vigor buy 2: expected {expected('Vigor', 0, 2)}, got {vafter2}"
assert C.SHOP_PRICE_MULT_PERM > C.SHOP_PRICE_MULT, \
    "a permanent upgrade has to inflate faster than a consumable"
print(f"permanent @ x{C.SHOP_PRICE_MULT_PERM}: Vigor "
      f"{BASE['Vigor']} -> {vafter1} -> {vafter2}  (Nectar reached {after3} in 3 buys)")

# --- reaching tier 1 and tier 2 multiplies EVERY offer, bought or not ------- #
NBUYS = {'Nectar de Cura': 3, 'Vigor': 2}       # what this run has bought so far
tier0 = opened(g)
for wave in (5, 10):
    g.rounds.wave = wave                        # as if the boss round had landed
    g._enter_camp()
    now = opened(g)
    for name in BASE:
        want = expected(name, wave, NBUYS.get(name, 0))
        assert now[name] == want, f"wave {wave}: {name} is {now[name]}, expected {want}"
        assert now[name] > tier0[name], \
            f"wave {wave}: {name} did not move off its tier-0 price {tier0[name]}"
    print(f"wave {wave} (tier {wave // 5}, x{rounds.tier_price_mult(wave):.1f}): "
          + ", ".join(f"{n}={c}" for n, c in now.items()))

# a buy made inside tier 2 compounds on top of the tier multiplier
tpaid, tafter = buy(VIGOR)
assert tpaid == expected('Vigor', 10, 2), f"tier 2 charged {tpaid} for Vigor"
assert tafter == expected('Vigor', 10, 3), \
    f"tier 2 buy: expected {expected('Vigor', 10, 3)}, got {tafter}"
print(f"tier 2 Vigor buy: charged {tpaid} -> now {tafter}")

# --- and the whole thing is per-RUN: a fresh Game starts clean -------------- #
g2 = new_game()
g2._enter_camp()
assert g2.shop_buys == {}, "the purchase count leaked across runs"
assert opened(g2) == BASE, f"prices leaked across runs: {opened(g2)}"
print("new run: prices back to base")

# the price table a clean run sees at each tier, spelled out (spec plans/05)
for wave, table in ((5, {'Nectar de Cura': 20, 'Vitalidade': 47, 'Vigor': 54,
                         'Charm': 255, 'Ovo de Amigo': 68}),
                    (10, {'Nectar de Cura': 28, 'Vitalidade': 67, 'Vigor': 76,
                          'Charm': 360, 'Ovo de Amigo': 96})):
    g2.rounds.wave = wave
    g2._enter_camp()
    assert opened(g2) == table, f"clean run at wave {wave}: {opened(g2)} != {table}"
    print(f"clean run, tier {wave // 5}: "
          + ", ".join(f"{n}={c}" for n, c in table.items()))

# --- the 'polen' route bonus rides the same tier multiplier ----------------- #
for wave, want in ((0, 25), (5, 42), (10, 60)):
    g3 = new_game()
    g3.rounds.wave = wave
    g3._enter_camp()
    g3.camp['routes'][0]['bonus'] = 'polen'
    g3.pollen = 0
    g3._apply_route(0)
    assert g3.pollen == want, f"wave {wave}: polen route gave {g3.pollen}, expected {want}"
print("polen route bonus by tier: 25 / 42 / 60")
print("ALL OK")
