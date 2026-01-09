from __future__ import annotations

if __name__ == "__main__" and __package__ is None:
    import os
    import sys

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import datetime
import json
import faulthandler
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.ffmpeg_utils import (
    ensure_ffmpeg_available,
    get_ffmpeg_missing_message,
    get_runtime_mode,
    resolve_ffmpeg_paths,
)
from app.ui.state import AppState
from app.ui.theme import apply_theme
from app.ui.utils import generate_thumbnail, get_media_duration_seconds
from app.ui.widgets import DropZone, SaveToRow, VideoCard
from app.workers import BurnInSettings, TaskType, TranscriptionSettings, Worker

VIDEO_FILTER = "Video Files (*.mp4 *.mkv *.mov *.m4v);;All Files (*.*)"
DEFAULT_SUBTITLE_EDIT_PATH = Path(r"C:\Program Files\Subtitle Edit\SubtitleEdit.exe")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, logger: logging.Logger, log_path: Path, log_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("Hebrew Subtitles")
        self.setMinimumSize(720, 640)
        self.setAcceptDrops(True)

        self._logger = logger
        self._log_path = log_path
        self._log_dir = log_dir
        self._video_path: Optional[Path] = None
        self._output_dir: Optional[Path] = None
        self._last_srt_path: Optional[Path] = None
        self._last_output_video: Optional[Path] = None
        self._worker_thread: Optional[QtCore.QThread] = None
        self._worker: Optional[Worker] = None
        self._ffmpeg_available = False
        self._ffprobe_available = False
        self._subtitles_reviewed = False
        self._subtitle_edit_path = self._load_subtitle_edit_path()
        self._state = AppState.EMPTY

        self._build_ui()
        self._log_diagnostics()
        self.set_state(AppState.EMPTY)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        self.drop_zone = DropZone()
        self.video_card = VideoCard()
        self.save_to_row = SaveToRow()

        self.generate_button = QtWidgets.QPushButton("Create subtitles")
        self.review_button = QtWidgets.QPushButton("Edit in Subtitle Edit")
        self.burn_button = QtWidgets.QPushButton("Export video with subtitles")
        self.cancel_button = QtWidgets.QPushButton("Cancel")

        self.ready_open_srt_button = QtWidgets.QPushButton("Open subtitles")
        self.ready_open_folder_button = QtWidgets.QPushButton("Open folder")

        self.done_open_video_button = QtWidgets.QPushButton("Play video")
        self.done_open_folder_button = QtWidgets.QPushButton("Open folder")
        self.done_edit_button = QtWidgets.QPushButton("Edit subtitles and export again")

        for button in (
            self.ready_open_srt_button,
            self.ready_open_folder_button,
        ):
            button.setFlat(True)
            button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.done_edit_button.setFlat(True)
        self.done_edit_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.filter_checkbox = QtWidgets.QCheckBox("Improve voice clarity")
        self.filter_checkbox.setChecked(True)

        style_group = QtWidgets.QGroupBox("Subtitle style")
        style_layout = QtWidgets.QGridLayout(style_group)
        self.font_combo = QtWidgets.QComboBox()
        self.font_combo.addItems(["Segoe UI", "Tahoma", "Arial"])
        self.font_size_spin = QtWidgets.QSpinBox()
        self.font_size_spin.setRange(10, 72)
        self.font_size_spin.setValue(28)
        self.outline_spin = QtWidgets.QSpinBox()
        self.outline_spin.setRange(0, 10)
        self.outline_spin.setValue(1)
        self.shadow_spin = QtWidgets.QSpinBox()
        self.shadow_spin.setRange(0, 10)
        self.shadow_spin.setValue(0)
        self.margin_spin = QtWidgets.QSpinBox()
        self.margin_spin.setRange(0, 200)
        self.margin_spin.setValue(30)

        style_layout.addWidget(QtWidgets.QLabel("Font"), 0, 0)
        style_layout.addWidget(self.font_combo, 0, 1)
        style_layout.addWidget(QtWidgets.QLabel("Size"), 0, 2)
        style_layout.addWidget(self.font_size_spin, 0, 3)
        style_layout.addWidget(QtWidgets.QLabel("Outline"), 1, 0)
        style_layout.addWidget(self.outline_spin, 1, 1)
        style_layout.addWidget(QtWidgets.QLabel("Shadow"), 1, 2)
        style_layout.addWidget(self.shadow_spin, 1, 3)
        style_layout.addWidget(QtWidgets.QLabel("Bottom margin"), 2, 0)
        style_layout.addWidget(self.margin_spin, 2, 1)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self._apply_progress_bar_style()

        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold;")

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(220)

        self.stack = QtWidgets.QStackedWidget()
        self._page_index = {
            AppState.EMPTY: self.stack.addWidget(self._build_empty_page()),
            AppState.VIDEO_SELECTED: self.stack.addWidget(self._build_video_selected_page()),
            AppState.WORKING: self.stack.addWidget(self._build_working_page()),
            AppState.SUBTITLES_READY: self.stack.addWidget(self._build_subtitles_ready_page()),
            AppState.EXPORT_DONE: self.stack.addWidget(self._build_done_page()),
        }
        layout.addWidget(self.save_to_row)
        layout.addWidget(self.stack)

        self.details_toggle = QtWidgets.QToolButton()
        self.details_toggle.setText("Show details")
        self.details_toggle.setCheckable(True)
        self.details_toggle.setArrowType(QtCore.Qt.RightArrow)
        self.details_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        layout.addWidget(self.details_toggle)

        self.details_panel = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(self.details_panel)

        advanced_group = QtWidgets.QGroupBox("Options")
        advanced_layout = QtWidgets.QVBoxLayout(advanced_group)
        advanced_layout.addWidget(self.filter_checkbox)
        advanced_layout.addWidget(style_group)
        details_layout.addWidget(advanced_group)

        log_group = QtWidgets.QGroupBox("Details")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        log_layout.addWidget(self.log_box)
        self.open_log_button = QtWidgets.QPushButton("Open details file")
        log_layout.addWidget(self.open_log_button)
        details_layout.addWidget(log_group)
        details_layout.addStretch()

        self.details_panel.setVisible(False)
        layout.addWidget(self.details_panel)

        self.setCentralWidget(central)

        self.drop_zone.choose_clicked.connect(self._browse_video)
        self.drop_zone.video_dropped.connect(self._handle_video_dropped)
        self.video_card.clear_clicked.connect(self._clear_video)
        self.video_card.video_dropped.connect(self._handle_video_dropped)
        self.save_to_row.change_clicked.connect(self._change_output_dir)
        self.generate_button.clicked.connect(self._on_generate)
        self.review_button.clicked.connect(self._on_review)
        self.burn_button.clicked.connect(self._on_burn)
        self.cancel_button.clicked.connect(self._on_cancel)
        self.ready_open_srt_button.clicked.connect(self._open_srt)
        self.ready_open_folder_button.clicked.connect(self._open_folder)
        self.done_open_video_button.clicked.connect(self._open_output_video)
        self.done_open_folder_button.clicked.connect(self._open_folder)
        self.done_edit_button.clicked.connect(self._edit_subtitles_again)
        self.open_log_button.clicked.connect(self._open_log_file)
        self.details_toggle.toggled.connect(self._toggle_details)

    def _build_empty_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.addStretch()
        layout.addWidget(self.drop_zone)
        layout.addStretch()
        return page

    def _build_video_selected_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.addWidget(self.video_card)

        action_layout = QtWidgets.QHBoxLayout()
        action_layout.addStretch()
        action_layout.addWidget(self.generate_button)
        action_layout.addStretch()
        layout.addLayout(action_layout)
        layout.addStretch()
        return page

    def _build_working_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.addStretch()
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        cancel_layout = QtWidgets.QHBoxLayout()
        cancel_layout.addStretch()
        cancel_layout.addWidget(self.cancel_button)
        cancel_layout.addStretch()
        layout.addLayout(cancel_layout)
        layout.addStretch()
        return page

    def _build_subtitles_ready_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        title = QtWidgets.QLabel("Subtitles are ready")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        primary_layout = QtWidgets.QHBoxLayout()
        primary_layout.addStretch()
        primary_layout.addWidget(self.review_button)
        primary_layout.addStretch()
        layout.addLayout(primary_layout)

        secondary_layout = QtWidgets.QHBoxLayout()
        secondary_layout.addStretch()
        secondary_layout.addWidget(self.burn_button)
        secondary_layout.addStretch()
        layout.addLayout(secondary_layout)

        links_layout = QtWidgets.QHBoxLayout()
        links_layout.addStretch()
        links_layout.addWidget(self.ready_open_srt_button)
        links_layout.addWidget(self.ready_open_folder_button)
        links_layout.addStretch()
        layout.addLayout(links_layout)
        layout.addStretch()
        return page

    def _build_done_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        title = QtWidgets.QLabel("Your video is ready")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        primary_layout = QtWidgets.QHBoxLayout()
        primary_layout.addStretch()
        primary_layout.addWidget(self.done_open_video_button)
        primary_layout.addStretch()
        layout.addLayout(primary_layout)

        secondary_layout = QtWidgets.QHBoxLayout()
        secondary_layout.addStretch()
        secondary_layout.addWidget(self.done_open_folder_button)
        secondary_layout.addStretch()
        layout.addLayout(secondary_layout)

        tertiary_layout = QtWidgets.QHBoxLayout()
        tertiary_layout.addStretch()
        tertiary_layout.addWidget(self.done_edit_button)
        tertiary_layout.addStretch()
        layout.addLayout(tertiary_layout)
        layout.addStretch()
        return page

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if self._state == AppState.WORKING:
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        if self._state == AppState.WORKING:
            return
        urls = event.mimeData().urls()
        if urls:
            self._handle_video_dropped(Path(urls[0].toLocalFile()))

    def set_state(self, state: AppState) -> None:
        self._state = state
        page_index = self._page_index.get(state, 0)
        self.stack.setCurrentIndex(page_index)
        self._update_ui_state(idle=state != AppState.WORKING)

    def _browse_video(self) -> None:
        if self._state == AppState.WORKING:
            return
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose video…", "", VIDEO_FILTER
        )
        if file_path:
            self._set_video_path(Path(file_path))

    def _set_video_path(self, path: Path) -> None:
        if not path.exists():
            return
        self._reset_video_state()
        self._video_path = path
        self._set_output_dir(path.parent)
        self._log(f"Selected video: {path}")
        duration_seconds = get_media_duration_seconds(path)
        thumbnail_path = generate_thumbnail(path, duration_seconds, self._logger)
        self.video_card.set_video(path, duration_seconds, thumbnail_path)
        self._probe_video(path)
        self.set_state(AppState.VIDEO_SELECTED)

    def _handle_video_dropped(self, path: Path) -> None:
        if self._state == AppState.WORKING:
            return
        self._set_video_path(path)

    def _probe_video(self, path: Path) -> None:
        try:
            _, ffprobe_path, _ = ensure_ffmpeg_available()
        except FileNotFoundError as exc:
            self._log(str(exc))
            return
        if not ffprobe_path:
            self._log("Warning: video details tool not found; skipping checks.")
            return

        command = [
            str(ffprobe_path),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        try:
            result = QtCore.QProcess.execute(command[0], command[1:])
            if result != 0:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Video check warning",
                    "We couldn't read details for this file. It may still work, but "
                    "please confirm the file is valid.",
                )
        except Exception as exc:  # noqa: BLE001
            self._log(f"Video check failed: {exc}")

    def _on_generate(self) -> None:
        if not self._video_path:
            QtWidgets.QMessageBox.warning(self, "No video selected", "Choose a video first.")
            return
        try:
            ensure_ffmpeg_available()
        except FileNotFoundError as exc:
            QtWidgets.QMessageBox.critical(self, "Video tools missing", str(exc))
            return

        self._subtitles_reviewed = False
        settings = TranscriptionSettings(apply_audio_filter=self.filter_checkbox.isChecked())
        self._start_worker(TaskType.GENERATE_SRT, self._video_path, None, settings, None)

    def _on_review(self) -> None:
        if not self._video_path:
            QtWidgets.QMessageBox.warning(self, "No video selected", "Choose a video first.")
            return

        srt_path = self._get_default_srt_path()
        if not self._is_srt_ready(srt_path):
            QtWidgets.QMessageBox.information(
                self, "Subtitles not ready", "Create subtitles first."
            )
            return

        subtitle_edit_path = self._resolve_subtitle_edit_path()
        if not subtitle_edit_path:
            subtitle_edit_path = self._prompt_for_subtitle_edit()
            if not subtitle_edit_path:
                return
            self._subtitle_edit_path = subtitle_edit_path
            self._save_subtitle_edit_path(subtitle_edit_path)

        arguments = [str(srt_path), f"/video:{self._video_path}"]
        started = QtCore.QProcess.startDetached(str(subtitle_edit_path), arguments)
        if isinstance(started, tuple):
            started = started[0]
        if not started:
            QtWidgets.QMessageBox.critical(
                self,
                "Couldn't open Subtitle Edit",
                "Subtitle Edit couldn't be opened. Please check the app path.",
            )
            return

        self._subtitles_reviewed = True
        self._update_ui_state(idle=True)

    def _on_burn(self) -> None:
        if not self._video_path:
            QtWidgets.QMessageBox.warning(self, "No video selected", "Choose a video first.")
            return
        if not self._subtitles_reviewed:
            QtWidgets.QMessageBox.information(
                self,
                "Edit before exporting",
                "Edit subtitles before exporting the video.",
            )
            return
        try:
            ensure_ffmpeg_available()
        except FileNotFoundError as exc:
            QtWidgets.QMessageBox.critical(self, "Video tools missing", str(exc))
            return

        srt_path = self._get_default_srt_path()
        if not self._is_srt_ready(srt_path):
            QtWidgets.QMessageBox.information(
                self, "Subtitles not ready", "Create subtitles first."
            )
            return

        settings = BurnInSettings(
            font_name=self.font_combo.currentText(),
            font_size=self.font_size_spin.value(),
            outline=self.outline_spin.value(),
            shadow=self.shadow_spin.value(),
            margin_v=self.margin_spin.value(),
        )
        self._start_worker(TaskType.BURN_IN, self._video_path, srt_path, None, settings)

    def _start_worker(
        self,
        task_type: str,
        video_path: Path,
        srt_path: Optional[Path],
        transcription_settings: Optional[TranscriptionSettings],
        burnin_settings: Optional[BurnInSettings],
    ) -> None:
        if self._worker_thread:
            QtWidgets.QMessageBox.warning(self, "Please wait", "Another task is running.")
            return

        self.log_box.clear()
        self._log_ffmpeg_resolution()
        self._worker_thread = QtCore.QThread()
        output_dir = self._output_dir or video_path.parent
        self._worker = Worker(
            task_type=task_type,
            video_path=video_path,
            output_dir=output_dir,
            srt_path=srt_path,
            transcription_settings=transcription_settings,
            burnin_settings=burnin_settings,
        )
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.signals.log.connect(self._log)
        self._worker.signals.progress.connect(self._on_worker_progress)
        self._worker.signals.started.connect(self._on_worker_started)
        self._worker.signals.finished.connect(self._on_worker_finished)
        self._worker_thread.start()

        self._update_ui_state(idle=False)

    def _on_worker_started(self, status: str) -> None:
        self.status_label.setText(status)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("")
        self.set_state(AppState.WORKING)

    def _on_worker_finished(self, success: bool, message: str, payload: dict) -> None:
        task_type = self._worker.task_type if self._worker else None
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("Done")
        elif message == "Operation cancelled.":
            self.progress_bar.setValue(0)
            self.status_label.setText("Cancelled")
        else:
            self.progress_bar.setValue(0)
            self.status_label.setText("Ready")

        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
            self._worker = None

        if payload.get("srt_path"):
            candidate = Path(payload["srt_path"])
            self._last_srt_path = candidate if candidate.exists() else None
        if payload.get("output_path"):
            candidate = Path(payload["output_path"])
            self._last_output_video = candidate if candidate.exists() else None

        if success:
            if task_type == TaskType.GENERATE_SRT:
                self._subtitles_reviewed = False
                QtWidgets.QMessageBox.information(
                    self,
                    "Subtitles are ready",
                    "Subtitles are ready. Next: edit them in Subtitle Edit, then export the video.",
                )
                self.set_state(AppState.SUBTITLES_READY)
            else:
                QtWidgets.QMessageBox.information(self, "Your video is ready", message)
                self.set_state(AppState.EXPORT_DONE)
        else:
            if message == "Operation cancelled.":
                QtWidgets.QMessageBox.information(self, "Cancelled", message)
            elif message.startswith("Subtitles were not created"):
                QtWidgets.QMessageBox.critical(self, "Subtitles were not created", message)
            elif "Video processing failed" in message:
                QtWidgets.QMessageBox.critical(
                    self, "Video processing failed", "Video processing failed. Check details."
                )
            elif "Couldn't create subtitles" in message:
                self._show_transcription_error(message)
            else:
                QtWidgets.QMessageBox.critical(self, "Error", message)
            self.set_state(AppState.VIDEO_SELECTED if self._video_path else AppState.EMPTY)

    def _on_cancel(self) -> None:
        if self._worker:
            self._log("Cancelling task...")
            self._worker.cancel()

    def _edit_subtitles_again(self) -> None:
        self.set_state(AppState.SUBTITLES_READY)
        self._on_review()

    def _open_folder(self) -> None:
        if not self._output_dir:
            return
        os.startfile(self._output_dir)  # type: ignore[arg-type]

    def _open_srt(self) -> None:
        srt_path = self._get_default_srt_path()
        if self._is_srt_ready(srt_path):
            QtCore.QProcess.startDetached("notepad.exe", [str(srt_path)])
            return
        if not self._last_srt_path or not self._last_srt_path.exists():
            QtWidgets.QMessageBox.information(
                self, "Subtitles not ready", "Create subtitles first."
            )
            return
        QtCore.QProcess.startDetached("notepad.exe", [str(self._last_srt_path)])

    def _open_output_video(self) -> None:
        if not self._last_output_video or not self._last_output_video.exists():
            QtWidgets.QMessageBox.information(self, "Video not ready", "Export the video first.")
            return
        os.startfile(self._last_output_video)  # type: ignore[arg-type]

    def _open_log_file(self) -> None:
        if not self._log_path.exists():
            QtWidgets.QMessageBox.information(
                self, "Details file missing", "No details file found."
            )
            return
        QtCore.QProcess.startDetached("notepad.exe", [str(self._log_path)])

    def _log(self, message: str, show_in_ui: bool = True) -> None:
        self._logger.info(message)
        if not show_in_ui:
            return
        scrollbar = self.log_box.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 2
        old_value = scrollbar.value()
        self.log_box.appendPlainText(message)
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(old_value)

    def _on_worker_progress(self, percent: int, status: str) -> None:
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(status)

    def _refresh_ffmpeg_status(self) -> None:
        ffmpeg_path, ffprobe_path, _ = resolve_ffmpeg_paths()
        self._ffmpeg_available = ffmpeg_path is not None
        self._ffprobe_available = ffprobe_path is not None

    def _log_ffmpeg_resolution(self) -> None:
        ffmpeg_path, ffprobe_path, mode = resolve_ffmpeg_paths()
        if not ffmpeg_path:
            self._log(get_ffmpeg_missing_message())
            return

        self._log(f"Video tools resolver: mode={mode}, path={ffmpeg_path}")
        if ffprobe_path:
            self._log(f"Video details tool: {ffprobe_path}")
        else:
            self._log("Warning: video details tool not found; some checks may be skipped.")

    def _log_diagnostics(self) -> None:
        runtime_mode = get_runtime_mode()
        ffmpeg_path, _, _ = resolve_ffmpeg_paths()
        ffmpeg_display = str(ffmpeg_path) if ffmpeg_path else "NOT FOUND"
        app_version = getattr(sys.modules.get("__main__"), "__version__", "unknown")
        self._log(f"App version: {app_version}")
        self._log(f"OS: {platform.platform()}")
        self._log(
            "Diagnostics: "
            f"Python {sys.version.split()[0]} | mode: {runtime_mode} | video tools: {ffmpeg_display}"
        )
        self._log_ffmpeg_resolution()

    def _toggle_details(self, checked: bool) -> None:
        self.details_panel.setVisible(checked)
        arrow = QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow
        self.details_toggle.setArrowType(arrow)
        self.details_toggle.setText("Hide details" if checked else "Show details")

    def _update_details_visibility(self, *, idle: bool) -> None:
        show_toggle = idle and self._state == AppState.VIDEO_SELECTED
        if not show_toggle:
            self.details_toggle.blockSignals(True)
            self.details_toggle.setChecked(False)
            self.details_toggle.blockSignals(False)
            self.details_panel.setVisible(False)
        self.details_toggle.setVisible(show_toggle)

    def _show_transcription_error(self, details: Optional[str] = None) -> None:
        message = (
            "Couldn't create subtitles.\n"
            f"A details file was saved to:\n{self._log_path}"
        )
        if details:
            message = f"{message}\n\nDetails:\n{details}"
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Critical)
        box.setWindowTitle("Couldn't create subtitles")
        box.setText(message)
        open_log_button = box.addButton("Open details file", QtWidgets.QMessageBox.ActionRole)
        open_folder_button = box.addButton("Open Folder", QtWidgets.QMessageBox.ActionRole)
        box.addButton("OK", QtWidgets.QMessageBox.AcceptRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == open_log_button:
            self._open_log_file()
        elif clicked == open_folder_button:
            os.startfile(self._log_dir)  # type: ignore[arg-type]

    def _update_ui_state(self, *, idle: bool) -> None:
        self._refresh_ffmpeg_status()
        has_video = self._video_path is not None
        ffmpeg_ready = self._ffmpeg_available
        srt_ready = self._is_srt_ready(self._get_default_srt_path())
        can_generate = idle and has_video and ffmpeg_ready
        can_review = idle and has_video and srt_ready
        can_burn = (
            idle and has_video and ffmpeg_ready and srt_ready and self._subtitles_reviewed
        )
        can_open_srt = srt_ready or self._last_srt_path is not None
        can_open_video = self._last_output_video is not None

        self.drop_zone.setEnabled(idle and self._state == AppState.EMPTY)
        self.video_card.setEnabled(idle and self._state == AppState.VIDEO_SELECTED)
        self.save_to_row.setVisible(has_video)
        self.save_to_row.set_change_enabled(idle and has_video)
        self.generate_button.setEnabled(
            can_generate and self._state == AppState.VIDEO_SELECTED
        )
        self.review_button.setEnabled(can_review and self._state == AppState.SUBTITLES_READY)
        self.burn_button.setEnabled(can_burn and self._state == AppState.SUBTITLES_READY)
        self.cancel_button.setEnabled(self._state == AppState.WORKING and not idle)

        ready_state = self._state == AppState.SUBTITLES_READY
        done_state = self._state == AppState.EXPORT_DONE
        self.ready_open_srt_button.setEnabled(ready_state and can_open_srt)
        self.ready_open_folder_button.setEnabled(ready_state and has_video)
        self.done_open_video_button.setEnabled(done_state and can_open_video)
        self.done_open_folder_button.setEnabled(done_state and has_video)
        self.done_edit_button.setEnabled(done_state and can_open_srt)
        self._update_details_visibility(idle=idle)

    def _apply_progress_bar_style(self) -> None:
        palette = QtWidgets.QApplication.palette()
        self.progress_bar.setPalette(palette)
        highlight = palette.color(QtGui.QPalette.Highlight).name()
        self.progress_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {highlight}; }}"
        )

    def _clear_video(self) -> None:
        self._reset_video_state()
        self._video_path = None
        self._output_dir = None
        self.save_to_row.set_path(None)
        self.video_card.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")
        self.set_state(AppState.EMPTY)

    def _reset_video_state(self) -> None:
        self._last_srt_path = None
        self._last_output_video = None
        self._subtitles_reviewed = False
        self._output_dir = None

    def _get_default_srt_path(self) -> Optional[Path]:
        if not self._video_path or not self._output_dir:
            return None
        return self._output_dir / f"{self._video_path.stem}.srt"

    def _set_output_dir(self, path: Path) -> None:
        self._output_dir = path
        self.save_to_row.set_path(path)
        self._log(f"Save folder: {path}")

    def _change_output_dir(self) -> None:
        if not self._output_dir:
            return
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose folder…",
            str(self._output_dir),
        )
        if not folder:
            return
        self._set_output_dir(Path(folder))

    def _is_srt_ready(self, srt_path: Optional[Path]) -> bool:
        if not srt_path or not srt_path.exists():
            return False
        return srt_path.stat().st_size > 0

    def _get_app_data_dir(self) -> Path:
        local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = local_appdata / "HebrewSubtitleGUI"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _load_subtitle_edit_path(self) -> Optional[Path]:
        config_path = self._get_app_data_dir() / "config.json"
        if not config_path.exists():
            return None
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        value = data.get("subtitle_edit_path")
        if not value:
            return None
        return Path(value)

    def _save_subtitle_edit_path(self, path: Path) -> None:
        config_path = self._get_app_data_dir() / "config.json"
        payload = {"subtitle_edit_path": str(path)}
        config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _resolve_subtitle_edit_path(self) -> Optional[Path]:
        if self._subtitle_edit_path and self._subtitle_edit_path.exists():
            return self._subtitle_edit_path
        if DEFAULT_SUBTITLE_EDIT_PATH.exists():
            return DEFAULT_SUBTITLE_EDIT_PATH
        return None

    def _prompt_for_subtitle_edit(self) -> Optional[Path]:
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Warning)
        box.setWindowTitle("Subtitle Edit not found")
        box.setText(
            "Subtitle Edit wasn't found. Please install it or choose SubtitleEdit.exe."
        )
        browse_button = box.addButton(
            "Choose Subtitle Edit…", QtWidgets.QMessageBox.ActionRole
        )
        box.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() != browse_button:
            return None

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Choose Subtitle Edit…",
            str(self._get_app_data_dir()),
            "Executable (*.exe)",
        )
        if not file_path:
            return None
        return Path(file_path)


