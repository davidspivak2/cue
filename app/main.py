from __future__ import annotations

if __name__ == "__main__" and __package__ is None:
    import os
    import sys

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import datetime
from dataclasses import replace
import json
import faulthandler
import logging
import os
import platform
import sys
import subprocess
import tempfile
import time
import zipfile
from enum import Enum
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia

from app.ass_karaoke import (
    build_ass_document_with_karaoke_fallback,
    build_style_config_from_subtitle_style,
)
from app.config import DEFAULT_HIGHLIGHT_COLOR, DEFAULT_HIGHLIGHT_OPACITY, apply_config_defaults
from app.ffmpeg_utils import (
    ensure_ffmpeg_available,
    extract_ass_frame,
    extract_raw_frame,
    extract_subtitled_frame,
    get_ffmpeg_missing_message,
    get_runtime_mode,
    get_subprocess_kwargs,
    resolve_ffmpeg_paths,
)
from app.graphics_preview_renderer import (
    build_preview_cache_key,
    render_graphics_preview,
)
from app.progress import ProgressController, ProgressStep
from app.transcription_device import gpu_available
from app.ui.state import AppState
from app.ui.theme import apply_theme
from app.ui.utils import format_duration, generate_thumbnail, get_media_duration_seconds
from app.ui.widgets import (
    AspectRatioFrame,
    ClickableLabel,
    DropZone,
    ElidedLineEdit,
    SavingToLine,
    VideoCard,
)
from app.paths import get_app_data_dir, get_logs_dir, get_preview_frames_dir
from app.preview_playback import (
    PreviewPlaybackController,
    STATIC_SRT_PIPELINE,
    WORD_HIGHLIGHT_ASS_PIPELINE,
)
from app.srt_utils import (
    compute_srt_sha256,
    is_word_timing_stale,
    parse_srt_file,
    select_cue_for_timestamp,
)
from app.align_utils import audio_path_for_srt, build_alignment_plan
from app.workers import (
    DiagnosticsSettings,
    TaskType,
    TranscriptionSettings,
    Worker,
)
from app.word_timing_schema import (
    SCHEMA_VERSION,
    WordTimingValidationError,
    build_word_timing_stub,
    load_word_timings_json,
    save_word_timings_json,
    word_timings_path_for_srt,
)
from app.subtitle_style import (
    PRESET_CUSTOM,
    PRESET_DEFAULT,
    PRESET_NAMES,
    SubtitleStyle,
    legacy_style_from_model,
    legacy_preset_defaults,
    legacy_style_from_custom_dict,
    normalize_style_model,
    preset_defaults,
    style_model_from_legacy,
    style_model_to_dict,
    summarize_style_model,
    get_box_alpha_byte,
    to_ffmpeg_force_style,
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
        self._word_timings_path: Optional[Path] = None
        self._last_output_video: Optional[Path] = None
        self._worker_thread: Optional[QtCore.QThread] = None
        self._worker: Optional[Worker] = None
        self._ffmpeg_available = False
        self._ffprobe_available = False
        self._subtitles_reviewed = False
        self._preview_frame_path: Optional[Path] = None
        self._preview_subtitle_text: Optional[str] = None
        self._preview_timestamp_seconds: Optional[float] = None
        self._preview_clip_start_seconds: Optional[float] = None
        self._preview_clip_duration_seconds: Optional[float] = None
        self._preview_pixmap: Optional[QtGui.QPixmap] = None
        self._preview_clip_path: Optional[Path] = None
        self._preview_slider_dragging = False
        self._preview_play_request_pending = False
        self._preview_loading = False
        self._preview_playback_controller = PreviewPlaybackController(self._log, self)
        self.preview_media_player: Optional[QtMultimedia.QMediaPlayer] = None
        self.preview_stack: Optional[QtWidgets.QStackedWidget] = None
        self.preview_play_button: Optional[QtWidgets.QPushButton] = None
        self.preview_stop_button: Optional[QtWidgets.QPushButton] = None
        self.preview_scrub_slider: Optional[QtWidgets.QSlider] = None
        self.preview_time_label: Optional[QtWidgets.QLabel] = None
        self.preview_status_label: Optional[QtWidgets.QLabel] = None
        self.subtitle_mode_group: Optional[QtWidgets.QButtonGroup] = None
        self.subtitle_mode_buttons: dict[str, QtWidgets.QPushButton] = {}
        self.subtitle_style_preset_group: Optional[QtWidgets.QButtonGroup] = None
        self.subtitle_style_preset_buttons: dict[str, QtWidgets.QPushButton] = {}
        self.background_mode_group: Optional[QtWidgets.QButtonGroup] = None
        self.background_mode_buttons: dict[str, QtWidgets.QPushButton] = {}
        self._progress_controller: Optional[ProgressController] = None
        self._worker_start_time: Optional[float] = None
        self._elapsed_timer = QtCore.QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self._update_elapsed_label)
        self._preview_render_timer = QtCore.QTimer(self)
        self._preview_render_timer.setSingleShot(True)
        self._preview_render_timer.setInterval(150)
        self._preview_render_timer.timeout.connect(self._refresh_preview_with_style)
        self._config = self._load_config()
        self._subtitle_edit_path = self._get_config_path("subtitle_edit_path")
        (
            self._subtitle_style_preset,
            self._subtitle_style_custom,
            self._style_model,
        ) = self._load_subtitle_style()
        self._subtitle_mode = self._style_model.subtitle_mode
        self._highlight_color = self._style_model.highlight_color
        self._highlight_opacity = self._config["subtitle_style"]["highlight_opacity"]
        self._subtitle_style_panel_open = False
        self._save_policy = self._load_save_policy()
        self._fixed_output_dir = self._get_config_path("save_folder")
        self._transcription_quality = self._load_transcription_quality()
        self._punctuation_rescue_fallback_enabled = (
            self._load_punctuation_rescue_fallback_enabled()
        )
        self._apply_audio_filter_enabled = self._load_apply_audio_filter_enabled()
        self._keep_extracted_audio_enabled = self._load_keep_extracted_audio_enabled()
        self._diagnostics_settings = self._load_diagnostics_settings()
        self._state = AppState.EMPTY

        self._build_ui()
        self._log(
            "Loaded config: "
            f"{summarize_style_model(self._style_model)} "
            f"highlight_opacity={self._highlight_opacity}"
        )
        self._log_diagnostics()
        self.set_state(AppState.EMPTY)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        self.drop_zone = DropZone()
        self.video_card = VideoCard()

        self.generate_button = QtWidgets.QPushButton("Create subtitles")
        self.burn_button = QtWidgets.QPushButton("Create final video")
        self.cancel_button = QtWidgets.QPushButton("Cancel")

        self.done_open_video_button = QtWidgets.QPushButton("Play video")
        self.done_open_folder_button = QtWidgets.QPushButton("Open folder")
        self.done_edit_button = QtWidgets.QPushButton("Edit subtitles and export again")

        self.done_edit_button.setFlat(True)
        self.done_edit_button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        self.filter_checkbox = QtWidgets.QCheckBox("Clean up audio before transcription")
        self.filter_checkbox.setChecked(False)
        self.keep_extracted_audio_checkbox = QtWidgets.QCheckBox("Keep extracted WAV file")

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
        self.burn_button.clicked.connect(self._on_burn)
        self.cancel_button.clicked.connect(self._on_cancel)
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
        self.filter_checkbox.toggled.connect(self._on_audio_filter_toggled)
        self.keep_extracted_audio_checkbox.toggled.connect(
            self._on_keep_extracted_audio_toggled
        )
        self.diagnostics_enabled_checkbox.toggled.connect(
            self._on_diagnostics_enabled_toggled
        )
        self.diagnostics_archive_checkbox.toggled.connect(
            self._on_diagnostics_archive_toggled
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
        layout = QtWidgets.QHBoxLayout(page)
        layout.setSpacing(24)
        layout.setAlignment(QtCore.Qt.AlignTop)

        preview_card = QtWidgets.QFrame()
        preview_layout = QtWidgets.QVBoxLayout(preview_card)
        preview_layout.setSpacing(12)

        preview_frame = AspectRatioFrame()
        preview_frame.setObjectName("PreviewCardFrame")
        preview_frame.setMinimumSize(720, 405)
        preview_frame.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        preview_frame_layout = QtWidgets.QGridLayout(preview_frame)
        preview_frame_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_image_label = ClickableLabel()
        self.preview_image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_image_label.setObjectName("PreviewCardImage")
        self.preview_image_label.setMinimumSize(720, 405)
        self.preview_image_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )
        self.preview_image_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.preview_image_label.clicked.connect(self._open_preview_dialog)

        preview_frame_layout.addWidget(self.preview_image_label, 0, 0, 1, 1)

        preview_layout.addWidget(preview_frame)
        preview_layout.addStretch()

        right_column = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_column)
        right_layout.setSpacing(12)
        right_layout.setContentsMargins(0, 0, 0, 0)

        style_card = self._build_subtitle_style_card()
        right_layout.addWidget(style_card)
        right_layout.addStretch()

        layout.addWidget(preview_card, 3)
        layout.addWidget(right_column, 2)
        layout.setAlignment(preview_card, QtCore.Qt.AlignTop)
        layout.setAlignment(right_column, QtCore.Qt.AlignTop)
        self._update_preview_card()
        return page

    def _build_subtitle_style_card(self) -> QtWidgets.QFrame:
        card = self._build_settings_section("Style")
        card_layout = card.layout()

        def _build_style_section(title: str) -> tuple[QtWidgets.QWidget, QtWidgets.QVBoxLayout]:
            section = QtWidgets.QWidget()
            section_layout = QtWidgets.QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(6)
            title_label = QtWidgets.QLabel(title)
            title_label.setStyleSheet("font-weight: 600;")
            section_layout.addWidget(title_label)
            return section, section_layout

        subtitle_mode_label = QtWidgets.QLabel("Subtitle mode")
        subtitle_mode_tooltip = (
            "Static: normal subtitles.\n"
            "Word highlight: highlights the current spoken word."
        )
        subtitle_mode_label.setToolTip(subtitle_mode_tooltip)
        subtitle_mode_control = QtWidgets.QWidget()
        subtitle_mode_layout = QtWidgets.QHBoxLayout(subtitle_mode_control)
        subtitle_mode_layout.setContentsMargins(0, 0, 0, 0)
        subtitle_mode_layout.setSpacing(0)
        self.subtitle_mode_group = QtWidgets.QButtonGroup(self)
        self.subtitle_mode_group.setExclusive(True)
        self.subtitle_mode_buttons = {}
        mode_buttons = [
            ("Static", "static", "SegmentedLeft"),
            ("Word highlight", "word_highlight", "SegmentedRight"),
        ]
        for label, mode, object_name in mode_buttons:
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
            )
            button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            button.setToolTip(subtitle_mode_tooltip)
            button.setObjectName(object_name)
            button.setProperty("mode", mode)
            self.subtitle_mode_group.addButton(button)
            self.subtitle_mode_buttons[mode] = button
            subtitle_mode_layout.addWidget(button)

        self.highlight_color_label = QtWidgets.QLabel("Highlight color")
        highlight_color_tooltip = "Color used for the highlighted word."
        self.highlight_color_label.setToolTip(highlight_color_tooltip)
        self.highlight_color_row = QtWidgets.QWidget()
        highlight_layout = QtWidgets.QHBoxLayout(self.highlight_color_row)
        highlight_layout.setContentsMargins(0, 0, 0, 0)
        highlight_layout.setSpacing(8)
        self.highlight_color_button = QtWidgets.QPushButton("Pick color…")
        self.highlight_color_button.setFixedHeight(32)
        self.highlight_color_button.setToolTip(highlight_color_tooltip)
        self.highlight_color_value = QtWidgets.QLineEdit()
        self.highlight_color_value.setReadOnly(True)
        self.highlight_color_value.setFixedHeight(32)
        self.highlight_color_value.setMinimumWidth(110)
        self.highlight_color_value.setToolTip(highlight_color_tooltip)
        highlight_layout.addWidget(self.highlight_color_button)
        highlight_layout.addWidget(self.highlight_color_value)
        highlight_layout.addStretch()

        preset_tooltip = (
            "Controls subtitle appearance (font size, outline, shadow, margin, box)."
        )
        preset_options = QtWidgets.QWidget()
        preset_layout = QtWidgets.QVBoxLayout(preset_options)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(4)
        self.subtitle_style_preset_group = QtWidgets.QButtonGroup(self)
        self.subtitle_style_preset_group.setExclusive(True)
        self.subtitle_style_preset_buttons = {}
        for preset in PRESET_NAMES:
            button = QtWidgets.QPushButton(preset)
            button.setCheckable(True)
            button.setFlat(True)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
            )
            button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            button.setToolTip(preset_tooltip)
            button.setObjectName("PresetOption")
            button.setProperty("preset", preset)
            self.subtitle_style_preset_group.addButton(button)
            self.subtitle_style_preset_buttons[preset] = button
            preset_layout.addWidget(button)

        mode_section, mode_layout = _build_style_section("Mode")
        mode_grid = QtWidgets.QGridLayout()
        mode_grid.setColumnMinimumWidth(0, 120)
        mode_grid.setColumnStretch(1, 1)
        mode_grid.setHorizontalSpacing(12)
        mode_grid.setVerticalSpacing(8)
        mode_grid.addWidget(subtitle_mode_label, 0, 0)
        mode_grid.addWidget(subtitle_mode_control, 0, 1)
        mode_grid.addWidget(self.highlight_color_label, 1, 0)
        mode_grid.addWidget(self.highlight_color_row, 1, 1)
        mode_layout.addLayout(mode_grid)
        card_layout.addWidget(mode_section)

        preset_section, preset_layout_container = _build_style_section("Preset")
        preset_layout_container.addWidget(preset_options)
        card_layout.addWidget(preset_section)

        quick_section, quick_layout = _build_style_section("Quick tweaks")
        controls_grid = QtWidgets.QGridLayout()
        controls_grid.setColumnMinimumWidth(0, 120)
        controls_grid.setColumnStretch(1, 1)
        controls_grid.setHorizontalSpacing(12)
        controls_grid.setVerticalSpacing(8)

        self.font_size_slider, self.font_size_spinbox = self._build_style_control(18, 72)
        self.outline_slider, self.outline_spinbox = self._build_style_control(0, 10)
        self.shadow_slider, self.shadow_spinbox = self._build_style_control(0, 10)
        self.margin_slider, self.margin_spinbox = self._build_style_control(0, 200)

        controls_grid.addWidget(QtWidgets.QLabel("Font size"), 0, 0)
        controls_grid.addWidget(self.font_size_slider, 0, 1)
        controls_grid.addWidget(self.font_size_spinbox, 0, 2)

        controls_grid.addWidget(QtWidgets.QLabel("Outline width"), 1, 0)
        controls_grid.addWidget(self.outline_slider, 1, 1)
        controls_grid.addWidget(self.outline_spinbox, 1, 2)

        controls_grid.addWidget(QtWidgets.QLabel("Shadow"), 2, 0)
        controls_grid.addWidget(self.shadow_slider, 2, 1)
        controls_grid.addWidget(self.shadow_spinbox, 2, 2)

        controls_grid.addWidget(QtWidgets.QLabel("Bottom margin"), 3, 0)
        controls_grid.addWidget(self.margin_slider, 3, 1)
        controls_grid.addWidget(self.margin_spinbox, 3, 2)

        quick_layout.addLayout(controls_grid)

        background_section = QtWidgets.QWidget()
        background_layout = QtWidgets.QVBoxLayout(background_section)
        background_layout.setContentsMargins(0, 0, 0, 0)
        background_layout.setSpacing(6)
        background_label = QtWidgets.QLabel("Background")
        background_layout.addWidget(background_label)

        background_controls = QtWidgets.QWidget()
        background_controls_layout = QtWidgets.QHBoxLayout(background_controls)
        background_controls_layout.setContentsMargins(0, 0, 0, 0)
        background_controls_layout.setSpacing(0)
        self.background_mode_group = QtWidgets.QButtonGroup(self)
        self.background_mode_group.setExclusive(True)
        self.background_mode_buttons = {}
        background_buttons = [
            ("None", "none", "SegmentedLeft"),
            ("Line", "line", "SegmentedMiddle"),
            ("Word", "word", "SegmentedRight"),
        ]
        for label, mode, object_name in background_buttons:
            button = QtWidgets.QPushButton(label)
            button.setCheckable(True)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
            )
            button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            button.setObjectName(object_name)
            button.setProperty("mode", mode)
            if mode == "word":
                button.setEnabled(False)
                button.setToolTip("Available in a future update.")
            self.background_mode_group.addButton(button)
            self.background_mode_buttons[mode] = button
            background_controls_layout.addWidget(button)

        background_layout.addWidget(background_controls)
        self.word_background_helper_label = QtWidgets.QLabel(
            "Word background is available in a future update."
        )
        self.word_background_helper_label.setEnabled(False)
        self.word_background_helper_label.setWordWrap(True)
        background_layout.addWidget(self.word_background_helper_label)
        quick_layout.addWidget(background_section)

        card_layout.addWidget(quick_section)

        self.subtitle_style_customize_button = QtWidgets.QPushButton("Show advanced options")
        self.subtitle_style_customize_button.setCheckable(True)
        self.subtitle_style_customize_button.setFlat(True)
        self.subtitle_style_customize_button.setCursor(
            QtGui.QCursor(QtCore.Qt.PointingHandCursor)
        )
        self.subtitle_style_customize_button.setToolTip(preset_tooltip)

        customize_layout = QtWidgets.QHBoxLayout()
        customize_layout.addWidget(self.subtitle_style_customize_button)
        customize_layout.addStretch()
        advanced_section, advanced_layout = _build_style_section("Advanced")
        advanced_layout.addLayout(customize_layout)
        card_layout.addWidget(advanced_section)

        self.subtitle_style_panel = QtWidgets.QWidget()
        panel_layout = QtWidgets.QVBoxLayout(self.subtitle_style_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(8)

        self.box_options_container = QtWidgets.QWidget()
        box_grid = QtWidgets.QGridLayout(self.box_options_container)
        box_grid.setColumnMinimumWidth(0, 120)
        box_grid.setColumnStretch(1, 1)
        box_grid.setHorizontalSpacing(12)
        box_grid.setVerticalSpacing(8)

        self.box_opacity_slider, self.box_opacity_spinbox = self._build_style_control(0, 100)
        self.box_padding_slider, self.box_padding_spinbox = self._build_style_control(0, 40)

        box_grid.addWidget(QtWidgets.QLabel("Box opacity"), 0, 0)
        box_grid.addWidget(self.box_opacity_slider, 0, 1)
        box_grid.addWidget(self.box_opacity_spinbox, 0, 2)

        box_grid.addWidget(QtWidgets.QLabel("Box padding"), 1, 0)
        box_grid.addWidget(self.box_padding_slider, 1, 1)
        box_grid.addWidget(self.box_padding_spinbox, 1, 2)

        panel_layout.addWidget(self.box_options_container)

        reset_layout = QtWidgets.QHBoxLayout()
        reset_layout.addStretch()
        self.subtitle_style_reset_button = QtWidgets.QPushButton("Reset to preset")
        self.subtitle_style_reset_button.setFlat(True)
        self.subtitle_style_reset_button.setCursor(
            QtGui.QCursor(QtCore.Qt.PointingHandCursor)
        )
        reset_layout.addWidget(self.subtitle_style_reset_button)
        panel_layout.addLayout(reset_layout)

        advanced_layout.addWidget(self.subtitle_style_panel)

        cta_layout = QtWidgets.QHBoxLayout()
        cta_layout.addStretch()
        cta_layout.addWidget(self.burn_button)
        cta_layout.addStretch()
        card_layout.addStretch()
        card_layout.addLayout(cta_layout)

        self.subtitle_style_panel.setVisible(self._subtitle_style_panel_open)
        self.subtitle_style_customize_button.setChecked(self._subtitle_style_panel_open)
        self._connect_subtitle_style_controls()
        self._apply_subtitle_style_to_controls()
        self._apply_subtitle_mode_to_controls()
        return card

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


    def _build_style_control(
        self, minimum: int, maximum: int
    ) -> tuple[QtWidgets.QSlider, QtWidgets.QSpinBox]:
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(1)
        slider.setPageStep(1)

        spinbox = QtWidgets.QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setSingleStep(1)
        spinbox.setMinimumWidth(56)

        def _sync_spinbox(value: int) -> None:
            if spinbox.value() == value:
                return
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)

        def _sync_slider(value: int) -> None:
            if slider.value() == value:
                return
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)

        slider.valueChanged.connect(_sync_spinbox)
        spinbox.valueChanged.connect(_sync_slider)
        return slider, spinbox

    def _connect_subtitle_style_controls(self) -> None:
        if self.subtitle_mode_group:
            self.subtitle_mode_group.buttonClicked.connect(
                self._on_subtitle_mode_button_clicked
            )
        self.highlight_color_button.clicked.connect(self._on_highlight_color_clicked)
        if self.subtitle_style_preset_group:
            self.subtitle_style_preset_group.buttonClicked.connect(
                self._on_subtitle_style_preset_clicked
            )
        if self.background_mode_group:
            self.background_mode_group.buttonClicked.connect(
                self._on_background_mode_clicked
            )
        self.subtitle_style_customize_button.toggled.connect(
            self._toggle_subtitle_style_panel
        )
        self.subtitle_style_reset_button.clicked.connect(self._reset_subtitle_style_preset)

        for slider in (
            self.font_size_slider,
            self.outline_slider,
            self.shadow_slider,
            self.margin_slider,
            self.box_opacity_slider,
            self.box_padding_slider,
        ):
            slider.valueChanged.connect(self._on_subtitle_style_custom_changed)

        for spinbox in (
            self.font_size_spinbox,
            self.outline_spinbox,
            self.shadow_spinbox,
            self.margin_spinbox,
            self.box_opacity_spinbox,
            self.box_padding_spinbox,
        ):
            spinbox.valueChanged.connect(self._on_subtitle_style_custom_changed)

    def _apply_subtitle_mode_to_controls(self) -> None:
        mode = (
            self._subtitle_mode
            if self._subtitle_mode in {"static", "word_highlight"}
            else "static"
        )
        for key, button in self.subtitle_mode_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == mode)
            button.blockSignals(False)
        self._update_highlight_color_display()
        self._update_highlight_color_visibility()

    def _update_highlight_color_display(self) -> None:
        self.highlight_color_value.setText(self._highlight_color)

    def _update_highlight_color_visibility(self) -> None:
        show = self._subtitle_mode == "word_highlight"
        self.highlight_color_label.setVisible(show)
        self.highlight_color_row.setVisible(show)
        self.highlight_color_label.setEnabled(show)
        self.highlight_color_row.setEnabled(show)

    def _on_subtitle_mode_button_clicked(self, button: QtWidgets.QAbstractButton) -> None:
        mode = button.property("mode")
        if not isinstance(mode, str):
            return
        self._set_subtitle_mode(mode)

    def _set_subtitle_mode(self, mode: str) -> None:
        if mode not in {"word_highlight", "static"}:
            return
        if mode == self._subtitle_mode:
            return
        self._subtitle_mode = mode
        self._style_model = replace(self._style_model, subtitle_mode=mode)
        self._subtitle_style_custom = replace(self._subtitle_style_custom, subtitle_mode=mode)
        self._config["subtitle_mode"] = mode
        self._store_subtitle_style_config()
        self._log(f"Subtitle mode set to: {mode}")
        self._update_highlight_color_visibility()
        self._invalidate_preview_playback()
        self._schedule_preview_refresh()

    def _on_highlight_color_clicked(self) -> None:
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._highlight_color), self
        )
        if not color.isValid():
            return
        hex_value = color.name().upper()
        if hex_value == self._highlight_color:
            return
        self._highlight_color = hex_value
        self._style_model = replace(self._style_model, highlight_color=hex_value)
        self._subtitle_style_custom = replace(self._subtitle_style_custom, highlight_color=hex_value)
        current_style = self._config.get("subtitle_style")
        if not isinstance(current_style, dict):
            current_style = {}
            self._config["subtitle_style"] = current_style
        current_style["highlight_color"] = hex_value
        self._store_subtitle_style_config()
        self._update_highlight_color_display()

    def _toggle_subtitle_style_panel(self, checked: bool) -> None:
        self._subtitle_style_panel_open = checked
        self.subtitle_style_panel.setVisible(checked)

    def _reset_subtitle_style_preset(self) -> None:
        self._subtitle_style_panel_open = False
        self.subtitle_style_panel.setVisible(False)
        self.subtitle_style_customize_button.blockSignals(True)
        self.subtitle_style_customize_button.setChecked(False)
        self.subtitle_style_customize_button.blockSignals(False)

        self._subtitle_style_preset = PRESET_DEFAULT
        self._set_subtitle_style_preset_buttons(PRESET_DEFAULT)

        self._style_model = preset_defaults(
            PRESET_DEFAULT,
            subtitle_mode=self._subtitle_mode,
            highlight_color=self._highlight_color,
        )
        self._apply_subtitle_style_to_controls()
        self._store_subtitle_style_config()
        self._invalidate_preview_playback()
        self._schedule_preview_refresh()

    def _apply_subtitle_style_to_controls(self) -> None:
        style = self._style_model
        self._set_subtitle_style_preset_buttons(self._subtitle_style_preset)

        controls = [
            (self.font_size_slider, self.font_size_spinbox, style.font_size),
            (
                self.outline_slider,
                self.outline_spinbox,
                int(round(style.outline_width)),
            ),
            (
                self.shadow_slider,
                self.shadow_spinbox,
                int(round(style.shadow_strength)),
            ),
            (
                self.margin_slider,
                self.margin_spinbox,
                int(round(style.vertical_offset)),
            ),
            (
                self.box_opacity_slider,
                self.box_opacity_spinbox,
                int(round(style.line_bg_opacity * 100)),
            ),
            (
                self.box_padding_slider,
                self.box_padding_spinbox,
                int(round(style.line_bg_padding)),
            ),
        ]
        for slider, spinbox, value in controls:
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)

        self._set_background_mode_buttons(style.background_mode)
        self._update_box_options_visibility(style.background_mode == "line")

    def _update_box_options_visibility(self, enabled: bool) -> None:
        self.box_options_container.setVisible(enabled)

    def _set_subtitle_style_preset_buttons(self, preset: str) -> None:
        for key, button in self.subtitle_style_preset_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == preset)
            button.blockSignals(False)

    def _set_background_mode_buttons(self, mode: str) -> None:
        for key, button in self.background_mode_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == mode)
            button.blockSignals(False)

    def _current_background_mode(self) -> str:
        for mode, button in self.background_mode_buttons.items():
            if button.isChecked():
                return mode
        return "none"

    def _collect_custom_style_from_controls(self) -> SubtitleStyle:
        outline_width = self.outline_slider.value()
        shadow_strength = self.shadow_slider.value()
        background_mode = self._current_background_mode()
        return replace(
            self._subtitle_style_custom,
            font_size=self.font_size_slider.value(),
            outline_enabled=outline_width > 0,
            outline_width=outline_width,
            shadow_enabled=shadow_strength > 0,
            shadow_strength=shadow_strength,
            vertical_offset=self.margin_slider.value(),
            background_mode=background_mode,
            line_bg_opacity=self.box_opacity_slider.value() / 100.0,
            line_bg_padding=self.box_padding_slider.value(),
            subtitle_mode=self._subtitle_mode,
            highlight_color=self._highlight_color,
        )

    def _on_subtitle_style_preset_changed(self, preset: str) -> None:
        if preset not in PRESET_NAMES:
            return
        if preset == self._subtitle_style_preset:
            return
        self._subtitle_style_preset = preset
        if preset == PRESET_CUSTOM:
            self._style_model = self._subtitle_style_custom
        else:
            self._style_model = preset_defaults(
                preset,
                subtitle_mode=self._subtitle_mode,
                highlight_color=self._highlight_color,
            )
        self._apply_subtitle_style_to_controls()
        self._store_subtitle_style_config()
        self._invalidate_preview_playback()
        self._schedule_preview_refresh()

    def _on_subtitle_style_preset_clicked(
        self, button: QtWidgets.QAbstractButton
    ) -> None:
        preset = button.property("preset")
        if not isinstance(preset, str):
            return
        self._on_subtitle_style_preset_changed(preset)

    def _on_background_mode_clicked(self, button: QtWidgets.QAbstractButton) -> None:
        mode = button.property("mode")
        if not isinstance(mode, str):
            return
        if mode == "word":
            return
        self._on_subtitle_style_custom_changed()

    def _on_subtitle_style_custom_changed(self) -> None:
        background_mode = self._current_background_mode()
        self._update_box_options_visibility(background_mode == "line")

        if self._subtitle_style_preset != PRESET_CUSTOM:
            self._subtitle_style_preset = PRESET_CUSTOM
            self._set_subtitle_style_preset_buttons(PRESET_CUSTOM)

        self._subtitle_style_custom = self._collect_custom_style_from_controls()
        self._style_model = self._subtitle_style_custom
        self._store_subtitle_style_config()
        self._invalidate_preview_playback()
        self._schedule_preview_refresh()

    def _schedule_preview_refresh(self) -> None:
        if self._preview_render_timer.isActive():
            self._preview_render_timer.stop()
        self._preview_render_timer.start()

    def _resolve_effective_subtitle_style(self) -> SubtitleStyle:
        return self._style_model

    def _resolve_preview_srt_path(self) -> Optional[Path]:
        if self._last_srt_path and self._last_srt_path.exists():
            return self._last_srt_path
        candidate = self._get_default_srt_path()
        if candidate and candidate.exists():
            return candidate
        return None

    def _refresh_preview_with_style(self) -> None:
        if not self._preview_timestamp_seconds or not self._video_path:
            self._update_preview_card()
            return
        style = self._resolve_effective_subtitle_style()
        preview_path = self._render_preview_frame(style)
        if preview_path:
            self._preview_frame_path = preview_path
        self._update_preview_card()

    def _render_preview_frame(self, style: SubtitleStyle) -> Optional[Path]:
        srt_path = self._resolve_preview_srt_path()
        if not srt_path or not self._preview_timestamp_seconds or not self._video_path:
            return None
        try:
            srt_mtime = int(srt_path.stat().st_mtime)
        except FileNotFoundError:
            srt_mtime = 0
        timestamp_ms = int(round(self._preview_timestamp_seconds * 1000))
        preview_width = 1280
        self._log(
            "Preview style resolved: "
            f"subtitle_mode={self._subtitle_mode} "
            f"background={style.background_mode} "
            f"shadow={style.shadow_strength} "
            f"shadow_opacity={style.shadow_opacity:.2f} "
            f"line_bg_opacity={style.line_bg_opacity:.2f}",
            True,
        )
        resolved_highlight_color = (
            self._highlight_color or style.highlight_color or DEFAULT_HIGHLIGHT_COLOR
        )
        resolved_highlight_opacity = (
            self._highlight_opacity
            if self._highlight_opacity is not None
            else DEFAULT_HIGHLIGHT_OPACITY
        )
        word_timings_mtime = None
        if self._subtitle_mode == "word_highlight":
            word_timings_path = word_timings_path_for_srt(srt_path)
            try:
                word_timings_mtime = int(word_timings_path.stat().st_mtime)
            except FileNotFoundError:
                word_timings_mtime = 0
        cache_name = (
            build_preview_cache_key(
                video_path=str(self._video_path.resolve()),
                srt_mtime=srt_mtime,
                word_timings_mtime=word_timings_mtime,
                timestamp_ms=timestamp_ms,
                preview_width=preview_width,
                style=style,
                subtitle_mode=self._subtitle_mode,
                highlight_color=resolved_highlight_color,
                highlight_opacity=resolved_highlight_opacity,
            )
            + ".png"
        )
        output_path = get_preview_frames_dir() / cache_name
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        try:
            raw_frame_path = None
            with tempfile.NamedTemporaryFile(
                dir=get_preview_frames_dir(), suffix=".jpg", delete=False
            ) as tmp:
                raw_frame_path = Path(tmp.name)
            if not extract_raw_frame(
                self._video_path,
                self._preview_timestamp_seconds,
                raw_frame_path,
                width=preview_width,
            ):
                raise RuntimeError("Failed to extract raw preview frame")
            frame_image = QtGui.QImage(str(raw_frame_path))
            if raw_frame_path and raw_frame_path.exists():
                try:
                    raw_frame_path.unlink()
                except OSError:
                    pass
            if frame_image.isNull():
                raise RuntimeError("Raw preview frame image could not be loaded")
            cues = parse_srt_file(srt_path)
            cue = select_cue_for_timestamp(cues, self._preview_timestamp_seconds)
            subtitle_text = cue.text if cue else ""
            result = render_graphics_preview(
                frame_image,
                subtitle_text=subtitle_text,
                style=style,
                subtitle_mode=self._subtitle_mode,
                highlight_color=resolved_highlight_color,
                highlight_opacity=resolved_highlight_opacity,
            )
            self._log(
                "Graphics preview: "
                f"mode={self._subtitle_mode} "
                f"bg={style.background_mode} "
                f"font={style.font_family} "
                f"size={style.font_size} "
                f"outline={style.outline_width if style.outline_enabled else 0} "
                f"shadow={style.shadow_strength if style.shadow_enabled else 0} "
                f"radius={style.line_bg_radius} "
                f"padding={style.line_bg_padding} "
                f"highlight_word_index={result.highlight_word_index}",
                True,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if not result.image.save(str(output_path), "PNG"):
                raise RuntimeError("Failed to save graphics preview image")
            return output_path
        except Exception as exc:
            if raw_frame_path and raw_frame_path.exists():
                try:
                    raw_frame_path.unlink()
                except OSError:
                    pass
            self._log(
                f"Graphics preview failed: {exc}; falling back to legacy preview",
                True,
            )

        word_timings_path = word_timings_path_for_srt(srt_path)
        if self._subtitle_mode == "word_highlight":
            pipeline = WORD_HIGHLIGHT_ASS_PIPELINE
            subtitles_path = output_path.with_suffix(".ass")
            filter_name = "ass"
        else:
            pipeline = STATIC_SRT_PIPELINE
            subtitles_path = srt_path
            filter_name = "subtitles"
        self._log(
            "Preview still render: "
            f"subtitle_mode={self._subtitle_mode} "
            f"pipeline={pipeline} "
            f"subtitles_path={subtitles_path} "
            f"filter={filter_name}",
            True,
        )
        if self._subtitle_mode == "word_highlight":
            style_config = build_style_config_from_subtitle_style(
                style,
                highlight_color=resolved_highlight_color,
                highlight_opacity=resolved_highlight_opacity,
            )
            cues = parse_srt_file(srt_path)
            decision = build_ass_document_with_karaoke_fallback(
                cues,
                srt_path=srt_path,
                word_timings_path=word_timings_path,
                style_config=style_config,
            )
            self._log(
                "Preview karaoke: "
                f"enabled={decision.karaoke_enabled} "
                f"reason={decision.reason} "
                f"word_timings_path={decision.word_timings_path} "
                f"highlight_events={decision.highlight_event_count}",
                True,
            )
            subtitles_path.write_text(decision.ass_text, encoding="utf-8")
            success = extract_ass_frame(
                self._video_path,
                subtitles_path,
                self._preview_timestamp_seconds,
                output_path,
                width=preview_width,
            )
        else:
            force_style = to_ffmpeg_force_style(style)
            alpha_byte = get_box_alpha_byte(style)
            legacy = legacy_style_from_model(style)
            self._log(
                "Preview style: "
                f"box_enabled={legacy.box_enabled} "
                f"box_opacity={legacy.box_opacity} "
                f"alpha={alpha_byte} "
                f"force_style={force_style}",
                True,
            )
            success = extract_subtitled_frame(
                self._video_path,
                srt_path,
                self._preview_timestamp_seconds,
                output_path,
                width=preview_width,
                force_style=force_style,
            )
        return output_path if success else None

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

        audio_card = self._build_settings_section("Audio")
        audio_layout = audio_card.layout()
        audio_filter_help = QtWidgets.QLabel(
            "May help noisy recordings, but can reduce punctuation. Recommended: OFF unless needed."
        )
        audio_filter_help.setObjectName("SettingsHelperText")
        audio_filter_help.setWordWrap(True)
        audio_filter_help.setIndent(24)
        keep_audio_help = QtWidgets.QLabel(
            "Keeps the *_audio_for_whisper.wav file after transcription completes."
        )
        keep_audio_help.setObjectName("SettingsHelperText")
        keep_audio_help.setWordWrap(True)
        keep_audio_help.setIndent(24)
        audio_layout.addWidget(self.filter_checkbox)
        audio_layout.addWidget(audio_filter_help)
        audio_layout.addWidget(self.keep_extracted_audio_checkbox)
        audio_layout.addWidget(keep_audio_help)
        layout.addWidget(audio_card)

        diagnostics_card = self._build_settings_section("Diagnostics")
        diagnostics_layout = diagnostics_card.layout()

        self.diagnostics_archive_checkbox = QtWidgets.QCheckBox(
            "Zip logs and outputs on exit"
        )
        self.diagnostics_enabled_checkbox = QtWidgets.QCheckBox("Enable diagnostics logging")
        self.diagnostics_success_checkbox = QtWidgets.QCheckBox(
            "Write diagnostics on successful completion"
        )

        diagnostics_layout.addWidget(self.diagnostics_archive_checkbox)
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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        try:
            self._archive_exit_bundle()
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Failed to archive logs on exit: %s", exc)
        super().closeEvent(event)

    def set_state(self, state: AppState) -> None:
        self._state = state
        page_index = self._state_pages.get(state, 0)
        self.stack.setCurrentIndex(page_index)
        self._update_ui_state(idle=state != AppState.WORKING)
        if state == AppState.SUBTITLES_READY:
            self._refresh_preview_with_style()
        else:
            self._stop_preview_playback(clear_media=True)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_preview_image()

    def _update_preview_card(self) -> None:
        if not hasattr(self, "preview_image_label"):
            return
        if self._preview_frame_path and self._preview_frame_path.exists():
            pixmap = QtGui.QPixmap(str(self._preview_frame_path))
        else:
            pixmap = QtGui.QPixmap()

        if pixmap.isNull():
            self._preview_pixmap = None
            self.preview_image_label.setPixmap(QtGui.QPixmap())
            self.preview_image_label.setText("Preview unavailable")
            self.preview_image_label.setAlignment(QtCore.Qt.AlignCenter)
        else:
            self._preview_pixmap = pixmap
            self.preview_image_label.setText("")
            self.preview_image_label.setAlignment(QtCore.Qt.AlignCenter)
            self._update_preview_image()
        self._update_preview_controls_availability()

    def _update_preview_image(self) -> None:
        if not hasattr(self, "preview_image_label"):
            return
        if not self._preview_pixmap or self._preview_pixmap.isNull():
            return
        scaled = self._preview_pixmap.scaled(
            self.preview_image_label.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.preview_image_label.setPixmap(scaled)

    def _connect_preview_playback_controller(self) -> None:
        self._preview_playback_controller.clip_ready.connect(self._on_preview_clip_ready)
        self._preview_playback_controller.clip_failed.connect(self._on_preview_clip_failed)
        self._preview_playback_controller.clip_loading.connect(self._on_preview_clip_loading)

    def _update_preview_controls_availability(self) -> None:
        if not self.preview_play_button:
            return
        ready = bool(self._preview_timestamp_seconds and self._resolve_preview_srt_path())
        self.preview_play_button.setEnabled(ready and not self._preview_loading)
        if not ready and self.preview_stop_button and self.preview_scrub_slider:
            self.preview_stop_button.setEnabled(False)
            self.preview_scrub_slider.setEnabled(False)
            if self.preview_time_label:
                self.preview_time_label.setText("0:00 / 0:00")

    def _set_preview_controls_enabled(self, enabled: bool) -> None:
        if self.preview_stop_button:
            self.preview_stop_button.setEnabled(enabled)
        if self.preview_scrub_slider:
            self.preview_scrub_slider.setEnabled(enabled)

    def _set_preview_status_message(self, message: str) -> None:
        if self.preview_status_label:
            self.preview_status_label.setText(message)

    def _on_preview_play_clicked(self) -> None:
        if not self.preview_media_player:
            return
        if (
            self.preview_media_player.playbackState()
            == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState
        ):
            self.preview_media_player.pause()
            return

        if (
            self.preview_media_player.mediaStatus()
            != QtMultimedia.QMediaPlayer.MediaStatus.NoMedia
        ):
            self._switch_preview_mode(playback=True)
            self.preview_media_player.play()
            return

        if not self._preview_timestamp_seconds or not self._video_path:
            return
        srt_path = self._resolve_preview_srt_path()
        if not srt_path:
            return
        self._ensure_word_timings_for_srt(srt_path)
        self._log_word_timing_status(srt_path)
        self._run_alignment_if_needed(srt_path, context="preview")
        style = self._resolve_effective_subtitle_style()
        force_style = to_ffmpeg_force_style(style)
        self._preview_play_request_pending = True
        self._set_preview_status_message("")
        self._preview_playback_controller.request_clip(
            video_path=self._video_path,
            srt_path=srt_path,
            anchor_seconds=self._preview_timestamp_seconds,
            clip_start_seconds=self._preview_clip_start_seconds,
            clip_duration_seconds=self._preview_clip_duration_seconds,
            force_style=force_style,
            subtitle_mode=self._subtitle_mode,
            style=style,
            highlight_color=self._highlight_color,
            highlight_opacity=self._highlight_opacity,
        )

    def _on_preview_stop_clicked(self) -> None:
        self._stop_preview_playback(clear_media=False)

    def _stop_preview_playback(self, *, clear_media: bool) -> None:
        if self.preview_media_player:
            self.preview_media_player.stop()
            if clear_media:
                self.preview_media_player.setSource(QtCore.QUrl())
                self._preview_clip_path = None
        self._switch_preview_mode(playback=False)
        self._preview_play_request_pending = False
        if self.preview_scrub_slider:
            self.preview_scrub_slider.blockSignals(True)
            self.preview_scrub_slider.setValue(0)
            self.preview_scrub_slider.blockSignals(False)
        if self.preview_time_label:
            self.preview_time_label.setText("0:00 / 0:00")
        self._set_preview_controls_enabled(False)
        self._update_preview_controls_availability()

    def _invalidate_preview_playback(self) -> None:
        self._stop_preview_playback(clear_media=True)
        self._preview_playback_controller.invalidate_current_clip()
        self._set_preview_status_message("")

    def _switch_preview_mode(self, *, playback: bool) -> None:
        if not self.preview_stack:
            return
        self.preview_stack.setCurrentIndex(1 if playback else 0)

    def _on_preview_clip_ready(self, path: str) -> None:
        self._preview_clip_path = Path(path)
        self._set_preview_status_message("")
        if not self._preview_play_request_pending:
            return
        self._preview_play_request_pending = False
        if not self.preview_media_player:
            return
        self.preview_media_player.setSource(QtCore.QUrl.fromLocalFile(path))
        self._switch_preview_mode(playback=True)
        self.preview_media_player.play()
        self._set_preview_controls_enabled(True)

    def _on_preview_clip_failed(self, message: str) -> None:
        self._preview_play_request_pending = False
        self._set_preview_controls_enabled(False)
        self._set_preview_status_message(message)
        self._switch_preview_mode(playback=False)

    def _on_preview_clip_loading(self, loading: bool) -> None:
        self._preview_loading = loading
        if self.preview_play_button:
            self.preview_play_button.setEnabled(not loading)
            if loading:
                self.preview_play_button.setText("Loading…")
            else:
                self.preview_play_button.setText("Play")

    def _on_preview_playback_state_changed(
        self, state: QtMultimedia.QMediaPlayer.PlaybackState
    ) -> None:
        if not self.preview_play_button:
            return
        if state == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
            self.preview_play_button.setText("Pause")
            self._set_preview_controls_enabled(True)
        else:
            self.preview_play_button.setText("Play")

    def _on_preview_media_status_changed(
        self, status: QtMultimedia.QMediaPlayer.MediaStatus
    ) -> None:
        if not self.preview_media_player:
            return
        if status == QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia:
            self._stop_preview_playback(clear_media=False)

    def _on_preview_player_error(self, error: QtMultimedia.QMediaPlayer.Error) -> None:
        if error == QtMultimedia.QMediaPlayer.Error.NoError:
            return
        if not self.preview_media_player:
            return
        self._log(f"Preview playback error: {self.preview_media_player.errorString()}", True)
        self._set_preview_status_message("Preview playback unavailable.")
        self._stop_preview_playback(clear_media=False)

    def _on_preview_position_changed(self, position: int) -> None:
        if self._preview_slider_dragging or not self.preview_scrub_slider:
            return
        self.preview_scrub_slider.setValue(position)
        if self.preview_media_player:
            self._update_preview_time_label(position, self.preview_media_player.duration())

    def _on_preview_duration_changed(self, duration: int) -> None:
        if self.preview_scrub_slider:
            self.preview_scrub_slider.setRange(0, max(duration, 0))
        if self.preview_media_player:
            self._update_preview_time_label(self.preview_media_player.position(), duration)

    def _on_preview_slider_pressed(self) -> None:
        if not self.preview_scrub_slider:
            return
        self._preview_slider_dragging = True

    def _on_preview_slider_released(self) -> None:
        self._preview_slider_dragging = False
        if self.preview_media_player and self.preview_scrub_slider:
            self.preview_media_player.setPosition(self.preview_scrub_slider.value())

    def _on_preview_slider_moved(self, value: int) -> None:
        if self._preview_slider_dragging and self.preview_media_player:
            self.preview_media_player.setPosition(value)
            self._update_preview_time_label(value, self.preview_media_player.duration())

    def _update_preview_time_label(self, position_ms: int, duration_ms: int) -> None:
        if not self.preview_time_label:
            return
        current_seconds = max(0.0, position_ms / 1000.0)
        total_seconds = max(0.0, duration_ms / 1000.0)
        self.preview_time_label.setText(
            f"{format_duration(current_seconds)} / {format_duration(total_seconds)}"
        )

    def _open_preview_dialog(self) -> None:
        if not self._preview_pixmap or self._preview_pixmap.isNull():
            return

        class PreviewDialog(QtWidgets.QDialog):
            def __init__(self, pixmap: QtGui.QPixmap, parent: QtWidgets.QWidget) -> None:
                super().__init__(parent)
                self._pixmap = pixmap
                self.setWindowTitle("Preview")
                self.setMinimumSize(720, 405)
                layout = QtWidgets.QVBoxLayout(self)
                self._label = QtWidgets.QLabel()
                self._label.setAlignment(QtCore.Qt.AlignCenter)
                self._label.setSizePolicy(
                    QtWidgets.QSizePolicy.Expanding,
                    QtWidgets.QSizePolicy.Expanding,
                )
                layout.addWidget(self._label)
                self._update_pixmap()

            def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
                super().resizeEvent(event)
                self._update_pixmap()

            def _update_pixmap(self) -> None:
                scaled = self._pixmap.scaled(
                    self._label.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
                self._label.setPixmap(scaled)

        dialog = PreviewDialog(self._preview_pixmap, self)
        dialog.exec()

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
            keep_extracted_audio=self.keep_extracted_audio_checkbox.isChecked(),
            device=device,
            compute_type=compute_type,
            quality=self._transcription_quality.value,
            punctuation_rescue_fallback_enabled=self._punctuation_rescue_fallback_enabled,
        )
        style = self._resolve_effective_subtitle_style()
        self._start_worker(
            TaskType.GENERATE_SRT,
            self._video_path,
            None,
            settings,
            style,
            self._subtitle_mode,
        )

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

        style = self._resolve_effective_subtitle_style()
        self._start_worker(
            TaskType.BURN_IN, self._video_path, srt_path, None, style, self._subtitle_mode
        )

    def _start_worker(
        self,
        task_type: str,
        video_path: Path,
        srt_path: Optional[Path],
        transcription_settings: Optional[TranscriptionSettings],
        subtitle_style: Optional[SubtitleStyle],
        subtitle_mode: str = "static",
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
            subtitle_style=subtitle_style,
            subtitle_mode=subtitle_mode,
            highlight_color=self._highlight_color,
            highlight_opacity=self._highlight_opacity,
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
        if payload.get("word_timings_path"):
            candidate = Path(payload["word_timings_path"])
            self._word_timings_path = candidate if candidate.exists() else None
        if payload.get("output_path"):
            candidate = Path(payload["output_path"])
            self._last_output_video = candidate if candidate.exists() else None
        if task_type == TaskType.GENERATE_SRT:
            frame_value = payload.get("preview_frame_path")
            self._preview_frame_path = Path(frame_value) if frame_value else None
            self._preview_subtitle_text = payload.get("preview_subtitle_text")
            self._preview_timestamp_seconds = payload.get("preview_timestamp_seconds")
            self._preview_clip_start_seconds = payload.get("preview_clip_start_seconds")
            self._preview_clip_duration_seconds = payload.get("preview_clip_duration_seconds")
            self._invalidate_preview_playback()

        if success:
            if task_type == TaskType.GENERATE_SRT:
                self._subtitles_reviewed = False
                self.set_state(AppState.SUBTITLES_READY)
                self._update_preview_card()
            else:
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

        self.diagnostics_archive_checkbox.blockSignals(True)
        self.diagnostics_archive_checkbox.setChecked(
            self._diagnostics_settings.archive_on_exit
        )
        self.diagnostics_archive_checkbox.blockSignals(False)

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

        self.filter_checkbox.blockSignals(True)
        self.filter_checkbox.setChecked(self._apply_audio_filter_enabled)
        self.filter_checkbox.blockSignals(False)

        self.keep_extracted_audio_checkbox.blockSignals(True)
        self.keep_extracted_audio_checkbox.setChecked(self._keep_extracted_audio_enabled)
        self.keep_extracted_audio_checkbox.blockSignals(False)

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

    def _archive_exit_bundle(self) -> None:
        if not self._diagnostics_settings.archive_on_exit:
            return
        if not self._video_path or not self._video_path.exists():
            return

        destination_dir = self._video_path.parent
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = destination_dir / f"hebrew_subtitles_bundle_{timestamp}.zip"
        entries = self._build_exit_archive_entries(zip_path)
        if not entries:
            return
        try:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for source, arcname in entries:
                    archive.write(source, arcname)
            self._logger.info("Exit archive created: %s", zip_path)
        except Exception:
            zip_path.unlink(missing_ok=True)
            raise

    def _build_exit_archive_entries(self, zip_path: Path) -> list[tuple[Path, str]]:
        entries: dict[str, Path] = {}
        if self._log_path.exists():
            entries.setdefault(f"logs/{self._log_path.name}", self._log_path)

        output_dir = self._output_dir or (self._video_path.parent if self._video_path else None)
        if output_dir and output_dir.exists():
            for path in output_dir.glob("diag_*.json"):
                if path.is_file() and path != zip_path:
                    entries.setdefault(f"diagnostics/{path.name}", path)

        for path in self._collect_output_files(output_dir, zip_path):
            entries.setdefault(f"outputs/{path.name}", path)

        return [(path, arcname) for arcname, path in entries.items()]

    def _collect_output_files(self, output_dir: Optional[Path], zip_path: Path) -> set[Path]:
        output_files: set[Path] = set()
        if not self._video_path:
            return output_files
        video_stem = self._video_path.stem
        resolved_output_dir = output_dir or self._video_path.parent
        if resolved_output_dir.exists():
            for path in resolved_output_dir.iterdir():
                if not path.is_file():
                    continue
                if path == self._video_path or path == zip_path:
                    continue
                if path.name.startswith(video_stem):
                    output_files.add(path)

        for path in (self._last_srt_path, self._word_timings_path, self._last_output_video):
            if path and path.exists():
                output_files.add(path)

        audio_path = resolved_output_dir / f"{video_stem}_audio_for_whisper.wav"
        if audio_path.exists():
            output_files.add(audio_path)

        output_files.discard(self._video_path)
        output_files.discard(zip_path)
        return output_files

    def _store_diagnostics_settings(self) -> None:
        self._config["diagnostics"] = {
            "enabled": self._diagnostics_settings.enabled,
            "write_on_success": self._diagnostics_settings.write_on_success,
            "archive_on_exit": self._diagnostics_settings.archive_on_exit,
            "categories": dict(self._diagnostics_settings.categories),
        }
        self._save_config()

    def _on_diagnostics_archive_toggled(self, checked: bool) -> None:
        if checked == self._diagnostics_settings.archive_on_exit:
            return
        self._diagnostics_settings.archive_on_exit = checked
        self._store_diagnostics_settings()

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

    def _on_audio_filter_toggled(self, checked: bool) -> None:
        if checked == self._apply_audio_filter_enabled:
            return
        self._apply_audio_filter_enabled = checked
        self._config["apply_audio_filter"] = checked
        self._save_config()

    def _on_keep_extracted_audio_toggled(self, checked: bool) -> None:
        if checked == self._keep_extracted_audio_enabled:
            return
        self._keep_extracted_audio_enabled = checked
        self._config["keep_extracted_audio"] = checked
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
        can_burn = idle and has_video and ffmpeg_ready and srt_ready
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
        self.burn_button.setEnabled(can_burn and self._state == AppState.SUBTITLES_READY)
        self.cancel_button.setEnabled(self._state == AppState.WORKING and not idle)

        done_state = self._state == AppState.EXPORT_DONE
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
        self._word_timings_path = None
        self._last_output_video = None
        self._subtitles_reviewed = False
        self._output_dir = None
        self._progress_controller = None
        self._preview_frame_path = None
        self._preview_subtitle_text = None
        self._preview_timestamp_seconds = None
        self._preview_clip_start_seconds = None
        self._preview_clip_duration_seconds = None
        self._preview_pixmap = None
        self._preview_clip_path = None
        self._stop_preview_playback(clear_media=True)
        self._update_preview_card()

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
            raw = {}
        else:
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                raw = {}
        return apply_config_defaults(raw)

    def _save_subtitle_edit_path(self, path: Path) -> None:
        self._config["subtitle_edit_path"] = str(path)
        self._save_config()

    def _save_config(self) -> None:
        self._config = apply_config_defaults(self._config)
        self._subtitle_mode = self._config["subtitle_mode"]
        self._highlight_color = self._config["subtitle_style"]["highlight_color"]
        self._highlight_opacity = self._config["subtitle_style"]["highlight_opacity"]
        self._style_model = normalize_style_model(
            self._config["subtitle_style"].get("appearance"),
            self._style_model,
        )
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

    def _ensure_word_timings_for_srt(self, srt_path: Path) -> Path:
        word_timings_path = word_timings_path_for_srt(srt_path)
        self._word_timings_path = word_timings_path
        if word_timings_path.exists():
            return word_timings_path
        cues = parse_srt_file(srt_path)
        cue_payload = [
            (idx + 1, cue.start_seconds, cue.end_seconds, cue.text)
            for idx, cue in enumerate(cues)
        ]
        try:
            doc = build_word_timing_stub(
                language="he",
                srt_sha256=compute_srt_sha256(srt_path),
                cues=cue_payload,
            )
            save_word_timings_json(word_timings_path, doc)
            self._log(
                f"Word timings created: {word_timings_path} (schema v{SCHEMA_VERSION})",
                True,
            )
        except Exception as exc:  # noqa: BLE001
            self._log(
                f"Warning: failed to create word timings file ({word_timings_path}): {exc}",
                True,
            )
        return word_timings_path

    def _log_word_timing_status(self, srt_path: Path) -> None:
        word_timings_path = word_timings_path_for_srt(srt_path)
        stale = is_word_timing_stale(word_timings_path, srt_path)
        self._log(f"Word timings: path={word_timings_path}", True)
        self._log(f"Word timings stale? {str(stale).lower()}", True)
        try:
            doc = load_word_timings_json(word_timings_path)
        except (WordTimingValidationError, OSError) as exc:
            self._log(f"Word timings load failed: {exc}", True)
        else:
            total_words = sum(len(cue.words) for cue in doc.cues)
            self._log(f"Word timings total_words={total_words}", True)
        if stale:
            self._log(
                "Word timings stale. Alignment must be regenerated (Task 8).",
                True,
            )

    def _run_alignment_if_needed(self, srt_path: Path, *, context: str) -> None:
        plan = build_alignment_plan(
            subtitle_mode=self._subtitle_mode,
            srt_path=srt_path,
            audio_path=audio_path_for_srt(srt_path),
            language="he",
            prefer_gpu=True,
        )
        self._log(
            "Alignment needed? "
            f"{str(plan.should_run).lower()} reason={plan.reason} (context={context})",
            True,
        )
        if not plan.should_run:
            return
        if plan.reason == "word_timings_has_no_words":
            self._log(
                "Alignment needed: word_timings_has_no_words",
                True,
            )
        if not plan.output_path.parent.exists():
            plan.output_path.parent.mkdir(parents=True, exist_ok=True)
        if not audio_path_for_srt(srt_path).exists():
            self._log(
                f"Alignment skipped: audio not found ({audio_path_for_srt(srt_path)})",
                True,
            )
            return
        self._log(
            "Alignment starting: "
            f"wav={audio_path_for_srt(srt_path)} srt={srt_path} output={plan.output_path} "
            f"device={plan.device or 'auto'} model={plan.align_model or 'default'}",
            True,
        )
        self._log(f"Alignment command: {subprocess.list2cmdline(plan.command)}", True)
        result = subprocess.run(
            plan.command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            **get_subprocess_kwargs(),
        )
        if result.stdout:
            for line in result.stdout.splitlines():
                self._log(line, True)
        if result.stderr:
            for line in result.stderr.splitlines():
                self._log(line, True)
        self._log(
            f"Alignment finished: exit_code={result.returncode} output={plan.output_path}",
            True,
        )
        if result.returncode != 0:
            self._log(
                "Alignment failed; continuing with static rendering.",
                True,
            )


    def _load_subtitle_style(self) -> tuple[str, SubtitleStyle, SubtitleStyle]:
        preset = PRESET_DEFAULT
        raw = self._config.get("subtitle_style")
        if not isinstance(raw, dict):
            raw = {}

        preset_value = raw.get("preset")
        if isinstance(preset_value, str) and preset_value in PRESET_NAMES:
            preset = preset_value

        subtitle_mode = self._config.get("subtitle_mode", "static")
        highlight_color = raw.get("highlight_color", DEFAULT_HIGHLIGHT_COLOR)
        legacy_defaults = legacy_preset_defaults(PRESET_DEFAULT)
        legacy_custom = legacy_style_from_custom_dict(raw.get("custom"), legacy_defaults)
        custom = style_model_from_legacy(
            legacy_custom,
            subtitle_mode=subtitle_mode,
            highlight_color=highlight_color,
        )
        if preset == PRESET_CUSTOM:
            custom = normalize_style_model(raw.get("appearance"), custom)

        effective_fallback = (
            custom
            if preset == PRESET_CUSTOM
            else preset_defaults(
                preset,
                subtitle_mode=subtitle_mode,
                highlight_color=highlight_color,
            )
        )
        effective_style = normalize_style_model(raw.get("appearance"), effective_fallback)
        return preset, custom, effective_style

    def _store_subtitle_style_config(self) -> None:
        current_style = self._config.get("subtitle_style")
        highlight_color = (
            current_style.get("highlight_color")
            if isinstance(current_style, dict)
            else self._highlight_color
        )
        highlight_opacity = (
            current_style.get("highlight_opacity")
            if isinstance(current_style, dict)
            else self._highlight_opacity
        )
        legacy_custom = legacy_style_from_model(self._subtitle_style_custom)
        self._config["subtitle_style"] = {
            "preset": self._subtitle_style_preset,
            "highlight_color": highlight_color,
            "highlight_opacity": highlight_opacity,
            "appearance": style_model_to_dict(self._style_model),
            "custom": {
                "font_size": legacy_custom.font_size,
                "outline": legacy_custom.outline,
                "shadow": legacy_custom.shadow,
                "margin_v": legacy_custom.margin_v,
                "box_enabled": legacy_custom.box_enabled,
                "box_opacity": legacy_custom.box_opacity,
                "box_padding": legacy_custom.box_padding,
            },
        }
        self._config["subtitle_mode"] = self._subtitle_mode
        self._save_config()

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
                archive_on_exit=False,
                categories=default_categories.copy(),
            )
        enabled = raw.get("enabled") if isinstance(raw.get("enabled"), bool) else False
        write_on_success = (
            raw.get("write_on_success")
            if isinstance(raw.get("write_on_success"), bool)
            else False
        )
        archive_on_exit = (
            raw.get("archive_on_exit")
            if isinstance(raw.get("archive_on_exit"), bool)
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
            archive_on_exit=archive_on_exit,
            categories=categories,
        )

    def _load_punctuation_rescue_fallback_enabled(self) -> bool:
        value = self._config.get("punctuation_rescue_fallback_enabled")
        if isinstance(value, bool):
            return value
        return True

    def _load_apply_audio_filter_enabled(self) -> bool:
        value = self._config.get("apply_audio_filter")
        if isinstance(value, bool):
            return value
        return False

    def _load_keep_extracted_audio_enabled(self) -> bool:
        value = self._config.get("keep_extracted_audio")
        if isinstance(value, bool):
            return value
        return False

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
