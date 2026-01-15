from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .ass_render import (
    DEFAULT_PRIMARY_COLOR,
    ass_color_from_hex,
    build_ass_document,
    build_ass_header_and_styles,
    escape_ass_text,
    format_ass_time,
    wrap_rtl_runs,
)
from .config import DEFAULT_HIGHLIGHT_COLOR, DEFAULT_HIGHLIGHT_OPACITY
from .srt_utils import is_word_timing_stale
from .subtitle_style import DEFAULT_FONT_NAME, SubtitleStyle
from .word_timing_schema import (
    CueWordTimings,
    WordTimingDocument,
    WordTimingValidationError,
    load_word_timings_json,
    word_timings_path_for_srt,
)

LOG = logging.getLogger("hebrew_subtitle_gui")

_CUE_TOLERANCE_SEC = 0.25
_DRIFT_TOLERANCE_SEC = 0.25


@dataclass(frozen=True)
class KaraokeCue:
    index: int
    start_sec: float
    end_sec: float
    text: str


@dataclass(frozen=True)
class KaraokeAssResult:
    ass_text: str
    highlight_event_count: int


@dataclass(frozen=True)
class KaraokeDecision:
    ass_text: str
    karaoke_enabled: bool
    reason: str
    highlight_event_count: int
    word_timings_path: Optional[Path]


def _ass_color_tag(color_ass: str) -> str:
    suffix = color_ass if color_ass.endswith("&") else f"{color_ass}&"
    return f"{{\\c{suffix}}}"


def _tokenize_word_tokens(text: str) -> list[tuple[str, bool]]:
    tokens: list[tuple[str, bool]] = []
    if not text:
        return tokens
    current: list[str] = []
    current_is_word: Optional[bool] = None
    for char in text:
        is_word = char.isalnum()
        if current_is_word is None:
            current_is_word = is_word
            current.append(char)
            continue
        if is_word == current_is_word:
            current.append(char)
        else:
            tokens.append(("".join(current), current_is_word))
            current = [char]
            current_is_word = is_word
    if current:
        tokens.append(("".join(current), current_is_word if current_is_word is not None else False))
    return tokens


def highlight_text_for_word_index(
    cue_text: str,
    word_index: int,
    normal_color_ass: str,
    highlight_color_ass: str,
) -> str:
    tokens = _tokenize_word_tokens(cue_text)
    word_positions = [idx for idx, (_, is_word) in enumerate(tokens) if is_word]
    if word_index < 0 or word_index >= len(word_positions):
        LOG.info(
            "Karaoke word index out of range: index=%s words=%s",
            word_index,
            len(word_positions),
        )
        return escape_ass_text(cue_text)
    normal_tag = _ass_color_tag(normal_color_ass)
    highlight_tag = _ass_color_tag(highlight_color_ass)
    output_parts = [normal_tag]
    current_word = 0
    for token, is_word in tokens:
        escaped = escape_ass_text(token)
        if is_word:
            if current_word == word_index:
                output_parts.append(highlight_tag)
                output_parts.append(escaped)
                output_parts.append(normal_tag)
            else:
                output_parts.append(escaped)
            current_word += 1
        else:
            output_parts.append(escaped)
    return "".join(output_parts)


def build_style_config_from_subtitle_style(
    style: SubtitleStyle,
    *,
    highlight_color: str,
    highlight_opacity: float,
) -> dict[str, object]:
    return {
        "font_name": DEFAULT_FONT_NAME,
        "font_size": style.font_size,
        "outline": style.outline,
        "shadow": style.shadow,
        "margin_v": style.margin_v,
        "box_enabled": style.box_enabled,
        "box_opacity": style.box_opacity,
        "box_padding": style.box_padding,
        "highlight_color": highlight_color,
        "highlight_opacity": highlight_opacity,
    }


