from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.align_utils import build_alignment_plan
from app.align_worker import AlignmentConfig, build_segments_from_srt, run_alignment
from app.srt_utils import compute_srt_sha256, is_word_timing_stale
from app.word_timing_schema import build_word_timing_stub, load_word_timings_json, save_word_timings_json


def _write_srt(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _make_stub_whisperx(monkeypatch: pytest.MonkeyPatch, aligned_segments: list[dict]) -> None:
    def load_audio(_path: str):
        return "audio"

    def load_align_model(language_code: str, device: str, model_name=None):  # noqa: ANN001
        return "model", {"language": language_code, "device": device, "model_name": model_name}

    def align(segments, model_a, metadata, audio, device, return_char_alignments=False):  # noqa: ANN001
        return {"segments": aligned_segments}

    stub = SimpleNamespace(load_audio=load_audio, load_align_model=load_align_model, align=align)
    monkeypatch.setitem(__import__("sys").modules, "whisperx", stub)


def test_build_segments_from_srt(tmp_path: Path) -> None:
    srt_path = tmp_path / "sample.srt"
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:02,000\nשלום\n\n2\n00:00:02,000 --> 00:00:04,000\nעולם\n",
    )
    segments = build_segments_from_srt(srt_path)
    assert segments == [
        {"start": 0.0, "end": 2.0, "text": "שלום"},
        {"start": 2.0, "end": 4.0, "text": "עולם"},
    ]


def test_run_alignment_writes_word_timings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    srt_path = tmp_path / "sample.srt"
    wav_path = tmp_path / "sample.wav"
    output_path = tmp_path / "sample.word_timings.json"
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:02,000\nאז\n\n2\n00:00:02,000 --> 00:00:04,000\nשלום עולם\n",
    )
    wav_path.write_bytes(b"")
    aligned_segments = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "אז",
            "words": [{"word": "אז", "start": 0.1, "end": 0.3, "score": 0.9}],
        },
        {
            "start": 2.0,
            "end": 4.0,
            "text": "שלום עולם",
            "words": [
                {"word": "שלום", "start": 2.1, "end": 2.6, "score": 0.8},
                {"word": "עולם", "start": 2.7, "end": 3.0, "score": 0.7},
            ],
        },
    ]
    _make_stub_whisperx(monkeypatch, aligned_segments)

    config = AlignmentConfig(
        wav_path=wav_path,
        srt_path=srt_path,
        output_path=output_path,
        language="he",
        prefer_gpu=False,
        device="cpu",
        align_model=None,
    )
    run_alignment(config)

    doc = load_word_timings_json(output_path)
    assert doc.schema_version == 1
    assert doc.srt_sha256 == compute_srt_sha256(srt_path)
    assert len(doc.cues) == 2
    assert [word.text for word in doc.cues[1].words] == ["שלום", "עולם"]
    assert doc.cues[1].words[0].confidence == 0.8


def test_alignment_clears_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    srt_path = tmp_path / "sample.srt"
    wav_path = tmp_path / "sample.wav"
    output_path = tmp_path / "sample.word_timings.json"
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:01,000\nבדיקה\n",
    )
    wav_path.write_bytes(b"")
    stub_doc = build_word_timing_stub(
        language="he",
        srt_sha256="wrong",
        cues=[(1, 0.0, 1.0, "בדיקה")],
    )
    save_word_timings_json(output_path, stub_doc)
    assert is_word_timing_stale(output_path, srt_path) is True
    aligned_segments = [
        {
            "start": 0.0,
            "end": 1.0,
            "text": "בדיקה",
            "words": [{"word": "בדיקה", "start": 0.1, "end": 0.6, "score": 0.95}],
        }
    ]
    _make_stub_whisperx(monkeypatch, aligned_segments)
    config = AlignmentConfig(
        wav_path=wav_path,
        srt_path=srt_path,
        output_path=output_path,
        language="he",
        prefer_gpu=False,
        device="cpu",
        align_model=None,
    )
    run_alignment(config)
    assert is_word_timing_stale(output_path, srt_path) is False


