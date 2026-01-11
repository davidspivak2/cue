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
import time
from enum import Enum
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from app.ffmpeg_utils import (
    ensure_ffmpeg_available,
    get_ffmpeg_missing_message,
    get_runtime_mode,
    resolve_ffmpeg_paths,
)
from app.progress import ProgressController, ProgressStep
from app.transcription_device import gpu_available
from app.ui.state import AppState
from app.ui.theme import apply_theme
from app.ui.utils import generate_thumbnail, get_media_duration_seconds
from app.ui.widgets import DropZone, ElidedLineEdit, SavingToLine, VideoCard
from app.paths import get_app_data_dir, get_logs_dir
from app.workers import (
    BurnInSettings,
    DiagnosticsSettings,
    TaskType,
    TranscriptionSettings,
    Worker,
)

VIDEO_FILTER = "Video Files (*.mp4 *.mkv *.mov *.m4v);;All Files (*.*)"
DEFAULT_SUBTITLE_EDIT_PATH = Path(r"C:\Program Files\Subtitle Edit\SubtitleEdit.exe")


class SaveLocationPolicy(Enum):
    SAME_FOLDER = "same_folder"
    FIXED_FOLDER = "fixed_folder"
    ASK_EVERY_TIME = "ask_every_time"


class TranscriptionQuality(Enum):
    AUTO = "auto"
    FAST = "fast"
    ACCURATE = "accurate"
    ULTRA = "ultra"


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
        self._progress_controller: Optional[ProgressController] = None
        self._worker_start_time: Optional[float] = None
        self._elapsed_timer = QtCore.QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self._update_elapsed_label)
        self._config = self._load_config()
        self._subtitle_edit_path = self._get_config_path("subtitle_edit_path")
        self._save_policy = self._load_save_policy()
        self._fixed_output_dir = self._get_config_path("save_folder")
        self._transcription_quality = self._load_transcription_quality()
        self._punctuation_rescue_fallback_enabled = (
            self._load_punctuation_rescue_fallback_enabled()
        )
        self._diagnostics_settings = self._load_diagnostics_settings()
        self._state = AppState.EMPTY

        self._build_ui()
        self._log_diagnostics()
        self.set_state(AppState.EMPTY)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        self.drop_zone = DropZone()
        self.video_card = VideoCard()

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
        self.substatus_label = QtWidgets.QLabel("")
        self.substatus_label.setAlignment(QtCore.Qt.AlignCenter)
        self.elapsed_label = QtWidgets.QLabel("")
        self.elapsed_label.setAlignment(QtCore.Qt.AlignCenter)
        self.elapsed_label.setStyleSheet("color: #777;")

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(220)

        self.stack = QtWidgets.QStackedWidget()
        self._state_pages = {
            AppState.EMPTY: self.stack.addWidget(self._build_empty_page()),
            AppState.VIDEO_SELECTED: self.stack.addWidget(self._build_video_selected_page()),
            AppState.WORKING: self.stack.addWidget(self._build_working_page()),
            AppState.SUBTITLES_READY: self.stack.addWidget(self._build_subtitles_ready_page()),
            AppState.EXPORT_DONE: self.stack.addWidget(self._build_done_page()),
        }

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

        self.settings_button = QtWidgets.QToolButton()
        self.settings_button.setObjectName("SettingsButton")
        self.settings_button.setToolTip("Settings")
        self.settings_button.setAutoRaise(True)
        self.settings_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.setIconSize(QtCore.QSize(16, 16))
        self.settings_button.setText("⚙")
        font = self.settings_button.font()
        font.setPointSize(14)
        self.settings_button.setFont(font)

        self.saving_to_line = SavingToLine()
        self.saving_to_line.setVisible(False)

        home_page = QtWidgets.QWidget()
        home_layout = QtWidgets.QVBoxLayout(home_page)
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(self.settings_button)
        home_layout.addLayout(header_layout)
        home_layout.addWidget(self.saving_to_line)
        home_layout.addWidget(self.stack)
        home_layout.addWidget(self.details_toggle)
        home_layout.addWidget(self.details_panel)

        self.settings_page = self._build_settings_page()

        self.page_stack = QtWidgets.QStackedWidget()
        self._page_index = {
            "home": self.page_stack.addWidget(home_page),
            "settings": self.page_stack.addWidget(self.settings_page),
        }
        layout.addWidget(self.page_stack)

        self.setCentralWidget(central)

        self.drop_zone.choose_clicked.connect(self._browse_video)
        self.drop_zone.video_dropped.connect(self._handle_video_dropped)
        self.video_card.clear_clicked.connect(self._clear_video)
        self.video_card.video_dropped.connect(self._handle_video_dropped)
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
        self.settings_button.clicked.connect(self._show_settings_page)
        self.settings_back_button.clicked.connect(self._show_home_page)
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        self.save_policy_group.buttonToggled.connect(self._on_save_policy_toggled)
        self.browse_button.clicked.connect(self._browse_fixed_output_dir)
        self.punctuation_rescue_checkbox.toggled.connect(
            self._on_punctuation_rescue_toggled
        )
        self.diagnostics_enabled_checkbox.toggled.connect(
            self._on_diagnostics_enabled_toggled
        )
        self.diagnostics_success_checkbox.toggled.connect(
            self._on_diagnostics_success_toggled
        )
        for key, checkbox in self.diagnostics_category_checkboxes.items():
            checkbox.toggled.connect(
                lambda checked, category_key=key: self._on_diagnostics_category_toggled(
                    category_key, checked
                )
            )

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
        layout.addWidget(self.substatus_label)
        layout.addWidget(self.elapsed_label)
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

    def _build_settings_section(self, title: str) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("SettingsSectionCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(8)
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("SettingsSectionTitle")
        card_layout.addWidget(title_label)
        return card

    def _build_settings_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_layout = QtWidgets.QHBoxLayout()
        self.settings_back_button = QtWidgets.QPushButton("← Back")
        self.settings_back_button.setObjectName("SettingsBackButton")
        self.settings_back_button.setFlat(True)
        self.settings_back_button.setFixedSize(80, 32)
        self.settings_back_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        title = QtWidgets.QLabel("Settings")
        title.setObjectName("SettingsTitle")

        header_layout.addWidget(self.settings_back_button)
        header_layout.addSpacing(8)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        performance_card = self._build_settings_section("Performance")
        performance_layout = performance_card.layout()

        performance_grid = QtWidgets.QGridLayout()
        performance_grid.setColumnMinimumWidth(0, 170)
        performance_grid.setColumnMinimumWidth(1, 320)
        performance_grid.setColumnStretch(1, 1)
        performance_grid.setHorizontalSpacing(16)
        performance_grid.setVerticalSpacing(8)

        quality_label = QtWidgets.QLabel("Transcription quality")
        quality_label.setFixedWidth(170)

        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItems(
            [
                "Auto",
                "Fast (int8)",
                "Accurate (int16)",
                "Ultra accurate (float32)",
            ]
        )
        self.quality_combo.setFixedHeight(36)
        self.quality_combo.setMinimumWidth(320)
        self.quality_combo.setMaximumWidth(360)

        self.quality_run_label = QtWidgets.QLabel("")
        self.quality_run_label.setObjectName("SettingsRunSummary")

        self.quality_helper_label = QtWidgets.QLabel("")
        self.quality_helper_label.setObjectName("SettingsHelperText")
        self.quality_helper_label.setWordWrap(True)

        performance_grid.addWidget(quality_label, 0, 0)
        performance_grid.addWidget(self.quality_combo, 0, 1)
        performance_grid.addWidget(QtWidgets.QLabel(""), 1, 0)
        performance_grid.addWidget(self.quality_run_label, 1, 1)
        performance_grid.addWidget(QtWidgets.QLabel(""), 2, 0)
        performance_grid.addWidget(self.quality_helper_label, 2, 1)
        performance_layout.addLayout(performance_grid)
        layout.addWidget(performance_card)

        save_card = self._build_settings_section("Save subtitles")
        save_layout = save_card.layout()

        save_grid = QtWidgets.QGridLayout()
        save_grid.setColumnMinimumWidth(0, 170)
        save_grid.setColumnMinimumWidth(1, 320)
        save_grid.setColumnStretch(1, 1)
        save_grid.setHorizontalSpacing(16)
        save_grid.setVerticalSpacing(8)

        self.save_policy_group = QtWidgets.QButtonGroup()
        self.save_same_radio = QtWidgets.QRadioButton("Same folder as the video")
        self.save_fixed_radio = QtWidgets.QRadioButton("Always save to this folder")
        self.save_ask_radio = QtWidgets.QRadioButton("Ask every time")
        for radio in (self.save_same_radio, self.save_fixed_radio, self.save_ask_radio):
            radio.setFixedHeight(36)
            self.save_policy_group.addButton(radio)

        radio_layout = QtWidgets.QVBoxLayout()
        radio_layout.setSpacing(8)
        radio_layout.addWidget(self.save_same_radio)
        radio_layout.addWidget(self.save_fixed_radio)
        radio_layout.addWidget(self.save_ask_radio)

        self.save_path_field = ElidedLineEdit()
        self.save_path_field.setObjectName("SettingsPathField")
        self.save_path_field.setReadOnly(True)
        self.save_path_field.setFixedHeight(36)
        self.save_path_field.setMinimumWidth(320)
        self.save_path_field.setMaximumWidth(360)
        palette = self.save_path_field.palette()
        palette.setColor(QtGui.QPalette.PlaceholderText, QtGui.QColor("#9CA3AF"))
        self.save_path_field.setPalette(palette)

        self.browse_button = QtWidgets.QPushButton("Browse...")
        self.browse_button.setFixedHeight(36)

        path_layout = QtWidgets.QHBoxLayout()
        path_layout.setSpacing(8)
        path_layout.addWidget(self.save_path_field)
        path_layout.addWidget(self.browse_button)

        save_grid.addWidget(QtWidgets.QLabel(""), 0, 0)
        save_grid.addLayout(radio_layout, 0, 1)
        save_grid.addWidget(QtWidgets.QLabel(""), 1, 0)
        save_grid.addLayout(path_layout, 1, 1)

        save_layout.addLayout(save_grid)
        layout.addWidget(save_card)

        punctuation_card = self._build_settings_section("Punctuation")
        punctuation_layout = punctuation_card.layout()
        self.punctuation_rescue_checkbox = QtWidgets.QCheckBox(
            "Improve punctuation automatically (recommended)"
        )
        punctuation_help = QtWidgets.QLabel(
            "If subtitles come out with little or no punctuation, the app will retry "
            "transcription in a compatibility mode and use that result. This can take "
            "longer."
        )
        punctuation_help.setObjectName("SettingsHelperText")
        punctuation_help.setWordWrap(True)
        punctuation_help.setIndent(24)
        punctuation_layout.addWidget(self.punctuation_rescue_checkbox)
        punctuation_layout.addWidget(punctuation_help)
        layout.addWidget(punctuation_card)

        diagnostics_card = self._build_settings_section("Diagnostics")
        diagnostics_layout = diagnostics_card.layout()

        self.diagnostics_enabled_checkbox = QtWidgets.QCheckBox("Enable diagnostics logging")
        self.diagnostics_success_checkbox = QtWidgets.QCheckBox(
            "Write diagnostics on successful completion"
        )

        diagnostics_layout.addWidget(self.diagnostics_enabled_checkbox)
        diagnostics_layout.addWidget(self.diagnostics_success_checkbox)

        self.diagnostics_category_checkboxes: dict[str, QtWidgets.QCheckBox] = {}
        category_labels = {
            "app_system": "App + system info",
            "video_info": "Video info",
            "audio_info": "Audio (WAV) info",
            "transcription_config": "Transcription config",
            "srt_stats": "SRT stats",
            "commands_timings": "Commands + timings",
        }
        for key, label in category_labels.items():
            checkbox = QtWidgets.QCheckBox(label)
            diagnostics_layout.addWidget(checkbox)
            self.diagnostics_category_checkboxes[key] = checkbox

        layout.addWidget(diagnostics_card)
        layout.addStretch()

        self._apply_settings_to_ui()
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
        page_index = self._state_pages.get(state, 0)
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
        self._log(f"Selected video: {path}")
        duration_seconds = get_media_duration_seconds(path)
        thumbnail_path = generate_thumbnail(path, duration_seconds, self._logger)
        self.video_card.set_video(path, duration_seconds, thumbnail_path)
        self._probe_video(path)
        self._update_saving_to_line()
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

        output_dir = self._resolve_output_dir_for_generate()
        if output_dir is None:
            return
        self._set_output_dir(output_dir)
        self._subtitles_reviewed = False
        device, compute_type = self._resolve_transcription_device()
        settings = TranscriptionSettings(
            apply_audio_filter=self.filter_checkbox.isChecked(),
            device=device,
            compute_type=compute_type,
            quality=self._transcription_quality.value,
            punctuation_rescue_fallback_enabled=self._punctuation_rescue_fallback_enabled,
        )
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
            diagnostics_settings=self._diagnostics_settings,
            session_log_path=self._log_path,
        )
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.signals.log.connect(self._log)
        self._worker.signals.progress.connect(self._on_worker_progress)
        self._worker.signals.started.connect(self._on_worker_started)
        self._worker.signals.finished.connect(self._on_worker_finished)
        self._progress_controller = self._build_progress_controller(task_type)
        self._worker_thread.start()
        self._update_ui_state(idle=False)

    def _on_worker_started(self, status: str) -> None:
        self.status_label.setText(status)
        self.substatus_label.setText("")
        self.elapsed_label.setText("")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")
        self._worker_start_time = time.monotonic()
        self._elapsed_timer.start()
        self.set_state(AppState.WORKING)

    def _on_worker_finished(self, success: bool, message: str, payload: dict) -> None:
        task_type = self._worker.task_type if self._worker else None
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("Done")
            self.substatus_label.setText("")
            self.elapsed_label.setText("")
        elif message == "Operation cancelled.":
            self.progress_bar.setValue(0)
            self.status_label.setText("Cancelled")
            self.substatus_label.setText("")
            self.elapsed_label.setText("")
        else:
            self.progress_bar.setValue(0)
            self.status_label.setText("Ready")
            self.substatus_label.setText("")
            self.elapsed_label.setText("")

        self._elapsed_timer.stop()
        self._worker_start_time = None

        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
            self._worker = None
            self._progress_controller = None

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

    def _on_worker_progress(
        self,
        step_id: str,
        step_progress: Optional[float],
        status: str,
    ) -> None:
        if not self._progress_controller:
            return
        global_progress = self._progress_controller.update(step_id, step_progress)
        percent = int(round(global_progress * 100))
        percent = max(0, min(percent, 100))
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{percent}%")
        self.substatus_label.setText(status)

    def _update_elapsed_label(self) -> None:
        if self._worker_start_time is None or self._state != AppState.WORKING:
            return
        elapsed = int(time.monotonic() - self._worker_start_time)
        minutes, seconds = divmod(elapsed, 60)
        text = f"Elapsed: {minutes:02d}:{seconds:02d}"
        if self.elapsed_label.text() != text:
            self.elapsed_label.setText(text)

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

    def _show_settings_page(self) -> None:
        self.page_stack.setCurrentIndex(self._page_index["settings"])

    def _show_home_page(self) -> None:
        self.page_stack.setCurrentIndex(self._page_index["home"])

    def _apply_settings_to_ui(self) -> None:
        quality_index = {
            TranscriptionQuality.AUTO: 0,
            TranscriptionQuality.FAST: 1,
            TranscriptionQuality.ACCURATE: 2,
            TranscriptionQuality.ULTRA: 3,
        }
        self.quality_combo.blockSignals(True)
        self.quality_combo.setCurrentIndex(quality_index[self._transcription_quality])
        self.quality_combo.blockSignals(False)

        self.save_policy_group.blockSignals(True)
        if self._save_policy == SaveLocationPolicy.SAME_FOLDER:
            self.save_same_radio.setChecked(True)
        elif self._save_policy == SaveLocationPolicy.FIXED_FOLDER:
            self.save_fixed_radio.setChecked(True)
        else:
            self.save_ask_radio.setChecked(True)
        self.save_policy_group.blockSignals(False)

        self.diagnostics_enabled_checkbox.blockSignals(True)
        self.diagnostics_enabled_checkbox.setChecked(self._diagnostics_settings.enabled)
        self.diagnostics_enabled_checkbox.blockSignals(False)

        self.diagnostics_success_checkbox.blockSignals(True)
        self.diagnostics_success_checkbox.setChecked(
            self._diagnostics_settings.write_on_success
        )
        self.diagnostics_success_checkbox.blockSignals(False)

        for key, checkbox in self.diagnostics_category_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(self._diagnostics_settings.categories.get(key, True))
            checkbox.blockSignals(False)

        self.punctuation_rescue_checkbox.blockSignals(True)
        self.punctuation_rescue_checkbox.setChecked(
            self._punctuation_rescue_fallback_enabled
        )
        self.punctuation_rescue_checkbox.blockSignals(False)

        self._update_fixed_path_field()
        self._update_save_policy_controls()
        self._update_quality_summary()
        self._update_saving_to_line()
        self._update_diagnostics_controls()

    def _update_fixed_path_field(self) -> None:
        path_text = str(self._fixed_output_dir) if self._fixed_output_dir else None
        self.save_path_field.set_full_text(path_text, placeholder="No folder selected")

    def _update_save_policy_controls(self) -> None:
        enable_fixed = self._save_policy == SaveLocationPolicy.FIXED_FOLDER
        self.save_path_field.setEnabled(enable_fixed)
        self.browse_button.setEnabled(enable_fixed)

    def _update_diagnostics_controls(self) -> None:
        enabled = self._diagnostics_settings.enabled
        self.diagnostics_success_checkbox.setEnabled(enabled)
        for checkbox in self.diagnostics_category_checkboxes.values():
            checkbox.setEnabled(enabled)

    def _store_diagnostics_settings(self) -> None:
        self._config["diagnostics"] = {
            "enabled": self._diagnostics_settings.enabled,
            "write_on_success": self._diagnostics_settings.write_on_success,
            "categories": dict(self._diagnostics_settings.categories),
        }
        self._save_config()

    def _on_diagnostics_enabled_toggled(self, checked: bool) -> None:
        if checked == self._diagnostics_settings.enabled:
            return
        self._diagnostics_settings.enabled = checked
        self._store_diagnostics_settings()
        self._update_diagnostics_controls()

    def _on_diagnostics_success_toggled(self, checked: bool) -> None:
        if checked == self._diagnostics_settings.write_on_success:
            return
        self._diagnostics_settings.write_on_success = checked
        self._store_diagnostics_settings()

    def _on_diagnostics_category_toggled(self, key: str, checked: bool) -> None:
        if self._diagnostics_settings.categories.get(key) == checked:
            return
        self._diagnostics_settings.categories[key] = checked
        self._store_diagnostics_settings()

    def _on_save_policy_toggled(
        self,
        button: QtWidgets.QAbstractButton,
        checked: bool,
    ) -> None:
        if not checked:
            return
        if button is self.save_same_radio:
            policy = SaveLocationPolicy.SAME_FOLDER
        elif button is self.save_fixed_radio:
            policy = SaveLocationPolicy.FIXED_FOLDER
        else:
            policy = SaveLocationPolicy.ASK_EVERY_TIME
        if policy == self._save_policy:
            return
        self._save_policy = policy
        self._config["save_policy"] = policy.value
        self._save_config()
        self._update_save_policy_controls()
        self._update_saving_to_line()
        self._update_ui_state(idle=self._state != AppState.WORKING)

    def _on_punctuation_rescue_toggled(self, checked: bool) -> None:
        if checked == self._punctuation_rescue_fallback_enabled:
            return
        self._punctuation_rescue_fallback_enabled = checked
        self._config["punctuation_rescue_fallback_enabled"] = checked
        self._save_config()

    def _browse_fixed_output_dir(self) -> None:
        start_dir = str(self._fixed_output_dir) if self._fixed_output_dir else ""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose folder…",
            start_dir,
        )
        if not folder:
            return
        self._fixed_output_dir = Path(folder)
        self._config["save_folder"] = str(self._fixed_output_dir)
        self._save_config()
        self._update_fixed_path_field()
        self._update_saving_to_line()

    def _on_quality_changed(self, index: int) -> None:
        quality_map = {
            0: TranscriptionQuality.AUTO,
            1: TranscriptionQuality.FAST,
            2: TranscriptionQuality.ACCURATE,
            3: TranscriptionQuality.ULTRA,
        }
        quality = quality_map.get(index, TranscriptionQuality.AUTO)
        if quality == self._transcription_quality:
            return
        self._transcription_quality = quality
        self._config["transcription_quality"] = quality.value
        self._save_config()
        self._update_quality_summary()

    def _resolve_transcription_device(self) -> tuple[str, str]:
        if self._transcription_quality == TranscriptionQuality.AUTO:
            if gpu_available():
                return "cuda", "float16"
            return "cpu", "int16"
        if self._transcription_quality == TranscriptionQuality.FAST:
            return "cpu", "int8"
        if self._transcription_quality == TranscriptionQuality.ACCURATE:
            return "cpu", "int16"
        return "cpu", "float32"

    def _update_quality_summary(self) -> None:
        device, compute_type = self._resolve_transcription_device()
        label = "GPU" if device == "cuda" else "CPU"
        self.quality_run_label.setText(f"This will run on: {label} ({compute_type})")
        helper_text = ""
        if self._transcription_quality == TranscriptionQuality.ULTRA:
            helper_text = (
                "Very slow on most CPUs. Use only if you need maximum accuracy."
            )
        elif self._transcription_quality == TranscriptionQuality.FAST:
            helper_text = "Faster, but may reduce accuracy on some machines."
        self.quality_helper_label.setText(helper_text)
        self.quality_helper_label.setVisible(bool(helper_text))

    def _update_saving_to_line(self) -> None:
        if not self._video_path:
            self.saving_to_line.set_path("")
            return
        if self._save_policy == SaveLocationPolicy.ASK_EVERY_TIME:
            self.saving_to_line.set_path("")
            return
        if self._save_policy == SaveLocationPolicy.SAME_FOLDER:
            path_text = str(self._video_path.parent)
        elif self._fixed_output_dir:
            path_text = str(self._fixed_output_dir)
        else:
            path_text = "No folder selected"
        self.saving_to_line.set_path(path_text)

    def _resolve_output_dir_for_generate(self) -> Optional[Path]:
        if not self._video_path:
            return None
        if self._save_policy == SaveLocationPolicy.SAME_FOLDER:
            return self._video_path.parent
        if self._save_policy == SaveLocationPolicy.FIXED_FOLDER:
            if not self._fixed_output_dir:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Save folder missing",
                    "Choose a folder in Settings to save your subtitles.",
                )
                return None
            if not self._fixed_output_dir.exists():
                QtWidgets.QMessageBox.warning(
                    self,
                    "Save folder missing",
                    "The selected save folder no longer exists. Choose another folder.",
                )
                return None
            return self._fixed_output_dir
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose folder…",
            str(self._video_path.parent),
        )
        if not folder:
            return None
        return Path(folder)

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
        self._update_saving_to_line()
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
        self.saving_to_line.setVisible(
            idle and has_video and self._save_policy != SaveLocationPolicy.ASK_EVERY_TIME
        )
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
        self.settings_button.setEnabled(idle)
        self.settings_page.setEnabled(idle)
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
        self._update_saving_to_line()
        self.video_card.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")
        self.substatus_label.setText("")
        self.set_state(AppState.EMPTY)

    def _reset_video_state(self) -> None:
        self._last_srt_path = None
        self._last_output_video = None
        self._subtitles_reviewed = False
        self._output_dir = None
        self._progress_controller = None

    def _get_default_srt_path(self) -> Optional[Path]:
        if not self._video_path or not self._output_dir:
            return None
        return self._output_dir / f"{self._video_path.stem}.srt"

    def _set_output_dir(self, path: Path) -> None:
        self._output_dir = path
        self._log(f"Save folder: {path}")

    def _is_srt_ready(self, srt_path: Optional[Path]) -> bool:
        if not srt_path or not srt_path.exists():
            return False
        return srt_path.stat().st_size > 0

    def _get_app_data_dir(self) -> Path:
        return get_app_data_dir()

    def _load_config(self) -> dict:
        config_path = self._get_app_data_dir() / "config.json"
        if not config_path.exists():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_subtitle_edit_path(self, path: Path) -> None:
        self._config["subtitle_edit_path"] = str(path)
        self._save_config()

    def _save_config(self) -> None:
        config_path = self._get_app_data_dir() / "config.json"
        config_path.write_text(json.dumps(self._config, indent=2), encoding="utf-8")

    def _get_config_path(self, key: str) -> Optional[Path]:
        value = self._config.get(key)
        if not value:
            return None
        return Path(value)

    def _load_save_policy(self) -> SaveLocationPolicy:
        value = self._config.get("save_policy")
        try:
            return SaveLocationPolicy(value)
        except ValueError:
            return SaveLocationPolicy.SAME_FOLDER

    def _load_transcription_quality(self) -> TranscriptionQuality:
        value = self._config.get("transcription_quality")
        try:
            return TranscriptionQuality(value)
        except ValueError:
            return TranscriptionQuality.AUTO

    def _load_diagnostics_settings(self) -> DiagnosticsSettings:
        default_categories = {
            "app_system": True,
            "video_info": True,
            "audio_info": True,
            "transcription_config": True,
            "srt_stats": True,
            "commands_timings": True,
        }
        raw = self._config.get("diagnostics")
        if not isinstance(raw, dict):
            return DiagnosticsSettings(
                enabled=False,
                write_on_success=False,
                categories=default_categories.copy(),
            )
        enabled = raw.get("enabled") if isinstance(raw.get("enabled"), bool) else False
        write_on_success = (
            raw.get("write_on_success")
            if isinstance(raw.get("write_on_success"), bool)
            else False
        )
        categories = default_categories.copy()
        raw_categories = raw.get("categories")
        if isinstance(raw_categories, dict):
            for key in categories:
                if isinstance(raw_categories.get(key), bool):
                    categories[key] = raw_categories[key]
        return DiagnosticsSettings(
            enabled=enabled,
            write_on_success=write_on_success,
            categories=categories,
        )

    def _load_punctuation_rescue_fallback_enabled(self) -> bool:
        value = self._config.get("punctuation_rescue_fallback_enabled")
        if isinstance(value, bool):
            return value
        return True

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

    def _build_progress_controller(self, task_type: str) -> ProgressController:
        if task_type == TaskType.GENERATE_SRT:
            steps = [ProgressStep.PREPARE_AUDIO, ProgressStep.TRANSCRIBE]
        else:
            steps = [ProgressStep.EXPORT]
        return ProgressController(steps)


def _configure_logging() -> tuple[logging.Logger, Path, Path, logging.FileHandler]:
    log_dir = get_logs_dir()
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
