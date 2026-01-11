from __future__ import annotations

import argparse
import faulthandler
import json
import os
import shutil
import sys
import threading
import traceback
from pathlib import Path
from typing import NoReturn

from .srt_utils import SrtSegment, segments_to_srt
from .srt_splitter import (
    SplitApplyThresholds,
    SplitMaxCue,
    SplitterConfig,
    split_segments_into_cues,
)
from .paths import get_models_dir
from .transcription_config import build_transcription_config
from .transcription_device import get_cuda_device_count

MODEL_NAME = "large-v3"
TRANSCRIBE_DEFAULTS = [
    "best_of",
    "temperature",
    "condition_on_previous_text",
    "compression_ratio_threshold",
    "log_prob_threshold",
    "no_speech_threshold",
    "patience",
    "length_penalty",
]


def _print(message: str) -> None:
    print(message, flush=True)


def _log_transcribe_config(config_json: str, config_text: str) -> None:
    _print(f"TRANSCRIBE_CONFIG_JSON {config_json}")
    for line in config_text.splitlines():
        _print(f"TRANSCRIBE_CONFIG_TEXT {line}")


def _log_transcribe_snapshot(
    transcribe_kwargs: dict[str, object],
    transcribe_defaults: list[str],
) -> None:
    snapshot = {
        "transcribe_kwargs": transcribe_kwargs,
        "transcribe_defaults": transcribe_defaults,
        "transcribe_defaults_missing": [
            key for key in transcribe_defaults if key not in transcribe_kwargs
        ],
    }
    _print(f"TRANSCRIBE_KWARGS_SNAPSHOT {json.dumps(snapshot, sort_keys=True)}")


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
    
def _resolve_device(
    requested_device: str,
    *,
    prefer_gpu: bool,
    force_cpu: bool,
) -> tuple[str, str]:
    if force_cpu:
        return "cpu", "GPU disabled: --force-cpu"
    if requested_device == "cpu":
        return "cpu", "Device requested: cpu"
    count = get_cuda_device_count()
    if requested_device == "cuda":
        if count > 0:
            return "cuda", f"CTRANSLATE2_CUDA_DEVICE_COUNT {count}"
        return "cpu", f"CTRANSLATE2_CUDA_DEVICE_COUNT {count}"
    if not prefer_gpu:
        return "cpu", "GPU not requested"
    return (
        ("cuda", f"CTRANSLATE2_CUDA_DEVICE_COUNT {count}")
        if count > 0
        else ("cpu", f"CTRANSLATE2_CUDA_DEVICE_COUNT {count}")
    )


def _resolve_compute_type(requested_type: str, device: str) -> str:
    if requested_type != "auto":
        if requested_type == "float16" and device != "cuda":
            return "int16"
        return requested_type
    if device == "cuda":
        return "float16"
    return "int16"


def _validate_model_dir(model_dir: Path) -> bool:
    return (model_dir / "model.bin").exists() and (model_dir / "config.json").exists()


def _start_heartbeat(label: str, stop_event: threading.Event) -> threading.Thread:
    def _beat() -> None:
        while not stop_event.wait(10.0):
            _print(f"HEARTBEAT {label}")

    thread = threading.Thread(target=_beat, daemon=True)
    thread.start()
    return thread


def _cpu_threads_for_device(device: str) -> int:
    if device != "cpu":
        return 2
    cpu_count = os.cpu_count() or 2
    return max(2, min(4, cpu_count))


