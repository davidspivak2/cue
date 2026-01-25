# Project Roadmap (Single Source of Truth)

## Rules
- This file is the ONLY place to look for “what to do next”.
- If work is not listed here, it is not scheduled.
- The UX spec defines target behavior; this file defines implementation order and acceptance criteria.
- Each work item must include: Status, Deliverable, Acceptance criteria, and UX spec reference (section name).

## Now / Next (Queue)
(Use a numbered list. Status tags must be one of: NEXT, IN PROGRESS, BLOCKED, DONE.)

1. [NEXT] PR12 — Error UX with details drawer + copy diagnostics
   - Deliverable:
     - Error UI includes a details drawer and a “Copy diagnostics” action.
     - Diagnostics tools remain in Settings only (error UI may show details, not tools).
   - Acceptance criteria:
     - Trigger an error: user can open details drawer and copy the diagnostics text.
     - No separate diagnostics “toolbox” appears on the error screen.
   - UX spec reference: Error UX + Diagnostics

2. [NEXT] Redesign Milestone 1 — Project system backend (persistence + multi-project)
   - Deliverable: app can create/open multiple projects with persisted state across restarts.
   - Acceptance criteria: see Milestone 1 checklist below.
   - UX spec reference: Project model / Project Hub

3. [NEXT] PR13 — Packaging hardening / smoke tests
   - Deliverable:
     - Packaging flow hardened for release and smoke tests run against packaged builds.
   - Acceptance criteria:
     - Packaged build launches and completes the golden-path smoke test without regressions.
   - UX spec reference: N/A (release engineering, not in UX spec)

4. [NEXT] PR15 — Copy polish + CTA reduction sweep
   - Deliverable:
     - Copy polish applied and CTA reduction pass completed across UI surfaces.
   - Acceptance criteria:
     - Strings match the approved copywriting glossary and CTA count is minimized per spec.
   - UX spec reference: Copywriting glossary (approved strings)

5. [NEXT] Export optimization — cache video stream info earlier + cheap revalidate; remove/adjust “Getting video info” checklist row if appropriate
   - Deliverable:
     - Video stream info cached earlier; export path uses cheap revalidation.
     - “Getting video info” checklist row removed or adjusted if no longer accurate.
   - Acceptance criteria:
     - Export step uses cached stream info with a fast revalidation pass; UI checklist reflects the actual work.
   - UX spec reference: Export progress + success (in-Workbench)

## Milestones (Ordered to Completion)

### Milestone 0 — Stabilization
0.1 PR12 — Error UX + details drawer + copy diagnostics
0.2 PR13 — Packaging hardening / smoke tests
0.3 PR15 — Copy polish + CTA reduction sweep
0.4 Export optimization — cache video stream info earlier + cheap revalidate; potentially remove/adjust “Getting video info” checklist row

Definition of done:
- App is stable enough to proceed with refactors needed for redesign without frequent regressions.

### Milestone 1 — Project system backend (required for redesign)
1.1 Persistence layer and project folder concept
- Deliverable:
  - App-managed projects root folder concept.
  - Autosave always on.
  - Persist: source video reference (plus relink metadata), subtitles, style config, word timings, export metadata, status.
- Acceptance criteria:
  - Create a project from a video, close app, reopen: project appears and can be opened.
  - Project status persists across restarts.

1.2 Project lifecycle operations
- Deliverable:
  - Create new project from video
  - Open existing project list
  - Open/close project tabs (no deletion required)
  - Relink missing source video workflow
- Acceptance criteria:
  - If source video is missing, app shows missing state and relink succeeds.

1.3 Project status model
- Deliverable:
  - Status enum: Needs video / Needs subtitles / Ready / Exporting / Done / Missing file
- Acceptance criteria:
  - Status is correct for each stage and survives restart.

Definition of done:
- User can manage multiple projects across restarts and relink missing video without breaking the project.

### Milestone 2 — Project Hub UI (new entry point)
2.1 Project Hub screen
- Deliverable:
  - Grid of project cards, primary CTA “New project”, drag-and-drop onto hub
