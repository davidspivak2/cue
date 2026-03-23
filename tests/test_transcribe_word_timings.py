from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.srt_utils import compute_srt_sha256
from app.transcribe_worker import (
    _deserialize_raw_segments,
    _serialize_raw_segments,
    _write_word_timings_from_transcription,
)
from app.word_timing_schema import load_word_timings_json


def _write_srt(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_write_word_timings_from_transcription_writes_direct_timings(tmp_path: Path) -> None:
    srt_path = tmp_path / "sample.srt"
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:01,000\nhello world\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nagain\n",
    )

    raw_segments = [
        SimpleNamespace(
            start=0.0,
            end=2.0,
            text="hello world again",
                words=[
                    SimpleNamespace(word="hello", start=0.05, end=0.35, probability=0.9),
                    SimpleNamespace(word="world", start=0.36, end=0.75, probability=0.8),
                    SimpleNamespace(word="again", start=1.20, end=1.45, probability=0.85),
                ],
            )
        ]
    output_segments = [
        SimpleNamespace(index=1, start=0.0, end=1.0, text="hello world"),
        SimpleNamespace(index=2, start=1.0, end=2.0, text="again"),
    ]

    total_words = _write_word_timings_from_transcription(
        raw_segments=raw_segments,
        output_segments=output_segments,
        srt_path=srt_path,
        language="en",
    )

    assert total_words == 3
    doc = load_word_timings_json(srt_path.with_suffix(".word_timings.json"))
    assert doc.language == "en"
    assert doc.srt_sha256 == compute_srt_sha256(srt_path)
    assert [word.text for word in doc.cues[0].words] == ["hello", "world"]
    assert [word.text for word in doc.cues[1].words] == ["again"]


def test_raw_segment_roundtrip_preserves_word_timestamps() -> None:
    raw_segments = [
        SimpleNamespace(
            start=0.0,
            end=1.0,
            text="hello",
            words=[
                SimpleNamespace(word="hello", start=0.1, end=0.4, probability=0.95),
            ],
        )
    ]

    payload = _serialize_raw_segments(raw_segments)
    restored = _deserialize_raw_segments(payload)

    assert len(restored) == 1
    assert restored[0].text == "hello"
    assert len(restored[0].words) == 1
    assert restored[0].words[0].word == "hello"
    assert restored[0].words[0].start == 0.1
    assert restored[0].words[0].end == 0.4
    assert restored[0].words[0].probability == 0.95
