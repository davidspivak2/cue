from __future__ import annotations

import argparse
import faulthandler
import importlib
import os
import shutil
import sys
import threading
import traceback
from pathlib import Path
from typing import NoReturn

from .srt_utils import SrtSegment, segments_to_srt
from .paths import get_models_dir

MODEL_NAME = "large-v3"


def _print(message: str) -> None:
    print(message, flush=True)


def _stabilize_runtime() -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    base_dir = None
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", ""))
        if not base_dir.exists():
            base_dir = Path(sys.executable).resolve().parent / "_internal"
    if base_dir and base_dir.exists():
        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(base_dir))
        except OSError as exc:
            _print(f"Warning: failed to add DLL directory: {exc}")
        os.environ["PATH"] = f"{base_dir};{os.environ.get('PATH', '')}"

    cuda_path = os.environ.get("CUDA_PATH")
    candidates: list[str] = []
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
    
def _ctranslate2_cuda_device_count() -> int:
    try:
        ctranslate2 = importlib.import_module("ctranslate2")
        return int(ctranslate2.get_cuda_device_count())
    except Exception as exc:  # noqa: BLE001
        _print(f"CTRANSLATE2_CUDA_PROBE_ERROR {exc}")
        return 0


def _should_use_gpu(prefer_gpu: bool, force_cpu: bool) -> tuple[bool, str]:
    if force_cpu:
        return False, "GPU disabled: --force-cpu"
    if not prefer_gpu:
        return False, "GPU not requested"
    count = _ctranslate2_cuda_device_count()
    return count > 0, f"CTRANSLATE2_CUDA_DEVICE_COUNT {count}"


def _validate_model_dir(model_dir: Path) -> bool:
    return (model_dir / "model.bin").exists() and (model_dir / "config.json").exists()


def _start_heartbeat(label: str, stop_event: threading.Event) -> threading.Thread:
    def _beat() -> None:
        while not stop_event.wait(10.0):
            _print(f"HEARTBEAT {label}")

    thread = threading.Thread(target=_beat, daemon=True)
    thread.start()
    return thread


def _load_model(prefer_gpu: bool, *, models_dir: Path):
    from faster_whisper import WhisperModel

    compute_type = "float16" if prefer_gpu else "int8"
    device = "cuda" if prefer_gpu else "cpu"
    _print(f"MODEL_DEVICE {device} compute_type={compute_type}")
    if prefer_gpu:
        try:
            _print("MODE gpu")
            _print("Loading model (GPU)...")
            model = WhisperModel(
                MODEL_NAME,
                device="cuda",
                compute_type=compute_type,
                cpu_threads=2,
                num_workers=1,
                download_root=str(models_dir),
            )
            return model
        except Exception as exc:  # noqa: BLE001
            summary = str(exc).replace("\n", " ")
            _print(f"MODE cpu {summary}")
            _print("Loading model (CPU)...")
            _print("MODEL_DEVICE cpu compute_type=int8")
            return WhisperModel(
                MODEL_NAME,
                device="cpu",
                compute_type="int8",
                cpu_threads=2,
                num_workers=1,
                download_root=str(models_dir),
            )
    _print("MODE cpu")
    _print("Loading model (CPU)...")
    return WhisperModel(
        MODEL_NAME,
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
        num_workers=1,
        download_root=str(models_dir),
    )


def _write_srt(segments: list[SrtSegment], srt_path: Path) -> None:
    srt_content = segments_to_srt(segments)
    srt_path.write_text(srt_content, encoding="utf-8")


def _hard_exit(code: int) -> NoReturn:
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(code)


def _enable_faulthandler() -> None:
    if sys.stderr is not None:
        faulthandler.enable()
        return
    log_dir = get_models_dir().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "transcribe_worker_faulthandler.log"
    with log_path.open("a", encoding="utf-8") as handle:
        faulthandler.enable(file=handle)


def main(argv: list[str] | None = None, *, hard_exit: bool = False) -> int:
    _enable_faulthandler()
    _print(f"Executable: {sys.executable}")
    _print(f"Args: {sys.argv}")
    _print(f"Frozen: {getattr(sys, 'frozen', False)}")
    _print(f"MEIPASS: {getattr(sys, '_MEIPASS', '')}")
    _print(f"CWD: {os.getcwd()}")
    _print(f"sys.path[:5]: {sys.path[:5]}")
    path_value = os.environ.get("PATH", "")
    _print(f"PATH length: {len(path_value)}")
    _print(f"PATH head: {path_value[:300]}")
    _print(
        f"PATH has _MEIPASS/_internal: {'_MEIPASS' in path_value or '_internal' in path_value}"
    )
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
        _stabilize_runtime()
        _print("ABOUT_TO_IMPORT_WHISPER")
        try:
            import ctranslate2
            import faster_whisper
            import tokenizers
            import av

            _print(f"faster_whisper: {getattr(faster_whisper, '__version__', 'unknown')}")
            _print(f"ctranslate2: {getattr(ctranslate2, '__version__', 'unknown')}")
            _print(f"tokenizers: {getattr(tokenizers, '__version__', 'unknown')}")
            _print(f"ctranslate2.__file__: {getattr(ctranslate2, '__file__', 'unknown')}")
            _print(f"av.__file__: {getattr(av, '__file__', 'unknown')}")
        except Exception as exc:  # noqa: BLE001
            _print(f"ERROR importing whisper deps: {exc}")
        _print("READY")
        models_dir = get_models_dir()
        model_dir = models_dir / MODEL_NAME
        _print(f"MODEL_NAME {MODEL_NAME}")
        _print(f"MODELS_DIR {models_dir}")
        _print(f"MODEL_DIR {model_dir}")
        if model_dir.exists():
            is_valid = _validate_model_dir(model_dir)
            _print(f"MODEL_VALIDATE {is_valid}")
            if not is_valid:
                _print("MODEL_INVALID removing")
                shutil.rmtree(model_dir, ignore_errors=True)
        prefer_gpu, gpu_reason = _should_use_gpu(args.prefer_gpu, args.force_cpu)
        _print(gpu_reason)
        if not prefer_gpu and args.prefer_gpu and not args.force_cpu:
            _print("GPU not available; falling back to CPU.")
        heartbeat_stop = threading.Event()
        heartbeat_thread = _start_heartbeat("MODEL_LOAD", heartbeat_stop)
        try:
            model = _load_model(prefer_gpu, models_dir=models_dir)
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)
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
            if hard_exit:
                _hard_exit(2)
            return 2
        _print(f"DONE {srt_path}")
        if hard_exit:
            _hard_exit(0)
        return 0
    except Exception as exc:  # noqa: BLE001
        _print(f"ERROR {exc}")
        _print(traceback.format_exc())
        if hard_exit:
            _hard_exit(1)
        return 1


if __name__ == "__main__":
    main(hard_exit=True)
