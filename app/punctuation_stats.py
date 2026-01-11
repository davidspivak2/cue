from __future__ import annotations

from typing import Iterable
import re

from .srt_splitter import Cue, SegmentLike

DEFAULT_PUNCTUATION = (".", ",", "?", "!", ";", ":", "—", "–", "…")


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def count_words(texts: Iterable[str]) -> int:
    return sum(_word_count(text) for text in texts)


def count_punctuation(
    texts: Iterable[str],
    punctuation: Iterable[str] = DEFAULT_PUNCTUATION,
) -> dict[str, int]:
    counts = {mark: 0 for mark in punctuation}
    for text in texts:
        for mark in counts:
            counts[mark] += text.count(mark)
    return counts


def _build_preview(
    items: Iterable[SegmentLike | Cue],
    limit: int,
) -> list[dict[str, object]]:
    preview = []
    for item in items:
        if len(preview) >= limit:
            break
        preview.append(
            {
                "start": float(getattr(item, "start", 0.0)),
                "end": float(getattr(item, "end", 0.0)),
                "text": str(getattr(item, "text", "")),
            }
        )
    return preview


def build_transcription_stats(
    *,
    raw_segments: Iterable[SegmentLike],
    cues: Iterable[Cue],
    model_name: str,
    device: str,
    compute_type: str,
    transcribe_kwargs: dict[str, object],
    transcribe_defaults: list[str],
    language_cli: str,
    language_auto: bool,
    initial_prompt: str | None,
    splitter_alignment_failures: int,
    preview_limit: int = 3,
) -> dict[str, object]:
    raw_texts = [str(segment.text) for segment in raw_segments]
    cue_texts = [str(cue.text) for cue in cues]
    return {
        "model_name": model_name,
        "device": device,
        "compute_type": compute_type,
        "language": language_cli,
        "language_auto": language_auto,
        "language_transcribe": transcribe_kwargs.get("language"),
        "vad_filter": transcribe_kwargs.get("vad_filter"),
        "vad_parameters": transcribe_kwargs.get("vad_parameters"),
        "initial_prompt": initial_prompt,
        "beam_size": transcribe_kwargs.get("beam_size"),
        "transcribe_kwargs": transcribe_kwargs,
        "transcribe_defaults": transcribe_defaults,
        "punctuation_counts_raw_segments": count_punctuation(raw_texts),
        "punctuation_counts_final_cues": count_punctuation(cue_texts),
        "words_count_raw": count_words(raw_texts),
        "words_count_final": count_words(cue_texts),
        "splitter_alignment_failures": splitter_alignment_failures,
        "raw_segments_preview": _build_preview(raw_segments, preview_limit),
        "final_cues_preview": _build_preview(cues, preview_limit),
    }
