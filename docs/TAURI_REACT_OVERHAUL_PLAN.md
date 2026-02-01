\# Cue: Tauri + React Desktop UI Overhaul Plan (Implementation + Tracking)



Last updated: 2026-01-30  

Owner: This document is the single source of truth for the UI overhaul plan. Update it as each PR lands.



\## 0) Why this overhaul exists



The current UI stack (PySide6 / Qt Widgets) is not meeting the goals of:

\- “Modern web-app quality” UI out-of-the-box

\- Easy component reuse and styling (like web frameworks)

\- Scalable UI iteration speed and discoverability for contributors



This overhaul replaces the desktop UI layer with a React-based UI packaged as a native Windows desktop app using Tauri (or Electron fallback). The Python pipeline remains the core engine.



This document is written for OOTL AI contributors so they can pick up work without a telephone-game.



---



\## 1) High-level decision



\### Chosen direction

\- Desktop shell: \*\*Tauri\*\*

\- UI: \*\*React + TypeScript\*\*

\- Component library: \*\*MUI (Material UI)\*\* initially (fast polished UI + mature theming)

\- Styling approach: MUI theme + (optional later) utility classes (Tailwind) if needed

\- Backend engine: existing \*\*Python\*\* pipeline (faster-whisper, whisperx, ffmpeg)

\- Backend communication: defined protocol (see §5)



\### Explicit non-goals (initial phase)

\- No “perfect UI/brand design” work upfront. First priority is a stable, scalable UI foundation.

\- No feature additions unrelated to UI migration (unless needed to support protocol/cancellation).

\- No re-implementing the transcription/alignment logic in Rust/JS.



\### Electron fallback

If Tauri integration proves blocking (packaging constraints, WebView limitations, sidecar friction), the UI can be packaged with Electron instead. The UI code (React/MUI) stays the same; only the shell changes.



---



\## 2) Target end state



\### End-user experience

\- Installed desktop app with a normal Windows installer (MSI or Setup.exe).

\- App installs to Program Files (or standard install location), creates Start Menu entry, supports uninstall.

\- UI is polished and consistent using the component library theme.

\- “Cancel” works reliably and stops work quickly (including subprocess trees).

\- Progress feels smooth, correct, and step-based (no “stuck” or “invisible running” gaps).



\### Developer experience

\- Frontend is a standard modern web app workflow (React dev server, hot reload).

\- Backend remains Python and is invoked via a stable contract from the UI.

\- Clear folder structure and clear boundaries between UI and engine.

\- CI + lint + basic types to prevent regressions.



---



\## 3) Repository structure after migration (target)



Top-level (example target; keep minimal at first):

\- `app/` (existing Python engine + current Qt UI; later we remove/retire Qt UI)

\- `desktop/` (NEW: Tauri + React app)

&nbsp; - `src/` (React UI)

&nbsp; - `src-tauri/` (Tauri config and Rust harness)

\- `docs/` (this plan + future docs)

\- `scripts/` (existing scripts; add new scripts if needed)

\- `tests/` (existing tests; add backend protocol tests later)



---



\## 4) Migration strategy (avoid big-bang rewrite)



We will migrate in thin vertical slices:

1\) Introduce new desktop UI shell (no backend integration).

2\) Establish stable backend “contract” and minimal sidecar process management.

3\) Wire progress + cancellation in the new UI.

4\) Port screens/features incrementally.

5\) Once parity is reached, remove/retire Qt UI.



Important: do not block forward progress by trying to perfect the architecture early. Each PR must be small and verifiable.



---



\## 5) Backend contract (UI ↔ Python engine)



This contract is critical. It prevents “telephone game” drift and allows multiple contributors to work independently.



\### 5.1 Terms

\- \*\*Job\*\*: a single pipeline run (create subtitles, align words, export video, etc.).

\- \*\*Event\*\*: structured progress/log/state message emitted from backend to UI.

\- \*\*Artifact\*\*: output file(s) (SRT, word timings JSON, exported video, diagnostics zip, etc.).

\- \*\*Cancel\*\*: a user action that must stop the current job quickly and reliably.



\### 5.2 Communication transport options (choose one and standardize)

Option A — Local HTTP + streaming (recommended):

\- Backend runs a localhost server on a random free port.

\- UI talks via HTTP for commands and uses SSE/WebSocket for events.

Pros: straightforward streaming, debuggable, common patterns.

Cons: port management, firewall paranoia (usually fine on localhost).



Option B — stdin/stdout JSON protocol:

\- UI spawns Python as a child process.

\- Commands/events flow through stdin/stdout lines (JSONL).

Pros: no ports, simple packaging.

Cons: streaming + backpressure + process management more delicate; harder to inspect with external tools.



Decision (for now): \*\*Option A (Local HTTP + streaming)\*\* unless blocked by packaging constraints.



\### 5.3 Standard message schema (must not drift)

All events are JSON objects. Every event must include:

