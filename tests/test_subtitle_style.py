from __future__ import annotations

from app.subtitle_style import (
    PRESET_DEFAULT,
    normalize_style_model,
    normalize_style_payload,
    preset_defaults,
    shadow_offset_from_polar,
    shadow_offset_to_polar,
)


def test_normalize_style_model_derives_font_weight_from_legacy_bold_style() -> None:
    fallback = preset_defaults(PRESET_DEFAULT)

    style = normalize_style_model({"font_style": "bold"}, fallback)

    assert style.font_weight == 700
    assert style.text_align == "center"
    assert style.line_spacing == 1.0


def test_default_preset_starts_static_with_effects_off() -> None:
    style = preset_defaults(PRESET_DEFAULT)

    assert style.font_family == "Heebo"
    assert style.font_size == 28
    assert style.font_style == "regular"
    assert style.text_color == "#FFFFFF"
    assert style.text_align == "center"
    assert style.line_spacing == 1.0
    assert style.text_opacity == 1.0
    assert style.letter_spacing == 0.0
    assert style.outline_enabled is True
    assert style.outline_width == 1
    assert style.shadow_enabled is False
    assert style.shadow_strength == 0.0
    assert style.subtitle_mode == "static"


def test_normalize_style_model_preserves_explicit_font_weight() -> None:
    fallback = preset_defaults(PRESET_DEFAULT)

    style = normalize_style_model(
        {"font_style": "bold", "font_weight": 500, "text_align": "left", "line_spacing": 1.4},
        fallback,
    )

    assert style.font_weight == 500
    assert style.text_align == "left"
    assert style.line_spacing == 1.4


def test_normalize_style_payload_returns_canonical_project_shape() -> None:
    payload = normalize_style_payload(
        {
            "subtitle_mode": "static",
            "subtitle_style": {
                "preset": "Default",
                "highlight_color": "#AABBCC",
                "highlight_opacity": 0.25,
                "appearance": {
                    "font_style": "bold",
                    "text_align": "right",
                    "line_spacing": 1.3,
                },
            },
        }
    )

    appearance = payload["subtitle_style"]["appearance"]
    assert payload["subtitle_mode"] == "static"
    assert payload["subtitle_style"]["highlight_color"] == "#AABBCC"
    assert payload["subtitle_style"]["highlight_opacity"] == 0.25
    assert appearance["font_weight"] == 700
    assert appearance["text_align"] == "right"
    assert appearance["line_spacing"] == 1.3


def test_shadow_offset_polar_helpers_round_trip() -> None:
    distance, angle = shadow_offset_to_polar(0.0, 4.0)
    offset_x, offset_y = shadow_offset_from_polar(distance, angle)

    assert distance == 4.0
    assert angle == 90.0
    assert round(offset_x, 4) == 0.0
    assert round(offset_y, 4) == 4.0
