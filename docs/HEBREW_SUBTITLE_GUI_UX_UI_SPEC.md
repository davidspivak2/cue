# Hebrew Subtitle GUI — UX/UI Specification (Design Contract)

**Last updated:** 2026-03-10  
**Scope:** This document is the **single source of truth** for the full redesign: visual system, navigation model, project model, screen specs, state machine, and pipeline contract.

This is a **strict design contract**. Implementation must follow it exactly. If implementation diverges, update this spec with rationale **before** or **as part of** the change.

For project status and upcoming tasks, see `ROADMAP.md`.

---

## A) Visual design system (Linear-style, dark only)

### A1) Visual principles
- **Theme:** Dark only (no light theme).
- **Typography:** Inter (bundled with the app).
- **Density:** Comfortable.
- **Radius:** 10px default.
- **Icons:** Lucide outline only.
- **Window chrome:** Native OS window frame (no custom title bar).
- **Motion:** Subtle only (e.g., 150ms drawer open/close). Avoid heavy or bouncy animations.
- **Surfaces:** **Option B**
  - Flat UI with 1px hairline borders as the primary separation.
  - Subtle elevation/shadow **only** for overlays (modals, drawers, popovers).
  - Avoid Windows-native card aesthetics; target clean, cross-platform product UI.

### A2) Design tokens (explicit)
**Color tokens (dark theme):**
- `color.bg`: `#0F1115`
- `color.surface`: `#151922`
- `color.surface-elevated`: `#1C2230`
- `color.border`: `#2A2F3A`
- `color.text.primary`: `#E6EAF2`
- `color.text.secondary`: `#B7BFCC`
- `color.text.muted`: `#8892A6`
- `color.accent`: `#7A5CFF` **(single app accent; use consistently)**
- `color.danger`: `#FF5D5D`
- `color.success`: `#3DDC84`

**Typography scale (Inter):**
- `type.h1`: 22px / 28px, semibold
- `type.h2`: 18px / 24px, semibold
- `type.section`: 13px / 18px, medium
- `type.body`: 14px / 20px, regular
- `type.caption`: 12px / 16px, regular

**Spacing scale:**
- `space.1`: 4px
- `space.2`: 8px
- `space.3`: 12px
- `space.4`: 16px
- `space.5`: 24px
- `space.6`: 32px
- `space.7`: 40px

**Radius tokens:**
- `radius.sm`: 6px
- `radius.md`: **10px** (default)

**Border thickness tokens:**
- `border.hairline`: 1px
- `border.focus`: 2px

**Interaction states (accessibility required):**
- **Hover:** background or border increases contrast by one step (e.g., surface → surface-elevated or border → slightly brighter).
- **Pressed:** reduce brightness by one step; maintain legibility.
- **Focus:** visible 2px accent focus ring (`border.focus`) with a 1px offset from control bounds.
- **Disabled:** 40% opacity and no hover/pressed state.

---

## B) Top-level navigation model (Premiere Rush-like)

### B1) Pages (top-level)
1) **Project Hub** (new, built from scratch)
2) **Workbench** (per project, in tabs)
3) **Settings** (existing page, restyled)

### B2) Global navigation rules
- App launch **always** shows **Project Hub** (never auto-opens the last project).
- Multiple projects can be open **simultaneously as tabs** within the same app window (no multiple windows).
- **Settings** is reachable from **Project Hub** and **Workbench** via a gear icon.
- **Settings navigation is disabled** while long-running tasks are active (Create Subtitles / Export).
- **Project tabs during long-running tasks (v1):**
  - Users **may switch** to other project tabs while any project is running Create Subtitles or Export.
  - All **other** project tabs are **read-only** during that time (no create/export/edit actions). Tabs are viewable with actions disabled and a clear “Busy” reason.
  - **Future (out of scope for v1):** allow concurrent Create Subtitles / Export across multiple projects simultaneously.

### B3) Back navigation rules
- **Settings:** top-left “Back” returns to the previous page (Project Hub or Workbench).
- **Workbench:** top-left “Back” returns to Project Hub (not in the bottom bar).

---

## C) Project model (new backend capability; document behavior)