- Acceptance criteria:
  - Launch opens Project Hub; “New project” works; DnD works.

2.2 Card content + interactions
- Deliverable:
  - Thumbnail, filename (no full path), duration, status label
  - Click opens/activates Workbench tab
  - Missing file shows Relink action
- Acceptance criteria:
  - All card fields render and actions work.

2.3 Launch behavior
- Deliverable:
  - App always launches to Project Hub (no auto-open last project)
- Acceptance criteria:
  - Restart app: Project Hub is shown.

Definition of done:
- Project Hub is the stable home screen and projects open into Workbench.

### Milestone 3 — Workbench shell (unified edit + style + preview + export)
3.1 Workbench layout regions
- Deliverable:
  - Center video preview
  - Left “All subtitles” panel
  - Right style inspector
- Acceptance criteria:
  - Workbench tab shows these regions with stable sizing.

3.2 Left panel responsive behavior
- Deliverable:
  - Collapsed by default
  - Docked at wide widths, resizable, per-project persisted width
  - Overlay drawer under 1100px with scrim + Esc closes
  - Only one overlay open at a time (left vs right)
- Acceptance criteria:
  - Resize window around threshold: dock/overlay rules work exactly.

3.3 Right panel responsive behavior
- Deliverable:
  - Docked wide; overlay narrow via “Style” button
  - No horizontal scroll
- Acceptance criteria:
  - Narrow width: style panel becomes overlay; content still accessible.

Definition of done:
- Workbench behaves correctly across window sizes and supports the unified workflow.

### Milestone 4 — In-app subtitle text editing (core missing feature)
4.1 Left list editing
- Deliverable:
  - Each row shows timestamps (read-only) + editable text
  - Clicking row seeks video + selects subtitle
- Acceptance criteria:
  - Edit text, seek + selection sync works.

4.2 On-video editing contract
- Deliverable:
  - Click subtitle while playing → pause + select
  - Click again when paused → inline edit anchored at subtitle position
  - Enter saves, Esc cancels
- Acceptance criteria:
  - Interactions match exactly; no accidental exports of selection styling.

4.3 Selection styling contract
- Deliverable:
  - Accent outline indicates selection only; never exported
  - List selection and on-video selection remain in sync
- Acceptance criteria:
  - Export shows no selection outline.

Definition of done:
- User can fully edit subtitles in-app with the specified interactions.

### Milestone 5 — Pipeline contract change: WhisperX timing is part of “Create Subtitles”
5.1 “Create Subtitles” completeness
- Deliverable:
  - “Create Subtitles” is not complete until BOTH SRT generation and WhisperX timed words succeed.
- Acceptance criteria:
  - After “Create Subtitles”, timed words exist; no timed-words step deferred to export.

5.2 Progress UI update
- Deliverable:
  - Progress checklist includes “Timing word highlighting (WhisperX)”
- Acceptance criteria:
  - Step appears and reports progress accurately.

5.3 Export behavior enforcement
- Deliverable:
  - Export does not normally run WhisperX.
  - If word highlight selected but timings missing/stale, export is blocked with instructions to re-run “Create Subtitles”.
- Acceptance criteria:
  - Export path never silently runs WhisperX in normal success path.

Definition of done:
- Word highlight mode is ready immediately after subtitle creation; export uses existing timings.

### Milestone 6 — Workbench CTAs + export UX (in-Workbench)
6.1 CTA placement rules
- Deliverable:
  - Bottom action bar exists only in “Subtitles ready” and “Export success”
  - Bottom bar has only “Create video with subtitles”
  - Earlier states show “Create subtitles” in main content area (no bottom bar)
- Acceptance criteria:
  - UI matches these CTA rules across states.

6.2 Export progress in Workbench
- Deliverable:
  - Checklist + determinate progress + elapsed time + Cancel
  - Editing/styling disabled while exporting
- Acceptance criteria:
  - Export shows correct progress; editing disabled.

6.3 Export success state
- Deliverable:
  - In-place success with Play video, Open folder
  - User can continue editing and re-export
