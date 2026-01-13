from __future__ import annotations

import re
from typing import Iterable

HIGHLIGHT_COLOR_RGB = (255, 214, 102)

_TOKEN_RE = re.compile(r"\S+")


def iter_token_spans(text: str) -> Iterable[tuple[int, int]]:
    for match in _TOKEN_RE.finditer(text):
        yield match.start(), match.end()


def build_highlight_spans(text: str, progress: float) -> list[tuple[int, int]]:
    spans = list(iter_token_spans(text))
    if not spans:
        return []
    clamped = max(0.0, min(progress, 1.0))
    completed = int(clamped * len(spans))
    return spans[:completed]


def build_token_durations_cs(duration_seconds: float, token_count: int) -> list[int]:
    if token_count <= 0:
        return []
    total_cs = max(0, round(duration_seconds * 100))
    if token_count == 1:
        return [total_cs]
    base = total_cs // token_count
    durations = [base] * token_count
    durations[-1] += total_cs - (base * token_count)
    return durations
