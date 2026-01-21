# PR10 — Word Highlight Subtitles (Karaoke-Style) — Implementation Plan

Last updated: 2026-02-27

## A) Goal and user-visible outcomes
- Subtitle mode selector is available, with **Word highlight** recommended as the default and **Static** as the alternative.
- RTL Hebrew ordering stays stable during and after highlighting.
- Highlight is real highlighting (not underline), with user-selectable highlight color.
- Word timings come from alignment (WhisperX), not heuristic splitting.

## B) Scope boundaries (anti-scope-explosion guardrails)
- Static SRT pipeline remains as-is (regression-free).
- Word highlight uses a separate ASS-based pipeline (FFmpeg `ass` filter) in the legacy/export
  and preview playback paths; graphics-overlay export is now the default path when enabled.
- Styling items not supported in legacy ASS/force_style (e.g., border radius) are deferred to Post-PR10.

## C) High-level technical approach
- **Static mode:** existing SRT + `subtitles` filter.
- **Word highlight mode (legacy pipeline):** generate ASS + FFmpeg `-vf ass=...`
  (graphics-overlay export is the default when enabled).
- **Alignment:** WhisperX produces word-level timestamps keyed to the edited SRT (so edits are respected).
- **Preview still:** same renderer as export (no divergence).

**RTL hardening in ASS:**
- Include explicit RTL embedding marks per event.
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

### Codex Task 3 — Introduce ASS rendering adapter (static ASS first) + unit tests
- **Goal:** Add an ASS rendering adapter that can render static subtitles via ASS. ✅ Done.
- **Scope:**
  - Create ASS generation utilities and adapter.
  - Unit tests for ASS output structure.
- **Primary files likely touched:**
  - `app/ass_render.py`
  - `tests/test_ass_renderer.py`
- **Implementation notes:**
  - Match existing static SRT styling as closely as possible.
  - Keep ASS generation deterministic for tests.
- **Acceptance criteria:**
  - ASS output validates basic structure (header + events). ✅
  - Unit tests pass. ✅
- **Depends on:** Task 1.

### Codex Task 4 — Legacy export path uses FFmpeg ass filter for word-highlight mode (still static ASS) + diagnostics fields
- **Goal:** Wire legacy export fallback to use ASS when word-highlight mode is selected (still static ASS content). ✅ Done.
- **Scope:**
  - Add export branch to use FFmpeg `ass` filter when mode is word-highlight.
  - Add diagnostics fields for selected subtitle mode/render path.
- **Primary files likely touched:**
  - `app/workers.py`
  - `app/ffmpeg_utils.py`
  - `app/diagnostics.py`
- **Implementation notes:**
  - Keep static SRT export as default for Static mode.
  - Log which renderer and filter are used.
- **Acceptance criteria:**
  - Export works for both modes.
  - Diagnostics include renderer/mode info.
- **Depends on:** Task 3.

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

### Codex Task 6 — Preview playback uses shifted ASS path when word-highlight mode selected + shifting test coverage (GUI removed)
- **Goal:** Preview playback uses ASS for word-highlight mode, including time-shift logic. ✅ Done.
- **Scope:**
  - Update preview playback generator to render ASS when needed.
  - Add tests for ASS time shifting and alignment.
- **Primary files likely touched:**
  - `app/preview_playback.py`
  - `app/subtitle_renderers/ass_renderer.py`
  - `tests/test_preview_playback.py`
- **Implementation notes:**
  - Ensure timing shifts match preview slice logic.
- **Acceptance criteria:**
  - Preview playback matches export for word-highlight mode (feature no longer surfaced in the GUI).
  - Tests cover time shifting for ASS.
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

### Codex Task 9 — Implement karaoke ASS generation using aligned word timings (per-word highlight events) + tests
- **Goal:** Generate karaoke-style ASS with per-word highlight events. ✅ Done.
- **Scope:**
  - Use aligned word timings to emit ASS events/styles.
  - Add tests for word highlight generation.
- **Primary files likely touched:**
  - `app/subtitle_renderers/ass_karaoke.py`
  - `app/subtitle_renderers/ass_renderer.py`
  - `tests/test_ass_karaoke.py`
- **Implementation notes:**
  - Preserve RTL stability via embedding marks.
  - Use ASS `\k`/`\kf` or separate events depending on stability.
- **Acceptance criteria:**
  - Highlighted words match timing JSON.
  - RTL ordering remains stable in generated ASS.
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
- [x] Mode switch works; Static pipeline unchanged.
- [x] Highlight color is configurable and persists.

## Post-merge fixes
- Wrapped-line highlight fix: graphics overlay clip rects are now line-relative.

## G) Post-PR10 follow-ups (not required for PR10 merge)
- A) Highlight opacity control.
- B) Base text color control.
- C) Font family picker with Hebrew-safe defaults.
- D) Legacy parity note: Line/word background controls (including opacity/padding/radius) are implemented in the Subtitles Ready UI and used by the graphics renderer for preview stills and graphics overlay export. The legacy ASS/force_style fallback supports only line background via box settings and does not support word backgrounds or rounded corners.
- J) Alignment/performance optimizations (caching, preview-window-only alignment improvements).
- K) Packaging hardening for WhisperX deps (tie to packaging work).

## H) Tracking tables

### PR10 task tracking
| Task | Status | PR link | Notes |
| --- | --- | --- | --- |
| 1 | Done |  | Config keys + defaults for subtitle mode + highlight settings. |
| 2 | Done |  | Subtitle mode + highlight color controls in Subtitles-ready UI. |
| 3 | Done |  | ASS document generation + tests complete. |
| 4 | Done |  | Export defaults to graphics overlay rendering when enabled; legacy ASS (word highlight) is used only as a fallback if graphics overlay export is disabled (SUBTITLES_GRAPHICS_OVERLAY_EXPORT=0) or fails. |
| 5 | Done |  | Preview still uses the graphics renderer by default; legacy ASS (word highlight) or SRT+force_style (static) is used only as a fallback if graphics preview rendering fails. |
| 6 | Done |  | Preview playback uses shifted ASS + tests (GUI no longer exposes playback). |
| 7 | Done |  | Word timing JSON contract + staleness detection. |
| 8 | Done |  | WhisperX alignment worker added. |
| 9 | Done |  | Karaoke step-highlight ASS generation + tests. |
| 10 | Done |  | Default subtitle mode is Word highlight; docs + diagnostics updated. |

### Post-PR10 follow-up tracking
| Item | Status | Notes |
| --- | --- | --- |
| Highlight opacity control | TODO |  |
| Base text color control | TODO |  |
| Font family picker | TODO |  |
| Legacy parity note: Line/word background controls (including opacity/padding/radius) are implemented in the Subtitles Ready UI and used by the graphics renderer for preview stills and graphics overlay export. The legacy ASS/force_style fallback supports only line background via box settings and does not support word backgrounds or rounded corners. | TODO |  |
| Alignment/performance optimizations | TODO |  |
| WhisperX packaging hardening | TODO |  |
