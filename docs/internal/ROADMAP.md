# Project Roadmap (Single Source of Truth)

Note: Tauri migration tracking lives in `docs/internal/TAURI_REACT_OVERHAUL_PLAN.md`; this roadmap is for product/pipeline priorities.
Terminology note: the user-facing screen label is now **"Projects"** (same screen/route previously labeled "Project Hub").

## Rules
- This file is the ONLY place to look for “what to do next”.
- Detailed bug write-ups, repro steps, and issue-level validation notes live in `docs/internal/KNOWN_ISSUES.md`.
- If work is not listed here, it is not scheduled.
- The UX spec defines target behavior; this file defines implementation order and acceptance criteria.
- Each work item must include: Status, Deliverable, Acceptance criteria, and UX spec reference (section name).
- Example UX spec reference format: UX spec reference: H) Error UX + Diagnostics

## Now / Next (Queue)
(Use a numbered list. Status tags must be one of: NEXT, IN PROGRESS, BLOCKED, DONE.)

1. [DONE] PR13 — Packaging hardening / smoke tests
   - Deliverable:
     - Packaging flow hardened for release and smoke tests run against packaged builds.
   - Current status:
     - MSI and NSIS installer builds work; packaged smoke path passes.
   - Acceptance criteria:
     - Packaged build launches and completes the golden-path smoke test without regressions.
     - NSIS `.exe` installer build succeeds without relying on MSI-only fallback.
   - UX spec reference: N/A (engineering / packaging)

2. [NEXT] Export success actions reliability (Workbench success strip)
   - Deliverable:
     - `Play video` and `Open folder` actions in Workbench success state reliably trigger OS open behavior in the desktop app.
     - If open-path actions fail, users get immediate, visible, non-blocking feedback instead of silent no-op behavior.
   - Acceptance criteria:
     - After a successful export, `Play video` opens the latest exported file and `Open folder` opens the containing folder.
     - Failure paths provide a clear retryable message without breaking the rest of the Editor flow.
   - UX spec reference: G) Export progress + success (in-Editor)

3. [NEXT] Preview truthfulness (style parity + responsive scaling)
   - Deliverable:
     - Preview subtitle styling is aligned with export output for core appearance fields (font family, font size, shadow treatment, and relative placement).
     - Subtitle overlay scales proportionally with the video viewport when the app window is resized.
   - Acceptance criteria:
     - Resizing the app window changes subtitle size proportionally with video size (no fixed-size subtitle drift).
     - Golden-path preview vs export checks show no material mismatch for font size/family/shadow rendering intent.
   - UX spec reference: E) Editor; G) Export progress + success

4. [NEXT] Preview word-highlight sync (preview-only)
   - Deliverable:
     - In-app preview highlight progression uses timed-word artifacts when available instead of evenly distributing highlight by cue duration.
     - Export timing behavior remains unchanged by this item.
   - Acceptance criteria:
     - On known test clips, preview highlight transitions track spoken words without obvious lead/lag drift.
     - Export output timing remains unchanged and regression-free.
   - UX spec reference: F) Create Subtitles pipeline contract; E) Editor

5. [NEXT] Subtitle edit-mode reliability (data integrity + RTL + play-resume behavior)
   - Deliverable:
     - Inline editor always shows full cue text (including three-line cues) so every line is editable.
     - Edit textarea behavior for Hebrew/RTL text keeps punctuation placement and arrow-key movement intuitive.
     - Clicking `Play` while edit mode is active auto-saves, exits edit mode, and resumes playback immediately.
     - Edit affordance becomes more obvious while staying subtle and non-distracting.
   - Acceptance criteria:
     - Three-line cues are fully visible and editable in the inline textarea.
     - RTL edit sessions keep comma/terminal punctuation placement correct and arrow-key navigation predictable.
     - `Play` from active edit mode saves once, exits edit mode, and resumes playback without extra prompts.
   - UX spec reference: E) Editor

6. [NEXT] PR12 — Support UX v1 (error details + copy diagnostics + hosted send logs)
   - Deliverable:
     - Error UI includes a details drawer and a “Copy diagnostics” action.
     - Settings support surface includes hosted “Send logs” with explicit user consent.
     - Diagnostics tools remain in Settings only (error UI may show details, not tools).
   - Acceptance criteria:
     - Trigger an error: user can open details drawer and copy diagnostics text.
     - User can send logs via a hosted receiver after seeing a clear consent summary of what will be shared.
     - Log payload excludes rendered video output and redacts sensitive local-path data where possible.
     - If upload fails, user still has a visible fallback path (`Copy diagnostics`).
   - UX spec reference: H) Error UX + Diagnostics; J) Settings page

