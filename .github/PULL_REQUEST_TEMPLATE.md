## What changed?

Describe the change in a few sentences.

## Why?

Explain the user problem, bug, or product goal this solves.

## State ownership map

Required for Editor-heavy PRs. Name one canonical writer for each user-visible value or behavior you changed.

| User-visible value / behavior | Canonical writer | Allowed fallback | Notes |
| --- | --- | --- | --- |
| Example: Preview highlighted word index | `resolveHighlightWordIndexFromTimings(...)` fed by fresh `wordTimingsDoc` | `null` means no timed-word progression | Remove example rows and add your own |

## Fallback matrix

Required for Editor-heavy PRs. Show what happens when the happy path is unavailable.

| Scenario | Expected behavior | Covered by |
| --- | --- | --- |
| Example: Word timings missing or stale | Keep preview usable and do not synthesize timed highlighting | `desktop/tests/e2e/workbench-preview-timing.spec.ts` |

## Regression risk

Required for Editor-heavy PRs.

- Primary regression risk:
- Secondary regression risk:
- Rollback or containment:

## How tested

1. ...
2. ...
3. ...

## Screenshots (if UI changes)

<!-- Add before/after screenshots if this PR changes the UI. -->

## Checklist

- [ ] Tested locally (app launches, core flow works)
- [ ] No new linter errors introduced
- [ ] Updated documentation if needed
- [ ] If this PR is Editor-heavy, I filled in the state ownership map and fallback matrix
