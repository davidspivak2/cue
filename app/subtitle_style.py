from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re
from typing import Any, Iterable

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

DEFAULT_FONT_NAME = "Assistant"
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_OUTLINE_COLOR = "#000000"
DEFAULT_SHADOW_COLOR = "#000000"
DEFAULT_LINE_BG_COLOR = "#000000"
DEFAULT_WORD_BG_COLOR = "#000000"
DEFAULT_SUBTITLE_MODE = "static"
DEFAULT_HIGHLIGHT_COLOR = "#FFD400"
DEFAULT_FONT_WEIGHT = 400
DEFAULT_TEXT_ALIGN = "center"
DEFAULT_LINE_SPACING = 1.0
MIN_TEXT_OPACITY = 0.10
STYLE_REFERENCE_FRAME_HEIGHT = 1000.0
MIN_RENDER_FONT_SIZE_PX = 10.0
QT_POINT_TO_PIXEL_RATIO = 96.0 / 72.0
QT_PIXEL_TO_POINT_RATIO = 72.0 / 96.0
RENDER_MODEL_VERSION = "frame_height_v1"

VALID_FONT_STYLES = {"regular", "bold", "italic", "bold_italic"}
VALID_BACKGROUND_MODES = {"none", "line", "word"}
VALID_VERTICAL_ANCHORS = {"bottom", "middle", "top"}
VALID_SUBTITLE_MODES = {"word_highlight", "static"}
VALID_TEXT_ALIGNS = {"left", "center", "right"}

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
    font_size: float
    font_style: str
    font_weight: int
    text_align: str
    line_spacing: float
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
    position_x: float
    position_y: float
    subtitle_mode: str
    highlight_color: str


_DEFAULT_PRESET_STYLE = PresetStyle(
    font_size=44,
    outline=0,
    shadow=0,
    margin_v=28,
    box_enabled=True,
    box_opacity=70,
    box_padding=8,
)

_PRESET_STYLE_DEFAULTS = {
    PRESET_DEFAULT: _DEFAULT_PRESET_STYLE,
    PRESET_LARGE_OUTLINE: PresetStyle(
        font_size=34,
        outline=4,
        shadow=2,
        margin_v=30,
        box_enabled=False,
        box_opacity=70,
        box_padding=10,
    ),
    PRESET_LARGE_OUTLINE_BOX: PresetStyle(
        font_size=34,
        outline=4,
        shadow=2,
        margin_v=30,
        box_enabled=True,
        box_opacity=70,
        box_padding=10,
    ),
    PRESET_LIFT: PresetStyle(
        font_size=28,
        outline=2,
        shadow=3,
        margin_v=28,
        box_enabled=False,
        box_opacity=70,
        box_padding=8,
    ),
}


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


def _coerce_positive_float(value: object, default: float) -> float:
    result = _coerce_float(value, default)
    return result if result > 0 else default


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


def _font_weight_from_font_style(font_style: str) -> int:
    return 700 if font_style in {"bold", "bold_italic"} else DEFAULT_FONT_WEIGHT


def _coerce_font_weight(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(100, min(900, int(round(value))))
    return default


def shadow_offset_to_polar(offset_x: float, offset_y: float) -> tuple[float, float]:
    distance = math.hypot(offset_x, offset_y)
    angle_degrees = math.degrees(math.atan2(offset_y, offset_x))
    if angle_degrees < 0:
        angle_degrees += 360.0
    return distance, angle_degrees


def shadow_offset_from_polar(distance: float, angle_degrees: float) -> tuple[float, float]:
    distance_value = max(0.0, float(distance))
    radians = math.radians(float(angle_degrees))
    return distance_value * math.cos(radians), distance_value * math.sin(radians)


def preset_style_defaults(name: str) -> PresetStyle:
    return _PRESET_STYLE_DEFAULTS.get(name, _DEFAULT_PRESET_STYLE)


def normalize_preset_name(value: object, *, default: str = PRESET_DEFAULT) -> str:
    fallback = default if default in PRESET_NAMES else PRESET_DEFAULT
    return value if isinstance(value, str) and value in PRESET_NAMES else fallback


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


def resolve_effective_preset_style(
    style_payload: object,
    *,
    default_preset: str = PRESET_DEFAULT,
) -> tuple[str, PresetStyle]:
    payload = style_payload if isinstance(style_payload, dict) else {}
    preset = normalize_preset_name(payload.get("preset"), default=default_preset)
    if preset == PRESET_CUSTOM:
        return preset, preset_style_from_custom_dict(payload.get("custom"), _DEFAULT_PRESET_STYLE)
    return preset, preset_style_defaults(preset)


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
        font_weight=DEFAULT_FONT_WEIGHT,
        text_align=DEFAULT_TEXT_ALIGN,
        line_spacing=DEFAULT_LINE_SPACING,
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
        shadow_blur=10.0,
        background_mode=background_mode,
        line_bg_color=DEFAULT_LINE_BG_COLOR,
        line_bg_opacity=preset.box_opacity / 100.0,
        line_bg_padding=float(preset.box_padding),
        line_bg_padding_top=float(preset.box_padding),
        line_bg_padding_right=float(preset.box_padding),
        line_bg_padding_bottom=float(preset.box_padding),
        line_bg_padding_left=float(preset.box_padding),
        line_bg_radius=8.0,
        word_bg_color=DEFAULT_WORD_BG_COLOR,
        word_bg_opacity=0.4,
        word_bg_padding=float(preset.box_padding),
        word_bg_padding_top=float(preset.box_padding),
        word_bg_padding_right=float(preset.box_padding),
        word_bg_padding_bottom=float(preset.box_padding),
        word_bg_padding_left=float(preset.box_padding),
        word_bg_radius=8.0,
        vertical_anchor="bottom",
        vertical_offset=preset.margin_v,
        position_x=0.5,
        position_y=_position_y_from_anchor_offset("bottom", preset.margin_v),
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
    )
    if preset_name == PRESET_LIFT:
        style = replace(
            style,
            shadow_enabled=True,
            shadow_strength=2.5,
            shadow_offset_x=2.0,
            shadow_offset_y=2.0,
            shadow_opacity=0.85,
            shadow_blur=8.0,
        )
    return style