7. [NEXT] PR15 — Clarity pass (plain-language labels + CTA reduction)
   - Deliverable:
     - Copy polish applied and CTA reduction pass completed across UI surfaces.
     - User-facing label updates include replacing technical wording (for example, Workbench/Editor naming) and ambiguous statuses (for example, `Ready`).
   - Acceptance criteria:
     - Strings match the approved copywriting glossary and CTA count is minimized per spec.
     - Project and Editor statuses read clearly for non-technical users, with no ambiguous standalone labels.
   - UX spec reference: K) Copywriting glossary (approved strings); D) Projects; E) Editor

8. [NEXT] Navigation simplification — remove global left sidebar and standardize top-level header behavior
   - Deliverable:
     - Global left sidebar is removed from the redesign flow.
     - Header/back/title/status placement is consistent across Projects, Editor, and Settings.
     - Settings entry remains discoverable from all primary surfaces when navigation is allowed.
   - Acceptance criteria:
     - App remains fully navigable without the left sidebar.
     - No duplicate app/page headings or duplicated video-name labels appear in Editor.
     - Editor back button appears in a consistent top-left location.
   - UX spec reference: B) Top-level navigation model; E) Editor

9. [NEXT] Progress truthfulness + continuity (Create Subtitles and Export)
   - Deliverable:
     - Progress surface reflects pre-transcription work instead of appearing stuck at 0%.
     - If user leaves Editor during an active task, background progress remains visible from other pages.
     - Checklist row detail text is displayed inline with clearer hierarchy.
   - Acceptance criteria:
     - Progress does not remain static at 0% during long startup phases without explanatory detail.
     - User can navigate back to Projects and still see active-task state/progress.
     - Editor progress copy and row details match actual backend work steps.
   - UX spec reference: F) Create Subtitles pipeline contract; G) Export progress + success

10. [NEXT] Settings clarity pass
   - Deliverable:
     - Transcription quality control is redesigned as clear choice cards with plain-language hints.
     - “Always save to this folder” and its path controls are visually grouped.
     - Punctuation + audio controls are merged into one understandable section.
     - “Keep extracted WAV file” is removed; extracted WAV is auto-cleaned.
     - Theme toggle is exposed in Settings.
   - Acceptance criteria:
     - Non-technical users can understand each transcription-quality option without prior knowledge.
     - Save-folder controls are only shown/enabled where policy context is explicit.
     - No user-facing control remains for keeping extracted WAV files.
   - UX spec reference: J) Settings page

11. [NEXT] Style pane modernization (usability + defaults + overlay affordances)
   - Deliverable:
     - Style controls are reorganized for lower cognitive load (spacing, grouping, progressive disclosure).
     - Background mode uses a segmented control pattern.
     - Curated font set prioritizes reliable Hebrew rendering.
     - Color controls support presets + custom picker, with optional hex entry for advanced users.
     - Default color sets are revised per option so defaults remain legible and sensible.
     - Style overlay uses an icon-only `X` close affordance, and wide layout supports a collapsed vertical strip entry point that opens style as overlay.
     - Style pane scrolling uses a thinner thumb-first treatment with reduced visual chrome.
   - Acceptance criteria:
     - Style pane is usable without opening advanced controls for common edits.
     - Fonts listed in the control produce visibly distinct, supported rendering outcomes.
     - Color controls provide predictable preset and custom behavior without regressions.
     - Overlay close/open affordances are obvious and consistent across wide/narrow layouts.
   - UX spec reference: E) Editor; J) Settings page; K) Copywriting glossary

12. [NEXT] Editor shell affordance polish (tabs + cursor semantics)
   - Deliverable:
     - Open-project tabs in Editor use browser/Figma-style tab treatment (not pill chips).
     - Interactive controls consistently use pointer cursor affordance, while text-editing surfaces retain I-beam behavior.
   - Acceptance criteria:
     - Active tab appears visually attached to the content surface and clearly distinct from inactive tabs.
     - Cursor feedback matches interaction type across Editor controls with no regressions in text-edit zones.
   - UX spec reference: E) Editor; I) State machine

13. [NEXT] Editor/Projects micro-interaction polish
   - Deliverable:
     - Delete dialog appears without side-swoop animation.
     - Delete-success feedback uses toast behavior (not persistent inline banner).
     - Empty Projects state shows one primary “New project” action.
     - Edit action buttons do not shift subtitle layout when they appear.
     - Editor status appears next to video name to strengthen meaning.
     - Native video control affordances are simplified, including playback-speed discoverability.
   - Acceptance criteria:
     - Deleting a project produces transient confirmation and no sticky banner.
     - Empty-state and non-empty-state CTA rules never show duplicate create actions.
     - Entering subtitle edit mode does not cause disorienting subtitle jump.
   - UX spec reference: D) Projects; E) Editor; G) Export progress + success

