# Session handoff — Workbench custom video controls and subtitle push

**Date:** 2026-02-20  
**Project:** Cue (C:\Cue_repo)  
**Purpose:** Hand off context after implementing YouTube-style custom video controls (hover-to-show, push subtitles) and restoring from a blank-screen regression. Next agent can safely re-apply instant hide and/or fix subtitle push if needed.

---

## Current state summary

- **Custom video controls** in the Workbench preview are implemented and working:
  - Native `<video controls>` removed; custom bar with play/pause, volume (icon + horizontal slider), time display, and seek bar with thumb.
  - Controls are **hidden by default** and **show on hover** over the video preview area. They **hide again after 2.5 seconds** when the cursor leaves (delay was restored to fix a blank-screen regression).
  - Control bar is positioned at the bottom of the video rect (z-index above subtitle overlay) so it is always clickable when visible.

- **Subtitle “push”** when controls are visible:
  - Implemented via an **inner wrapper** inside the subtitle overlay position layer: a div with `height: "100%"`, `paddingBottom: showVideoControls ? VIDEO_CONTROLS_TOTAL_HEIGHT_PX : 0`, and the same flex/transition classes. This reserves space at the bottom when the bar is shown so subtitles sit above it.
  - A previous approach (merging controls inset into the position layer style as `subtitleOverlayPositionStyleWithControls`) was **reverted** because it led to a **blank screen** when opening a project. The codebase is back to the inner-wrapper approach only.

- **Known limitation:** With the current inner wrapper, subtitles may not always appear to “push” visually (layout depends on flex alignment). If the user wants subtitles to reliably move up when the bar appears, the next agent may need to re-introduce a safe way to apply the controls inset (e.g. on the position layer) without causing the blank screen—e.g. by ensuring the combined style is never invalid and is only applied when `activeCue` is set.

---

## Important context for next agent

1. **Hover and delay:** The video preview wrapper (the div that contains `<video>`, overlay, and control bar) has `onMouseEnter` (show controls immediately, clear any hide timeout) and `onMouseLeave` (set a 2.5s timeout to hide). `videoControlsHideTimeoutRef` and `VIDEO_CONTROLS_HIDE_DELAY_MS` (2500) are used; cleanup on unmount clears the timeout.

2. **Why the delay was restored:** The user asked to hide controls “right away” when the cursor leaves. We changed to immediate `setShowVideoControls(false)` on mouse leave and removed the timeout/ref. After that, the user reported a **blank screen** when opening a project. We restored the delay and also reverted the overlay to the inner-wrapper approach (removed `subtitleOverlayPositionStyleWithControls`). The blank screen may have been caused by the combined style, not by removing the delay; restoring both was done to match the last known good state.

3. **Subtitle overlay structure (current):**  
   - Position layer: `style={subtitleOverlayPositionStyle}` (no “WithControls” variant).  
   - Inner wrapper: `height: "100%"`, `paddingBottom: showVideoControls ? VIDEO_CONTROLS_TOTAL_HEIGHT_PX : 0`, flex column + `subtitleVerticalClass`.  
   - Subtitle content lives inside that inner wrapper. One extra closing `</div>` is required for the inner wrapper.

4. **Constants:** `VIDEO_CONTROL_BAR_HEIGHT_PX` (44), `VIDEO_PROGRESS_STRIP_HEIGHT_PX` (6), `VIDEO_CONTROLS_TOTAL_HEIGHT_PX` = 44 + 2 + 6 + 8 (includes padded seek bar). Control bar container style uses this total height for positioning.

---

## Immediate next steps

1. **If the user wants controls to hide immediately again (no delay):**  
   - Change `onMouseLeave` to call `setShowVideoControls(false)` directly (no `setTimeout`).  
   - Remove the timeout ref and `VIDEO_CONTROLS_HIDE_DELAY_MS`, and the useEffect cleanup, **but do not** re-introduce `subtitleOverlayPositionStyleWithControls` or change the overlay structure.  
   - Test that the project page still renders (no blank screen). If the blank screen was tied to the combined style, instant hide alone should be safe.

2. **If the blank screen returns:**  
   - First revert only the overlay: keep using `subtitleOverlayPositionStyle` and the inner wrapper; do not add a useMemo that merges padding into the position layer style.  
   - If the blank screen persists, the cause is elsewhere (e.g. data loading, another component). Check browser console and any error boundaries.

3. **If subtitles still don’t visibly “push” when controls show:**  
   - The inner wrapper has `height: "100%"`; in a flex row parent with `items-end`, the wrapper may not get full height in all cases. Options: try `minHeight: "100%"` on the inner wrapper, or re-introduce a **safe** combined style for the position layer (e.g. only add `paddingBottom` in px when `showVideoControls`, and ensure the base style is always a valid object so no render path can hit an invalid style).

---

## Critical files

| Area | File | Notes |
|------|------|--------|
| Frontend | [desktop/src/pages/Workbench.tsx](desktop/src/pages/Workbench.tsx) | All custom control logic: `showVideoControls`, `videoControlsHideTimeoutRef`, `VIDEO_CONTROLS_HIDE_DELAY_MS`, hover handlers; control bar JSX (play, volume, slider, time, seek bar); subtitle overlay position layer and inner wrapper with `paddingBottom`; `formatTime`, `handlePlayPauseToggle`, `handleProgressBarPointer`, volume handlers. |

---

## Decisions made

- **Restore 2.5s hide delay** after the user reported a blank screen, to match the last known good behavior.
- **Remove `subtitleOverlayPositionStyleWithControls`** and rely only on the inner wrapper with `paddingBottom` for “pushing” subtitles, to avoid the blank screen that appeared when the combined style was used on the position layer.
- **Keep control bar visibility tied to hover** with a single `showVideoControls` state; no fullscreen button per user request.

---

## References

- Plan (user’s project): YouTube-style custom video controls — hide native controls, custom bar above overlay, play/pause, volume (icon + horizontal slider), time, seek bar; no fullscreen; then hover-to-show and push subtitles.
- Earlier in session: seek bar thumb, volume slider horizontal and always visible, cursor pointer, timer contrast, seek bar padding, then hover-to-show with delay, then instant hide (which preceded blank screen reports).
