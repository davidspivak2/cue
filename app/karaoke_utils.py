from __future__ import annotations

import re
from typing import Iterable

DEFAULT_HIGHLIGHT_COLOR_HEX = "#FFD666"
_RTL_RE = re.compile(r"[\u0590-\u08FF]")
_TOKEN_RE = re.compile(r"\S+")


def parse_hex_color(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError("Expected 6-digit hex color.")
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return r, g, b


def highlight_rgb_from_hex(value: str) -> tuple[int, int, int]:
    try:
        return parse_hex_color(value)
    except ValueError:
        return parse_hex_color(DEFAULT_HIGHLIGHT_COLOR_HEX)


def is_rtl_text(text: str) -> bool:
    return bool(_RTL_RE.search(text))


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
