from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import backend_server, project_store
from app.paths import get_projects_dir


def _setup_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(project_store, "generate_thumbnail", lambda *args, **kwargs: None)
    monkeypatch.setattr(project_store, "get_media_duration_seconds", lambda *args, **kwargs: None)


def test_job_result_updates_project(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "video.mp4"
    video_path.write_text("video", encoding="utf-8")

    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]

    srt_path = tmp_path / "out.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    word_timings_path = tmp_path / "out.word_timings.json"
    word_timings_path.write_text("{}", encoding="utf-8")

    request = backend_server.JobRequest(
        kind="create_subtitles",
        input_path=str(video_path),
        output_dir=str(tmp_path),
        project_id=project_id,
    )
    backend_server._maybe_update_project_from_runner_event(
        request,
        "result",
        {"payload": {"srt_path": str(srt_path), "word_timings_path": str(word_timings_path)}},
    )

    project_dir = get_projects_dir() / project_id
    assert (project_dir / "subtitles.srt").exists()
    assert (project_dir / "word_timings.json").exists()

    output_path = tmp_path / "out.mp4"
    output_path.write_text("video", encoding="utf-8")
    export_request = backend_server.JobRequest(
        kind="create_video_with_subtitles",
        input_path=str(video_path),
        output_dir=str(tmp_path),
        srt_path=str(srt_path),
        project_id=project_id,
    )
    backend_server._maybe_update_project_from_runner_event(
        export_request,
        "result",
        {"payload": {"output_path": str(output_path)}},
    )

    manifest = project_store.get_project(project_id)
    assert manifest["latest_export"]["output_video_path"] == str(output_path)


def test_runner_command_strips_ui_selection_options() -> None:
    request = backend_server.JobRequest(
        kind="create_video_with_subtitles",
        input_path="in.mp4",
        output_dir="out",
        srt_path="subs.srt",
        word_timings_path="subs.word_timings.json",
        style_path="style.json",
        options={
            "subtitle_mode": "word_highlight",
            "highlight_color": "#FFD400",
            "selected_cue_id": "cue-3",
            "selectionOutline": True,
            "ui_selection": {"cue": "cue-3"},
        },
    )

    command = backend_server._build_runner_command(request)
    assert "--word-timings-path" in command
    assert command[command.index("--word-timings-path") + 1] == "subs.word_timings.json"
    assert "--style-path" in command
    assert command[command.index("--style-path") + 1] == "style.json"
    assert "--options-json" in command
    options_index = command.index("--options-json")
    options_payload = json.loads(command[options_index + 1])

    assert options_payload.get("subtitle_mode") == "word_highlight"
    assert options_payload.get("highlight_color") == "#FFD400"
    assert "selected_cue_id" not in options_payload
    assert "selectionOutline" not in options_payload
    assert "ui_selection" not in options_payload


def test_runner_command_frozen_requires_sibling_runner_executable(
    tmp_path: Path, monkeypatch
) -> None:
    frozen_backend_exe = tmp_path / "CueBackend.exe"
    frozen_backend_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(backend_server.sys, "frozen", True, raising=False)
    monkeypatch.setattr(backend_server.sys, "executable", str(frozen_backend_exe))

    request = backend_server.JobRequest(
        kind="create_subtitles",
        input_path="in.mp4",
        output_dir="out",
    )

    with pytest.raises(RuntimeError, match="Missing packaged runner executable"):
        backend_server._build_runner_command(request)
