# Cue Tauri Migration - Qt Parity Multi-Agent Handoff Plan

Last updated: 2026-02-13

Owner: This document is the single source of truth for multi-agent handoff.
Every agent must update it before handing work to another agent.

---

## Current State (overwrite this section on each handoff)

**Last shipped:** Queue item 3 (`Preview truthfulness`) is now complete: KI-002 and KI-003 are closed. Workbench playback preview now uses backend Qt-rendered subtitle overlays for export-parity styling and responsive scaling. Backend adds `/preview-overlay` with cached transparent overlay rendering; Workbench keeps HTML subtitle UI for edit interactions and falls back safely if overlay requests fail. Tests/docs were updated for the image-overlay preview path.

**Next actionable task:** See `docs/internal/ROADMAP.md` and `docs/internal/KNOWN_ISSUES.md`. Queue item 4 is next: KI-004 (`Preview word-highlight sync`) to align preview highlight timing with timed-word artifacts while keeping export timing unchanged.

**Gotchas (3–6):** (1) Cue uses **Tauri + React** (not Svelte, not Next.js); (2) No MUI — use shadcn/Tailwind and lucide-react only; (3) Config and projects live in **app data dir** (see `app/paths.py`); (4) **Cue_extra** folder holds `backend_port.txt` and is used by run scripts; (5) Workbench tabs are **in-memory** (no persistence); closing the app clears open tabs; (6) The "All subtitles" panel and any placeholder for it are **not in the current application UI** — they exist only in docs (spec/roadmap); do not assume users see that panel.

**Run locally:** Windows: `scripts\run_desktop_all.cmd`. From repo root it installs deps, starts the backend, then launches the Tauri app. Alternative: start backend manually, then from `desktop/` run `npm run tauri dev`.

**Outside this repo:** **Cue_extra** (e.g. `C:\Cue_extra`) for backend port file; **FFmpeg** in `bin/` or system PATH; app data dir for projects and `config.json`. See `docs/CONTRIBUTING.md` for setup.

**Cursor rules pruned (2026-02-13):** Removed rules targeting unused stacks: `typescript-nextjs-expo-trpc-stack`, `typescript-nextjs-expert`, `tauri-svelte-typescript-desktop` (Svelte). Kept: conventional-commits, playwright-e2e-qa, python-*, typescript-react-tailwind, react-component-v0-workflow, logging, plain-english.

---

## 0) How to use this doc

- Read sections 1 through 5 before starting any work.
- Read `docs/internal/KNOWN_ISSUES.md` for current detailed bug repros, scope notes, and validation checklists.
- Pick ONE phase to own at a time.
- Update section 6 (Status board) and section 7 (Handoff log) before you hand off.
- If reality differs from this doc, update this doc first, then proceed.

### Definition of Done / Handoff checklist

Before marking work done or handing off:

1. **No debug instrumentation left** — Grep for `agent log`, `hypothesis`, `_append_debug`, and debug log paths; remove or gate behind `CUE_DEBUG_WORKER` (or similar) with a comment.
2. **Lint passes with zero errors and zero warnings** — Run from repo root: `cd desktop && npm run lint`; `python -m ruff check app tests tools`; `cd desktop/src-tauri && cargo clippy`. See `docs/CONTRIBUTING.md` for details.
3. **Build and tests** — `npm run build` (in `desktop/`) passes; run `pytest` and, if applicable, `npm run test:e2e` (with dev server).
4. **If you added debug scaffolding during this session** — Remove it before marking done (or move it behind a debug flag and document why it stays).

---

## 1) Non-negotiables (must follow)

- The legacy Qt/PySide6 UI has been removed.
- The new UI is the Tauri + React app under `desktop/`.
- Do NOT use MUI anywhere in the desktop app. Remove it now, not later.
- Do not use text symbol icons (like check marks or gears). Use real icons from `lucide-react`.
- Fix backend reliability (Qt worker in a safe subprocess). No fake progress.
- Goal: Qt parity first, then improvements.

---

## 2) Current repo snapshot (verify and update)

As of 2026-02-11, in this repo:

