from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from ..ffmpeg_utils import ensure_ffmpeg_available, get_media_duration


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_app_data_dir() -> Path:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = local_appdata / "HebrewSubtitleGUI"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_media_duration_seconds(path: Path) -> Optional[float]:
    try:
        return get_media_duration(path)
    except FileNotFoundError:
        return None


def _thumbnail_cache_dir() -> Path:
    cache_dir = get_app_data_dir() / "cache" / "thumbs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _thumbnail_cache_key(video_path: Path) -> str:
    try:
        stat = video_path.stat()
        size = stat.st_size
        mtime = stat.st_mtime
    except FileNotFoundError:
        size = 0
        mtime = 0.0
    path_key = str(video_path.resolve())
    return f"{path_key}|{size}|{mtime}"


def _candidate_timestamps(duration_seconds: Optional[float]) -> Iterable[float]:
    if duration_seconds and duration_seconds > 0:
        target = max(0.0, min(duration_seconds * 0.25, max(duration_seconds - 0.1, 0.0)))
    else:
        target = 1.0
    candidates = [target, 1.0, 0.0]
    seen = set()
    for value in candidates:
        if value in seen:
            continue
        seen.add(value)
        yield value


def generate_thumbnail(
    video_path: Path,
    duration_seconds: Optional[float],
    logger: Optional[logging.Logger] = None,
) -> Optional[Path]:
    try:
        ffmpeg_path, _, _ = ensure_ffmpeg_available()
    except FileNotFoundError:
        if logger:
            logger.info("Thumbnail skipped: ffmpeg not available.")
        return None

    cache_key = _thumbnail_cache_key(video_path)
    cache_name = hashlib.sha1(cache_key.encode("utf-8")).hexdigest() + ".png"
    output_path = _thumbnail_cache_dir() / cache_name
    if output_path.exists():
        if logger:
            logger.info("Thumbnail cache hit: %s", output_path)
        return output_path

    for timestamp in _candidate_timestamps(duration_seconds):
        if logger:
            logger.info("Thumbnail generation start: t=%.2fs, video=%s", timestamp, video_path)
        command = [
            str(ffmpeg_path),
            "-y",
            "-ss",
            f"{timestamp:.2f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=960:-1:force_original_aspect_ratio=decrease",
            str(output_path),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except Exception:
            if logger:
                logger.info("Thumbnail generation failed: ffmpeg invocation error.")
            continue
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            if logger:
                logger.info("Thumbnail generated: %s", output_path)
            return output_path
        if logger:
            stderr = (result.stderr or "").strip().replace("\n", " ")
            if stderr:
                logger.info(
                    "Thumbnail generation failed: exit=%s stderr=%s",
                    result.returncode,
                    stderr[:240],
                )
            else:
                logger.info("Thumbnail generation failed: exit=%s", result.returncode)

    if output_path.exists():
        try:
            output_path.unlink()
        except OSError:
            pass
    if logger:
        logger.info("Thumbnail generation failed: no valid frame captured.")
    return None
