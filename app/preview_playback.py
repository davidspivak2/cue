from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Callable, Optional

from PySide6 import QtCore

from .ass_render import build_ass_document
from .ffmpeg_utils import (
    build_ass_filter,
    build_subtitles_filter,
    ensure_ffmpeg_available,
    get_ffprobe_json,
    get_media_duration,
    get_subprocess_kwargs,
)
from .paths import get_preview_clips_dir
from .srt_utils import parse_srt_file
from .subtitle_style import SubtitleStyle, to_preview_params


@dataclass(frozen=True)
class PreviewClipSettings:
    video_path: Path
    srt_path: Path
    start_seconds: float
    duration_seconds: float
    force_style: str
    subtitle_mode: str
    style: SubtitleStyle
    scale_width: int = 1280
    crf: int = 23
    preset: str = "veryfast"
    audio_bitrate: str = "128k"


STATIC_SRT_PIPELINE = "static_srt"
WORD_HIGHLIGHT_ASS_PIPELINE = "word_highlight_ass"


@dataclass(frozen=True)
class PreviewClipPlan:
    command: list[str]
    pipeline: str
    subtitles_path: Path
    filter_string: str
    ass_path: Optional[Path] = None


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
        shifted_srt_path = self._output_path.with_suffix(".srt")
        shift_result = _shift_srt_file(
            self._settings.srt_path,
            shifted_srt_path,
            self._settings.start_seconds,
        )
        self.signals.log.emit(
            "Preview clip timing: "
            f"start={self._settings.start_seconds:.3f}s "
            f"duration={self._settings.duration_seconds:.3f}s "
            f"output={self._output_path}"
        )
        self.signals.log.emit(
            "Preview clip cues: "
            f"count={shift_result.cues_written} "
            f"first_start={shift_result.first_start} "
            f"first_end={shift_result.first_end}"
        )
        plan = build_preview_clip_plan(
            ffmpeg_path=ffmpeg_path,
            settings=self._settings,
            output_path=self._output_path,
            shifted_srt_path=shifted_srt_path,
        )
        self.signals.log.emit(f"Preview subtitle_mode={self._settings.subtitle_mode}")
        self.signals.log.emit(f"Preview pipeline={plan.pipeline}")
        self.signals.log.emit(f"Preview subtitles path={plan.subtitles_path}")
        self.signals.log.emit(f"Preview filter={plan.filter_string}")
        command = plan.command
        command_text = subprocess.list2cmdline(command)
        self.signals.log.emit(
            "Preview clip ffmpeg: "
            f"{command_text}"
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
        clip_start_seconds: Optional[float],
        clip_duration_seconds: Optional[float],
        force_style: str,
        subtitle_mode: str,
        style: SubtitleStyle,
        scale_width: int = 1280,
    ) -> None:
        if self._thread is not None:
            return
        try:
            duration = get_media_duration(video_path)
        except FileNotFoundError:
            duration = None
        start_seconds = (
            clip_start_seconds if clip_start_seconds is not None else max(0.0, anchor_seconds - 1.0)
        )
        clip_duration = clip_duration_seconds if clip_duration_seconds is not None else 15.0
        if duration:
            clip_duration = max(0.0, min(clip_duration, duration - start_seconds))
        if clip_duration <= 0.2:
            self.clip_failed.emit("Preview playback unavailable.")
            return

        settings = PreviewClipSettings(
            video_path=video_path,
            srt_path=srt_path,
            start_seconds=start_seconds,
            duration_seconds=clip_duration,
            force_style=force_style,
            subtitle_mode=subtitle_mode,
            style=style,
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
            "subtitle_mode": settings.subtitle_mode,
            "style": to_preview_params(settings.style),
            "scale_width": settings.scale_width,
            "crf": settings.crf,
            "preset": settings.preset,
            "audio_bitrate": settings.audio_bitrate,
            "shifted_subtitles": True,
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


def build_preview_clip_plan(
    *,
    ffmpeg_path: Path,
    settings: PreviewClipSettings,
    output_path: Path,
    shifted_srt_path: Path,
) -> PreviewClipPlan:
    if settings.subtitle_mode == "word_highlight":
        cues = parse_srt_file(shifted_srt_path)
        ass_text = build_ass_document(cues, style_config=settings.style)
        ass_path = output_path.with_suffix(".ass")
        ass_path.write_text(ass_text, encoding="utf-8")
        filter_string = build_ass_filter(ass_path)
        pipeline = WORD_HIGHLIGHT_ASS_PIPELINE
        subtitles_path = ass_path
    else:
        filter_string = build_subtitles_filter(
            shifted_srt_path,
            force_style=settings.force_style,
        )
        pipeline = STATIC_SRT_PIPELINE
        subtitles_path = shifted_srt_path
        ass_path = None

    video_chain = (
        f"trim=start={settings.start_seconds:.3f}:duration={settings.duration_seconds:.3f},"
        "setpts=PTS-STARTPTS,"
        f"{filter_string},"
        f"scale='min({settings.scale_width},iw)':-2:force_original_aspect_ratio=decrease"
    )
    if settings.subtitle_mode == "word_highlight":
        audio_filter_complex, audio_label = _build_audio_filter_complex(
            settings.start_seconds,
            settings.duration_seconds,
            settings.video_path,
        )
        command = [
            str(ffmpeg_path),
            "-y",
            "-hide_banner",
            "-i",
            str(settings.video_path),
            "-vf",
            video_chain,
        ]
        if audio_filter_complex and audio_label:
            command += [
                "-filter_complex",
                audio_filter_complex,
                "-map",
                "0:v:0",
                "-map",
                audio_label,
            ]
        else:
            command += ["-map", "0:v:0"]
    else:
        filter_complex, audio_label = _build_filter_complex(
            video_chain,
            settings.start_seconds,
            settings.duration_seconds,
            settings.video_path,
        )
        command = [
            str(ffmpeg_path),
            "-y",
            "-hide_banner",
            "-i",
            str(settings.video_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
        ]
        if audio_label:
            command += ["-map", audio_label]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        settings.preset,
        "-crf",
        str(settings.crf),
        "-c:a",
        "aac",
        "-b:a",
        settings.audio_bitrate,
        "-movflags",
        "+faststart",
        "-shortest",
        str(output_path),
    ]

    return PreviewClipPlan(
        command=command,
        pipeline=pipeline,
        subtitles_path=subtitles_path,
        filter_string=filter_string,
        ass_path=ass_path,
    )


@dataclass(frozen=True)
class ShiftedSrtResult:
    cues_written: int
    first_start: Optional[str]
    first_end: Optional[str]


_SRT_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)


