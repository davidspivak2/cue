from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

PRESET_DEFAULT = "Default"
PRESET_LARGE_OUTLINE = "Large outline"
PRESET_LARGE_OUTLINE_BOX = "Large outline + box"
PRESET_LIFT = "Lift"
PRESET_CUSTOM = "Custom"
PRESET_NAMES = (
    PRESET_DEFAULT,
    PRESET_LARGE_OUTLINE,
    PRESET_LARGE_OUTLINE_BOX,
    PRESET_LIFT,
    PRESET_CUSTOM,
)

DEFAULT_FONT_NAME = "Heebo"
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_OUTLINE_COLOR = "#000000"
DEFAULT_SHADOW_COLOR = "#000000"
DEFAULT_LINE_BG_COLOR = "#000000"
DEFAULT_WORD_BG_COLOR = "#000000"
DEFAULT_SUBTITLE_MODE = "word_highlight"
DEFAULT_HIGHLIGHT_COLOR = "#FFD400"
MIN_TEXT_OPACITY = 0.10

VALID_FONT_STYLES = {"regular", "bold", "italic", "bold_italic"}
VALID_BACKGROUND_MODES = {"none", "line", "word"}
VALID_VERTICAL_ANCHORS = {"bottom", "middle", "top"}
VALID_SUBTITLE_MODES = {"word_highlight", "static"}

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class PresetStyle:
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
    shadow_blur: float
    background_mode: str
    line_bg_color: str
    line_bg_opacity: float
    line_bg_padding: float
    line_bg_padding_top: float
    line_bg_padding_right: float
    line_bg_padding_bottom: float
    line_bg_padding_left: float
    line_bg_radius: float
    word_bg_color: str
    word_bg_opacity: float
    word_bg_padding: float
    word_bg_padding_top: float
    word_bg_padding_right: float
    word_bg_padding_bottom: float
    word_bg_padding_left: float
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


OUTLINE_AUTO_SENTINEL = "auto"


def resolve_outline_color(style: SubtitleStyle) -> str:
    if style.outline_color != OUTLINE_AUTO_SENTINEL:
        return style.outline_color
    if not _HEX_COLOR_RE.match(style.text_color):
        return DEFAULT_OUTLINE_COLOR
    r = int(style.text_color[1:3], 16) / 255
    g = int(style.text_color[3:5], 16) / 255
    b = int(style.text_color[5:7], 16) / 255
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance > 0.5 else "#FFFFFF"


def _coerce_str(value: object, default: str) -> str:
    return value if isinstance(value, str) and value.strip() else default


def preset_style_defaults(name: str) -> PresetStyle:
    if name == PRESET_LARGE_OUTLINE:
        return PresetStyle(
            font_size=34,
            outline=4,
            shadow=2,
            margin_v=30,
            box_enabled=False,
            box_opacity=70,
            box_padding=10,
        )
    if name == PRESET_LARGE_OUTLINE_BOX:
        return PresetStyle(
            font_size=34,
            outline=4,
            shadow=2,
            margin_v=30,
            box_enabled=True,
            box_opacity=70,
            box_padding=10,
        )
    if name == PRESET_LIFT:
        return PresetStyle(
            font_size=28,
            outline=2,
            shadow=3,
            margin_v=28,
            box_enabled=False,
            box_opacity=70,
            box_padding=8,
        )
    return PresetStyle(
        font_size=28,
        outline=2,
        shadow=1,
        margin_v=28,
        box_enabled=False,
        box_opacity=70,
        box_padding=8,
    )


def preset_style_from_custom_dict(
    custom: object, defaults: PresetStyle
) -> PresetStyle:
    if not isinstance(custom, dict):
        return defaults
    return PresetStyle(
        font_size=_coerce_int(custom.get("font_size"), defaults.font_size),
        outline=_coerce_int(custom.get("outline"), defaults.outline),
        shadow=_coerce_int(custom.get("shadow"), defaults.shadow),
        margin_v=_coerce_int(custom.get("margin_v"), defaults.margin_v),
        box_enabled=_coerce_bool(custom.get("box_enabled"), defaults.box_enabled),
        box_opacity=_coerce_int(custom.get("box_opacity"), defaults.box_opacity),
        box_padding=_coerce_int(custom.get("box_padding"), defaults.box_padding),
    )