- Acceptance criteria:
  - No separate “Done” screen required for success.

Definition of done:
- Export is a Workbench flow and matches the UX contract.

### Milestone 7 — Settings integration rules + busy-state rules
7.1 Settings navigation rules
- Deliverable:
  - Settings accessible from Project Hub + Workbench
  - Settings nav disabled during long tasks
- Acceptance criteria:
  - Long task: Settings entry disabled with clear reason.

7.2 Multi-project busy rules (v1)
- Deliverable:
  - Switching tabs allowed while one project runs
  - Other tabs read-only with visible “Busy” reason
- Acceptance criteria:
  - Busy tabs cannot start conflicting operations.

7.3 Diagnostics entry point enforcement
- Deliverable:
  - Diagnostics tools live in Settings only
  - Error UI may show details drawer but not diagnostics tools
- Acceptance criteria:
  - No diagnostics tools appear outside Settings.

Definition of done:
- App obeys navigation + busy-state rules.

### Milestone 8 — Visual system conformance pass
8.1 Token alignment (radius, borders, typography scale)
8.2 Focus/hover/disabled states compliance
8.3 Remove remaining old UI surfaces

Definition of done:
- UI consistently matches the UX spec visual system.

### Milestone 9 — Cleanup + ship readiness
9.1 Remove obsolete screens/states replaced by Project Hub/Workbench
9.2 Packaging + smoke tests (if not already satisfied)
9.3 Final regression checklist (Create Subtitles / edit / style / export / relink / multi-project)

Definition of done:
- All UX spec sections B–H are implemented; ROADMAP has no remaining redesign items.

## Backlog (Unscheduled)
- Keep this short; ideas go here only if they are explicitly not scheduled.

## Completed
- A short bullet list only (do not paste old plans here; those go in the Archive appendix below).

## Decision log
- Date + short note for any decision that changes scope/order.

## Appendix: Archived documents (verbatim)
- “CAPTION_GRAPHICS_OVERLAY_PLAN.md (verbatim)”
- “PR10_WORD_HIGHLIGHT_PLAN.md (verbatim)”

### CAPTION_GRAPHICS_OVERLAY_PLAN.md (verbatim)
# Caption Graphics Overlay Plan

Status: Completed. This plan is kept for historical reference. For upcoming work, see [`ROADMAP.md`](ROADMAP.md).

## Status update (snapshot from 2025-02-14; see GUI context for current status)
- Overlay PR5 is complete (streaming overlay export is in place with the default graphics overlay path).
- Overlay PR6 is complete (performance pass landed).
- Overlay PR7 is complete (word background rendering, mutual exclusivity, and UI controls for line/word background color, opacity, padding, and corner radius are in place).
- Overlay PR8 is complete (graphics overlay is the only export renderer; subtitle-filter paths are removed).
- Wrapped-line word-highlight clip rects now use line-relative cursor offsets in the graphics overlay renderer.
- Graphics overlay export now handles QImage bit-buffer variants for RGBA streaming.
- Overlay render caching keys are normalized to the expected text + highlight index format.
- The Subtitles Ready screen uses a two-column layout with a sticky bottom bar showing “Saving as:” plus the “Create video with subtitles” CTA.
- Preview stills are graphics-rendered and highlight the second word in Word highlight mode.
- Preview playback controls are no longer surfaced in the Subtitles Ready view.

## Goals and non-goals

### Goals
- Build a scalable caption graphics overlay renderer that avoids disk explosion and supports:
  - Perfect-timing word highlighting.
  - Rounded corner backgrounds.
  - Richer styling than libass/force_style.
- Overhaul the SUBTITLES_READY screen per the latest decisions:
  - Single CTA only.
  - Still preview only (no playback).
  - When Word highlight mode is selected, preview highlights the 2nd word (preview-only behavior).
  - Presets are a dropdown (no preview tiles).
  - Line background and word background are mutually exclusive.

### Non-goals
- No animations.
- No live preview playback.
- Non-goal (SUBTITLES_READY): No extra actions like “Open folder” on the Subtitles Ready screen.

