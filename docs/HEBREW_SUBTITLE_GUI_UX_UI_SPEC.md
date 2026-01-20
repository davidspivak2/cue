# Hebrew Subtitle GUI — UX/UI Specification (Design Contract)

**Last updated:** 2026-03-10  
**Scope:** This document describes the intended **pixel-level UI behavior** for Hebrew Subtitle GUI, and the interaction rules the app should follow as it continues the PR1–PR13 overhaul.

This is intentionally opinionated. If an implementation choice conflicts with this spec, update the spec (with rationale) or change the implementation.

> For current project status, roadmap progress, and known issues (including the Hebrew punctuation problem), see `/docs/HEBREW_SUBTITLE_GUI_CONTEXT.md`.

---

## A) Core principles

1) **One obvious next step**
- At any point, show **one** primary CTA.
- Avoid presenting more than two prominent buttons.

2) **Progressive disclosure**
- Only show controls when they are relevant:
  - No export styling when subtitles don’t exist.
  - No save location details when “Ask every time” is selected.

3) **Media-first confirmation**
- Users confirm file selection by recognizing the video thumbnail.
- File paths are secondary and should be visually de-emphasized.

4) **Non-technical copy**
- Buttons should not say “SRT”, “encode”, “burn”, “hardcode”.
- Use:
  - “Choose video…”
  - “Create subtitles”
  - “Open subtitles”
  - “Create final video”

5) **Delightful waiting / never feel stuck**
- Even when progress is slow or coarse (e.g., long Whisper segments), the UI should communicate:
  - “the app is alive” (heartbeat/animation)
  - “it is making progress” (at least occasional % movement)

6) **Works on fast and slow machines**
- The UX must feel acceptable on:
  - CPU-only laptops
  - GPU gaming PCs
- Heavy visuals must be throttled and optional.

7) **Diagnostics are secondary**
- Diagnostics exist for debugging but are hidden by default.
- Success diagnostics are opt-in; failure logs still exist by default.

---

## B) Top-level navigation model

The UI is a **single window** with a content stack.

### Pages
- **Home page**: the main flow (select → create → review → export)
- **Settings page**: full-page settings (no dialogs)

### Header
Home page header (top row):
- Left: app title (or nothing; optional)
- Right: Settings icon button (32×32)
  - Tooltip: “Settings”
  - Disabled while a task is running

Settings page header:
- Left: “← Back” button
  - 80×32, flat/link style
- Center-left: title “Settings”
- Right: nothing

Transitions:
- Switching between Home and Settings is instant (no modal overlay).
- While any worker task runs (extract/transcribe/export), Settings is disabled.

---

## C) Layout and styling rules

### Window
- Default size: ~900×700 (resizable)
- Outer padding: 16px
- Vertical spacing between blocks: 12px
- Inner spacing inside cards: 8px

### Surfaces
- Prefer cards with subtle borders/shadows over group boxes.
- Card corner radius: 10–12px

### Typography
- Page title: 18–20px, semibold
- Section title: 12–13px, medium
- Body: 13–14px, regular
- Muted secondary text: only when necessary

### Buttons
- Primary: filled accent
- Secondary: tonal/outline
- Tertiary: link-style

---

## D) State machine (home page)

### Home page states
- **A: EMPTY** — no video selected
- **B: VIDEO_SELECTED** — video selected, ready to create subtitles
- **C1: WORKING_EXTRACT** — extracting/cleaning audio
- **C2: WORKING_TRANSCRIBE** — transcribing subtitles
- **D: SUBTITLES_READY** — subtitles exist, ready to review/export
- **E: WORKING_EXPORT** — exporting subtitled video
- **F: DONE** — export complete
- **X: ERROR** — recoverable error UI

---

## E) Detailed state specs

### State A — EMPTY

**Goal:** Make it obvious what to do; highlight drag & drop.

UI:
- Centered **Drop Zone Card**
  - Dashed rounded border
  - Icon (video)
  - Headline: “Drop a video here”
  - Subtext: “or choose one from your computer”
  - Primary button: “Choose video…”

Interaction:
- Drag-over: highlight border/background; change text to “Drop to add video”.
- Drop unsupported file: show inline error **inside** the card (no popup).

Hidden:
- No save location summary
- No progress
- No export controls

---

### State B — VIDEO_SELECTED

**Goal:** Confirm the video; provide one next step.

Video Card:
- 16:9 thumbnail
- Clear “X” overlay in top-right
- Under thumbnail:
  - filename (no path)
  - duration

Save location summary (read-only):
- Only visible when a video is selected **and** the save policy is not “Ask every time”.
- Format:
  - Label: “Saving to:” (muted)
  - Value: resolved folder path (single line, elide middle if long)
- No “Change…” link here; user changes this in Settings.

Primary action:
- Primary button: “Create subtitles”

Drag/drop:
- Dropping a new video replaces the current selection.

---

### State C1 — WORKING_EXTRACT

