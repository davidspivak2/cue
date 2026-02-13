from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests


def _wait_for_job_result(events_url: str, timeout_seconds: int) -> dict[str, Any]:
    result_payload: dict[str, Any] | None = None
    completed = False

    with requests.get(events_url, stream=True, timeout=(10, timeout_seconds)) as response:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            payload_text = line[len("data:") :].strip()
            if not payload_text:
                continue
            event = json.loads(payload_text)
            event_type = event.get("type")
            if event_type == "result":
                payload = event.get("payload")
                if isinstance(payload, dict):
                    result_payload = payload
            if event_type == "error":
                message = event.get("message") or "job error"
                raise RuntimeError(str(message))
            if event_type == "cancelled":
                raise RuntimeError("job cancelled")
            if event_type == "completed":
                completed = True
                break

    if not completed:
        raise RuntimeError("job did not complete")
    if result_payload is None:
        raise RuntimeError("missing result payload")
    return result_payload


def _post_json(base_url: str, route: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}{route}",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Packaged-backend smoke test (project -> subtitles -> export)"
    )
    parser.add_argument("--video", required=True, help="Path to source video")
    parser.add_argument("--output-dir", default=r"C:\Cue_extra\smoke_packaged")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(f"Missing video: {video_path}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    project = _post_json(args.base_url, "/projects", {"video_path": str(video_path)})
    project_id = project.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise RuntimeError("project_id_missing")
    print(f"SMOKE_PROJECT_ID={project_id}")

    create_job = _post_json(
        args.base_url,
        "/jobs",
        {
            "kind": "create_subtitles",
            "project_id": project_id,
            "input_path": str(video_path),
            "output_dir": str(output_dir),
            "options": {},
        },
    )
    create_events_url = create_job.get("events_url")
    if not isinstance(create_events_url, str) or not create_events_url:
        raise RuntimeError("create_subtitles_events_url_missing")
    create_payload = _wait_for_job_result(create_events_url, args.timeout_seconds)

    srt_path = create_payload.get("srt_path")
    if not isinstance(srt_path, str) or not srt_path:
        raise RuntimeError("srt_path_missing")
    if not Path(srt_path).exists():
        raise RuntimeError(f"srt_missing_on_disk: {srt_path}")
    print(f"SMOKE_SRT={srt_path}")

    export_job = _post_json(
        args.base_url,
        "/jobs",
        {
            "kind": "create_video_with_subtitles",
            "project_id": project_id,
            "output_dir": str(output_dir),
            "options": {},
        },
    )
    export_events_url = export_job.get("events_url")
    if not isinstance(export_events_url, str) or not export_events_url:
        raise RuntimeError("export_events_url_missing")
    export_payload = _wait_for_job_result(export_events_url, args.timeout_seconds)

    output_path = export_payload.get("output_path")
    if not isinstance(output_path, str) or not output_path:
        raise RuntimeError("output_path_missing")
    if not Path(output_path).exists():
        raise RuntimeError(f"output_missing_on_disk: {output_path}")
    print(f"SMOKE_OUTPUT={output_path}")
    print("SMOKE_RESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
