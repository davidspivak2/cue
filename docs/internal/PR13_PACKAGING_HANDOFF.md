# PR13 Packaging Handoff (Windows)

Last updated: 2026-02-13

Purpose:
- Give the next agent a fast, reliable starting point for PR13 continuation.
- Avoid re-discovery of what is already done and what is still blocked.

## Current Status
- Overall: Done.
- Done: engine packaging, frozen subprocess routing, Tauri backend autostart, backend startup wait/retry UX, MSI smoke path, NSIS installer build.

## What Was Implemented

### Engine build and packaging
- Added entry wrappers:
  - `engine/run_backend.py`
  - `engine/run_runner.py`
  - `engine/run_worker.py`
  - `engine/run_align_worker.py`
- Added PyInstaller engine spec:
  - `tools/pyinstaller.engine.spec.in`
- Added engine build scripts:
  - `scripts/build_engine.cmd`
  - `scripts/build_engine.ps1`
- Output engine executables:
  - `CueBackend.exe`
  - `CueRunner.exe`
  - `CueWorker.exe`
  - `CueAlignWorker.exe`
- Engine folder synced into:
  - `desktop/src-tauri/engine/`

### Frozen subprocess hardening
- `app/backend_server.py`
  - Runner command now prefers sibling `CueRunner.exe` when frozen.
- `app/align_utils.py`
  - Alignment command now prefers sibling `CueAlignWorker.exe` when frozen.

### Tauri bundling and backend lifecycle
- `desktop/src-tauri/tauri.conf.json`
  - Engine bundled via resources.
  - Explicit icon list configured for packaging.
- `desktop/src-tauri/src/main.rs`
  - Auto-starts packaged backend from resources.
  - Writes sidecar logs to `%LOCALAPPDATA%\Cue\logs\backend_sidecar_*.log`.
  - Stops backend on app exit.

### Frontend startup resilience
- Added `desktop/src/backendHealth.ts`:
  - `waitForBackendHealthy()` polling helper.
- Integrated into:
  - `desktop/src/pages/ProjectHub.tsx`
  - `desktop/src/pages/Settings.tsx`
- UX:
  - Shows `Starting the engine...` while backend initializes.

### Build/release/smoke tooling
- `scripts/build_release.cmd`
  - Runs engine build and Tauri build (NSIS and MSI).
  - Full build including NSIS works; MSI-only fallback remains available if needed.
- `tools/smoke_test_packaged_backend.py`
  - API-based golden path smoke (create project -> subtitles -> export).
- `docs/internal/SMOKE_TEST_PACKAGED.md`
  - Smoke steps and recorded result table.

## Validation Already Run
- `python -m pytest tests/test_backend_server.py tests/test_backend_job_project_update.py`
- `python -m pytest tests/test_align_worker.py`
- `npm run build` (in `desktop`)
- `cargo check` (in `desktop/src-tauri`)
- `scripts/build_engine.cmd`
- `npm run tauri build -- --bundles msi`
- `scripts/build_release.cmd` (full build including NSIS + MSI validated)
- `python tools/smoke_test_packaged_backend.py --video "C:\Users\david\Desktop\test_30s.mp4" --output-dir "C:\Cue_extra\smoke_packaged"` -> `SMOKE_RESULT=PASS`

## NSIS (Resolved)
- Resolved as of 2026-02-13. Both NSIS and MSI installers build successfully; no mitigation needed.
- (Previously: NSIS failed during `makensis` with `Internal compiler error #12345 ... mmapping file ... out of range` and `os error 2`; build script fell back to MSI-only.)

## First Commands for Next Agent
From repo root:

1. `scripts\build_engine.cmd`
2. `scripts\build_release.cmd` (produces both NSIS and MSI)
3. Or from `desktop`: `npm run tauri build`
4. For MSI-only build: `npm run tauri build -- --bundles msi`
5. Smoke test packaged backend path:
   - `python tools\smoke_test_packaged_backend.py --video "C:\Users\david\Desktop\test_30s.mp4" --output-dir "C:\Cue_extra\smoke_packaged"`

## Next Best Task
- PR13 acceptance criteria met; proceed to next roadmap item.
