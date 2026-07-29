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
(mass-spring-damper, overdamped so it settles in well under a second)
and `PlayerCapsule` (per-player state: the spring plus last-frame vitals
for change detection). The capsule is drawn by `state_play._draw_hud`
inside one `ui.panel` call, exactly the way the menu and level-up screens
draw their frames.

## The four-times applied

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

## Layout

- **P1 capsule** in the bottom-left corner, **P2** in the bottom-right.
  Symmetric in coop; same rule of thumb both ways.
- **Top-centre column** is owned by `TopStack` (score, wave, combo,
  boss name, boss bar, banner). Player blocks no longer compete with it
  — that's the gain the move to the bottom bought.
- Inside each capsule, top to bottom: header (P1/Nv), health, energy,
  XP, dial row (DASH / LING / RABO), bottom strip (weapons + active
  item in their own corners).

Width and height of the capsule live in `config.HUD_PANEL_W` /
`HUD_PANEL_H` so the layout maths stays in one place.

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
(coop, two players, full bar of 16 sacs). The four levers, in order:

1. **Drop the sim rate to 30 Hz.** The capsule spring and the fluid
   sim update at 30 Hz, interpolating between steps. The capsule moves
   slowly enough that interpolation is invisible.
2. **Drop detail by sac count.** Past N sacs, full ones become flat
   circles without specular or individual pulse; the two at each end
   keep all the detail. The eye lives at the edges.
3. **(Already discarded) Cache the bar to a `Surface`.** This would
   kill the per-sac pulse — which is the whole point of the bar.

`palette.glow` stays cached with the quantized key (see
[ADR-0009](../adr/0009-glow-cache-quantized-keys.md)), `bio_bar`
stays per-frame and rule-of-thumb stays: no per-frame `Surface`
allocations.

## Verification

`tools/check_hud_anatomy.py` pins four claims with teeth:

1. Capsule lives at the bottom — no player block's `y` is above the
   screen mid-line in either singleplayer or coop.
2. The capsule is framed — `state_play._draw_hud` calls `ui.panel` for
   the block.
3. Worst-case TopStack (score + wave + combo + boss name + boss bar +
   banner) does not collide with the player blocks at 1120x720.
4. The spring settles — one impulse drives the capsule back to
   `(|x|, |y|) < 0.05 px` within ~1 s of 60 Hz ticks. A spring that
   rings forever is nausea, not feel.

`tools/check_hud_anatomy.py` was broken on purpose during writing to
confirm both halves of the spring and the bottom anchor are checked.

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