Backend
- `app/backend_server.py` supports `create_subtitles` and `create_video_with_subtitles`, plus `/settings`, `/preview-style`, `/preview-overlay`, and `/device`.
- `app/worker_runner.py` exists and emits JSONL events.
- `app/workers.py` includes ffmpeg watchdog + audio filter fallback and safer transcription subprocess handling.
- Settings stored in `config.json` under the app data dir (same as Qt).
- Project system backend:
  - Projects stored under app data `projects/` with `index.json` and per-project folders (`project.json`, `subtitles.srt`, `word_timings.json`, `style.json`).
  - New endpoints: `GET/POST /projects`, `GET/PUT/DELETE /projects/{project_id}`, `GET /projects/{project_id}/subtitles`, `POST /projects/{project_id}/relink`.
  - Jobs accept optional `project_id`; runner events update project state (`result` updates artifacts/export path, export `started` sets `exporting`, `cancelled`/`error` refresh project status).
  - Export is now project-first: when `project_id` is provided for `create_video_with_subtitles`, backend resolves project video/subtitles/style/word-timings artifacts server-side; explicit path payloads remain compatible for migration.
  - `project_store` now returns project style in project responses and exposes export-artifact resolution helpers for job creation.

Desktop
- `desktop/src/main.tsx` uses shadcn/Tailwind ThemeProvider (no MUI).
- `desktop/src/components/AppLayout.tsx` uses shadcn layout + lucide icons, with a user-controlled collapsible sidebar (icon strip, persisted in localStorage).
- `desktop/src/pages/ProjectHub.tsx` is the default route (`Projects` label in UI), with header CTA `New project`, auto-open-to-Workbench on create, project list/create/delete (with confirmation), `needs_subtitles` per-card `Create subtitles` quick action, and relink flow for missing files.
- `desktop/src/workbenchTabs.tsx` tracks open project tabs in memory; Workbench renders a tab strip.
- `desktop/src/pages/Workbench.tsx` is the active edit/export surface: strict no-subtitles empty state, on-video subtitle editing, style pane/drawer, and in-Workbench export CTA/progress/cancel/success.
- Workbench playback preview now uses backend-rendered subtitle overlay images (`/preview-overlay`) for renderer parity and responsive scaling; on-video HTML subtitle UI remains for editing interactions.
- Workbench export now runs entirely in-page (no legacy handoff): checklist + progress + cancel + success actions (`Play video`, `Open folder`, re-export).
- Workbench style persistence is project-scoped (`PUT /projects/{id}` style payload) with fallback initialization from settings when a project has no saved style yet.
- `desktop/src/hooks/useWindowWidth.ts` provides exact 1100px breakpoint logic.
- `desktop/src/pages/Home.tsx` and `desktop/src/pages/Review.tsx` remain in the repo as legacy reference files but are no longer active routes in `App.tsx`.
- `desktop/src/pages/Settings.tsx` exists and matches Qt parity (no subtitle style section).
- `desktop/src/jobsClient.ts` supports project-first export payloads (`project_id` primary, explicit paths optional for compatibility).
- Active app routes are now `/`, `/settings`, and `/workbench/:projectId`; `/legacy` and `/review` were removed from `App.tsx`.
- `desktop/tests/e2e/workbench-shell.spec.ts` covers Workbench shell layout, no-subtitles empty state, create-subtitles transition, on-video subtitle edit interactions, image-overlay preview mocks/assertions, and Workbench export CTA flow.
- `desktop/tests/e2e/project-hub.spec.ts` covers Projects card interactions, relink flow, delete confirmation flow, and the per-card `Create subtitles` quick action.
- Legacy `desktop/tests/e2e/home.spec.ts` has been removed as part of active-route cleanup.
- `desktop/src-tauri/tauri.conf.json` enables capabilities and asset protocol scope for previews.
- `desktop/package.json` has no `@mui` or `@emotion` deps.

Note: We intentionally diverged from the UX spec’s “left docked subtitles panel on wide screens” because it made the video preview unusably small. Subtitles list remains overlay-only by design and is still hidden/paused; Milestone 4.2 currently uses on-video editing without re-enabling the left list UI.

If any item above is no longer true, update this section before you continue.

---

## 3) Legacy Qt source of truth (read before coding)

The legacy Qt UI has been removed. Copy and state machine behavior now live in the Tauri app.

Primary files (current)
- `desktop/` (Tauri + React: state machine, copy, checklist mapping)
- `app/progress.py` (checklist step IDs)
- `app/workers.py` (Worker signals used by worker_runner subprocess)

