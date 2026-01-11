# Hebrew Subtitle GUI — Project Context (Read This First)

**Last updated:** 2026-01-11

This document is for:
- new contributors
- new chat sessions
- future-you, when something breaks and you need the “why” and the “where” quickly

It explains:
- what the app does
- how the pipeline works (GUI → FFmpeg → faster-whisper → SRT → FFmpeg burn-in)
- where files go (models, logs, outputs)
- the PR1–PR13 roadmap **and current status**
- what has been worked on since PR6 (progress + settings + diagnostics)
- the current punctuation problem (what we measured, what we tried, what to do next)

UX/UI target spec (design contract): **`HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md`** (same folder as this file).

---

## 1) What the app does (user-facing)

Goal: turn a single video into:
1) a Hebrew subtitle file (`.srt`, UTF‑8), and optionally
2) a new subtitled video (`*_subtitled.mp4`) with the subtitles burned-in.

Typical flow:
1) Choose or drag & drop a video.
2) App extracts a mono 16 kHz WAV using FFmpeg (optional cleanup filter).
3) App runs faster‑whisper (Whisper) to transcribe Hebrew and write an `.srt`.
4) User optionally reviews/edits in Subtitle Edit.
5) App burns subtitles into a new MP4 using FFmpeg.

---

## 2) How it works (technical overview)

### Main moving parts
- **GUI (PySide6)**: `app/main.py`
  - state machine / stacked pages (Home + Settings)
  - launches workers and updates UI
- **Worker thread (PySide6 QRunnable/QThread)**: `app/workers.py`
  - runs FFmpeg extraction
  - spawns transcription worker subprocess
  - runs FFmpeg burn-in with real progress
  - emits structured progress events to the GUI
- **Transcription worker (separate process)**: `app/transcribe_worker.py`
  - loads Whisper (faster‑whisper)
  - transcribes audio
  - prints progress tokens to stdout (parsed by parent)
  - writes the `.srt`
- **SRT splitting + formatting**:
  - `app/srt_splitter.py` (turns Whisper segments into readable cues)
  - `app/srt_utils.py` (timestamp formatting + SRT file output)
- **FFmpeg discovery + helpers**: `app/ffmpeg_utils.py`

### Why transcription is a subprocess
Transcription uses native dependencies (ctranslate2/tokenizers/etc.) and can take minutes.
Running it out-of-process:
- keeps the UI responsive
- makes cancellation/watchdogs reliable
- isolates crashes in packaged builds

---

## 3) Where data goes

