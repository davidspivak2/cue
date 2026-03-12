from __future__ import annotations

from dataclasses import replace
import sys

import pytest

from app.graphics_preview_renderer import (
    _build_text_layout,
    _build_line_paths,
    _compute_text_rect_from_lines,
    _compute_text_rect_from_paths,
    _resolve_qt_font_family,
    build_preview_cache_key,
)
from app.subtitle_style import PRESET_DEFAULT, preset_defaults


def _build_font(style):
    from PySide6 import QtGui

    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    _ = app
    resolved_family, _ = _resolve_qt_font_family(style.font_family)
    font = QtGui.QFont(resolved_family, int(round(style.font_size)))
    font.setWeight(QtGui.QFont.Weight(int(style.font_weight)))
    if style.font_style in ("italic", "bold_italic"):
        font.setItalic(True)
    return font


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Qt font layout can be unstable headless on Windows.",
)
def test_build_text_layout_applies_text_alignment_and_line_spacing() -> None:
    pytest.importorskip("PySide6")
    style = preset_defaults(PRESET_DEFAULT)
    text = "Short\nA much longer subtitle line"
    font = _build_font(style)

    _, lines_left, _ = _build_text_layout(
        text,
        font,
        width=640,
        height=360,
        position_x=0.5,
        position_y=0.5,
        text_align="left",
        line_spacing=1.0,
    )
    _, lines_center, _ = _build_text_layout(
        text,
        font,
        width=640,
        height=360,
        position_x=0.5,
        position_y=0.5,
        text_align="center",
        line_spacing=1.0,
    )
    _, lines_right, _ = _build_text_layout(
        text,
        font,
        width=640,
        height=360,
        position_x=0.5,
        position_y=0.5,
        text_align="right",
        line_spacing=1.0,
    )
    _, lines_spaced, _ = _build_text_layout(
        text,
        font,
        width=640,
        height=360,
        position_x=0.5,
        position_y=0.5,
        text_align="center",
        line_spacing=1.5,
    )

    assert lines_left[0].position().x() < lines_center[0].position().x() < lines_right[0].position().x()
    assert lines_spaced[1].position().y() > lines_center[1].position().y()


def test_build_preview_cache_key_changes_for_new_typography_fields() -> None:
    base_style = preset_defaults(PRESET_DEFAULT)

    key_default = build_preview_cache_key(
        video_path="video.mp4",
        srt_mtime=1,
        word_timings_mtime=None,
        timestamp_ms=1000,
        preview_width=1280,
        style=base_style,
        subtitle_mode="static",
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    key_weight = build_preview_cache_key(
        video_path="video.mp4",
        srt_mtime=1,
        word_timings_mtime=None,
        timestamp_ms=1000,
        preview_width=1280,
        style=replace(base_style, font_weight=700),
        subtitle_mode="static",
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    key_align = build_preview_cache_key(
        video_path="video.mp4",
        srt_mtime=1,
        word_timings_mtime=None,
        timestamp_ms=1000,
        preview_width=1280,
        style=replace(base_style, text_align="left"),
        subtitle_mode="static",
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    key_spacing = build_preview_cache_key(
        video_path="video.mp4",
        srt_mtime=1,
        word_timings_mtime=None,
        timestamp_ms=1000,
        preview_width=1280,
        style=replace(base_style, line_spacing=1.4),
        subtitle_mode="static",
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )

    assert key_default != key_weight
    assert key_default != key_align
    assert key_default != key_spacing


def test_build_text_layout_keeps_centered_rtl_text_centered() -> None:
    pytest.importorskip("PySide6")
    style = replace(preset_defaults(PRESET_DEFAULT), font_family="IBM Plex Sans Hebrew")
    text = "הספר האדם והטבע של א.ד גורדון"
    font = _build_font(style)

    layout, lines, _ = _build_text_layout(
        text,
        font,
        width=1280,
        height=720,
        position_x=0.5,
        position_y=0.8,
        text_align="center",
        line_spacing=1.0,
    )
    text_rect = _compute_text_rect_from_lines(lines)
    path_rect = _compute_text_rect_from_paths(_build_line_paths(layout, lines, text, font))

    assert abs(text_rect.center().x() - 640.0) <= 1.0
    assert abs(path_rect.center().x() - 640.0) <= 2.0
    assert abs(path_rect.center().x() - text_rect.center().x()) <= 2.0