def test_alignment_handles_segment_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srt_path = tmp_path / "mismatch.srt"
    wav_path = tmp_path / "mismatch.wav"
    output_path = tmp_path / "mismatch.word_timings.json"
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:02,000\nאז\n\n"
        "2\n00:00:02,000 --> 00:00:06,000\nשלום עולם\n",
    )
    wav_path.write_bytes(b"")
    aligned_segments = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "אז",
            "words": [{"word": "אז", "start": 0.2, "end": 0.5, "score": 0.9}],
        },
        {
            "start": 2.0,
            "end": 4.0,
            "text": "שלום",
            "words": [{"word": "שלום", "start": 2.2, "end": 2.8, "score": 0.85}],
        },
        {
            "start": 4.0,
            "end": 6.0,
            "text": "עולם",
            "words": [{"word": "עולם", "start": 4.2, "end": 4.7, "score": 0.8}],
        },
    ]
    _make_stub_whisperx(monkeypatch, aligned_segments)
    config = AlignmentConfig(
        wav_path=wav_path,
        srt_path=srt_path,
        output_path=output_path,
        language="he",
        prefer_gpu=False,
        device="cpu",
        align_model=None,
    )
    run_alignment(config)
    doc = load_word_timings_json(output_path)
    assert sum(len(cue.words) for cue in doc.cues) > 0
    assert [word.text for word in doc.cues[1].words] == ["שלום", "עולם"]


def test_alignment_falls_back_to_estimated_when_align_model_load_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    srt_path = tmp_path / "fallback.srt"
    wav_path = tmp_path / "fallback.wav"
    output_path = tmp_path / "fallback.word_timings.json"
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:02,000\nשלום עולם\n",
    )
    wav_path.write_bytes(b"")

    def load_audio(_path: str):
        return "audio"

    def load_align_model(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise IndexError("list index out of range")

    def align(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return {"segments": []}

    stub = SimpleNamespace(load_audio=load_audio, load_align_model=load_align_model, align=align)
    monkeypatch.setitem(__import__("sys").modules, "whisperx", stub)

    config = AlignmentConfig(
        wav_path=wav_path,
        srt_path=srt_path,
        output_path=output_path,
        language="he",
        prefer_gpu=False,
        device="cpu",
        align_model=None,
    )
    run_alignment(config)
    doc = load_word_timings_json(output_path)
    assert sum(len(cue.words) for cue in doc.cues) > 0


def test_build_alignment_plan_for_preview(tmp_path: Path) -> None:
    srt_path = tmp_path / "sample.srt"
    audio_path = tmp_path / "sample_audio_for_whisper.wav"
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:01,000\nבדיקה\n",
    )
    audio_path.write_bytes(b"")
    doc = build_word_timing_stub(
        language="he",
        srt_sha256="wrong",
        cues=[(1, 0.0, 1.0, "בדיקה")],
    )
    output_path = srt_path.with_suffix(".word_timings.json")
    save_word_timings_json(output_path, doc)

    plan_static = build_alignment_plan(
        subtitle_mode="static",
        srt_path=srt_path,
        audio_path=audio_path,
        language="he",
    )
    assert plan_static.should_run is False

    plan = build_alignment_plan(
        subtitle_mode="word_highlight",
        srt_path=srt_path,
        audio_path=audio_path,
        language="he",
    )
    assert plan.should_run is True
    assert plan.command[1] == "-u"
    assert plan.command[2:4] == ["-m", "app.align_worker"]


def test_alignment_plan_runs_when_word_timings_empty(tmp_path: Path) -> None:
    srt_path = tmp_path / "empty_words.srt"
    audio_path = tmp_path / "empty_words_audio_for_whisper.wav"
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:01,000\nבדיקה\n",
    )
    audio_path.write_bytes(b"")
    doc = build_word_timing_stub(
        language="he",
        srt_sha256=compute_srt_sha256(srt_path),
        cues=[(1, 0.0, 1.0, "בדיקה")],
    )
    output_path = srt_path.with_suffix(".word_timings.json")
    save_word_timings_json(output_path, doc)

    plan = build_alignment_plan(
        subtitle_mode="word_highlight",
        srt_path=srt_path,
        audio_path=audio_path,
        language="he",
    )
    assert plan.should_run is True
    assert plan.reason == "word_timings_has_no_words"