**Goal:** Show real progress; keep UI calm.

Layout:
- Compact video card remains visible.
- Progress Card:
  - Title: “Preparing audio”
  - Sub-status line: “Extracting audio”
  - Determinate progress bar
    - **Only the progress bar shows the %** (e.g., “18%”).
    - The sub-status text must not include “— 18%”.
  - Cancel button (single CTA)

“Not stuck” rule:
- If the numeric % doesn’t change for >10 seconds, show a subtle activity indicator:
  - e.g., pulsing dot after the sub-status: “Extracting audio ···”

---

### State C2 — WORKING_TRANSCRIBE

**Goal:** Transcription often has coarse progress updates; the UI must still feel alive.

Layout:
- Compact video card remains visible.
- Progress Card:
  - Title: “Creating subtitles”
  - Sub-status line: “Listening to audio”
  - Determinate progress bar
    - **Only the progress bar shows the %**.
  - Cancel button

“Not stuck” rules (mandatory):
- Always show an activity indicator while transcribing (even if % holds):
  - Example: “Listening to audio ···” (animated)
- If progress updates are coarse, the app should:
  - show occasional small % movement (estimator/smoothing), **without lying** (do not exceed a safe ceiling until real progress arrives)
  - never jump from 20% to 100% without intermediate movement

Future (PR11):
- A thumbnail strip showing “subtitle moments” updated periodically (throttled).

---

### State D — SUBTITLES_READY

**Goal:** Make the result feel real; allow styling adjustments before export.

Current implementation:
- Actions:
  - Primary: “Create final video” (single CTA, inside the Style card).
- Two-column layout:
  - Left: Preview Card (subtitle still only)
    - Click still frame to expand preview in a dialog.
    - Preview stills are graphics-rendered to match export styling.
  - Right: Style Card (grouped sections + CTA)
    - Mode: segmented control (“Static” / “Word highlight”).
    - Highlight color row (only visible when Subtitle mode = Word highlight).
      - Changing the highlight color refreshes the preview still immediately.
    - Presets: Default, Large outline, Large outline + box, Custom (text list).
    - Quick tweaks: font size, outline width, shadow, bottom margin.
    - Background: none/line/word segmented control (Word disabled with helper text).
    - Line background controls: opacity + padding (visible when Line is selected).
    - Advanced: “Show advanced options” toggle reveals extra controls and a “Reset to preset” action.

---

### State E — WORKING_EXPORT

**Goal:** Export progress must be trustworthy.

Layout:
- Compact video card remains visible.
- Progress Card:
  - Title: “Exporting video”
  - Determinate progress bar (real FFmpeg progress)
  - Cancel button

Future (PR11):
- Slideshow preview frames with final subtitle style.

---

### State F — DONE

UI:
- Result card:
  - Title: “Your video is ready”
  - Filename: `<video_stem>_subtitled.mp4`
- Actions:
  - Primary: “Play video”
  - Secondary: “Open folder”
  - Link: “Edit subtitles and export again”

Collision behavior:
- If the output already exists, show modal:
  - “A subtitled video already exists”
  - Options:
    - Replace it
    - Create new copy (`_subtitled_2`, `_subtitled_3`, …) **default**
    - Cancel

---

### State X — ERROR

Rules:
- Don’t dump logs by default.
- Keep the message non-technical.

Inline errors:
- Invalid file drop

Blocking errors (modal):
- Title: “Couldn’t create subtitles” / “Couldn’t export video”
- Body: one sentence
- Buttons:
  - Primary: “Try again”
  - Secondary: “Choose another video”
  - Link: “Show details”

Details drawer:
- “Copy diagnostic info”
- “Open log file”
- Read-only log viewer

---

## F) Settings page specification

Settings is a **full page** that replaces Home (no dialog).
For operational workflow details (debugging, benchmarks, handover rules), see `/docs/HEBREW_SUBTITLE_GUI_CONTEXT.md`.

### Section 1 — Performance

Controls:
- Label: “Transcription quality”
- Combo box options:
  - Auto
  - Fast (int8)
  - Accurate (int16)
  - Ultra accurate (float32)

Behavior:
- “Auto” chooses a sensible default based on hardware:
  - GPU available → GPU (fast)
  - CPU-only → `int16` (accuracy baseline)
- “Ultra” uses `float32` (CPU) and should warn via helper text that it is slow.

Helper text (always visible):
- A 1–2 line explanation of what the chosen mode prioritizes.

Run summary line (always visible):
- Shows resolved runtime choice, e.g.:
  - “This will run on: GPU (float16)”
  - “This will run on: CPU (int16)”

### Section 2 — Save subtitles

Control 1: Save policy radio group
- Group title: “Save subtitles”
- Options:
  - Same folder as the video
  - Always save to this folder
  - Ask every time

Control 2: Path row
- A single-line path field + button
- Button text: “Browse...”

