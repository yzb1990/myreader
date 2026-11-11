from __future__ import annotations

import html
import time

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QKeySequence,
    QPalette,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .book import Book, EMPTY_CHAPTER_TEXT
from .config import BookEntry, Library, Settings
from .dialogs import SearchDialog
from .icons import make_icon
from .themes import get_theme, reader_css
from .toc import TocPanel
from .widgets import ElidedLabel


class _ReadingPane(QWidget):
    MAX_WIDTH = 880

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ReadingPane")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 16, 40, 0)
        layout.setSpacing(0)

        self.browser = QTextBrowser()
        self.browser.setObjectName("ReaderText")
        self.browser.setFrameShape(QFrame.Shape.NoFrame)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.browser.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.browser.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.browser.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.browser.document().setDocumentMargin(28)
        layout.addWidget(self.browser)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        side = max(24, (self.width() - self.MAX_WIDTH) // 2)
        margins = self.layout().contentsMargins()
        if margins.left() != side:
            self.layout().setContentsMargins(side, 16, side, 0)


class ReaderPage(QWidget):
    back_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    mini_requested = pyqtSignal()

    def __init__(self, settings: Settings, library: Library, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.library = library
        self.book: Book | None = None
        self.entry: BookEntry | None = None
        self.chapter_index = 0
        self._search_term = ""
        self._pending_ratio: float | None = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(900)
        self._save_timer.timeout.connect(self._persist_progress)
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.setInterval(400)
        self._pending_timer.timeout.connect(self._clear_pending_restore)

        self._build_ui()
        self._install_shortcuts()
        self._connect_signals()
        self.apply_settings()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("Header")
        header.setFixedHeight(58)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 16, 0)
        header_layout.setSpacing(6)

        self.back_btn = self._tool_button("返回书架 (Esc)")
        header_layout.addWidget(self.back_btn)

        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)
        self.book_label = ElidedLabel()
        self.book_label.setObjectName("readerBookTitle")
        self.book_label.setMaximumWidth(460)
        self.chapter_label = ElidedLabel()
        self.chapter_label.setObjectName("readerChapter")
        self.chapter_label.setMaximumWidth(460)
        title_layout.addWidget(self.book_label)
        title_layout.addWidget(self.chapter_label)
        header_layout.addWidget(title_box, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch(1)

        self.percent_label = QLabel("0.0%")
        self.percent_label.setObjectName("percentLabel")
        header_layout.addWidget(self.percent_label)
        header_layout.addSpacing(10)

        self.toc_btn = self._tool_button("目录 (Ctrl+B)", checkable=True)
        self.search_btn = self._tool_button("全书搜索 (Ctrl+F)")
        self.mini_btn = self._tool_button("迷你阅读：置顶两行小窗 (Ctrl+M)")
        self.settings_btn = self._tool_button("阅读设置")
        for button in (self.toc_btn, self.search_btn, self.mini_btn, self.settings_btn):
            header_layout.addWidget(button)
        root.addWidget(header)

        body = QWidget()
        body.setObjectName("Page")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.toc = TocPanel()
        self.toc.setFixedWidth(268)
        body_layout.addWidget(self.toc)

        self.pane = _ReadingPane()
        self.text = self.pane.browser
        body_layout.addWidget(self.pane, 1)
        root.addWidget(body, 1)

        footer = QWidget()
        footer.setObjectName("Footer")
        footer.setFixedHeight(54)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(28, 0, 28, 0)
        footer_layout.setSpacing(8)

        self.prev_btn = QPushButton("‹  上一章")
        self.prev_btn.setObjectName("navButton")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.position_label = QLabel("第 1 / 1 章")
        self.position_label.setObjectName("smallMuted")
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_btn = QPushButton("下一章  ›")
        self.next_btn.setObjectName("navButton")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        footer_layout.addWidget(self.prev_btn)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.position_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.next_btn)
        root.addWidget(footer)

    def _tool_button(self, tooltip: str, checkable: bool = False) -> QToolButton:
        button = QToolButton()
        button.setToolTip(tooltip)
        button.setCheckable(checkable)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIconSize(QSize(20, 20))
        button.setFixedSize(36, 36)
        return button

    def _install_shortcuts(self) -> None:
        context = Qt.ShortcutContext.WidgetWithChildrenShortcut

        def add(sequence: str, handler) -> None:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(context)
            shortcut.activated.connect(handler)

        add("Ctrl+F", self.open_search)
        add("Ctrl+B", self._toggle_toc)
        add("Ctrl+M", self.mini_requested.emit)
        add("Ctrl+=", lambda: self._change_font_size(1))
        add("Ctrl++", lambda: self._change_font_size(1))
        add("Ctrl+-", lambda: self._change_font_size(-1))

        for sequence, handler in (
            ("Right", lambda: self._page_by(1)),
            ("PgDown", lambda: self._page_by(1)),
            ("Space", lambda: self._page_by(1)),
            ("Left", lambda: self._page_by(-1)),
            ("PgUp", lambda: self._page_by(-1)),
            ("Shift+Space", lambda: self._page_by(-1)),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self.text)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(handler)

    def _connect_signals(self) -> None:
        self.back_btn.clicked.connect(self.back_requested.emit)
        self.toc_btn.toggled.connect(self._set_toc_visible)
        self.search_btn.clicked.connect(self.open_search)
        self.mini_btn.clicked.connect(self.mini_requested.emit)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        self.toc.chapter_selected.connect(self._on_toc_selected)
        self.prev_btn.clicked.connect(lambda: self._step_chapter(-1))
        self.next_btn.clicked.connect(lambda: self._step_chapter(1))
        scrollbar = self.text.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll)
        scrollbar.rangeChanged.connect(self._on_range_changed)

    # ---------- 打开与渲染 ----------

    def open_book(self, book: Book, entry: BookEntry) -> None:
        self.book = book
        self.entry = entry
        self._search_term = ""
        self.book_label.setText(book.title)
        entry.total_chapters = len(book.chapters)
        entry.last_read_at = time.time()
        index = max(0, min(entry.chapter, len(book.chapters) - 1))
        ratio = entry.scroll if index == entry.chapter else 0.0
        self.toc.set_chapters([chapter.title for chapter in book.chapters], index)
        self._set_toc_visible(self.settings.show_toc, save=False)
        self._load_chapter(index, ratio, focus_text=True)
        self.library.save()

    def _load_chapter(
        self, index: int, ratio: float = 0.0, focus_text: bool = True
    ) -> None:
        if self.book is None:
            return
        index = max(0, min(index, len(self.book.chapters) - 1))
        self.chapter_index = index
        chapter = self.book.chapters[index]
        self.chapter_label.setText(chapter.title)
        self._render_chapter()
        self.toc.set_current(index)
        self._update_progress_labels()
        self._update_nav_buttons()
        QTimer.singleShot(0, lambda r=ratio: self._restore_scroll(r))
        if self._search_term:
            term = self._search_term
            QTimer.singleShot(0, lambda: self._highlight_search(term))
        if focus_text:
            self.text.setFocus(Qt.FocusReason.OtherFocusReason)

    def _render_chapter(self) -> None:
        if self.book is None:
            return
        chapter = self.book.chapters[self.chapter_index]
        theme = get_theme(self.settings.theme)
        css = reader_css(
            theme,
            self.settings.font_family,
            self.settings.font_size,
            self.settings.line_spacing,
            text_color=self.settings.text_color,
        )
        document = self.text.document()
        document.setDefaultStyleSheet(css)
        document.setDocumentMargin(28)

        parts = [f'<h1 class="chapter-title">{html.escape(chapter.title)}</h1>']
        for paragraph in chapter.paragraphs:
            if paragraph == EMPTY_CHAPTER_TEXT:
                parts.append(f'<p class="empty">{html.escape(paragraph)}</p>')
            else:
                parts.append(f"<p>\u3000\u3000{html.escape(paragraph)}</p>")
        self.text.setHtml("".join(parts))
        self.text.verticalScrollBar().setValue(0)

    def _restore_scroll(self, ratio: float) -> None:
        scrollbar = self.text.verticalScrollBar()
        if ratio <= 0:
            self._pending_ratio = None
            self._pending_timer.stop()
            scrollbar.setValue(0)
            return
        self._pending_ratio = ratio
        if scrollbar.maximum() > 0:
            scrollbar.setValue(int(round(ratio * scrollbar.maximum())))
        self._pending_timer.start()

    def _clear_pending_restore(self) -> None:
        self._pending_ratio = None

    def _text_color(self) -> QColor:
        color = QColor(self.settings.text_color)
        if color.isValid():
            return color
        return QColor(get_theme(self.settings.theme).text)

    def apply_settings(self) -> None:
        theme = get_theme(self.settings.theme)
        text_color = self._text_color()
        for button, name in (
            (self.back_btn, "back"),
            (self.toc_btn, "toc"),
            (self.search_btn, "search"),
            (self.mini_btn, "mini"),
            (self.settings_btn, "settings"),
        ):
            button.setIcon(make_icon(name, theme.text))
        palette = self.text.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(theme.bg))
        palette.setColor(QPalette.ColorRole.Text, text_color)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.selection))
        palette.setColor(QPalette.ColorRole.HighlightedText, text_color)
        self.text.setPalette(palette)
        self.text.setStyleSheet(
            f"""
QTextBrowser {{
    background-color: {theme.bg};
    color: {text_color.name()};
    border: none;
}}
QTextBrowser QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 3px 2px;
}}
QTextBrowser QScrollBar::handle:vertical {{
    background: {theme.border};
    border-radius: 3px;
    min-height: 32px;
}}
QTextBrowser QScrollBar::handle:vertical:hover {{ background: {theme.muted}; }}
QTextBrowser QScrollBar::add-line:vertical,
QTextBrowser QScrollBar::sub-line:vertical {{ height: 0; }}
QTextBrowser QScrollBar::add-page:vertical,
QTextBrowser QScrollBar::sub-page:vertical {{ background: transparent; }}
"""
        )
        self._set_toc_visible(self.settings.show_toc, save=False)
        if self.book is not None:
            ratio = self._scroll_ratio()
            self._render_chapter()
            QTimer.singleShot(0, lambda: self._restore_scroll(ratio))
            if self._search_term:
                term = self._search_term
                QTimer.singleShot(0, lambda: self._highlight_search(term))

    # ---------- 阅读与进度 ----------

    def _scroll_ratio(self) -> float:
        scrollbar = self.text.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return 0.0
        return scrollbar.value() / scrollbar.maximum()

    def _book_percent(self) -> float:
        if self.book is None:
            return 0.0
        return (self.chapter_index + self._scroll_ratio()) / len(self.book.chapters) * 100

    def _update_progress_labels(self) -> None:
        if self.book is None:
            return
        self.percent_label.setText(f"{self._book_percent():.1f}%")
        self.position_label.setText(
            f"第 {self.chapter_index + 1} / {len(self.book.chapters)} 章"
        )

    def _update_nav_buttons(self) -> None:
        if self.book is None:
            return
        self.prev_btn.setEnabled(self.chapter_index > 0)
        self.next_btn.setEnabled(self.chapter_index < len(self.book.chapters) - 1)

    def _on_scroll(self, value: int) -> None:
        self._update_progress_labels()
        if self.entry is not None:
            self._save_timer.start()

    def _on_range_changed(self, minimum: int, maximum: int) -> None:
        # 页面刚切换/布局未稳定时滚动条范围还会变，按比例重放恢复位置
        if self._pending_ratio is not None and maximum > 0:
            scrollbar = self.text.verticalScrollBar()
            scrollbar.setValue(int(round(self._pending_ratio * maximum)))
        self._update_progress_labels()

    def _persist_progress(self) -> None:
        if self.book is None or self.entry is None:
            return
        ratio = self._scroll_ratio()
        self.entry.chapter = self.chapter_index
        self.entry.scroll = ratio
        self.entry.percent = (
            (self.chapter_index + ratio) / len(self.book.chapters) * 100
        )
        self.entry.total_chapters = len(self.book.chapters)
        self.entry.last_read_at = time.time()
        self.library.save()

    def leave(self) -> None:
        self._save_timer.stop()
        self._persist_progress()

    def _step_chapter(self, delta: int) -> None:
        self._go_to_chapter(self.chapter_index + delta)

    def _on_toc_selected(self, index: int) -> None:
        self._go_to_chapter(index, focus_text=False)

    def _go_to_chapter(self, index: int, focus_text: bool = True) -> None:
        if self.book is None:
            return
        if index < 0 or index >= len(self.book.chapters) or index == self.chapter_index:
            return
        self._persist_progress()
        self._load_chapter(index, 0.0, focus_text=focus_text)

    # ---------- 页内滚动 ----------

    def _page_by(self, direction: int) -> None:
        scrollbar = self.text.verticalScrollBar()
        step = max(120, int(self.text.viewport().height() * 0.86))
        scrollbar.setValue(scrollbar.value() + direction * step)

    # ---------- 目录与字号 ----------

    def _toggle_toc(self) -> None:
        self._set_toc_visible(not self.settings.show_toc)

    def _set_toc_visible(self, visible: bool, save: bool = True) -> None:
        self.toc.setVisible(visible)
        self.toc_btn.blockSignals(True)
        self.toc_btn.setChecked(visible)
        self.toc_btn.blockSignals(False)
        if self.settings.show_toc != visible:
            self.settings.show_toc = visible
            if save:
                self.settings.save()

    def _change_font_size(self, delta: int) -> None:
        size = max(12, min(40, self.settings.font_size + delta))
        if size == self.settings.font_size:
            return
        self.settings.font_size = size
        self.settings.save()
        self.apply_settings()

    # ---------- 搜索 ----------

    def open_search(self) -> None:
        if self.book is None:
            return
        dialog = SearchDialog(self.book, self._jump_from_search, self)
        dialog.exec()

    def _jump_from_search(
        self, chapter_index: int, term: str, occurrence: int
    ) -> None:
        if self.book is None:
            return
        self._search_term = term
        if chapter_index != self.chapter_index:
            self._persist_progress()
            self._load_chapter(chapter_index, 0.0, focus_text=False)
        QTimer.singleShot(
            0,
            lambda: self._highlight_search(term, focus_occurrence=occurrence),
        )
        self.text.setFocus(Qt.FocusReason.OtherFocusReason)

    def _highlight_search(
        self, term: str, focus_occurrence: int | None = None
    ) -> None:
        if not term:
            return
        theme = get_theme(self.settings.theme)
        background = QColor(theme.highlight)
        foreground = self._text_color()
        document = self.text.document()
        selections = []
        target: QTextCursor | None = None
        cursor = QTextCursor(document)
        index = 0
        while True:
            cursor = document.find(term, cursor)
            if cursor.isNull():
                break
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            fmt = QTextCharFormat()
            fmt.setBackground(background)
            fmt.setForeground(foreground)
            selection.format = fmt
            selections.append(selection)
            if focus_occurrence is not None and index == focus_occurrence:
                target = QTextCursor(cursor)
            index += 1
        self.text.setExtraSelections(selections)
        if target is not None:
            self.text.setTextCursor(target)
            self.text.ensureCursorVisible()

    def clear_search(self) -> bool:
        if not self._search_term:
            return False
        self._search_term = ""
        self.text.setExtraSelections([])
        return True
