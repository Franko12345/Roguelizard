# Controls

Every input crosses `Controller`. See [Input buffer](./input-buffer.md)
for the timer that keeps edges alive across zero-step frames.

## P1

- **WASD** — move
- **mouse** — aim
- **left click / SPACE** — dash (Investida)
- **right click / SHIFT** — tongue
- **middle click / Q** — whip (tail sweep)
- **LCTRL** — Rolamento (the other dodge, [Dodge](./dodge.md))
- **E** — active item

In single-player, a gamepad also controls P1 (hybrid — whichever is
active; `KeyboardMouseController(joy)`), so the game plays without a
mouse.

## The button budget is full

All three mouse buttons and all four pad face buttons are taken (A/RB dash,
X/LB tongue, Y whip, B item), which is why the Rolamento landed on a
**trigger** — LT or RT, the first trigger this game reads — and on a keyboard
key rather than a fourth click.

## Tongue auto-aim

Aims at the nearest edible in range (`game.nearest_edible` — no cone)
and **costs energy** (8). Skips the mouse.

## P2 (coop)

- **gamepad** (sticks + A/X/**Y**/B + **LT/RT**) if detected
- else arrows + IJKL + RCtrl / RShift / **RAlt** / U (item) / **O** (Rolamento)

On the raw-joystick fallback the triggers are only read on a 6-axis pad: with
four axes, axis 2/3 *are* the right stick, so trusting axis 2 would make aiming
roll.

## Global keys

Not player actions — preferences, so they are read in `app.py` before the
per-state handlers and work in any state.

- **TAB** — toggle the [stat grid](./stat-grid.md). A latch, not a hold;
  default on; persisted in `core/settings.py`. One toggle for the whole
  game, not one per player.
- **F3** — cycle the perf meter. **F11** — fullscreen. **ESC** — pause.

TAB was the free key: P1 and P2 between them take WASD, the arrows, IJKL,
space, both shifts, both ctrls, RALT, Q/E/U/O, and the sandbox overlay
takes backquote / F1.

## Window (`display.py`)

Everything is drawn on a fixed logical surface (`C.WIDTH × C.HEIGHT`) and
scaled (smoothscale) to the window; presets **1x / 2x / 3x**, fullscreen
with letterbox, **F11** toggles.

Any click or aim **must** pass through `display.to_logical(pos)` —
otherwise it misaligns when scaled.

## Gamepad

Uses the SDL GameController API when available (correct mapping per
device, DualSense / Xbox), with fallback to raw axes + hat. **Hot-plug**
works. `MenuNav` converts stick / dpad into menu events (with repeat) —
navigates menu, level-up cards, and camp.

## Related

- [Input buffer](./input-buffer.md) — grace window for actions.
- [Dodge](./dodge.md) — what the new button does.
- [Pause](./pause.md) — controls text is shared with the pause menu
  (`menu.CONTROLS`, which lists the global keys too).
- [Stat grid](./stat-grid.md) — what TAB shows and hides.
- [Camp](./camp.md) — walk-in-shop input model.
