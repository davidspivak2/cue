from __future__ import annotations

import json
import re
from typing import Any

from app.paths import get_config_path
from app.subtitle_style import (
    normalize_style_model,
    resolve_effective_preset_style,
    style_model_from_preset,
    style_model_to_dict,
)

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


def diagnostics_enabled(config: dict[str, Any] | Any) -> bool:
    if not isinstance(config, dict):
        return False
    raw_diagnostics = config.get("diagnostics")
    return isinstance(raw_diagnostics, dict) and raw_diagnostics.get("enabled") is True


def read_diagnostics_enabled() -> bool:
    config_path = get_config_path()
    if not config_path.exists():
        return False
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return diagnostics_enabled(raw)


def apply_config_defaults(config: dict) -> dict:
    if not isinstance(config, dict):
        config = {}
    config["subtitle_mode"] = _normalize_subtitle_mode(config.get("subtitle_mode"))
    raw_style = config.get("subtitle_style")
    if not isinstance(raw_style, dict):
        raw_style = {}
        config["subtitle_style"] = raw_style
    highlight_color = _normalize_highlight_color(raw_style.get("highlight_color"))
    raw_style["highlight_color"] = highlight_color
    raw_style["highlight_opacity"] = _normalize_highlight_opacity(
        raw_style.get("highlight_opacity")
    )
    preset, preset_style = resolve_effective_preset_style(raw_style)
    if raw_style.get("preset") != preset:
        raw_style["preset"] = preset
    fallback_style = style_model_from_preset(
        preset_style,
        subtitle_mode=config["subtitle_mode"],
        highlight_color=highlight_color,
        preset_name=preset,
    )
    style_model = normalize_style_model(raw_style.get("appearance"), fallback_style)
    raw_style["appearance"] = style_model_to_dict(style_model)
    config["subtitle_mode"] = style_model.subtitle_mode
    raw_style["highlight_color"] = style_model.highlight_color
    return config
