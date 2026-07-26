# Architecture

The `lagarto/` package is one module per responsibility, grouped into
subpackages. Do not collapse back to a single file — see
[ADR-0010](../adr/0010-single-file-per-module.md).

`lizard_game.py` is a launcher: `from lagarto.app import main`.

## `lagarto/core/` — leaves of the import graph

Utilities with no game-side dependencies. Everything imports from here:
`from .core import config as C`, `from .core.mathutil import ...`.
`lagarto/core/__init__.py` is intentionally empty — explicit imports
grep better than re-exports.

| Module | Responsibility |
|---|---|
| `core/config.py` | Constants (window/world, timing, vivid palette, energy costs). Colour/balance dials start here. |
| `core/palette.py` | HSV colour (`vibrant`, `random_in_family`), lighten/darken/mix, and cached additive `glow` (`BLEND_RGB_ADD`) for rim/brilho. Cache quantised — see [ADR-0009](../adr/0009-glow-cache-quantized-keys.md). |
| `core/mathutil.py` | Vector/angle helpers (`math` + `Vector2`, **not numpy** in hot loops). |
| `core/fonts.py` | Picks the best installed font (Noto Sans etc.), cached by size. |
| `core/settings.py` | `~/.lagarto/settings.json` (fullscreen/scale/vsync/volumes). Tolerates corrupted file. |
| `core/registry.py` | Lookup/filter/weighted-roll helper shared by charms, characters, items, mutations, synergies. |

## `lagarto/anim/` — procedural-animation primitives

Springs, oscillators and the body chains built from them.

| Module | Responsibility |
|---|---|
| `anim/anim.py` | Reusable secondary-motion primitives (`SpringDamper`, `Vector2Spring`, `PhaseOscillator`, `Anticipation`). Nothing here reads `Lizard`/`Genome`. |
| `anim/spine.py` | [`Spine`](./spine.md): follow-the-leader chain + `body_polygon`. |
| `anim/leg.py` | [`Leg`](./leg.md): foot-planting + 2-bone IK. |

## `lagarto/audio/` — synthesised SFX + generative music

| Module | Responsibility |
|---|---|
| `audio/engine.py` | Synthesised SFX (numpy) + generative music. See [Icons & Audio](./icons-audio.md). |

## `lagarto/combat/` — weapons, charms, items, projectiles, evolution

| Module | Responsibility |
|---|---|
| `combat/projectile.py` | `Projectile` (spit, web, boss shots). Helpers `spit`/`web`. |
| `combat/charms.py` | [Charms](./charm.md). |
| `combat/items.py` | [Items](./item.md): actives + mechanic-changing passives. |
| `combat/evolution/cards.py` | Level-up hand roller. See [Evolution](./evolution.md). |
| `combat/evolution/mutations.py` | The `MUTATIONS` table (passive level-up cards). |
| `combat/evolution/synergies.py` | `SYNERGIES`, `owned_tags`, `check_synergies`. See [Synergy](./synergy.md). |
| `combat/weapons/base.py` | `Weapon` base class, `_enemies_in`, `Puddle`. |
| `combat/weapons/spit.py` | Cuspe — projectile weapon. |
| `combat/weapons/sting.py` | Ferrão — homing weapon. |
| `combat/weapons/web.py` | Teia — slow-projectile weapon. |
| `combat/weapons/spores.py` | Nuvem de Esporos — damage aura. |
| `combat/weapons/pheromone.py` | Feromônio — slow aura. |
| `combat/weapons/breath.py` | Sopro — knockback aura. |
| `combat/weapons/swarm.py` | Enxame — orbitals. |
| `combat/weapons/acid.py` | Ácido — ground puddles. |

## `lagarto/creatures/` — the body, the player, the AI, species, champions

| Module | Responsibility |
|---|---|
| `creatures/base.py` | `Lizard`: spine + legs + parts + squash & stretch + hit testing + draw. The shared procedural body. |
| `creatures/player.py` | `Player`: input, dash, whip, tongue, weapons, evolution, XP. |
| `creatures/genome.py` | [`Genome`](./genome.md): creature = numbers. |
| `creatures/species.py` | [Species](./species.md): genome templates + metadata. |
| `creatures/characters.py` | [Playable characters](./character.md). |
| `creatures/parts.py` | [Parts](./parts.md) drawing pipeline (`parts.draw_all`). |
| `creatures/ai/__init__.py` | `AILizard` (prey/enemy/friend) + the `BEHAVIORS` dispatch. Deliberate exception to the empty-`__init__` convention. |
| `creatures/ai/chase.py` | Melee-family behaviours (chase, lunge, frog hop). |
| `creatures/ai/ranged.py` | Shooter behaviours (spitter, gunner, venomer). |
| `creatures/ai/fly.py` | Airborne behaviours (flyer, bomber). |
| `creatures/ai/burrow.py` | Centipede dive-and-ambush FSM. |
| `creatures/ai/grapple.py` | Octopus anti-kite grappler. |
| `creatures/ai/posing.py` | Per-state resting posture (the body-language layer). |
| `creatures/champions/base.py` | [Champions](./champion.md): template + `maybe_promote`. |
| `creatures/champions/variants.py` | Named variants (FILHOTE, ALFA, ESPECTRO, …). |
| `creatures/champions/modifiers.py` | Stackable modifiers (BLINDADO, GIGANTE, EXPLOSIVO, DIVISOR). |

