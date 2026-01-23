# PR10 — Word Highlight Subtitles (Karaoke-Style) — Implementation Plan

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

## G) Post-PR10 follow-ups (not required for PR10 merge)
- A) Highlight opacity control.
- B) Base text color control.
- C) Font family picker with Hebrew-safe defaults.
- D) Line/word background controls (including opacity/padding/radius) are implemented in the Subtitles Ready UI and used by the graphics renderer for preview stills and graphics overlay export.
- J) Alignment/performance optimizations (caching, preview-window-only alignment improvements).
- K) Packaging hardening for WhisperX deps (tie to packaging work).

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

### Post-PR10 follow-up tracking
| Item | Status | Notes |
| --- | --- | --- |
| Highlight opacity control | TODO |  |
| Base text color control | TODO |  |
| Font family picker | TODO |  |
| Alignment/performance optimizations | TODO |  |
| WhisperX packaging hardening | TODO |  |
