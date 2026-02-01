# Cue Desktop (Tauri + React)

## Prerequisites (Windows)

- Node.js (LTS)
- Rust toolchain (stable) with `cargo`
- WebView2 Runtime (Evergreen)

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
workspace\cue\desktop\src-tauri\target\release\bundle\
```

Look for `.msi` and `.exe` (NSIS) installers inside the `bundle` subfolders.
