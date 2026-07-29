# HUD anatomy

The HUD is the lizard's anatomy seen from the inside. Every readout is an
organ sitting inside a framed **capsule**; the capsule is "massa rigida"
with its own low-frequency rhythm, while each organ inside has its own
faster rhythm. One visual language, six places to read.

## Why a metaphor

The HUD reached its current shape by accumulation: one block per readout,
each hard-coding its own `y`. The cost was invisible until someone tried
to add a medidor novo: there was no rule for where it went, so each one
chose a corner and fought the next.

The metaphor turns "where does this go?" into "what organ is this?":

| readout | organ |
|---|---|
| health | tissue (saco/skin) |
| energy | fluid and air |
| XP | skull and brain |
| cooldowns | gland |
| active item | the dedicated organ it represents |

Without the metaphor, the HUD stays a pile. With it, an addition three
months from now lands in the obvious slot.

## Capsule vs organ

Two layers, two frequencies. From [procedural-animation](./procedural-animation.md)
the body's animations are split into Intent / Action / Reaction /
Follow-through; the same applies here:

- **Capsule** = the container. Mass. Low frequency. Overshoots on entry,
  trembles when something inside changes, swings when damage lands.
  Frequencies around 1-2 Hz, amplitudes around 3-12 px.
- **Organs** = the bars, dials, item icon. Each on its own rhythm (the
  flagella wave at ~3 Hz, the leading-edge bulge of `bio_bar` at ~3 Hz,
  the dial ready-pulse at ~6 Hz). They never share a phase clock.

If everything bounces together the panel reads as gelatin and the player
loses **which** medidor moved. Two layers read as "a container holding
something alive" — that is the metaphor at work.

The implementation lives in `lagarto/game/hud.py`: `CapsuleSpring`
(mass-spring-damper, under-damped so the entry overshoot is visible but
settles in ~0.7s) and `PlayerCapsule` (per-player state: **two**
`CapsuleSpring`s — one for vitais, one for cooldowns — plus last-frame
vitals for change detection). The capsules are drawn by
`state_play._draw_hud` inside two `ui.panel` calls per player, exactly
the way the menu and level-up screens draw their frames.

## The four-times applied

Every HUD element obeys the same four beats as the body:


Every HUD element obeys the same four beats as the body:

- **Intent** — the readout is *meant* to change. The bio bar's leading
  edge has a meniscus because the player reads "fluid under pressure",
  not "filling up a rectangle".
- **Action** — the change actually happens. A HP drop is not the bar
  shrinking: it is the bar shrinking AND the capsule shaking.
- **Reaction** — the inside of the organ answers. `bio_bar`'s bulge
  wobbles after a hit because the fluid still moves after the wall moved.
- **Follow-through** — the panel settles. The overdamped spring returns
  the capsule to rest instead of ringing forever.

The thing the old HUD was missing was **follow-through on the
container**: the flagella waved (organ reaction), but the panel they
lived in was a static rectangle. Two rhythms in series is the answer.

## The organs, one by one

Each vital gets a distinct anatomical motion, so the player never has to read
a label to know *which* readout moved. Health pulses, energy inflates, XP
fills a cavity.

### Energy bellows

Energy is a bellows: its inflation follows `energy / max_energy`. Spending
energy collapses it on the same frame; its damped spring supplies reaction and
follow-through. Ability dials remain the source of cost-threshold information,
so the bellows has no cost notches.

### XP skull

The skull separates two progression signals:

- cerebrospinal fluid represents XP inside the current level and drains to
  zero at level-up;
- brain size and folds represent level, grow at level-up, and never shrink.

Brain size grows with the square root of level, so there is no reachable hard
cap and later growth becomes denser rather than escaping the skull. Each level
adds two folds. The fluid surface is a damped 16-point wave stepped at 30 Hz;
the renderer allocates no `Surface` per frame.

## Layout

- **P1 block** in the bottom-left corner, **P2** in the bottom-right.
  Symmetric in coop; same rule of thumb both ways.
- **Top-centre column** is owned by `TopStack` (score, wave, combo,
  boss name, boss bar, banner). Player blocks no longer compete with it
  — that's the gain the move to the bottom bought.
