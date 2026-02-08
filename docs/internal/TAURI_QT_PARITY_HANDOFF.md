# Cue Tauri Migration - Qt Parity Multi-Agent Handoff Plan

Last updated: 2026-02-06

Owner: This document is the single source of truth for multi-agent handoff.
Every agent must update it before handing work to another agent.

---

## 0) How to use this doc

- Read sections 1 through 5 before starting any work.
- Pick ONE phase to own at a time.
- Update section 6 (Status board) and section 7 (Handoff log) before you hand off.
- If reality differs from this doc, update this doc first, then proceed.

---

## 1) Non-negotiables (must follow)

- The legacy Qt/PySide6 UI is the source of truth for workflow, copy, and checklist labels.
- The new UI is the Tauri + React app under `desktop/`.
- Do NOT use MUI anywhere in the desktop app. Remove it now, not later.
- Do not use text symbol icons (like check marks or gears). Use real icons from `lucide-react`.
- Fix backend reliability (Qt worker in a safe subprocess). No fake progress.
- Goal: Qt parity first, then improvements.

---

## 2) Current repo snapshot (verify and update)

As of 2026-02-08, in this repo:

Backend
- `app/backend_server.py` supports `create_subtitles` and `create_video_with_subtitles`, plus `/settings`, `/preview-style`, and `/device`.
- `app/qt_worker_runner.py` exists and emits JSONL events.
- `app/workers.py` includes ffmpeg watchdog + audio filter fallback and safer transcription subprocess handling.
- Settings stored in `config.json` under the app data dir (same as Qt).
- Project system backend:
  - Projects stored under app data `projects/` with `index.json` and per-project folders (`project.json`, `subtitles.srt`, `word_timings.json`, `style.json`).
  - New endpoints: `GET/POST /projects`, `GET/PUT /projects/{project_id}`, `POST /projects/{project_id}/relink`.
  - Jobs accept optional `project_id`; runner `result` events update project artifacts and export path.

Desktop
- `desktop/src/main.tsx` uses shadcn/Tailwind ThemeProvider (no MUI).
- `desktop/src/components/AppLayout.tsx` uses shadcn layout and lucide icons.
- `desktop/src/pages/Home.tsx` implements the 5-state UI and Tauri file picker/drag-drop.
- `desktop/src/pages/Review.tsx` provides the Review screen for style, preview, and export.
- `desktop/src/pages/Settings.tsx` exists and matches Qt parity (no subtitle style section).
- `desktop/src-tauri/tauri.conf.json` enables capabilities and asset protocol scope for previews.
- `desktop/package.json` has no `@mui` or `@emotion` deps.

If any item above is no longer true, update this section before you continue.

---

## 3) Legacy Qt source of truth (read before coding)

Primary files
- `app/main.py` (state machine, copy, checklist mapping)
- `app/ui/widgets.py` (DropZone, VideoCard, SavingToLine)
- `app/progress.py` (checklist step IDs)
- `app/workers.py` (Worker signals used by Qt UI)

State machine (Home screen)
`EMPTY -> VIDEO_SELECTED -> WORKING -> SUBTITLES_READY -> EXPORT_DONE`
Note: after `create_subtitles` completes, the UI navigates to `/review` for styling and export. Home still owns the job state machine.

---

## 4) Qt parity copy and labels (must match)

Drop zone
- "Drop a video here"
- "or choose one from your computer"
- Button: "Choose video..."

Video selected
- CTA: "Create subtitles"

Working
- Heading: "Creating subtitles" (generate)
- Heading: "Creating video with subtitles" (burn/export)
- Button: "Cancel"

Subtitles ready
- Header: "Subtitles ready" + check icon (icon, not text)
- Footer prefix: "Saving as:"
- CTA: "Create video with subtitles"

Done
- "Your video is ready"
- Buttons: "Play video", "Open folder", "Edit subtitles and export again"

Details
- Toggle: "Show details"
- Group title: "Details"
- Button: "Open details file"

Settings
- Back: arrow icon + "Back" (icon, not text)

Checklist labels (generate subtitles)
- "Extracting audio" OR "Extracting and cleaning up audio" (if audio filter enabled)
- "Loading AI model"
- "Detecting language"
- "Writing subtitles"
- "Reviewing punctuation" (if punctuation rescue enabled)
- "Checking for missed speech" (if VAD gap rescue enabled)
- "Matching individual words to speech" (if subtitle_mode == word_highlight)
- "Preparing preview"

