# Architecture Overview

For contributors: how Cue is wired together (system layout, pipeline, repo map, and where files land on disk).

For setup and development instructions, see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## System overview

Cue is a desktop app with two main layers:

```
+---------------------------------------------+
|         Desktop UI (Tauri + React)           |
|   desktop/src/  —  TypeScript / React        |
+---------------------------------------------+
        |  HTTP + SSE (localhost)
        v
+---------------------------------------------+
|         Backend (Python / FastAPI)            |
|   app/backend_server.py                      |
|   Runs as a local server on 127.0.0.1        |
+---------------------------------------------+
        |  Subprocess calls
        v
+---------------------------------------------+
|         Processing pipeline                  |
|   FFmpeg  |  faster-whisper  |  WhisperX     |
+---------------------------------------------+
```

- **Desktop UI** — A Tauri + React app (`desktop/`) that provides the user interface. Communicates with the backend over HTTP and Server-Sent Events (SSE).
- **Backend** — A Python FastAPI server (`app/backend_server.py`) that manages jobs, settings, and device info. Spawns pipeline workers as subprocesses.
- **Pipeline** — The actual work: audio extraction (FFmpeg), transcription (faster-whisper), word alignment (WhisperX), and subtitle burn-in (FFmpeg with graphics overlay).

---

## Processing pipeline

When a user creates subtitles and exports a video, the pipeline runs these steps:

```
Video file
  |
  v
1. Audio extraction (FFmpeg)
  |  Extracts mono 16 kHz WAV from the video.
  |  Optional audio cleanup filter (highpass, lowpass, noise reduction, loudnorm).
  v
2. Transcription (faster-whisper)
  |  Runs the Whisper large-v3 model on the extracted audio.
  |  Outputs raw segments with timestamps.
  |  Includes punctuation rescue (re-runs if punctuation is poor).
  |  Includes VAD gap rescue (re-transcribes silent gaps with VAD off).
  v
3. SRT generation
  |  Splits long segments into readable subtitle cues.
  |  Writes a standard .srt file.
  v
4. Word alignment (WhisperX)
  |  Aligns individual words to precise timestamps.
  |  Produces a .word_timings.json file.
  |  Required for Word Highlight mode.
  v
5. Subtitle styling + preview
  |  Graphics renderer draws subtitles onto video frames.
  |  Preview stills use the same renderer as export.
  v
6. Export / burn-in (FFmpeg)
     Graphics overlay renderer streams RGBA frames to FFmpeg.
     FFmpeg composites subtitles over the original video.
     Outputs a new MP4 with subtitles baked in.
```

Transcription runs as a **separate subprocess** to keep the UI responsive, enable reliable cancellation, and isolate native dependency crashes.

---

## Repo layout

```
app/                              # Python backend and pipeline
  backend_server.py               # FastAPI server (health, jobs, settings, device)
  project_store.py                # Project persistence (project folders, index, manifest)
  worker_runner.py                # Runs pipeline Worker in a Qt-safe subprocess
  workers.py                      # Audio extraction, worker orchestration, burn-in
  transcribe_worker.py            # Whisper transcription subprocess
  align_worker.py                 # WhisperX word-timing alignment
  align_utils.py                  # Alignment planning + staleness checks
  graphics_overlay_export.py      # Graphics overlay export (RGBA streaming to FFmpeg)
  graphics_preview_renderer.py    # Preview still rendering (subtitle graphics on frames)
  srt_splitter.py                 # Splits Whisper segments into subtitle cues
  srt_utils.py                    # SRT formatting primitives
  subtitle_style.py               # Style presets and normalization
  word_timing_schema.py           # Word timing JSON contract + validation
  progress.py                     # Progress aggregation and step weights
  ffmpeg_utils.py                 # FFmpeg/FFprobe discovery and subprocess helpers
  config.py                       # Settings persistence (config.json)
  paths.py                        # App data directory resolution

desktop/                          # Tauri + React desktop app
  src/                            # React frontend (TypeScript)
    pages/                        # ProjectHub, Workbench, Settings screens
    components/                   # UI components (shadcn/Tailwind)
    jobsClient.ts                 # Backend job API client
    settingsClient.ts             # Backend settings API client
  src-tauri/                      # Tauri/Rust backend shell
  package.json
  vite.config.ts

bin/                              # Bundled FFmpeg/FFprobe binaries
docs/                             # Documentation
  CONTRIBUTING.md                 # Setup and development guide
  ARCHITECTURE.md                 # This file
  ROADMAP.md                      # Product roadmap (published)
  KNOWN_ISSUES.md                 # Detailed issue tracking (published)
tests/                            # Test suite (pytest)
tools/                            # Developer utilities (benchmarks, packaging)
scripts/                          # Dev workflow scripts (Windows cmd/ps1)
```

