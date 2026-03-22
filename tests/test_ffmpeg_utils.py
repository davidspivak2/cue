from pathlib import Path

import pytest

from app.ffmpeg_utils import (
    escape_ffmpeg_filter_path,
    format_ffmpeg_failure_message,
    media_has_audio_stream,
)


def test_escape_ffmpeg_filter_path_windows_drive_and_spaces() -> None:
    path = r"C:\Videos\My Clips\subs file.ass"
    escaped = escape_ffmpeg_filter_path(path)
    assert escaped == "C\\:/Videos/My Clips/subs file.ass"


def test_escape_ffmpeg_filter_path_escapes_quotes_and_brackets() -> None:
    path = r"D:\Show\[Episode]\subtitle's.ass"
    escaped = escape_ffmpeg_filter_path(path)
    assert escaped == "D\\:/Show/\\[Episode\\]/subtitle\\'s.ass"


def test_format_ffmpeg_failure_message_no_audio_stream() -> None:
    lines = [
        "Output #0, wav, to 'out.wav'",
        "[out#0/wav] Output file does not contain any stream",
        "Error opening output files: Invalid argument",
    ]
    msg = format_ffmpeg_failure_message(lines)
    assert "no audio track" in msg.lower()
    assert "Technical details (ffmpeg):" in msg
    assert "does not contain any stream" in msg


def test_format_ffmpeg_failure_message_generic() -> None:
    msg = format_ffmpeg_failure_message(["Something obscure happened"])
    assert "Video processing failed" in msg
    assert "Something obscure" in msg


def test_media_has_audio_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.ffmpeg_utils.get_ffprobe_json",
        lambda _p: {"streams": [{"codec_type": "video"}, {"codec_type": "audio"}]},
    )
    assert media_has_audio_stream(Path("x.mp4")) is True

    monkeypatch.setattr(
        "app.ffmpeg_utils.get_ffprobe_json",
        lambda _p: {"streams": [{"codec_type": "video"}]},
    )
    assert media_has_audio_stream(Path("silent.mp4")) is False

    monkeypatch.setattr("app.ffmpeg_utils.get_ffprobe_json", lambda _p: None)
    assert media_has_audio_stream(Path("unknown.bin")) is None
