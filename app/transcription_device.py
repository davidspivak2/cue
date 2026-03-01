from __future__ import annotations

import importlib
import os
import subprocess

ULTRA_GPU_VRAM_MIN_BYTES = 8 * (1024**3)
ULTRA_CPU_RAM_MIN_BYTES = 16 * (1024**3)
ULTRA_CPU_MIN_CORES = 4


def get_cuda_device_count() -> int:
    try:
        ctranslate2 = importlib.import_module("ctranslate2")
        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001
        return 0


def gpu_available() -> bool:
    return get_cuda_device_count() > 0


def get_gpu_name() -> str | None:
    if not gpu_available():
        return None
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0) or None
    except Exception:  # noqa: BLE001
        pass
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip().split("\n")[0].strip() or None
    except Exception:  # noqa: BLE001
        pass
    return None


def get_gpu_vram_total_bytes() -> int | None:
    if not gpu_available():
        return None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        line = result.stdout.strip().split("\n")[0].strip()
        mib = int(line.split()[0])
        return mib * 1024 * 1024
    except (ValueError, IndexError, OSError, subprocess.TimeoutExpired):
        return None


def get_system_ram_total_bytes() -> int | None:
    try:
        import psutil
        return psutil.virtual_memory().total
    except Exception:  # noqa: BLE001
        return None


def ultra_available() -> bool:
    if gpu_available():
        vram = get_gpu_vram_total_bytes()
        if vram is not None and vram >= ULTRA_GPU_VRAM_MIN_BYTES:
            return True
    ram = get_system_ram_total_bytes()
    if ram is None or ram < ULTRA_CPU_RAM_MIN_BYTES:
        return False
    if get_cpu_cores() < ULTRA_CPU_MIN_CORES:
        return False
    return True


def ultra_device() -> str | None:
    if gpu_available():
        vram = get_gpu_vram_total_bytes()
        if vram is not None and vram >= ULTRA_GPU_VRAM_MIN_BYTES:
            return "gpu"
    ram = get_system_ram_total_bytes()
    if ram is None or ram < ULTRA_CPU_RAM_MIN_BYTES:
        return None
    if get_cpu_cores() < ULTRA_CPU_MIN_CORES:
        return None
    return "cpu"


def get_cpu_cores() -> int:
    return os.cpu_count() or 1
