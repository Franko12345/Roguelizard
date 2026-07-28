"""Assert the sandbox store (SB5) actually builds its catalog (#107).

``Sandbox._generate_store`` used to call ``g._roll_shop()``. ``Game`` has no such
method -- the native offers come from ``state_camp._roll_shop(game)``, a module
function taking the game -- so every store path raised AttributeError: the manual
pick, the random-N roll, and the launch preset's ``store`` entry.

This drives all three paths and asserts the catalog comes out as the native
offers plus the wrapped ones, with the camp opened in shop mode and pollen above
any price. The preset path needs its own assertion because ``apply_preset``
swallows exceptions per entry (``_try``), so a crash there is silent.

Run from the repo root:  python tools/check_sandbox_store.py
"""
import os, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
pygame.init()
from lagarto.render import display
from lagarto.core import fonts
from lagarto.game import state_camp
from lagarto.game.loop import Game
from lagarto.input.controllers import make_controllers
from lagarto import sandbox as sb

display.init()
g = Game(1, make_controllers(1, []), fonts.get(16), fonts.get(26), mode='sandbox')
box = sb.Sandbox(g, fonts.get(16), fonts.get(26))

# The bug in one line: the native offers are a module function, not a Game method.
assert not hasattr(g, '_roll_shop'), \
    "Game grew a _roll_shop; the sandbox reads state_camp._roll_shop, fix both"

NATIVE = [it['name'] for it in state_camp._roll_shop(g)]
print(f"native offers ({len(NATIVE)}):", ", ".join(NATIVE))


def assert_store(sources, label):
    """Run one store path and assert the staged catalog is native + wrapped."""
    box.infinite_money = False
    g.pollen = 0
    box._generate_store(sources)
    shop = g.camp['shop']
    names = [it['name'] for it in shop]
    assert names[:len(NATIVE)] == NATIVE, f"{label}: native offers missing, got {names}"
    assert len(shop) == len(NATIVE) + len(sources), \
        f"{label}: {len(shop)} offers, expected {len(NATIVE)} + {len(sources)}"
    for it in shop[len(NATIVE):]:
        assert callable(it['fn']), f"{label}: wrapped offer {it['name']} has no grant"
        assert it['cost'] == sb.SANDBOX_STORE_COST, f"{label}: {it['name']} priced {it['cost']}"
    assert g.camp['mode'] == 'shop', f"{label}: camp did not open in shop mode"
    assert g.pollen >= max(it['cost'] for it in shop), f"{label}: pollen {g.pollen} too low"
    assert box.infinite_money, f"{label}: infinite money never armed"
    assert list(box.store_entries) == list(sources), f"{label}: sources not remembered"
    print(f"{label}: {len(shop)} offers = {len(NATIVE)} native + "
          f"{len(sources)} wrapped ({', '.join(names[len(NATIVE):])})")
    return shop


# 1. manual pick -- one of each purchasable pool, the sorted set the overlay sends
picks = sorted((pool, box._pool_items(pool)[0][0]) for pool, _ in sb.STORE_POOLS)
assert_store(picks, "pick manual")

# 2. random N -- the overlay's other button
rand = box._random_sources(4)
assert len(rand) == 4, "random sources came back short"
assert_store(rand, "aleatorio")

# 3. launch preset -- apply_preset swallows per-entry failures, so assert the result
box.store_entries = []
g.camp = None
box.apply_preset({'store': [[pool, pid] for pool, pid in picks]})
assert g.camp is not None, "preset: the store never staged (apply_preset swallowed it)"
assert len(g.camp['shop']) == len(NATIVE) + len(picks), \
    f"preset: staged {len(g.camp['shop'])} offers, expected {len(NATIVE) + len(picks)}"
assert list(box.store_entries) == picks, "preset: sources not replayed"
print(f"preset de launch: {len(g.camp['shop'])} offers replayed through _generate_store")

# 4. every wrapped offer is a real grant: run each fn the way _apply_buy does
for it in g.camp['shop'][len(NATIVE):]:
    it['fn'](g)
print(f"wrapped grants ran through their real fn: "
      f"{', '.join(it['name'] for it in g.camp['shop'][len(NATIVE):])}")
print("ALL OK")
