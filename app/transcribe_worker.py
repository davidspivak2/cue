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
from .punctuation_stats import DEFAULT_PUNCTUATION, build_transcription_stats
from .srt_splitter import (
    SplitApplyThresholds,
    SplitMaxCue,
    SplitterConfig,
    SplitterStats,
    split_segments_into_cues,
)
from .paths import get_models_dir
from .transcription_config import build_transcription_config
from .transcription_device import get_cuda_device_count

DEFAULT_MODEL_NAME = "large-v3"
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
PUNCTUATION_RESCUE_DEFAULTS = {
    "enabled": True,
    "min_density": 0.03,
    "max_attempts": 2,
}


def _print(message: str) -> None:
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        # Windows console / redirected output may be cp1252/cp437, which can't print Hebrew.
        sys.stdout.buffer.write((message + "\n").encode("utf-8", errors="backslashreplace"))
        sys.stdout.buffer.flush()


def _log_transcribe_config(config_json: str, config_text: str) -> None:
    _print(f"TRANSCRIBE_CONFIG_JSON {config_json}")
    for line in config_text.splitlines():
        _print(f"TRANSCRIBE_CONFIG_TEXT {line}")


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
    model_name: str,
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
                model_name,
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
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=cpu_threads_cpu,
                num_workers=1,
                download_root=str(models_dir),
            )
    _print("MODE cpu")
    _print("Loading model (CPU)...")
    return WhisperModel(
        model_name,
        device="cpu",
        compute_type=compute_type,
        cpu_threads=cpu_threads_active,
        num_workers=1,
        download_root=str(models_dir),
    )


def _write_srt(segments: list[SrtSegment], srt_path: Path) -> None:
    srt_content = segments_to_srt(segments)
    srt_path.write_text(srt_content, encoding="utf-8")


def _calculate_punctuation_density(cues: list[object]) -> float:
    cue_texts = [str(getattr(cue, "text", "")) for cue in cues]
    words = sum(len(text.split()) for text in cue_texts)
    punctuation_count = 0
    for text in cue_texts:
        for mark in DEFAULT_PUNCTUATION:
            punctuation_count += text.count(mark)
    return punctuation_count / max(words, 1)


def _build_transcribe_kwargs(
    *,
    language: str,
    language_auto: bool,
    vad_filter: bool,
    vad_min_silence_ms: int,
    initial_prompt: str | None,
) -> dict[str, object]:
    transcribe_kwargs: dict[str, object] = {
        "language": None if language_auto else language,
        "task": "transcribe",
        "beam_size": 5,
        "vad_filter": vad_filter,
        "word_timestamps": True,
    }
    if vad_filter:
        transcribe_kwargs["vad_parameters"] = {
            "min_silence_duration_ms": vad_min_silence_ms
        }
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt
    return transcribe_kwargs


