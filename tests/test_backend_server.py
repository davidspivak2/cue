from __future__ import annotations

import asyncio
import json
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from asgi_lifespan import LifespanManager
from fastapi import HTTPException
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app import backend_server, project_store
from app.paths import get_diagnostics_dir, get_logs_dir, get_projects_dir
from app.srt_utils import compute_srt_sha256
from app.word_timing_schema import (
    CueWordTimings,
    SCHEMA_VERSION,
    WordSpan,
    WordTimingDocument,
    save_word_timings_json,
)


@pytest.mark.order(3)
async def test_sse_stream_emits_result_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    worker_done: asyncio.Event = asyncio.Event()

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
        worker_done.set()

    backend_server.JOBS.clear()
    monkeypatch.setattr(backend_server, "_run_worker_job_maybe_inprocess", fake_run_runner_job)

    async with LifespanManager(backend_server.app):
        async with AsyncClient(
            transport=ASGITransport(app=backend_server.app),
            base_url="http://test",
        ) as client:
            response = await client.post(
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
            job = backend_server.JOBS.get(job_id)
            assert job is not None
            request = backend_server.JobRequest(
                kind="create_subtitles",
                input_path=r"C:\fake\input.mp4",
                output_dir=r"C:\fake",
            )

            async def inject_completion() -> None:
                await asyncio.sleep(0.05)
                await fake_run_runner_job(job, request)

            asyncio.create_task(inject_completion())
            await asyncio.wait_for(worker_done.wait(), timeout=5.0)

            events: list[dict[str, Any]] = []
            async with client.stream("GET", f"/jobs/{job_id}/events") as stream:
                async for line in stream.aiter_lines():
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


@pytest.mark.order(1)
async def test_create_subtitles_emits_extract_audio_step_before_worker_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker_done: asyncio.Event = asyncio.Event()

    async def fake_run_runner_job(
        job: backend_server.JobState,
        request: backend_server.JobRequest,  # noqa: ARG001 - test stub uses job only
    ) -> None:
        await asyncio.sleep(0.01)
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
        worker_done.set()

    backend_server.JOBS.clear()
    monkeypatch.setattr(backend_server, "_run_worker_job_maybe_inprocess", fake_run_runner_job)

    async with LifespanManager(backend_server.app):
        async with AsyncClient(
            transport=ASGITransport(app=backend_server.app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/jobs",
                json={
                    "kind": "create_subtitles",
                    "input_path": r"C:\fake\input.mp4",
                    "output_dir": r"C:\fake",
                },
            )
            assert response.status_code == 201
            job_id = response.json()["job_id"]

            for _ in range(50):
                await asyncio.sleep(0.02)
                if worker_done.is_set():
                    break
            else:
                await asyncio.wait_for(worker_done.wait(), timeout=4.0)

            events: list[dict[str, Any]] = []
            async with client.stream("GET", f"/jobs/{job_id}/events") as stream:
                async for line in stream.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[6:]
                    elif line.startswith("data:"):
                        data = line[5:]
                    else:
                        continue
                    event = json.loads(data.strip())
                    events.append(event)
                    if event.get("type") == "completed":
                        break

    first_started = next(event for event in events if event.get("type") == "started")
    assert first_started.get("message") == "Preparing audio"

    checklist_index = next(
        index
        for index, event in enumerate(events)
        if event.get("type") == "checklist"
        and event.get("step_id") == "extract_audio"
        and event.get("state") == "start"
    )
    progress_index = next(
        index
        for index, event in enumerate(events)
        if event.get("type") == "progress"
        and event.get("step_id") == "PREPARE_AUDIO"
        and event.get("step_progress") == 0.0
    )
    result_index = next(
        index for index, event in enumerate(events) if event.get("type") == "result"
    )
    assert checklist_index < result_index
    assert progress_index < result_index


@pytest.mark.order(2)
async def test_create_subtitles_job_updates_project_and_subtitles_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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

    worker_done: asyncio.Event = asyncio.Event()

    async def fake_run_runner_job(
        job: backend_server.JobState,
        request: backend_server.JobRequest,
    ) -> None:
        try:
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
        finally:
            worker_done.set()

    monkeypatch.setattr(backend_server, "_run_worker_job_maybe_inprocess", fake_run_runner_job)

    async with LifespanManager(backend_server.app):
        async with AsyncClient(
            transport=ASGITransport(app=backend_server.app),
            base_url="http://test",
        ) as client:
            response = await client.post(
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
            job = backend_server.JOBS.get(job_id)
            assert job is not None
            request = backend_server.JobRequest(
                kind="create_subtitles",
                input_path=str(video_path),
                output_dir=str(tmp_path),
                project_id=project_id,
            )

            async def inject_completion() -> None:
                await asyncio.sleep(0.05)
                await fake_run_runner_job(job, request)

            asyncio.create_task(inject_completion())
            await asyncio.wait_for(worker_done.wait(), timeout=5.0)

            events: list[dict[str, Any]] = []
            async with client.stream("GET", f"/jobs/{job_id}/events") as stream:
                async for line in stream.aiter_lines():
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

            sub_response = await client.get(f"/projects/{project_id}/subtitles")
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
    monkeypatch.setattr(project_store, "get_media_duration", lambda *args, **kwargs: None)
    backend_server.JOBS.clear()


def test_archive_exit_bundle_writes_zip_in_video_folder(tmp_path: Path, monkeypatch) -> None:
    _setup_env(tmp_path, monkeypatch)
    settings = backend_server._read_settings_file()
    settings["diagnostics"]["archive_on_exit"] = True
    backend_server._write_settings_file(settings)

    video_path = tmp_path / "sample.mp4"
    video_path.write_text("video", encoding="utf-8")
    summary = project_store.create_project(str(video_path))
    project_id = summary["project_id"]
    project_dir = get_projects_dir() / project_id
    (project_dir / "subtitles.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
        encoding="utf-8",
    )
    (project_dir / "word_timings.json").write_text("{}", encoding="utf-8")

    (tmp_path / "sample_subtitled.srt").write_text("srt", encoding="utf-8")
    (tmp_path / "diag_create_subtitles_01.json").write_text("{}", encoding="utf-8")
    (get_logs_dir() / "session.log").write_text("log", encoding="utf-8")
    (get_diagnostics_dir() / "diag_create_subtitles_02.json").write_text("{}", encoding="utf-8")
    active_trace = get_logs_dir() / "job_trace_active.jsonl"
    active_trace.write_text('{"type":"progress"}\n', encoding="utf-8")
    stale_log = get_logs_dir() / "stale.log"
    stale_log.write_text("old", encoding="utf-8")
    stale_mtime = backend_server.BACKEND_SESSION_STARTED_AT - 60.0
    os.utime(stale_log, (stale_mtime, stale_mtime))
    stale_trace = get_logs_dir() / "job_trace_stale.jsonl"
    stale_trace.write_text('{"type":"progress"}\n', encoding="utf-8")
    os.utime(stale_trace, (stale_mtime, stale_mtime))

    archives = backend_server._archive_exit_bundles()
    assert len(archives) == 1
    archive_path = Path(archives[0])
    assert archive_path.parent == video_path.parent
    assert archive_path.exists()
    assert archive_path.name.startswith("cue_log_bundle_")

    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
    assert "logs/session.log" in names
    assert "logs/stale.log" not in names
    assert "job_traces/job_trace_active.jsonl" in names
    assert "job_traces/job_trace_stale.jsonl" not in names
    assert "diagnostics/diag_create_subtitles_02.json" in names
    assert "outputs/sample_subtitled.srt" in names
    assert "outputs/diag_create_subtitles_01.json" in names
    assert "project/subtitles.srt" in names
    assert "project/word_timings.json" in names


def test_archive_exit_bundle_endpoint_returns_created_archives(
    tmp_path: Path, monkeypatch
) -> None:
    _setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(backend_server, "_exit_archive_created_this_session", False)
    settings = backend_server._read_settings_file()
    settings["diagnostics"]["archive_on_exit"] = True
    backend_server._write_settings_file(settings)

    older_video_path = tmp_path / "older.mp4"
    older_video_path.write_text("video", encoding="utf-8")
    project_store.create_project(str(older_video_path))

    video_path = tmp_path / "sample2.mp4"
    video_path.write_text("video", encoding="utf-8")
    latest_summary = project_store.create_project(str(video_path))
    project_store.update_project(
        latest_summary["project_id"],
        subtitles_srt_text="1\n00:00:00,000 --> 00:00:01,000\nHello\n",
    )
    (get_logs_dir() / "session.log").write_text("log", encoding="utf-8")

    with TestClient(backend_server.app) as client:
        response = client.post("/diagnostics/archive-on-exit")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert len(payload["archives"]) == 1
    archive_path = Path(payload["archives"][0])
    assert archive_path.exists()
    assert archive_path.name.startswith("cue_log_bundle_")
    assert archive_path.parent == video_path.parent


def test_enqueue_event_appends_job_trace_jsonl(tmp_path: Path) -> None:
    trace_path = tmp_path / "job_trace_test.jsonl"
    job = backend_server.JobState(
        job_id="job-trace",
        status="running",
        created_at=datetime.now(timezone.utc),
        trace_path=trace_path,
    )

    backend_server._enqueue_event(
        job,
        backend_server._build_event(
            job.job_id,
            "progress",
            step_id="ALIGN_WORDS",
            step_progress=0.5,
            pct=50,
            message="Timing word highlighting",
        ),
    )
    backend_server._enqueue_event(
        job,
        backend_server._build_event(
            job.job_id,
            "checklist",
            step_id="timing_word_highlights",
            state="start",
            reason_text="50/100 words",
        ),
    )

    lines = [line for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["type"] == "progress"
    assert first["step_id"] == "ALIGN_WORDS"
    assert second["type"] == "checklist"
    assert second["reason_text"] == "50/100 words"


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


def _new_running_job(job_id: str) -> backend_server.JobState:
    return backend_server.JobState(
        job_id=job_id,
        status="running",
        created_at=datetime.now(timezone.utc),
    )


def test_progress_step_ids_are_canonicalized_without_duplicate_logical_rows() -> None:
    job = _new_running_job("job-canonical")

    backend_server._update_job_snapshot(
        job,
        backend_server._build_event(
            job.job_id,
            "progress",
            step_id="ALIGN_WORDS",
            pct=17,
            message="Timing word highlighting",
            step_progress=0.17,
        ),
    )
    backend_server._update_job_snapshot(
        job,
        backend_server._build_event(
            job.job_id,
            "checklist",
            step_id="timing_word_highlights",
            state="start",
            reason_text="17/100 words",
        ),
    )
    backend_server._update_job_snapshot(
        job,
        backend_server._build_event(
            job.job_id,
            "checklist",
            step_id="timing_word_highlights",
            state="done",
            reason_text="100/100 words",
        ),
    )

    assert "ALIGN_WORDS" not in job.snapshot_checklist
    assert job.snapshot_checklist_order == ["timing_word_highlights"]
    assert job.snapshot_step_id == "timing_word_highlights"
    row = job.snapshot_checklist["timing_word_highlights"]
    assert row["state"] == "done"
    assert row["detail"] == "100/100 words"

    active_task = backend_server._serialize_active_task(job)
    assert [item["id"] for item in active_task["checklist"]] == ["timing_word_highlights"]


def test_progress_messages_do_not_overwrite_checklist_detail() -> None:
    job = _new_running_job("job-detail-authority")

    backend_server._update_job_snapshot(
        job,
        backend_server._build_event(
            job.job_id,
            "checklist",
            step_id="timing_word_highlights",
            state="start",
            reason_text="3/50 words",
        ),
    )
    backend_server._update_job_snapshot(
        job,
        backend_server._build_event(
            job.job_id,
            "progress",
            step_id="ALIGN_WORDS",
            pct=61,
            message="61%",
            step_progress=0.61,
        ),
    )

    row = job.snapshot_checklist["timing_word_highlights"]
    assert row["detail"] == "3/50 words"
    assert row["state"] == "active"
    assert job.snapshot_step_id == "timing_word_highlights"
    assert job.snapshot_message == "61%"