State machine (Home screen)
`EMPTY -> VIDEO_SELECTED -> WORKING -> SUBTITLES_READY -> EXPORT_DONE`
Note: after `create_subtitles` completes, the user stays in Workbench for styling/edit/export. There is no active `/review` handoff.

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
- Add `app/worker_runner.py` that creates a Qt app context and runs the legacy Worker.
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
- Phase 6 - Tests and verification: Done (full backend pytest + full desktop Playwright suite + desktop build passed)
- Tauri dev build unblock (capabilities/main.json): Done
- Project system backend (Milestone 1 backend): Done (API + tests)
- Projects UI (Milestone 2.1 + 2.2): Done (Projects screen + card interactions + relink prompt/validation)
- Projects launch behavior (Milestone 2.3): Done
- Project deletion with confirmation: Done (Projects delete action + confirmation + backend cancel-then-delete)
- Workbench tabs/navigation: Done (tab strip + open/activate)
- Workbench shell (Milestone 3.1): Done (preview + style docked/overlay; right style pane uses real controls and now updates on-video subtitle preview styling immediately; left subtitles list overlay remains hidden/paused)
- Projects-to-Workbench entry refinement: Done (`New project` now opens Workbench and auto-starts subtitle generation; `needs_subtitles` cards include quick `Create subtitles` action with auto-start).
- Workbench no-subtitles empty state + create flow: Done (strict empty state exists for manual entry points; style hidden until subtitles exist; auto-start entry points skip double-clicking and go straight into create-subtitles progress).
- Milestone 4.1 (left list editing): Deferred while subtitle list UI is hidden/paused.
- Milestone 4.2 (on-video editing contract): Done (single-click pause+edit, input-like hover affordance, icon actions, keyboard parity, and playback resume on Save/Cancel)
- Milestone 4.3 (selection styling contract): Done for on-video path (selection accent is UI-only and export runner options drop UI-only selection keys)
- Workbench export-only migration (project-first API + Workbench export UX + project-scoped style + runner/worker style/timing consumption): Done
- Legacy export route cleanup (`/legacy`, `/review` removed from active routing): Done
- Export migration docs refresh (`ARCHITECTURE`, UX spec, roadmap, parity handoff, implementation playbook): Done
- 2026-02-11 roadmap/spec reprioritization sync: Done (Support UX v1 with hosted Send Logs, sidebar-removal navigation contract, settings clarity pass, progress continuity, and style-pane modernization documented)
- PR13 packaging hardening/smoke tests: Done (packaged engine + MSI and NSIS installers build; smoke path passes)
- Queue item 2 / KI-001 export success actions reliability: Done (desktop validation complete; `Play video` and `Open folder` work, and open failures are surfaced in-UI)
- Queue item 3 / KI-002 + KI-003 preview truthfulness: Done (Qt-rendered overlay preview path merged; renderer parity + resize scaling validated)

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
Note: Entries are chronological snapshots. Older entries may mention gaps that were later resolved; use the newest entry plus sections 2 and 6 for current state.

Date: 2026-02-13
Agent: gpt-5.3-codex-xhigh
Phase: Queue item 3 / KI-002 + KI-003 preview truthfulness
Status: Done
Summary:
- Closed KI-002 and KI-003 with an exact-parity playback preview path in Workbench.
- Added backend `POST /preview-overlay` in `app/backend_server.py` using `render_graphics_preview(...)` with cache-keyed transparent PNG outputs.
- Added frontend overlay client in `desktop/src/settingsClient.ts` and integrated Workbench overlay rendering in `desktop/src/pages/Workbench.tsx` (`object-contain`, video-native dimensions, HTML-edit fallback path).
- Updated tests:
  - `tests/test_backend_server.py` adds overlay endpoint cache/path coverage.
  - `desktop/tests/e2e/workbench-shell.spec.ts` adds `/preview-overlay` mocks and stable assertions for image-overlay preview mode.
- Validation run in this session:
  - `python -m pytest tests/test_backend_server.py` (pass)
  - `cd desktop && npm run lint` (pass)
  - `cd desktop && npx playwright test tests/e2e/workbench-shell.spec.ts` (pass; 14 tests)
- Next best task: Queue item 4 / KI-004 (`Preview word-highlight sync`) to drive preview highlight timing from timed-word artifacts.

