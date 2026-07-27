# Architecture Decision Records

One file per decision, numbered sequentially. An ADR captures *that* a decision
was made and *why* — the source of the answer to "why on earth did they do it
this way?" that shows up months later.

An ADR belongs here when all three are true:

1. **Hard to reverse** — reversing costs meaningful work.
2. **Surprising without context** — a future reader will wonder.
3. **A real trade-off** — genuine alternatives existed.

If any is missing, the decision isn't an ADR — it's just a commit message or
a comment.

## Format

Each file is `NNNN-slug.md`:

```md
# {Short title}

{1–3 sentences: context, decision, why.}
```

That's the minimum. Add `Considered Options`, `Consequences`, or `Status`
frontmatter only when they add real value.

Terminology: use the words in [`CONTEXT.md`](../../CONTEXT.md). If the ADR
introduces a new concept, add it to `CONTEXT.md` in the same commit.

## Index

| # | Title | Why it's an ADR |
|---|---|---|
| [0001](./0001-genome-is-the-creature.md) | Every creature is a Genome | Forces "no classes for kinds" for the life of the codebase |
| [0002](./0002-fixed-timestep-decoupled-render.md) | Fixed timestep at SIM_HZ, render at same rate | Physics stability + hit-stop rely on this; also gates cache behaviour |
| [0003](./0003-zero-assets-with-png-fallback.md) | Zero-assets broken deliberately with PNG-first, procedural fallback | Overturns a load-bearing invariant that once shaped the whole engine |
| [0004](./0004-boss-pool-per-tier.md) | Isaac-style boss pools per tier, not one boss per wave | Random-per-run identity requires a very different `_spawn_boss` |
| [0005](./0005-camp-is-a-physical-clearing.md) | Camp is a walkable clearing, not a menu screen | Reuses the play-state pipeline; changing back would rip out `field/shop` split |
| [0006](./0006-soft-player-contact.md) | Player↔enemy contact is soft (drag, not push) | Fixes "pinball feel" — reverting would break the whole game feel budget |
| [0007](./0007-cosmetic-skeleton-for-tail.md) | Cosmetic joints for tail spring & wave, physical spine unchanged | Hitbox/legs read the sim; changing this rots the alignment of every part |
| [0008](./0008-might-scales-all-damage.md) | Might multiplies weapons, dash, and whip | Card text is a promise; every new damage source has to remember to multiply |
| [0009](./0009-glow-cache-quantized-keys.md) | Quantize radius + colour before caching glow surfaces | Sessions used to leak >100 MB; getting this wrong regresses that |
| [0010](./0010-single-file-per-module.md) | One responsibility per module in `lagarto/` | The repo grew from one file — the split is what makes the codebase navigable |
| [0011](./0011-camera-transform-cached-on-property-writes.md) | Cache the camera transform, invalidated by property setters | `w2s` is the hottest function in the frame; mutating a camera vector in place silently breaks every conversion |
| [0012](./0012-shared-pattern-emitter.md) | One pattern emitter shared by bosses and common enemies | Un-couples 20 patterns from `boss_ai`; going back means re-coupling them and disarming every enemy built on it |
| [0013](./0013-two-dodge-verbs.md) | Two dodge verbs (Investida + Rolamento), both invulnerable | Two invulnerability buttons looks redundant; the asymmetry is what lets bullet density rise, and the pad's last free input is spent on it |

## Adding a new ADR

Scan for the highest number, add one:

```bash
ls docs/adr/ | grep -oE '^[0-9]+' | sort -n | tail -1
```

Then write a file, link it from the index above, and update `CONTEXT.md` if
a new term is introduced.
