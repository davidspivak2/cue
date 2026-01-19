from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
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
DIAG_LOGGER = logging.getLogger("hebrew_subtitle_gui")
_MAX_HLDBG_LINES = 3


def _format_qcolor(color: QtGui.QColor) -> str:
    try:
        return f"{color.name(QtGui.QColor.HexArgb)}@{color.alphaF():.3f}"
    except Exception:
        return "<invalid-color>"


def _format_qpen(pen: QtGui.QPen) -> str:
    try:
        width = pen.widthF()
        style = int(pen.style())
    except Exception:
        width = None
        style = None
    return f"{_format_qcolor(pen.color())} width={width} style={style}"


def _format_qbrush(brush: QtGui.QBrush) -> str:
    try:
        style = int(brush.style())
    except Exception:
        style = None
    return f"{_format_qcolor(brush.color())} style={style}"


def _format_painter_state(painter: QtGui.QPainter) -> dict[str, object]:
    try:
        composition = painter.compositionMode()
        composition_value = getattr(composition, "value", None)
        if composition_value is None:
            composition_value = str(composition)
    except Exception:
        composition_value = str(painter.compositionMode())
    try:
        render_hints = int(painter.renderHints())
    except Exception:
        render_hints = str(painter.renderHints())
    return {
        "opacity": painter.opacity(),
        "pen": _format_qpen(painter.pen()),
        "brush": _format_qbrush(painter.brush()),
        "composition": composition_value,
        "render_hints": render_hints,
    }


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
        highlight_selection = _select_highlight_word(subtitle_text)
    if subtitle_mode == "word_highlight" and highlight_selection is None:
        try:
            DIAG_LOGGER.info(
                "HLDBG: phase=pre_highlight_overlay skip_reason=selection_none "
                "font_size=%s subtitle_mode=%s text_len=%s",
                style.font_size,
                subtitle_mode,
                len(subtitle_text),
            )
        except Exception as exc:
            DIAG_LOGGER.info("HLDBG: logging_failed err=%r", exc)

    line_paths = _build_line_paths(lines, subtitle_text, font)
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
            if subtitle_mode == "word_highlight":
                try:
                    line_count = layout.lineCount() if hasattr(layout, "lineCount") else 0
                    resolved_highlight_color = highlight_color or DEFAULT_HIGHLIGHT_COLOR
                    resolved_highlight_opacity = (
                        1.0 if highlight_opacity is None else float(highlight_opacity)
                    )
                    selection_start = max(0, min(highlight_selection.start, len(subtitle_text)))
                    selection_end = max(0, min(highlight_selection.end, len(subtitle_text)))
                    selection_text = subtitle_text[selection_start:selection_end]
                    DIAG_LOGGER.info(
                        "HLDBG: phase=pre_highlight_overlay font_size=%s subtitle_mode=%s "
                        "text_len=%s highlight_color=%s highlight_opacity=%s "
                        "text_opacity=%s selection_start=%s selection_end=%s "
                        "selection_len=%s selected=%r line_count=%s",
                        style.font_size,
                        subtitle_mode,
                        len(subtitle_text),
                        resolved_highlight_color,
                        resolved_highlight_opacity,
                        effective_text_opacity,
                        selection_start,
                        selection_end,
                        selection_end - selection_start,
                        selection_text,
                        line_count,
                    )
                    for line_index in range(min(line_count, _MAX_HLDBG_LINES)):
                        line = layout.lineAt(line_index)
                        DIAG_LOGGER.info(
                            "HLDBG_LINE: phase=pre_highlight_overlay line_index=%s "
                            "line_start=%s line_len=%s natural_width=%s ascent=%s descent=%s "
                            "pos=(%s,%s)",
                            line_index,
                            line.textStart(),
                            line.textLength(),
                            line.naturalTextWidth(),
                            line.ascent(),
                            line.descent(),
                            line.position().x(),
                            line.position().y(),
                        )
                except Exception as exc:
                    DIAG_LOGGER.info("HLDBG: logging_failed err=%r", exc)
            _draw_highlight_overlay(
                painter,
                layout,
                subtitle_text,
                highlight_selection,
                highlight_color or DEFAULT_HIGHLIGHT_COLOR,
                highlight_opacity,
            )
            if subtitle_mode == "word_highlight":
                try:
                    line_count = layout.lineCount() if hasattr(layout, "lineCount") else 0
                    resolved_highlight_color = highlight_color or DEFAULT_HIGHLIGHT_COLOR
                    resolved_highlight_opacity = (
                        1.0 if highlight_opacity is None else float(highlight_opacity)
                    )
                    selection_start = max(0, min(highlight_selection.start, len(subtitle_text)))
                    selection_end = max(0, min(highlight_selection.end, len(subtitle_text)))
                    selection_text = subtitle_text[selection_start:selection_end]
                    DIAG_LOGGER.info(
                        "HLDBG: phase=post_highlight_overlay font_size=%s subtitle_mode=%s "
                        "text_len=%s highlight_color=%s highlight_opacity=%s "
                        "text_opacity=%s selection_start=%s selection_end=%s "
                        "selection_len=%s selected=%r line_count=%s",
                        style.font_size,
                        subtitle_mode,
                        len(subtitle_text),
                        resolved_highlight_color,
                        resolved_highlight_opacity,
                        effective_text_opacity,
                        selection_start,
                        selection_end,
                        selection_end - selection_start,
                        selection_text,
                        line_count,
                    )
                    for line_index in range(min(line_count, _MAX_HLDBG_LINES)):
                        line = layout.lineAt(line_index)
                        DIAG_LOGGER.info(
                            "HLDBG_LINE: phase=post_highlight_overlay line_index=%s "
                            "line_start=%s line_len=%s natural_width=%s ascent=%s descent=%s "
                            "pos=(%s,%s)",
                            line_index,
                            line.textStart(),
                            line.textLength(),
                            line.naturalTextWidth(),
                            line.ascent(),
                            line.descent(),
                            line.position().x(),
                            line.position().y(),
                        )
                except Exception as exc:
                    DIAG_LOGGER.info("HLDBG: logging_failed err=%r", exc)
        elif subtitle_mode == "word_highlight":
            try:
                resolved_highlight_opacity = (
                    1.0 if highlight_opacity is None else float(highlight_opacity)
                )
                DIAG_LOGGER.info(
                    "HLDBG: phase=pre_highlight_overlay skip_reason=no_overlay "
                    "selection_none=%s highlight_opacity=%s",
                    highlight_selection is None,
                    resolved_highlight_opacity,
                )
            except Exception as exc:
                DIAG_LOGGER.info("HLDBG: logging_failed err=%r", exc)
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


