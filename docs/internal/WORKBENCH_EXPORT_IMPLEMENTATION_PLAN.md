# Workbench Export Implementation Playbook

This document is the implementation reference for moving export fully into the
new Workbench flow.

## Goal

Ship a Workbench-only export flow that:

- Starts export from Workbench (no `/legacy` or `/review` dependency).
- Uses project artifacts (edited subtitles + project style + word timings).
- Shows in-Workbench export progress, cancel, and success actions.
- Keeps project status accurate in Projects and Workbench.

## Locked Decisions

- New app only flow: `Projects -> Workbench -> Export`.
- Project-first backend contract: export can be started with `project_id`.
- Project-scoped style for export.
- Backward compatibility can exist temporarily for explicit path payloads.

## Data + API Contract

### Frontend request (preferred)

`POST /jobs` with:

- `kind = "create_video_with_subtitles"`
- `project_id`
- optional `output_dir`
- optional `options`

### Backend behavior

When `kind=create_video_with_subtitles` and `project_id` is provided:

1. Resolve project artifacts from project storage:
   - video path
   - subtitles path
   - word timings path
   - style path
2. Validate all required artifacts.
3. Build runner command from resolved paths.
4. Stream SSE events with existing event schema.
5. Update project status to `exporting` on start and `done` on success.

## Word Timings Rule

Project artifacts use `word_timings.json`, while legacy derivation from SRT uses
`subtitles.word_timings.json`. Export must support explicit project
`word_timings.json` path to avoid mismatches.

## Style Rule

Export style must come from project style artifact (`style.json`) with safe
normalization and fallback defaults if missing/corrupt.

## Workbench UI State Machine

Workbench should support:

- `WB_SUBTITLES_READY`: show primary CTA "Create video with subtitles".
- `WB_EXPORTING`: checklist + determinate progress + cancel.
- `WB_EXPORT_SUCCESS`: play/open folder + allow re-export.

During `WB_EXPORTING`, editing/styling controls are disabled.

## File-by-File Work Checklist

### Backend

- `app/project_store.py`
  - add helper to resolve absolute export artifact paths by `project_id`
- `app/backend_server.py`
  - support project-first validation and request resolution
  - pass resolved paths to runner command

### Runner + Worker

- `app/qt_worker_runner.py`
  - accept `--style-path` and `--word-timings-path`
  - load + normalize project style
- `app/workers.py`
  - accept explicit word timings path
  - prefer explicit path over derived path
  - include compatibility fallback for project naming

### Frontend

- `desktop/src/jobsClient.ts`
  - support project-first export payload
- `desktop/src/pages/Workbench.tsx`
  - export CTA + progress + cancel + success
  - job event handlers for export
  - disable editing/styling during export
- `desktop/src/projectsClient.ts`
  - include project style + latest export fields needed by Workbench

### Legacy cleanup

- `desktop/src/App.tsx`
  - remove export routes once Workbench flow is validated
- `desktop/src/pages/Home.tsx` and `desktop/src/pages/Review.tsx`
  - remove or deprecate export-related code paths

## Testing Matrix

### Frontend E2E

- Export CTA visibility in Workbench when subtitles exist.
- Export progress rendering + checklist updates.
- Cancel export.
- Success state actions ("Play video", "Open folder").
- Editing disabled during export.
- Export continuity after navigating away and back.

### Backend tests

- Project-first export request validation.
- Artifact resolution failure modes.
- Project status transitions during export.
- Export result persistence to `latest_export`.

## Acceptance Criteria

- Export is fully usable from Workbench.
- No user-facing dependence on `/legacy` or `/review` for export.
- Export output reflects project subtitles and project style.
- Word highlight export works with project word timings.
- Tests pass for updated frontend and backend coverage.
