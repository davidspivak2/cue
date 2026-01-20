# HebrewSubtitleGUI

Windows desktop app for extracting Hebrew subtitles with faster-whisper (large-v3) and optionally hard-burning them into a new MP4. The GUI is built with PySide6 and is packaged as a double-clickable `.exe` with bundled FFmpeg.

## Features
- Drag & drop or browse a single video (`.mp4`, `.mkv`, `.mov`, `.m4v`).
- Extracts mono 16k WAV (`<video_stem>_audio_for_whisper.wav`).
- Generates UTF-8 SRT subtitles (`<video_stem>.srt`).
- Hard-burns subtitles into `<video_stem>_subtitled.mp4` with subtitle style presets, subtitle modes, and customization.
- Subtitles-ready preview card with a subtitle still frame (click to expand).
- Subtitle mode selector (Word highlight vs Static) and highlight color picker (Word highlight is the default).
- Word-highlight pipeline uses ASS rendering with WhisperX word alignment for per-word timing.
- Graphics-based preview rendering keeps subtitle styling aligned with export results.
- Graphics overlay export pipeline streams RGBA frames to FFmpeg (gated by `SUBTITLES_GRAPHICS_OVERLAY_EXPORT=1`; legacy export remains default).
- Uses GPU (CUDA) when available, auto-falls back to CPU with clear logs.
- Non-blocking UI with Cancel support; runtime logs are written to `%LOCALAPPDATA%\HebrewSubtitleGUI\logs\`.
- Optional diagnostics bundle: zip logs + outputs automatically on exit.
- Transcription includes VAD gap rescue to recover missed speech in large silent gaps.
- Export is available immediately after subtitle creation (Subtitle Edit is optional).

## Project structure
```
app/
  main.py                 # Application entry point (Qt UI + orchestration)
  align_utils.py          # Word-alignment plan + helpers
  align_worker.py         # WhisperX alignment worker (word timings)
  transcribe_worker.py    # Background transcription worker logic
  srt_splitter.py         # Subtitle chunking/splitting helpers
  progress.py             # Progress tracking and reporting utilities
  workers.py              # Worker queue/thread management
  ffmpeg_utils.py         # FFmpeg invocation helpers
  graphics_preview_renderer.py # Graphics-based preview rendering
  preview_playback.py     # Preview clip generation and playback caching
  srt_utils.py            # SRT parsing/formatting helpers
  subtitle_style.py       # Subtitle style presets and FFmpeg style mapping
  ass_render.py           # ASS subtitle document generation (static rendering)
  ass_karaoke.py          # ASS step-highlight generation (word highlight mode)
  burn_in_export.py       # Burn-in/export planning for SRT + ASS pipelines
  word_timing_schema.py   # Word timing JSON contract + validation
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

## Developer setup
See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for the canonical Windows setup, FFmpeg acquisition,
run-from-source, testing, and packaging steps.

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
