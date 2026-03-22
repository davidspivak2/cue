# Roadmap

What we plan to ship, in order. Notes that never leave the machine stay under `docs/internal/`. The project list in the app is **Home** (your videos); older docs may still say "Projects" or "Project Hub."

## Rules

- Scheduling lives here; bug write-ups and repro steps live in [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md).
- Anything not listed here is not scheduled.
- Each item needs a status, deliverable, and acceptance criteria.

## Queue

Statuses: NEXT, IN PROGRESS, BLOCKED, DONE.

1. **[NEXT] Support UX** (error details, copy diagnostics, hosted send logs)
   - **Deliverable:** Error UI: details drawer and Copy diagnostics. Settings: hosted Send logs with explicit consent. Diagnostics tools only in Settings (errors may show details, not the full diagnostics toolkit).
   - **Acceptance:** User can open details and copy diagnostics from an error. Send logs only after a clear consent summary; payload excludes rendered video and redacts sensitive paths where possible. Upload failure still leaves Copy diagnostics available. No diagnostics tools outside Settings.

2. **[NEXT] Export optimization**
   - **Deliverable:** Cache video stream info earlier; export path revalidates cheaply. Remove or relabel the "Getting video info" checklist row if it no longer matches real work.
   - **Acceptance:** Export uses cached stream info with a fast revalidation pass; checklist text matches what runs.

3. **[NEXT] Diagnostics leftovers** (diagnostics disabled)
   - **Deliverable:** With diagnostics off, do not retain diagnostics-only SRT or `word_timings.json`. Editing and export can keep whatever they legitimately need. No diagnostics-only path should create or keep extra timing-file copies.
   - **Acceptance:** With diagnostics disabled in Settings, processing does not leave diagnostics-only SRT/`word_timings.json` clutter. Edit and export still work. Confirm with code review and validation.

## Milestones (deferred / remaining)

### Editor shell: left panel (deferred)

The left panel is hidden/paused. When it ships: collapsed by default; docked and resizable at wide widths; under 1100px, overlay drawer with scrim and Esc; only one overlay open (left vs right). **Acceptance:** Dock/overlay behavior holds across resize once the panel is enabled again.

### In-app editing: left subtitle list

Rows show read-only timestamps plus editable text; clicking a row seeks the video and selects that cue. **Acceptance:** Text edits, seek, and selection stay in sync.

## Gaps vs queue

| Area | Status | Where |
| --- | --- | --- |
| Easier support path vs diagnostics-heavy settings | Partial | Queue 1 |
| No diagnostics-only file retention when diagnostics off | Gap | Queue 3 |
| Export stream cache / "Getting video info" row | Gap | Queue 2 |

## Safeguards and regression checks

- Do not change export or rendering behavior unless a queue item says so.
- Send Logs: opt-in; redact sensitive paths; exclude rendered output video by default. If upload fails, Copy diagnostics remains.
- Worth exercising: Projects to Editor to Settings and back; create subtitles, leave Editor, confirm background progress; after export success, Play and Open folder; golden clip preview vs export (font, size, shadow, placement); resize window and confirm subtitles scale with video; word-highlight sync on a known clip; 3-line cue in edit; RTL edit textarea; Play during edit saves and exits edit; delete project yields a toast, not a sticky banner; settings (transcription, save path, theme); style pane (fonts, colors, overlay close, strip entry, scrollbar).

## Analytics (privacy-preserving)

Clicks and outcomes for Play / Open folder (no paths). Preview parity and highlight drift signals (no subtitle text). Inline edit save-on-play usage and failures. Transcription preset distribution. Send Logs attempts and outcomes. Create-subtitles cancel rate and stage. Back-during-active-task frequency and outcomes.

## Backlog

Unscheduled ideas only; keep it short.

## Decision log

- 2026-02-11: `KNOWN_ISSUES.md` holds issue detail; this file holds schedule.
- 2026-02-11: Queue bumped export opens, preview parity and resize, word-highlight preview sync, and inline edit (3-line, RTL, Play-to-save). Later the same day: packaging first, then Support UX, clarity pass, sidebar removal, progress continuity, settings clarity, style pass, micro-interactions. Editor tabs: browser-style attached tabs; style overlay close is icon-only X.
- 2026-02-10: User-facing name "Project Hub" to "Projects" (routes unchanged).
- 2026-02-08: Milestone 1 backend shipped (projects storage, `/projects` API, job linkage) before Hub UI.