### Key files to read first

If you are new to the codebase, start here:

1. **`app/backend_server.py`** — The FastAPI server that the desktop UI talks to. Defines job endpoints and SSE event streaming.
2. **`app/workers.py`** — Orchestrates audio extraction, transcription subprocesses, FFmpeg burn-in, and progress reporting.
3. **`app/transcribe_worker.py`** — The transcription subprocess. Loads the Whisper model, runs transcription, applies punctuation rescue, and writes the SRT file.
4. **`desktop/src/pages/Workbench.tsx`** — The unified editor/export surface. Handles subtitle creation, on-video text editing, styling, export progress, cancel, and success actions.
5. **`desktop/src/pages/ProjectHub.tsx`** — The project list and entry point (**Add video**, relink, delete, and related project actions).
6. **`desktop/src/pages/TabHost.tsx`** — Renders the Home panel (`ProjectHub`) plus one mounted `Workbench` per open tab; URL `/` vs `/workbench/:projectId` stays in sync with the title-bar tab strip.
7. **`desktop/src/pages/Settings.tsx`** — Settings content for the right-hand sheet opened from the title bar (transcription quality, save policy, audio options, diagnostics).

---

## Where data lives

### App data (Windows)

`%LOCALAPPDATA%\Cue\` contains:

| Folder/file | Purpose |
|---|---|
| `config.json` | User settings |
| `models/` | Downloaded Whisper model files (1-3 GB) |
| `logs/` | Runtime log files (timestamped) |
| `cache/thumbs/` | Video thumbnail cache |
| `cache/preview_frames/` | Subtitle preview frame cache |
| `projects/` | Project folders + `index.json` + per-project `project.json` |

### Per-video outputs

Output files are placed according to the Save Policy setting:

- **Same folder as the video** (default) — outputs live next to the original video.
- **Specific folder** — outputs go to a fixed folder set in Settings.
- **Ask every time** — the user picks the folder each run.

Files produced per video:

| File | Description |
|---|---|
| `<video>_audio_for_whisper.wav` | Extracted audio (deleted after transcription unless "Keep WAV" is on) |
| `<video>.srt` | Subtitle file (UTF-8) |
| `<video>.word_timings.json` | Word-level timestamps for highlight mode |
| `<video>_subtitled.mp4` | Final video with subtitles burned in |

---

## Communication between UI and backend

The desktop UI communicates with the Python backend over HTTP:

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Backend health check (used by dev scripts to wait for startup) |
| `/jobs` | POST | Create a new job (create subtitles or export video) |
| `/jobs/{id}/events` | GET | SSE event stream for job progress |
| `/jobs/{id}/cancel` | POST | Cancel a running job |
| `/projects` | GET/POST | List or create projects |
| `/projects/{id}` | GET/PUT/DELETE | Fetch, update, or delete a project |
| `/projects/{id}/subtitles` | GET | Fetch stored project subtitles (SRT text) |
| `/projects/{id}/relink` | POST | Relink a missing source video |
| `/settings` | GET/PUT | Read or update app settings |
| `/preview-style` | POST | Render a styled preview still and return a file path |
| `/device` | GET | GPU/device info for the settings UI |

Jobs emit typed SSE events: `started`, `checklist`, `progress`, `log`, `result`, `heartbeat`, `completed`, `cancelled`, `error`.
`POST /jobs` accepts an optional `project_id`; for export jobs, `project_id` is the preferred contract and the backend resolves project artifacts (video, subtitles, style, word timings).