def style_model_from_preset(
    preset: PresetStyle,
    *,
    subtitle_mode: str,
    highlight_color: str,
    preset_name: str | None = None,
) -> SubtitleStyle:
    background_mode = "line" if preset.box_enabled else "none"
    style = SubtitleStyle(
        font_family=DEFAULT_FONT_NAME,
        font_size=preset.font_size,
        font_style="regular",
        text_color=DEFAULT_TEXT_COLOR,
        text_opacity=1.0,
        letter_spacing=0.0,
        outline_enabled=preset.outline > 0,
        outline_width=preset.outline,
        outline_color=DEFAULT_OUTLINE_COLOR,
        shadow_enabled=preset.shadow > 0,
        shadow_strength=float(preset.shadow),
        shadow_offset_x=0.0,
        shadow_offset_y=0.0,
        shadow_color=DEFAULT_SHADOW_COLOR,
        shadow_opacity=1.0,
        shadow_blur=6.0,
        background_mode=background_mode,
        line_bg_color=DEFAULT_LINE_BG_COLOR,
        line_bg_opacity=preset.box_opacity / 100.0,
        line_bg_padding=float(preset.box_padding),
        line_bg_padding_top=float(preset.box_padding),
        line_bg_padding_right=float(preset.box_padding),
        line_bg_padding_bottom=float(preset.box_padding),
        line_bg_padding_left=float(preset.box_padding),
        line_bg_radius=0.0,
        word_bg_color=DEFAULT_WORD_BG_COLOR,
        word_bg_opacity=0.4,
        word_bg_padding=float(preset.box_padding),
        word_bg_padding_top=float(preset.box_padding),
        word_bg_padding_right=float(preset.box_padding),
        word_bg_padding_bottom=float(preset.box_padding),
        word_bg_padding_left=float(preset.box_padding),
        word_bg_radius=0.0,
        vertical_anchor="bottom",
        vertical_offset=preset.margin_v,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
    )
    if preset_name == PRESET_LIFT:
        style = SubtitleStyle(
            font_family=style.font_family,
            font_size=style.font_size,
            font_style=style.font_style,
            text_color=style.text_color,
            text_opacity=style.text_opacity,
            letter_spacing=style.letter_spacing,
            outline_enabled=style.outline_enabled,
            outline_width=style.outline_width,
            outline_color=style.outline_color,
            shadow_enabled=True,
            shadow_strength=2.5,
            shadow_offset_x=2.0,
            shadow_offset_y=2.0,
            shadow_color=style.shadow_color,
            shadow_opacity=0.85,
            shadow_blur=8.0,
            background_mode=style.background_mode,
            line_bg_color=style.line_bg_color,
            line_bg_opacity=style.line_bg_opacity,
            line_bg_padding=style.line_bg_padding,
            line_bg_padding_top=style.line_bg_padding_top,
            line_bg_padding_right=style.line_bg_padding_right,
            line_bg_padding_bottom=style.line_bg_padding_bottom,
            line_bg_padding_left=style.line_bg_padding_left,
            line_bg_radius=style.line_bg_radius,
            word_bg_color=style.word_bg_color,
            word_bg_opacity=style.word_bg_opacity,
            word_bg_padding=style.word_bg_padding,
            word_bg_padding_top=style.word_bg_padding_top,
            word_bg_padding_right=style.word_bg_padding_right,
            word_bg_padding_bottom=style.word_bg_padding_bottom,
            word_bg_padding_left=style.word_bg_padding_left,
            word_bg_radius=style.word_bg_radius,
            vertical_anchor=style.vertical_anchor,
            vertical_offset=style.vertical_offset,
            subtitle_mode=style.subtitle_mode,
            highlight_color=style.highlight_color,
        )
    return style


