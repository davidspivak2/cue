from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

HOST = "127.0.0.1"
PORT = 8765

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_version_from_tauri_config() -> Optional[str]:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "desktop" / "src-tauri" / "tauri.conf.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    version = data.get("version")
    return version if isinstance(version, str) and version else None


def _get_app_version() -> str:
    version = getattr(sys.modules.get("__main__"), "__version__", None)
    if isinstance(version, str) and version:
        return version

    version = _load_version_from_tauri_config()
    if version:
        return version

    return "0.0.0"  # TODO: wire to backend package version once defined.


def _get_git_commit() -> Optional[str]:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    commit = result.stdout.strip()
    return commit or None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "pid": os.getpid(),
        "version": _get_app_version(),
    }


@app.get("/version")
def version() -> dict[str, Optional[str]]:
    return {
        "version": _get_app_version(),
        "git_commit": _get_git_commit(),
    }


def main() -> None:
    import uvicorn

    uvicorn.run("app.backend_server:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
