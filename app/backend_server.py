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
import asyncio
import json
import logging
import os
import subprocess
import sys
import uuid
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .ui.utils import get_media_duration_seconds, generate_thumbnail

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT = DEFAULT_PORT
PING_INTERVAL_SECONDS = 12.0

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


@dataclass
class JobState:
    job_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    kind: str = "demo"
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    event_queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    sse_client_connected: bool = False
    task: Optional[asyncio.Task[None]] = None


JOBS: dict[str, JobState] = {}


class JobRequest(BaseModel):
    kind: Literal["demo", "pipeline"] = "pipeline"
    input_path: Optional[str] = None
    output_dir: Optional[str] = None
    options: dict[str, Any] = Field(default_factory=dict)


class VideoInfoRequest(BaseModel):
    path: str
    output_dir: str


class FilePathRequest(BaseModel):
    path: str


class FileWriteRequest(BaseModel):
    path: str
    content: str


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


def _job_or_404(job_id: str) -> JobState:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job


@app.post("/video/info")
async def video_info(payload: VideoInfoRequest) -> dict[str, Any]:
    video_path = Path(payload.path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="video_not_found")
    output_dir = Path(payload.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    duration_seconds = get_media_duration_seconds(video_path)
    if duration_seconds is None:
        raise HTTPException(status_code=500, detail="duration_unavailable")
    thumbnail_path = generate_thumbnail(video_path, duration_seconds, logger)
    if thumbnail_path is None:
        raise HTTPException(status_code=500, detail="thumbnail_unavailable")
    target_thumbnail = output_dir / "thumb.png"
    try:
        shutil.copy2(thumbnail_path, target_thumbnail)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"thumbnail_copy_failed: {exc}") from exc
    return {
        "duration_seconds": duration_seconds,
        "thumbnail_path": str(target_thumbnail),
        "filename": video_path.name,
    }


@app.post("/fs/exists")
async def fs_exists(payload: FilePathRequest) -> dict[str, Any]:
    path = Path(payload.path)
    return {"exists": path.exists()}


@app.post("/fs/read_text")
async def fs_read_text(payload: FilePathRequest) -> dict[str, Any]:
    path = Path(payload.path)
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="file_not_found") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"read_failed: {exc}") from exc
    return {"content": content}


@app.post("/fs/write_text")
async def fs_write_text(payload: FileWriteRequest) -> dict[str, Any]:
    path = Path(payload.path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload.content, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"write_failed: {exc}") from exc
    return {"ok": True}


@app.post("/jobs")
async def create_job(payload: JobRequest) -> dict[str, str]:
    if payload.kind == "pipeline":
        if not payload.input_path:
            raise HTTPException(status_code=422, detail="input_path_required")
        if not payload.output_dir:
            raise HTTPException(status_code=422, detail="output_dir_required")

    job_id = str(uuid.uuid4())
    job = JobState(
        job_id=job_id,
        status="queued",
        created_at=datetime.now(timezone.utc),
        kind=payload.kind,
    )
    JOBS[job_id] = job
    if payload.kind == "demo":
        job.task = asyncio.create_task(_run_demo_job(job))
    else:
        job.task = asyncio.create_task(_run_pipeline_job(job, payload))
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
    return {"ok": True, "job_id": job_id, "status": "cancel_requested"}


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
