from pathlib import Path

from app.graphics_overlay_export import GRAPHICS_OVERLAY_PIPELINE
from app.preview_playback import (
    PreviewClipSettings,
    build_preview_clip_plan,
)
from app.subtitle_style import PRESET_DEFAULT, preset_defaults


def _write_srt(path: Path) -> None:
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n",
        encoding="utf-8",
    )


def test_build_preview_clip_plan_graphics_overlay(tmp_path: Path) -> None:
    srt_path = tmp_path / "video.srt"
    _write_srt(srt_path)
    style = preset_defaults(PRESET_DEFAULT)
    settings = PreviewClipSettings(
        video_path=tmp_path / "video.mp4",
        srt_path=srt_path,
        start_seconds=1.0,
        duration_seconds=2.0,
        subtitle_mode="static",
        style=style,
    )
    output_path = tmp_path / "preview.mp4"

    plan = build_preview_clip_plan(
        ffmpeg_path=Path("ffmpeg"),
        settings=settings,
        output_path=output_path,
        width=1920,
        height=1080,
        fps=30.0,
    )

    assert plan.pipeline == GRAPHICS_OVERLAY_PIPELINE
    assert "overlay=0:0:format=auto" in plan.filter_string
    assert "scale='min(1280,iw)'" in plan.filter_string
    assert "subtitles=" not in plan.filter_string
    assert "ass=" not in plan.filter_string
    assert list(tmp_path.glob("*.ass")) == []
    filter_index = plan.command.index("-filter_complex")
    assert plan.filter_string in plan.command[filter_index + 1]
    assert plan.command[plan.command.index("-ss") + 1] == "1.000"
    assert plan.command[plan.command.index("-t") + 1] == "2.000"
