from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import backend_server, project_store
from app.paths import get_projects_dir


def test_sse_stream_emits_result_payload(monkeypatch) -> None:
    async def fake_run_runner_job(
        job: backend_server.JobState,
        request: backend_server.JobRequest,  # noqa: ARG001 - test stub uses job only
    ) -> None:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        backend_server._enqueue_event(job, backend_server._build_event(job.job_id, "started"))
        backend_server._enqueue_event(
            job,
            backend_server._build_event(
                job.job_id,
                "result",
                payload={
                    "srt_path": r"C:\fake\output.srt",
                    "log_path": r"C:\fake\session.log",
                },
            ),
        )
        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        backend_server._enqueue_event(
            job,
            backend_server._build_event(job.job_id, "completed", status=job.status),
        )

    backend_server.JOBS.clear()
    monkeypatch.setattr(backend_server, "_run_runner_job", fake_run_runner_job)

    with TestClient(backend_server.app) as client:
        response = client.post(
            "/jobs",
            json={
                "kind": "create_subtitles",
                "input_path": r"C:\fake\input.mp4",
                "output_dir": r"C:\fake",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        job_id = payload["job_id"]

        events: list[dict[str, Any]] = []
        with client.stream("GET", f"/jobs/{job_id}/events") as stream:
            for line in stream.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:]
                elif line.startswith("data:"):
                    data = line[5:]
                else:
                    continue
                events.append(json.loads(data.strip()))
                if events[-1].get("type") == "completed":
                    break

        result_events = [event for event in events if event.get("type") == "result"]
        assert result_events, "Expected a result event in the SSE stream."
        result_payload = result_events[0].get("payload", {})
        assert result_payload.get("srt_path")
        assert result_payload.get("log_path")
        assert any(event.get("type") == "completed" for event in events)
        assert all(event.get("job_id") == job_id for event in events)


def _setup_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(project_store, "generate_thumbnail", lambda *args, **kwargs: None)
    monkeypatch.setattr(project_store, "get_media_duration_seconds", lambda *args, **kwargs: None)
    backend_server.JOBS.clear()


def test_project_first_export_resolves_project_artifacts(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    video_path = tmp_path / "source.mp4"
    video_path.write_text("video", encoding="utf-8")
    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]

    project_store.update_project(
        project_id,
        subtitles_srt_text="1\n00:00:00,000 --> 00:00:01,000\nHello\n",
        style={"subtitle_mode": "static", "subtitle_style": {"appearance": {"font_size": 34}}},
    )
    project_dir = get_projects_dir() / project_id
    (project_dir / "word_timings.json").write_text("{}", encoding="utf-8")

    request = backend_server.JobRequest(
        kind="create_video_with_subtitles",
        project_id=project_id,
    )
    backend_server._resolve_export_request_from_project(request)

    assert request.input_path == str(video_path)
    assert request.srt_path == str(project_dir / "subtitles.srt")
    assert request.word_timings_path == str(project_dir / "word_timings.json")
    assert request.style_path == str(project_dir / "style.json")
    assert request.output_dir == str(video_path.parent)


def test_project_first_export_requires_subtitles(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    video_path = tmp_path / "source.mp4"
    video_path.write_text("video", encoding="utf-8")
    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]

    request = backend_server.JobRequest(
        kind="create_video_with_subtitles",
        project_id=project_id,
    )
    with pytest.raises(HTTPException) as exc_info:
        backend_server._resolve_export_request_from_project(request)
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "project_subtitles_missing"
