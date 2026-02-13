from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import math
import re
import sys
import traceback
from typing import Any, Callable, Optional

from .alignment_words import count_alignment_words_in_cues, tokenize_alignment_words
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


def _normalize_for_match(text: str) -> str:
    cleaned = re.sub(r"[\\.,!?;:\"'\\-–—…()\\[\\]{}]", " ", text)
    return " ".join(cleaned.split()).strip().casefold()


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


def _build_estimated_segments(cues: list[SrtCue], language: str) -> list[dict[str, Any]]:
    estimated_segments: list[dict[str, Any]] = []
    for cue in cues:
        tokens = tokenize_alignment_words(cue.text, language)
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


def _collect_aligned_words(
    aligned_segments: list[dict[str, Any]]
) -> list[dict[str, Optional[float]]]:
    words: list[dict[str, Optional[float]]] = []
    for segment in aligned_segments:
        segment_words = segment.get("words")
        if not isinstance(segment_words, list):
            continue
        for word in segment_words:
            if not isinstance(word, dict):
                continue
            start = word.get("start")
            end = word.get("end")
            text = word.get("word")
            if not _is_real_number(start) or not _is_real_number(end):
                continue
            if text is None:
                continue
            cleaned = str(text).strip()
            if not cleaned:
                continue
            words.append(
                {
                    "word": cleaned,
                    "start": float(start),
                    "end": float(end),
                    "score": float(word["score"]) if word.get("score") is not None else None,
                }
            )
    words.sort(key=lambda item: item["start"] if item["start"] is not None else 0.0)
    return words


def _direct_segment_words(
    aligned_segments: list[dict[str, Any]],
) -> list[list[WordSpan]]:
    cue_words: list[list[WordSpan]] = []
    for segment in aligned_segments:
        words: list[WordSpan] = []
        segment_words = segment.get("words")
        if isinstance(segment_words, list):
            for word in segment_words:
                if not isinstance(word, dict):
                    continue
                start = word.get("start")
                end = word.get("end")
                text = word.get("word")
                if not _is_real_number(start) or not _is_real_number(end):
                    continue
                if text is None:
                    continue
                cleaned = str(text).strip()
                if not cleaned:
                    continue
                words.append(
                    WordSpan(
                        text=cleaned,
                        start=float(start),
                        end=float(end),
                        confidence=float(word["score"]) if word.get("score") is not None else None,
                    )
                )
        cue_words.append(words)
    return cue_words


def _assign_words_to_cues(
    cues: list[SrtCue],
    aligned_words: list[dict[str, Optional[float]]],
    *,
    tolerance: float,
    emit_progress: Optional[Callable[[int, int], None]] = None,
) -> tuple[list[list[WordSpan]], int, int]:
    assignments: list[list[WordSpan]] = []
    assigned_words = 0
    processed_words = 0
    index = 0
    total_words = len(aligned_words)
    for cue in cues:
        cue_words: list[WordSpan] = []
        cue_start = cue.start_seconds
        cue_end = cue.end_seconds
        cue_window_start = cue_start - tolerance
        cue_window_end = cue_end + tolerance
        while index < total_words:
            word_entry = aligned_words[index]
            word_start = word_entry["start"] or 0.0
            word_end = word_entry["end"] or 0.0
            if word_end < cue_window_start:
                index += 1
                processed_words += 1
                continue
            if word_start > cue_window_end:
                break
            cue_words.append(
                WordSpan(
                    text=str(word_entry["word"]),
                    start=float(word_start),
                    end=float(word_end),
                    confidence=word_entry["score"],
                )
            )
            index += 1
            processed_words += 1
            assigned_words += 1
        if emit_progress and total_words:
            emit_progress(min(processed_words, total_words), total_words)
        assignments.append(cue_words)
    if index < total_words:
        processed_words += total_words - index
    if emit_progress and total_words:
        emit_progress(total_words, total_words)
    return assignments, assigned_words, processed_words


