# Contributing

Thanks for helping improve HebrewSubtitleGUI! This guide focuses on Windows development, which is the primary target for the app and build pipeline.

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
* `docs/HEBREW_SUBTITLE_GUI_CONTEXT.md`
* `docs/transcription_pipeline.md`

## Run from source (developer testing)
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

If you add tests, prefer pytest:
```bat
pytest
```

Preview playback includes a focused regression test for timestamp shifting:
```bat
pytest tests/test_preview_playback_shift.py
```

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
dist\HebrewSubtitleGUI\HebrewSubtitleGUI.exe
```

The `dist\HebrewSubtitleGUI\` folder is the portable package you can zip or copy for release.

## Preview cache notes
The preview still frames and preview playback clips are cached under:
`%LOCALAPPDATA%\HebrewSubtitleGUI\cache\preview_frames` and
`%LOCALAPPDATA%\HebrewSubtitleGUI\cache\previews`. If you need to refresh
previews during development, clear these folders.