- Inside each player's block, **two framed capsules stack vertically**:
  the vitais capsule (header `P1`/`Nv` + 3 bars — health, energy, XP)
  on top, the cooldowns capsule (3 dials — DASH / LING / RABO) below.
  Each capsule has its own spring; a fast organ (energy) inside a slow
  container (capsule spring) would otherwise read as one block, not two.
  The vitais organs are #131/#132's sacs + bellows + skull (not the
  bars the issue sketch first named).
- **Weapon + item strip** lives below the cooldowns capsule, unframed.
  Weapons march toward the centre, the active item owns the opposite
  corner, so a six-weapon build never collides with the item sphere.

Width lives in `config.HUD_PANEL_W`. The vitais height is a **sum**,
not a magic number: `HUD_VITALS_H = HUD_HEAD_H + HUD_HEALTH_H +
HUD_ORGAN_GAP + HUD_BELLOWS_H + HUD_ORGAN_GAP + HUD_SKULL_H`. Add an
organ inside vitais and the capsule grows to fit it instead of the
bands colliding. Total player height is
`HUD_PLAYER_H = HUD_VITALS_H + HUD_COOLDOWNS_H + HUD_STRIP_H + 2 *
HUD_BLOCK_GAP`.

The HP number rides the header band, centred, because the sac row is
centred in the capsule width — a corner label collided with it.

## O que o topo e

The metaphor covers the **rodape** (the corpus, the body) and runs out of
room at the top. The `TopStack` is a separate visual language, and
**that is the decision**, not a gap. Section written in #134, ratified
here.

### Two languages, declared

| column | metaphor | what lives there | rhythm |
|---|---|---|---|
| rodape (P1 left, P2 right) | **lingua do corpo** | your vitais + your cooldowns | organ + capsule, two frequencies |
| topo (centre column) | **lingua do mundo** | the run, the wave, the threats, the allies | mono — typography, clean bands, status |

The split is **deliberate**, not accidental. The rodape earns the
anatomy because every organ there is something you *are* — your
tissue, your air, your breath, your gland. The top is something you
*are in* — the run's score, the wave's progress, the boss's name,
the friends' count. Anatomy on the top fails the decision rule:
"what organ is the score?" has no honest answer, and forcing one
produces the arbitrary symbol the rodape metaphor was written to
avoid.

### The six inquilinos, one by one

| element | decision | reason |
|---|---|---|
| score | stays as-is | numeric telemetry of the run; nothing anatomizes without invention |
| linha de onda | stays as-is | same — the run's position, not yours |
| combo | stays in top, gets a pulse | the only momentary combat state, but it's **the run's** state, not the body's |
| banner de tema | stays as-is | transient announcement, not a readout |
| nome do chefe | stays as-is | identifier, not a value |
| barra do chefe | keeps the ramp | anatomy, but not YOUR anatomy — see [health-hud](./health-hud.md) |

A "stays as-is" is a real decision. If it isn't written, the next
contributor sees a top that looks like the old rodape and "fixes" it
with an organ the metaphor doesn't actually cover.

### Combo, the only candidate to move

Combo is the only element that answers "what changed inside the
fight, just now?" — the closest the top has to an organ. The
argument for moving it down is honest: it would slot next to the
body, and the limb that just killed sits inside the body that
gained the kill.

The argument against: combo is **the run's** kill-streak, not the
body's. Pulling it into the capsule breaks the rule that the
capsule holds what you are. The run isn't you; the run is the
world you're inside.

**Decision:** combo stays in `TopStack`, but the **pulse** it gets
is louder than the other elements when it ticks — a brief
amplitude bump on the score line so the eye catches the moment
the streak grew. The bump is small enough to read as "the run
moved" not "the body moved". See #135.

### Friends count and the world grammar

The friends counter is "**Amigos N**" today, with **torreta**
counting as a friend since the build in #111. The number reads
honest: one friend, two friends, three friends. The HUD shows
the number, not the meaning.

If the lingua do mundo ever gets grammar, **this counter is the
first client** — it has the strongest claim to "what does this
number mean?" because the answer is a body, not a run. Until
then, the counter stays raw and the next contributor sees the
unfinished sentence. See #135.

## Active item, weapons, item corner

Three things were competing for the same row in the old top-corner HUD:

