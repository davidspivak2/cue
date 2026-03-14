from __future__ import annotations

# Qt app must be ensured before other imports that may use Qt. Imports below are intentional.
def _ensure_qt_app() -> None:
    try:
        from PySide6 import QtGui
    except Exception:
        return

    if QtGui.QGuiApplication.instance() is None:
        QtGui.QGuiApplication([])

_ensure_qt_app()

import argparse
import contextlib
from contextlib import asynccontextmanager
import asyncio
import json
import logging
import mimetypes
import os
import re
import subprocess
import signal
import sys
import tempfile
import threading
import time
from urllib.parse import unquote
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import project_store
from app.config import apply_config_defaults
from app.ffmpeg_utils import ensure_ffmpeg_available, get_subprocess_kwargs
from app.paths import (
    get_app_data_dir,
    get_config_path,
    get_diagnostics_dir,
    get_logs_dir,
    get_projects_dir,
)
from app.backend_pipeline_adapter import _resolve_device_and_compute
from app.transcription_device import (
    get_cpu_cores,
    get_gpu_name,
    gpu_available,
    ultra_available,
    ultra_device,
)
from app.transcription_rtf import get_rtf_est, get_rtf_est_for_device


HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT = DEFAULT_PORT
PING_INTERVAL_SECONDS = 12.0
RUNNER_CANCEL_TIMEOUT_SECONDS = 8.0
PROJECT_DELETE_CANCEL_TIMEOUT_SECONDS = 3.0
BROWSER_UPLOAD_FILENAME_HEADER = "x-cue-filename"
SUPPORTED_BROWSER_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".m4v", ".webm"}

logger = logging.getLogger(__name__)
_startup_warmup_task: Optional[asyncio.Task[None]] = None
BACKEND_SESSION_STARTED_AT = time.time()


async def _run_startup_warmup() -> None:
    logger.info("Startup warmup: begin")
    try:
        ffmpeg_path, ffprobe_path, mode = await asyncio.to_thread(ensure_ffmpeg_available)
        if ffprobe_path:
            logger.info(
                "Startup warmup: ffmpeg ready (mode=%s, ffmpeg=%s, ffprobe=%s)",
                mode,
                ffmpeg_path,
                ffprobe_path,
            )
        else:
            logger.info(
                "Startup warmup: ffmpeg ready (mode=%s, ffmpeg=%s, ffprobe missing)",
                mode,
                ffmpeg_path,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup warmup: ffmpeg check failed: %s", exc)

    try:
        from app.backend_inprocess_worker import warmup_inprocess_runtime

        warmup = await asyncio.to_thread(warmup_inprocess_runtime)
        if warmup.get("ok"):
            logger.info(
                "Startup warmup: in-process worker ready in %sms",
                warmup.get("elapsed_ms", 0),
            )
        else:
            logger.warning(
                "Startup warmup: in-process worker warmup skipped (%s)",
                warmup.get("error") or "unknown error",
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup warmup: in-process worker warmup failed: %s", exc)
    logger.info("Startup warmup: complete")


@asynccontextmanager
async def _app_lifespan(app: FastAPI):  # noqa: ARG001
    global _queue_worker_tasks, _startup_warmup_task
    _queue_worker_tasks = [
        asyncio.create_task(_queue_worker_create_subtitles()),
    ]
    for _ in range(EXPORT_CONCURRENCY):
        _queue_worker_tasks.append(asyncio.create_task(_queue_worker_export()))
    _startup_warmup_task = asyncio.create_task(_run_startup_warmup())
    yield
    if _startup_warmup_task is not None:
        _startup_warmup_task.cancel()
        try:
            await _startup_warmup_task
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 - ensure shutdown completes
            pass
        _startup_warmup_task = None
    for task in _queue_worker_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001 - ensure shutdown completes
            pass
    # Do not create exit archive here. Archiving runs only when the desktop
    # explicitly requests it via POST /diagnostics/archive-on-exit (on app exit).
    # Otherwise a zip would be created on startup when run_desktop_all is used:
    # the script starts the backend, then Tauri spawns a second backend that
    # fails to bind (port in use); that process's lifespan shutdown would run
    # and create a bundle.
    _queue_worker_tasks = []


app = FastAPI(lifespan=_app_lifespan)
ALLOWED_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

TERMINAL_STATUSES = {"completed", "cancelled", "error"}
UI_ONLY_JOB_OPTION_KEYS = {
    "selectedCueId",
    "selected_cue_id",
    "selectedCue",
    "selected_cue",
    "selection",
    "selectionOutline",
    "selection_outline",
    "uiSelection",
    "ui_selection",
}
ACTIVE_TASK_JOB_KINDS = {"create_subtitles", "create_video_with_subtitles"}
MAX_JOB_EVENT_QUEUE_SIZE = 600
TASK_NOTICE_TTL_SECONDS = 600
SSE_CONFLICT_WARN_INTERVAL_SECONDS = 10.0
CHECKLIST_LABEL_BY_STEP_ID = {
    "extract_audio": "Extracting audio",
    "load_model": "Loading AI model",
    "detect_language": "Detecting language",
    "write_subtitles": "Writing subtitles",
    "fix_punctuation": "Reviewing punctuation",
    "fix_missing_subtitles": "Making sure no words were missed",
    "timing_word_highlights": "Building word-by-word karaoke effect",
    "preparing_preview": "Preparing preview",
    "get_video_info": "Getting video info",
    "add_subtitles": "Adding subtitles to video",
    "save_video": "Saving video",
}
PROGRESS_STEP_TO_CHECKLIST_STEP_ID = {
    "PREPARE_AUDIO": "extract_audio",
    "TRANSCRIBE": "load_model",
    "FIX_PUNCTUATION": "fix_punctuation",
    "FIX_GAPS": "fix_missing_subtitles",
    "ALIGN_WORDS": "timing_word_highlights",
    "PREPARING_PREVIEW": "preparing_preview",
}


@dataclass
class JobState:
    job_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    kind: str = "demo"
    project_id: Optional[str] = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    event_queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    sse_client_connected: bool = False
    task: Optional[asyncio.Task[None]] = None
    process: Optional[asyncio.subprocess.Process] = None
    snapshot_heading: Optional[str] = None
    snapshot_message: Optional[str] = None
    snapshot_pct: Optional[float] = None
    snapshot_step_id: Optional[str] = None
    snapshot_updated_at: Optional[str] = None
    snapshot_checklist_order: list[str] = field(default_factory=list)
    snapshot_checklist: dict[str, dict[str, Any]] = field(default_factory=dict)
    enqueue_lock: threading.Lock = field(default_factory=threading.Lock)
    trace_path: Optional[Path] = None
    trace_warn_at: float = 0.0


JOBS: dict[str, JobState] = {}
PROJECT_TASK_NOTICES: dict[str, dict[str, Any]] = {}
SSE_CONFLICT_WARN_AT: dict[str, float] = {}
_inprocess_slot_lock: asyncio.Lock = asyncio.Lock()

# Per-kind job queues: (JobState, JobRequest). Workers run jobs; create_job enqueues.
_create_subtitles_queue: asyncio.Queue[tuple[JobState, JobRequest]] = asyncio.Queue()
_export_queue: asyncio.Queue[tuple[JobState, JobRequest]] = asyncio.Queue()
_queue_worker_tasks: list[asyncio.Task[None]] = []
EXPORT_CONCURRENCY = 10


class JobRequest(BaseModel):
    kind: Literal[
        "demo",
        "pipeline",
        "create_subtitles",
        "create_video_with_subtitles",
        "calibrate",
    ] = "pipeline"
    input_path: Optional[str] = None
    output_dir: Optional[str] = None
    srt_path: Optional[str] = None
    word_timings_path: Optional[str] = None
    style_path: Optional[str] = None
    options: dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


class PreviewStyleRequest(BaseModel):
    video_path: str
    srt_path: str
    timestamp: Optional[float] = None
    subtitle_style: dict[str, Any] = Field(default_factory=dict)
    subtitle_mode: str = "static"
    highlight_color: str = "#FFD400"
    highlight_opacity: float = 1.0


class PreviewOverlayRequest(BaseModel):
    width: int
    height: int
    subtitle_text: str = ""
    highlight_word_index: Optional[int] = None
    subtitle_style: dict[str, Any] = Field(default_factory=dict)
    subtitle_mode: str = "static"
    highlight_color: str = "#FFD400"
    highlight_opacity: float = 1.0


class ProjectCreateRequest(BaseModel):
    video_path: str
    style: dict[str, Any] = Field(default_factory=dict)

    def to_project_store_kwargs(self) -> dict[str, Any]:
        return self.model_dump()


class ProjectUpdateRequest(BaseModel):
    subtitles_srt_text: Optional[str] = None
    style: Optional[dict[str, Any]] = None

    def to_project_store_kwargs(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class ProjectRelinkRequest(BaseModel):
    video_path: str


VALID_SAVE_POLICIES = {"same_folder", "fixed_folder", "ask_every_time"}
VALID_TRANSCRIPTION_QUALITIES = {"auto", "speed", "quality", "ultra"}
LEGACY_QUALITY_TO_NEW = {"fast": "speed", "accurate": "auto"}
VALID_INTERFACE_SCALES = (1.0, 1.1, 1.25, 1.5)
DEFAULT_INTERFACE_SCALE = 1.0
DEFAULT_DIAGNOSTICS_CATEGORIES = {
    "app_system": True,
    "video_info": True,
    "audio_info": True,
    "transcription_config": True,
    "srt_stats": True,
    "commands_timings": True,
}


def _normalize_settings(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    data = apply_config_defaults(raw)

    save_policy = data.get("save_policy")
    if save_policy not in VALID_SAVE_POLICIES:
        data["save_policy"] = "same_folder"

    save_folder = data.get("save_folder")
    if not isinstance(save_folder, str):
        data["save_folder"] = ""

    transcription_quality = data.get("transcription_quality")
    if transcription_quality in LEGACY_QUALITY_TO_NEW:
        data["transcription_quality"] = LEGACY_QUALITY_TO_NEW[transcription_quality]
    elif transcription_quality not in VALID_TRANSCRIPTION_QUALITIES:
        data["transcription_quality"] = "quality"
    if data["transcription_quality"] == "ultra" and not ultra_available():
        data["transcription_quality"] = "quality"

    interface_scale = data.get("interface_scale")
    if isinstance(interface_scale, bool):
        data["interface_scale"] = DEFAULT_INTERFACE_SCALE
    elif isinstance(interface_scale, (int, float)):
        numeric_scale = float(interface_scale)
        matched_scale = next(
            (
                option
                for option in VALID_INTERFACE_SCALES
                if abs(option - numeric_scale) < 0.001
            ),
            None,
        )
        data["interface_scale"] = (
            matched_scale if matched_scale is not None else DEFAULT_INTERFACE_SCALE
        )
    else:
        data["interface_scale"] = DEFAULT_INTERFACE_SCALE

    data["punctuation_rescue_fallback_enabled"] = (
        data.get("punctuation_rescue_fallback_enabled")
        if isinstance(data.get("punctuation_rescue_fallback_enabled"), bool)
        else True
    )
    data["apply_audio_filter"] = (
        data.get("apply_audio_filter")
        if isinstance(data.get("apply_audio_filter"), bool)
        else False
    )
    data["keep_extracted_audio"] = (
        data.get("keep_extracted_audio")
        if isinstance(data.get("keep_extracted_audio"), bool)
        else False
    )

    raw_diagnostics = data.get("diagnostics")
    if not isinstance(raw_diagnostics, dict):
        diagnostics = {
            "enabled": False,
            "write_on_success": False,
            "archive_on_exit": False,
            "categories": DEFAULT_DIAGNOSTICS_CATEGORIES.copy(),
            "render_timing_logs_enabled": False,
        }
    else:
        categories = DEFAULT_DIAGNOSTICS_CATEGORIES.copy()
        raw_categories = raw_diagnostics.get("categories")
        if isinstance(raw_categories, dict):
            for key in categories:
                if isinstance(raw_categories.get(key), bool):
                    categories[key] = raw_categories[key]
        diagnostics = {
            "enabled": raw_diagnostics.get("enabled")
            if isinstance(raw_diagnostics.get("enabled"), bool)
            else False,
            "write_on_success": raw_diagnostics.get("write_on_success")
            if isinstance(raw_diagnostics.get("write_on_success"), bool)
            else False,
            "archive_on_exit": raw_diagnostics.get("archive_on_exit")
            if isinstance(raw_diagnostics.get("archive_on_exit"), bool)
            else False,
            "categories": categories,
            "render_timing_logs_enabled": raw_diagnostics.get("render_timing_logs_enabled")
            if isinstance(raw_diagnostics.get("render_timing_logs_enabled"), bool)
            else False,
        }

    data["diagnostics"] = diagnostics
    return data


def _browser_uploads_dir() -> Path:
    path = get_app_data_dir() / "browser_uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _decode_upload_filename(raw_value: Optional[str]) -> str:
    decoded = unquote((raw_value or "").strip())
    if not decoded:
        raise HTTPException(status_code=422, detail="upload_filename_required")
    return decoded


def _sanitize_upload_filename(filename: str) -> str:
    original = Path(filename).name.strip()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original).stem).strip("._")
    suffix = Path(original).suffix.lower()
    if suffix not in SUPPORTED_BROWSER_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=422, detail="unsupported_video_type")
    return f"{stem or 'video'}{suffix}"


async def _save_browser_upload(request: Request) -> str:
    filename = _decode_upload_filename(request.headers.get(BROWSER_UPLOAD_FILENAME_HEADER))
    safe_name = _sanitize_upload_filename(filename)
    destination = _browser_uploads_dir() / f"{uuid.uuid4().hex}_{safe_name}"
    total_bytes = 0
    try:
        with destination.open("wb") as handle:
            async for chunk in request.stream():
                if not chunk:
                    continue
                total_bytes += len(chunk)
                handle.write(chunk)
    except Exception as exc:  # noqa: BLE001
        with contextlib.suppress(OSError):
            destination.unlink()
        raise HTTPException(status_code=500, detail="upload_write_failed") from exc
    if total_bytes == 0:
        with contextlib.suppress(OSError):
            destination.unlink()
        raise HTTPException(status_code=422, detail="upload_empty")
    return str(destination)


def _resolve_local_file(raw_path: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise HTTPException(status_code=422, detail="path_required")
    try:
        resolved = Path(raw_path).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="local_file_not_found") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="local_file_invalid") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="local_file_not_found")
    return resolved


