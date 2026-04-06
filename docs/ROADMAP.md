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

7. **Subtitle segmentation controls** (adjust words per subtitle)
   - **Deliverable:** Add a user-facing control for subtitle segmentation so people can decide how aggressively Cue splits speech into subtitle blocks, including a simple way to set a rough max words-per-subtitle target for shorter or longer captions.
   - **Acceptance:** User can change the segmentation setting before generating subtitles, then see that choice reflected in the resulting subtitle length and pacing. The setting is clear enough that a non-expert can predict the effect without knowing subtitle jargon.

8. **Style presets**
   - **Deliverable:** Let users save style presets from their current design choices, give each preset a name, and reapply it later instead of rebuilding the same look by hand.
   - **Acceptance:** User can save the current subtitle style as a preset, find saved presets later, apply one in a couple of clicks, and still tweak the result before export.

9. **More fonts + custom font import**
   - **Deliverable:** Expand the built-in subtitle font options and let users add their own font files so they are not limited to the bundled list when styling subtitles.
   - **Acceptance:** User can choose from a larger built-in font list, import a supported font file from their computer, see that font appear in the style controls, preview it in the editor, and use it successfully in export without manual file copying.

10. **Grid view: hover-only delete button on cards**
    - **Deliverable:** In grid view (Home), the delete button on each video card is hidden by default and appears only when the user hovers over the card.
    - **Acceptance:** Delete button is not visible in the resting state; hovering a card reveals it; the interaction and outcome are unchanged.

11. **Disable default browser right-click context menu**
    - **Deliverable:** Suppress the native browser/webview context menu app-wide (or at minimum in the main editor and Home views) so options like Share, Print, and other irrelevant browser actions are never shown to users.
    - **Acceptance:** Right-clicking anywhere in the app does not open the default context menu; any custom context menus the app intentionally provides are unaffected.

12. **Configurable transcription queue concurrency**
    - **Deliverable:** Replace the hardcoded “one video transcribing at a time” limit with a user setting: choose how many videos may run transcription concurrently (for example 2), or turn transcription queueing off so concurrency is unconstrained (subject to system limits).
    - **Acceptance:** User can change the concurrency limit or disable queueing in Settings (or an equivalent clear control); behavior matches the chosen setting across add/import flows.

13. **Multi-video add (picker and drag-and-drop)**
    - **Deliverable:** When adding videos via “Add video” or the drag-and-drop zone, allow selecting or dropping multiple files at once instead of a single file per action.
    - **Acceptance:** User can queue several videos in one file-picker session or one drop; each file is handled according to existing add rules without requiring separate actions per video.

14. **Multi-queue transcription: progress and navigation (KI-016)**
    - **Deliverable:** Fix incorrect blocking on “creating subtitles” and any spurious repeated transcription steps when multiple videos are queued; see [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) KI-016.
    - **Acceptance:** Completing transcription for a video moves that user into the editor (or correct next step) without waiting for unrelated queued jobs; no duplicate transcription-step churn tied to sibling job completion.

15. **Line layout: max lines and max words per line**
    - **Deliverable:** User-facing limits for how subtitle text wraps within a cue: maximum number of lines (for example 1 or 2) and maximum words per line. Distinct from subtitle *segmentation* (queue item 7), which splits speech into cues; this controls typography and wrapping inside a cue.
    - **Acceptance:** User can set max lines and max words per line; preview and export reflect wrapping and line breaks consistently.

16. **Subtitle track above seek bar**
    - **Deliverable:** A visual subtitle strip on the timeline (above the seek bar) showing where subtitles appear: for example segment markers or bars whose length matches each subtitle’s on-screen duration.
    - **Acceptance:** User can see at a glance when subtitles are active while scrubbing or playing; indicators align with cue timing.

17. **Subtitle rotation**
    - **Deliverable:** Style control to rotate subtitle text (or the subtitle box) for angled or vertical treatments where supported by the renderer.
    - **Acceptance:** User can set rotation; preview and export match within renderer capabilities.

18. **Subtitle motion / entrance animations**
    - **Deliverable:** Optional animation styles for subtitles—such as fade, slide, float, and additional presets—applied when a cue appears (and optionally when it leaves), with sensible defaults so plain subtitles stay unchanged unless chosen.
    - **Acceptance:** User can pick an animation preset; preview and export show the chosen motion without breaking untimed or static captions.

19. **Karaoke vs word-highlight highlight modes**
    - **Deliverable:** Clarify and offer two word-level highlight behaviors: *karaoke-style* (highlight every word from the start of the cue through the current word) versus *word-highlight* (current behavior: emphasize only the active word, or the existing “single-word” karaoke feel—document the exact distinction in UI copy). Consider naming that avoids confusing the two modes.
    - **Acceptance:** User can choose the mode; preview and export match the selected semantics consistently.
