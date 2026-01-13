from __future__ import annotations

from bisect import bisect_right
import re
from typing import Optional, Sequence

from PySide6 import QtCore, QtGui, QtWidgets

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
        self._position_seconds = 0.0
        self._karaoke_enabled = True
        self._highlight_color = QtGui.QColor(255, 214, 102)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

    def set_style(self, style: SubtitleStyle) -> None:
        self._style = style
        self.update()

    def set_cues(self, cues: Sequence[SrtCue]) -> None:
        self._cues = list(cues)
        self._cue_starts = [cue.start_seconds for cue in self._cues]
        self._active_cue = None
        self.update()

    def set_karaoke_enabled(self, enabled: bool) -> None:
        self._karaoke_enabled = enabled
        self.update()

    def clear(self) -> None:
        self._active_cue = None
        self.update()

    def update_position(self, seconds: float) -> None:
        self._position_seconds = seconds
        self._active_cue = self._find_active_cue(seconds)
        self.update()

    def _find_active_cue(self, seconds: float) -> Optional[SrtCue]:
        if not self._cues:
            return None
        index = bisect_right(self._cue_starts, seconds) - 1
        if index < 0:
            return None
        cue = self._cues[index]
        if cue.start_seconds <= seconds < cue.end_seconds:
            return cue
        return None

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

        metrics = QtGui.QFontMetricsF(font)
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()
        x = (self.width() - text_width) / 2
        baseline = self.height() - self._style.margin_v - metrics.descent()
        text_rect = QtCore.QRectF(x, baseline - metrics.ascent(), text_width, text_height)

        if self._style.box_enabled:
            padding = self._style.box_padding
            box_rect = text_rect.adjusted(-padding, -padding, padding, padding)
            alpha = max(0, min(255, round(255 * (self._style.box_opacity / 100))))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(box_rect, 6, 6)

        path = QtGui.QPainterPath()
        path.addText(x, baseline, font, text)

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

        if not self._karaoke_enabled:
            return

        duration = max(self._active_cue.end_seconds - self._active_cue.start_seconds, 0.0)
        if duration <= 0:
            return
        progress = (self._position_seconds - self._active_cue.start_seconds) / duration
        progress = max(0.0, min(progress, 1.0))
        highlight_width = text_rect.width() * progress
        if highlight_width <= 0:
            return

        if _is_rtl_text(text):
            clip_x = text_rect.right() - highlight_width
        else:
            clip_x = text_rect.left()
        clip_rect = QtCore.QRectF(clip_x, text_rect.top(), highlight_width, text_rect.height())

        painter.save()
        painter.setClipRect(clip_rect)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(self._highlight_color)
        painter.drawPath(path)
        painter.restore()
