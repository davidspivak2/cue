from __future__ import annotations

from bisect import bisect_right
import re
from typing import Callable, Optional, Sequence

from PySide6 import QtCore, QtGui, QtWidgets

from app.karaoke_utils import HIGHLIGHT_COLOR_RGB, build_highlight_spans
from app.subtitle_style import DEFAULT_FONT_NAME, SubtitleStyle
from app.srt_utils import SrtCue

_RTL_RE = re.compile(r"[\u0590-\u08FF]")


def _is_rtl_text(text: str) -> bool:
    return bool(_RTL_RE.search(text))


class PreviewSubtitleOverlay(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._style: Optional[SubtitleStyle] = None
        self._cues: list[SrtCue] = []
        self._cue_starts: list[float] = []
        self._active_cue: Optional[SrtCue] = None
        self._active_cue_index: Optional[int] = None
        self._position_seconds = 0.0
        self._karaoke_enabled = True
        self._highlight_color = QtGui.QColor(*HIGHLIGHT_COLOR_RGB)
        self._logger: Optional[Callable[[str], None]] = None
        self._karaoke_fallback_logged = False
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

    def set_style(self, style: SubtitleStyle) -> None:
        self._style = style
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

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        del event
        if not self._active_cue or not self._style:
            return
        text = self._active_cue.text.strip()
        if not text:
            return

        painter = QtGui.QPainter(self)
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
                return
            progress = (self._position_seconds - self._active_cue.start_seconds) / duration
            highlight_spans = build_highlight_spans(text, progress)
            if not highlight_spans:
                return
            highlight_layout = self._build_highlight_layout(text, font, layout, highlight_spans)
            if not highlight_layout:
                return
            painter.save()
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(self._highlight_color)
            highlight_layout.draw(painter, origin)
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
            QtCore.Qt.RightToLeft if _is_rtl_text(text) else QtCore.Qt.LeftToRight
        )
        max_width = max(0.0, self.width() * 0.9)
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
        origin_x = (self.width() - max_width) / 2 if max_width > 0 else 0.0
        origin_y = self.height() - self._style.margin_v - height
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
                painter.setBrush(QtGui.QColor(255, 255, 255))
                painter.drawPath(path)
            else:
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QColor(255, 255, 255))
                painter.drawPath(path)

    def _build_highlight_layout(
        self,
        text: str,
        font: QtGui.QFont,
        base_layout: QtGui.QTextLayout,
        highlight_spans: list[tuple[int, int]],
    ) -> Optional[QtGui.QTextLayout]:
        if not highlight_spans:
            return None
        option = base_layout.textOption()
        layout = QtGui.QTextLayout(text, font)
        layout.setTextOption(option)
        format_ranges: list[QtGui.QTextLayout.FormatRange] = []
        for start, end in highlight_spans:
            if end <= start:
                continue
            fmt = QtGui.QTextCharFormat()
            fmt.setForeground(self._highlight_color)
            fmt_range = QtGui.QTextLayout.FormatRange()
            fmt_range.start = start
            fmt_range.length = end - start
            fmt_range.format = fmt
            format_ranges.append(fmt_range)
        if not format_ranges:
            return None
        layout.setFormats(format_ranges)
        layout.beginLayout()
        height = 0.0
        max_width = max(0.0, self.width() * 0.9)
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max_width)
            line_width = line.naturalTextWidth()
            line_x = (max_width - line_width) / 2 if max_width > 0 else 0.0
            line.setPosition(QtCore.QPointF(line_x, height))
            height += line.height()
        layout.endLayout()
        return layout
