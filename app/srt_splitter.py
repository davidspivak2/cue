from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol


class WordLike(Protocol):
    start: float
    end: float
    word: str


class SegmentLike(Protocol):
    start: float
    end: float
    text: str
    words: Iterable[WordLike] | None


@dataclass(frozen=True)
class SplitApplyThresholds:
    duration_sec: float = 12.0
    text_length_chars: int = 160
    word_count: int = 26


@dataclass(frozen=True)
class SplitMaxCue:
    duration_sec: float = 8.0
    text_length_chars: int = 90
    word_count: int = 14


@dataclass(frozen=True)
class SplitterConfig:
    apply_if: SplitApplyThresholds = field(default_factory=SplitApplyThresholds)
    max_cue: SplitMaxCue = field(default_factory=SplitMaxCue)
    gap_sec: float = 0.4
    prefer: tuple[str, ...] = ("punctuation", "gap")

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": True,
            "apply_if": {
                "segment_duration_sec": self.apply_if.duration_sec,
                "segment_text_length_chars": self.apply_if.text_length_chars,
                "segment_word_count": self.apply_if.word_count,
            },
            "max_cue": {
                "max_cue_duration_sec": self.max_cue.duration_sec,
                "max_cue_text_length_chars": self.max_cue.text_length_chars,
                "max_cue_word_count": self.max_cue.word_count,
            },
            "gap_sec": self.gap_sec,
            "prefer": list(self.prefer),
        }


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class _Word:
    start: float
    end: float
    text: str


_TRAILING_STRIP = "\"'“”‘’()[]{}״׳"
_PUNCTUATION = {".", ",", "?", "!", ";", ":", "—", "–"}


def split_segments_into_cues(
    segments: Iterable[SegmentLike],
    *,
    config: SplitterConfig = SplitterConfig(),
) -> list[Cue]:
    cues: list[Cue] = []
    for segment in segments:
        cues.extend(_split_segment(segment, config))
    return cues


def _split_segment(segment: SegmentLike, config: SplitterConfig) -> list[Cue]:
    raw_words = list(getattr(segment, "words", []) or [])
    if not _should_split(segment, config.apply_if, raw_words):
        return [
            Cue(
                start=float(segment.start),
                end=float(segment.end),
                text=str(segment.text),
            )
        ]
    words = _normalize_words(raw_words)
    if not words:
        return _split_segment_by_time_and_text(segment, config.max_cue)
    return _split_segment_by_words(segment, words, config)


def _should_split(
    segment: SegmentLike,
    thresholds: SplitApplyThresholds,
    words: list[WordLike],
) -> bool:
    duration = float(segment.end) - float(segment.start)
    text = str(segment.text)
    text_length = len(text.strip())
    word_count = len(words) if words else len(text.split())
    return (
        duration > thresholds.duration_sec
        or text_length > thresholds.text_length_chars
        or word_count > thresholds.word_count
    )


