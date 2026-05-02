from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ToastWindow(QWidget):
    def __init__(self, timeout_ms: int = 3200) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.timeout_ms = timeout_ms
        self.setObjectName("toastWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(430)
        self._animations: list[QPropertyAnimation] = []

        self.label = QLabel(self)
        self.label.setObjectName("toastLabel")
        self.label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 13, 17, 13)
        layout.addWidget(self.label)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)

    def show_message(self, message: str, success: bool = True) -> None:
        self.label.setText(message)
        border = "rgba(168, 255, 216, 105)" if success else "rgba(255, 139, 139, 125)"
        color = "#f8fbff" if success else "#ffd6d6"
        self.setStyleSheet(
            f"""
            QWidget#toastWindow {{
                background: rgba(8, 9, 12, 232);
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel#toastLabel {{
                color: {color};
                font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
                font-size: 13px;
                font-weight: 560;
            }}
            """
        )

        self.adjustSize()
        self.setWindowOpacity(0.0)
        start, end = self._move_to_screen_corner()
        self.move(start)
        self.show()
        self.raise_()
        self._animate_in(end)
        self.timer.start(self.timeout_ms)

    def _move_to_screen_corner(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return self.pos(), self.pos()

        area = screen.availableGeometry()
        margin = 24
        x = area.x() + area.width() - self.width() - margin
        y = area.y() + area.height() - self.height() - margin
        end = self.pos().__class__(x, y)
        start = self.pos().__class__(x + 18, y)
        return start, end

    def _animate_in(self, end) -> None:
        pos_animation = QPropertyAnimation(self, b"pos", self)
        pos_animation.setDuration(190)
        pos_animation.setStartValue(self.pos())
        pos_animation.setEndValue(end)
        pos_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start_animation(pos_animation)

        opacity_animation = QPropertyAnimation(self, b"windowOpacity", self)
        opacity_animation.setDuration(150)
        opacity_animation.setStartValue(0.0)
        opacity_animation.setEndValue(1.0)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start_animation(opacity_animation)

    def _fade_out(self) -> None:
        opacity_animation = QPropertyAnimation(self, b"windowOpacity", self)
        opacity_animation.setDuration(170)
        opacity_animation.setStartValue(self.windowOpacity())
        opacity_animation.setEndValue(0.0)
        opacity_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        opacity_animation.finished.connect(self.hide)
        self._start_animation(opacity_animation)

    def _start_animation(self, animation: QPropertyAnimation) -> None:
        self._animations.append(animation)
        animation.finished.connect(lambda: self._animations.remove(animation) if animation in self._animations else None)
        animation.start()
