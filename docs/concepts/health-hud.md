# Health HUD

Visible health for player, enemies, bosses, and friends.

## Player

Bar on the HUD with the `palette.health_color` ramp (green → yellow →
red). Mixing two stops turns the middle into muddy olive — the ramp has
**three** stops for that reason.

Alongside: energy bar and XP bar. Glued underneath, the
[stat grid](./stat-grid.md) — the numbers the bars cannot show
(`might`, the multipliers, the items and charms owned).

## Enemies

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
- [Stat grid](./stat-grid.md) — the stat column under the player's bar.
- [UI legibility](./ui-legibility.md) — the top-stack that owns the boss
  bar.
- [Balance](./balance.md) — the friend lifetime that drives the fade.