def _read_settings_file() -> dict[str, Any]:
    config_path = get_config_path()
    if not config_path.exists():
        return _normalize_settings({})
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    return _normalize_settings(raw)


def _write_settings_file(settings: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_settings(settings)
    config_path = get_config_path()
    config_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return normalized


def _merge_settings(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base) if isinstance(base, dict) else {}
    if not isinstance(update, dict):
        return merged
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_settings(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def _is_file_from_current_session(path: Path) -> bool:
    try:
        return path.stat().st_mtime >= BACKEND_SESSION_STARTED_AT - 1.0
    except OSError:
        return False


def _parse_project_updated_at_ts(value: Any) -> float:
    if not isinstance(value, str) or not value.strip():
        return 0.0
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return 0.0


def _collect_exit_archive_entries(
    *,
    project_id: str,
    video_path: Path,
    latest_export: Optional[dict[str, Any]],
    zip_path: Path,
) -> list[tuple[Path, str]]:
    entries: dict[str, Path] = {}

    logs_dir = get_logs_dir()
    if logs_dir.exists():
        for path in logs_dir.glob("*.log"):
            if path.is_file() and _is_file_from_current_session(path):
                entries.setdefault(f"logs/{path.name}", path)
        for path in logs_dir.glob("job_trace_*.jsonl"):
            if path.is_file() and _is_file_from_current_session(path):
                entries.setdefault(f"job_traces/{path.name}", path)

    diagnostics_dir = get_diagnostics_dir()
    if diagnostics_dir.exists():
        for path in diagnostics_dir.glob("diag_*.json"):
            if path.is_file() and _is_file_from_current_session(path):
                entries.setdefault(f"diagnostics/{path.name}", path)

    project_dir = get_projects_dir() / project_id
    for artifact_name in ("subtitles.srt", "word_timings.json", "style.json"):
        artifact_path = project_dir / artifact_name
        if artifact_path.exists() and artifact_path.is_file():
            entries.setdefault(f"project/{artifact_name}", artifact_path)

    stem = video_path.stem
    output_dir = video_path.parent
    if output_dir.exists():
        for path in output_dir.iterdir():
            if not path.is_file():
                continue
            if path == video_path or path == zip_path:
                continue
            if path.name.startswith(stem):
                entries.setdefault(f"outputs/{path.name}", path)
            elif path.name.startswith("diag_") and _is_file_from_current_session(path):
                entries.setdefault(f"outputs/{path.name}", path)

    if isinstance(latest_export, dict):
        output_value = latest_export.get("output_video_path")
        if isinstance(output_value, str) and output_value:
            output_path = Path(output_value)
            if (
                output_path.exists()
                and output_path.is_file()
                and output_path != video_path
                and output_path != zip_path
            ):
                entries.setdefault(f"outputs/{output_path.name}", output_path)

    return [(path, arcname) for arcname, path in entries.items()]


def _archive_exit_bundle_for_project(
    *,
    project_id: str,
    video_path: Path,
    latest_export: Optional[dict[str, Any]],
) -> Optional[Path]:
    destination_dir = video_path.parent
    if not destination_dir.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    zip_path = destination_dir / f"cue_log_bundle_{timestamp}.zip"
    entries = _collect_exit_archive_entries(
        project_id=project_id,
        video_path=video_path,
        latest_export=latest_export,
        zip_path=zip_path,
    )
    if not entries:
        return None
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source, arcname in entries:
                archive.write(source, arcname)
    except Exception:
        with contextlib.suppress(OSError):
            zip_path.unlink(missing_ok=True)
        raise
    return zip_path


_exit_archive_created_this_session: bool = False


def _archive_exit_bundles() -> list[str]:
    global _exit_archive_created_this_session
    if _exit_archive_created_this_session:
        return []
    settings = _read_settings_file()
    diagnostics = settings.get("diagnostics") if isinstance(settings, dict) else None
    archive_on_exit = (
        diagnostics.get("archive_on_exit")
        if isinstance(diagnostics, dict) and isinstance(diagnostics.get("archive_on_exit"), bool)
        else False
    )
    if not archive_on_exit:
        return []

    summaries = project_store.list_projects()
    latest_candidate: tuple[Any, float] | None = None
    for summary in summaries:
        project_id = getattr(summary, "project_id", None)
        video_path_text = getattr(summary, "video_path", None)
        if not isinstance(project_id, str) or not project_id:
            continue
        if not isinstance(video_path_text, str) or not video_path_text:
            continue
        video_path = Path(video_path_text)
        if not video_path.exists() or not video_path.is_file():
            continue
        updated_ts = _parse_project_updated_at_ts(getattr(summary, "updated_at", None))
        if latest_candidate is None or updated_ts >= latest_candidate[1]:
            latest_candidate = (summary, updated_ts)

    if latest_candidate is None:
        return []

    summary = latest_candidate[0]
    project_id = getattr(summary, "project_id", "")
    video_path = Path(getattr(summary, "video_path", ""))
    latest_export = getattr(summary, "latest_export", None)
    try:
        zip_path = _archive_exit_bundle_for_project(
            project_id=project_id,
            video_path=video_path,
            latest_export=latest_export if isinstance(latest_export, dict) else None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Exit archive failed for project %s (%s): %s",
            project_id,
            video_path,
            exc,
        )
        return []
    if zip_path is not None:
        _exit_archive_created_this_session = True  # noqa: PLW0603
    return [str(zip_path)] if zip_path is not None else []


def _resolve_output_dir_for_export(
    video_path: str,
    requested_output_dir: Optional[str],
) -> str:
    if isinstance(requested_output_dir, str) and requested_output_dir.strip():
        return requested_output_dir
    settings = _read_settings_file()
    save_policy = settings.get("save_policy")
    if save_policy == "fixed_folder":
        save_folder = settings.get("save_folder")
        if isinstance(save_folder, str) and save_folder.strip():
            return save_folder
        raise HTTPException(status_code=422, detail="save_folder_required")
    # For same_folder and ask_every_time, backend uses the source video folder.
    return str(Path(video_path).parent)


def _resolve_export_request_from_project(payload: JobRequest) -> None:
    if payload.kind != "create_video_with_subtitles" or not payload.project_id:
        return
    artifacts = project_store.get_project_export_artifacts(payload.project_id)
    video_path = artifacts.get("video_path")
    subtitles_path = artifacts.get("subtitles_path")
    if not isinstance(video_path, str) or not video_path:
        raise HTTPException(status_code=422, detail="project_video_missing")
    if not isinstance(subtitles_path, str) or not subtitles_path:
        raise HTTPException(status_code=422, detail="project_subtitles_missing")
    payload.input_path = video_path
    payload.srt_path = subtitles_path
    payload.output_dir = _resolve_output_dir_for_export(video_path, payload.output_dir)
    payload.word_timings_path = artifacts.get("word_timings_path")
    payload.style_path = artifacts.get("style_path")


def _reuses_existing_subtitles(payload: JobRequest) -> bool:
    if payload.kind != "create_subtitles":
        return False
    options = payload.options if isinstance(payload.options, dict) else {}
    return bool(options.get("reuse_existing_subtitles"))


def _resolve_create_subtitles_request_from_project(payload: JobRequest) -> None:
    if not payload.project_id or not _reuses_existing_subtitles(payload):
        return
    artifacts = project_store.get_project_export_artifacts(payload.project_id)
    video_path = artifacts.get("video_path")
    subtitles_path = artifacts.get("subtitles_path")
    if isinstance(video_path, str) and video_path:
        payload.input_path = video_path
    if isinstance(subtitles_path, str) and subtitles_path:
        payload.srt_path = subtitles_path
    payload.word_timings_path = artifacts.get("word_timings_path")


def _resolve_port() -> int:
    raw = os.getenv("CUE_BACKEND_PORT")
    if not raw:
        return DEFAULT_PORT
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid CUE_BACKEND_PORT=%s, falling back to %s", raw, DEFAULT_PORT)
        return DEFAULT_PORT


PORT = _resolve_port()


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_timestamp(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _checklist_label(step_id: str) -> str:
    label = CHECKLIST_LABEL_BY_STEP_ID.get(step_id)
    if label:
        return label
    return step_id.replace("_", " ").strip().title()


def _canonical_snapshot_step_id(step_id: str) -> str:
    return PROGRESS_STEP_TO_CHECKLIST_STEP_ID.get(step_id, step_id)


def _ensure_snapshot_checklist_step(job: JobState, step_id: str) -> dict[str, Any]:
    row = job.snapshot_checklist.get(step_id)
    if row is None:
        row = {
            "id": step_id,
            "label": _checklist_label(step_id),
            "state": "pending",
            "detail": None,
        }
        job.snapshot_checklist[step_id] = row
        job.snapshot_checklist_order.append(step_id)
    elif not isinstance(row.get("label"), str) or not str(row.get("label")).strip():
        row["label"] = _checklist_label(step_id)
    return row


def _cleanup_task_notices() -> None:
    now = datetime.now(timezone.utc)
    expired_project_ids: list[str] = []
    for project_id, notice in PROJECT_TASK_NOTICES.items():
        ts_text = notice.get("created_at")
        if not isinstance(ts_text, str):
            expired_project_ids.append(project_id)
            continue
        try:
            created_at = datetime.fromisoformat(ts_text)
        except ValueError:
            expired_project_ids.append(project_id)
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if (now - created_at).total_seconds() > TASK_NOTICE_TTL_SECONDS:
            expired_project_ids.append(project_id)
    for project_id in expired_project_ids:
        PROJECT_TASK_NOTICES.pop(project_id, None)


def _set_project_task_notice(job: JobState, event: dict[str, Any]) -> None:
    if not job.project_id:
        return
    message = event.get("message")
    if isinstance(message, str) and message.strip():
        detail = message.strip()
    elif str(event.get("type")) == "cancelled":
        detail = "Operation cancelled."
    else:
        detail = "Task failed."
    PROJECT_TASK_NOTICES[job.project_id] = {
        "notice_id": uuid.uuid4().hex,
        "project_id": job.project_id,
        "job_id": job.job_id,
        "kind": job.kind,
        "status": str(event.get("type") or job.status),
        "message": detail,
        "created_at": _now_ts(),
        "finished_at": _job_timestamp(job.finished_at),
    }


def _get_project_task_notice(project_id: str) -> Optional[dict[str, Any]]:
    _cleanup_task_notices()
    notice = PROJECT_TASK_NOTICES.get(project_id)
    if not notice:
        return None
    return dict(notice)


def _update_job_snapshot(job: JobState, event: dict[str, Any]) -> None:
    event_type = str(event.get("type") or "")
    event_ts = event.get("ts")
    if isinstance(event_ts, str) and event_ts:
        job.snapshot_updated_at = event_ts
    else:
        job.snapshot_updated_at = _now_ts()

    if event_type == "started":
        if isinstance(event.get("heading"), str) and str(event.get("heading")).strip():
            job.snapshot_heading = str(event.get("heading")).strip()
        if isinstance(event.get("message"), str) and str(event.get("message")).strip():
            job.snapshot_message = str(event.get("message")).strip()
        if job.project_id:
            PROJECT_TASK_NOTICES.pop(job.project_id, None)
        return

    if event_type == "checklist":
        step_id = event.get("step_id")
        if isinstance(step_id, str) and step_id:
            canonical_step_id = _canonical_snapshot_step_id(step_id)
            row = _ensure_snapshot_checklist_step(job, canonical_step_id)
            state = str(event.get("state") or "")
            if state == "start":
                row["state"] = "active"
                job.snapshot_step_id = canonical_step_id
            elif state in {"done", "skipped", "failed"}:
                row["state"] = state
            reason_text = event.get("reason_text")
            if isinstance(reason_text, str):
                detail = reason_text.strip()
                row["detail"] = detail or None
                if detail:
                    job.snapshot_message = detail
            if row.get("state") == "active":
                job.snapshot_step_id = canonical_step_id
        return

    if event_type == "progress":
        pct = event.get("pct")
        if isinstance(pct, (int, float)):
            clamped = max(0.0, min(float(pct), 100.0))
            job.snapshot_pct = clamped
        step_id = event.get("step_id")
        message = event.get("message")
        if isinstance(step_id, str) and step_id:
            canonical_step_id = _canonical_snapshot_step_id(step_id)
            row = _ensure_snapshot_checklist_step(job, canonical_step_id)
            if row.get("state") in {"pending", None, ""}:
                row["state"] = "active"
            if row.get("state") == "active":
                job.snapshot_step_id = canonical_step_id
        if isinstance(message, str) and message.strip():
            job.snapshot_message = message.strip()
        return

    if event_type in TERMINAL_STATUSES:
        job.status = event_type
        job.finished_at = datetime.now(timezone.utc)
        SSE_CONFLICT_WARN_AT.pop(job.job_id, None)
        message = event.get("message")
        if isinstance(message, str) and message.strip():
            job.snapshot_message = message.strip()
        if event_type in {"cancelled", "error"}:
            _set_project_task_notice(job, event)
        if event_type == "completed" and getattr(job, "kind", None) == "calibrate":
            try:
                if job.started_at and job.finished_at:
                    elapsed = (job.finished_at - job.started_at).total_seconds()
                    effective_sec = max(
                        0.0, elapsed - CALIBRATION_PREPARING_PREVIEW_SEC
                    )
                    rtf_speed_measured = effective_sec / 60.0
                    device_speed, compute_speed = _resolve_device_and_compute(
                        "speed", gpu_available_fn=gpu_available
                    )
                    rtf_speed_est = get_rtf_est(
                        "speed", device_speed, compute_speed
                    )
                    estimate_speed = int(
                        round(AUDIO_DURATION_5MIN_SEC * rtf_speed_measured)
                    )
                    device_auto, compute_auto = _resolve_device_and_compute(
                        "auto", gpu_available_fn=gpu_available
                    )
                    device_quality, compute_quality = _resolve_device_and_compute(
                        "quality", gpu_available_fn=gpu_available
                    )
                    rtf_auto = get_rtf_est(
                        "auto", device_auto, compute_auto
                    )
                    rtf_quality = get_rtf_est(
                        "quality", device_quality, compute_quality
                    )
                    estimate_5min_sec: dict[str, int] = {
                        "speed": estimate_speed,
                        "auto": int(
                            round(
                                AUDIO_DURATION_5MIN_SEC
                                * rtf_speed_measured
                                * (rtf_auto / rtf_speed_est)
                            )
                        ),
                        "quality": int(
                            round(
                                AUDIO_DURATION_5MIN_SEC
                                * rtf_speed_measured
                                * (rtf_quality / rtf_speed_est)
                            )
                        ),
                    }
                    if ultra_available():
                        device_ultra, compute_ultra = _resolve_device_and_compute(
                            "ultra", gpu_available_fn=gpu_available
                        )
                        rtf_ultra = get_rtf_est(
                            "ultra", device_ultra, compute_ultra
                        )
                        estimate_5min_sec["ultra"] = int(
                            round(
                                AUDIO_DURATION_5MIN_SEC
                                * rtf_speed_measured
                                * (rtf_ultra / rtf_speed_est)
                            )
                        )
                    _save_calibration_estimates(estimate_5min_sec)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Calibration save failed: %s", exc)


def _prune_job_event_queue(job: JobState) -> None:
    if job.event_queue.qsize() < MAX_JOB_EVENT_QUEUE_SIZE:
        return
    buffered: list[dict[str, Any]] = []
    dropped = False
    while True:
        try:
            event = job.event_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        event_type = str(event.get("type") or "")
        if not dropped and event_type not in TERMINAL_STATUSES:
            dropped = True
            continue
        buffered.append(event)
    if not dropped and buffered:
        buffered = buffered[1:]
    for event in buffered:
        job.event_queue.put_nowait(event)


def _build_event(job_id: str, event_type: str, **fields: Any) -> dict[str, Any]:
    payload = {"job_id": job_id, "ts": _now_ts(), "type": event_type}
    payload.update(fields)
    return payload


def _append_job_trace_event(job: JobState, event: dict[str, Any]) -> None:
    path = job.trace_path
    if path is None:
        return
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False))
            handle.write("\n")
    except Exception as exc:  # noqa: BLE001
        now = time.monotonic()
        if now - job.trace_warn_at >= 10.0:
            job.trace_warn_at = now
            logger.warning("Failed to append job trace %s: %s", path, exc)


def _enqueue_event(job: JobState, event: dict[str, Any]) -> None:
    with job.enqueue_lock:
        _update_job_snapshot(job, event)
        _append_job_trace_event(job, event)
        _prune_job_event_queue(job)
        job.event_queue.put_nowait(event)


async def _sleep_with_cancel(job: JobState, duration: float) -> bool:
    interval = 0.2
    elapsed = 0.0
    while elapsed < duration:
        if job.cancel_event.is_set():
            return False
        await asyncio.sleep(interval)
        elapsed += interval
    return True


def _mark_cancelled(job: JobState) -> None:
    job.status = "cancelled"
    job.finished_at = datetime.now(timezone.utc)
    _enqueue_event(job, _build_event(job.job_id, "cancelled", status=job.status))


async def _run_demo_job(job: JobState) -> None:
    try:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        _enqueue_event(job, _build_event(job.job_id, "started"))

        steps = [
            ("prepare", "Preparing demo inputs", [0, 10, 20]),
            ("work", "Running demo workload", [35, 50, 65]),
            ("finalize", "Finalizing demo output", [80, 90, 100]),
        ]

        for step_name, message, progress_points in steps:
            if job.cancel_event.is_set():
                _mark_cancelled(job)
                return
            _enqueue_event(
                job,
                _build_event(job.job_id, "step", step=step_name, message=message),
            )
            for pct in progress_points:
                if job.cancel_event.is_set():
                    _mark_cancelled(job)
                    return
                _enqueue_event(
                    job,
                    _build_event(job.job_id, "progress", pct=pct, message=message),
                )
                if not await _sleep_with_cancel(job, 1.0):
                    _mark_cancelled(job)
                    return

        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(job, _build_event(job.job_id, "completed", status=job.status))
    except Exception as exc:  # noqa: BLE001 - demo job should report errors to the stream
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(
            job,
            _build_event(job.job_id, "error", status=job.status, message=str(exc)),
        )


async def _run_pipeline_job(job: JobState, request: JobRequest) -> None:
    try:
        from .backend_pipeline_adapter import (
            PipelineCancelledError,
            PipelineDependencyError,
            run_pipeline_job,
        )
    except ImportError as exc:
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(
            job,
            _build_event(
                job.job_id,
                "error",
                status=job.status,
                message=f"Pipeline adapter failed to load: {exc}",
            ),
        )
        return

    try:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        _enqueue_event(job, _build_event(job.job_id, "started"))

        async def emit_event(event: dict[str, Any]) -> None:
            _enqueue_event(job, _build_event(job.job_id, event.pop("type", "message"), **event))

        await run_pipeline_job(
            input_path=request.input_path or "",
            output_dir=request.output_dir or "",
            options=request.options,
            cancel_event=job.cancel_event,
            emit_event=emit_event,
        )
        if job.cancel_event.is_set():
            _mark_cancelled(job)
            return
        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(job, _build_event(job.job_id, "completed", status=job.status))
    except PipelineDependencyError as exc:
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(
            job,
            _build_event(job.job_id, "error", status=job.status, message=str(exc)),
        )
    except PipelineCancelledError:
        _mark_cancelled(job)
    except Exception as exc:  # noqa: BLE001 - pipeline job should report errors to the stream
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(
            job,
            _build_event(job.job_id, "error", status=job.status, message=str(exc)),
        )


def _resolve_frozen_sibling_executable(exe_name: str) -> Optional[Path]:
    if not getattr(sys, "frozen", False):
        return None
    candidate = Path(sys.executable).resolve().with_name(exe_name)
    if candidate.exists():
        return candidate
    return None


def _build_runner_command(request: JobRequest) -> list[str]:
    task = "generate_srt" if request.kind == "create_subtitles" else "burn_in"
    if getattr(sys, "frozen", False):
        runner_exe = _resolve_frozen_sibling_executable("CueRunner.exe")
        if runner_exe is None:
            expected_path = Path(sys.executable).resolve().with_name("CueRunner.exe")
            raise RuntimeError(f"Missing packaged runner executable: {expected_path}")
        command = [str(runner_exe)]
    else:
        command = [
            sys.executable,
            "-m",
            "app.worker_runner",
        ]
    command += [
        "--task",
        task,
        "--video-path",
        request.input_path or "",
        "--output-dir",
        request.output_dir or "",
    ]
    if request.srt_path:
        command.extend(["--srt-path", request.srt_path])
    if request.word_timings_path:
        command.extend(["--word-timings-path", request.word_timings_path])
    if request.style_path:
        command.extend(["--style-path", request.style_path])
    options = {
        key: value
        for key, value in request.options.items()
        if isinstance(key, str)
        and key not in UI_ONLY_JOB_OPTION_KEYS
        and not key.startswith("ui_")
    }
    if options:
        command.extend(["--options-json", json.dumps(options)])
    return command


def _kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return


def _maybe_update_project_from_runner_event(
    request: JobRequest,
    event_type: str,
    event: dict[str, Any],
) -> None:
    project_id = request.project_id
    if not project_id:
        return
    try:
        if event_type == "started" and request.kind == "create_video_with_subtitles":
            project_store.set_project_status(project_id, "exporting")
            return
        if event_type == "result":
            payload = event.get("payload")
            if not isinstance(payload, dict):
                return
            if request.kind == "create_subtitles":
                project_store.record_subtitles_result(
                    project_id,
                    srt_path=payload.get("srt_path"),
                    word_timings_path=payload.get("word_timings_path"),
                )
                project_store.refresh_project_status(project_id)
            elif request.kind == "create_video_with_subtitles":
                exported_at = project_store.record_export_result(
                    project_id,
                    output_path=payload.get("output_path"),
                )
                if isinstance(exported_at, str) and isinstance(payload, dict):
                    payload["exported_at"] = exported_at
            return
        if event_type in {"cancelled", "error"}:
            project_store.refresh_project_status(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Project update failed for %s: %s", project_id, exc)


async def _run_inprocess_worker_job(job: JobState, request: JobRequest) -> None:
    from app.backend_inprocess_worker import run_worker_inprocess

    worker_ref: list[Any] = []

    def enqueue_event_cb(ev: dict[str, Any]) -> None:
        event_type = str(ev.pop("type", "message"))
        event = _build_event(job.job_id, event_type, **ev)
        _maybe_update_project_from_runner_event(request, event_type, event)
        _enqueue_event(job, event)

    async def watch_cancel_and_call_worker_cancel() -> None:
        await job.cancel_event.wait()
        if worker_ref:
            worker_ref[0].cancel()

    cancel_task = asyncio.create_task(watch_cancel_and_call_worker_cancel())
    try:
        await asyncio.to_thread(
            run_worker_inprocess,
            job.job_id,
            request,
            enqueue_event_cb,
            job.cancel_event,
            worker_ref,
        )
    finally:
        cancel_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cancel_task

    if job.status not in TERMINAL_STATUSES:
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(
            job,
            _build_event(
                job.job_id,
                "error",
                status=job.status,
                message="In-process worker exited without terminal event.",
            ),
        )


async def _run_worker_job_maybe_inprocess(job: JobState, request: JobRequest) -> None:
    if _inprocess_slot_lock.locked():
        await _run_runner_job(job, request)
        return
    try:
        async with _inprocess_slot_lock:
            await _run_inprocess_worker_job(job, request)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "In-process worker failed for job %s, falling back to runner: %s",
            job.job_id,
            exc,
        )
        await _run_runner_job(job, request)


async def _queue_worker_create_subtitles() -> None:
    while True:
        job, request = await _create_subtitles_queue.get()
        if job.cancel_event.is_set():
            _mark_cancelled(job)
            continue
        if job.status != "running":
            create_heading = (
                "Syncing karaoke timing"
                if _reuses_existing_subtitles(request)
                else "Creating subtitles"
            )
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            _enqueue_event(
                job,
                _build_event(
                    job.job_id,
                    "started",
                    heading=create_heading,
                    message="Preparing audio",
                ),
            )
            _enqueue_event(
                job,
                _build_event(
                    job.job_id,
                    "checklist",
                    step_id="extract_audio",
                    state="start",
                ),
            )
            _enqueue_event(
                job,
                _build_event(
                    job.job_id,
                    "progress",
                    step_id="PREPARE_AUDIO",
                    step_progress=0.0,
                    pct=0,
                    message="Extracting audio",
                ),
            )
        try:
            await _run_worker_job_maybe_inprocess(job, request)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Queue worker create_subtitles job %s failed: %s", job.job_id, exc)
            if job.status not in TERMINAL_STATUSES:
                job.status = "error"
                job.finished_at = datetime.now(timezone.utc)
                _enqueue_event(
                    job,
                    _build_event(
                        job.job_id,
                        "error",
                        status=job.status,
                        message=str(exc),
                    ),
                )


async def _queue_worker_export() -> None:
    while True:
        job, request = await _export_queue.get()
        if job.cancel_event.is_set():
            _mark_cancelled(job)
            continue
        if job.status != "running":
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            _enqueue_event(
                job,
                _build_event(
                    job.job_id,
                    "started",
                    heading="Creating video with subtitles",
                ),
            )
        try:
            await _run_worker_job_maybe_inprocess(job, request)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Queue worker export job %s failed: %s", job.job_id, exc)
            if job.status not in TERMINAL_STATUSES:
                job.status = "error"
                job.finished_at = datetime.now(timezone.utc)
                _enqueue_event(
                    job,
                    _build_event(
                        job.job_id,
                        "error",
                        status=job.status,
                        message=str(exc),
                    ),
                )


async def _run_runner_job(job: JobState, request: JobRequest) -> None:
    job.status = "running"
    if job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    try:
        command = _build_runner_command(request)
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(
            job,
            _build_event(
                job.job_id,
                "error",
                status=job.status,
                message=f"Failed to prepare runner command: {exc}",
            ),
        )
        return
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    spawn_start = datetime.now(timezone.utc)
    logger.info(
        "Job %s spawning runner after %.2fs",
        job.job_id,
        (spawn_start - job.created_at).total_seconds(),
    )
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            env=env,
            **get_subprocess_kwargs(),
        )
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(
            job,
            _build_event(
                job.job_id,
                "error",
                status=job.status,
                message=f"Failed to start runner: {exc}",
            ),
        )
        return

    job.process = process
    terminal_seen = False
    first_event_seen = False
    logger.info(
        "Job %s runner spawned after %.2fs",
        job.job_id,
        (datetime.now(timezone.utc) - job.created_at).total_seconds(),
    )

    async def _read_stdout() -> None:
        nonlocal terminal_seen, first_event_seen
        assert process.stdout is not None
        while True:
            raw = await process.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                _enqueue_event(
                    job,
                    _build_event(
                        job.job_id,
                        "log",
                        message=f"Runner output (non-JSON): {line}",
                        important=True,
                    ),
                )
                continue
            if not isinstance(event, dict):
                _enqueue_event(
                    job,
                    _build_event(
                        job.job_id,
                        "log",
                        message=f"Runner output (invalid): {line}",
                        important=True,
                    ),
                )
                continue
            event_type = str(event.pop("type", "message"))
            _maybe_update_project_from_runner_event(request, event_type, event)
            if not first_event_seen:
                first_event_seen = True
                logger.info(
                    "Job %s first runner event after %.2fs",
                    job.job_id,
                    (datetime.now(timezone.utc) - job.created_at).total_seconds(),
                )
            _enqueue_event(job, _build_event(job.job_id, event_type, **event))
            if event_type in TERMINAL_STATUSES:
                terminal_seen = True
                job.status = event_type
                job.finished_at = datetime.now(timezone.utc)

    async def _read_stderr() -> None:
        assert process.stderr is not None
        while True:
            raw = await process.stderr.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                _enqueue_event(
                    job,
                    _build_event(
                        job.job_id,
                        "log",
                        message=f"Runner stderr: {line}",
                        important=True,
                    ),
                )

    async def _watch_cancel() -> None:
        await job.cancel_event.wait()
        if process.stdin is not None:
            try:
                process.stdin.write(b"cancel\n")
                await process.stdin.drain()
            except Exception:  # noqa: BLE001
                pass
        try:
            await asyncio.wait_for(process.wait(), timeout=RUNNER_CANCEL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await asyncio.to_thread(_kill_process_tree, process.pid)

    stdout_task = asyncio.create_task(_read_stdout())
    stderr_task = asyncio.create_task(_read_stderr())
    cancel_task = asyncio.create_task(_watch_cancel())

    return_code = await process.wait()
    await stdout_task
    await stderr_task
    cancel_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await cancel_task

    if not terminal_seen:
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        _enqueue_event(
            job,
            _build_event(
                job.job_id,
                "error",
                status=job.status,
                message="Runner exited without terminal event.",
                exit_code=return_code,
            ),
        )


def _job_or_404(job_id: str) -> JobState:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job


def _jobs_for_project(project_id: str) -> list[JobState]:
    return [
        job
        for job in JOBS.values()
        if job.project_id == project_id and job.status not in TERMINAL_STATUSES
    ]


def _count_running_by_kind(kind: str) -> int:
    return sum(
        1
        for job in JOBS.values()
        if job.kind == kind and job.status == "running"
    )


def _active_job_for_project(project_id: str) -> Optional[JobState]:
    active_jobs = [
        job
        for job in JOBS.values()
        if job.project_id == project_id
        and job.kind in ACTIVE_TASK_JOB_KINDS
        and job.status in ("running", "queued")
    ]
    if not active_jobs:
        return None
    # Prefer running over queued; then most recent by started_at/created_at
    active_jobs.sort(
        key=lambda job: (
            0 if job.status == "running" else 1,
            job.started_at or job.created_at,
            job.created_at,
        ),
        reverse=True,
    )
    return active_jobs[0]


def _serialize_active_task(job: JobState) -> dict[str, Any]:
    checklist: list[dict[str, Any]] = []
    for step_id in job.snapshot_checklist_order:
        row = job.snapshot_checklist.get(step_id, {})
        checklist.append(
            {
                "id": step_id,
                "label": (
                    str(row.get("label")).strip()
                    if isinstance(row.get("label"), str)
                    else _checklist_label(step_id)
                ),
                "state": (
                    str(row.get("state")).strip()
                    if isinstance(row.get("state"), str) and str(row.get("state")).strip()
                    else "pending"
                ),
                "detail": (
                    str(row.get("detail")).strip()
                    if isinstance(row.get("detail"), str) and str(row.get("detail")).strip()
                    else None
                ),
            }
        )
    return {
        "job_id": job.job_id,
        "kind": job.kind,
        "status": job.status,
        "heading": job.snapshot_heading,
        "message": job.snapshot_message,
        "pct": job.snapshot_pct,
        "step_id": job.snapshot_step_id,
        "started_at": _job_timestamp(job.started_at),
        "updated_at": job.snapshot_updated_at or _now_ts(),
        "checklist": checklist,
    }


def _attach_project_runtime_fields(
    payload: dict[str, Any],
    project_id: str,
) -> dict[str, Any]:
    response = dict(payload)
    active_job = _active_job_for_project(project_id)
    if active_job is not None:
        response["active_task"] = _serialize_active_task(active_job)
    notice = _get_project_task_notice(project_id)
    if notice is not None:
        response["task_notice"] = notice
    return response


async def _cancel_jobs_for_project(project_id: str) -> list[str]:
    target_jobs = _jobs_for_project(project_id)
    if not target_jobs:
        return []

    for job in target_jobs:
        job.cancel_event.set()
        if job.process and job.process.stdin:
            try:
                job.process.stdin.write(b"cancel\n")
                await job.process.stdin.drain()
            except Exception:  # noqa: BLE001
                pass

    loop = asyncio.get_running_loop()
    deadline = loop.time() + PROJECT_DELETE_CANCEL_TIMEOUT_SECONDS
    while loop.time() < deadline:
        remaining = [job for job in target_jobs if job.status not in TERMINAL_STATUSES]
        if not remaining:
            break
        await asyncio.sleep(0.1)

    remaining = [job for job in target_jobs if job.status not in TERMINAL_STATUSES]
    for job in remaining:
        if job.process and job.process.returncode is None:
            await asyncio.to_thread(_kill_process_tree, job.process.pid)

    return [job.job_id for job in target_jobs]


@app.post("/jobs", status_code=201)
async def create_job(payload: JobRequest) -> dict[str, str]:
    request_received_at = datetime.now(timezone.utc)
    if payload.project_id:
        project_store.get_project(payload.project_id)
    if payload.kind == "create_subtitles" and payload.project_id:
        _resolve_create_subtitles_request_from_project(payload)
    if payload.kind == "create_video_with_subtitles" and payload.project_id:
        _resolve_export_request_from_project(payload)
    if payload.kind in {"pipeline", "create_subtitles", "create_video_with_subtitles", "calibrate"}:
        if not payload.input_path:
            raise HTTPException(status_code=422, detail="input_path_required")
        if payload.kind != "calibrate" and not payload.output_dir:
            raise HTTPException(status_code=422, detail="output_dir_required")
    if payload.kind == "create_video_with_subtitles" and not payload.srt_path:
        raise HTTPException(status_code=422, detail="srt_path_required")

    job_id = str(uuid.uuid4())
    trace_path: Optional[Path] = None
    try:
        trace_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        trace_path = get_logs_dir() / f"job_trace_{job_id}_{trace_timestamp}.jsonl"
    except Exception:  # noqa: BLE001
        trace_path = None
    job = JobState(
        job_id=job_id,
        status="queued",
        created_at=datetime.now(timezone.utc),
        kind=payload.kind,
        project_id=payload.project_id,
        trace_path=trace_path,
    )
    logger.info("Job %s request received (kind=%s)", job_id, payload.kind)
    JOBS[job_id] = job

    if payload.kind == "calibrate":
        output_dir = tempfile.mkdtemp(prefix="cue_calibrate_")
        calibrate_options = dict(payload.options or {})
        calibrate_options["quality"] = "speed"
        calibrate_options["transcription_quality"] = "speed"
        calibrate_request = JobRequest(
            kind="calibrate",
            input_path=payload.input_path,
            output_dir=output_dir,
            options=calibrate_options,
        )
        slot_free = _count_running_by_kind("calibrate") == 0
        if slot_free:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            _enqueue_event(
                job,
                _build_event(
                    job_id,
                    "started",
                    heading="Calibrating",
                    message="Extracting audio",
                ),
            )
            _enqueue_event(
                job,
                _build_event(
                    job_id,
                    "checklist",
                    step_id="extract_audio",
                    state="start",
                ),
            )
            _enqueue_event(
                job,
                _build_event(
                    job_id,
                    "progress",
                    step_id="PREPARE_AUDIO",
                    step_progress=0.0,
                    pct=0,
                    message="Extracting audio",
                ),
            )
        _create_subtitles_queue.put_nowait((job, calibrate_request))
        events_url = f"http://{HOST}:{PORT}/jobs/{job_id}/events"
        return {"job_id": job_id, "events_url": events_url, "status": job.status}
    if payload.kind == "create_subtitles":
        create_heading = (
            "Syncing karaoke timing"
            if _reuses_existing_subtitles(payload)
            else "Creating subtitles"
        )
        slot_free = _count_running_by_kind("create_subtitles") == 0
        if slot_free:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            _enqueue_event(
                job,
                _build_event(
                    job_id,
                    "started",
                    heading=create_heading,
                    message="Preparing audio",
                ),
            )
            _enqueue_event(
                job,
                _build_event(
                    job_id,
                    "checklist",
                    step_id="extract_audio",
                    state="start",
                ),
            )
            _enqueue_event(
                job,
                _build_event(
                    job_id,
                    "progress",
                    step_id="PREPARE_AUDIO",
                    step_progress=0.0,
                    pct=0,
                    message="Extracting audio",
                ),
            )
        _create_subtitles_queue.put_nowait((job, payload))
        events_url = f"http://{HOST}:{PORT}/jobs/{job_id}/events"
        return {"job_id": job_id, "events_url": events_url, "status": job.status}
    if payload.kind == "create_video_with_subtitles":
        slot_free = _count_running_by_kind("create_video_with_subtitles") < EXPORT_CONCURRENCY
        if slot_free:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            _enqueue_event(
                job,
                _build_event(
                    job_id,
                    "started",
                    heading="Creating video with subtitles",
                ),
            )
        _export_queue.put_nowait((job, payload))
        events_url = f"http://{HOST}:{PORT}/jobs/{job_id}/events"
        return {"job_id": job_id, "events_url": events_url, "status": job.status}

    if payload.kind == "demo":
        job.task = asyncio.create_task(_run_demo_job(job))
    elif payload.kind == "pipeline":
        job.task = asyncio.create_task(_run_pipeline_job(job, payload))
    else:
        job.task = asyncio.create_task(_run_runner_job(job, payload))
    events_url = f"http://{HOST}:{PORT}/jobs/{job_id}/events"
    return {"job_id": job_id, "events_url": events_url, "status": job.status}


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    job = _job_or_404(job_id)
    if job.sse_client_connected:
        now = time.monotonic()
        last_warn = SSE_CONFLICT_WARN_AT.get(job_id, 0.0)
        if now - last_warn >= SSE_CONFLICT_WARN_INTERVAL_SECONDS:
            SSE_CONFLICT_WARN_AT[job_id] = now
            logger.warning(
                "SSE attach conflict for job %s (status=%s queue_size=%s)",
                job_id,
                job.status,
                job.event_queue.qsize(),
            )
        return JSONResponse(
            status_code=409,
            content={"error": "sse_client_already_connected", "job_id": job_id},
        )
    job.sse_client_connected = True

    async def event_generator() -> Any:
        terminal_seen = False
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        job.event_queue.get(),
                        timeout=PING_INTERVAL_SECONDS,
                    )
                    yield f"event: message\ndata: {json.dumps(event)}\n\n"
                    if event.get("type") in TERMINAL_STATUSES:
                        terminal_seen = True
                except asyncio.TimeoutError:
                    if terminal_seen and job.event_queue.empty():
                        break
                    yield ": ping\n\n"
        finally:
            job.sse_client_connected = False

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    job = _job_or_404(job_id)
    job.cancel_event.set()
    if job.process and job.process.stdin:
        try:
            job.process.stdin.write(b"cancel\n")
            await job.process.stdin.drain()
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "job_id": job_id, "status": "cancel_requested"}


