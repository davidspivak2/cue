from __future__ import annotations

import datetime
import hashlib
import json
import logging
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6 import QtCore
from .progress import ProgressStep
from .ffmpeg_utils import (
    ensure_ffmpeg_available,
    extract_video_frame,
    escape_subtitles_filter_path,
    format_filter_style,
    get_ffprobe_json,
    get_media_duration,
    get_runtime_mode,
    get_subprocess_kwargs,
    resolve_ffmpeg_paths,
)
from .paths import get_models_dir, get_preview_frames_dir
from .srt_utils import parse_srt_file, select_preview_moment

TRANSCRIBE_MODEL_NAME = "large-v3"


class CancelledError(Exception):
    pass


class TranscriptionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        return_code: Optional[int],
        watchdog_triggered: bool,
        srt_exists: bool,
        srt_size: int,
    ) -> None:
        super().__init__(message)
        self.return_code = return_code
        self.watchdog_triggered = watchdog_triggered
        self.srt_exists = srt_exists
        self.srt_size = srt_size


@dataclass
class TranscriptionSettings:
    apply_audio_filter: bool
    keep_extracted_audio: bool
    device: str
    compute_type: str
    quality: str
    punctuation_rescue_fallback_enabled: bool


@dataclass
class BurnInSettings:
    font_name: str
    font_size: int
    outline: int
    shadow: int
    margin_v: int


@dataclass
class DiagnosticsSettings:
    enabled: bool
    write_on_success: bool
    categories: dict[str, bool]


class WorkerSignals(QtCore.QObject):
    log = QtCore.Signal(str, bool)
    finished = QtCore.Signal(bool, str, dict)
    started = QtCore.Signal(str)
    progress = QtCore.Signal(str, object, str)


class TaskType:
    GENERATE_SRT = "generate_srt"
    BURN_IN = "burn_in"


