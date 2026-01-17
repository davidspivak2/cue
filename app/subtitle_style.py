from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

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
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_OUTLINE_COLOR = "#000000"
DEFAULT_SHADOW_COLOR = "#000000"
DEFAULT_LINE_BG_COLOR = "#000000"
DEFAULT_WORD_BG_COLOR = "#000000"
DEFAULT_SUBTITLE_MODE = "word_highlight"
DEFAULT_HIGHLIGHT_COLOR = "#FFD400"

VALID_FONT_STYLES = {"regular", "bold", "italic"}
VALID_BACKGROUND_MODES = {"none", "line", "word"}
VALID_VERTICAL_ANCHORS = {"bottom", "middle", "top"}
VALID_SUBTITLE_MODES = {"word_highlight", "static"}

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class LegacySubtitleStyle:
    font_size: int
    outline: int
    shadow: int
    margin_v: int
    box_enabled: bool
    box_opacity: int
    box_padding: int


@dataclass(frozen=True)
class SubtitleStyle:
    font_family: str
    font_size: int
    font_style: str
    text_color: str
    text_opacity: float
    letter_spacing: float
    outline_enabled: bool
    outline_width: float
    outline_color: str
    shadow_enabled: bool
    shadow_strength: float
    shadow_offset_x: float
    shadow_offset_y: float
    shadow_color: str
    shadow_opacity: float
    background_mode: str
    line_bg_color: str
    line_bg_opacity: float
    line_bg_padding: float
    line_bg_radius: float
    word_bg_color: str
    word_bg_opacity: float
    word_bg_padding: float
    word_bg_radius: float
    vertical_anchor: str
    vertical_offset: float
    subtitle_mode: str
    highlight_color: str


def _coerce_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(round(value))
    return default


