# Docs

Documentation for Lagarto follows the Matt Pocock ecosystem: one concept
per file, cross-linked, with a single canonical glossary at the root.

Read [CLAUDE.md](../CLAUDE.md) for the maintenance rules (when to update
what, one-file-per-commit convention).

## Layout

```
CONTEXT.md            ← domain glossary (canonical vocabulary)
docs/
├── README.md         ← you are here
├── adr/              ← Architecture Decision Records
│   ├── README.md     ← format + index
│   └── NNNN-slug.md  ← one file per decision
├── concepts/         ← concept docs
│   ├── README.md     ← index by group
│   └── <slug>.md     ← one file per concept
└── agents/           ← operational conventions for AFK agents
    ├── issue-tracker.md
    ├── triage-labels.md
    ├── verification.md   ← an issue closes when a CHECK says so
    └── domain.md
```

## Where new content goes

- **A new domain term.** `CONTEXT.md`. Sometimes also a concept doc.
- **A hard-to-reverse decision.** `docs/adr/NNNN-slug.md`.
- **A new concept the code introduces.** `docs/concepts/<slug>.md` +
  entry in `CONTEXT.md`.
- **An operational rule for agents.** `docs/agents/`.

The three-part test for an ADR (hard-to-reverse, surprising, real
trade-off) is in [`docs/adr/README.md`](./adr/README.md). Do not create
an ADR for a decision that fails the test.

## Naming and cross-linking

- Files use kebab-case slugs.
- Prose uses the canonical term from `CONTEXT.md`. If the term is
  avoided in the glossary, the doc is wrong.
- Cross-links are markdown relative paths: `[Genome](../concepts/genome.md)`,
  `[ADR-0004](../adr/0004-boss-pool-per-tier.md)`.
- Never duplicate a definition — link to it.

## Where the source of truth lives

- **Runtime behaviour** — the code. Concept docs describe intent.
- **Vocabulary** — `CONTEXT.md`.
- **Why-we-did-it** — the ADR.
- **Working brief for Claude** — `CLAUDE.md`. Long-form operational
  reference; not the place to look up a term.
