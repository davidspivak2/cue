from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel

from .paths import get_projects_dir
from .ui.utils import generate_thumbnail, get_media_duration_seconds


logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
INDEX_FILENAME = "index.json"
MANIFEST_FILENAME = "project.json"
SUBTITLES_FILENAME = "subtitles.srt"
WORD_TIMINGS_FILENAME = "word_timings.json"
STYLE_FILENAME = "style.json"

VALID_STATUSES = {
    "needs_video",
    "needs_subtitles",
    "ready",
    "exporting",
    "done",
    "missing_file",
}

_STORE_LOCK = threading.RLock()


class ProjectSummary(BaseModel):
    project_id: str
    title: str
    video_path: Optional[str]
    missing_video: bool
    status: str
    created_at: str
    updated_at: str
    duration_seconds: Optional[float] = None
    thumbnail_path: Optional[str] = None


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


def _projects_root() -> Path:
    return get_projects_dir()


def _index_path() -> Path:
    return _projects_root() / INDEX_FILENAME


def _project_dir(project_id: str) -> Path:
    return _projects_root() / project_id


def _manifest_path(project_id: str) -> Path:
    return _project_dir(project_id) / MANIFEST_FILENAME


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    os.replace(tmp_path, path)


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _legacy_store_path() -> Path:
    return _projects_root().parent / "projects.json"


def _ensure_store() -> None:
    root = _projects_root()
    root.mkdir(parents=True, exist_ok=True)
    index_path = _index_path()
    if index_path.exists():
        return
    legacy_path = _legacy_store_path()
    if legacy_path.exists():
        _migrate_legacy_store(legacy_path)
    if not index_path.exists():
        _atomic_write_json(index_path, {"projects": []})


def _migrate_legacy_store(legacy_path: Path) -> None:
    data = _read_json_file(legacy_path)
    records = data.get("projects")
    if not isinstance(records, list):
        return
    summaries: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        project_id = str(record.get("project_id") or "").strip()
        video_path = record.get("video_path")
        if not project_id:
            project_id = str(uuid.uuid4())
        manifest_path = _manifest_path(project_id)
        if manifest_path.exists():
            continue
        created_at = str(record.get("created_at") or _now_iso())
        updated_at = str(record.get("updated_at") or created_at)
        manifest = _build_manifest(
            project_id=project_id,
            video_path=str(video_path) if isinstance(video_path, str) else None,
            created_at=created_at,
            updated_at=updated_at,
            status=None,
            style=None,
            latest_export=None,
        )
        _atomic_write_json(manifest_path, manifest)
        summaries.append(_manifest_to_summary(manifest).model_dump())
    if summaries:
        _atomic_write_json(_index_path(), {"projects": summaries})


def _build_manifest(
    *,
    project_id: str,
    video_path: Optional[str],
    created_at: str,
    updated_at: str,
    status: Optional[str],
    style: Optional[dict[str, Any]],
    latest_export: Optional[dict[str, Any]],
) -> dict[str, Any]:
    video_info = _build_video_info(video_path)
    project_dir = _project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    style_path = project_dir / STYLE_FILENAME
    if style is None:
        style = {}
    _atomic_write_json(style_path, style)
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "video": video_info,
        "status": status or "needs_subtitles",
        "artifacts": {
            "subtitles_path": SUBTITLES_FILENAME,
            "word_timings_path": WORD_TIMINGS_FILENAME,
            "style_path": STYLE_FILENAME,
        },
        "latest_export": latest_export,
    }
    manifest["status"] = _compute_status(manifest)
    return manifest


def _build_video_info(video_path: Optional[str]) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": video_path,
        "filename": _derive_title(video_path),
        "size_bytes": None,
        "mtime_ns": None,
        "duration_seconds": None,
        "thumbnail_path": None,
    }
    if not video_path:
        return info
    path = Path(video_path)
    try:
        stat = path.stat()
        info["size_bytes"] = stat.st_size
        info["mtime_ns"] = stat.st_mtime_ns
    except OSError:
        pass
    duration = get_media_duration_seconds(path)
    if duration is not None:
        info["duration_seconds"] = duration
    try:
        thumbnail_path = generate_thumbnail(path, duration, logger)
    except Exception:
        thumbnail_path = None
    if thumbnail_path:
        info["thumbnail_path"] = str(thumbnail_path)
    return info


def _artifact_path(manifest: dict[str, Any], key: str) -> Path:
    project_id = str(manifest.get("project_id") or "")
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    rel_path = artifacts.get(key)
    if not project_id or not isinstance(rel_path, str):
        return _project_dir(project_id)
    return _project_dir(project_id) / rel_path


def _artifact_exists(manifest: dict[str, Any], key: str) -> bool:
    path = _artifact_path(manifest, key)
    return path.exists()


def _read_style_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    style_path = _artifact_path(manifest, "style_path")
    if not style_path.exists():
        return {}
    style_data = _read_json_file(style_path)
    return style_data if isinstance(style_data, dict) else {}


