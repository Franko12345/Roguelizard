# A bullet's colour encodes the side, not the creature that fired it

**Context.** Every shot took its colour from `creature.color`, which comes from
the species hue — and the species cover the whole wheel (spitter 150, gunner
200, venomer 100, scorpion 18, spider 265). The player's own shots take the
weapon's hue, which covers the same wheel. At ~100 bullets on screen with an
additive halo under each one, there was **no visual rule that answered "what
hurts me"**. You had to trace each streak back to its source.

**Decision.** The bullet body is fixed per side. Hostile is a hot-white core in
a near-black rim; friendly is the player's green. The creature's own colour
survives in exactly one place, the additive halo of `palette.glow`. This holds
for **bosses too, with no exception** — the rule that has an exception dies at
the moment it matters most, which is the fight with the most bullets in it.

**Why.** This is a partial, deliberate override of
[ADR-0001](./0001-genome-is-the-creature.md): the creature *is* its genome, and
its colour is part of that genome, but the projectile is not the creature. It is
information the player has ~200 ms to act on. Legibility of the threat outranks
identity of the shooter, and the halo is enough identity to keep a spitter's
volley looking like a spitter's.

**Consequences.**

- Anything that changes which side a shot is on must repaint it. The whip's
  Contragolpe (`Player._whip_reflect`) flips `pr.hostile`, which repaints the
  body for free; it sets `pr.color` to the friendly hue so the halo agrees
  instead of leaving the shot glowing in the enemy's colour. Its old ad-hoc
  `(255, 230, 150)` is gone.
- **This is what makes the body cacheable.** Two colour variants instead of one
  per creature means the three rings collapse to a sprite keyed on
  `(even radius, side)` — see
  [ADR-0009](./0009-glow-cache-quantized-keys.md) for the key discipline and
  [Performance](../concepts/performance.md) for the numbers. Putting the
  species colour back in the body reopens an unbounded cache as well as the
  legibility problem.
- Registered risk: a new hazard that is neither "hostile bullet" nor "player
  bullet" (a neutral or an environmental shot) has no colour reserved for it.
  Give it a third fixed body, do not reach for the creature's hue.
- `tools/check_projectile.py` pins it: five species render byte-identical
  bodies within a side, the two sides are far apart, and the halo still varies.
