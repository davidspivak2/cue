from __future__ import annotations

from dataclasses import replace

import pytest

from app.subtitle_style import preset_defaults


def _ensure_qt_app(QtGui) -> None:
    if QtGui.QGuiApplication.instance() is None:
        QtGui.QGuiApplication([])


def _image_bytes(image, QtGui) -> bytes:
    image = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    size = image.sizeInBytes()
    buffer = image.bits()
    if hasattr(buffer, "setsize"):
        buffer.setsize(size)
        return bytes(buffer)
    data = buffer.tobytes()
    return data[:size]


def test_render_context_caches_layout_and_paths() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    _ensure_qt_app(QtGui)
    from app.graphics_preview_renderer import (
        LAYOUT_CACHE_MAX_ENTRIES,
        PATH_CACHE_MAX_ENTRIES,
        LRUCache,
        RenderContext,
        RenderPerfStats,
        render_graphics_preview,
    )

    style = preset_defaults("Default", subtitle_mode="word_highlight")
    style = replace(
        style,
        font_family="Arial",
        font_size=28,
        outline_enabled=True,
        shadow_enabled=True,
        background_mode="none",
        text_color="#FFFFFF",
        text_opacity=1.0,
    )
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))

    perf_stats = RenderPerfStats()
    render_context = RenderContext(
        layout_cache=LRUCache(max_entries=LAYOUT_CACHE_MAX_ENTRIES),
        path_cache=LRUCache(max_entries=PATH_CACHE_MAX_ENTRIES),
        perf_stats=perf_stats,
    )

    first = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם זה מבחן",
        style=style,
        subtitle_mode="word_highlight",
        highlight_color="#FFF04C",
        highlight_opacity=1.0,
        highlight_word_index=0,
        render_context=render_context,
    )
    second = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם זה מבחן",
        style=style,
        subtitle_mode="word_highlight",
        highlight_color="#FFF04C",
        highlight_opacity=1.0,
        highlight_word_index=0,
        render_context=render_context,
    )

    assert _image_bytes(first.image, QtGui) == _image_bytes(second.image, QtGui)
    assert perf_stats.render_calls_total == 2
    assert perf_stats.layout_cache_misses == 1
    assert perf_stats.path_cache_misses == 1
    assert perf_stats.layout_cache_hits == 1
    assert perf_stats.path_cache_hits == 1
