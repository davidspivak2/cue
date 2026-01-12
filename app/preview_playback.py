from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PySide6 import QtCore

from .ffmpeg_utils import (
    build_subtitles_filter,
    ensure_ffmpeg_available,
    get_media_duration,
    get_subprocess_kwargs,
)
from .paths import get_preview_clips_dir


@dataclass(frozen=True)
class PreviewClipSettings:
    video_path: Path
    srt_path: Path
    start_seconds: float
    duration_seconds: float
    force_style: str
    scale_width: int = 1280
    crf: int = 23
    preset: str = "veryfast"
    audio_bitrate: str = "128k"


class PreviewClipSignals(QtCore.QObject):
    log = QtCore.Signal(str)
    finished = QtCore.Signal(bool, str, str, int)


class PreviewClipWorker(QtCore.QObject):
    def __init__(self, settings: PreviewClipSettings, output_path: Path, request_id: int) -> None:
        super().__init__()
        self.signals = PreviewClipSignals()
        self._settings = settings
        self._output_path = output_path
        self._request_id = request_id

    @QtCore.Slot()
    def run(self) -> None:
        try:
            ffmpeg_path, _, _ = ensure_ffmpeg_available()
        except FileNotFoundError as exc:
            self.signals.finished.emit(False, "", str(exc), self._request_id)
            return

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        subtitles_filter = build_subtitles_filter(
            self._settings.srt_path,
            force_style=self._settings.force_style,
        )
        filter_chain = (
            f"{subtitles_filter},scale='min({self._settings.scale_width},iw)':-2:"
            "force_original_aspect_ratio=decrease"
        )
        command = [
            str(ffmpeg_path),
            "-y",
            "-hide_banner",
            "-ss",
            f"{self._settings.start_seconds:.3f}",
            "-i",
            str(self._settings.video_path),
            "-t",
            f"{self._settings.duration_seconds:.3f}",
            "-vf",
            filter_chain,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            self._settings.preset,
            "-crf",
            str(self._settings.crf),
            "-c:a",
            "aac",
            "-b:a",
            self._settings.audio_bitrate,
            "-movflags",
            "+faststart",
            "-shortest",
            str(self._output_path),
        ]
        self.signals.log.emit(
            "Preview clip ffmpeg: "
            f"-vf {filter_chain} "
            f"force_style={self._settings.force_style}"
        )
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                **get_subprocess_kwargs(),
            )
        except Exception as exc:  # noqa: BLE001
            self.signals.finished.emit(False, "", f"ffmpeg failed to start: {exc}", self._request_id)
            return

        if result.returncode == 0 and self._output_path.exists() and self._output_path.stat().st_size > 0:
            self.signals.finished.emit(True, str(self._output_path), "", self._request_id)
            return

        if self._output_path.exists():
            try:
                self._output_path.unlink()
            except OSError:
                pass
        stderr = (result.stderr or "").strip()
        summary = f"ffmpeg exited with code {result.returncode}"
        if stderr:
            summary = f"{summary}: {stderr[:240]}"
        self.signals.finished.emit(False, "", summary, self._request_id)


class PreviewPlaybackController(QtCore.QObject):
    clip_ready = QtCore.Signal(str)
    clip_failed = QtCore.Signal(str)
    clip_loading = QtCore.Signal(bool)

    def __init__(self, log: Callable[[str], None], parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._log = log
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[PreviewClipWorker] = None
        self._request_id = 0

    def invalidate_current_clip(self) -> None:
        self._request_id += 1
        self.clip_loading.emit(False)

    def request_clip(
        self,
        *,
        video_path: Path,
        srt_path: Path,
        anchor_seconds: float,
        force_style: str,
        scale_width: int = 1280,
    ) -> None:
        if self._thread is not None:
            return
        try:
            duration = get_media_duration(video_path)
        except FileNotFoundError:
            duration = None
        start_seconds = max(0.0, anchor_seconds - 1.0)
        clip_duration = 8.0
        if duration:
            clip_duration = max(0.0, min(clip_duration, duration - start_seconds))
        if clip_duration <= 0.05:
            self.clip_failed.emit("Preview playback unavailable.")
            return

        settings = PreviewClipSettings(
            video_path=video_path,
            srt_path=srt_path,
            start_seconds=start_seconds,
            duration_seconds=clip_duration,
            force_style=force_style,
            scale_width=scale_width,
        )
        cache_key = self._build_cache_key(settings)
        output_path = get_preview_clips_dir() / f"{cache_key}.mp4"
        if output_path.exists() and output_path.stat().st_size > 0:
            self._log(f"Preview clip cache hit: {output_path}")
            self.clip_ready.emit(str(output_path))
            return
        self._log(f"Preview clip cache miss: {output_path}")
        self._log(f"Preview clip output: {output_path}")

        self._request_id += 1
        request_id = self._request_id
        self.clip_loading.emit(True)
        self._thread = QtCore.QThread()
        self._worker = PreviewClipWorker(settings, output_path, request_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.signals.log.connect(self._log)
        self._worker.signals.finished.connect(self._on_worker_finished)
        self._thread.start()

    def _on_worker_finished(self, success: bool, path: str, message: str, request_id: int) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None
        if request_id != self._request_id:
            return
        self.clip_loading.emit(False)
        if success and path:
            self.clip_ready.emit(path)
        else:
            if message:
                self._log(f"Preview clip generation failed: {message}")
            self.clip_failed.emit("Preview playback unavailable.")

    def _build_cache_key(self, settings: PreviewClipSettings) -> str:
        payload = {
            "version": 1,
            "video": self._stat_payload(settings.video_path),
            "srt": self._stat_payload(settings.srt_path),
            "start_seconds": round(settings.start_seconds, 3),
            "duration_seconds": round(settings.duration_seconds, 3),
            "force_style": settings.force_style,
            "scale_width": settings.scale_width,
            "crf": settings.crf,
            "preset": settings.preset,
            "audio_bitrate": settings.audio_bitrate,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _stat_payload(path: Path) -> dict[str, object]:
        try:
            stat = path.stat()
            size = stat.st_size
            mtime = stat.st_mtime
        except FileNotFoundError:
            size = 0
            mtime = 0.0
        return {
            "path": str(path.resolve()),
            "size": size,
            "mtime": mtime,
        }
