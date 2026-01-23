# Graphics Overlay Renderer Debugging Notes

## What the graphics overlay renderer does
The graphics overlay renderer draws subtitle text into RGBA frames (using the same styling rules as the preview renderer) and streams those frames to FFmpeg, which composites them over the source video using an overlay filter. This means export is purely image-based: the renderer paints the text into frames, and FFmpeg handles the video encode + audio mux.

## Where to look when export or preview fails
**Primary logs**
- App runtime logs live in `%LOCALAPPDATA%\HebrewSubtitleGUI\logs\`.
- Each run produces a timestamped log file like `hebrew_subtitle_gui_YYYYMMDD_HHMMSS.log`.

**Diagnostics JSON (optional)**
- When diagnostics logging is enabled, JSON files named `diag_*.json` are written **next to the export outputs** (same folder as the selected save location).
- If “Zip logs and outputs on exit” is enabled, the app writes `hebrew_subtitles_bundle_*.zip` next to the selected video; it includes logs, diagnostics JSON, and output artifacts.

## How to enable diagnostics
See the Diagnostics section in `docs/HEBREW_SUBTITLE_GUI_CONTEXT.md` (Section 6) for the full settings reference. The exact checkbox labels you should look for are:
- “Enable diagnostics logging”
- “Write diagnostics on successful completion”
- “Zip logs and outputs on exit”
- “App + system info”
- “Video info”
- “Audio (WAV) info”
- “Transcription config”
- “SRT stats”
- “Commands + timings”

## Most important debug signals
1. **Renderer line at export start**
   - Look for `Export renderer=graphics_overlay` in the log to confirm the pipeline.
2. **FFmpeg command line + filter**
   - The log captures the export filter string and the FFmpeg command used for burn-in.
   - The diagnostics JSON includes `commands_timings.burn_in_command_used` and `commands_timings.burn_in_filter`.
3. **FFmpeg stderr output**
   - Export failures emit the FFmpeg stderr lines into the session log. This is usually the fastest signal for codec/muxing failures.

## Quick triage checklist
- Confirm the renderer line is present and set to graphics overlay.
- Confirm the overlay filter is `overlay=0:0:format=auto` (graphics overlay pipeline).
- If audio copy fails, verify the retry uses AAC (logged as `burn_in_audio_mode`).
- Use the diagnostics JSON to cross-check paths (video, SRT, output) when mismatches are suspected.