\- `job\_id` (string, stable for job lifetime)

\- `ts` (ISO string or epoch ms)

\- `type` (one of: `state`, `step`, `progress`, `log`, `artifact`, `error`, `done`)

\- `payload` (object; type-specific)



\#### Event types

1\) `state`

\- payload:

&nbsp; - `state`: `idle` | `running` | `cancelling` | `cancelled` | `failed` | `succeeded`



2\) `step`

\- payload:

&nbsp; - `step\_id`: stable identifier (e.g., `detect\_language`, `transcribe`, `align\_words`, `export\_video`)

&nbsp; - `label`: UI label (short, user-facing)

&nbsp; - `status`: `pending` | `running` | `skipped` | `done`



3\) `progress`

\- payload:

&nbsp; - `step\_id`

&nbsp; - `percent`: 0..100 (number)

&nbsp; - `detail`: optional short text (e.g., `123/500 words timed`)

&nbsp; - `counters`: optional object (e.g., `{ "done": 123, "total": 500, "unit": "words" }`)



4\) `log`

\- payload:

&nbsp; - `level`: `debug` | `info` | `warning` | `error`

&nbsp; - `message`: string

&nbsp; - `context`: optional object



5\) `artifact`

\- payload:

&nbsp; - `kind`: `srt` | `word\_timings\_json` | `export\_mp4` | `diagnostics\_zip` | `other`

&nbsp; - `path`: absolute or app-relative path

&nbsp; - `meta`: optional object



6\) `error`

\- payload:

&nbsp; - `code`: stable code string

&nbsp; - `message`: user-facing message (short)

&nbsp; - `debug`: optional (stack trace path, etc.)



7\) `done`

\- payload:

&nbsp; - `result`: `succeeded` | `cancelled` | `failed`

&nbsp; - `duration\_ms`



\### 5.4 Command endpoints (if HTTP transport)

Minimal endpoints to start:

\- `POST /jobs`

&nbsp; - body: job request (see §5.5)

&nbsp; - returns: `{ job\_id, events\_url, cancel\_url }`

\- `GET /jobs/{job\_id}/events`

&nbsp; - SSE stream or WebSocket

\- `POST /jobs/{job\_id}/cancel`

\- `GET /health`

\- `GET /version`



\### 5.5 Job request schema (initial)

Define explicit job types. Example:

\- `job\_type`: `create\_subtitles` | `export\_video`

\- `input`:

&nbsp; - `video\_path`

&nbsp; - `project\_dir` (or derived)

&nbsp; - `settings` (subtitle style, language hints, etc.)



Backend should validate and respond with structured errors.



---



\## 6) Packaging and installer goals



\### 6.1 Windows installer

Target: installer experience like Discord:

\- Start menu entry

\- Uninstall via Windows settings

\- Installs into standard location



Tauri outputs:

\- MSI (WiX) and/or NSIS installer depending on configuration.



\### 6.2 Python engine packaging

We will likely ship the Python engine as a packaged executable and run it as a sidecar.

Options:

\- PyInstaller build of backend worker/server

\- Bundle ffmpeg/ffprobe similarly

\- Tauri sidecar config points to those binaries



Non-negotiable:

\- Backend must run without requiring Python installed on the user’s machine.



\### 6.3 Code signing (later milestone)

\- Add signing once distribution begins (reduces SmartScreen warnings).

Not required for initial internal use.



---



\## 7) PR plan (tracking)



This plan is written so any contributor can pick up “the next PR” with minimal context.



\### Status legend

\- \[ ] Not started

\- \[~] In progress

\- \[x] Done (merged to main)



\### PR0 — Add this implementation plan document

\- \[ ] Add `docs/TAURI\_REACT\_OVERHAUL\_PLAN.md`

Acceptance:

\- File exists on main

\- Contains PR checklist + contract section



\### PR1 — Add Tauri + React UI shell (no backend integration)
Status: Done (UI shell only; no backend integration yet; legacy Qt UI still exists).

\- \[x] Create `desktop/` with Vite + React + TS

\- \[x] Add MUI and a basic theme module

\- \[x] Minimal navigation: Home + Settings

\- \[x] Home shows placeholder “Ready” and disabled Start button

\- \[x] Settings shows dummy controls (toggles/sliders) to prove component styling

\- \[x] `desktop/README.md` with exact Windows commands

Acceptance:

\- `npm install` and `npm run tauri dev` opens the window

\- `npm run tauri build` produces Windows bundle artifacts



\### PR2 — Sidecar process management (backend runner stub)

Status: Done

\- \[x] Decide transport: HTTP streaming preferred

\- \[x] Add minimal backend runner (can be a Python server stub) packaged as sidecar

\- \[x] UI can launch backend, call `/health`, show backend status in Settings

\- \[x] Fixed dev port for PR2: `127.0.0.1:8765`

Acceptance:

\- UI displays backend “connected” / “not connected”