14. [NEXT] Export optimization — cache video stream info earlier + cheap revalidate; remove/adjust “Getting video info” checklist row if appropriate
   - Deliverable:
     - Video stream info cached earlier; export path uses cheap revalidation.
     - “Getting video info” checklist row removed or adjusted if no longer accurate.
   - Acceptance criteria:
     - Export step uses cached stream info with a fast revalidation pass; UI checklist reflects the actual work.
   - UX spec reference: G) Export progress + success (in-Editor)

15. [DONE] Redesign Milestone 1 — Project system backend (persistence + multi-project)
   - Deliverable: app can create/open multiple projects with persisted state across restarts.
   - Acceptance criteria: see Milestone 1 checklist below.
   - UX spec reference: C) Project model (new backend capability; document behavior)

## Milestones (Ordered to Completion)

### Milestone 0 — Stabilization
0.1 PR12 — Support UX v1 (error details + copy diagnostics + hosted send logs)
- Deliverable:
  - Error UI includes a details drawer and a “Copy diagnostics” action.
  - Settings provides a hosted “Send logs” support action with explicit consent and redaction summary.
  - Diagnostics tools remain in Settings only.
- Acceptance criteria:
  - Trigger an error: user can open details drawer and copy diagnostics text.
  - User can submit logs to hosted support without attaching video outputs.
  - Upload failure path keeps a clear fallback (`Copy diagnostics`) visible.
  - No diagnostics tools appear outside Settings.

0.2 PR13 — Packaging hardening / smoke tests
- Deliverable:
  - Packaging flow hardened for release and smoke tests run against packaged builds.
- Current status:
  - MSI and NSIS builds pass; packaged smoke flow passes.
- Acceptance criteria:
  - Packaged build launches and completes the golden-path smoke test without regressions.
  - NSIS `.exe` build succeeds in the default `npm run tauri build` path.

0.3 PR15 — Clarity pass (plain-language labels + CTA reduction sweep)
- Deliverable:
  - Copy polish applied and CTA reduction pass completed across UI surfaces.
  - Replace technical/ambiguous labels with plain-language wording.
- Acceptance criteria:
  - Strings match the approved copywriting glossary and CTA count is minimized per spec.
  - “Ready” and other ambiguous labels are replaced with user-meaningful statuses.

0.4 Export optimization — cache video stream info earlier + cheap revalidate; adjust “Getting video info” checklist row if appropriate
- Deliverable:
  - Video stream info cached earlier; export path uses cheap revalidation.
  - “Getting video info” checklist row removed or adjusted if no longer accurate.
- Acceptance criteria:
  - Export step uses cached stream info with a fast revalidation pass; UI checklist reflects the actual work.

0.5 Export success actions reliability (Workbench success strip)
- Deliverable:
  - `Play video` and `Open folder` actions reliably open the expected file/folder in desktop app builds.
  - Failure paths show clear user feedback instead of silent no-op behavior.
- Acceptance criteria:
  - Successful export state can open the latest output file and containing folder from Workbench.
  - Open failures surface visible retryable feedback and do not break Editor state.

0.6 Preview truthfulness: style parity + responsive scaling
- Deliverable:
  - Preview subtitle styling aligns with export styling intent for font family/size, shadow, and relative positioning.
  - Subtitle overlay scales proportionally with the rendered video viewport during window resize.
- Acceptance criteria:
  - Resizing the window does not leave subtitles at a fixed size while video scales.
  - Golden-path parity checks show no material preview/export mismatch in core style fields.

0.7 Preview word-highlight sync (preview-only)
- Deliverable:
  - Preview highlight progression uses timed-word artifacts when available.
  - Export timing logic remains unchanged by this milestone item.
- Acceptance criteria:
  - Preview highlight transitions track spoken words without obvious drift on known clips.
  - Export timing remains correct and regression-free.

0.8 Edit-mode reliability fixes (inline editor)
- Deliverable:
  - Inline editor displays full text for multi-line cues (including 3-line cues).
  - RTL/Hebrew inline edit behavior preserves punctuation placement and intuitive arrow-key motion.
  - Clicking `Play` during active edit auto-saves and exits edit mode before playback resumes.
