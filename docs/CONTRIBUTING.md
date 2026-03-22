# Contributing

How to run Cue locally and submit changes. For layout of the repo and pipeline, see [ARCHITECTURE.md](ARCHITECTURE.md).

Non-maintainer pull requests need a signed contributor agreement before merge. See [CLA_POLICY.md](CLA_POLICY.md).

---

## First-time contributor quick start

1. Clone the repo and install Python + Node.js (see platform-specific setup below).
2. Run the one-command dev launcher:
   ```bat
   scripts\run_desktop_all.cmd
   ```
   This installs dependencies, starts the backend, and opens the desktop app.
3. Make your changes on a feature branch, test locally, and open a PR.

The sections below are platform-specific setup.

Personal scripts can go in `scripts/local/` (gitignored; not part of the shared workflow).

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
scripts\download_ffmpeg.bat
```

**Option 2** — install via winget:
```bat
winget install -e --id Gyan.FFmpeg
```

The app looks for `bin\ffmpeg.exe` / `bin\ffprobe.exe` first, then falls back to the system PATH.

For Windows release packaging, `scripts\build_engine.ps1` now provisions a pinned Gyan `8.0.1` essentials build into `bin\` instead of copying a machine-local FFmpeg from `PATH`. You can override the download source for packaging with `CUE_FFMPEG_URL` if you intentionally need a different archive.

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

This desktop-only build uses the current Tauri bundle config in `desktop/src-tauri/tauri.conf.json`.
For packaged Windows installers, that config expects the engine payload under `desktop/src-tauri/`: `cue-engine-parts.json` plus `cue-engine-01-executables.zip` through `cue-engine-04-internal.zip` (small placeholders are committed; run `scripts\build_engine.cmd` before release to replace them with real archives).

---

## Development workflow

- **Branching:** Create feature branches from `main`, e.g. `feature/short-description`.
- **Commits:** Prefer clear, imperative messages (e.g., "Add settings validation").
- **Pull requests:** Describe the change, include steps to test locally, and call out any UX changes.

### Contributor agreement (CLA)

A CLA is a short legal agreement that lets the maintainer keep the option to relicense future versions of Cue later.

- Non-maintainer contributions require a signed CLA before merge.
- The maintainer will provide the agreement during review until an automated signing flow is added.
- See [CLA_POLICY.md](CLA_POLICY.md) for the current policy.

### Workbench-heavy PR rules

Treat a PR as Workbench-heavy if it changes `desktop/src/pages/Workbench.tsx`, preview/checklist state ownership, or `desktop/tests/e2e/workbench-shell.spec.ts`.

- **Single writer per user-visible value:** If a PR changes a displayed value or status, name one canonical writer in the PR body. Frontend fallback logic is only for display-safe degradation, not competing ownership.
- **Large Workbench edits need extraction:** If a PR changes more than 200 lines inside `desktop/src/pages/Workbench.tsx`, extract a hook, component, or pure helper in the same PR, or explain in the PR body why the change is intentionally localized and temporary.
- **Prefer observable waits in Workbench E2E tests:** Do not add raw `waitForTimeout(...)` calls in new or edited Workbench coverage unless the wait is animation-only, uses a named constant, and includes a short reason comment.
- **Document preview fallbacks:** Any preview-related PR must say how it behaves when timings are present, timings are missing or stale, and overlay rendering fails.
- **Use the Workbench PR template fields:** For Workbench-heavy PRs, fill in the `State ownership map`, `Fallback matrix`, `Regression risk`, and `How tested` sections in the PR template.

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
- Some tests use PySide6 for graphics/preview rendering. If PySide6 is not installed, those tests are skipped automatically.
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

For the full Windows release flow from the repo root:

```bat
scripts\build_release.cmd
```

That script rebuilds the split engine zips and manifest under `desktop/src-tauri/` first, then runs the Tauri installer build.
The engine rebuild step also refreshes the pinned FFmpeg package used for the packaged backend, so installer size is not affected by whichever FFmpeg happens to be installed on the build machine.

If you only need to rebuild the Tauri installers and the engine archive is already current:

```bash
cd desktop
npm run tauri build
```

Outputs `.msi` and `.exe` installers under `desktop/src-tauri/target/release/bundle/`.

Windows installers are currently x64-only.

The packaged Windows installer flow shows Cue's installer terms during setup and ships `TERMS.md`, `PRIVACY.md`, `LICENSE`, and `THIRD_PARTY_NOTICES.md` with the app bundle.

The live Windows packaging flow uses those engine part zips and `cue-engine-parts.json` as Tauri bundle resources. The old mirrored `desktop/src-tauri/engine/` folder is not part of the active release path.

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

## Project status and issues

- **[Roadmap](ROADMAP.md)** — What to work on next, milestones, and acceptance criteria.
- **[Known issues](KNOWN_ISSUES.md)** — Detailed bug write-ups and validation notes.

Other planning material (UX specs, session handoffs, migration archives) may live under `docs/internal/` or `docs/handoffs/` **locally only**; those folders are not tracked on GitHub.
