"""Tests for graphics overlay export (burn-in overlay frame rendering)."""

import sys

import pytest

from app.graphics_overlay_export import (
    OVERLAY_RESOLUTION_SCALE,
    render_overlay_frame,
)
from app.subtitle_style import PRESET_DEFAULT, preset_defaults

_skip_qt_render_on_win = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Qt overlay render can crash headless on Windows; use visual check",
)


@_skip_qt_render_on_win
def test_render_overlay_frame_returns_correct_size_and_format() -> None:
    pytest.importorskip("PySide6")
    width, height = 100, 60
    style = preset_defaults(PRESET_DEFAULT)
    data, highlight_index = render_overlay_frame(
        width=width,
        height=height,
        subtitle_text="Hello",
        style=style,
        subtitle_mode="static",
        highlight_color=None,
        highlight_opacity=0.0,
    )
    assert len(data) == width * height * 4
    assert highlight_index is None


@_skip_qt_render_on_win
def test_render_overlay_frame_supersampling_produces_final_dimensions() -> None:
    pytest.importorskip("PySide6")
    width, height = 50, 30
    style = preset_defaults(PRESET_DEFAULT)
    data, _ = render_overlay_frame(
        width=width,
        height=height,
        subtitle_text="x",
        style=style,
        subtitle_mode="static",
        highlight_color=None,
        highlight_opacity=0.0,
    )
    assert OVERLAY_RESOLUTION_SCALE >= 1
    assert len(data) == width * height * 4