@app.get("/projects")
def list_projects() -> list[dict[str, Any]]:
    active_project_ids = {
        job.project_id
        for job in JOBS.values()
        if getattr(job, "project_id", None) and job.status in ("running", "queued")
    }
    active_ids = active_project_ids or None
    summaries = project_store.list_projects(active_ids)
    response: list[dict[str, Any]] = []
    for summary in summaries:
        payload = summary.model_dump()
        project_id = payload.get("project_id")
        if isinstance(project_id, str) and project_id:
            payload = _attach_project_runtime_fields(payload, project_id)
        response.append(payload)
    return response


@app.post("/projects")
def create_project(payload: ProjectCreateRequest) -> dict[str, Any]:
    return project_store.create_project(**payload.to_project_store_kwargs())


@app.post("/projects/import")
async def create_project_from_browser_upload(request: Request) -> dict[str, Any]:
    video_path = await _save_browser_upload(request)
    return project_store.create_project(video_path)


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    payload = project_store.get_project(project_id)
    return _attach_project_runtime_fields(payload, project_id)


@app.get("/projects/{project_id}/subtitles")
def get_project_subtitles(project_id: str) -> dict[str, str]:
    subtitles_srt_text = project_store.get_project_subtitles_text(project_id)
    return {"subtitles_srt_text": subtitles_srt_text}


