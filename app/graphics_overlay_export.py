from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .ffmpeg_utils import get_ffprobe_json
from .srt_utils import SrtCue
from .subtitle_style import SubtitleStyle
from .word_timing_schema import CueWordTimings, WordTimingDocument

GRAPHICS_OVERLAY_PIPELINE = "graphics_overlay_stream"


@dataclass(frozen=True)
class VideoStreamInfo:
    width: int
    height: int
    fps: float


@dataclass(frozen=True)
class GraphicsOverlayPlan:
    base_command: list[str]
    pipeline: str
    filter_string: str
    width: int
    height: int
    fps: float


@dataclass(frozen=True)
class OverlaySegment:
    start_seconds: float
    end_seconds: float
    text: str
    highlight_word_index: Optional[int]


def _parse_frame_rate(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    if "/" in value:
        parts = value.split("/")
        if len(parts) != 2:
            return None
        try:
            numerator = float(parts[0])
            denominator = float(parts[1])
        except ValueError:
            return None
        if denominator == 0:
            return None
        return numerator / denominator
    try:
        return float(value)
    except ValueError:
        return None


def resolve_video_stream_info(video_path: Path) -> VideoStreamInfo:
    ffprobe_json = get_ffprobe_json(video_path)
    if not ffprobe_json:
        raise ValueError("ffprobe data unavailable for overlay export")
    streams = ffprobe_json.get("streams", [])
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    if not video_stream:
        raise ValueError("No video stream found for overlay export")
    width = video_stream.get("width")
    height = video_stream.get("height")
    if not width or not height:
        raise ValueError("Video size unavailable for overlay export")
    frame_rate = _parse_frame_rate(video_stream.get("avg_frame_rate"))
    if not frame_rate:
        frame_rate = _parse_frame_rate(video_stream.get("r_frame_rate"))
    if not frame_rate or frame_rate <= 0:
        frame_rate = 30.0
    return VideoStreamInfo(width=int(width), height=int(height), fps=float(frame_rate))


def build_graphics_overlay_plan(
    *,
    ffmpeg_path: Path,
    video_path: Path,
    output_path: Path,
    width: int,
    height: int,
    fps: float,
) -> GraphicsOverlayPlan:
    filter_string = "[0:v][1:v]overlay=0:0:format=auto[v]"
    base_command = [
        str(ffmpeg_path),
        "-y",
        "-hide_banner",
        "-i",
        str(video_path),
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
        "-progress",
        "pipe:1",
        "-nostats",
        "-filter_complex",
        filter_string,
        "-map",
        "[v]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
    ]
    return GraphicsOverlayPlan(
        base_command=base_command,
        pipeline=GRAPHICS_OVERLAY_PIPELINE,
        filter_string=filter_string,
        width=width,
        height=height,
        fps=fps,
    )


def build_static_overlay_segments(
    cues: Iterable[SrtCue], duration_seconds: float
) -> list[OverlaySegment]:
    segments: list[OverlaySegment] = []
    last_end = 0.0
    for cue in sorted(cues, key=lambda item: item.start_seconds):
        if cue.start_seconds >= duration_seconds:
            break
        start = max(0.0, cue.start_seconds)
        end = min(cue.end_seconds, duration_seconds)
        if end <= start:
            continue
        if start > last_end:
            segments.append(
                OverlaySegment(
                    start_seconds=last_end,
                    end_seconds=start,
                    text="",
                    highlight_word_index=None,
                )
            )
        segments.append(
            OverlaySegment(
                start_seconds=start,
                end_seconds=end,
                text=cue.text,
                highlight_word_index=None,
            )
        )
        last_end = max(last_end, end)
    if last_end < duration_seconds:
        segments.append(
            OverlaySegment(
                start_seconds=last_end,
                end_seconds=duration_seconds,
                text="",
                highlight_word_index=None,
            )
        )
    return segments


def _coerce_word_span(word: object) -> Optional[tuple[float, float]]:
    if isinstance(word, dict):
        start = word.get("start")
        end = word.get("end")
    else:
        start = getattr(word, "start", None)
        end = getattr(word, "end", None)
    if start is None or end is None:
        return None
    try:
        return float(start), float(end)
    except (TypeError, ValueError):
        return None


def _index_word_timings(doc: WordTimingDocument) -> dict[int, CueWordTimings]:
    mapping: dict[int, CueWordTimings] = {}
    for cue in doc.cues:
        mapping[int(cue.cue_index)] = cue
    return mapping


def build_word_highlight_overlay_segments(
    cues: Iterable[SrtCue],
    word_timings_doc: WordTimingDocument,
    duration_seconds: float,
) -> list[OverlaySegment]:
    cue_timings = _index_word_timings(word_timings_doc)
    segments: list[OverlaySegment] = []
    last_end = 0.0
    for cue_index, cue in enumerate(sorted(cues, key=lambda item: item.start_seconds), start=1):
        if cue.start_seconds >= duration_seconds:
            break
        timing = cue_timings.get(cue_index)
        start = max(0.0, cue.start_seconds)
        end = min(cue.end_seconds, duration_seconds)
        if end <= start:
            continue
        if start > last_end:
            segments.append(
                OverlaySegment(
                    start_seconds=last_end,
                    end_seconds=start,
                    text="",
                    highlight_word_index=None,
                )
            )
        if not timing or not timing.words:
            segments.append(
                OverlaySegment(
                    start_seconds=start,
                    end_seconds=end,
                    text=cue.text,
                    highlight_word_index=None,
                )
            )
            last_end = max(last_end, end)
            continue
        word_entries: list[tuple[float, float, int]] = []
        for word_index, word in enumerate(timing.words):
            span = _coerce_word_span(word)
            if span is None:
                continue
            word_start, word_end = span
            if word_start < cue.start_seconds:
                word_start = cue.start_seconds
            if word_end > cue.end_seconds:
                word_end = cue.end_seconds
            if word_end <= word_start:
                continue
            word_entries.append((word_start, word_end, word_index))
        if not word_entries:
            segments.append(
                OverlaySegment(
                    start_seconds=start,
                    end_seconds=end,
                    text=cue.text,
                    highlight_word_index=None,
                )
            )
            last_end = max(last_end, end)
            continue
        first_start = word_entries[0][0]
        if start < first_start:
            segments.append(
                OverlaySegment(
                    start_seconds=start,
                    end_seconds=first_start,
                    text=cue.text,
                    highlight_word_index=None,
                )
            )
        for idx, (word_start, word_end, word_index) in enumerate(word_entries):
            next_start = word_entries[idx + 1][0] if idx + 1 < len(word_entries) else end
            if next_start <= word_start:
                continue
            segments.append(
                OverlaySegment(
                    start_seconds=word_start,
                    end_seconds=next_start,
                    text=cue.text,
                    highlight_word_index=word_index,
                )
            )
        last_end = max(last_end, end)
    if last_end < duration_seconds:
        segments.append(
            OverlaySegment(
                start_seconds=last_end,
                end_seconds=duration_seconds,
                text="",
                highlight_word_index=None,
            )
        )
    return segments


def render_overlay_frame(
    *,
    width: int,
    height: int,
    subtitle_text: str,
    style: SubtitleStyle,
    subtitle_mode: str,
    highlight_color: Optional[str],
    highlight_opacity: Optional[float],
    highlight_word_index: Optional[int] = None,
) -> tuple[bytes, Optional[int]]:
    from PySide6 import QtCore, QtGui
    from .graphics_preview_renderer import render_graphics_preview

    frame = QtGui.QImage(width, height, QtGui.QImage.Format_RGBA8888)
    frame.fill(QtCore.Qt.transparent)
    result = render_graphics_preview(
        frame,
        subtitle_text=subtitle_text,
        style=style,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
        highlight_opacity=highlight_opacity,
        highlight_word_index=highlight_word_index,
    )
    image = result.image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    size = image.sizeInBytes()
    buffer = image.bits()
    if hasattr(buffer, "setsize"):
        buffer.setsize(size)
        data = bytes(buffer)
    else:
        data = buffer.tobytes()
        if len(data) != size:
            if len(data) < size:
                raise RuntimeError(
                    f"Unexpected QImage bits size: got {len(data)} expected {size}"
                )
            data = data[:size]
    return data, result.highlight_word_index
