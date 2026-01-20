from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable, Optional

from PySide6 import QtCore, QtGui

from .subtitle_style import (
    DEFAULT_FONT_NAME,
    DEFAULT_HIGHLIGHT_COLOR,
    DEFAULT_LINE_BG_COLOR,
    DEFAULT_OUTLINE_COLOR,
    DEFAULT_SHADOW_COLOR,
    DEFAULT_TEXT_COLOR,
    MIN_TEXT_OPACITY,
    SubtitleStyle,
)

_WORD_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class GraphicsPreviewResult:
    image: QtGui.QImage
    highlight_word_index: Optional[int]


def build_preview_cache_key(
    *,
    video_path: str,
    srt_mtime: int,
    word_timings_mtime: Optional[int],
    timestamp_ms: int,
    preview_width: int,
    style: SubtitleStyle,
    subtitle_mode: str,
    highlight_color: Optional[str],
    highlight_opacity: Optional[float],
) -> str:
    snapshot = {
        "font_family": style.font_family,
        "font_size": style.font_size,
        "font_style": style.font_style,
        "text_color": style.text_color,
        "text_opacity": style.text_opacity,
        "letter_spacing": style.letter_spacing,
        "outline_enabled": style.outline_enabled,
        "outline_width": style.outline_width,
        "outline_color": style.outline_color,
        "shadow_enabled": style.shadow_enabled,
        "shadow_strength": style.shadow_strength,
        "shadow_offset_x": style.shadow_offset_x,
        "shadow_offset_y": style.shadow_offset_y,
        "shadow_color": style.shadow_color,
        "shadow_opacity": style.shadow_opacity,
        "background_mode": style.background_mode,
        "line_bg_color": style.line_bg_color,
        "line_bg_opacity": style.line_bg_opacity,
        "line_bg_padding": style.line_bg_padding,
        "line_bg_radius": style.line_bg_radius,
        "vertical_anchor": style.vertical_anchor,
        "vertical_offset": style.vertical_offset,
        "subtitle_mode": subtitle_mode,
        "highlight_color": highlight_color,
        "highlight_opacity": highlight_opacity,
        "word_timings_mtime": word_timings_mtime,
    }
    signature = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    cache_key = f"{video_path}|{srt_mtime}|{timestamp_ms}|{preview_width}|{signature}"
    return hashlib.sha1(cache_key.encode("utf-8")).hexdigest()


def render_graphics_preview(
    frame: QtGui.QImage,
    *,
    subtitle_text: str,
    style: SubtitleStyle,
    subtitle_mode: str,
    highlight_color: Optional[str],
    highlight_opacity: Optional[float],
    highlight_word_index: Optional[int] = None,
) -> GraphicsPreviewResult:
    rendered = QtGui.QImage(frame)
    if rendered.isNull():
        raise ValueError("Preview frame image is empty")
    if not subtitle_text.strip():
        return GraphicsPreviewResult(rendered, None)

    font = QtGui.QFont(style.font_family or DEFAULT_FONT_NAME, int(round(style.font_size)))
    if style.font_style == "bold":
        font.setBold(True)
    elif style.font_style == "italic":
        font.setItalic(True)
    if style.letter_spacing:
        font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, style.letter_spacing)

    layout, lines, line_width = _build_text_layout(
        subtitle_text,
        font,
        width=rendered.width(),
        height=rendered.height(),
        vertical_offset=style.vertical_offset,
        vertical_anchor=style.vertical_anchor,
    )

    highlight_selection = None
    if subtitle_mode == "word_highlight":
        highlight_selection = _select_highlight_word(
            subtitle_text, highlight_word_index=highlight_word_index
        )

    line_paths = _build_line_paths(layout, lines, subtitle_text, font)
    bg_rect = _compute_text_rect_from_lines(lines)
    if bg_rect.isEmpty() or bg_rect.width() <= 0 or bg_rect.height() <= 0:
        bg_rect = _compute_text_rect_from_metrics(
            subtitle_text,
            font,
            rendered.width(),
            rendered.height(),
            style.vertical_anchor,
            style.vertical_offset,
        )
    if bg_rect.isEmpty() or bg_rect.width() <= 0 or bg_rect.height() <= 0:
        bg_rect = _compute_text_rect_from_frame(rendered, style)
    painter = QtGui.QPainter(rendered)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
    try:
        if style.background_mode == "line":
            painter.save()
            painter.setOpacity(style.line_bg_opacity)
            _draw_line_background(
                painter,
                bg_rect,
                style.line_bg_color,
                1.0,
                style.line_bg_padding,
                style.line_bg_radius,
            )
            painter.restore()
        _draw_shadow(painter, line_paths, style)
        _draw_outline(painter, line_paths, style)
        effective_text_opacity = max(MIN_TEXT_OPACITY, style.text_opacity)
        if effective_text_opacity > 0:
            painter.save()
            painter.setOpacity(effective_text_opacity)
            _draw_text_fill(painter, layout, style)
            painter.restore()
        if (
            highlight_selection is not None
            and (1.0 if highlight_opacity is None else float(highlight_opacity)) > 0.0
        ):
            _draw_highlight_overlay(
                painter,
                layout,
                subtitle_text,
                highlight_selection,
                highlight_color or DEFAULT_HIGHLIGHT_COLOR,
                highlight_opacity,
            )
    finally:
        painter.end()
    return GraphicsPreviewResult(
        rendered, highlight_selection.index if highlight_selection else None
    )


