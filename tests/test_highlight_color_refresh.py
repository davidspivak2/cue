import logging

from app.main import MainWindow


def test_apply_highlight_color_schedules_refresh(qapp, tmp_path, monkeypatch):
    logger = logging.getLogger("test_highlight_color_refresh")
    window = MainWindow(logger, tmp_path / "app.log", tmp_path)
    calls = []

    def _record_refresh():
        calls.append(True)

    monkeypatch.setattr(window, "_schedule_preview_refresh", _record_refresh)
    new_color = "#00FF00"
    if new_color == window._highlight_color:
        new_color = "#00FF11"

    window._apply_highlight_color(new_color)

    assert window._highlight_color == new_color
    assert calls == [True]

    window._apply_highlight_color(new_color)
    assert calls == [True]