## `lagarto/flow/` — rounds, progression, boss

| Module | Responsibility |
|---|---|
| `flow/rounds.py` | [Round](./round.md) manager: themed waves from nests. |
| `flow/progression.py` | [Meta-progression](./progression.md): DNA save file. |
| `flow/boss/ai.py` | [Boss](./boss.md) FSM: intro → approach → windup → attack → recover → phase. |
| `flow/boss/patterns.py` | Attack patterns and per-boss phase kits. |
| `flow/boss/personality.py` | `BossPersonality`: mood → speed / pattern weight / glow / tell length. |
| `flow/boss/telegraph.py` | Per-kind telegraph drawing. |
| `flow/boss/arena.py` | Per-boss arena modifiers (bounds-shrink, screen-tint). |

## `lagarto/game/` — the run loop + per-state modules

`Game` owns world state, spawning, collisions and the fixed-step update;
each `state_*` module is one entry in the dispatch table.

| Module | Responsibility |
|---|---|
| `game/loop.py` | `Game`: world, spawns, waves, projectiles, XP/evolution, HUD, game over. |
| `game/hud.py` | Pure HUD drawing primitives — no game state. |
| `game/menu.py` | Hub: play (1/2), options, controls, bestiary, compendium. |
| `game/state_play.py` | State `play`: live sim step + in-run HUD. |
| `game/state_camp.py` | State `camp`: walkable clearing + beetle tent shop. |
| `game/state_levelup.py` | State `levelup`: card panel + absorption animation. |
| `game/state_pause.py` | State `pause`: overlay menu. |
| `game/state_over.py` | States `over` and `victory`: run-summary screens. |

## `lagarto/input/` — controllers

| Module | Responsibility |
|---|---|
| `input/controllers.py` | Input abstraction: `KeyboardMouseController`, `KeyboardController`, `GamepadController`. |

## `lagarto/render/` — display, UI, icons, fx, camera, perf, assets, outline

| Module | Responsibility |
|---|---|
| `render/display.py` | Fixed logical surface + 1x/2x/3x + fullscreen letterbox; `present()` smoothscales; `to_logical(pos)` maps mouse (essential for clicks). |
| `render/ui.py` | Visual kit: `panel`, `chip`, `list_menu`, `tabs`, `paragraph`, `footer`, `fit`, `Fade`, and `drop_in` (staggered entry — use on every new screen). |
| `render/icons.py` | Procedural icons (weapons/mutations/charms) drawn in code — cards, HUD, shop, charms, compendium. |
| `render/fx.py` | Particles (pool, cap), sparks, rings, floating text, shadows. |
| `render/camera.py` | Follow 1 player or frame 2; screen shake; `w2s`/`s2w`. |
| `render/perf.py` | FPS meter / diagnostics. See [Performance](./performance.md). |
| `render/assets.py` | Optional pixel-art PNG loader with procedural fallback. See [ADR-0003](../adr/0003-zero-assets-with-png-fallback.md). |
| `render/outline.py` | Mask-based outline for legs/tongue (DaFluffyPotato technique). |

## `lagarto/world/` — terrain, collision, pickups

| Module | Responsibility |
|---|---|
| `world/terrain.py` | `World`: biome tiles, water shimmer, flora, culling. |
| `world/collision.py` | Body separation via spatial hash. See [Combat](./combat.md). |
| `world/pickups.py` | `Bug`, `Fruit`, `Egg`. |

## `lagarto/` top level

| Module | Responsibility |
|---|---|
| `app.py` | Window setup + main loop with fixed timestep. |
| `sandbox.py` | The `--sandbox` dev overlay. Top level on purpose: it reaches across every package (creatures, combat, flow, world, render) and belongs to none of them. |

## Related

- [ADR-0010](../adr/0010-single-file-per-module.md) — why the split.
- [Performance](./performance.md) — the fixed-timestep / render decoupling.
- [Sandbox](./sandbox.md) — what `sandbox.py` opens.