### C1) Storage and persistence
- **Autosave is always on.**
- Projects are stored in an **app-managed projects folder** (describe conceptually; do **not** hardcode absolute paths).
- Closing a project tab **does not delete** the project.

### C2) Required project data (minimum persisted set)
Each project persists:
- Source video reference (and relink metadata)
- Generated subtitles text (SRT or internal representation)
- Style configuration (all supported controls, for Static + Word highlight)
- Word highlight timing artifacts (WhisperX output)
- Export output reference (latest exported video path, if any)
- Last-known status (e.g., Needs video, Ready, Exporting, Exported)

### C3) Missing source video behavior
- If the source video is missing, the project **remains** in Project Hub.
- The card shows a **“Relink”** action.
- Relinking restores the project without data loss.

---

## D) Project Hub (new screen)

### D1) Layout
- **Grid of thumbnail cards** (video thumbnails).
- **Primary CTA:** “New project” (choose video) plus **drag-and-drop** on the entire hub surface.

### D2) Project card content
Each card shows:
- Thumbnail
- Filename (no full path)
- Duration
- Status label: **Ready / Exporting / Done / Missing file / Needs subtitles**

### D3) Card interactions
- Clicking a card **opens or activates** that project in a **Workbench tab**.
- Missing source video:
  - Card shows **“Relink”** action.
  - After relink, project remains intact and usable.

---

## E) Workbench (new unified screen)

The Workbench is a **single unified** edit + style + preview + export surface for a project.

### E1) Workbench layout regions
- **Center:** Video player with playback controls. Styled subtitles render **on the video** (preview is the truth).
- **Right:** Style inspector.
- **Left:** “All subtitles” panel (collapsible, resizable when docked).

### E2) Left “All subtitles” panel behavior
- Default on first entry: **collapsed**.
- Expanded at wide window widths:
  - Docked panel that **pushes layout** (does not overlay).
  - Default width **360px**, min **280px**, max **480px**.
  - User-resizable via drag handle.
  - Persist **per-project**: open/closed state + width.
- Responsive rule (mandatory):
  - If window width **< 1100px**, expanding the left panel becomes an **overlay drawer** with a dim scrim.
  - **Esc** or scrim click closes.
- Overlay coordination rule:
  - **Only one overlay drawer may be open at a time.** Opening the left drawer closes the right drawer (and vice versa).

### E3) Right Style inspector behavior
- **Wide window:** docked fixed-width inspector; vertically scrollable; **no horizontal scroll**.
- **Narrow window:** inspector collapses and opens as an **overlay drawer** via a “Style” button.
- Styling capabilities remain conceptually the same, but controls are reorganized into **clean sections** with consistent spacing and hierarchy (Linear-style).
- Preview reflects style changes **immediately**.

### E4) Subtitle editing requirements (explicit)
Users can **edit subtitle text only**. Timestamps are visible but **not editable**.
The redesign workflow is **in-app subtitle text editing only** (no external subtitle editor).

**Entry points:**
1) **All subtitles list**
   - Each row shows timestamps (read-only) + editable subtitle text.
   - Clicking a row seeks the video to that timestamp and selects the subtitle.
2) **On-video editing**
   - When video is **playing**: clicking the currently displayed subtitle **pauses** playback and **selects** it (no edit box yet).
   - When **paused** and selected: clicking again enters **inline edit mode** anchored to the subtitle position.
   - **Enter** saves, **Esc** cancels.

**Selection highlight contract (never exported):**
- Selected subtitle overlay shows a **thin accent outline** for UI selection only.
- Selected row in the list is also visually selected.
- This highlight **must never** affect export styling.

### E5) Primary CTA and export rules
- **Bottom action bar exists on Workbench** only in **WB_SUBTITLES_READY** and **WB_EXPORT_SUCCESS**.
- Bottom bar contains **only** the primary CTA labeled exactly:
  - **“Create video with subtitles”**
- In earlier states (e.g., **WB_VIDEO_LINKED_READY**), the primary CTA is a **normal primary button** in the main content area labeled **“Create subtitles”** (no bottom bar).
- **No export settings** in Workbench. If export settings exist, they live in **Settings only**.
- Export progress is shown as an **in-Workbench** state (not a separate page).

---

