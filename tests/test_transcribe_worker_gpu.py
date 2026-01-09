from __future__ import annotations

import types

import pytest

from app import transcribe_worker


def _make_module(device_count: int) -> types.SimpleNamespace:
    return types.SimpleNamespace(get_cuda_device_count=lambda: device_count)


def test_should_use_gpu_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        transcribe_worker.importlib,
        "import_module",
        lambda name: _make_module(1),
    )
    should_use, reason = transcribe_worker._should_use_gpu(True, False)
    assert should_use is True
    assert "CTRANSLATE2_CUDA_DEVICE_COUNT" in reason


def test_should_use_gpu_false_no_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        transcribe_worker.importlib,
        "import_module",
        lambda name: _make_module(0),
    )
    should_use, reason = transcribe_worker._should_use_gpu(True, False)
    assert should_use is False
    assert "CTRANSLATE2_CUDA_DEVICE_COUNT 0" in reason


def test_should_use_gpu_force_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        transcribe_worker.importlib,
        "import_module",
        lambda name: _make_module(1),
    )
    should_use, reason = transcribe_worker._should_use_gpu(True, True)
    assert should_use is False
    assert "--force-cpu" in reason


def test_should_use_gpu_probe_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_: str) -> None:
        raise ImportError("boom")

    monkeypatch.setattr(transcribe_worker.importlib, "import_module", _raise)
    should_use, reason = transcribe_worker._should_use_gpu(True, False)
    assert should_use is False
    assert "CTRANSLATE2_CUDA_DEVICE_COUNT" in reason
