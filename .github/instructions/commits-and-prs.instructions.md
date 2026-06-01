---
applyTo: "**"
---

# Git Commits and Pull Requests

## Atomic commits

One commit = one logical change. A logical change is the smallest unit that leaves the codebase in a working state.

**Good — one concern per commit:**
```
feat(datasets): add CSV importer with lat/lon column detection
feat(datasets): add Dataset and Tree models with migrations
test(datasets): add unit tests for CSV importer edge cases
```

**Bad — mixed concerns:**
```
add datasets model and fix login bug and update readme
```

Split commits when a single diff touches:
- A model change AND a view change (separate: model first, then view)
- A feature AND a bug fix unrelated to it
- Application code AND test code for different features

Tests for a feature commit in the same commit as that feature — they are one logical unit.

## Commit message format

```
<type>(<scope>): <subject>

[optional body — only when WHY is not obvious from subject]
```

**Types:** `feat`, `fix`, `refactor`, `test`, `chore`, `docs`

**Scopes:** `datasets`, `optimization`, `routes`, `accounts`, `core`, `docker`, `frontend`

**Subject rules:**
- Imperative mood: "add", "fix", "remove" — not "added", "fixing"
- No capital first letter
- No period at end
- Max 72 characters
- Describe what changes, not how

**Body:** Only when the commit fixes a non-obvious bug or makes a non-obvious architectural decision. Reference the constraint, not the task.

**Examples:**
```
feat(optimization): add OSRM cost matrix builder with SHA256 cache

fix(solver): subtract 1 from OR-Tools node index to remove dummy depot offset

test(datasets): add CSV importer tests for missing lat/lon columns

chore(docker): add start_period to OSRM healthcheck for PBF processing delay
```

## Pull Requests

**One PR = one feature or one fix.** A PR that spans multiple unrelated features is rejected at review.

PR title follows the same format as commit subject: `type(scope): subject`.

PR description must include:
1. What changed (one sentence)
2. How to test it manually (specific curl/browser steps)
3. Any migration to run

Do not open a PR with:
- Failing tests
- Debug prints or `console.log` left in code
- TODO comments that aren't tracked in the backlog
- Commented-out code blocks

## Branch naming

```
feat/datasets-csv-import
fix/solver-dummy-depot-offset
refactor/pipeline-error-handling
```

Always branch from `main`. Rebase before opening PR if `main` has diverged.
