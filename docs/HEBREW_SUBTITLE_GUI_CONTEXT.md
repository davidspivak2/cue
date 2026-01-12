# Hebrew Subtitle GUI — Project Context (Read This First)

**Last updated:** 2026-01-12

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

UX/UI target spec (design contract): **`/docs/HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md`**.

---

## 0) One-page overview (for new maintainers)

**What this app is:** a Windows desktop GUI built with **PySide6** that generates Hebrew subtitles and (optionally) burns them into a new MP4.

**Core workflow:**
1) Select a video
2) Extract audio (FFmpeg)
3) Transcribe to Hebrew SRT (faster‑whisper)
4) Optionally burn subtitles into an MP4 (FFmpeg)

**Primary outputs (exact naming):**
- `<video_stem>_audio_for_whisper.wav`
- `<video_stem>.srt`
- `<video_stem>_subtitled.mp4`

**Runtime modes:**
- Runs from source (python `-m app.main`).
- Runs as a packaged EXE (PyInstaller).
- Worker process launch differs by mode (python module vs worker EXE).

**App data location (Windows):**
`%LOCALAPPDATA%\HebrewSubtitleGUI\` — stores models, logs, config, and cache.

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

## 2.5) Repo layout / architecture map

**What to look at first (core pipeline):**
- `app/main.py` — main UI + settings wiring + state machine
- `app/workers.py` — audio extraction, worker orchestration, burn-in, diagnostics
- `app/transcribe_worker.py` — faster‑whisper transcription + punctuation rescue logic

**Supporting areas:**
- `app/ui/*` — widgets, state helpers, styling/theme
- `app/ffmpeg_utils.py` — ffmpeg discovery + subprocess settings
- `app/srt_utils.py` — SRT formatting primitives
- `app/srt_splitter.py` — cue splitting and word alignment fallback
- `app/progress.py` — progress aggregation and weights
- `tools/*` — local benchmark tools
- `docs/*` — handover + UX spec

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
Save policy determines the output folder:
- **Same folder as the video** → outputs live next to the video file.
- **Always save to this folder** → outputs live in the fixed folder set in Settings.
- **Ask every time** → the user chooses the output folder each run.

Outputs include:
- `<video_stem>_audio_for_whisper.wav` (scratch audio)
- `<video_stem>.srt` (subtitles)
- `<video_stem>_subtitled.mp4` (burned output)

### Diagnostics JSON (opt-in, **on success**)
If diagnostics logging is enabled and “Write diagnostics on successful completion” is ON, diagnostics JSON is written **next to the created output** (hotfixed from the old LocalAppData location):
- `diag_generate_srt_YYYYMMDD_HHMMSS_micro.json`
- `diag_burn_in_YYYYMMDD_HHMMSS_micro.json`

On failure, the app still writes/keeps error logs even if success diagnostics are disabled.

### Local dev benchmark outputs (not committed)

When running `tools\punct_benchmark.py` (and similar local diagnostics), save output logs outside the repo so they are never accidentally committed:

- Folder: `C:\subtitles_extra\outputs`
- Do not write benchmark logs into `C:\subtitles_repo` (repo) to avoid accidental commits.

Example:
- `C:\subtitles_extra\outputs\bench_rescue_test_audio_30s.txt`
- `C:\subtitles_extra\outputs\bench_rescue_test_audio_full.txt`

---

## 3.25) Persisted settings (config.json) reference

Settings are stored in `%LOCALAPPDATA%\HebrewSubtitleGUI\config.json` and are loaded in `app/main.py`.

| Config key | UI label (exact) | Allowed values | Default | Pipeline impact |
| --- | --- | --- | --- | --- |
| `save_policy` | “Save subtitles” (radio group) | `same_folder`, `fixed_folder`, `ask_every_time` | `same_folder` | Output folder selection |
| `save_folder` | Unlabeled path field under “Save subtitles” (paired with “Always save to this folder”) + “Browse...” button; placeholder: “No folder selected” | String path | unset | Output folder selection |
| `transcription_quality` | “Transcription quality” | `auto`, `fast`, `accurate`, `ultra` | `auto` | Transcription device/compute type |
| `punctuation_rescue_fallback_enabled` | “Improve punctuation automatically (recommended)” | `true` / `false` | `true` | Transcription (comma-rescue attempts) |
| `apply_audio_filter` | “Clean up audio before transcription” | `true` / `false` | `false` | Audio extraction filter chain |
| `keep_extracted_audio` | “Keep extracted WAV file” | `true` / `false` | `false` | Audio extraction output retention |
| `subtitle_edit_path` | “Choose Subtitle Edit…” (path picker) | String path | unset (falls back to default install path) | External tool integration |
| `diagnostics.enabled` | “Enable diagnostics logging” | `true` / `false` | `false` | Diagnostics output |
| `diagnostics.write_on_success` | “Write diagnostics on successful completion” | `true` / `false` | `false` | Diagnostics output |
| `diagnostics.categories` | Category checkboxes (see below) | Object of booleans | all `true` | Diagnostics output |

Diagnostics category keys (from `diagnostics.categories`), with UI labels:
- `app_system` → “App + system info”
- `video_info` → “Video info”
- `audio_info` → “Audio (WAV) info”
- `transcription_config` → “Transcription config”
- `srt_stats` → “SRT stats”
- `commands_timings` → “Commands + timings”

---

## 3.5) Handover essentials (operational addendum)

### Where to change what (cheat-sheet)
- Audio extraction output path & naming (`<video>_audio_for_whisper.wav`), FFmpeg args, audio filter toggle behavior → `app/workers.py`
- Burn-in (subtitles filter, style string, audio copy → AAC retry) → `app/workers.py` (plus `app/ffmpeg_utils.py` for escaping/discovery)
- Worker launching (python `-m app.transcribe_worker` vs exe), stdout token parsing, watchdog timeout → `app/workers.py`
- Worker internals: faster-whisper args, device/compute-type logic, punctuation stats JSON, punctuation rescue attempts + chooser gate → `app/transcribe_worker.py`
- SRT formatting primitives → `app/srt_utils.py`
- Cue splitting/word alignment fallback behavior → `app/srt_splitter.py`
- Progress weights/aggregation behavior → `app/progress.py`
- UI state machine, settings wiring/persistence (`config.json`), toggle behaviors, enabling/disabling buttons → `app/main.py`

### Working with Codex branches (project-critical workflow rule)
- If a branch is actively being worked on by Codex, **do not push additional local commits to that same branch** if you expect Codex to keep pushing hotfixes (risk of conflicts / Codex push failures).
- Preferred workflows:
  - **A)** Let Codex make all commits on that branch (including hotfixes).
  - **B)** If you already made local changes, either:
    - Tell Codex to incorporate those changes itself (so it owns the commit), **or**
    - Merge your local changes into `main` separately (new PR), keeping the Codex branch untouched.
- **Last resort:** if a local emergency fix must be pushed to the active Codex branch, expect Codex to rebase/resolve conflicts afterward.

### Progress model details (numbers)
Progress weights are defined in `app/progress.py` and the docs must reflect the code. If the weights ever change, update both the code and this section together.

Current weights:
- `PREPARE_AUDIO`: **15%**
- `TRANSCRIBE`: **60%**
- `EXPORT`: **25%**

The UI aggregates progress without regression (percent should not go backwards). Retry-style operations should **not** reset or jump backward; they should continue forward from the current aggregate progress.

### “Golden path” manual smoke test checklist (10–15 steps)
1) Launch the app from source (`python -m app.main`).
2) In Settings, set Save policy to **Same folder as the video**.
3) Ensure **Improve punctuation automatically (recommended)** is ON.
4) Ensure **Clean up audio before transcription** is OFF (baseline).
5) Select a short MP4 (e.g., `Desktop\clip.mp4`).
6) Click **Create subtitles**.
7) Confirm `<video_stem>_audio_for_whisper.wav` is created during processing.
8) Confirm `<video_stem>.srt` is created in the expected output folder.
9) Open the SRT in Subtitle Edit (via the UI or file association).
10) In the app, click **Export video with subtitles**.
11) Confirm `<video_stem>_subtitled.mp4` is created.
12) Play the exported MP4 and verify subtitles display and audio plays.
13) Toggle **Clean up audio before transcription** ON, re-run on the same clip, confirm it still completes.
14) Toggle **Improve punctuation automatically (recommended)** OFF, re-run on the same clip, confirm it still completes.
15) (Optional) Enable diagnostics and verify a `diag_generate_srt_*.json` appears next to outputs.

Success looks like: SRT created in the correct folder, no crashes, optional diagnostics generated when enabled, and the exported video plays with visible subtitles.

### Known issues / gotchas (short, living list)
- **Windows console Unicode:** printing Hebrew to cp1252 can crash; JSON printing is safest when redirected. Prefer `ensure_ascii=True` or safe-print helpers for stdout.
- **Benchmark outputs location:** write to `C:\subtitles_extra\outputs`, not inside the repo, to avoid churn and accidental commits.
- **Keep-extracted-WAV affects reproducibility:** the app may delete the extracted WAV unless “Keep extracted WAV file” is enabled.
- **Benchmark vs app differences:** device/compute-type and audio filter chain differences can change results; compare `TRANSCRIBE_CONFIG_JSON` / `TRANSCRIBE_STATS_JSON` / diagnostics to align runs.

---

## 4) Quick start (Windows, from source)

For the canonical developer setup, FFmpeg acquisition, testing, and packaging steps, see
`docs/CONTRIBUTING.md`.

---

## 5) App-generated WAV lifecycle (critical for benchmarking)

When creating subtitles, the app extracts audio to a WAV named:
- `<video_stem>_audio_for_whisper.wav`

**Audio format (current behavior):**
- 16 kHz, mono, PCM (`pcm_s16le`)

**Default location:**
- The WAV is created **next to the video** when Save policy is “Same folder as the video”.
- The WAV is created in the **resolved output folder** when Save policy is “Always save to this folder” or “Ask every time”.

**Retention vs deletion:**
- By default, the WAV is **deleted after transcription succeeds**.
- If transcription fails, the WAV is kept for debugging.
- To always retain it, enable **Settings → Audio → “Keep extracted WAV file”**.

---

### File lifecycle (where files are written and when they are deleted)
- `<video_stem>_audio_for_whisper.wav` is written in the output folder dictated by Save policy (often the same folder as the video).
- By default, the WAV is deleted after successful transcription; if **“Keep extracted WAV file”** is enabled, it is retained.
- Diagnostics JSON files are written next to the outputs when possible; if that fails, the app falls back to the app log directory.
- Benchmark outputs should be written outside the repo (e.g., `C:\subtitles_extra\outputs`).

---

## 6) Audio extraction filter chain (current behavior)

The app has an optional **audio cleaning filter chain** controlled by:
- **Settings → Audio → “Clean up audio before transcription”**

When enabled, FFmpeg applies the following chain:
- `highpass=f=80` → remove low rumble
- `lowpass=f=8000` → remove extreme highs
- `afftdn=nf=-25` → noise reduction
- `loudnorm=I=-16:TP=-1.5:LRA=11` → normalize loudness

Intent:
- Improve noisy recordings and speech clarity before Whisper.

Current default:
- **Disabled by default** (OFF), because it can reduce punctuation quality on some audio.

Configuration source:
- Stored in `%LOCALAPPDATA%\HebrewSubtitleGUI\config.json` as `apply_audio_filter`.

---

## 7) Punctuation rescue (current behavior, not the old description)

The existing Settings toggle is a **conditional comma-rescue**, not an always-retry behavior:
- **Settings → Punctuation → “Improve punctuation automatically (recommended)”**

What it does:
- Runs a **baseline transcription** first.
- **Only if a gate triggers** (low comma density on a sufficiently long transcript), it runs extra attempts and picks the best result.
- If the gate does **not** trigger, the baseline transcript is used as-is.

Trigger inputs (high level):
- `min_words` → minimum transcript length needed before rescue can trigger.
- `comma_density` threshold → if commas per word are already healthy, rescue is skipped.
- “Triggered” means the baseline transcript failed the comma-density gate and extra attempts were executed.

Diagnostics emitted by the worker:
- The transcription worker prints a structured line:  
  `TRANSCRIBE_STATS_JSON { ... }`
- Key fields (subset):
  - `punctuation_rescue_enabled` / `punctuation_rescue_triggered` / `punctuation_rescue_reason`
  - `punctuation_rescue_min_words`
  - `punctuation_rescue_min_comma_density`
  - `punctuation_rescue_baseline_comma_count_raw`
  - `punctuation_rescue_baseline_total_punctuation_count_raw`
  - `punctuation_rescue_attempts_ran`
  - `punctuation_rescue_attempts` (per-attempt summary list)
  - `punctuation_rescue_chosen_attempt`

Chooser gate (plain language):
- The rescue logic **will not choose an attempt that is worse than the baseline**.
- If no attempt is clearly better, the baseline is kept even if rescue ran.

---

### Punctuation rescue variability + diagnostics interpretation
Punctuation counts can vary across runs due to:
- device/compute-type differences (CPU int16 vs CUDA float16)
- VAD on/off differences
- model nondeterminism

Interpret key diagnostics in `TRANSCRIBE_STATS_JSON` like this:
- `punctuation_rescue_triggered` → whether extra attempts ran at all.
- `punctuation_rescue_reason` → why it triggered or why it was skipped.
- `punctuation_rescue_gate_passed` / `punctuation_rescue_gate_reason` → whether the chooser gate allowed a replacement and why.
- `punctuation_rescue_chosen_attempt` → which attempt index was selected.
- `punctuation_rescue_attempts` → per-attempt summaries (comma counts, totals, and metadata).

This is especially important when comparing CLI benchmark runs vs in-app runs.

---

## 8) Benchmarking (repeatable, and keep outputs out of the repo)

**Recommended output folder (local only):**
- Create `C:\subtitles_extra\outputs`
- Do **not** write benchmark outputs inside the repo.

**Use the app-created WAV for benchmarks:**
1) In the GUI, enable **Settings → Audio → “Keep extracted WAV file”**.
2) Run **Create subtitles** once.
3) Use the resulting `<video_stem>_audio_for_whisper.wav` for benchmarking.

**Example benchmark commands (Windows cmd):**
```bat
cd C:\subtitles_repo
.venv\Scripts\activate
python -u tools\punct_benchmark.py --wav "D:\videos\clip_audio_for_whisper.wav" > C:\subtitles_extra\outputs\bench_clip.txt 2>&1
```

**Unicode/console notes:**
- Console Unicode issues can occur; redirect stdout+stderr to a file as shown.
- Use `python -u` to reduce buffering in logs.
- If text looks garbled, open the output file in a UTF‑8 capable editor.

---

## 8.5) Benchmarking (correct method: app-generated WAV)

Benchmarks must use the **exact** `<video_stem>_audio_for_whisper.wav` produced by the app (not a manually-created WAV). The app’s audio extraction settings and optional filter chain can materially change punctuation results.

**Procedure (Windows cmd):**
- In Settings, enable **“Keep extracted WAV file”**.
- Run **Create subtitles** once for a test video.
- Locate the produced `*_audio_for_whisper.wav` in the output folder dictated by Save policy.
- Run the benchmark against that exact WAV and redirect output outside the repo:
  ```bat
  python -u tools\punct_benchmark.py --wav "D:\videos\clip_audio_for_whisper.wav" > C:\subtitles_extra\outputs\bench_clip.txt 2>&1
  ```

---

## 9) Troubleshooting & diagnostics cheat-sheet

**Logs (GUI runtime):**
- Location: `%LOCALAPPDATA%\HebrewSubtitleGUI\logs\`
- Open the most recent timestamped log to see FFmpeg commands, worker output, and errors.

**Diagnostics JSON (opt-in):**
- Location: next to the output SRT / video in the Save policy folder.
- Contains structured data about inputs, settings, commands, timings, and punctuation stats.

**Punctuation rescue issues:**
- Look for `TRANSCRIBE_STATS_JSON` in logs or benchmark output.
- Key fields: `punctuation_rescue_enabled`, `punctuation_rescue_triggered`, `punctuation_rescue_reason`,
  `punctuation_rescue_attempts_ran`, and `punctuation_rescue_chosen_attempt`.

**Audio extraction issues:**
- Check whether the filter chain was enabled (`apply_audio_filter` in `config.json`).
- Confirm the extracted WAV exists (use “Keep extracted WAV file” to retain it).
- Diagnostics category “Commands + timings” includes the FFmpeg audio extract command.

**Burn-in issues:**
- Inspect `diag_burn_in_*.json` in the output folder (if diagnostics enabled).
- Look for the FFmpeg burn-in command and timing metadata.

---

## 10) Roadmap (PR1–PR13) and current status

This repo started with a 13‑PR UX/architecture overhaul plan. The exact PR boundaries have shifted a bit (some items were combined or rescaled), but the sequence is still a good mental model.

### Status snapshot (as of 2026-01-12)

Done / merged:
- **PR1** — dark theme foundation ✅
- **PR2** — step-based state machine shell (stacked pages) ✅
- **PR3** — video selection UX (DropZone + thumbnail card + replace on drop) ✅
- **PR4 (rescoped)** — Settings page + save policy (Ask / Same folder / Always) ✅
- **PR5 (partial)** — copy polish + CTA reduction (still needs another pass later) 🟡
- **Plan decision:** PR5 stays partial; we will **not** try to finish it in-place while features are still moving.
- **PR6 (expanded)** — progress work ✅
  - burn-in/export (FFmpeg) progress: smooth and correct
  - transcription progress: improved, but can still move in coarse jumps depending on Whisper segmentation
- **Extra (not originally in the plan)** — opt-in success diagnostics JSON + “write next to outputs” hotfix ✅
- **PR14 — Docs refresh / handover readiness (this update)** ✅

Unplanned but merged work since the original PR plan:
- Punctuation benchmark/diagnostics tooling work
- Punctuation rescue behavior changes + chooser gate
- Audio extraction filter chain changes
- Windows Unicode stdout hardening affecting benchmark/worker output

**PR15 — copy polish + CTA reduction sweep (final pass)**
- One-primary-CTA-per-state audit
- Microcopy consistency audit
- Remove leftover technical terms in user-facing labels
- Align error/warning copy with UX/UI spec

Not done yet (still in PR7+ territory):
- **PR7** — Subtitles-ready page: auto-pick a subtitle moment and render a preview still frame (no dependence on extracted WAV staying on disk)
- **PR8** — style presets + customize panel + instant preview updates
- **PR9** — in-app preview playback (QtMultimedia) + caching
- **PR10** — karaoke-like highlighting (default ON)
- **PR11** — “delightful waiting” visuals (waveform + thumbnail strip; cached under LocalAppData)
- **PR12** — error UX with details drawer + copy diagnostics (complement the existing diagnostics JSON)
- **PR13** — packaging hardening / smoke tests
- **PR15** — copy polish + CTA reduction sweep (after stabilization)

### Where a new contributor should pick up
Priority work items:
1) If punctuation is acceptable: continue the UX roadmap at **PR7** (preview still frame).
2) If punctuation regresses: use the benchmark + diagnostics to confirm whether loss happens in raw segments vs splitter; the new rescue diagnostics fields help choose.

---

## 11) What changed since PR6 (summary)

### 11.1 Progress + status text improvements
Problem observed:
- During transcription, UI could sit at ~20% for a long time and then jump (e.g., to 28%), making it feel stuck.

Changes implemented:
- Progress is now **step-weighted** (audio extract → transcription → burn-in) into one global percent.
- Transcription emits “heartbeat” style signals so the UI can keep moving even when Whisper only reports progress in large segment jumps.
- Status text was clarified (e.g., “Listening to audio”).

Current reality:
- Burn-in progress is solid.
- Transcription progress is better than before, but still depends heavily on Whisper’s segmenting behavior.

### 11.2 Settings page (full-page, not a dialog)
Key UX decisions implemented:
- Settings replaces the content area (stacked page), not a modal.
- Save policy moved into Settings:
  - Ask every time
  - Same folder as the video
  - Always save to this folder (+ Browse...)
- The path row is always visible, but disabled unless “Always save to this folder” is selected.

Performance settings implemented:
- “Transcription quality” options map to device/compute-type selections.
- **Auto on CPU-only → int16** (per requirement).
- A **float32** option exists (slowest, potentially most accurate) for debugging/edge cases.
- Punctuation rescue is user-controllable in Settings and defaults to ON, but only triggers when comma density is low.

### 11.3 Diagnostics / logs (for debugging even when runs succeed)
Goal:
- When a user reports “it worked but results are bad,” we need structured logs (video/audio/srt/model/params) without asking for screenshots.

Behavior:
- Disabled by default.
- When enabled, a diagnostics JSON file is written next to outputs.
- Failure logs still exist by default even if success diagnostics are off.

### 11.4 Punctuation work (unplanned, now merged)
Why it was added:
- We needed repeatable punctuation counts on **raw Whisper segments vs final cues**, not just intuition.
- The rescue system needed to avoid making results worse while still salvaging bad punctuation runs.

What changed:
- Added **local benchmark tooling** (`tools/punct_benchmark.py`) to generate repeatable punctuation counts and compare raw segment output to final cues.
- Hardened **punctuation rescue** with a chooser gate + diagnostics so we can prove the rescue **won’t choose a worse transcript**.
- Adjusted **audio extraction default behavior** because it materially affected punctuation quality (extraction still happens in `app/workers.py`).

Current reality:
- We have a reliable way to measure punctuation density and compare raw vs final output.
- Rescue now protects against regressions instead of blindly swapping outputs.

---

## 12) Punctuation problem (current investigation)

### Status now
- Punctuation is **significantly improved** on WAVs extracted by the app with the current baseline configuration.
- Rescue often **does not trigger** because comma density is already OK.
- When punctuation regresses, debugging must use the **WAV produced by the app extraction path** (not a hand-made WAV), plus the benchmark tool and diagnostics JSON.

### 12.1 What we see
- Earlier SRT output sometimes had **no commas at all**, and generally far less punctuation than older “good” output.
- This was visible in side-by-side comparisons of SRT outputs and triggered the investigation.

### 12.2 Why “fixing commas in our splitter” is usually the wrong first move
The SRT splitter (`app/srt_splitter.py`) mostly preserves punctuation **if Whisper provides it**.
The splitter can only “lose” punctuation in one main situation:
- It fails to align `segment.words` back to `segment.text` and falls back to joining the word tokens (which often lack punctuation).

However, we verified cases where:
- **Whisper raw segment text already contains almost no punctuation**, so there is nothing for the splitter to preserve.

### 12.3 What we measured (key debugging results)
We used small debug scripts (run locally) to count punctuation in **raw Whisper segments** before any splitting.

Earlier measurements (pre audio-extraction default change) on a 30s Hebrew WAV (representative):
- `large-v3`, `int16`, VAD **on**, word timestamps **on** → **0 commas / 0 periods**
- `large-v3`, `int16`, VAD **off** → sometimes **1 comma**
- `large-v3`, `int8`, VAD **on** → sometimes **1 comma**
- `large-v2`, `int16`, VAD **on** → **multiple periods** (punctuation output is noticeably better)

Current measurements (post change):
- Commas and periods are present at **healthy density** on app-extracted WAVs with the current baseline configuration.

Conclusion (current best hypothesis):
- The missing punctuation was **primarily a model/decoding + extraction-path interaction**, not an SRT formatting bug.

### 12.4 Things that were tried
- Tweaking `srt_splitter` reconstruction/alignment logic:
  - Helps only when punctuation exists in `segment.text`.
  - Does not create commas if Whisper didn’t output them.
- Adding a Hebrew `initial_prompt` asking Whisper to add punctuation:
  - Did not reliably restore commas.

### 12.5 Constraints / non-negotiables
- Do **not** increase “words per timestamp” (cue length) just to add punctuation.
- Keep timing behavior stable:
  - punctuation restoration should ideally modify text only, not timestamps.

### 12.6 Recommended next steps (current priority)
Punctuation is no longer the active blocker. Move priority back to PR7+.

If punctuation regresses, re-open investigation like this:
1) **Confirm the loss location** (raw segments vs splitter output)
   - Use the **benchmark tool** plus **diagnostics JSON** to compare raw `segment.text` counts vs final cues.
   - Ensure the WAV is the one produced by the app extraction path.
2) **Use rescue diagnostics fields to confirm chooser behavior**
   - Verify rescue only switches when the alternate transcript is clearly better.
3) **Only then consider model/decoder experiments**
   - Keep experiments behind the punctuation toggle so defaults remain stable.

---

## 13) Performance notes (why 3m audio can take ~20 minutes)

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

## 14) Debugging checklist (what to collect)

When reporting issues, attach:
1) The **diagnostics JSON** (if enabled)
2) The produced `.srt`
3) The exact Settings used (or let diagnostics capture it)

If diagnostics are not enabled, capture:
- the GUI runtime log file from `%LOCALAPPDATA%\HebrewSubtitleGUI\logs\`
- the `TRANSCRIBE_CONFIG_JSON` line (if present)

---

## 15) Important implementation gotchas

- **Console windows:** subprocess launches must use Windows flags to avoid flashing consoles.
- **PyInstaller + native deps:** ctranslate2/tokenizers/Qt multimedia plugins can fail only in EXE.
- **Path handling:** support OneDrive paths and spaces; always quote paths when calling tools.
- **FFmpeg progress parsing:** keep it resilient (stderr format differences).
