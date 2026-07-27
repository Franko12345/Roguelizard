# Two dodge verbs, both invulnerable

The **Investida** (the dash) is invulnerable but punctual: 0.16 s of i-frames on
a 0.45 s cooldown for 18 energy is 36% of the cycle in a burst and ~5%
sustained, and 5% is not enough headroom to raise bullet density without being
unfair. Rather than make the investida cheaper or longer — which would also make
it a better *weapon*, since it deals damage — we added a second verb: the
**Rolamento** is cheap (5 energy, 0.2 s cooldown) and deals no damage.

So the player owns two invulnerability buttons on purpose. They are not
redundant: the investida trades frequency for damage and reach, the rolamento
trades damage for frequency and efficiency. Both read their i-frames from the
one guard in `Player.hurt`.

### The asymmetry is damage and cost, not impulse

This first shipped with the rolamento deliberately *not* launching — steer
stayed live and it only multiplied speed, so the investida would keep its
identity as the committed move. Playtest killed that: at 1.9× for 0.15 s the
lizard travelled about a third of its own body, and the verb read as "tried to
roll and did not dash". A dodge that does not leave the spot the bullet is
going to is not a dodge.

The rolamento now launches like the investida (3.4× max speed against 3.0×, over
a shorter window). Measured over one second of holding a direction: **+174 px
per roll against +223 px per investida**, at 5 energy against 18 — 34.8 px per
energy point against 12.4. The investida is still the bigger single commitment
and the only one that hurts anybody; the rolamento is the cheaper, more frequent
exit. `tools/check_roll.py` asserts all three of those relations, because "it
moves you" turned out to be the part nobody had measured.

A second playtest killed the animation for the same class of reason. The pose
was a *fake roll* — collapse the spine into a spinning disc — and it read as
"it just curls you up": the body became a blob and the direction you left in
was unreadable. It is a squash-and-release now, compress on the launch and
overshoot past neutral on the exit. See [Dodge](../concepts/dodge.md) for the
filter that makes those constants look strange.

## Consequences

- The gamepad's button budget is spent: the four face buttons were already
  taken, so the rolamento sits on a **trigger** (LT/RT) — the first trigger this
  game reads at all.
- The registered risk was that the investida would stay the optimal dodge and
  the rolamento would die as a button. It nearly did, for the opposite reason to
  the one predicted: not because forward commitment was too cheap, but because
  the rolamento covered no ground at all. The economy that needed reopening was
  the rolamento's, not the investida's, which is untouched.
- The animation is a *fake* roll (collapse the joints into a spinning disc), not
  a coil; the spine's bend limit makes a real coil impossible. See
  [Dodge](../concepts/dodge.md).
