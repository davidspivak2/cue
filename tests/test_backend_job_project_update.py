from __future__ import annotations

from pathlib import Path

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
