# HebrewSubtitleGUI

Windows desktop app for extracting Hebrew subtitles with faster-whisper (large-v3) and optionally hard-burning them into a new MP4. The GUI is built with PySide6 and is packaged as a double-clickable `.exe` with bundled FFmpeg.

## Docs
- ROADMAP.md is the only task list and single source of truth for “what to do next.”
- HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md is the design contract for the redesign.
- Historical docs were consolidated; archived contents now live in the ROADMAP appendices, the UX spec appendix, and the README appendices below.
- README describes current behavior in main; future redesign behavior is defined in HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md.

## Features
- Drag & drop or browse a single video (`.mp4`, `.mkv`, `.mov`, `.m4v`).
- Extracts mono 16k WAV (`<video_stem>_audio_for_whisper.wav`).
- Generates UTF-8 SRT subtitles (`<video_stem>.srt`).
- Hard-burns subtitles into `<video_stem>_subtitled.mp4` with subtitle style presets, subtitle modes, and customization.
- Subtitles-ready preview card with a subtitle still frame (click to expand).
- Subtitle mode selector (Word highlight vs Static) and highlight color picker (Word highlight is the default).
- Highlight color changes refresh the preview still immediately.
- Export uses the graphics overlay renderer only.
- Graphics-based preview rendering keeps subtitle styling aligned with export results.
- Word highlighting now applies correctly on wrapped subtitle lines in the graphics overlay preview/export path.
- Graphics overlay export pipeline streams RGBA frames to FFmpeg.
- Uses GPU (CUDA) when available, auto-falls back to CPU with clear logs.
- Non-blocking UI with Cancel support; runtime logs are written to `%LOCALAPPDATA%\HebrewSubtitleGUI\logs\`.
- Checklist above the progress bar shows in-progress/completed statuses during subtitle creation and export.
- Optional diagnostics bundle: zip logs + outputs automatically on exit.
- Transcription includes VAD gap rescue to recover missed speech in large silent gaps.
- Export is available immediately after subtitle creation in the Subtitles Ready view.

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
  srt_utils.py            # SRT parsing/formatting helpers
  subtitle_style.py       # Subtitle style presets and style normalization helpers
  graphics_overlay_export.py # Graphics overlay export planning + helpers
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

## Quick start (Windows EXE)
1. Double-click `HebrewSubtitleGUI.exe` (or create a shortcut and launch it).
2. Drop a video in the window and click **Create subtitles**.
3. Expect outputs next to your video: `<video_stem>_audio_for_whisper.wav`, `<video_stem>.srt`, and `<video_stem>_subtitled.mp4`.
4. Logs and cache live under `%LOCALAPPDATA%\HebrewSubtitleGUI\...`.

For more detail, see the UX/UI design contract in [`docs/HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md`](docs/HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md).

## Notes on model downloads
- The first transcription run downloads the `large-v3` model from Hugging Face.
- This can take time and will be logged in the app.
- Symlink warnings on Windows are logged but not fatal.

## Troubleshooting
- **CUDA missing DLLs / GPU error**: The app automatically falls back to CPU and logs the CUDA error.
- **FFmpeg not found**: Run `download_ffmpeg.bat` or install FFmpeg via winget.
- **Audio copy fails during burn-in**: The app retries with AAC audio and logs the retry.
- **Graphics overlay export debugging**: See the “Appendix: Archived — Graphics overlay debugging notes (original)” section below.

## Appendix: Archived — Transcription pipeline (original)
# Transcription pipeline

This document describes how the app extracts audio, launches the transcription worker,
and writes SRT output. It also explains how to compare transcription configuration
between machines.

## End-to-end flow

1. **Video selection (GUI).**
   The GUI selects a video file and prepares output paths for the WAV and SRT.
2. **Audio extraction via FFmpeg.**
   The GUI runs FFmpeg to extract a 16 kHz mono WAV. It logs the exact FFmpeg command
   to the GUI log.
3. **Whisper worker subprocess.**
   The GUI launches `app.transcribe_worker` (or the packaged worker executable) with
   the WAV/SRT paths and GPU/CPU flags.
4. **Model load and transcription.**
   The worker selects device/compute type based on `--prefer-gpu`/`--force-cpu` and
   the CUDA probe, loads the `faster-whisper` model from the cache, and calls
   `model.transcribe(...)` with the configured parameters.
5. **SRT generation.**
   The worker converts segments into SRT, writes the file, and reports completion.
6. **Word-timing alignment (word highlight mode).**
   When subtitle mode is set to word highlight, the GUI runs `app.align_worker`
   to populate `<video_stem>.word_timings.json` using WhisperX alignment. The
   alignment step re-runs when the timings file is missing, invalid, empty, or stale.

## FFmpeg discovery notes

FFmpeg and FFprobe are resolved in this order:
1. Packaged `bin\ffmpeg.exe`/`bin\ffprobe.exe` for PyInstaller builds.
2. `bin\ffmpeg.exe`/`bin\ffprobe.exe` in the repo for source runs.
3. System `PATH` fallback.

## Model cache paths

Model files live under the models directory returned by `app.paths.get_models_dir()`.
The worker logs the `MODELS_DIR` and `MODEL_DIR` paths at startup. The configured
`download_root` passed to `WhisperModel` points at this directory, so model cache
contents should be comparable across machines.

## Transcription parameters

The worker logs a full `TRANSCRIBE_CONFIG_JSON` line and a readable
`TRANSCRIBE_CONFIG_TEXT` block at startup. This configuration includes:

- **Audio extraction:** the FFmpeg arguments used by the GUI (see the GUI log and
  `TRANSCRIBE_PARENT_CONFIG` entries, plus any `--ffmpeg-args-json` provided to the worker).
- **Device selection:** whether GPU was requested, the CUDA probe result, and the
  chosen device/compute type.
- **Model initialization:** the exact `WhisperModel(...)` arguments, including
  `device`, `compute_type`, `cpu_threads`, `num_workers`, and `download_root`.
- **Transcription kwargs:** the `model.transcribe(...)` keyword arguments such as
  `beam_size`, `vad_filter`, `vad_parameters`, and `word_timestamps`.
- **SRT formatting:** the worker-controlled formatting (timestamp style, index
  start, trimming, and separator behavior).

The worker also enumerates the defaults it relies on (for example, parameters like
`best_of` or `temperature` that are left to `faster-whisper` defaults).

## Comparing machines

To compare machines without running a transcription or downloading models, run:

```cmd
python -m app.transcribe_worker --print-transcribe-config --prefer-gpu
```

### Optional alternatives (non-primary)

```bash
python -m app.transcribe_worker --print-transcribe-config --prefer-gpu
```

```powershell
python -m app.transcribe_worker --print-transcribe-config --prefer-gpu
```

This prints:

- `TRANSCRIBE_CONFIG_JSON ...` (single-line JSON for diffing)
- `TRANSCRIBE_CONFIG_TEXT ...` (multi-line human-readable summary)

The config dump resolves the effective compute type (even in `--print-transcribe-config`
mode), so it is safe to use for comparing GPU/CPU fallbacks without running a full
transcription.

Compare the JSON payloads between machines to spot differences in device selection,
model cache paths, or parameter settings.

## Notes on segmentation and formatting

SRT segmentation starts from `faster-whisper` output segments, but the worker
**does** apply a splitter (`app/srt_splitter.py`) when segments are long. A segment
is split into multiple cues if it exceeds any of these thresholds:
- **Apply-if thresholds:** >12.0s duration, >160 characters, or >26 words.
- **Max cue targets when splitting:** 8.0s, 90 characters, or 14 words per cue.

When splitting, the worker prefers boundaries at punctuation, then large gaps
(`gap_sec=0.4`) between words. If word timings cannot be aligned to the original
segment text, the splitter falls back to time-based chunking and reconstructs text
from words. If segmentation differs between machines, compare the config dump,
device selection, model versions, and splitter thresholds.

## VAD gap rescue

When VAD filtering is enabled, the worker scans for large gaps between VAD segments.
If a gap exceeds the rescue threshold, the worker extracts each gap audio slice and
re-transcribes it with VAD disabled, then merges any usable segments back into the
main transcript. Limits are enforced on the number of gaps and total rescued duration.

## Punctuation rescue

When **Improve punctuation automatically (recommended)** is enabled, the pipeline can run an optional punctuation rescue after the initial transcription. This happens in the Create Subtitles flow before/alongside gap rescue, and it only triggers when punctuation quality appears poor. The rescue may run multiple passes; the UI reflects this with “Improving punctuation...” on attempt 1 and “Improving punctuation... (attempt 2/3)” on later attempts. The UI also supports skipping punctuation rescue: clicking Skip shows “Skipping...”, the step only becomes Skipped after confirmation, and the pipeline continues forward without waiting on punctuation rescue to finish.

## Subtitle preview generation (GUI)

When subtitles are ready, the GUI prepares a preview moment:

1. **SRT parsing + cue selection.** The GUI parses the generated SRT file, picks the
   first non-empty cue, and anchors the preview moment at ~25% into that cue
   (clamped to the cue bounds).
2. **Preview still frame.** The GUI extracts a raw video frame via FFmpeg and renders
   subtitles with the graphics preview renderer (draws text directly onto the image).
   The graphics preview renderer computes highlight clip rects line-relative so wrapped
   lines highlight correctly.
   The preview cache key includes subtitle style + highlight settings and word-timing
   mtimes so word-highlight previews update when alignment data changes. Highlight
   color changes force an immediate preview refresh. Frames are cached under
   `%LOCALAPPDATA%\HebrewSubtitleGUI\cache\preview_frames`.
   In Word highlight mode, the still preview highlights the **second word** when no
   explicit word index is supplied (preview-only behavior; not time-accurate).

## Appendix: Archived — Graphics overlay debugging notes (original)
# Graphics Overlay Renderer Debugging Notes

## What the graphics overlay renderer does
The graphics overlay renderer draws subtitle text into RGBA frames (using the same styling rules as the preview renderer) and streams those frames to FFmpeg, which composites them over the source video using an overlay filter. This means export is purely image-based: the renderer paints the text into frames, and FFmpeg handles the video encode + audio mux.

## Where to look when export or preview fails
**Primary logs**
- App runtime logs live in `%LOCALAPPDATA%\HebrewSubtitleGUI\logs\`.
- Each run produces a timestamped log file like `hebrew_subtitle_gui_YYYYMMDD_HHMMSS.log`.

**Diagnostics JSON (optional)**
- When diagnostics logging is enabled, JSON files named `diag_*.json` are written **next to the export outputs** (same folder as the selected save location).
- If “Zip logs and outputs on exit” is enabled, the app writes `hebrew_subtitles_bundle_*.zip` next to the selected video; it includes logs, diagnostics JSON, and output artifacts.

## How to enable diagnostics
In the app, open Settings → Diagnostics and enable the following checkboxes (as needed):
- “Enable diagnostics logging”
- “Write diagnostics on successful completion”
- “Zip logs and outputs on exit”
- “App + system info”
- “Video info”
- “Audio (WAV) info”
- “Transcription config”
- “SRT stats”
- “Commands + timings”

## Most important debug signals
1. **Renderer line at export start**
   - Look for `Export renderer=graphics_overlay` in the log to confirm the pipeline.
2. **FFmpeg command line + filter**
   - The log captures the export filter string and the FFmpeg command used for burn-in.
   - The diagnostics JSON includes `commands_timings.burn_in_command_used` and `commands_timings.burn_in_filter`.
3. **FFmpeg stderr output**
   - Export failures emit the FFmpeg stderr lines into the session log. This is usually the fastest signal for codec/muxing failures.

## Quick triage checklist
- Confirm the renderer line is present and set to graphics overlay.
- Confirm the overlay filter is `overlay=0:0:format=auto` (graphics overlay pipeline).
- If audio copy fails, verify the retry uses AAC (logged as `burn_in_audio_mode`).
- Use the diagnostics JSON to cross-check paths (video, SRT, output) when mismatches are suspected.

## Appendix: Archived — Documentation index (original)
# Documentation index

Welcome to the HebrewSubtitleGUI documentation set. Use this page to find the right guide for your task.

## Start here
- Roadmap (upcoming work): [`docs/ROADMAP.md`](docs/ROADMAP.md).
- Current behavior overview + archived references: [`README.md`](README.md).
- Redesign contract: [`docs/HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md`](docs/HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md).
- Developers: [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## Guides
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — single source of truth for tasks and milestones.
- [`docs/HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md`](docs/HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md) — redesign contract and archived project context appendix.
- [`README.md`](README.md) — current behavior summary and archived appendices:
  - [Transcription pipeline appendix](README.md#appendix-archived--transcription-pipeline-original)
  - [Graphics overlay debugging appendix](README.md#appendix-archived--graphics-overlay-debugging-notes-original)
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) — setup, development workflow, tests, and packaging notes.
