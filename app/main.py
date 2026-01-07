from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .ffmpeg_utils import ensure_ffmpeg_available
from .workers import BurnInSettings, TaskType, TranscriptionSettings, Worker

VIDEO_FILTER = "Video Files (*.mp4 *.mkv *.mov *.m4v);;All Files (*.*)"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hebrew Subtitle GUI")
        self.setMinimumSize(720, 640)
        self.setAcceptDrops(True)

        self._video_path: Optional[Path] = None
        self._last_srt_path: Optional[Path] = None
        self._last_output_video: Optional[Path] = None
        self._worker_thread: Optional[QtCore.QThread] = None
        self._worker: Optional[Worker] = None

        self._build_ui()
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

        self.filter_checkbox = QtWidgets.QCheckBox("Apply audio cleanup filter")
        self.filter_checkbox.setChecked(True)
        file_layout.addWidget(self.filter_checkbox, 2, 0, 1, 3)

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
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)

        self.status_label = QtWidgets.QLabel("Idle")
        self.status_label.setStyleSheet("font-weight: bold;")

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(220)

        layout.addWidget(file_group)
        layout.addWidget(style_group)
        layout.addWidget(controls_group)
        layout.addWidget(open_group)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(QtWidgets.QLabel("Logs"))
        layout.addWidget(self.log_box)

        self.setCentralWidget(central)

        self.browse_button.clicked.connect(self._browse_video)
        self.generate_button.clicked.connect(self._on_generate)
        self.burn_button.clicked.connect(self._on_burn)
        self.cancel_button.clicked.connect(self._on_cancel)
        self.open_folder_button.clicked.connect(self._open_folder)
        self.open_srt_button.clicked.connect(self._open_srt)
        self.open_video_button.clicked.connect(self._open_output_video)

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
        self._probe_video(path)
        self._update_ui_state(idle=True)

    def _probe_video(self, path: Path) -> None:
        try:
            _, ffprobe_path = ensure_ffmpeg_available()
        except FileNotFoundError as exc:
            self._log(str(exc))
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
        self._worker.signals.started.connect(self._on_worker_started)
        self._worker.signals.finished.connect(self._on_worker_finished)
        self._worker_thread.start()

        self._update_ui_state(idle=False)

    def _on_worker_started(self, status: str) -> None:
        self.status_label.setText(status)
        self.progress_bar.setVisible(True)

    def _on_worker_finished(self, success: bool, message: str, payload: dict) -> None:
        self.progress_bar.setVisible(False)
        self._update_ui_state(idle=True)
        self.status_label.setText("Idle")

        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
            self._worker = None

        if payload.get("srt_path"):
            self._last_srt_path = Path(payload["srt_path"])
        if payload.get("output_path"):
            self._last_output_video = Path(payload["output_path"])

        if success:
            QtWidgets.QMessageBox.information(self, "Success", message)
        else:
            if message == "Operation cancelled.":
                QtWidgets.QMessageBox.information(self, "Cancelled", message)
            elif "FFmpeg failed" in message:
                QtWidgets.QMessageBox.critical(self, "FFmpeg failed", "FFmpeg failed. Check logs.")
            elif "Transcription failed" in message:
                QtWidgets.QMessageBox.critical(
                    self, "Transcription failed", "Transcription failed. Check logs."
                )
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

    def _log(self, message: str) -> None:
        self.log_box.appendPlainText(message)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def _update_ui_state(self, *, idle: bool) -> None:
        has_video = self._video_path is not None
        self.generate_button.setEnabled(idle and has_video)
        self.burn_button.setEnabled(idle and has_video)
        self.cancel_button.setEnabled(not idle)
        self.open_folder_button.setEnabled(has_video)
        self.open_srt_button.setEnabled(self._last_srt_path is not None)
        self.open_video_button.setEnabled(self._last_output_video is not None)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