def _apply_highlight_overlay_formats(
    text: str,
    selection: Optional[_HighlightSelection],
    transparent_format: QtGui.QTextCharFormat,
    highlight_format: QtGui.QTextCharFormat,
    resolved_opacity: float,
) -> tuple[list[QtGui.QTextLayout.FormatRange], int, int]:
    selections: list[QtGui.QTextLayout.FormatRange] = []
    text_length = len(text)
    prefix_length = 0
    highlight_length = 0
    if selection is not None:
        prefix_length = max(0, min(selection.start, text_length))
        highlight_length = max(0, min(selection.end, text_length) - prefix_length)
    suffix_start = prefix_length + highlight_length
    suffix_length = max(0, text_length - suffix_start)
    if prefix_length > 0:
        prefix = QtGui.QTextLayout.FormatRange()
        prefix.start = 0
        prefix.length = prefix_length
        prefix.format = transparent_format
        selections.append(prefix)
    if highlight_length > 0:
        highlight = QtGui.QTextLayout.FormatRange()
        highlight.start = prefix_length
        highlight.length = highlight_length
        highlight.format = highlight_format
        selections.append(highlight)
    if suffix_length > 0:
        suffix = QtGui.QTextLayout.FormatRange()
        suffix.start = suffix_start
        suffix.length = suffix_length
        suffix.format = transparent_format
        selections.append(suffix)
    try:
        DIAG_LOGGER.info(
            "HLDBG: phase=apply_highlight_formats resolved_opacity=%s ranges_count=%s",
            resolved_opacity,
            len(selections),
        )
        for format_range in selections:
            color = format_range.format.foreground().color()
            DIAG_LOGGER.info(
                "HLDBG: phase=apply_highlight_formats range_start=%s range_length=%s fg=%s",
                format_range.start,
                format_range.length,
                _format_qcolor(color),
            )
    except Exception as exc:
        DIAG_LOGGER.info("HLDBG: logging_failed err=%r", exc)
    return selections, prefix_length, highlight_length


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
        try:
            DIAG_LOGGER.info(
                "HLDBG: phase=highlight_overlay skip_reason=opacity_non_positive opacity=%s",
                resolved_opacity,
            )
        except Exception as exc:
            DIAG_LOGGER.info("HLDBG: logging_failed err=%r", exc)
        return
    transparent = QtGui.QColor(0, 0, 0, 0)
    highlight_color_value = QtGui.QColor(highlight_color or DEFAULT_HIGHLIGHT_COLOR)
    highlight_color_value.setAlphaF(max(0.0, min(resolved_opacity, 1.0)))
    transparent_format = QtGui.QTextCharFormat()
    transparent_format.setForeground(QtGui.QBrush(transparent))
    highlight_format = QtGui.QTextCharFormat()
    highlight_format.setForeground(QtGui.QBrush(highlight_color_value))

    selections, highlight_start, highlight_length = _apply_highlight_overlay_formats(
        text,
        selection,
        transparent_format,
        highlight_format,
        resolved_opacity,
    )

    painter.save()
    painter.setOpacity(1.0)
    painter.setPen(QtGui.QColor(0, 0, 0, 0))
    try:
        state = _format_painter_state(painter)
        DIAG_LOGGER.info(
            "HLDBG_PAINTER: opacity=%s pen=%s brush=%s comp=%s hints=%s formats_count=%s",
            state["opacity"],
            state["pen"],
            state["brush"],
            state["composition"],
            state["render_hints"],
            len(selections),
        )
        if hasattr(layout, "lineCount"):
            line_count = layout.lineCount()
        else:
            line_count = 0
        logged_lines = 0
        for line_index in range(line_count):
            line = layout.lineAt(line_index)
            line_start = line.textStart()
            line_len = line.textLength()
            line_end = line_start + line_len
            overlap_start = max(selection.start, line_start)
            overlap_end = min(selection.end, line_end)
            if overlap_start >= overlap_end:
                continue
            local_start = overlap_start - line_start
            local_end = overlap_end - line_start
            raw_x1 = line.cursorToX(local_start)
            raw_x2 = line.cursorToX(local_end)

            def _cursor_x(value: object) -> Optional[float]:
                if isinstance(value, (tuple, list)) and value:
                    value = value[0]
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            x1 = _cursor_x(raw_x1)
            x2 = _cursor_x(raw_x2)
            left = min(x1, x2) if x1 is not None and x2 is not None else None
            right = max(x1, x2) if x1 is not None and x2 is not None else None
            clip_rect = None
            if left is not None and right is not None:
                clip_rect = QtCore.QRectF(
                    line.position().x() + left,
                    line.position().y(),
                    right - left,
                    line.height(),
                )
            DIAG_LOGGER.info(
                "HLDBG_LINE: phase=highlight_overlay line_index=%s line_start=%s line_len=%s "
                "overlap_start=%s overlap_end=%s cursor_x1_raw=%r cursor_x2_raw=%r "
                "x1=%s x2=%s clip_rect=%s",
                line_index,
                line_start,
                line_len,
                overlap_start,
                overlap_end,
                raw_x1,
                raw_x2,
                x1,
                x2,
                None
                if clip_rect is None
                else (clip_rect.x(), clip_rect.y(), clip_rect.width(), clip_rect.height()),
            )
            logged_lines += 1
            if logged_lines >= _MAX_HLDBG_LINES:
                break
    except Exception as exc:
        DIAG_LOGGER.info("HLDBG: logging_failed err=%r", exc)
    layout.draw(painter, QtCore.QPointF(0, 0), selections)
    painter.restore()


def _build_line_paths(
    lines: Iterable[QtGui.QTextLine], text: str, font: QtGui.QFont
) -> list[QtGui.QPainterPath]:
    paths: list[QtGui.QPainterPath] = []
    for line in lines:
        if not line.textLength():
            continue
        baseline = QtCore.QPointF(line.position().x(), line.position().y() + line.ascent())
        line_path = QtGui.QPainterPath()
        start = line.textStart()
        length = line.textLength()
        fragment = text[start : start + length]
        line_path.addText(baseline, font, fragment)
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