def _split_segment_by_time_and_text(
    segment: SegmentLike, max_cue: SplitMaxCue
) -> list[Cue]:
    duration = float(segment.end) - float(segment.start)
    if duration <= max_cue.duration_sec:
        return [
            Cue(
                start=float(segment.start),
                end=float(segment.end),
                text=str(segment.text),
            )
        ]
    total_cues = max(1, int(-(-duration // max_cue.duration_sec)))
    words = str(segment.text).split()
    if words:
        total_cues = min(total_cues, len(words))
    text_chunks = _split_text_into_chunks(words, total_cues)
    chunk_duration = duration / total_cues
    cues: list[Cue] = []
    for idx in range(total_cues):
        start = float(segment.start) + chunk_duration * idx
        end = float(segment.start) + chunk_duration * (idx + 1)
        if idx == total_cues - 1:
            end = float(segment.end)
        text = text_chunks[idx] if idx < len(text_chunks) else ""
        cues.append(Cue(start=start, end=end, text=text))
    return cues


def _split_text_into_chunks(words: list[str], total_cues: int) -> list[str]:
    if not words:
        return [""]
    total_cues = max(1, min(total_cues, len(words)))
    per_chunk = max(1, int(-(-len(words) // total_cues)))
    chunks = []
    for idx in range(0, len(words), per_chunk):
        chunk = " ".join(words[idx : idx + per_chunk]).strip()
        chunks.append(chunk)
    if len(chunks) < total_cues:
        chunks.extend([""] * (total_cues - len(chunks)))
    return chunks


def _split_segment_by_words(
    segment: SegmentLike,
    words: list[_Word],
    config: SplitterConfig,
) -> list[Cue]:
    cues: list[Cue] = []
    current_words: list[_Word] = []
    start_idx = 0
    punctuation_candidate: int | None = None
    gap_candidate: int | None = None
    i = 0
    while i < len(words):
        word = words[i]
        if not current_words:
            start_idx = i
            punctuation_candidate = None
            gap_candidate = None
        prospective_words = current_words + [word]
        if current_words and _would_exceed(prospective_words, config.max_cue):
            split_idx = _best_candidate(
                start_idx,
                i - 1,
                punctuation_candidate,
                gap_candidate,
            )
            if split_idx < start_idx:
                split_idx = i - 1
            cues.append(
                _build_cue(
                    segment,
                    words[start_idx : split_idx + 1],
                )
            )
            current_words = []
            i = split_idx + 1
            continue
        current_words.append(word)
        if _ends_with_punctuation(word.text):
            punctuation_candidate = i
        if i - 1 >= start_idx:
            gap = word.start - words[i - 1].end
            if gap >= config.gap_sec:
                gap_candidate = i - 1
        i += 1
    if current_words:
        cues.append(_build_cue(segment, current_words))
    return cues


def _build_cue(segment: SegmentLike, words: list[_Word]) -> Cue:
    start = max(float(segment.start), words[0].start)
    end = min(float(segment.end), words[-1].end)
    text = _join_words(words)
    return Cue(start=start, end=end, text=text)


def _normalize_words(words: Iterable[WordLike] | None) -> list[_Word]:
    if not words:
        return []
    normalized: list[_Word] = []
    for word in words:
        text = _word_text(word)
        if text is None:
            continue
        normalized.append(_Word(start=float(word.start), end=float(word.end), text=text))
    return normalized


def _word_text(word: WordLike) -> str | None:
    if hasattr(word, "word"):
        return str(word.word)
    if hasattr(word, "text"):
        return str(getattr(word, "text"))
    return None


def _join_words(words: list[_Word]) -> str:
    parts: list[str] = []
    for word in words:
        raw = word.text
        if not parts:
            parts.append(raw.lstrip())
            continue
        if raw[:1].isspace():
            parts.append(raw)
        else:
            parts.append(" " + raw.lstrip())
    return "".join(parts).strip()


def _ends_with_punctuation(word_text: str) -> bool:
    cleaned = word_text.rstrip().rstrip(_TRAILING_STRIP)
    if not cleaned:
        return False
    return cleaned[-1] in _PUNCTUATION


def _would_exceed(words: list[_Word], max_cue: SplitMaxCue) -> bool:
    duration = words[-1].end - words[0].start
    text_length = len(_join_words(words))
    word_count = len(words)
    return (
        duration > max_cue.duration_sec
        or text_length > max_cue.text_length_chars
        or word_count > max_cue.word_count
    )


def _best_candidate(
    start_idx: int,
    last_idx: int,
    punctuation_candidate: int | None,
    gap_candidate: int | None,
) -> int:
    if punctuation_candidate is not None and start_idx <= punctuation_candidate <= last_idx:
        return punctuation_candidate
    if gap_candidate is not None and start_idx <= gap_candidate <= last_idx:
        return gap_candidate
    return -1
