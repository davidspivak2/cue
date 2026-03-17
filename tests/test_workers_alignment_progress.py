from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.graphics_overlay_export import OverlaySegment
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


def test_resolve_word_timings_path_prefers_srt_derived_file(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "video.mp4"
    srt_path = tmp_path / "subtitles.srt"
    derived_path = tmp_path / "subtitles.word_timings.json"
    project_path = tmp_path / "word_timings.json"
    video_path.write_bytes(b"video")
    _write_srt(srt_path, "1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    derived_path.write_text("{}", encoding="utf-8")
    project_path.write_text("{}", encoding="utf-8")

    worker = workers_module.Worker(
        task_type=workers_module.TaskType.GENERATE_SRT,
        video_path=video_path,
        output_dir=tmp_path,
        subtitle_mode="word_highlight",
        word_timings_path=project_path,
    )

    assert worker._resolve_word_timings_path(srt_path) == derived_path


def test_alignment_uses_derived_result_path_when_timings_are_already_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "video.mp4"
    srt_path = tmp_path / "subtitles.srt"
    audio_path = tmp_path / "subtitles_audio_for_whisper.wav"
    derived_path = tmp_path / "subtitles.word_timings.json"
    project_path = tmp_path / "word_timings.json"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"wav")
    _write_srt(srt_path, "1\n00:00:00,000 --> 00:00:01,000\nhello\n")
    derived_path.write_text("{}", encoding="utf-8")
    project_path.write_text("{}", encoding="utf-8")

    plan = SimpleNamespace(
        should_run=False,
        command=[],
        output_path=derived_path,
        reason="up_to_date",
        device=None,
        align_model=None,
        prefer_gpu=True,
    )
    monkeypatch.setattr(workers_module, "build_alignment_plan", lambda **_kwargs: plan)

    worker = workers_module.Worker(
        task_type=workers_module.TaskType.GENERATE_SRT,
        video_path=video_path,
        output_dir=tmp_path,
        subtitle_mode="word_highlight",
        word_timings_path=project_path,
    )

    state, reason = worker._run_alignment_if_needed(
        srt_path,
        audio_path,
        context="create_subtitles",
    )

    assert state == StepState.SKIPPED
    assert reason == "Already timed"
    assert worker._word_timings_path == derived_path


def test_generate_srt_runs_alignment_even_in_static_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    worker = workers_module.Worker(
        task_type=workers_module.TaskType.GENERATE_SRT,
        video_path=video_path,
        output_dir=tmp_path,
        subtitle_mode="static",
        transcription_settings=workers_module.TranscriptionSettings(
            apply_audio_filter=False,
            keep_extracted_audio=True,
            device="cpu",
            compute_type="float32",
            quality="quality",
            punctuation_rescue_fallback_enabled=False,
            vad_gap_rescue_enabled=False,
        ),
    )

    checklist_events: list[tuple[str, str, str | None]] = []
    alignment_calls: list[tuple[Path, Path, str]] = []
    monotonic_state = {"value": 0.0}

    def _fake_monotonic() -> float:
        monotonic_state["value"] += 1.0
        return monotonic_state["value"]

    def _fake_run_transcription_subprocess(**kwargs: object) -> None:
        srt_path = kwargs["srt_path"]
        assert isinstance(srt_path, Path)
        _write_srt(srt_path, "1\n00:00:00,000 --> 00:00:01,000\nhello\n")

    def _fake_run_alignment_if_needed(
        srt_path: Path,
        audio_path: Path,
        *,
        context: str,
        **_kwargs: object,
    ) -> tuple[str, str]:
        alignment_calls.append((srt_path, audio_path, context))
        return StepState.DONE, "Matching complete"

    def _capture_checklist(
        step_id: str,
        state: str,
        *,
        reason_code: str | None = None,
        reason_text: str | None = None,
    ) -> None:
        del reason_code
        checklist_events.append((step_id, state, reason_text))

    monkeypatch.setattr(worker, "_probe_duration", lambda _path: 1.0)
    monkeypatch.setattr(worker, "_extract_audio", lambda path, *_args: path.write_bytes(b"wav"))
    monkeypatch.setattr(worker, "_run_transcription_subprocess", _fake_run_transcription_subprocess)
    monkeypatch.setattr(worker, "_capture_audio_info_if_needed", lambda _path: None)
    monkeypatch.setattr(worker, "_ensure_word_timings_file", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "_emit_transcription_post_steps", lambda: None)
    monkeypatch.setattr(worker, "_run_alignment_if_needed", _fake_run_alignment_if_needed)
    monkeypatch.setattr(worker, "_emit_step_event", _capture_checklist)
    monkeypatch.setattr(worker, "_emit_step_progress", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workers_module, "parse_srt_file", lambda _path: [])
    monkeypatch.setattr(workers_module, "select_preview_moment", lambda _cues, _duration: None)
    monkeypatch.setattr(workers_module.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(workers_module.time, "sleep", lambda _seconds: None)

    result = worker._run_generate_srt()

    assert result["srt_path"] == str(tmp_path / "video.srt")
    assert alignment_calls == [
        (
            tmp_path / "video.srt",
            tmp_path / "video_audio_for_whisper.wav",
            "create_subtitles",
        )
    ]
    assert any(
        step_id == ChecklistStep.TIMING_WORD_HIGHLIGHTS
        and state == StepState.DONE
        and detail == "Matching complete"
        for step_id, state, detail in checklist_events
    )


def test_build_overlay_frame_segments_uses_source_frame_count_override(
    tmp_path: Path,
) -> None:
    worker = workers_module.Worker(
        task_type=workers_module.TaskType.GENERATE_SRT,
        video_path=tmp_path / "video.mp4",
        output_dir=tmp_path,
    )

    frame_segments, total_frames = worker._build_overlay_frame_segments(
        [
            OverlaySegment(
                start_seconds=0.0,
                end_seconds=0.2,
                text="hello",
                highlight_word_index=0,
            )
        ],
        duration_seconds=0.2,
        fps=24.0,
        total_frames_override=4,
    )

    assert total_frames == 4
    assert frame_segments == [("hello", 0, 4)]


def test_build_overlay_frame_segments_keeps_short_highlighted_word_visible(
    tmp_path: Path,
) -> None:
    worker = workers_module.Worker(
        task_type=workers_module.TaskType.GENERATE_SRT,
        video_path=tmp_path / "video.mp4",
        output_dir=tmp_path,
    )

    frame_segments, total_frames = worker._build_overlay_frame_segments(
        [
            OverlaySegment(
                start_seconds=0.0,
                end_seconds=0.50,
                text="first second",
                highlight_word_index=0,
            ),
            OverlaySegment(
                start_seconds=0.50,
                end_seconds=0.52,
                text="first second",
                highlight_word_index=1,
            ),
            OverlaySegment(
                start_seconds=0.52,
                end_seconds=0.72,
                text="next cue",
                highlight_word_index=0,
            ),
        ],
        duration_seconds=0.72,
        fps=24.0,
        total_frames_override=17,
    )

    assert total_frames == 17
    assert frame_segments == [
        ("first second", 0, 12),
        ("first second", 1, 1),
        ("next cue", 0, 4),
    ]
