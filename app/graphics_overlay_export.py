from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ffmpeg_utils import get_ffprobe_json
from .subtitle_style import SubtitleStyle

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


def render_overlay_frame(
    *,
    width: int,
    height: int,
    subtitle_text: str,
    style: SubtitleStyle,
    subtitle_mode: str,
    highlight_color: Optional[str],
    highlight_opacity: Optional[float],
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
    )
    image = result.image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    buffer = image.bits()
    buffer.setsize(image.sizeInBytes())
    return bytes(buffer), result.highlight_word_index
