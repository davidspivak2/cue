# Known Issues (Detailed Tracking)

Purpose:
- This file stores detailed bug write-ups (repro steps, expected vs actual, risks, and validation plans).
- Scheduling and priority stay in `docs/internal/ROADMAP.md`.

Working rules:
- Keep issue write-ups concrete and reproducible.
- Keep fixes scoped; do not change unrelated behavior.
- Update the matching ROADMAP queue item when status changes.

Status legend:
- `OPEN`: confirmed and not yet implemented.
- `IN PROGRESS`: implementation work is active.
- `BLOCKED`: waiting on dependency/decision.
- `DONE`: verified and regression-checked.

---

**Debug instrumentation cleanup:** completed on 2026-02-13. Re-check before release: grep for `agent log`, `hypothesis`, `_append_debug`.

---

## KI-001 - Export success actions do nothing (`Play video` / `Open folder`)

- Status: `DONE`
- Completed on: `2026-02-13`
- Priority: High
- Tracked in roadmap: Queue item 2 (`Export success actions reliability`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (`openLatestOutputVideo`, `openLatestOutputFolder`, success-strip button handlers)
  - `desktop/src-tauri/capabilities/main.json` (opener permission scopes)

User impact:
- After export succeeds, users click action buttons and nothing visible happens.
- This breaks confidence in completion state and forces manual file browsing.

Repro steps:
1. Start app via `scripts/run_desktop_all.cmd`.
2. Open a project, export video, and wait for success strip.
3. Click `Play video`, then click `Open folder`.

Expected:
- `Play video` opens the exported video in the default player.
- `Open folder` opens the folder containing the latest export.
- If open fails, UI shows a clear message.

Actual:
- RESOLVED. `Play video` and `Open folder` now execute reliably in desktop runtime.
- Open failures now show visible, retryable feedback instead of silent no-op.

Likely cause / notes:
- Root cause in desktop runtime was opener path permission/scope denial plus weak error surfacing.
- `openPath(...)` denials for user paths (for example Desktop exports) surfaced as opaque failures.

Implemented fix:
- `desktop/src/pages/Workbench.tsx`
  - Added explicit try/catch + non-blocking error banner (`workbench-open-action-error`) for success-strip actions.
  - Added robust error detail extraction for non-`Error` invoke payloads.
  - Added path normalization and candidate retries for slash variants.
  - Added `Open folder` fallback via `revealItemInDir(...)`.
- `desktop/src-tauri/capabilities/main.json`
  - Added scoped `opener:allow-open-path` entries for user output locations (`$HOME`, `$DESKTOP`, `$DOCUMENT`, `$DOWNLOAD`, `$VIDEO`, `$PICTURE`, `$PUBLIC`, `$TEMP`, `$APPDATA`, `$LOCALDATA`, `$APPLOCALDATA`).
  - Added `opener:allow-reveal-item-in-dir`.

Risks / regressions:
- Exports written outside allowed opener scopes may still require additional capability scope entries.
- Capability updates require a full Tauri app restart before behavior changes apply.

Validation checklist:
- [x] Success path opens file and folder in desktop runtime.
- [x] Failure path shows visible retryable feedback.
- [x] No regression to export completion state or re-export flow.

---

## KI-002 - Preview style does not match export (font/size/shadow)

- Status: `DONE`
- Completed on: `2026-02-13`
- Priority: High
- Tracked in roadmap: Queue item 3 (`Preview truthfulness`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (on-video preview styling)
  - `desktop/src/settingsClient.ts` (preview API client contract)
  - `app/graphics_overlay_export.py` (export rendering path)
  - `app/graphics_preview_renderer.py` (renderer parity context)
  - `app/backend_server.py` (`/preview-style`, `/preview-overlay`)

User impact:
- Users choose style in preview, but exported video looks different.
- This makes styling decisions unreliable.

Repro steps:
1. Create/export subtitles with custom font, size, and shadow.
2. Compare in-app preview against final exported frame.

Expected:
- Preview and export match for core style intent (font family, size, shadow, relative placement).

Actual:
- RESOLVED. Workbench preview now uses backend Qt-rendered subtitle overlay output for visible playback styling.
- Font family/size/shadow rendering intent now matches export renderer behavior for the same style payload.

Likely cause / notes:
- Root cause is renderer mismatch:
  - Workbench preview currently uses browser HTML/CSS text rendering.
  - Export uses Qt path/text rendering (`render_graphics_preview`) in backend worker paths.
- Known behavior differences that create visible drift:
  - Shadow semantics differ (CSS blur shadow vs Qt translated fill/shadow behavior).
  - Font metrics and text layout can differ between browser and Qt.
  - Browser-space sizing differs from video-pixel render sizing.

Minimum-scope fix:
- Make Workbench preview use the same Qt renderer as export for visible subtitle appearance.
- Add backend `POST /preview-overlay` endpoint that returns a transparent subtitle overlay PNG generated by `render_graphics_preview(...)`.
- In Workbench, render returned overlay image above video with `object-contain` and keep HTML subtitle layer only for edit-mode interactions.
- Keep subtitle style contract unchanged; move rendering parity to shared backend path.
- Add parity validation using one or more golden clips.

Implemented fix:
- `app/backend_server.py`
  - Added `POST /preview-overlay` and `PreviewOverlayRequest`.
  - Renders transparent overlay PNGs via `render_graphics_preview(...)` and caches by style/text/size signature.
- `desktop/src/settingsClient.ts`
  - Added `previewOverlay(...)` API client contract.
- `desktop/src/pages/Workbench.tsx`
  - Requests overlay for active cue + style state and displays it over video with `object-contain`.
  - Keeps interactive HTML subtitle layer for edit mode; playback path uses renderer-accurate image overlay.
  - Falls back to HTML preview when overlay request fails, so preview remains usable.
- `tests/test_backend_server.py`
  - Added backend test coverage for overlay path generation/cache reuse.
- `desktop/tests/e2e/workbench-shell.spec.ts`
  - Updated mocks/assertions for image-overlay preview path.

Risks / regressions:
- Font availability/fallback differences between runtime surfaces.
- Overlay generation latency or cache churn could affect smoothness if not cached.
- Overlay positioning must match video letterboxing behavior at all window sizes.
- Tightening parity could expose hidden layout assumptions in existing projects.

Validation checklist:
- [x] Golden clip comparison for font/size/shadow at default and non-default styles.
- [x] Compare Workbench preview frame vs exported frame at same timestamp for at least one default and one custom style profile.
- [x] Resize window across common widths and confirm subtitle-to-video proportion remains stable.
- [x] Verify fallback path: if overlay render request fails, preview remains usable (non-fatal).
- [x] No regressions to export rendering correctness.

---

## KI-003 - Subtitle preview does not scale with video during window resize

- Status: `DONE`
- Completed on: `2026-02-13`
- Priority: High
- Tracked in roadmap: Queue item 3 (`Preview truthfulness`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (subtitle overlay size/position logic)
  - `app/backend_server.py` (`/preview-overlay`)

User impact:
- When video shrinks/grows on resize, subtitle size stays fixed, so preview is misleading.

Repro steps:
1. Open Editor with subtitles visible.
2. Resize app window wider/narrower.
3. Observe video and subtitle relative scale.

Expected:
- Subtitle overlay scales proportionally with rendered video size.

Actual:
- RESOLVED. Subtitle preview now scales with rendered video viewport during window resize.
- Overlay presentation remains proportionally aligned with the video frame while preserving style intent.

Likely cause / notes:
- Preview subtitle sizing is tied to static values without viewport-relative scaling.

Implemented fix:
- Workbench now displays a backend-rendered subtitle overlay image for playback preview.
- Overlay is rendered at video-native dimensions and displayed with `object-contain`, matching the video viewport behavior across resize states.

Minimum-scope fix:
- Make preview subtitle sizing proportional to rendered video viewport.
- Preserve style intent while scaling.

Risks / regressions:
- Could affect edit-shell readability if scaling is applied uniformly.
- Extreme aspect ratios may need clamping rules.

Validation checklist:
- [x] Resize tests across common window widths.
- [x] Relative subtitle-to-video proportion stays stable.
- [x] No edit-mode legibility regression.

---

## KI-004 - Word highlight drift in preview (export timing is correct)

- Status: `OPEN`
- Priority: High
- Tracked in roadmap: Queue item 4 (`Preview word-highlight sync`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (preview highlighted word index calculation)
  - `app/workers.py` / word timing artifacts (export timing source)

User impact:
- In preview playback, highlight can lead or lag speech.
- Users may think timing is broken even when export is correct.

Repro steps:
1. Run Create subtitles on a clip with word highlight mode enabled.
2. Play preview in Editor and watch word-by-word highlight timing.
3. Export and compare final timing behavior.

Expected:
- Preview highlight timing tracks spoken words similarly to final export.

Actual:
- Preview highlight timing drifts; exported timing appears correct.

Likely cause / notes:
- Preview likely uses evenly distributed cue progress instead of timed-word boundaries.

Minimum-scope fix:
- Drive preview highlight from the same timed-word artifacts used by export.
- Keep export behavior unchanged.

Risks / regressions:
- Missing/stale timing artifacts need safe fallback behavior.
- Boundary transitions can flicker if rounding is inconsistent.

Validation checklist:
- Known timing clips show aligned preview transitions.
- Export output remains unchanged and correct.

---

## KI-005 - RTL edit textarea punctuation/caret behavior (Hebrew)

- Status: `OPEN`
- Priority: High
- Tracked in roadmap: Queue item 5 (`Subtitle edit-mode reliability`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (inline edit textarea and direction handling)

User impact:
- In edit mode, punctuation and caret navigation feel reversed/wrong for Hebrew text.
- Users risk introducing text errors while editing.

Repro steps:
1. Open an RTL subtitle (Hebrew) in inline edit mode.
2. Place punctuation at sentence end.
3. Move caret with arrow keys.

Expected:
- Punctuation remains logically correct.
- Arrow-key movement feels natural for RTL editing.

Actual:
- Comma/terminal punctuation can appear at wrong side; arrow navigation feels reversed.

Likely cause / notes:
- Direction and bidi behavior for textarea edit mode is not fully aligned with RTL editing expectations.

Minimum-scope fix:
- Adjust textarea directional/bidi handling for RTL content.
- Keep non-edit preview/export behavior untouched.

Risks / regressions:
- Mixed LTR/RTL lines can be sensitive to bidi tweaks.
- Keyboard behavior may vary by OS/input method.

Validation checklist:
- Hebrew-only and mixed-direction subtitle samples.
- Punctuation placement and caret motion remain stable across save/cancel paths.

---

## KI-006 - 3-line subtitle is clipped/missing in inline edit mode

- Status: `OPEN`
- Priority: High
- Tracked in roadmap: Queue item 5 (`Subtitle edit-mode reliability`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (inline textarea row sizing and edit state)

User impact:
- Third line is not visible/editable in edit mode for 3-line subtitles.
- This is a direct data-editability issue.

Repro steps:
1. Select a subtitle cue with 3 text lines.
2. Enter inline edit mode.
3. Check whether all lines are visible/editable.

Expected:
- All cue lines are visible and editable.

Actual:
- Bottom line is partially or fully missing.

Likely cause / notes:
- Row/height/overflow behavior is clipping text in edit textarea.

Minimum-scope fix:
- Ensure textarea dimensions always fit full cue text (with safe max/scroll fallback).

Risks / regressions:
- Larger cues could make editor too tall without sensible clamping.

Validation checklist:
- 1-line, 2-line, 3-line, and 4+ line cue cases.
- Save/cancel/undo behavior unaffected.

---

## KI-007 - Clicking Play during edit should auto-save and exit edit mode

- Status: `OPEN`
- Priority: Medium
- Tracked in roadmap: Queue item 5 (`Subtitle edit-mode reliability`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (play/pause controls + inline edit save flow)

User impact:
- Current behavior can leave users unsure whether edits are saved when resuming playback.

Repro steps:
1. Enter inline edit mode on active subtitle.
2. Change text.
3. Click Play without clicking Save/Cancel/Undo.

Expected:
- App auto-saves, exits edit mode, and resumes playback immediately.

Actual:
- Behavior does not currently guarantee this flow.

Likely cause / notes:
- Play action and edit-save lifecycle are not coordinated.

Minimum-scope fix:
- Add guarded auto-save-on-play path for active inline edits.

Risks / regressions:
- Potential double-save if save is already in progress.
- Need clear fallback when save fails.

Validation checklist:
- Play during edit saves once and resumes playback.
- Save failure keeps user informed and prevents silent data loss.

---

## KI-008 - Workbench tabs do not look like browser/Figma tabs

- Status: `OPEN`
- Priority: Medium
- Tracked in roadmap: Queue item 12 (`Editor shell affordance polish`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (current tab strip rendering)
  - `desktop/src/workbenchTabs.tsx` (tab state)

User impact:
- Tab strip feels like pill buttons instead of true project tabs.
- Reduces visual clarity for multi-project workflow.

Repro steps:
1. Open multiple projects.
2. View Workbench tab strip.

Expected:
- Active tab looks attached to content (browser/Figma style), with clear active/inactive distinction.

Actual:
- Tabs look like chips/pills rather than attached tabs.

Likely cause / notes:
- Current class styling favors chip visuals over attached-tab semantics.

Minimum-scope fix:
- Update tab-strip visual contract (style-only where possible).

Risks / regressions:
- Responsive wrapping and truncation behavior must remain stable.

Validation checklist:
- Multi-tab state at narrow/wide widths.
- Active tab remains obvious and keyboard navigation remains intact.

---

## KI-009 - Interactive controls need consistent pointer cursor feedback

- Status: `OPEN`
- Priority: Medium
- Tracked in roadmap: Queue item 12 (`Editor shell affordance polish`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (interactive surfaces)
  - shared UI controls in `desktop/src/components/ui/`

User impact:
- Inconsistent cursor feedback makes clickable controls less obvious.

Repro steps:
1. Hover buttons, clickable labels, and tab controls across Editor.
2. Compare cursor behavior on interactive vs text-entry areas.

Expected:
- Interactive elements show pointer cursor.
- Text-entry surfaces show I-beam.

Actual:
- Cursor affordance is inconsistent in some areas.

Likely cause / notes:
- Missing or mixed cursor classes on interactive wrappers.

Minimum-scope fix:
- Normalize cursor semantics across core interactive controls.

Risks / regressions:
- Must avoid overriding I-beam on editable text surfaces.

Validation checklist:
- Cursor behavior audit across tab strip, action buttons, style pane controls, and subtitle edit surfaces.

---

## KI-010 - Style pane scrollbar should be thinner thumb-only (reduced chrome)

- Status: `OPEN`
- Priority: Medium
- Tracked in roadmap: Queue item 11 (`Style pane modernization`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (style pane scroll containers)
  - `desktop/src/components/ui/scroll-area.tsx` (if standardized scrollbar path is used)

User impact:
- Current scrollbar treatment feels heavy/noisy in style pane.

Repro steps:
1. Open style pane with enough controls to scroll.
2. Inspect scrollbar visuals.

Expected:
- Thin thumb-first scrollbar with minimal background chrome.

Actual:
- Scrollbar visuals are heavier than desired.

Likely cause / notes:
- Current pane uses default overflow scroll behavior rather than a tuned style pattern.

Minimum-scope fix:
- Apply consistent thin-thumb scrollbar treatment in style pane contexts.

Risks / regressions:
- Accessibility and hit target size on high-DPI displays.

Validation checklist:
- Scroll usability with mouse wheel/trackpad/drag.
- No horizontal overflow regressions.

---

## KI-011 - Style pane collapsed-strip entry + icon-only overlay close

- Status: `OPEN`
- Priority: Medium
- Tracked in roadmap: Queue item 11 (`Style pane modernization`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (right panel and overlay drawer controls)

User impact:
- Requested right-pane interaction model is not fully met:
  - wide layout collapsed strip with icon entry is missing
  - overlay close uses text button (`Close`) instead of icon-only `X`

Repro steps:
1. Use Editor at wide width and inspect right style pane behavior.
2. Use narrow overlay mode and inspect close affordance.

Expected:
- Wide layout supports collapsed vertical strip with icon entry to open style overlay.
- Overlay closes via icon-only `X`.

Actual:
- Collapsed strip entry is not present.
- Overlay close affordance is text button.

Likely cause / notes:
- Current implementation supports docked panel/overlay but not collapsed-strip mode.

Minimum-scope fix:
- Add collapsed-strip state and icon entry behavior.
- Replace text close button with icon-only `X`.

Risks / regressions:
- Overlay coordination (left/right panel interactions) must stay stable.

Validation checklist:
- Wide and narrow behavior both work.
- Keyboard close (`Esc`) and scrim behavior unchanged.

---

## KI-012 - Subtitle edit affordance is too hidden

- Status: `OPEN`
- Priority: Medium
- Tracked in roadmap: Queue item 5 (`Subtitle edit-mode reliability`)
- Primary code pointers:
  - `desktop/src/pages/Workbench.tsx` (active subtitle non-edit shell styles/hover states)

User impact:
- Users may not discover quickly that subtitle text is directly editable on video.

Repro steps:
1. Open Editor with subtitles visible.
2. Observe subtitle area without prior instruction.

Expected:
- Editability is discoverable quickly but still subtle.

Actual:
- Editability is easy to miss.

Likely cause / notes:
- Current hover/focus affordance is present but too low-signal for first-time users.

Minimum-scope fix:
- Slightly strengthen affordance (visual hint and/or microcopy/tooltip) without adding clutter.

Risks / regressions:
- Overly strong styling can make normal playback look noisy.

Validation checklist:
- First-use discoverability improves in manual QA.
- Visual treatment remains subtle during playback.

---

## Capture checklist for issue evidence

- Export success strip click behavior recording (`Play video`, `Open folder`).
- Preview vs export comparison frame(s) showing font/size/shadow mismatch.
- Window resize recording showing subtitle/video relative-scale behavior.
- Preview word-highlight drift clip.
- RTL inline edit clip showing punctuation/caret behavior.
- 3-line cue inline edit clipping screenshot.
