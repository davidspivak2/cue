from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.workers as workers_module
from app.progress import ChecklistStep, ProgressStep, StepState


def _write_srt(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_alignment_emits_intermediate_progress_without_stdout_updates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "video.mp4"
    output_path = tmp_path / "sample.word_timings.json"
    srt_path = tmp_path / "sample.srt"
    audio_path = tmp_path / "sample_audio_for_whisper.wav"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"wav")
    _write_srt(
        srt_path,
        "1\n00:00:00,000 --> 00:00:05,000\nhello world this alignment test should emit progress\n",
    )

    command = [
        sys.executable,
        "-u",
        "-c",
        (
            "import sys,time; "
            "time.sleep(2.5); "
            "open(sys.argv[1], 'w', encoding='utf-8').write('ok')"
        ),
        str(output_path),
    ]
    plan = SimpleNamespace(
        should_run=True,
        command=command,
        output_path=output_path,
        reason="missing",
        device=None,
        align_model=None,
        prefer_gpu=True,
    )
    monkeypatch.setattr(workers_module, "build_alignment_plan", lambda **_kwargs: plan)

    doc = SimpleNamespace(cues=[SimpleNamespace(words=[object()] * 364)])
    monkeypatch.setattr(workers_module, "load_word_timings_json", lambda _path: doc)

    worker = workers_module.Worker(
        task_type=workers_module.TaskType.GENERATE_SRT,
        video_path=video_path,
        output_dir=tmp_path,
        subtitle_mode="word_highlight",
    )
    worker._write_subtitles_words_total = 364

    progress_events: list[tuple[str, object]] = []
    checklist_events: list[tuple[str, str, str | None]] = []

    def _capture_progress(
        step_id: str,
        step_progress: object,
        _label: str,
        *,
        force: bool = False,
    ) -> None:
        del force
        progress_events.append((step_id, step_progress))

    def _capture_checklist(
        step_id: str,
        state: str,
        *,
        reason_code: str | None = None,
        reason_text: str | None = None,
    ) -> None:
        del reason_code
        checklist_events.append((step_id, state, reason_text))

    monkeypatch.setattr(worker, "_emit_step_progress", _capture_progress)
    monkeypatch.setattr(worker, "_emit_step_event", _capture_checklist)

    state, reason = worker._run_alignment_if_needed(
        srt_path,
        audio_path,
        context="create_subtitles",
    )

    assert state == StepState.DONE
    assert reason == "Matching complete"

    align_progress_values = [
        float(value)
        for step_id, value in progress_events
        if step_id == ProgressStep.ALIGN_WORDS and isinstance(value, (int, float))
    ]
    intermediate_values = [value for value in align_progress_values if 0.0 < value < 1.0]
    assert len(intermediate_values) >= 2

    timing_details = [
        detail
        for step_id, state, detail in checklist_events
        if step_id == ChecklistStep.TIMING_WORD_HIGHLIGHTS
        and state == StepState.START
        and isinstance(detail, str)
    ]
    assert any(detail == "0/364 words" for detail in timing_details)
    assert any(detail not in {"0/364 words", "364/364 words"} for detail in timing_details)

