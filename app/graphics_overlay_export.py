from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Optional, TYPE_CHECKING

from .ffmpeg_utils import get_ffprobe_json
from .srt_utils import SrtCue
from .subtitle_style import SubtitleStyle, resolve_outline_color, resolve_style_for_frame
from .word_timing_schema import CueWordTimings, WordTimingDocument

if TYPE_CHECKING:
    from .graphics_preview_renderer import RenderContext

GRAPHICS_OVERLAY_PIPELINE = "graphics_overlay_stream"


@dataclass(frozen=True)
class VideoStreamInfo:
    width: int
    height: int
    fps: float
    fps_arg: str
    video_bitrate: Optional[int] = None
    frame_count: Optional[int] = None


@dataclass(frozen=True)
class GraphicsOverlayPlan:
    base_command: list[str]
    pipeline: str
    filter_string: str
    width: int
    height: int
    fps: float
    fps_arg: str
    phase1_command: Optional[list[str]] = None
    phase2_command: Optional[list[str]] = None
    phase2_aac_command: Optional[list[str]] = None
    two_pass_pass1_command: Optional[list[str]] = None
    two_pass_pass2_command: Optional[list[str]] = None
    two_pass_pass2_aac_command: Optional[list[str]] = None
    phase2_pass1_command: Optional[list[str]] = None
    phase2_pass2_command: Optional[list[str]] = None
    phase2_pass2_aac_command: Optional[list[str]] = None


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
    avg_frame_rate_raw = video_stream.get("avg_frame_rate")
    r_frame_rate_raw = video_stream.get("r_frame_rate")
    frame_rate = _parse_frame_rate(avg_frame_rate_raw)
    frame_rate_arg = avg_frame_rate_raw if frame_rate else None
    if not frame_rate:
        frame_rate = _parse_frame_rate(r_frame_rate_raw)
        if frame_rate:
            frame_rate_arg = r_frame_rate_raw
    if not frame_rate or frame_rate <= 0:
        frame_rate = 30.0
        frame_rate_arg = "30"
    raw_nb_frames = video_stream.get("nb_frames")
    frame_count: Optional[int] = None
    if raw_nb_frames not in (None, "N/A"):
        try:
            parsed_frame_count = int(raw_nb_frames)
        except (TypeError, ValueError):
            parsed_frame_count = 0
        if parsed_frame_count > 0:
            frame_count = parsed_frame_count
    raw_bitrate = video_stream.get("bit_rate")
    video_bitrate: Optional[int] = None
    if raw_bitrate is not None:
        try:
            video_bitrate = int(raw_bitrate)
        except (TypeError, ValueError):
            pass
    if video_bitrate is None or video_bitrate <= 0:
        format_br = ffprobe_json.get("format", {}).get("bit_rate")
        if format_br is not None:
            try:
                total = int(format_br)
                if total > 256000:
                    video_bitrate = total - 256000
            except (TypeError, ValueError):
                pass
    return VideoStreamInfo(
        width=int(width),
        height=int(height),
        fps=float(frame_rate),
        fps_arg=str(frame_rate_arg),
        video_bitrate=video_bitrate,
        frame_count=frame_count,
    )


