from __future__ import annotations

from dataclasses import replace

import pytest

from app.subtitle_style import MIN_TEXT_OPACITY, normalize_style_model, preset_defaults


def _has_non_black_pixel(image, QtGui) -> bool:
    for y in range(image.height()):
        for x in range(image.width()):
            if QtGui.QColor(image.pixel(x, y)).value() > 0:
                return True
    return False


def test_graphics_preview_renderer_hebrew() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    from app.graphics_preview_renderer import render_graphics_preview

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


def test_highlight_keeps_base_text_visible() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    from app.graphics_preview_renderer import render_graphics_preview

    style = preset_defaults("Default", subtitle_mode="word_highlight")
    style = replace(
        style,
        outline_enabled=False,
        shadow_enabled=False,
        background_mode="none",
        text_color="#FFFFFF",
        text_opacity=1.0,
    )
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))
    result = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם",
        style=style,
        subtitle_mode="word_highlight",
        highlight_color="#FF0000",
        highlight_opacity=0.0,
    )
    assert _has_non_black_pixel(result.image, QtGui)


def test_line_background_visible_without_text() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    from app.graphics_preview_renderer import render_graphics_preview

    style = preset_defaults("Default", subtitle_mode="static")
    style = replace(
        style,
        outline_enabled=False,
        shadow_enabled=False,
        background_mode="line",
        line_bg_color="#FFFFFF",
        line_bg_opacity=1.0,
        line_bg_padding=10,
        line_bg_radius=0.0,
        text_color="#000000",
        text_opacity=1.0,
    )
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))
    result = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם",
        style=style,
        subtitle_mode="static",
        highlight_color="#FF0000",
        highlight_opacity=1.0,
    )
    assert _has_non_black_pixel(result.image, QtGui)


def test_normalize_style_model_clamps_text_opacity() -> None:
    fallback = preset_defaults("Default")
    normalized = normalize_style_model({"text_opacity": 0.0}, fallback)
    assert normalized.text_opacity == MIN_TEXT_OPACITY


def _has_highlight_pixel(image, QtGui, target_hex: str) -> bool:
    target = QtGui.QColor(target_hex)
    for y in range(image.height()):
        for x in range(image.width()):
            color = QtGui.QColor(image.pixel(x, y))
            if (
                abs(color.red() - target.red()) <= 12
                and abs(color.green() - target.green()) <= 12
                and abs(color.blue() - target.blue()) <= 12
            ):
                return True
    return False


def test_highlight_fill_pixels_present() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    from app.graphics_preview_renderer import render_graphics_preview

    style = preset_defaults("Default", subtitle_mode="word_highlight")
    style = replace(
        style,
        outline_enabled=False,
        shadow_enabled=False,
        background_mode="none",
        text_color="#FFFFFF",
        text_opacity=1.0,
    )
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))
    result = render_graphics_preview(
        frame,
        subtitle_text="אז אני רוצה",
        style=style,
        subtitle_mode="word_highlight",
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    assert _has_highlight_pixel(result.image, QtGui, "#FFD400")


def test_outline_visible() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    from app.graphics_preview_renderer import render_graphics_preview

    style = preset_defaults("Default", subtitle_mode="static")
    style = replace(
        style,
        outline_enabled=True,
        outline_color="#FFFFFF",
        outline_width=4,
        shadow_enabled=False,
        background_mode="none",
        text_color="#000000",
        text_opacity=1.0,
    )
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))
    result = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם",
        style=style,
        subtitle_mode="static",
        highlight_color="#FF0000",
        highlight_opacity=1.0,
    )
    assert _has_non_black_pixel(result.image, QtGui)


def test_shadow_visible() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    from app.graphics_preview_renderer import render_graphics_preview

    style = preset_defaults("Default", subtitle_mode="static")
    style = replace(
        style,
        outline_enabled=False,
        shadow_enabled=True,
        shadow_color="#FFFFFF",
        shadow_opacity=1.0,
        shadow_strength=3,
        background_mode="none",
        text_color="#000000",
        text_opacity=1.0,
    )
    frame = QtGui.QImage(640, 360, QtGui.QImage.Format_ARGB32)
    frame.fill(QtGui.QColor("black"))
    result = render_graphics_preview(
        frame,
        subtitle_text="שלום עולם",
        style=style,
        subtitle_mode="static",
        highlight_color="#FF0000",
        highlight_opacity=1.0,
    )
    assert _has_non_black_pixel(result.image, QtGui)