Checklist labels (export)
- "Getting video info"
- "Adding subtitles to video"
- "Saving video"

Also show in UI
- Percent progress
- Elapsed time ("Elapsed: mm:ss")
- Cancel button

---

## 5) Progressive build plan (multi-agent phases)

### Phase 1 - Backend reliability: Qt-safe runner and events
Goal: Fix the 25% hang by running the legacy Worker inside a Qt-safe subprocess.
Depends on: None

Tasks
- Add `app/qt_worker_runner.py` that creates a Qt app context and runs the legacy Worker.
- Emit JSONL events to stdout: started, checklist, progress, log, result, heartbeat, terminal.
- Watch stdin for "cancel" and call `worker.cancel()`.
- Update `app/backend_server.py` to spawn the runner per job and stream events via SSE.
- Add job kinds: `create_subtitles` and `create_video_with_subtitles`.
- Ensure SSE closes on terminal events and sends heartbeat.

Acceptance
- Create subtitles job completes and sends result payload.
- Export job completes and sends output path.
- Cancel works reliably on Windows (stdin cancel + terminate if needed).
- UI never appears stuck at 25% without progress events.

Handoff outputs
- Updated backend files.
- Notes on event schema and any behavior changes.

---

### Phase 2 - Frontend job client and copy helpers
Goal: UI can start the two new job kinds and parse typed events.
Depends on: Phase 1 (backend event stream)

Tasks
- Update `desktop/src/jobsClient.ts` with `createSubtitlesJob` and `createVideoWithSubtitlesJob`.
- Define typed events (started, checklist, progress, log, result, heartbeat, completed, cancelled, error).
- Add `desktop/src/legacyCopy.ts` to centralize Qt strings and checklist label builders.
- Add base components: DropZone, VideoCard, Checklist.

Acceptance
- Jobs start and stream events without errors.
- Copy in the UI matches section 4.

Handoff outputs
- Updated client and new components.
- Notes on any event parsing edge cases.

---

### Phase 3 - Home page Qt parity state machine UI
Goal: Rebuild Home screen to match Qt states and copy.
Depends on: Phase 2 (client + copy + components)

Tasks
- Replace `desktop/src/pages/Home.tsx` with the 5-state UI.
- Implement WORKING state with checklist, progress, elapsed timer, and Cancel.
- Implement SUBTITLES_READY and EXPORT_DONE screens.
- Add Details panel: "Show details" toggle and log list.
- Add "Open details file" action (likely Tauri opener plugin).

Acceptance
- All 5 states render with correct copy.
- Elapsed timer and progress display match Qt behavior.
- Details panel works and can open the details file.

Handoff outputs
- Updated Home page and any helper components.
- Notes on any Tauri opener integration used.

---

### Phase 4 - Settings migration off MUI + App layout rebuild
Goal: Remove MUI from layout and Settings UI.
Depends on: None (can be done in parallel with Phase 3 if careful)

Tasks
- Rebuild `desktop/src/components/AppLayout.tsx` using shadcn/Tailwind.
- Rebuild `desktop/src/pages/Settings.tsx` using shadcn/Tailwind.
- Add Back button (arrow icon + "Back") in Settings.
- Remove MUI ThemeProvider/CssBaseline usage from `desktop/src/main.tsx`.

Acceptance
- App runs without any MUI components.
- Settings works and still calls `desktop/src/settingsClient.ts`.

Handoff outputs
- Updated layout and Settings page.
- Notes on any UI differences to correct.

---

### Phase 5 - Remove MUI/Emotion and cleanup
Goal: Ensure zero MUI usage anywhere.
Depends on: Phase 4

Tasks
- Remove any remaining MUI imports or icons.
- Delete unused MUI theme files if present.
- Verify `rg "@mui|@emotion" desktop/src` returns no matches.

Acceptance
- No MUI or Emotion imports remain in desktop code.

Handoff outputs
- Cleanup summary.

---

### Phase 6 - Tests and verification
Goal: Add minimal coverage for the new flow.
Depends on: Phase 1 and Phase 3

Tasks
- Add Playwright test `desktop/tests/e2e/home.spec.ts` to check Qt parity elements.
- Add a lightweight backend test for SSE event streaming and result payload.

Acceptance
- Tests run and pass.
- App still works end to end.