Rules:
- The path row is always visible.
- The path field is disabled unless policy = “Always save to this folder”.
- Browse button is disabled unless policy = “Always save to this folder”.
- Do not show a “folder” label; the field itself communicates what it is.
- Placeholder when unset: “No folder selected”.

### Section 3 — Subtitle Edit

Controls:
- Label: “Choose Subtitle Edit…”
- A single-line path field + “Browse...” button.

Behavior:
- The path field displays the configured `SubtitleEdit.exe` location (read-only).
- Browse opens a file picker filtered to executables (`*.exe`) and saves the selected path.
- If no path is configured, the app still attempts the default install location:
  - `C:\Program Files\Subtitle Edit\SubtitleEdit.exe`
- If the configured/default path does not exist when the user clicks **Edit in Subtitle Edit**:
  - Show a modal titled “Subtitle Edit not found” with the message:
    - “Subtitle Edit wasn't found. Please install it or choose SubtitleEdit.exe.”
  - Actions: “Choose Subtitle Edit…” (opens the file picker) and “Cancel”.
- If the app fails to launch Subtitle Edit after a path is selected:
  - Show a modal titled “Couldn't open Subtitle Edit” with the message:
    - “Subtitle Edit couldn't be opened. Please check the app path.”

### Section 4 — Punctuation

Controls:
- Checkbox label: “Improve punctuation automatically (recommended)”

Helper text (always visible, indented to align with checkbox text):
- “If subtitles come out with little punctuation, the app may run extra attempts and only switches when results are clearly better. This can take longer.”

Behavior:
- **Do not add a second toggle. This toggle already exists; future PRs must modify its behavior/wiring rather than creating a new control.**
- Defaults ON for new users.
- Preserve existing config values when present.
- This is a **conditional comma-rescue**, not an always-retry feature.
- Trigger logic (conceptual):
  - Only considers rescue if the transcript meets a minimum word count (`min_words`).
  - If comma density is already healthy, rescue is skipped.
- User experience:
  - No new screens or prompts.
  - Rescue happens (if triggered) during the same transcription run.
  - Logs/diagnostics show whether rescue triggered (`punctuation_rescue_triggered`) and the reason.
  - When it triggers, logs/diagnostics include which attempt was chosen; when it does not, the baseline is kept.

**Behavior + UX during run (requirements):**
- **When ON:**
  - The app may run additional transcription attempts **only** when the comma-rescue trigger conditions are met.
  - Progress must **not** regress/reset; the user remains in the same WORKING state.
  - No second progress bar; percent should never jump backward.
  - Status text:
    - Baseline transcription → normal “Creating subtitles…”
    - If rescue triggers → sub-status changes to “Improving punctuation…” while attempts run
  - Cancel stays available and cancels the entire operation (including rescue attempts).
- **When OFF:**
  - Baseline transcription only; no rescue attempts.

### Section 5 — Audio

Controls:
- Checkbox label: “Clean up audio before transcription”
- Checkbox label: “Keep extracted WAV file”

Behavior:
- Audio filter chain default: **OFF** (recommended unless noisy audio).
- When enabled, FFmpeg applies a highpass/lowpass/noise-reduction/loudness-normalization chain.
- “Keep extracted WAV file” default: **OFF**; when ON, the extracted WAV is retained next to outputs.

Helper text (always visible, indented to align with checkbox text):
- Explain that cleaning can help noisy recordings but may reduce punctuation.
- Explain that keeping the WAV is useful for debugging/benchmarking and increases disk usage.

Note on WAV location:
- The app-created WAV is written to the output folder dictated by Save Policy (often the same folder as the video).
- If “Keep extracted WAV file” is OFF, the app may delete it after subtitles are created; if ON, it remains.

### Section 6 — Diagnostics

Diagnostics are for debugging and **must be OFF by default**.

Controls:
- Master checkbox: “Enable diagnostics logging” (default OFF)
- Secondary checkbox (enabled only when master is ON): “Write diagnostics on successful completion” (default OFF)
- When enabled, show checkboxes for what to include:
  - Video file info (path/size/ffprobe)
  - Extracted audio info (wav stats)
  - Subtitle stats (cue/word counts, punctuation counts)
  - Whisper config and parameters
  - FFmpeg command lines and timings
  - App settings used

Output location:
- Diagnostics JSON is written **next to the generated SRT / output video** (same folder).

Note:
- Benchmarks/diagnostics are for debugging only and should not be treated as a user-facing feature.

---

## G) Copywriting glossary (approved)

- “Choose video…”
- “Create subtitles”
- “Creating subtitles”
- “Preparing audio”
- “Listening to audio”
- “Subtitles are ready”
- “Open subtitles”
- “Edit in Subtitle Edit”
- “Create final video”
- “Exporting video”
- “Your video is ready”
- “Play video”
- “Open folder”
- “Try again”
- “Choose another video”
- “Show details”

Avoid:
- “Input”, “Output”, “SRT” in button text
- “Encode”, “Burn-in”, “Hardcode”
