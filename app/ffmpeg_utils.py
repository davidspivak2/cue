from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Any, Optional
from pathlib import Path

BIN_DIR_NAME = "bin"
MISSING_FFMPEG_MESSAGE = (
    "FFmpeg not found. Run download_ffmpeg.bat or install via winget: "
    "winget install -e --id Gyan.FFmpeg"
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
        "creationflags": subprocess.CREATE_NO_WINDOW,
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
