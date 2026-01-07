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
  main.py
  workers.py
  ffmpeg_utils.py
  srt_utils.py
bin/
  ffmpeg.exe
  ffprobe.exe
build_exe.bat
download_ffmpeg.bat
requirements.txt
```

## Developer setup (Windows 11 + Python 3.11)
1. `python -m venv .venv`
2. `.venv\Scripts\activate`
3. `python -m pip install -r requirements.txt`
4. `python -m pip install pyinstaller`

### Obtain FFmpeg binaries
Place `ffmpeg.exe` and `ffprobe.exe` in `bin\`.

Option A (manual):
- Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/
- Extract and copy `ffmpeg.exe` and `ffprobe.exe` into `bin\`

Option B (scripted, requires 7-Zip in PATH):
- Double-click `download_ffmpeg.bat`

## Run from source (developer testing)
```
.venv\Scripts\activate
python -m app.main
```

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
- **FFmpeg not found**: Ensure `bin\ffmpeg.exe` and `bin\ffprobe.exe` exist before building.
- **Audio copy fails during burn-in**: The app retries with AAC audio and logs the fallback.