@dataclass(frozen=True)
class _HighlightSelection:
    index: int
    start: int
    end: int


def _select_highlight_word(
    text: str, *, highlight_word_index: Optional[int] = None
) -> Optional[_HighlightSelection]:
    matches = list(_WORD_RE.finditer(text))
    if not matches:
        return None
    if highlight_word_index is None:
        index = 1 if len(matches) > 1 else 0
    else:
        if highlight_word_index < 0 or highlight_word_index >= len(matches):
            return None
        index = highlight_word_index
    match = matches[index]
    return _HighlightSelection(index=index, start=match.start(), end=match.end())


def _build_text_layout(
    text: str,
    font: QtGui.QFont,
    *,
    width: int,
    height: int,
    vertical_offset: float,
    vertical_anchor: str,
) -> tuple[QtGui.QTextLayout, list[QtGui.QTextLine], float]:
    layout = QtGui.QTextLayout(text, font)
    option = QtGui.QTextOption()
    option.setAlignment(QtCore.Qt.AlignLeft)
    option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
    if _is_rtl(text):
        option.setTextDirection(QtCore.Qt.RightToLeft)
    layout.setTextOption(option)
    layout.beginLayout()
    lines: list[QtGui.QTextLine] = []
    y = 0.0
    line_width = float(width)
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(line_width)
        line.setPosition(QtCore.QPointF(0.0, y))
        y += line.height()
        lines.append(line)
    layout.endLayout()
    total_height = y
    margin_v = float(vertical_offset)
    if vertical_anchor == "top":
        top_y = margin_v
    elif vertical_anchor == "middle":
        top_y = (height - total_height) / 2 - margin_v
    else:
        top_y = height - margin_v - total_height
    top_y = max(0.0, top_y)
    for line in lines:
        centered_x = (line_width - line.naturalTextWidth()) / 2
        line.setPosition(QtCore.QPointF(centered_x, line.position().y() + top_y))
    return layout, lines, line_width


def _is_rtl(text: str) -> bool:
    return any("\u0590" <= char <= "\u08FF" for char in text)


def _resolve_color(value: str, default: str, alpha: Optional[float] = None) -> QtGui.QColor:
    color = QtGui.QColor(value) if value else QtGui.QColor(default)
    if not color.isValid():
        color = QtGui.QColor(default)
    if alpha is not None:
        color.setAlphaF(max(0.0, min(alpha, 1.0)))
    return color


def _draw_line_background(
    painter: QtGui.QPainter,
    text_rect: QtCore.QRectF,
    color: str,
    opacity: float,
    padding: float,
    radius: float,
) -> None:
    bg_color = _resolve_color(color, DEFAULT_LINE_BG_COLOR, opacity)
    rect = QtCore.QRectF(text_rect)
    rect.adjust(-padding, -padding, padding, padding)
    painter.save()
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(bg_color)
    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()


def _draw_shadow(
    painter: QtGui.QPainter,
    paths: Iterable[QtGui.QPainterPath],
    style: SubtitleStyle,
) -> None:
    if not style.shadow_enabled or style.shadow_opacity <= 0:
        return
    offset_x = style.shadow_offset_x
    offset_y = style.shadow_offset_y
    if abs(offset_x) < 0.1 and abs(offset_y) < 0.1:
        offset_x = style.shadow_strength
        offset_y = style.shadow_strength
    shadow_color = _resolve_color(style.shadow_color, DEFAULT_SHADOW_COLOR, style.shadow_opacity)
    painter.save()
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(shadow_color)
    painter.translate(offset_x, offset_y)
    for path in paths:
        painter.drawPath(path)
    painter.restore()


def _draw_outline(
    painter: QtGui.QPainter,
    paths: Iterable[QtGui.QPainterPath],
    style: SubtitleStyle,
) -> None:
    if not style.outline_enabled or style.outline_width <= 0:
        return
    outline_color = _resolve_color(style.outline_color, DEFAULT_OUTLINE_COLOR)
    pen = QtGui.QPen(outline_color, style.outline_width * 2)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    painter.save()
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    for path in paths:
        painter.drawPath(path)
    painter.restore()


