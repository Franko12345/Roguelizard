# Lagarto

Top-down pygame game about a procedurally-animated lizard. Combat is a
bullet-heaven / survivor-like: weapons fire automatically, the player only
positions and dashes. Every visible creature is drawn from numbers — there are
no sprites.

Read this file for the vocabulary the codebase and docs use. Definitions here
are **canonical**: prefer the term listed over any synonym in `_Avoid_`.

Related: [ADR index](./docs/adr/README.md) · [concept docs](./docs/concepts/README.md).

## Language

### Creatures

**Genome**:
The numbers that fully describe a creature (size, leg count, colour, hp, body
plan, behaviour, diet). Every enemy, prey, champion, boss and playable
character is built from a `Genome`.
_Avoid_: stats, blueprint, template.

**Species**:
A named `Genome` template plus metadata (role, xp reward, `grants`, diet).
`species.make()` spawns a randomised variation.
_Avoid_: type, kind, class.

**Plan** (body plan):
`Genome.plan` — the coarse silhouette. Values: `'normal'` (spine + legs),
`'segmented'` (centipede), `'tentacle'` (kraken). Chosen at spawn; forks
`rebuild_body` and `draw`.
_Avoid_: shape, form.

**Behavior**:
`Genome.behavior` — which AI dispatch the creature runs (`chase`, `ranged`,
`lunge`, `hop`, `fly`, `bomber`, `gunner`, `venom`, `burrow`, `grapple`).
_Avoid_: AI, mode.

**Champion**:
A named variant of an enemy species with a visual trait that explains its
ability (e.g. ALFA has antennae because it commands the pack). Rain-World
inspired. Champions can stack an orthogonal **modifier** (BLINDADO, GIGANTE,
EXPLOSIVO, DIVISOR).
_Avoid_: elite, boss, minor boss.

**Boss**:
A large enemy with an FSM (`intro → approach → windup → attack → recover`),
multiple phases, and a personality. Spawns every `BOSS_EVERY` waves. Not a
champion — champions live inside a normal round; bosses gate the round.
_Avoid_: mini-boss (use `champion` instead).

**Character**:
A player-selectable `Genome` template plus one exclusive mechanic (LAGARTO
rerolls, VIBORA weapon cap, COURACADO no-dash, LARVA grows). The player's
colour comes from the slot, not the character.
_Avoid_: class, hero.

### Anatomy

**Spine**:
The follow-the-leader chain of joints that is the physical body. Hit-tests,
legs and eyes read `spine.joints` directly.
_Avoid_: backbone, chain.

**Leg**:
A two-bone IK limb with foot-planting (threshold + arc). In `radial` genomes
(spider) it uses `rest_angle` instead of a partner-based diagonal gait.
_Avoid_: limb, foot.

**Part**:
An additive decoration read from the genome each frame — spikes, plates,
horns, tail-tip (club/sting), fins. Drawn by `parts.draw_all`. Evolving a
part _is_ mutating the genome number for that part.
_Avoid_: piece, appendage.

**Cosmetic Skeleton**:
The draw-only joint positions used for tail overshoot and travelling waves.
Distinct from the physical `Spine` — sim reads spine, draw reads cosmetic.
`_cosmetic_joints()` is the single choke point that returns them.
_Avoid_: display bones, render skeleton.

**Body Plan**:
`Genome.plan`: which anatomy `rebuild_body` and `draw` build. One of
`normal`, `segmented` (centipede), `tentacle` (kraken), `orbital` (the eye),
`fixed` (the wall). A plan changes the DRAWING; the species carries the speed
and the damping, which is why re-skinning a mobile species into `fixed` gives
you a wall that walks.
_Avoid_: body type, morph, shape.

**Oscillator**:
A `PhaseOscillator` on the creature driving one waving part, read via
`parts._osc_offset`. Tuned from the `OSC_PRESETS` table, and clocked from
`creature.wobble` rather than its own accumulator so parts keep the rate they
had and creatures stay out of phase with each other.
_Avoid_: wave, sine, wobbler.

### Combat

**Weapon**:
An automatic attack the player owns at a level (`Player.weapons[id] = level`).
Each ticks every frame; there are 8 weapons and a cap of 6 equipped. Cards
raise level; global stats (Might, Area, Cooldown, Amount) scale every weapon.
_Avoid_: skill, ability.

**Might**:
Global damage multiplier. Read by weapons, dash and whip. Raised by cards and
DNA. Renaming target: keep as **Might** in prose; `might` is the field.
_Avoid_: damage bonus, power.

**Mutation**:
A stat or part card offered at level-up. Lives in `evolution.MUTATIONS`.
Rolled by `roll_cards`. Distinct from **Item**: mutations tweak numbers, items
rewrite a verb.
_Avoid_: perk, buff.

**Item**:
A run-scoped pickup that changes a mechanic (`items.py`). Two kinds: 4
**actives** (E button, charge per kill) and 16 **passives** that rewrite a
verb. Isaac's dividing line — "+10% damage" is a mutation, "shoot swords" is
an item.
_Avoid_: relic, artifact.

**Investida**:
The dash: the damaging dodge. Invulnerable while it runs (`Player.dashing`),
deals `DASH_DAMAGE` on contact, costs 18 energy on a 0.45 s cooldown, and
commits you forward with a velocity impulse. Prose says **Investida**; the code
field is `dash_time`/`dash_cd` and the HUD dial reads DASH — the same
prose/code split as Whip / `whip_t`.
_Avoid_: lunge, charge.

**Rolamento**:
The other dodge (`Player.rolling`): cheap, frequent, **no damage**, and
steerable instead of committed. Same i-frames, from the same guard in
`Player.hurt`. Its animation is the **fake roll** — the joints collapse into a
spinning disc, because a real coil cannot close against the spine's bend limit.
Prose says **Rolamento**; the fields are `roll_time`/`roll_cd`/`roll_f`.
_Avoid_: dodge-roll, esquiva (that word covers both verbs, not this one).