- Acceptance criteria:
  - Three-line cues are fully visible/editable in edit mode.
  - RTL punctuation and caret behavior are correct in edit textarea.
  - `Play` from edit mode saves once, exits edit mode, and resumes playback immediately.

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
  - Open/close project tabs
  - Delete project from Projects with confirmation (project data only; source video file remains untouched)
  - Relink missing source video workflow
- Acceptance criteria:
  - Deleting a project removes its project record/artifacts and it no longer appears in the project list.
  - If source video is missing, app shows missing state and relink succeeds.

1.3 Project status model
- Deliverable:
  - Status enum: Needs video / Needs subtitles / Needs edits / Exporting / Done / Missing file (API values remain `needs_video` / `needs_subtitles` / `ready` / `exporting` / `done` / `missing_file`; user-facing label for `ready` becomes “Needs edits”)
- Acceptance criteria:
  - Status is correct for each stage and survives restart.

Definition of done:
- User can manage multiple projects across restarts and relink missing video without breaking the project.

### Milestone 2 — Projects UI (new entry point)
2.1 Projects screen
- Deliverable:
  - Grid of project cards, primary CTA “New project”, drag-and-drop onto hub
- Acceptance criteria:
  - Launch opens Projects; “New project” works; DnD works.

2.2 Card content + interactions
- Deliverable:
  - Thumbnail, filename (no full path), duration, status label
  - Click opens/activates Editor tab
  - Missing file shows Relink action
- Acceptance criteria:
  - All card fields render and actions work.

2.3 Launch behavior
- Deliverable:
  - App always launches to Projects (no auto-open last project)
- Acceptance criteria:
  - Restart app: Projects is shown.

2.4 Global shell simplification (sidebar removal)
- Deliverable:
  - Remove global left sidebar from the redesign flow.
  - Use a consistent header contract across Projects, Editor, and Settings (top-left back behavior + stable title region + consistent settings affordance).
  - Remove duplicated page/app headings and duplicate video-name label surfaces.
- Acceptance criteria:
  - Navigation remains clear without a left nav (Projects -> Editor -> Settings -> Back).
  - Editor back button and title placement are consistent and stable across states.
  - Settings remains reachable when not blocked by long-running task rules.

2.5 Projects micro-interaction polish
- Deliverable:
  - Delete confirmation dialog appears without side-swoop entrance animation.
  - Delete success uses toast feedback (not a persistent inline banner).
  - Empty state and non-empty state never show duplicate “New project” actions.
- Acceptance criteria:
  - Deleting a project gives transient confirmation and the message auto-clears.
  - Empty-state layout has one clear primary CTA.
  - Standard (non-empty) layout keeps top-right “New project” behavior unchanged.

Definition of done:
- Projects is the stable home screen and projects open into Editor.

### Milestone 3 — Editor shell (unified edit + style + preview + export; internal route/state naming may still use Workbench)
3.1 Editor layout regions
- Deliverable:
  - Center video preview
  - Left “All subtitles” panel (currently hidden/paused in implementation to protect preview size; overlay-only when re-enabled)
  - Right style inspector
- Acceptance criteria:
  - Workbench tab shows these regions with stable sizing.

3.2 Left panel responsive behavior
Status: Deferred while left panel remains hidden/paused.
- Deliverable:
  - Collapsed by default
  - Docked at wide widths, resizable, per-project persisted width
  - Overlay drawer under 1100px with scrim + Esc closes
  - Only one overlay open at a time (left vs right)
- Acceptance criteria:
  - Resize window around threshold: dock/overlay rules work exactly once left panel is re-enabled.

3.3 Right panel responsive behavior
- Deliverable:
  - Docked wide; overlay narrow via “Style” button
  - No horizontal scroll
- Acceptance criteria:
  - Narrow width: style panel becomes overlay; content still accessible.

3.4 Editor header orientation fixes
- Deliverable:
  - Back button remains in the top-left header region.
  - Page title is top-left aligned in the primary header flow.
  - Status appears adjacent to video name for clear association.
  - Duplicate workbench/video labels are removed.
- Acceptance criteria:
  - Users can identify page, current video, and status without scanning multiple header regions.
  - Header layout remains stable across no-subtitles, in-progress, and ready/export states.

3.5 Editor tab strip clarity + cursor semantics
- Deliverable:
  - Open project tabs in Editor adopt browser/Figma-style attached-tab visuals (not pill chips).
  - Interactive controls use pointer cursor affordance consistently; text-entry surfaces retain I-beam behavior.
- Acceptance criteria:
  - Active tab appears visually connected to content and clearly distinct from inactive tabs.
  - Cursor affordances match interaction type without regressions in subtitle text-edit zones.

