from __future__ import annotations

from enum import Enum, auto


class AppState(Enum):
    EMPTY = auto()
    VIDEO_SELECTED = auto()
    WORKING = auto()
    SUBTITLES_READY = auto()
    EXPORT_DONE = auto()