## Critical constraints (must follow)
- Must not create thousands of PNGs on disk; no “PNG per state” for full exports.
- Rollback is via the annotated Git tag (no runtime fallback).
- Must keep export progress UI behavior unchanged (reuse existing progress bar/worker UX). Note: export progress now ties 0–10% to word timing progress so the bar does not hang at 10% during timing.
- CTA label must be exactly: “Create video with subtitles”.
- No live preview playback; preview is always a still frame.
- Presets must be a dropdown (no tiny preview tiles).
- Must not allow both line background and word background at the same time.

## Restore baseline main later

Primary restore mechanism: annotated tag.

Windows cmd instructions to create and push the tag:
- `git checkout main`
- `git pull --ff-only`
- `git tag -a baseline_before_graphics_overlay -m "Baseline before caption graphics overlay"`
- `git push origin baseline_before_graphics_overlay`

Optional: create a baseline branch as a convenience, but the tag above is the primary restore point.

## Architecture overview

### Scalable backend approach
- Implement a state-driven graphics renderer that only re-renders when caption state changes (for example, on word index changes or line changes).
- Render the overlay in-memory and stream frames as raw RGBA to FFmpeg via stdin.
- Composite the overlay using an FFmpeg overlay filter during export.

### Why this scales
- No per-frame PNGs are written to disk.
- Rendering only on state changes means far fewer render operations, even for long exports.
- Streaming RGBA keeps memory usage bounded and avoids filesystem bottlenecks.

### Preview alignment
- The preview uses the same graphics renderer as export.
- In Word highlight mode, the still preview highlights the 2nd word for clarity; it is not time-accurate and is explicitly a preview-only behavior.

## SUBTITLES_READY UI spec (fully described)

### Layout
- Two-column layout:
  - Left: still preview frame.
  - Right: style panel.

### CTA
- Only one CTA button.
- Label must be exactly: “Create video with subtitles”.
- CTA lives in the sticky bottom bar (not inside the style panel).
- Bottom bar also shows “Saving as: <output path>”.

### Mode control
- Segmented control: Static | Word highlight.
- Do not use a dropdown.

### Presets
- Display presets in a dropdown.
- No preview tiles.

### Preview behavior
- Still preview only.
- No play buttons.
- Preview moment is auto-picked (first non-empty cue; preview anchors ~25% into the cue).
- Header shows “Subtitles ready ✓”.

### Line vs word background controls
- Provide controls for line background and word background.
- Segmented control labels: None / Around line / Around word.
- Around word is visible but disabled in Static mode with a tooltip that it requires Word highlight.
- They are mutually exclusive:
  - Enabling one must disable the other.
  - The UI must make the enable/disable behavior clear.

## Progressive multi-PR implementation plan (historical; all PRs completed)

### Overlay PR1 — SUBTITLES_READY UI overhaul (no rendering changes)
- Purpose: Implement the new UI layout and controls without touching rendering or export logic.
- Scope:
  - Rework the SUBTITLES_READY screen layout to the two-column design.
  - Update CTA label to “Create video with subtitles” in the sticky bottom bar.
  - Replace mode dropdown with segmented control.
  - Convert presets to a dropdown.
  - Keep the auto-picked preview moment (first non-empty cue; preview anchors ~25% into the cue).
  - Remove playback-related elements (play buttons).
  - Add mutually exclusive line vs word background UI controls (logic can be visual-only for now).
- Likely files/modules:
  - UI components for the SUBTITLES_READY screen.
  - Style panel components and related state wiring.
- Key implementation notes and risks:
  - Keep all rendering/export logic untouched to avoid regressions.
  - Ensure the CTA text is exact.
- Manual test checklist:
  - Verify two-column layout and still preview on the left.
  - Verify CTA text matches exactly.
  - Confirm segmented control and preset dropdown appear.
  - Confirm no playback controls are present.
  - Toggle line vs word background and ensure only one can be enabled.