## F) Create Subtitles pipeline contract (WhisperX required)

Word highlight mode must be available **immediately** after Create Subtitles. Therefore, WhisperX alignment is **required** during Create Subtitles.

### F1) Create Subtitles completion criteria
Create Subtitles is **not complete** until **both** succeed:
- Base subtitles generated (SRT or internal text).
- Word highlight timing artifacts generated via WhisperX alignment (non-empty timed words).

### F2) Progress checklist requirement
Progress checklist **must include** a step named exactly:
- **“Timing word highlighting (WhisperX)”**

### F3) SUBTITLES_READY transition rule
- Transition to **SUBTITLES_READY** only **after** WhisperX timing succeeds.
- **Failure contract (chosen behavior):**
  - **Option 1 (strict):** Treat WhisperX failure or 0 timed words as a **blocking failure**.
  - Show a blocking error; **do not** mark subtitles ready.
  - Preserve the project for **retry**.

### F4) Required Create Subtitles artifacts (per project)
Create Subtitles must output:
- Base subtitle artifact (SRT or internal saved representation).
- WhisperX word timing artifact:
  - Canonical filename: `<video_basename>.word_timings.json`
  - Schema: **v1**
  - Must contain **non-empty** timed words on success.
- Any derived files required for preview/export (e.g., ASS templates, karaoke mapping) must also be produced during Create Subtitles and documented per project.

### F5) Export pipeline rule
- Export **must not** run WhisperX in the normal success path.
- Export uses the **already-generated artifacts** to burn subtitles (Static or Word highlight) and saves the MP4.
- **Export precondition (Word highlight):** if Word highlight mode is selected and required word-timing artifacts are missing or stale, export **must block** and instruct the user to rerun **Create Subtitles** (or a clearly labeled retry action if exposed). Do not fall back to running WhisperX during export.

---

## G) Export progress + success (in-Workbench)

### G1) During export
- Show progress UI **within Workbench**:
  - Checklist + determinate progress bar + elapsed time + **Cancel**.
- **Disable editing/styling** while exporting.

### G2) On success (no separate Done screen)
- Stay in Workbench and show an **in-place success state** with actions:
  - **Play video**
  - **Open folder**
- User can continue editing/styling and export again.

---

## H) Error UX + Diagnostics

### H1) Error presentation rules
- **Recoverable errors:** inline banner.
- **Blocking errors:** modal dialog.
- “Show details” is allowed inside error UI, but **Diagnostics tools live in Settings only**.

### H2) Diagnostics entry point
- Diagnostics entry point is **Settings only**.
- If any error-only diagnostics buttons are referenced elsewhere, they must be removed or redirected to Settings.

---

## I) State machine (explicit, implementation-friendly)

### I1) Project Hub states

| State | Description | Primary CTA (exact label) | Navigation enabled | Panel rules | Notes |
| --- | --- | --- | --- | --- | --- |
| HUB_EMPTY | No projects exist | **“New project”** | Settings enabled (unless task running) | No Workbench panels | Hub surface accepts drag & drop. |
| HUB_HAS_PROJECTS | One or more projects exist | **“New project”** | Settings enabled (unless task running) | No Workbench panels | Cards open/activate Workbench tabs. |
| HUB_PROJECT_MISSING_FILE | Project exists but source video missing | **“Relink”** (card action) | Settings enabled (unless task running) | No Workbench panels | Project stays in hub until relinked. |

### I2) Workbench per-project states

**Overlay rules (apply to all Workbench states):**
- If window width **< 1100px**, docked panels become overlay drawers.
- Only **one overlay drawer** may be open at a time.

