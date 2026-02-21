from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import backend_server, project_store
from app.paths import get_projects_dir
from app.srt_utils import compute_srt_sha256
from app.word_timing_schema import (
    CueWordTimings,
    SCHEMA_VERSION,
    WordSpan,
    WordTimingDocument,
    save_word_timings_json,
)


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
    monkeypatch.setattr(backend_server, "_run_worker_job_maybe_inprocess", fake_run_runner_job)

    with TestClient(backend_server.app) as client:
        response = client.post(
            "/jobs",
            json={
                "kind": "create_subtitles",
                "input_path": r"C:\fake\input.mp4",
                "output_dir": r"C:\fake",
            },
        )

        assert response.status_code == 201
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


def test_create_subtitles_job_updates_project_and_subtitles_file(
    tmp_path: Path, monkeypatch
) -> None:
    """Critical path: POST create_subtitles with project_id, mock result, then project has SRT."""
    _setup_env(tmp_path, monkeypatch)
    video_path = tmp_path / "video.mp4"
    video_path.write_text("video", encoding="utf-8")
    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]

    srt_path = tmp_path / "out.srt"
    srt_content = "1\n00:00:00,000 --> 00:00:02,000\nHello world\n"
    srt_path.write_text(srt_content, encoding="utf-8")
    word_timings_path = tmp_path / "out.word_timings.json"
    word_timings_path.write_text("{}", encoding="utf-8")

    async def fake_run_runner_job(
        job: backend_server.JobState,
        request: backend_server.JobRequest,
    ) -> None:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        backend_server._enqueue_event(job, backend_server._build_event(job.job_id, "started"))
        result_payload = {
            "srt_path": str(srt_path),
            "word_timings_path": str(word_timings_path),
            "log_path": str(tmp_path / "session.log"),
        }
        backend_server._enqueue_event(
            job,
            backend_server._build_event(job.job_id, "result", payload=result_payload),
        )
        backend_server._maybe_update_project_from_runner_event(
            request, "result", {"payload": result_payload}
        )
        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        backend_server._enqueue_event(
            job,
            backend_server._build_event(job.job_id, "completed", status=job.status),
        )

    monkeypatch.setattr(backend_server, "_run_worker_job_maybe_inprocess", fake_run_runner_job)

    with TestClient(backend_server.app) as client:
        response = client.post(
            "/jobs",
            json={
                "kind": "create_subtitles",
                "input_path": str(video_path),
                "output_dir": str(tmp_path),
                "project_id": project_id,
            },
        )
        assert response.status_code == 201
        job_id = response.json()["job_id"]

        # Allow queue worker to run and enqueue events (TestClient runs app in thread)
        time.sleep(0.3)

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

        assert any(e.get("type") == "completed" for e in events)

        sub_response = client.get(f"/projects/{project_id}/subtitles")
        assert sub_response.status_code == 200
        assert sub_response.json()["subtitles_srt_text"].strip() == srt_content.strip()

        project_dir = get_projects_dir() / project_id
        assert (project_dir / "subtitles.srt").exists()
        assert (project_dir / "subtitles.srt").read_text(encoding="utf-8").strip() == srt_content.strip()


