from __future__ import annotations

import re

DEFAULT_SUBTITLE_MODE = "static"
DEFAULT_HIGHLIGHT_COLOR = "#FFD400"
DEFAULT_HIGHLIGHT_OPACITY = 1.0
VALID_SUBTITLE_MODES = {"word_highlight", "static"}

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _normalize_subtitle_mode(value: object) -> str:
    if isinstance(value, str) and value in VALID_SUBTITLE_MODES:
        return value
    return DEFAULT_SUBTITLE_MODE


def _normalize_highlight_color(value: object) -> str:
    if isinstance(value, str) and _HEX_COLOR_RE.match(value):
        return value
    return DEFAULT_HIGHLIGHT_COLOR


def _normalize_highlight_opacity(value: object) -> float:
    if isinstance(value, bool):
        return DEFAULT_HIGHLIGHT_OPACITY
    if isinstance(value, (int, float)):
        opacity = float(value)
        if 0.0 <= opacity <= 1.0:
            return opacity
    return DEFAULT_HIGHLIGHT_OPACITY


def apply_config_defaults(config: dict) -> dict:
    if not isinstance(config, dict):
        config = {}
    config["subtitle_mode"] = _normalize_subtitle_mode(config.get("subtitle_mode"))
    raw_style = config.get("subtitle_style")
    if not isinstance(raw_style, dict):
        raw_style = {}
        config["subtitle_style"] = raw_style
    raw_style["highlight_color"] = _normalize_highlight_color(
        raw_style.get("highlight_color")
    )
    raw_style["highlight_opacity"] = _normalize_highlight_opacity(
        raw_style.get("highlight_opacity")
    )
    return config
