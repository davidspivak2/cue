"""Tests for backend_pipeline_adapter (e.g. _resolve_device_and_compute for ultra)."""

from __future__ import annotations

import pytest

from app.backend_pipeline_adapter import _resolve_device_and_compute


def test_resolve_device_and_compute_ultra_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import transcription_device

    monkeypatch.setattr(transcription_device, "ultra_device", lambda: "gpu")
    device, compute = _resolve_device_and_compute(
        "ultra", gpu_available_fn=lambda: True
    )
    assert device == "cuda"
    assert compute == "float32"


def test_resolve_device_and_compute_ultra_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import transcription_device

    monkeypatch.setattr(transcription_device, "ultra_device", lambda: "cpu")
    device, compute = _resolve_device_and_compute(
        "ultra", gpu_available_fn=lambda: False
    )
    assert device == "cpu"
    assert compute == "float32"


def test_resolve_device_and_compute_ultra_unavailable_fallback_gpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import transcription_device

    monkeypatch.setattr(transcription_device, "ultra_device", lambda: None)
    device, compute = _resolve_device_and_compute(
        "ultra", gpu_available_fn=lambda: True
    )
    assert device == "cuda"
    assert compute == "float16"


def test_resolve_device_and_compute_ultra_unavailable_fallback_cpu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import transcription_device

    monkeypatch.setattr(transcription_device, "ultra_device", lambda: None)
    device, compute = _resolve_device_and_compute(
        "ultra", gpu_available_fn=lambda: False
    )
    assert device == "cpu"
    assert compute == "float32"
