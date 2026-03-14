from __future__ import annotations

import pytest

from app.subtitle_style import (
    MIN_RENDER_FONT_SIZE_PX,
    PRESET_DEFAULT,
    QT_POINT_TO_PIXEL_RATIO,
    STYLE_REFERENCE_FRAME_HEIGHT,
    normalize_style_model,
    normalize_style_payload,
    preset_defaults,
    preset_style_defaults,
    resolve_style_for_frame,
    resolve_style_scale_for_frame,
    shadow_offset_from_polar,
    shadow_offset_to_polar,
)


def test_normalize_style_model_derives_font_weight_from_legacy_bold_style() -> None:
    fallback = preset_defaults(PRESET_DEFAULT)

    style = normalize_style_model({"font_style": "bold"}, fallback)

    assert style.font_weight == 700
    assert style.text_align == "center"
    assert style.line_spacing == 1.0


def test_default_preset_style_source_of_truth_enables_line_background() -> None:
    preset = preset_style_defaults(PRESET_DEFAULT)

    assert preset == preset_style_defaults("unexpected")
    assert preset.font_size == 44
    assert preset.outline == 0
    assert preset.shadow == 0
    assert preset.margin_v == 28
    assert preset.box_enabled is True
    assert preset.box_opacity == 70
    assert preset.box_padding == 8


def test_default_preset_starts_static_with_background_on_and_outline_off() -> None:
    preset = preset_style_defaults(PRESET_DEFAULT)
    style = preset_defaults(PRESET_DEFAULT)

    assert style.font_family == "Assistant"
    assert style.font_size == preset.font_size
    assert style.font_style == "regular"
    assert style.text_color == "#FFFFFF"
    assert style.text_align == "center"
    assert style.line_spacing == 1.0
    assert style.text_opacity == 1.0
    assert style.letter_spacing == 0.0
    assert style.outline_enabled is False
    assert style.outline_width == preset.outline
    assert style.shadow_enabled is False
    assert style.shadow_strength == float(preset.shadow)
    assert style.background_mode == "line"
    assert style.line_bg_opacity == pytest.approx(preset.box_opacity / 100.0)
    assert style.line_bg_padding_top == float(preset.box_padding)
    assert style.vertical_offset == float(preset.margin_v)
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


def test_resolve_style_for_frame_scales_font_size_to_1080_height() -> None:
    preset = preset_style_defaults(PRESET_DEFAULT)
    style = preset_defaults(PRESET_DEFAULT)

    resolved = resolve_style_for_frame(style, 1080)
    expected_scale = 1080 / STYLE_REFERENCE_FRAME_HEIGHT

    assert resolved.font_size * QT_POINT_TO_PIXEL_RATIO == pytest.approx(
        preset.font_size * expected_scale,
        abs=0.05,
    )
    assert resolved.outline_width == pytest.approx(preset.outline * expected_scale, abs=0.001)
    assert resolved.line_bg_padding_top == pytest.approx(
        preset.box_padding * expected_scale,
        abs=0.001,
    )


def test_resolve_style_for_frame_scales_font_size_to_720_height() -> None:
    preset = preset_style_defaults(PRESET_DEFAULT)
    style = preset_defaults(PRESET_DEFAULT)

    resolved = resolve_style_for_frame(style, 720)
    expected_scale = 720 / STYLE_REFERENCE_FRAME_HEIGHT

    assert resolved.font_size * QT_POINT_TO_PIXEL_RATIO == pytest.approx(
        preset.font_size * expected_scale,
        abs=0.05,
    )
    assert resolved.line_bg_padding_top == pytest.approx(
        preset.box_padding * expected_scale,
        abs=0.001,
    )


def test_resolve_style_for_frame_applies_minimum_font_floor() -> None:
    preset = preset_style_defaults(PRESET_DEFAULT)
    style = preset_defaults(PRESET_DEFAULT)

    resolved = resolve_style_for_frame(style, 200)
    expected_scale = MIN_RENDER_FONT_SIZE_PX / preset.font_size

    assert resolve_style_scale_for_frame(style, 200) == pytest.approx(expected_scale, abs=0.0001)
    assert resolved.font_size * QT_POINT_TO_PIXEL_RATIO == pytest.approx(
        MIN_RENDER_FONT_SIZE_PX,
        abs=0.05,
    )
    assert resolved.outline_width == pytest.approx(style.outline_width * expected_scale, abs=0.001)