def _draw_text_fill(
    painter: QtGui.QPainter, layout: QtGui.QTextLayout, style: SubtitleStyle
) -> None:
    text_color = _resolve_color(style.text_color, DEFAULT_TEXT_COLOR, 1.0)
    painter.save()
    painter.setPen(text_color)
    layout.draw(painter, QtCore.QPointF(0, 0))
    painter.restore()


def _cursor_x_value(value: object) -> float:
    if isinstance(value, tuple):
        return float(value[0])
    return float(value)


def _to_layout_x(line: QtGui.QTextLine, x: float) -> float:
    left = float(line.x())
    right = left + float(line.naturalTextWidth())
    if (left - 1.0) <= x <= (right + 1.0):
        return x
    return left + x


def _iter_highlight_clip_rects(
    layout: QtGui.QTextLayout,
    selection: _HighlightSelection,
    text_len: int,
) -> Iterable[QtCore.QRectF]:
    if text_len <= 0:
        return
    selection_start = max(0, min(selection.start, text_len))
    selection_end = max(0, min(selection.end, text_len))
    if selection_end <= selection_start:
        return
    epsilon = 1.0
    min_width = 0.01
    for index in range(layout.lineCount()):
        line = layout.lineAt(index)
        if not line.isValid() or not line.textLength():
            continue
        line_start = line.textStart()
        line_end = line_start + line.textLength()
        overlap_start = max(selection_start, line_start)
        overlap_end = min(selection_end, line_end)
        if overlap_end <= overlap_start:
            continue
        x_start_raw = _cursor_x_value(line.cursorToX(overlap_start))
        x_end_raw = _cursor_x_value(line.cursorToX(overlap_end))
        x_start = _to_layout_x(line, x_start_raw)
        x_end = _to_layout_x(line, x_end_raw)
        left = min(x_start, x_end)
        right = max(x_start, x_end)
        width = right - left
        if width <= min_width:
            continue
        rect = QtCore.QRectF(left - epsilon, float(line.y()) - epsilon, width + 2.0 * epsilon, float(line.height()) + 2.0 * epsilon)
        if rect.width() <= min_width or rect.height() <= 0:
            continue
        yield rect


def _draw_highlight_overlay(
    painter: QtGui.QPainter,
    layout: QtGui.QTextLayout,
    text: str,
    selection: _HighlightSelection,
    highlight_color: str,
    highlight_opacity: Optional[float],
) -> None:
    resolved_opacity = 1.0 if highlight_opacity is None else float(highlight_opacity)
    if resolved_opacity <= 0.0:
        return
    rects = list(_iter_highlight_clip_rects(layout, selection, len(text)))
    if not rects:
        return
    highlight_color_value = QtGui.QColor(highlight_color or DEFAULT_HIGHLIGHT_COLOR)
    highlight_color_value.setAlphaF(max(0.0, min(resolved_opacity, 1.0)))
    for rect in rects:
        painter.save()
        painter.setOpacity(1.0)
        painter.setClipRect(rect)
        painter.setPen(highlight_color_value)
        layout.draw(painter, QtCore.QPointF(0, 0))
        painter.restore()


def _supports_glyph_runs() -> bool:
    return hasattr(QtGui.QTextLine, "glyphRuns") or hasattr(QtGui.QTextLayout, "glyphRuns")


def _apply_font_matrix(path: QtGui.QPainterPath, raw_font: QtGui.QRawFont) -> QtGui.QPainterPath:
    if hasattr(raw_font, "fontMatrix"):
        matrix = raw_font.fontMatrix()
        if not matrix.isIdentity():
            return matrix.map(path)
    return path


def _glyph_runs_for_line(
    layout: QtGui.QTextLayout, line: QtGui.QTextLine
) -> Optional[list[QtGui.QGlyphRun]]:
    if hasattr(line, "glyphRuns"):
        try:
            runs = list(line.glyphRuns())
            return runs
        except TypeError:
            pass
    if hasattr(layout, "glyphRuns"):
        try:
            runs = list(layout.glyphRuns(line.textStart(), line.textLength()))
            return runs
        except TypeError:
            pass
    return None


