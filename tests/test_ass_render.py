from __future__ import annotations

from app.ass_render import (
    AssCue,
    ass_color_from_hex,
    build_ass_document,
    escape_ass_text,
    format_ass_time,
    wrap_rtl,
)
from app.subtitle_style import preset_defaults


def test_format_ass_time_examples() -> None:
    assert format_ass_time(0.0) == "0:00:00.00"
    assert format_ass_time(1.234) == "0:00:01.23"
    assert format_ass_time(61.005) == "0:01:01.00"


def test_escape_ass_text_removes_override_braces() -> None:
    text = "Line {override}\nwith \\ backslash"
    escaped = escape_ass_text(text)
    assert "{" not in escaped
    assert "}" not in escaped
    assert "\\" in escaped
    assert "\\N" in escaped


def test_wrap_rtl_adds_marks() -> None:
    sample = "שלום"
    wrapped = wrap_rtl(sample)
    assert wrapped.startswith("\u202B")
    assert wrapped.endswith("\u202C")
    assert wrap_rtl(wrapped) == wrapped


def test_ass_color_from_hex_examples() -> None:
    assert ass_color_from_hex("#AABBCC", alpha=0.0) == "&H00CCBBAA"
    assert ass_color_from_hex("#AABBCC", alpha=1.0) == "&HFFCCBBAA"
    assert ass_color_from_hex("invalid", alpha=0.5) == "&H80FFFFFF"


def test_build_ass_document_has_sections_and_style() -> None:
    cues = [AssCue(start_s=0.0, end_s=1.0, text="Hello")]
    style = preset_defaults("Default")
    ass = build_ass_document(cues, style)
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass
    assert "Style: BASE" in ass
    assert "Dialogue:" in ass


def test_hebrew_line_contains_rtl_marks() -> None:
    cues = [AssCue(start_s=0.0, end_s=1.0, text="אז אני רוצה …")]
    style = preset_defaults("Default")
    ass = build_ass_document(cues, style)
    assert "\u202B" in ass
    assert "\u202C" in ass
