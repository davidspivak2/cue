# Workbench Guardrails

Use this when reviewing or authoring Workbench-heavy PRs. The goal is to reduce regressions from mixed state ownership, large in-place rewrites, and timing-based test patches.

## Author requirements

- Fill in the PR template sections for `State ownership map`, `Fallback matrix`, `Regression risk`, and `How tested`.
- Name one canonical writer for each user-visible value or behavior you changed.
- If the PR changes more than 200 lines inside `desktop/src/pages/Workbench.tsx`, extract a hook, component, or pure helper in the same PR, or explain why the large edit is temporary and localized.
- Prefer observable Playwright waits over raw sleeps. If a sleep is still needed for animation-only behavior, keep it behind a named constant and add a short reason comment.

## Reviewer checklist

- Can each changed user-visible value be traced back to one canonical writer?
- Do fallback paths keep the UI usable without inventing a second source of truth?
- If `Workbench.tsx` changed heavily, did the PR extract a helper/hook/component or justify why not?
- Do Workbench E2E edits wait on visible state, geometry stability, or data readiness instead of ad hoc timeouts?
- Does the PR say what happens when timings are present, timings are missing or stale, and overlay rendering fails?

## Example state ownership map

| User-visible value / behavior | Canonical writer | Allowed fallback | Why this is safe |
| --- | --- | --- | --- |
| Preview highlighted word index in Workbench | `resolveHighlightWordIndexFromTimings(...)` using fresh `wordTimingsDoc` | `null` means no timed-word progression | Missing or stale timing data degrades to a static preview instead of guessing |
| Preview overlay image path | `previewOverlay(...)` response stored in `subtitleOverlayPath` | `null` keeps DOM subtitle preview active | Overlay failure does not blank the editor or subtitle text |

## Example fallback matrix

| Scenario | Expected behavior | Notes |
| --- | --- | --- |
| Timings present and fresh | Use aligned word timings to derive the active highlighted word | No evenly distributed approximation |
| Timings missing or stale | Keep preview usable and return `null` highlighted word index | No synthetic word progression |
| Overlay render request fails | Clear `subtitleOverlayPath` and keep DOM subtitle preview usable | Failure is non-fatal and should stay visible in logs only |
