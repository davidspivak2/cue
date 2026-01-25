from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import math
import re
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

ALIGN_CHUNK_SECONDS = 600.0


def _print(message: str) -> None:
    sys.stdout.buffer.write((message + "\n").encode("utf-8", errors="backslashreplace"))
    sys.stdout.buffer.flush()


def _eprint(message: str) -> None:
    sys.stderr.buffer.write((message + "\n").encode("utf-8", errors="backslashreplace"))
    sys.stderr.buffer.flush()


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


def _count_words(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def _count_words_in_cues(cues: list[SrtCue]) -> int:
    total = 0
    for cue in cues:
        total += _count_words(cue.text)
    return total


def _count_tokens_in_cues(cues: list[SrtCue]) -> int:
    total = 0
    for cue in cues:
        total += len(re.findall(r"\S+", cue.text))
    return total


def _is_real_number(value: object) -> bool:
    if not isinstance(value, (int, float)):
        return False
    return not math.isnan(float(value))


def _summarize_alignment_stats(
    aligned_segments: list[dict[str, Any]],
) -> tuple[int, int, int, int]:
    segments_total = len(aligned_segments)
    segments_with_words = 0
    words_total_raw = 0
    words_with_times = 0
    for segment in aligned_segments:
        words = segment.get("words")
        if not isinstance(words, list):
            continue
        if words:
            segments_with_words += 1
        words_total_raw += len(words)
        for word in words:
            if not isinstance(word, dict):
                continue
            start = word.get("start")
            end = word.get("end")
            if _is_real_number(start) and _is_real_number(end):
                words_with_times += 1
    return segments_total, segments_with_words, words_total_raw, words_with_times


def _segment_has_usable_words(segment: dict[str, Any]) -> bool:
    words = segment.get("words")
    if not isinstance(words, list) or not words:
        return False
    for word in words:
        if not isinstance(word, dict):
            continue
        if word.get("start") is None or word.get("end") is None:
            continue
        return True
    return False


def _has_usable_word_timings(aligned_segments: list[dict[str, Any]]) -> bool:
    return any(_segment_has_usable_words(segment) for segment in aligned_segments)


def _chunk_segments(
    segments: list[dict[str, Any]],
    max_seconds: float,
) -> list[tuple[float, float, list[int]]]:
    if not segments:
        return []
    chunks: list[tuple[float, float, list[int]]] = []
    chunk_start = float(segments[0].get("start", 0.0))
    chunk_end_limit = chunk_start + max_seconds
    current_indices: list[int] = []
    current_end = chunk_start
    for idx, segment in enumerate(segments):
        seg_start = float(segment.get("start", 0.0))
        seg_end = float(segment.get("end", seg_start))
        if current_indices and seg_start >= chunk_end_limit:
            chunks.append(
                (
                    chunk_start,
                    max(current_end, chunk_start + 0.001),
                    current_indices,
                )
            )
            chunk_start = seg_start
            chunk_end_limit = chunk_start + max_seconds
            current_indices = []
            current_end = seg_end
        current_indices.append(idx)
        current_end = max(current_end, seg_end)
    if current_indices:
        chunks.append(
            (
                chunk_start,
                max(current_end, chunk_start + 0.001),
                current_indices,
            )
        )
    return chunks


def _offset_aligned_segment(segment: dict[str, Any], offset: float) -> dict[str, Any]:
    adjusted = dict(segment)
    words = segment.get("words")
    if isinstance(words, list):
        adjusted_words = []
        for word in words:
            if not isinstance(word, dict):
                continue
            adjusted_word = dict(word)
            if adjusted_word.get("start") is not None:
                adjusted_word["start"] = float(adjusted_word["start"]) + offset
            if adjusted_word.get("end") is not None:
                adjusted_word["end"] = float(adjusted_word["end"]) + offset
            adjusted_words.append(adjusted_word)
        adjusted["words"] = adjusted_words
    return adjusted


def _build_estimated_segments(cues: list[SrtCue]) -> list[dict[str, Any]]:
    estimated_segments: list[dict[str, Any]] = []
    for cue in cues:
        tokens = re.findall(r"\S+", cue.text)
        words: list[dict[str, Any]] = []
        duration = max(0.0, cue.end_seconds - cue.start_seconds)
        if tokens:
            if duration > 0:
                weights = [max(len(token), 1) for token in tokens]
                total_weight = sum(weights)
                cursor = cue.start_seconds
                for token, weight in zip(tokens, weights):
                    span = duration * (weight / total_weight)
                    start = cursor
                    end = min(cue.end_seconds, cursor + span)
                    words.append({"word": token, "start": start, "end": end, "score": None})
                    cursor = end
            else:
                for token in tokens:
                    words.append(
                        {
                            "word": token,
                            "start": cue.start_seconds,
                            "end": cue.start_seconds,
                            "score": None,
                        }
                    )
        estimated_segments.append(
            {
                "start": cue.start_seconds,
                "end": cue.end_seconds,
                "text": _normalize_cue_text(cue.text),
                "words": words,
            }
        )
    return estimated_segments


def _emit_words_timed(current: int, total: int) -> None:
    _print(f"ALIGN_WORDS_TIMED current={current} total={total}")


def _build_document(
    *,
    cues: list[SrtCue],
    aligned_segments: list[Optional[dict[str, Any]]],
    language: str,
    srt_hash: str,
    total_words: int,
) -> WordTimingDocument:
    created_utc = datetime.now(timezone.utc).isoformat()
    cue_entries: list[CueWordTimings] = []
    clamp_count = 0
    skipped_words_total = 0
    words_timed = 0
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
        words_timed += _count_words(cue.text)
        if total_words:
            _emit_words_timed(min(words_timed, total_words), total_words)
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
    total_words = _count_words_in_cues(cues)
    if total_words:
        _emit_words_timed(0, total_words)

    device = _resolve_device(config.prefer_gpu, config.device)
    import whisperx

    audio = whisperx.load_audio(str(config.wav_path))
    model_a, metadata = _load_align_model(config.language, device, config.align_model)
    _print("ALIGN_STAGE stage=full_align_start")
    align_result = whisperx.align(
        segments,
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )
    aligned_segments = align_result.get("segments", [])
    (
        segments_total,
        segments_with_words,
        words_total_raw,
        words_with_times,
    ) = _summarize_alignment_stats(aligned_segments)
    align_stats_line = (
        "ALIGN_STATS "
        f"segments_total={segments_total} "
        f"segments_with_words={segments_with_words} "
        f"words_total_raw={words_total_raw} "
        f"words_with_times={words_with_times}"
    )
    _print(align_stats_line)
    mapped_segments = _map_aligned_segments(segments, aligned_segments)
    if not _has_usable_word_timings(aligned_segments):
        _print("ALIGN_FALLBACK mode=chunked_retry")
        sample_rate = getattr(getattr(whisperx, "audio", None), "SAMPLE_RATE", 16000)
        chunked_segments: list[Optional[dict[str, Any]]] = [None] * len(segments)
        chunks = _chunk_segments(segments, ALIGN_CHUNK_SECONDS)
        total_chunks = len(chunks)
        for chunk_index, (chunk_start, chunk_end, indices) in enumerate(chunks, start=1):
            _print(
                "ALIGN_STAGE stage=chunk_align_start "
                f"chunk={chunk_index} total_chunks={total_chunks}"
            )
            sample_start = int(chunk_start * sample_rate)
            sample_end = int(chunk_end * sample_rate)
            sample_end = min(sample_end, audio.shape[0])
            chunk_audio = audio[sample_start:sample_end]
            local_segments = []
            for idx in indices:
                seg = segments[idx]
                local_segments.append(
                    {
                        "start": float(seg.get("start", 0.0)) - chunk_start,
                        "end": float(seg.get("end", 0.0)) - chunk_start,
                        "text": seg.get("text", ""),
                    }
                )
            chunk_result = whisperx.align(
                local_segments,
                model_a,
                metadata,
                chunk_audio,
                device,
                return_char_alignments=False,
            )
            chunk_aligned = chunk_result.get("segments", [])
            mapped_chunk = _map_aligned_segments(local_segments, chunk_aligned)
            for local_index, aligned in enumerate(mapped_chunk):
                if aligned is None:
                    continue
                original_index = indices[local_index]
                chunked_segments[original_index] = _offset_aligned_segment(
                    aligned,
                    chunk_start,
                )
        mapped_segments = chunked_segments
        aligned_segments = [segment for segment in chunked_segments if segment is not None]
        if not _has_usable_word_timings(aligned_segments):
            if _count_tokens_in_cues(cues) > 0:
                _print("ALIGN_FALLBACK mode=estimated reason=no_word_timings")
                mapped_segments = _build_estimated_segments(cues)
                aligned_segments = mapped_segments
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
        total_words=total_words,
    )
    total_words = sum(len(cue.words) for cue in document.cues)
    cues_with_words = sum(1 for cue in document.cues if cue.words)
    align_output_line = (
        f"ALIGN_OUTPUT total_words={total_words} "
        f"cues={len(document.cues)} cues_with_words={cues_with_words}"
    )
    _print(align_output_line)
    if total_words == 0:
        _eprint(
            "ALIGN_ERROR alignment produced no timed words. "
            f"{align_stats_line} {align_output_line}"
        )
        raise RuntimeError("Alignment produced no timed words.")
    save_word_timings_json(config.output_path, document)
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
