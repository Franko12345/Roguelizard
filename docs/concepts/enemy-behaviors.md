# Enemy Behaviors

Phase-2 enemies exist to attack a specific player **habit**. New enemy =
new decision, not more HP.

## Roster

| Species | `behavior` | Attacks the habit of |
|---|---|---|
| **VESPA** | `fly` | hiding behind the horde — `collision._samples` skips flyers, so they neither push nor are pushed, and come straight in |
| **ESTOURADOR** | `bomber` | standing still — `BOMBER_FUSE` fuse; once lit, it slows down |
| **METRALHADOR** | `gunner` | open field — burst of `GUNNER_BURST`, low per-shot damage |
| **ENVENENADOR** | `venom` | camping — spits where you _are_ and leaves a puddle |
| **ANTECIPADOR** | `lead` | **rolling on reflex** — aims at where you are GOING |
| **MORTEIRO** | `mortar` | **charging in** — area that arms late, on your landing spot |

The last two attack the habits the [Rolamento](./dodge.md) created. The roll is
cheap (5 energy, 0.2 s), so it gets pressed without looking — the ANTECIPADOR
shoots the point that reflex puts you on, and reuses `emitter.aimed_barrage`
(the boss barrage's lead, dialled to a perfect prediction). The MORTEIRO answers
the other one: its patch is picked at the **start** of the wind-up and only
becomes a hazard a second later, so an investida aimed at it ends inside it.

Neither is unfair, and the fairness comes from the telegraph rather than from
bad aim. Walking out of the MORTEIRO's patch always works. The ANTECIPADOR
**draws the exact point it will shoot, for the whole wind-up** — it predicts
where you will be when the bullet arrives, so any path you are already
committed to feeds it, and the answer is to read the marker and break the
commitment (a rolamento is the cheapest way to).

`lead` is a **quality**, not a duration: `1.0` predicts perfectly, and a boss's
`0.8` or a `lead_fan`'s `0.6` deliberately under-leads so a change of pace beats
it. The lead *time* always comes from the shot's flight (`dist / shot_speed`) in
`emitter.lead_point`. It was once a fixed number of seconds, which meant every
leading shot in the game was only aimed correctly at one distance — see the
superseded rows in [Balance](./balance.md).

## Every shooter fires through the emitter

No behaviour in `ranged.py` builds a projectile. The tick decides *when* to
shoot and *how to move*; what leaves the mouth is `genome.shot` — an
[emitter](../../CONTEXT.md) pattern plus its dials ([ADR-0012](../adr/0012-shared-pattern-emitter.md)).
The CUSPIDOR's single spit is a one-shot fan, the METRALHADOR's dispersion is a
`jitter` dial, the ENVENENADOR's lob is `emitter.lob_shot`. Turning any of them
into a radial burst, a cone or a spiral is a dict edit in `species.py`.

## Telegraph rule: draw the footprint

Telegraph is **time AND visibility**. The first bomber fuse was 0.85 s
(>27 frames) and had **nothing to see** but sparks — useless. Today
`_draw_fuse` draws the **blast footprint on the ground**, which answers
the only question that matters: _am I inside?_

Rule: when you add an area attack, draw the radius, not just an icon.
This is the same rule as boss [Telegraph](../../CONTEXT.md).

A marked attack (`AILizard._draw_mark`, driven by `_rain_points` +
`mark_r` + `mark_total`) borrows the boss's own `rain` telegraph, so a common
enemy's area tell speaks the same visual language as a boss's. One deliberate
difference: a common enemy's mark is drawn at **full radius from the first
frame**. The boss's circle grows, and a growing circle understates the danger
zone while it grows — for an enemy whose whole pitch is catching you standing
in it, that is the one thing the mark may not do. Urgency lives in the line
width and the glow, which already scale with progress.

## Hostile puddle: `dmg` changes meaning

`weapons.Puddle(hostile=True)`:

- `hostile=False` → damage per **second** (multiplied by `dt`, feeds the
  `AILizard.damage` accumulator).
- `hostile=True` → damage per **tick** with its own cadence
  (`VENOM_PUDDLE_TICK`).

Player i-frames do **not** rate-limit — they reopen every ~0.17 s and
measured **42 dmg/s**. And `VENOM_PUDDLE_LIFE` must be **less than**
`VENOM_CD`, otherwise puddles overlap and stack: the same bug as
`Acido`, again. `MORTAR_LIFE` (3.0) < `MORTAR_CD` (4.0) for the same
reason, and `tools/check_content.py` asserts both pairs so the fourth
time cannot happen quietly.

_Third time this project trips on "effect lasts longer than the interval
that reapplies it" — Ácido, venom puddle, sting slow._

## Verification

`tools/check_content.py` — the three old shooters call `genome.shot['fn']` and
build no projectile of their own; the same species fires 1 shot or 7 depending
only on its dial; the ANTECIPADOR's shot lands 19.9° ahead of a target moving at
260 px/s and its ground mark shows exactly that point (a still target is shot
dead on); the MORTEIRO's footprint is drawn in 72/72 directions for 60 frames,
away from its own body, **before** any puddle exists.

## Related

- [Champion](./champion.md) — variants stack on any of these species.
- [Weapon](./weapon.md) — the puddle system these hostile puddles share.
- [Body plan](./body-plan.md) — centipede/octopus follow the same
  "attack a habit" rule.
