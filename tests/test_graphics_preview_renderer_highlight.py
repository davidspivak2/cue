from __future__ import annotations

from dataclasses import replace

import pytest

from app.subtitle_style import preset_defaults


def _ensure_qt_app(QtGui) -> None:
    if QtGui.QGuiApplication.instance() is None:
        QtGui.QGuiApplication([])


def _count_yellowish_pixels(image, QtGui) -> int:
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            color = QtGui.QColor(image.pixel(x, y))
            if color.red() >= 200 and color.green() >= 180 and color.blue() <= 180:
                count += 1
    return count


@pytest.mark.parametrize("font_size", [28, 29])
def test_word_highlight_overlay_visible(font_size: int) -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    _ensure_qt_app(QtGui)
    from app.graphics_preview_renderer import render_graphics_preview

    style = preset_defaults("Default", subtitle_mode="word_highlight")
    style = replace(
        style,
        font_family="Arial",
        font_size=font_size,
        outline_enabled=False,
        shadow_enabled=False,
        background_mode="none",
        text_color="#FFFFFF",
        text_opacity=1.0,
        subtitle_mode="word_highlight",
    )
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))
    result = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם זה מבחן",
        style=style,
        subtitle_mode="word_highlight",
        highlight_color="#FFF04C",
        highlight_opacity=1.0,
    )
    assert result.highlight_word_index == 1
    highlight_pixels = _count_yellowish_pixels(result.image, QtGui)
    assert highlight_pixels > 50

    static_result = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם זה מבחן",
        style=replace(style, subtitle_mode="static"),
        subtitle_mode="static",
        highlight_color="#FFF04C",
        highlight_opacity=1.0,
    )
    static_pixels = _count_yellowish_pixels(static_result.image, QtGui)
    assert static_pixels < 10