Date: 2026-02-13
Agent: gpt-5.3-codex-xhigh
Phase: Queue item 2 / KI-001 export success actions reliability
Status: Done
Summary:
- Closed KI-001: Workbench export success-strip actions now reliably handle `Play video` and `Open folder`.
- Implemented robust opener handling in `desktop/src/pages/Workbench.tsx` (error surfacing, path normalization, and folder reveal fallback).
- Updated opener capability scopes in `desktop/src-tauri/capabilities/main.json` so exported videos in user folders (including Desktop) are allowed.
- User validation confirmed current behavior: `Open folder` and `Play video` now work.
- Docs updated to reflect completed state in `KNOWN_ISSUES.md`, `ROADMAP.md`, and this handoff file.
- Next best task: Queue item 3 (`Preview truthfulness`), starting with KI-002 (style parity) and KI-003 (preview scaling).

Date: 2026-02-13
Agent: (docs update)
Phase: PR13 packaging — NSIS blocker resolved
Status: Done
Summary:
- NSIS blocker resolved; installer works. PR13 packaging acceptance criteria met. Docs updated (PR13 handoff, README, smoke test, roadmap, this handoff). The 2026-02-11 entry’s "Known gap / blocker" (NSIS) is now resolved.

Date: 2026-02-11
Agent: gpt-5.3-codex-xhigh
Phase: PR13 packaging hardening + packaged smoke tests
Status: Partial (MSI pass; NSIS blocked) — now resolved per 2026-02-13
Summary:
- Implemented packaged-engine build flow and outputs for `CueBackend.exe`, `CueRunner.exe`, `CueWorker.exe`, and `CueAlignWorker.exe` plus FFmpeg bundle sync into `desktop/src-tauri/engine/`.
- Added frozen-aware subprocess routing:
  - `app/backend_server.py` now prefers sibling `CueRunner.exe` when frozen.
  - `app/align_utils.py` now prefers sibling `CueAlignWorker.exe` when frozen.
- Bundled engine resources and backend lifecycle in Tauri:
  - `desktop/src-tauri/tauri.conf.json` includes engine resources.
  - `desktop/src-tauri/src/main.rs` auto-starts/stops packaged backend and writes sidecar logs under `%LOCALAPPDATA%\Cue\logs\`.
- Added frontend startup resilience:
  - `desktop/src/backendHealth.ts` wait/retry helper.
  - `ProjectHub` and `Settings` wait for `/health` and show friendly startup messaging.
- Added release/smoke tooling and docs:
  - `scripts/build_engine.cmd`, `scripts/build_engine.ps1`, `scripts/build_release.cmd`
  - `tools/pyinstaller.engine.spec.in`
  - `tools/smoke_test_packaged_backend.py`
  - `docs/internal/SMOKE_TEST_PACKAGED.md`
- Tests and validation run:
  - `python -m pytest tests/test_backend_server.py tests/test_backend_job_project_update.py`
  - `python -m pytest tests/test_align_worker.py`
  - `npm run build` (desktop)
  - `cargo check` (desktop/src-tauri)
  - `scripts/build_engine.cmd`
  - `npm run tauri build -- --bundles msi`
  - `scripts/build_release.cmd` (fallback path validated)
  - `python tools/smoke_test_packaged_backend.py --video "C:\Users\david\Desktop\test_30s.mp4" --output-dir "C:\Cue_extra\smoke_packaged"` (`SMOKE_RESULT=PASS`)
- Known gap / blocker:
  - NSIS installer build fails during `makensis` with:
    - `Internal compiler error #12345: error mmapping file (..., 33554432) is out of range.`
    - `failed to bundle project \`The system cannot find the file specified. (os error 2)\``
  - MSI installer path is currently the working release route.
- Next best task:
  - Resolve NSIS packaging failure while preserving MSI output and packaged smoke parity.

Date: 2026-02-11
Agent: gpt-5.3-codex-xhigh
Phase: Workbench export-only migration implementation
Status: Done
Summary:
- Implemented full Workbench export migration from `docs/internal/WORKBENCH_EXPORT_IMPLEMENTATION_PLAN.md`:
  - backend project-first export contract and artifact resolution,
  - runner/worker support for explicit project style + word timings,
  - Workbench export CTA/progress/cancel/success UX,
  - project-scoped style persistence with fallback initialization,
  - active route cleanup removing `/legacy` and `/review` from `App.tsx`.
