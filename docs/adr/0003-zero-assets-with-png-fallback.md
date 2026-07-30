# Zero-assets broken deliberately with PNG-first, procedural fallback

**Context.** The engine's identity was "zero assets" — every visible thing
drawn by code. Player and world stayed that way, but weapon / mutation /
charm icons were tiny and repetitive, and hand-authoring pixel-art for those
UI slots was fast.

**Decision.** Break the invariant, but keep the shape: `icons.draw` tries a
PNG in `assets/icons/<id>.png` first, falling back to the procedural
drawer. Audio is still 100% synthesised. Player body, world, particles are
still 100% code. Only icons and boss emblems have PNG variants.

**Why.** A build without `assets/` behaves identically to the old code path
— the fallback is not a stub, it's the drawer that shipped for months. But
where a PNG exists, it wins. This makes the "add a memorable icon" workflow
1 PR of pixel-art instead of 1 PR of custom drawing per id.

**Consequences.**

- `lagarto/render/assets.py` handles PyInstaller's `_MEIPASS` and lazy loading; the
  cache is keyed on `(id, diameter)` with a 300-entry cap.
- `build.py --add-data` packages `assets/` inside the executable.
- If a PNG id is missing (typo, forgotten copy), the drawer silently draws
  the procedural version. This is intentional but means "why is my icon
  wrong?" is always "PNG name mismatch" before it is anything else.
- Do not extend the exception. Audio, world, creatures stay code-only.
  New PNG surfaces should go through `icons.draw`.

## Extension (issue #159): boss personality elements

**Context.** Two bosses in the pipeline — Serpente de Cristal (faceted
crystal head + segments) and ANKH (multi-body ghost with per-phase alpha
blending) — need visual elements the procedural drawing cannot deliver
honestly (faceted geometry, multi-skeleton overlay). The existing exception
covers icons and emblems; the rest of the body stays procedural by the same
"spine + legs + body polygon" rule.

**Decision.** Add a second layer to the exception: **boss personality
elements** — segments of crystal, fangs, eye variants, ornamental layers
that sit ON TOP of the procedural body and serve only to mark the boss's
identity. The procedural body (spine, legs, body polygon, the part types
already in `parts.draw_all`) is unchanged. The override is per-(boss_id,
part_name), optional, with procedural fallback when the PNG is missing.

- **Where to look**: `assets/boss/<boss_id>/<part_name>.png`.
- **How to load**: `boss_part(boss_id, part_name) -> Surface | None` in
  `lagarto/render/boss_assets.py` — same `_MEIPASS` + cache pattern as
  `lagarto/render/assets.py`. Missing file = `None` = procedural drawer.
- **Where to plug**: `parts.draw_all` accepts an optional `boss_id`. When
  present and the part has a registered override, blit the PNG; otherwise
  the existing procedural code runs unchanged.
- **Scope limit**: "personality elements" only. The body's silhouette,
  motion, and hit-test stay procedural — the only thing the PNG can
  change is the *look* of a single part, never the physics.

**Why a layer, not a full exception.** A full exception would let any
creature load any PNG and break the "everything is a Genome" invariant
behind [ADR-0001](./0001-genome-is-the-creature.md). A scoped layer keeps
that boundary intact: the boss's body is still drawn by code; the PNG is
only paint.

**Consequences.**

- A build without `assets/boss/` ships identically to before — the
  procedural fallback is the canonical path, not a stub.
- The cached surface reuses the `assets._ROOT` / `_MEIPASS` plumbing. Cache
  key `(boss_id, part_name, diameter)`, same `clear()`-on-overflow policy
  as `icons.draw`.
- The `Genome` gains an optional `boss_id` field; `AILizard.is_boss` is
  the runtime gate. Common enemies and prey never load boss assets.
- The `boss_part` helper is the only path. No direct `pygame.image.load`
  in any boss drawing code.
- "Why is my boss's PNG not showing?" is always "path mismatch" — same
  debug rule as icons. See [`parts.md`](../concepts/parts.md).

## Anti-patterns (do not extend further)

- Player body, world, particles: still 100% code. PNGs here would
  undermine the whole "no keyframes" pitch.
- Audio: still 100% synthesised. No PNG and no audio file in `assets/`.
- Genome-defined creatures (`role='prey'` or `role='enemy'`, non-boss):
  no PNG. The `boss_id` field is `None`; the override path short-circuits.
