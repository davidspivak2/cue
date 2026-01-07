from __future__ import annotations

import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6 import QtCore
from faster_whisper import WhisperModel

from .ffmpeg_utils import (
    ensure_ffmpeg_available,
    escape_subtitles_filter_path,
    format_filter_style,
)
from .srt_utils import SrtSegment, segments_to_srt


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
    log = QtCore.Signal(str)
    finished = QtCore.Signal(bool, str, dict)
    started = QtCore.Signal(str)


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
                self.signals.finished.emit(True, "SRT generated successfully.", result)
            elif self.task_type == TaskType.BURN_IN:
                self.signals.started.emit("Hardcoding subtitles")
                result = self._run_burn_in()
                self.signals.finished.emit(True, "Subtitles hardcoded successfully.", result)
            else:
                raise ValueError(f"Unknown task type: {self.task_type}")
        except CancelledError:
            self.signals.finished.emit(False, "Operation cancelled.", {})
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit("Exception occurred:")
            self.signals.log.emit(str(exc))
            self.signals.finished.emit(False, str(exc), {})

    def _run_generate_srt(self) -> dict:
        settings = self.transcription_settings
        if settings is None:
            raise ValueError("Missing transcription settings")

        output_dir = self.video_path.parent
        audio_path = output_dir / f"{self.video_path.stem}_audio_for_whisper.wav"
        srt_path = output_dir / f"{self.video_path.stem}.srt"

        self.signals.log.emit("Extracting audio via FFmpeg...")
        self._extract_audio(audio_path, settings.apply_audio_filter)

        if self._cancelled.is_set():
            raise CancelledError()

        self.signals.log.emit("Loading Whisper model (large-v3). First run may download files...")
        try:
            model, device_used, fallback_error = self._load_model()
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit(str(exc))
            raise RuntimeError("Transcription failed. See logs for details.") from exc

        self.signals.log.emit(f"Whisper running on: {device_used}")
        if fallback_error:
            self.signals.log.emit(f"CUDA fallback error: {fallback_error}")

        if self._cancelled.is_set():
            raise CancelledError()

        self.signals.log.emit("Transcribing audio...")
        try:
            segments_iter, info = model.transcribe(
                str(audio_path),
                language="he",
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400},
                word_timestamps=True,
            )
            self.signals.log.emit(
                f"Detected language: {info.language} (prob={info.language_probability:.2f})"
            )
        except Exception as exc:  # noqa: BLE001
            self.signals.log.emit(str(exc))
            raise RuntimeError("Transcription failed. See logs for details.") from exc

        segments = []
        index = 1
        for segment in segments_iter:
            if self._cancelled.is_set():
                raise CancelledError()
            segments.append(SrtSegment(index=index, start=segment.start, end=segment.end, text=segment.text))
            index += 1

        srt_content = segments_to_srt(segments)
        srt_path.write_text(srt_content, encoding="utf-8")
        self.signals.log.emit(f"Saved SRT: {srt_path}")

        return {
            "audio_path": str(audio_path),
            "srt_path": str(srt_path),
            "device_used": device_used,
        }

    def _extract_audio(self, audio_path: Path, apply_filter: bool) -> None:
        ffmpeg_path, _ = ensure_ffmpeg_available()
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
        command.append(str(audio_path))
        self._run_ffmpeg(command)

    def _run_burn_in(self) -> dict:
        settings = self.burnin_settings
        if settings is None:
            raise ValueError("Missing burn-in settings")

        output_dir = self.video_path.parent
        srt_path = self.srt_path or output_dir / f"{self.video_path.stem}.srt"
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT not found: {srt_path}")

        output_path = output_dir / f"{self.video_path.stem}_subtitled.mp4"
        ffmpeg_path, _ = ensure_ffmpeg_available()

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

        self.signals.log.emit("Burning subtitles with audio copy...")
        copy_command = base_command + ["-c:a", "copy", str(output_path)]
        try:
            self._run_ffmpeg(copy_command)
            return {"output_path": str(output_path)}
        except RuntimeError as exc:
            self.signals.log.emit("Audio copy failed, retrying with AAC...")
            self.signals.log.emit(str(exc))

        aac_command = base_command + ["-c:a", "aac", "-b:a", "192k", str(output_path)]
        self._run_ffmpeg(aac_command)
        return {"output_path": str(output_path)}

    def _run_ffmpeg(self, command: list[str]) -> None:
        if self._cancelled.is_set():
            raise CancelledError()

        self.signals.log.emit(f"FFmpeg command: {subprocess.list2cmdline(command)}")
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
            self.signals.log.emit(line.rstrip())
            if self._cancelled.is_set():
                process.terminate()
                raise CancelledError()

        return_code = process.wait()
        self._process = None

        if return_code != 0:
            tail_text = "\n".join(stderr_tail)
            raise RuntimeError("FFmpeg failed. Last output:\n" + tail_text)

    def _load_model(self) -> tuple[WhisperModel, str, Optional[str]]:
        fallback_error: Optional[str] = None
        try:
            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            return model, "GPU (cuda float16)", fallback_error
        except Exception as exc:  # noqa: BLE001
            fallback_error = str(exc)
            self.signals.log.emit("CUDA load failed, falling back to CPU...")
            model = WhisperModel("large-v3", device="cpu", compute_type="int8")
            return model, "CPU (int8)", fallback_error
