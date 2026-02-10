from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import backend_server, project_store


def _setup_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(project_store, "generate_thumbnail", lambda *args, **kwargs: None)
    monkeypatch.setattr(project_store, "get_media_duration_seconds", lambda *args, **kwargs: None)
    backend_server.JOBS.clear()


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

        response = client.get(f"/projects/{project_id}/subtitles")
        assert response.status_code == 404
        assert response.json().get("detail") == "subtitles_not_found"

        subtitles_text = "1\n00:00:00,000 --> 00:00:01,000\nHi\n"
        response = client.put(
            f"/projects/{project_id}",
            json={"subtitles_srt_text": subtitles_text},
        )
        assert response.status_code == 200

        response = client.get(f"/projects/{project_id}/subtitles")
        assert response.status_code == 200
        assert response.json().get("subtitles_srt_text") == subtitles_text

        new_video = tmp_path / "input2.mp4"
        new_video.write_text("video2", encoding="utf-8")
        response = client.post(
            f"/projects/{project_id}/relink",
            json={"video_path": str(new_video)},
        )
        assert response.status_code == 200


def test_delete_project_endpoint(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "input.mp4"
    video_path.write_text("video", encoding="utf-8")

    with TestClient(backend_server.app) as client:
        create_response = client.post("/projects", json={"video_path": str(video_path)})
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]

        delete_response = client.delete(f"/projects/{project_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["ok"] is True
        assert delete_response.json()["project_id"] == project_id

        list_response = client.get("/projects")
        assert list_response.status_code == 200
        assert all(item["project_id"] != project_id for item in list_response.json())

        get_response = client.get(f"/projects/{project_id}")
        assert get_response.status_code == 404
        assert get_response.json().get("detail") == "project_not_found"

        missing_delete_response = client.delete(f"/projects/{project_id}")
        assert missing_delete_response.status_code == 404
        assert missing_delete_response.json().get("detail") == "project_not_found"


def test_delete_project_cancels_running_job(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(backend_server, "PROJECT_DELETE_CANCEL_TIMEOUT_SECONDS", 0.01)

    video_path = tmp_path / "input.mp4"
    video_path.write_text("video", encoding="utf-8")

    with TestClient(backend_server.app) as client:
        create_response = client.post("/projects", json={"video_path": str(video_path)})
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]

        job = backend_server.JobState(
            job_id="job-delete-1",
            status="running",
            created_at=datetime.now(timezone.utc),
            project_id=project_id,
            cancel_event=asyncio.Event(),
        )
        backend_server.JOBS[job.job_id] = job

        delete_response = client.delete(f"/projects/{project_id}")
        assert delete_response.status_code == 200
        payload = delete_response.json()
        assert payload["ok"] is True
        assert job.job_id in payload.get("cancelled_job_ids", [])
        assert job.cancel_event.is_set() is True

    backend_server.JOBS.clear()
