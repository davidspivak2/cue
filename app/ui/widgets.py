from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .theme import ACCENT, BORDER, SURFACE, SURFACE_2
from .utils import format_duration


class AspectRatioFrame(QtWidgets.QFrame):
    def __init__(self, ratio: float = 16 / 9, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._ratio = ratio

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        if self._ratio <= 0:
            return super().heightForWidth(width)
        return int(width / self._ratio)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        width = 360
        return QtCore.QSize(width, self.heightForWidth(width))


class DropZone(QtWidgets.QFrame):
    video_dropped = QtCore.Signal(Path)
    choose_clicked = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragOver", False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        layout.setSpacing(12)

        headline = QtWidgets.QLabel("Drop a video here")
        headline.setObjectName("DropZoneHeadline")
        headline.setAlignment(QtCore.Qt.AlignCenter)

        subtext = QtWidgets.QLabel("or choose one from your computer")
        subtext.setObjectName("DropZoneSubtext")
        subtext.setAlignment(QtCore.Qt.AlignCenter)

        self.choose_button = QtWidgets.QPushButton("Choose video…")
        self.choose_button.clicked.connect(self.choose_clicked.emit)

        layout.addWidget(headline)
        layout.addWidget(subtext)
        layout.addWidget(self.choose_button)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            self._set_drag_over(True)
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent) -> None:  # noqa: N802
        self._set_drag_over(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        self._set_drag_over(False)
        urls = event.mimeData().urls()
        if urls:
            self.video_dropped.emit(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        background = QtGui.QColor(SURFACE_2 if self.property("dragOver") else SURFACE)
        painter.setBrush(background)
        pen_color = QtGui.QColor(ACCENT if self.property("dragOver") else BORDER)
        pen = QtGui.QPen(pen_color, 2)
        pen.setStyle(QtCore.Qt.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10, 10)

    def _set_drag_over(self, active: bool) -> None:
        self.setProperty("dragOver", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class VideoCard(QtWidgets.QWidget):
    clear_clicked = QtCore.Signal()
    video_dropped = QtCore.Signal(Path)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoCard")
        self.setAcceptDrops(True)
        self.setProperty("dragOver", False)
        self._thumbnail_pixmap: Optional[QtGui.QPixmap] = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        self.thumbnail_frame = AspectRatioFrame()
        self.thumbnail_frame.setObjectName("VideoCardThumbnail")
        self.thumbnail_frame.setMinimumHeight(180)
        self.thumbnail_frame.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        thumb_layout = QtWidgets.QGridLayout(self.thumbnail_frame)
        thumb_layout.setContentsMargins(0, 0, 0, 0)

        self.thumbnail_label = QtWidgets.QLabel()
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_label.setObjectName("VideoCardPreview")
        self.thumbnail_label.setMinimumHeight(180)

        self.clear_button = QtWidgets.QToolButton()
        self.clear_button.setObjectName("VideoCardClear")
        self.clear_button.setText("✕")
        self.clear_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.clear_button.setToolTip("Remove video")
        self.clear_button.setFixedSize(26, 26)
        self.clear_button.clicked.connect(self.clear_clicked.emit)

        thumb_layout.addWidget(self.thumbnail_label, 0, 0, 1, 1)
        thumb_layout.addWidget(
            self.clear_button,
            0,
            0,
            alignment=QtCore.Qt.AlignTop | QtCore.Qt.AlignRight,
        )
        self.clear_button.raise_()

        self.filename_label = QtWidgets.QLabel("")
        self.filename_label.setObjectName("VideoCardFilename")

        self.duration_label = QtWidgets.QLabel("—")
        self.duration_label.setObjectName("VideoCardDuration")

        layout.addWidget(self.thumbnail_frame)
        layout.addWidget(self.filename_label)
        layout.addWidget(self.duration_label)

        self._set_placeholder()

    def set_video(
        self,
        path: Path,
        duration_seconds: Optional[float],
        thumbnail_path: Optional[Path],
    ) -> None:
        self.filename_label.setText(path.name)
        self.duration_label.setText(format_duration(duration_seconds))

        if thumbnail_path and thumbnail_path.exists():
            pixmap = QtGui.QPixmap(str(thumbnail_path))
        else:
            pixmap = QtGui.QPixmap()

        if pixmap.isNull():
            self._set_placeholder()
        else:
            self._thumbnail_pixmap = pixmap
            self._update_thumbnail()

    def clear(self) -> None:
        self.filename_label.setText("")
        self.duration_label.setText("—")
        self._set_placeholder()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            self._set_drag_over(True)
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent) -> None:  # noqa: N802
        self._set_drag_over(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        self._set_drag_over(False)
        urls = event.mimeData().urls()
        if urls:
            self.video_dropped.emit(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()


    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_thumbnail()

    def _set_placeholder(self) -> None:
        self._thumbnail_pixmap = None
        self.thumbnail_label.setPixmap(QtGui.QPixmap())
        self.thumbnail_label.setText("Preview not available")
        self.thumbnail_label.setObjectName("VideoCardPlaceholder")
        self._refresh_label_style()

    def _update_thumbnail(self) -> None:
        if not self._thumbnail_pixmap or self._thumbnail_pixmap.isNull():
            return
        self.thumbnail_label.setText("")
        self.thumbnail_label.setObjectName("VideoCardPreview")
        scaled = self._thumbnail_pixmap.scaled(
            self.thumbnail_label.size(),
            QtCore.Qt.KeepAspectRatioByExpanding,
            QtCore.Qt.SmoothTransformation,
        )
        self.thumbnail_label.setPixmap(scaled)
        self._refresh_label_style()

    def _refresh_label_style(self) -> None:
        self.thumbnail_label.style().unpolish(self.thumbnail_label)
        self.thumbnail_label.style().polish(self.thumbnail_label)
        self.thumbnail_label.update()

    def _set_drag_over(self, active: bool) -> None:
        self.setProperty("dragOver", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class SaveToRow(QtWidgets.QWidget):
    change_clicked = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._path_text = ""

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.label = QtWidgets.QLabel("Save to")
        self.label.setObjectName("SaveToLabel")

        self.path_label = QtWidgets.QLabel("")
        self.path_label.setObjectName("SaveToPath")
        self.path_label.setToolTip("")
        self.path_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred,
        )

        self.change_button = QtWidgets.QPushButton("Change…")
        self.change_button.setObjectName("SaveToChange")
        self.change_button.setFlat(True)
        self.change_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.change_button.clicked.connect(self.change_clicked.emit)

        layout.addWidget(self.label)
        layout.addWidget(self.path_label, stretch=1)
        layout.addWidget(self.change_button)

    def set_path(self, path: Optional[Path]) -> None:
        if path is None:
            self._path_text = ""
            self.path_label.setText("")
            self.path_label.setToolTip("")
            return
        self._path_text = str(path)
        self.path_label.setToolTip(self._path_text)
        self._update_elided_text()

    def set_change_enabled(self, enabled: bool) -> None:
        self.change_button.setEnabled(enabled)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        if not self._path_text:
            self.path_label.setText("")
            return
        metrics = self.path_label.fontMetrics()
        elided = metrics.elidedText(
            self._path_text,
            QtCore.Qt.ElideMiddle,
            max(0, self.path_label.width()),
        )
        self.path_label.setText(elided)


class ElidedLabel(QtWidgets.QLabel):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._full_text = ""

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        if not self._full_text:
            self.setText("")
            return
        metrics = self.fontMetrics()
        elided = metrics.elidedText(
            self._full_text,
            QtCore.Qt.ElideMiddle,
            max(0, self.width()),
        )
        self.setText(elided)


class ElidedLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._full_text = ""

    def set_full_text(self, text: Optional[str], *, placeholder: str = "") -> None:
        self._full_text = text or ""
        if not self._full_text:
            self.setText("")
            if placeholder:
                self.setPlaceholderText(placeholder)
            self.setToolTip("")
            return
        self.setPlaceholderText("")
        self.setToolTip(self._full_text)
        self._update_elided_text()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        if not self._full_text:
            return
        metrics = self.fontMetrics()
        available = max(0, self.width() - 10)
        elided = metrics.elidedText(
            self._full_text,
            QtCore.Qt.ElideMiddle,
            available,
        )
        self.setText(elided)


class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ClickableFrame(QtWidgets.QFrame):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ColorSwatch(QtWidgets.QFrame):
    clicked = QtCore.Signal()

    def __init__(
        self,
        color: Optional[str] = None,
        *,
        multicolor: bool = False,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._color = color
        self._multicolor = multicolor
        self.setFixedSize(28, 28)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.setProperty("active", False)

    @property
    def color(self) -> Optional[str]:
        return self._color

    def set_color(self, color: Optional[str]) -> None:
        self._color = color
        self.update()

    def set_active(self, active: bool) -> None:
        if self.property("active") == active:
            return
        self.setProperty("active", active)
        self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        if self._multicolor:
            gradient = QtGui.QLinearGradient(rect.topLeft(), rect.topRight())
            gradient.setColorAt(0.0, QtGui.QColor("#F43F5E"))
            gradient.setColorAt(0.33, QtGui.QColor("#F59E0B"))
            gradient.setColorAt(0.66, QtGui.QColor("#22C55E"))
            gradient.setColorAt(1.0, QtGui.QColor("#3B82F6"))
            painter.setBrush(gradient)
        else:
            painter.setBrush(QtGui.QColor(self._color or "#000000"))
        border_color = QtGui.QColor(ACCENT if self.property("active") else BORDER)
        pen = QtGui.QPen(border_color, 2 if self.property("active") else 1)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 6, 6)


class ColorSwatchRow(QtWidgets.QWidget):
    colorChanged = QtCore.Signal(str)

    def __init__(
        self,
        recommended_colors: list[str],
        *,
        initial_color: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
        dialog_title: str = "Pick color…",
    ) -> None:
        super().__init__(parent)
        if len(recommended_colors) != 3:
            raise ValueError("ColorSwatchRow expects exactly three recommended colors.")
        self._recommended_colors = [color.upper() for color in recommended_colors]
        self._custom_color: Optional[str] = None
        self._dialog_title = dialog_title
        initial = (initial_color or self._recommended_colors[0]).upper()
        if initial not in self._recommended_colors:
            self._custom_color = initial

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._swatches: list[ColorSwatch] = []
        swatch_one = ColorSwatch(self._custom_color or self._recommended_colors[0])
        self._swatches.append(swatch_one)
        for color in self._recommended_colors:
            self._swatches.append(ColorSwatch(color))
        self._more_swatch = ColorSwatch(multicolor=True)
        self._swatches.append(self._more_swatch)

        for index, swatch in enumerate(self._swatches):
            layout.addWidget(swatch)
            if swatch is self._more_swatch:
                swatch.setToolTip("More colors…")
                swatch.clicked.connect(self._choose_custom_color)
            else:
                swatch.clicked.connect(
                    lambda _, swatch_index=index: self._apply_swatch_color(swatch_index)
                )

        self.set_color(initial)

    @property
    def current_color(self) -> str:
        color = self._custom_color or self._recommended_colors[0]
        for index, swatch in enumerate(self._swatches[:-1]):
            if swatch.property("active"):
                return self._color_for_index(index)
        return color

    def set_color(self, color: str) -> None:
        hex_color = color.upper()
        if hex_color not in self._recommended_colors:
            self._custom_color = hex_color
            self._swatches[0].set_color(hex_color)
        self._set_active_from_color(hex_color)

    def _color_for_index(self, index: int) -> str:
        if index == 0:
            return (self._custom_color or self._recommended_colors[0]).upper()
        return self._recommended_colors[index - 1]

    def _apply_swatch_color(self, index: int) -> None:
        color = self._color_for_index(index)
        self._set_active_from_color(color, active_index=index)
        self.colorChanged.emit(color)

    def _set_active_from_color(self, color: str, active_index: Optional[int] = None) -> None:
        if active_index is None:
            if color == (self._custom_color or "").upper():
                active_index = 0
            elif color in self._recommended_colors:
                active_index = self._recommended_colors.index(color) + 1
            else:
                active_index = 0
        for idx, swatch in enumerate(self._swatches[:-1]):
            swatch.set_active(idx == active_index)

    def _choose_custom_color(self) -> None:
        current = QtGui.QColor(self.current_color)
        color = QtWidgets.QColorDialog.getColor(current, self, self._dialog_title)
        if not color.isValid():
            return
        hex_value = color.name().upper()
        if hex_value not in self._recommended_colors:
            self._custom_color = hex_value
            self._swatches[0].set_color(hex_value)
            self._set_active_from_color(hex_value, active_index=0)
        else:
            self._set_active_from_color(hex_value)
        self.colorChanged.emit(hex_value)


class SavingToLine(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.prefix_label = QtWidgets.QLabel("Saving to:")
        self.prefix_label.setObjectName("SavingToPrefix")

        self.path_label = ElidedLabel()
        self.path_label.setObjectName("SavingToPath")
        self.path_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred,
        )

        layout.addWidget(self.prefix_label)
        layout.addWidget(self.path_label, stretch=1)

    def set_path(self, path_text: str) -> None:
        self.path_label.set_full_text(path_text)
