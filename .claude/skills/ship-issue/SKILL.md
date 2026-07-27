---
name: Ship Issue
description: "End-to-end workflow to implement a GitHub issue in an isolated worktree and land it via PR on a chosen base branch (not main). Handles worktree creation, feature branch, delegation to a subagent, smoke test in the project venv, PR open, conflict resolution against the base, and merge. Invoke as `/ship-issue <issue-number> <base-branch>`."
version: 0.1.0
---

# Ship Issue

Workflow for implementing a GitHub issue end-to-end against a **non-main integration branch** (feature stack, refactor line, release candidate, etc.).

## Invocation

```
/ship-issue <issue-number> <base-branch>
```

Examples:
- `/ship-issue 38 refactor/architecture`
- `/ship-issue 71 release/1.2`

If user omits base branch, ask once before proceeding — never assume `main`.

## Preflight

Run in parallel:

```bash
gh issue view <N> --json number,title,body,labels,state
git branch -r | grep -F "<base-branch>"
git rev-parse --abbrev-ref HEAD
```

Bail if:
- Issue closed → confirm intent before continuing.
- Base branch missing on remote → ask user for correct name (do not fall back to `main`).

## Worktree setup

Feature branch name: derive from issue slug — e.g. issue `#38 T3 — Move render modules` becomes `refactor/t3-render` (match existing naming in `git branch -r`). Prefix must match the base branch family (`refactor/*` off `refactor/architecture`, `feature/*` off `develop`, etc.). Check `git log --format=%s <base-branch> | head -20` to confirm the style.

Create worktree at `.claude/worktrees/agent-<hex>` off the base branch:

```bash
git fetch origin <base-branch>
git worktree add -b <feature-branch> .claude/worktrees/agent-<hex> origin/<base-branch>
```

All subsequent work runs inside that worktree path.

## Implementation

Delegate mechanical work (renames, moves, mass import rewrites) to a `general-purpose` agent. Brief it with:
- Absolute worktree path as CWD.
- The issue body verbatim.
- The base branch name (so it knows what to diff against).
- Instruction to use `git mv` for moves (preserves rename history).
- Instruction to **not** open a PR or push — that stays with the parent.
- The standing brief block below, verbatim. A subagent starts cold: it never
  sees the conversation, so anything omitted here is simply absent.

Keep design/judgment work in the parent thread.

### Standing brief block (paste into every subagent brief)

```
Read `CLAUDE.md` in the worktree first, including the "Ferramentas — sempre
use o RTK" and "Modos de trabalho" sections.

- `rtk` is mandatory. The Bash hook rewrites simple command lines for free,
  but it cannot reach inside a pipeline, an `&&` chain, or a heredoc — so
  prefer one simple command per Bash call, and write `rtk grep …` /
  `rtk read …` by hand when a pipeline is unavoidable.
- Build the ponytail way: reuse what the repo already has before writing
  anything new; no abstraction, config knob, or scaffolding that the issue
  did not ask for. Read the whole flow first, then take the shortest fix.
- Code, commits, PRs and docs are written in normal prose — the caveman
  style applies to chat replies only, never to files.
```

## Smoke test

Run from the repo (or worktree) root. Use `.venv/bin/python` if a venv exists,
otherwise plain `python` — `pygame` must be importable either way.

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python lizard_game.py --smoke 90
```

Expect `[smoke] 90 frames ok`. Do not proceed to PR without a green smoke.

## PR open

```bash
git push -u origin <feature-branch>
gh pr create --base <base-branch> --head <feature-branch> \
  --title "<Txx — short title> (#<issue-number>)" \
  --body "$(cat <<'EOF'
Closes #<issue-number>.

## Summary
- <bullet 1>
- <bullet 2>

## Test plan
- [x] `--smoke 90` green
- [ ] <anything human should eyeball>
EOF
)"
```

Return the PR URL to the user immediately after creation. Do not merge yet — user reviews first unless they explicitly said "merge when green".

## Conflict resolution (when base moves under you)

If `gh pr view <N> --json mergeable,mergeStateStatus` reports `CONFLICTING` / `DIRTY`:

```bash
cd .claude/worktrees/agent-<hex>
git fetch origin <base-branch>
git merge origin/<base-branch>
```

For each conflicted file:
- If both sides moved/renamed the same symbol → **take the union of both intents**, not one side. Example: T3 rewrote `from .core import X` and T4 added `from .audio import engine`; resolution keeps both.
- If a pre-existing breakage sits outside the current issue's scope, leave it alone and note it in the PR — do not expand scope.

Re-run smoke, commit merge, push. PR state should flip to `MERGEABLE / CLEAN`.

## Merge

Only when user says to merge:

```bash
gh pr merge <N> --merge --delete-branch
```

Use `--merge` (merge commit), not `--squash`, when the base branch is an integration line that accumulates a stack — the individual commits carry per-issue history. Confirm with the user if unsure.

## Cleanup

After merge, remove the worktree if the parent thread will not need it again:

```bash
git worktree remove .claude/worktrees/agent-<hex>
```

## Guardrails

- **Never open a PR to `main`** unless the user explicitly names `main` as the base. The most common mistake on this repo is defaulting to `main` when an integration branch exists.
- **Never force-push, never `reset --hard`** on the feature branch after the PR is open — reviewers may have already fetched it.
- **Never skip the smoke** to "just get the PR up". Smoke is cheap; a red PR wastes a review round.
- **Never rename or delete files outside the issue's stated scope.** If you spot unrelated rot (stale `__all__` entries, dead imports), mention it in the PR body — do not fix it.