@app.get("/projects/{project_id}/word-timings")
def get_project_word_timings(project_id: str) -> dict[str, Any]:
    from .srt_utils import is_word_timing_stale
    from .word_timing_schema import WordTimingValidationError, load_word_timings_json

    artifacts = project_store.get_project_word_timing_artifacts(project_id)
    subtitles_path_text = artifacts.get("subtitles_path")
    word_timings_path_text = artifacts.get("word_timings_path")
    if not isinstance(subtitles_path_text, str) or not subtitles_path_text:
        return {
            "available": False,
            "stale": None,
            "reason": "subtitles_not_found",
            "document": None,
        }
    if not isinstance(word_timings_path_text, str) or not word_timings_path_text:
        return {
            "available": False,
            "stale": None,
            "reason": "word_timings_not_found",
            "document": None,
        }

    subtitles_path = Path(subtitles_path_text)
    word_timings_path = Path(word_timings_path_text)
    try:
        doc = load_word_timings_json(word_timings_path)
    except (WordTimingValidationError, OSError) as exc:
        return {
            "available": False,
            "stale": None,
            "reason": "word_timings_invalid",
            "document": None,
            "error": str(exc),
        }

    stale = is_word_timing_stale(word_timings_path, subtitles_path)
    total_words = sum(len(cue.words) for cue in doc.cues)
    document_payload = {
        "schema_version": doc.schema_version,
        "created_utc": doc.created_utc,
        "language": doc.language,
        "srt_sha256": doc.srt_sha256,
        "cues": [
            {
                "cue_index": cue.cue_index,
                "cue_start": cue.cue_start,
                "cue_end": cue.cue_end,
                "cue_text": cue.cue_text,
                "words": [
                    {
                        "text": word.text,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence,
                    }
                    for word in cue.words
                ],
            }
            for cue in doc.cues
        ],
    }
    if total_words <= 0:
        return {
            "available": False,
            "stale": stale,
            "reason": "word_timings_empty",
            "document": document_payload,
        }
    return {
        "available": True,
        "stale": stale,
        "reason": None,
        "document": document_payload,
    }