def _run_transcription_attempt(
    *,
    model,
    wav_path: Path,
    transcribe_kwargs: dict[str, object],
    splitter_config: SplitterConfig,
    duration_seconds: float | None,
) -> tuple[list[object], list[object], list[SrtSegment], SplitterStats]:
    segments_iter, info = model.transcribe(str(wav_path), **transcribe_kwargs)
    _print(f"Detected language: {info.language} (prob={info.language_probability:.2f})")

    transcribe_heartbeat_stop = threading.Event()
    transcribe_heartbeat_thread = _start_heartbeat("TRANSCRIBE", transcribe_heartbeat_stop)
    try:
        raw_segments = []
        max_end = 0.0
        last_reported_end = 0.0
        last_reported_percent = 0.0
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
        splitter_stats = SplitterStats()
        cues = split_segments_into_cues(
            raw_segments,
            config=splitter_config,
            stats=splitter_stats,
        )
        segments: list[SrtSegment] = []
        for index, cue in enumerate(cues, start=1):
            segments.append(
                SrtSegment(index=index, start=cue.start, end=cue.end, text=cue.text)
            )
    finally:
        transcribe_heartbeat_stop.set()
        transcribe_heartbeat_thread.join(timeout=1)
    return raw_segments, cues, segments, splitter_stats


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
    parser.add_argument(
        "--model",
        choices=["large-v3", "large-v2"],
        default=DEFAULT_MODEL_NAME,
    )
    parser.add_argument("--vad-filter", dest="vad_filter", action="store_true")
    parser.add_argument("--no-vad-filter", dest="vad_filter", action="store_false")
    parser.set_defaults(vad_filter=True)
    parser.add_argument("--vad-min-silence-ms", type=int, default=400)
    parser.add_argument("--initial-prompt")
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
    parser.add_argument("--punctuation-rescue", dest="punctuation_rescue", action="store_true")
    parser.add_argument(
        "--no-punctuation-rescue",
        dest="punctuation_rescue",
        action="store_false",
    )
    parser.set_defaults(punctuation_rescue=True)
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
        model_dir = models_dir / args.model
        _print(f"MODEL_NAME {args.model}")
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
        language_auto = args.lang == "auto"
        transcribe_kwargs = _build_transcribe_kwargs(
            language=args.lang,
            language_auto=language_auto,
            vad_filter=args.vad_filter,
            vad_min_silence_ms=args.vad_min_silence_ms,
            initial_prompt=args.initial_prompt,
        )
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
        punctuation_rescue = dict(PUNCTUATION_RESCUE_DEFAULTS)
        punctuation_rescue["enabled"] = bool(args.punctuation_rescue)
        config = build_transcription_config(
            model_name=args.model,
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
            language_cli=args.lang,
            language_auto=language_auto,
            initial_prompt=args.initial_prompt,
            srt_formatting={
                "timestamp_format": "HH:MM:SS,mmm",
                "index_start": 1,
                "text_trim": "strip",
                "segment_separator": "blank_line",
            },
            post_splitter=splitter_config.to_dict(),
            audio_extraction=audio_extraction,
            punctuation_rescue=punctuation_rescue,
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
                args.model,
                device,
                compute_type,
                models_dir=models_dir,
                cpu_threads_cpu=cpu_threads_cpu,
                cpu_threads_active=cpu_threads_active,
            )
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)
        duration_seconds = args.duration_seconds
        attempts: list[dict[str, object]] = []
        raw_segments, cues, segments, splitter_stats = _run_transcription_attempt(
            model=model,
            wav_path=wav_path,
            transcribe_kwargs=transcribe_kwargs,
            splitter_config=splitter_config,
            duration_seconds=duration_seconds,
        )
        density = _calculate_punctuation_density(cues)
        attempts.append(
            {
                "attempt": 0,
                "model": args.model,
                "vad_filter": transcribe_kwargs.get("vad_filter"),
                "transcribe_kwargs": transcribe_kwargs,
                "raw_segments": raw_segments,
                "cues": cues,
                "segments": segments,
                "splitter_stats": splitter_stats,
                "density": density,
            }
        )

        rescue_triggered = False
        if punctuation_rescue.get("enabled", True) and density < float(
            punctuation_rescue.get("min_density", 0.03)
        ):
            rescue_triggered = True
            if int(punctuation_rescue.get("max_attempts", 2)) >= 1:
                attempt_vad = not args.vad_filter
                attempt_kwargs = _build_transcribe_kwargs(
                    language=args.lang,
                    language_auto=language_auto,
                    vad_filter=attempt_vad,
                    vad_min_silence_ms=args.vad_min_silence_ms,
                    initial_prompt=args.initial_prompt,
                )
                raw_segments, cues, segments, splitter_stats = _run_transcription_attempt(
                    model=model,
                    wav_path=wav_path,
                    transcribe_kwargs=attempt_kwargs,
                    splitter_config=splitter_config,
                    duration_seconds=duration_seconds,
                )
                attempts.append(
                    {
                        "attempt": 1,
                        "model": args.model,
                        "vad_filter": attempt_kwargs.get("vad_filter"),
                        "transcribe_kwargs": attempt_kwargs,
                        "raw_segments": raw_segments,
                        "cues": cues,
                        "segments": segments,
                        "splitter_stats": splitter_stats,
                        "density": _calculate_punctuation_density(cues),
                    }
                )
            if int(punctuation_rescue.get("max_attempts", 2)) >= 2:
                heartbeat_stop = threading.Event()
                heartbeat_thread = _start_heartbeat("MODEL_LOAD", heartbeat_stop)
                try:
                    rescue_model = _load_model(
                        "large-v2",
                        device,
                        compute_type,
                        models_dir=models_dir,
                        cpu_threads_cpu=cpu_threads_cpu,
                        cpu_threads_active=cpu_threads_active,
                    )
                finally:
                    heartbeat_stop.set()
                    heartbeat_thread.join(timeout=1)
                attempt_kwargs = _build_transcribe_kwargs(
                    language=args.lang,
                    language_auto=language_auto,
                    vad_filter=True,
                    vad_min_silence_ms=400,
                    initial_prompt=args.initial_prompt,
                )
                raw_segments, cues, segments, splitter_stats = _run_transcription_attempt(
                    model=rescue_model,
                    wav_path=wav_path,
                    transcribe_kwargs=attempt_kwargs,
                    splitter_config=splitter_config,
                    duration_seconds=duration_seconds,
                )
                attempts.append(
                    {
                        "attempt": 2,
                        "model": "large-v2",
                        "vad_filter": attempt_kwargs.get("vad_filter"),
                        "transcribe_kwargs": attempt_kwargs,
                        "raw_segments": raw_segments,
                        "cues": cues,
                        "segments": segments,
                        "splitter_stats": splitter_stats,
                        "density": _calculate_punctuation_density(cues),
                    }
                )

        max_density = max(attempt["density"] for attempt in attempts)
        chosen_attempt = attempts[0]
        if attempts[0]["density"] != max_density:
            for attempt in attempts[1:]:
                if attempt["density"] == max_density:
                    chosen_attempt = attempt
                    break

        for attempt in attempts:
            _print(
                "PUNCT_RESCUE "
                f"attempt={attempt['attempt']} "
                f"model={attempt['model']} "
                f"vad={attempt['vad_filter']} "
                f"density={attempt['density']:.4f} "
                f"chosen={attempt is chosen_attempt}"
            )

        transcribe_stats = build_transcription_stats(
            raw_segments=chosen_attempt["raw_segments"],
            cues=chosen_attempt["cues"],
            model_name=str(chosen_attempt["model"]),
            device=device,
            compute_type=compute_type,
            transcribe_kwargs=chosen_attempt["transcribe_kwargs"],
            transcribe_defaults=TRANSCRIBE_DEFAULTS,
            language_cli=args.lang,
            language_auto=language_auto,
            initial_prompt=args.initial_prompt,
            splitter_alignment_failures=chosen_attempt["splitter_stats"].alignment_failures,
            preview_limit=3,
        )
        transcribe_stats["punctuation_density_attempts"] = [
            {
                "attempt": attempt["attempt"],
                "model": attempt["model"],
                "vad_filter": attempt["vad_filter"],
                "density": attempt["density"],
            }
            for attempt in attempts
        ]
        transcribe_stats["punctuation_rescue_triggered"] = rescue_triggered
        transcribe_stats["punctuation_rescue_chosen_attempt"] = chosen_attempt["attempt"]
        _print(f"TRANSCRIBE_STATS_JSON {json.dumps(transcribe_stats, ensure_ascii=True)}")
        _write_srt(chosen_attempt["segments"], srt_path)
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
