# Cue Desktop (Tauri + React)

For overall project info, see: [`../README.md`](../README.md).

## Prerequisites (Windows)

- Node.js (LTS)
- Rust toolchain (stable) with `cargo`
- WebView2 Runtime (Evergreen)

## Desktop (Tauri) development
The recommended contributor workflow is still the one-command entrypoint from the repo root:
```bat
C:\Cue_repo\scripts\run_desktop_all.cmd
```
Use the desktop-only scripts below when you need to iterate/debug the UI without running the full stack.

### Desktop-only scripts (from repo root)

Install desktop dev dependencies (uses `package-lock.json` via `npm ci`):
```bat
scripts\install_desktop_dev_deps.cmd
```
Note: this script is expected to be run from the repo root `scripts\` folder.

Run the desktop dev server / Tauri dev flow:
```bat
scripts\run_desktop_dev.cmd
```

## Install dependencies

```bat
cd desktop
npm ci
```

## Run in dev mode (Tauri window)

```bat
npm run tauri dev
```

## Run backend dev server

One-time backend deps install (from repo root):
```bat
scripts\install_backend_dev_deps.cmd
```

Run backend (from repo root):
```bat
scripts\run_backend_dev.cmd
```

Health check URL: http://127.0.0.1:8765/health
Backend dev logs land in `C:\Cue_extra\backend_dev.log`.

## Current backend wiring (implemented)
- Backend health endpoint is available (used by dev scripts), and Settings reads/writes `/settings`.
- Backend endpoints for pipeline jobs and SSE are implemented (`POST /jobs`, `GET /jobs/{job_id}/events`).
- The Home screen UI is still a placeholder; the Job Runner/Monitor UI is tracked in `docs/ROADMAP.md` (Desktop UI Migration D3).
- Cancel is supported by the backend (`POST /jobs/{job_id}/cancel`) and will be surfaced in the Job Runner UI.

## Full dev workflow (backend + UI)

```bat
scripts\install_backend_dev_deps.cmd
scripts\run_backend_dev.cmd
cd desktop
npm ci
npm run tauri dev
```

## Build Windows bundles/installers

```bat
npm run tauri build
```

## Build outputs

After `npm run tauri build`, Windows artifacts are emitted under:

```
desktop\src-tauri\target\release\bundle\
```

Look for `.msi` and `.exe` (NSIS) installers inside the `bundle` subfolders.
