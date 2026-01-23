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

```bash
python -m app.transcribe_worker --print-transcribe-config --prefer-gpu
```

```cmd
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
