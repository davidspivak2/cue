from __future__ import annotations

import types
from pathlib import Path

import pytest

from app import transcribe_worker
from app.srt_utils import SrtSegment
from app.srt_splitter import SplitterStats


def test_whisperx_load_model_avoids_vad_method(tmp_path, monkeypatch):
    calls: list[dict[str, object]] = []

    def load_model(model_name, device, **kwargs):  # noqa: ANN001
        calls.append(kwargs)
        if "vad_method" in kwargs:
            raise TypeError("load_model() got an unexpected keyword argument 'vad_method'")

        class DummyModel:
            def transcribe(self, path):  # noqa: ANN001
                return {"segments": [], "language": "he"}

        return DummyModel()

    def load_align_model(language_code, device):  # noqa: ANN001
        return object(), {}

    def align(segments, align_model, metadata, audio, device):  # noqa: ANN001
        return {"segments": segments}

    fake_whisperx = types.SimpleNamespace(
        __version__="0.test",
        load_model=load_model,
        load_align_model=load_align_model,
        align=align,
    )
    monkeypatch.setitem(transcribe_worker.sys.modules, "whisperx", fake_whisperx)

    result = transcribe_worker._run_whisperx_alignment(
        wav_path=tmp_path / "audio.wav",
        model_name="large-v3",
        language="he",
        device="cpu",
        compute_type="float32",
        vad_method="silero",
    )

    assert result is not None
    assert len(calls) == 1
    assert "vad_method" not in calls[0]


def test_main_falls_back_when_whisperx_alignment_fails(tmp_path, monkeypatch, capsys):
    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"dummy")
    srt_path = tmp_path / "out.srt"
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"dummy")

    monkeypatch.setattr(transcribe_worker, "_run_whisperx_alignment", lambda **_: None)

    def fake_run_transcription_attempt(**_kwargs):
        segments = [SrtSegment(index=1, start=0.0, end=1.0, text="שלום")]
        return [], [], segments, SplitterStats()

    monkeypatch.setattr(transcribe_worker, "_run_transcription_attempt", fake_run_transcription_attempt)
    monkeypatch.setattr(transcribe_worker, "_load_model", lambda *args, **kwargs: object())
    monkeypatch.setattr(transcribe_worker, "_enable_faulthandler", lambda: None)
    monkeypatch.setattr(transcribe_worker, "_resolve_whisperx_device", lambda *_: ("cpu", "float32"))

    exit_code = transcribe_worker.main(
        [
            "--wav",
            str(wav_path),
            "--srt",
            str(srt_path),
            "--video",
            str(video_path),
            "--subtitle-mode",
            "word_highlight",
        ],
        hard_exit=False,
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "DONE" in captured
    assert srt_path.exists()
    assert srt_path.stat().st_size > 0


def test_word_highlight_fallback_segments_have_underlines_and_monotonic_times():
    class FakeWord:
        def __init__(self, word, start, end):
            self.word = word
            self.start = start
            self.end = end

    class FakeSegment:
        def __init__(self, text, start, end, words):
            self.text = text
            self.start = start
            self.end = end
            self.words = words

    segment = FakeSegment(
        text="זה הטקסט שלי",
        start=0.0,
        end=1.2,
        words=[
            FakeWord("זה", 0.0, 0.2),
            FakeWord(" הטקסט", 0.2, 0.6),
            FakeWord(" שלי", 0.6, 1.0),
        ],
    )
    cues = transcribe_worker._build_word_highlight_fallback_segments([segment])
    assert len(cues) == 3
    assert all(cue.text for cue in cues)
    assert all("<u>" in cue.text and "</u>" in cue.text for cue in cues)
    times = [(cue.start, cue.end) for cue in cues]
    assert all(end > start for start, end in times)
    assert times == sorted(times, key=lambda item: item[0])
