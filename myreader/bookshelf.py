from __future__ import annotations

import hashlib
import time
from pathlib import Path

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .config import BookEntry, Library
from .icons import make_icon
from .themes import Theme
from .widgets import ElidedLabel

_COVER_PALETTES = (
    ("#7b3f3b", "#3c1e1d"),
    ("#31504a", "#152a27"),
    ("#3e4a63", "#1d2335"),
    ("#6b5230", "#332411"),
    ("#593a54", "#2a1a28"),
    ("#484a45", "#232420"),
    ("#7a4a29", "#372311"),
    ("#35555d", "#172a2f"),
)


def _relative_time(timestamp: float) -> str:
    if timestamp <= 0:
        return "尚未阅读"
    delta = max(0.0, time.time() - timestamp)
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前"
    if delta < 86400 * 2:
        return "昨天"
    if delta < 86400 * 7:
        return f"{int(delta // 86400)} 天前"
    return time.strftime("%Y-%m-%d", time.localtime(timestamp))


class CoverWidget(QWidget):
    def __init__(self, title: str, dimmed: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._title = title
        self._dimmed = dimmed
        seed = hashlib.md5(title.encode("utf-8")).digest()[0] % len(_COVER_PALETTES)
        self._start = QColor(_COVER_PALETTES[seed][0])
        self._end = QColor(_COVER_PALETTES[seed][1])
        self.setFixedSize(154, 200)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if self._dimmed:
            painter.setOpacity(0.5)

        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        clip = QPainterPath()
        clip.addRoundedRect(rect, 9, 9)
        painter.setClipPath(clip)

        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, self._start)
        gradient.setColorAt(1.0, self._end)
        painter.fillRect(self.rect(), gradient)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 22))
        painter.drawEllipse(QPointF(self.width() * 0.88, self.height() * 0.10), 62, 62)
        painter.setBrush(QColor(255, 255, 255, 9))
        painter.drawEllipse(QPointF(self.width() * 0.10, self.height() * 0.94), 54, 54)

        spine = QLinearGradient(0, 0, 22, 0)
        spine.setColorAt(0.0, QColor(0, 0, 0, 80))
        spine.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(0, 0, 22, self.height()), spine)
        painter.setClipping(False)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 32), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)

        length = len(self._title)
        pixel_size = 27 if length <= 4 else 21 if length <= 8 else 17
        font = QFont("Microsoft YaHei")
        font.setPixelSize(pixel_size)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(250, 246, 238))
        title_rect = QRectF(20, 34, self.width() - 38, 116)
        flags = int(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
        )
        painter.drawText(title_rect, flags, self._title)

        painter.setPen(QPen(QColor(255, 255, 255, 70), 1.5))
        painter.drawLine(QPointF(30, 166), QPointF(56, 166))

        badge = QRectF(20, self.height() - 38, 38, 19)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 28))
        painter.drawRoundedRect(badge, 4, 4)
        badge_font = QFont("Microsoft YaHei")
        badge_font.setPixelSize(9)
        badge_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(badge_font)
        painter.setPen(QColor(255, 255, 255, 185))
        painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), "TXT")
        painter.end()


