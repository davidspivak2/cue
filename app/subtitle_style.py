from __future__ import annotations

from dataclasses import dataclass

PRESET_DEFAULT = "Default"
PRESET_LARGE_OUTLINE = "Large outline"
PRESET_LARGE_OUTLINE_BOX = "Large outline + box"
PRESET_CUSTOM = "Custom"
PRESET_NAMES = (
    PRESET_DEFAULT,
    PRESET_LARGE_OUTLINE,
    PRESET_LARGE_OUTLINE_BOX,
    PRESET_CUSTOM,
)

DEFAULT_FONT_NAME = "Arial"


@dataclass(frozen=True)
class SubtitleStyle:
    font_size: int
    outline: int
    shadow: int
    margin_v: int
    box_enabled: bool
    box_opacity: int
    box_padding: int


def preset_defaults(name: str) -> SubtitleStyle:
    if name == PRESET_LARGE_OUTLINE:
        return SubtitleStyle(
            font_size=34,
            outline=4,
            shadow=2,
            margin_v=30,
            box_enabled=False,
            box_opacity=70,
            box_padding=10,
        )
    if name == PRESET_LARGE_OUTLINE_BOX:
        return SubtitleStyle(
            font_size=34,
            outline=4,
            shadow=2,
            margin_v=30,
            box_enabled=True,
            box_opacity=70,
            box_padding=10,
        )
    return SubtitleStyle(
        font_size=28,
        outline=2,
        shadow=1,
        margin_v=28,
        box_enabled=False,
        box_opacity=70,
        box_padding=8,
    )


def _opacity_to_ass_alpha(opacity: int) -> int:
    clamped = max(0, min(opacity, 100))
    return round((100 - clamped) / 100 * 255)


def get_box_alpha_byte(style: SubtitleStyle) -> int:
    return _opacity_to_ass_alpha(style.box_opacity)


def format_back_colour(style: SubtitleStyle) -> str:
    alpha = get_box_alpha_byte(style)
    return f"&H{alpha:02X}000000&"


def to_ffmpeg_force_style(style: SubtitleStyle) -> str:
    outline = style.outline
    if style.box_enabled:
        outline = style.outline + style.box_padding
    border_style = 3 if style.box_enabled else 1
    fields = [
        f"FontName={DEFAULT_FONT_NAME}",
        f"FontSize={style.font_size}",
        f"Outline={outline}",
        f"Shadow={style.shadow}",
        f"MarginV={style.margin_v}",
        "Alignment=2",
        f"BorderStyle={border_style}",
    ]
    if style.box_enabled:
        fields.append(f"BackColour={format_back_colour(style)}")
    return ",".join(fields)


def to_preview_params(style: SubtitleStyle) -> dict:
    outline = style.outline
    if style.box_enabled:
        outline = style.outline + style.box_padding
    return {
        "font_name": DEFAULT_FONT_NAME,
        "font_size": style.font_size,
        "outline": outline,
        "shadow": style.shadow,
        "margin_v": style.margin_v,
        "box_enabled": style.box_enabled,
        "box_opacity": style.box_opacity,
        "box_padding": style.box_padding,
    }
