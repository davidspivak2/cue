from __future__ import annotations

import re

from app.subtitle_style import (
    PRESET_CUSTOM,
    PRESET_DEFAULT,
    PRESET_NAMES,
    normalize_style_model,
    preset_style_defaults,
    preset_style_from_custom_dict,
    style_model_from_preset,
    style_model_to_dict,
)

DEFAULT_SUBTITLE_MODE = "static"
DEFAULT_HIGHLIGHT_COLOR = "#FFD400"
DEFAULT_HIGHLIGHT_OPACITY = 1.0
VALID_SUBTITLE_MODES = {"word_highlight", "static"}

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

_LEGACY_DEFAULT_APPEARANCE = {
    "font_family": "Assistant",
    "font_size": 44,
    "font_style": "regular",
    "font_weight": 400,
    "text_align": "center",
    "line_spacing": 1.0,
    "text_color": "#FFFFFF",
    "text_opacity": 1.0,
    "letter_spacing": 0.0,
    "outline_enabled": False,
    "outline_width": 0.0,
    "outline_color": "#000000",
    "shadow_enabled": False,
    "shadow_strength": 0.0,
    "shadow_offset_x": 0.0,
    "shadow_offset_y": 0.0,
    "shadow_color": "#000000",
    "shadow_opacity": 1.0,
    "shadow_blur": 10.0,
    "background_mode": "none",
    "line_bg_color": "#000000",
    "line_bg_opacity": 0.7,
    "line_bg_padding": 8.0,
    "line_bg_padding_top": 8.0,
    "line_bg_padding_right": 8.0,
    "line_bg_padding_bottom": 8.0,
    "line_bg_padding_left": 8.0,
    "line_bg_radius": 8.0,
    "vertical_anchor": "bottom",
    "vertical_offset": 28.0,
    "subtitle_mode": "static",
    "highlight_color": "#FFD400",
}


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


def _is_legacy_default_appearance(appearance: dict[str, object]) -> bool:
    return all(appearance.get(key) == value for key, value in _LEGACY_DEFAULT_APPEARANCE.items())


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
    preset_value = raw_style.get("preset")
    preset = preset_value if isinstance(preset_value, str) and preset_value in PRESET_NAMES else PRESET_DEFAULT
    if preset_value != preset:
        raw_style["preset"] = preset
    preset_defaults_style = preset_style_defaults(PRESET_DEFAULT)
    preset_custom = preset_style_from_custom_dict(
        raw_style.get("custom"),
        preset_defaults_style,
    )
    preset_effective = (
        preset_custom if preset == PRESET_CUSTOM else preset_style_defaults(preset)
    )
    fallback_style = style_model_from_preset(
        preset_effective,
        subtitle_mode=config["subtitle_mode"],
        highlight_color=highlight_color,
        preset_name=preset,
    )
    style_model = normalize_style_model(raw_style.get("appearance"), fallback_style)
    if preset == PRESET_DEFAULT and _is_legacy_default_appearance(style_model_to_dict(style_model)):
        style_model = fallback_style
    raw_style["appearance"] = style_model_to_dict(style_model)
    config["subtitle_mode"] = style_model.subtitle_mode
    raw_style["highlight_color"] = style_model.highlight_color
    return config