Definition of done:
- Editor behaves correctly across window sizes and supports the unified workflow.

### Milestone 4 — In-app subtitle text editing (partially implemented)
Current status: Milestone 4.2 is implemented in Workbench, and Milestone 4.3 is implemented for the on-video path; Milestone 4.1 remains.
4.1 Left list editing
- Deliverable:
  - Each row shows timestamps (read-only) + editable text
  - Clicking row seeks video + selects subtitle
- Acceptance criteria:
  - Edit text, seek + selection sync works.

4.2 On-video editing contract
- Deliverable:
  - Hover active subtitle → input-like shell + I-beam cursor
  - Single click active subtitle while playing → pause + immediate inline edit
  - Inline editor includes icon actions: Save (check), Undo, Cancel (x)
  - Enter saves, Esc cancels, Ctrl/Cmd+Z undoes
  - Save/Cancel exits edit mode and resumes playback from the paused position
- Acceptance criteria:
  - Interactions match exactly (single-click edit + icon controls + keyboard parity).
  - No accidental exports of selection styling.

4.3 Selection styling contract
- Deliverable:
  - Accent outline indicates selection only; never exported
  - List selection and on-video selection remain in sync
- Acceptance criteria:
  - Export shows no selection outline.

4.4 Edit action stability
- Deliverable:
  - Save/Undo/Cancel controls appear without pushing subtitle text vertically.
- Acceptance criteria:
  - Entering and exiting edit mode does not shift subtitle position unexpectedly.

4.5 Edit-mode reliability and discoverability
- Deliverable:
  - Inline editor always shows full cue text (including three-line cues) with no clipped lines.
  - RTL/Hebrew edit behavior keeps punctuation placement and arrow-key movement intuitive.
  - Clicking `Play` while inline edit is active auto-saves and exits edit mode before playback continues.
  - Edit affordance remains subtle but easier to discover at first glance.
- Acceptance criteria:
  - Three-line cues are fully visible/editable in edit mode.
  - RTL edit sessions keep punctuation placement/caret navigation correct.
  - `Play` from edit mode saves once and resumes playback without extra prompts.

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
  - Progress checklist includes “Matching individual words to speech”
  - Pre-transcription startup work is surfaced instead of appearing idle at 0%.
- Acceptance criteria:
  - Step appears and reports progress accurately.
  - During startup, progress/detail text reflects active work (no unexplained 20-30s stall at 0%).

5.3 Export behavior enforcement
- Deliverable:
  - Export does not normally run WhisperX.
  - If word highlight selected but timings missing/stale, export is blocked with instructions to re-run “Create Subtitles”.
- Acceptance criteria:
  - Export path never silently runs WhisperX in normal success path.

5.4 Progress detail readability contract
- Deliverable:
  - Checklist row detail text appears inline to the right of each step label with clear separation.
- Acceptance criteria:
  - Row label and detail are visually associated (single-line at common widths, with graceful wrap fallback).
  - Detail text updates never shift checklist rows in a disorienting way.

Definition of done:
- Word highlight mode is ready immediately after subtitle creation; export uses existing timings.

### Milestone 6 — Editor CTAs + export UX (in-Editor)
6.1 CTA placement rules
- Deliverable:
  - Bottom action bar exists only in “Subtitles ready” and “Export success”
  - Bottom bar has only “Create video with subtitles”
  - Earlier states show “Create subtitles” in main content area (no bottom bar)
- Acceptance criteria:
  - UI matches these CTA rules across states.

6.2 Export progress in Editor
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

6.4 Background task continuity when leaving Editor
- Deliverable:
  - If user clicks Back during active subtitle creation/export, task continues in the background unless explicitly cancelled.
  - Projects surface shows active-task state so users can see work is still running.
- Acceptance criteria:
  - Back navigation does not silently abandon active work.
  - User can return to the same project and see synchronized progress state.

6.5 Playback-speed control discoverability
- Deliverable:
  - Playback speed is discoverable without relying on hidden overflow menu affordances.
- Acceptance criteria:
  - Users can change playback speed from the main video-control surface.

Definition of done:
- Export is an Editor flow and matches the UX contract.

### Milestone 7 — Settings integration rules + busy-state rules
7.1 Settings navigation rules
- Deliverable:
  - Settings accessible from Projects + Editor
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

7.4 Settings clarity restructure
- Deliverable:
  - Transcription quality is presented as four plain-language cards with helper hints.
  - Save-subtitles path controls are grouped directly under “Always save to this folder”.
  - Punctuation and audio controls are merged into one section with clear intent-first wording.
  - “Keep extracted WAV file” control is removed (auto-delete behavior only).