def _build_document(
    *,
    cues: list[SrtCue],
    cue_words: list[list[WordSpan]],
    language: str,
    srt_hash: str,
) -> WordTimingDocument:
    created_utc = datetime.now(timezone.utc).isoformat()
    cue_entries: list[CueWordTimings] = []
    for index, cue in enumerate(cues):
        words = cue_words[index] if index < len(cue_words) else []
        cue_entries.append(
            CueWordTimings(
                cue_index=index + 1,
                cue_start=cue.start_seconds,
                cue_end=cue.end_seconds,
                cue_text=cue.text,
                words=words,
            )
        )
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
    planned_total = count_alignment_words_in_cues(cues, config.language)
    if planned_total > 0:
        _emit_words_timed(0, planned_total)
    if len(segments) != len(cues):
        raise ValueError("Mismatch between segments and SRT cues.")
    device = _resolve_device(config.prefer_gpu, config.device)
    import whisperx

    audio = whisperx.load_audio(str(config.wav_path))
    try:
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
    except Exception as exc:  # noqa: BLE001
        # Keep subtitle generation alive when WhisperX align model loading fails in packaged runs.
        _print(f"ALIGN_FALLBACK mode=estimated reason=align_runtime_error detail={exc}")
        aligned_segments = _build_estimated_segments(cues, config.language)
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
            if count_alignment_words_in_cues(cues, config.language) > 0:
                _print("ALIGN_FALLBACK mode=estimated reason=no_word_timings")
                aligned_segments = _build_estimated_segments(cues, config.language)
    srt_hash = compute_srt_sha256(config.srt_path)
    cue_words: list[list[WordSpan]]
    assigned_words = 0
    aligned_words_total = 0
    unassigned_words = 0
    if len(aligned_segments) == len(cues):
        normalized_matches = 0
        for cue, segment in zip(cues, aligned_segments):
            cue_text = _normalize_for_match(cue.text)
            segment_text = _normalize_for_match(str(segment.get("text", "")))
            if cue_text and cue_text == segment_text:
                normalized_matches += 1
        if normalized_matches >= max(1, int(len(cues) * 0.8)):
            _print("ALIGN_STAGE stage=direct_segment_map")
            cue_words = _direct_segment_words(aligned_segments)
            aligned_words_total = sum(len(words) for words in cue_words)
            assigned_words = aligned_words_total
            if aligned_words_total:
                _emit_words_timed(0, aligned_words_total)
                running_total = 0
                for words in cue_words:
                    running_total += len(words)
                    _emit_words_timed(min(running_total, aligned_words_total), aligned_words_total)
        else:
            cue_words = []
    else:
        cue_words = []

    if not cue_words:
        aligned_words = _collect_aligned_words(aligned_segments)
        aligned_words_total = len(aligned_words)
        if aligned_words_total:
            _emit_words_timed(0, aligned_words_total)
        cue_words, assigned_words, processed_words = _assign_words_to_cues(
            cues,
            aligned_words,
            tolerance=0.1,
            emit_progress=_emit_words_timed,
        )
        if aligned_words_total:
            _emit_words_timed(min(processed_words, aligned_words_total), aligned_words_total)
        unassigned_words = aligned_words_total - assigned_words

    cues_with_words = sum(1 for words in cue_words if words)
    align_assign_line = (
        f"ALIGN_ASSIGN cues={len(cues)} "
        f"aligned_words_with_times={aligned_words_total} "
        f"assigned_words={assigned_words} "
        f"cues_with_words={cues_with_words} "
        f"unassigned_words={unassigned_words}"
    )
    _print(align_assign_line)
    document = _build_document(
        cues=cues,
        cue_words=cue_words,
        language=config.language,
        srt_hash=srt_hash,
    )
    total_words = sum(len(cue.words) for cue in document.cues)
    align_output_line = (
        f"ALIGN_OUTPUT total_words={total_words} "
        f"cues={len(document.cues)} cues_with_words={cues_with_words}"
    )
    _print(align_output_line)
    if total_words == 0:
        _eprint(
            "ALIGN_ERROR alignment produced no timed words. "
            f"{align_stats_line} {align_assign_line} {align_output_line}"
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
        _eprint(traceback.format_exc())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