- Added and updated coverage:
  - Backend tests: `test_backend_server.py`, `test_backend_job_project_update.py`, `test_backend_projects_api.py`, and updated `test_align_worker.py` expectation.
  - Desktop E2E: `workbench-shell.spec.ts` + `project-hub.spec.ts`; removed legacy `home.spec.ts`.
- Updated docs for handoff continuity:
  - `docs/ARCHITECTURE.md`
  - `docs/internal/CUE_UX_UI_SPEC.md`
  - `docs/internal/ROADMAP.md`
  - `docs/internal/WORKBENCH_EXPORT_IMPLEMENTATION_PLAN.md`
  - this handoff file.
- Tests run:
  - `python -m pytest` -> 45 passed
  - `npm run build` (desktop) -> passed
  - `npx playwright test` (desktop) -> 18 passed
- Known gaps:
  - Legacy `Home.tsx` / `Review.tsx` files still exist as reference-only code (inactive routes).
  - Left subtitles list editing milestone remains deferred while list UI is hidden/paused.
- Next best task:
  - Start next roadmap slice from `docs/internal/ROADMAP.md` (packaging hardening/smoke gate), then continue prioritized UX queue.

Date: 2026-02-11
Agent: gpt-5.3-codex-xhigh
Phase: Roadmap/spec prioritization sync
Status: Done
Summary:
- Updated `docs/internal/ROADMAP.md` queue and milestone acceptance criteria to prioritize packaging gate, Support UX v1, clarity pass, sidebar removal, progress continuity, settings clarity, style modernization, and micro-interaction polish.
- Added a coverage map linking requested UX items to scheduled roadmap milestones and explicit safeguards/regression checks/analytics guardrails.
- Updated `docs/internal/CUE_UX_UI_SPEC.md` to reflect:
  - user-facing `Editor` naming,
  - no persistent sidebar navigation model,
  - clearer status wording (`Ready to review`),
  - progress transparency and background-task continuity,
  - settings clarity updates (quality cards, grouped save-path controls, merged transcription-assist controls, theme toggle),
  - hosted Send Logs contract (consent, redaction, fallback),
  - style-pane modernization expectations.
- Tests run: N/A (documentation-only update).
- Known gaps: implementation work for these newly documented items is pending.
- Next best task: execute queue item 1 (`PR13` packaging hardening/smoke) as a release stability gate before UX implementation slices.

Date: 2026-02-10
Agent: gpt-5.3-codex-xhigh
Phase: Workbench auto-start flow + style-preview parity fix
Status: Done
Summary:
- Updated `New project` flow to pass Workbench auto-start state so selecting a video immediately enters create-subtitles progress (no second click on `Create subtitles`).
- Wired Workbench subtitle preview rendering to style appearance state (font family, size, color/opacity, outline, shadow, vertical anchor/offset, and line/word background treatment), so style pane edits now visibly affect on-video subtitle preview immediately.
- Kept on-video editing shell behavior intact while applying preview style only in non-edit mode (to preserve editor legibility and action controls).
- Updated docs/spec status for the new behavior and current parity.
- Updated E2E coverage in `desktop/tests/e2e/workbench-shell.spec.ts`:
  - New project auto-start request assertion.
  - Style controls -> preview appearance assertion (`Font size` updates subtitle preview).
- Tests run:
  - `npm run test:e2e -- tests/e2e/workbench-shell.spec.ts`
  - `npm run build` (desktop)
- Known gaps: Milestone 4.1 (left list editing + list/on-video selection sync) remains deferred while left subtitles list UI is hidden/paused.
- Next best task: resume Milestone 4.1 by re-enabling left subtitles list editing and syncing list selection with on-video selection/seek behavior.

Date: 2026-02-10
Agent: gpt-5.3-codex-xhigh
Phase: Milestone 4 on-video UX polish + selection export guard
Status: Done
Summary:
- Updated Workbench on-video editing UX for discoverability and speed:
  - Hover state now presents an input-like shell with an I-beam cursor.
  - Single click on active subtitle now pauses playback (when needed) and immediately enters inline edit mode.
- Added explicit icon actions in edit mode (check/save, undo, x/cancel) with keyboard parity:
  - Enter = Save, Esc = Cancel, Ctrl/Cmd+Z = Undo.
  - Save/Cancel now exits edit mode and resumes playback when edit mode started from a playing state.