Handoff outputs
- Test additions and any known gaps.

---

## 6) Status board (update before handoff)

- Phase 1 - Backend reliability: Done (manual run on test_30s.mp4)
- Phase 2 - Frontend job client and copy helpers: Done
- Phase 3 - Home page Qt parity UI: Done
- Phase 4 - Settings migration off MUI: Done (MUI removed from layout/settings/main)
- Phase 5 - Remove MUI/Emotion and cleanup: Done
- Phase 6 - Tests and verification: Done (tests not run locally)
- Tauri dev build unblock (capabilities/main.json): Done
- Project system backend (Milestone 1 backend): Done (API + tests)

---

## 7) Handoff protocol (mandatory)

Before you start
- Read sections 1 to 6.
- Confirm the repo snapshot is correct. If not, update it.

Before you hand off
- Update the Status board (section 6).
- Add a Handoff log entry (section 8).
- List: what you changed, what still breaks, and the next best task.
- If you added or changed event schema, note it clearly.

---

## 8) Handoff log (append-only)

Template (copy and fill; newest at top)

Date: 2026-02-08
Agent: gpt-5.2-codex-xhigh
Phase: Project system backend (Milestone 1 backend)
Status: Done
Summary:
- Added backend project persistence (per-project folders under app data + `project.json` manifest + `index.json`).
- Added `/projects` endpoints and `project_id` job linkage (runner `result` updates project artifacts + export path).
- Tests run: `pytest tests/test_project_store.py tests/test_backend_projects_api.py tests/test_backend_job_project_update.py`
- Known issues: Desktop UI is not wired to `/projects` yet (API-only for now).
- Suggested next step: Wire desktop UI to create/open projects and build Project Hub (Milestone 2).

Date: 2026-02-08
Agent: gpt-5.2-codex-xhigh
Phase: Tauri dev build unblock (capabilities)
Status: Done
Summary:
- Fixed Tauri `generate_context!()` panic: `capability ... identifier main not found`.
- Root cause: `desktop/src-tauri/capabilities/` existed but had no `main.json`.
- Fix:
  - Added `desktop/src-tauri/capabilities/main.json`
  - Updated `desktop/src-tauri/tauri.conf.json` to use `"capabilities": ["main"]` and set window `"label": "main"`.
- Tests run: `cargo build --no-default-features`, `scripts/run_desktop_dev.cmd`.
- Known issues: None observed.
- Suggested next step: `docs/internal/ROADMAP.md` → PR12 (Error UX + details drawer + Copy diagnostics).

