from __future__ import annotations

from pathlib import Path

import pytest

def test_render_overlay_frame_no_disk_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    from app.graphics_overlay_export import render_overlay_frame
    from app.subtitle_style import preset_defaults

    monkeypatch.chdir(tmp_path)
    style = preset_defaults("Default", subtitle_mode="static")
    frame_bytes, highlight_index = render_overlay_frame(
        width=320,
        height=180,
        subtitle_text="Hello overlay",
        style=style,
        subtitle_mode="static",
        highlight_color=None,
        highlight_opacity=None,
    )
    assert len(frame_bytes) == 320 * 180 * 4
    assert highlight_index is None
    assert list(tmp_path.rglob("*.png")) == []
    assert list(tmp_path.rglob("*.jpg")) == []


def test_build_graphics_overlay_plan_command_shape() -> None:
    from app.graphics_overlay_export import build_graphics_overlay_plan

    plan = build_graphics_overlay_plan(
        ffmpeg_path=Path("ffmpeg"),
        video_path=Path("input.mp4"),
        output_path=Path("output.mp4"),
        width=1920,
        height=1080,
        fps=30.0,
    )
    command = plan.base_command
    assert "rawvideo" in command
    pix_index = command.index("-pix_fmt")
    assert command[pix_index + 1] == "rgba"
    size_index = command.index("-s")
    assert command[size_index + 1] == "1920x1080"
    filter_index = command.index("-filter_complex")
    assert "overlay" in command[filter_index + 1]
