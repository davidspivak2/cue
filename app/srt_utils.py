from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
import re
from typing import Iterable, Optional, Sequence


class SrtSegment:
    def __init__(self, index: int, start: float, end: float, text: str) -> None:
        self.index = index
        self.start = start
        self.end = end
        self.text = text


@dataclass(frozen=True)
class SrtCue:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class PreviewMoment:
    cue_index: int
    timestamp_seconds: float
    subtitle_text: str
    cue_start_seconds: float
    cue_end_seconds: float


def _format_timestamp(seconds: float) -> str:
    delta = timedelta(seconds=max(seconds, 0))
    total_seconds = int(delta.total_seconds())
    millis = int(delta.microseconds / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def segments_to_srt(segments: Iterable[SrtSegment]) -> str:
    lines: list[str] = []
    for segment in segments:
        lines.append(str(segment.index))
        lines.append(f"{_format_timestamp(segment.start)} --> {_format_timestamp(segment.end)}")
        lines.append(segment.text.strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"


_TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})"
)


def _parse_timestamp(value: str) -> Optional[float]:
    parts = value.replace(",", ".").split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds


def parse_srt_text(srt_text: str) -> list[SrtCue]:
    normalized = srt_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    blocks = re.split(r"\n\s*\n", normalized)
    cues: list[SrtCue] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        timestamp_line_index = None
        match = None
        for idx, line in enumerate(lines):
            match = _TIMESTAMP_RE.search(line)
            if match:
                timestamp_line_index = idx
                break
        if timestamp_line_index is None or not match:
            continue
        start_seconds = _parse_timestamp(match.group("start"))
        end_seconds = _parse_timestamp(match.group("end"))
        if start_seconds is None or end_seconds is None:
            continue
        text_lines = lines[timestamp_line_index + 1 :]
        text = " ".join(text_lines).strip()
        cues.append(SrtCue(start_seconds=start_seconds, end_seconds=end_seconds, text=text))
    return cues


def parse_srt_file(path: Path) -> list[SrtCue]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return []
    return parse_srt_text(content)


def select_preview_moment(
    cues: Sequence[SrtCue], duration_seconds: Optional[float]
) -> Optional[PreviewMoment]:
    if not cues:
        return None
    chosen_index = None
    chosen = None
    for idx, cue in enumerate(cues):
        if cue.text.strip():
            chosen_index = idx
            chosen = cue
            break
    if chosen is None or chosen_index is None:
        return None
    length = max(chosen.end_seconds - chosen.start_seconds, 0.0)
    timestamp = chosen.start_seconds + (length * 0.25 if length > 0 else 0.0)
    timestamp = max(chosen.start_seconds, min(timestamp, chosen.end_seconds))
    return PreviewMoment(
        cue_index=chosen_index,
        timestamp_seconds=timestamp,
        subtitle_text=chosen.text,
        cue_start_seconds=chosen.start_seconds,
        cue_end_seconds=chosen.end_seconds,
    )
