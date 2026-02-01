from __future__ import annotations

import asyncio
import contextlib
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable


class PipelineCancelledError(Exception):
    pass


class PipelineDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class PipelineSettings:
    transcription: object
    subtitle_mode: str
    highlight_color: str


def _resolve_device_and_compute(
    quality: str,
    *,
    gpu_available_fn: Callable[[], bool],
) -> tuple[str, str]:
    if quality == "fast":
        return "cpu", "int8"
    if quality == "accurate":
        return "cpu", "int16"
    if quality == "ultra":
        return "cpu", "float32"
    if gpu_available_fn():
        return "cuda", "float16"
    return "cpu", "int16"


def _resolve_pipeline_settings(
    options: dict,
    *,
    gpu_available_fn: Callable[[], bool],
    valid_subtitle_modes: set[str],
    default_subtitle_mode: str,
    default_highlight_color: str,
    transcription_settings_cls: type,
) -> PipelineSettings:
    quality = str(options.get("quality", "auto")).strip().lower() or "auto"
    device_override = options.get("device")
    compute_override = options.get("compute_type")
    device, compute_type = _resolve_device_and_compute(quality, gpu_available_fn=gpu_available_fn)
    if isinstance(device_override, str) and device_override:
        device = device_override
        if isinstance(compute_override, str) and compute_override:
            compute_type = compute_override
        elif device == "cuda":
            compute_type = "float16"
        else:
            compute_type = "int16"
    elif isinstance(compute_override, str) and compute_override:
        compute_type = compute_override

    subtitle_mode = options.get("subtitle_mode")
    if not isinstance(subtitle_mode, str) or subtitle_mode not in valid_subtitle_modes:
        subtitle_mode = default_subtitle_mode

    highlight_color = options.get("highlight_color")
    if not isinstance(highlight_color, str) or not highlight_color.strip():
        highlight_color = default_highlight_color

    transcription = transcription_settings_cls(
        apply_audio_filter=bool(options.get("apply_audio_filter", True)),
        keep_extracted_audio=bool(options.get("keep_extracted_audio", False)),
        device=device,
        compute_type=compute_type,
        quality=quality,
        punctuation_rescue_fallback_enabled=bool(
            options.get("punctuation_rescue_fallback_enabled", True)
        ),
        vad_gap_rescue_enabled=bool(options.get("vad_gap_rescue_enabled", True)),
    )
    return PipelineSettings(
        transcription=transcription,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
    )


def _run_worker_task(
    *,
    task_type: str,
    video_path: Path,
    output_dir: Path,
    srt_path: Path | None,
    settings: PipelineSettings,
    cancel_flag: threading.Event,
    worker_cls: type,
    preset_style_defaults_fn: Callable[[str], object],
    style_model_from_preset_fn: Callable[..., object],
    preset_default: str,
) -> tuple[bool, str, dict]:
    result: dict[str, object] = {"success": False, "message": "", "payload": {}}

    def _on_finished(success: bool, message: str, payload: dict) -> None:
        result["success"] = success
        result["message"] = message
        result["payload"] = payload

    subtitle_style = style_model_from_preset_fn(
        preset_style_defaults_fn(preset_default),
        subtitle_mode=settings.subtitle_mode,
        highlight_color=settings.highlight_color,
    )
    worker = worker_cls(
        task_type=task_type,
        video_path=video_path,
        output_dir=output_dir,
        srt_path=srt_path,
        transcription_settings=settings.transcription,
        subtitle_style=subtitle_style,
        subtitle_mode=settings.subtitle_mode,
        highlight_color=settings.highlight_color,
        highlight_opacity=None,
        diagnostics_settings=None,
        session_log_path=None,
    )
    worker.signals.finished.connect(_on_finished)

    def _watch_cancel() -> None:
        cancel_flag.wait()
        worker.cancel()

    threading.Thread(target=_watch_cancel, daemon=True).start()
    worker.run()
    return (
        bool(result["success"]),
        str(result["message"]),
        dict(result["payload"]),
    )


