from __future__ import annotations

import re
from pathlib import Path

from .srt_utils import SrtCue, parse_srt_file


def tokenize_alignment_words(text: str, language: str) -> list[str]:
    del language
    return re.findall(r"\S+", text)


def count_alignment_words_in_cues(cues: list[SrtCue], language: str) -> int:
    total = 0
    for cue in cues:
        total += len(tokenize_alignment_words(cue.text, language))
    return total


def count_alignment_words_in_srt(srt_path: Path, language: str) -> int:
    try:
        cues = parse_srt_file(srt_path)
    except Exception:  # noqa: BLE001
        return 0
    return count_alignment_words_in_cues(cues, language)
