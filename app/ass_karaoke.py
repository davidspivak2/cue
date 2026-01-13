from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.karaoke_utils import HIGHLIGHT_COLOR_RGB, build_token_durations_cs, iter_token_spans
from app.srt_utils import SrtCue
from app.subtitle_style import DEFAULT_FONT_NAME, SubtitleStyle, get_box_alpha_byte


@dataclass(frozen=True)
class KaraokeAssResult:
    ass_path: Path
    dialogue_count: int


def _format_ass_timestamp(seconds: float) -> str:
    total_cs = max(0, round(seconds * 100))
    hours = total_cs // 360000
    minutes = (total_cs % 360000) // 6000
    secs = (total_cs % 6000) // 100
    cs = total_cs % 100
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _format_ass_color(rgb: tuple[int, int, int], alpha: int = 0) -> str:
    r, g, b = rgb
    alpha = max(0, min(alpha, 255))
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}&"


def _build_ass_header(style: SubtitleStyle) -> str:
    outline = style.outline + style.box_padding if style.box_enabled else style.outline
    border_style = 3 if style.box_enabled else 1
    back_alpha = get_box_alpha_byte(style) if style.box_enabled else 255
    primary = _format_ass_color((255, 255, 255))
    secondary = _format_ass_color(HIGHLIGHT_COLOR_RGB)
    outline_color = _format_ass_color((0, 0, 0))
    back_color = _format_ass_color((0, 0, 0), back_alpha)
    style_line = (
        "Style: Default,"
        f"{DEFAULT_FONT_NAME},"
        f"{style.font_size},"
        f"{primary},"
        f"{secondary},"
        f"{outline_color},"
        f"{back_color},"
        "0,0,0,0,"
        f"{border_style},"
        f"{outline},"
        f"{style.shadow},"
        "2,"
        "0,"
        "0,"
        f"{style.margin_v},"
        "1"
    )
    return "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "Collisions: Normal",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "Timer: 100.0000",
            "",
            "[V4+ Styles]",
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
            style_line,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


def _build_karaoke_text(text: str, duration_seconds: float) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    token_spans = list(iter_token_spans(normalized))
    durations = build_token_durations_cs(duration_seconds, len(token_spans))
    if not token_spans:
        return normalized.replace("\n", "\\N")
    chunks: list[str] = []
    last_end = 0
    for idx, (start, end) in enumerate(token_spans):
        chunks.append(normalized[last_end:start].replace("\n", "\\N"))
        duration_cs = durations[idx]
        token_text = normalized[start:end].replace("\n", "\\N")
        chunks.append(f"{{\\k{duration_cs}}}{token_text}")
        last_end = end
    chunks.append(normalized[last_end:].replace("\n", "\\N"))
    return "".join(chunks)


def build_karaoke_ass_text(cues: Iterable[SrtCue], style: SubtitleStyle) -> tuple[str, int]:
    lines = [_build_ass_header(style)]
    dialogue_count = 0
    for cue in cues:
        text = cue.text.strip()
        if not text:
            continue
        duration = max(0.0, cue.end_seconds - cue.start_seconds)
        start = _format_ass_timestamp(cue.start_seconds)
        end = _format_ass_timestamp(cue.end_seconds)
        karaoke_text = _build_karaoke_text(text, duration)
        lines.append(
            f"Dialogue: 0,{start},{end},Default,,0,0,{style.margin_v},,{karaoke_text}"
        )
        dialogue_count += 1
    return "\n".join(lines) + "\n", dialogue_count


def write_karaoke_ass(path: Path, cues: Iterable[SrtCue], style: SubtitleStyle) -> KaraokeAssResult:
    content, count = build_karaoke_ass_text(cues, style)
    path.write_text(content, encoding="utf-8")
    return KaraokeAssResult(ass_path=path, dialogue_count=count)
