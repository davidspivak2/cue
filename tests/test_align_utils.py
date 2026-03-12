from __future__ import annotations

from pathlib import Path

from app import align_utils


def test_build_alignment_plan_uses_python_module_command_when_not_frozen(
    tmp_path: Path, monkeypatch
) -> None:
    python_exe = str(tmp_path / "python.exe")
    monkeypatch.setattr(align_utils.sys, "frozen", False, raising=False)
    monkeypatch.setattr(align_utils.sys, "executable", python_exe)

    srt_path = tmp_path / "sample.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    audio_path = tmp_path / "sample_audio_for_whisper.wav"

    plan = align_utils.build_alignment_plan(
        srt_path=srt_path,
        audio_path=audio_path,
        language="he",
    )

    assert plan.should_run is True
    assert plan.command[:4] == [python_exe, "-u", "-m", "app.align_worker"]


def test_build_alignment_plan_skips_when_frozen_align_worker_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    frozen_backend_exe = tmp_path / "CueBackend.exe"
    frozen_backend_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(align_utils.sys, "frozen", True, raising=False)
    monkeypatch.setattr(align_utils.sys, "executable", str(frozen_backend_exe))

    srt_path = tmp_path / "sample.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    audio_path = tmp_path / "sample_audio_for_whisper.wav"

    plan = align_utils.build_alignment_plan(
        srt_path=srt_path,
        audio_path=audio_path,
        language="he",
    )

    assert plan.should_run is False
    assert plan.command == []
    assert plan.reason == "align_worker_missing"


def test_build_alignment_plan_allows_explicit_python_override_when_frozen(
    tmp_path: Path, monkeypatch
) -> None:
    frozen_backend_exe = tmp_path / "CueBackend.exe"
    frozen_backend_exe.write_text("", encoding="utf-8")
    explicit_python = str(tmp_path / "python.exe")
    monkeypatch.setattr(align_utils.sys, "frozen", True, raising=False)
    monkeypatch.setattr(align_utils.sys, "executable", str(frozen_backend_exe))

    srt_path = tmp_path / "sample.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    audio_path = tmp_path / "sample_audio_for_whisper.wav"

    plan = align_utils.build_alignment_plan(
        srt_path=srt_path,
        audio_path=audio_path,
        language="he",
        python_executable=explicit_python,
    )

    assert plan.should_run is True
    assert plan.command[:4] == [explicit_python, "-u", "-m", "app.align_worker"]