def _coerce_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _coerce_bool(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _coerce_enum(value: object, options: Iterable[str], default: str) -> str:
    return value if isinstance(value, str) and value in options else default


def _coerce_color(value: object, default: str) -> str:
    return value if isinstance(value, str) and _HEX_COLOR_RE.match(value) else default


def _coerce_str(value: object, default: str) -> str:
    return value if isinstance(value, str) and value.strip() else default


def legacy_preset_defaults(name: str) -> LegacySubtitleStyle:
    if name == PRESET_LARGE_OUTLINE:
        return LegacySubtitleStyle(
            font_size=34,
            outline=4,
            shadow=2,
            margin_v=30,
            box_enabled=False,
            box_opacity=70,
            box_padding=10,
        )
    if name == PRESET_LARGE_OUTLINE_BOX:
        return LegacySubtitleStyle(
            font_size=34,
            outline=4,
            shadow=2,
            margin_v=30,
            box_enabled=True,
            box_opacity=70,
            box_padding=10,
        )
    return LegacySubtitleStyle(
        font_size=28,
        outline=2,
        shadow=1,
        margin_v=28,
        box_enabled=False,
        box_opacity=70,
        box_padding=8,
    )


def legacy_style_from_custom_dict(
    custom: object, defaults: LegacySubtitleStyle
) -> LegacySubtitleStyle:
    if not isinstance(custom, dict):
        return defaults
    return LegacySubtitleStyle(
        font_size=_coerce_int(custom.get("font_size"), defaults.font_size),
        outline=_coerce_int(custom.get("outline"), defaults.outline),
        shadow=_coerce_int(custom.get("shadow"), defaults.shadow),
        margin_v=_coerce_int(custom.get("margin_v"), defaults.margin_v),
        box_enabled=_coerce_bool(custom.get("box_enabled"), defaults.box_enabled),
        box_opacity=_coerce_int(custom.get("box_opacity"), defaults.box_opacity),
        box_padding=_coerce_int(custom.get("box_padding"), defaults.box_padding),
    )


def style_model_from_legacy(
    legacy: LegacySubtitleStyle,
    *,
    subtitle_mode: str,
    highlight_color: str,
) -> SubtitleStyle:
    background_mode = "line" if legacy.box_enabled else "none"
    return SubtitleStyle(
        font_family=DEFAULT_FONT_NAME,
        font_size=legacy.font_size,
        font_style="regular",
        text_color=DEFAULT_TEXT_COLOR,
        text_opacity=1.0,
        letter_spacing=0.0,
        outline_enabled=legacy.outline > 0,
        outline_width=legacy.outline,
        outline_color=DEFAULT_OUTLINE_COLOR,
        shadow_enabled=legacy.shadow > 0,
        shadow_strength=legacy.shadow,
        shadow_offset_x=0.0,
        shadow_offset_y=0.0,
        shadow_color=DEFAULT_SHADOW_COLOR,
        shadow_opacity=1.0,
        background_mode=background_mode,
        line_bg_color=DEFAULT_LINE_BG_COLOR,
        line_bg_opacity=legacy.box_opacity / 100.0,
        line_bg_padding=legacy.box_padding,
        line_bg_radius=0.0,
        word_bg_color=DEFAULT_WORD_BG_COLOR,
        word_bg_opacity=0.4,
        word_bg_padding=legacy.box_padding,
        word_bg_radius=0.0,
        vertical_anchor="bottom",
        vertical_offset=legacy.margin_v,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
    )


def preset_defaults(
    name: str,
    *,
    subtitle_mode: str = DEFAULT_SUBTITLE_MODE,
    highlight_color: str = DEFAULT_HIGHLIGHT_COLOR,
) -> SubtitleStyle:
    legacy = legacy_preset_defaults(name)
    return style_model_from_legacy(
        legacy,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
    )


def normalize_style_model(raw: object, fallback: SubtitleStyle) -> SubtitleStyle:
    if not isinstance(raw, dict):
        return fallback
    return SubtitleStyle(
        font_family=_coerce_str(raw.get("font_family"), fallback.font_family),
        font_size=_coerce_int(raw.get("font_size"), fallback.font_size),
        font_style=_coerce_enum(
            raw.get("font_style"), VALID_FONT_STYLES, fallback.font_style
        ),
        text_color=_coerce_color(raw.get("text_color"), fallback.text_color),
        text_opacity=max(0.0, min(_coerce_float(raw.get("text_opacity"), fallback.text_opacity), 1.0)),
        letter_spacing=_coerce_float(raw.get("letter_spacing"), fallback.letter_spacing),
        outline_enabled=_coerce_bool(raw.get("outline_enabled"), fallback.outline_enabled),
        outline_width=_coerce_float(raw.get("outline_width"), fallback.outline_width),
        outline_color=_coerce_color(raw.get("outline_color"), fallback.outline_color),
        shadow_enabled=_coerce_bool(raw.get("shadow_enabled"), fallback.shadow_enabled),
        shadow_strength=_coerce_float(raw.get("shadow_strength"), fallback.shadow_strength),
        shadow_offset_x=_coerce_float(raw.get("shadow_offset_x"), fallback.shadow_offset_x),
        shadow_offset_y=_coerce_float(raw.get("shadow_offset_y"), fallback.shadow_offset_y),
        shadow_color=_coerce_color(raw.get("shadow_color"), fallback.shadow_color),
        shadow_opacity=max(0.0, min(_coerce_float(raw.get("shadow_opacity"), fallback.shadow_opacity), 1.0)),
        background_mode=_coerce_enum(
            raw.get("background_mode"), VALID_BACKGROUND_MODES, fallback.background_mode
        ),
        line_bg_color=_coerce_color(raw.get("line_bg_color"), fallback.line_bg_color),
        line_bg_opacity=max(0.0, min(_coerce_float(raw.get("line_bg_opacity"), fallback.line_bg_opacity), 1.0)),
        line_bg_padding=_coerce_float(raw.get("line_bg_padding"), fallback.line_bg_padding),
        line_bg_radius=_coerce_float(raw.get("line_bg_radius"), fallback.line_bg_radius),
        word_bg_color=_coerce_color(raw.get("word_bg_color"), fallback.word_bg_color),
        word_bg_opacity=max(0.0, min(_coerce_float(raw.get("word_bg_opacity"), fallback.word_bg_opacity), 1.0)),
        word_bg_padding=_coerce_float(raw.get("word_bg_padding"), fallback.word_bg_padding),
        word_bg_radius=_coerce_float(raw.get("word_bg_radius"), fallback.word_bg_radius),
        vertical_anchor=_coerce_enum(
            raw.get("vertical_anchor"), VALID_VERTICAL_ANCHORS, fallback.vertical_anchor
        ),
        vertical_offset=_coerce_float(raw.get("vertical_offset"), fallback.vertical_offset),
        subtitle_mode=_coerce_enum(
            raw.get("subtitle_mode"), VALID_SUBTITLE_MODES, fallback.subtitle_mode
        ),
        highlight_color=_coerce_color(raw.get("highlight_color"), fallback.highlight_color),
    )


def style_model_to_dict(style: SubtitleStyle) -> dict[str, object]:
    return {
        "font_family": style.font_family,
        "font_size": style.font_size,
        "font_style": style.font_style,
        "text_color": style.text_color,
        "text_opacity": style.text_opacity,
        "letter_spacing": style.letter_spacing,
        "outline_enabled": style.outline_enabled,
        "outline_width": style.outline_width,
        "outline_color": style.outline_color,
        "shadow_enabled": style.shadow_enabled,
        "shadow_strength": style.shadow_strength,
        "shadow_offset_x": style.shadow_offset_x,
        "shadow_offset_y": style.shadow_offset_y,
        "shadow_color": style.shadow_color,
        "shadow_opacity": style.shadow_opacity,
        "background_mode": style.background_mode,
        "line_bg_color": style.line_bg_color,
        "line_bg_opacity": style.line_bg_opacity,
        "line_bg_padding": style.line_bg_padding,
        "line_bg_radius": style.line_bg_radius,
        "word_bg_color": style.word_bg_color,
        "word_bg_opacity": style.word_bg_opacity,
        "word_bg_padding": style.word_bg_padding,
        "word_bg_radius": style.word_bg_radius,
        "vertical_anchor": style.vertical_anchor,
        "vertical_offset": style.vertical_offset,
        "subtitle_mode": style.subtitle_mode,
        "highlight_color": style.highlight_color,
    }


def legacy_style_from_model(style: SubtitleStyle) -> LegacySubtitleStyle:
    outline = int(round(style.outline_width)) if style.outline_enabled else 0
    shadow = int(round(style.shadow_strength)) if style.shadow_enabled else 0
    margin_v = int(round(style.vertical_offset))
    box_enabled = style.background_mode == "line"
    box_opacity = int(round(style.line_bg_opacity * 100))
    box_padding = int(round(style.line_bg_padding))
    return LegacySubtitleStyle(
        font_size=style.font_size,
        outline=outline,
        shadow=shadow,
        margin_v=margin_v,
        box_enabled=box_enabled,
        box_opacity=max(0, min(box_opacity, 100)),
        box_padding=max(0, box_padding),
    )


def summarize_style_model(style: SubtitleStyle) -> str:
    legacy = legacy_style_from_model(style)
    return (
        "style_model "
        f"font={style.font_family} "
        f"size={style.font_size} "
        f"outline={legacy.outline} "
        f"shadow={legacy.shadow} "
        f"margin_v={legacy.margin_v} "
        f"background={style.background_mode} "
        f"line_bg_opacity={style.line_bg_opacity:.2f} "
        f"line_bg_padding={style.line_bg_padding}"
    )


def _opacity_to_ass_alpha(opacity: int) -> int:
    clamped = max(0, min(opacity, 100))
    return round((100 - clamped) / 100 * 255)


def get_box_alpha_byte(style: SubtitleStyle) -> int:
    legacy = legacy_style_from_model(style)
    return _opacity_to_ass_alpha(legacy.box_opacity)


def _ass_color_from_hex(
    hex_rgb: str,
    *,
    alpha: float,
    default: str,
    trailing_amp: bool = True,
) -> str:
    resolved = hex_rgb if isinstance(hex_rgb, str) and _HEX_COLOR_RE.match(hex_rgb) else default
    try:
        alpha_value = float(alpha)
    except (TypeError, ValueError):
        alpha_value = 0.0
    alpha_value = max(0.0, min(alpha_value, 1.0))
    alpha_byte = int(round(alpha_value * 255))
    red = int(resolved[1:3], 16)
    green = int(resolved[3:5], 16)
    blue = int(resolved[5:7], 16)
    value = f"&H{alpha_byte:02X}{blue:02X}{green:02X}{red:02X}"
    return f"{value}&" if trailing_amp else value


def _opacity_to_ass_alpha_float(opacity: float) -> float:
    clamped = max(0.0, min(opacity, 1.0))
    return 1.0 - clamped


def format_shadow_colour(style: SubtitleStyle) -> str:
    return _ass_color_from_hex(
        style.shadow_color,
        alpha=_opacity_to_ass_alpha_float(style.shadow_opacity),
        default=DEFAULT_SHADOW_COLOR,
    )


def format_outline_colour(style: SubtitleStyle) -> str:
    return _ass_color_from_hex(
        style.outline_color,
        alpha=0.0,
        default=DEFAULT_OUTLINE_COLOR,
    )


def format_line_back_colour(style: SubtitleStyle) -> str:
    return _ass_color_from_hex(
        style.line_bg_color,
        alpha=_opacity_to_ass_alpha_float(style.line_bg_opacity),
        default=DEFAULT_LINE_BG_COLOR,
    )


def to_ffmpeg_force_style(style: SubtitleStyle) -> str:
    legacy = legacy_style_from_model(style)
    outline = legacy.outline
    if legacy.box_enabled:
        outline = legacy.outline + legacy.box_padding
    border_style = 3 if legacy.box_enabled else 1
    outline_colour = format_outline_colour(style)
    if legacy.box_enabled:
        outline_colour = format_line_back_colour(style)
    back_colour = format_shadow_colour(style)
    fields = [
        f"FontName={style.font_family or DEFAULT_FONT_NAME}",
        f"FontSize={legacy.font_size}",
        f"Outline={outline}",
        f"Shadow={legacy.shadow}",
        f"MarginV={legacy.margin_v}",
        "Alignment=2",
        f"BorderStyle={border_style}",
        f"OutlineColour={outline_colour}",
        f"BackColour={back_colour}",
    ]
    return ",".join(fields)


def to_preview_params(style: SubtitleStyle) -> dict:
    legacy = legacy_style_from_model(style)
    outline = legacy.outline
    if legacy.box_enabled:
        outline = legacy.outline + legacy.box_padding
    return {
        "font_name": style.font_family or DEFAULT_FONT_NAME,
        "font_size": legacy.font_size,
        "outline": outline,
        "shadow": legacy.shadow,
        "margin_v": legacy.margin_v,
        "box_enabled": legacy.box_enabled,
        "box_opacity": legacy.box_opacity,
        "box_padding": legacy.box_padding,
    }
