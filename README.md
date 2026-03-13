# Cue

Create subtitles for any video, in any language, right on your computer.

Cue is a desktop app that uses AI speech recognition to generate subtitles and burn them directly into your video. Everything runs locally on your machine — no uploads, no cloud, no subscriptions.

## Screenshots

<!-- TODO: Add 2-3 screenshots or a GIF of the app once the UI is stable. -->

## Features

- **Automatic subtitles** — Drop a video in, get an SRT subtitle file out. Powered by Whisper large-v3.
- **Burn subtitles into video** — Export a new MP4 with subtitles baked in. No extra tools needed.
- **Word-by-word highlighting** — Karaoke-style word highlighting that follows the speaker in real time.
- **Style customization** — Choose from presets or customize fonts, colors, outlines, shadows, and backgrounds.
- **Any language** — Automatic language detection. Supports all languages that Whisper supports.
- **RTL support** — Full right-to-left rendering for Hebrew, Arabic, and other RTL languages.
- **GPU acceleration** — Uses your GPU (CUDA) when available for faster transcription. Falls back to CPU automatically.
- **Runs offline** — Everything runs locally. Your videos never leave your computer.
- **Open source** — Free to use. Built on top of open-source tools.

## Download and install

### Windows

<!-- TODO: Add download link to the latest .msi or .exe installer once packaging is ready. -->

Download the latest installer from the [Releases](../../releases) page and run it.

Windows releases currently ship x64 installers only.

The NSIS `.exe` installer shows Cue's GPL license during setup and installs `THIRD_PARTY_NOTICES.md` with the app.

### macOS

<!-- TODO: Add download link to the latest .dmg once macOS packaging is ready. -->

macOS support is planned. Check the [Releases](../../releases) page for updates.

### Build from source

If you want to run the app from source or contribute, see the [Contributing guide](docs/CONTRIBUTING.md).

## Quick start

1. **Open the app** and drop a video file into the window (or click "Choose video...").
2. **Click "Create subtitles"** and wait for the AI to transcribe. The first run downloads the language model, which may take a few minutes.
3. **Review and style your subtitles** — the app opens a “Review subtitles” screen where you can pick a style, choose between static or word-highlight mode, and adjust colors.
4. **Click "Create video with subtitles"** to export a new MP4 with subtitles burned in.

Your subtitle file (`.srt`) and the new video appear next to the original video by default. You can change the save location in Settings.

## How it works

Cue extracts the audio from your video, runs it through [Whisper](https://github.com/openai/whisper) (via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) to generate subtitles, and then uses [FFmpeg](https://ffmpeg.org/) to burn them into a new video. Word-level timing for the highlight mode comes from [WhisperX](https://github.com/m-bain/whisperX) alignment.

For a deeper technical overview, see the [Architecture guide](docs/ARCHITECTURE.md).

## Contributing

Contributions are welcome. See the [Contributing guide](docs/CONTRIBUTING.md) for setup instructions and the [Architecture guide](docs/ARCHITECTURE.md) for a codebase overview.

External contributors must sign Cue's contributor agreement before a pull request can be merged. See the [CLA policy](docs/CLA_POLICY.md).

## License

Cue is licensed under [GPL-3.0-only](LICENSE).

If someone distributes a modified version of Cue, they must also share the source code for that modified version under the same license.

For redistributed third-party components in packaged Windows builds, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Acknowledgments

Cue is built on top of these excellent open-source projects:

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Fast Whisper transcription with CTranslate2
- [WhisperX](https://github.com/m-bain/whisperX) — Word-level timestamp alignment
- [FFmpeg](https://ffmpeg.org/) — Audio/video processing
- [Tauri](https://tauri.app/) — Desktop app framework
- [React](https://react.dev/) — UI framework
