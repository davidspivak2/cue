# Caption Graphics Overlay Plan

## Status update (2025-02-14)
- PR5 is complete (streaming overlay export is in place with the default graphics overlay path).
- PR6 is complete (performance pass landed).
- PR7 is complete (word background rendering, mutual exclusivity, and UI controls for line/word background color, opacity, padding, and corner radius are in place).
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
- No extra actions like “Open folder”.

## Critical constraints (must follow)
- Must not create thousands of PNGs on disk; no “PNG per state” for full exports.
- Must preserve the current main behavior as a fallback restore point.
- Must keep export progress UI behavior unchanged (reuse existing progress bar/worker UX).
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
- No “auto-picked moment”.
- Header shows “Subtitles ready ✓”.

### Line vs word background controls
- Provide controls for line background and word background.
- Segmented control labels: None / Around line / Around word.
- Around word is visible but disabled in Static mode with a tooltip that it requires Word highlight.
- They are mutually exclusive:
  - Enabling one must disable the other.
  - The UI must make the enable/disable behavior clear.

## Progressive multi-PR implementation plan

### PR1 — SUBTITLES_READY UI overhaul (no rendering changes)
- Purpose: Implement the new UI layout and controls without touching rendering or export logic.
- Scope:
  - Rework the SUBTITLES_READY screen layout to the two-column design.
  - Update CTA label to “Create video with subtitles” in the sticky bottom bar.
  - Replace mode dropdown with segmented control.
  - Convert presets to a dropdown.
  - Remove playback-related elements (play buttons, auto-picked moment).
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
  - Confirm no playback controls or auto-picked moment are present.
  - Toggle line vs word background and ensure only one can be enabled.

### PR2 — Style/config schema foundation
- Purpose: Create a unified style schema that supports both legacy and graphics overlay rendering paths.
- Scope:
  - Define or extend a style/config model for caption graphics overlay options.
  - Ensure the schema includes fields for word highlight, rounded corners, and line/word backgrounds.
  - Introduce a compatibility layer so existing exports still work.
- Likely files/modules:
  - Configuration models or schema definitions.
  - Settings serialization/deserialization.
- Key implementation notes and risks:
  - Maintain backward compatibility with existing saved presets.
  - Include a clear marker or flag for renderer choice with a default of legacy.
- Manual test checklist:
  - Load existing projects without schema errors.
  - Create a new preset and confirm it serializes and reloads.

### PR3 — Graphics renderer for preview still (no export integration yet)
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
  - Confirm fallback to legacy preview if renderer fails.
- Manual test checklist:
  - Toggle Static and Word highlight; preview updates accordingly.
  - Word highlight preview uses 2nd word, not time-based alignment.
  - Rounded corners and line background render correctly in still preview.

### PR4 — RTL/mixed text word rectangle correctness hardening
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

### PR5 — Export integration with streaming overlay frames (no disk)
- Purpose: Stream overlay frames to FFmpeg during export without creating PNGs.
- Scope:
  - Add a state-driven render loop that emits frames only when caption state changes.
  - Pipe raw RGBA frames to FFmpeg stdin and composite via overlay filter.
  - Preserve existing progress bar and worker UX.
  - Keep the new pipeline gated (default on; allow legacy fallback).
- Likely files/modules:
  - Export pipeline and FFmpeg invocation logic.
  - Renderer integration points.
- Key implementation notes and risks:
  - Ensure the export progress UI behaves exactly as before.
  - Keep legacy path intact as a fallback switch (env flag: `SUBTITLES_GRAPHICS_OVERLAY_EXPORT=0` disables).
- Manual test checklist:
  - Export a short clip and confirm no PNGs are written.
  - Verify progress bar and worker behavior unchanged.
  - Confirm output matches the preview styling.

### PR6 — Performance pass
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

### PR7 — Word background controls + rendering with mutual exclusivity
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

### PR8 — Flip default to graphics renderer while keeping legacy fallback
- Purpose: Make graphics renderer the default path with a legacy fallback option preserved.
- Scope:
  - Switch default renderer selection to graphics overlay.
  - Maintain a config or runtime toggle to revert to legacy rendering if needed.
  - Add logging to indicate which renderer is used during export.
- Likely files/modules:
  - Renderer selection logic.
  - Logging utility.
- Key implementation notes and risks:
  - Ensure legacy path remains fully functional.
  - Make it easy to diagnose renderer choice in logs.
- Manual test checklist:
  - Verify default uses graphics renderer.
  - Toggle fallback and confirm legacy output is produced.

### PR9 — Optional cleanup and follow-ups
- Purpose: Remove dead code and document new renderer usage after stability is confirmed.
- Scope:
  - Remove unused helpers left behind by the transition.
  - Add developer notes for renderer selection and debug logging.
- Likely files/modules:
  - Renderer utilities and legacy glue code.
  - Developer documentation (only if explicitly permitted later; do not touch now).
- Key implementation notes and risks:
  - Only proceed after verifying rollback path and production stability.
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
