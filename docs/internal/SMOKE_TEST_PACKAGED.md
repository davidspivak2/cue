# Packaged Build Smoke Test (Windows)

Purpose:
- Verify that packaged installers launch and complete the golden path without a local Python or FFmpeg install.
- Keep this test short and repeatable for every release candidate.

## Scope
- Installer types:
  - NSIS (`.exe`)
  - MSI (`.msi`) when available
- Golden path:
  - Launch app
  - Create project
  - Create subtitles
  - Export video with subtitles

## Build Artifacts
- Build command (repo root):
  - `scripts\build_release.cmd`
- Installer outputs:
  - `desktop\src-tauri\target\release\bundle\nsis\`
  - `desktop\src-tauri\target\release\bundle\msi\`

## Test Inputs
- One short MP4 clip (about 20-60 seconds) on local disk.
- Optional second clip for a quick re-run.

## Preconditions
- Uninstall older Cue build if it may conflict with the test.
- Close all running Cue processes.
- Confirm no local dev backend is running on port `8765`.

## Smoke Test Steps
1. Install the packaged app (`.exe` or `.msi`).
2. Launch Cue from Start menu or desktop shortcut.
3. Wait for the Projects screen to appear.
4. Click `New project` and choose the test MP4.
5. Confirm a new project card appears.
6. Open the project (or let auto-open happen if enabled).
7. Click `Create subtitles`.
8. Wait for completion and confirm subtitles are present.
9. Click `Create video with subtitles`.
10. Wait for export to complete.
11. Confirm the exported MP4 exists on disk.
12. Re-open the app and confirm the project is still listed.

Optional automation helper (packaged backend flow):
- `python tools\smoke_test_packaged_backend.py --video "C:\path\to\sample.mp4" --output-dir "C:\Cue_extra\smoke_packaged"`

## Build status
NSIS build resolved as of 2026-02-13; both NSIS and MSI installers build and are smoke-testable.

## Pass Criteria
- App launches successfully.
- No fatal error blocks the create-subtitles or export flow.
- Exported MP4 is created and playable.
- Project persists across restart.

## Failure Data to Collect
- Installer type and filename used.
- Exact step where failure happened.
- Screenshot of the visible error (if any).
- Latest backend log from `%LOCALAPPDATA%\Cue\logs\`:
  - `backend_sidecar_*.log`
- Latest worker log from `%LOCALAPPDATA%\Cue\logs\`:
  - `cue_*.log`

## Result Record
| Date (UTC) | Commit | Installer | Result | Notes |
| --- | --- | --- | --- | --- |
| 2026-02-13 | post-PR13 | NSIS `.exe` | PASS | NSIS blocker resolved; installer builds and works. |
| 2026-02-11 | `d17a31f` | NSIS `.exe` | FAIL | NSIS packaging fails with `Internal compiler error #12345 ... mmapping file ... out of range` on this build size. |
| 2026-02-11 | `d17a31f` | MSI `.msi` | PASS | `scripts\build_release.cmd` fallback built MSI; packaged backend smoke command produced `SMOKE_RESULT=PASS` and `test_30s_subtitled.mp4`. |
