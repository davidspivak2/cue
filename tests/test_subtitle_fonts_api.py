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
    fredoka = next(font for font in payload["fonts"] if font["family"] == "Fredoka")
    assert fredoka["weights"] == [300, 400, 500, 600, 700]
    fredoka_hebrew = next(
        font for font in payload["fonts"] if font["family"] == "Fredoka One Hebrew"
    )
    assert fredoka_hebrew["weights"] == [300, 400, 500, 600, 700]
    playpen_hebrew = next(
        font for font in payload["fonts"] if font["family"] == "Playpen Sans Hebrew"
    )
    assert playpen_hebrew["weights"] == [100, 200, 300, 400, 500, 600, 700, 800]
    assert any(font["family"] == "Baloo 2" for font in payload["fonts"])
    assert any(font["family"] == "Lilita One" for font in payload["fonts"])
    assert any(font["family"] == "Luckiest Guy" for font in payload["fonts"])
    assert any(font["family"] == "Titan One" for font in payload["fonts"])
