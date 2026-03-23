from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

BIN_DIR_NAME = "bin"
WINDOWS_HIDDEN_SUBPROCESS_CREATIONFLAGS = 0
if os.name == "nt":
    WINDOWS_HIDDEN_SUBPROCESS_CREATIONFLAGS = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
    )

MISSING_FFMPEG_MESSAGE = (
    "Video tools not found. Run scripts\\download_ffmpeg.bat or install them with winget."
)


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_resource_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_runtime_mode() -> str:
    if _is_frozen():
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if meipass and meipass.exists():
            return "pyinstaller-onefile"
        return "pyinstaller-onefolder"
    return "source"


def get_ffmpeg_path() -> Path:
    return get_resource_root() / BIN_DIR_NAME / "ffmpeg.exe"


def get_ffprobe_path() -> Path:
    return get_resource_root() / BIN_DIR_NAME / "ffprobe.exe"


def resolve_ffmpeg_paths() -> tuple[Optional[Path], Optional[Path], str]:
    if _is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        packaged_candidates = [
            ("pyinstaller-onefolder", exe_dir / BIN_DIR_NAME),
        ]
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if meipass and meipass.exists():
            packaged_candidates.append(("pyinstaller-onefile", meipass / BIN_DIR_NAME))

        for mode, bin_dir in packaged_candidates:
            ffmpeg_path = bin_dir / "ffmpeg.exe"
            if ffmpeg_path.exists():
                ffprobe_path = bin_dir / "ffprobe.exe"
                return ffmpeg_path, (ffprobe_path if ffprobe_path.exists() else None), mode

    source_bin_dir = get_resource_root() / BIN_DIR_NAME
    ffmpeg_path = source_bin_dir / "ffmpeg.exe"
    if ffmpeg_path.exists():
        ffprobe_path = source_bin_dir / "ffprobe.exe"
        return ffmpeg_path, (ffprobe_path if ffprobe_path.exists() else None), "source-bin"

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        system_ffprobe = shutil.which("ffprobe")
        return (
            Path(system_ffmpeg),
            (Path(system_ffprobe) if system_ffprobe else None),
            "system-path",
        )

    return None, None, "missing"


def get_subprocess_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": WINDOWS_HIDDEN_SUBPROCESS_CREATIONFLAGS,
        "startupinfo": startupinfo,
    }


def ensure_ffmpeg_available() -> tuple[Path, Optional[Path], str]:
    ffmpeg_path, ffprobe_path, mode = resolve_ffmpeg_paths()
    if not ffmpeg_path:
        raise FileNotFoundError(MISSING_FFMPEG_MESSAGE)
    return ffmpeg_path, ffprobe_path, mode


def get_ffmpeg_missing_message() -> str:
    return MISSING_FFMPEG_MESSAGE


def get_media_duration(path: Path) -> Optional[float]:
    _, ffprobe_path, _ = ensure_ffmpeg_available()
    if not ffprobe_path:
        return None
    command = [
        str(ffprobe_path),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            **get_subprocess_kwargs(),
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def get_ffprobe_json(path: Path) -> Optional[dict[str, Any]]:
    _, ffprobe_path, _ = resolve_ffmpeg_paths()
    if not ffprobe_path:
        return None
    command = [
        str(ffprobe_path),
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-print_format",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            **get_subprocess_kwargs(),
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def media_has_audio_stream(path: Path) -> Optional[bool]:
    """
    True if ffprobe reports at least one audio stream, False if none.
    None if the file could not be probed (missing ffprobe, unreadable file, etc.).
    """
    data = get_ffprobe_json(path)
    if not data:
        return None
    streams = data.get("streams")
    if not isinstance(streams, list):
        return False
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "audio":
            return True
    return False


def format_ffmpeg_failure_message(stderr_lines: Iterable[str]) -> str:
    """
    Turn ffmpeg stderr into a short explanation plus the original log for support.
    """
    tail_text = "\n".join(line for line in stderr_lines if line)
    lower = tail_text.lower()
    if "does not contain any stream" in lower and "output" in lower:
        return (
            "This video has no audio track, so subtitles cannot be generated from it.\n\n"
            "Technical details (ffmpeg):\n"
            + tail_text
        )
    if "no audio streams" in lower:
        return (
            "This video has no audio track, so subtitles cannot be generated from it.\n\n"
            "Technical details (ffmpeg):\n"
            + tail_text
        )
    return "Video processing failed.\n\nTechnical details (ffmpeg):\n" + tail_text


def escape_ffmpeg_filter_path(path: os.PathLike | str) -> str:
    """
    Escape a Windows path for FFmpeg filter arguments.
    """
    text = str(path)
    text = text.replace("\\", "/")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def extract_raw_frame(
    video_path: Path,
    timestamp_seconds: float,
    output_path: Path,
    *,
    width: int = 1280,
) -> bool:
    try:
        ffmpeg_path, _, _ = ensure_ffmpeg_available()
    except FileNotFoundError:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_chain = f"scale='min({width},iw)':-2:force_original_aspect_ratio=decrease"
    command = [
        str(ffmpeg_path),
        "-y",
        "-hide_banner",
        "-ss",
        f"{timestamp_seconds:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        filter_chain,
        str(output_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            **get_subprocess_kwargs(),
        )
    except Exception:
        return False
    if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        return True
    if output_path.exists():
        try:
            output_path.unlink()
        except OSError:
            pass
    return False


def generate_thumbnail(
    path: Path,
    duration: Optional[float],
    logger: Optional[logging.Logger],
) -> Optional[Path]:
    from .paths import get_cache_dir

    thumb_dir = get_cache_dir() / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(str(path.resolve()).encode()).hexdigest()
    out_path = thumb_dir / f"{key}.png"
    if out_path.exists():
        return out_path
    timestamp = 1.0 if (duration is None or duration < 1) else min(1.0, duration * 0.1)
    if extract_raw_frame(path, timestamp, out_path, width=640):
        return out_path
    return None
