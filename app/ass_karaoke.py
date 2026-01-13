from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.karaoke_utils import (
    build_weighted_token_durations_cs,
    highlight_rgb_from_hex,
    is_rtl_text,
    iter_token_spans,
)
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


def _build_ass_header(
    style: SubtitleStyle,
    *,
    highlight_rgb: tuple[int, int, int],
    highlight_mode: str,
    highlight_bg_opacity: int,
    play_res_x: int,
    play_res_y: int,
) -> str:
    outline = style.outline + style.box_padding if style.box_enabled else style.outline
    base_border_style = 3 if style.box_enabled else 1
    base_back_alpha = get_box_alpha_byte(style) if style.box_enabled else 255
    highlight_border_style = 3 if highlight_mode == "text+bg" else 1
    highlight_back_alpha = max(0, min(255, round(255 * (highlight_bg_opacity / 100))))
    primary = _format_ass_color((255, 255, 255))
    secondary = _format_ass_color((0, 0, 0), 255)
    outline_color = _format_ass_color((0, 0, 0))
    base_back_color = _format_ass_color((0, 0, 0), base_back_alpha)
    highlight_primary = _format_ass_color(highlight_rgb)
    highlight_secondary = _format_ass_color((0, 0, 0), 255)
    highlight_back_color = (
        _format_ass_color(highlight_rgb, highlight_back_alpha)
        if highlight_mode == "text+bg"
        else _format_ass_color((0, 0, 0), 255)
    )
    base_style = (
        "Style: Base,"
        f"{DEFAULT_FONT_NAME},"
        f"{style.font_size},"
        f"{primary},"
        f"{secondary},"
        f"{outline_color},"
        f"{base_back_color},"
        "0,0,0,0,"
        f"{base_border_style},"
        f"{outline},"
        f"{style.shadow},"
        "2,"
        "20,"
        "20,"
        f"{style.margin_v},"
        "1"
    )
    highlight_style = (
        "Style: Highlight,"
        f"{DEFAULT_FONT_NAME},"
        f"{style.font_size},"
        f"{highlight_primary},"
        f"{highlight_secondary},"
        f"{outline_color},"
        f"{highlight_back_color},"
        "0,0,0,0,"
        f"{highlight_border_style},"
        f"{outline},"
        f"{style.shadow},"
        "2,"
        "20,"
        "20,"
        f"{style.margin_v},"
        "1"
    )
    return "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "Collisions: Normal",
            f"PlayResX: {play_res_x}",
            f"PlayResY: {play_res_y}",
            "ScaledBorderAndShadow: yes",
            "Timer: 100.0000",
            "",
            "[V4+ Styles]",
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
            base_style,
            highlight_style,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


def _build_karaoke_text(text: str, duration_seconds: float, *, rtl_marks: bool) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    token_spans = list(iter_token_spans(normalized))
    durations = build_weighted_token_durations_cs(normalized, duration_seconds)
    if not token_spans:
        return normalized.replace("\n", "\\N")
    chunks: list[str] = []
    last_end = 0
    for idx, (start, end) in enumerate(token_spans):
        chunks.append(normalized[last_end:start].replace("\n", "\\N"))
        duration_cs = durations[idx]
        token_text = normalized[start:end].replace("\n", "\\N")
        if rtl_marks:
            token_text = f"\u200F{token_text}"
        chunks.append(f"{{\\k{duration_cs}}}{token_text}")
        last_end = end
    chunks.append(normalized[last_end:].replace("\n", "\\N"))
    return "".join(chunks)


def build_karaoke_ass_text(
    cues: Iterable[SrtCue],
    style: SubtitleStyle,
    *,
    highlight_color: str,
    highlight_mode: str,
    highlight_bg_opacity: int,
    play_res_x: int,
    play_res_y: int,
) -> tuple[str, int]:
    highlight_rgb = highlight_rgb_from_hex(highlight_color)
    lines = [
        _build_ass_header(
            style,
            highlight_rgb=highlight_rgb,
            highlight_mode=highlight_mode,
            highlight_bg_opacity=highlight_bg_opacity,
            play_res_x=play_res_x,
            play_res_y=play_res_y,
        )
    ]
    dialogue_count = 0
    for cue in cues:
        text = cue.text.strip()
        if not text:
            continue
        duration = max(0.0, cue.end_seconds - cue.start_seconds)
        start = _format_ass_timestamp(cue.start_seconds)
        end = _format_ass_timestamp(cue.end_seconds)
        rtl_text = is_rtl_text(text)
        base_text = text.replace("\n", "\\N")
        karaoke_text = _build_karaoke_text(text, duration, rtl_marks=rtl_text)
        if rtl_text:
            base_text = f"\u202B{base_text}\u202C"
            karaoke_text = f"\u202B{karaoke_text}\u202C"
        lines.append(f"Dialogue: 0,{start},{end},Base,,0,0,0,,{base_text}")
        lines.append(f"Dialogue: 1,{start},{end},Highlight,,0,0,0,,{karaoke_text}")
        dialogue_count += 1
    return "\n".join(lines) + "\n", dialogue_count


def write_karaoke_ass(
    path: Path,
    cues: Iterable[SrtCue],
    style: SubtitleStyle,
    *,
    highlight_color: str,
    highlight_mode: str,
    highlight_bg_opacity: int,
    play_res_x: int,
    play_res_y: int,
) -> KaraokeAssResult:
    content, count = build_karaoke_ass_text(
        cues,
        style,
        highlight_color=highlight_color,
        highlight_mode=highlight_mode,
        highlight_bg_opacity=highlight_bg_opacity,
        play_res_x=play_res_x,
        play_res_y=play_res_y,
    )
    path.write_text(content, encoding="utf-8")
    return KaraokeAssResult(ass_path=path, dialogue_count=count)
