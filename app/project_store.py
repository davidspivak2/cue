from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel

from .paths import get_app_data_dir


class ProjectSummary(BaseModel):
    project_id: str
    video_path: Optional[str]
    title: str
    missing_video: bool
    created_at: str
    updated_at: str


_PROJECTS_FILE = get_app_data_dir() / "projects.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_path(value: str) -> str:
    try:
        return str(Path(value).expanduser().resolve(strict=False))
    except Exception:
        return value


def _derive_title(video_path: Optional[str]) -> str:
    if not video_path:
        return "Untitled project"
    try:
        name = Path(video_path).name
    except Exception:
        name = ""
    return name or video_path


def _is_missing(video_path: Optional[str]) -> bool:
    if not video_path:
        return True
    try:
        return not Path(video_path).exists()
    except Exception:
        return True


def _read_store() -> dict[str, Any]:
    if not _PROJECTS_FILE.exists():
        return {"projects": []}
    try:
        data = json.loads(_PROJECTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"projects": []}
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
        return {"projects": []}
    return data


def _write_store(data: dict[str, Any]) -> None:
    _PROJECTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _record_to_summary(record: dict[str, Any]) -> ProjectSummary:
    return ProjectSummary(
        project_id=str(record.get("project_id", "")),
        video_path=record.get("video_path"),
        title=str(record.get("title") or ""),
        missing_video=bool(record.get("missing_video")),
        created_at=str(record.get("created_at") or ""),
        updated_at=str(record.get("updated_at") or ""),
    )


def list_projects() -> list[ProjectSummary]:
    store = _read_store()
    return [_record_to_summary(record) for record in store.get("projects", [])]


def get_project(project_id: str) -> dict[str, Any]:
    store = _read_store()
    for record in store.get("projects", []):
        if record.get("project_id") == project_id:
            return _record_to_summary(record).model_dump()
    raise HTTPException(status_code=404, detail="project_not_found")


def create_project(video_path: str) -> dict[str, Any]:
    if not isinstance(video_path, str) or not video_path.strip():
        raise HTTPException(status_code=422, detail="video_path_required")

    store = _read_store()
    canonical = _normalize_path(video_path)

    for record in store.get("projects", []):
        existing_path = record.get("video_path")
        if isinstance(existing_path, str) and _normalize_path(existing_path) == canonical:
            record["video_path"] = video_path
            record["title"] = _derive_title(video_path)
            record["missing_video"] = _is_missing(video_path)
            record["updated_at"] = _now_iso()
            _write_store(store)
            return _record_to_summary(record).model_dump()

    now = _now_iso()
    record = {
        "project_id": str(uuid.uuid4()),
        "video_path": video_path,
        "title": _derive_title(video_path),
        "missing_video": _is_missing(video_path),
        "created_at": now,
        "updated_at": now,
    }
    store.setdefault("projects", []).append(record)
    _write_store(store)
    return _record_to_summary(record).model_dump()


def relink_project(project_id: str, video_path: str) -> dict[str, Any]:
    if not isinstance(video_path, str) or not video_path.strip():
        raise HTTPException(status_code=422, detail="video_path_required")

    store = _read_store()
    for record in store.get("projects", []):
        if record.get("project_id") == project_id:
            record["video_path"] = video_path
            record["title"] = _derive_title(video_path)
            record["missing_video"] = _is_missing(video_path)
            record["updated_at"] = _now_iso()
            _write_store(store)
            return _record_to_summary(record).model_dump()

    raise HTTPException(status_code=404, detail="project_not_found")
