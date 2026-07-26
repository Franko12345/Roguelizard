# Game Modes

`Game(..., mode='normal'|'endless')`. `menu.run_menu` returns
`(player_count, mode)`.

## NORMAL

The run **ends** on the final [Boss](./boss.md) of wave
`config.RUN_FINAL_WAVE` (20). `rounds.is_final` spawns the boss bigger
(`PRIMORDIAL`, ~2× HP), and killing it goes to the `victory` state
(summary + **+150 DNA** bonus).

## INFINITO

Unlocks **after the first win** (`progression.beat_game`). Ignores the
final wave and scales forever. The menu greys the item while locked.

## `--sandbox` is not a third mode

`Game(mode='sandbox')` exists, but it is a dev harness reached only by a CLI
flag — no menu entry, no unlock, and the wave machine never advances on its
own. It is listed here only so nobody adds it to this page as a player-facing
mode. See [Sandbox](./sandbox.md).

## Related

- [Gameloop](./gameloop.md) — same core loop for both modes.
- [Sandbox](./sandbox.md) — the dev-only harness, deliberately not a mode.
- [Boss](./boss.md) — the wave-20 gate for NORMAL.
- [Progression](./progression.md) — where the win flag lives.
- [Round](./round.md) — how the wave counter drives the mode.
