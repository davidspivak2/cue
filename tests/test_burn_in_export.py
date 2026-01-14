from pathlib import Path

from app.burn_in_export import (
    STATIC_SRT_PIPELINE,
    WORD_HIGHLIGHT_ASS_PIPELINE,
    build_burn_in_plan,
)
from app.ffmpeg_utils import build_ass_filter, build_subtitles_filter
from app.subtitle_style import PRESET_DEFAULT, preset_defaults, to_ffmpeg_force_style


def _write_srt(path: Path) -> None:
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n",
        encoding="utf-8",
    )


def test_build_burn_in_plan_static_keeps_srt(tmp_path: Path) -> None:
    srt_path = tmp_path / "video.srt"
    _write_srt(srt_path)
    style = preset_defaults(PRESET_DEFAULT)
    output_path = tmp_path / "video_subtitled.mp4"
    plan = build_burn_in_plan(
        ffmpeg_path=Path("ffmpeg"),
        video_path=tmp_path / "video.mp4",
        output_path=output_path,
        srt_path=srt_path,
        subtitle_mode="static",
        style=style,
    )

    assert plan.pipeline == STATIC_SRT_PIPELINE
    assert plan.ass_path is None
    expected_filter = build_subtitles_filter(srt_path, force_style=to_ffmpeg_force_style(style))
    assert plan.filter_string == expected_filter
    assert plan.subtitles_path == srt_path
    assert "ass=" not in plan.filter_string
    assert list(tmp_path.glob("*.ass")) == []
    vf_index = plan.base_command.index("-vf")
    assert plan.base_command[vf_index + 1] == plan.filter_string


def test_build_burn_in_plan_word_highlight_uses_ass(tmp_path: Path) -> None:
    export_dir = tmp_path / "export dir"
    export_dir.mkdir()
    srt_path = export_dir / "video.srt"
    _write_srt(srt_path)
    style = preset_defaults(PRESET_DEFAULT)
    output_path = export_dir / "video_subtitled.mp4"
    plan = build_burn_in_plan(
        ffmpeg_path=Path("ffmpeg"),
        video_path=export_dir / "video.mp4",
        output_path=output_path,
        srt_path=srt_path,
        subtitle_mode="word_highlight",
        style=style,
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
    vf_index = plan.base_command.index("-vf")
    assert plan.base_command[vf_index + 1] == plan.filter_string
