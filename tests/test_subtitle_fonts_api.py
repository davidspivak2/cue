from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import backend_server, project_store


def _setup_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(project_store, "generate_thumbnail", lambda *args, **kwargs: None)
    monkeypatch.setattr(project_store, "get_media_duration", lambda *args, **kwargs: None)


def test_subtitle_fonts_endpoint_returns_curated_metadata(tmp_path: Path, monkeypatch) -> None:
    __import__("PySide6")
    _setup_env(tmp_path, monkeypatch)

    with TestClient(backend_server.app) as client:
        response = client.get("/subtitle-fonts")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("fonts"), list)
    heebo = next(font for font in payload["fonts"] if font["family"] == "Heebo")
    assert heebo["weights"] == [100, 200, 300, 400, 500, 600, 700, 800, 900]
    assert heebo["default_weight"] == 400
    assert heebo["italic_supported"] is False