@app.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdateRequest) -> dict[str, Any]:
    return project_store.update_project(project_id, **payload.to_project_store_kwargs())


@app.post("/projects/{project_id}/relink")
def relink_project(project_id: str, payload: ProjectRelinkRequest) -> dict[str, Any]:
    return project_store.relink_project(project_id, payload.video_path)


@app.post("/projects/{project_id}/relink-import")
async def relink_project_from_browser_upload(
    project_id: str, request: Request
) -> dict[str, Any]:
    video_path = await _save_browser_upload(request)
    return project_store.relink_project(project_id, video_path)


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, Any]:
    cancelled_job_ids = await _cancel_jobs_for_project(project_id)
    PROJECT_TASK_NOTICES.pop(project_id, None)
    project_store.delete_project(project_id)
    return {
        "ok": True,
        "project_id": project_id,
        "cancelled_job_ids": cancelled_job_ids,
    }


@app.get("/settings")
def get_settings() -> dict[str, Any]:
    return _read_settings_file()


@app.get("/local-file")
def get_local_file(path: str) -> FileResponse:
    local_path = _resolve_local_file(path)
    media_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    return FileResponse(local_path, media_type=media_type, filename=local_path.name)


@app.get("/subtitle-fonts")
def get_subtitle_fonts() -> dict[str, Any]:
    from .graphics_preview_renderer import _ensure_application_fonts_loaded
    from .subtitle_fonts import list_available_subtitle_fonts

    _ensure_application_fonts_loaded()
    try:
        from PySide6 import QtGui as _QtGui
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PySide6 not available: {exc}",
        ) from exc
    return {"fonts": list_available_subtitle_fonts(_QtGui.QFontDatabase.families())}


