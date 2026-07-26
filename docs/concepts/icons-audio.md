# Icons & Audio

Both generated in code. See [ADR-0003](../adr/0003-zero-assets-with-png-fallback.md)
for the pixel-art PNG fallback.

## `render/icons.py`

Every weapon / mutation / charm has a procedural drawer. `icons.draw(surf,
id, centre, radius, colour)`. IDs match `weapons.WEAPONS`,
`evolution.MUTATIONS` (`Mutation.icon`), and `charms.CHARMS`. Fallback =
disc, so a new ID never breaks rendering.

Assets (Phase 7): if `assets/<id>.png` exists, `lagarto/render/assets.py`
prefers the pixel-art PNG; otherwise the procedural drawer runs. Sound
and music stay 100% synthesised.

## `audio/engine.py`

`init()` synthesises **21 SFX** (3 pitch variations each; includes one
per weapon archetype: `w_spit` / `w_homing` / `w_web` / `w_aura` /
`w_orbit` / `w_puddle`, and `tongue_out` / `tongue_hit` for the
[tongue](./combat.md)) + 4 generative loops + **6 adaptive stems**.

- `play(name, vol)`
- `set_music('calm' | 'combat' | 'boss' | 'victory')` — discrete track.
- `set_music_intensity(0..1)` + `update_music(dt)` — the stem mix.

If pygame lacks `mixer`, everything becomes no-op and the game runs
silent (verified).

### Adaptive music: one dial, six stems

Six seamless loops at a shared 104 BPM — `bass`, `pad`, `arp_low`,
`arp_high`, `perc_low`, `perc_high` — each with its own volume-vs-intensity
curve in `_STEM_CURVES`. `set_music_intensity` sets the targets and
`update_music(dt)` eases toward them, so boss-enters and boss-dies crossfade
continuously instead of hard-swapping whole pre-mixed tracks.

`app.main` drives the dial: camp → 0.0, combat → 0.4 rising with the wave,
boss → 1.0. Victory stays on the **discrete** track, because it is a one-shot
fanfare and the stems loop forever.

| | bass | pad | arp_low | arp_high | perc_low | perc_high |
|---|---|---|---|---|---|---|
| calm | 0.247 | 0.135 | 0.081 | — | — | — |
| combat | 0.247 | 0.135 | 0.073 | 0.041 | 0.090 | — |
| boss | 0.247 | 0.135 | 0.045 | 0.090 | 0.099 | 0.099 |

Channel 0 is the discrete track and 1–6 are the stems, reserved via
`set_reserved` so a heavy combat frame's SFX cannot sit on a stem channel in
the window before the stems start.

`tools/check_music.py` runs against a **real** mixer via the SDL `disk`
driver — the dummy audio driver makes every call a no-op and would prove
nothing.

## Related

- [ADR-0003](../adr/0003-zero-assets-with-png-fallback.md) — the fallback
  contract.
- [Architecture](./architecture.md) — where these modules sit.
- [UI screens](./ui-screens.md) — where the `buy` chime plays on impact.
