from __future__ import annotations

import sys
import subprocess
from unittest.mock import MagicMock

import pytest

from app import transcription_device


def test_get_gpu_vram_total_bytes_returns_none_when_no_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: False)
    assert transcription_device.get_gpu_vram_total_bytes() is None


def test_get_gpu_vram_total_bytes_parses_mib_to_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: True)

    def fake_run(cmd, *args, **kwargs):
        assert any("memory.total" in str(x) for x in cmd)
        return MagicMock(returncode=0, stdout="8192\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = transcription_device.get_gpu_vram_total_bytes()
    assert result == 8192 * 1024 * 1024


def test_get_gpu_vram_total_bytes_returns_none_on_invalid_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: True)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: MagicMock(returncode=0, stdout="not-a-number\n"),
    )
    assert transcription_device.get_gpu_vram_total_bytes() is None


def test_get_gpu_vram_total_bytes_returns_none_on_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: True)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MagicMock(returncode=1, stdout=""))
    assert transcription_device.get_gpu_vram_total_bytes() is None


def test_get_system_ram_total_bytes_returns_total_when_psutil_available(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_mem = MagicMock()
    fake_mem.total = 32 * (1024**3)
    fake_psutil = MagicMock()
    fake_psutil.virtual_memory.return_value = fake_mem
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    result = transcription_device.get_system_ram_total_bytes()
    assert result == 32 * (1024**3)


def test_get_system_ram_total_bytes_returns_none_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_psutil = MagicMock()
    fake_psutil.virtual_memory.side_effect = RuntimeError("virtual_memory failed")
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    result = transcription_device.get_system_ram_total_bytes()
    assert result is None


def test_ultra_available_and_device_gpu_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: True)
    monkeypatch.setattr(
        transcription_device,
        "get_gpu_vram_total_bytes",
        lambda: 8 * (1024**3),
    )
    monkeypatch.setattr(
        transcription_device,
        "get_system_ram_total_bytes",
        lambda: 8 * (1024**3),
    )
    monkeypatch.setattr(transcription_device, "get_cpu_cores", lambda: 2)
    assert transcription_device.ultra_available() is True
    assert transcription_device.ultra_device() == "gpu"


def test_ultra_available_and_device_cpu_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: False)
    monkeypatch.setattr(
        transcription_device,
        "get_system_ram_total_bytes",
        lambda: 16 * (1024**3),
    )
    monkeypatch.setattr(transcription_device, "get_cpu_cores", lambda: 4)
    assert transcription_device.ultra_available() is True
    assert transcription_device.ultra_device() == "cpu"


def test_ultra_available_and_device_cpu_path_low_ram(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: False)
    monkeypatch.setattr(
        transcription_device,
        "get_system_ram_total_bytes",
        lambda: 8 * (1024**3),
    )
    monkeypatch.setattr(transcription_device, "get_cpu_cores", lambda: 4)
    assert transcription_device.ultra_available() is False
    assert transcription_device.ultra_device() is None


def test_ultra_available_and_device_cpu_path_low_cores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: False)
    monkeypatch.setattr(
        transcription_device,
        "get_system_ram_total_bytes",
        lambda: 16 * (1024**3),
    )
    monkeypatch.setattr(transcription_device, "get_cpu_cores", lambda: 2)
    assert transcription_device.ultra_available() is False
    assert transcription_device.ultra_device() is None


def test_ultra_available_gpu_vram_below_threshold_falls_back_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: True)
    monkeypatch.setattr(
        transcription_device,
        "get_gpu_vram_total_bytes",
        lambda: 4 * (1024**3),
    )
    monkeypatch.setattr(
        transcription_device,
        "get_system_ram_total_bytes",
        lambda: 16 * (1024**3),
    )
    monkeypatch.setattr(transcription_device, "get_cpu_cores", lambda: 4)
    assert transcription_device.ultra_available() is True
    assert transcription_device.ultra_device() == "cpu"


def test_ultra_available_exactly_8gb_vram(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transcription_device, "gpu_available", lambda: True)
    monkeypatch.setattr(
        transcription_device,
        "get_gpu_vram_total_bytes",
        lambda: transcription_device.ULTRA_GPU_VRAM_MIN_BYTES,
    )
    monkeypatch.setattr(
        transcription_device,
        "get_system_ram_total_bytes",
        lambda: 16 * (1024**3),
    )
    monkeypatch.setattr(transcription_device, "get_cpu_cores", lambda: 4)
    assert transcription_device.ultra_available() is True
    assert transcription_device.ultra_device() == "gpu"
