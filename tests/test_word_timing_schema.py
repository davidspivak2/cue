from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.srt_utils import compute_srt_sha256, is_word_timing_stale
from app.word_timing_schema import (
    CueWordTimings,
    SCHEMA_VERSION,
    WordSpan,
    WordTimingDocument,
    build_word_timing_stub,
    load_word_timings_json,
    save_word_timings_json,
    word_timings_path_for_srt,
)


def test_schema_round_trip(tmp_path: Path) -> None:
    created = datetime.now(timezone.utc).isoformat()
    doc = WordTimingDocument(
        schema_version=SCHEMA_VERSION,
        created_utc=created,
        language="he",
        srt_sha256="deadbeef",
        cues=[
            CueWordTimings(
                cue_index=1,
                cue_start=0.0,
                cue_end=1.0,
                cue_text="שלום עולם",
                words=[WordSpan(text="שלום", start=0.0, end=0.5, confidence=0.9)],
            )
        ],
    )
    path = tmp_path / "sample.word_timings.json"
    save_word_timings_json(path, doc)
    loaded = load_word_timings_json(path)
    assert loaded.schema_version == doc.schema_version
    assert loaded.created_utc == doc.created_utc
    assert loaded.language == doc.language
    assert loaded.srt_sha256 == doc.srt_sha256
    assert loaded.cues[0].cue_text == doc.cues[0].cue_text
    assert loaded.cues[0].words[0].text == doc.cues[0].words[0].text


def test_hash_consistency(tmp_path: Path) -> None:
    srt_path = tmp_path / "sample.srt"
    content = "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    srt_path.write_text(content, encoding="utf-8")
    first = compute_srt_sha256(srt_path)
    srt_path.write_text(content, encoding="utf-8")
    second = compute_srt_sha256(srt_path)
    assert first == second


def test_staleness_detection(tmp_path: Path) -> None:
    srt_path = tmp_path / "sample.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    word_timings_path = word_timings_path_for_srt(srt_path)
    doc = build_word_timing_stub(
        language="he",
        srt_sha256=compute_srt_sha256(srt_path),
        cues=[(1, 0.0, 1.0, "Hi")],
    )
    save_word_timings_json(word_timings_path, doc)
    assert is_word_timing_stale(word_timings_path, srt_path) is False

    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi there\n", encoding="utf-8")
    assert is_word_timing_stale(word_timings_path, srt_path) is True

    missing_path = tmp_path / "missing.word_timings.json"
    assert is_word_timing_stale(missing_path, srt_path) is True

    mismatched_path = tmp_path / "mismatch.word_timings.json"
    mismatched_payload = {
        "schema_version": SCHEMA_VERSION + 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "language": "he",
        "srt_sha256": compute_srt_sha256(srt_path),
        "cues": [],
    }
    mismatched_path.write_text(
        json.dumps(mismatched_payload, indent=2),
        encoding="utf-8",
    )
    assert is_word_timing_stale(mismatched_path, srt_path) is True


def test_word_timing_naming_convention(tmp_path: Path) -> None:
    srt_path = tmp_path / "video.srt"
    expected = tmp_path / "video.word_timings.json"
    assert word_timings_path_for_srt(srt_path) == expected
