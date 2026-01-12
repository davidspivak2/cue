# Hebrew Subtitle GUI — UX/UI Specification (Design Contract)

**Last updated:** 2026-01-12  
**Scope:** This document describes the intended **pixel-level UI behavior** for Hebrew Subtitle GUI, and the interaction rules the app should follow as it continues the PR1–PR13 overhaul.

This is intentionally opinionated. If an implementation choice conflicts with this spec, update the spec (with rationale) or change the implementation.

> For current project status, roadmap progress, and known issues (including the Hebrew punctuation problem), see `/docs/HEBREW_SUBTITLE_GUI_CONTEXT.md`.

---

## 0) Implementation status snapshot (post-PR6)

Implemented (merged):
- ✅ Dark-only theme foundation
- ✅ Step/state-based single-window UI (stacked pages)
- ✅ Video selection UX: drop zone + thumbnail card + replace-on-drop
- ✅ Settings page is a **full page**, not a dialog (replaces the content area)
- ✅ “Save subtitles to …” moved into Settings (supports *Ask every time* / *Same folder* / *Always save to this folder*)
- ✅ Performance/Quality selector in Settings (includes `float32` option)
- ✅ Burn-in (FFmpeg) progress is real and smooth (no jump-to-100)
- ✅ Transcription progress is **weighted into global progress** and uses smoothing/heartbeat updates to reduce long “stuck” moments (may still be coarse on some files)
- ✅ Optional **success diagnostics JSON** (opt-in) written next to outputs
- ✅ Punctuation rescue hardening: chooser gate prevents selecting worse transcript; additional diagnostics fields
- ✅ Audio extraction default behavior updated to improve transcription readability/punctuation

Not implemented yet (still the target of PR7+):
- ⬜ Subtitles-ready page: preview still frame with real subtitle line (derive from video frame + SRT cues; do **not** rely on extracted WAV staying on disk; cache under LocalAppData, not next to user outputs)
- ⬜ Style presets + customize panel with instant preview
- ⬜ In-app preview playback + karaoke-like highlighting
- ⬜ “Delightful waiting” visuals (waveform strip, thumbnail strip during transcription; cache lightweight artifacts under app cache, throttle updates, avoid repo/output clutter)
- ⬜ Error UX details drawer
- ⬜ Packaging hardening pass
- ⬜ PR15 — copy polish + CTA reduction sweep (final pass after features stabilize; PR5 remains partial until PR7–PR13 are done)

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
  - “Export video with subtitles”

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

**Goal:** Make the result feel real; allow review/edit before export.

Current minimal implementation (already OK):
- Title: “Subtitles are ready”
- Actions:
  - Primary: “Edit in Subtitle Edit”
  - Secondary: “Export video with subtitles”
  - Tertiary: “Open subtitles”, “Open folder”

Target end-state (PR7–PR10):
- Two-column layout
  - Left: Preview Card (frame + real subtitle)
  - Right: Style Card (presets + customize)
- Optional karaoke-like highlighting (default ON)

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
- Subtitle Edit executable missing

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
- Label: “Quality”
- Combo box options:
  - Auto
  - Fast
  - Accurate
  - Ultra

Behavior:
- “Auto” chooses a sensible default based on hardware:
  - GPU available → GPU (fast)
  - CPU-only → `int16` (accuracy baseline)
- “Ultra” uses `float32` (CPU) and should warn via helper text that it is slow.

Helper text (always visible):
- A 1–2 line explanation of what the chosen mode prioritizes.

Run summary line (always visible):
- Shows resolved runtime choice, e.g.:
  - “Will run on: GPU (CUDA) — float16”
  - “Will run on: CPU — int16”

### Section 2 — Save subtitles

Control 1: Save policy combo
- Label: “Save subtitles”
- Options:
  - Ask every time
  - Same folder as the video
  - Always save to this folder

Control 2: Path row
- A single-line path field + button
- Button text: “Browse…”

Rules:
- If policy = **Ask every time**
  - Hide the entire path row.
- Else
  - Show the path row.
  - The path field is always visible.
  - The path field is disabled unless policy = “Always save to this folder”.
  - Browse button is disabled unless policy = “Always save to this folder”.
  - Do not show a “folder” label; the field itself communicates what it is.

### Section 3 — Punctuation

Controls:
- Checkbox label: “Improve punctuation automatically (recommended)”

Helper text (always visible, indented to align with checkbox text):
- “If subtitles come out with little punctuation, the app may run extra attempts and only switches when results are clearly better. This can take longer.”

Behavior:
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

### Section 4 — Audio

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

### Section 5 — Diagnostics

Diagnostics are for debugging and **must be OFF by default**.

Controls:
- Master checkbox: “Write diagnostics after successful runs” (default OFF)
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
- “Export video with subtitles”
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
