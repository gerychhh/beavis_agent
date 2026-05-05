from __future__ import annotations

import math
import random
from typing import Callable, Optional

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from python_agent.ui.icons import BEAVIS_LOGO_PATH


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class _HomeBackground(QWidget):
    """Animated black / white liquid-glass stage used only on the home page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("beavisHomeRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self._phase = random.random() * 10.0
        self._center_panel: QWidget | None = None
        self._hero_title: QLabel | None = None
        self._header: QWidget | None = None
        self._particles = [
            {
                "x": random.random(),
                "y": random.random(),
                "speed": random.uniform(0.0009, 0.0032),
                "size": random.uniform(0.55, 1.65),
                "alpha": random.randint(16, 75),
                "drift": random.uniform(-0.00055, 0.00055),
            }
            for _ in range(115)
        ]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_center_panel(self, widget: QWidget) -> None:
        self._center_panel = widget
        self._sync_responsive_layout()

    def set_hero_title(self, label: QLabel) -> None:
        self._hero_title = label
        self._sync_responsive_layout()

    def set_header(self, widget: QWidget) -> None:
        self._header = widget
        self._sync_responsive_layout()

    def _tick(self) -> None:
        self._phase += 0.010
        for particle in self._particles:
            particle["y"] = (particle["y"] - particle["speed"]) % 1.04
            particle["x"] = (particle["x"] + particle["drift"]) % 1.02
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._sync_responsive_layout()
        super().resizeEvent(event)

    def _sync_responsive_layout(self) -> None:
        width = max(1, self.width())
        height = max(1, self.height())
        compact = width < 860 or height < 620
        tiny = width < 680 or height < 520

        if self._center_panel is not None:
            if width < 760:
                max_width = max(360, width - 22)
            else:
                max_width = min(1060, max(720, int(width * 0.78)))
            self._center_panel.setMaximumWidth(max_width)

        if self._hero_title is not None:
            font = self._hero_title.font()
            font.setPointSize(26 if tiny else 32 if compact else 39)
            font.setWeight(QFont.Weight.DemiBold)
            self._hero_title.setFont(font)

        if self._header is not None:
            self._header.setMaximumWidth(max(360, width - 22))

        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            if tiny:
                layout.setContentsMargins(12, 10, 12, 10)
                layout.setSpacing(8)
            elif compact:
                layout.setContentsMargins(18, 14, 18, 14)
                layout.setSpacing(12)
            else:
                layout.setContentsMargins(28, 22, 28, 22)
                layout.setSpacing(18)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        w = max(1, rect.width())
        h = max(1, rect.height())

        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0.0, QColor(2, 3, 5))
        base.setColorAt(0.36, QColor(8, 10, 12))
        base.setColorAt(0.72, QColor(12, 13, 15))
        base.setColorAt(1.0, QColor(1, 2, 3))
        painter.fillRect(rect, base)

        # Slow living mist behind the command bar.
        glows = [
            (0.47 + 0.045 * math.sin(self._phase * 1.10), 0.39 + 0.035 * math.cos(self._phase * 0.90), 0.45, 24),
            (0.18 + 0.030 * math.cos(self._phase * 0.72), 0.56 + 0.050 * math.sin(self._phase * 0.86), 0.30, 18),
            (0.86 + 0.035 * math.sin(self._phase * 0.54), 0.46 + 0.030 * math.cos(self._phase * 0.70), 0.36, 16),
        ]
        for nx, ny, nr, alpha in glows:
            radius = max(w, h) * nr
            cx, cy = w * nx, h * ny
            glow = QRadialGradient(cx, cy, radius)
            glow.setColorAt(0.0, QColor(255, 255, 255, alpha))
            glow.setColorAt(0.40, QColor(255, 255, 255, max(3, alpha // 3)))
            glow.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Diagonal light beams like on the reference, but calmer.
        painter.save()
        painter.translate(w * 0.45, h * 0.39)
        painter.rotate(-11)
        for i, offset in enumerate((-0.42, -0.10, 0.24)):
            x = (math.sin(self._phase * (0.42 + i * 0.08)) * 0.08 + offset) * w
            beam = QRectF(x, -h * 0.07, w * 0.72, max(10, h * 0.045))
            gradient = QLinearGradient(beam.left(), 0, beam.right(), 0)
            gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
            gradient.setColorAt(0.45, QColor(255, 255, 255, 22 - i * 4))
            gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(beam, beam.height() / 2, beam.height() / 2)
        painter.restore()

        # Fine dust / stars. It gives motion without making the UI noisy.
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self._particles:
            x = p["x"] * w
            y = p["y"] * h
            shimmer = (math.sin(self._phase * 5.2 + x * 0.017 + y * 0.011) + 1.0) / 2.0
            alpha = int(p["alpha"] * (0.34 + 0.66 * shimmer))
            size = float(p["size"])
            painter.setBrush(QColor(255, 255, 255, alpha))
            painter.drawEllipse(QPointF(x, y), size, size)

        # Window-like inner stroke.
        outer = rect.adjusted(1, 1, -2, -2)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.2))
        painter.drawRoundedRect(QRectF(outer), 22, 22)
        painter.setPen(QPen(QColor(255, 255, 255, 9), 1.0))
        painter.drawRoundedRect(QRectF(rect.adjusted(8, 8, -9, -9)), 18, 18)
        painter.end()


class _HomeWaveform(QWidget):
    def __init__(self, parent: QWidget | None = None, on_level: Optional[Callable[[float], None]] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMinimumHeight(34)
        self._phase = random.random() * 10.0
        self._target_level = 0.11
        self._display_level = 0.11
        self._on_level = on_level
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(18)

    def set_level(self, value: float) -> None:
        value = _clamp(float(value), 0.0, 1.0)
        self._target_level = max(self._target_level, 0.08 + value * 0.92)
        if self._on_level is not None:
            self._on_level(value)
        self.update()

    def _tick(self) -> None:
        self._phase += 0.080
        idle = 0.10 + 0.035 * ((math.sin(self._phase * 0.65) + 1.0) / 2.0)
        goal = max(idle, self._target_level)
        self._display_level += (goal - self._display_level) * 0.30
        self._target_level = max(idle, self._target_level * 0.93)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(10, 4, -10, -4)
        width = max(1, rect.width())
        mid = rect.center().y()
        amp = max(3.0, rect.height() * (0.12 + self._display_level * 0.42))

        for layer, alpha in enumerate((36, 22, 12)):
            path = QPainterPath()
            path.moveTo(rect.left(), mid)
            step = max(8, width // 90)
            for x in range(rect.left(), rect.right() + step, step):
                t = (x - rect.left()) / width
                envelope = math.sin(math.pi * t) ** 0.55
                y = mid + math.sin(t * math.pi * 4.0 + self._phase * (1.8 + layer * 0.24)) * amp * envelope * (1.0 + layer * 0.38)
                path.lineTo(x, y)
            pen = QPen(QColor(255, 255, 255, alpha), 1.4 + layer * 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPath(path)

        painter.end()


class _MicPulseButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(64, 64)
        self.setObjectName("homeMicButton")
        self._level = 0.05
        self._hover = 0.0
        self._phase = random.random() * 6.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(64, 64)

    def set_level(self, value: float) -> None:
        self._level = max(self._level, _clamp(value, 0.0, 1.0))
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = 1.0
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = 0.0
        super().leaveEvent(event)

    def _tick(self) -> None:
        self._phase += 0.065
        self._level = max(0.035 + 0.030 * ((math.sin(self._phase * 0.85) + 1.0) / 2.0), self._level * 0.91)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2
        pulse = self._level

        for i in range(3):
            ring_radius = radius + 2 + i * 4 + pulse * (8 + i * 5)
            alpha = int((22 - i * 5) * (0.35 + pulse))
            painter.setPen(QPen(QColor(255, 255, 255, alpha), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, ring_radius, ring_radius)

        glow = QRadialGradient(center, radius * 1.45)
        glow.setColorAt(0.0, QColor(255, 255, 255, 54 + int(self._hover * 18)))
        glow.setColorAt(0.58, QColor(255, 255, 255, 18 + int(pulse * 36)))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius * 1.42, radius * 1.42)

        body = QRadialGradient(center, radius)
        body.setColorAt(0.0, QColor(255, 255, 255, 38 + int(self._hover * 35)))
        body.setColorAt(1.0, QColor(255, 255, 255, 10))
        painter.setBrush(body)
        painter.setPen(QPen(QColor(255, 255, 255, 58 + int(self._hover * 45)), 1.1))
        painter.drawEllipse(rect)

        pen = QPen(QColor(255, 255, 255, 230), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        mic = QRectF(center.x() - 6, center.y() - 14, 12, 24)
        painter.drawRoundedRect(mic, 6, 6)
        painter.drawArc(QRectF(center.x() - 14, center.y() - 5, 28, 22), 200 * 16, 140 * 16)
        painter.drawLine(QPointF(center.x(), center.y() + 16), QPointF(center.x(), center.y() + 23))
        painter.drawLine(QPointF(center.x() - 8, center.y() + 23), QPointF(center.x() + 8, center.y() + 23))
        painter.end()


class _HomeCommandPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("homeCommandPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setMouseTracking(True)
        self._hover = 0.0
        self._focus = 0.0
        self._pulse = 0.0
        self._phase = random.random() * 6.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def bind_focus_widget(self, widget: QWidget) -> None:
        widget.installEventFilter(self)

    def pulse(self) -> None:
        self._pulse = 1.0
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = 1.0
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = 0.0
        super().leaveEvent(event)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.FocusIn:
            self._focus = 1.0
        elif event.type() == QEvent.Type.FocusOut:
            self._focus = 0.0
        return super().eventFilter(watched, event)

    def _tick(self) -> None:
        self._phase += 0.025
        self._pulse *= 0.92
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        radius = 28.0
        intensity = _clamp(self._hover * 0.45 + self._focus * 0.55 + self._pulse, 0.0, 1.55)

        outer_glow = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.72)
        outer_glow.setColorAt(0.0, QColor(255, 255, 255, 30 + int(intensity * 28)))
        outer_glow.setColorAt(0.50, QColor(255, 255, 255, 10 + int(intensity * 10)))
        outer_glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(outer_glow)
        painter.drawRoundedRect(rect.adjusted(-18, -18, 18, 18), radius + 12, radius + 12)

        glass = QLinearGradient(rect.topLeft(), rect.bottomRight())
        glass.setColorAt(0.0, QColor(255, 255, 255, 32 + int(intensity * 8)))
        glass.setColorAt(0.43, QColor(255, 255, 255, 15))
        glass.setColorAt(1.0, QColor(255, 255, 255, 25 + int(intensity * 8)))
        painter.setBrush(glass)
        painter.setPen(QPen(QColor(255, 255, 255, 64 + int(intensity * 56)), 1.15))
        painter.drawRoundedRect(rect, radius, radius)

        # Top moving shine.
        shine_x = rect.left() + (math.sin(self._phase) * 0.5 + 0.5) * rect.width()
        shine = QLinearGradient(shine_x - rect.width() * 0.24, rect.top(), shine_x + rect.width() * 0.28, rect.top())
        shine.setColorAt(0.0, QColor(255, 255, 255, 0))
        shine.setColorAt(0.52, QColor(255, 255, 255, 94 + int(intensity * 24)))
        shine.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(shine, 1.8))
        painter.drawLine(QPointF(rect.left() + radius, rect.top() + 1), QPointF(rect.right() - radius, rect.top() + 1))

        # Bottom frosted line.
        bottom = QLinearGradient(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        bottom.setColorAt(0.0, QColor(255, 255, 255, 0))
        bottom.setColorAt(0.50, QColor(255, 255, 255, 48 + int(intensity * 20)))
        bottom.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(bottom, 1.1))
        painter.drawLine(QPointF(rect.left() + 30, rect.bottom() - 1), QPointF(rect.right() - 30, rect.bottom() - 1))
        painter.end()


class _Separator(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("homeVerticalSeparator")
        self.setFixedWidth(1)
        self.setMinimumHeight(50)


_HOME_STYLE = """
QWidget#beavisHomeRoot {
    color: rgba(255, 255, 255, 230);
    font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
    background: transparent;
}
QFrame#beavisHomeHeader {
    background: transparent;
    border: 0;
}
QLabel#homeLogo {
    background: transparent;
    border: 0;
}
QLabel#homeBrandText {
    color: #ffffff;
    font-size: 24px;
    font-weight: 650;
    letter-spacing: 0px;
}
QLabel#homeStatusChip {
    color: rgba(255, 255, 255, 220);
    background: rgba(255, 255, 255, 15);
    border: 1px solid rgba(255, 255, 255, 54);
    border-radius: 18px;
    padding: 8px 14px;
    font-size: 14px;
    font-weight: 560;
}
QLabel#homeStatusChip[state="running"] {
    border-color: rgba(255, 255, 255, 110);
    background: rgba(255, 255, 255, 26);
}
QLabel#homeStatusChip[state="success"] {
    border-color: rgba(255, 255, 255, 95);
    background: rgba(255, 255, 255, 22);
}
QLabel#homeStatusChip[state="error"] {
    border-color: rgba(255, 255, 255, 130);
    background: rgba(255, 255, 255, 32);
}
QPushButton#homeTopNav {
    background: transparent;
    border: 0;
    color: rgba(255, 255, 255, 138);
    padding: 10px 14px;
    font-size: 15px;
    font-weight: 520;
}
QPushButton#homeTopNav:hover,
QPushButton#homeTopNav[active="true"] {
    color: rgba(255, 255, 255, 235);
    background: rgba(255, 255, 255, 10);
    border-radius: 13px;
}
QFrame#homeHeaderDivider {
    background: rgba(255, 255, 255, 30);
    min-width: 1px;
    max-width: 1px;
}
QPushButton#homeWindowControl {
    background: transparent;
    border: 0;
    color: rgba(255, 255, 255, 170);
    padding: 6px 10px;
    font-size: 27px;
    font-weight: 300;
    min-width: 30px;
}
QPushButton#homeWindowControl:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 13);
    border-radius: 10px;
}
QLabel#homeHeroTitle {
    color: #ffffff;
    font-weight: 640;
    letter-spacing: 0.5px;
}
QFrame#homeCenterPanel {
    background: transparent;
    border: 0;
}
QFrame#homeCommandPanel {
    background: transparent;
    border: 0;
}
QLineEdit#homeCommandInput {
    background: transparent;
    border: 0;
    color: rgba(255, 255, 255, 238);
    font-size: 22px;
    padding: 8px 10px 8px 24px;
    selection-background-color: rgba(255, 255, 255, 210);
    selection-color: #08090b;
}
QLineEdit#homeCommandInput:focus {
    background: transparent;
    border: 0;
}
QLineEdit#homeCommandInput::placeholder {
    color: rgba(255, 255, 255, 80);
}
QPushButton#homeRunButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff,
        stop:1 #e8e8e8);
    color: #0b0d10;
    border: 1px solid rgba(255, 255, 255, 210);
    border-radius: 18px;
    padding: 17px 36px;
    font-size: 18px;
    font-weight: 760;
    min-width: 174px;
    min-height: 44px;
}
QPushButton#homeRunButton:hover {
    background: #ffffff;
    border-color: rgba(255, 255, 255, 255);
}
QPushButton#homeRunButton:pressed {
    background: #d8d8d8;
    padding-top: 18px;
    padding-bottom: 16px;
}
QPushButton#homeRunButton:disabled {
    background: rgba(255, 255, 255, 32);
    color: rgba(255, 255, 255, 78);
    border-color: rgba(255, 255, 255, 36);
}
QFrame#homeVerticalSeparator {
    background: rgba(255, 255, 255, 36);
    border: 0;
}
QLabel#homeLastPrefix,
QLabel#homeLastMeta {
    color: rgba(255, 255, 255, 128);
    font-size: 15px;
    font-weight: 520;
}
QPlainTextEdit#homeSummaryView {
    background: transparent;
    border: 0;
    color: rgba(255, 255, 255, 152);
    font-family: "Segoe UI Variable", "Segoe UI", Arial, sans-serif;
    font-size: 15px;
    padding: 0;
    margin: 0;
}
QPushButton#homeCorrectButton {
    background: transparent;
    border: 0;
    color: rgba(255, 255, 255, 135);
    font-size: 15px;
    text-decoration: underline;
    padding: 4px 8px;
}
QPushButton#homeCorrectButton:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 9);
    border-radius: 8px;
}
QProgressBar#homeVoiceLevel {
    background: transparent;
    border: 0;
    max-height: 1px;
}
QPlainTextEdit#homeJsonView {
    background: rgba(0, 0, 0, 50);
    border: 1px solid rgba(255, 255, 255, 20);
    color: rgba(255, 255, 255, 150);
    border-radius: 14px;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 12px;
}
QCheckBox#homeExecuteCheckbox {
    color: rgba(255, 255, 255, 130);
}
QScrollArea#beavisHomeScrollArea {
    background: transparent;
    border: 0;
}
QScrollArea#beavisHomeScrollArea > QWidget > QWidget {
    background: transparent;
}
"""


def _make_logo(parent: QWidget) -> QLabel:
    logo = QLabel(parent)
    logo.setObjectName("homeLogo")
    logo.setFixedSize(40, 40)
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pixmap = QPixmap(str(BEAVIS_LOGO_PATH))
    if not pixmap.isNull():
        logo.setPixmap(
            pixmap.scaled(
                38,
                38,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    else:
        logo.setText("●")
    return logo


def _nav_button(window, text: str, page_index: int, parent: QWidget) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName("homeTopNav")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setProperty("pageIndex", page_index)
    button.clicked.connect(lambda checked=False, index=page_index: window._select_page(index))
    return button


def _window_button(text: str, parent: QWidget, callback: Callable[[], None]) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName("homeWindowControl")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(callback)
    return button


def _toggle_maximized(window) -> None:
    if window.isMaximized():
        window.showNormal()
    else:
        window.showMaximized()


def _build_home_page(window) -> QWidget:
    root = _HomeBackground(window)
    root.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    root.setMinimumWidth(0)
    root.setStyleSheet(_HOME_STYLE)
    window._beavis_home_root = root

    header = QFrame(root)
    header.setObjectName("beavisHomeHeader")
    root.set_header(header)

    brand = _make_logo(header)
    title = QLabel("Beavis", header)
    title.setObjectName("homeBrandText")

    home_status = QLabel("●  Готов", header)
    home_status.setObjectName("homeStatusChip")
    home_status.setProperty("state", "idle")
    window.home_status_label = home_status

    nav_apps = _nav_button(window, "Приложения", 1, header)
    nav_history = _nav_button(window, "История", 2, header)
    nav_settings = _nav_button(window, "Настройки", 3, header)
    window.home_nav_buttons = [nav_apps, nav_history, nav_settings]

    header_divider = QFrame(header)
    header_divider.setObjectName("homeHeaderDivider")
    header_divider.setFixedHeight(34)

    minimize = _window_button("−", header, window.showMinimized)
    maximize = _window_button("□", header, lambda: _toggle_maximized(window))
    close = _window_button("×", header, window.close)

    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(18, 14, 18, 8)
    header_layout.setSpacing(12)
    header_layout.addWidget(brand)
    header_layout.addWidget(title)
    header_layout.addWidget(home_status)
    header_layout.addStretch(1)
    header_layout.addWidget(nav_apps)
    header_layout.addWidget(nav_history)
    header_layout.addWidget(nav_settings)
    header_layout.addSpacing(12)
    header_layout.addWidget(header_divider)
    header_layout.addSpacing(12)
    header_layout.addWidget(minimize)
    header_layout.addWidget(maximize)
    header_layout.addWidget(close)

    center = QFrame(root)
    center.setObjectName("homeCenterPanel")
    center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    root.set_center_panel(center)

    hero = QLabel("Что сделать?", center)
    hero.setObjectName("homeHeroTitle")
    hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
    root.set_hero_title(hero)

    # Reuse the existing command input / run button so the old pipeline stays intact.
    window.command_input.setObjectName("homeCommandInput")
    window.command_input.setPlaceholderText("открой telegram и vscode пополам")
    window.command_input.setMinimumHeight(60)
    window.command_input.setClearButtonEnabled(True)
    window.command_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    window.run_button.setObjectName("homeRunButton")
    window.run_button.setText("Выполнить")
    window.run_button.setIcon(QIcon())
    window.run_button.setCursor(Qt.CursorShape.PointingHandCursor)

    window.execute_checkbox.setObjectName("homeExecuteCheckbox")
    window.execute_checkbox.setChecked(True)
    window.execute_checkbox.setVisible(False)

    mic_button = _MicPulseButton(center)
    mic_button.setToolTip("Голосовой ввод / тест микрофона")
    if hasattr(window, "voice_test_requested"):
        mic_button.clicked.connect(window.voice_test_requested.emit)
    window.home_mic_button = mic_button

    command_panel = _HomeCommandPanel(center)
    command_panel.setMinimumHeight(116)
    command_panel.bind_focus_widget(window.command_input)
    window.home_command_panel = command_panel

    wave = _HomeWaveform(command_panel, on_level=mic_button.set_level)
    wave.setFixedHeight(30)
    window.voice_waveform = wave

    input_row = QHBoxLayout()
    input_row.setContentsMargins(26, 16, 26, 14)
    input_row.setSpacing(16)
    input_row.addWidget(window.command_input, 1)
    input_row.addWidget(mic_button, 0, Qt.AlignmentFlag.AlignVCenter)
    input_row.addWidget(_Separator(command_panel))
    input_row.addWidget(window.run_button, 0, Qt.AlignmentFlag.AlignVCenter)

    panel_layout = QVBoxLayout(command_panel)
    panel_layout.setContentsMargins(0, 0, 0, 0)
    panel_layout.setSpacing(0)
    panel_layout.addLayout(input_row)
    panel_layout.addWidget(wave)

    window.summary_view.setObjectName("homeSummaryView")
    window.summary_view.setReadOnly(True)
    window.summary_view.setFixedHeight(28)
    window.summary_view.setMaximumBlockCount(1)
    window.summary_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    window.summary_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    window.summary_view.setFrameShape(QFrame.Shape.NoFrame)
    window.summary_view.setPlainText("команд ещё не было")

    last_prefix = QLabel("Последнее:", center)
    last_prefix.setObjectName("homeLastPrefix")
    window.last_command_status_label = QLabel("", center)
    window.last_command_status_label.setObjectName("homeLastMeta")
    window.last_command_status_label.setVisible(False)
    window.last_command_meta_label = QLabel("", center)
    window.last_command_meta_label.setObjectName("homeLastMeta")
    window.last_command_meta_label.setText("✓")

    last_row = QHBoxLayout()
    last_row.setSpacing(7)
    last_row.setContentsMargins(0, 0, 0, 0)
    last_row.addStretch(1)
    last_row.addWidget(last_prefix)
    last_row.addWidget(window.summary_view, 0)
    last_row.addWidget(window.last_command_meta_label)
    last_row.addStretch(1)

    correct_button = QPushButton("Не то? Исправить", center)
    correct_button.setObjectName("homeCorrectButton")
    correct_button.setCursor(Qt.CursorShape.PointingHandCursor)
    correct_button.clicked.connect(lambda checked=False: window._select_page(2))
    window.home_correct_button = correct_button

    # Keep these attributes alive for old voice/result handlers, but do not clutter the hero.
    window.voice_status_label = QLabel("Голосовой ввод", root)
    window.voice_status_label.setVisible(False)
    window.voice_detail_label = QLabel("", root)
    window.voice_detail_label.setVisible(False)
    window.voice_level = QProgressBar(root)
    window.voice_level.setObjectName("homeVoiceLevel")
    window.voice_level.setRange(0, 100)
    window.voice_level.setTextVisible(False)
    window.voice_level.setVisible(False)

    window.json_view.setObjectName("homeJsonView")
    window.json_view.setVisible(False)
    window.json_view.setMinimumHeight(140)

    center_layout = QVBoxLayout(center)
    center_layout.setContentsMargins(0, 0, 0, 0)
    center_layout.setSpacing(24)
    center_layout.addWidget(hero)
    center_layout.addWidget(command_panel)
    center_layout.addSpacing(10)
    center_layout.addLayout(last_row)
    center_layout.addWidget(correct_button, 0, Qt.AlignmentFlag.AlignHCenter)
    center_layout.addWidget(window.execute_checkbox)
    center_layout.addWidget(window.voice_status_label)
    center_layout.addWidget(window.voice_detail_label)
    center_layout.addWidget(window.voice_level)
    center_layout.addWidget(window.json_view)

    main_layout = QVBoxLayout(root)
    main_layout.setContentsMargins(28, 22, 28, 22)
    main_layout.setSpacing(18)
    main_layout.addWidget(header)
    main_layout.addItem(QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
    main_layout.addWidget(center, 0, Qt.AlignmentFlag.AlignHCenter)
    main_layout.addItem(QSpacerItem(0, 26, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

    QTimer.singleShot(0, root._sync_responsive_layout)
    QTimer.singleShot(0, lambda: root.setStyleSheet(_HOME_STYLE))
    return root


def _refresh_style(widget: QWidget | None) -> None:
    if widget is None:
        return
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _sync_home_nav(window, index: int) -> None:
    for button in getattr(window, "home_nav_buttons", []):
        active = int(button.property("pageIndex") or -1) == index
        button.setProperty("active", active)
        _refresh_style(button)


def _set_home_status(window, text: str, state: str) -> None:
    label = getattr(window, "home_status_label", None)
    if label is None:
        return
    clean = str(text or "").strip()
    if not clean:
        clean = "Готов"
    if not clean.startswith("●"):
        clean = "●  " + clean
    label.setText(clean)
    label.setProperty("state", state or "idle")
    _refresh_style(label)


def _apply_home_shell_mode(window, index: int) -> None:
    is_home = index == 0
    sidebar = window.findChild(QFrame, "sidebar")
    header = window.findChild(QFrame, "headerPanel")
    content = window.findChild(QFrame, "contentRoot")

    if sidebar is not None:
        sidebar.setVisible(not is_home)
    if header is not None:
        header.setVisible(not is_home)
    if content is not None and content.layout() is not None:
        if is_home:
            content.layout().setContentsMargins(10, 10, 10, 10)
            content.layout().setSpacing(0)
        else:
            content.layout().setContentsMargins(26, 22, 26, 22)
            content.layout().setSpacing(16)

    root = getattr(window, "_beavis_home_root", None)
    if root is not None:
        root.setStyleSheet(_HOME_STYLE)
        root.update()

    _sync_home_nav(window, index)


def install_home_page(window_cls) -> None:
    """Monkey-patch BeavisMainWindow without touching Apps/History/Settings pages."""

    if getattr(window_cls, "_beavis_home_patch_installed", False):
        return

    original_select_page = window_cls._select_page
    original_scrollable_tab = window_cls._scrollable_tab
    original_set_status = window_cls._set_status
    original_submit = window_cls._submit

    def patched_build_command_tab(self):
        return _build_home_page(self)

    def patched_scrollable_tab(self, content: QWidget) -> QScrollArea:
        scroll = original_scrollable_tab(self, content)
        if content.objectName() == "beavisHomeRoot":
            content.setMinimumWidth(0)
            content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            scroll.setObjectName("beavisHomeScrollArea")
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    def patched_select_page(self, index: int) -> None:
        original_select_page(self, index)
        _apply_home_shell_mode(self, index)

    def patched_set_status(self, text: str, state: str) -> None:
        original_set_status(self, text, state)
        _set_home_status(self, text, state)

    def patched_submit(self) -> None:
        panel = getattr(self, "home_command_panel", None)
        if panel is not None:
            panel.pulse()
        _set_home_status(self, "Выполняю", "running")
        original_submit(self)

    window_cls._build_command_tab = patched_build_command_tab
    window_cls._scrollable_tab = patched_scrollable_tab
    window_cls._select_page = patched_select_page
    window_cls._set_status = patched_set_status
    window_cls._submit = patched_submit
    window_cls._beavis_home_patch_installed = True