def build_ass_karaoke_document(
    cues: Iterable[object],
    word_timings_doc: WordTimingDocument | Sequence[CueWordTimings] | None,
    style_config: object | None,
    *,
    time_offset_sec: float = 0.0,
    time_window: Optional[tuple[float, float]] = None,
) -> str:
    return build_ass_karaoke_document_with_stats(
        cues,
        word_timings_doc,
        style_config,
        time_offset_sec=time_offset_sec,
        time_window=time_window,
    ).ass_text


def build_ass_karaoke_document_with_stats(
    cues: Iterable[object],
    word_timings_doc: WordTimingDocument | Sequence[CueWordTimings] | None,
    style_config: object | None,
    *,
    time_offset_sec: float = 0.0,
    time_window: Optional[tuple[float, float]] = None,
) -> KaraokeAssResult:
    normalized = _coerce_karaoke_cues(cues)
    info_lines, style_lines, margin_v = build_ass_header_and_styles(style_config=style_config)
    LOG.info("Karaoke rtl_wrap_strategy=per_run")

    highlight_color = _style_highlight_color(style_config)
    highlight_opacity = _style_highlight_opacity(style_config)
    highlight_color_ass = ass_color_from_hex(highlight_color, alpha=1.0 - highlight_opacity)
    normal_color_ass = ass_color_from_hex(DEFAULT_PRIMARY_COLOR)

    cue_timings = _index_word_timings(word_timings_doc)
    events: list[tuple[float, int, float, str]] = []
    highlight_events = 0

    for cue in normalized:
        base_times = _apply_time_window(
            cue.start_sec,
            cue.end_sec,
            time_offset_sec,
            time_window,
        )
        if base_times is not None:
            base_start, base_end = base_times
            payload = wrap_rtl_runs(escape_ass_text(cue.text))
            events.append((base_start, 0, base_end, payload))

        cue_timing, lookup_key = _resolve_cue_timing(cue, cue_timings)
        if not cue_timing:
            LOG.info(
                "Karaoke cue timing missing: cue_index=%s lookup_key=%s",
                cue.index,
                lookup_key,
            )
            continue
        if (
            abs(cue_timing.cue_start - cue.start_sec) > _CUE_TOLERANCE_SEC
            or abs(cue_timing.cue_end - cue.end_sec) > _CUE_TOLERANCE_SEC
        ):
            LOG.info(
                "Karaoke cue timing mismatch: cue_index=%s cue_start=%.3f cue_end=%.3f "
                "lookup_key=%s timing_start=%.3f timing_end=%.3f timing_cue_index=%s",
                cue.index,
                cue.start_sec,
                cue.end_sec,
                lookup_key,
                cue_timing.cue_start,
                cue_timing.cue_end,
                cue_timing.cue_index,
            )
            continue
        if not cue_timing.words:
            continue
        clamped = 0
        skipped = 0
        for word_index, word in enumerate(cue_timing.words):
            span = _coerce_word_span(word)
            if span is None:
                skipped += 1
                continue
            start, end = span
            if start < cue.start_sec - _DRIFT_TOLERANCE_SEC or end > cue.end_sec + _DRIFT_TOLERANCE_SEC:
                skipped += 1
                LOG.info(
                    "Karaoke word span out of range: cue_index=%s word_index=%s start=%.3f end=%.3f",
                    cue.index,
                    word_index,
                    start,
                    end,
                )
                continue
            if start < cue.start_sec:
                start = cue.start_sec
                clamped += 1
            if end > cue.end_sec:
                end = cue.end_sec
                clamped += 1
            if end <= start:
                skipped += 1
                continue
            adjusted = _apply_time_window(start, end, time_offset_sec, time_window)
            if adjusted is None:
                continue
            event_start, event_end = adjusted
            payload = highlight_text_for_word_index(
                cue.text,
                word_index,
                normal_color_ass,
                highlight_color_ass,
            )
            events.append((event_start, 1, event_end, wrap_rtl_runs(payload)))
            highlight_events += 1
        if clamped:
            LOG.info(
                "Karaoke word spans clamped: cue_index=%s count=%s",
                cue.index,
                clamped,
            )
        if skipped:
            LOG.info(
                "Karaoke word spans skipped: cue_index=%s count=%s",
                cue.index,
                skipped,
            )

    events.sort(key=lambda item: (item[0], item[1]))

    event_lines = [
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for start_s, layer, end_s, payload in events:
        start_time = format_ass_time(start_s)
        end_time = format_ass_time(end_s)
        event_lines.append(
            f"Dialogue: {layer},{start_time},{end_time},BASE,,0,0,{margin_v},,{payload}"
        )

    return KaraokeAssResult(
        ass_text="\n".join(info_lines + style_lines + event_lines) + "\n",
        highlight_event_count=highlight_events,
    )


def build_ass_document_with_karaoke_fallback(
    cues: Iterable[object],
    *,
    srt_path: Optional[Path],
    word_timings_path: Optional[Path],
    style_config: object | None,
    time_offset_sec: float = 0.0,
    time_window: Optional[tuple[float, float]] = None,
) -> KaraokeDecision:
    resolved_word_timings_path = word_timings_path
    if resolved_word_timings_path is None and srt_path is not None:
        resolved_word_timings_path = word_timings_path_for_srt(srt_path)
    if resolved_word_timings_path is None or not resolved_word_timings_path.exists():
        return KaraokeDecision(
            ass_text=build_ass_document(cues, style_config=style_config),
            karaoke_enabled=False,
            reason="missing json",
            highlight_event_count=0,
            word_timings_path=resolved_word_timings_path,
        )
    if srt_path is not None and is_word_timing_stale(resolved_word_timings_path, srt_path):
        return KaraokeDecision(
            ass_text=build_ass_document(cues, style_config=style_config),
            karaoke_enabled=False,
            reason="stale",
            highlight_event_count=0,
            word_timings_path=resolved_word_timings_path,
        )
    try:
        doc = load_word_timings_json(resolved_word_timings_path)
    except (WordTimingValidationError, OSError) as exc:
        LOG.info("Karaoke word timings invalid: %s", exc)
        return KaraokeDecision(
            ass_text=build_ass_document(cues, style_config=style_config),
            karaoke_enabled=False,
            reason="invalid",
            highlight_event_count=0,
            word_timings_path=resolved_word_timings_path,
        )

    result = build_ass_karaoke_document_with_stats(
        cues,
        doc,
        style_config,
        time_offset_sec=time_offset_sec,
        time_window=time_window,
    )
    if result.highlight_event_count == 0:
        return KaraokeDecision(
            ass_text=build_ass_document(cues, style_config=style_config),
            karaoke_enabled=False,
            reason="no words",
            highlight_event_count=0,
            word_timings_path=resolved_word_timings_path,
        )
    return KaraokeDecision(
        ass_text=result.ass_text,
        karaoke_enabled=True,
        reason="ok",
        highlight_event_count=result.highlight_event_count,
        word_timings_path=resolved_word_timings_path,
    )


def _coerce_karaoke_cues(cues: Iterable[object]) -> list[KaraokeCue]:
    normalized: list[KaraokeCue] = []
    for idx, cue in enumerate(cues):
        if isinstance(cue, KaraokeCue):
            normalized.append(cue)
            continue
        if isinstance(cue, dict):
            index = cue.get("index", cue.get("cue_index"))
            start = cue.get("start_sec", cue.get("start_seconds", cue.get("start_s")))
            end = cue.get("end_sec", cue.get("end_seconds", cue.get("end_s")))
            text = cue.get("text")
            if start is None or end is None or text is None:
                continue
            normalized.append(
                KaraokeCue(
                    index=int(index) if index is not None else idx + 1,
                    start_sec=float(start),
                    end_sec=float(end),
                    text=str(text),
                )
            )
            continue
        start = getattr(cue, "start_sec", None)
        end = getattr(cue, "end_sec", None)
        text = getattr(cue, "text", None)
        cue_index = getattr(cue, "index", None)
        if start is None and hasattr(cue, "start_seconds"):
            start = getattr(cue, "start_seconds", None)
        if end is None and hasattr(cue, "end_seconds"):
            end = getattr(cue, "end_seconds", None)
        if cue_index is None and hasattr(cue, "cue_index"):
            cue_index = getattr(cue, "cue_index", None)
        if start is None or end is None or text is None:
            continue
        normalized.append(
            KaraokeCue(
                index=int(cue_index) if cue_index is not None else idx + 1,
                start_sec=float(start),
                end_sec=float(end),
                text=str(text),
            )
        )
    return normalized


def _resolve_cue_timing(
    cue: KaraokeCue,
    cue_timings: dict[int, CueWordTimings],
) -> tuple[Optional[CueWordTimings], int]:
    lookup_key = cue.index
    cue_timing = cue_timings.get(lookup_key)
    if cue_timing:
        return cue_timing, lookup_key
    fallback_key = lookup_key + 1
    fallback = cue_timings.get(fallback_key)
    if fallback:
        LOG.info(
            "Karaoke cue timing fallback: cue_index=%s lookup_key=%s fallback_key=%s",
            cue.index,
            lookup_key,
            fallback_key,
        )
        return fallback, fallback_key
    return None, lookup_key


def _index_word_timings(
    word_timings_doc: WordTimingDocument | Sequence[CueWordTimings] | None,
) -> dict[int, CueWordTimings]:
    if word_timings_doc is None:
        return {}
    if isinstance(word_timings_doc, WordTimingDocument):
        cues = word_timings_doc.cues
    else:
        cues = list(word_timings_doc)
    mapping: dict[int, CueWordTimings] = {}
    for cue in cues:
        cue_index = getattr(cue, "cue_index", None)
        if cue_index is None and isinstance(cue, dict):
            cue_index = cue.get("cue_index")
        if cue_index is None:
            continue
        mapping[int(cue_index)] = cue
    return mapping


def _coerce_word_span(word: object) -> Optional[tuple[float, float]]:
    if isinstance(word, dict):
        start = word.get("start")
        end = word.get("end")
    else:
        start = getattr(word, "start", None)
        end = getattr(word, "end", None)
    if start is None or end is None:
        return None
    try:
        return float(start), float(end)
    except (TypeError, ValueError):
        return None


def _style_highlight_color(style_config: object | None) -> str:
    value = _style_get(style_config, "highlight_color", DEFAULT_HIGHLIGHT_COLOR)
    return value if isinstance(value, str) else DEFAULT_HIGHLIGHT_COLOR


def _style_highlight_opacity(style_config: object | None) -> float:
    value = _style_get(style_config, "highlight_opacity", DEFAULT_HIGHLIGHT_OPACITY)
    if isinstance(value, bool):
        return DEFAULT_HIGHLIGHT_OPACITY
    if isinstance(value, (int, float)):
        opacity = float(value)
        if 0.0 <= opacity <= 1.0:
            return opacity
    return DEFAULT_HIGHLIGHT_OPACITY


def _style_get(style_config: object | None, key: str, default: object) -> object:
    if style_config is None:
        return default
    if isinstance(style_config, dict):
        return style_config.get(key, default)
    return getattr(style_config, key, default)


def _apply_time_window(
    start: float,
    end: float,
    offset: float,
    window: Optional[tuple[float, float]],
) -> Optional[tuple[float, float]]:
    adjusted_start = start - offset
    adjusted_end = end - offset
    if window is not None:
        window_start, window_end = window
        if adjusted_end <= window_start or adjusted_start >= window_end:
            return None
        adjusted_start = max(adjusted_start, window_start)
        adjusted_end = min(adjusted_end, window_end)
    if adjusted_end <= adjusted_start:
        return None
    return adjusted_start, adjusted_end
