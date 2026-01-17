from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Optional

from PySide6 import QtCore, QtGui

from .subtitle_style import (
    DEFAULT_FONT_NAME,
    DEFAULT_HIGHLIGHT_COLOR,
    DEFAULT_LINE_BG_COLOR,
    DEFAULT_OUTLINE_COLOR,
    DEFAULT_SHADOW_COLOR,
    DEFAULT_TEXT_COLOR,
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

    layout = _build_text_layout(subtitle_text, font, rendered.width())
    line = layout.lineAt(0)
    text_width = line.naturalTextWidth()
    text_height = line.height()
    margin_v = int(round(style.vertical_offset))
    anchor = style.vertical_anchor
    if anchor == "top":
        top_y = margin_v
    elif anchor == "middle":
        top_y = (rendered.height() - text_height) / 2 - margin_v
    else:
        top_y = rendered.height() - margin_v - text_height
    top_y = max(0.0, top_y)
    x_pos = (rendered.width() - text_width) / 2
    line.setPosition(QtCore.QPointF(x_pos, top_y))

    highlight_selection = None
    if subtitle_mode == "word_highlight":
        highlight_selection = _select_highlight_word(subtitle_text)

    text_rect = QtCore.QRectF(x_pos, top_y, text_width, text_height)
    painter = QtGui.QPainter(rendered)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
    try:
        if style.background_mode == "line":
            _draw_line_background(
                painter,
                text_rect,
                style.line_bg_color,
                style.line_bg_opacity,
                style.line_bg_padding,
                style.line_bg_radius,
            )
        baseline = top_y + line.ascent()
        text_path = QtGui.QPainterPath()
        text_path.addText(QtCore.QPointF(x_pos, baseline), font, subtitle_text)
        _draw_shadow(painter, text_path, style)
        _draw_outline(painter, text_path, style)
        _draw_text_fill(painter, layout, style)
        if highlight_selection is not None:
            _draw_highlight(
                painter,
                layout,
                line,
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


def _select_highlight_word(text: str) -> Optional[_HighlightSelection]:
    matches = list(_WORD_RE.finditer(text))
    if not matches:
        return None
    index = 1 if len(matches) > 1 else 0
    match = matches[index]
    return _HighlightSelection(index=index, start=match.start(), end=match.end())


def _build_text_layout(text: str, font: QtGui.QFont, width: int) -> QtGui.QTextLayout:
    layout = QtGui.QTextLayout(text, font)
    option = QtGui.QTextOption()
    option.setAlignment(QtCore.Qt.AlignHCenter)
    option.setWrapMode(QtGui.QTextOption.NoWrap)
    if _is_rtl(text):
        option.setTextDirection(QtCore.Qt.RightToLeft)
    layout.setTextOption(option)
    layout.beginLayout()
    line = layout.createLine()
    line.setLineWidth(width)
    layout.endLayout()
    return layout


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


def _draw_shadow(painter: QtGui.QPainter, path: QtGui.QPainterPath, style: SubtitleStyle) -> None:
    if not style.shadow_enabled or style.shadow_opacity <= 0:
        return
    offset_x = style.shadow_offset_x
    offset_y = style.shadow_offset_y
    if abs(offset_x) < 0.1 and abs(offset_y) < 0.1:
        offset_x = style.shadow_strength
        offset_y = style.shadow_strength
    shadow_color = _resolve_color(style.shadow_color, DEFAULT_SHADOW_COLOR, style.shadow_opacity)
    painter.save()
    painter.translate(offset_x, offset_y)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(shadow_color)
    painter.drawPath(path)
    painter.restore()


def _draw_outline(
    painter: QtGui.QPainter, path: QtGui.QPainterPath, style: SubtitleStyle
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
    painter.drawPath(path)
    painter.restore()


def _draw_text_fill(
    painter: QtGui.QPainter, layout: QtGui.QTextLayout, style: SubtitleStyle
) -> None:
    text_color = _resolve_color(style.text_color, DEFAULT_TEXT_COLOR, style.text_opacity)
    painter.save()
    painter.setPen(text_color)
    layout.draw(painter, QtCore.QPointF(0, 0))
    painter.restore()


def _draw_highlight(
    painter: QtGui.QPainter,
    layout: QtGui.QTextLayout,
    line: QtGui.QTextLine,
    selection: _HighlightSelection,
    highlight_color: str,
    highlight_opacity: Optional[float],
) -> None:
    start_x = line.cursorToX(selection.start)
    end_x = line.cursorToX(selection.end)
    left = min(start_x, end_x)
    width = abs(end_x - start_x)
    rect = QtCore.QRectF(line.position().x() + left, line.position().y(), width, line.height())
    color = _resolve_color(
        highlight_color,
        DEFAULT_HIGHLIGHT_COLOR,
        highlight_opacity if highlight_opacity is not None else 1.0,
    )
    painter.save()
    painter.setClipRect(rect)
    painter.setPen(color)
    layout.draw(painter, QtCore.QPointF(0, 0))
    painter.restore()
