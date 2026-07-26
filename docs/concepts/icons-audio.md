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

`init()` synthesises **19 SFX** (3 pitch variations each; includes one
per weapon archetype: `w_spit` / `w_homing` / `w_web` / `w_aura` /
`w_orbit` / `w_puddle`) + 4 generative loops.

- `play(name, vol)`
- `set_music('calm' | 'combat' | 'boss' | 'victory')`

If pygame lacks `mixer`, everything becomes no-op and the game runs
silent (verified).

## Related

- [ADR-0003](../adr/0003-zero-assets-with-png-fallback.md) — the fallback
  contract.
- [Architecture](./architecture.md) — where these modules sit.
- [UI screens](./ui-screens.md) — where the `buy` chime plays on impact.
