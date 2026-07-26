# Running the game

```bash
python lizard_game.py             # play (opens the menu)
python lizard_game.py --smoke 90  # headless self-test: N frames and exit
python lizard_game.py --sandbox   # dev-only debug overlay (skips the menu)
python build.py                   # single-file binary in dist/ (needs pyinstaller)
```

## Windows build

PyInstaller does **not** cross-compile. Either run `build.py` on Windows,
or use CI: `.github/workflows/build.yml` builds **Windows + Linux** on
every push and attaches binaries to a Release when you push a `v*` tag.

## Dependencies (`requirements.txt`)

- **`pygame-ce`** — community edition; same API and ships `mixer`
  (needed for sound).
- **`numpy`** — audio synthesis. Hot loops use `math` + `pygame.Vector2`
  (scalar numpy is slower per operation).

## Headless test

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python lizard_game.py --smoke 90
```

## Assets — the invariant is broken on purpose

Phase 7 introduced `assets/` + `lagarto/assets.py`: weapon / mutation /
charm icons prefer a pixel-art PNG when it exists, and fall back to the
procedural drawing (`icons.draw`). A build without the `assets/`
directory (or an ID without a PNG) runs identically. Sound and music
stay 100% synthesised; the rest of the art (body, world, particles) is
still generated in code.

See [ADR-0003](../adr/0003-zero-assets-with-png-fallback.md) and
[Icons & Audio](./icons-audio.md).

## Screenshot from headless

The `dummy` driver cannot save PNG directly from the display surface.
Blit to `Surface(..., 0, 24)` and save BMP → PNG.

## Related

- [Architecture](./architecture.md) — where `lizard_game.py`,
  `lagarto/app.py`, and the CLI flag land.
- [Performance](./performance.md) — the timestep and render decoupling.
- [Sandbox](./sandbox.md) — what `--sandbox` opens.