@app.put("/settings")
def update_settings(payload: SettingsUpdateRequest) -> dict[str, Any]:
    current = _read_settings_file()
    merged = _merge_settings(current, payload.settings)
    return _write_settings_file(merged)


@app.post("/diagnostics/archive-on-exit")
def archive_exit_bundle() -> dict[str, Any]:
    archives = _archive_exit_bundles()
    return {"ok": True, "archives": archives}


@app.post("/preview-style")
def preview_style(payload: PreviewStyleRequest) -> dict[str, Any]:
    import hashlib as _hashlib

    from .ffmpeg_utils import extract_raw_frame
    from .graphics_preview_renderer import build_preview_cache_key, render_graphics_preview
    from .paths import get_preview_frames_dir
    from .srt_utils import parse_srt_file, select_cue_for_timestamp, select_preview_moment
    from .subtitle_style import normalize_style_model, preset_defaults, resolve_style_for_frame

    video_path = Path(payload.video_path)
    srt_path = Path(payload.srt_path)

    if not video_path.exists():
        raise HTTPException(status_code=422, detail="video_path not found")
    if not srt_path.exists():
        raise HTTPException(status_code=422, detail="srt_path not found")

    cues = parse_srt_file(srt_path)
    if not cues:
        raise HTTPException(status_code=422, detail="srt_file_empty")

    if payload.timestamp is not None:
        timestamp = payload.timestamp
        cue = select_cue_for_timestamp(cues, timestamp)
        subtitle_text = cue.text if cue else cues[0].text
    else:
        moment = select_preview_moment(cues, None)
        if moment is None:
            raise HTTPException(status_code=422, detail="no_preview_moment")
        timestamp = moment.timestamp_seconds
        subtitle_text = moment.subtitle_text

    fallback = preset_defaults(
        "Default",
        subtitle_mode=payload.subtitle_mode,
        highlight_color=payload.highlight_color,
    )
    style = normalize_style_model(payload.subtitle_style, fallback)

    try:
        srt_mtime = int(srt_path.stat().st_mtime_ns)
    except OSError:
        srt_mtime = 0

    preview_dir = get_preview_frames_dir()
    cache_key = build_preview_cache_key(
        video_path=str(video_path),
        srt_mtime=srt_mtime,
        word_timings_mtime=None,
        timestamp_ms=int(timestamp * 1000),
        preview_width=1280,
        style=style,
        subtitle_mode=payload.subtitle_mode,
        highlight_color=payload.highlight_color,
        highlight_opacity=payload.highlight_opacity,
    )

    output_path = preview_dir / f"{cache_key}.png"
    if output_path.exists():
        return {"preview_path": str(output_path), "cached": True}

    raw_key = _hashlib.sha1(
        f"{video_path}|{int(timestamp * 1000)}|1280".encode()
    ).hexdigest()
    raw_frame_path = preview_dir / f"_raw_{raw_key}.png"

    if not raw_frame_path.exists():
        success = extract_raw_frame(video_path, timestamp, raw_frame_path, width=1280)
        if not success:
            raise HTTPException(status_code=500, detail="frame_extraction_failed")

    try:
        from PySide6 import QtGui as _QtGui
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PySide6 not available: {exc}",
        ) from exc

    frame = _QtGui.QImage(str(raw_frame_path))
    if frame.isNull():
        raise HTTPException(status_code=500, detail="frame_load_failed")

    resolved_style = resolve_style_for_frame(style, frame.height())

    result = render_graphics_preview(
        frame,
        subtitle_text=subtitle_text,
        style=resolved_style,
        subtitle_mode=payload.subtitle_mode,
        highlight_color=payload.highlight_color,
        highlight_opacity=payload.highlight_opacity,
    )

    result.image.save(str(output_path), "PNG")
    return {
        "preview_path": str(output_path),
        "cached": False,
        "requested_font_family": result.requested_font_family,
        "resolved_font_family": result.resolved_font_family,
        "font_fallback_used": result.font_fallback_used,
    }