### App data root (Windows)
`%LOCALAPPDATA%\HebrewSubtitleGUI\`

Common subfolders:
- `models\` — faster‑whisper model cache
- `logs\` — GUI runtime logs (timestamped)
- `cache\` — thumbnails, preview frames, etc. (as implemented)
- `config.json` — user settings

### Per-video outputs (folder chosen by Save policy)
- `<video_stem>_audio_for_whisper.wav` (scratch audio)
- `<video_stem>.srt` (subtitles)
- `<video_stem>_subtitled.mp4` (burned output)

### Diagnostics JSON (opt-in, **on success**)
If enabled in Settings, diagnostics JSON is written **next to the created output** (hotfixed from the old LocalAppData location):
- `diag_generate_srt_YYYYMMDD_HHMMSS_micro.json`
- `diag_burn_in_YYYYMMDD_HHMMSS_micro.json`

On failure, the app still writes/keeps error logs even if success diagnostics are disabled.

### Local dev benchmark outputs (not committed)

When running `tools\punct_benchmark.py` (and similar local diagnostics), save output logs outside the repo so they are never accidentally committed:

- Folder: `C:\subtitles_extra\outputs`

Example:
- `C:\subtitles_extra\outputs\bench_rescue_test_audio_30s.txt`
- `C:\subtitles_extra\outputs\bench_rescue_test_audio_full.txt`

---

## 4) Running and building

### Run from source
```bat
cd C:\subtitles_repo
.venv\Scripts\activate
python -m app.main
```

### Build EXE (PyInstaller)
```bat
cd C:\subtitles_repo
.venv\Scripts\activate
build_exe.bat
```

Expected output:
- `dist\HebrewSubtitleGUI\HebrewSubtitleGUI.exe`

---

## 5) Roadmap (PR1–PR13) and current status

This repo started with a 13‑PR UX/architecture overhaul plan. The exact PR boundaries have shifted a bit (some items were combined or rescaled), but the sequence is still a good mental model.

### Status snapshot (as of 2026-01-11)

Done / merged:
- **PR1** — dark theme foundation ✅
- **PR2** — step-based state machine shell (stacked pages) ✅
- **PR3** — video selection UX (DropZone + thumbnail card + replace on drop) ✅
- **PR4 (rescoped)** — Settings page + save policy (Ask / Same folder / Always) ✅
- **PR5 (partial)** — copy polish + CTA reduction (still needs another pass later) 🟡
- **PR6 (expanded)** — progress work ✅
  - burn-in/export (FFmpeg) progress: smooth and correct
  - transcription progress: improved, but can still move in coarse jumps depending on Whisper segmentation
- **Extra (not originally in the plan)** — opt-in success diagnostics JSON + “write next to outputs” hotfix ✅

Not done yet (still in PR7+ territory):
- **PR7** — Subtitles-ready page: auto-pick a subtitle moment and render a preview still frame
- **PR8** — style presets + customize panel + instant preview updates
- **PR9** — in-app preview playback (QtMultimedia) + caching
- **PR10** — karaoke-like highlighting (default ON)
- **PR11** — “delightful waiting” visuals (waveform + thumbnail strip)
- **PR12** — error UX with details drawer + copy diagnostics
- **PR13** — packaging hardening / smoke tests

### Where a new contributor should pick up
Priority work items:
1) **Punctuation issue (quality blocker)** — see Section 7.
2) Continue the UX roadmap at **PR7** (preview still frame) once punctuation is acceptable.

---

## 6) What changed since PR6 (summary)

### 6.1 Progress + status text improvements
Problem observed:
- During transcription, UI could sit at ~20% for a long time and then jump (e.g., to 28%), making it feel stuck.

Changes implemented:
- Progress is now **step-weighted** (audio extract → transcription → burn-in) into one global percent.
- Transcription emits “heartbeat” style signals so the UI can keep moving even when Whisper only reports progress in large segment jumps.
- Status text was clarified (e.g., “Listening to audio”).

Current reality:
- Burn-in progress is solid.
- Transcription progress is better than before, but still depends heavily on Whisper’s segmenting behavior.

### 6.2 Settings page (full-page, not a dialog)
Key UX decisions implemented:
- Settings replaces the content area (stacked page), not a modal.
- Save policy moved into Settings:
  - Ask every time
  - Same folder as the video
  - Always save to this folder (+ Browse…)
- If Save policy is not “Always…”, the path is still displayed but disabled.
- If Save policy is “Ask every time”, **no path is shown**.

Performance settings implemented:
- “Quality” options map to device/compute-type selections.
- **Auto on CPU-only → int16** (per requirement).
- A **float32** option exists (slowest, potentially most accurate) for debugging/edge cases.

### 6.3 Diagnostics / logs (for debugging even when runs succeed)
Goal:
- When a user reports “it worked but results are bad,” we need structured logs (video/audio/srt/model/params) without asking for screenshots.

Behavior:
- Disabled by default.
- When enabled, a diagnostics JSON file is written next to outputs.
- Failure logs still exist by default even if success diagnostics are off.

---

## 7) Punctuation problem (current investigation)

### 7.1 What we see
- Recent SRT output sometimes has **no commas at all**, and generally far less punctuation than older “good” output.
- This is visible in side-by-side comparisons of SRT outputs.

### 7.2 Why “fixing commas in our splitter” is usually the wrong first move
The SRT splitter (`app/srt_splitter.py`) mostly preserves punctuation **if Whisper provides it**.
The splitter can only “lose” punctuation in one main situation:
- It fails to align `segment.words` back to `segment.text` and falls back to joining the word tokens (which often lack punctuation).

However, we verified cases where:
- **Whisper raw segment text already contains almost no punctuation**, so there is nothing for the splitter to preserve.

### 7.3 What we measured (key debugging results)
We used small debug scripts (run locally) to count punctuation in **raw Whisper segments** before any splitting.

Observed matrix on a 30s Hebrew WAV (representative):
- `large-v3`, `int16`, VAD **on**, word timestamps **on** → **0 commas / 0 periods**
- `large-v3`, `int16`, VAD **off** → sometimes **1 comma**
- `large-v3`, `int8`, VAD **on** → sometimes **1 comma**
- `large-v2`, `int16`, VAD **on** → **multiple periods** (punctuation output is noticeably better)

Conclusion (current best hypothesis):
- The missing punctuation is **primarily a model/decoding behavior issue** (especially `large-v3` on Hebrew), not an SRT formatting bug.

### 7.4 Things that were tried
- Tweaking `srt_splitter` reconstruction/alignment logic:
  - Helps only when punctuation exists in `segment.text`.
  - Does not create commas if Whisper didn’t output them.
- Adding a Hebrew `initial_prompt` asking Whisper to add punctuation:
  - Did not reliably restore commas.

### 7.5 Constraints / non-negotiables
- Do **not** increase “words per timestamp” (cue length) just to add punctuation.
- Keep timing behavior stable:
  - punctuation restoration should ideally modify text only, not timestamps.

### 7.6 Recommended next steps (for the next PR focused on punctuation)
Do these in order (cheapest signal first):

1) **Make it easy to confirm where punctuation is lost**
   - Add a diagnostics field that captures a short preview of raw `segment.text` output (first N segments) and punctuation counts.
   - This must run in production builds (when diagnostics are enabled).

2) **Try model/decoder configuration changes behind a setting**
   Candidate experiments (keep them behind a “Punctuation” / “Advanced” toggle, off by default):
   - Toggle VAD on/off (Hebrew punctuation seemed to improve slightly with VAD off).
   - Try `large-v2` for Hebrew only (or provide a “Model: v3 / v2” override).
   - Evaluate whether compute type (`int8` vs `int16`) affects punctuation/accuracy tradeoffs.

3) **Only if Whisper still won’t emit punctuation: add post-processing punctuation restoration**
   - Must not change timestamps or cue boundaries.
   - Should run on the *final cue text* so it does not affect splitting logic.
   - Must be optional (because it adds complexity and can introduce errors).

---

## 8) Performance notes (why 3m audio can take ~20 minutes)

The Whisper **large** models are expensive on CPU.

Example observed in diagnostics:
- ~194 seconds of audio (3m14s) on CPU (`large-v3`, `int16`, 4 threads) → ~1300 seconds transcription time (~6.7× realtime).

This can be normal on low-end laptops.

Practical guidance:
- If a CUDA GPU is available, prefer GPU (often much faster).
- If CPU-only, prefer:
  - `Auto` / `Accurate` (int16) for correctness
  - `Fast` (int8) only when speed matters and errors are acceptable
  - `Ultra` (float32) only for debugging/edge cases

---

## 9) Debugging checklist (what to collect)

When reporting issues, attach:
1) The **diagnostics JSON** (if enabled)
2) The produced `.srt`
3) The exact Settings used (or let diagnostics capture it)

If diagnostics are not enabled, capture:
- the GUI runtime log file from `%LOCALAPPDATA%\HebrewSubtitleGUI\logs\`
- the `TRANSCRIBE_CONFIG_JSON` line (if present)

---

## 10) Important implementation gotchas

- **Console windows:** subprocess launches must use Windows flags to avoid flashing consoles.
- **PyInstaller + native deps:** ctranslate2/tokenizers/Qt multimedia plugins can fail only in EXE.
- **Path handling:** support OneDrive paths and spaces; always quote paths when calling tools.
- **FFmpeg progress parsing:** keep it resilient (stderr format differences).