async def run_pipeline_job(
    *,
    input_path: str,
    output_dir: str,
    options: dict,
    cancel_event: asyncio.Event,
    emit_event: Callable[[dict], Awaitable[None]],
) -> None:
    video_path = Path(input_path)
    if not video_path.exists():
        raise ValueError(f"Input path does not exist: {input_path}")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        from .subtitle_style import (
            DEFAULT_HIGHLIGHT_COLOR,
            DEFAULT_SUBTITLE_MODE,
            PRESET_DEFAULT,
            VALID_SUBTITLE_MODES,
            preset_style_defaults,
            style_model_from_preset,
        )
        from .transcription_device import gpu_available
        from .workers import TaskType, TranscriptionSettings, Worker
    except ImportError as exc:
        message = (
            "Pipeline dependencies are missing (PySide6). "
            "Install with `pip install PySide6` to run pipeline jobs."
        )
        raise PipelineDependencyError(message) from exc

    settings = _resolve_pipeline_settings(
        options,
        gpu_available_fn=gpu_available,
        valid_subtitle_modes=set(VALID_SUBTITLE_MODES),
        default_subtitle_mode=DEFAULT_SUBTITLE_MODE,
        default_highlight_color=DEFAULT_HIGHLIGHT_COLOR,
        transcription_settings_cls=TranscriptionSettings,
    )

    await emit_event({"type": "step", "step": "validate", "message": "Validated inputs."})
    await emit_event({"type": "progress", "pct": 0})
    if cancel_event.is_set():
        raise PipelineCancelledError()

    await emit_event({"type": "step", "step": "transcribe", "message": "Starting transcription."})
    await emit_event({"type": "progress", "pct": 25})

    async def _watch_cancel(flag: threading.Event) -> None:
        await cancel_event.wait()
        flag.set()

    cancel_flag = threading.Event()
    cancel_task = asyncio.create_task(_watch_cancel(cancel_flag))
    try:
        success, message, payload = await asyncio.to_thread(
            _run_worker_task,
            task_type=TaskType.GENERATE_SRT,
            video_path=video_path,
            output_dir=output_path,
            srt_path=None,
            settings=settings,
            cancel_flag=cancel_flag,
            worker_cls=Worker,
            preset_style_defaults_fn=preset_style_defaults,
            style_model_from_preset_fn=style_model_from_preset,
            preset_default=PRESET_DEFAULT,
        )
    finally:
        cancel_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cancel_task

    if cancel_event.is_set() or (not success and message == "Operation cancelled."):
        raise PipelineCancelledError()
    if not success:
        raise RuntimeError(message or "Pipeline transcription failed.")

    srt_path_value = payload.get("srt_path")
    srt_path = Path(srt_path_value) if srt_path_value else None
    if srt_path is None or not srt_path.exists():
        raise RuntimeError("Pipeline output missing subtitles file.")

    await emit_event({"type": "step", "step": "align", "message": "Syncing word timings."})
    await emit_event({"type": "progress", "pct": 60})
    if cancel_event.is_set():
        raise PipelineCancelledError()

    await emit_event({"type": "step", "step": "export", "message": "Exporting video."})
    await emit_event({"type": "progress", "pct": 90})

    cancel_flag = threading.Event()
    cancel_task = asyncio.create_task(_watch_cancel(cancel_flag))
    try:
        success, message, _ = await asyncio.to_thread(
            _run_worker_task,
            task_type=TaskType.BURN_IN,
            video_path=video_path,
            output_dir=output_path,
            srt_path=srt_path,
            settings=settings,
            cancel_flag=cancel_flag,
            worker_cls=Worker,
            preset_style_defaults_fn=preset_style_defaults,
            style_model_from_preset_fn=style_model_from_preset,
            preset_default=PRESET_DEFAULT,
        )
    finally:
        cancel_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cancel_task

    if cancel_event.is_set() or (not success and message == "Operation cancelled."):
        raise PipelineCancelledError()
    if not success:
        raise RuntimeError(message or "Pipeline export failed.")

    await emit_event({"type": "progress", "pct": 100})
