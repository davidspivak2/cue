from __future__ import annotations

import importlib


def get_cuda_device_count() -> int:
    try:
        ctranslate2 = importlib.import_module("ctranslate2")
        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001
        return 0


def gpu_available() -> bool:
    return get_cuda_device_count() > 0
