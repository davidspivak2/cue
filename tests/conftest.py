from __future__ import annotations

import sys
from pathlib import Path

import pytest

try:
    from PySide6.QtWidgets import QApplication
except Exception:
    QApplication = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_app = QApplication.instance() or QApplication(sys.argv) if QApplication else None


@pytest.fixture(scope="session", autouse=True)
def qapp():
    return _app
