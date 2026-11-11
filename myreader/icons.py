from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from .themes import Theme


def _draw_glyph(name: str, color: QColor, size: int) -> QPixmap:
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    s = float(size)

    if name == "back":
        path = QPainterPath()
        path.moveTo(s * 0.60, s * 0.24)
        path.lineTo(s * 0.34, s * 0.50)
        path.lineTo(s * 0.60, s * 0.76)
        painter.drawPath(path)
    elif name == "toc":
        for index, length in enumerate((0.62, 0.50, 0.38)):
            y = s * (0.30 + index * 0.20)
            painter.drawLine(
                QPointF(s * 0.20, y),
                QPointF(s * (0.20 + length), y),
            )
    elif name == "search":
        painter.drawEllipse(QRectF(s * 0.21, s * 0.21, s * 0.35, s * 0.35))
        painter.drawLine(QPointF(s * 0.56, s * 0.56), QPointF(s * 0.78, s * 0.78))
    elif name == "settings":
        for y, knob in ((0.30, 0.62), (0.50, 0.38), (0.70, 0.68)):
            painter.drawLine(QPointF(s * 0.20, s * y), QPointF(s * 0.80, s * y))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for y, knob in ((0.30, 0.62), (0.50, 0.38), (0.70, 0.68)):
            painter.drawEllipse(QPointF(s * knob, s * y), s * 0.085, s * 0.085)
    elif name == "plus":
        painter.drawLine(QPointF(s * 0.50, s * 0.24), QPointF(s * 0.50, s * 0.76))
        painter.drawLine(QPointF(s * 0.24, s * 0.50), QPointF(s * 0.76, s * 0.50))
    elif name == "close":
        painter.drawLine(QPointF(s * 0.30, s * 0.30), QPointF(s * 0.70, s * 0.70))
        painter.drawLine(QPointF(s * 0.70, s * 0.30), QPointF(s * 0.30, s * 0.70))
    elif name == "mini":
        painter.drawRoundedRect(
            QRectF(s * 0.16, s * 0.24, s * 0.68, s * 0.52), s * 0.09, s * 0.09
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(
            QRectF(s * 0.50, s * 0.50, s * 0.28, s * 0.18), s * 0.04, s * 0.04
        )
    elif name == "expand":
        a, b, c = s * 0.22, s * 0.78, s * 0.36
        for x1, y1, x2, y2, x3, y3 in (
            (a, c, a, a, c, a),
            (b - (c - a), a, b, a, b, c),
            (a, b - (c - a), a, b, c, b),
            (b, b, b, b - (c - a), b - (c - a), b),
        ):
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            painter.drawLine(QPointF(x2, y2), QPointF(x3, y3))
    elif name == "ghost":
        painter.drawRoundedRect(
            QRectF(s * 0.20, s * 0.24, s * 0.60, s * 0.52), s * 0.08, s * 0.08
        )
        painter.drawLine(QPointF(s * 0.30, s * 0.72), QPointF(s * 0.72, s * 0.28))
    elif name == "solid":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(
            QRectF(s * 0.18, s * 0.24, s * 0.64, s * 0.52), s * 0.09, s * 0.09
        )

    painter.end()
    return pixmap


def make_icon(name: str, color: str, size: int = 20) -> QIcon:
    return QIcon(_draw_glyph(name, QColor(color), size))


def app_icon(theme: Theme) -> QIcon:
    size = 256
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    rect = QRectF(10, 10, 236, 236)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor(theme.accent))
    gradient.setColorAt(1.0, QColor(theme.accent).darker(150))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(rect, 56, 56)

    painter.setBrush(QColor(255, 255, 255, 20))
    painter.drawEllipse(QPointF(206, 56), 74, 74)
    painter.setBrush(QColor(0, 0, 0, 24))
    painter.drawEllipse(QPointF(46, 216), 86, 86)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 42), 3))
    painter.drawRoundedRect(rect.adjusted(7, 7, -7, -7), 50, 50)

    pen = QPen(QColor(theme.on_accent), 9)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    left = QPainterPath()
    left.moveTo(128, 180)
    left.cubicTo(108, 164, 82, 160, 58, 168)
    left.lineTo(58, 88)
    left.cubicTo(84, 80, 110, 84, 128, 98)
    painter.drawPath(left)

    right = QPainterPath()
    right.moveTo(128, 180)
    right.cubicTo(148, 164, 174, 160, 198, 168)
    right.lineTo(198, 88)
    right.cubicTo(172, 80, 146, 84, 128, 98)
    painter.drawPath(right)

    painter.drawLine(QPointF(128, 98), QPointF(128, 180))
    painter.end()
    return QIcon(pixmap)
