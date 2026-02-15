# Contributing

Thanks for helping improve Cue! This guide covers everything you need to get the app running locally and start contributing.

For a high-level overview of how the codebase is organized, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## First-time contributor quick start

1. Clone the repo and install Python + Node.js (see platform-specific setup below).
2. Run the one-command dev launcher:
   ```bat
   scripts\run_desktop_all.cmd
   ```
   This installs dependencies, starts the backend, and opens the desktop app.
3. Make your changes on a feature branch, test locally, and open a PR.

That's it for the basics. The rest of this guide covers setup details for each platform.

---

## Windows setup (primary platform)

### Prerequisites

- **Python 3.11+**
- **Node.js** (LTS)
- **Rust toolchain** (stable) with `cargo`
- **Visual Studio C++ build tools** (for native compilation)
- **WebView2 Runtime** (usually already installed on Windows 10/11)

### Python environment

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Optional dev/test dependencies:
```bat
python -m pip install -r requirements-dev.txt
```

### FFmpeg

The app needs FFmpeg and FFprobe. Either:

**Option 1** (recommended) — run the bundled download script:
```bat
download_ffmpeg.bat
```

**Option 2** — install via winget:
```bat
winget install -e --id Gyan.FFmpeg
```

The app looks for `bin\ffmpeg.exe` / `bin\ffprobe.exe` first, then falls back to the system PATH.

### Running the app (Windows)

The preferred one-command entrypoint:
```bat
scripts\run_desktop_all.cmd
```

This handles everything: installs backend and frontend dependencies, starts the Python backend, waits for it to be healthy, then launches the Tauri desktop app.

---

## macOS setup

### Prerequisites

- **Python 3.11+** (via Homebrew: `brew install python@3.11`)
- **Node.js** (LTS, via Homebrew: `brew install node`)
- **Rust toolchain** (via rustup: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
- **Xcode Command Line Tools** (`xcode-select --install`)
- **FFmpeg** (`brew install ffmpeg`)

### Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional dev/test dependencies:
```bash
pip install -r requirements-dev.txt
```

### Running the app (macOS)

Start the backend:
```bash
source .venv/bin/activate
python -m app.backend_server
```

In a second terminal, start the desktop app:
```bash
cd desktop
npm ci
npm run tauri dev
```

> **Note:** The `scripts/*.cmd` files are Windows-only. On macOS, run the backend and desktop dev server separately as shown above.

---

## Desktop app (Tauri + React)

The desktop UI lives in `desktop/` and communicates with the Python backend over HTTP and SSE.

For desktop-specific setup details, see [`desktop/README.md`](../desktop/README.md).

**Install frontend dependencies:**
```bash
cd desktop
npm ci
```

**Run in dev mode:**
```bash
npm run tauri dev
```

**Build installers:**
```bash
npm run tauri build
```

---

## Legacy Qt UI (PySide6) — reference only

The legacy Qt UI under `app/main.py` is the original production interface. It is kept as a reference while the Tauri app reaches full feature parity. **Do not add new features to the Qt UI.** It will be removed once the Tauri app is fully functional.

To run it (Windows only, for reference):
```bat
.venv\Scripts\activate
python -m app.main
```

---

## Development workflow

- **Branching:** Create feature branches from `main`, e.g. `feature/short-description`.
- **Commits:** Prefer clear, imperative messages (e.g., "Add settings validation").
- **Pull requests:** Describe the change, include steps to test locally, and call out any UX changes.

## Running tests

The preferred way to run tests locally:

```bash
pytest
```

### Desktop e2e tests (Playwright)

These tests exercise the Tauri UI flow in a browser:

1) Start the Vite dev server (keep it running in a separate terminal):
```bash
cd desktop
npx vite --port 5173
```

2) Run the e2e tests:
```bash
cd desktop
npm run test:e2e
```

On Windows, there is also a helper script:
```bat
scripts\run_tests.cmd
```

Notes:
- Qt-based tests auto-create a `QApplication`. If PySide6 is not installed, those tests are skipped automatically.
- Set `RUN_TESTS_NO_PAUSE=1` to skip the final pause in non-interactive runs on Windows.

### Linting

Lint must pass with zero errors and zero warnings before merge:

- **Frontend (desktop):** From repo root, `cd desktop` then `npm run lint` (ESLint).
- **Python (app, tests, tools):** From repo root, `python -m ruff check app tests tools`.
- **Rust (Tauri):** From repo root, `cd desktop/src-tauri` then `cargo clippy`.

### CI

There is no CI pipeline configured yet. Run tests and lint locally before opening a PR.

---

## Packaging / release

### Windows (Tauri installer)

```bash
cd desktop
npm run tauri build
```

Outputs `.msi` and `.exe` installers under `desktop/src-tauri/target/release/bundle/`.

### Windows (Legacy PyInstaller — reference only)

```bat
.venv\Scripts\activate
build_exe.bat
```

Produces `dist\Cue\Cue.exe` (portable folder).

### macOS

```bash
cd desktop
npm run tauri build
```

Produces a `.dmg` under `desktop/src-tauri/target/release/bundle/`.

---

## Preview cache

Preview still frames are cached at `%LOCALAPPDATA%\Cue\cache\preview_frames` (Windows) or `~/Library/Application Support/Cue/cache/preview_frames` (macOS). Clear this folder if you need to force a preview refresh during development.

---

## Internal documentation

For internal planning documents (roadmap, UX spec, migration plans), see [`docs/internal/`](internal/).
