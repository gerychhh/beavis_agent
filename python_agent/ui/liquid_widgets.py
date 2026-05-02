
from __future__ import annotations

import math
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class LiquidBackground(QWidget):
    """Dark liquid-glass background with soft cyan/violet light blobs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        base = QLinearGradient(0, 0, rect.width(), rect.height())
        base.setColorAt(0.0, QColor(4, 10, 24))
        base.setColorAt(0.45, QColor(6, 18, 42))
        base.setColorAt(1.0, QColor(16, 7, 47))
        painter.fillRect(rect, base)

        blobs = [
            (rect.width() * 0.62, rect.height() * 0.08, rect.width() * 0.42, QColor(23, 120, 255, 70)),
            (rect.width() * 0.92, rect.height() * 0.88, rect.width() * 0.36, QColor(125, 54, 255, 78)),
            (rect.width() * 0.30, rect.height() * 0.62, rect.width() * 0.34, QColor(0, 213, 255, 35)),
        ]
        for cx, cy, radius, color in blobs:
            gradient = QRadialGradient(cx, cy, radius)
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(0.58, QColor(color.red(), color.green(), color.blue(), 18))
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

        painter.end()


class WaveformWidget(QWidget):
    """Animated waveform with stronger sound-reactive motion and soft glow."""

    def __init__(self, parent: QWidget | None = None, *, compact: bool = False) -> None:
        super().__init__(parent)
        self.compact = compact
        self._phase = random.random() * 10.0
        self._sensitivity = 2.4 if compact else 1.85
        self._target_level = 0.22 if compact else 0.18
        self._display_level = self._target_level
        self._bars_cache: list[float] = []
        self.setMinimumHeight(42 if compact else 82)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(20)

    def set_level(self, value: float) -> None:
        value = max(0.02, min(1.0, float(value) * self._sensitivity))
        self._target_level = max(self._target_level, value)
        self.update()

    def _tick(self) -> None:
        self._phase += 0.24
        idle = (0.14 if self.compact else 0.11) + 0.05 * ((math.sin(self._phase * 0.8) + 1.0) / 2.0)
        goal = max(idle, self._target_level)
        self._display_level += (goal - self._display_level) * 0.42
        self._target_level = max(idle, self._target_level * 0.95)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(8, 4, -8, -4)
        mid_y = rect.center().y()
        bars = 44 if not self.compact else 32
        gap = 4 if not self.compact else 3
        width = max(2.0, (rect.width() - gap * (bars - 1)) / bars)
        base_thickness = max(2, int(width))

        if len(self._bars_cache) != bars:
            self._bars_cache = [0.18 for _ in range(bars)]

        for i in range(bars):
            t = i / max(1, bars - 1)
            envelope = math.sin(math.pi * t) ** 0.58
            reactive = (math.sin(self._phase * 2.2 + i * 0.58) + 1.0) / 2.0
            shimmer = (math.sin(self._phase * 1.1 - i * 0.31) + 1.0) / 2.0
            pulse = (math.sin(self._phase * 3.1 + i * 0.17) + 1.0) / 2.0
            strength = (0.14 + 0.24 * shimmer + self._display_level * (0.96 + 0.86 * reactive)) * envelope
            target = max(0.06, strength)
            self._bars_cache[i] += (target - self._bars_cache[i]) * (0.40 + pulse * 0.18)

            height = max(4.0, self._bars_cache[i] * rect.height())
            x = rect.left() + i * (width + gap) + width / 2.0

            if t < 0.45:
                color = QColor(31, 196, 255)
            elif t < 0.72:
                color = QColor(77, 113, 255)
            else:
                color = QColor(174, 74, 255)

            glow = QPen(QColor(color.red(), color.green(), color.blue(), 54), max(5, int(width + 5)))
            glow.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(glow)
            painter.drawLine(int(x), int(mid_y - height / 2), int(x), int(mid_y + height / 2))

            pen = QPen(color, base_thickness)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(int(x), int(mid_y - height / 2), int(x), int(mid_y + height / 2))

        painter.end()


class NeonDivider(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 0))
        gradient.setColorAt(0.2, QColor(52, 174, 255, 120))
        gradient.setColorAt(0.75, QColor(147, 72, 255, 120))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), gradient)


def make_stat_card(title: str, value: str, detail: str = "", parent: QWidget | None = None) -> QFrame:
    card = QFrame(parent)
    card.setObjectName("statCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(4)

    title_label = QLabel(title, card)
    title_label.setObjectName("metricTitle")
    value_label = QLabel(value, card)
    value_label.setObjectName("metricValue")
    detail_label = QLabel(detail, card)
    detail_label.setObjectName("metricDetail")

    layout.addWidget(title_label)
    layout.addWidget(value_label)
    layout.addWidget(detail_label)
    return card
