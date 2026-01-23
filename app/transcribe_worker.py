from __future__ import annotations

import argparse
import faulthandler
import importlib
import json
import os
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from dataclasses import dataclass
from tempfile import TemporaryDirectory
from typing import Callable, NoReturn, Optional

from .srt_utils import SrtSegment, segments_to_srt
from .punctuation_stats import (
    DEFAULT_PUNCTUATION,
    build_transcription_stats,
    count_punctuation,
    count_words,
)
from .srt_splitter import (
    SplitApplyThresholds,
    Cue,
    SplitMaxCue,
    SplitterConfig,
    SplitterStats,
    split_segments_into_cues,
)
from .ffmpeg_utils import ensure_ffmpeg_available, get_subprocess_kwargs
from .paths import get_models_dir
from .transcription_config import build_transcription_config

MODEL_NAME = "large-v3"
DEFAULT_MODEL_NAME = MODEL_NAME
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
    "min_words": 80,
    "min_comma_density": 0.01,
    "min_comma_gain": 5,
    "min_total_punct_ratio": 0.5,
    "max_attempts": 2,
}
VAD_GAP_RESCUE_THRESHOLD_SEC = 5.0
VAD_GAP_RESCUE_MAX_GAPS = 5
VAD_GAP_RESCUE_MAX_TOTAL_DURATION_SEC = 60.0


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
    count = _get_cuda_device_count()
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


def _get_cuda_device_count() -> int:
    try:
        ctranslate2 = importlib.import_module("ctranslate2")
        return int(ctranslate2.get_cuda_device_count())
    except Exception:  # noqa: BLE001
        return 0


def _should_use_gpu(prefer_gpu: bool, force_cpu: bool) -> tuple[bool, str]:
    if force_cpu:
        return False, "GPU disabled: --force-cpu"
    if not prefer_gpu:
        return False, "GPU not requested"
    count = _get_cuda_device_count()
    return count > 0, f"CTRANSLATE2_CUDA_DEVICE_COUNT {count}"


def _resolve_compute_type(requested_type: str, device: str) -> str:
    if requested_type != "auto":
        # If the user asked for float16 but we're on CPU, fall back to int8.
        if requested_type == "float16" and device != "cuda":
            return "int8"
        return requested_type
    if device == "cuda":
        return "float16"
    return "int8"


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


def _build_raw_punctuation_summary(raw_segments: list[object]) -> dict[str, float | int]:
    raw_texts = [str(getattr(segment, "text", "")) for segment in raw_segments]
    punctuation_counts = count_punctuation(raw_texts, punctuation=DEFAULT_PUNCTUATION)
    words_count = count_words(raw_texts)
    total_punctuation = sum(punctuation_counts.values())
    comma_count = punctuation_counts.get(",", 0)
    density = total_punctuation / max(words_count, 1)
    return {
        "words_count_raw": words_count,
        "comma_count_raw": comma_count,
        "total_punctuation_count_raw": total_punctuation,
        "punctuation_density_raw": density,
    }


def _choose_best_attempt(
    attempts: list[dict[str, object]],
    *,
    min_comma_gain: int,
    min_total_punct_ratio: float,
    baseline_commas: int,
    best_total_punct: int,
) -> tuple[dict[str, object], bool]:
    allowed_attempts = [
        attempt
        for attempt in attempts[1:]
        if int(attempt["comma_count_raw"]) >= baseline_commas + min_comma_gain
        and int(attempt["total_punctuation_count_raw"])
        >= best_total_punct * min_total_punct_ratio
    ]
    if not allowed_attempts:
        return attempts[0], False
    chosen = max(
        allowed_attempts,
        key=lambda attempt: (
            float(attempt["comma_count_raw"]),
            float(attempt["total_punctuation_count_raw"]),
            float(attempt["punctuation_density_raw"]),
            -int(attempt["attempt"]),
        ),
    )
    return chosen, True


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


@dataclass(frozen=True)
class VadGap:
    idx: int
    start_sec: float
    end_sec: float
    dur_sec: float


