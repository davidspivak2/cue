# Cue

Create subtitles for any video, in any language, on your own computer.

Cue uses speech recognition to build subtitles and burn them into the video. Everything runs locally: no upload, no cloud account, no subscription.

## Screenshots

<!-- TODO: Add 2-3 screenshots or a GIF of the app once the UI is stable. -->

## Features

- **Automatic subtitles:** Add a video from Home, get an SRT file out. Uses Whisper large-v3.
- **Burn-in export:** New MP4 with subtitles baked in; no separate encoder step.
- **Word-by-word highlighting:** Karaoke in the Effects panel tracks the speaker as the video plays.
- **Style customization:** Presets plus fonts, colors, outlines, shadows, and backgrounds in the workbench Effects panel.
- **Languages:** Auto-detects language; supports what Whisper supports.
- **RTL:** Right-to-left layout for Hebrew, Arabic, and other RTL scripts.
- **GPU acceleration:** Uses CUDA when available; otherwise CPU.
- **Offline:** Processing stays on your machine; videos are not uploaded.
- **Open source:** GPL-3.0; see License below.

## Download and install

### Windows

<!-- TODO: Add download link to the latest .msi or .exe installer once packaging is ready. -->

Download the latest Windows installer from the [Releases](../../releases) page and run it.

Windows releases currently ship packaged desktop app installers for x64 only.

The Windows installer bundle includes Cue's local engine as several resource archives (`cue-engine-01-executables.zip` … `cue-engine-04-internal.zip` plus a small manifest) and installs `TERMS.md`, `PRIVACY.md`, `LICENSE`, and `THIRD_PARTY_NOTICES.md` with the app.

The NSIS `.exe` installer shows Cue's end-user terms during setup.

### macOS

<!-- TODO: Add download link to the latest .dmg once macOS packaging is ready. -->

macOS support is planned. Check the [Releases](../../releases) page for updates.

### Build from source

If you want to run the app from source or contribute, see the [Contributing guide](docs/CONTRIBUTING.md).

## Quick start

1. **Home (project hub):** Click **Add video** or drop a supported file on the empty area (MP4, MKV, MOV, M4V, WEBM). Cue opens the video in a **workbench tab** (you can keep several videos open and switch tabs in the title bar).
2. **Create subtitles:** In the workbench, click **Create subtitles** and wait for transcription. The first run may download the Whisper model, which can take a few minutes.
3. **Review and style:** Use the preview and the **Effects** panel for presets, typography, colors, outline, shadow, background, and **Karaoke** for word-by-word highlighting.
4. **Export:** Click **Export** to burn subtitles into a new MP4.

Choose where the `.srt` and exported video go in **Settings** (gear in the title bar): next to the source video, a fixed folder, or ask every time.

## How it works

Cue extracts the audio from your video, runs it through [Whisper](https://github.com/openai/whisper) (via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) to generate subtitles, and then uses [FFmpeg](https://ffmpeg.org/) to burn them into a new video. Word-level timing for the highlight mode comes from [WhisperX](https://github.com/m-bain/whisperX) alignment.

For a deeper technical overview, see the [Architecture guide](docs/ARCHITECTURE.md).

## Contributing

Contributions are welcome. See the [Contributing guide](docs/CONTRIBUTING.md) for setup instructions and the [Architecture guide](docs/ARCHITECTURE.md) for a codebase overview. For what we are working on next and tracked issues, see [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

External contributors must sign Cue's contributor agreement before a pull request can be merged. See the [CLA policy](docs/CLA_POLICY.md).

## License

Cue is licensed under [GPL-3.0-only](LICENSE).

If someone distributes a modified version of Cue, they must also share the source code for that modified version under the same license.

For redistributed third-party components in packaged Windows builds, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

For end-user legal terms and privacy details, see [TERMS.md](TERMS.md) and [PRIVACY.md](PRIVACY.md).

## Acknowledgments

Cue uses:

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Whisper via CTranslate2)
- [WhisperX](https://github.com/m-bain/whisperX) (word-level alignment)
- [FFmpeg](https://ffmpeg.org/)
- [Tauri](https://tauri.app/)
- [React](https://react.dev/)
