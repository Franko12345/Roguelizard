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
`lunge`, `hop`, `fly`, `bomber`, `gunner`, `venom`, `lead`, `mortar`, `burrow`,
`grapple`).
_Avoid_: AI, mode.

**Shot**:
`Genome.shot` — how a creature attacks, as data: an **Emitter** Pattern plus
that pattern's **Dials** (`dict(fn=emitter.fan_shot, count=1, …)`). The AI tick
decides when to fire and where to walk; the shot decides what leaves the mouth,
so a species' whole attack arrangement changes from `species.py`.
_Avoid_: attack data, weapon (a Weapon is the player's automatic kind).

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

**Health Sac**:
The fixed 25-HP unit in the player's health row. Its shell stays visible when
empty, so the row shows maximum health; arbitrary health fills the last sac
fractionally. Eight fit per row and rows stop at two. See
[Health HUD](docs/concepts/health-hud.md).
_Avoid_: health segment, heart, pip.

**Weapon**:
An automatic attack the player owns at a level (`Player.weapons[id] = level`).
Each ticks every frame; there are 9 weapons and a cap of 6 equipped. Cards
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

**Deployable**:
Something the player leaves on the ground that acts on its own — a creature
with a position, health and a tick, so it is an `AILizard` and not a new entity
type. Three presentations of the one concept: **Torreta** (fires where it
stands), trap (fires on a trigger), persistent pet (walks). Only the Torreta
exists. See [Deployable](docs/concepts/deployable.md).
_Avoid_: summon, minion, pet (that word is the third cut), placeable.

**Torreta**:
The first Deployable and the only one built. A **Weapon**
(`lagarto/combat/weapons/torreta.py`) that spends its cooldown planting an
`AILizard` of the stationary `turret` kind at the player's own position. It
fires an **Emitter** Pattern from its **Shot**, has hp and dies to enemy
contact, and steals the aggro of what it shoots at — its job is space, not
damage.
_Avoid_: torre, tower, sentinela, and "turret" in prose — that string is only
the `kind` in code.

**Pattern**:
One attack arrangement, as a plain function
`(shooter, game, target, dials) -> None` — a ring of shots, a cone, a rotating
spray, a contact bite. Named by its id (`fan`, `spiral`, `web_trap`). Not a
class, not an "attack object".
_Avoid_: attack, move, ability (all taken).

**Emitter**:
`lagarto/combat/emitter.py` — the one place every Pattern is implemented,
shared by [Boss](docs/concepts/boss.md) and common enemy alike. It never looks
its own tuning up: the caller passes **Dials**. See
[ADR-0012](docs/adr/0012-shared-pattern-emitter.md).
_Avoid_: pattern library, bullet factory, spawner.

**Dials**:
The plain dict of tuning a Pattern reads (`count`, `spread`, `lead`, `mod`, …).
A boss passes its `PATTERNS` row; a common enemy passes its **Shot**. A "new"
attack is usually a new dial set on a pattern that already exists — Massive
Fan, deathroll, Web Dome, `radial_wall` are all dials and no code.
_Avoid_: params, config, tuning dict (say **dials**).

**Projectile**:
Every shot in the game, from one class (`lagarto/combat/projectile.py`).
`hostile=True` hits players, `False` hits creatures. Its body colour encodes
that **side** and nothing else — the firing creature's colour survives only in
the halo, bosses included (see
[ADR-0014](docs/adr/0014-bullet-colour-encodes-side.md)).
_Avoid_: bullet, shot, bala (fine in speech, but the field and the docs say
projectile).

**Slow**:
A timed speed multiplier on a creature (`slow_mul` / `slow_t`), applied only
through `Lizard.apply_slow` — Feromônio, the slow projectile, hostile puddles,
a sting. Strongest source wins, longest timer wins. A [Boss](docs/concepts/boss.md)
has a **slow floor** (`BOSS_SLOW_FLOOR`) and a cut duration, so a stack can
never switch its movement patterns off; nobody else is capped. Distinct from the
contact `clog` brake ([Combat](docs/concepts/combat.md)), which is pressure from
bodies and not a status.
_Avoid_: lentidão, debuff, stun (there is no stun in this game).

**Hook**:
A plain function appended to one of a Projectile's three lists — `on_update`
(movement), `on_hit`, `on_death`. No base class, no registry: a modifier IS the
function. The player stacks hooks (`Game._stack_shot_mods`, counters like
`shot_bounces`); an enemy shot picks **one** movement and stops there
(`emitter._launch`, `dials['mod']`). See
[Projectile](docs/concepts/projectile.md).
_Avoid_: modifier class, behaviour, component, plugin.

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
The dev-only mode behind `--sandbox` (`Game.mode == 'sandbox'`): a real `Game`
with the `RoundManager` auto-spawner frozen, driven by hand through a
left-docked overlay to spawn any entity and watch it in the actual world.
Not a player-facing `Mode`. Launch presets persist in `~/.lagarto/sandbox.json`.
_Avoid_: debug mode, dev mode, test level, test mode, editor.

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
Time _and_ visibility are both required. A common enemy draws its footprint
through the same `rain` drawer a boss uses (`AILizard._draw_mark`), but at full
radius from the first frame — a growing circle understates the danger zone
while it grows.
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

**Capsule**:
The framed panel that holds a player's HUD readouts. Drawn with `ui.panel`;
springs (`CapsuleSpring`) on damage and on value change inside. The HUD's
"massa rigida" — two layers in series with the organs inside. See
[HUD anatomy](docs/concepts/hud-anatomy.md).
_Avoid_: HUD block, panel (the term `panel` is the primitive, not the
metaphor).

**HUD anatomy**:
The metaphor that governs every HUD element: each readout is an organ inside
a framed capsule; the capsule has its own rhythm, the organ has its own. The
four beats of [procedural animation](docs/concepts/procedural-animation.md)
apply to the HUD as well as to the body. See
[HUD anatomy](docs/concepts/hud-anatomy.md) and
[ADR-0015](docs/adr/0015-hud-anatomy.md).
_Avoid_: HUD style, HUD look.

**Organ**:
A single readout inside a capsule — bio bar, gland, bellows, skull,
weapon icon, active item. Each organ has its own faster rhythm; the
capsule holds them.
_Avoid_: HUD element (broader — it includes the capsule).

**Gland**:
A cooldown organ: the silhouette of the body part that performs the
action (dash = leg muscle, tongue = throat sac, whip = coiling tail),
sized by the recharge fraction. Three states — charging,
ready-but-no-energy, ready — are distinct by size, colour and pulse
glow. The cooldown row emits no text; the silhouette is the only signal.
See [HUD anatomy](docs/concepts/hud-anatomy.md) and issue #133.
_Avoid_: dial, ring, cooldown icon.

**TopStack**:
The reservation-based layout for the top-of-screen HUD (score, wave, combo,
banner, boss name, boss bar). Elements call `top.take(h)`; order of draw =
priority.
_Avoid_: HUD (HUD is broader).

**Lingua do corpo**:
The HUD's anatomy metaphor — every readout in the rodape is an organ inside
a capsule. Lives in the two capsules per player, vitais + cooldowns. The
metaphor is enforced by [ADR-0015](docs/adr/0015-hud-anatomy.md) and the rodape
is the only place it applies.
_Avoid_: HUD style, HUD look, HUD theme.

**Lingua do mundo**:
The HUD's second language — the lingua do mundo covers the top-centre
column and the things that aren't the body: the run's score, the wave's
progress, the boss's name, the boss's bar, the friends' count. It is the
default language for the `TopStack` and is **not** anatomy. Ratified by
#134 and [ADR-0016](docs/adr/0016-topo-e-mundo.md).
_Avoid_: HUD chrome, HUD chrome style, HUD chrome language.
