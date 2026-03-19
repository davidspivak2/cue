from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app import project_store
from app.paths import get_config_path, get_projects_dir


def _setup_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(project_store, "generate_thumbnail", lambda *args, **kwargs: None)
    monkeypatch.setattr(project_store, "get_media_duration", lambda *args, **kwargs: None)


def _word_highlight_style() -> dict[str, object]:
    return {
        "subtitle_mode": "word_highlight",
        "subtitle_style": {
            "preset": "Default",
            "highlight_color": "#00FF99",
            "appearance": {
                "font_size": 61,
                "background_mode": "word",
                "subtitle_mode": "word_highlight",
                "highlight_color": "#00FF99",
            },
        },
    }


def test_create_project_rejects_unsupported_extension(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    bad_path = tmp_path / "song.mp3"
    bad_path.write_bytes(b"x")
    with pytest.raises(HTTPException) as exc_info:
        project_store.create_project(str(bad_path))
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "unsupported_video_type"


def test_relink_project_rejects_unsupported_extension(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    good_path = tmp_path / "video.mp4"
    good_path.write_text("video", encoding="utf-8")
    summary = project_store.create_project(str(good_path))
    project_id = summary["project_id"]
    bad_path = tmp_path / "song.mp3"
    bad_path.write_bytes(b"x")
    with pytest.raises(HTTPException) as exc_info:
        project_store.relink_project(project_id, str(bad_path))
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "unsupported_video_type"


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


def test_store_bootstrap_ignores_parent_projects_json(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    legacy_project_id = "legacy-project"
    legacy_store_path = get_projects_dir().parent / "projects.json"
    legacy_store_path.write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "project_id": legacy_project_id,
                        "video_path": str(tmp_path / "legacy.mp4"),
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert project_store.list_projects() == []

    index_path = get_projects_dir() / project_store.INDEX_FILENAME
    assert json.loads(index_path.read_text(encoding="utf-8")) == {"projects": []}
    assert not (get_projects_dir() / legacy_project_id).exists()

    video_path = tmp_path / "current.mp4"
    video_path.write_text("video", encoding="utf-8")

    summary = project_store.create_project(str(video_path))
    assert summary["project_id"] != legacy_project_id

    projects = project_store.list_projects()
    assert [project.project_id for project in projects] == [summary["project_id"]]
    assert not (get_projects_dir() / legacy_project_id).exists()


def test_project_style_is_normalized_on_write_and_read(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "video.mp4"
    video_path.write_text("video", encoding="utf-8")

    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]

    project_store.update_project(
        project_id,
        style={
            "subtitle_mode": "static",
            "subtitle_style": {
                "preset": "Default",
                "appearance": {
                    "font_style": "bold",
                    "text_align": "left",
                    "line_spacing": 1.5,
                },
            },
        },
    )

    detail = project_store.get_project(project_id)
    appearance = detail["style"]["subtitle_style"]["appearance"]

    assert detail["style"]["subtitle_mode"] == "static"
    assert appearance["font_weight"] == 700
    assert appearance["text_align"] == "left"
    assert appearance["line_spacing"] == 1.5


@pytest.mark.parametrize("omitted_style", [None, {}])
def test_create_project_uses_built_in_default_style_instead_of_saved_settings(
    tmp_path: Path, monkeypatch, omitted_style: dict[str, object] | None
) -> None:
    _setup_env(tmp_path, monkeypatch)

    get_config_path().write_text(
        json.dumps(
            {
                "subtitle_mode": "word_highlight",
                "subtitle_style": {
                    "preset": "Default",
                    "highlight_color": "#00FF99",
                    "highlight_opacity": 0.35,
                    "appearance": {
                        "font_size": 61,
                        "background_mode": "word",
                        "subtitle_mode": "word_highlight",
                        "highlight_color": "#00FF99",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    video_path = tmp_path / "seeded.mp4"
    video_path.write_text("video", encoding="utf-8")

    summary = project_store.create_project(str(video_path), style=omitted_style)
    detail = project_store.get_project(summary["project_id"])
    appearance = detail["style"]["subtitle_style"]["appearance"]

    assert detail["style"]["subtitle_mode"] == "static"
    assert detail["style"]["subtitle_style"]["preset"] == "Default"
    assert detail["style"]["subtitle_style"]["highlight_color"] == "#FFD400"
    assert detail["style"]["subtitle_style"]["highlight_opacity"] == 1.0
    assert appearance["font_size"] == 44
    assert appearance["background_mode"] == "line"
    assert appearance["outline_enabled"] is False
    assert appearance["subtitle_mode"] == "static"


@pytest.mark.parametrize("omitted_style", [None, {}])
def test_create_project_does_not_clear_existing_style_when_style_is_omitted(
    tmp_path: Path, monkeypatch, omitted_style: dict[str, object] | None
) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "same-video.mp4"
    video_path.write_text("video", encoding="utf-8")

    summary = project_store.create_project(str(video_path), style=_word_highlight_style())

    project_store.create_project(str(video_path), style=omitted_style)

    detail = project_store.get_project(summary["project_id"])
    appearance = detail["style"]["subtitle_style"]["appearance"]

    assert detail["style"]["subtitle_mode"] == "word_highlight"
    assert appearance["font_size"] == 61
    assert appearance["background_mode"] == "word"


def test_delete_then_recreate_same_video_starts_from_fresh_default_style(
    tmp_path: Path, monkeypatch
) -> None:
    _setup_env(tmp_path, monkeypatch)

    get_config_path().write_text(
        json.dumps(
            {
                "subtitle_mode": "static",
                "subtitle_style": {
                    "preset": "Custom",
                    "highlight_color": "#00FF99",
                    "highlight_opacity": 0.35,
                    "appearance": {
                        "font_size": 61,
                        "background_mode": "word",
                        "outline_enabled": True,
                        "outline_width": 2.0,
                        "subtitle_mode": "word_highlight",
                        "highlight_color": "#00FF99",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    video_path = tmp_path / "same-video.mp4"
    video_path.write_text("video", encoding="utf-8")

    first_summary = project_store.create_project(str(video_path), style=_word_highlight_style())
    project_store.delete_project(first_summary["project_id"])

    recreated_summary = project_store.create_project(str(video_path))
    recreated_detail = project_store.get_project(recreated_summary["project_id"])
    recreated_appearance = recreated_detail["style"]["subtitle_style"]["appearance"]

    assert recreated_summary["project_id"] != first_summary["project_id"]
    assert recreated_detail["style"]["subtitle_mode"] == "static"
    assert recreated_appearance["font_size"] == 44
    assert recreated_appearance["background_mode"] == "line"
    assert recreated_appearance["outline_enabled"] is False
