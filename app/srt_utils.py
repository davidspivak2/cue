from __future__ import annotations

from datetime import timedelta
from typing import Iterable


class SrtSegment:
    def __init__(self, index: int, start: float, end: float, text: str) -> None:
        self.index = index
        self.start = start
        self.end = end
        self.text = text


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
