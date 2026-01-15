from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1


class WordTimingValidationError(ValueError):
    pass


@dataclass(frozen=True)
class WordSpan:
    text: str
    start: float
    end: float
    confidence: Optional[float] = None


@dataclass(frozen=True)
class CueWordTimings:
    cue_index: int
    cue_start: float
    cue_end: float
    cue_text: str
    words: list[WordSpan]


@dataclass(frozen=True)
class WordTimingDocument:
    schema_version: int
    created_utc: str
    language: str
    srt_sha256: str
    cues: list[CueWordTimings]


def compute_sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def word_timings_path_for_srt(srt_path: Path) -> Path:
    return srt_path.with_suffix(".word_timings.json")


def load_word_timings_json(path: Path) -> WordTimingDocument:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WordTimingValidationError(f"Missing word timings file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WordTimingValidationError(f"Invalid JSON in word timings file: {path}") from exc

    if not isinstance(raw, dict):
        raise WordTimingValidationError("Word timings JSON must be an object.")

    schema_version = _require_int(raw.get("schema_version"), "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise WordTimingValidationError(
            f"Unsupported word timing schema version: {schema_version}"
        )
    created_utc = _require_iso8601(raw.get("created_utc"), "created_utc")
    language = _require_str(raw.get("language"), "language")
    srt_sha256 = _require_str(raw.get("srt_sha256"), "srt_sha256")
    cues_raw = raw.get("cues")
    if not isinstance(cues_raw, list):
        raise WordTimingValidationError("cues must be a list.")

    cues = [_parse_cue(item, idx) for idx, item in enumerate(cues_raw)]
    return WordTimingDocument(
        schema_version=schema_version,
        created_utc=created_utc,
        language=language,
        srt_sha256=srt_sha256,
        cues=cues,
    )


def save_word_timings_json(path: Path, doc: WordTimingDocument) -> None:
    payload = {
        "schema_version": doc.schema_version,
        "created_utc": doc.created_utc,
        "language": doc.language,
        "srt_sha256": doc.srt_sha256,
        "cues": [
            {
                "cue_index": cue.cue_index,
                "cue_start": cue.cue_start,
                "cue_end": cue.cue_end,
                "cue_text": cue.cue_text,
                "words": [
                    {
                        "text": word.text,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence,
                    }
                    for word in cue.words
                ],
            }
            for cue in doc.cues
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_word_timing_stub(
    *,
    language: str,
    srt_sha256: str,
    cues: list[tuple[int, float, float, str]],
) -> WordTimingDocument:
    created_utc = datetime.now(timezone.utc).isoformat()
    cue_entries = [
        CueWordTimings(
            cue_index=cue_index,
            cue_start=cue_start,
            cue_end=cue_end,
            cue_text=cue_text,
            words=[],
        )
        for cue_index, cue_start, cue_end, cue_text in cues
    ]
    return WordTimingDocument(
        schema_version=SCHEMA_VERSION,
        created_utc=created_utc,
        language=language,
        srt_sha256=srt_sha256,
        cues=cue_entries,
    )


def _parse_cue(item: Any, index: int) -> CueWordTimings:
    if not isinstance(item, dict):
        raise WordTimingValidationError(f"Cue {index} must be an object.")
    cue_index = _require_int(item.get("cue_index"), f"cues[{index}].cue_index")
    cue_start = _require_float(item.get("cue_start"), f"cues[{index}].cue_start")
    cue_end = _require_float(item.get("cue_end"), f"cues[{index}].cue_end")
    cue_text = _require_str(item.get("cue_text"), f"cues[{index}].cue_text")
    words_raw = item.get("words")
    if not isinstance(words_raw, list):
        raise WordTimingValidationError(f"cues[{index}].words must be a list.")
    words = [_parse_word_span(word, index, word_index) for word_index, word in enumerate(words_raw)]
    return CueWordTimings(
        cue_index=cue_index,
        cue_start=cue_start,
        cue_end=cue_end,
        cue_text=cue_text,
        words=words,
    )


def _parse_word_span(item: Any, cue_index: int, word_index: int) -> WordSpan:
    if not isinstance(item, dict):
        raise WordTimingValidationError(
            f"cues[{cue_index}].words[{word_index}] must be an object."
        )
    text = _require_str(item.get("text"), f"cues[{cue_index}].words[{word_index}].text")
    start = _require_float(item.get("start"), f"cues[{cue_index}].words[{word_index}].start")
    end = _require_float(item.get("end"), f"cues[{cue_index}].words[{word_index}].end")
    confidence_value = item.get("confidence")
    if confidence_value is None:
        confidence = None
    else:
        confidence = _require_float(
            confidence_value,
            f"cues[{cue_index}].words[{word_index}].confidence",
        )
    return WordSpan(text=text, start=start, end=end, confidence=confidence)


def _require_str(value: Any, field: str) -> str:
    if isinstance(value, str):
        return value
    raise WordTimingValidationError(f"{field} must be a string.")


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise WordTimingValidationError(f"{field} must be an integer.")
    if isinstance(value, int):
        return value
    raise WordTimingValidationError(f"{field} must be an integer.")


def _require_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise WordTimingValidationError(f"{field} must be a number.")
    if isinstance(value, (int, float)):
        return float(value)
    raise WordTimingValidationError(f"{field} must be a number.")


def _require_iso8601(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise WordTimingValidationError(f"{field} must be a string.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WordTimingValidationError(f"{field} must be ISO8601.") from exc
    return value
