# Evolution

The level-up flow: XP → 3 cards → apply mutation. Cards can be stats,
parts, or [Weapons](./weapon.md). Sinergies fire on `apply_mutation`.

Defined in `lagarto/combat/evolution/`.

## Sources of evolution

Two paths add parts to the player [Genome](./genome.md):

- **Eating** a carrier prey grants the part via `species.grants`.
- **Dash-killing** a carrier enemy has a **~12% chance**. Rare on purpose —
  the drop rate is the pacing knob. Sources: spider → +legs (cap 10,
  +speed), spiky → spikes, tank → plates, horned → horns, scorpion →
  sting. See `Player.grant_part` / `game._collisions`.

XP feeds the card flow: `Player.gain_xp` queues `pending_levelups`,
`game.step` enters state `levelup` and shows 3 cards from
`roll_cards`; `game.choose_card` applies via
[UI absorption](./ui-screens.md).

Game states: `play` / `levelup` / `camp` / `pause` / `over` / `victory`.

## Mutations vs Weapons

The card pool mixes:

- **Weapon cards** (`WeaponCard`) — new weapon or `+1` level. Cap 6
  equipped ([VIBORA](./character.md) caps at 2).
- **Passive cards** (`MUTATIONS`) — stats (health, speed, dash, energy,
  regen, XP, tongue, thorns, venom, wings) and parts (spikes/plates/
  horns/legs). The club tail is **charm-only** — see [Charm](./charm.md).

Input handled in `app.py` (1/2/3, arrows + ENTER, click).

## Synergies (`SYNERGIES`)

12 named combos flatten mutations + weapons + items + character into one
tag set via `evolution.owned_tags`. See [Synergy](./synergy.md).

## Off-screen indicator

`game._draw_offscreen` draws arrows on the edge pointing at enemies /
nests off-camera — finds stragglers from a wave.

## Related

- [Genome](./genome.md) — where parts and stats land.
- [Weapon](./weapon.md) — level cap 6, VIBORA cap 2.
- [Synergy](./synergy.md) — how mutations combine.
- [Item](./item.md) — the mechanic-changing sibling of MUTATIONS.
- [UI screens](./ui-screens.md) — the level-up entry/absorption flow.
- [Progression](./progression.md) — meta-DNA on top of run mutations.