def _compute_status(manifest: dict[str, Any], *, allow_exporting: bool = False) -> str:
    video = manifest.get("video") if isinstance(manifest.get("video"), dict) else {}
    video_path = video.get("path")
    if not video_path:
        return "needs_video"
    if _is_missing(str(video_path)):
        return "missing_file"
    if allow_exporting and manifest.get("status") == "exporting":
        return "exporting"
    has_subtitles = _artifact_exists(manifest, "subtitles_path")
    has_word_timings = _artifact_exists(manifest, "word_timings_path")
    if not has_subtitles or not has_word_timings:
        return "needs_subtitles"
    latest_export = manifest.get("latest_export") if isinstance(manifest.get("latest_export"), dict) else None
    if latest_export and latest_export.get("output_video_path"):
        return "done"
    return "ready"


def _manifest_to_summary(
    manifest: dict[str, Any],
    *,
    allow_exporting: bool = False,
) -> ProjectSummary:
    video = manifest.get("video") if isinstance(manifest.get("video"), dict) else {}
    video_path = video.get("path")
    missing_video = _is_missing(str(video_path)) if video_path else True
    status = _compute_status(manifest, allow_exporting=allow_exporting)
    return ProjectSummary(
        project_id=str(manifest.get("project_id") or ""),
        title=_derive_title(video_path),
        video_path=str(video_path) if isinstance(video_path, str) else None,
        missing_video=missing_video,
        status=status,
        created_at=str(manifest.get("created_at") or ""),
        updated_at=str(manifest.get("updated_at") or ""),
        duration_seconds=video.get("duration_seconds"),
        thumbnail_path=video.get("thumbnail_path"),
    )


def _read_manifest(project_id: str) -> dict[str, Any]:
    manifest_path = _manifest_path(project_id)
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="project_not_found")
    manifest = _read_json_file(manifest_path)
    if not manifest:
        raise HTTPException(status_code=404, detail="project_not_found")
    return manifest


def _write_manifest(manifest: dict[str, Any], *, allow_exporting: bool = False) -> None:
    project_id = str(manifest.get("project_id") or "")
    if not project_id:
        raise ValueError("project_id missing")
    manifest["updated_at"] = _now_iso()
    manifest["status"] = _compute_status(manifest, allow_exporting=allow_exporting)
    _atomic_write_json(_manifest_path(project_id), manifest)


def _write_index(summaries: list[ProjectSummary]) -> None:
    payload = {"projects": [summary.model_dump() for summary in summaries]}
    _atomic_write_json(_index_path(), payload)


def _update_index_entry(summary: ProjectSummary) -> None:
    index = _read_json_file(_index_path())
    records = index.get("projects")
    if not isinstance(records, list):
        records = []
    updated = False
    for i, record in enumerate(records):
        if isinstance(record, dict) and record.get("project_id") == summary.project_id:
            records[i] = summary.model_dump()
            updated = True
            break
    if not updated:
        records.append(summary.model_dump())
    _atomic_write_json(_index_path(), {"projects": records})


def _refresh_index() -> list[ProjectSummary]:
    summaries: list[ProjectSummary] = []
    root = _projects_root()
    if not root.exists():
        return summaries
    for child in root.iterdir():
        if not child.is_dir():
            continue
        manifest_path = child / MANIFEST_FILENAME
        if not manifest_path.exists():
            continue
        manifest = _read_json_file(manifest_path)
        if not manifest:
            continue
        summary = _manifest_to_summary(manifest)
        summaries.append(summary)
        if summary.status != manifest.get("status"):
            manifest["status"] = summary.status
            _atomic_write_json(manifest_path, manifest)
    _write_index(summaries)
    return summaries


def list_projects(active_project_ids: Optional[set[str]] = None) -> list[ProjectSummary]:
    with _STORE_LOCK:
        _ensure_store()
        index = _read_json_file(_index_path())
        records = index.get("projects")
        if not isinstance(records, list):
            return _refresh_index()
        summaries: list[ProjectSummary] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            project_id = str(record.get("project_id") or "")
            if not project_id:
                continue
            try:
                manifest = _read_manifest(project_id)
            except HTTPException:
                continue
            allow_exporting = (
                active_project_ids is not None and project_id in active_project_ids
            )
            summary = _manifest_to_summary(manifest, allow_exporting=allow_exporting)
            summaries.append(summary)
        _write_index(summaries)
        return summaries


def get_project(project_id: str) -> dict[str, Any]:
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        manifest["status"] = _compute_status(manifest)
        _write_manifest(manifest)
        response = dict(manifest)
        response["style"] = _read_style_from_manifest(manifest)
        return response


def get_project_style(project_id: str) -> dict[str, Any]:
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        return _read_style_from_manifest(manifest)


