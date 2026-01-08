from __future__ import annotations

import argparse
import faulthandler
import os
import sys
import traceback
from ctypes import CDLL
from pathlib import Path

from faster_whisper import WhisperModel

from .srt_utils import SrtSegment, segments_to_srt


def _print(message: str) -> None:
    print(message, flush=True)


def _add_cuda_paths() -> None:
    candidates: list[str] = []
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        candidates.append(str(Path(cuda_path) / "bin"))
    cuda_root = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
    if cuda_root.exists():
        for entry in cuda_root.glob("v*"):
            bin_dir = entry / "bin"
            if bin_dir.exists():
                candidates.append(str(bin_dir))
    existing = os.environ.get("PATH", "")
    new_paths = [path for path in candidates if path and path not in existing]
    if new_paths:
        os.environ["PATH"] = ";".join(new_paths + [existing])
        _print(f"CUDA PATH added: {', '.join(new_paths)}")


def _gpu_is_available() -> bool:
    dll_candidates = [
        "cublas64_12.dll",
        "cublas64_11.dll",
        "cudart64_120.dll",
        "cudart64_110.dll",
        "cudart64_101.dll",
    ]
    for dll_name in dll_candidates:
        try:
            CDLL(dll_name)
            return True
        except OSError:
            continue
    return False


def _load_model(prefer_gpu: bool) -> WhisperModel:
    if prefer_gpu:
        try:
            _print("MODE gpu")
            _print("Loading model (GPU)...")
            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            return model
        except Exception as exc:  # noqa: BLE001
            summary = str(exc).replace("\n", " ")
            _print(f"MODE cpu {summary}")
            _print("Loading model (CPU)...")
            return WhisperModel("large-v3", device="cpu", compute_type="int8")
    _print("MODE cpu")
    _print("Loading model (CPU)...")
    return WhisperModel("large-v3", device="cpu", compute_type="int8")


def _write_srt(segments: list[SrtSegment], srt_path: Path) -> None:
    srt_content = segments_to_srt(segments)
    srt_path.write_text(srt_content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    faulthandler.enable()
    parser = argparse.ArgumentParser(description="Whisper transcription worker")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--srt", required=True)
    parser.add_argument("--lang", default="he")
    parser.add_argument("--prefer-gpu", action="store_true")
    parser.add_argument("--force-cpu", action="store_true")
    parser.add_argument("--duration-seconds", type=float)
    args = parser.parse_args(argv)

    wav_path = Path(args.wav)
    srt_path = Path(args.srt)

    try:
        _print("READY")
        prefer_gpu = args.prefer_gpu and not args.force_cpu
        if prefer_gpu:
            _add_cuda_paths()
            if not _gpu_is_available():
                _print("GPU not available; falling back to CPU.")
                prefer_gpu = False
        model = _load_model(prefer_gpu)
        segments_iter, info = model.transcribe(
            str(wav_path),
            language=args.lang,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            word_timestamps=True,
        )
        _print(
            f"Detected language: {info.language} "
            f"(prob={info.language_probability:.2f})"
        )

        segments: list[SrtSegment] = []
        max_end = 0.0
        index = 1
        for segment in segments_iter:
            segments.append(
                SrtSegment(index=index, start=segment.start, end=segment.end, text=segment.text)
            )
            if segment.end > max_end:
                max_end = segment.end
                _print(f"PROGRESS_END {max_end:.3f}")
            index += 1

        _write_srt(segments, srt_path)
        if not srt_path.exists() or srt_path.stat().st_size == 0:
            _print(f"ERROR SRT_WRITE_FAILED {srt_path}")
            return 2
        _print(f"DONE {srt_path}")
        return 0
    except Exception as exc:  # noqa: BLE001
        _print(f"ERROR {exc}")
        _print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
