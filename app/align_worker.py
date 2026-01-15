from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Optional

from .srt_utils import compute_srt_sha256, parse_srt_file, SrtCue
from .word_timing_schema import (
    CueWordTimings,
    SCHEMA_VERSION,
    WordSpan,
    WordTimingDocument,
    save_word_timings_json,
)


def _print(message: str) -> None:
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((message + "\n").encode("utf-8", errors="backslashreplace"))
        sys.stdout.buffer.flush()


@dataclass(frozen=True)
class AlignmentConfig:
    wav_path: Path
    srt_path: Path
    output_path: Path
    language: str
    prefer_gpu: bool
    device: Optional[str]
    align_model: Optional[str]


def _normalize_cue_text(text: str) -> str:
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").splitlines()).strip()


def build_segments_from_srt(srt_path: Path) -> list[dict[str, Any]]:
    cues = parse_srt_file(srt_path)
    segments: list[dict[str, Any]] = []
    for cue in cues:
        segments.append(
            {
                "start": cue.start_seconds,
                "end": cue.end_seconds,
                "text": _normalize_cue_text(cue.text),
            }
        )
    return segments


def _resolve_device(prefer_gpu: bool, requested: Optional[str]) -> str:
    if requested:
        return requested
    try:
        import torch
    except Exception:  # noqa: BLE001
        return "cpu"
    if prefer_gpu and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load_align_model(language: str, device: str, align_model: Optional[str]):
    import whisperx

    try:
        return whisperx.load_align_model(
            language_code=language,
            device=device,
            model_name=align_model,
        )
    except Exception as exc:  # noqa: BLE001
        if language != "he" or align_model is not None:
            raise
        _print(f"ALIGN_MODEL_FALLBACK {exc}")
        return whisperx.load_align_model(
            language_code=language,
            device=device,
            model_name="imvladikon/wav2vec2-xls-r-300m-hebrew",
        )


def _segment_key(segment: dict[str, Any]) -> tuple[float, float, str]:
    return (
        float(segment.get("start", 0.0)),
        float(segment.get("end", 0.0)),
        str(segment.get("text", "")),
    )


def _map_aligned_segments(
    segments: list[dict[str, Any]], aligned_segments: list[dict[str, Any]]
) -> list[Optional[dict[str, Any]]]:
    if len(segments) == len(aligned_segments):
        return aligned_segments
    aligned_by_key: dict[tuple[float, float, str], dict[str, Any]] = {
        _segment_key(segment): segment for segment in aligned_segments
    }
    mapped: list[Optional[dict[str, Any]]] = []
    for segment in segments:
        mapped.append(aligned_by_key.get(_segment_key(segment)))
    return mapped


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _build_document(
    *,
    cues: list[SrtCue],
    aligned_segments: list[Optional[dict[str, Any]]],
    language: str,
    srt_hash: str,
) -> WordTimingDocument:
    created_utc = datetime.now(timezone.utc).isoformat()
    cue_entries: list[CueWordTimings] = []
    clamp_count = 0
    skipped_words_total = 0
    for index, cue in enumerate(cues):
        aligned = aligned_segments[index] if index < len(aligned_segments) else None
        words: list[WordSpan] = []
        if aligned and isinstance(aligned.get("words"), list):
            for word in aligned["words"]:
                if not isinstance(word, dict):
                    continue
                start = word.get("start")
                end = word.get("end")
                text = word.get("word")
                if start is None or end is None or text is None:
                    skipped_words_total += 1
                    continue
                start_value = float(start)
                end_value = float(end)
                clamped_start = _clamp(start_value, cue.start_seconds, cue.end_seconds)
                clamped_end = _clamp(end_value, cue.start_seconds, cue.end_seconds)
                if clamped_start != start_value or clamped_end != end_value:
                    clamp_count += 1
                confidence = word.get("score")
                words.append(
                    WordSpan(
                        text=str(text),
                        start=clamped_start,
                        end=clamped_end,
                        confidence=float(confidence) if confidence is not None else None,
                    )
                )
        cue_entries.append(
            CueWordTimings(
                cue_index=index + 1,
                cue_start=cue.start_seconds,
                cue_end=cue.end_seconds,
                cue_text=cue.text,
                words=words,
            )
        )
    if clamp_count:
        _print(f"ALIGN_CLAMPED_WORDS {clamp_count}")
    if skipped_words_total:
        _print(f"ALIGN_SKIPPED_WORDS {skipped_words_total}")
    return WordTimingDocument(
        schema_version=SCHEMA_VERSION,
        created_utc=created_utc,
        language=language,
        srt_sha256=srt_hash,
        cues=cue_entries,
    )


def run_alignment(config: AlignmentConfig) -> WordTimingDocument:
    if not config.wav_path.exists():
        raise FileNotFoundError(f"Missing wav file: {config.wav_path}")
    if not config.srt_path.exists():
        raise FileNotFoundError(f"Missing srt file: {config.srt_path}")

    segments = build_segments_from_srt(config.srt_path)
    cues = parse_srt_file(config.srt_path)
    if len(segments) != len(cues):
        raise ValueError("Mismatch between segments and SRT cues.")

    device = _resolve_device(config.prefer_gpu, config.device)
    import whisperx

    audio = whisperx.load_audio(str(config.wav_path))
    model_a, metadata = _load_align_model(config.language, device, config.align_model)
    align_result = whisperx.align(
        segments,
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )
    aligned_segments = align_result.get("segments", [])
    mapped_segments = _map_aligned_segments(segments, aligned_segments)
    if len(mapped_segments) != len(segments):
        _print(
            "ALIGN_SEGMENT_MISMATCH "
            f"input={len(segments)} aligned={len(aligned_segments)}"
        )
    srt_hash = compute_srt_sha256(config.srt_path)
    document = _build_document(
        cues=cues,
        aligned_segments=mapped_segments,
        language=config.language,
        srt_hash=srt_hash,
    )
    save_word_timings_json(config.output_path, document)
    total_words = sum(len(cue.words) for cue in document.cues)
    _print(f"ALIGN_DONE words={total_words} output={config.output_path}")
    return document


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WhisperX alignment worker")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--srt", required=True)
    parser.add_argument("--word-timings-json", required=True)
    parser.add_argument("--lang", required=True)
    parser.add_argument("--prefer-gpu", action="store_true")
    parser.add_argument("--device")
    parser.add_argument("--align-model")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    config = AlignmentConfig(
        wav_path=Path(args.wav),
        srt_path=Path(args.srt),
        output_path=Path(args.word_timings_json),
        language=args.lang,
        prefer_gpu=bool(args.prefer_gpu),
        device=args.device,
        align_model=args.align_model,
    )
    try:
        _print(
            "ALIGN_START "
            f"wav={config.wav_path} srt={config.srt_path} "
            f"output={config.output_path} lang={config.language} "
            f"device={config.device or 'auto'} align_model={config.align_model or 'default'} "
            f"prefer_gpu={config.prefer_gpu}"
        )
        run_alignment(config)
    except FileNotFoundError as exc:
        _print(f"ALIGN_ERROR {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        _print(f"ALIGN_ERROR {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
