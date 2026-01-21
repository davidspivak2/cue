from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from PySide6 import QtCore

from .config import DEFAULT_HIGHLIGHT_COLOR, DEFAULT_HIGHLIGHT_OPACITY
from .ffmpeg_utils import ensure_ffmpeg_available, get_ffprobe_json, get_subprocess_kwargs
from .graphics_overlay_export import (
    GRAPHICS_OVERLAY_PIPELINE,
    OverlaySegment,
    build_static_overlay_segments,
    build_word_highlight_overlay_segments,
    render_overlay_frame,
    resolve_video_stream_info,
)
from .graphics_preview_renderer import (
    LAYOUT_CACHE_MAX_ENTRIES,
    LRUCache,
    PATH_CACHE_MAX_ENTRIES,
    RenderContext,
)
from .paths import get_preview_clips_dir
from .srt_utils import SrtCue, parse_srt_file
from .subtitle_style import SubtitleStyle, to_preview_params
from .word_timing_schema import WordTimingValidationError, load_word_timings_json, word_timings_path_for_srt


@dataclass(frozen=True)
class PreviewClipSettings:
    video_path: Path
    srt_path: Path
    start_seconds: float
    duration_seconds: float
    subtitle_mode: str
    style: SubtitleStyle
    highlight_color: Optional[str] = None
    highlight_opacity: Optional[float] = None
    scale_width: int = 1280
    crf: int = 23
    preset: str = "veryfast"
    audio_bitrate: str = "128k"


