# Triage Decision — Orphan Boss Patterns (issue #14)

Status: **decision recorded 2026-07-26**. Issue #14 moves from
`needs-triage` to `ready-for-agent` once the boss tickets below pick up
their respective patterns.

Related: [issue #14][i14], [Boss patterns](../../lagarto/flow/boss/patterns.py),
[Boss concepts](../concepts/boss.md), [Enemy behaviors](../concepts/enemy-behaviors.md),
[Boss tickets](#boss-tickets-that-will-consume-the-patterns).

[i14]: https://github.com/Franko12345/Roguelizard/issues/14

## The three orphans

`flow/boss/patterns.py` has 18 patterns, all of which fire. The original
issue text asked for three more that **no boss currently uses** and that
**no authored boss in `plans/03_chefes_descricoes.md` explicitly requests**:

| Pattern | Spec | Origin |
|---------|------|--------|
| `minefield` | N mines on the floor, arm after 0.5s, pulsing circles mark radius | inspired by Mine Flayer |
| `gravity_well` | pulls the player to a point for 1.5s, vortex telegraph with arrows | inspired by Lich phase 3 |
| `teleport_strike` | boss vanishes, growing shadow marks destination, reappears and attacks | inspired by Mine Flayer / Isaac |

The repo convention (T14 verified) is that every entry in `PATTERNS` is
sorted into at least one boss phase kit — speculative patterns rot.

## Decision: Option (1) — assign each to an upcoming authored boss

The triage offered three options. (2) "save for a future boss" and (3)
"discard" both leave the pattern unbuilt until another ticket asks for
it. (1) "assign to an existing boss" is cleaner here because the three
in-flight boss tickets (#73, #74, #75) describe bosses whose authored
designs naturally fit each orphan:

| Pattern | Assigned boss | Why it fits the authored design |
|---------|---------------|---------------------------------|
| `gravity_well` | **Olho-Sísmico** (#73) | The eye is a fixed orbital; a gravity well is the "the eye pulls you toward it" fantasy the design implies. Adds a control pattern to a kit that's otherwise all projectiles. |
| `minefield` | **A Muralha** (#74) | The corridor arena (700×500, fire on the left pushes you right) is already a positioning puzzle; mines on the floor are the obvious second pressure layer to match the "you cannot pass" fantasy. |
| `teleport_strike` | **ANKH** (#75) | ANKH's phase transitions already dissolve and reform the body. A teleport-strike is the *in-phase* version of that fantasy: mid-phase, she vanishes and reappears on top of you. Fits the "memories of previous bosses" theme (this is the Mine Flayer's move). |

This keeps every entry in `PATTERNS` fired by some boss, preserves the
T14 invariant, and gives each orphan a clear home without inventing new
bosses.

## How the patterns are picked up

When implementing #73 / #74 / #75, the boss's phase kit simply lists
the new pattern id alongside its existing ones, e.g. for ANKH:

```python
def ankh_phases():
    return [
        # Phase 1 — O Caçador (agile lizard form)
        dict(hp_frac=1.00, patterns=['charge', 'pincha', 'swipe'], cd_mul=1.0),
        # Phase 2 — O Tanque (large plated form)
        dict(hp_frac=0.75, patterns=['radial', 'shockwave', 'summon'], cd_mul=0.95),
        # Phase 3 — O Tentáculo (spectral Kraken form)
        dict(hp_frac=0.50, patterns=['grapple', 'arms_rain', 'spiral'], cd_mul=0.85),
        # Phase 4 — A Eterna (all previous, plus the teleport-strike memory)
        dict(hp_frac=0.25,
             patterns=['charge', 'radial', 'grapple', 'teleport_strike'], cd_mul=0.6),
    ]
```

The pattern itself (the `def teleport_strike(boss, game, target)` function
plus its `PATTERNS` entry) is implemented **as part of the consuming
boss ticket**, not as a standalone change — that's how the four patterns
called out in the issue body (`laser_sweep`, `beam_barrage`,
`bounce_shot`, `creep_wave`) were already distributed across #73 and
#74.

## Implementation checklist (per pattern)

When the consuming boss ticket implements the pattern:

- [ ] Telegraph drawn on the floor for **≥ 27 frames (0.45s @ 60Hz)** before activation. See [Enemy behaviors](../concepts/enemy-behaviors.md).
- [ ] Pattern is added to `PATTERNS` with a `windup` ≥ 0.45 and a `telegraph` kind.
- [ ] At least one boss phase kit references the new id (no orphan entries).
- [ ] `--smoke 90` green.
- [ ] Cross-check against neighbors: `minefield` vs `web_dome` (overlapping floor hazards); `gravity_well` vs `grapple` (both displace the player); `teleport_strike` vs `burrow` (both vanish/reappear) — make sure the boss using them has a clear visual contrast.

## Boss tickets that will consume the patterns

- #73 — Olho-Sísmico → consumes `gravity_well`
- #74 — A Muralha → consumes `minefield`
- #75 — ANKH → consumes `teleport_strike`

Once those three tickets ship, this issue can be closed as
"distributed, not discarded".
