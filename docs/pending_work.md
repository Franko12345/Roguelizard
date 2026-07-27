# Pending Work — From Plans

> **LEGADO.** Este arquivo e o registro historico dos planos ANTES do
> refactor T1-T16; os caminhos `lagarto/*.py` que ele cita sao os antigos,
> de proposito, para o texto continuar batendo com a decisao da epoca. Os
> caminhos vivos estao em [architecture.md](concepts/architecture.md).
> `tools/check_doc_paths.py` pula este arquivo por isso.

> **Legacy:** This file was extracted from `plans/` on 2026-07-21. Its items
> have since been promoted to GitHub Issues. Kept for historical context only;
> paths may be stale.

Issues extracted from `plans/` — not yet implemented as of 2026-07-21.

---

## Animation System (plans/01 + 04)

### Easy — only instantiate classes that already exist in `anim.py`

**[A1] Instanciar `PhaseOscillator` — eliminar `math.sin` raw em parts/weapons/lizard**

`anim.PhaseOscillator` exists with 0 instances. There are 11 ad-hoc `math.sin(creature.wobble * X + i * Y) * Z` calls in `parts.py`, `weapons.py`, and `lizard.py` with no configurable frequency/amplitude/phase_gap.

Targets:

| Part | File | speed | amplitude | phase_gap |
|------|------|-------|-----------|-----------|
| Spikes | parts.py | 6 | 0.20 | 1.0 |
| Horns sway | parts.py | 5 | 0.15 | 0.8 |
| Fins | parts.py | 7 | 0.25 | 0.6 |
| Antennae | parts.py | 4 | 0.18 | 1.2 |
| Wings | parts.py / weapons.py | 12 | 0.08 | 0.5 |
| Spore sacs | parts.py | 3 | 0.12 | 1.5 |
| Tentacle wave | lizard.py | 5 | 0.30 | 0.8 |
| Tail ripple | lizard.py | 2.2 | auto | 0.9 |

Each `Lizard` holds a `part_oscillators: dict` initialized in `rebuild_body()`.  
Files: `anim.py`, `parts.py`, `weapons.py`, `lizard.py:350`  
Effort: ~1h

---

**[A2] Instanciar `Anticipation` para timers de IA e ações do player**

`anim.Anticipation` exists with 0 instances. All wind-ups use raw floats (`shoot_charge`, `lunge_t`, `grapple_t`). Player dash, tongue, and whip have no wind-up at all.

AI replacements:

| Raw timer | Action | File | Line ~ |
|-----------|--------|------|--------|
| `shoot_charge` | ranged shot | lizard.py | 1550 |
| `lunge_t` | spider lunge | lizard.py | 1480 |
| `grapple_t` | octopus grapple | lizard.py | 1620 |

Player additions:

| Action | Wind-up | Visual |
|--------|---------|--------|
| Dash | 0.08s | squash horizontal + dust particle |
| Tongue | 0.10s | mouth opens slightly |
| Whip | 0.06s | tail tenses before sweeping |

Files: `anim.py`, `lizard.py:1446-1679` (AILizard dispatch), Player dash/tongue/whip  
Effort: ~1h

---

**[A3] `SpringDamper` 1D para placas, ângulo de chifres e pupilas**

`anim.SpringDamper` (1D) exists with 0 instances. Plates, horns, and pupils are static.

| Part | What springs | Stiffness | Damping | Effect |
|------|-------------|-----------|---------|--------|
| Plates | tilt angle | 14 | 0.80 | tilts on acceleration, returns smooth |
| Horns | angle relative to body | 16 | 0.85 | sways on turn, stiff like bone |
| Pupil | x/y offset inside eye | 8 | 0.70 | tracks target with natural lag |

Lives in `Lizard.spring_1d: dict`, updated in `update_secondary_springs()`.  
Files: `anim.py:12-30`, `parts.py` (`draw_plates`, `draw_horns`, `draw_eye`), `lizard.py:355`  
Effort: ~30min

---

### Medium

**[A4] Spring follow-through pós-whip e pós-tongue**

After whip swing ends, tail should oscillate for ~0.2s (follow-through). After tongue retracts, tip should snap with a lash. Both use existing `Vector2Spring`.