def _configure_logging() -> tuple[logging.Logger, Path, Path, logging.FileHandler]:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    log_dir = local_appdata / "HebrewSubtitleGUI" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"hebrew_subtitle_gui_{timestamp}.log"

    logger = logging.getLogger("hebrew_subtitle_gui")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger, log_path, log_dir, handler


def _install_exception_hook(
    logger: logging.Logger,
    log_path: Path,
) -> None:
    def _handle_exception(exc_type: type[BaseException], exc: BaseException, tb: object) -> None:
        logger.error("Uncaught exception", exc_info=(exc_type, exc, tb))
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        message = (
            "An unexpected error occurred. The application will stay open.\n"
            f"A details file was saved to:\n{log_path}"
        )
        QtWidgets.QMessageBox.critical(None, "Unexpected error", message)

    sys.excepthook = _handle_exception


def _apply_inactive_progress_palette(app: QtWidgets.QApplication) -> None:
    palette = app.palette()
    active_highlight = palette.color(QtGui.QPalette.Active, QtGui.QPalette.Highlight)
    palette.setColor(QtGui.QPalette.Inactive, QtGui.QPalette.Highlight, active_highlight)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Highlight, active_highlight)
    active_text = palette.color(QtGui.QPalette.Active, QtGui.QPalette.HighlightedText)
    palette.setColor(QtGui.QPalette.Inactive, QtGui.QPalette.HighlightedText, active_text)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.HighlightedText, active_text)
    app.setPalette(palette)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    _apply_inactive_progress_palette(app)

    logger, log_path, log_dir, handler = _configure_logging()
    logger.info("Log file: %s", log_path)
    apply_theme(app, logger)
    try:
        faulthandler.enable(file=handler.stream, all_threads=True)
    except Exception:  # noqa: BLE001
        logger.info("Warning: failed to enable faulthandler.")

    _install_exception_hook(logger, log_path)

    window = MainWindow(logger, log_path, log_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
