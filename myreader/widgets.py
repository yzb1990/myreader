from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    """按可用宽度省略文字，完整内容保留在 tooltip 中。"""

    def __init__(
        self,
        text: str = "",
        parent=None,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
    ) -> None:
        super().__init__(parent)
        self._full_text = text
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        super().setText(text)
        self.setToolTip(text)

    def setText(self, text: str) -> None:
        self._full_text = text or ""
        super().setText(self._full_text)
        self.setToolTip(self._full_text)
        self.update()

    def fullText(self) -> str:
        return self._full_text

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        metrics = self.fontMetrics()
        text = metrics.elidedText(self._full_text, self._mode, max(0, self.width()))
        painter.setPen(self.palette().color(self.foregroundRole()))
        alignment = self.alignment() | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(self.rect(), int(alignment), text)
        painter.end()