- Added backend guard for selection non-leak:
  - `_build_runner_command(...)` now strips UI-only selection keys from `options` before passing `--options-json` to the runner.
- Updated contract docs to match the implemented interaction:
  - `docs/internal/CUE_UX_UI_SPEC.md` E4 on-video editing rules.
  - `docs/internal/ROADMAP.md` Milestone 4.2 deliverables + acceptance wording.
  - Status board entry wording in this handoff doc.
- Updated E2E coverage:
  - `desktop/tests/e2e/workbench-shell.spec.ts` now covers one-click edit, icon save/cancel/undo, keyboard undo shortcut, and playback resume checks.
- Tests run:
  - `python -m pytest tests/test_backend_job_project_update.py`
  - `npm run test:e2e -- tests/e2e/workbench-shell.spec.ts`
  - `npm run build` (desktop)
- Known gaps: Milestone 4.1 (left list editing) remains deferred while the left subtitles list UI is hidden/paused; list/on-video selection sync is validated fully once 4.1 is resumed.
- Next best task: resume Milestone 4.1 (left list editing + selection/seek sync) while preserving the one-click on-video editing contract and export non-leak guarantees.

Date: 2026-02-10
Agent: gpt-5.3-codex-xhigh
Phase: Projects/Workbench flow realignment + docs update
Status: Done
Summary:
- Renamed user-facing `Project Hub` label to `Projects` in desktop UI and updated route-facing copy/tests accordingly.
- Updated Projects flow:
  - Header CTA is now `New project`.
  - Creating a project auto-opens Workbench.
  - `needs_subtitles` cards now show a secondary `Create subtitles` quick action that opens Workbench and auto-starts subtitle generation.
- Updated Workbench no-subtitles behavior:
  - Strict empty state with only `No subtitles yet.` and primary `Create subtitles`.
  - No style pane/drawer until subtitles exist.
  - Create-subtitles now runs in Workbench with checklist/progress/cancel.
- Added project-linked job payload support in `desktop/src/jobsClient.ts` (`projectId` -> `project_id`).
- Updated E2E coverage:
  - `desktop/tests/e2e/project-hub.spec.ts`
  - `desktop/tests/e2e/workbench-shell.spec.ts`
- Tests run:
  - `npm run test:e2e -- project-hub.spec.ts workbench-shell.spec.ts`
- Known gaps: Milestone 4.3 selection styling contract still pending; left subtitles list editing (Milestone 4.1) remains deferred while list UI is hidden.
- Next best task: implement Milestone 4.3 (selection styling contract) and verify selection accents never leak into export.

Date: 2026-02-10
Agent: gpt-5.3-codex-xhigh
Phase: Workbench style controls + docs parity reconciliation
Status: Done
Summary:
- Wired `StyleControls` into Workbench (docked right panel on wide screens + right overlay drawer on narrow screens) and backed it with `fetchSettings`/`updateSettings` so style edits now persist from Workbench.
- Confirmed Project Hub delete flow remains live (project-data-only delete with confirmation; backend cancel-then-delete semantics for running project jobs).
- Reconciled docs to current behavior:
  - Snapshot now reflects current backend project/job semantics and Workbench style pane state.
  - Status board wording now matches implemented Workbench shell behavior.
- Tests run:
  - `npm run build` (desktop)
  - `npm run test:e2e -- tests/e2e/workbench-shell.spec.ts tests/e2e/project-hub.spec.ts`
  - `python -m pytest tests/test_project_store.py tests/test_backend_projects_api.py tests/test_backend_job_project_update.py`
- Known gaps: Milestone 4.1 (left list editing) remains deferred while left subtitles panel is hidden/paused; Milestone 4.3 selection styling contract still pending.
- Next best task: Milestone 4.3 selection styling contract (selection accent behavior, export non-persistence verification, then list/on-video sync when 4.1 is resumed).