class BookCard(QFrame):
    open_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)

    def __init__(self, entry: BookEntry, file_exists: bool, parent=None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("BookCard")
        self.setFixedSize(178, 282)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        cover = CoverWidget(entry.title, dimmed=not file_exists)
        layout.addWidget(cover, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)

        title = ElidedLabel(entry.title)
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        layout.addSpacing(3)

        self.meta = QLabel(self._meta_text(file_exists))
        self.meta.setObjectName("cardMeta")
        layout.addWidget(self.meta)
        layout.addSpacing(9)

        progress = QProgressBar()
        progress.setRange(0, 1000)
        progress.setValue(min(1000, max(0, int(entry.percent * 10))))
        progress.setTextVisible(False)
        progress.setFixedHeight(4)
        layout.addWidget(progress)
        layout.addStretch(1)

        for child in self.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        tooltip = f"{entry.title}\n{entry.path}"
        if entry.total_chapters:
            tooltip += f"\n共 {entry.total_chapters} 章"
        if not file_exists:
            tooltip += "\n（原始文件已丢失）"
        self.setToolTip(tooltip)

    def _meta_text(self, file_exists: bool) -> str:
        if not file_exists:
            return "文件已丢失"
        if self.entry.last_read_at <= 0:
            return "尚未阅读"
        percent = max(0.0, min(100.0, self.entry.percent))
        return f"{percent:.0f}%  ·  {_relative_time(self.entry.last_read_at)}"

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(self.entry.path)
        super().mouseReleaseEvent(event)

    def _show_menu(self, position) -> None:
        menu = QMenu(self)
        open_action = menu.addAction("打开阅读")
        menu.addSeparator()
        remove_action = menu.addAction("从书架移除")
        chosen = menu.exec(self.mapToGlobal(position))
        if chosen is open_action:
            self.open_requested.emit(self.entry.path)
        elif chosen is remove_action:
            self.remove_requested.emit(self.entry.path)


class BookshelfPage(QWidget):
    open_requested = pyqtSignal(str)
    import_requested = pyqtSignal()
    remove_requested = pyqtSignal(str)

    CARD_WIDTH = 178
    GAP = 24

    def __init__(self, library: Library, parent=None) -> None:
        super().__init__(parent)
        self.library = library
        self.cards: list[BookCard] = []
        self._columns = -1
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 22)
        root.setSpacing(22)

        header = QHBoxLayout()
        header.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        page_title = QLabel("我的书架")
        page_title.setObjectName("pageTitle")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("muted")
        titles.addWidget(page_title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles)
        header.addStretch(1)

        self.import_btn = QPushButton("导入 TXT")
        self.import_btn.setObjectName("primary")
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.clicked.connect(self.import_requested.emit)
        header.addWidget(self.import_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header)

        self.stack = QStackedWidget()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)

        self.canvas = QWidget()
        self.canvas.setObjectName("ShelfCanvas")
        self.grid = QGridLayout(self.canvas)
        self.grid.setContentsMargins(0, 2, 3, 16)
        self.grid.setHorizontalSpacing(self.GAP)
        self.grid.setVerticalSpacing(26)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.canvas)
        self.scroll.viewport().installEventFilter(self)
        self.stack.addWidget(self.scroll)

        self.empty = self._build_empty()
        self.stack.addWidget(self.empty)
        root.addWidget(self.stack, 1)

    def _build_empty(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(2)

        glyph = QLabel("书")
        glyph.setObjectName("emptyGlyph")
        glyph.setFixedSize(92, 92)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(22)

        title = QLabel("书架还是空的")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(7)

        subtitle = QLabel("导入一本 TXT 小说，或者直接把文件拖进窗口")
        subtitle.setObjectName("emptySub")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(22)

        self.empty_import_btn = QPushButton("导入 TXT 小说")
        self.empty_import_btn.setObjectName("primary")
        self.empty_import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.empty_import_btn.clicked.connect(self.import_requested.emit)
        layout.addWidget(self.empty_import_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(3)
        return page

    def eventFilter(self, obj, event) -> bool:
        if obj is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._reflow()
        return super().eventFilter(obj, event)

    def refresh(self) -> None:
        while self.grid.count():
            self.grid.takeAt(0)
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()

        entries = self.library.sorted_books()
        self.subtitle.setText(f"共 {len(entries)} 本  ·  支持拖入 TXT 文件导入")
        for entry in entries:
            exists = Path(entry.path).is_file()
            card = BookCard(entry, exists)
            card.open_requested.connect(self.open_requested.emit)
            card.remove_requested.connect(self.remove_requested.emit)
            self.cards.append(card)

        has_books = bool(entries)
        self.stack.setCurrentWidget(self.scroll if has_books else self.empty)
        self._columns = -1
        QTimer.singleShot(0, lambda: self._reflow(force=True))

    def _reflow(self, force: bool = False) -> None:
        width = self.scroll.viewport().width()
        if width <= 0 or not self.cards:
            return
        columns = max(1, (width + self.GAP) // (self.CARD_WIDTH + self.GAP))
        if not force and columns == self._columns:
            return
        self._columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(
                card,
                index // columns,
                index % columns,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            )
        for column in range(32):
            self.grid.setColumnStretch(column, 0)
        self.grid.setColumnStretch(columns, 1)

    def apply_theme(self, theme: Theme) -> None:
        icon = make_icon("plus", theme.on_accent, 18)
        for button in (self.import_btn, self.empty_import_btn):
            button.setIcon(icon)
            button.setIconSize(QSize(18, 18))
