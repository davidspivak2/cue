# HebrewSubtitleGUI

Windows desktop app for extracting Hebrew subtitles with faster-whisper (large-v3) and optionally hard-burning them into a new MP4. The GUI is built with PySide6 and is packaged as a double-clickable `.exe` with bundled FFmpeg.

## Features
- Drag & drop or browse a single video (`.mp4`, `.mkv`, `.mov`, `.m4v`).
- Extracts mono 16k WAV (`*_audio_for_whisper.wav`).
- Generates UTF-8 SRT subtitles (`.srt`).
- Hard-burns subtitles into `<basename>_subtitled.mp4` with configurable styling.
- Uses GPU (CUDA) when available, auto-falls back to CPU with clear logs.
- Non-blocking UI with live logs and Cancel support.

## Project structure
```
app/
  main.py                 # Application entry point (Qt UI + orchestration)
  transcribe_worker.py    # Background transcription worker logic
  srt_splitter.py         # Subtitle chunking/splitting helpers
  progress.py             # Progress tracking and reporting utilities
  workers.py              # Worker queue/thread management
  ffmpeg_utils.py         # FFmpeg invocation helpers
  srt_utils.py            # SRT parsing/formatting helpers
  ui/                     # UI components, theme, and widgets
bin/
  ffmpeg.exe
  ffprobe.exe
docs/                     # Project documentation
tools/                    # Developer tooling/utilities
tests/                    # Test suite
build_exe.bat
download_ffmpeg.bat
run_app.py                # Convenience script to launch the app
run_worker.py             # Convenience script to launch the worker
requirements.txt
```

## Developer setup (Windows 11 + Python 3.11)
1. `python -m venv .venv`
2. `.venv\Scripts\activate`
3. `python -m pip install -r requirements.txt`
   - This installs all Python dependencies (including `requests`).

### Obtain FFmpeg binaries
Option 1 (recommended): run `download_ffmpeg.bat` (invokes the bundled PowerShell script).

Option 2: install FFmpeg via winget:
```
winget install -e --id Gyan.FFmpeg
```

## Run from source (developer testing)
```
.venv\Scripts\activate
python -m app.main
```
The app will use `bin\ffmpeg.exe`/`bin\ffprobe.exe` if present, otherwise it will fall back to
FFmpeg installed on PATH.

## Build the Windows executable
Double-click `build_exe.bat` or run:
```
.venv\Scripts\activate
build_exe.bat
```
Output will be:
```
dist\HebrewSubtitleGUI\HebrewSubtitleGUI.exe
```
Then double-click `dist\HebrewSubtitleGUI\HebrewSubtitleGUI.exe`.

## Portable install
1. Copy the `dist\HebrewSubtitleGUI\` folder to `C:\Program Files\HebrewSubtitleGUI` (or any folder).
2. Right-click `HebrewSubtitleGUI.exe` → **Create shortcut** → move shortcut to Desktop.
3. Double-click the shortcut to launch (no Command Prompt needed).

## Notes on model downloads
- The first transcription run downloads the `large-v3` model from Hugging Face.
- This can take time and will be logged in the app.
- Symlink warnings on Windows are logged but not fatal.

## Troubleshooting
- **CUDA missing DLLs / GPU error**: The app automatically falls back to CPU and logs the CUDA error.
- **FFmpeg not found**: Run `download_ffmpeg.bat` or install FFmpeg via winget.
- **Audio copy fails during burn-in**: The app retries with AAC audio and logs the fallback.
