from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6 import QtCore
from .ffmpeg_utils import (
    ensure_ffmpeg_available,
    escape_subtitles_filter_path,
    format_filter_style,
    get_media_duration,
)


class CancelledError(Exception):
    pass


@dataclass
class TranscriptionSettings:
    apply_audio_filter: bool


@dataclass
class BurnInSettings:
    font_name: str
    font_size: int
    outline: int
    shadow: int
    margin_v: int


class WorkerSignals(QtCore.QObject):
    log = QtCore.Signal(str, bool)
    finished = QtCore.Signal(bool, str, dict)
    started = QtCore.Signal(str)
    progress = QtCore.Signal(int, str)


class TaskType:
    GENERATE_SRT = "generate_srt"
    BURN_IN = "burn_in"


class Worker(QtCore.QObject):
    def __init__(
        self,
        task_type: str,
        video_path: Path,
        srt_path: Optional[Path] = None,
        transcription_settings: Optional[TranscriptionSettings] = None,
        burnin_settings: Optional[BurnInSettings] = None,
    ) -> None:
        super().__init__()
        self.signals = WorkerSignals()
        self.task_type = task_type
        self.video_path = video_path
        self.srt_path = srt_path
        self.transcription_settings = transcription_settings
        self.burnin_settings = burnin_settings
        self._cancelled = threading.Event()
        self._process: Optional[subprocess.Popen[str]] = None
        self._progress_value = 0
        self._progress_label = ""
        self._progress_phase = ""
        self._logger = logging.getLogger("hebrew_subtitle_gui")

    def cancel(self) -> None:
        self._cancelled.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()

    @QtCore.Slot()
    def run(self) -> None:
        try:
            ensure_ffmpeg_available()
            if self.task_type == TaskType.GENERATE_SRT:
                self.signals.started.emit("Generating SRT")
                result = self._run_generate_srt()
                message = f"SRT created: {result['srt_path']}"
                self.signals.finished.emit(True, message, result)
            elif self.task_type == TaskType.BURN_IN:
                self.signals.started.emit("Hardcoding subtitles")
                result = self._run_burn_in()
                self.signals.finished.emit(True, "Subtitles hardcoded successfully.", result)
            else:
                raise ValueError(f"Unknown task type: {self.task_type}")
        except CancelledError:
            self.signals.finished.emit(False, "Operation cancelled.", {})
        except Exception as exc:  # noqa: BLE001
            self._logger.exception("Unhandled worker exception")
            self.signals.log.emit("Exception occurred:", True)
            self.signals.log.emit(str(exc), True)
            self.signals.finished.emit(False, str(exc), {})

    def _run_generate_srt(self) -> dict:
        settings = self.transcription_settings
        if settings is None:
            raise ValueError("Missing transcription settings")

        output_dir = self.video_path.parent
        audio_path = output_dir / f"{self.video_path.stem}_audio_for_whisper.wav"
        srt_path = output_dir / f"{self.video_path.stem}.srt"
        self.signals.log.emit(f"Output WAV: {audio_path}", True)
        self.signals.log.emit(f"Output SRT: {srt_path}", True)

        video_duration = self._probe_duration(self.video_path)
        if video_duration:
            self.signals.log.emit(f"Video duration: {video_duration:.2f}s", True)
        else:
            self.signals.log.emit(
                "Warning: unable to read video duration; progress may be limited.",
                True,
            )

        self.signals.log.emit("Extracting audio via FFmpeg...", True)
        self._emit_progress(0, "Extracting audio")
        self._extract_audio(audio_path, settings.apply_audio_filter, video_duration)

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

        try:
            self._run_transcription_subprocess(
                audio_path=audio_path,
                srt_path=srt_path,
                duration_seconds=duration_seconds,
            )
        except Exception:
            self.signals.log.emit(f"Transcription failed; keeping WAV: {audio_path}", True)
            raise

        if not srt_path.exists() or srt_path.stat().st_size == 0:
            raise RuntimeError(f"SRT was not created: {srt_path}")

        try:
            audio_path.unlink(missing_ok=True)
            self.signals.log.emit(f"Deleted WAV: {audio_path}", True)
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit(
                f"Warning: failed to delete WAV ({audio_path}): {exc}",
                True,
            )

        return {
            "audio_path": str(audio_path),
            "srt_path": str(srt_path),
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
        self._run_ffmpeg_with_progress(command, duration_seconds, "Extracting audio")

    def _run_burn_in(self) -> dict:
        settings = self.burnin_settings
        if settings is None:
            raise ValueError("Missing burn-in settings")

        output_dir = self.video_path.parent
        srt_path = self.srt_path or output_dir / f"{self.video_path.stem}.srt"
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT not found: {srt_path}")

        output_path = output_dir / f"{self.video_path.stem}_subtitled.mp4"
        self.signals.log.emit(f"SRT input: {srt_path}", True)
        self.signals.log.emit(f"Output video: {output_path}", True)
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

        self.signals.log.emit("Burning subtitles with audio copy...", True)
        copy_command = base_command + ["-c:a", "copy", str(output_path)]
        try:
            self._run_ffmpeg(copy_command)
            return {"output_path": str(output_path)}
        except RuntimeError as exc:
            self.signals.log.emit("Audio copy failed, retrying with AAC...", True)
            self.signals.log.emit(str(exc), True)

        aac_command = base_command + ["-c:a", "aac", "-b:a", "192k", str(output_path)]
        self._run_ffmpeg(aac_command)
        return {"output_path": str(output_path)}

    def _run_ffmpeg(self, command: list[str]) -> None:
        if self._cancelled.is_set():
            raise CancelledError()

        self.signals.log.emit(f"FFmpeg command: {subprocess.list2cmdline(command)}", True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
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
            raise RuntimeError("FFmpeg failed. Last output:\n" + tail_text)

    def _run_ffmpeg_with_progress(
        self,
        command: list[str],
        duration_seconds: Optional[float],
        phase_label: str,
    ) -> None:
        if self._cancelled.is_set():
            raise CancelledError()

        self.signals.log.emit(f"FFmpeg command: {subprocess.list2cmdline(command)}", True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._process = process
        stderr_tail: deque[str] = deque(maxlen=50)
        log_lock = threading.Lock()

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
                percent = (out_time_ms / (duration_seconds * 1_000_000)) * 100
                percent = max(0.0, min(percent, 100.0))
                self._emit_progress(percent, phase_label)
                now = time.monotonic()
                if now - last_log_time >= 0.25:
                    self.signals.log.emit(
                        f"{phase_label} progress: {int(percent)}%",
                        True,
                    )
                    last_log_time = now
            elif text == "progress=end":
                self._emit_progress(100, phase_label)

        return_code = process.wait()
        stderr_thread.join(timeout=1)
        self._process = None

        if return_code == 0:
            self._emit_progress(100, phase_label)

        if return_code != 0:
            tail_text = "\n".join(stderr_tail)
            raise RuntimeError("FFmpeg failed. Last output:\n" + tail_text)

    def _run_transcription_subprocess(
        self,
        audio_path: Path,
        srt_path: Path,
        duration_seconds: Optional[float],
    ) -> None:
        self.signals.log.emit("Starting Whisper worker subprocess...", True)
        command = [
            sys.executable,
            "-m",
            "app.transcribe_worker",
            "--wav",
            str(audio_path),
            "--srt",
            str(srt_path),
            "--lang",
            "he",
            "--prefer-gpu",
        ]
        if duration_seconds:
            command += ["--duration-seconds", f"{duration_seconds:.2f}"]

        self.signals.log.emit(f"Whisper command: {subprocess.list2cmdline(command)}", True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._process = process

        stderr_tail: deque[str] = deque(maxlen=50)
        log_lock = threading.Lock()

        def _emit_log(message: str, show_in_ui: bool = True) -> None:
            with log_lock:
                self.signals.log.emit(message, show_in_ui)

        def _read_stderr() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                text = line.rstrip()
                if text:
                    stderr_tail.append(text)
                    _emit_log(text, True)
                if self._cancelled.is_set():
                    break

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()

        max_end_seconds = 0.0
        last_progress_log = 0.0
        saw_done = False

        assert process.stdout is not None
        for line in process.stdout:
            if self._cancelled.is_set():
                process.terminate()
                raise CancelledError()
            text = line.strip()
            if not text:
                continue
            if text.startswith("PROGRESS_END"):
                _emit_log(text, False)
                if duration_seconds:
                    try:
                        end_value = float(text.split(" ", 1)[1])
                    except (IndexError, ValueError):
                        continue
                    if end_value > max_end_seconds:
                        max_end_seconds = end_value
                        percent = min(99, int((max_end_seconds / duration_seconds) * 100))
                        self._emit_progress(percent, "Transcribing")
                now = time.monotonic()
                if now - last_progress_log >= 2.0:
                    _emit_log("Transcribing progress update received.", True)
                    last_progress_log = now
                continue

            _emit_log(text, True)
            if text.startswith("MODE"):
                continue
            if text.startswith("READY"):
                self._emit_progress(0, "Transcribing")
                continue
            if text.startswith("DONE"):
                saw_done = True
                self._emit_progress(100, "Transcribing")

        return_code = process.wait()
        stderr_thread.join(timeout=1)
        self._process = None

        if return_code != 0 or not saw_done:
            tail_text = "\n".join(stderr_tail)
            raise RuntimeError("Transcription failed. Last output:\n" + tail_text)

    def _emit_progress(self, percent: float, phase_label: str) -> None:
        percent_int = int(round(percent))
        percent_int = max(0, min(percent_int, 100))
        if phase_label != self._progress_phase:
            self._progress_phase = phase_label
            self._progress_value = 0
            self._progress_label = ""
        if percent_int < self._progress_value:
            percent_int = self._progress_value
        status = f"{phase_label} ({percent_int}%)"
        if percent_int != self._progress_value or status != self._progress_label:
            self._progress_value = percent_int
            self._progress_label = status
            self.signals.progress.emit(percent_int, status)

    def _probe_duration(self, path: Path) -> Optional[float]:
        try:
            return get_media_duration(path)
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit(f"FFprobe failed: {exc}", True)
            return None
