from __future__ import annotations

import os
from pathlib import Path


def get_app_data_dir() -> Path:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = local_appdata / "HebrewSubtitleGUI"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_models_dir() -> Path:
    path = get_app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path