### Overlay PR2 — Style/config schema foundation
- Purpose: Create a unified style schema that supports the graphics overlay rendering path.
- Scope:
  - Define or extend a style/config model for caption graphics overlay options.
  - Ensure the schema includes fields for word highlight, rounded corners, and line/word backgrounds.
  - Introduce a compatibility layer so existing presets still load.
- Likely files/modules:
  - Configuration models or schema definitions.
  - Settings serialization/deserialization.
- Key implementation notes and risks:
  - Maintain backward compatibility with existing saved presets.
  - Include a clear marker or flag for renderer choice with graphics overlay as the default.
- Manual test checklist:
  - Load existing projects without schema errors.
  - Create a new preset and confirm it serializes and reloads.

### Overlay PR3 — Graphics renderer for preview still (no export integration yet)
- Purpose: Implement the graphics overlay renderer and wire it to still preview only.
- Scope:
  - Add a graphics renderer that can draw a single frame overlay.
  - Use the renderer for the SUBTITLES_READY preview still.
  - In Word highlight mode, highlight the 2nd word in preview.
- Likely files/modules:
  - New graphics renderer module and drawing utilities.
  - Preview rendering integration.
- Key implementation notes and risks:
  - Do not change export behavior in this PR.
  - Confirm preview failures surface errors without switching renderers.
- Manual test checklist:
  - Toggle Static and Word highlight; preview updates accordingly.
  - Word highlight preview uses 2nd word, not time-based alignment.
  - Rounded corners and line background render correctly in still preview.

### Overlay PR4 — RTL/mixed text word rectangle correctness hardening
- Purpose: Ensure word bounding boxes are correct for RTL and mixed-direction text.
- Scope:
  - Implement robust text measurement for word rectangles.
  - Validate order and bounds in RTL scripts and mixed text.
- Likely files/modules:
  - Text shaping/measurement utilities in the graphics renderer.
  - Locale or bidi handling helpers.
- Key implementation notes and risks:
  - Use consistent text shaping to avoid mismatch between rendering and highlight positions.
  - Be explicit about font fallback behavior.
- Manual test checklist:
  - Verify word highlights align with Arabic/Hebrew samples.
  - Verify mixed RTL/LTR sentences render correct word rectangles.

### Overlay PR5 — Export integration with streaming overlay frames (no disk)
- Purpose: Stream overlay frames to FFmpeg during export without creating PNGs.
- Scope:
  - Add a state-driven render loop that emits frames only when caption state changes.
  - Pipe raw RGBA frames to FFmpeg stdin and composite via overlay filter.
  - Preserve existing progress bar and worker UX.
  - Use the graphics overlay pipeline for all exports.
- Likely files/modules:
  - Export pipeline and FFmpeg invocation logic.
  - Renderer integration points.
- Key implementation notes and risks:
  - Ensure the export progress UI behaves exactly as before.
  - No subtitle-filter export path or runtime toggle remains.
- Manual test checklist:
  - Export a short clip and confirm no PNGs are written.
  - Verify progress bar and worker behavior unchanged.
  - Confirm output matches the preview styling.

### Overlay PR6 — Performance pass
- Purpose: Optimize renderer and export performance for long videos.
- Scope:
  - Cache static layout results across frames with identical state.
  - Optimize text measurement hot paths.
  - Add basic instrumentation logs for render timing (dev-only).
- Likely files/modules:
  - Graphics renderer implementation.
  - Export loop and state comparison logic.
- Key implementation notes and risks:
  - Do not change visual output.
  - Keep logging behind a dev-only flag.
- Manual test checklist:
  - Export a longer clip and confirm runtime improves or stays stable.
  - Confirm output matches previous visual results.

### Overlay PR7 — Word background controls + rendering with mutual exclusivity
- Status: ✅ Complete (merged).
- Purpose: Implemented word background rendering and enforced mutual exclusivity in logic.
- Scope (delivered):
  - Added word background rendering to graphics overlay.
  - Wired UI controls to the renderer.
  - Enforced mutual exclusivity between line background and word background in state logic.
- Likely files/modules:
  - UI state management for background mode.
  - Graphics renderer background drawing.