| State | Description | Primary CTA (exact label) | Navigation enabled | Panel behavior | Notes |
| --- | --- | --- | --- | --- | --- |
| WB_NEEDS_VIDEO | Project exists but no linked video | **“Choose video…”** | Settings enabled (unless task running) | Panels closed/disabled | Workbench accessible via tab, but requires relink. |
| WB_VIDEO_LINKED_READY | Video linked, ready to create subtitles | **“Create subtitles”** | Settings enabled (unless task running) | Left panel collapsed by default; right inspector available | Center preview shows video player. |
| WB_CREATING_SUBTITLES | Running Create Subtitles (includes WhisperX step) | **Cancel** (progress UI) | Settings **disabled** | Panels closed; editing disabled | Checklist includes “Timing word highlighting (WhisperX)”. |
| WB_SUBTITLES_READY | Subtitles + word timings available | **“Create video with subtitles”** | Settings enabled | Left panel user-controlled; right inspector docked/overlay per width | Subtitle text editable; timestamps read-only. |
| WB_EXPORTING | Export in progress | **Cancel** (progress UI) | Settings **disabled** | Panels closed; editing disabled | Export uses existing artifacts only. |
| WB_EXPORT_SUCCESS | Export completed | **“Create video with subtitles”** | Settings enabled | Panels user-controlled | Show success UI with “Play video” + “Open folder”. |
| WB_ERROR_RECOVERABLE | Recoverable error occurred | **Retry** (contextual) | Settings enabled (unless task running) | Panels user-controlled | Inline banner. |
| WB_ERROR_BLOCKING | Blocking error occurred | **Try again** (modal) | Settings enabled (unless task running) | Panels closed while modal active | Modal can show “Show details”. |

**Primary CTA label requirement:** The Workbench bottom bar **always** uses exactly **“Create video with subtitles”** when subtitles are ready or after successful export.

---

## J) Settings page (restyled; behavior preserved)

Settings is a **full page** that replaces the current view. It uses the new design system but retains the existing controls and behaviors, with updated layout consistency only.

### J0) Legacy removal requirement (Subtitle Edit)
- Subtitle Edit integration must be **removed entirely** from the application code (UI + settings + config + launcher code).
- Remove the persisted config key **`subtitle_edit_path`** and any related logic.

### J1) Performance
- “Transcription quality” combo: Auto / Fast (int8) / Accurate (int16) / Ultra accurate (float32)
- Helper text always visible.
- Run summary line always visible.

### J2) Save subtitles
- Radio group: Same folder / Always save to this folder / Ask every time
- Path row: single-line field + “Browse...”
- Path field + Browse enabled only when policy = “Always save to this folder”.
- Placeholder when unset: “No folder selected”.

### J3) Punctuation
- Checkbox: “Improve punctuation automatically (recommended)”
- Behavior and rescue logic remain the same as current requirements.

### J4) Audio
- Checkbox: “Clean up audio before transcription”
- Checkbox: “Keep extracted WAV file”
- Helper text always visible.

### J5) Diagnostics (Settings only)
- Master checkbox: “Enable diagnostics logging” (default OFF)
- Secondary checkbox: “Write diagnostics on successful completion” (default OFF)
- Include checkboxes for diagnostics categories.
- Diagnostics JSON written next to SRT/output.

---

## K) Copywriting glossary (approved strings)

- “Project Hub”
- “New project”
- “Workbench”
- “Settings”
- “Back”
- “Choose video…”
- “Create subtitles”
- “Creating subtitles”
- “Timing word highlighting (WhisperX)”
- “Subtitles ready ✓”
- “Create video with subtitles”
- “Exporting video”
- “Play video”
- “Open folder”
- “Relink”
- “Try again”
- “Show details”

**Avoid:**
- “Input”, “Output”, “SRT” in button text
- “Encode”, “Burn-in”, “Hardcode”

## Appendix: Archived — Project context (original)
# Hebrew Subtitle GUI — Project Context (Read This First)

**Last updated:** 2026-03-10

This document is for:
- new contributors
- new chat sessions
- future-you, when something breaks and you need the “why” and the “where” quickly

It explains:
- what the app does
- how the pipeline works (GUI → FFmpeg → faster-whisper → SRT → FFmpeg burn-in)
- where files go (models, logs, outputs)
- the GUI PR1–PR13 roadmap **and current status**
- what has been worked on since GUI PR6 (progress + settings + diagnostics)
- the current punctuation problem (what we measured, what we tried, what to do next)

UX/UI target spec (design contract): **`/docs/HEBREW_SUBTITLE_GUI_UX_UI_SPEC.md`**.

## Current behavior vs target redesign

**Current (main today):**
- Single-flow UI without a Project Hub.
- Subtitle editing is limited; no in-app text-only editing for every subtitle.
- Word-timing alignment may not be guaranteed during Create Subtitles.

