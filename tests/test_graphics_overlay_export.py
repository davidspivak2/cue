"""Tests for graphics overlay export (burn-in overlay frame rendering)."""

from dataclasses import replace

import pytest

from app.graphics_overlay_export import (
    OVERLAY_RESOLUTION_SCALE,
    _scale_style_for_supersampling,
    render_overlay_frame,
)
from app.subtitle_style import PRESET_DEFAULT, preset_defaults, resolve_style_for_frame


def _ensure_qt_app() -> None:
    from PySide6 import QtGui

    if QtGui.QGuiApplication.instance() is None:
        QtGui.QGuiApplication([])


def test_render_overlay_frame_returns_correct_size_and_format() -> None:
    pytest.importorskip("PySide6")
    _ensure_qt_app()
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


def test_render_overlay_frame_supersampling_produces_final_dimensions() -> None:
    pytest.importorskip("PySide6")
    _ensure_qt_app()
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


def test_render_overlay_frame_accepts_chunk1_typography_fields() -> None:
    pytest.importorskip("PySide6")
    _ensure_qt_app()
    width, height = 80, 40
    style = replace(
        preset_defaults(PRESET_DEFAULT),
        font_weight=700,
        text_align="left",
        line_spacing=1.4,
        shadow_offset_x=3.0,
        shadow_offset_y=1.0,
    )
    data, _ = render_overlay_frame(
        width=width,
        height=height,
        subtitle_text="Two\nLines",
        style=style,
        subtitle_mode="static",
        highlight_color=None,
        highlight_opacity=0.0,
    )

    assert len(data) == width * height * 4


def test_export_style_resolves_frame_height_before_supersampling() -> None:
    style = preset_defaults(PRESET_DEFAULT)

    resolved = resolve_style_for_frame(style, 720)
    draw_style = _scale_style_for_supersampling(resolved, OVERLAY_RESOLUTION_SCALE)

    assert draw_style.font_size == pytest.approx(
        resolved.font_size * OVERLAY_RESOLUTION_SCALE,
        abs=0.2,
    )
    assert draw_style.outline_width == pytest.approx(
        resolved.outline_width * OVERLAY_RESOLUTION_SCALE,
        abs=0.001,
    )
    assert draw_style.line_bg_padding_top == pytest.approx(
        resolved.line_bg_padding_top * OVERLAY_RESOLUTION_SCALE,
        abs=0.001,
    )
