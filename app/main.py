from __future__ import annotations

import datetime
import faulthandler
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .ffmpeg_utils import (
    ensure_ffmpeg_available,
    get_ffmpeg_missing_message,
    get_runtime_mode,
    resolve_ffmpeg_paths,
)
from .workers import BurnInSettings, TaskType, TranscriptionSettings, Worker

VIDEO_FILTER = "Video Files (*.mp4 *.mkv *.mov *.m4v);;All Files (*.*)"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, logger: logging.Logger, log_path: Path, log_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("Hebrew Subtitle GUI")
        self.setMinimumSize(720, 640)
        self.setAcceptDrops(True)

        self._logger = logger
        self._log_path = log_path
        self._log_dir = log_dir
        self._video_path: Optional[Path] = None
        self._last_srt_path: Optional[Path] = None
        self._last_output_video: Optional[Path] = None
        self._worker_thread: Optional[QtCore.QThread] = None
        self._worker: Optional[Worker] = None
        self._ffmpeg_available = False
        self._ffprobe_available = False

        self._build_ui()
        self._log_diagnostics()
        self._update_ui_state(idle=True)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        file_group = QtWidgets.QGroupBox("Input")
        file_layout = QtWidgets.QGridLayout(file_group)
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setReadOnly(True)
        self.browse_button = QtWidgets.QPushButton("Browse")
        self.output_label = QtWidgets.QLabel("Output folder: -")
        file_layout.addWidget(QtWidgets.QLabel("Video file:"), 0, 0)
        file_layout.addWidget(self.path_edit, 0, 1)
        file_layout.addWidget(self.browse_button, 0, 2)
        file_layout.addWidget(self.output_label, 1, 0, 1, 3)

        controls_group = QtWidgets.QGroupBox("Actions")
        controls_layout = QtWidgets.QHBoxLayout(controls_group)
        self.generate_button = QtWidgets.QPushButton("Generate SRT")
        self.burn_button = QtWidgets.QPushButton("Hardcode subtitles")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        controls_layout.addWidget(self.generate_button)
        controls_layout.addWidget(self.burn_button)
        controls_layout.addWidget(self.cancel_button)

        open_group = QtWidgets.QGroupBox("Quick actions")
        open_layout = QtWidgets.QHBoxLayout(open_group)
        self.open_srt_button = QtWidgets.QPushButton("Open SRT")
        self.open_video_button = QtWidgets.QPushButton("Open Output Video")
        self.open_folder_button = QtWidgets.QPushButton("Open Folder")
        open_layout.addWidget(self.open_srt_button)
        open_layout.addWidget(self.open_video_button)
        open_layout.addWidget(self.open_folder_button)

        self.filter_checkbox = QtWidgets.QCheckBox("Apply audio cleanup filter")
        self.filter_checkbox.setChecked(True)

        style_group = QtWidgets.QGroupBox("Subtitle style (burn-in)")
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
        style_layout.addWidget(QtWidgets.QLabel("MarginV"), 2, 0)
        style_layout.addWidget(self.margin_spin, 2, 1)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        self.status_label = QtWidgets.QLabel("Idle")
        self.status_label.setStyleSheet("font-weight: bold;")

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(220)

        layout.addWidget(file_group)
        layout.addWidget(controls_group)
        layout.addWidget(open_group)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        self.details_toggle = QtWidgets.QToolButton()
        self.details_toggle.setText("Show details")
        self.details_toggle.setCheckable(True)
        self.details_toggle.setArrowType(QtCore.Qt.RightArrow)
        self.details_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        layout.addWidget(self.details_toggle)

        self.details_panel = QtWidgets.QWidget()
        details_layout = QtWidgets.QVBoxLayout(self.details_panel)

        advanced_group = QtWidgets.QGroupBox("Advanced options")
        advanced_layout = QtWidgets.QVBoxLayout(advanced_group)
        advanced_layout.addWidget(self.filter_checkbox)
        advanced_layout.addWidget(style_group)
        details_layout.addWidget(advanced_group)

        log_group = QtWidgets.QGroupBox("Logs")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        log_layout.addWidget(self.log_box)
        self.open_log_button = QtWidgets.QPushButton("Open Log File")
        log_layout.addWidget(self.open_log_button)
        details_layout.addWidget(log_group)
        details_layout.addStretch()

        self.details_panel.setVisible(False)
        layout.addWidget(self.details_panel)

        self.setCentralWidget(central)

        self.browse_button.clicked.connect(self._browse_video)
        self.generate_button.clicked.connect(self._on_generate)
        self.burn_button.clicked.connect(self._on_burn)
        self.cancel_button.clicked.connect(self._on_cancel)
        self.open_folder_button.clicked.connect(self._open_folder)
        self.open_srt_button.clicked.connect(self._open_srt)
        self.open_video_button.clicked.connect(self._open_output_video)
        self.open_log_button.clicked.connect(self._open_log_file)
        self.details_toggle.toggled.connect(self._toggle_details)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls:
            self._set_video_path(Path(urls[0].toLocalFile()))

    def _browse_video(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select video", "", VIDEO_FILTER
        )
        if file_path:
            self._set_video_path(Path(file_path))

    def _set_video_path(self, path: Path) -> None:
        self._video_path = path
        self.path_edit.setText(str(path))
        self.output_label.setText(f"Output folder: {path.parent}")
        self._log(f"Selected video: {path}")
        self._log(f"Output folder: {path.parent}")
        self._probe_video(path)
        self._update_ui_state(idle=True)

    def _probe_video(self, path: Path) -> None:
        try:
            _, ffprobe_path, _ = ensure_ffmpeg_available()
        except FileNotFoundError as exc:
            self._log(str(exc))
            return
        if not ffprobe_path:
            self._log("Warning: ffprobe not found; skipping video probe.")
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
                    "FFprobe warning",
                    "FFprobe could not read this file. It may still work, but "
                    "please confirm the file is valid.",
                )
        except Exception as exc:  # noqa: BLE001
            self._log(f"FFprobe failed: {exc}")

    def _on_generate(self) -> None:
        if not self._video_path:
            QtWidgets.QMessageBox.warning(self, "Missing input", "Select a video file first.")
            return
        try:
            ensure_ffmpeg_available()
        except FileNotFoundError as exc:
            QtWidgets.QMessageBox.critical(self, "FFmpeg missing", str(exc))
            return

        settings = TranscriptionSettings(apply_audio_filter=self.filter_checkbox.isChecked())
        self._start_worker(TaskType.GENERATE_SRT, self._video_path, None, settings, None)

    def _on_burn(self) -> None:
        if not self._video_path:
            QtWidgets.QMessageBox.warning(self, "Missing input", "Select a video file first.")
            return
        try:
            ensure_ffmpeg_available()
        except FileNotFoundError as exc:
            QtWidgets.QMessageBox.critical(self, "FFmpeg missing", str(exc))
            return

        default_srt = self._video_path.parent / f"{self._video_path.stem}.srt"
        srt_path = default_srt
        if not default_srt.exists():
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Select SRT", str(self._video_path.parent), "SubRip (*.srt)"
            )
            if not file_path:
                return
            srt_path = Path(file_path)

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
            QtWidgets.QMessageBox.warning(self, "Busy", "Another task is running.")
            return

        self.log_box.clear()
        self._log_ffmpeg_resolution()
        self._worker_thread = QtCore.QThread()
        self._worker = Worker(
            task_type=task_type,
            video_path=video_path,
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

    def _on_worker_finished(self, success: bool, message: str, payload: dict) -> None:
        self._update_ui_state(idle=True)
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("Done")
        elif message == "Operation cancelled.":
            self.progress_bar.setValue(0)
            self.status_label.setText("Cancelled")
        else:
            self.progress_bar.setValue(0)
            self.status_label.setText("Idle")

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
            QtWidgets.QMessageBox.information(self, "Success", message)
        else:
            if message == "Operation cancelled.":
                QtWidgets.QMessageBox.information(self, "Cancelled", message)
            elif message.startswith("SRT was not created"):
                QtWidgets.QMessageBox.critical(self, "SRT was not created", message)
            elif "FFmpeg failed" in message:
                QtWidgets.QMessageBox.critical(self, "FFmpeg failed", "FFmpeg failed. Check logs.")
            elif "Transcription failed" in message:
                self._show_transcription_error()
            else:
                QtWidgets.QMessageBox.critical(self, "Error", message)

    def _on_cancel(self) -> None:
        if self._worker:
            self._log("Cancelling task...")
            self._worker.cancel()

    def _open_folder(self) -> None:
        if not self._video_path:
            return
        os.startfile(self._video_path.parent)  # type: ignore[arg-type]

    def _open_srt(self) -> None:
        if not self._last_srt_path or not self._last_srt_path.exists():
            QtWidgets.QMessageBox.information(self, "Missing SRT", "Generate an SRT first.")
            return
        QtCore.QProcess.startDetached("notepad.exe", [str(self._last_srt_path)])

    def _open_output_video(self) -> None:
        if not self._last_output_video or not self._last_output_video.exists():
            QtWidgets.QMessageBox.information(
                self, "Missing output", "Hardcode subtitles to create the output video."
            )
            return
        os.startfile(self._last_output_video)  # type: ignore[arg-type]

    def _open_log_file(self) -> None:
        if not self._log_path.exists():
            QtWidgets.QMessageBox.information(self, "Log missing", "No log file found.")
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
        self.status_label.setText(status)

    def _refresh_ffmpeg_status(self) -> None:
        ffmpeg_path, ffprobe_path, _ = resolve_ffmpeg_paths()
        self._ffmpeg_available = ffmpeg_path is not None
        self._ffprobe_available = ffprobe_path is not None

    def _log_ffmpeg_resolution(self) -> None:
        ffmpeg_path, ffprobe_path, mode = resolve_ffmpeg_paths()
        if not ffmpeg_path:
            self._log(get_ffmpeg_missing_message())
            return

        self._log(f"FFmpeg resolver: mode={mode}, ffmpeg={ffmpeg_path}")
        if ffprobe_path:
            self._log(f"FFprobe resolver: {ffprobe_path}")
        else:
            self._log("Warning: ffprobe not found; some metadata checks may be skipped.")

    def _log_diagnostics(self) -> None:
        runtime_mode = get_runtime_mode()
        ffmpeg_path, _, _ = resolve_ffmpeg_paths()
        ffmpeg_display = str(ffmpeg_path) if ffmpeg_path else "NOT FOUND"
        app_version = getattr(sys.modules.get("__main__"), "__version__", "unknown")
        self._log(f"App version: {app_version}")
        self._log(f"OS: {platform.platform()}")
        self._log(
            "Diagnostics: "
            f"Python {sys.version.split()[0]} | mode: {runtime_mode} | ffmpeg: {ffmpeg_display}"
        )
        self._log_ffmpeg_resolution()

    def _toggle_details(self, checked: bool) -> None:
        self.details_panel.setVisible(checked)
        arrow = QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow
        self.details_toggle.setArrowType(arrow)
        self.details_toggle.setText("Hide details" if checked else "Show details")

    def _show_transcription_error(self) -> None:
        message = (
            "Transcription failed.\n"
            f"A log file was saved to:\n{self._log_path}"
        )
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Critical)
        box.setWindowTitle("Transcription failed")
        box.setText(message)
        open_log_button = box.addButton("Open Log", QtWidgets.QMessageBox.ActionRole)
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
        self.generate_button.setEnabled(idle and has_video and ffmpeg_ready)
        self.burn_button.setEnabled(idle and has_video and ffmpeg_ready)
        self.cancel_button.setEnabled(not idle)
        self.open_folder_button.setEnabled(has_video)
        self.open_srt_button.setEnabled(self._last_srt_path is not None)
        self.open_video_button.setEnabled(self._last_output_video is not None)


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
            f"A log file was saved to:\n{log_path}"
        )
        QtWidgets.QMessageBox.critical(None, "Unexpected error", message)

    sys.excepthook = _handle_exception


def _apply_inactive_progress_palette(app: QtWidgets.QApplication) -> None:
    palette = app.palette()
    active_highlight = palette.color(QtGui.QPalette.Active, QtGui.QPalette.Highlight)
    palette.setColor(QtGui.QPalette.Inactive, QtGui.QPalette.Highlight, active_highlight)
    active_text = palette.color(QtGui.QPalette.Active, QtGui.QPalette.HighlightedText)
    palette.setColor(QtGui.QPalette.Inactive, QtGui.QPalette.HighlightedText, active_text)
    app.setPalette(palette)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    _apply_inactive_progress_palette(app)

    logger, log_path, log_dir, handler = _configure_logging()
    logger.info("Log file: %s", log_path)
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