Files: `lizard.py` (whip: ~1051-1098, tongue: ~1185-1194)  
Effort: ~1h

---

**[A5] Spring chain na cauda (N springs em vez de 1)**

Current tail uses 1 `Vector2Spring` (`tail_spring`). Replace with a chain of N springs (stiffness 12 → 6 base-to-tip), matching the plan in `plans/01 §3`:

```python
# lizard.py — replace tail_spring with:
self.tail_springs = [
    Vector2Spring(stiffness=12 - i * 0.8, damping=0.80)
    for i in range(n_tail_springs)  # 4-6 springs
]
```

Effect: natural overshoot cascade when creature stops; tail "whips" on sharp turns.  
Files: `lizard.py`, `anim.py`  
Effort: ~1h

---

**[A6] Wind-up no dash (squash) e na língua (boca abre)**

- **Dash wind-up** (0.08s): horizontal squash `squash → 0.7` + dust particles at feet before launch
- **Tongue wind-up** (0.10s): jaw opens slightly (`head_dir_spring` target offset) before shoot

Both gate the actual action through `Anticipation` (see A2) but need the visual component here.  
Files: `lizard.py` (Player dash ~925, tongue ~1185)  
Effort: ~1h

---

### Heavy

**[A7] Ground adaptation — raycast de pé, pelvis spring, inclinação em rampa**

Feet currently float on slopes. Three sub-tasks:

1. **Foot raycast**: `world.ground_y_at(x)` → clamp foot target to terrain y when diff > 8px
2. **Pelvis spring**: `Vector2Spring` on pelvis height, target = avg foot y + body height/2
3. **Slope lean**: compute ground angle between 2 contact points → tilt spine

Files: `leg.py` (no changes yet), `lizard.py`, `world.py` (needs `ground_y_at`)  
Effort: ~3h

---

**[A8] Procedural posing por estado de IA (hunting/alert/flee/attack)**

Posing library keyed by AI state. Each pose modifies spine joint offsets:

| State | Posture | Tail | Head |
|-------|---------|------|------|
| Idle (grazing) | low, relaxed | dragging | level |
| Alert (spotted player) | upright, tense | raised | tracks target |
| Hunting | crouched, focused | rigid | tilted forward |
| Hurt | curved, slow | dragging | low |
| Attacking | arched | raised | open (mouth) |

`ProceduralPose.update(dt)` → `apply(spine)` called after `resolve()`, before draw.  
Files: `lizard.py` (AILizard dispatch ~1300-1680)  
Effort: ~3h

---

**[A9] Esqueleto cosmético full-body (`cosmetics.py`)**

Current cosmetic layer only covers last 4 tail joints via `_cosmetic_joints()`. Full plan (see `plans/01 §10`):

- `CosmeticSkeleton`: 32 interpolated points, each with a `Vector2Spring`
- Follows sim-skeleton (lerp between joints + spring lag)
- Used by `body_polygon_smooth()`, leg draw positions, part draw positions
- Sim skeleton (hitbox, leg IK) unchanged

New file: `lagarto/cosmetics.py`  
Files: `lizard.py`, `spine.py`, `cosmetics.py` (new)  
Effort: ~5h

---

## Boss System (plans/02 + 03 + 04)

**[B1] Telegraph corporal no boss durante windup**

Current telegraph is HUD-only (circles/lines drawn by `boss.py:_draw_telegraph`). Missing body-level tells:

- Glow in mouth when charging a ranged attack
- Tail rises when charging tail slam
- Crests/spines erect when transitioning to `enraged` mood
- Body pose change (arch) matching `_apply_mood_pose`

Ties into A8 (procedural posing).  
Files: `lagarto/boss.py` (~623-685)  
Effort: ~2h

---

**[B2] Patterns faltantes em `boss.py`**