**Charm**:
A permanent slot the player fills at camp. Persists across level-ups within a
run. Costs 150 pollen.
_Avoid_: trinket, accessory.

**Synergy**:
A named combo that fires when a set of tags is present (mutations + weapons +
items + character all tag into one set via `evolution.owned_tags`). Weighted
by the **Synergy Factor** — the roll weight of a card that would complete a
combo is multiplied, so completing sets is meaningfully more likely.
_Avoid_: combo (that word is taken — see below).

**Combo**:
The kill-streak multiplier (`game.combo`). Kills raise it; time-outs decay
it. Score and pollen scale by combo. Do not use "combo" for synergies.
_Avoid_: streak, multiplier.

**Card**:
The choice offered at level-up (`WeaponCard` for weapons, mutation card for
passives). Three are rolled; one is picked. Absorbed by the player's body
before its effect applies — the pick is a physical event, not an instant.
_Avoid_: option, upgrade.

**Ability**:
The single active-item slot on the player (`Player.ability`/`ability_cd`).
Charged by kills, fired on E. Not the same as a Weapon (weapons are
automatic).
_Avoid_: active, ultimate.

### Run structure

**Round**:
The unit of play between camps. `RoundManager` runs a themed wave: enemies
drip from **Nests** via **Spawn Marks** until the budget is spent, then the
round `cleared` state opens the camp.
_Avoid_: wave, level, stage.

**Wave**:
The integer index of the current round (`rounds.wave`). Also loosely the
theme (`enxame`, `cuspidores`, `tanques`, `aranhas`, `invasao`, `toca`).
_Avoid_: round number (say `wave`).

**Nest**:
A destructible POI that emits enemies. Destroying nests cuts the flow. Nests
drop items and pollen.
_Avoid_: spawner.

**Camp**:
The physical clearing between rounds (`state == 'camp'`). Two modes:
`camp['mode'] = 'field'` (walkable) and `'shop'` (menu open). Three doors =
three route choices. The beetle tent is the shop.
_Avoid_: hub, safe room.

**Route**:
A door in the camp. Picking one commits to the next round's theme and its
bonus (heal / pollen / card).
_Avoid_: path, choice.

**Tier**:
The boss slot index (1..N). Wave 5 = tier 1, wave 10 = tier 2, etc. Bosses
are drawn from a `BOSS_TIER_POOLS` list per tier, Isaac-style. The **final**
tier (wave 20 in `normal` mode) is always PRIMORDIAL.
_Avoid_: chapter, floor.

**Mode**:
`normal` ends at the PRIMORDIAL fight on wave `RUN_FINAL_WAVE`. `endless`
unlocks after the first `normal` win and scales forever.
_Avoid_: difficulty (unrelated).

**Arena**:
A `BossArena` on a boss: a `size` play box **centred on the boss** for the
length of the fight, plus a screen `tint`. Centred is the point — a box
anchored to the world origin only shaves the far corners off a 3200x3200 map,
which the player never reaches. A boss with no entry fights in the open world.
_Avoid_: room, chamber, bounds.

**Sandbox**:
The dev-only mode behind `--sandbox`: a real `Game` with the wave machine
frozen, driven by hand through a left-docked overlay to spawn any entity and
watch it in the actual world. Not a player-facing `Mode`.
_Avoid_: debug mode, test level, editor.

### Economy

**Pollen**:
Run-scoped currency. Earned from kills and combo. Spent at the camp shop.
Never persists across runs.
_Avoid_: coins, gold.

**DNA**:
Meta-progression currency. Persisted in `~/.lagarto/save.json`. Credited at
end of run. Spent on `UPGRADES` (permanent stats) and `UNLOCKS` (weapons,
charms, characters entering the pool).
_Avoid_: XP (XP is per-run), currency.

**Unlock**:
A `UNLOCKS` entry that puts a weapon / charm / character into the run's pool.
`cost=None` = achievement-only. Locked things still appear in menus with the
requirement — invisible rewards are not rewards.
_Avoid_: unlock (verb-only in prose is fine; the noun refers to the entry).

### Feel

**Personality**:
`BossPersonality` — mood_speed, per-mood pattern weights, glow-per-mood,
telegraph length. Turns "random pattern" into "chooses based on how it
feels".
_Avoid_: AI mood, character.

**Mood**:
The boss state (`calm`, `agitated`, `enraged`, `frustrated`, `cornered`).
Drives personality outputs. Scales `tail_spring.stiffness` too (calm = loose,
cornered = tense).
_Avoid_: emotion, state.

**Telegraph**:
The pre-attack tell the player reads. Rule of thumb: **draw the footprint,
not just a warning** (the puddle before the shockwave, not a flashing icon).
Time _and_ visibility are both required.
_Avoid_: warning, tell (informal — `tell` is fine in casual speech, but the
noun is `telegraph` in prose and code comments).

**Squat / Anticipation**:
`Lizard.squat_bias` — a multiplier on the squash target that a wind-up sets
to <1 for a frame, decaying back to 1 on its own. Ranged/lunge/hop AIs and
every boss windup use it.
_Avoid_: crouch, prepare.

**Bio bar**:
The organic HUD element (membrane + meniscus + inner glow + flagella) used
for health/energy/xp. Not a rectangle.
_Avoid_: stat bar, gauge.

**TopStack**:
The reservation-based layout for the top-of-screen HUD (score, wave, combo,
banner, boss name, boss bar). Elements call `top.take(h)`; order of draw =
priority.
_Avoid_: HUD (HUD is broader).
