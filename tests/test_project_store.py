from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from app import project_store
from app.paths import get_projects_dir


def _setup_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(project_store, "generate_thumbnail", lambda *args, **kwargs: None)
    monkeypatch.setattr(project_store, "get_media_duration_seconds", lambda *args, **kwargs: None)


def test_create_list_relink_update(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "video.mp4"
    video_path.write_text("video", encoding="utf-8")

    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]

    projects = project_store.list_projects()
    assert len(projects) == 1
    assert projects[0].project_id == project_id

    detail = project_store.get_project(project_id)
    assert detail["video"]["path"] == str(video_path)

    project_store.update_project(
        project_id,
        subtitles_srt_text="1\n00:00:00,000 --> 00:00:01,000\nHello\n",
        style={"preset": "Default"},
    )
    subtitles_path = get_projects_dir() / project_id / "subtitles.srt"
    assert subtitles_path.exists()

    new_video_path = tmp_path / "video2.mp4"
    new_video_path.write_text("video2", encoding="utf-8")
    relinked = project_store.relink_project(project_id, str(new_video_path))
    assert relinked["video_path"] == str(new_video_path)

    new_video_path.unlink()
    projects = project_store.list_projects()
    assert projects[0].missing_video is True
    assert projects[0].status == "missing_file"


def test_delete_project(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "video.mp4"
    video_path.write_text("video", encoding="utf-8")

    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]
    project_dir = get_projects_dir() / project_id
    assert project_dir.exists()

    project_store.delete_project(project_id)

    assert not project_dir.exists()
    assert project_store.list_projects() == []

    try:
        project_store.get_project(project_id)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "project_not_found"
    else:
        raise AssertionError("Expected project_not_found after delete")
