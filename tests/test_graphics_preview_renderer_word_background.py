from __future__ import annotations

from dataclasses import replace

import pytest

from app.subtitle_style import preset_defaults


def _ensure_qt_app(QtGui) -> None:
    if QtGui.QGuiApplication.instance() is None:
        QtGui.QGuiApplication([])


def _image_bytes(image, QtGui) -> bytes:
    ptr = image.bits()
    ptr.setsize(image.sizeInBytes())
    return bytes(ptr)


def test_word_background_applies_only_in_word_highlight_mode() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    _ensure_qt_app(QtGui)
    from app.graphics_preview_renderer import render_graphics_preview

    style = preset_defaults("Default", subtitle_mode="word_highlight")
    style = replace(
        style,
        font_family="Arial",
        font_size=30,
        outline_enabled=False,
        shadow_enabled=False,
        background_mode="word",
        word_bg_color="#FF0000",
        word_bg_opacity=0.8,
        word_bg_padding=4.0,
        word_bg_radius=4.0,
        text_color="#FFFFFF",
        text_opacity=1.0,
        subtitle_mode="word_highlight",
    )
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))

    with_bg = render_graphics_preview(
        frame,
        subtitle_text="hello world",
        style=style,
        subtitle_mode="word_highlight",
        highlight_color="#FFFFFF",
        highlight_opacity=0.0,
        highlight_word_index=1,
    )
    without_bg = render_graphics_preview(
        frame,
        subtitle_text="hello world",
        style=replace(style, background_mode="none"),
        subtitle_mode="word_highlight",
        highlight_color="#FFFFFF",
        highlight_opacity=0.0,
        highlight_word_index=1,
    )
    assert _image_bytes(with_bg.image, QtGui) != _image_bytes(without_bg.image, QtGui)

    static_with_bg = render_graphics_preview(
        frame,
        subtitle_text="hello world",
        style=replace(style, subtitle_mode="static"),
        subtitle_mode="static",
        highlight_color="#FFFFFF",
        highlight_opacity=0.0,
        highlight_word_index=1,
    )
    static_without_bg = render_graphics_preview(
        frame,
        subtitle_text="hello world",
        style=replace(style, subtitle_mode="static", background_mode="none"),
        subtitle_mode="static",
        highlight_color="#FFFFFF",
        highlight_opacity=0.0,
        highlight_word_index=1,
    )
    assert _image_bytes(static_with_bg.image, QtGui) == _image_bytes(
        static_without_bg.image, QtGui
    )
