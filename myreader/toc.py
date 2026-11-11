from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TocPanel(QWidget):
    chapter_selected = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TocPanel")
        self._syncing = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 12, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("目录")
        title.setObjectName("tocTitle")
        self.count = QLabel("共 0 章")
        self.count.setObjectName("smallMuted")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.count)
        layout.addLayout(header)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("筛选章节…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._filter)
        self.filter.returnPressed.connect(self._focus_first_visible)
        layout.addWidget(self.filter)

        self.list = QListWidget()
        self.list.setObjectName("TocList")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list.setUniformItemSizes(True)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list, 1)

    def set_chapters(self, titles: list[str], current: int = 0) -> None:
        self._syncing = True
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.blockSignals(False)
        self.list.clear()
        for index, title in enumerate(titles):
            item = QListWidgetItem(title)
            item.setToolTip(title)
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.list.addItem(item)
        self.count.setText(f"共 {len(titles)} 章")
        self._syncing = False
        self.set_current(current)

    def set_current(self, index: int) -> None:
        if 0 <= index < self.list.count():
            self._syncing = True
            self.list.setCurrentRow(index)
            item = self.list.item(index)
            if item is not None:
                self.list.scrollToItem(
                    item, QAbstractItemView.ScrollHint.PositionAtCenter
                )
            self._syncing = False

    def _on_row_changed(self, row: int) -> None:
        if self._syncing or row < 0:
            return
        self.chapter_selected.emit(row)

    def _filter(self, text: str) -> None:
        query = text.strip().lower()
        for index in range(self.list.count()):
            item = self.list.item(index)
            item.setHidden(bool(query) and query not in item.text().lower())

    def _focus_first_visible(self) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            if not item.isHidden():
                self.list.setCurrentRow(index)
                break
        self.list.setFocus()