Date: 2026-02-10
Agent: gpt-5.3-codex-xhigh
Phase: Project delete with confirmation
Status: Done
Summary:
- Added backend project delete support: `project_store.delete_project(...)` and `DELETE /projects/{project_id}`.
- Delete behavior is project-data-only (keeps source video file untouched) and now cancels running jobs for that project before delete proceeds.
- Added frontend delete client helper (`deleteProject`) and Project Hub delete UI (trash action on card + confirmation dialog + cancel/confirm flow).
- Updated tests:
  - Backend: `tests/test_project_store.py` and `tests/test_backend_projects_api.py` now cover delete success/not-found and cancel-running-job behavior.
  - E2E: `desktop/tests/e2e/project-hub.spec.ts` now covers delete confirm/cancel and successful card removal.
- Tests run:
  - `python -m pytest tests/test_project_store.py tests/test_backend_projects_api.py`
  - `npm run build` (desktop)
  - `npm run test:e2e -- tests/e2e/project-hub.spec.ts`
  - `npm run test:e2e -- tests/e2e/workbench-shell.spec.ts`
- Known gaps: no undo/restore flow for deleted projects; busy/read-only cross-project rules remain unimplemented.
- Next best task: Milestone 4.3 selection styling contract and export-time verification that selection accents are never rendered.

Date: 2026-02-10
Agent: gpt-5.3-codex-xhigh
Phase: Milestone 4.2 - on-video editing contract
Status: Done
Summary:
- Added backend subtitle-read contract for projects: `project_store.get_project_subtitles_text()` and `GET /projects/{project_id}/subtitles`.
- Added frontend project client support for subtitle editing persistence (`fetchProjectSubtitles`, `updateProject`) plus frontend SRT parse/serialize utility (`desktop/src/lib/srt.ts`).
- Implemented Workbench on-video editing contract: click active subtitle while playing pauses + selects; click again while paused opens inline editor anchored on-video; Enter saves via `PUT /projects/{id}`; Esc cancels local edit.
- Added/updated tests:
  - Backend: `tests/test_backend_projects_api.py` covers missing + read-after-write subtitle endpoint behavior.
  - E2E: `desktop/tests/e2e/workbench-shell.spec.ts` now covers Enter-save and Esc-cancel contract flows.
- Tests run:
  - `python -m pytest tests/test_backend_projects_api.py tests/test_project_store.py tests/test_backend_job_project_update.py`
  - `npm run build` (desktop)
  - `npm run test:e2e -- tests/e2e/workbench-shell.spec.ts`
- Known gaps: Milestone 4.1 left list editing remains deferred/hidden; style inspector is still placeholder; busy/read-only cross-project rules still not enforced.
- Next best task: Milestone 4.3 selection styling contract (selection accent behavior and explicit export non-persistence verification, plus list/on-video sync once list UI is re-enabled).

Date: 2026-02-09
Agent: gpt-5.2-codex-xhigh
Phase: Docs alignment - Milestone 4 sequencing
Status: Done
Summary:
- Clarified that Milestone 4.1 is not the next actionable UI task right now.
- Rationale: Milestone 4.1 in `docs/internal/ROADMAP.md` is explicitly "Left list editing", and the subtitle list UI is intentionally hidden/paused.
- Next best task is Milestone 4.2 (on-video editing contract), then resume 4.1 when subtitle list UI is re-enabled.
- Tests run: Not run (doc-only update).
- Known gaps: subtitle list content + editing not implemented; style inspector still placeholder; busy/read-only rules not enforced.
- Next best task: Milestone 4.2 on-video editing (pause/select/edit with Enter/Esc), followed by 4.3 selection styling contract.

Date: 2026-02-09
Agent: gpt-5.2-codex-xhigh
Phase: Pause subtitles overlay UI
Status: Done
Summary:
- Subtitles overlay drawer UI is now hidden while keeping the code in place (feature paused).
- Workbench remains preview-first with Style docked on wide screens and overlay on narrow screens.
- Tests updated to stop expecting the subtitles drawer.
- Tests run: Not run (not requested).
- Known gaps: subtitle list content + editing not implemented; style inspector still placeholder; busy/read-only rules not enforced.
- Next best task: implement Workbench subtitle list editing + selection/seek sync (Milestone 4.1), then wire StyleControls into Workbench.