- Key implementation notes and risks (resolved):
  - The mutual exclusivity must be enforced both in UI and in persisted state.
  - Ensure the renderer behaves predictably when toggling modes.
- Manual test checklist:
  - Enable word background and verify line background is disabled automatically.
  - Switch back to line background and verify word background turns off.
  - Export a short clip and confirm the correct background mode renders.

### Overlay PR8 — Graphics-only export (graphics overlay only)
- Status: ✅ Complete.
- Purpose: Make graphics overlay the only export renderer and remove subtitle-filter paths.
- Scope (delivered):
  - Removed subtitle-filter export paths and runtime toggles.
  - Log the renderer choice at export start.
- Likely files/modules:
  - Renderer selection logic.
  - Logging utility.
- Key implementation notes and risks (resolved):
  - Ensure export failures surface clearly without fallback.
- Manual test checklist:
  - Verify export uses graphics overlay renderer.

### Overlay PR9 — Optional cleanup and follow-ups (completed)
- Status: ✅ Complete.
- Purpose: Remove dead code and document graphics overlay renderer usage.
- Scope (delivered):
  - Removed unused helpers left behind by the transition.
  - Added developer notes for renderer debugging and logging.
- Likely files/modules:
  - Renderer utilities cleanup.
  - Developer documentation.
- Manual test checklist:
  - Smoke test export and preview still to confirm no regressions.

## Diagnostics and debug strategy

- Timing misalignment:
  - Validate segment timelines against subtitle timestamps during export.
  - Add an optional dev-only debug burn that overlays timestamps and current word index on the preview/export output.
- Renderer backend choice:
  - Log which renderer path is selected at export start.
- FFmpeg command visibility:
  - Log the full FFmpeg command line for debugging pipeline issues.
- Actionable debug steps:
  - Reproduce with a short clip and enable dev logging.
  - Check logs for state change counts vs. expected word transitions.
  - Compare debug burn output to expected word indices at key timestamps.

### PR10_WORD_HIGHLIGHT_PLAN.md (verbatim)
# PR10 — Word Highlight Subtitles (Karaoke-Style) — Implementation Plan

Status: Completed. This plan is kept for historical reference. For upcoming work, see [`ROADMAP.md`](ROADMAP.md).

Last updated: 2026-02-27

## A) Goal and user-visible outcomes
- Subtitle mode selector is available, with **Word highlight** recommended as the default and **Static** as the alternative.
- RTL Hebrew ordering stays stable during and after highlighting.
- Highlight is real highlighting (not underline), with user-selectable highlight color.
- Word timings come from alignment (WhisperX), not heuristic splitting.

## B) Scope boundaries (anti-scope-explosion guardrails)
- Static rendering is supported via the graphics overlay renderer (regression-free).
- Word highlight uses the graphics overlay renderer for export and preview.
- Styling items not supported in FFmpeg subtitle filters (e.g., border radius) are handled by the graphics renderer.

**Removal note:** The subtitle-filter export and preview pipelines were removed in the graphics-only export PR (this PR).

## C) High-level technical approach
- **Static mode:** graphics overlay renderer (no FFmpeg subtitle filters).
- **Word highlight mode:** graphics overlay renderer with word timing alignment.
- **Alignment:** WhisperX produces word-level timestamps keyed to the edited SRT (so edits are respected).
- **Preview still:** same renderer as export (no divergence).

**RTL hardening in graphics renderer:**
- Ensure RTL ordering stays stable during word highlight updates.
- Avoid style changes that cause reflow in RTL runs.

## D) Execution strategy (how we split work)
1) **Stacked sub-PRs (recommended):** PR10a, PR10b, ...
2) **Single PR10 branch** with multiple commit batches.

**Recommendation:** use stacked sub-PRs for reviewability and safer merges.

## E) Progressive task breakdown

### Codex Task 1 — Data model/config keys for `subtitle_mode` + highlight settings (no behavior change)
- **Goal:** Add config/state support for subtitle mode and highlight settings without changing behavior. ✅ Done.
- **Scope:**
  - Add new config keys for `subtitle_mode` and highlight styling settings.
  - No UI wiring and no pipeline changes.
