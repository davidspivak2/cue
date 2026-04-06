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

## KI-016 - Multi-video queue: stuck on “creating subtitles” until other jobs finish; possible repeated transcription steps

- Status: `OPEN`
- Priority: Medium (needs investigation to confirm frequency and exact trigger)
- Tracked in roadmap: Queue item 14 (`Multi-queue transcription: progress and navigation (KI-016)`)

User impact:
- With several videos queued for transcription, after the first video completes transcription the UI can remain on the “creating subtitles” progress screen until the other queued videos also finish, instead of opening the editor for that video as soon as it is ready.
- In some cases (conditions unclear), transcription-related steps for a video may appear to run again after other videos in the queue complete.

Repro steps:
1. Queue multiple videos for transcription (exact count and order may matter; capture when reproducing).
2. Let the first video complete its transcription pipeline.
3. Observe whether navigation to the editor happens immediately or the progress UI stays up until remaining jobs finish.
4. If steps repeat, note queue size, completion order, and any errors in logs.

Expected:
- When a video’s transcription and subtitle creation for that video are done, the app should proceed to the editor (or the next appropriate step) for that video without waiting for unrelated queued videos.
- Transcription steps for a given video should not re-run spuriously after sibling jobs complete.

Actual:
- Progress can appear to block on “creating subtitles” until other videos finish.
- Transcription UI steps may sometimes repeat after other videos finish (needs confirmation).

Likely cause / notes:
- Possible race or shared state between concurrent/sequenced transcription jobs and the navigation/progress state machine; needs tracing in frontend progress handling and backend job completion ordering.

Minimum-scope fix:
- TBD after investigation: ensure per-video completion drives UI and routing independently; guard against duplicate step transitions when sibling jobs complete.

Risks / regressions:
- Fixes must not break single-video flows or legitimate re-runs when the user explicitly retries.

Validation checklist:
- Multi-video queue: first completed video opens editor promptly; no duplicate step spam; remaining videos still process correctly.

---

## Capture checklist for issue evidence

- Project folder tree with diagnostics disabled showing SRT/`word_timings.json` retention (KI-015).
- Multi-video transcription queue: logs and screen recording for KI-016 (completion order, stuck progress, repeated steps).
