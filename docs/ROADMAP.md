# Roadmap

What we plan to ship and in what order. One-off migration notes sometimes stay in local `docs/internal/` and never hit GitHub.
In the app, the project list is titled **Home** (your videos). Older write-ups here may still say “Projects” or “Project Hub.”

## Rules
- Use this file for what ships next and in what order.
- Detailed bug write-ups, repro steps, and issue-level validation notes live in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).
- If work is not listed here, it is not scheduled.
- This file defines implementation order and acceptance criteria.
- Each work item must include: Status, Deliverable, and Acceptance criteria.

## Planned changes / additions
- Diagnostics leftovers cleanup so diagnostics-only SRT and `word_timings.json` are not retained when diagnostics are disabled.

## Now / Next (Queue)
(Use a numbered list. Status tags must be one of: NEXT, IN PROGRESS, BLOCKED, DONE.)

1. [NEXT] Support UX (error details + copy diagnostics + hosted send logs)
   - Deliverable:
     - Error UI includes a details drawer and a “Copy diagnostics” action.
     - Settings support surface includes hosted “Send logs” with explicit user consent.
     - Diagnostics tools remain in Settings only (error UI may show details, not tools).
   - Acceptance criteria:
     - Trigger an error: user can open details drawer and copy diagnostics text.
     - User can send logs via a hosted receiver after seeing a clear consent summary of what will be shared.
     - Log payload excludes rendered video output and redacts sensitive local-path data where possible.
     - If upload fails, user still has a visible fallback path (`Copy diagnostics`).

2. [NEXT] Export optimization: cache video stream info earlier + cheap revalidate; remove/adjust “Getting video info” checklist row if appropriate
   - Deliverable:
     - Video stream info cached earlier; export path uses cheap revalidation.
     - “Getting video info” checklist row removed or adjusted if no longer accurate.
   - Acceptance criteria:
     - Export step uses cached stream info with a fast revalidation pass; UI checklist reflects the actual work.

3. [NEXT] Diagnostics leftovers cleanup (diagnostics disabled)
   - Deliverable:
      - When diagnostics are disabled, diagnostics-only retention of SRT and `word_timings.json` is removed.
      - Project artifacts required for normal editing/export may still be present.
      - No diagnostics-only code path creates or keeps extra copies of subtitle timing artifacts when diagnostics are disabled.
   - Acceptance criteria:
      - With diagnostics disabled in Settings, processing a project does not create or retain diagnostics-only SRT/`word_timings.json` leftovers.
      - Editing/export-required project artifacts remain available and functional.
      - Diagnostics-only retention paths are confirmed disabled by code review and validation checks.

## Milestones (Ordered to Completion)

### Milestone 0: Stabilization (remaining)
0.1 Support UX (error details + copy diagnostics + hosted send logs)
- Deliverable:
  - Error UI includes a details drawer and a “Copy diagnostics” action.
  - Settings provides a hosted “Send logs” support action with explicit consent and redaction summary.
  - Diagnostics tools remain in Settings only.
- Acceptance criteria:
  - Trigger an error: user can open details drawer and copy diagnostics text.
  - User can submit logs to hosted support without attaching video outputs.
  - Upload failure path keeps a clear fallback (`Copy diagnostics`) visible.
  - No diagnostics tools appear outside Settings.

0.2 Export optimization: cache video stream info earlier + cheap revalidate; adjust “Getting video info” checklist row if appropriate
- Deliverable:
  - Video stream info cached earlier; export path uses cheap revalidation.
  - “Getting video info” checklist row removed or adjusted if no longer accurate.
- Acceptance criteria:
  - Export step uses cached stream info with a fast revalidation pass; UI checklist reflects the actual work.

Definition of done (Milestone 0):
- Remaining stabilization items above are complete.

### Milestone 3: Editor shell (deferred item)
3.2 Left panel responsive behavior
Status: Deferred while left panel remains hidden/paused.
- Deliverable:
  - Collapsed by default
  - Docked at wide widths, resizable, per-project persisted width
  - Overlay drawer under 1100px with scrim + Esc closes
  - Only one overlay open at a time (left vs right)
