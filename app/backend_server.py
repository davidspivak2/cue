from __future__ import annotations

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
import asyncio
import json
import logging
import os
import subprocess
import signal
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import project_store
from app.config import apply_config_defaults
from app.paths import get_config_path
from app.transcription_device import gpu_available


HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT = DEFAULT_PORT
PING_INTERVAL_SECONDS = 12.0
RUNNER_CANCEL_TIMEOUT_SECONDS = 8.0
PROJECT_DELETE_CANCEL_TIMEOUT_SECONDS = 3.0

logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
    ],
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


JOBS: dict[str, JobState] = {}


class JobRequest(BaseModel):
    kind: Literal[
        "demo",
        "pipeline",
        "create_subtitles",
        "create_video_with_subtitles",
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
    subtitle_mode: str = "word_highlight"
    highlight_color: str = "#FFD400"
    highlight_opacity: float = 1.0


class ProjectCreateRequest(BaseModel):
    video_path: str
    style: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdateRequest(BaseModel):
    subtitles_srt_text: Optional[str] = None
    style: Optional[dict[str, Any]] = None


class ProjectRelinkRequest(BaseModel):
    video_path: str


VALID_SAVE_POLICIES = {"same_folder", "fixed_folder", "ask_every_time"}
VALID_TRANSCRIPTION_QUALITIES = {"auto", "fast", "accurate", "ultra"}
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
    if transcription_quality not in VALID_TRANSCRIPTION_QUALITIES:
        data["transcription_quality"] = "auto"

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


def _build_event(job_id: str, event_type: str, **fields: Any) -> dict[str, Any]:
    payload = {"job_id": job_id, "ts": _now_ts(), "type": event_type}
    payload.update(fields)
    return payload


def _enqueue_event(job: JobState, event: dict[str, Any]) -> None:
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


def _build_runner_command(request: JobRequest) -> list[str]:
    task = "generate_srt" if request.kind == "create_subtitles" else "burn_in"
    command = [
        sys.executable,
        "-m",
        "app.qt_worker_runner",
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
            elif request.kind == "create_video_with_subtitles":
                project_store.record_export_result(
                    project_id,
                    output_path=payload.get("output_path"),
                )
            return
        if event_type in {"cancelled", "error"}:
            project_store.refresh_project_status(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Project update failed for %s: %s", project_id, exc)


async def _run_runner_job(job: JobState, request: JobRequest) -> None:
    job.status = "running"
    if job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    command = _build_runner_command(request)
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


@app.post("/jobs")
async def create_job(payload: JobRequest) -> dict[str, str]:
    request_received_at = datetime.now(timezone.utc)
    if payload.project_id:
        project_store.get_project(payload.project_id)
    if payload.kind == "create_video_with_subtitles" and payload.project_id:
        _resolve_export_request_from_project(payload)
    if payload.kind in {"pipeline", "create_subtitles", "create_video_with_subtitles"}:
        if not payload.input_path:
            raise HTTPException(status_code=422, detail="input_path_required")
        if not payload.output_dir:
            raise HTTPException(status_code=422, detail="output_dir_required")
    if payload.kind == "create_video_with_subtitles" and not payload.srt_path:
        raise HTTPException(status_code=422, detail="srt_path_required")

    job_id = str(uuid.uuid4())
    job = JobState(
        job_id=job_id,
        status="queued",
        created_at=datetime.now(timezone.utc),
        kind=payload.kind,
        project_id=payload.project_id,
    )
    logger.info("Job %s request received (kind=%s)", job_id, payload.kind)
    JOBS[job_id] = job
    if payload.kind in {"create_subtitles", "create_video_with_subtitles"}:
        heading = (
            "Creating video with subtitles"
            if payload.kind == "create_video_with_subtitles"
            else "Creating subtitles"
        )
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        _enqueue_event(job, _build_event(job_id, "started", heading=heading))
        logger.info(
            "Job %s started event queued after %.2fs",
            job_id,
            (job.started_at - request_received_at).total_seconds(),
        )
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
        if getattr(job, "project_id", None) and job.status == "running"
    }
    active_ids = active_project_ids or None
    summaries = project_store.list_projects(active_ids)
    return [summary.model_dump() for summary in summaries]


@app.post("/projects")
def create_project(payload: ProjectCreateRequest) -> dict[str, Any]:
    return project_store.create_project(payload.video_path, style=payload.style)


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    return project_store.get_project(project_id)


@app.get("/projects/{project_id}/subtitles")
def get_project_subtitles(project_id: str) -> dict[str, str]:
    subtitles_srt_text = project_store.get_project_subtitles_text(project_id)
    return {"subtitles_srt_text": subtitles_srt_text}


@app.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdateRequest) -> dict[str, Any]:
    return project_store.update_project(
        project_id,
        subtitles_srt_text=payload.subtitles_srt_text,
        style=payload.style,
    )


@app.post("/projects/{project_id}/relink")
def relink_project(project_id: str, payload: ProjectRelinkRequest) -> dict[str, Any]:
    return project_store.relink_project(project_id, payload.video_path)


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, Any]:
    cancelled_job_ids = await _cancel_jobs_for_project(project_id)
    project_store.delete_project(project_id)
    return {
        "ok": True,
        "project_id": project_id,
        "cancelled_job_ids": cancelled_job_ids,
    }


@app.get("/settings")
def get_settings() -> dict[str, Any]:
    return _read_settings_file()


@app.put("/settings")
def update_settings(payload: SettingsUpdateRequest) -> dict[str, Any]:
    current = _read_settings_file()
    merged = _merge_settings(current, payload.settings)
    return _write_settings_file(merged)


@app.post("/preview-style")
def preview_style(payload: PreviewStyleRequest) -> dict[str, Any]:
    import hashlib as _hashlib

    from .ffmpeg_utils import extract_raw_frame
    from .graphics_preview_renderer import build_preview_cache_key, render_graphics_preview
    from .paths import get_preview_frames_dir
    from .srt_utils import parse_srt_file, select_cue_for_timestamp, select_preview_moment
    from .subtitle_style import normalize_style_model, preset_defaults

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
        return {"preview_path": str(output_path)}

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

    result = render_graphics_preview(
        frame,
        subtitle_text=subtitle_text,
        style=style,
        subtitle_mode=payload.subtitle_mode,
        highlight_color=payload.highlight_color,
        highlight_opacity=payload.highlight_opacity,
    )

    result.image.save(str(output_path), "PNG")
    return {"preview_path": str(output_path)}


@app.get("/device")
def device_info() -> dict[str, Any]:
    try:
        available = bool(gpu_available())
    except Exception:  # noqa: BLE001
        available = False
    return {"gpu_available": available}


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
