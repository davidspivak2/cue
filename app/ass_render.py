from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Sequence

from .subtitle_style import DEFAULT_FONT_NAME


RTL_EMBEDDING = "\u202B"
RTL_POP = "\u202C"
DEFAULT_PRIMARY_COLOR = "#FFFFFF"
DEFAULT_OUTLINE_COLOR = "#000000"
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class AssCue:
    start_s: float
    end_s: float
    text: str


def format_ass_time(seconds: float) -> str:
    safe_seconds = max(seconds, 0.0)
    total_centiseconds = int(math.floor(safe_seconds * 100))
    total_seconds, centiseconds = divmod(total_centiseconds, 100)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02}:{secs:02}.{centiseconds:02}"


def escape_ass_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("{", "｛").replace("}", "｝")
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n")
    escaped = escaped.replace("\n", "\\N")
    return escaped


def wrap_rtl(text: str) -> str:
    if text.startswith(RTL_EMBEDDING) and text.endswith(RTL_POP):
        return text
    return f"{RTL_EMBEDDING}{text}{RTL_POP}"


def wrap_rtl_runs(text: str) -> str:
    stripped = text
    if stripped.startswith(RTL_EMBEDDING) and stripped.endswith(RTL_POP):
        stripped = stripped[len(RTL_EMBEDDING) : -len(RTL_POP)]
    parts = re.split(r"(\{[^}]*\})", stripped)
    wrapped_parts: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("{") and part.endswith("}"):
            wrapped_parts.append(part)
        else:
            wrapped_parts.append(f"{RTL_EMBEDDING}{part}{RTL_POP}")
    return "".join(wrapped_parts)


def ass_color_from_hex(hex_rgb: str, alpha: float = 0.0) -> str:
    if not isinstance(hex_rgb, str) or not _HEX_COLOR_RE.match(hex_rgb):
        hex_rgb = DEFAULT_PRIMARY_COLOR
    try:
        alpha_value = float(alpha)
    except (TypeError, ValueError):
        alpha_value = 0.0
    alpha_value = max(0.0, min(alpha_value, 1.0))
    alpha_byte = int(round(alpha_value * 255))
    red = int(hex_rgb[1:3], 16)
    green = int(hex_rgb[3:5], 16)
    blue = int(hex_rgb[5:7], 16)
    return f"&H{alpha_byte:02X}{blue:02X}{green:02X}{red:02X}"


def _coerce_cues(cues: Iterable[object]) -> list[AssCue]:
    normalized: list[AssCue] = []
    for cue in cues:
        if isinstance(cue, AssCue):
            normalized.append(cue)
            continue
        if isinstance(cue, dict):
            start = cue.get("start_s", cue.get("start_seconds"))
            end = cue.get("end_s", cue.get("end_seconds"))
            text = cue.get("text")
            if start is None or end is None or text is None:
                continue
            normalized.append(AssCue(start_s=float(start), end_s=float(end), text=str(text)))
            continue
        start = getattr(cue, "start_s", None)
        end = getattr(cue, "end_s", None)
        text = getattr(cue, "text", None)
        if start is None and hasattr(cue, "start_seconds"):
            start = getattr(cue, "start_seconds", None)
        if end is None and hasattr(cue, "end_seconds"):
            end = getattr(cue, "end_seconds", None)
        if start is None or end is None or text is None:
            continue
        normalized.append(AssCue(start_s=float(start), end_s=float(end), text=str(text)))
    return normalized


from collections.abc import Mapping
from typing import Any

_DEFAULT_FONT_NAME = DEFAULT_FONT_NAME
_DEFAULT_FONT_SIZE = 48
_DEFAULT_OUTLINE = 2
_DEFAULT_SHADOW = 0
_DEFAULT_MARGIN_V = 0
_DEFAULT_BOX_ENABLED = False
_DEFAULT_BOX_PADDING = 0


def _style_get(style_config: Any, key: str, default: Any) -> Any:
    """
    Read style values from either:
    - an object with attributes (style_config.outline), or
    - a dict/mapping (style_config["outline"]), or
    - None (use defaults)
    """
    if style_config is None:
        return default
    if isinstance(style_config, Mapping):
        return style_config.get(key, default)
    return getattr(style_config, key, default)


