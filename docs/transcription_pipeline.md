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

This prints:

- `TRANSCRIBE_CONFIG_JSON ...` (single-line JSON for diffing)
- `TRANSCRIBE_CONFIG_TEXT ...` (multi-line human-readable summary)

Compare the JSON payloads between machines to spot differences in device selection,
model cache paths, or parameter settings.

## Notes on segmentation and formatting

SRT segmentation is determined by `faster-whisper` output segments. The worker
does not re-segment or post-process text beyond trimming whitespace and formatting
timestamps. If segmentation differs between machines, focus on differences in the
config dump, device selection, or library versions.
