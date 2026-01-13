from __future__ import annotations

from bisect import bisect_right
from typing import Callable, Optional, Sequence

from PySide6 import QtCore, QtGui, QtWidgets

from app.karaoke_utils import (
    DEFAULT_HIGHLIGHT_COLOR_HEX,
    highlight_rgb_from_hex,
    is_rtl_text,
    iter_token_spans,
)
from app.subtitle_style import DEFAULT_FONT_NAME, SubtitleStyle
from app.srt_utils import SrtCue


class PreviewGraphicsView(QtWidgets.QGraphicsView):
    resized = QtCore.Signal(QtCore.QSize)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.resized.emit(event.size())


class PreviewSubtitleItem(QtWidgets.QGraphicsObject):
    def __init__(self) -> None:
        super().__init__()
        self._style: Optional[SubtitleStyle] = None
        self._cues: list[SrtCue] = []
        self._cue_starts: list[float] = []
        self._active_cue: Optional[SrtCue] = None
        self._active_cue_index: Optional[int] = None
        self._position_seconds = 0.0
        self._karaoke_enabled = True
        self._highlight_color = QtGui.QColor(*highlight_rgb_from_hex(DEFAULT_HIGHLIGHT_COLOR_HEX))
        self._highlight_mode = "text"
        self._highlight_bg_opacity = 40
        self._logger: Optional[Callable[[str], None]] = None
        self._karaoke_fallback_logged = False
        self._viewport_rect = QtCore.QRectF()

    def boundingRect(self) -> QtCore.QRectF:  # noqa: N802
        return self._viewport_rect

    def set_viewport_rect(self, rect: QtCore.QRectF) -> None:
        if rect == self._viewport_rect:
            return
        self.prepareGeometryChange()
        self._viewport_rect = rect
        self.update()

    def set_style(self, style: SubtitleStyle) -> None:
        self._style = style
        self.update()

    def set_highlight_color(self, hex_color: str) -> None:
        rgb = highlight_rgb_from_hex(hex_color)
        self._highlight_color = QtGui.QColor(*rgb)
        self.update()

    def set_highlight_mode(self, mode: str) -> None:
        if mode not in {"text", "text+bg"}:
            mode = "text"
        self._highlight_mode = mode
        self.update()

    def set_highlight_bg_opacity(self, opacity: int) -> None:
        self._highlight_bg_opacity = max(0, min(100, opacity))
        self.update()

    def set_logger(self, logger: Callable[[str], None]) -> None:
        self._logger = logger

    def set_cues(self, cues: Sequence[SrtCue]) -> None:
        self._cues = list(cues)
        self._cue_starts = [cue.start_seconds for cue in self._cues]
        self._active_cue = None
        self._active_cue_index = None
        self._karaoke_fallback_logged = False
        self.update()

    def set_karaoke_enabled(self, enabled: bool) -> None:
        self._karaoke_enabled = enabled
        self.update()

    def clear(self) -> None:
        self._active_cue = None
        self._active_cue_index = None
        self.update()

    def update_position(self, seconds: float) -> None:
        self._position_seconds = seconds
        self._active_cue, self._active_cue_index = self._find_active_cue(seconds)
        self.update()

    def active_cue_index(self) -> Optional[int]:
        return self._active_cue_index

    def _find_active_cue(self, seconds: float) -> tuple[Optional[SrtCue], Optional[int]]:
        if not self._cues:
            return None, None
        index = bisect_right(self._cue_starts, seconds) - 1
        if index < 0:
            return None, None
        cue = self._cues[index]
        if cue.start_seconds <= seconds < cue.end_seconds:
            return cue, index
        return None, None

    def _log_karaoke_fallback(self, message: str) -> None:
        if self._karaoke_fallback_logged:
            return
        if self._logger:
            self._logger(message)
        self._karaoke_fallback_logged = True

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionGraphicsItem, widget: Optional[QtWidgets.QWidget] = None) -> None:  # noqa: N802
        del option
        del widget
        if not self._active_cue or not self._style:
            return
        text = self._active_cue.text.strip()
        if not text:
            return

        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

        font = QtGui.QFont(DEFAULT_FONT_NAME)
        font.setPointSize(self._style.font_size)
        painter.setFont(font)

        layout_data = self._build_layout(text, font)
        if not layout_data:
            return
        layout, lines, text_rect, origin = layout_data

        if self._style.box_enabled:
            padding = self._style.box_padding
            box_rect = text_rect.adjusted(-padding, -padding, padding, padding)
            alpha = max(0, min(255, round(255 * (self._style.box_opacity / 100))))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(box_rect, 6, 6)

        self._draw_text_with_outline(painter, font, text, lines, origin)

        if not self._karaoke_enabled:
            return

        try:
            duration = max(self._active_cue.end_seconds - self._active_cue.start_seconds, 0.0)
            if duration <= 0:
                self._log_karaoke_fallback("Karaoke highlight skipped: non-positive duration")
                return
            progress = (self._position_seconds - self._active_cue.start_seconds) / duration
            highlight_width = self._measure_highlight_width(text, font, progress, text_rect.width())
            if highlight_width <= 0:
                self._log_karaoke_fallback("Karaoke highlight skipped: no highlight width")
                return
            if is_rtl_text(text):
                clip_x = text_rect.right() - highlight_width
            else:
                clip_x = text_rect.left()
            clip_rect = QtCore.QRectF(clip_x, text_rect.top(), highlight_width, text_rect.height())
            painter.save()
            painter.setClipRect(clip_rect)
            if self._highlight_mode == "text+bg":
                alpha = max(0, min(255, round(255 * (self._highlight_bg_opacity / 100))))
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QColor(0, 0, 0, alpha))
                painter.drawRect(clip_rect)
            self._draw_text_with_outline(
                painter,
                font,
                text,
                lines,
                origin,
                override_brush=self._highlight_color,
            )
            painter.restore()
        except Exception as exc:  # noqa: BLE001
            self._log_karaoke_fallback(f"Karaoke highlight fallback: {exc}")
            return

    def _build_layout(
        self,
        text: str,
        font: QtGui.QFont,
    ) -> Optional[
        tuple[
            QtGui.QTextLayout,
            list[QtGui.QTextLine],
            QtCore.QRectF,
            QtCore.QPointF,
        ]
    ]:
        if not text:
            return None
        option = QtGui.QTextOption()
        option.setAlignment(QtCore.Qt.AlignHCenter)
        option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        option.setTextDirection(
            QtCore.Qt.RightToLeft if is_rtl_text(text) else QtCore.Qt.LeftToRight
        )
        max_width = max(0.0, self._viewport_rect.width() * 0.9)
        layout = QtGui.QTextLayout(text, font)
        layout.setTextOption(option)
        layout.beginLayout()
        lines: list[QtGui.QTextLine] = []
        height = 0.0
        max_line_width = 0.0
        min_x = None
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max_width)
            line_width = line.naturalTextWidth()
            line_x = (max_width - line_width) / 2 if max_width > 0 else 0.0
            line.setPosition(QtCore.QPointF(line_x, height))
            height += line.height()
            max_line_width = max(max_line_width, line_width)
            min_x = line_x if min_x is None else min(min_x, line_x)
            lines.append(line)
        layout.endLayout()
        if not lines:
            return None
        origin_x = self._viewport_rect.x() + (self._viewport_rect.width() - max_width) / 2
        origin_y = self._viewport_rect.y() + self._viewport_rect.height() - self._style.margin_v - height
        origin = QtCore.QPointF(origin_x, origin_y)
        left = origin_x + (min_x or 0.0)
        text_rect = QtCore.QRectF(left, origin_y, max_line_width, height)
        return layout, lines, text_rect, origin

    def _draw_text_with_outline(
        self,
        painter: QtGui.QPainter,
        font: QtGui.QFont,
        text: str,
        lines: list[QtGui.QTextLine],
        origin: QtCore.QPointF,
        *,
        override_brush: Optional[QtGui.QBrush] = None,
    ) -> None:
        if not lines:
            return
        for line in lines:
            start = line.textStart()
            length = line.textLength()
            line_text = text[start : start + length]
            x = origin.x() + line.position().x()
            y = origin.y() + line.position().y() + line.ascent()
            path = QtGui.QPainterPath()
            path.addText(x, y, font, line_text)
            if self._style.shadow > 0:
                shadow_path = QtGui.QPainterPath(path)
                shadow_path.translate(self._style.shadow, self._style.shadow)
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QColor(0, 0, 0, 160))
                painter.drawPath(shadow_path)
            if self._style.outline > 0:
                outline_width = max(1.0, self._style.outline * 2.0)
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), outline_width))
                painter.setBrush(override_brush or QtGui.QColor(255, 255, 255))
                painter.drawPath(path)
            else:
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(override_brush or QtGui.QColor(255, 255, 255))
                painter.drawPath(path)

    def _measure_highlight_width(
        self,
        text: str,
        font: QtGui.QFont,
        progress: float,
        max_width: float,
    ) -> float:
        spans = list(iter_token_spans(text))
        if not spans:
            return 0.0
        clamped = max(0.0, min(progress, 1.0))
        completed = int(clamped * len(spans))
        if completed <= 0:
            return 0.0
        end_index = spans[completed - 1][1]
        substring = text[:end_index]
        metrics = QtGui.QFontMetricsF(font)
        width = metrics.horizontalAdvance(substring.replace("\n", " "))
        return min(width, max_width)