- Acceptance criteria:
  - Users can explain option trade-offs without technical terms.
  - Save-path controls are obviously tied to the selected policy.
  - No setting remains that can preserve extracted WAV files.

7.5 Theme and support access in Settings
- Deliverable:
  - Theme toggle (Light/Dark/System) is available in Settings.
  - Hosted Send Logs action is available in Settings support area.
- Acceptance criteria:
  - Theme can be changed without leaving Settings.
  - Send Logs flow includes consent summary and clear success/failure feedback.

Definition of done:
- App obeys navigation + busy-state rules.

### Milestone 8 — Visual system conformance pass
8.1 Token alignment (radius, borders, typography scale)
- Deliverable:
  - Radius, border, and typography tokens aligned with UX spec.
- Acceptance criteria:
  - Visual tokens match the UX spec and no regressions remain.

8.2 Focus/hover/disabled states compliance
- Deliverable:
  - Focus, hover, and disabled states conform to the UX spec.
- Acceptance criteria:
  - UI interaction states match UX spec behaviors.

8.3 Remove remaining old UI surfaces
- Deliverable:
  - Legacy UI surfaces replaced by redesign components.
- Acceptance criteria:
  - No old UI surfaces remain in the redesign flow.

8.4 Style pane modernization pass
- Deliverable:
  - Replace dense or ambiguous style controls with clearer grouped controls and spacing.
  - Use segmented control for background mode selection.
  - Curate font list for visual distinction and Hebrew support.
  - Standardize color option UX with presets + custom picker (+ optional advanced hex input).
  - Define sensible default color sets per style option.
  - Style overlay close control uses icon-only `X`; wide layout supports collapsed vertical strip entry to reopen style as overlay.
  - Style pane scrollbar uses thinner thumb-first styling with reduced visual chrome.
- Acceptance criteria:
  - Common style tasks are possible without opening advanced controls.
  - Curated fonts visibly differ and apply consistently in preview/export.
  - Color controls support preset, picker, and optional hex workflows without confusion.
  - Overlay open/close affordances stay clear and consistent across wide/narrow layouts.
  - Scroll behavior remains accessible with no horizontal-overflow regressions.

Definition of done:
- UI consistently matches the UX spec visual system.

### Milestone 9 — Cleanup + ship readiness
9.1 Remove obsolete screens/states replaced by Projects/Editor
- Deliverable:
  - Old screens/states removed and replaced by Projects/Editor flow.
- Acceptance criteria:
  - No obsolete screens or states remain accessible.

9.2 Packaging + smoke tests (if not already satisfied)
- Deliverable:
  - Packaging hardening complete; smoke tests repeatable for releases.
- Acceptance criteria:
  - Packaged build launches and completes the golden-path smoke test.

9.3 Final regression checklist (Create Subtitles / edit / style / export / relink / multi-project)
- Deliverable:
  - Final regression checklist executed across core flows.
- Acceptance criteria:
  - No regressions in Create Subtitles, edit, style, export, relink, or multi-project flows.

9.4 Remove legacy Subtitle Edit integration
- Deliverable:
  - Subtitle Edit integration removed from UI, config, and launcher paths.
  - `subtitle_edit_path` config key removed.
- Acceptance criteria:
  - No UI entry points or config references remain for Subtitle Edit.
  - Codebase contains no Subtitle Edit launcher or integration logic.

Definition of done:
- All UX spec sections B–H are implemented; ROADMAP has no remaining redesign items.

## Requested UX additions coverage map (2026-02-11)

