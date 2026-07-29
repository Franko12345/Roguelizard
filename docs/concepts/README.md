# Concepts

One file per concept. Each file introduces the concept, links to the
neighbours that reference it, and points at the ADRs that constrain it.

Prose here uses the canonical term from [`CONTEXT.md`](../../CONTEXT.md).
If a concept file names a word the glossary avoids, one of the two is
wrong.

## Index

### Overview

- [Architecture](./architecture.md) — the `lagarto/` module table
- [Running](./running.md) — how to launch, build, and test
- [Gameloop](./gameloop.md) — the Bullet Heaven loop
- [Game modes](./game-modes.md) — NORMAL vs INFINITO

### Anatomy

- [Genome](./genome.md) — the bag of numbers that defines a creature
- [Spine](./spine.md) — the follow-the-leader physical chain
- [Leg](./leg.md) — two-bone IK with foot planting
- [Parts](./parts.md) — spikes, plates, horns, tail-tip, fins
- [Body plan](./body-plan.md) — centipede (segmented) + kraken (tentacle)
- [Procedural animation](./procedural-animation.md) — the 4-element rule

### Creatures

- [Species](./species.md) — named genome templates
- [Character](./character.md) — playable genomes + exclusive mechanic
- [Champion](./champion.md) — named variant + orthogonal modifier
- [Boss](./boss.md) — FSM + personality + phase transitions
- [AI](./ai.md) — behavior branches
- [Enemy behaviors](./enemy-behaviors.md) — phase-2 species and telegraphs

### Combat

- [Combat](./combat.md) — dash, whip, tongue, soft contact
- [Dodge](./dodge.md) — the two dodge verbs and the fake roll
- [Projectile](./projectile.md) — the one shot class and its three hooks
- [Weapon](./weapon.md) — the 9 automatic attacks
- [Deployable](./deployable.md) — the body you plant: Torreta today
- [Item](./item.md) — actives + mechanic-changing passives
- [Charm](./charm.md) — permanent camp slot
- [Synergy](./synergy.md) — named combos with Synergy Factor
- [Hitbox](./hitbox.md) — whole body + head weak point
- [Damage](./damage.md) — player HP model

### Run

- [Round](./round.md) — themed wave from nests to camp
- [Camp](./camp.md) — walkable clearing with shop + doors
- [Evolution](./evolution.md) — level-up card flow
- [Progression](./progression.md) — meta-DNA save

### UI / Feel

- [UI screens](./ui-screens.md) — level-up / camp entrance + absorption
- [UI legibility](./ui-legibility.md) — text rendering + top stack
- [Health HUD](./health-hud.md) — player, enemy, boss, friend bars
- [Stat grid](./stat-grid.md) — per-player stat column, TAB toggle
- [Juice](./juice.md) — hit-stop, transitions, menu drop-in
- [Icons & audio](./icons-audio.md) — code-generated art and sound

### Input / Runtime

- [Controls](./controls.md) — P1 / P2 / gamepad map
- [Input buffer](./input-buffer.md) — grace window for actions
- [Pause](./pause.md) — the `pause` state
- [Performance](./performance.md) — timestep, caches, perf rules
- [Networking](./networking.md) — coop-only today; wire-ready seams

### Meta

- [Balance](./balance.md) — the two balancing passes

## When you add a concept file

1. Add a `**Term**` block to [`CONTEXT.md`](../../CONTEXT.md) with `_Avoid_`
   synonyms.
2. Write `<slug>.md` here — short. Intro sentence, then the pieces that
   matter, then links out.
3. Update this index.
4. Grep for the word in existing concept docs and link back to yours where
   it's referenced.
- [Sandbox](./sandbox.md) — dev-only debug overlay behind `--sandbox`