- a fourth dial (impossible, the panel was 216 px at 68 px pitch),
- the active item (the doc comment in `state_play.py` explained it),
- the weapon strip (which then moved to its own bottom-row corner).

With the capsule in the bottom and three rows of room (header / bars /
dials / strip), the three now have distinct corners:

- **Dials** stay in their row inside the capsule.
- **Weapons** march along the bottom strip toward the centre.
- **Active item** owns the opposite corner — for P1 the right side of
  the strip, for P2 the left. In coop each player gets the same corner
  of their own capsule, so they never share a slot.

## Budget

Frame budget for the HUD: **1.0 ms**, measured on the worst case
(coop, two players, both capsules per player). Measured
**0.27 ms / frame** in steady state on the reference box, well
inside the ceiling. The levers, in order:

1. **Drop the sim rate to 30 Hz.** The capsule spring and the fluid
   sim update at 30 Hz, interpolating between steps. The capsule moves
   slowly enough that interpolation is invisible.
2. **Cache `ui.panel`'s fill.** The dark fill surface is one entry
   per `(w, h, alpha, radius)` in `_PANEL_CACHE`; the rim is one
   cheap `draw.rect` per call (the rim lives on the target surface so
   its outer edge stays pixel-perfect against neighbouring blocks).
3. **(Already discarded) Cache the bar to a `Surface`.** This would
   kill the per-sac pulse — which is the whole point of the bar.

`palette.glow` stays cached with the quantized key (see
[ADR-0009](../adr/0009-glow-cache-quantized-keys.md)), `bio_bar`
stays per-frame and rule-of-thumb stays: no per-frame `Surface`
allocations.

## Verification

`tools/check_hud_anatomy.py` pins seven claims with teeth:

1. **Capsule anchored at the bottom** — no player block's `y` is
   above the screen mid-line in either singleplayer or coop; the two
   player blocks never overlap each other at 1120x720.
2. **Two framed capsules** — `state_play._draw_hud` calls `ui.panel`
   for *both* vitais and cooldowns, with the rim primitive present.
3. **No TopStack collision** — the worst-case draw (score + wave +
   combo + boss name + boss bar + banner) reserves bands that all
   finish above the vitals top; the rim is visible on the vitals
   left edge for both players.
4. **Spring settles through the wired path** — damage on a real
   player drives `detect_changes` to call `impulse()` on the spring,
   and the spring returns to `(0, 0)` within ~1 s of 60 Hz ticks.
5. **`detect_changes` fires the right shakes, and amplitude decays**
   — damage is louder than value-change; a fresh impulse after the
   envelope has died does not inherit the prior amplitude.
6. **HUD draw under 1 ms** — bench of `_draw_hud` alone in coop,
   steady state (caches warm), under a 2.5 ms ceiling (2.5× slack
   over the issue's 1 ms budget, generous enough for noisy boxes).
7. **Panel cache is bounded** — `_PANEL_CACHE` ends with a small,
   stable number of entries after a draw; 0 means the panel never
   drew, >4 means the keyspace is unstable.

The anatomy specifics from #131/#132 are checked by the **same**
`tools/check_hud_anatomy.py` (sections 6-9): brain growth monotonic,
cranial fluid drains on level-up, bellows collapse/inflate without
overshoot, and a two-skull draw stays under the 1 ms budget. They
were added into the same file (rather than a separate script) so a
broken HUD never passes one check and fails another -- the whole
anatomy fails or the whole anatomy passes.

`tools/check_hud_anatomy.py` was broken on purpose during writing to
confirm both halves of the spring and the bottom anchor are checked.
`--shot` writes `hud-anatomy-comparison.bmp` with three skull states.

## Related

- [Procedural animation](./procedural-animation.md) — the four beats
  that govern the body, applied here to the HUD.
- [UI legibility](./ui-legibility.md) — the top-centre column and
  the `TopStack` reservation system.
- [Health HUD](./health-hud.md) — what each organ shows.
- [Juice](./juice.md) — the per-event beat that surrounds each
  read.
- [ADR-0015](../adr/0015-hud-anatomy.md) — the rule and why it is
  hard to reverse.
- [ADR-0016](../adr/0016-topo-e-mundo.md) — the rodape/topo split
  between the lingua do corpo and the lingua do mundo.