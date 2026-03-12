from __future__ import annotations

import json

from app.config import (
    DEFAULT_HIGHLIGHT_COLOR,
    DEFAULT_HIGHLIGHT_OPACITY,
    apply_config_defaults,
)


def test_apply_config_defaults_adds_missing_keys() -> None:
    config: dict = {}
    result = apply_config_defaults(config)
    assert result["subtitle_mode"] == "static"
    assert result["subtitle_style"]["highlight_color"] == DEFAULT_HIGHLIGHT_COLOR
    assert result["subtitle_style"]["highlight_opacity"] == DEFAULT_HIGHLIGHT_OPACITY
    appearance = result["subtitle_style"]["appearance"]
    assert appearance["font_weight"] == 400
    assert appearance["font_family"] == "Assistant"
    assert appearance["font_size"] == 44
    assert appearance["text_align"] == "center"
    assert appearance["line_spacing"] == 1.0
    assert appearance["text_color"] == "#FFFFFF"
    assert appearance["text_opacity"] == 1.0
    assert appearance["letter_spacing"] == 0.0
    assert appearance["outline_enabled"] is False
    assert appearance["outline_width"] == 0.0
    assert appearance["shadow_enabled"] is False
    assert appearance["shadow_strength"] == 0.0


def test_apply_config_defaults_fills_partial_style() -> None:
    config = {"subtitle_style": {"preset": "Default"}}
    result = apply_config_defaults(config)
    style = result["subtitle_style"]
    assert style["highlight_color"] == DEFAULT_HIGHLIGHT_COLOR
    assert style["highlight_opacity"] == DEFAULT_HIGHLIGHT_OPACITY
    assert style["appearance"]["font_weight"] == 400


def test_apply_config_defaults_round_trip() -> None:
    config = {
        "subtitle_mode": "static",
        "subtitle_style": {
            "highlight_color": "#AABBCC",
            "highlight_opacity": 0.25,
        },
    }
    result = apply_config_defaults(config)
    payload = json.loads(json.dumps(result))
    assert payload["subtitle_mode"] == "static"
    assert payload["subtitle_style"]["highlight_color"] == "#AABBCC"
    assert payload["subtitle_style"]["highlight_opacity"] == 0.25