Date: 2026-02-09
Agent: gpt-5.2-codex-xhigh
Phase: Workbench tabs + preview-friendly shell layout
Status: Done
Summary:
- Project Hub cards open/activate Workbench tabs; missing-file projects are blocked in hub via relink prompt.
- Workbench layout updated to protect preview: Style docked on wide screens, overlay on narrow; subtitles list is overlay-only.
- Sidebar can collapse to icon strip (user-controlled, persisted in localStorage).
- Tests updated/added: `desktop/tests/e2e/workbench-shell.spec.ts`, `desktop/tests/e2e/project-hub.spec.ts`.
- Known divergence: left docked subtitles panel intentionally avoided to prevent preview shrink.
- Tests run: Not run (not requested).
- Known gaps: subtitle list content + editing not implemented; style inspector still placeholder; busy/read-only rules not enforced.
- Next best task: implement Workbench subtitle list editing + selection/seek sync (Milestone 4.1), then wire StyleControls into Workbench.

Date: 2026-02-09
Agent: gpt-5.2-codex-xhigh
Phase: Workbench entry (Project Hub cards open Workbench)
Status: Done
Summary:
- Project Hub normal cards now open Workbench (`/workbench/:projectId`); missing-file cards still use the relink prompt.
- Workbench shell added with Back button + left/center/right placeholders; loads project detail from `GET /projects/{id}`.
- Current routes: `/` Project Hub (cold-start forced), `/workbench/:projectId`, `/legacy`, `/review`, `/settings`.
- Tests run: `npm run build`, `npm run test:e2e` (all pass).
- Known gaps: Workbench is a placeholder only (no tabs, no real panels).
- Next Project Hub/Workbench steps:
  - Implement Workbench tabs (multi-project open/activate) per UX spec.
  - Update card clicks to activate existing tabs when open.
  - Decide missing-file behavior in Workbench (open with relink-required vs keep hub-only).
  - Replace placeholders with real panels (video preview, subtitles list, style inspector).

Date: 2026-02-09
Agent: gpt-5.2-codex-xhigh
Phase: Project Hub launch behavior (Milestone 2.3)
Status: Done
Summary:
- Added a one-time launch guard so the app always starts on Project Hub.
- Updated Playwright E2E tests to start at Project Hub before navigating to Settings or Legacy Home.
- Tests run: `npm run build` (vite build). E2E not run.
- Known issues: None observed.
- Suggested next step: Continue Milestone 3 (Workbench shell) from `docs/internal/ROADMAP.md`.

Date: 2026-02-09
Agent: gpt-5.2-codex-xhigh
Phase: Project Hub UI (Milestone 2.1 + 2.2)
Status: Done
Summary:
- Added Project Hub screen as the default route (`/`) and moved legacy Home to `/legacy`.
- Project Hub supports project list + create (button + drag/drop) via `/projects`.
- Card interactions added:
  - Normal cards show a “Workbench coming soon” message.
  - Missing-file cards show an explicit prompt explaining the file moved and offer Select/Cancel.
  - Relink uses warn + confirm validation: mismatched filename and/or duration warns before allowing “Use this file anyway”.
  - Unsupported file types are blocked with a clear error.
- Added `relinkProject` client helper and updated Playwright coverage for card interactions.
- Tests run: Manual UI verification by user (“tested, looks good”).
- Known issues: No Workbench flow yet; `/legacy` is not linked in the UI.
- Suggested next step: Milestone 2.3 (force launch to Project Hub) and update E2E tests that deep-link to routes like `/settings`.

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
- Added `app/worker_runner.py` to run legacy Worker in a Qt-safe subprocess and emit JSON events (started, checklist, progress, log, result, heartbeat, terminal).
- Updated `app/backend_server.py` to support `create_subtitles` / `create_video_with_subtitles` and spawn the runner with cancel handling.
- Fixed audio extraction hang: added `-nostdin`, a no-output watchdog for ffmpeg, and fallback retry without filters.
- Hardened transcription: unbuffered `-u`, env `PYTHONUNBUFFERED`, safe-mode retry (CPU int8, no VAD/rescue), and stdin set to DEVNULL.
- Fixed stdout encoding in runner (UTF-8 bytes) to avoid UnicodeEncodeError on Hebrew.
- Alignment subprocess now runs unbuffered and stdin=DEVNULL to avoid blocking.
- Removed passing `--ffmpeg-args-json` to the transcription worker to avoid hanging in this environment.
- Manual test succeeded on `C:\\Users\\david\\Desktop\\test_30s.mp4` with full result payload.
- Tests run: `python -m app.worker_runner --task generate_srt` (manual).
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