def preset_defaults(
    name: str,
    *,
    subtitle_mode: str = DEFAULT_SUBTITLE_MODE,
    highlight_color: str = DEFAULT_HIGHLIGHT_COLOR,
) -> SubtitleStyle:
    preset = preset_style_defaults(name)
    return style_model_from_preset(
        preset,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
        preset_name=name,
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
        text_opacity=max(
            MIN_TEXT_OPACITY,
            min(_coerce_float(raw.get("text_opacity"), fallback.text_opacity), 1.0),
        ),
        letter_spacing=_coerce_float(raw.get("letter_spacing"), fallback.letter_spacing),
        outline_enabled=_coerce_bool(raw.get("outline_enabled"), fallback.outline_enabled),
        outline_width=_coerce_float(raw.get("outline_width"), fallback.outline_width),
        outline_color=(
            OUTLINE_AUTO_SENTINEL
            if raw.get("outline_color") == OUTLINE_AUTO_SENTINEL
            else _coerce_color(raw.get("outline_color"), fallback.outline_color)
        ),
        shadow_enabled=_coerce_bool(raw.get("shadow_enabled"), fallback.shadow_enabled),
        shadow_strength=_coerce_float(raw.get("shadow_strength"), fallback.shadow_strength),
        shadow_offset_x=_coerce_float(raw.get("shadow_offset_x"), fallback.shadow_offset_x),
        shadow_offset_y=_coerce_float(raw.get("shadow_offset_y"), fallback.shadow_offset_y),
        shadow_color=_coerce_color(raw.get("shadow_color"), fallback.shadow_color),
        shadow_opacity=max(0.0, min(_coerce_float(raw.get("shadow_opacity"), fallback.shadow_opacity), 1.0)),
        shadow_blur=max(0.0, min(_coerce_float(raw.get("shadow_blur"), fallback.shadow_blur), 30.0)),
        background_mode=_coerce_enum(
            raw.get("background_mode"), VALID_BACKGROUND_MODES, fallback.background_mode
        ),
        line_bg_color=_coerce_color(raw.get("line_bg_color"), fallback.line_bg_color),
        line_bg_opacity=max(0.0, min(_coerce_float(raw.get("line_bg_opacity"), fallback.line_bg_opacity), 1.0)),
        line_bg_padding=_coerce_float(raw.get("line_bg_padding"), fallback.line_bg_padding),
        line_bg_padding_top=_coerce_float(raw.get("line_bg_padding_top"), _coerce_float(raw.get("line_bg_padding"), fallback.line_bg_padding)),
        line_bg_padding_right=_coerce_float(raw.get("line_bg_padding_right"), _coerce_float(raw.get("line_bg_padding"), fallback.line_bg_padding)),
        line_bg_padding_bottom=_coerce_float(raw.get("line_bg_padding_bottom"), _coerce_float(raw.get("line_bg_padding"), fallback.line_bg_padding)),
        line_bg_padding_left=_coerce_float(raw.get("line_bg_padding_left"), _coerce_float(raw.get("line_bg_padding"), fallback.line_bg_padding)),
        line_bg_radius=_coerce_float(raw.get("line_bg_radius"), fallback.line_bg_radius),
        word_bg_color=_coerce_color(raw.get("word_bg_color"), fallback.word_bg_color),
        word_bg_opacity=max(0.0, min(_coerce_float(raw.get("word_bg_opacity"), fallback.word_bg_opacity), 1.0)),
        word_bg_padding=_coerce_float(raw.get("word_bg_padding"), fallback.word_bg_padding),
        word_bg_padding_top=_coerce_float(raw.get("word_bg_padding_top"), _coerce_float(raw.get("word_bg_padding"), fallback.word_bg_padding)),
        word_bg_padding_right=_coerce_float(raw.get("word_bg_padding_right"), _coerce_float(raw.get("word_bg_padding"), fallback.word_bg_padding)),
        word_bg_padding_bottom=_coerce_float(raw.get("word_bg_padding_bottom"), _coerce_float(raw.get("word_bg_padding"), fallback.word_bg_padding)),
        word_bg_padding_left=_coerce_float(raw.get("word_bg_padding_left"), _coerce_float(raw.get("word_bg_padding"), fallback.word_bg_padding)),
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
        "shadow_blur": style.shadow_blur,
        "background_mode": style.background_mode,
        "line_bg_color": style.line_bg_color,
        "line_bg_opacity": style.line_bg_opacity,
        "line_bg_padding": style.line_bg_padding,
        "line_bg_padding_top": style.line_bg_padding_top,
        "line_bg_padding_right": style.line_bg_padding_right,
        "line_bg_padding_bottom": style.line_bg_padding_bottom,
        "line_bg_padding_left": style.line_bg_padding_left,
        "line_bg_radius": style.line_bg_radius,
        "word_bg_color": style.word_bg_color,
        "word_bg_opacity": style.word_bg_opacity,
        "word_bg_padding": style.word_bg_padding,
        "word_bg_padding_top": style.word_bg_padding_top,
        "word_bg_padding_right": style.word_bg_padding_right,
        "word_bg_padding_bottom": style.word_bg_padding_bottom,
        "word_bg_padding_left": style.word_bg_padding_left,
        "word_bg_radius": style.word_bg_radius,
        "vertical_anchor": style.vertical_anchor,
        "vertical_offset": style.vertical_offset,
        "subtitle_mode": style.subtitle_mode,
        "highlight_color": style.highlight_color,
    }


def preset_style_from_model(style: SubtitleStyle) -> PresetStyle:
    outline = int(round(style.outline_width)) if style.outline_enabled else 0
    shadow = int(round(style.shadow_strength)) if style.shadow_enabled else 0
    margin_v = int(round(style.vertical_offset))
    box_enabled = style.background_mode == "line"
    box_opacity = int(round(style.line_bg_opacity * 100))
    box_padding = int(round(style.line_bg_padding_top))
    return PresetStyle(
        font_size=style.font_size,
        outline=outline,
        shadow=shadow,
        margin_v=margin_v,
        box_enabled=box_enabled,
        box_opacity=max(0, min(box_opacity, 100)),
        box_padding=max(0, box_padding),
    )


def summarize_style_model(style: SubtitleStyle) -> str:
    preset = preset_style_from_model(style)
    return (
        "style_model "
        f"font={style.font_family} "
        f"size={style.font_size} "
        f"outline={preset.outline} "
        f"shadow={preset.shadow} "
        f"margin_v={preset.margin_v} "
        f"background={style.background_mode} "
        f"line_bg_opacity={style.line_bg_opacity:.2f} "
        f"line_bg_padding={style.line_bg_padding_top}"
    )


def to_preview_params(style: SubtitleStyle) -> dict:
    preset = preset_style_from_model(style)
    outline = preset.outline
    if preset.box_enabled:
        outline = preset.outline + preset.box_padding
    return {
        "font_name": style.font_family or DEFAULT_FONT_NAME,
        "font_size": preset.font_size,
        "outline": outline,
        "shadow": preset.shadow,
        "margin_v": preset.margin_v,
        "box_enabled": preset.box_enabled,
        "box_opacity": preset.box_opacity,
        "box_padding": preset.box_padding,
    }
