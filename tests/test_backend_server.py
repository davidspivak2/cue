from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from app import backend_server


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
