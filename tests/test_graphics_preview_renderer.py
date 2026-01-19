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
    tr, tg, tb = target.red(), target.green(), target.blue()
    # Use a tolerant Manhattan distance for subpixel antialiasing (Windows/ClearType).
    max_dist = 120
    for y in range(image.height()):
        for x in range(image.width()):
            color = QtGui.QColor(image.pixel(x, y))
            dist = abs(color.red() - tr) + abs(color.green() - tg) + abs(color.blue() - tb)
            if dist <= max_dist:
                return True
    return False


def _color_distance(color, target) -> int:
    return (
        abs(color.red() - target.red())
        + abs(color.green() - target.green())
        + abs(color.blue() - target.blue())
    )


def _row_target_count(image, QtGui, target, tolerance: int, y: int) -> int:
    count = 0
    for x in range(image.width()):
        color = QtGui.QColor(image.pixel(x, y))
        if _color_distance(color, target) <= tolerance:
            count += 1
    return count


def _row_clusters(image, QtGui, target, tolerance: int) -> list[tuple[int, int]]:
    clusters: list[tuple[int, int]] = []
    start = None
    for y in range(image.height()):
        row_count = _row_target_count(image, QtGui, target, tolerance, y)
        if row_count > 0 and start is None:
            start = y
        elif row_count == 0 and start is not None:
            clusters.append((start, y - 1))
            start = None
    if start is not None:
        clusters.append((start, image.height() - 1))
    return clusters


def _line_bboxes(image, QtGui, target_hex: str, tolerance: int) -> list[tuple[int, int, int, int]]:
    target = QtGui.QColor(target_hex)
    clusters = _row_clusters(image, QtGui, target, tolerance)
    bboxes: list[tuple[int, int, int, int]] = []
    for start_y, end_y in clusters:
        min_x = image.width()
        max_x = -1
        min_y = None
        max_y = None
        for y in range(start_y, end_y + 1):
            row_has_target = False
            for x in range(image.width()):
                color = QtGui.QColor(image.pixel(x, y))
                if _color_distance(color, target) <= tolerance:
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                    row_has_target = True
            if row_has_target:
                if min_y is None:
                    min_y = y
                max_y = y
        if max_x >= 0 and min_y is not None and max_y is not None:
            bboxes.append((min_x, max_x, min_y, max_y))
    return bboxes


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


def test_wrapped_outline_shadow_alignment() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    from app.graphics_preview_renderer import render_graphics_preview, _supports_glyph_runs

    if not _supports_glyph_runs():
        pytest.skip("Glyph-run APIs not available; skipping wrapped-line alignment test.")

    text = "שלום עולם זה מבחן ארוך מאוד כדי שיישבר לשתי שורות"
    base_style = preset_defaults("Default", subtitle_mode="static")
    base_style = replace(
        base_style,
        font_size=48,
        background_mode="none",
        text_opacity=1.0,
    )

    def _render(style):
        frame = QtGui.QImage(320, 240, QtGui.QImage.Format_ARGB32)
        frame.fill(QtGui.QColor("black"))
        return render_graphics_preview(
            frame,
            subtitle_text=text,
            style=style,
            subtitle_mode="static",
            highlight_color="#FF0000",
            highlight_opacity=1.0,
        ).image

    fill_style = replace(
        base_style,
        outline_enabled=False,
        shadow_enabled=False,
        text_color="#FFFFFF",
    )
    outline_style = replace(
        base_style,
        outline_enabled=True,
        outline_color="#00FF00",
        outline_width=4,
        shadow_enabled=False,
        text_color="#000000",
    )
    shadow_style = replace(
        base_style,
        outline_enabled=False,
        shadow_enabled=True,
        shadow_color="#00A0FF",
        shadow_opacity=1.0,
        shadow_strength=4,
        shadow_offset_x=3,
        shadow_offset_y=3,
        text_color="#000000",
    )

    fill_image = _render(fill_style)
    outline_image = _render(outline_style)
    shadow_image = _render(shadow_style)

    tolerance = 120
    fill_bboxes = _line_bboxes(fill_image, QtGui, "#FFFFFF", tolerance)
    outline_bboxes = _line_bboxes(outline_image, QtGui, "#00FF00", tolerance)
    shadow_bboxes = _line_bboxes(shadow_image, QtGui, "#00A0FF", tolerance)

    assert len(fill_bboxes) == 2
    assert len(outline_bboxes) == 2
    assert len(shadow_bboxes) == 2

    for index in range(2):
        fill_center = (fill_bboxes[index][0] + fill_bboxes[index][1]) / 2
        outline_center = (outline_bboxes[index][0] + outline_bboxes[index][1]) / 2
        shadow_center = (shadow_bboxes[index][0] + shadow_bboxes[index][1]) / 2
        assert abs(outline_center - fill_center) <= 3
        assert abs(shadow_center - fill_center) <= 3
