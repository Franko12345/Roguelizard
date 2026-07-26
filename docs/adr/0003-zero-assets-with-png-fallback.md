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