def _position_y_from_anchor_offset(vertical_anchor: str, vertical_offset: float) -> float:
    """Convert vertical_anchor + vertical_offset (px) to position_y in [0, 1]. Nominal height 1000."""
    h = 1000.0
    o = max(0.0, min(vertical_offset, h))
    if vertical_anchor == "top":
        return o / h
    if vertical_anchor == "middle":
        return 0.5 - (o / h) * 0.5
    return 1.0 - (o / h)


def _position_y_from_normalize_raw(
    raw: object, fallback: SubtitleStyle, vertical_anchor: str, vertical_offset: float
) -> float:
    """position_y for normalize: from raw if present, else derived from anchor+offset."""
    if isinstance(raw, dict) and raw.get("position_y") is not None:
        default_y = getattr(fallback, "position_y", 0.92)
        return max(0.0, min(1.0, _coerce_float(raw.get("position_y"), default_y)))
    return max(0.0, min(1.0, _position_y_from_anchor_offset(vertical_anchor, vertical_offset)))


def resolve_style_scale_for_frame(
    style: SubtitleStyle,
    frame_height: float,
    *,
    min_font_size_px: float = MIN_RENDER_FONT_SIZE_PX,
) -> float:
    base_scale = max(0.0, float(frame_height)) / STYLE_REFERENCE_FRAME_HEIGHT
    if style.font_size <= 0:
        return base_scale
    return max(base_scale, min_font_size_px / float(style.font_size))


def resolve_style_for_frame(
    style: SubtitleStyle,
    frame_height: float,
    *,
    min_font_size_px: float = MIN_RENDER_FONT_SIZE_PX,
) -> SubtitleStyle:
    pixel_scale = resolve_style_scale_for_frame(
        style,
        frame_height,
        min_font_size_px=min_font_size_px,
    )
    # Qt font APIs take point sizes, while the stored style now scales in frame-relative pixels.
    font_size_px = max(min_font_size_px, float(style.font_size) * pixel_scale)
    return replace(
        style,
        font_size=font_size_px * QT_PIXEL_TO_POINT_RATIO,
        letter_spacing=style.letter_spacing * pixel_scale,
        outline_width=style.outline_width * pixel_scale,
        shadow_strength=style.shadow_strength * pixel_scale,
        shadow_offset_x=style.shadow_offset_x * pixel_scale,
        shadow_offset_y=style.shadow_offset_y * pixel_scale,
        shadow_blur=style.shadow_blur * pixel_scale,
        line_bg_padding=style.line_bg_padding * pixel_scale,
        line_bg_padding_top=style.line_bg_padding_top * pixel_scale,
        line_bg_padding_right=style.line_bg_padding_right * pixel_scale,
        line_bg_padding_bottom=style.line_bg_padding_bottom * pixel_scale,
        line_bg_padding_left=style.line_bg_padding_left * pixel_scale,
        line_bg_radius=style.line_bg_radius * pixel_scale,
        word_bg_padding=style.word_bg_padding * pixel_scale,
        word_bg_padding_top=style.word_bg_padding_top * pixel_scale,
        word_bg_padding_right=style.word_bg_padding_right * pixel_scale,
        word_bg_padding_bottom=style.word_bg_padding_bottom * pixel_scale,
        word_bg_padding_left=style.word_bg_padding_left * pixel_scale,
        word_bg_radius=style.word_bg_radius * pixel_scale,
    )


