from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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
        assert isinstance(response.json().get("style"), dict)

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

        style_payload = {
            "subtitle_mode": "static",
            "subtitle_style": {"preset": "Default", "appearance": {"font_size": 32}},
        }
        response = client.put(
            f"/projects/{project_id}",
            json={"style": style_payload},
        )
        assert response.status_code == 200
        assert response.json().get("style") == style_payload

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


def test_projects_include_active_task_snapshot(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "active.mp4"
    video_path.write_text("video", encoding="utf-8")

    with TestClient(backend_server.app) as client:
        create_response = client.post("/projects", json={"video_path": str(video_path)})
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]

        running_job = backend_server.JobState(
            job_id="job-active-1",
            status="running",
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            kind="create_subtitles",
            project_id=project_id,
            cancel_event=asyncio.Event(),
        )
        backend_server.JOBS[running_job.job_id] = running_job
        backend_server._enqueue_event(
            running_job,
            backend_server._build_event(
                running_job.job_id,
                "started",
                heading="Creating subtitles",
            ),
        )
        backend_server._enqueue_event(
            running_job,
            backend_server._build_event(
                running_job.job_id,
                "checklist",
                step_id="load_model",
                state="start",
                reason_text="Loading weights",
            ),
        )
        backend_server._enqueue_event(
            running_job,
            backend_server._build_event(
                running_job.job_id,
                "progress",
                step_id="load_model",
                pct=12,
                message="Loading AI model",
            ),
        )

        list_response = client.get("/projects")
        assert list_response.status_code == 200
        summary = next(
            item for item in list_response.json() if item["project_id"] == project_id
        )
        active_task = summary.get("active_task")
        assert isinstance(active_task, dict)
        assert active_task.get("job_id") == running_job.job_id
        assert active_task.get("kind") == "create_subtitles"
        assert active_task.get("heading") == "Creating subtitles"
        assert active_task.get("pct") == 12
        checklist = active_task.get("checklist") or []
        assert checklist
        assert checklist[0].get("id") == "load_model"
        assert checklist[0].get("state") == "active"
        assert checklist[0].get("detail") == "Loading AI model"

        detail_response = client.get(f"/projects/{project_id}")
        assert detail_response.status_code == 200
        detail_active_task = detail_response.json().get("active_task")
        assert isinstance(detail_active_task, dict)
        assert detail_active_task.get("job_id") == running_job.job_id


def test_create_job_accepts_second_subtitles_job_as_queued_when_first_running(
    tmp_path: Path, monkeypatch
) -> None:
    """Second create_subtitles for same project is accepted with 201 and status queued."""
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "conflict.mp4"
    video_path.write_text("video", encoding="utf-8")

    with TestClient(backend_server.app) as client:
        create_response = client.post("/projects", json={"video_path": str(video_path)})
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]

        running_job = backend_server.JobState(
            job_id="job-conflict-1",
            status="running",
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            kind="create_subtitles",
            project_id=project_id,
            cancel_event=asyncio.Event(),
        )
        backend_server.JOBS[running_job.job_id] = running_job

        second_response = client.post(
            "/jobs",
            json={
                "kind": "create_subtitles",
                "input_path": str(video_path),
                "output_dir": str(tmp_path),
                "project_id": project_id,
            },
        )
        assert second_response.status_code == 201
        payload = second_response.json()
        assert payload.get("job_id")
        assert payload.get("status") == "queued"
        second_job_id = payload["job_id"]
        assert second_job_id != running_job.job_id
        assert backend_server.JOBS[second_job_id].status == "queued"
        assert backend_server.JOBS[second_job_id].project_id == project_id


def test_projects_include_task_notice_for_terminal_error(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "notice.mp4"
    video_path.write_text("video", encoding="utf-8")

    with TestClient(backend_server.app) as client:
        create_response = client.post("/projects", json={"video_path": str(video_path)})
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]

        job = backend_server.JobState(
            job_id="job-notice-1",
            status="running",
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            kind="create_video_with_subtitles",
            project_id=project_id,
            cancel_event=asyncio.Event(),
        )
        backend_server.JOBS[job.job_id] = job
        job.status = "error"
        job.finished_at = datetime.now(timezone.utc)
        backend_server._enqueue_event(
            job,
            backend_server._build_event(
                job.job_id,
                "error",
                status="error",
                message="Export failed in test",
            ),
        )

        list_response = client.get("/projects")
        assert list_response.status_code == 200
        summary = next(
            item for item in list_response.json() if item["project_id"] == project_id
        )
        notice = summary.get("task_notice")
        assert isinstance(notice, dict)
        assert notice.get("job_id") == job.job_id
        assert notice.get("status") == "error"
        assert notice.get("message") == "Export failed in test"


def test_expired_task_notice_is_not_returned(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)

    video_path = tmp_path / "notice-expired.mp4"
    video_path.write_text("video", encoding="utf-8")

    with TestClient(backend_server.app) as client:
        create_response = client.post("/projects", json={"video_path": str(video_path)})
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]

        expired_at = datetime.now(timezone.utc) - timedelta(
            seconds=backend_server.TASK_NOTICE_TTL_SECONDS + 5
        )
        backend_server.PROJECT_TASK_NOTICES[project_id] = {
            "notice_id": "expired-notice-1",
            "project_id": project_id,
            "job_id": "job-expired",
            "kind": "create_subtitles",
            "status": "error",
            "message": "old notice",
            "created_at": expired_at.isoformat(),
            "finished_at": expired_at.isoformat(),
        }

        list_response = client.get("/projects")
        assert list_response.status_code == 200
        summary = next(
            item for item in list_response.json() if item["project_id"] == project_id
        )
        assert "task_notice" not in summary
        assert project_id not in backend_server.PROJECT_TASK_NOTICES
