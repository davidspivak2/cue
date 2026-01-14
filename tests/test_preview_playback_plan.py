from pathlib import Path

from app.ffmpeg_utils import build_ass_filter, build_subtitles_filter
from app.preview_playback import (
    STATIC_SRT_PIPELINE,
    WORD_HIGHLIGHT_ASS_PIPELINE,
    PreviewClipSettings,
    build_preview_clip_plan,
)
from app.subtitle_style import PRESET_DEFAULT, preset_defaults, to_ffmpeg_force_style


def _write_srt(path: Path) -> None:
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n",
        encoding="utf-8",
    )


def test_build_preview_clip_plan_static_keeps_srt(tmp_path: Path) -> None:
    srt_path = tmp_path / "video.srt"
    _write_srt(srt_path)
    style = preset_defaults(PRESET_DEFAULT)
    settings = PreviewClipSettings(
        video_path=tmp_path / "video.mp4",
        srt_path=srt_path,
        start_seconds=0.0,
        duration_seconds=1.0,
        force_style=to_ffmpeg_force_style(style),
        subtitle_mode="static",
        style=style,
    )
    output_path = tmp_path / "preview.mp4"

    plan = build_preview_clip_plan(
        ffmpeg_path=Path("ffmpeg"),
        settings=settings,
        output_path=output_path,
        shifted_srt_path=srt_path,
    )

    assert plan.pipeline == STATIC_SRT_PIPELINE
    assert plan.ass_path is None
    expected_filter = build_subtitles_filter(srt_path, force_style=to_ffmpeg_force_style(style))
    assert plan.filter_string == expected_filter
    assert plan.subtitles_path == srt_path
    assert list(tmp_path.glob("*.ass")) == []
    filter_index = plan.command.index("-filter_complex")
    assert plan.filter_string in plan.command[filter_index + 1]


def test_build_preview_clip_plan_word_highlight_uses_ass(tmp_path: Path) -> None:
    srt_path = tmp_path / "video.srt"
    _write_srt(srt_path)
    style = preset_defaults(PRESET_DEFAULT)
    settings = PreviewClipSettings(
        video_path=tmp_path / "video.mp4",
        srt_path=srt_path,
        start_seconds=0.0,
        duration_seconds=1.0,
        force_style=to_ffmpeg_force_style(style),
        subtitle_mode="word_highlight",
        style=style,
    )
    output_path = tmp_path / "preview.mp4"

    plan = build_preview_clip_plan(
        ffmpeg_path=Path("ffmpeg"),
        settings=settings,
        output_path=output_path,
        shifted_srt_path=srt_path,
    )

    assert plan.pipeline == WORD_HIGHLIGHT_ASS_PIPELINE
    assert plan.ass_path is not None
    assert plan.ass_path.exists()
    assert plan.filter_string == build_ass_filter(plan.ass_path)
    assert "subtitles=" not in plan.filter_string
    ass_text = plan.ass_path.read_text(encoding="utf-8")
    assert "[Script Info]" in ass_text
    assert "[V4+ Styles]" in ass_text
    assert "[Events]" in ass_text
    vf_index = plan.command.index("-vf")
    assert plan.filter_string in plan.command[vf_index + 1]