def _detect_vad_gaps(
    segments: list[SrtSegment], *, threshold_sec: float
) -> list[VadGap]:
    ordered = sorted(segments, key=lambda seg: (seg.start, seg.end))
    gaps: list[VadGap] = []
    for idx in range(len(ordered) - 1):
        current = ordered[idx]
        upcoming = ordered[idx + 1]
        if (
            current.start < 0
            or current.end < 0
            or upcoming.start < 0
            or upcoming.end < 0
        ):
            continue
        if current.end > upcoming.start:
            continue
        gap_start = current.end
        gap_end = upcoming.start
        gap_dur = gap_end - gap_start
        if gap_dur >= threshold_sec:
            gaps.append(
                VadGap(
                    idx=len(gaps) + 1,
                    start_sec=gap_start,
                    end_sec=gap_end,
                    dur_sec=gap_dur,
                )
            )
    return gaps


def _offset_segments(segments: list[SrtSegment], offset_sec: float) -> list[SrtSegment]:
    return [
        SrtSegment(
            index=segment.index,
            start=segment.start + offset_sec,
            end=segment.end + offset_sec,
            text=segment.text,
        )
        for segment in segments
    ]


def _merge_segments(
    primary_segments: list[SrtSegment], rescued_segments: list[SrtSegment]
) -> list[SrtSegment]:
    merged = primary_segments + rescued_segments
    merged.sort(key=lambda segment: (segment.start, segment.end))
    for idx, segment in enumerate(merged, start=1):
        segment.index = idx
    return merged


