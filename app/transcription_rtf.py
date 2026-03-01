"""Real-time factor (RTF) estimates for transcription. Shared by workers and /device endpoint.

Benchmark lookup: add (GPU name substring, quality -> rtf) to _RTF_GPU_BENCHMARKS
or (max_cores, quality -> rtf) to _RTF_CPU_BENCHMARKS from real runs; model fixed large-v3.
"""

_RTF_GPU_BENCHMARKS: dict[str, dict[str, float]] = {}
"""GPU name substring -> quality -> RTF. Match by substring in gpu_name (longest match wins)."""

_RTF_CPU_BENCHMARKS: list[tuple[int, dict[str, float]]] = []
"""List of (max_cores_inclusive, quality -> RTF). First bucket with cpu_cores <= max_cores wins."""


def get_rtf_est(quality: str, device: str, compute_type: str) -> float:
    """Return estimated RTF (processing time / audio duration) for given quality, device, compute_type."""
    if quality in ("speed", "fast"):
        result = 1.0 if device == "cuda" else 4.0
    elif quality == "accurate":
        result = 6.0
    elif quality == "quality":
        result = 10.0 if device == "cpu" else 1.5
    elif quality == "ultra":
        result = 15.0 if device == "cpu" else 2.25
    elif device == "cuda" and compute_type == "float16":
        result = 1.5
    elif device == "cuda" and compute_type == "int8_float16":
        result = 1.3
    else:
        result = 6.0
    return result


def get_rtf_est_for_device(
    quality: str,
    device: str,
    compute_type: str,
    *,
    gpu_name: str | None = None,
    cpu_cores: int | None = None,
) -> float:
    """Return RTF from benchmark lookup if device matches; else fall back to get_rtf_est."""
    if device == "cuda" and gpu_name:
        normalized = gpu_name.strip()
        if normalized:
            matching = [k for k in _RTF_GPU_BENCHMARKS if k in normalized]
            if matching:
                key = max(matching, key=len)
                entry = _RTF_GPU_BENCHMARKS[key]
                if quality in entry:
                    return entry[quality]
    if device == "cpu" and cpu_cores is not None and cpu_cores > 0:
        for max_cores, entry in _RTF_CPU_BENCHMARKS:
            if cpu_cores <= max_cores and quality in entry:
                return entry[quality]
    return get_rtf_est(quality, device, compute_type)