**Target (per UX spec):**
- Project Hub launch screen with multi-project tabs in a single window.
- In-app subtitle **text-only** editing in the Workbench; timestamps visible but **read-only**.
- Create Subtitles **always** includes WhisperX alignment; SUBTITLES_READY requires non-empty timed words.

## Roadmap / What’s next

For all upcoming tasks, see [`ROADMAP.md`](ROADMAP.md) (single source of truth).

---

## 0) One-page overview (for new maintainers)

**What this app is:** a Windows desktop GUI built with **PySide6** that generates Hebrew subtitles and (optionally) burns them into a new MP4.

**Core workflow:**
1) Create or open a project from **Project Hub**
2) Create subtitles (extract audio → transcribe → WhisperX alignment)
3) Edit text + style in **Workbench**
4) Export a subtitled MP4 (FFmpeg)

**Primary outputs (exact naming):**
- `<video_stem>_audio_for_whisper.wav`
- `<video_stem>.srt`
- `<video_stem>.word_timings.json` (word timing output; see §3.6)
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
1) Create a new project from Project Hub (or open an existing one).
2) App extracts a mono 16 kHz WAV using FFmpeg (optional cleanup filter).
3) App runs faster‑whisper (Whisper) to transcribe Hebrew and write an `.srt`.
4) App runs WhisperX alignment to generate word timings for Word highlight mode.
5) User edits subtitle text in the Workbench (timestamps are visible but read-only).
6) App burns subtitles into a new MP4 using FFmpeg.

---

## 2) How it works (technical overview)

### Main moving parts
- **GUI (PySide6)**: `app/main.py`
  - state machine / stacked pages (Project Hub + Workbench + Settings)
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
- `app/srt_splitter.py` — cue splitting and word alignment recovery
- `app/progress.py` — progress aggregation and weights
- `app/subtitle_style.py` — subtitle style presets + style normalization helpers
- `app/graphics_preview_renderer.py` — graphics-based preview rendering for still frames
- `app/align_worker.py` — WhisperX alignment worker for word timings
- `app/align_utils.py` — alignment planning + staleness checks
- `tools/*` — local benchmark tools
- `docs/*` — handover + UX spec

---

## 3) Where data goes