def preset_defaults(
    name: str,
    *,
    subtitle_mode: str = DEFAULT_SUBTITLE_MODE,
    highlight_color: str = DEFAULT_HIGHLIGHT_COLOR,
) -> SubtitleStyle:
    preset_name = normalize_preset_name(name)
    preset = preset_style_defaults(preset_name)
    return style_model_from_preset(
        preset,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
        preset_name=preset_name,
    )


def normalize_style_model(raw: object, fallback: SubtitleStyle) -> SubtitleStyle:
    if not isinstance(raw, dict):
        return fallback
    font_style = _coerce_enum(raw.get("font_style"), VALID_FONT_STYLES, fallback.font_style)
    if raw.get("font_weight") is None:
        font_weight = (
            _font_weight_from_font_style(font_style)
            if raw.get("font_style") is not None
            else fallback.font_weight
        )
    else:
        font_weight = _coerce_font_weight(raw.get("font_weight"), fallback.font_weight)
    return SubtitleStyle(
        font_family=_coerce_str(raw.get("font_family"), fallback.font_family),
        font_size=_coerce_int(raw.get("font_size"), fallback.font_size),
        font_style=font_style,
        font_weight=font_weight,
        text_align=_coerce_enum(raw.get("text_align"), VALID_TEXT_ALIGNS, fallback.text_align),
        line_spacing=_coerce_positive_float(raw.get("line_spacing"), fallback.line_spacing),
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
        position_x=max(
            0.0,
            min(1.0, _coerce_float(raw.get("position_x"), getattr(fallback, "position_x", 0.5))),
        ),
        position_y=_position_y_from_normalize_raw(
            raw,
            fallback,
            _coerce_enum(
                raw.get("vertical_anchor"), VALID_VERTICAL_ANCHORS, fallback.vertical_anchor
            ),
            _coerce_float(raw.get("vertical_offset"), fallback.vertical_offset),
        ),
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
        "font_weight": style.font_weight,
        "text_align": style.text_align,
        "line_spacing": style.line_spacing,
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
        "position_x": style.position_x,
        "position_y": style.position_y,
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
        f"weight={style.font_weight} "
        f"align={style.text_align} "
        f"line_spacing={style.line_spacing:.2f} "
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


def _normalize_highlight_opacity(value: object, default: float = 1.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        opacity = float(value)
        return max(0.0, min(opacity, 1.0))
    return default


def normalize_style_payload(
    raw_style: object,
    *,
    default_preset: str = PRESET_DEFAULT,
    default_subtitle_mode: str = DEFAULT_SUBTITLE_MODE,
    default_highlight_color: str = DEFAULT_HIGHLIGHT_COLOR,
) -> dict[str, Any]:
    if not isinstance(raw_style, dict) or not raw_style:
        return {}

    root = raw_style
    has_nested_style_payload = isinstance(raw_style.get("subtitle_style"), dict)
    style_payload = raw_style.get("subtitle_style") if has_nested_style_payload else raw_style
    if not isinstance(style_payload, dict):
        style_payload = {}

    subtitle_mode = _coerce_enum(
        root.get("subtitle_mode"), VALID_SUBTITLE_MODES, default_subtitle_mode
    )
    highlight_color = _coerce_color(
        style_payload.get("highlight_color"),
        _coerce_color(root.get("highlight_color"), default_highlight_color),
    )
    preset, preset_effective = resolve_effective_preset_style(
        style_payload,
        default_preset=default_preset,
    )
    fallback_style = style_model_from_preset(
        preset_effective,
        subtitle_mode=subtitle_mode,
        highlight_color=highlight_color,
        preset_name=preset,
    )

    appearance_raw = style_payload.get("appearance")
    if not isinstance(appearance_raw, dict):
        appearance_raw = style_payload
    style_model = normalize_style_model(appearance_raw, fallback_style)

    normalized_subtitle_style: dict[str, Any] = dict(style_payload) if has_nested_style_payload else {}
    normalized_subtitle_style["preset"] = preset
    normalized_subtitle_style["highlight_color"] = style_model.highlight_color
    normalized_subtitle_style["highlight_opacity"] = _normalize_highlight_opacity(
        style_payload.get("highlight_opacity")
    )
    if isinstance(style_payload.get("custom"), dict):
        _, normalized_custom = resolve_effective_preset_style(
            {
                "preset": PRESET_CUSTOM,
                "custom": style_payload.get("custom"),
            }
        )
        normalized_subtitle_style["custom"] = {
            "font_size": normalized_custom.font_size,
            "outline": normalized_custom.outline,
            "shadow": normalized_custom.shadow,
            "margin_v": normalized_custom.margin_v,
            "box_enabled": normalized_custom.box_enabled,
            "box_opacity": normalized_custom.box_opacity,
            "box_padding": normalized_custom.box_padding,
        }
    normalized_subtitle_style["appearance"] = style_model_to_dict(style_model)

    normalized_root: dict[str, Any] = {
        "subtitle_mode": style_model.subtitle_mode,
        "subtitle_style": normalized_subtitle_style,
    }
    return normalized_root