def _shift_srt_file(source_path: Path, output_path: Path, offset_seconds: float) -> ShiftedSrtResult:
    text = source_path.read_text(encoding="utf-8", errors="replace")
    shifted_text, result = _shift_srt_text(text, offset_seconds)
    output_path.write_text(shifted_text, encoding="utf-8")
    return result


def _shift_srt_text(srt_text: str, offset_seconds: float) -> tuple[str, ShiftedSrtResult]:
    normalized = srt_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return "", ShiftedSrtResult(0, None, None)
    blocks = re.split(r"\n\s*\n", normalized)
    output_blocks: list[str] = []
    cues_written = 0
    first_start: Optional[str] = None
    first_end: Optional[str] = None
    for block in blocks:
        lines = block.split("\n")
        timestamp_index = None
        match = None
        for idx, line in enumerate(lines):
            match = _SRT_TIMESTAMP_RE.search(line)
            if match:
                timestamp_index = idx
                break
        if timestamp_index is None or not match:
            continue
        start_seconds = _parse_srt_timestamp(match.group("start"))
        end_seconds = _parse_srt_timestamp(match.group("end"))
        if start_seconds is None or end_seconds is None:
            continue
        new_start = max(0.0, start_seconds - offset_seconds)
        new_end = max(0.0, end_seconds - offset_seconds)
        if new_end <= 0:
            continue
        lines[timestamp_index] = (
            f"{_format_srt_timestamp(new_start)} --> {_format_srt_timestamp(new_end)}"
        )
        output_blocks.append("\n".join(lines))
        cues_written += 1
        if first_start is None:
            first_start = _format_srt_timestamp(new_start)
            first_end = _format_srt_timestamp(new_end)
    shifted = "\n\n".join(output_blocks)
    if shifted:
        shifted = shifted.strip() + "\n"
    return shifted, ShiftedSrtResult(cues_written, first_start, first_end)


def _parse_srt_timestamp(value: str) -> Optional[float]:
    parts = value.replace(",", ".").split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _format_srt_timestamp(seconds: float) -> str:
    delta = timedelta(seconds=max(seconds, 0))
    total_seconds = int(delta.total_seconds())
    millis = int(delta.microseconds / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _build_audio_filter_complex(
    start_seconds: float,
    duration_seconds: float,
    video_path: Path,
) -> tuple[str, Optional[str]]:
    has_audio = False
    ffprobe_json = get_ffprobe_json(video_path)
    if ffprobe_json:
        streams = ffprobe_json.get("streams", [])
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    audio_label = None
    if has_audio:
        audio_chain = (
            f"atrim=start={start_seconds:.3f}:duration={duration_seconds:.3f},"
            "asetpts=PTS-STARTPTS"
        )
        filter_complex = f"[0:a]{audio_chain}[a]"
        audio_label = "[a]"
        return filter_complex, audio_label
    return "", None


def _build_filter_complex(
    video_chain: str,
    start_seconds: float,
    duration_seconds: float,
    video_path: Path,
) -> tuple[str, Optional[str]]:
    has_audio = False
    ffprobe_json = get_ffprobe_json(video_path)
    if ffprobe_json:
        streams = ffprobe_json.get("streams", [])
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    audio_label = None
    if has_audio:
        audio_chain = (
            f"atrim=start={start_seconds:.3f}:duration={duration_seconds:.3f},"
            "asetpts=PTS-STARTPTS"
        )
        filter_complex = f"[0:v]{video_chain}[v];[0:a]{audio_chain}[a]"
        audio_label = "[a]"
    else:
        filter_complex = f"[0:v]{video_chain}[v]"
    return filter_complex, audio_label