def build_graphics_overlay_plan(
    *,
    ffmpeg_path: Path,
    video_path: Path,
    output_path: Path,
    stats_dir: Optional[Path] = None,
    width: int,
    height: int,
    fps: float,
    fps_arg: str,
    video_bitrate: Optional[int] = None,
    raw_path: Optional[Path] = None,
) -> GraphicsOverlayPlan:
    filter_string = "[0:v][1:v]overlay=0:0:format=auto[v]"
    use_two_step = False
    if use_two_step:
        filter_phase1 = "[0:v][1:v]overlay=0:0:format=auto[v];[v]format=yuv420p[vout]"
        phase1_parts = [
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
            fps_arg,
            "-i",
            "pipe:0",
            "-progress",
            "pipe:2",
            "-nostats",
            "-filter_complex",
            filter_phase1,
            "-map",
            "[vout]",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "yuv420p",
            "pipe:1",
        ]
        br = video_bitrate
        bufsize_phase2 = 4 * br
        phase2_common = [
            str(ffmpeg_path),
            "-y",
            "-hide_banner",
            "-progress",
            "pipe:1",
            "-nostats",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "yuv420p",
            "-s",
            f"{width}x{height}",
            "-r",
            fps_arg,
            "-i",
            "pipe:0",
            "-i",
            str(video_path),
            "-map",
            "0:v",
            "-map",
            "1:a?",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-minrate",
            str(br),
            "-b:v",
            str(br),
            "-maxrate",
            str(br),
            "-bufsize",
            str(bufsize_phase2),
        ]
        phase2_copy_parts = phase2_common + [
            "-movflags",
            "+faststart",
            "-c:a",
            "copy",
            str(output_path),
        ]
        phase2_aac_parts = phase2_common + [
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]
        phase2_pass1_parts = phase2_common + [
            "-pass",
            "1",
            "-an",
            "-f",
            "null",
            "-",
        ]
        phase2_pass2_parts = phase2_common + [
            "-pass",
            "2",
            "-movflags",
            "+faststart",
            "-c:a",
            "copy",
            str(output_path),
        ]
        phase2_pass2_aac_parts = phase2_common + [
            "-pass",
            "2",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]
        phase1_command = phase1_parts
        phase2_command = phase2_copy_parts
        phase2_aac_command = phase2_aac_parts
        phase2_pass1_command = phase2_pass1_parts
        phase2_pass2_command = phase2_pass2_parts
        phase2_pass2_aac_command = phase2_pass2_aac_parts
    else:
        phase1_command = None
        phase2_command = None
        phase2_aac_command = None
        phase2_pass1_command = None
        phase2_pass2_command = None
        phase2_pass2_aac_command = None

    base_parts = [
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
        fps_arg,
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
        "slow",
        "-movflags",
        "+faststart",
    ]
    if video_bitrate and video_bitrate > 0 and not use_two_step:
        base_parts.extend(["-qp", "10"])
    else:
        base_parts.extend(["-crf", "15"])
    base_command = base_parts

    two_pass_pass1_command: Optional[list[str]] = None
    two_pass_pass2_command: Optional[list[str]] = None
    two_pass_pass2_aac_command: Optional[list[str]] = None
    if video_bitrate and video_bitrate > 0:
        br = video_bitrate
        bufsize = 8 * br
        # ffmpeg creates temporary x264 two-pass stats via -passlogfile.
        # For Workbench projects we want those temps in the project dir
        # (next to the SRT + word timings), even if the final MP4 output
        # follows the UI save policy.
        resolved_stats_dir = stats_dir or output_path.parent
        resolved_stats_dir.mkdir(parents=True, exist_ok=True)
        stats_base = resolved_stats_dir / (output_path.stem + "_x264pass")
        single_pipeline_head = [
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
            fps_arg,
            "-i",
            "pipe:0",
            "-progress",
            "pipe:1",
            "-nostats",
            "-filter_complex",
            filter_string,
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-b:v",
            str(br),
            "-bufsize",
            str(bufsize),
        ]
        two_pass_pass1_command = single_pipeline_head + [
            "-pass",
            "1",
            "-passlogfile",
            str(stats_base),
            "-an",
            "-f",
            "null",
            os.devnull,
        ]
        two_pass_pass2_command = single_pipeline_head + [
            "-pass",
            "2",
            "-passlogfile",
            str(stats_base),
            "-movflags",
            "+faststart",
            "-map",
            "0:a?",
            "-c:a",
            "copy",
            str(output_path),
        ]
        two_pass_pass2_aac_command = single_pipeline_head + [
            "-pass",
            "2",
            "-passlogfile",
            str(stats_base),
            "-movflags",
            "+faststart",
            "-map",
            "0:a?",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]

    return GraphicsOverlayPlan(
        base_command=base_command,
        pipeline=GRAPHICS_OVERLAY_PIPELINE,
        filter_string=filter_string,
        width=width,
        height=height,
        fps=fps,
        fps_arg=fps_arg,
        phase1_command=phase1_command,
        phase2_command=phase2_command,
        phase2_aac_command=phase2_aac_command,
        two_pass_pass1_command=two_pass_pass1_command,
        two_pass_pass2_command=two_pass_pass2_command,
        two_pass_pass2_aac_command=two_pass_pass2_aac_command,
        phase2_pass1_command=phase2_pass1_command,
        phase2_pass2_command=phase2_pass2_command,
        phase2_pass2_aac_command=phase2_pass2_aac_command,
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


OVERLAY_RESOLUTION_SCALE = 4
OVERLAY_OUTLINE_METHOD = "filled_path"
OVERLAY_OUTLINE_SOFT_EDGE = "halo"
OVERLAY_DOWNSCALE_TWO_STEP = True


def _scale_style_for_supersampling(style: SubtitleStyle, scale: float) -> SubtitleStyle:
    if scale <= 1.0:
        return style
    return replace(
        style,
        font_size=style.font_size * scale,
        letter_spacing=style.letter_spacing * scale,
        outline_width=style.outline_width * scale,
        outline_color=resolve_outline_color(style),
        shadow_strength=style.shadow_strength * scale,
        shadow_offset_x=style.shadow_offset_x * scale,
        shadow_offset_y=style.shadow_offset_y * scale,
        shadow_blur=style.shadow_blur * scale,
        line_bg_padding=style.line_bg_padding * scale,
        line_bg_padding_top=style.line_bg_padding_top * scale,
        line_bg_padding_right=style.line_bg_padding_right * scale,
        line_bg_padding_bottom=style.line_bg_padding_bottom * scale,
        line_bg_padding_left=style.line_bg_padding_left * scale,
        line_bg_radius=style.line_bg_radius * scale,
        word_bg_padding=style.word_bg_padding * scale,
        word_bg_padding_top=style.word_bg_padding_top * scale,
        word_bg_padding_right=style.word_bg_padding_right * scale,
        word_bg_padding_bottom=style.word_bg_padding_bottom * scale,
        word_bg_padding_left=style.word_bg_padding_left * scale,
        word_bg_radius=style.word_bg_radius * scale,
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
    highlight_word_index: Optional[int] = None,
    render_context: Optional["RenderContext"] = None,
) -> tuple[bytes, Optional[int]]:
    from PySide6 import QtCore, QtGui
    from .graphics_preview_renderer import render_graphics_preview

    scale = OVERLAY_RESOLUTION_SCALE
    render_w = width * scale
    render_h = height * scale
    draw_style = resolve_style_for_frame(style, height)
    draw_style = _scale_style_for_supersampling(draw_style, scale)
    frame = QtGui.QImage(render_w, render_h, QtGui.QImage.Format_RGBA8888)
    frame.fill(QtCore.Qt.transparent)
    result = render_graphics_preview(
        frame,
        subtitle_text=subtitle_text,
        style=draw_style,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
        highlight_opacity=highlight_opacity,
        highlight_word_index=highlight_word_index,
        render_context=render_context,
    )
    image = result.image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    if scale > 1:
        if OVERLAY_DOWNSCALE_TWO_STEP and scale >= 2:
            smooth = QtCore.Qt.SmoothTransformation
            w, h = render_w, render_h
            while w > width or h > height:
                next_w = max(width, w // 2)
                next_h = max(height, h // 2)
                image = image.scaled(next_w, next_h, QtCore.Qt.IgnoreAspectRatio, smooth)
                w, h = next_w, next_h
        else:
            image = image.scaled(
                width,
                height,
                QtCore.Qt.IgnoreAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
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
