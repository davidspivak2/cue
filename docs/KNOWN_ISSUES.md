# Known Issues (Detailed Tracking)

Purpose:
- This file stores detailed bug write-ups (repro steps, expected vs actual, risks, and validation plans).
- Scheduling and priority stay in [`ROADMAP.md`](ROADMAP.md).

Working rules:
- Keep issue write-ups concrete and reproducible.
- Keep fixes scoped; do not change unrelated behavior.
- Update the matching ROADMAP queue item when status changes.

Status legend:
- `OPEN`: confirmed and not yet implemented.
- `IN PROGRESS`: implementation work is active.
- `BLOCKED`: waiting on dependency/decision.
- `DONE`: verified and regression-checked.

---

## KI-015 - SRT and word_timings.json retained for diagnostics when diagnostics disabled

- Status: `OPEN`
- Priority: High
- Tracked in roadmap: Queue item 17 (`Diagnostics leftovers cleanup (diagnostics disabled)`)
- Primary code pointers:
  - `app/backend_server.py` (diagnostics/settings wiring)
  - `app/workers.py` and artifact retention/cleanup paths

User impact:
- Users who disabled diagnostics still get diagnostics-only leftovers in project paths, which is unexpected and adds clutter.

Repro steps:
1. In Settings, disable diagnostics.
2. Process a video through Create subtitles.
3. Inspect the project folder for retained SRT and `word_timings.json` artifacts that exist only for diagnostics retention.

Expected:
- When diagnostics are disabled, diagnostics-only SRT and `word_timings.json` artifacts are not created or retained.
- Project artifacts required for normal editing/export can still exist.

Actual:
- SRT and `word_timings.json` leftovers are still present from diagnostics retention paths even with diagnostics disabled.

Likely cause / notes:
- Diagnostics-off gating is incomplete around artifact creation/retention paths.

Minimum-scope fix:
- Gate diagnostics-only artifact creation/retention behind diagnostics-enabled checks while preserving required edit/export artifacts.

Risks / regressions:
- Cleanup changes must not remove artifacts needed by normal project editing/export behavior.

Validation checklist:
- With diagnostics disabled, no diagnostics-only SRT/`word_timings.json` leftovers remain.
- Editing/export flows continue to work with required project artifacts intact.

---

## Capture checklist for issue evidence

- Project folder tree with diagnostics disabled showing SRT/`word_timings.json` retention (KI-015).
