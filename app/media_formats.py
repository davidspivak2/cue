"""Shared allowed media extensions for imports (browser upload + local path)."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

SUPPORTED_BROWSER_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".mkv", ".mov", ".m4v", ".webm"}
)


def require_supported_video_extension(path_str: str) -> None:
    """Reject create/relink when the file suffix is not a supported video type."""
    suffix = Path(path_str).suffix.lower()
    if suffix not in SUPPORTED_BROWSER_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=422, detail="unsupported_video_type")
