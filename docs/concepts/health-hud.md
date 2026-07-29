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
