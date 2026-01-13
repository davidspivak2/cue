from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .subtitle_style import DEFAULT_FONT_NAME, SubtitleStyle, get_box_alpha_byte

RTL_EMBED = "\u202B"
RTL_POP = "\u202C"


@dataclass(frozen=True)
class AssStyleSpec:
    name: str
    font_name: str
    font_size: int
    primary_colour: str
    secondary_colour: str
    outline_colour: str
    back_colour: str
    border_style: int
    outline: int
    shadow: int
    alignment: int
    margin_l: int
    margin_r: int
    margin_v: int


def build_ass_text(
    aligned_segments_with_words: Iterable[dict],
    style: SubtitleStyle,
    *,
    highlight_color: str,
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
        primary_colour=_format_ass_colour(highlight_color),
        secondary_colour=_format_ass_colour("#FFFFFF"),
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
    events = _build_events(aligned_segments_with_words, style_spec)
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
                f"{style_spec.primary_colour},{style_spec.secondary_colour},"
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


def _build_events(
    aligned_segments_with_words: Iterable[dict],
    style_spec: AssStyleSpec,
) -> str:
    lines: list[str] = []
    segment_count = 0
    word_total = 0
    for segment in aligned_segments_with_words:
        start = _coerce_time(segment.get("start"))
        end = _coerce_time(segment.get("end"))
        if start is None or end is None:
            continue
        text = segment.get("text") or ""
        words = segment.get("words") or []
        normalized_words = _normalize_words(words, start, end, text=text)
        word_total += len(normalized_words)
        dialogue_text = _build_karaoke_text(normalized_words)
        dialogue_text = f"{RTL_EMBED}{dialogue_text}{RTL_POP}"
        lines.append(
            "Dialogue: 0,"
            f"{_format_ass_timestamp(start)},"
            f"{_format_ass_timestamp(end)},"
            f"{style_spec.name},,"
            f"{style_spec.margin_l},{style_spec.margin_r},{style_spec.margin_v},,"
            f"{dialogue_text}"
        )
        segment_count += 1
    return "\n".join(lines)


def _normalize_words(
    words: Iterable[dict],
    segment_start: float,
    segment_end: float,
    *,
    text: str,
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for word in words:
        token = str(word.get("word") or word.get("text") or "").strip()
        if not token:
            continue
        normalized.append(
            {
                "text": token,
                "start": _coerce_time(word.get("start")),
                "end": _coerce_time(word.get("end")),
            }
        )
    if not normalized and text.strip():
        normalized.append(
            {
                "text": text.strip(),
                "start": segment_start,
                "end": segment_end,
            }
        )
    for idx, entry in enumerate(normalized):
        if entry["start"] is None:
            entry["start"] = (
                normalized[idx - 1]["end"] if idx > 0 else segment_start
            )
        if entry["end"] is None:
            next_start = None
            for later in normalized[idx + 1 :]:
                if later["start"] is not None:
                    next_start = later["start"]
                    break
            entry["end"] = next_start if next_start is not None else segment_end
    last_end = segment_start
    for entry in normalized:
        start = float(entry["start"] or segment_start)
        end = float(entry["end"] or start)
        start = max(start, last_end)
        if end <= start:
            end = start + 0.01
        if end > segment_end:
            end = segment_end
        if end <= start:
            end = start + 0.01
        entry["start"] = start
        entry["end"] = end
        last_end = end
    return normalized


def _build_karaoke_text(words: Iterable[dict[str, object]]) -> str:
    parts: list[str] = []
    for word in words:
        start = float(word.get("start", 0.0))
        end = float(word.get("end", start))
        duration = max(0.0, end - start)
        centiseconds = max(1, int(round(duration * 100)))
        parts.append(f"{{\\k{centiseconds}}}{word.get('text', '')}")
    return " ".join(parts).strip()


def _format_ass_colour(value: str) -> str:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        return "&H00FFFFFF&"
    r = text[0:2]
    g = text[2:4]
    b = text[4:6]
    return f"&H00{b}{g}{r}&"


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


def _coerce_time(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
