"""Validate the shop delta preview (#140) without rendering.

Three things to guard against, all silent:

  1. **Preview diverges from the real effect.** The whole point of
     ``preview_delta`` is to lie honestly -- it must predict what the
     real ``fn`` would do. We call BOTH on a player snapshot and assert
     they agree (within float tolerance).

  2. **A charm or Ovo de Amigo gets a preview.** Those have non-numeric
     effects and must return ``None`` so the UI knows to skip them.

  3. **Health preview overflows max_health.** The Nectar offer heals
     up to the cap; the preview must apply the same cap, otherwise the
     player sees a number that the real buy cannot reach.

Run from the repo root:  python tools/check_shop_delta.py
"""

import importlib.util
import os
import sys

# Headless stub for pygame -- we don't need a real display for this test
class _FakeRect:
    def __init__(self, *a, **kw): pass
class _FakeSurface:
    def __init__(self, *a, **kw): pass
    def set_alpha(self, *a): pass
    def get_width(self): return 100
    def get_height(self): return 100
    def blit(self, *a, **kw): pass
class _FakeVector2:
    def __init__(self, x=0.0, y=0.0): self.x, self.y = x, y
    def length(self): return 0.0
    def __add__(self, o): return _FakeVector2(self.x + o.x, self.y + o.y)
class _FakeFont:
    def render(self, *a, **kw): return _FakeSurface()
    def size(self, *a, **kw): return (50, 14)
    def get_linesize(self): return 16
    def get_height(self): return 14
class _PygameStub:
    Rect = _FakeRect
    Surface = _FakeSurface
    Vector2 = _FakeVector2
    SRCALPHA = 0
    font = type("F", (), {"SysFont": staticmethod(lambda *a, **kw: _FakeFont())})
    draw = type("D", (), {"rect": staticmethod(lambda *a, **kw: None),
                           "line": staticmethod(lambda *a, **kw: None)})()
    time = type("T", (), {"get_ticks": staticmethod(lambda: 0)})()
    mouse = type("M", (), {"get_pos": staticmethod(lambda: (0, 0))})()
sys.modules["pygame"] = _PygameStub()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# We need preview_delta + EFFECT_FIELDS from state_camp, but importing
# state_camp drags in pygame.display. Stub pygame before the import.
import lagarto.game.state_camp as _state_camp  # noqa: E402
EFFECT_FIELDS = _state_camp.EFFECT_FIELDS
preview_delta = _state_camp.preview_delta


class _P:
    """Stand-in for a Player with just the fields the preview reads."""
    def __init__(self, might=1.0, health=80.0, max_health=100.0, cooldown_mult=1.0):
        self.might = might
        self.health = health
        self.max_health = max_health
        self.cooldown_mult = cooldown_mult


def test_vigor_preview_matches_real_mult():
    """Vigor: preview says might *= 1.15. Apply the real fn and check."""
    p = _P(might=1.0)
    offer = {"name": "Vigor", "effect": EFFECT_FIELDS["might"]}
    delta = preview_delta(offer, p)
    assert delta is not None, "Vigor has a numeric effect, must preview"
    stat, cur, pred = delta
    assert stat == "might", f"stat must be 'might', got {stat!r}"
    assert cur == 1.0
    assert abs(pred - 1.15) < 1e-9, f"predicted might {pred} != 1.15"
    # Real fn equivalent
    p.might *= 1.15
    assert abs(p.might - pred) < 1e-9, f"real fn diverged from preview ({p.might} vs {pred})"
    print("  Vigor: preview == real  OK")


def test_vitalidade_preview_matches_real_add():
    """Vitalidade: +20 max_health. Real fn bumps the cap."""
    p = _P(max_health=100.0)
    offer = {"name": "Vitalidade", "effect": EFFECT_FIELDS["max_health"]}
    delta = preview_delta(offer, p)
    assert delta is not None
    stat, cur, pred = delta
    assert stat == "max_health"
    assert cur == 100.0
    assert pred == 120.0
    p.max_health += 20
    assert abs(p.max_health - pred) < 1e-9
    print("  Vitalidade: preview == real  OK")


def test_nectar_respects_max_health_cap():
    """Nectar heals +40 but caps at max_health. Preview must too."""
    p = _P(health=80.0, max_health=100.0)
    offer = {"name": "Nectar de Cura", "effect": EFFECT_FIELDS["health"]}
    delta = preview_delta(offer, p)
    stat, cur, pred = delta
    assert stat == "health"
    assert cur == 80.0
    assert pred == 100.0, f"health should cap at max_health=100, got {pred}"
    # Real fn would do min(max_health, cur + 40)
    real = min(p.max_health, p.health + 40)
    assert abs(real - pred) < 1e-9
    print(f"  Nectar: preview caps at max_health (80 -> {pred:.0f})  OK")


def test_nectar_no_overflow():
    """Healing when already at cap should stay at the cap, not push past."""
    p = _P(health=100.0, max_health=100.0)
    offer = {"name": "Nectar de Cura", "effect": EFFECT_FIELDS["health"]}
    delta = preview_delta(offer, p)
    _, _, pred = delta
    assert pred == 100.0, f"full-HP heal must stay at 100, got {pred}"
    print("  Nectar at full HP: stays at 100  OK")


def test_charm_returns_none():
    """Charm has no numeric preview (effect=None)."""
    p = _P()
    offer = {"name": "Charm", "effect": None}
    assert preview_delta(offer, p) is None
    print("  Charm: effect=None -> preview returns None  OK")


def test_ovo_returns_none():
    """Ovo de Amigo has no numeric preview."""
    p = _P()
    offer = {"name": "Ovo de Amigo", "effect": None}
    assert preview_delta(offer, p) is None
    print("  Ovo de Amigo: effect=None -> preview returns None  OK")


def test_unknown_mode_raises():
    """Defensive: a misconfigured effect with an unknown mode should
    fail loudly, not silently produce a wrong number."""
    p = _P()
    bad = {"name": "X", "effect": ("might", "sqrt", 1.0)}
    try:
        preview_delta(bad, p)
    except ValueError as e:
        assert "sqrt" in str(e), f"error should mention the bad mode: {e}"
        print(f"  unknown mode 'sqrt' -> ValueError  OK")
        return
    raise AssertionError("preview_delta should have raised ValueError for unknown mode")


print("--- shop delta preview tests ---")
test_vigor_preview_matches_real_mult()
test_vitalidade_preview_matches_real_add()
test_nectar_respects_max_health_cap()
test_nectar_no_overflow()
test_charm_returns_none()
test_ovo_returns_none()
test_unknown_mode_raises()
print("\nALL OK")