def test_project_word_timings_endpoint_returns_document(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    video_path = tmp_path / "video.mp4"
    video_path.write_text("video", encoding="utf-8")
    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]

    srt_text = "1\n00:00:00,000 --> 00:00:02,000\nhello world\n"
    project_store.update_project(project_id, subtitles_srt_text=srt_text)

    project_dir = get_projects_dir() / project_id
    subtitles_path = project_dir / "subtitles.srt"
    word_timings_path = project_dir / "word_timings.json"
    doc = WordTimingDocument(
        schema_version=SCHEMA_VERSION,
        created_utc=datetime.now(timezone.utc).isoformat(),
        language="en",
        srt_sha256=compute_srt_sha256(subtitles_path),
        cues=[
            CueWordTimings(
                cue_index=1,
                cue_start=0.0,
                cue_end=2.0,
                cue_text="hello world",
                words=[
                    WordSpan(text="hello", start=0.2, end=0.7, confidence=0.9),
                    WordSpan(text="world", start=0.8, end=1.4, confidence=0.92),
                ],
            )
        ],
    )
    save_word_timings_json(word_timings_path, doc)

    with TestClient(backend_server.app) as client:
        response = client.get(f"/projects/{project_id}/word-timings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["stale"] is False
    assert payload["reason"] is None
    assert payload["document"]["schema_version"] == SCHEMA_VERSION
    assert len(payload["document"]["cues"]) == 1
    assert payload["document"]["cues"][0]["cue_index"] == 1
    assert payload["document"]["cues"][0]["words"][0]["text"] == "hello"


def test_project_word_timings_endpoint_handles_missing_file(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    video_path = tmp_path / "video.mp4"
    video_path.write_text("video", encoding="utf-8")
    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]
    project_store.update_project(
        project_id,
        subtitles_srt_text="1\n00:00:00,000 --> 00:00:01,000\nHello\n",
    )

    with TestClient(backend_server.app) as client:
        response = client.get(f"/projects/{project_id}/word-timings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["stale"] is None
    assert payload["reason"] == "word_timings_not_found"
    assert payload["document"] is None


def test_project_word_timings_endpoint_marks_stale(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    video_path = tmp_path / "video.mp4"
    video_path.write_text("video", encoding="utf-8")
    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]

    initial_srt = "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    project_store.update_project(project_id, subtitles_srt_text=initial_srt)

    project_dir = get_projects_dir() / project_id
    subtitles_path = project_dir / "subtitles.srt"
    word_timings_path = project_dir / "word_timings.json"
    doc = WordTimingDocument(
        schema_version=SCHEMA_VERSION,
        created_utc=datetime.now(timezone.utc).isoformat(),
        language="en",
        srt_sha256=compute_srt_sha256(subtitles_path),
        cues=[
            CueWordTimings(
                cue_index=1,
                cue_start=0.0,
                cue_end=1.0,
                cue_text="Hello",
                words=[WordSpan(text="Hello", start=0.1, end=0.8, confidence=0.9)],
            )
        ],
    )
    save_word_timings_json(word_timings_path, doc)
    project_store.update_project(
        project_id,
        subtitles_srt_text="1\n00:00:00,000 --> 00:00:01,000\nHello there\n",
    )

    with TestClient(backend_server.app) as client:
        response = client.get(f"/projects/{project_id}/word-timings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["stale"] is True
    assert payload["reason"] is None
    assert payload["document"] is not None


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


def test_preview_overlay_returns_existing_cached_png(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("PySide6")
    _setup_env(tmp_path, monkeypatch)

    payload = {
        "width": 640,
        "height": 360,
        "subtitle_text": "Preview parity check",
        "highlight_word_index": 0,
        "subtitle_style": {},
        "subtitle_mode": "word_highlight",
        "highlight_color": "#FFD400",
        "highlight_opacity": 1.0,
    }

    with TestClient(backend_server.app) as client:
        first = client.post("/preview-overlay", json=payload)
        assert first.status_code == 200
        first_path = first.json().get("overlay_path")
        assert isinstance(first_path, str) and first_path
        first_file = Path(first_path)
        assert first_file.exists()
        assert first_file.suffix.lower() == ".png"

        second = client.post("/preview-overlay", json=payload)
        assert second.status_code == 200
        second_path = second.json().get("overlay_path")
        assert second_path == first_path


def test_enqueue_event_bounds_queue_without_dropping_terminal() -> None:
    job = backend_server.JobState(
        job_id="job-queue-limit",
        status="running",
        created_at=datetime.now(timezone.utc),
    )
    original_limit = backend_server.MAX_JOB_EVENT_QUEUE_SIZE
    backend_server.MAX_JOB_EVENT_QUEUE_SIZE = 5
    try:
        for idx in range(8):
            backend_server._enqueue_event(
                job,
                backend_server._build_event(job.job_id, "progress", pct=idx, message=f"p{idx}"),
            )
        assert job.event_queue.qsize() <= 5

        backend_server._enqueue_event(
            job,
            backend_server._build_event(job.job_id, "completed", status="completed"),
        )
        buffered: list[dict[str, Any]] = []
        while not job.event_queue.empty():
            buffered.append(job.event_queue.get_nowait())
        assert any(event.get("type") == "completed" for event in buffered)
    finally:
        backend_server.MAX_JOB_EVENT_QUEUE_SIZE = original_limit
