# Third-Party Notices

This file summarizes major third-party components redistributed with Cue Windows installers.

It is intentionally curated. It is not a full transitive dependency inventory, source offer, or SBOM.

## FFmpeg and FFprobe

Cue redistributes `ffmpeg.exe` and `ffprobe.exe` for local audio/video processing.

- Source used by this repo: Gyan Windows builds, downloaded by `scripts\download_ffmpeg.ps1`
- Pinned packaged artifact: `https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.0.1-essentials_build.zip`
- Upstream project: <https://ffmpeg.org/>
- Build provider: <https://www.gyan.dev/ffmpeg/builds/>
- Current bundled binary report: `ffmpeg version 8.0.1-essentials_build-www.gyan.dev`
- Current bundled binary configuration includes: `--enable-gpl --enable-version3`

Important note:

- Cue's packaged Windows build uses the pinned Gyan "essentials" build for reproducible installer size.
- This notice file does not attempt to reproduce a full per-library audit of every FFmpeg build flag.
- For full FFmpeg licensing guidance, see <https://ffmpeg.org/legal.html>.

## Python Engine and Runtime Components

Cue ships a packaged Python engine as split zip resources under `desktop/src-tauri/` (`cue-engine-01-executables.zip` through `cue-engine-04-internal.zip`, driven by `cue-engine-parts.json`). Together they are equivalent to one engine tree. This section calls out the primary redistributed components Cue uses directly.

| Component | Version | Cue use | Upstream | Reported license |
| --- | --- | --- | --- | --- |
| PySide6 / Qt for Python | 6.7.2 | Backend preview and export rendering, Qt runtime pieces | <https://pyside.org/> | PySide6 metadata reports `LGPL` |
| faster-whisper | 1.1.1 | Local transcription backend | <https://github.com/SYSTRAN/faster-whisper> | MIT |
| WhisperX | 3.7.6 | Word-level alignment | <https://github.com/m-bain/whisperX> | BSD-2-Clause |
| FastAPI | 0.128.0 | Local backend HTTP API | <https://github.com/fastapi/fastapi> | MIT |
| Uvicorn | 0.40.0 | Local ASGI server | <https://uvicorn.dev/> | BSD-3-Clause |

Additional note:

- The packaged engine also contains transitive dependencies required by these components.
- This file does not enumerate every transitive Python package bundled inside the engine archive.

## Desktop and Runtime Components

Cue's desktop shell and frontend are built on these primary redistributed runtime components.

| Component group | Cue use | Upstream | Reported license |
| --- | --- | --- | --- |
| Tauri framework (`tauri`, `@tauri-apps/api`) | Desktop shell, native windowing, resource access | <https://tauri.app/> | Apache-2.0 OR MIT |
| Tauri plugins (`tauri-plugin-dialog`, `tauri-plugin-opener`, `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-opener`) | Native file dialogs and opener integration | <https://github.com/tauri-apps/plugins-workspace> | MIT OR Apache-2.0 |
| React | Desktop UI rendering | <https://react.dev/> | MIT |

## Bundled Fonts

Cue redistributes bundled fonts for subtitle rendering and desktop UI presentation.

### Subtitle font set

The files under `app/fonts` are bundled for subtitle preview/export and desktop subtitle editing:

- Alef
- Arimo
- Assistant
- Frank Ruhl Libre
- Heebo
- IBM Plex Sans Hebrew
- Noto Sans Hebrew
- Rubik
- Secular One
- Suez One

Source:

- Google Fonts: <https://fonts.google.com/>
- Repo note: `app/fonts/README.md`

License note:

- The current repo documentation for these bundled subtitle fonts says they are sourced from Google Fonts under `OFL` or `Apache-2.0`, depending on the family.

### Plus Jakarta Sans

Cue also bundles Plus Jakarta Sans for parts of the desktop UI.

- Package: `@fontsource/plus-jakarta-sans`
- Declared package version in this workspace: `^5.2.6`
- Upstream: <https://fontsource.org/fonts/plus-jakarta-sans>
- Reported license: OFL-1.1

## Explicit Exclusions

These items are referenced by Cue but are not redistributed as packaged app assets in this repo's Windows installer payload:

- `Noto Color Emoji` is loaded from jsDelivr in `desktop/src/index.css`. It is not bundled in the packaged installer payload.
- Microsoft WebView2 may be downloaded or updated by the Windows installer when needed, but it is not shipped as a Cue app resource.

## Packaging Notes

- The live Windows packaging flow ships `THIRD_PARTY_NOTICES.md` alongside the desktop app bundle.
- The packaged local engine artifacts are `desktop/src-tauri/cue-engine-01-executables.zip` … `cue-engine-04-internal.zip` and `cue-engine-parts.json`.
- The retired mirrored `desktop/src-tauri/engine/` folder is not part of the active packaged Windows release path.