def _rescue_text_is_usable(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 2:
        return False
    return any(char.isalnum() for char in stripped)


def _extract_gap_wav(
    wav_path: Path,
    gap_start: float,
    gap_duration: float,
    output_path: Path,
) -> None:
    ffmpeg_path, _, _ = ensure_ffmpeg_available()
    command = [
        str(ffmpeg_path),
        "-y",
        "-ss",
        f"{gap_start:.3f}",
        "-t",
        f"{gap_duration:.3f}",
        "-i",
        str(wav_path),
        str(output_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        **get_subprocess_kwargs(),
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or "ffmpeg failed"
        raise RuntimeError(detail)


def _apply_vad_gap_rescue(
    *,
    model,
    wav_path: Path,
    detection_segments: list[SrtSegment],
    merge_segments: list[SrtSegment],
    transcribe_kwargs: dict[str, object],
    splitter_config: SplitterConfig,
    duration_seconds: float | None,
    enabled: bool,
    should_abort: Optional[Callable[[], bool]] = None,
) -> tuple[list[SrtSegment], dict[str, object]]:
    stats = {
        "enabled": enabled,
        "threshold_sec": VAD_GAP_RESCUE_THRESHOLD_SEC,
        "max_gaps": VAD_GAP_RESCUE_MAX_GAPS,
        "max_total_rescue_duration_sec": VAD_GAP_RESCUE_MAX_TOTAL_DURATION_SEC,
        "gaps_found": 0,
        "gaps_attempted": 0,
        "gaps_restored": 0,
        "total_rescue_duration_sec": 0.0,
        "segments_added": 0,
        "gaps": [],
    }
    if not enabled:
        return merge_segments, stats
    if should_abort and should_abort():
        _print("VAD_GAP_RESCUE_SKIPPED")
        return merge_segments, stats

    gaps = _detect_vad_gaps(
        detection_segments, threshold_sec=VAD_GAP_RESCUE_THRESHOLD_SEC
    )
    stats["gaps_found"] = len(gaps)
    max_gap = max((gap.dur_sec for gap in gaps), default=0.0)
    _print(f"VAD_GAP_RESCUE primary_segments={len(detection_segments)}")
    _print(
        "VAD_GAP_RESCUE "
        f"gaps_found={len(gaps)} max_gap_sec={max_gap:.3f}"
    )
    for gap in gaps:
        _print(
            "VAD_GAP_DETECTED "
            f"idx={gap.idx} start={gap.start_sec:.3f} "
            f"end={gap.end_sec:.3f} dur={gap.dur_sec:.3f}"
        )

    if not gaps:
        return merge_segments, stats

    total_rescue_duration = 0.0
    rescued_segments_total = 0
    gaps_attempted = 0
    gaps_restored = 0
    original_segments = list(merge_segments)
    merged_segments = list(merge_segments)
    rescue_kwargs = dict(transcribe_kwargs)
    rescue_kwargs["vad_filter"] = False
    rescue_kwargs.pop("vad_parameters", None)
    with TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        for gap in gaps:
            if should_abort and should_abort():
                _print("VAD_GAP_RESCUE_SKIPPED")
                return original_segments, stats
            entry = {
                "idx": gap.idx,
                "start_sec": gap.start_sec,
                "end_sec": gap.end_sec,
                "dur_sec": gap.dur_sec,
                "attempted": False,
                "restored": False,
                "rescued_segments": 0,
                "kept_segments": 0,
                "status": "skipped",
                "reason": "not_attempted",
            }
            if gaps_attempted >= VAD_GAP_RESCUE_MAX_GAPS:
                entry["reason"] = "max_gaps"
                _print(
                    "VAD_GAP_RESCUE_SKIPPED "
                    f"idx={gap.idx} reason=max_gaps"
                )
                stats["gaps"].append(entry)
                continue
            if total_rescue_duration + gap.dur_sec > VAD_GAP_RESCUE_MAX_TOTAL_DURATION_SEC:
                entry["reason"] = "max_total_duration"
                _print(
                    "VAD_GAP_RESCUE_SKIPPED "
                    f"idx={gap.idx} reason=max_total_duration"
                )
                stats["gaps"].append(entry)
                continue

            total_rescue_duration += gap.dur_sec
            entry["attempted"] = True
            entry["status"] = "error"
            entry["reason"] = "unknown"
            gaps_attempted += 1
            _print(
                "VAD_GAP_RESCUE_ATTEMPT "
                f"idx={gap.idx} start={gap.start_sec:.3f} end={gap.end_sec:.3f} "
                f"dur={gap.dur_sec:.3f} total_rescue_sec={total_rescue_duration:.3f}"
            )
            try:
                temp_wav = tmp_root / f"vad_gap_{gap.idx}.wav"
                _extract_gap_wav(wav_path, gap.start_sec, gap.dur_sec, temp_wav)
                try:
                    raw_segments, _, rescue_segments, _ = _run_transcription_attempt(
                        model=model,
                        wav_path=temp_wav,
                        transcribe_kwargs=rescue_kwargs,
                        splitter_config=splitter_config,
                        duration_seconds=gap.dur_sec,
                        should_abort=should_abort,
                    )
                except SkipRequested:
                    _print("VAD_GAP_RESCUE_SKIPPED")
                    return original_segments, stats
                entry["rescued_segments"] = len(rescue_segments)
                kept = [
                    segment
                    for segment in rescue_segments
                    if _rescue_text_is_usable(segment.text)
                ]
                entry["kept_segments"] = len(kept)
                kept_chars = sum(len(segment.text.strip()) for segment in kept)
                if not raw_segments:
                    entry["status"] = "no_speech"
                    entry["reason"] = "no_segments"
                elif not kept:
                    entry["status"] = "rejected"
                    entry["reason"] = "filtered"
                else:
                    entry["status"] = "restored"
                    entry["reason"] = "segments_added"
                    entry["restored"] = True
                    gaps_restored += 1
                    rescued_segments_total += len(kept)
                    offset_segments = _offset_segments(kept, gap.start_sec)
                    merged_segments.extend(offset_segments)
                _print(
                    "VAD_GAP_RESCUE_RESULT "
                    f"idx={gap.idx} rescued_segments={entry['rescued_segments']} "
                    f"kept_segments={entry['kept_segments']} kept_chars={kept_chars} "
                    f"status={entry['status']} reason={entry['reason']}"
                )
            except Exception as exc:  # noqa: BLE001
                entry["status"] = "error"
                entry["reason"] = str(exc).replace("\n", " ")
                _print(
                    "VAD_GAP_RESCUE_RESULT "
                    f"idx={gap.idx} rescued_segments=0 kept_segments=0 kept_chars=0 "
                    f"status=error reason={entry['reason']}"
                )
            stats["gaps"].append(entry)

    merged_segments = _merge_segments(merged_segments, [])
    stats["gaps_attempted"] = gaps_attempted
    stats["gaps_restored"] = gaps_restored
    stats["total_rescue_duration_sec"] = total_rescue_duration
    stats["segments_added"] = rescued_segments_total
    _print(
        "VAD_GAP_RESCUE_SUMMARY "
        f"gaps_found={stats['gaps_found']} attempted={gaps_attempted} "
        f"restored={gaps_restored} total_rescue_sec={total_rescue_duration:.3f} "
        f"segments_added={rescued_segments_total}"
    )
    return merged_segments, stats


class SkipRequested(Exception):
    pass


def _serialize_raw_segments(raw_segments: list[object]) -> list[dict[str, object]]:
    return [
        {
            "start": float(getattr(segment, "start", 0.0)),
            "end": float(getattr(segment, "end", 0.0)),
            "text": str(getattr(segment, "text", "")),
        }
        for segment in raw_segments
    ]


def _serialize_cues(cues: list[Cue]) -> list[dict[str, object]]:
    return [
        {
            "start": float(cue.start),
            "end": float(cue.end),
            "text": str(cue.text),
        }
        for cue in cues
    ]


def _serialize_srt_segments(segments: list[SrtSegment]) -> list[dict[str, object]]:
    return [
        {
            "index": int(segment.index),
            "start": float(segment.start),
            "end": float(segment.end),
            "text": str(segment.text),
        }
        for segment in segments
    ]


def _deserialize_raw_segments(payload: list[dict[str, object]]) -> list[SrtSegment]:
    raw_segments: list[SrtSegment] = []
    for idx, segment in enumerate(payload, start=1):
        raw_segments.append(
            SrtSegment(
                index=idx,
                start=float(segment.get("start", 0.0)),
                end=float(segment.get("end", 0.0)),
                text=str(segment.get("text", "")),
            )
        )
    return raw_segments


def _deserialize_cues(payload: list[dict[str, object]]) -> list[Cue]:
    return [
        Cue(
            start=float(cue.get("start", 0.0)),
            end=float(cue.get("end", 0.0)),
            text=str(cue.get("text", "")),
        )
        for cue in payload
    ]


def _deserialize_srt_segments(payload: list[dict[str, object]]) -> list[SrtSegment]:
    return [
        SrtSegment(
            index=int(segment.get("index", idx)),
            start=float(segment.get("start", 0.0)),
            end=float(segment.get("end", 0.0)),
            text=str(segment.get("text", "")),
        )
        for idx, segment in enumerate(payload, start=1)
    ]


def _run_transcription_attempt(
    *,
    model,
    wav_path: Path,
    transcribe_kwargs: dict[str, object],
    splitter_config: SplitterConfig,
    duration_seconds: float | None,
    should_abort: Optional[Callable[[], bool]] = None,
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
            if should_abort and should_abort():
                raise SkipRequested()
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


def _run_punctuation_child_attempt(
    *,
    model_name: str,
    device: str,
    compute_type: str,
    models_dir: Path,
    cpu_threads_cpu: int,
    cpu_threads_active: int,
    wav_path: Path,
    transcribe_kwargs: dict[str, object],
    splitter_config: SplitterConfig,
    duration_seconds: float | None,
    attempt_number: int,
    output_path: Path,
    force_cpu: bool,
) -> dict[str, object]:
    heartbeat_stop = threading.Event()
    heartbeat_thread = _start_heartbeat("MODEL_LOAD", heartbeat_stop)
    try:
        model = _load_model(
            model_name,
            device,
            compute_type,
            models_dir=models_dir,
            cpu_threads_cpu=cpu_threads_cpu,
            cpu_threads_active=cpu_threads_active,
        )
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1)

    raw_segments, cues, segments, splitter_stats = _run_transcription_attempt(
        model=model,
        wav_path=wav_path,
        transcribe_kwargs=transcribe_kwargs,
        splitter_config=splitter_config,
        duration_seconds=duration_seconds,
    )
    raw_summary = _build_raw_punctuation_summary(raw_segments)
    payload = {
        "attempt": attempt_number,
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
        "force_cpu": force_cpu,
        "vad_filter": transcribe_kwargs.get("vad_filter"),
        "transcribe_kwargs": transcribe_kwargs,
        "raw_segments": _serialize_raw_segments(raw_segments),
        "cues": _serialize_cues(cues),
        "segments": _serialize_srt_segments(segments),
        "splitter_stats": {"alignment_failures": splitter_stats.alignment_failures},
        **raw_summary,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def _load_punctuation_child_output(payload: dict[str, object]) -> dict[str, object]:
    raw_segments_payload = payload.get("raw_segments")
    cues_payload = payload.get("cues")
    segments_payload = payload.get("segments")
    if not isinstance(raw_segments_payload, list):
        raise ValueError("Invalid child payload: raw_segments missing.")
    if not isinstance(cues_payload, list):
        raise ValueError("Invalid child payload: cues missing.")
    if not isinstance(segments_payload, list):
        raise ValueError("Invalid child payload: segments missing.")
    splitter_payload = payload.get("splitter_stats") or {}
    alignment_failures = int(splitter_payload.get("alignment_failures", 0) or 0)
    payload["raw_segments"] = _deserialize_raw_segments(raw_segments_payload)
    payload["cues"] = _deserialize_cues(cues_payload)
    payload["segments"] = _deserialize_srt_segments(segments_payload)
    payload["splitter_stats"] = SplitterStats(alignment_failures=alignment_failures)
    return payload


def _run_punctuation_child_process(
    *,
    attempt_number: int,
    wav_path: Path,
    srt_path: Path,
    lang: str,
    model_name: str,
    device: str,
    compute_type: str,
    vad_filter: bool,
    vad_min_silence_ms: int,
    initial_prompt: str | None,
    duration_seconds: float | None,
    should_abort: Callable[[], bool],
    force_cpu: bool,
) -> tuple[Optional[dict[str, object]], bool]:
    with TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / f"punct_rescue_attempt_{attempt_number}.json"
        if getattr(sys, "frozen", False):
            command = [sys.executable]
        else:
            command = [sys.executable, "-m", "app.transcribe_worker"]
        command += [
            "--wav",
            str(wav_path),
            "--srt",
            str(srt_path),
            "--lang",
            lang,
            "--model",
            model_name,
            "--device",
            device,
            "--compute-type",
            compute_type,
            "--vad-min-silence-ms",
            str(vad_min_silence_ms),
            "--punctuation-rescue",
            "off",
            "--punct-child-attempt",
            str(attempt_number),
            "--punct-child-output-json",
            str(output_path),
        ]
        if force_cpu:
            command.append("--force-cpu")
        if vad_filter:
            command.append("--vad-filter")
        else:
            command.append("--no-vad-filter")
        if initial_prompt:
            command += ["--initial-prompt", initial_prompt]
        if duration_seconds:
            command += ["--duration-seconds", f"{duration_seconds:.2f}"]

        stdout_tail: list[str] = []
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **get_subprocess_kwargs(),
        )

        def _drain_stdout() -> None:
            if process.stdout is None:
                return
            for line in process.stdout:
                if len(stdout_tail) < 50:
                    stdout_tail.append(line.strip())
                else:
                    stdout_tail.pop(0)
                    stdout_tail.append(line.strip())

        stdout_thread = threading.Thread(target=_drain_stdout, daemon=True)
        stdout_thread.start()

        while process.poll() is None:
            if should_abort():
                process.terminate()
                try:
                    process.wait(timeout=0.4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
                stdout_thread.join(timeout=1)
                return None, True
            time.sleep(0.05)

        stdout_thread.join(timeout=1)
        if process.returncode != 0:
            _print(
                f"PUNCT_RESCUE_CHILD_FAILED attempt={attempt_number} "
                f"code={process.returncode}"
            )
            return None, False

        if not output_path.exists():
            _print(f"PUNCT_RESCUE_CHILD_FAILED attempt={attempt_number} code=missing_output")
            return None, False
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _print(f"PUNCT_RESCUE_CHILD_FAILED attempt={attempt_number} code=invalid_output")
            return None, False
        return _load_punctuation_child_output(payload), False


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
        default=MODEL_NAME,
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
    parser.add_argument(
        "--punctuation-rescue",
        choices=["on", "off"],
        default="on",
    )
    parser.add_argument("--punct-child-attempt", type=int)
    parser.add_argument("--punct-child-output-json")
    parser.add_argument("--control-dir")
    args = parser.parse_args(argv)

    if args.punct_child_attempt is not None and not args.punct_child_output_json:
        parser.error("--punct-child-output-json is required with --punct-child-attempt.")
    if not args.print_transcribe_config and (not args.wav or not args.srt):
        parser.error("--wav and --srt are required unless --print-transcribe-config is used.")

    wav_path = Path(args.wav) if args.wav else None
    srt_path = Path(args.srt) if args.srt else None
    control_dir = Path(args.control_dir) if args.control_dir else None

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
        vad_gap_rescue_enabled = bool(transcribe_kwargs.get("vad_filter", False))
        _print(
            "VAD_GAP_RESCUE "
            f"enabled={str(vad_gap_rescue_enabled).lower()} "
            f"threshold_sec={VAD_GAP_RESCUE_THRESHOLD_SEC:.1f} "
            f"max_gaps={VAD_GAP_RESCUE_MAX_GAPS} "
            f"max_total_rescue_sec={VAD_GAP_RESCUE_MAX_TOTAL_DURATION_SEC:.1f}"
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
        punctuation_rescue["enabled"] = args.punctuation_rescue == "on"
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
        if args.punct_child_attempt is not None:
            output_path = Path(args.punct_child_output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            _run_punctuation_child_attempt(
                model_name=args.model,
                device=device,
                compute_type=compute_type,
                models_dir=models_dir,
                cpu_threads_cpu=cpu_threads_cpu,
                cpu_threads_active=cpu_threads_active,
                wav_path=wav_path,
                transcribe_kwargs=transcribe_kwargs,
                splitter_config=splitter_config,
                duration_seconds=args.duration_seconds,
                attempt_number=args.punct_child_attempt,
                output_path=output_path,
                force_cpu=force_cpu,
            )
            if hard_exit:
                _hard_exit(0)
            return 0
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

        def _should_skip(control_root: Optional[Path], filename: str) -> bool:
            if not control_root:
                return False
            return (control_root / filename).exists()

        def _should_skip_punctuation() -> bool:
            return _should_skip(control_dir, "skip_punct.flag")

        def _should_skip_gaps() -> bool:
            return _should_skip(control_dir, "skip_gaps.flag")
        attempts: list[dict[str, object]] = []
        raw_segments, cues, segments, splitter_stats = _run_transcription_attempt(
            model=model,
            wav_path=wav_path,
            transcribe_kwargs=transcribe_kwargs,
            splitter_config=splitter_config,
            duration_seconds=duration_seconds,
        )
        raw_summary = _build_raw_punctuation_summary(raw_segments)
        attempts.append(
            {
                "attempt": 0,
                "model": args.model,
                "device": device,
                "compute_type": compute_type,
                "force_cpu": args.force_cpu,
                "vad_filter": transcribe_kwargs.get("vad_filter"),
                "transcribe_kwargs": transcribe_kwargs,
                "raw_segments": raw_segments,
                "cues": cues,
                "segments": segments,
                "splitter_stats": splitter_stats,
                **raw_summary,
            }
        )

        rescue_triggered = False
        rescue_reason = "disabled"
        rescue_enabled = punctuation_rescue.get("enabled", True)
        min_words = int(punctuation_rescue.get("min_words", 80))
        min_comma_density = float(punctuation_rescue.get("min_comma_density", 0.01))
        min_comma_gain = int(punctuation_rescue.get("min_comma_gain", 5))
        min_total_punct_ratio = float(
            punctuation_rescue.get("min_total_punct_ratio", 0.5)
        )
        words_count_raw = int(attempts[0]["words_count_raw"])
        comma_count_raw = int(attempts[0]["comma_count_raw"])
        comma_density_raw = comma_count_raw / max(words_count_raw, 1)
        if rescue_enabled:
            if words_count_raw < min_words:
                rescue_reason = "skipped_short_clip"
            elif comma_density_raw >= min_comma_density:
                rescue_reason = "comma_density_ok"
            else:
                rescue_triggered = True
                rescue_reason = "comma_density_low"
        if rescue_triggered:
            max_attempts = int(punctuation_rescue.get("max_attempts", 2))
            if _should_skip_punctuation():
                rescue_triggered = False
                rescue_reason = "skipped_by_user"
                _print("PUNCT_RESCUE_SKIPPED")
            elif max_attempts >= 1:
                _print("PUNCT_RESCUE_START attempt=1")
                attempt_vad = not args.vad_filter
                attempt_kwargs = _build_transcribe_kwargs(
                    language=args.lang,
                    language_auto=language_auto,
                    vad_filter=attempt_vad,
                    vad_min_silence_ms=args.vad_min_silence_ms,
                    initial_prompt=args.initial_prompt,
                )
                try:
                    raw_segments, cues, segments, splitter_stats = _run_transcription_attempt(
                        model=model,
                        wav_path=wav_path,
                        transcribe_kwargs=attempt_kwargs,
                        splitter_config=splitter_config,
                        duration_seconds=duration_seconds,
                        should_abort=_should_skip_punctuation,
                    )
                except SkipRequested:
                    rescue_triggered = False
                    rescue_reason = "skipped_by_user"
                    _print("PUNCT_RESCUE_SKIPPED")
                else:
                    raw_summary = _build_raw_punctuation_summary(raw_segments)
                    attempts.append(
                        {
                            "attempt": 1,
                            "model": args.model,
                            "device": device,
                            "compute_type": compute_type,
                            "force_cpu": args.force_cpu,
                            "vad_filter": attempt_kwargs.get("vad_filter"),
                            "transcribe_kwargs": attempt_kwargs,
                            "raw_segments": raw_segments,
                            "cues": cues,
                            "segments": segments,
                            "splitter_stats": splitter_stats,
                            **raw_summary,
                        }
                    )
            for attempt_number in range(2, max_attempts + 1):
                if not rescue_triggered:
                    break
                if _should_skip_punctuation():
                    rescue_triggered = False
                    rescue_reason = "skipped_by_user"
                    _print("PUNCT_RESCUE_SKIPPED")
                    break
                _print(f"PUNCT_RESCUE_START attempt={attempt_number}")
                child_payload, skipped = _run_punctuation_child_process(
                    attempt_number=attempt_number,
                    wav_path=wav_path,
                    srt_path=srt_path,
                    lang=args.lang,
                    model_name="large-v2",
                    device="cpu",
                    compute_type="float32",
                    vad_filter=True,
                    vad_min_silence_ms=400,
                    initial_prompt=args.initial_prompt,
                    duration_seconds=duration_seconds,
                    should_abort=_should_skip_punctuation,
                    force_cpu=True,
                )
                if skipped:
                    rescue_triggered = False
                    rescue_reason = "skipped_by_user"
                    _print("PUNCT_RESCUE_SKIPPED")
                    break
                if child_payload:
                    attempts.append(child_payload)

        baseline_commas = int(attempts[0]["comma_count_raw"])
        baseline_total_punct = int(attempts[0]["total_punctuation_count_raw"])
        best_total_punct = max(
            int(attempt["total_punctuation_count_raw"]) for attempt in attempts
        )
        chosen_attempt, gate_passed = _choose_best_attempt(
            attempts,
            min_comma_gain=min_comma_gain,
            min_total_punct_ratio=min_total_punct_ratio,
            baseline_commas=baseline_commas,
            best_total_punct=best_total_punct,
        )
        if not rescue_enabled:
            gate_reason = "disabled"
        elif not rescue_triggered:
            gate_reason = "not_triggered"
        elif len(attempts) == 1:
            gate_reason = "baseline_kept_no_alternative"
        elif gate_passed:
            gate_reason = "non_baseline_chosen_gate_passed"
        else:
            gate_reason = "baseline_kept_gate_failed"

        for attempt in attempts:
            _print(
                "PUNCT_RESCUE "
                f"attempt={attempt['attempt']} "
                f"model={attempt['model']} "
                f"vad={attempt['vad_filter']} "
                f"commas={attempt['comma_count_raw']} "
                f"punct={attempt['total_punctuation_count_raw']} "
                f"density={attempt['punctuation_density_raw']:.4f} "
                f"chosen={attempt is chosen_attempt}"
            )
        if rescue_triggered:
            _print(
                "PUNCT_RESCUE_DONE "
                f"chosen_attempt={chosen_attempt['attempt']} attempts_ran={len(attempts)}"
            )

        vad_gap_segments = chosen_attempt["segments"]
        vad_gap_stats = {
            "enabled": False,
            "threshold_sec": VAD_GAP_RESCUE_THRESHOLD_SEC,
            "max_gaps": VAD_GAP_RESCUE_MAX_GAPS,
            "max_total_rescue_duration_sec": VAD_GAP_RESCUE_MAX_TOTAL_DURATION_SEC,
            "gaps_found": 0,
            "gaps_attempted": 0,
            "gaps_restored": 0,
            "total_rescue_duration_sec": 0.0,
            "segments_added": 0,
            "gaps": [],
        }
        if vad_gap_rescue_enabled and bool(attempts[0]["vad_filter"]):
            if not _should_skip_gaps():
                _print("VAD_GAP_RESCUE_START")
                vad_gap_segments, vad_gap_stats = _apply_vad_gap_rescue(
                    model=model,
                    wav_path=wav_path,
                    detection_segments=attempts[0]["segments"],
                    merge_segments=vad_gap_segments,
                    transcribe_kwargs=chosen_attempt["transcribe_kwargs"],
                    splitter_config=splitter_config,
                    duration_seconds=duration_seconds,
                    enabled=vad_gap_rescue_enabled,
                    should_abort=_should_skip_gaps,
                )
                _print(
                    "VAD_GAP_RESCUE_DONE "
                    f"gaps_found={vad_gap_stats['gaps_found']} "
                    f"gaps_restored={vad_gap_stats['gaps_restored']}"
                )
            else:
                _print("VAD_GAP_RESCUE_SKIPPED")
        transcribe_stats = build_transcription_stats(
            raw_segments=chosen_attempt["raw_segments"],
            cues=chosen_attempt["cues"],
            model_name=str(chosen_attempt["model"]),
            device=str(chosen_attempt["device"]),
            compute_type=str(chosen_attempt["compute_type"]),
            transcribe_kwargs=chosen_attempt["transcribe_kwargs"],
            transcribe_defaults=TRANSCRIBE_DEFAULTS,
            language_cli=args.lang,
            language_auto=language_auto,
            initial_prompt=args.initial_prompt,
            splitter_alignment_failures=chosen_attempt["splitter_stats"].alignment_failures,
            preview_limit=3,
        )
        transcribe_stats["punctuation_rescue_enabled"] = rescue_enabled
        transcribe_stats["punctuation_rescue_triggered"] = rescue_triggered
        transcribe_stats["punctuation_rescue_reason"] = rescue_reason
        transcribe_stats["punctuation_rescue_min_words"] = min_words
        transcribe_stats["punctuation_rescue_min_comma_density"] = min_comma_density
        transcribe_stats["punctuation_rescue_min_comma_gain"] = min_comma_gain
        transcribe_stats["punctuation_rescue_min_total_punct_ratio"] = (
            min_total_punct_ratio
        )
        transcribe_stats["punctuation_rescue_gate_passed"] = gate_passed
        transcribe_stats["punctuation_rescue_gate_reason"] = gate_reason
        transcribe_stats["punctuation_rescue_baseline_comma_count_raw"] = (
            baseline_commas
        )
        transcribe_stats["punctuation_rescue_baseline_total_punctuation_count_raw"] = (
            baseline_total_punct
        )
        transcribe_stats["punctuation_rescue_best_total_punctuation_count_raw"] = (
            best_total_punct
        )
        transcribe_stats["punctuation_rescue_comma_density_raw"] = comma_density_raw
        transcribe_stats["punctuation_rescue_comma_count_raw"] = comma_count_raw
        transcribe_stats["punctuation_rescue_words_count_raw"] = words_count_raw
        transcribe_stats["punctuation_rescue_attempts_ran"] = len(attempts)
        transcribe_stats["punctuation_rescue_attempts_executed_total"] = len(attempts)
        transcribe_stats["punctuation_rescue_retry_attempts_executed"] = max(
            0, len(attempts) - 1
        )
        transcribe_stats["punctuation_rescue_chosen_attempt"] = chosen_attempt["attempt"]
        transcribe_stats["punctuation_rescue_mode"] = "on" if rescue_enabled else "off"
        transcribe_stats["punctuation_rescue_attempts"] = [
            {
                "attempt_index": attempt["attempt"],
                "model_name": attempt["model"],
                "device": attempt["device"],
                "compute_type": attempt["compute_type"],
                "vad_filter": attempt["vad_filter"],
                "force_cpu": attempt["force_cpu"],
                "words_count_raw": attempt["words_count_raw"],
                "comma_count_raw": attempt["comma_count_raw"],
                "total_punctuation_count_raw": attempt["total_punctuation_count_raw"],
                "punctuation_density_raw": attempt["punctuation_density_raw"],
            }
            for attempt in attempts
        ]
        transcribe_stats["vad_gap_rescue"] = vad_gap_stats
        _print(f"TRANSCRIBE_STATS_JSON {json.dumps(transcribe_stats, ensure_ascii=True)}")
        _write_srt(vad_gap_segments, srt_path)
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
