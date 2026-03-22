# Cue Desktop (Tauri + React)

For overall project info, see: [`../README.md`](../README.md).

## Prerequisites (Windows)

- Node.js (LTS)
- Rust toolchain (stable) with `cargo`
- WebView2 Runtime (Evergreen)

## Desktop (Tauri) development
From the repo root, the usual path is the one-command launcher:
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

## Backend wiring
- Backend health endpoint (`/health`) is used by dev scripts to wait for startup.
- Settings reads/writes via `/settings`.
- Pipeline jobs via `POST /jobs` with SSE event streaming at `GET /jobs/{job_id}/events`.
- Cancel via `POST /jobs/{job_id}/cancel`.

For the full API surface, see [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

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
