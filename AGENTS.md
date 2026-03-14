# AGENTS.md

Context for AI agents working in the Cue repo. Keep this file short; link to existing docs for detail.

---

## Project summary

Cue is a local desktop app for creating and burning subtitles into video. Stack: **Tauri + React** (`desktop/`), **Python FastAPI** backend (`app/`), pipeline: FFmpeg, faster-whisper, WhisperX. User flow: Projects (ProjectHub) → open project → Workbench (create subtitles, edit, style, export). Settings for transcription, save policy, diagnostics.

---

## Where things live

**Desktop UI** (`desktop/`)

- **Pages:** `desktop/src/pages/` — **ProjectHub** (route `/`), **Workbench** (`/workbench/:projectId`), **Settings**, plus **Home.tsx** and **Review.tsx** (e.g. drop-in / review flows).
- **Components:** `desktop/src/components/` (shared UI), `desktop/src/components/ui/` (design primitives).
- **API clients:** `jobsClient.ts`, `settingsClient.ts`.
- **Tauri shell:** `desktop/src-tauri/`.

**Backend** (`app/`)

- **Server:** `backend_server.py` — FastAPI (health, jobs, projects, settings, device, preview).
- **Pipeline:** `backend_pipeline_adapter.py`, `backend_inprocess_worker.py`, `worker_runner.py`, `workers.py`, `transcribe_worker.py`, `align_worker.py`, `align_utils.py`.
- **Graphics:** `graphics_overlay_export.py`, `graphics_preview_renderer.py`.
- **Persistence:** `project_store.py`, `config.py`, `paths.py`.
- **Support:** `srt_splitter.py`, `srt_utils.py`, `word_timing_schema.py`, `subtitle_style.py`, `progress.py`, `ffmpeg_utils.py`, `transcription_*.py`, `preview_playback.py`, etc.

**Design system**

- `desktop/design-system/components.md`, `tokens.md`. Use these and `desktop/src/components/ui/`; `@/` for imports under `desktop/src`.

**Docs**

- `docs/ARCHITECTURE.md` — system design, pipeline, repo layout, API.
- `docs/CONTRIBUTING.md` — setup, run, **tests**, lint, packaging.

---

## Debug logs and temporary output

**Save all debug logs, dumps, and temporary debug artifacts under the repo’s `.cursor/` directory** (e.g. `.cursor/logs/` or `.cursor/debug/`). Do not use repo root, `~/.cursor`, or other ad-hoc locations. This keeps logs in one place so agents and developers can find them when debugging.

---

## Conventions

- **UI:** Follow `desktop/design-system/components.md` (PageHeader, button variants, cursor/accessibility, `data-interactive="true"` for custom clickables).
- **Imports:** Use `@/` for `desktop/src` (e.g. `@/components/PageHeader`).
- **Code style:** Concise, direct; no over-engineering or unnecessary comments.

---

## Run and test

- **Run app:** `scripts\run_desktop_all.cmd` (from repo root). See `docs/CONTRIBUTING.md` for prerequisites.
- **Backend tests:** From repo root with venv active: `pytest`. Tests in `tests/`.
- **E2E:** Start backend and Vite (`cd desktop` then `npx vite --port 5173`), then `npm run test:e2e`. Specs in `desktop/tests/e2e/`.
- **Lint:** See `docs/CONTRIBUTING.md` (ESLint, ruff, clippy).

### Verification standard for agent chunks

- Do not claim "nothing is broken" from a seam-only test command. That only proves the edited seam.
- After every chunk, run the chunk's direct tests and the direct dependent tests for any shared module touched.
- If a shared backend seam reaches API or project persistence code, also run at least one integration/API test file that exercises that path before declaring the chunk safe.
- If earlier cleanup chunks are still uncommitted in the worktree, keep their test files in the regression command too. Do not verify only the newest file and ignore already-dirty related seams.
- Always report skipped tests explicitly, especially Windows PySide6 skips, as remaining verification gaps.

### Current cleanup-chain regression command

- For the current config/subtitle-style/project-style cleanup chain, run this broader backend regression command in addition to the chunk-local pytest command:
  - `C:\Cue_repo\.venv\Scripts\python.exe -m pytest C:\Cue_repo\tests\test_config_defaults.py C:\Cue_repo\tests\test_subtitle_style.py C:\Cue_repo\tests\test_graphics_overlay_export.py C:\Cue_repo\tests\test_graphics_preview_renderer.py C:\Cue_repo\tests\test_preview_playback_plan.py C:\Cue_repo\tests\test_project_store.py C:\Cue_repo\tests\test_backend_projects_api.py C:\Cue_repo\tests\test_backend_job_project_update.py C:\Cue_repo\tests\test_backend_server.py`

---

## What to avoid

- Do not use the legacy Qt UI (`app/main.py`) for new features; active flow is Tauri (ProjectHub → Workbench → Export).
- Do not write debug logs or temp debug files to repo root or outside the repo’s `.cursor/` folder.
- Do not duplicate design-system or architecture detail; link to `desktop/design-system/` and `docs/ARCHITECTURE.md`.

---

## Large files

- `desktop/src/pages/Workbench.tsx` is very large; prefer targeted edits and search by feature rather than whole-file rewrites.
