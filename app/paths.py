from __future__ import annotations

import os
from pathlib import Path


def get_app_data_dir() -> Path:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = local_appdata / "Cue"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_models_dir() -> Path:
    path = get_app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir() -> Path:
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_diagnostics_dir() -> Path:
    path = get_logs_dir() / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir() -> Path:
    path = get_app_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_preview_frames_dir() -> Path:
    path = get_cache_dir() / "preview_frames"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_preview_clips_dir() -> Path:
    path = get_cache_dir() / "previews"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    return get_app_data_dir() / "config.json"