@dataclass(frozen=True)
class PreviewClipPlan:
    command: list[str]
    pipeline: str
    filter_string: str
    width: int
    height: int
    fps: float


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
        self.signals.log.emit(
            "Preview clip timing: "
            f"start={self._settings.start_seconds:.3f}s "
            f"duration={self._settings.duration_seconds:.3f}s "
            f"output={self._output_path}"
        )

        stream_info = resolve_video_stream_info(self._settings.video_path)
        plan = build_preview_clip_plan(
            ffmpeg_path=ffmpeg_path,
            settings=self._settings,
            output_path=self._output_path,
            width=stream_info.width,
            height=stream_info.height,
            fps=stream_info.fps,
        )
        self.signals.log.emit(f"Preview subtitle_mode={self._settings.subtitle_mode}")
        self.signals.log.emit(f"Preview pipeline={plan.pipeline}")
        self.signals.log.emit(f"Preview filter={plan.filter_string}")
        self.signals.log.emit(
            f"Overlay stream: {plan.width}x{plan.height} @{plan.fps:.3f}fps"
        )
        command_text = subprocess.list2cmdline(plan.command)
        self.signals.log.emit(
            "Preview clip ffmpeg: "
            f"{command_text}"
        )

        cues = parse_srt_file(self._settings.srt_path)
        clip_end = self._settings.start_seconds + self._settings.duration_seconds
        segments = self._build_overlay_segments(cues=cues, clip_end=clip_end)
        clip_segments = _slice_overlay_segments(
            segments,
            start_seconds=self._settings.start_seconds,
            end_seconds=clip_end,
        )
        frame_segments, total_frames = _build_overlay_frame_segments(
            clip_segments,
            self._settings.duration_seconds,
            plan.fps,
        )
        self.signals.log.emit(
            f"Overlay frames: total={total_frames} segments={len(frame_segments)}"
        )

        render_cache: dict[tuple[object, ...], bytes] = {}
        layout_cache = LRUCache(max_entries=LAYOUT_CACHE_MAX_ENTRIES)
        path_cache = LRUCache(max_entries=PATH_CACHE_MAX_ENTRIES)
        render_context = RenderContext(
            layout_cache=layout_cache,
            path_cache=path_cache,
            perf_stats=None,
        )
        resolved_highlight_color = self._settings.highlight_color or DEFAULT_HIGHLIGHT_COLOR
        resolved_highlight_opacity = (
            self._settings.highlight_opacity
            if self._settings.highlight_opacity is not None
            else DEFAULT_HIGHLIGHT_OPACITY
        )

        def make_frame_generator() -> Iterable[bytes]:
            last_state: Optional[tuple[object, ...]] = None
            last_frame: Optional[bytes] = None
            for text, highlight_index, frame_count in frame_segments:
                state = (
                    text.strip(),
                    highlight_index,
                    plan.width,
                    plan.height,
                    self._settings.style,
                    self._settings.subtitle_mode,
                    resolved_highlight_color,
                    resolved_highlight_opacity,
                )
                if state != last_state:
                    if state in render_cache:
                        last_frame = render_cache[state]
                    else:
                        frame_bytes, _ = render_overlay_frame(
                            width=plan.width,
                            height=plan.height,
                            subtitle_text=text,
                            style=self._settings.style,
                            subtitle_mode=self._settings.subtitle_mode,
                            highlight_color=resolved_highlight_color,
                            highlight_opacity=resolved_highlight_opacity,
                            highlight_word_index=highlight_index,
                            render_context=render_context,
                        )
                        render_cache[state] = frame_bytes
                        last_frame = frame_bytes
                    last_state = state
                if last_frame is None:
                    continue
                for _ in range(frame_count):
                    yield last_frame

        success, message = _run_ffmpeg_streaming(plan.command, make_frame_generator())
        if success and self._output_path.exists() and self._output_path.stat().st_size > 0:
            self.signals.finished.emit(True, str(self._output_path), "", self._request_id)
            return

        if self._output_path.exists():
            try:
                self._output_path.unlink()
            except OSError:
                pass
        summary = message or "Preview clip generation failed."
        self.signals.finished.emit(False, "", summary, self._request_id)

    def _build_overlay_segments(self, *, cues: list[SrtCue], clip_end: float) -> list[OverlaySegment]:
        if self._settings.subtitle_mode != "word_highlight":
            return build_static_overlay_segments(cues, clip_end)
        word_timings_path = word_timings_path_for_srt(self._settings.srt_path)
        if not word_timings_path.exists():
            self.signals.log.emit(
                "Overlay word timings missing; rendering static overlay text.",
            )
            return build_static_overlay_segments(cues, clip_end)
        try:
            doc = load_word_timings_json(word_timings_path)
        except (WordTimingValidationError, OSError) as exc:
            self.signals.log.emit(
                f"Overlay word timings failed to load ({exc}); using static overlay text.",
            )
            return build_static_overlay_segments(cues, clip_end)
        return build_word_highlight_overlay_segments(cues, doc, clip_end)


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
        subtitle_mode: str,
        style: SubtitleStyle,
        highlight_color: Optional[str] = None,
        highlight_opacity: Optional[float] = None,
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
            subtitle_mode=subtitle_mode,
            style=style,
            highlight_color=highlight_color,
            highlight_opacity=highlight_opacity,
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
        word_timings_path = word_timings_path_for_srt(settings.srt_path)
        word_timings_stat = self._stat_payload(word_timings_path)
        payload = {
            "version": 2,
            "video": self._stat_payload(settings.video_path),
            "srt": self._stat_payload(settings.srt_path),
            "word_timings": word_timings_stat,
            "start_seconds": round(settings.start_seconds, 3),
            "duration_seconds": round(settings.duration_seconds, 3),
            "subtitle_mode": settings.subtitle_mode,
            "style": to_preview_params(settings.style),
            "highlight_color": settings.highlight_color,
            "highlight_opacity": settings.highlight_opacity,
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


def build_preview_clip_plan(
    *,
    ffmpeg_path: Path,
    settings: PreviewClipSettings,
    output_path: Path,
    width: int,
    height: int,
    fps: float,
) -> PreviewClipPlan:
    filter_string = (
        "[0:v][1:v]overlay=0:0:format=auto,"
        f"scale='min({settings.scale_width},iw)':-2:force_original_aspect_ratio=decrease"
        "[v]"
    )
    base_command = [
        str(ffmpeg_path),
        "-y",
        "-hide_banner",
        "-ss",
        f"{settings.start_seconds:.3f}",
        "-t",
        f"{settings.duration_seconds:.3f}",
        "-i",
        str(settings.video_path),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgba",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.3f}",
        "-i",
        "pipe:0",
        "-filter_complex",
        filter_string,
        "-map",
        "[v]",
        "-map",
        "0:a?",
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
        command=base_command,
        pipeline=GRAPHICS_OVERLAY_PIPELINE,
        filter_string=filter_string,
        width=width,
        height=height,
        fps=fps,
    )


def _slice_overlay_segments(
    segments: Iterable[OverlaySegment],
    *,
    start_seconds: float,
    end_seconds: float,
) -> list[OverlaySegment]:
    sliced: list[OverlaySegment] = []
    for segment in segments:
        if segment.end_seconds <= start_seconds:
            continue
        if segment.start_seconds >= end_seconds:
            break
        start = max(segment.start_seconds, start_seconds)
        end = min(segment.end_seconds, end_seconds)
        if end <= start:
            continue
        sliced.append(
            OverlaySegment(
                start_seconds=start - start_seconds,
                end_seconds=end - start_seconds,
                text=segment.text,
                highlight_word_index=segment.highlight_word_index,
            )
        )
    return sliced


def _build_overlay_frame_segments(
    segments: list[OverlaySegment],
    duration_seconds: float,
    fps: float,
) -> tuple[list[tuple[str, Optional[int], int]], int]:
    total_frames = max(0, int(round(duration_seconds * fps)))
    frame_segments: list[tuple[str, Optional[int], int]] = []
    frame_cursor = 0
    for segment in segments:
        if segment.start_seconds >= duration_seconds:
            break
        start_frame = int(round(segment.start_seconds * fps))
        end_frame = int(round(min(segment.end_seconds, duration_seconds) * fps))
        start_frame = max(frame_cursor, start_frame)
        if start_frame > frame_cursor:
            frame_segments.append(("", None, start_frame - frame_cursor))
        if end_frame > start_frame:
            frame_segments.append((segment.text, segment.highlight_word_index, end_frame - start_frame))
        frame_cursor = max(frame_cursor, end_frame)
    if total_frames > frame_cursor:
        frame_segments.append(("", None, total_frames - frame_cursor))
    return frame_segments, total_frames


def _run_ffmpeg_streaming(command: list[str], frame_iterator: Iterable[bytes]) -> tuple[bool, str]:
    stderr_tail: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **get_subprocess_kwargs(),
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"ffmpeg failed to start: {exc}"

    def _read_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            stderr_tail.append(line.rstrip())

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    assert process.stdin is not None
    try:
        for frame in frame_iterator:
            process.stdin.buffer.write(frame)
        process.stdin.close()
    except Exception as exc:  # noqa: BLE001
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        return False, f"Overlay stream failed: {exc}"

    return_code = process.wait()
    stderr_thread.join(timeout=1)
    if return_code != 0:
        tail_text = "\n".join(stderr_tail[-50:])
        summary = f"ffmpeg exited with code {return_code}"
        if tail_text:
            summary = f"{summary}: {tail_text}"
        return False, summary
    return True, ""


def get_media_duration(path: Path) -> Optional[float]:
    ffprobe_json = get_ffprobe_json(path)
    if not ffprobe_json:
        return None
    fmt = ffprobe_json.get("format")
    if not isinstance(fmt, dict):
        return None
    value = fmt.get("duration")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
