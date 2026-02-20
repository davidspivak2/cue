# Session handoff — Progress truthfulness, runner early emit, in-process worker

**Date:** 2026-02-19  
**Project:** Cue (C:\Cue_repo)  
**Purpose:** Hand off context after implementing Queue 9–related work (progress surface, runner first event, run worker in backend process). Next agent can fix remaining issues (elapsed timer reset, optional UI polish).

---

## Current state summary

- **Queue 9 (Progress truthfulness + continuity)** is partially addressed:
  - **Runner early emit:** [app/qt_worker_runner.py](app/qt_worker_runner.py) now emits "started" and progress (0%, "Preparing...") right after minimal validation and before loading PySide6/Worker, so the first event from the runner can arrive in hundreds of ms when the runner process is used.
  - **In-process worker:** Create-subtitles and create-video-with-subtitles jobs can run **inside the backend process** in a thread ([app/backend_inprocess_worker.py](app/backend_inprocess_worker.py)), so there is **no 25s cold start** when in-process is used. The backend tries in-process first (single slot, one job at a time); if the in-process slot is busy or PySide6 fails, it falls back to spawning CueRunner.exe.
  - **Thread-safe enqueue:** [app/backend_server.py](app/backend_server.py) uses `JobState.enqueue_lock` and sets `job.status` / `job.finished_at` when terminal events are enqueued so both runner and in-process paths behave consistently.

- **Known issue — elapsed timer reset:** When a "started" event is received from the runner (or in-process), the frontend **overwrites** `createSubtitlesStartedAt` / `exportStartedAt` with `event.ts`. If that event is the runner’s "started" (with a timestamp from when the backend received it, e.g. ~25s later when using subprocess), the elapsed timer effectively resets. **Fix:** In [desktop/src/pages/Workbench.tsx](desktop/src/pages/Workbench.tsx), when handling "started", only set startedAt if not already set, or use the **earlier** of current startedAt and `event.ts` so the timer never moves backward. Same for export in `handleExportEvent`.

- **Optional remaining Queue 9 items (see ROADMAP):** Show checklist optimistically when user clicks "Create subtitles"; ensure progress/detail text reflects pre-transcription work (e.g. when `duration_seconds` is None during extraction, consider indeterminate or synthetic progress).

---

## Important context for next agent

1. **In-process vs runner:** `_run_worker_job_maybe_inprocess` uses `_inprocess_slot_lock`; if the lock is free it runs the worker in a thread via `run_worker_inprocess`; if locked or if that raises, it falls back to `_run_runner_job` (subprocess). Cancel for in-process is done by a watcher task that waits on `job.cancel_event` and then calls `worker_ref[0].cancel()`.
2. **Event contract:** In-process events match the runner (started, progress with pct/step_id/message, checklist, log, result, completed/cancelled/error). `_maybe_update_project_from_runner_event` is called from the same `enqueue_event_cb` so project status updates for in-process too.
3. **Timer reset root cause:** `handleCreateSubtitlesEvent` and `handleExportEvent` do `setCreateSubtitlesStartedAt(asString(event.ts) ?? ...)` / `setExportStartedAt(asString(event.ts) ?? ...)` on every "started" event. The **first** startedAt is set when the user clicks (client time). A later "started" from the runner has `ts` = backend time when that event was built, which can be much later → timer resets. Fix is to never replace startedAt with a **later** timestamp.

---

## Immediate next steps

1. **Fix elapsed timer reset (high priority):**
   - In [desktop/src/pages/Workbench.tsx](desktop/src/pages/Workbench.tsx), in `handleCreateSubtitlesEvent` for `event.type === "started"`: only call `setCreateSubtitlesStartedAt(...)` if the new value is **earlier** than the current `createSubtitlesStartedAt`, or if `createSubtitlesStartedAt` is null. Same logic in `handleExportEvent` for export startedAt.
   - Option: use a ref to hold "job start time" set once when the job is started from the UI and never overwrite it from events.

2. **Optional — Queue 9 / ROADMAP:**  
   - Show Create Subtitles checklist (and first step "Extracting audio") as soon as the user clicks "Create subtitles", before the first event arrives, so 0% is contextualized.  
   - If still using subprocess runner in some flows: consider backend sending an initial progress (0%, "Preparing...") when the job is created so the UI never shows a generic stall.

3. **Verify in-process in packaged build:** Confirm the packaged backend has PySide6 and that in-process path is used (no 25s stall). If not, fallback to runner is expected; timer fix still matters when runner’s "started" arrives late.

---

## Critical files

| Area | File | Notes |
|------|------|--------|
| Backend | [app/backend_server.py](app/backend_server.py) | `JobState.enqueue_lock`, `_run_inprocess_worker_job`, `_run_worker_job_maybe_inprocess`, terminal status set in `_update_job_snapshot`. |
| Backend | [app/backend_inprocess_worker.py](app/backend_inprocess_worker.py) | `run_worker_inprocess`; uses qt_worker_runner helpers for settings/style/progress. |
| Runner | [app/qt_worker_runner.py](app/qt_worker_runner.py) | Early emit block (logging, validation, started + progress "Preparing...") before PySide6. |
| Frontend | [desktop/src/pages/Workbench.tsx](desktop/src/pages/Workbench.tsx) | `handleCreateSubtitlesEvent` / `handleExportEvent` — startedAt overwrite causes timer reset; `createSubtitlesStartedAt` set at ~1273 and ~1147. |
| Docs | [docs/internal/ROADMAP.md](docs/internal/ROADMAP.md) | Queue 9 — Progress truthfulness + continuity; Milestone 5.2 (pre-transcription progress). |

---

## Decisions made

- **Run worker in backend process** (not warm runner process): simpler, one process, no extra protocol; matches PySide6 app model.
- **Single in-process slot:** only one create_subtitles/create_video_with_subtitles job at a time in-process; second job uses subprocess runner.
- **Terminal status in _update_job_snapshot:** when a terminal event is enqueued (from any path), we set `job.status` and `job.finished_at` there so in-process and runner both update job state consistently.

---

## References

- Queue 9: [docs/internal/ROADMAP.md](docs/internal/ROADMAP.md) (lines 114–126).
- Milestone 5.2 (pre-transcription): same file, ~483–490.
- Plan used for in-process: run worker in backend process (remove 25s cold start).
