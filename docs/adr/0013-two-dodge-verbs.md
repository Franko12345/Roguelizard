# Two dodge verbs, both invulnerable

The **Investida** (the dash) is invulnerable but punctual: 0.16 s of i-frames on
a 0.45 s cooldown for 18 energy is 36% of the cycle in a burst and ~5%
sustained, and 5% is not enough headroom to raise bullet density without being
unfair. Rather than make the investida cheaper or longer — which would also make
it a better *weapon*, since it deals damage — we added a second verb: the
**Rolamento** is cheap (5 energy, 0.2 s cooldown), deals no damage, and does not
launch you forward.

So the player owns two invulnerability buttons on purpose. They are not
redundant: the investida trades frequency for damage and forward commitment (in
a bullet-hell, usually *toward* whoever is shooting), the rolamento trades
damage for frequency and steering. Both read their i-frames from the one guard
in `Player.hurt`.

## Consequences

- The gamepad's button budget is spent: the four face buttons were already
  taken, so the rolamento sits on a **trigger** (LT/RT) — the first trigger this
  game reads at all.
- Registered risk: if going forward does not punish enough, the investida stays
  the optimal dodge and the rolamento dies as a button. The test is whether
  enemies that lead their shots make the investida dangerous. If they do not,
  the investida's economy is the thing to reopen — not the rolamento's.
- The animation is a *fake* roll (collapse the joints into a spinning disc), not
  a coil; the spine's bend limit makes a real coil impossible. See
  [Dodge](../concepts/dodge.md).
