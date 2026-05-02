from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from python_agent.ui.icons import beavis_icon


class BeavisTrayIcon(QSystemTrayIcon):
    def __init__(
        self,
        app: QApplication,
        show_main,
        show_overlay,
        quit_app,
    ) -> None:
        super().__init__(beavis_icon(), app)

        self.setToolTip("Beavis Agent")

        menu = QMenu()
        show_action = QAction("Показать", menu)
        overlay_action = QAction("Команда", menu)
        quit_action = QAction("Выход", menu)

        show_action.triggered.connect(show_main)
        overlay_action.triggered.connect(show_overlay)
        quit_action.triggered.connect(quit_app)

        menu.addAction(show_action)
        menu.addAction(overlay_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.setContextMenu(menu)

        self.activated.connect(
            lambda reason: show_main()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