- Acceptance criteria:
  - Resize window around threshold: dock/overlay rules work exactly once left panel is re-enabled.

### Milestone 4: In-app subtitle text editing (remaining)
4.1 Left list editing
- Deliverable:
  - Each row shows timestamps (read-only) + editable text
  - Clicking row seeks video + selects subtitle
- Acceptance criteria:
  - Edit text, seek + selection sync works.

## Requested additions coverage map (2026-02-11)

| Requested area | Existing coverage | Scheduled in roadmap |
| --- | --- | --- |
| Replace diagnostics-heavy settings UI with easy support path | Partial | Queue item 1, Milestone 0.1 |
| Diagnostics leftovers (no diagnostics-only retention when disabled) | Gap | Queue item 3 |
| Export optimization / “Getting video info” row | Gap | Queue item 2, Milestone 0.2 |

## Cross-cutting safeguards, validation, and analytics

- Safeguards:
  - Keep export/rendering behavior unchanged unless explicitly called out by milestone acceptance criteria.
  - Send Logs must be opt-in, redact sensitive local data where possible, and exclude rendered output video by default.
  - If hosted log upload fails, keep local fallback actions (`Copy diagnostics`) available.
- Regression tests (minimum):
  - Projects -> Editor -> Settings -> Back navigation without sidebar.
  - Create subtitles -> Back while running -> confirm background progress remains visible -> reopen project.
  - Export success state -> click `Play` and `Open folder` -> verify open succeeds (or explicit error message appears).
  - Preview/export parity check on golden clip for font family, font size, shadow, and relative subtitle placement.
  - Resize Editor window -> verify subtitle overlay scales proportionally with video viewport.
  - Preview word highlight sync check using known timing clip; confirm no obvious spoken-word drift.
  - Inline edit multi-line check: 3-line cue remains fully visible/editable.
  - RTL textarea check (Hebrew): punctuation placement and arrow-key behavior stay intuitive in edit mode.
  - While inline edit is active, click Play -> verify auto-save + exit edit mode + immediate playback resume.
  - Delete project -> transient toast appears -> no persistent banner remains (E2E: `project-hub.spec.ts` asserts toast and no inline banner).
  - Settings clarity checks for transcription quality, save policy/path grouping, and theme toggle.
  - Style pane checks for font list, color presets/picker behavior, default-color sanity, overlay `X` close affordance, collapsed-strip entry, and thin scrollbar usability.
- Lightweight analytics (privacy-preserving):
  - Export success actions click/success/failure counts (`Play`, `Open folder`), without collecting opened paths.
  - Preview/export parity mismatch report count (manual QA flag or lightweight telemetry event).
  - Preview highlight drift report count (no subtitle text payloads).
  - Inline edit auto-save-on-play usage count and failure count.
  - Transcription-quality option selection distribution.
  - Send Logs attempt/success/failure counts (no payload contents).
  - Create-subtitles cancel rate and cancel stage.
  - Back-during-active-task frequency and completion outcomes.

## Backlog (Unscheduled)
- Keep this short; ideas go here only if they are explicitly not scheduled.

## Decision log
- Date + short note for any decision that changes scope/order.
- 2026-02-11: Added `KNOWN_ISSUES.md` as the detailed issue tracker; `ROADMAP.md` remains the scheduling source of truth.
- 2026-02-11: Reprioritized queue to address: export success action reliability, preview truthfulness (style parity + resize scaling), preview-only word-highlight sync, and inline edit reliability (3-line visibility + RTL textarea + Play auto-save).
- 2026-02-11: Editor tab visuals should follow browser/Figma-style attached tabs; style overlay close affordance should use icon-only `X`.
- 2026-02-11: Reprioritized queue to: packaging gate first, then Support UX, Clarity pass, sidebar removal, progress continuity, settings clarity, style modernization, and micro-interaction polish.
- 2026-02-10: User-facing label updated from "Project Hub" to "Projects"; no route/model change.
- 2026-02-08: Milestone 1 backend completed (projects storage + `/projects` API + job linkage) ahead of Project Hub UI.
