# Juice / Feel

Whole-screen feedback layers that make hits feel like hits.

## Hit-stop

`game.punch(freeze, shake, flash)`. The `app.py` loop **skips
simulation steps** while `game.hitstop > 0` (still draws). Uses:

- dash-kill (0.07 s)
- damage to player (0.05 s)
- boss death (0.22 s + white flash)

## Transitions

`ui.Fade` (short fade) on entering a run and on every state change
(play ↔ camp ↔ levelup ↔ victory / over), and between menu screens.

## Menu animation (Vampire Survivors-style)

`menu._menu_list` takes an `anim` dict (`{'t', 'sel_f'}`) and does:

- **Staggered drop-in** of items (slide + fade, ~45 ms apart)
- **Sliding highlight** between options (`sel_f` chases `sel`)
- Selected item pulses softly

## `ui.fit`

`ui.fit(font, text, width)` truncates text with `"..."` so nothing
overflows a box.

## Hang the juice off the beats, not over the action

The [tongue](./combat.md) is the worked example. It has three beats, and each
one owns its feedback rather than the whole strike getting a spray of
particles:

| beat | what fires |
|---|---|
| launch | `tongue_out` sound, dust at the mouth, a 1.5 shake |
| contact | `tongue_hit`, `punch(0.045, 5)`, spark burst, a ring in the target's own colour, a glow snapping outward from the pad, **and a recoil impulse on the lizard toward its catch** |
| reel | trail particles off what it caught |
| arrival | `game.eat`'s own burst/popup, plus a gulp squash |
| whiff | a puff of dust. Nothing else — missing must not be rewarded |

Two of those are worth naming as general rules:

- **Feedback goes where the event is.** The hit resolves at full extension,
  so the impact juice fires there — not when the tongue gets home, which is
  where the old code resolved it.
- **Push the player, not just the screen.** The recoil that tugs the lizard
  toward what it grabbed costs one line and does more for "this tongue is
  attached to a body with mass" than any particle. Shake tells you something
  happened; moving the character tells you it happened *to you*.

Cost of all of it: 0.066 ms/frame while the tongue is out, 0.0002 ms when it
is not.

## Related

- [UI screens](./ui-screens.md) — where drop-in + absorption compose.
- [Combat](./combat.md) — where hit-stop is called, and the tongue's beats.
- [Boss](./boss.md) — the 0.22 s freeze on boss death.
- [Icons & audio](./icons-audio.md) — the adaptive stem mix.
