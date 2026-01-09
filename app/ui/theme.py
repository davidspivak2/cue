from __future__ import annotations

import logging
from importlib import resources
from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets

ACCENT = "#5E6AD2"
BG = "#0B0F14"
SURFACE = "#111827"
SURFACE_2 = "#0F172A"
TEXT = "#E5E7EB"
MUTED_TEXT = "#9CA3AF"
BORDER = "#1F2937"
RADIUS = 10
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16


def _theme_tokens() -> dict[str, str]:
    return {
        "ACCENT": ACCENT,
        "BG": BG,
        "SURFACE": SURFACE,
        "SURFACE_2": SURFACE_2,
        "TEXT": TEXT,
        "MUTED_TEXT": MUTED_TEXT,
        "BORDER": BORDER,
        "RADIUS": str(RADIUS),
        "SPACING_SM": str(SPACING_SM),
        "SPACING_MD": str(SPACING_MD),
        "SPACING_LG": str(SPACING_LG),
    }


def load_stylesheet() -> str:
    stylesheet_path = Path(__file__).with_name("styles.qss")
    try:
        try:
            raw_qss = resources.files("app.ui").joinpath("styles.qss").read_text(encoding="utf-8")
        except Exception:
            raw_qss = stylesheet_path.read_text(encoding="utf-8")
        return raw_qss.format(**_theme_tokens())
    except Exception:
        return (
            "QWidget {{ background-color: {BG}; color: {TEXT}; }}\n"
            "QLineEdit, QPlainTextEdit, QTextEdit {{\n"
            "  background-color: {SURFACE};\n"
            "  color: {TEXT};\n"
            "  border: 1px solid {BORDER};\n"
            "  border-radius: {RADIUS}px;\n"
            "  padding: 6px;\n"
            "}}\n"
            "QPushButton {{\n"
            "  background-color: {SURFACE_2};\n"
            "  color: {TEXT};\n"
            "  border: 1px solid {BORDER};\n"
            "  border-radius: {RADIUS}px;\n"
            "  padding: 6px 10px;\n"
            "}}\n"
            "QProgressBar::chunk {{ background-color: {ACCENT}; }}\n"
        ).format(**_theme_tokens())


def apply_theme(
    app: QtWidgets.QApplication, logger: Optional[logging.Logger] = None
) -> None:
    try:
        app.setStyle("Fusion")
        app.setStyleSheet(load_stylesheet())
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warning("Failed to apply theme: %s", exc)