def _build_line_paths(
    layout: QtGui.QTextLayout,
    lines: Iterable[QtGui.QTextLine],
    text: str,
    font: QtGui.QFont,
) -> list[QtGui.QPainterPath]:
    paths: list[QtGui.QPainterPath] = []
    glyph_runs_supported = _supports_glyph_runs()
    for line in lines:
        if not line.textLength():
            continue
        baseline = QtCore.QPointF(line.position().x(), line.position().y() + line.ascent())
        expected = QtCore.QRectF(
            line.position().x(),
            line.position().y(),
            line.naturalTextWidth(),
            line.height(),
        )
        runs = _glyph_runs_for_line(layout, line) if glyph_runs_supported else None
        if runs is None:
            line_path = QtGui.QPainterPath()
            start = line.textStart()
            length = line.textLength()
            fragment = text[start : start + length]
            line_path.addText(baseline, font, fragment)
            paths.append(line_path)
            continue

        candidate_layout = QtGui.QPainterPath()
        candidate_baseline = QtGui.QPainterPath()
        for run in runs:
            raw = run.rawFont()
            glyph_indexes = run.glyphIndexes()
            positions = run.positions()
            for glyph_index, position in zip(glyph_indexes, positions):
                glyph_path = _apply_font_matrix(raw.pathForGlyph(glyph_index), raw)
                glyph_layout = QtGui.QPainterPath(glyph_path)
                glyph_layout.translate(position.x(), position.y())
                candidate_layout.addPath(glyph_layout)
                glyph_baseline = QtGui.QPainterPath(glyph_path)
                glyph_baseline.translate(
                    baseline.x() + position.x(), baseline.y() + position.y()
                )
                candidate_baseline.addPath(glyph_baseline)

        rect_layout = candidate_layout.boundingRect()
        rect_baseline = candidate_baseline.boundingRect()
        expected_center = expected.center()

        def _center_distance(rect: QtCore.QRectF) -> float:
            center = rect.center()
            dx = center.x() - expected_center.x()
            dy = center.y() - expected_center.y()
            return (dx * dx + dy * dy) ** 0.5

        layout_intersects = rect_layout.intersects(expected)
        baseline_intersects = rect_baseline.intersects(expected)
        if layout_intersects and not baseline_intersects:
            line_path = candidate_layout
        elif baseline_intersects and not layout_intersects:
            line_path = candidate_baseline
        elif layout_intersects and baseline_intersects:
            if _center_distance(rect_layout) <= _center_distance(rect_baseline):
                line_path = candidate_layout
            else:
                line_path = candidate_baseline
        else:
            if _center_distance(rect_layout) <= _center_distance(rect_baseline):
                line_path = candidate_layout
            else:
                line_path = candidate_baseline

        paths.append(line_path)
    return paths





def _compute_text_rect_from_paths(paths: Iterable[QtGui.QPainterPath]) -> QtCore.QRectF:
    rect: Optional[QtCore.QRectF] = None
    for path in paths:
        line_rect = path.boundingRect()
        rect = line_rect if rect is None else rect.united(line_rect)
    return rect or QtCore.QRectF()


def _compute_text_rect_from_lines(lines: Iterable[QtGui.QTextLine]) -> QtCore.QRectF:
    rect: Optional[QtCore.QRectF] = None
    for line in lines:
        if not line.textLength():
            continue
        line_rect = QtCore.QRectF(
            line.position().x(),
            line.position().y(),
            line.naturalTextWidth(),
            line.height(),
        )
        rect = line_rect if rect is None else rect.united(line_rect)
    return rect or QtCore.QRectF()


def _compute_text_rect_from_metrics(
    text: str,
    font: QtGui.QFont,
    width: int,
    height: int,
    vertical_anchor: str,
    vertical_offset: float,
) -> QtCore.QRectF:
    metrics = QtGui.QFontMetricsF(font)
    bounding = metrics.boundingRect(text)
    advance = metrics.horizontalAdvance(text)
    text_w = max(1.0, bounding.width(), advance)
    text_h = max(1.0, metrics.height())
    margin_v = float(vertical_offset)
    if vertical_anchor == "top":
        top_y = margin_v
    elif vertical_anchor == "middle":
        top_y = (height - text_h) / 2 - margin_v
    else:
        top_y = height - margin_v - text_h
    top_y = max(0.0, min(float(height) - text_h, top_y))
    x = (width - text_w) / 2
    x = max(0.0, min(float(width) - text_w, x))
    return QtCore.QRectF(x, top_y, text_w, text_h)


def _compute_text_rect_from_frame(
    frame: QtGui.QImage, style: SubtitleStyle
) -> QtCore.QRectF:
    frame_width = float(frame.width())
    frame_height = float(frame.height())
    text_w = max(1.0, frame_width * 0.6)
    text_h = max(1.0, frame_height * 0.1)
    margin_v = float(style.vertical_offset)
    if style.vertical_anchor == "top":
        top_y = margin_v
    elif style.vertical_anchor == "middle":
        top_y = (frame_height - text_h) / 2 - margin_v
    else:
        top_y = frame_height - margin_v - text_h
    top_y = max(0.0, min(frame_height - text_h, top_y))
    x = (frame_width - text_w) / 2
    x = max(0.0, min(frame_width - text_w, x))
    return QtCore.QRectF(x, top_y, text_w, text_h)


def _resolve_text_color(style: SubtitleStyle) -> QtGui.QColor:
    return _resolve_color(style.text_color, DEFAULT_TEXT_COLOR, style.text_opacity)