def _box_alpha_byte(style_config: Any) -> int:
    opacity = _style_get(style_config, "box_opacity", None)
    if opacity is None:
        return 0
    try:
        opacity_value = int(opacity)
    except (TypeError, ValueError):
        return 0
    clamped = max(0, min(opacity_value, 100))
    return round((100 - clamped) / 100 * 255)


def build_ass_header_and_styles(
    style_config: object | None = None,
    play_res: Sequence[int] = (1920, 1080),
) -> tuple[list[str], list[str], int]:
    play_res_x, play_res_y = play_res

    font_name = _style_get(style_config, "font_name", _DEFAULT_FONT_NAME)
    font_size = _style_get(style_config, "font_size", _DEFAULT_FONT_SIZE)
    shadow = _style_get(style_config, "shadow", _DEFAULT_SHADOW)
    margin_v = _style_get(style_config, "margin_v", _DEFAULT_MARGIN_V)

    outline = _style_get(style_config, "outline", _DEFAULT_OUTLINE)
    box_enabled = _style_get(style_config, "box_enabled", _DEFAULT_BOX_ENABLED)
    box_padding = _style_get(style_config, "box_padding", _DEFAULT_BOX_PADDING)

    # Coerce numeric fields to safe ints
    try:
        font_size = int(round(float(font_size)))
    except (TypeError, ValueError):
        font_size = _DEFAULT_FONT_SIZE
    try:
        shadow = int(round(float(shadow)))
    except (TypeError, ValueError):
        shadow = _DEFAULT_SHADOW
    try:
        margin_v = int(round(float(margin_v)))
    except (TypeError, ValueError):
        margin_v = _DEFAULT_MARGIN_V
    try:
        outline = float(outline)
    except (TypeError, ValueError):
        outline = float(_DEFAULT_OUTLINE)
    try:
        box_padding = float(box_padding)
    except (TypeError, ValueError):
        box_padding = float(_DEFAULT_BOX_PADDING)

    border_style = 1
    back_colour = ass_color_from_hex("#000000", alpha=1.0)

    if box_enabled:
        outline = outline + box_padding
        border_style = 3
        alpha_byte = _box_alpha_byte(style_config)
        back_colour = f"&H{alpha_byte:02X}000000"

    outline_int = int(round(outline))

    primary_colour = ass_color_from_hex(DEFAULT_PRIMARY_COLOR)
    outline_colour = ass_color_from_hex(DEFAULT_OUTLINE_COLOR)

    info_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 0",
        f"PlayResX: {int(play_res_x)}",
        f"PlayResY: {int(play_res_y)}",
        "",
    ]
    style_lines = [
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
            "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding"
        ),
        (
            "Style: BASE,"
            f"{font_name},"
            f"{font_size},"
            f"{primary_colour},"
            f"{primary_colour},"
            f"{outline_colour},"
            f"{back_colour},"
            "0,0,0,0,100,100,0,0,"
            f"{border_style},"
            f"{outline_int},"
            f"{shadow},"
            "2,"
            "0,0,"
            f"{margin_v},"
            "1"
        ),
        "",
    ]
    return info_lines, style_lines, margin_v


def build_ass_document(
    cues: Iterable[object],
    style_config: object | None = None,
    play_res: Sequence[int] = (1920, 1080),
) -> str:
    normalized = _coerce_cues(cues)
    info_lines, style_lines, margin_v = build_ass_header_and_styles(
        style_config=style_config,
        play_res=play_res,
    )
    event_lines = [
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in normalized:
        start_time = format_ass_time(cue.start_s)
        end_time = format_ass_time(cue.end_s)
        payload = wrap_rtl(escape_ass_text(cue.text))
        event_lines.append(
            f"Dialogue: 0,{start_time},{end_time},BASE,,0,0,{margin_v},,{payload}"
        )

    return "\n".join(info_lines + style_lines + event_lines) + "\n"