\- No pipeline yet



\### PR3 — Backend contract scaffolding + event viewer

Status: Complete

\- \[ ] Implement event stream consumer in UI

\- \[ ] Show steps/progress in UI with a generic “Job Monitor” screen

\- \[ ] Implement Cancel button that triggers cancel endpoint and UI transitions to “cancelling/cancelled”

Endpoints (demo job only):
\- `POST /jobs`
\- `GET /jobs/{id}/events` (SSE)
\- `POST /jobs/{id}/cancel`

Dev workflow (PR3):
\- Start backend: `scripts\run_backend_dev.cmd`
\- Start UI: `cd desktop` then `npm ci` then `npm run tauri dev`
\- Settings → Demo Job → “Start demo job” to stream events; “Cancel” to stop.

Acceptance:

\- A fake/demo backend job produces step/progress events; UI renders them correctly

\- Cancel works against demo backend and updates UI state



\### PR4 — Wire real “Create Subtitles” job to Python engine

Status: In progress (current)

\- \[ ] Use existing engine behavior to run create-subtitles pipeline through the new contract

\- \[ ] Map existing steps to stable step IDs

\- \[ ] Ensure artifacts (SRT + word timings if applicable) are returned via `artifact` events

POST /jobs request body (pipeline jobs):
```json
{
  "kind": "pipeline",
  "input_path": "C:\\path\\to\\video.mp4",
  "output_dir": "C:\\Cue_output",
  "options": {}
}
```

Progress/events (pipeline jobs):
\- `started` → `step` (validate/transcribe/align/export) → `progress` (0/25/60/90/100) → terminal (`completed`/`cancelled`/`error`)

Acceptance:

\- You can create subtitles end-to-end from the new UI

\- Output matches existing behavior (as close as possible)

\- Cancel works reliably



\### PR5 — Wire real “Export Video” job

\- \[ ] Trigger export pipeline through contract

\- \[ ] Progress and artifacts emitted correctly

Acceptance:

\- Export completes successfully

\- Cancel stops export



\### PR6 — Diagnostics/logging parity

\- \[ ] UI has “Export diagnostics” / “Open logs” flow

\- \[ ] Backend writes structured logs and can package them (zip)

Acceptance:

\- Same or better diagnostics than current system



\### PR7 — Installer polish

\- \[ ] Confirm Start Menu entry, app icon, app name

\- \[ ] Confirm FFmpeg and backend binaries are bundled correctly

\- \[ ] Document build steps

Acceptance:

\- Fresh Windows machine install works end-to-end



\### PR8 — Deprecate/remove Qt UI (after parity)

\- \[ ] Decide: delete Qt UI or keep it behind a dev flag temporarily

\- \[ ] Remove unused Qt dependencies if fully removed

Acceptance:

\- Main distribution path uses new desktop UI only



---



\## 8) Design system approach in the new UI (avoid “custom design crap”)



Goal: “web-app quality UI” without hand-rolling widgets.



Rules:

\- Use MUI components as the default building blocks.

\- Only write custom components when:

&nbsp; 1) a feature is truly missing, AND

&nbsp; 2) it’s a thin wrapper around MUI primitives, AND

&nbsp; 3) styling is controlled via theme tokens (not ad-hoc CSS everywhere).



Theming:

\- Keep a single `theme.ts` (or similar) exporting the MUI theme.

\- Define palette, typography, spacing, radius there.

\- Do not scatter hard-coded colors across components.



Component organization:

\- `src/components/` for reusable components

\- `src/pages/` for screens

\- `src/state/` for job state management

\- `src/api/` for backend contract calls



---



\## 9) Cancellation reliability requirements (must be enforced)



Cancel must:

\- Stop backend work quickly.

\- Kill subprocess trees if needed (FFmpeg, alignment workers, etc.).

\- Never leave a job “running” after Cancel is confirmed.



Backend must:

\- Check cancellation frequently during long loops.

\- Use process-group killing on Windows when terminating subprocesses.

\- Emit `state` transitions: `running -> cancelling -> cancelled` (or `failed`).



UI must:

\- Disable Start while cancelling.

\- Display explicit cancel state.

\- Allow retry after cancellation.



---



\## 10) Definition of Done (for each PR)



Every PR must include:

\- Clear acceptance criteria (in the PR description)

\- Manual test steps

\- No unrelated refactors

\- Update this document:

&nbsp; - Mark the PR as \[x]

&nbsp; - Add notes in the changelog below (what changed, any protocol tweaks)



---



\## 11) Running changelog (append-only)



\### 2026-02-01

\- PR1: Added initial `desktop/` Tauri + React shell with MUI theming, navigation, and placeholder screens (UI shell only; no backend integration yet; legacy Qt UI still exists).



\### 2026-01-30

\- Plan created. Selected direction: Tauri/Electron + React (Tauri preferred). No implementation yet.



(When implementing, add entries here per PR.)
