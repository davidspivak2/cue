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

        self.choose_button = QtWidgets.QPushButton("Choose video...")
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
        self.clear_button.setToolTip("Clear selection")
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
        self.thumbnail_label.setText("Preview unavailable")
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
