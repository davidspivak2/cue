from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.ass_karaoke import (
    KaraokeCue,
    build_ass_document_with_karaoke_fallback,
    build_ass_karaoke_document,
    build_ass_karaoke_document_with_stats,
    build_style_config_from_subtitle_style,
    highlight_text_for_word_index,
)
from app.ass_render import ass_color_from_hex, build_ass_document
from app.srt_utils import compute_srt_sha256
from app.subtitle_style import PRESET_DEFAULT, preset_defaults
from app.word_timing_schema import CueWordTimings, WordSpan, WordTimingDocument, save_word_timings_json


def _build_word_timing_doc(
    *,
    srt_sha256: str,
    cue_index: int,
    cue_start: float,
    cue_end: float,
    cue_text: str,
    words: list[WordSpan],
) -> WordTimingDocument:
    return WordTimingDocument(
        schema_version=1,
        created_utc=datetime.now(timezone.utc).isoformat(),
        language="he",
        srt_sha256=srt_sha256,
        cues=[
            CueWordTimings(
                cue_index=cue_index,
                cue_start=cue_start,
                cue_end=cue_end,
                cue_text=cue_text,
                words=words,
            )
        ],
    )


def _parse_ass_times(line: str) -> tuple[str, str, int]:
    parts = line.split(",", 9)
    layer = int(parts[0].split(":", 1)[1])
    return parts[1], parts[2], layer


def _ass_time_to_seconds(value: str) -> float:
    hours, minutes, rest = value.split(":")
    seconds, centiseconds = rest.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(centiseconds) / 100


