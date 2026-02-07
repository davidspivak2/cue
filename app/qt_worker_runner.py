from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


HEARTBEAT_SECONDS = 10.0


class EventEmitter:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def emit(self, event_type: str, **fields: Any) -> None:
        payload = {"type": event_type}
        payload.update(fields)
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            data = (line + "\n").encode("utf-8", errors="backslashreplace")
            if hasattr(sys.stdout, "buffer"):
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            else:
                sys.stdout.write(data.decode("utf-8", errors="backslashreplace"))
                sys.stdout.flush()


@dataclass(frozen=True)
class RunnerSettings:
    transcription: object
    subtitle_mode: str
    highlight_color: str


def _configure_logging() -> tuple[logging.Logger, Path, logging.FileHandler]:
    from app.paths import get_logs_dir

    log_dir = get_logs_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"cue_{timestamp}.log"

    logger = logging.getLogger("cue")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger, log_path, handler


def _parse_options(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _build_progress_controller(
    *,
    task_type: str,
    transcription_settings: object | None,
    subtitle_mode: str,
) -> "ProgressController":
    from app.progress import ProgressController, ProgressStep
    from app.workers import TaskType, TranscriptionSettings

    if task_type == TaskType.GENERATE_SRT:
        steps = [ProgressStep.PREPARE_AUDIO, ProgressStep.TRANSCRIBE]
        if isinstance(transcription_settings, TranscriptionSettings):
            if transcription_settings.punctuation_rescue_fallback_enabled:
                steps.append(ProgressStep.FIX_PUNCTUATION)
            if transcription_settings.vad_gap_rescue_enabled:
                steps.append(ProgressStep.FIX_GAPS)
        if subtitle_mode == "word_highlight":
            steps.append(ProgressStep.ALIGN_WORDS)
        steps.append(ProgressStep.PREPARING_PREVIEW)
    else:
        steps = [ProgressStep.EXPORT]
    return ProgressController(steps)


def _resolve_settings(options: dict[str, Any]) -> RunnerSettings:
    from app.subtitle_style import DEFAULT_HIGHLIGHT_COLOR, DEFAULT_SUBTITLE_MODE, VALID_SUBTITLE_MODES
    from app.transcription_device import gpu_available
    from app.workers import TranscriptionSettings
    from app.backend_pipeline_adapter import _resolve_pipeline_settings

    settings = _resolve_pipeline_settings(
        options,
        gpu_available_fn=gpu_available,
        valid_subtitle_modes=set(VALID_SUBTITLE_MODES),
        default_subtitle_mode=DEFAULT_SUBTITLE_MODE,
        default_highlight_color=DEFAULT_HIGHLIGHT_COLOR,
        transcription_settings_cls=TranscriptionSettings,
    )
    return RunnerSettings(
        transcription=settings.transcription,
        subtitle_mode=settings.subtitle_mode,
        highlight_color=settings.highlight_color,
    )


def _emit_heartbeat(emitter: EventEmitter, stop_event: threading.Event) -> None:
    while not stop_event.wait(HEARTBEAT_SECONDS):
        emitter.emit("heartbeat")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cue Qt worker runner")
    parser.add_argument("--task", required=True, choices=["generate_srt", "burn_in"])
    parser.add_argument("--video-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--srt-path")
    parser.add_argument("--options-json")
    args = parser.parse_args()

    emitter = EventEmitter()
    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_emit_heartbeat, args=(emitter, stop_heartbeat), daemon=True
    )
    heartbeat_thread.start()

    try:
        from PySide6 import QtWidgets
    except Exception as exc:  # noqa: BLE001
        emitter.emit("error", status="error", message=f"PySide6 unavailable: {exc}")
        stop_heartbeat.set()
        return 1

    app = QtWidgets.QApplication(sys.argv)
    _ = app

    logger, log_path, handler = _configure_logging()
    logger.info("Log file: %s", log_path)

    options = _parse_options(args.options_json)
    settings = _resolve_settings(options)

    video_path = Path(args.video_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        emitter.emit(
            "error",
            status="error",
            message=f"Input path does not exist: {video_path}",
            log_path=str(log_path),
        )
        stop_heartbeat.set()
        return 1

    srt_path = Path(args.srt_path) if args.srt_path else None
    if args.task == "burn_in" and (srt_path is None or not srt_path.exists()):
        emitter.emit(
            "error",
            status="error",
            message="Missing or invalid srt_path for burn_in task.",
            log_path=str(log_path),
        )
        stop_heartbeat.set()
        return 1

    from app.progress import StepEvent
    from app.subtitle_style import PRESET_DEFAULT, preset_style_defaults, style_model_from_preset
    from app.workers import TaskType, Worker

    subtitle_style = style_model_from_preset(
        preset_style_defaults(PRESET_DEFAULT),
        subtitle_mode=settings.subtitle_mode,
        highlight_color=settings.highlight_color,
    )

    progress_controller = _build_progress_controller(
        task_type=args.task,
        transcription_settings=settings.transcription,
        subtitle_mode=settings.subtitle_mode,
    )

    cancel_requested = threading.Event()
    finished_emitted = threading.Event()

    def _on_log(message: str, important: bool) -> None:
        if important:
            logger.info(message)
        else:
            logger.debug(message)
        emitter.emit("log", message=message, important=important)

    def _on_started(message: str) -> None:
        heading = (
            "Creating subtitles"
            if args.task == TaskType.GENERATE_SRT
            else "Creating video with subtitles"
        )
        emitter.emit(
            "started",
            heading=heading,
            message=message,
            log_path=str(log_path),
            task=args.task,
        )

    def _on_progress(step_id: str, step_progress: object, label: str) -> None:
        progress_value: Optional[float] = None
        if isinstance(step_progress, (int, float)):
            progress_value = float(step_progress)
        global_progress = progress_controller.update(step_id, progress_value)
        pct = int(round(global_progress * 100))
        emitter.emit(
            "progress",
            step_id=step_id,
            step_progress=progress_value,
            pct=pct,
            message=label,
        )

    def _on_step_event(event: StepEvent) -> None:
        emitter.emit(
            "checklist",
            step_id=event.step_id,
            state=event.state,
            reason_code=event.reason_code,
            reason_text=event.reason_text,
        )

    def _emit_terminal(event_type: str, message: str) -> None:
        emitter.emit(
            event_type,
            status=event_type,
            message=message,
            log_path=str(log_path),
        )

    def _on_finished(success: bool, message: str, payload: dict) -> None:
        if finished_emitted.is_set():
            return
        finished_emitted.set()
        if success:
            result_payload = dict(payload or {})
            result_payload["log_path"] = str(log_path)
            emitter.emit("result", payload=result_payload)
            _emit_terminal("completed", message)
            return
        if cancel_requested.is_set() or message == "Operation cancelled.":
            _emit_terminal("cancelled", message)
            return
        _emit_terminal("error", message or "Worker failed.")

    worker = Worker(
        task_type=args.task,
        video_path=video_path,
        output_dir=output_dir,
        srt_path=srt_path,
        transcription_settings=settings.transcription,
        subtitle_style=subtitle_style,
        subtitle_mode=settings.subtitle_mode,
        highlight_color=settings.highlight_color,
        highlight_opacity=None,
        diagnostics_settings=None,
        session_log_path=log_path,
    )
    worker.signals.log.connect(_on_log)
    worker.signals.started.connect(_on_started)
    worker.signals.progress.connect(_on_progress)
    worker.signals.step_event.connect(_on_step_event)
    worker.signals.finished.connect(_on_finished)

    def _watch_cancel() -> None:
        for line in sys.stdin:
            if line.strip().lower() == "cancel":
                cancel_requested.set()
                worker.cancel()
                break

    threading.Thread(target=_watch_cancel, daemon=True).start()

    try:
        worker.run()
    except Exception as exc:  # noqa: BLE001
        _emit_terminal("error", str(exc))
    finally:
        stop_heartbeat.set()
        handler.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
