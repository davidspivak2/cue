from __future__ import annotations

import os
import sys
from pathlib import Path


BIN_DIR_NAME = "bin"


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_resource_root() -> Path:
    if _is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def get_ffmpeg_path() -> Path:
    return get_resource_root() / BIN_DIR_NAME / "ffmpeg.exe"


def get_ffprobe_path() -> Path:
    return get_resource_root() / BIN_DIR_NAME / "ffprobe.exe"


def ensure_ffmpeg_available() -> tuple[Path, Path]:
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()
    if not ffmpeg_path.exists() or not ffprobe_path.exists():
        missing = []
        if not ffmpeg_path.exists():
            missing.append(str(ffmpeg_path))
        if not ffprobe_path.exists():
            missing.append(str(ffprobe_path))
        raise FileNotFoundError(
            "Bundled FFmpeg binaries not found: " + ", ".join(missing)
        )
    return ffmpeg_path, ffprobe_path


def escape_subtitles_filter_path(path: os.PathLike | str) -> str:
    """
    Escape a Windows path for FFmpeg subtitles filter.
    """
    text = str(path)
    text = text.replace("\\", "/")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def format_filter_style(
    font_name: str,
    font_size: int,
    outline: int,
    shadow: int,
    margin_v: int,
) -> str:
    return (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"Outline={outline},"
        f"Shadow={shadow},"
        f"MarginV={margin_v}"
    )