| Requested area | Existing coverage | Scheduled in roadmap |
| --- | --- | --- |
| Export success actions reliability (`Play video`, `Open folder`) | Partial (`G2` labels/spec present; reliability bug observed) | Queue item 2, Milestone 0.5 + 6.3 |
| Preview style parity (font/size/shadow) vs export output | Gap | Queue item 3, Milestone 0.6 |
| Preview subtitle scaling with video on window resize | Gap | Queue item 3, Milestone 0.6 |
| Preview word-highlight drift while export timing is correct | Partial (`F`, `G`; export contract already enforced) | Queue item 4, Milestone 0.7 |
| Three-line cue clipped/missing in inline edit textarea | Gap | Queue item 5, Milestone 0.8 + 4.5 |
| RTL edit textarea punctuation/caret behavior (Hebrew) | Gap | Queue item 5, Milestone 0.8 + 4.5 |
| Auto-save + exit edit mode when Play is clicked mid-edit | Gap | Queue item 5, Milestone 0.8 + 4.5 |
| Subtitle edit affordance is too hidden | Partial (`E4` contract exists) | Queue item 5, Milestone 4.5 |
| Transcription quality clarity (cards, plain-language hints, run-time expectation cues) | Partial (`J1`) | Queue item 10, Milestone 7.4 |
| Save-subtitles policy/path relationship clarity | Partial (`J2`) | Queue item 10, Milestone 7.4 |
| Replace diagnostics-heavy settings UI with easy support path | Partial (`H`, `J5`) | Queue item 6, Milestone 0.1 + 7.5 |
| Merge punctuation + audio controls; remove “keep extracted WAV” | Partial (`J3`, `J4`) | Queue item 10, Milestone 7.4 |
| Remove sidebar and fix app-shell/title/back/status orientation | Partial (`B`, `E`) | Queue item 8, Milestone 2.4 + 3.4 |
| Editor duplicated labels/name/status placement | Gap | Queue item 13, Milestone 3.4 |
| Browser/Figma-style Editor tab visuals | Gap | Queue item 12, Milestone 3.5 |
| Pointer cursor affordance on interactive controls | Partial (`E4` I-beam rule exists only for subtitle text) | Queue item 12, Milestone 3.5 + 8.2 |
| Playback-speed discoverability without hidden menu reliance | Gap | Queue item 13, Milestone 6.5 |
| Back during active work keeps processing and remains visible | Partial (`B2`, `I2`) | Queue item 9, Milestone 6.4 |
| Progress 0% stall + row-detail readability | Partial (`F2`, `G1`) | Queue item 9, Milestone 5.2 + 5.4 |
| Delete dialog animation + delete success toast | Gap | Queue item 13, Milestone 2.5 |
| Empty-state duplicate CTA cleanup | Partial (`I1`) | Queue item 13, Milestone 2.5 |
| Style pane control density/layout modernization | Partial (`E3`) | Queue item 11, Milestone 8.4 |
| Style overlay close affordance should be icon-only `X` | Gap | Queue item 11, Milestone 8.4 |
| Wide-layout style pane collapsed strip + icon entry | Gap | Queue item 11, Milestone 8.4 |
| Style pane scrollbar should be thinner thumb-only | Gap | Queue item 11, Milestone 8.4 |
| Curated Hebrew-friendly font list | Gap | Queue item 11, Milestone 8.4 |
| Color UX redesign (presets + picker + optional hex) | Partial (`E3`) | Queue item 11, Milestone 8.4 |
| Sensible per-option default color sets | Gap | Queue item 11, Milestone 8.4 |
| Theme toggle in Settings | Partial (`A`, not surfaced in Settings contract) | Queue item 10, Milestone 7.5 |
| Replace ambiguous status wording (e.g., `Ready`) | Partial (`D2`, `K`) | Queue item 7, Milestone 1.3 + 0.3 |
| Edit controls should not push subtitles while editing | Gap | Queue item 5, Milestone 4.4 |

## Cross-cutting safeguards, validation, and analytics

- Safeguards:
  - Keep export/rendering behavior unchanged unless explicitly called out by milestone acceptance criteria.
  - Keep export word-timing behavior unchanged while addressing preview-only highlight drift.
  - Limit RTL punctuation/cursor fixes to inline edit textarea behavior; do not alter non-edit preview/export rendering unless explicitly scheduled.
  - Export-success open actions (`Play video`, `Open folder`) must never fail silently; always surface clear retryable feedback.
  - Send Logs must be opt-in, redact sensitive local data where possible, and exclude rendered output video by default.
  - If hosted log upload fails, keep local fallback actions (`Copy diagnostics`) available.
- Regression tests (minimum):
  - Projects -> Editor -> Settings -> Back navigation without sidebar.
  - Create subtitles -> Back while running -> confirm background progress remains visible -> reopen project.
  - Export success state -> click `Play video` and `Open folder` -> verify open succeeds (or explicit error message appears).
  - Preview/export parity check on golden clip for font family, font size, shadow, and relative subtitle placement.
  - Resize Editor window -> verify subtitle overlay scales proportionally with video viewport.
  - Preview word highlight sync check using known timing clip; confirm no obvious spoken-word drift.
  - Inline edit multi-line check: 3-line cue remains fully visible/editable.
  - RTL textarea check (Hebrew): punctuation placement and arrow-key behavior stay intuitive in edit mode.
  - While inline edit is active, click Play -> verify auto-save + exit edit mode + immediate playback resume.
  - Delete project -> transient toast appears -> no persistent banner remains.
  - Settings clarity checks for transcription quality, save policy/path grouping, and theme toggle.
  - Style pane checks for font list, color presets/picker behavior, default-color sanity, overlay `X` close affordance, collapsed-strip entry, and thin scrollbar usability.
