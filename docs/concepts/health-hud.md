# Health HUD

Visible health for player, enemies, bosses, and friends.

## Player

Player health uses **Health Sacs**, each worth a fixed 25 HP. The fixed unit
keeps the row countable as `max_health` grows: eight sacs fit per row, the
second row grows upward, and sacs shrink instead of opening a third row after
sixteen.

A sac's shell remains visible when empty, with residue at its base, so the row
shows both current and maximum health. Arbitrary health values fill the last
sac fractionally. Exact `health/max_health` text remains small at the row edge
for runs where shrinking makes precise values harder to read.

Filled sacs are blood-red rather than using `palette.health_color`. Low health
raises pulse frequency and saturation across the row so danger attracts the
eye. Damage swells the active sac, bursts its fluid state, rocks its neighbours
along the artery, then leaves the empty shell settled in place.

Alongside: energy bar and XP bar. The three sit inside the player
**capsule** ([HUD anatomy](./hud-anatomy.md)) and animate on their own
faster rhythm; the capsule itself answers damage with a low-frequency
spring.

## Enemies

Enemy health keeps the `palette.health_color` ramp (green → yellow → red).
Mixing two stops turns the middle into muddy olive, so the ramp has three stops.
`AILizard._draw_health` draws a small bar above the head **only when
wounded** (hidden at full HP so the screen stays clean). Scales by
`max_hp` — if `hp` is adjusted after spawn, call `sync_max_hp()` (species
and rounds do already).

## Bosses

No mini-bar; use the **big top-of-screen bar** (`rounds.draw_boss_bar`).
See [UI legibility](./ui-legibility.md) for the top-stack rules.

The boss bar keeps `palette.health_color` (green → yellow → red, three
stops). The decision was made in #134 and the reason is written so it
does not become silent drift:

- **The boss's body is anatomy, but it is not YOUR anatomy.** The ramp
  reads as "the other body is weakening" — the same signal the player
  reads on any enemy. If the boss bar became sacs like the player, the
  eye would say "your body is on the line" — which is true, but only
  in the abstract sense of "your run is on the line". The bar has to
  name the other body, not your own.
- **Two languages of "life" was also a candidate.** The boss bar as
  sacs would land in the rodape metaphor (and make the bar alone
  anatomy-based). It would also collide with the player's row: a boss
  bar next to a player row, both files of sacs, would invite the
  comparison the rodape is trying to avoid. The two linger on
  opposite sides of the screen so the eye doesn't pair them.
- **The rampa stays useful and three-stops is documented.** Two stops
  become muddy olive, see the original health-hud rationale. The
  enemy mini-bar (`AILizard._draw_health`) reuses the same ramp, so
  the visual signal is consistent across every "that creature has
  less HP than full" surface in the game — boss included.
- **If the top ever gets grammar, the boss bar is the first to be
  reconsidered.** The ramp is a lingua do mundo element; if that
  language earns metaphor (see #152, the friends count follow-up
  that opens the work), the boss bar gets re-evaluated then, not
  before.

## Friends

Alongside the mini-bar, the **body colour fades** as they weaken
(`AILizard._fade_by_vitality`: interpolates from `base_color` toward a
grey-lavender using the **worse** of `hp/max_hp` and
`life/FRIEND_LIFE`), and they blink the last 5 s before disappearing.
Every draw reads `self.color`, so updating that alone drags body / legs /
rim / glow with it.

## Related

- [Damage](./damage.md) — where HP comes from.
- [Hitbox](./hitbox.md) — where damage lands.
- [UI legibility](./ui-legibility.md) — the top-stack that owns the boss
  bar.
- [HUD anatomy](./hud-anatomy.md) — the capsule that wraps the player bars
  and the four beats the HUD obeys.
- [Balance](./balance.md) — the friend lifetime that drives the fade.
