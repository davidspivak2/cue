from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .subtitle_style import DEFAULT_FONT_NAME, SubtitleStyle, get_box_alpha_byte
from .srt_utils import SrtCue

RLI = "\u2067"
PDI = "\u2069"


@dataclass(frozen=True)
class AssStyleSpec:
    name: str
    font_name: str
    font_size: int
    primary_colour: str
    outline_colour: str
    back_colour: str
    border_style: int
    outline: int
    shadow: int
    alignment: int
    margin_l: int
    margin_r: int
    margin_v: int


def build_ass_from_srt_cues(
    cues: Iterable[SrtCue],
    style: SubtitleStyle,
    *,
    play_res_x: int,
    play_res_y: int,
) -> str:
    outline = style.outline + style.box_padding if style.box_enabled else style.outline
    border_style = 3 if style.box_enabled else 1
    back_colour = _format_back_colour(style.box_enabled, style.box_opacity)
    style_spec = AssStyleSpec(
        name="Default",
        font_name=DEFAULT_FONT_NAME,
        font_size=style.font_size,
        primary_colour="&H00FFFFFF&",
        outline_colour="&H00000000&",
        back_colour=back_colour,
        border_style=border_style,
        outline=outline,
        shadow=style.shadow,
        alignment=2,
        margin_l=10,
        margin_r=10,
        margin_v=style.margin_v,
    )
    header = _build_header(play_res_x, play_res_y, style_spec)
    events = _build_events(cues, style_spec)
    return "\n".join([header, events]).strip() + "\n"


def _build_header(play_res_x: int, play_res_y: int, style_spec: AssStyleSpec) -> str:
    return "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {play_res_x}",
            f"PlayResY: {play_res_y}",
            "ScaledBorderAndShadow: yes",
            "Timer: 100.0000",
            "",
            "[V4+ Styles]",
            (
                "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
                "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,"
                "ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,"
                "MarginR,MarginV,Encoding"
            ),
            (
                "Style: "
                f"{style_spec.name},{style_spec.font_name},{style_spec.font_size},"
                f"{style_spec.primary_colour},{style_spec.primary_colour},"
                f"{style_spec.outline_colour},{style_spec.back_colour},"
                "0,0,0,0,100,100,0,0,"
                f"{style_spec.border_style},{style_spec.outline},{style_spec.shadow},"
                f"{style_spec.alignment},{style_spec.margin_l},{style_spec.margin_r},"
                f"{style_spec.margin_v},1"
            ),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


def _build_events(cues: Iterable[SrtCue], style_spec: AssStyleSpec) -> str:
    lines: list[str] = []
    for cue in cues:
        start = _format_ass_timestamp(cue.start_seconds)
        end = _format_ass_timestamp(cue.end_seconds)
        text = _format_ass_text(cue.text)
        lines.append(
            "Dialogue: 0,"
            f"{start},{end},{style_spec.name},,"
            f"{style_spec.margin_l},{style_spec.margin_r},{style_spec.margin_v},,"
            f"{text}"
        )
    return "\n".join(lines)


def _format_ass_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\N")
    normalized = normalized.replace("<u>", r"{\u1}").replace("</u>", r"{\u0}")
    return f"{RLI}{normalized}{PDI}"


def _format_back_colour(box_enabled: bool, box_opacity: int) -> str:
    alpha = get_box_alpha_byte(
        SubtitleStyle(
            font_size=0,
            outline=0,
            shadow=0,
            margin_v=0,
            box_enabled=box_enabled,
            box_opacity=box_opacity,
            box_padding=0,
        )
    )
    if not box_enabled:
        alpha = 255
    return f"&H{alpha:02X}000000&"


def _format_ass_timestamp(seconds: float) -> str:
    total_cs = max(0, int(round(seconds * 100)))
    hours = total_cs // (3600 * 100)
    remainder = total_cs % (3600 * 100)
    minutes = remainder // (60 * 100)
    remainder %= 60 * 100
    secs = remainder // 100
    cs = remainder % 100
    return f"{hours:d}:{minutes:02}:{secs:02}.{cs:02}"