@app.post("/preview-overlay")
def preview_overlay(payload: PreviewOverlayRequest) -> dict[str, Any]:
    import hashlib as _hashlib

    from .graphics_preview_renderer import (
        _ensure_application_fonts_loaded,
        render_graphics_preview,
        _resolve_qt_font_family,
    )
    from .paths import get_preview_frames_dir
    from .subtitle_style import (
        DEFAULT_FONT_NAME,
        RENDER_MODEL_VERSION,
        normalize_style_model,
        preset_defaults,
        resolve_style_for_frame,
        style_model_to_dict,
    )

    width = int(payload.width)
    height = int(payload.height)
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=422, detail="invalid_overlay_dimensions")
    if width > 7680 or height > 4320:
        raise HTTPException(status_code=422, detail="overlay_dimensions_too_large")

    fallback = preset_defaults(
        "Default",
        subtitle_mode=payload.subtitle_mode,
        highlight_color=payload.highlight_color,
    )
    style = normalize_style_model(payload.subtitle_style, fallback)
    resolved_style = resolve_style_for_frame(style, height)
    resolved_highlight_color = payload.highlight_color
    resolved_highlight_opacity = max(0.0, min(float(payload.highlight_opacity), 1.0))

    _ensure_application_fonts_loaded()
    resolved_font_family, _ = _resolve_qt_font_family(
        style.font_family.strip() if style.font_family else DEFAULT_FONT_NAME
    )

    signature = json.dumps(
        {
            "render_model_version": RENDER_MODEL_VERSION,
            "width": width,
            "height": height,
            "subtitle_text": payload.subtitle_text,
            "highlight_word_index": payload.highlight_word_index,
            "style": style_model_to_dict(resolved_style),
            "resolved_font_family": resolved_font_family,
            "subtitle_mode": payload.subtitle_mode,
            "highlight_color": resolved_highlight_color,
            "highlight_opacity": resolved_highlight_opacity,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    cache_key = _hashlib.sha1(signature.encode("utf-8")).hexdigest()
    output_path = get_preview_frames_dir() / f"_overlay_{cache_key}.png"
    if output_path.exists():
        return {"overlay_path": str(output_path), "cached": True}

    try:
        from PySide6 import QtCore as _QtCore
        from PySide6 import QtGui as _QtGui
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PySide6 not available: {exc}",
        ) from exc

    frame = _QtGui.QImage(width, height, _QtGui.QImage.Format_RGBA8888)
    if frame.isNull():
        raise HTTPException(status_code=500, detail="overlay_frame_init_failed")
    frame.fill(_QtCore.Qt.transparent)

    result = render_graphics_preview(
        frame,
        subtitle_text=payload.subtitle_text,
        style=resolved_style,
        subtitle_mode=payload.subtitle_mode,
        highlight_color=resolved_highlight_color,
        highlight_opacity=resolved_highlight_opacity,
        highlight_word_index=payload.highlight_word_index,
    )
    if not result.image.save(str(output_path), "PNG"):
        raise HTTPException(status_code=500, detail="overlay_save_failed")
    return {
        "overlay_path": str(output_path),
        "cached": False,
        "requested_font_family": result.requested_font_family,
        "resolved_font_family": result.resolved_font_family,
        "font_fallback_used": result.font_fallback_used,
    }


AUDIO_DURATION_5MIN_SEC = 300
CALIBRATION_PREPARING_PREVIEW_SEC = 5
CALIBRATION_FILENAME = "calibration.json"


def _load_calibration_estimates() -> Optional[dict[str, int]]:
    path = get_app_data_dir() / CALIBRATION_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        est = data.get("estimate_5min_sec") if isinstance(data, dict) else None
        if isinstance(est, dict) and all(
            isinstance(v, (int, float)) for v in est.values()
        ):
            return {k: int(v) for k, v in est.items()}
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _save_calibration_estimates(estimate_5min_sec: dict[str, int]) -> None:
    path = get_app_data_dir() / CALIBRATION_FILENAME
    try:
        path.write_text(
            json.dumps({"estimate_5min_sec": estimate_5min_sec}, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Failed to save calibration: %s", exc)


@app.get("/device")
def device_info() -> dict[str, Any]:
    try:
        available = bool(gpu_available())
    except Exception:  # noqa: BLE001
        available = False
    out: dict[str, Any] = {"gpu_available": available}
    try:
        gpu_name = get_gpu_name()
        if gpu_name is not None:
            out["gpu_name"] = gpu_name
    except Exception:  # noqa: BLE001
        pass
    try:
        out["cpu_cores"] = get_cpu_cores()
    except Exception:  # noqa: BLE001
        out["cpu_cores"] = 1
    try:
        out["ultra_available"] = ultra_available()
        out["ultra_device"] = ultra_device()
    except Exception:  # noqa: BLE001
        out["ultra_available"] = False
        out["ultra_device"] = None
    estimate_5min_sec: dict[str, int] = {}
    calibration = _load_calibration_estimates()
    if calibration:
        estimate_5min_sec = dict(calibration)
        out["calibration_done"] = True
        if "quality" in estimate_5min_sec and "ultra" in estimate_5min_sec and estimate_5min_sec["quality"] == estimate_5min_sec["ultra"]:
            estimate_5min_sec["ultra"] = int(round(estimate_5min_sec["quality"] * 1.5))
    else:
        qualities = ("speed", "auto", "quality") + (
            ("ultra",) if ultra_available() else ()
        )
        for q in qualities:
            try:
                device, compute_type = _resolve_device_and_compute(
                    q, gpu_available_fn=gpu_available
                )
                rtf = get_rtf_est_for_device(
                    q,
                    device,
                    compute_type,
                    gpu_name=out.get("gpu_name"),
                    cpu_cores=out.get("cpu_cores"),
                )
                estimate_5min_sec[q] = int(round(AUDIO_DURATION_5MIN_SEC * rtf))
            except Exception:  # noqa: BLE001
                pass
    if estimate_5min_sec:
        out["estimate_5min_sec"] = estimate_5min_sec
    return out


def _load_version_from_tauri_config() -> Optional[str]:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "desktop" / "src-tauri" / "tauri.conf.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    version = data.get("version")
    return version if isinstance(version, str) and version else None


def _get_app_version() -> str:
    version = getattr(sys.modules.get("__main__"), "__version__", None)
    if isinstance(version, str) and version:
        return version

    version = _load_version_from_tauri_config()
    if version:
        return version

    return "0.0.0"  # TODO: wire to backend package version once defined.


def _get_git_commit() -> Optional[str]:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    commit = result.stdout.strip()
    return commit or None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "pid": os.getpid(),
        "version": _get_app_version(),
    }


@app.get("/version")
def version() -> dict[str, Optional[str]]:
    return {
        "version": _get_app_version(),
        "git_commit": _get_git_commit(),
    }


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Cue backend dev server")
    parser.add_argument("--port", type=int, default=None, help="Override backend port")
    args = parser.parse_args()

    global PORT
    PORT = args.port if args.port is not None else _resolve_port()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting backend server on http://%s:%s", HOST, PORT)

    uvicorn.run("app.backend_server:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