### App data root (Windows)
`%LOCALAPPDATA%\HebrewSubtitleGUI\`

Common subfolders:
- `models\` — faster‑whisper model cache
- `logs\` — GUI runtime logs (timestamped)
- `cache\` — thumbnails, preview frames
  - `cache\preview_frames` — cached subtitle preview still frames
- `config.json` — user settings

### Per-video outputs (folder chosen by Save policy)
Save policy determines the output folder:
- **Same folder as the video** → outputs live next to the video file.
- **Always save to this folder** → outputs live in the fixed folder set in Settings.
- **Ask every time** → the user chooses the output folder each run.

Outputs include:
- `<video_stem>_audio_for_whisper.wav` (scratch audio)
- `<video_stem>.srt` (subtitles)
- `<video_stem>.word_timings.json` (word timing output; see §3.6)
- `<video_stem>_subtitled.mp4` (burned output)

### Diagnostics JSON (opt-in, **on success**)
If diagnostics logging is enabled and “Write diagnostics on successful completion” is ON, diagnostics JSON is written **next to the created output** (hotfixed from the old LocalAppData location):
- `diag_generate_srt_YYYYMMDD_HHMMSS_micro.json`
- `diag_burn_in_YYYYMMDD_HHMMSS_micro.json`

On failure, the app still writes/keeps error logs even if success diagnostics are disabled.

### Exit diagnostics bundle (optional)
If **“Zip logs and outputs on exit”** is enabled, the app creates a ZIP file in the same
folder as the selected video on exit. The bundle includes:
- The current session log file.
- Diagnostics JSON files in the output folder (if any).
- Output artifacts (SRT, word timings JSON, output video, extracted WAV if present).

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
| `diagnostics.enabled` | “Enable diagnostics logging” | `true` / `false` | `false` | Diagnostics output |
| `diagnostics.write_on_success` | “Write diagnostics on successful completion” | `true` / `false` | `false` | Diagnostics output |
| `diagnostics.archive_on_exit` | “Zip logs and outputs on exit” | `true` / `false` | `false` | Diagnostics bundle |
| `diagnostics.categories` | Category checkboxes (see below) | Object of booleans | all `true` | Diagnostics output |
| `subtitle_style.preset` | Subtitle style preset dropdown | `Default`, `Large outline`, `Large outline + box`, `Custom` | `Default` | Preview + export styling |
| `subtitle_style.custom` | “Customize...” panel controls | Object: `font_family`, `font_size`, `text_color`, `outline`, `shadow`, `margin_v`, `box_enabled`, `box_opacity`, `box_padding` | Defaults per preset | Preview + export styling |
| `subtitle_style.appearance` | (style model, internal) | Object with font, color, outline, shadow, background, and layout fields | Derived from preset/custom | Preview + export styling |
| `subtitle_mode` | “Subtitle mode” | `word_highlight`, `static` | `word_highlight` | Selects word-highlight vs static rendering; export uses graphics overlay only |
| `subtitle_style.highlight_color` | “Highlight color” | Hex color string | `#FFD400` | Word highlight styling (graphics overlay only) |
| `subtitle_style.highlight_opacity` | “Highlight opacity” (slider in Subtitles Ready style pane) | 0.0–1.0 float | `1.0` | Word highlight styling (graphics overlay only) |

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
- Burn-in (graphics overlay stream, audio copy → AAC retry) → `app/workers.py`
- Worker launching (python `-m app.transcribe_worker` vs exe), stdout token parsing, watchdog timeout → `app/workers.py`
- Worker internals: faster-whisper args, device/compute-type logic, punctuation stats JSON, punctuation rescue attempts + chooser gate → `app/transcribe_worker.py`
- SRT formatting primitives → `app/srt_utils.py`
- Cue splitting/word alignment fallback behavior → `app/srt_splitter.py`
- Progress weights/aggregation behavior → `app/progress.py`
- UI state machine, settings wiring/persistence (`config.json`), toggle behaviors, enabling/disabling buttons → `app/main.py`

---

## 3.6) Word-timing JSON artifact (Task 7)

The app creates a **word-timing JSON** artifact next to each SRT during **Create Subtitles**:

- **Naming convention:** `<video_stem>.word_timings.json` (same folder as the SRT).
- **Schema:** validated JSON with `schema_version=1`, SRT hash, and cue metadata.
- **Staleness rule:** if the SRT file changes, the word-timing JSON is **stale** when its
  stored `srt_sha256` no longer matches the current SRT hash.
- **Lifecycle (target contract):** WhisperX alignment runs **during Create Subtitles** and
  must produce **non-empty timed words** for success. SUBTITLES_READY is allowed only after
  this succeeds.
- **Export rule:** Export uses the existing artifacts and **does not** run WhisperX in the
  normal success path.

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

### Current progress UI behavior
- Punctuation step label is **“Reviewing punctuation”**.
- If punctuation rescue is enabled but not needed, the step completes with inline detail “Looks good!”, and the detail remains visible after completion.
- Skip semantics for punctuation rescue:
  - Clicking Skip immediately shows “Skipping...” and disables/hides the Skip control.
  - The step becomes Skipped only after backend confirmation (not immediately on click).
  - The pipeline continues to the next step without waiting for punctuation rescue to finish.
- Export progress: stages cover video info, subtitle rendering/burn-in, and saving output (no WhisperX timing stage during export in the redesign contract).

### “Golden path” manual smoke test checklist (10–15 steps)
1) Launch the app from source (`python -m app.main`).
2) In Settings, set Save policy to **Same folder as the video**.
3) Ensure **Improve punctuation automatically (recommended)** is ON.
4) Ensure **Clean up audio before transcription** is OFF (baseline).
5) Select a short MP4 (e.g., `Desktop\clip.mp4`).
6) Click **Create subtitles**.
7) Confirm `<video_stem>_audio_for_whisper.wav` is created during processing.
8) Confirm `<video_stem>.srt` is created in the expected output folder.
9) In the app, click **Create video with subtitles** (in the sticky bottom bar).
10) Confirm `<video_stem>_subtitled.mp4` is created.
11) Play the exported MP4 and verify subtitles display and audio plays.
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

