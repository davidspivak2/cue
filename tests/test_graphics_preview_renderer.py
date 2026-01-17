from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtGui

from app.graphics_preview_renderer import render_graphics_preview
from app.subtitle_style import preset_defaults


def test_graphics_preview_renderer_hebrew() -> None:
    style = preset_defaults("Default", subtitle_mode="word_highlight")
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))
    result = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם",
        style=style,
        subtitle_mode="word_highlight",
        highlight_color="#FF0000",
        highlight_opacity=1.0,
    )
    assert result.image.width() == 640
    assert result.image.height() == 360
    assert result.highlight_word_index == 1