def get_project_export_artifacts(project_id: str) -> dict[str, Optional[str]]:
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        video = manifest.get("video") if isinstance(manifest.get("video"), dict) else {}
        video_path_value = video.get("path")
        if not isinstance(video_path_value, str) or not video_path_value.strip():
            raise HTTPException(status_code=422, detail="project_video_missing")
        video_path = Path(video_path_value)
        if not video_path.exists():
            raise HTTPException(status_code=422, detail="project_video_not_found")
        subtitles_path = _artifact_path(manifest, "subtitles_path")
        if not subtitles_path.exists():
            raise HTTPException(status_code=422, detail="project_subtitles_missing")
        word_timings_path = _artifact_path(manifest, "word_timings_path")
        style_path = _artifact_path(manifest, "style_path")
        project_dir = _project_dir(project_id)
        return {
            "project_id": project_id,
            "project_dir": str(project_dir),
            "video_path": str(video_path),
            "subtitles_path": str(subtitles_path),
            "word_timings_path": str(word_timings_path) if word_timings_path.exists() else None,
            "style_path": str(style_path) if style_path.exists() else None,
        }


def get_project_subtitles_text(project_id: str) -> str:
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        subtitles_path = _artifact_path(manifest, "subtitles_path")
        if not subtitles_path.exists():
            raise HTTPException(status_code=404, detail="subtitles_not_found")
        try:
            return subtitles_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(status_code=500, detail="subtitles_read_failed") from exc


def delete_project(project_id: str) -> None:
    with _STORE_LOCK:
        _ensure_store()
        _read_manifest(project_id)
        project_dir = _project_dir(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
        summaries = [
            summary for summary in list_projects() if summary.project_id != project_id
        ]
        _write_index(summaries)


def create_project(video_path: str, *, style: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if not isinstance(video_path, str) or not video_path.strip():
        raise HTTPException(status_code=422, detail="video_path_required")
    with _STORE_LOCK:
        _ensure_store()
        canonical = _normalize_path(video_path)
        summaries = list_projects()
        for summary in summaries:
            if summary.video_path and _normalize_path(summary.video_path) == canonical:
                manifest = _read_manifest(summary.project_id)
                manifest["video"] = _build_video_info(video_path)
                if style is not None:
                    style_path = _artifact_path(manifest, "style_path")
                    _atomic_write_json(style_path, style)
                _write_manifest(manifest)
                _write_index(list_projects())
                return _manifest_to_summary(manifest).model_dump()
        now = _now_iso()
        project_id = str(uuid.uuid4())
        manifest = _build_manifest(
            project_id=project_id,
            video_path=video_path,
            created_at=now,
            updated_at=now,
            status=None,
            style=style,
            latest_export=None,
        )
        _atomic_write_json(_manifest_path(project_id), manifest)
        summaries = list_projects()
        summaries.append(_manifest_to_summary(manifest))
        _write_index(summaries)
        return _manifest_to_summary(manifest).model_dump()


def relink_project(project_id: str, video_path: str) -> dict[str, Any]:
    if not isinstance(video_path, str) or not video_path.strip():
        raise HTTPException(status_code=422, detail="video_path_required")
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        manifest["video"] = _build_video_info(video_path)
        _write_manifest(manifest)
        _write_index(list_projects())
        return _manifest_to_summary(manifest).model_dump()


def update_project(
    project_id: str,
    *,
    subtitles_srt_text: Optional[str] = None,
    style: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        if isinstance(subtitles_srt_text, str):
            subtitle_path = _artifact_path(manifest, "subtitles_path")
            subtitle_path.write_text(subtitles_srt_text, encoding="utf-8")
        if style is not None:
            style_path = _artifact_path(manifest, "style_path")
            _atomic_write_json(style_path, style)
        _write_manifest(manifest)
        _write_index(list_projects())
        response = dict(manifest)
        response["style"] = _read_style_from_manifest(manifest)
        return response


def set_project_status(project_id: str, status: str) -> None:
    if status not in VALID_STATUSES:
        return
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        manifest["status"] = status
        _write_manifest(manifest, allow_exporting=True)
        summary = _manifest_to_summary(manifest, allow_exporting=True)
        _update_index_entry(summary)


def refresh_project_status(project_id: str) -> str:
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        manifest["status"] = _compute_status(manifest)
        _write_manifest(manifest)
        _write_index(list_projects())
        return str(manifest.get("status") or "")


def record_subtitles_result(
    project_id: str,
    *,
    srt_path: Optional[str],
    word_timings_path: Optional[str],
) -> None:
    if not srt_path and not word_timings_path:
        return
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        project_dir = _project_dir(project_id)
        if srt_path:
            source = Path(srt_path)
            dest = project_dir / SUBTITLES_FILENAME
            if source.exists() and source.resolve() != dest.resolve(strict=False):
                shutil.copy2(source, dest)
        if word_timings_path:
            source = Path(word_timings_path)
            dest = project_dir / WORD_TIMINGS_FILENAME
            if source.exists() and source.resolve() != dest.resolve(strict=False):
                shutil.copy2(source, dest)
        _write_manifest(manifest)
        _write_index(list_projects())


def record_export_result(project_id: str, *, output_path: Optional[str]) -> None:
    if not output_path:
        return
    with _STORE_LOCK:
        _ensure_store()
        manifest = _read_manifest(project_id)
        manifest["latest_export"] = {
            "output_video_path": output_path,
            "exported_at": _now_iso(),
        }
        _write_manifest(manifest)
        _write_index(list_projects())
