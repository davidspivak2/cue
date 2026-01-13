from app.preview_playback import _shift_srt_text


def test_shift_srt_text_offsets_and_drops_cues() -> None:
    original = (
        "1\n"
        "00:00:02,000 --> 00:00:04,000\n"
        "Hello\n"
        "\n"
        "2\n"
        "00:00:05,500 --> 00:00:06,000\n"
        "World\n"
        "\n"
        "3\n"
        "00:00:00,200 --> 00:00:00,400\n"
        "Drop\n"
        "\n"
    )
    shifted, result = _shift_srt_text(original, 3.0)

    assert result.cues_written == 2
    assert result.first_start == "00:00:00,000"
    assert result.first_end == "00:00:01,000"
    assert "00:00:00,000 --> 00:00:01,000" in shifted
    assert "00:00:02,500 --> 00:00:03,000" in shifted
    assert "Drop" not in shifted
