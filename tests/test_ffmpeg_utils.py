from app.ffmpeg_utils import escape_ffmpeg_filter_path


def test_escape_ffmpeg_filter_path_windows_drive_and_spaces() -> None:
    path = r"C:\Videos\My Clips\subs file.ass"
    escaped = escape_ffmpeg_filter_path(path)
    assert escaped == "C\\:/Videos/My Clips/subs file.ass"


def test_escape_ffmpeg_filter_path_escapes_quotes_and_brackets() -> None:
    path = r"D:\Show\[Episode]\subtitle's.ass"
    escaped = escape_ffmpeg_filter_path(path)
    assert escaped == "D\\:/Show/\\[Episode\\]/subtitle\\'s.ass"
