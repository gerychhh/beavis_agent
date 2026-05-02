from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BEAVIS_LOGO_PATH = PROJECT_ROOT / "python_agent" / "assets" / "beavis_logo.png"


def beavis_icon() -> QIcon:
    return QIcon(str(BEAVIS_LOGO_PATH))
