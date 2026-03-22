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

2. **Export optimization**
   - **Deliverable:** Cache video stream info earlier; export path revalidates cheaply. Editor export shows only a progress bar and percentage (no per-step checklist). Goal: less redundant probe work and progress that matches real work.
   - **Acceptance:** Export uses cached stream info with a fast revalidation pass; progress reflects real work.

3. **Diagnostics leftovers** (diagnostics disabled)
   - **Deliverable:** With diagnostics off, do not retain diagnostics-only SRT or `word_timings.json`. Editing and export can keep whatever they legitimately need. No diagnostics-only path should create or keep extra timing-file copies.
   - **Acceptance:** With diagnostics disabled in Settings, processing does not leave diagnostics-only SRT/`word_timings.json` clutter. Edit and export still work. Confirm with code review and validation.

4. **macOS desktop release**
   - **Deliverable:** Packaged macOS app for distribution (for example a `.dmg` or notarized installer from the Tauri build), including a macOS-appropriate engine/FFmpeg story consistent with [`CONTRIBUTING.md`](CONTRIBUTING.md) release notes. Releases page lists the macOS download alongside Windows when artifacts are available.
   - **Acceptance:** On a supported macOS version, a user can install from Releases and run Cue with the same core editing and export flow as the Windows beta; [`README.md`](../README.md) links to the macOS artifact without “planned only” once shipped.

5. **Left panel: all-subtitles list**
   - **Deliverable:** A left strip listing all cues (read-only timestamps, editable text); click a row to seek and select. Layout: collapsed by default; docked and resizable at wide widths; under ~1100px use an overlay drawer with scrim and Esc; only one overlay open at a time (this panel vs style).
   - **Acceptance:** Editing, seek, and selection stay in sync; dock/overlay behavior holds across resize.

6. **Subtitle translation** (target language can differ from audio)
   - **Deliverable:** A path distinct from same-language transcription: user chooses a subtitle language that may not match the spoken audio, and the app produces timed subtitles in that language (translation, not “wrong-language” transcribe).
   - **Acceptance:** User can set an explicit target subtitle language independent of the audio language; cues appear in that language with usable timing; edit, preview, and export behave like other subtitle workflows.