class Worker(QtCore.QObject):
    def __init__(
        self,
        task_type: str,
        video_path: Path,
        output_dir: Path,
        srt_path: Optional[Path] = None,
        transcription_settings: Optional[TranscriptionSettings] = None,
        burnin_settings: Optional[BurnInSettings] = None,
        diagnostics_settings: Optional[DiagnosticsSettings] = None,
        session_log_path: Optional[Path] = None,
    ) -> None:
        super().__init__()
        self.signals = WorkerSignals()
        self.task_type = task_type
        self.video_path = video_path
        self.output_dir = output_dir
        self.srt_path = srt_path
        self.transcription_settings = transcription_settings
        self.burnin_settings = burnin_settings
        self.diagnostics_settings = diagnostics_settings
        self.session_log_path = session_log_path
        self._cancelled = threading.Event()
        self._process: Optional[subprocess.Popen[str]] = None
        self._progress_value = 0
        self._progress_label = ""
        self._progress_phase = ""
        self._step_progress: dict[str, float] = {}
        self._last_progress_emit = 0.0
        self._smooth_progress: Optional[SmoothProgress] = None
        self._transcribe_estimator_stop: Optional[threading.Event] = None
        self._transcribe_estimator_thread: Optional[threading.Thread] = None
        self._logger = logging.getLogger("hebrew_subtitle_gui")
        self._last_audio_extract_command: Optional[list[str]] = None
        self._audio_path: Optional[Path] = None
        self._srt_path: Optional[Path] = None
        self._output_video_path: Optional[Path] = None
        self._transcribe_command: Optional[str] = None
        self._burn_in_command: Optional[str] = None
        self._burn_in_audio_mode: Optional[str] = None
        self._transcribe_parent_config: Optional[dict[str, object]] = None
        self._transcribe_worker_config: Optional[dict[str, object]] = None
        self._transcribe_worker_note: Optional[str] = None
        self._transcribe_stats: Optional[dict[str, object]] = None
        self._audio_info: Optional[dict[str, object]] = None
        self._prepare_audio_seconds: Optional[float] = None
        self._transcribe_seconds: Optional[float] = None
        self._burn_in_seconds: Optional[float] = None
        self._total_seconds: Optional[float] = None

    def cancel(self) -> None:
        self._cancelled.set()
        self._stop_smooth_progress()
        self._stop_transcribe_estimator()
        if self._process and self._process.poll() is None:
            self._process.terminate()

    @QtCore.Slot()
    def run(self) -> None:
        start_time = time.monotonic()
        success = False
        message = ""
        result: dict[str, str] = {}
        try:
            ensure_ffmpeg_available()
            if self.task_type == TaskType.GENERATE_SRT:
                self.signals.started.emit("Preparing audio")
                result = self._run_generate_srt()
                message = f"Subtitles created: {result['srt_path']}"
                success = True
            elif self.task_type == TaskType.BURN_IN:
                self.signals.started.emit("Exporting video")
                result = self._run_burn_in()
                message = "Your video is ready."
                success = True
            else:
                raise ValueError(f"Unknown task type: {self.task_type}")
        except CancelledError:
            message = "Operation cancelled."
        except Exception as exc:  # noqa: BLE001
            self._logger.exception("Unhandled worker exception")
            self.signals.log.emit("Exception occurred:", True)
            self.signals.log.emit(str(exc), True)
            message = str(exc)
        finally:
            self._total_seconds = time.monotonic() - start_time
            self._maybe_write_diagnostics(success, message, result)
            self.signals.finished.emit(success, message, result)

    def _run_generate_srt(self) -> dict:
        settings = self.transcription_settings
        if settings is None:
            raise ValueError("Missing transcription settings")

        audio_path = self.output_dir / f"{self.video_path.stem}_audio_for_whisper.wav"
        srt_path = self.output_dir / f"{self.video_path.stem}.srt"
        self._audio_path = audio_path
        self._srt_path = srt_path
        self.signals.log.emit(f"Audio file: {audio_path}", True)
        self.signals.log.emit(f"Subtitles file: {srt_path}", True)

        video_duration = self._probe_duration(self.video_path)
        if video_duration:
            self.signals.log.emit(f"Video duration: {video_duration:.2f}s", True)
        else:
            self.signals.log.emit(
                "Warning: unable to read video duration; progress may be limited.",
                True,
            )
        self.signals.log.emit("Preparing audio...", True)
        self._emit_step_progress(ProgressStep.PREPARE_AUDIO, 0.0, "Extracting audio", force=True)
        prepare_start = time.monotonic()
        self._extract_audio(audio_path, settings.apply_audio_filter, video_duration)
        self._prepare_audio_seconds = time.monotonic() - prepare_start

        if self._cancelled.is_set():
            raise CancelledError()

        audio_duration = self._probe_duration(audio_path)
        if audio_duration:
            self.signals.log.emit(f"Audio duration: {audio_duration:.2f}s", True)
        else:
            self.signals.log.emit(
                "Warning: unable to read audio duration; using video duration.",
                True,
            )
        duration_seconds = audio_duration or video_duration

        if self._cancelled.is_set():
            raise CancelledError()

        transcribe_start = time.monotonic()
        try:
            self._run_transcription_subprocess(
                audio_path=audio_path,
                srt_path=srt_path,
                duration_seconds=duration_seconds,
                force_cpu=False,
            )
        except TranscriptionError as exc:
            should_retry = (
                exc.return_code == 3221225477
                or exc.watchdog_triggered
                or not exc.srt_exists
                or exc.srt_size == 0
            )
            if should_retry:
                model_dir = get_models_dir() / TRANSCRIBE_MODEL_NAME
                if exc.return_code == 3221225477 and model_dir.exists():
                    self.signals.log.emit(
                        f"Clearing cached data due to an access issue: {model_dir}",
                        True,
                    )
                    shutil.rmtree(model_dir, ignore_errors=True)
                self.signals.log.emit(
                    "Fast mode failed; retrying in compatibility mode. This may take longer.",
                    True,
                )
                try:
                    self._run_transcription_subprocess(
                        audio_path=audio_path,
                        srt_path=srt_path,
                        duration_seconds=duration_seconds,
                        force_cpu=True,
                    )
                except TranscriptionError as retry_exc:
                    message = (
                        "Couldn't create subtitles after a retry.\n"
                        f"Return code: {retry_exc.return_code}"
                    )
                    raise RuntimeError(message) from retry_exc
            else:
                self.signals.log.emit(
                    f"Couldn't create subtitles; keeping audio file: {audio_path}",
                    True,
                )
                raise
        except Exception:
            self.signals.log.emit(
                f"Couldn't create subtitles; keeping audio file: {audio_path}",
                True,
            )
            raise
        finally:
            self._transcribe_seconds = time.monotonic() - transcribe_start

        if not srt_path.exists() or srt_path.stat().st_size == 0:
            raise RuntimeError(f"Subtitles were not created: {srt_path}")

        self._capture_audio_info_if_needed(audio_path)

        preview_frame_path: Optional[Path] = None
        preview_subtitle_text: Optional[str] = None
        preview_timestamp_seconds: Optional[float] = None
        try:
            cues = parse_srt_file(srt_path)
            preview = select_preview_moment(cues, video_duration)
            if preview:
                preview_subtitle_text = preview.subtitle_text
                preview_timestamp_seconds = preview.timestamp_seconds
                preview_frame_path = self._ensure_preview_frame(
                    srt_path=srt_path,
                    timestamp_seconds=preview_timestamp_seconds,
                )
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit(f"Preview generation failed: {exc}", False)
        if settings.keep_extracted_audio:
            self.signals.log.emit(
                f"Keeping extracted audio file: {audio_path}",
                True,
            )
        else:
            try:
                audio_path.unlink(missing_ok=True)
                self.signals.log.emit(f"Deleted audio file: {audio_path}", True)
            except Exception as exc:  # noqa: BLE001
                self.signals.log.emit(
                    f"Warning: failed to delete audio file ({audio_path}): {exc}",
                    True,
                )

        return {
            "audio_path": str(audio_path),
            "srt_path": str(srt_path),
            "preview_frame_path": (
                str(preview_frame_path) if preview_frame_path is not None else None
            ),
            "preview_subtitle_text": preview_subtitle_text,
            "preview_timestamp_seconds": preview_timestamp_seconds,
        }

    def _extract_audio(self, audio_path: Path, apply_filter: bool, duration_seconds: Optional[float]) -> None:
        ffmpeg_path, _, _ = ensure_ffmpeg_available()
        command = [
            str(ffmpeg_path),
            "-y",
            "-hide_banner",
            "-i",
            str(self.video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
        ]
        if apply_filter:
            command += [
                "-af",
                "highpass=f=80,lowpass=f=8000,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11",
            ]
        command += ["-progress", "pipe:1", "-nostats"]
        command.append(str(audio_path))
        self._last_audio_extract_command = command
        self._run_ffmpeg_with_progress(
            command,
            duration_seconds,
            ProgressStep.PREPARE_AUDIO,
            "Extracting audio",
        )

    def _ensure_preview_frame(
        self,
        *,
        srt_path: Path,
        timestamp_seconds: float,
    ) -> Optional[Path]:
        try:
            srt_mtime = int(srt_path.stat().st_mtime)
        except FileNotFoundError:
            srt_mtime = 0
        timestamp_ms = int(round(timestamp_seconds * 1000))
        cache_key = f"{self.video_path.resolve()}|{srt_mtime}|{timestamp_ms}"
        cache_name = hashlib.sha1(cache_key.encode("utf-8")).hexdigest() + ".jpg"
        output_path = get_preview_frames_dir() / cache_name
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        success = extract_video_frame(
            self.video_path,
            timestamp_seconds,
            output_path,
            width=640,
        )
        return output_path if success else None

    def _run_burn_in(self) -> dict:
        settings = self.burnin_settings
        if settings is None:
            raise ValueError("Missing burn-in settings")

        srt_path = self.srt_path or self.output_dir / f"{self.video_path.stem}.srt"
        self._srt_path = srt_path
        if not srt_path.exists():
            raise FileNotFoundError(f"Subtitles file not found: {srt_path}")

        output_path = self.output_dir / f"{self.video_path.stem}_subtitled.mp4"
        self._output_video_path = output_path
        self.signals.log.emit(f"Subtitles file: {srt_path}", True)
        self.signals.log.emit(f"Video file: {output_path}", True)
        video_duration = self._probe_duration(self.video_path)
        if video_duration:
            self.signals.log.emit(f"Video duration: {video_duration:.2f}s", True)
        else:
            self.signals.log.emit(
                "Warning: unable to read video duration; progress may be limited.",
                True,
            )
        ffmpeg_path, _, _ = ensure_ffmpeg_available()

        escaped_path = escape_subtitles_filter_path(srt_path)
        style = format_filter_style(
            settings.font_name,
            settings.font_size,
            settings.outline,
            settings.shadow,
            settings.margin_v,
        )
        subtitles_filter = f"subtitles='{escaped_path}':force_style='{style}'"

        base_command = [
            str(ffmpeg_path),
            "-y",
            "-hide_banner",
            "-i",
            str(self.video_path),
            "-progress",
            "pipe:1",
            "-nostats",
            "-vf",
            subtitles_filter,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-movflags",
            "+faststart",
        ]

        self.signals.log.emit("Adding subtitles to the video...", True)
        self._emit_step_progress(ProgressStep.EXPORT, 0.0, "Encoding", force=True)
        copy_command = base_command + ["-c:a", "copy", str(output_path)]
        self._burn_in_command = subprocess.list2cmdline(copy_command)
        self._burn_in_audio_mode = "copy"
        burn_start = time.monotonic()
        try:
            self._run_ffmpeg_with_progress(
                copy_command,
                video_duration,
                ProgressStep.EXPORT,
                "Encoding",
            )
            self._burn_in_seconds = time.monotonic() - burn_start
            return {"output_path": str(output_path)}
        except RuntimeError as exc:
            self.signals.log.emit("Audio copy failed, trying another format...", True)
            self.signals.log.emit(str(exc), True)

        aac_command = base_command + ["-c:a", "aac", "-b:a", "192k", str(output_path)]
        self._burn_in_command = subprocess.list2cmdline(aac_command)
        self._burn_in_audio_mode = "aac"
        self._run_ffmpeg_with_progress(
            aac_command,
            video_duration,
            ProgressStep.EXPORT,
            "Encoding",
        )
        self._burn_in_seconds = time.monotonic() - burn_start
        return {"output_path": str(output_path)}

    def _run_ffmpeg(self, command: list[str]) -> None:
        if self._cancelled.is_set():
            raise CancelledError()

        self.signals.log.emit(f"Video tool command: {subprocess.list2cmdline(command)}", True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **get_subprocess_kwargs(),
        )
        self._process = process
        stderr_tail: deque[str] = deque(maxlen=50)

        assert process.stderr is not None
        for line in process.stderr:
            stderr_tail.append(line.rstrip())
            self.signals.log.emit(line.rstrip(), True)
            if self._cancelled.is_set():
                process.terminate()
                raise CancelledError()

        return_code = process.wait()
        self._process = None

        if return_code != 0:
            tail_text = "\n".join(stderr_tail)
            raise RuntimeError("Video processing failed. Details:\n" + tail_text)

    def _run_ffmpeg_with_progress(
        self,
        command: list[str],
        duration_seconds: Optional[float],
        step_id: str,
        status_label: str,
    ) -> None:
        if self._cancelled.is_set():
            raise CancelledError()

        self.signals.log.emit(f"Video tool command: {subprocess.list2cmdline(command)}", True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **get_subprocess_kwargs(),
        )
        self._process = process
        stderr_tail: deque[str] = deque(maxlen=50)
        stdout_tail: deque[str] = deque(maxlen=50)
        log_lock = threading.Lock()
        output_lock = threading.Lock()
        last_output_time = time.monotonic()

        def _read_stderr() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                text = line.rstrip()
                stderr_tail.append(text)
                if text:
                    with log_lock:
                        self.signals.log.emit(text, True)
                if self._cancelled.is_set():
                    break

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()

        last_log_time = 0.0
        end_emitted = False
        if duration_seconds is None:
            self._start_smooth_progress(step_id, status_label)
        assert process.stdout is not None
        for line in process.stdout:
            if self._cancelled.is_set():
                process.terminate()
                raise CancelledError()
            text = line.strip()
            if text.startswith("out_time_ms=") and duration_seconds:
                try:
                    out_time_ms = int(text.split("=", 1)[1])
                except ValueError:
                    continue
                progress = out_time_ms / (duration_seconds * 1_000_000)
                progress = max(0.0, min(progress, 1.0))
                self._emit_step_progress(step_id, progress, status_label)
                now = time.monotonic()
                if now - last_log_time >= 0.25:
                    self.signals.log.emit(
                        f"{status_label} progress: {int(progress * 100)}%",
                        True,
                    )
                    last_log_time = now
            elif text == "progress=end":
                self._emit_step_progress(step_id, 1.0, status_label, force=True)
                end_emitted = True

        return_code = process.wait()
        stderr_thread.join(timeout=1)
        self._process = None

        if return_code == 0:
            if not end_emitted:
                self._emit_step_progress(step_id, 1.0, status_label, force=True)
        self._stop_smooth_progress()

        if return_code != 0:
            tail_text = "\n".join(stderr_tail)
            raise RuntimeError("Video processing failed. Details:\n" + tail_text)

    def _run_transcription_subprocess(
        self,
        audio_path: Path,
        srt_path: Path,
        duration_seconds: Optional[float],
        force_cpu: bool,
    ) -> None:
        if not self.transcription_settings:
            raise ValueError("Missing transcription settings")
        device = self.transcription_settings.device
        compute_type = self.transcription_settings.compute_type
        if force_cpu and device != "cpu":
            device = "cpu"
            if compute_type == "float16":
                compute_type = "int16"
        prefer_gpu = device == "cuda" and not force_cpu
        force_cpu_flag = force_cpu or device == "cpu"
        self.signals.started.emit("Creating subtitles")
        self.signals.log.emit("Starting subtitles worker...", True)
        self._emit_step_progress(
            ProgressStep.TRANSCRIBE,
            0.0,
            "Loading model",
            force=True,
        )
        runtime_mode = get_runtime_mode()
        if runtime_mode == "source":
            command = [
                sys.executable,
                "-m",
                "app.transcribe_worker",
            ]
        else:
            worker_exe = Path(sys.executable).with_name("HebrewSubtitleWorker.exe")
            if worker_exe.exists():
                command = [str(worker_exe)]
            else:
                command = [
                    sys.executable,
                    "--run-transcribe-worker",
                ]
        command += [
            "--wav",
            str(audio_path),
            "--srt",
            str(srt_path),
            "--lang",
            "he",
        ]
        if force_cpu_flag:
            command.append("--force-cpu")
        else:
            command.append("--prefer-gpu")
        command += ["--device", device, "--compute-type", compute_type]
        if duration_seconds:
            command += ["--duration-seconds", f"{duration_seconds:.2f}"]
        if self._last_audio_extract_command:
            command += [
                "--ffmpeg-args-json",
                json.dumps(self._last_audio_extract_command),
            ]
        command += [
            "--punctuation-rescue",
            "on" if self.transcription_settings.punctuation_rescue_fallback_enabled else "off",
        ]

        parent_config = {
            "model_name": TRANSCRIBE_MODEL_NAME,
            "models_dir": str(get_models_dir()),
            "prefer_gpu": prefer_gpu,
            "force_cpu": force_cpu_flag,
            "device": device,
            "compute_type": compute_type,
            "ffmpeg_args": self._last_audio_extract_command,
            "punctuation_rescue_fallback_enabled": (
                self.transcription_settings.punctuation_rescue_fallback_enabled
            ),
        }
        self.signals.log.emit(
            f"TRANSCRIBE_PARENT_CONFIG {json.dumps(parent_config, sort_keys=True)}",
            True,
        )
        self._transcribe_parent_config = parent_config
        self._transcribe_command = subprocess.list2cmdline(command)
        self.signals.log.emit(f"Subtitles command: {subprocess.list2cmdline(command)}", True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **get_subprocess_kwargs(),
        )
        self._process = process

        stderr_tail: deque[str] = deque(maxlen=50)
        stdout_tail: deque[str] = deque(maxlen=50)
        log_lock = threading.Lock()
        output_lock = threading.Lock()
        last_output_time = time.monotonic()

        def _emit_log(message: str, show_in_ui: bool = True) -> None:
            with log_lock:
                self.signals.log.emit(message, show_in_ui)

        def _mark_output() -> None:
            nonlocal last_output_time
            with output_lock:
                last_output_time = time.monotonic()

        def _read_stderr() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                text = line.rstrip()
                if text:
                    stderr_tail.append(text)
                    _mark_output()
                    _emit_log(text, True)
                if self._cancelled.is_set():
                    break

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()

        max_end_seconds = 0.0
        progress_lock = threading.Lock()
        real_progress = 0.0
        real_progress_seen = False
        transcribe_started = False
        last_progress_log = 0.0
        done_seen = False
        done_srt_path: Optional[Path] = None
        transcribe_config_json: Optional[str] = None
        watchdog_triggered = False
        watchdog_elapsed = 0.0
        watchdog_stop = threading.Event()
        no_output_timeout = 60.0
        smooth_transcribe_started = False
        if duration_seconds is None:
            self._start_smooth_progress(ProgressStep.TRANSCRIBE, "Loading model")
        else:
            rtf_est = self._resolve_transcribe_rtf_est(
                self.transcription_settings,
                device,
                compute_type,
            )
            estimator_stop = threading.Event()
            self._transcribe_estimator_stop = estimator_stop

            def _estimate_progress() -> None:
                start_time = time.monotonic()
                while not estimator_stop.wait(0.5):
                    if self._cancelled.is_set():
                        break
                    elapsed = time.monotonic() - start_time
                    processed_seconds_est = elapsed / rtf_est
                    step_progress_est = processed_seconds_est / duration_seconds
                    with progress_lock:
                        current_real = real_progress
                        has_real = real_progress_seen
                        has_started = transcribe_started
                    if not has_real:
                        step_progress_est = min(step_progress_est, 0.85)
                    else:
                        step_progress_est = min(
                            step_progress_est,
                            min(0.99, current_real + 0.02),
                        )
                    step_progress = max(current_real, step_progress_est)
                    label = "Listening to audio" if has_started else "Loading model"
                    self._emit_step_progress(
                        ProgressStep.TRANSCRIBE,
                        step_progress,
                        label,
                    )

            self._transcribe_estimator_thread = threading.Thread(
                target=_estimate_progress, daemon=True
            )
            self._transcribe_estimator_thread.start()

        def _watchdog() -> None:
            nonlocal watchdog_triggered, watchdog_elapsed
            while not watchdog_stop.is_set():
                time.sleep(1.0)
                if done_seen:
                    continue
                with output_lock:
                    elapsed = time.monotonic() - last_output_time
                if elapsed > no_output_timeout and process.poll() is None:
                    watchdog_triggered = True
                    watchdog_elapsed = elapsed
                    _emit_log(
                        f"No updates for {elapsed:.1f}s; stopping subtitles worker.",
                        True,
                    )
                    process.terminate()
                    break

        watchdog_thread = threading.Thread(target=_watchdog, daemon=True)
        watchdog_thread.start()

        assert process.stdout is not None
        for line in process.stdout:
            if self._cancelled.is_set():
                process.terminate()
                raise CancelledError()
            text = line.strip()
            if not text:
                continue
            stdout_tail.append(text)
            _mark_output()
            show_in_ui = True
            if text.startswith("TRANSCRIBE_CONFIG_JSON "):
                transcribe_config_json = text
                config_payload = text.split(" ", 1)[1] if " " in text else ""
                if config_payload:
                    try:
                        self._transcribe_worker_config = json.loads(config_payload)
                    except json.JSONDecodeError:
                        self._transcribe_worker_config = None
                        self._transcribe_worker_note = (
                            "TRANSCRIBE_CONFIG_JSON was present but could not be parsed."
                        )
                else:
                    self._transcribe_worker_config = None
                    self._transcribe_worker_note = (
                        "TRANSCRIBE_CONFIG_JSON was present but empty."
                    )
            if text.startswith("TRANSCRIBE_STATS_JSON "):
                show_in_ui = False
                stats_payload = text.split(" ", 1)[1] if " " in text else ""
                if stats_payload:
                    try:
                        self._transcribe_stats = json.loads(stats_payload)
                    except json.JSONDecodeError:
                        self._transcribe_stats = None
            if text.startswith("PROGRESS_END"):
                _emit_log(text, False)
                if duration_seconds:
                    try:
                        end_value = float(text.split(" ", 1)[1])
                    except (IndexError, ValueError):
                        continue
                    if end_value > max_end_seconds:
                        max_end_seconds = end_value
                        progress = min(0.99, max_end_seconds / duration_seconds)
                        with progress_lock:
                            real_progress = progress
                            real_progress_seen = True
                            transcribe_started = True
                        self._emit_step_progress(
                            ProgressStep.TRANSCRIBE,
                            progress,
                            "Listening to audio",
                        )
                else:
                    transcribe_started = True
                    if not smooth_transcribe_started:
                        smooth_transcribe_started = True
                        self._start_smooth_progress(
                            ProgressStep.TRANSCRIBE,
                            "Listening to audio",
                            start=self._step_progress.get(ProgressStep.TRANSCRIBE, 0.0),
                        )
                now = time.monotonic()
                if now - last_progress_log >= 2.0:
                    _emit_log("Listening progress update received.", True)
                    last_progress_log = now
                continue

            _emit_log(text, show_in_ui)
            if text.startswith("MODE"):
                continue
            if text.startswith("HEARTBEAT MODEL_LOAD") or text.startswith("Loading model"):
                self._emit_step_progress(
                    ProgressStep.TRANSCRIBE,
                    None,
                    "Loading model",
                )
                continue
            if text.startswith("HEARTBEAT TRANSCRIBE"):
                with progress_lock:
                    transcribe_started = True
                if duration_seconds is None and not smooth_transcribe_started:
                    smooth_transcribe_started = True
                    self._start_smooth_progress(
                        ProgressStep.TRANSCRIBE,
                        "Listening to audio",
                        start=self._step_progress.get(ProgressStep.TRANSCRIBE, 0.0),
                    )
                self._emit_step_progress(
                    ProgressStep.TRANSCRIBE,
                    None,
                    "Listening to audio",
                )
                continue
            if text.startswith("READY"):
                self._emit_step_progress(
                    ProgressStep.TRANSCRIBE,
                    0.0,
                    "Loading model",
                    force=True,
                )
                continue
            if text.startswith("DONE"):
                done_seen = True
                watchdog_stop.set()
                parts = text.split(" ", 1)
                if len(parts) == 2:
                    done_srt_path = Path(parts[1].strip())
                self._stop_smooth_progress()
                self._stop_transcribe_estimator()
                self._emit_step_progress(
                    ProgressStep.TRANSCRIBE,
                    1.0,
                    "Writing subtitles",
                    force=True,
                )

        return_code = process.wait()
        watchdog_stop.set()
        watchdog_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        self._process = None
        self._stop_smooth_progress()
        self._stop_transcribe_estimator()

        srt_candidate = done_srt_path or srt_path
        srt_exists = srt_candidate.exists()
        srt_size = srt_candidate.stat().st_size if srt_exists else 0

        if done_seen and srt_exists and srt_size > 0:
            if return_code != 0:
                _emit_log(
                    f"Subtitles worker exited with code {return_code}, but DONE was received and "
                    f"subtitles file exists; continuing.",
                    True,
                )
            return

        diagnostics = [
            f"Return code: {return_code}",
            f"DONE seen: {done_seen}",
            f"Subtitles path: {srt_candidate}",
            f"Subtitles file exists: {srt_exists}",
            f"Subtitles file size: {srt_size}",
        ]
        if watchdog_triggered:
            diagnostics.append(
                f"Watchdog timeout after {watchdog_elapsed:.1f}s since the last update."
            )

        stdout_tail_text = "\n".join(stdout_tail) or "(empty)"
        if transcribe_config_json and transcribe_config_json not in stdout_tail_text:
            stdout_tail_text = f"{transcribe_config_json}\n{stdout_tail_text}"
        stderr_tail_text = "\n".join(stderr_tail) or "(empty)"
        error_message = (
            "Couldn't create subtitles.\n"
            + "\n".join(diagnostics)
            + "\n\n--- stdout tail ---\n"
            + stdout_tail_text
            + "\n\n--- stderr tail ---\n"
            + stderr_tail_text
        )
        raise TranscriptionError(
            error_message,
            return_code=return_code,
            watchdog_triggered=watchdog_triggered,
            srt_exists=srt_exists,
            srt_size=srt_size,
        )

    def _capture_audio_info_if_needed(self, audio_path: Path) -> None:
        if not self._diagnostics_category_enabled("audio_info"):
            return
        self._audio_info = self._build_media_info(audio_path)

    def _diagnostics_category_enabled(self, key: str) -> bool:
        settings = self.diagnostics_settings
        if not settings or not settings.enabled:
            return False
        return settings.categories.get(key, False)

    def _maybe_write_diagnostics(
        self,
        success: bool,
        message: str,
        result: dict[str, str],
    ) -> None:
        if not self.diagnostics_settings or not self.diagnostics_settings.enabled:
            return
        if success and not self.diagnostics_settings.write_on_success:
            return
        payload = self._build_diagnostics_payload(success, message, result)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"diag_{self.task_type}_{timestamp}.json"
        primary_path = self.output_dir / filename
        try:
            primary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._logger.info("Diagnostics file written: %s", primary_path)
            return
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Failed to write diagnostics file to output folder: %s",
                exc,
            )

        fallback_dir = (
            self.session_log_path.parent
            if self.session_log_path and self.session_log_path.parent.exists()
            else None
        )
        if not fallback_dir:
            return
        fallback_path = fallback_dir / filename
        try:
            fallback_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._logger.info("Diagnostics file written: %s", fallback_path)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Failed to write diagnostics file fallback: %s", exc)

    def _build_diagnostics_payload(
        self,
        success: bool,
        message: str,
        result: dict[str, str],
    ) -> dict[str, object]:
        created_at = datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")
        data: dict[str, object] = {
            "schema_version": 1,
            "created_at": created_at,
            "task_type": self.task_type,
            "success": success,
            "session_log_path": str(self.session_log_path) if self.session_log_path else None,
            "inputs_outputs": {
                "video_path": str(self.video_path),
                "output_dir": str(self.output_dir),
                "audio_path": str(self._audio_path) if self._audio_path else None,
                "srt_path": str(self._srt_path) if self._srt_path else None,
                "output_video_path": str(self._output_video_path)
                if self._output_video_path
                else None,
            },
            "audio_filter_enabled": bool(
                self.transcription_settings and self.transcription_settings.apply_audio_filter
            ),
            "keep_extracted_audio_enabled": bool(
                self.transcription_settings and self.transcription_settings.keep_extracted_audio
            ),
        }
        if not success:
            data["error"] = message

        if self._diagnostics_category_enabled("app_system"):
            ffmpeg_path, ffprobe_path, mode = resolve_ffmpeg_paths()
            ffmpeg_mode = mode
            app_version = getattr(sys.modules.get("__main__"), "__version__", "unknown")
            data["app_system"] = {
                "app_version": app_version,
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "runtime_mode": get_runtime_mode(),
                "ffmpeg": str(ffmpeg_path) if ffmpeg_path else "missing",
                "ffprobe": str(ffprobe_path) if ffprobe_path else "missing",
                "ffmpeg_mode": ffmpeg_mode,
                "process_executable": sys.executable,
            }

        if self._diagnostics_category_enabled("video_info"):
            data["video_info"] = self._build_media_info(self.video_path)

        if self._diagnostics_category_enabled("audio_info"):
            data["audio_info"] = self._audio_info or (
                self._build_media_info(self._audio_path)
                if self._audio_path
                else None
            )

        if self._diagnostics_category_enabled("transcription_config"):
            worker_config = self._transcribe_worker_config
            note = self._transcribe_worker_note
            if worker_config is None and note is None:
                note = "TRANSCRIBE_CONFIG_JSON was not captured from the worker output."
            data["transcription_config"] = {
                "parent_config": self._transcribe_parent_config,
                "worker_config": worker_config,
                "worker_config_note": note,
            }

        if self._diagnostics_category_enabled("srt_stats"):
            srt_path = self._srt_path
            srt_stats = self._build_srt_stats(srt_path) if srt_path else None
            if self._transcribe_stats is not None:
                if srt_stats is None:
                    srt_stats = {"transcription_stats": self._transcribe_stats}
                else:
                    srt_stats["transcription_stats"] = self._transcribe_stats
            data["srt_stats"] = srt_stats

        if self._diagnostics_category_enabled("commands_timings"):
            data["commands_timings"] = {
                "commands": {
                    "audio_extract_command": (
                        subprocess.list2cmdline(self._last_audio_extract_command)
                        if self._last_audio_extract_command
                        else None
                    ),
                    "transcribe_command": self._transcribe_command,
                    "burn_in_command_used": self._burn_in_command,
                    "burn_in_audio_mode": self._burn_in_audio_mode,
                },
                "timings": {
                    "prepare_audio_seconds": self._prepare_audio_seconds,
                    "transcribe_seconds": self._transcribe_seconds,
                    "burn_in_seconds": self._burn_in_seconds,
                    "total_seconds": self._total_seconds,
                },
            }

        return data

    def _build_media_info(self, path: Optional[Path]) -> Optional[dict[str, object]]:
        if not path:
            return None
        exists = path.exists()
        info: dict[str, object] = {
            "path": str(path),
            "exists": exists,
            "size_bytes": None,
            "mtime": None,
            "duration_seconds": None,
            "ffprobe_json": None,
        }
        if not exists:
            return info
        try:
            stat = path.stat()
            info["size_bytes"] = stat.st_size
            info["mtime"] = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception:  # noqa: BLE001
            pass
        try:
            info["duration_seconds"] = get_media_duration(path)
        except Exception:  # noqa: BLE001
            info["duration_seconds"] = None
        try:
            info["ffprobe_json"] = get_ffprobe_json(path)
        except Exception:  # noqa: BLE001
            info["ffprobe_json"] = None
        return info

    def _build_srt_stats(self, path: Path) -> Optional[dict[str, object]]:
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return None

        cue_count = 0
        words_total = 0
        words_per_cue: list[int] = []
        punctuation = {".": 0, ",": 0, "?": 0, "!": 0, ";": 0, ":": 0}
        current_lines: list[str] = []

        def _flush_cue() -> None:
            nonlocal words_total
            if not current_lines:
                return
            cue_text = " ".join(current_lines)
            for mark in punctuation:
                punctuation[mark] += cue_text.count(mark)
            word_count = len(re.findall(r"\w+", cue_text, flags=re.UNICODE))
            words_total += word_count
            words_per_cue.append(word_count)
            current_lines.clear()

        for line in text.splitlines():
            stripped = line.strip()
            if "-->" in stripped:
                cue_count += 1
                _flush_cue()
                continue
            if not stripped:
                _flush_cue()
                continue
            if stripped.isdigit():
                continue
            current_lines.append(stripped)

        _flush_cue()
        avg_words = words_total / cue_count if cue_count else 0
        max_words = max(words_per_cue) if words_per_cue else 0
        try:
            stat = path.stat()
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
            size_bytes = stat.st_size
        except Exception:  # noqa: BLE001
            mtime = None
            size_bytes = None
        return {
            "path": str(path),
            "exists": True,
            "size_bytes": size_bytes,
            "mtime": mtime,
            "cue_count": cue_count,
            "words_total": words_total,
            "words_per_cue_avg": avg_words,
            "words_per_cue_max": max_words,
            "punctuation_counts": punctuation,
        }

    def _emit_step_progress(
        self,
        step_id: str,
        step_progress: Optional[float],
        label: str,
        *,
        force: bool = False,
    ) -> None:
        if step_id != self._progress_phase:
            self._progress_phase = step_id
            self._progress_value = 0
            self._progress_label = ""
        percent_int: Optional[int] = None
        if step_progress is not None:
            clamped = max(0.0, min(step_progress, 1.0))
            clamped = max(clamped, self._step_progress.get(step_id, 0.0))
            self._step_progress[step_id] = clamped
            percent_int = int(round(clamped * 100))

        status = label
        now = time.monotonic()
        if not force and now - self._last_progress_emit < 0.1:
            return
        if status == self._progress_label and percent_int == self._progress_value:
            return
        if percent_int is None:
            percent_int = self._progress_value
        self._progress_value = percent_int
        self._progress_label = status
        self._last_progress_emit = now
        self.signals.progress.emit(step_id, step_progress, status)

    def _start_smooth_progress(
        self,
        step_id: str,
        label: str,
        *,
        start: float = 0.0,
        cap: float = 0.95,
        increment: float = 0.002,
        interval: float = 0.3,
    ) -> None:
        self._stop_smooth_progress()
        smooth = SmoothProgress(self._emit_step_progress)
        smooth.start(
            step_id=step_id,
            label=label,
            start=start,
            cap=cap,
            increment=increment,
            interval=interval,
        )
        self._smooth_progress = smooth

    def _stop_smooth_progress(self) -> None:
        if self._smooth_progress:
            self._smooth_progress.stop()
            self._smooth_progress = None

    def _resolve_transcribe_rtf_est(
        self,
        settings: TranscriptionSettings,
        device: str,
        compute_type: str,
    ) -> float:
        quality = settings.quality
        if quality == "fast":
            return 4.0
        if quality == "accurate":
            return 6.0
        if quality == "ultra":
            return 10.0
        if device == "cuda" and compute_type == "float16":
            return 1.5
        return 6.0

    def _stop_transcribe_estimator(self) -> None:
        if self._transcribe_estimator_stop:
            self._transcribe_estimator_stop.set()
        if self._transcribe_estimator_thread:
            self._transcribe_estimator_thread.join(timeout=1)
        self._transcribe_estimator_stop = None
        self._transcribe_estimator_thread = None

    def _probe_duration(self, path: Path) -> Optional[float]:
        try:
            return get_media_duration(path)
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit(f"Video check failed: {exc}", True)
            return None


class SmoothProgress:
    def __init__(self, emit_callback) -> None:
        self._emit_callback = emit_callback
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(
        self,
        *,
        step_id: str,
        label: str,
        start: float,
        cap: float,
        increment: float,
        interval: float,
    ) -> None:
        self.stop()
        self._stop_event = threading.Event()
        progress_value = start

        def _run() -> None:
            nonlocal progress_value
            while not self._stop_event.wait(interval):
                if progress_value >= cap:
                    continue
                progress_value = min(cap, progress_value + increment)
                self._emit_callback(step_id, progress_value, label)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._thread:
            return
        self._stop_event.set()
        self._thread.join(timeout=1)
        self._thread = None