def test_karaoke_structure_and_ordering() -> None:
    cues = [KaraokeCue(index=0, start_sec=0.0, end_sec=1.0, text="שלום עולם יפה")]
    doc = _build_word_timing_doc(
        srt_sha256="stub",
        cue_index=0,
        cue_start=0.0,
        cue_end=1.0,
        cue_text="שלום עולם יפה",
        words=[
            WordSpan(text="שלום", start=0.1, end=0.3),
            WordSpan(text="עולם", start=0.3, end=0.6),
            WordSpan(text="יפה", start=0.6, end=0.9),
        ],
    )
    style = build_style_config_from_subtitle_style(
        preset_defaults(PRESET_DEFAULT),
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    result = build_ass_karaoke_document_with_stats(cues, doc, style)
    ass_text = result.ass_text

    assert "[Script Info]" in ass_text
    assert "[V4+ Styles]" in ass_text
    assert "[Events]" in ass_text
    dialogue_lines = [line for line in ass_text.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogue_lines) == 4
    assert result.highlight_event_count == 3

    starts = [
        _ass_time_to_seconds(_parse_ass_times(line)[0])
        for line in dialogue_lines
    ]
    assert starts == sorted(starts)


def test_highlight_text_for_word_index_with_punctuation() -> None:
    normal_color = ass_color_from_hex("#FFFFFF")
    highlight_color = ass_color_from_hex("#00FF00")
    normal_tag = f"{{\\c{normal_color}&}}"
    highlight_tag = f"{{\\c{highlight_color}&}}"

    plain = "שלום עולם יפה"
    output = highlight_text_for_word_index(plain, 1, normal_color, highlight_color)
    assert output.startswith(normal_tag)
    assert f"{highlight_tag}עולם{normal_tag}" in output
    assert output.count(highlight_tag) == 1

    punctuated = "שלום, עולם! יפה"
    output_punct = highlight_text_for_word_index(punctuated, 1, normal_color, highlight_color)
    assert f"{highlight_tag}עולם{normal_tag}" in output_punct


def test_rtl_wrapper_matches_static_base() -> None:
    cues = [KaraokeCue(index=0, start_sec=0.0, end_sec=1.0, text="שלום עולם")]
    doc = _build_word_timing_doc(
        srt_sha256="stub",
        cue_index=0,
        cue_start=0.0,
        cue_end=1.0,
        cue_text="שלום עולם",
        words=[WordSpan(text="שלום", start=0.1, end=0.2)],
    )
    style = build_style_config_from_subtitle_style(
        preset_defaults(PRESET_DEFAULT),
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    static_ass = build_ass_document(
        [{"start_s": 0.0, "end_s": 1.0, "text": "שלום עולם"}],
        style_config=style,
    )
    karaoke_ass = build_ass_karaoke_document(cues, doc, style)
    static_payload = [line for line in static_ass.splitlines() if line.startswith("Dialogue:")][
        0
    ].split(",", 9)[-1]
    karaoke_payload = [
        line for line in karaoke_ass.splitlines() if line.startswith("Dialogue:")
    ][0].split(",", 9)[-1]
    assert karaoke_payload[0] == static_payload[0]
    assert karaoke_payload[-1] == static_payload[-1]


def test_time_offset_and_window() -> None:
    cues = [KaraokeCue(index=0, start_sec=10.0, end_sec=12.0, text="שלום עולם")]
    doc = _build_word_timing_doc(
        srt_sha256="stub",
        cue_index=0,
        cue_start=10.0,
        cue_end=12.0,
        cue_text="שלום עולם",
        words=[
            WordSpan(text="שלום", start=10.1, end=10.3),
            WordSpan(text="עולם", start=10.3, end=10.8),
        ],
    )
    style = build_style_config_from_subtitle_style(
        preset_defaults(PRESET_DEFAULT),
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    ass_text = build_ass_karaoke_document(
        cues,
        doc,
        style,
        time_offset_sec=10.0,
        time_window=(0.0, 2.0),
    )
    dialogue_lines = [line for line in ass_text.splitlines() if line.startswith("Dialogue:")]
    times = [_parse_ass_times(line) for line in dialogue_lines]
    base_times = next(item for item in times if item[2] == 0)
    word_times = [item for item in times if item[2] == 1]
    base_start = _ass_time_to_seconds(base_times[0])
    base_end = _ass_time_to_seconds(base_times[1])
    word_start = _ass_time_to_seconds(word_times[0][0])
    word_end = _ass_time_to_seconds(word_times[0][1])
    assert abs(base_start - 0.0) < 0.02
    assert abs(base_end - 2.0) < 0.02
    assert abs(word_start - 0.1) < 0.02
    assert abs(word_end - 0.3) < 0.02


def test_fallback_behavior(tmp_path: Path) -> None:
    style = build_style_config_from_subtitle_style(
        preset_defaults(PRESET_DEFAULT),
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    cue_text = "שלום עולם"
    cues = [KaraokeCue(index=0, start_sec=0.0, end_sec=1.0, text=cue_text)]
    empty_doc = _build_word_timing_doc(
        srt_sha256="stub",
        cue_index=0,
        cue_start=0.0,
        cue_end=1.0,
        cue_text=cue_text,
        words=[],
    )
    result = build_ass_karaoke_document_with_stats(cues, empty_doc, style)
    dialogue_lines = [line for line in result.ass_text.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogue_lines) == 1
    assert result.highlight_event_count == 0

    srt_path = tmp_path / "karaoke_test.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nשלום עולם\n", encoding="utf-8")
    word_timings_path = tmp_path / "karaoke_test.word_timings.json"
    stale_doc = _build_word_timing_doc(
        srt_sha256="mismatch",
        cue_index=0,
        cue_start=0.0,
        cue_end=1.0,
        cue_text=cue_text,
        words=[],
    )
    save_word_timings_json(word_timings_path, stale_doc)
    decision = build_ass_document_with_karaoke_fallback(
        cues,
        srt_path=srt_path,
        word_timings_path=word_timings_path,
        style_config=style,
    )
    assert decision.karaoke_enabled is False
    assert decision.reason == "stale"

    fresh_hash = compute_srt_sha256(srt_path)
    no_words_doc = _build_word_timing_doc(
        srt_sha256=fresh_hash,
        cue_index=0,
        cue_start=0.0,
        cue_end=1.0,
        cue_text=cue_text,
        words=[],
    )
    save_word_timings_json(word_timings_path, no_words_doc)
    decision = build_ass_document_with_karaoke_fallback(
        cues,
        srt_path=srt_path,
        word_timings_path=word_timings_path,
        style_config=style,
    )
    assert decision.karaoke_enabled is False
    assert decision.reason == "no words"

    with_words_doc = _build_word_timing_doc(
        srt_sha256=fresh_hash,
        cue_index=0,
        cue_start=0.0,
        cue_end=1.0,
        cue_text=cue_text,
        words=[WordSpan(text="שלום", start=0.1, end=0.4)],
    )
    save_word_timings_json(word_timings_path, with_words_doc)
    decision = build_ass_document_with_karaoke_fallback(
        cues,
        srt_path=srt_path,
        word_timings_path=word_timings_path,
        style_config=style,
    )
    assert decision.karaoke_enabled is True
    assert decision.reason == "ok"


def test_karaoke_cue_index_mapping_from_one_based() -> None:
    cues = [{"start_s": 0.0, "end_s": 1.0, "text": "שלום עולם"}]
    doc = _build_word_timing_doc(
        srt_sha256="stub",
        cue_index=1,
        cue_start=0.0,
        cue_end=1.0,
        cue_text="שלום עולם",
        words=[WordSpan(text="שלום", start=0.1, end=0.4)],
    )
    style = build_style_config_from_subtitle_style(
        preset_defaults(PRESET_DEFAULT),
        highlight_color="#FFD400",
        highlight_opacity=1.0,
    )
    result = build_ass_karaoke_document_with_stats(cues, doc, style)
    assert result.highlight_event_count == 1
