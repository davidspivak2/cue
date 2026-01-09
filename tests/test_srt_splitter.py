from __future__ import annotations

from dataclasses import dataclass

from app.srt_splitter import (
    SplitApplyThresholds,
    SplitMaxCue,
    SplitterConfig,
    split_segments_into_cues,
)


@dataclass(frozen=True)
class FakeWord:
    start: float
    end: float
    word: str


@dataclass(frozen=True)
class FakeSegment:
    start: float
    end: float
    text: str
    words: list[FakeWord] | None


def _make_words(
    tokens: list[str],
    *,
    start: float = 0.0,
    word_duration: float = 0.4,
    gap: float = 0.05,
    gap_after_index: int | None = None,
    gap_duration: float = 0.5,
) -> list[FakeWord]:
    words: list[FakeWord] = []
    current = start
    for idx, token in enumerate(tokens):
        word_start = current
        word_end = word_start + word_duration
        words.append(FakeWord(start=word_start, end=word_end, word=token))
        current = word_end + gap
        if gap_after_index is not None and idx == gap_after_index:
            current += gap_duration
    return words


def _make_segment(words: list[FakeWord]) -> FakeSegment:
    text = " ".join(word.word for word in words)
    return FakeSegment(start=words[0].start, end=words[-1].end, text=text, words=words)


def test_short_segment_returns_single_cue() -> None:
    words = _make_words(["Hello", "world"])
    segment = _make_segment(words)
    cues = split_segments_into_cues([segment])
    assert len(cues) == 1
    assert cues[0].start == segment.start
    assert cues[0].end == segment.end
    assert cues[0].text == segment.text


def test_long_segment_splits_on_punctuation() -> None:
    tokens = [
        "This",
        "is",
        "a",
        "long",
        "segment",
        "that",
        "needs",
        "splitting",
        "because",
        "it",
        "is",
        "huge.",
        "Next",
        "sentence",
        "continues",
        "here",
        "with",
        "more",
        "words",
        "to",
        "trigger",
        "the",
        "split.",
        "More",
        "words",
        "after",
        "the",
        "second",
        "punctuation",
        "mark",
    ]
    words = _make_words(tokens)
    segment = _make_segment(words)
    cues = split_segments_into_cues([segment])
    assert len(cues) > 1
    assert cues[0].text.endswith("huge.")


def test_long_segment_splits_on_gap() -> None:
    tokens = [f"word{idx}" for idx in range(30)]
    words = _make_words(tokens, gap_after_index=5, gap_duration=0.6)
    segment = _make_segment(words)
    cues = split_segments_into_cues([segment])
    assert len(cues) > 1
    assert cues[0].text.split()[-1] == "word5"


def test_long_segment_hard_splits_without_candidates() -> None:
    tokens = [f"word{idx}" for idx in range(30)]
    words = _make_words(tokens, gap=0.01)
    segment = _make_segment(words)
    cues = split_segments_into_cues([segment])
    assert len(cues) > 1
    for cue in cues:
        assert len(cue.text.split()) <= 14
        assert cue.end - cue.start <= 8.0


def test_joined_words_are_stripped() -> None:
    words = _make_words([" hello", "world"], gap=0.0)
    segment = _make_segment(words)
    config = SplitterConfig(
        apply_if=SplitApplyThresholds(duration_sec=0.1, text_length_chars=1, word_count=1),
        max_cue=SplitMaxCue(duration_sec=2.0, text_length_chars=20, word_count=2),
    )
    cues = split_segments_into_cues([segment], config=config)
    assert cues[0].text == "hello world"
