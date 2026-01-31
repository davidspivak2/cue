# Cue Desktop (Tauri + React)

## Prerequisites (Windows)

- Node.js (LTS)
- Rust toolchain (stable) with `cargo`
- WebView2 Runtime (Evergreen)

## Install dependencies

```powershell
cd desktop
npm install
```

## Run in dev mode (Tauri window)

```powershell
npm run tauri dev
```

## Run backend stub (PR2)

```powershell
scripts\\run_backend_dev.cmd
```

Health check URL: http://127.0.0.1:8765/health

## Full dev workflow (backend + UI)

```powershell
scripts\\run_backend_dev.cmd
cd desktop
npm run tauri dev
```

## Build Windows bundles/installers

```powershell
npm run tauri build
```

## Build outputs

After `npm run tauri build`, Windows artifacts are emitted under:

```
workspace\cue\desktop\src-tauri\target\release\bundle\
```

Look for `.msi` and `.exe` (NSIS) installers inside the `bundle` subfolders.
