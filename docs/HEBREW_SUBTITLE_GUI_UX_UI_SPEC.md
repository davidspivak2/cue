# Hebrew Subtitle GUI — UX/UI Specification (Design Contract)

**Last updated:** 2026-03-10  
**Scope:** This document is the **single source of truth** for the full redesign: visual system, navigation model, project model, screen specs, state machine, and pipeline contract.

This is a **strict design contract**. Implementation must follow it exactly. If implementation diverges, update this spec with rationale **before** or **as part of** the change.

> For project status and roadmap context, see `/docs/HEBREW_SUBTITLE_GUI_CONTEXT.md`.

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