- **Primary files likely touched:**
  - `app/main.py`
  - `app/ui/state.py`
  - `docs/HEBREW_SUBTITLE_GUI_CONTEXT.md`
- **Implementation notes:**
  - Keep defaults as current behavior (static) until Task 10 is complete.
  - Ensure config migrations are backward-compatible.
- **Acceptance criteria:**
  - Config loads/saves new keys without errors.
  - Existing static subtitle flow unchanged.
- **Depends on:** none.

### Codex Task 2 — UI controls in `SUBTITLES_READY` (no behavior change)
- **Goal:** Add UI controls for subtitle mode and highlight settings in the Subtitles-ready view. ✅ Done.
- **Scope:**
  - Add UI elements only; do not change preview/export behavior.
  - Persist selection to config/state.
- **Primary files likely touched:**
  - `app/ui/subtitles_ready.py`
  - `app/main.py`
  - `app/ui/widgets/*`
- **Implementation notes:**
  - Default to Static until Task 10 (now complete; Word highlight is the default).
  - Provide clear explanatory labels/tooltips.
- **Acceptance criteria:**
  - Controls render and persist selections.
  - No behavioral changes to preview/export.
- **Depends on:** Task 1.

### Codex Task 3 — Subtitle-filter rendering adapter (removed)
- **Status:** Removed in the graphics-only export PR (subtitle-filter pipeline deleted).

### Codex Task 4 — Subtitle-filter export path (removed)
- **Status:** Removed in the graphics-only export PR (no FFmpeg subtitle filters remain).

### Codex Task 5 — Preview still uses graphics renderer + cache key updates
- **Goal:** Preview still renderer supports word-highlight styling and updates cache keys. ✅ Done.
- **Scope:**
  - Update preview still generator to draw graphics directly over a raw frame.
  - Update cache keys to include subtitle mode + highlight settings.
- **Primary files likely touched:**
  - `app/graphics_preview_renderer.py`
  - `app/main.py`
  - `app/workers.py`
- **Implementation notes:**
  - Ensure caching differentiates Static vs Word highlight modes.
- **Acceptance criteria:**
  - Preview still respects selected mode.
  - Cache invalidates on mode/setting change.
- **Depends on:** Task 4.

### Codex Task 6 — Preview playback renderer alignment
- **Goal:** Preview playback uses the graphics overlay renderer for both modes. ✅ Done.
- **Scope:**
  - Update preview playback generator to stream overlay frames (no subtitle filters).
  - Add/update tests for overlay clip planning.
- **Primary files likely touched:**
  - `app/preview_playback.py`
  - `tests/test_preview_playback_plan.py`
- **Implementation notes:**
  - Ensure timing shifts match preview slice logic.
- **Acceptance criteria:**
  - Preview playback matches graphics overlay export styling.
  - Tests cover overlay clip planning.
- **Depends on:** Task 5.

### Codex Task 7 — Define and plumb a word-timing JSON contract end-to-end (staleness detection on SRT edits)
- **Goal:** Define a word-timing JSON schema and plumb it through the pipeline. ✅ Done.
- **Scope:**
  - Define JSON contract for word timings.
  - Detect staleness when SRT edits occur.
- **Primary files likely touched:**
  - `app/word_timing_schema.py`
  - `app/srt_utils.py`
  - `app/workers.py`
  - `docs/HEBREW_SUBTITLE_GUI_CONTEXT.md`
- **Implementation notes:**
  - Include checksum/hash of SRT to detect staleness.
- **Acceptance criteria:**
  - Word-timing JSON is generated/read with validation.
  - Stale word timings are detected and flagged.
- **Depends on:** Task 4.

### Codex Task 8 — Implement WhisperX alignment worker to produce word timestamps (no heuristics)
- **Goal:** Implement alignment worker for word timestamps using WhisperX. ✅ Done.
- **Scope:**
  - Add worker process to run WhisperX alignment.
  - Output word timing JSON aligned to edited SRT.
