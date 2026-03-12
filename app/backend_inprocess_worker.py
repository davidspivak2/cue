"""Run the Worker in-process (same process as the backend) to avoid runner cold start."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("cue")


def warmup_inprocess_runtime() -> dict[str, Any]:
    """Warm imports/Qt runtime used by in-process jobs."""
    started = time.monotonic()
    result: dict[str, Any] = {
        "ok": False,
        "qt_ready": False,
        "worker_ready": False,
        "error": None,
        "elapsed_ms": 0,
    }
    try:
        from PySide6 import QtWidgets

        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv if hasattr(sys, "argv") else [])
        del app
        result["qt_ready"] = True

        # Warm module imports used in run_worker_inprocess without starting a job.
        from app.worker_runner import (  # noqa: F401
            _build_progress_controller,
            _resolve_settings,
            _resolve_subtitle_style,
        )
        from app.workers import TaskType, Worker  # noqa: F401

        result["worker_ready"] = True
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    finally:
        result["elapsed_ms"] = int(round((time.monotonic() - started) * 1000))
    return result


def run_worker_inprocess(
    job_id: str,
    request: Any,
    enqueue_event_cb: Callable[[dict[str, Any]], None],
    cancel_event: Any,
    worker_ref: list[Any],
) -> None:
    """Run Worker in this thread; bridge signals to enqueue_event_cb. Sets worker_ref[0] = worker for cancel."""
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError as e:
        raise RuntimeError(f"PySide6 unavailable: {e}") from e

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv if hasattr(sys, "argv") else [])

    from app.progress import StepEvent
    from app.worker_runner import (
        _build_progress_controller,
        _resolve_settings,
        _resolve_subtitle_style,
    )
    from app.workers import TaskType, Worker

    task_type = (
        TaskType.GENERATE_SRT
        if getattr(request, "kind", None) in ("create_subtitles", "calibrate")
        else TaskType.BURN_IN
    )
    options = getattr(request, "options", None) or {}
    settings = _resolve_settings(options)
    reuse_existing_subtitles = bool(options.get("reuse_existing_subtitles"))

    video_path = Path(getattr(request, "input_path", "") or "")
    output_dir = Path(getattr(request, "output_dir", "") or "")
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path: Optional[Path] = None
    if getattr(request, "srt_path", None):
        srt_path = Path(request.srt_path)
    word_timings_path: Optional[Path] = None
    if getattr(request, "word_timings_path", None):
        word_timings_path = Path(request.word_timings_path)
    style_path: Optional[Path] = None
    if getattr(request, "style_path", None):
        style_path = Path(request.style_path)

    subtitle_style = _resolve_subtitle_style(
        style_path,
        settings.subtitle_mode,
        settings.highlight_color,
        logger,
    )
    resolved_subtitle_mode = subtitle_style.subtitle_mode
    resolved_highlight_color = subtitle_style.highlight_color

    progress_controller = _build_progress_controller(
        task_type=task_type,
        transcription_settings=settings.transcription,
        subtitle_mode=resolved_subtitle_mode,
    )

    log_path: Optional[Path] = None
    try:
        from app.paths import get_logs_dir
        import datetime as _dt
        log_dir = get_logs_dir()
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"cue_inprocess_{ts}.log"
    except Exception:
        pass

    finished_emitted = False

    def enqueue(ev: dict[str, Any]) -> None:
        enqueue_event_cb(ev)

    def _on_log(message: str, important: bool) -> None:
        if important:
            logger.info(message)
        else:
            logger.debug(message)
        enqueue({"type": "log", "message": message, "important": important})

    def _on_started(message: str) -> None:
        heading = (
            "Syncing karaoke timing"
            if task_type == TaskType.GENERATE_SRT and reuse_existing_subtitles
            else "Creating subtitles"
            if task_type == TaskType.GENERATE_SRT
            else "Creating video with subtitles"
        )
        ev: dict[str, Any] = {
            "type": "started",
            "heading": heading,
            "message": message,
            "task": getattr(request, "kind", None),
        }
        if log_path is not None:
            ev["log_path"] = str(log_path)
        enqueue(ev)

    def _on_progress(step_id: str, step_progress: object, label: str) -> None:
        progress_value: Optional[float] = None
        if isinstance(step_progress, (int, float)):
            progress_value = float(step_progress)
        global_progress = progress_controller.update(step_id, progress_value)
        pct = int(round(global_progress * 100))
        enqueue({
            "type": "progress",
            "step_id": step_id,
            "step_progress": progress_value,
            "pct": pct,
            "message": label,
        })

    def _on_step_event(event: StepEvent) -> None:
        enqueue({
            "type": "checklist",
            "step_id": event.step_id,
            "state": event.state,
            "reason_code": event.reason_code,
            "reason_text": event.reason_text,
        })

    def _emit_terminal(event_type: str, message: str) -> None:
        ev: dict[str, Any] = {
            "type": event_type,
            "status": event_type,
            "message": message,
        }
        if log_path is not None:
            ev["log_path"] = str(log_path)
        enqueue(ev)

    def _on_finished(success: bool, message: str, payload: dict) -> None:
        nonlocal finished_emitted
        if finished_emitted:
            return
        finished_emitted = True
        if success:
            result_payload = dict(payload or {})
            if log_path is not None:
                result_payload["log_path"] = str(log_path)
            enqueue({"type": "result", "payload": result_payload})
            _emit_terminal("completed", message)
            return
        if message == "Operation cancelled.":
            _emit_terminal("cancelled", message)
            return
        _emit_terminal("error", message or "Worker failed.")

    worker = Worker(
        task_type=task_type,
        video_path=video_path,
        output_dir=output_dir,
        srt_path=srt_path,
        word_timings_path=word_timings_path,
        transcription_settings=settings.transcription,
        subtitle_style=subtitle_style,
        subtitle_mode=resolved_subtitle_mode,
        highlight_color=resolved_highlight_color,
        highlight_opacity=None,
        diagnostics_settings=None,
        session_log_path=log_path,
        reuse_existing_subtitles=reuse_existing_subtitles,
    )
    direct = QtCore.Qt.ConnectionType.DirectConnection
    worker.signals.log.connect(_on_log, direct)
    worker.signals.started.connect(_on_started, direct)
    worker.signals.progress.connect(_on_progress, direct)
    worker.signals.step_event.connect(_on_step_event, direct)
    worker.signals.finished.connect(_on_finished, direct)

    try:
        worker_ref.clear()
        worker_ref.append(worker)
        worker.run()
    finally:
        worker_ref.clear()
