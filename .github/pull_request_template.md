## What and why

<!-- What does this change, and what problem does it solve? Link the issue: "Closes #123". -->

## Type

- [ ] Bug fix
- [ ] New pattern / pack
- [ ] Feature
- [ ] Docs / CI / chore

## Checklist

- [ ] `ruff check .` and `pytest` pass locally
- [ ] Tests added or updated for the change
- [ ] New patterns have tests for lines that **should** and **should not** match
- [ ] Still read-only: nothing new executes, restarts, deletes, or writes outside `--out-dir` / the history file
- [ ] No secrets, real hostnames, or customer data in tests or examples
- [ ] `CHANGELOG.md` updated under *Unreleased* (if user-facing)
- [ ] If `viewer.html` changed, `firstsignal/viewer.html` and `site/viewer.html` are still identical

## How I tested it

<!-- Commands you ran, sample input, before/after output. -->
