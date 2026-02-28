from __future__ import annotations

import importlib
import os
import subprocess


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


def get_cpu_cores() -> int:
    return os.cpu_count() or 1