def _load_model(
    device: str,
    compute_type: str,
    *,
    models_dir: Path,
    cpu_threads_cpu: int,
    cpu_threads_active: int,
):
    from faster_whisper import WhisperModel

    _print(f"MODEL_DEVICE {device} compute_type={compute_type}")
    if device == "cuda":
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
                cpu_threads=cpu_threads_cpu,
                num_workers=1,
                download_root=str(models_dir),
            )
    _print("MODE cpu")
    _print("Loading model (CPU)...")
    return WhisperModel(
        MODEL_NAME,
        device="cpu",
        compute_type=compute_type,
        cpu_threads=cpu_threads_active,
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
    parser.add_argument("--wav")
    parser.add_argument("--srt")
    parser.add_argument("--lang", default="he")
    parser.add_argument("--prefer-gpu", action="store_true")
    parser.add_argument("--force-cpu", action="store_true")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument(
        "--compute-type",
        choices=["auto", "int8", "int16", "float16", "float32"],
        default="auto",
    )
    parser.add_argument("--duration-seconds", type=float)
    parser.add_argument("--print-transcribe-config", action="store_true")
    parser.add_argument("--ffmpeg-args-json")
    args = parser.parse_args(argv)

    if not args.print_transcribe_config and (not args.wav or not args.srt):
        parser.error("--wav and --srt are required unless --print-transcribe-config is used.")

    wav_path = Path(args.wav) if args.wav else None
    srt_path = Path(args.srt) if args.srt else None

    try:
        _stabilize_runtime()
        if not args.print_transcribe_config:
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
        device, gpu_reason = _resolve_device(
            args.device,
            prefer_gpu=args.prefer_gpu,
            force_cpu=args.force_cpu,
        )
        _print(gpu_reason)
        if device != "cuda" and args.device == "cuda":
            _print("GPU not available; falling back to CPU.")
        elif device != "cuda" and args.prefer_gpu and not args.force_cpu:
            _print("GPU not available; falling back to CPU.")
        compute_type = _resolve_compute_type(args.compute_type, device)
        prefer_gpu = device == "cuda"
        force_cpu = device == "cpu"
        cpu_threads_cpu = _cpu_threads_for_device("cpu")
        cpu_threads_active = _cpu_threads_for_device(device)
        transcribe_kwargs = {
            "language": args.lang,
            "task": "transcribe",
            "beam_size": 5,
            "vad_filter": True,
            "vad_parameters": {"min_silence_duration_ms": 400},
            "word_timestamps": True,
        }
        _log_transcribe_snapshot(transcribe_kwargs, TRANSCRIBE_DEFAULTS)
        splitter_config = SplitterConfig(
            apply_if=SplitApplyThresholds(
                duration_sec=12.0,
                text_length_chars=160,
                word_count=26,
            ),
            max_cue=SplitMaxCue(
                duration_sec=8.0,
                text_length_chars=90,
                word_count=14,
            ),
            gap_sec=0.4,
            prefer=("punctuation", "gap"),
        )
        audio_extraction = None
        if args.ffmpeg_args_json:
            try:
                audio_extraction = {"ffmpeg_args": json.loads(args.ffmpeg_args_json)}
            except json.JSONDecodeError as exc:
                _print(f"WARNING invalid ffmpeg args JSON: {exc}")
        whisper_model_kwargs = {
            "device": device,
            "compute_type": compute_type,
            "cpu_threads": cpu_threads_active,
            "num_workers": 1,
            "download_root": str(models_dir),
        }
        whisper_model_fallback_kwargs = None
        if prefer_gpu:
            whisper_model_fallback_kwargs = {
                "device": "cpu",
                "compute_type": "int8",
                "cpu_threads": cpu_threads_cpu,
                "num_workers": 1,
                "download_root": str(models_dir),
            }
        config = build_transcription_config(
            model_name=MODEL_NAME,
            models_dir=models_dir,
            prefer_gpu=prefer_gpu,
            force_cpu=force_cpu,
            device=device,
            compute_type=compute_type,
            gpu_probe_reason=gpu_reason,
            whisper_model_kwargs=whisper_model_kwargs,
            whisper_model_fallback_kwargs=whisper_model_fallback_kwargs,
            transcribe_kwargs=transcribe_kwargs,
            transcribe_defaults=TRANSCRIBE_DEFAULTS,
            srt_formatting={
                "timestamp_format": "HH:MM:SS,mmm",
                "index_start": 1,
                "text_trim": "strip",
                "segment_separator": "blank_line",
            },
            post_splitter=splitter_config.to_dict(),
            audio_extraction=audio_extraction,
        )
        _log_transcribe_config(config.to_json(), config.to_pretty_text())
        if args.print_transcribe_config:
            if hard_exit:
                _hard_exit(0)
            return 0
        if wav_path is None or srt_path is None:
            raise ValueError("Missing WAV or SRT path.")
        heartbeat_stop = threading.Event()
        heartbeat_thread = _start_heartbeat("MODEL_LOAD", heartbeat_stop)
        try:
            model = _load_model(
                device,
                compute_type,
                models_dir=models_dir,
                cpu_threads_cpu=cpu_threads_cpu,
                cpu_threads_active=cpu_threads_active,
            )
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)
        segments_iter, info = model.transcribe(str(wav_path), **transcribe_kwargs)
        _print(
            f"Detected language: {info.language} "
            f"(prob={info.language_probability:.2f})"
        )

        transcribe_heartbeat_stop = threading.Event()
        transcribe_heartbeat_thread = _start_heartbeat("TRANSCRIBE", transcribe_heartbeat_stop)
        try:
            raw_segments = []
            max_end = 0.0
            last_reported_end = 0.0
            last_reported_percent = 0.0
            duration_seconds = args.duration_seconds
            for segment in segments_iter:
                raw_segments.append(segment)
                if segment.end > max_end:
                    max_end = segment.end
                should_report = max_end - last_reported_end >= 0.5
                if duration_seconds:
                    current_percent = max_end / duration_seconds
                    if current_percent - last_reported_percent >= 0.01:
                        should_report = True
                if should_report and max_end > last_reported_end:
                    _print(f"PROGRESS_END {max_end:.3f}")
                    last_reported_end = max_end
                    if duration_seconds:
                        last_reported_percent = max_end / duration_seconds
            cues = split_segments_into_cues(raw_segments, config=splitter_config)
            segments: list[SrtSegment] = []
            for index, cue in enumerate(cues, start=1):
                segments.append(
                    SrtSegment(index=index, start=cue.start, end=cue.end, text=cue.text)
                )

            _write_srt(segments, srt_path)
        finally:
            transcribe_heartbeat_stop.set()
            transcribe_heartbeat_thread.join(timeout=1)
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
