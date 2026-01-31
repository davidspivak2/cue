# Contributing

Thanks for helping improve Cue! This guide focuses on Windows development, which is the primary target for the app and build pipeline.

## Local setup (Windows 11 + Python 3.11)
1. Create and activate a venv:
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bat
   python -m pip install -r requirements.txt
   ```
   Optional dev/test deps:
   ```bat
   python -m pip install -r requirements-dev.txt
   ```

### FFmpeg acquisition
The app expects `bin\ffmpeg.exe` and `bin\ffprobe.exe` or an FFmpeg installation on PATH.

Option 1 (recommended): run the bundled script:
```bat
download_ffmpeg.bat
```

Option 2: install with winget:
```bat
winget install -e --id Gyan.FFmpeg
```

For more context on the app and pipeline, see:
* `docs/CUE_UX_UI_SPEC.md` (design contract; includes the archived project context appendix).
* `README.md` (archived transcription pipeline appendix + consolidated docs pointers).
* `docs/ROADMAP.md` (single source of truth for tasks).

## New Desktop UI (Tauri + React)
PR1 provides a UI shell only (no backend integration yet). The legacy Qt UI still exists for end-to-end runs.

**Prereqs:** Node.js, Rust toolchain, Visual Studio C++ build tools, WebView2.

**Dev run:**
```bat
cd desktop
npm install
npm run tauri dev
```

**Build:**
```bat
cd desktop
npm run tauri build
```

## Legacy UI (PySide6) — Run from source (developer testing)
```bat
.venv\Scripts\activate
python -m app.main
```
The app will use `bin\ffmpeg.exe`/`bin\ffprobe.exe` if present, otherwise it will fall back to
FFmpeg installed on PATH.


## Recommended dev workflow
* **Branching:** create feature branches from `main`, e.g. `feature/short-description`.
* **Commits:** there are no strict commit conventions enforced; prefer clear, imperative messages (e.g., `Add settings validation`).
* **Pull requests:** describe the change, include steps to test locally, and call out any UX changes.

## Running checks/tests
There is minimal test coverage currently. The preferred way to run tests locally is:
```bat
scripts\run_tests.cmd
```

Notes on `scripts\run_tests.cmd`:
* Prompts for the branch to test and refuses dirty working trees.
* Runs from a temporary copy so branch switches don't change the script mid-run.
* Creates/uses `.venv`, upgrades pip, and installs `requirements.txt` (+ `requirements-dev.txt` if present).
* Set `RUN_TESTS_NO_PAUSE=1` to skip the final pause in non-interactive runs.

If you add tests, prefer pytest:
```bat
pytest
```

Qt-based tests auto-create a `QApplication` (see `tests/conftest.py`). If PySide6
is missing, those tests will be skipped via `pytest.importorskip`.

Preview playback includes a focused regression test for timestamp shifting (feature currently hidden in the GUI):
```bat
pytest tests/test_preview_playback_shift.py
```

Convenience script for branch testing + launch:
```bat
scripts\test_branch.cmd
```

## Dependency syncing (Windows helpers)
`scripts\start_app.cmd` and `scripts\run_tests.cmd` automatically install dependencies when
`requirements.txt` or `requirements-dev.txt` change. You can override this behavior with
`start_app.cmd --install` or `start_app.cmd --no-install`.

### CI
There is no CI pipeline configured yet (no `.github/workflows`), so run relevant checks locally before opening a PR.

## Packaging / release (Windows)
To build the distributable executable, use:
```bat
.venv\Scripts\activate
build_exe.bat
```

Expected output:
```
dist\Cue\Cue.exe
```

The `dist\Cue\` folder is the portable package you can zip or copy for release.

## Preview cache notes
Preview still frames are cached under:
`%LOCALAPPDATA%\Cue\cache\preview_frames`. If you need to refresh
previews during development, clear this folder.
