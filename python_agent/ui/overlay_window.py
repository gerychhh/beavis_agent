from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from python_agent.ui.icons import BEAVIS_LOGO_PATH, beavis_icon
from python_agent.ui.liquid_widgets import NeonDivider, WaveformWidget


def _enable_windows_acrylic_blur(widget: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int), ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]

        accent = ACCENT_POLICY()
        accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2
        accent.GradientColor = 0xA01B1208
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(int(widget.winId()), ctypes.byref(data))
    except Exception:
        pass


class OverlayCommandWindow(QWidget):
    submitted = Signal(str)

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("overlayWindow")
        self.setWindowIcon(beavis_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(920, 88)
        self._animations: list[QPropertyAnimation] = []

        self.logo_badge = QLabel(self)
        self.logo_badge.setObjectName("overlayLogo")
        logo = QPixmap(str(BEAVIS_LOGO_PATH))
        if not logo.isNull():
            self.logo_badge.setPixmap(
                logo.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        self.logo_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_badge.setFixedSize(50, 50)

        self.command_input = QLineEdit(self)
        self.command_input.setObjectName("overlayInput")
        self.command_input.setPlaceholderText("Введите команду")
        self.command_input.returnPressed.connect(self._submit)

        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self.logo_badge)
        row.addWidget(self.command_input, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(0)
        root.addLayout(row)

        QShortcut(QKeySequence("Escape"), self, activated=self.hide)
        self.command_input.installEventFilter(self)

        self.setStyleSheet(
            """
            QWidget#overlayWindow {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(15, 28, 52, 150),
                    stop:0.55 rgba(19, 37, 66, 128),
                    stop:1 rgba(27, 30, 64, 150));
                border: 1px solid rgba(220, 240, 255, 90);
                border-radius: 18px;
            }
            QLabel#overlayLogo {
                background: rgba(255, 255, 255, 20);
                border: 1px solid rgba(235, 245, 255, 60);
                border-radius: 14px;
                padding: 5px;
            }
            QLineEdit#overlayInput {
                min-height: 48px;
                background: transparent;
                border: 0;
                color: #f5fbff;
                font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
                font-size: 23px;
                padding: 0 2px;
                selection-background-color: rgba(56, 205, 255, 110);
            }
            QLineEdit#overlayInput:focus {
                background: transparent;
                border: 0;
            }
            """
        )

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        _enable_windows_acrylic_blur(self)

    def show_centered(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            self.show()
            self.activateWindow()
            self.command_input.setFocus()
            return

        area = screen.availableGeometry()
        x = area.x() + (area.width() - self.width()) // 2
        y = area.y() + max(36, area.height() // 8)
        self.move(x, y - 10)
        self.command_input.clear()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.command_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._animate_in(x, y)

    def _submit(self) -> None:
        command = self.command_input.text().strip()
        if not command:
            self.hide()
            return

        self.command_input.clear()
        self.hide()
        self.submitted.emit(command)

    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        if event.type() == QEvent.Type.WindowDeactivate and self.isVisible():
            self.hide()
        return handled

    def eventFilter(self, watched, event: QEvent) -> bool:
        if watched is self.command_input and event.type() == QEvent.Type.FocusOut and self.isVisible():
            self.hide()
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        if self.childAt(event.position().toPoint()) is None:
            self.hide()
            return
        super().mousePressEvent(event)

    def _animate_in(self, x: int, y: int) -> None:
        pos_animation = QPropertyAnimation(self, b"pos", self)
        pos_animation.setDuration(200)
        pos_animation.setStartValue(self.pos())
        pos_animation.setEndValue(self.pos().__class__(x, y))
        pos_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start_animation(pos_animation)

        opacity_animation = QPropertyAnimation(self, b"windowOpacity", self)
        opacity_animation.setDuration(170)
        opacity_animation.setStartValue(0.0)
        opacity_animation.setEndValue(1.0)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start_animation(opacity_animation)

    def _start_animation(self, animation: QPropertyAnimation) -> None:
        self._animations.append(animation)
        animation.finished.connect(lambda: self._animations.remove(animation) if animation in self._animations else None)
        animation.start()


class VoiceOverlayWindow(QWidget):
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("voiceOverlayWindow")
        self.setWindowIcon(beavis_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(760, 220)
        self._animations: list[QPropertyAnimation] = []

        self.title_label = QLabel("Слушаю", self)
        self.title_label.setObjectName("voiceOverlayTitle")
        self.detail_label = QLabel("Говори команду", self)
        self.detail_label.setObjectName("voiceOverlayDetail")

        self.waveform = WaveformWidget(self)
        self.waveform.setFixedHeight(100)

        content = QVBoxLayout(self)
        content.setContentsMargins(28, 24, 28, 24)
        content.setSpacing(10)
        content.addWidget(self.title_label)
        content.addWidget(self.detail_label)
        content.addSpacing(2)
        content.addWidget(self.waveform)

        QShortcut(QKeySequence("Escape"), self, activated=self._cancel)

        self.setStyleSheet(
            """
            QWidget#voiceOverlayWindow {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(15, 28, 52, 150),
                    stop:0.55 rgba(19, 37, 66, 128),
                    stop:1 rgba(27, 30, 64, 150));
                border: 0;
                border-radius: 18px;
            }
            QLabel#voiceOverlayTitle {
                color: #ffffff;
                font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
                font-size: 24px;
                font-weight: 760;
            }
            QLabel#voiceOverlayDetail {
                color: rgba(226, 237, 255, 165);
                font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            """
        )

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        _enable_windows_acrylic_blur(self)

    def show_centered(self, title: str = "Слушаю", detail: str = "Говори команду") -> None:
        self.set_message(title, detail)
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            self.show()
            self.activateWindow()
            return

        area = screen.availableGeometry()
        x = area.x() + (area.width() - self.width()) // 2
        y = area.y() + max(52, area.height() // 6)
        self.move(x, y - 10)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._animate_in(x, y)

    def set_message(self, title: str, detail: str = "") -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)

    def set_level(self, level: float) -> None:
        normalized = max(0.03, min(1.0, float(level) * 4.2))
        self.waveform.set_level(normalized)

    def _cancel(self) -> None:
        self.cancelled.emit()
        self.hide()

    def _animate_in(self, x: int, y: int) -> None:
        pos_animation = QPropertyAnimation(self, b"pos", self)
        pos_animation.setDuration(220)
        pos_animation.setStartValue(self.pos())
        pos_animation.setEndValue(self.pos().__class__(x, y))
        pos_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start_animation(pos_animation)

        opacity_animation = QPropertyAnimation(self, b"windowOpacity", self)
        opacity_animation.setDuration(180)
        opacity_animation.setStartValue(0.0)
        opacity_animation.setEndValue(1.0)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._start_animation(opacity_animation)

    def _start_animation(self, animation: QPropertyAnimation) -> None:
        self._animations.append(animation)
        animation.finished.connect(lambda: self._animations.remove(animation) if animation in self._animations else None)
        animation.start()