> **Triage decided 2026-07-26 — see [docs/agents/triage-issue-14.md](../agents/triage-issue-14.md).**
>
> The original list of 7 missing patterns has been distributed across the
> three upcoming boss tickets:
>
> - `laser_sweep` → #73 (Olho-Sísmico's `gaze`)
> - `beam_barrage` → #74 (A Muralha's 3-eye `eye_laser`)
> - `bounce_shot` → #74 (A Muralha's `bouncing_bullets`)
> - `creep_wave` → #74 (A Muralha's phase-2 advancing floor fire)
> - `gravity_well` → #73 (Olho-Sísmico — eye pulls player toward it)
> - `minefield` → #74 (A Muralha — corridor floor mines)
> - `teleport_strike` → #75 (ANKH — in-phase dissolve/reform attack)
>
> Patterns are implemented **as part of** the consuming boss ticket, not
> standalone. Issue #14 closes once #73 / #74 / #75 ship.

Currently implemented: `radial_burst`, `fan_shot`, `aimed_barrage`, `summon_adds`, `shockwave`, `spiral_pattern`, `charge_attack` (7 total).

Still missing from `plans/02 §7` (all assigned per the triage doc above):

| Pattern | Description | Telegraph | Inspiration | Owner |
|---------|-------------|-----------|-------------|-------|
| `laser_sweep` | laser sweeps an arc | filling cone | Beholster, Bullet King | #73 |
| `bounce_shot` | projectile ricochets N times | dashed line predicting bounces | Wallmonger | #74 |
| `minefield` | places mines on ground | pulsing circles | Mine Flayer | #74 |
| `gravity_well` | pulls player to a point | vortex with arrows | Lich phase 3 | #73 |
| `creep_wave` | advancing puddle of damage | liquid creeping | Peep | #74 |
| `beam_barrage` | telegraphed laser barrage | ground markers | High Dragun | #74 |
| `teleport_strike` | vanishes, reappears, attacks | shadow at destination | Mine Flayer, Isaac | #75 |

Files: `lagarto/combat/emitter.py` (the function) + `lagarto/flow/boss/patterns.py`
(one `PATTERNS` row of dials) — see [ADR-0012](adr/0012-shared-pattern-emitter.md)
Effort: ~3h (folded into the consuming boss tickets)

---

**[B3] Novos planos de corpo para chefes**

From `plans/03` — 4 new `genome.plan` values needed for upcoming bosses:

| Plan | Boss | Description |
|------|------|-------------|
| `winged` | Terror Alado (wave 8) | small body, large spring wings, stinger tail, flyer collision skip |
| `orbital` | Olho-Sísmico (wave 12) | spherical body, 6 thin tentacles with spring/wave, large eye with dilating iris |
| `wall` | A Muralha (wave 15) | fixed structure occupying one arena side; mouth, eye array, hands |
| `crystal` | Serpente de Cristal (wave 13) | segmented (like centipede) but floating; prismatic refraction on ground |

Each plan needs `rebuild_body`, `draw`, and behavior/telegraph hooks.  
Files: `lagarto/genome.py` (__slots__), `lagarto/lizard.py` (rebuild/draw dispatch), new species in `species.py`  
Effort: ~2h per plan (~8h total)

---

**[B4] Personalidades para chefes 4-10**

`boss.py` has personalities for: `king`, `centipede`, `kraken`, `primordial`. Missing:

| Boss | Wave | Missing personality fn |
|------|------|------------------------|
| Terror Alado | 8 | `terror_personality()` |
| Mãe-Escaravelho | 9 | `beetle_personality()` |
| Kraken-Mor | 10 | already done |
| Aranha-Rei | 11 | `spider_king_personality()` |
| Olho-Sísmico | 12 | `eye_personality()` |
| Serpente de Cristal | 13 | `crystal_personality()` |
| A Muralha | 15 | `wall_personality()` |
| ANKH | 18 | `ankh_personality()` — 4 distinct phase personas |

Each `BossPersonality` defines `mood_speed`, `pattern_weights`, `mood_colors`, `tell_mult`.  
Files: `lagarto/boss.py` (~332-418)  
Effort: ~1h

---

**[B5] Damping/weight para as 15 espécies restantes**

`genome.angular_damping`, `linear_damping`, `weight` are set in only 3 of 18 species (`tank`, `spider`, `octopus`). Reference table from `plans/01 §7`:

| Creature | angular_damping | linear_damping | weight |
|----------|----------------|----------------|--------|
| Filhote (champ) | 0.10 | 0.10 | 0.5 |
| Normal (default) | 0.30 | 0.30 | 1.0 |
| Tank | 0.60 ✅ | 0.50 ✅ | 2.5 ✅ |
| Octopus | 0.70 ✅ | 0.60 ✅ | 3.0 ✅ |
| Spider | 0.15 ✅ | 0.20 ✅ | 0.8 ✅ |
| Horned | 0.35 | 0.30 | 1.2 |
| Spiky | 0.25 | 0.25 | 1.0 |
| Snake | 0.20 | 0.15 | 0.7 |
| Runner | 0.10 | 0.10 | 0.6 |
| Frog | 0.40 | 0.35 | 1.5 |
| Centipede | 0.30 | 0.20 | 1.8 |
| Wasp/bomber | 0.10 | 0.10 | 0.5 |
| Gunner | 0.25 | 0.20 | 0.9 |
| Venomer | 0.30 | 0.25 | 1.0 |
| Scorpion | 0.40 | 0.35 | 1.4 |

Files: `lagarto/species.py`  
Effort: ~30min

---

## Visual (plan/05)

**[V1] Outline via mask para pernas e língua (`pygame.mask`)**

From `plans/05_outline_mask.md`. Body already has `outline_smooth()` (vectorial polygon, keep as-is). Legs and tongue have no outline — visual inconsistency, especially at `PIXEL_SCALE=1`.

Technique (DaFluffyPotato):
```python
mask = pygame.mask.from_surface(surf, threshold=127)
pts = mask.outline()
for i in range(len(pts)):
    pygame.draw.line(target, color, pts[i-1], pts[i])
```

Helper `outline_from_surf(surf, color, thickness=1)` → returns new surface with outline baked in. Apply in `leg.py` (draw) and `lizard.py._draw_tongue`.

Performance: each leg/tongue is 20-40px surface → ~7 calls/creature → <0.1ms for 20 creatures (estimate; measure with `--smoke 400`).

Risk: `mask.outline()` returns only first connected component (legs and tongue are single-connected → OK). Pixel-staircase is expected/desired at low res.

Files: `lagarto/leg.py`, `lagarto/lizard.py` (`_draw_tongue`), new `lagarto/outline.py` or `utils.py`  
Effort: ~1h

---

## Refactor

**[R1] Eliminar duplicação do pipeline em `menu.py`**

`menu.py` replicates ~70% of `Lizard.integrate()` in 3 separate places (`_step_backdrop`, `_preview_step`, character select). This is the same bug pattern that `update_secondary_springs()` was created to prevent — if physics changes, 3 menu locations need updating manually.

Consolidate into a single `step_creature_for_display(creature, dt)` helper that calls the canonical `integrate()` → `update_secondary_springs()` path.

Files: `lagarto/menu.py`  
Effort: ~1h

---

## Summary Table

| ID | Title | Effort | Priority |
|----|-------|--------|----------|
| A1 | PhaseOscillator — replace raw sin | 1h | Easy |
| A2 | Anticipation — replace raw timers | 1h | Easy |
| A3 | SpringDamper 1D — plates/horns/pupils | 30min | Easy |
| A4 | Spring follow-through pós-whip/tongue | 1h | Medium |
| A5 | Spring chain in tail (N springs) | 1h | Medium |
| A6 | Wind-up visuals for dash + tongue | 1h | Medium |
| A7 | Ground adaptation — foot raycast + pelvis | 3h | Heavy |
| A8 | Procedural posing by AI state | 3h | Heavy |
| A9 | Full-body cosmetic skeleton | 5h | Heavy |
| B1 | Boss body telegraph during windup | 2h | Medium |
| B2 | 7 missing attack patterns in boss.py | 3h | Medium |
| B3 | 4 new body plans (winged/orbital/wall/crystal) | 8h | Heavy |
| B4 | Boss personalities for bosses 4-10 | 1h | Easy |
| B5 | Damping/weight for 15 remaining species | 30min | Easy |
| V1 | Outline via mask for legs + tongue | 1h | Easy |
| R1 | Deduplicate menu.py pipeline | 1h | Easy |