- **Primary files likely touched:**
  - `app/align_worker.py`
  - `app/workers.py`
  - `scripts/run_alignment.py`
- **Implementation notes:**
  - No heuristic word splitting.
  - Ensure dependency handling for packaging.
- **Acceptance criteria:**
  - Alignment outputs word-level timestamps for each SRT cue.
  - No heuristic fallback in normal path.
- **Depends on:** Task 7.

### Codex Task 9 — Word highlight rendering using aligned word timings
- **Goal:** Render karaoke-style word highlighting via the graphics overlay renderer. ✅ Done.
- **Scope:**
  - Use aligned word timings to emit per-word highlight states.
  - Add/update tests for overlay clip planning where needed.
- **Primary files likely touched:**
  - `app/graphics_overlay_export.py`
  - `app/preview_playback.py`
  - `tests/test_preview_playback_plan.py`
- **Implementation notes:**
  - Preserve RTL stability in graphics rendering.
- **Acceptance criteria:**
  - Highlighted words match timing JSON.
  - RTL ordering remains stable in graphics rendering.
- **Depends on:** Task 8.

### Codex Task 10 — Flip default to Word highlight + tighten UX + update diagnostics + docs references
- **Goal:** Make Word highlight the default and finalize UX/diagnostics. ✅ Done.
- **Scope:**
  - Update default mode to Word highlight.
  - Tighten labels, hints, and diagnostics.
  - Update docs references.
- **Primary files likely touched:**
  - `app/main.py`
  - `app/ui/subtitles_ready.py`
  - `app/diagnostics.py`
  - `docs/HEBREW_SUBTITLE_GUI_CONTEXT.md`
  - `docs/PR10_WORD_HIGHLIGHT_PLAN.md`
- **Implementation notes:**
  - Ensure Static mode remains available and unchanged.
- **Acceptance criteria:**
  - Default selection is Word highlight.
  - Diagnostics clearly capture mode and renderer.

## Implementation updates (2026-02-27)
- Preview stills now use a graphics renderer that draws subtitles directly onto the raw frame.
- Preview cache keys include subtitle styling + word timing mtimes to refresh when alignment data changes.
- Word highlight is the default subtitle mode, with highlight color defaults applied in config.
- Graphics preview rendering is covered by PySide6-based tests (`tests/test_graphics_preview_renderer.py`).
- Highlight color changes now trigger an immediate preview refresh.
- Highlight overlay clipping and clip-rect alignment were corrected in graphics previews.
- Outline/shadow alignment was fixed for wrapped text and glyph-run paths in graphics rendering.

## F) Definition of Done (PR10)
- [x] RTL stability maintained in preview and export.
- [x] Preview/export parity for styling and timing.
- [x] No heuristics: alignment-based word timing only.
- [x] Mode switch works; Static mode supported by graphics overlay.
- [x] Highlight color is configurable and persists.

## Post-merge fixes
- Wrapped-line highlight fix: graphics overlay clip rects are now line-relative.

## G) Post-PR10 follow-ups
Post-PR10 follow-ups: implemented (see the SUBTITLES_READY style pane).

## H) Tracking tables

### PR10 task tracking
| Task | Status | PR link | Notes |
| --- | --- | --- | --- |
| 1 | Done |  | Config keys + defaults for subtitle mode + highlight settings. |
| 2 | Done |  | Subtitle mode + highlight color controls in Subtitles-ready UI. |
| 3 | Done |  | Subtitle-filter adapter removed with graphics-only export. |
| 4 | Done |  | Export uses graphics overlay only; no runtime toggle or subtitle filters. |
| 5 | Done |  | Preview still uses graphics renderer only. |
| 6 | Done |  | Preview playback uses graphics overlay clip streaming. |
| 7 | Done |  | Word timing JSON contract + staleness detection. |
| 8 | Done |  | WhisperX alignment worker added. |
| 9 | Done |  | Word highlight overlay states driven by aligned word timings. |
| 10 | Done |  | Default subtitle mode is Word highlight; docs + diagnostics updated. |