- Lightweight analytics (privacy-preserving):
  - Export success actions click/success/failure counts (`Play video`, `Open folder`), without collecting opened paths.
  - Preview/export parity mismatch report count (manual QA flag or lightweight telemetry event).
  - Preview highlight drift report count (no subtitle text payloads).
  - Inline edit auto-save-on-play usage count and failure count.
  - Transcription-quality option selection distribution.
  - Send Logs attempt/success/failure counts (no payload contents).
  - Create-subtitles cancel rate and cancel stage.
  - Back-during-active-task frequency and completion outcomes.

## Backlog (Unscheduled)
- Keep this short; ideas go here only if they are explicitly not scheduled.

## Completed
- A short bullet list only (do not paste old plans here; those go in the archived appendices below).
- Desktop shell/backend wiring complete: `/health` + `POST /jobs` + SSE events are live; UI can run pipeline jobs and Cancel works.
- Backend project persistence complete: `/projects` endpoints (`GET/POST`, `GET/PUT/DELETE /projects/{id}`, `GET /projects/{id}/subtitles`, `POST /projects/{id}/relink`) + on-disk project folders + job `project_id` linkage.
- Workbench export migration complete: export CTA/progress/cancel/success now run directly in Workbench with project-first `/jobs` payloads (`project_id`) and no user-facing handoff to legacy routes.
- Project-scoped style export contract complete: Workbench style persists per project (`style.json`), and export consumes project style + project word timings.
- Active routing cleanup complete: `/legacy` and `/review` were removed from `App.tsx`; Workbench is the only active editor/export flow.
- Project Hub delete flow complete: confirmed delete in UI, project-data-only removal, and backend cancel-then-delete behavior.
- Workbench on-video edit + style pane complete: on-video Enter/Esc editing contract is live and Workbench style pane now renders real `StyleControls` (wide + narrow overlay).
- Projects entry flow update complete: top-right CTA is now `New project`, creating a project auto-opens its Workbench tab, and `needs_subtitles` cards now include a secondary `Create subtitles` action.
- Workbench no-subtitles state update complete: strict empty state (`No subtitles yet.` + primary `Create subtitles`) is live, style pane/drawer is hidden until subtitles exist, and create-subtitles now runs directly in Workbench with checklist/progress/cancel plus `project_id` job linkage.

## Decision log
- Date + short note for any decision that changes scope/order.
- 2026-02-11 — Added `docs/internal/KNOWN_ISSUES.md` as the detailed issue tracker; `ROADMAP.md` remains the scheduling source of truth.
- 2026-02-11 — Reprioritized queue to address: export success action reliability, preview truthfulness (style parity + resize scaling), preview-only word-highlight sync, and inline edit reliability (3-line visibility + RTL textarea + Play auto-save).
- 2026-02-11 — Editor tab visuals should follow browser/Figma-style attached tabs; style overlay close affordance should use icon-only `X`.
- 2026-02-11 — Reprioritized queue to: packaging gate first, then Support UX v1, Clarity pass, sidebar removal, progress continuity, settings clarity, style modernization, and micro-interaction polish.
- 2026-02-10 — User-facing label updated from "Project Hub" to "Projects"; no route/model change.
- 2026-02-08 — Milestone 1 backend completed (projects storage + `/projects` API + job linkage) ahead of Project Hub UI.

## Appendix: Archived plans (original content)

### Appendix: Archived — Caption graphics overlay plan (original)
# Caption Graphics Overlay Plan

Status: Completed. This plan is kept for historical reference. For upcoming work, see [`ROADMAP.md`](ROADMAP.md).

## Status update (snapshot from 2025-02-14; see the archived project context appendix in the UX spec for current status)
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
  - Verify word highlights align with RTL samples (Arabic/Hebrew).
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

### Appendix: Archived — Word highlight plan (PR10) (original)
# PR10 — Word Highlight Subtitles (Karaoke-Style) — Implementation Plan

Status: Completed. This plan is kept for historical reference. For upcoming work, see [`ROADMAP.md`](ROADMAP.md).

Last updated: 2026-02-27

## A) Goal and user-visible outcomes
- Subtitle mode selector is available, with **Word highlight** recommended as the default and **Static** as the alternative.
- RTL ordering stays stable during and after highlighting (e.g., Hebrew/Arabic).
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
  - `project context appendix in the UX spec`
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
  - `project context appendix in the UX spec`
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
  - `project context appendix in the UX spec`
  - `word highlight plan appendix in ROADMAP`
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