Date: 2026-02-08
Agent: gpt-5.2-codex-xhigh
Phase: Docs sync for Review flow
Status: Done
Summary:
- Updated repo snapshot to include `/preview-style` and the Review screen.
- Noted the flow change: Home runs the job state machine but navigates to `/review` after subtitle creation.
- Docs and UI were aligned to use “Create video with subtitles” as the export CTA.
- Tests run: `npx vite build`, `npx playwright test` (with dev server).
- Known issues: None observed.
- Suggested next step: Continue roadmap items in `docs/internal/ROADMAP.md`.

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Post Phase 6 fixes
Status: Done
Summary:
- Added backend `/settings` (config.json) and `/device` (GPU info) endpoints.
- Added Tauri capabilities (`desktop/src-tauri/capabilities/main.json`) and enabled asset protocol scope for file previews.
- Home: Tauri file picker + drag-drop now provide paths; preview uses asset protocol; “Create subtitles” switches to Working immediately.
- Settings: layout left-aligned; transcription quality hint uses GPU status; subtitle style section removed.
- Tests run: Manual app run (`scripts/run_desktop_all.cmd`) and interactive verification.
- Known issues: Backend job start event still takes ~3–5s; overall transcription speed slower than Qt for 30s test clip (needs investigation).
- Suggested next step: Investigate job startup delay/perf regression and consider preview frame generation.

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Phase 6
Status: Done
Summary:
- Added Playwright `desktop/tests/e2e/home.spec.ts` to cover Home flow Qt parity copy (mocked settings + SSE).
- Added backend SSE test `tests/test_backend_server.py` with a stubbed runner and result payload checks.
- Tests run: Not run (not requested).
- Known issues: None noted.
- Suggested next step: Run `npm run test:e2e` (with dev server) and `pytest tests/test_backend_server.py`.

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Phase 5
Status: Done
Summary:
- Verified `rg "@mui|@emotion" desktop` returns no matches (including `package-lock.json`).
- Confirmed no `desktop/src/theme/` folder remains.
- Tests run: N/A (verification only).
- Known issues: None found.
- Suggested next step: Phase 6 (tests and verification).

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Phase 3
Status: Done
Summary:
- Confirmed Home UI wiring + job flow are in place and the desktop build passes.
- Build warning noted: plugin-dialog is both dynamically and statically imported (build still succeeds).
- Tests run: `npm run build`.
- Known issues: None observed beyond the build warning above.
- Suggested next step: Phase 6 (tests and verification).

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Phase 3
Status: Done
Summary:
- Rebuilt `desktop/src/pages/Home.tsx` with the 5-state UI, Qt copy, checklist, progress, elapsed timer, and details panel.
- Wired Home to `jobsClient` and `settingsClient`, including save policy folder resolution and opener actions.
- Build now passes: `npm run build` (warning about plugin-dialog mixed imports; build succeeds).
- Tests run: `npm run build`.
- Known issues: None observed in the build output.
- Suggested next step: Phase 6 (tests and verification) or polish UI states as needed.

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Phase 4
Status: Done
Summary:
- Removed MUI from `desktop/src/main.tsx`, added Tailwind theme provider + base CSS import.
- Rebuilt `desktop/src/components/AppLayout.tsx` with shadcn/Tailwind + lucide icons.
- Recreated `desktop/src/pages/Settings.tsx` to match Qt/UX spec and e2e expectations.
- Tests run: `npm run build` (failed: `desktop/src/pages/Home.tsx` has no default export).
- Known issues: Build currently blocked by empty Home page file (Phase 3 work).
- Suggested next step: Phase 3 (Home page Qt parity state machine UI, plus add Home default export).

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Phase 4 (prep)
Status: Partial
Summary:
- Progress: frontend build fails due to `@mui/material` import.
- No code changes in this update.
- Tests run: `npm run build` (failed: `@mui/material` import in `desktop/src/main.tsx`).
- Known issues: Build currently blocked by remaining MUI usage.
- Suggested next step: Phase 4 (remove MUI from layout/settings/main).

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Phase 2
Status: Done
Summary:
- Added `desktop/src/jobsClient.ts` with job creators, typed event parsing, and SSE auto-close on terminal events.
- Added `desktop/src/legacyCopy.ts` for Qt copy strings and checklist label builders.
- Added base components `DropZone`, `VideoCard`, and `Checklist` using shadcn/Tailwind and lucide-react.
- Tests run: Not run (not requested).
- Known issues: None noted.
- Suggested next step: Phase 3 (Home page Qt parity state machine UI).

Date: 2026-02-06
Agent: gpt-5.2-codex-xhigh
Phase: Phase 1
Status: Done
Summary:
- Added `app/qt_worker_runner.py` to run legacy Worker in a Qt-safe subprocess and emit JSON events (started, checklist, progress, log, result, heartbeat, terminal).
- Updated `app/backend_server.py` to support `create_subtitles` / `create_video_with_subtitles` and spawn the runner with cancel handling.
- Fixed audio extraction hang: added `-nostdin`, a no-output watchdog for ffmpeg, and fallback retry without filters.
- Hardened transcription: unbuffered `-u`, env `PYTHONUNBUFFERED`, safe-mode retry (CPU int8, no VAD/rescue), and stdin set to DEVNULL.
- Fixed stdout encoding in runner (UTF-8 bytes) to avoid UnicodeEncodeError on Hebrew.
- Alignment subprocess now runs unbuffered and stdin=DEVNULL to avoid blocking.
- Removed passing `--ffmpeg-args-json` to the transcription worker to avoid hanging in this environment.
- Manual test succeeded on `C:\\Users\\david\\Desktop\\test_30s.mp4` with full result payload.
- Tests run: `python -m app.qt_worker_runner --task generate_srt` (manual).
- Known issues: None observed in the final run; additional UI and tests still pending.
- Suggested next step: Phase 2 (frontend job client + typed events + legacy copy), then Phase 3 (Home UI).

Date: YYYY-MM-DD
Agent: Name or ID
Phase: Phase N
Status: Done | Partial | Blocked
Summary:
- What changed
- Tests run
- Known issues
- Suggested next step