## 10) Roadmap (GUI PR1–PR13) and current status

This repo started with a 13‑PR UX/architecture overhaul plan. The exact PR boundaries have shifted a bit (some items were combined or rescaled), but the sequence is still a good mental model.

### Status snapshot (as of 2026-02-27)

Done / merged:
- **GUI PR1** — dark theme foundation ✅
- **GUI PR2** — step-based state machine shell (stacked pages) ✅
- **GUI PR3** — video selection UX (DropZone + thumbnail card + replace on drop) ✅
- **GUI PR4 (rescoped)** — Settings page + save policy (Ask / Same folder / Always) ✅
- **GUI PR5 (partial)** — copy polish + CTA reduction (still needs another pass later) 🟡
- **Plan decision:** GUI PR5 stays partial; we will **not** try to finish it in-place while features are still moving.
- **GUI PR6 (expanded)** — progress work ✅
  - burn-in/export (FFmpeg) progress: smooth and correct
  - transcription progress: improved, but can still move in coarse jumps depending on Whisper segmentation
- **GUI PR7** — Subtitles-ready page: auto-pick a subtitle moment and render a preview still frame ✅
- **GUI PR8** — style presets + customize panel + instant preview updates ✅
- **GUI PR9** — in-app preview playback (QtMultimedia) + caching ✅ (feature no longer surfaced in the GUI)
- **GUI PR10** — word highlight default mode + highlight color picker ✅
- **GUI PR11** — delightful waiting checklist ✅ (adds a three-step checklist UI above the progress bar that updates across C1/C2/E states)
- **Extra (not originally in the plan)** — opt-in success diagnostics JSON + “write next to outputs” hotfix ✅
- **GUI PR14 — Docs refresh / handover readiness (this update)** ✅

Unplanned but merged work since the original PR plan:
- Punctuation benchmark/diagnostics tooling work
- Punctuation rescue behavior changes + chooser gate
- Audio extraction filter chain changes
- Windows Unicode stdout hardening affecting benchmark/worker output
- Unified subtitle style model + regrouped style UI
- Graphics-based preview renderer for subtitle stills
- Exit diagnostics bundle (zip logs + outputs on close)

GUI PR10 tracking doc: see the ROADMAP appendix for the Word highlight plan (PR10).

For upcoming work, see [`ROADMAP.md`](ROADMAP.md).

---

## 11) What changed since GUI PR6 (summary)

### 11.1 Progress + status text improvements
Problem observed:
- During transcription, UI could sit at ~20% for a long time and then jump (e.g., to 28%), making it feel stuck.

Changes implemented:
- Progress is now **step-weighted** (audio extract → transcription → burn-in) into one global percent.
- Transcription emits “heartbeat” style signals so the UI can keep moving even when Whisper only reports progress in large segment jumps.
- Status text was clarified (e.g., “Listening to audio”).
- A waiting checklist sits above the progress bar in C1/C2/E states to make the extract → transcribe → burn-in sequence visible.

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

### 11.5 Subtitle styling + preview renderer updates
Recent updates include:
- A unified subtitle style model (font, outline, shadow, background, alignment) now backs the style UI.
- The Subtitles Ready screen is reorganized into a two-column layout with a dedicated style panel and a single CTA for export.
- Preview stills now use a graphics-based renderer that draws subtitle styling directly onto the raw video frame, rather than relying on FFmpeg’s subtitle filters.
- Preview cache keys now include word-timing metadata and highlight settings so word-highlight previews refresh when alignment data changes.
- Changing the highlight color forces an immediate preview refresh.
- Word-highlight clipping and clip-rect alignment were tightened for the graphics preview renderer.
- Outline/shadow alignment was corrected for wrapped text and glyph-run paths in graphics rendering.
- Wrapped-line word highlight fixes now make highlight clip rects line-relative so multi-line cues highlight correctly.
- Graphics overlay export is the only rendering path; FFmpeg subtitle filters are not used.
- Diagnostics can optionally zip logs + outputs on exit for easier support handoffs.

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

### 12.6 Recommended investigation steps if punctuation regresses (reference only)
This is troubleshooting guidance, not a roadmap.

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
