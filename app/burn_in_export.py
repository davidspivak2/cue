from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ass_karaoke import (
    build_ass_document_with_karaoke_fallback,
    build_style_config_from_subtitle_style,
)
from .config import DEFAULT_HIGHLIGHT_COLOR, DEFAULT_HIGHLIGHT_OPACITY
from .ffmpeg_utils import build_ass_filter, build_subtitles_filter
from .srt_utils import parse_srt_file
from .subtitle_style import SubtitleStyle, to_ffmpeg_force_style


STATIC_SRT_PIPELINE = "static_srt"
WORD_HIGHLIGHT_ASS_PIPELINE = "word_highlight_ass"


@dataclass(frozen=True)
class BurnInPlan:
    base_command: list[str]
    pipeline: str
    subtitles_path: Path
    filter_string: str
    ass_path: Optional[Path] = None
    karaoke_enabled: bool = False
    karaoke_reason: str = ""
    karaoke_event_count: int = 0
    karaoke_word_timings_path: Optional[Path] = None


def build_burn_in_plan(
    *,
    ffmpeg_path: Path,
    video_path: Path,
    output_path: Path,
    srt_path: Path,
    subtitle_mode: str,
    style: SubtitleStyle,
    word_timings_path: Optional[Path] = None,
    highlight_color: Optional[str] = None,
    highlight_opacity: Optional[float] = None,
) -> BurnInPlan:
    if subtitle_mode == "word_highlight":
        cues = parse_srt_file(srt_path)
        style_config = build_style_config_from_subtitle_style(
            style,
            highlight_color=highlight_color or DEFAULT_HIGHLIGHT_COLOR,
            highlight_opacity=(
                highlight_opacity
                if highlight_opacity is not None
                else DEFAULT_HIGHLIGHT_OPACITY
            ),
        )
        decision = build_ass_document_with_karaoke_fallback(
            cues,
            srt_path=srt_path,
            word_timings_path=word_timings_path,
            style_config=style_config,
        )
        ass_text = decision.ass_text
        ass_path = output_path.with_name(f"{video_path.stem}_word_highlight.ass")
        ass_path.write_text(ass_text, encoding="utf-8")
        filter_string = build_ass_filter(ass_path)
        pipeline = WORD_HIGHLIGHT_ASS_PIPELINE
        subtitles_path = ass_path
    else:
        force_style = to_ffmpeg_force_style(style)
        filter_string = build_subtitles_filter(srt_path, force_style=force_style)
        pipeline = STATIC_SRT_PIPELINE
        subtitles_path = srt_path
        ass_path = None
        decision = None

    base_command = [
        str(ffmpeg_path),
        "-y",
        "-hide_banner",
        "-i",
        str(video_path),
        "-progress",
        "pipe:1",
        "-nostats",
        "-vf",
        filter_string,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
    ]

    return BurnInPlan(
        base_command=base_command,
        pipeline=pipeline,
        subtitles_path=subtitles_path,
        filter_string=filter_string,
        ass_path=ass_path,
        karaoke_enabled=decision.karaoke_enabled if decision else False,
        karaoke_reason=decision.reason if decision else "static",
        karaoke_event_count=decision.highlight_event_count if decision else 0,
        karaoke_word_timings_path=decision.word_timings_path if decision else None,
    )
