from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import backend_server, project_store


def _setup_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(project_store, "generate_thumbnail", lambda *args, **kwargs: None)
    monkeypatch.setattr(project_store, "get_media_duration_seconds", lambda *args, **kwargs: None)


def test_projects_endpoints(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "input.mp4"
    video_path.write_text("video", encoding="utf-8")

    with TestClient(backend_server.app) as client:
        response = client.post("/projects", json={"video_path": str(video_path)})
        assert response.status_code == 200
        project = response.json()
        project_id = project["project_id"]

        response = client.get("/projects")
        assert response.status_code == 200
        summaries = response.json()
        assert any(item["project_id"] == project_id for item in summaries)

        response = client.get(f"/projects/{project_id}")
        assert response.status_code == 200

        response = client.put(
            f"/projects/{project_id}",
            json={"subtitles_srt_text": "1\n00:00:00,000 --> 00:00:01,000\nHi\n"},
        )
        assert response.status_code == 200

        new_video = tmp_path / "input2.mp4"
        new_video.write_text("video2", encoding="utf-8")
        response = client.post(
            f"/projects/{project_id}/relink",
            json={"video_path": str(new_video)},
        )
        assert response.status_code == 200
