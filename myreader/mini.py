from __future__ import annotations

import html
import time

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QPalette,
    QShortcut,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .book import Book, EMPTY_CHAPTER_TEXT
from .config import (
    MINI_MAX_WIDTH,
    MINI_MIN_WIDTH,
    BookEntry,
    Library,
    Settings,
)
from .icons import make_icon
from .themes import get_theme, reader_css
from .widgets import ElidedLabel

_DOC_MARGIN = 4
_HEADER_HEIGHT = 22
_GRIP_WIDTH = 6
_SAVE_DELAY = 900


class _MiniHeader(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().request_restore()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _ResizeGrip(QWidget):
    def __init__(self, side: str, window: "MiniReaderWindow") -> None:
        super().__init__(window)
        self._side = side
        self._window = window
        self._hover = False
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setToolTip("拖动调整宽度")

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        if not self._hover:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(self._window._theme.accent)
        color.setAlpha(120)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        bar_width = 3
        bar_height = min(40, max(16, self.height() - 48))
        painter.drawRoundedRect(
            (self.width() - bar_width) // 2,
            (self.height() - bar_height) // 2,
            bar_width,
            bar_height,
            1.5,
            1.5,
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._window._begin_resize(self._side, event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._window._drag_resize(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._window._end_resize()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MiniReaderWindow(QWidget):
    restore_requested = pyqtSignal()

    def __init__(
        self,
        book: Book,
        entry: BookEntry,
        settings: Settings,
        library: Library,
        chapter_index: int,
        ratio: float,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.book = book
        self.entry = entry
        self.settings = settings
        self.library = library
        self.chapter_index = max(0, min(chapter_index, len(book.chapters) - 1))
        self._theme = get_theme(settings.theme)
        self._ghost = bool(settings.mini_ghost)
        self._pending_ratio: float | None = None
        self._restore_emitted = False
        self._calibrated = False
        self._resize_side: str | None = None
        self._resize_start_x = 0
        self._resize_start_width = 0
        self._resize_start_global = 0
        self._resize_anchor: int | None = None
        self._pending_anchor: int | None = None
        self._line_height = self._compute_line_height()
        self._text_height = _DOC_MARGIN + self._line_height * 2 - 3

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_SAVE_DELAY)
        self._save_timer.timeout.connect(self._persist_progress)
        self._pending_timer = QTimer(self)
        self._pending_timer.setSingleShot(True)
        self._pending_timer.setInterval(400)
        self._pending_timer.timeout.connect(self._clear_pending_restore)

        self._build_ui()
        self._install_shortcuts()
        self._position_window()
        self._load_chapter(self.chapter_index, ratio)

    def _compute_line_height(self) -> int:
        font = QFont(self.settings.font_family)
        font.setPixelSize(self.settings.font_size)
        metrics = QFontMetrics(font)
        return max(10, round(metrics.height() * self.settings.line_spacing))

    def _text_color(self) -> QColor:
        color = QColor(self.settings.text_color)
        if color.isValid():
            return color
        return QColor(self._theme.text)

    def _build_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumWidth(MINI_MIN_WIDTH)
        self.setMaximumWidth(MINI_MAX_WIDTH)
        self.setWindowTitle(f"墨读 · {self.book.title}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("MiniCard")
        root.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 6, 12, 8)
        layout.setSpacing(2)

        header = _MiniHeader()
        header.setFixedHeight(_HEADER_HEIGHT)
        header.setToolTip("拖动移动位置 · 拖动左右边缘调整宽度 · 双击还原主窗口")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self.title_label = ElidedLabel()
        self.title_label.setObjectName("miniTitle")
        self.title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        header_layout.addWidget(self.title_label, 1)

        self.percent_label = QLabel("0.0%")
        self.percent_label.setObjectName("miniPercent")
        self.percent_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        header_layout.addWidget(self.percent_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.expand_btn = QToolButton()
        self.expand_btn.setObjectName("miniExpand")
        self.expand_btn.setToolTip("还原主窗口 (Esc)")
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.setIcon(make_icon("expand", self._theme.text, 14))
        self.expand_btn.setIconSize(QSize(14, 14))
        self.expand_btn.setFixedSize(22, 22)
        self.expand_btn.clicked.connect(self.request_restore)
        header_layout.addWidget(self.expand_btn)

        self.ghost_btn = QToolButton()
        self.ghost_btn.setObjectName("miniGhost")
        self.ghost_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ghost_btn.setIconSize(QSize(14, 14))
        self.ghost_btn.setFixedSize(22, 22)
        self.ghost_btn.clicked.connect(self._toggle_ghost)
        header_layout.addWidget(self.ghost_btn)
        layout.addWidget(header)

        divider = QFrame()
        divider.setObjectName("MiniDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        self.text = QTextBrowser()
        self.text.setObjectName("MiniText")
        self.text.setFrameShape(QFrame.Shape.NoFrame)
        self.text.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text.setOpenLinks(False)
        self.text.setOpenExternalLinks(False)
        self.text.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.text.setToolTip("滚轮逐行 · 到底自动进入下一章")
        self.text.setFixedHeight(self._text_height)
        self.text.document().setDocumentMargin(_DOC_MARGIN)
        palette = self.text.palette()
        text_color = self._text_color()
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        palette.setColor(QPalette.ColorRole.Text, text_color)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(self._theme.selection))
        palette.setColor(QPalette.ColorRole.HighlightedText, text_color)
        self.text.setPalette(palette)
        self.text.viewport().installEventFilter(self)
        scrollbar = self.text.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll)
        scrollbar.rangeChanged.connect(self._on_range_changed)
        layout.addWidget(self.text)

        self.setFixedHeight(
            6 + _HEADER_HEIGHT + 2 + 1 + 2 + self._text_height + 8 + 2
        )
        width = max(
            MINI_MIN_WIDTH, min(MINI_MAX_WIDTH, self.settings.mini_width)
        )
        self.resize(width, self.height())
        self._left_grip = _ResizeGrip("left", self)
        self._right_grip = _ResizeGrip("right", self)
        self._layout_grips()
        self._apply_ghost()

    def _style_sheet(self) -> str:
        if self._ghost:
            r, g, b, _ = QColor(self._theme.bg).getRgb()
            # QSS 的 rgba alpha 是 0~1 浮点；全透明像素会被 Windows 命中测试
            # 穿透导致收不到滚轮，保留约 1/255 的 alpha 视觉不可见但可命中
            bg = f"rgba({r}, {g}, {b}, 0.004)"
            border = f"rgba({r}, {g}, {b}, 0.004)"
        else:
            bg = self._theme.bg
            border = self._theme.border
        title_color = "transparent" if self._ghost else self._theme.text
        percent_color = "transparent" if self._ghost else self._theme.muted
        divider_color = "transparent" if self._ghost else self._theme.border
        expand_hover = "transparent" if self._ghost else self._theme.accent_soft
        if self._ghost:
            br, bg_, bb, _ = QColor(self._theme.border).getRgb()
            ghost_btn_bg = f"rgba({r}, {g}, {b}, 0.88)"
            ghost_btn_border = f"1px solid rgba({br}, {bg_}, {bb}, 0.78)"
            ghost_btn_radius = "11px"
            ghost_btn_padding = "3px"
        else:
            ghost_btn_bg = "transparent"
            ghost_btn_border = "none"
            ghost_btn_radius = "5px"
            ghost_btn_padding = "4px"
        text_color = self.settings.text_color or self._theme.text
        return f"""
QFrame#MiniCard {{
    background-color: {bg};
    border: 1px solid {border};
    border-radius: 12px;
}}
QLabel#miniTitle {{ color: {title_color}; font-size: 11px; }}
QLabel#miniPercent {{ color: {percent_color}; font-size: 10px; }}
QFrame#MiniDivider {{ background-color: {divider_color}; border: none; }}
QToolButton#miniExpand, QToolButton#miniGhost {{
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 4px;
}}
QToolButton#miniExpand:hover {{ background-color: {expand_hover}; }}
QToolButton#miniGhost {{
    background-color: {ghost_btn_bg};
    border: {ghost_btn_border};
    border-radius: {ghost_btn_radius};
    padding: {ghost_btn_padding};
}}
QToolButton#miniGhost:hover {{ background-color: {self._theme.accent_soft}; }}
QTextBrowser#MiniText {{ background: transparent; border: none; color: {text_color}; }}
"""

    def _apply_ghost(self) -> None:
        ghost = self._ghost
        self.expand_btn.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, ghost
        )
        if ghost:
            self.expand_btn.setIcon(make_icon("expand", "#00000000", 14))
            self.expand_btn.setToolTip("")
            self.ghost_btn.setIcon(make_icon("solid", self._theme.text, 14))
            self.ghost_btn.setToolTip("显示背景")
        else:
            self.expand_btn.setIcon(make_icon("expand", self._theme.text, 14))
            self.expand_btn.setToolTip("还原主窗口 (Esc)")
            self.ghost_btn.setIcon(make_icon("ghost", self._theme.text, 14))
            self.ghost_btn.setToolTip("隐藏背景，只显示文字")
        self.setStyleSheet(self._style_sheet())

    def _toggle_ghost(self) -> None:
        self._ghost = not self._ghost
        self.settings.mini_ghost = self._ghost
        self.settings.save()
        self._apply_ghost()

    def _install_shortcuts(self) -> None:
        def add(sequence: str, handler, target=None) -> None:
            shortcut = QShortcut(QKeySequence(sequence), target or self)
            shortcut.setContext(
                Qt.ShortcutContext.WidgetShortcut
                if target is not None
                else Qt.ShortcutContext.WidgetWithChildrenShortcut
            )
            shortcut.activated.connect(handler)

        add("Esc", self.request_restore)
        add("Ctrl+M", self.request_restore)
        add("Space", lambda: self._scroll_pixels(self._line_height * 2), self.text)
        add("PgDown", lambda: self._scroll_pixels(self._line_height * 2), self.text)
        add("PgUp", lambda: self._scroll_pixels(-self._line_height * 2), self.text)
        add("Shift+Space", lambda: self._scroll_pixels(-self._line_height * 2), self.text)

    def _position_window(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        if self.width() > area.width():
            self.resize(area.width(), self.height())
        margin = 24
        x = area.right() - self.width() - margin + 1
        y = area.top() + margin
        self.move(max(area.left(), x), y)

    # ---------- 宽度调整 ----------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_grips()

    def _layout_grips(self) -> None:
        if not hasattr(self, "_left_grip"):
            return
        height = self.height()
        self._left_grip.setGeometry(0, 0, _GRIP_WIDTH, height)
        self._right_grip.setGeometry(
            self.width() - _GRIP_WIDTH, 0, _GRIP_WIDTH, height
        )
        self._left_grip.raise_()
        self._right_grip.raise_()

    def _begin_resize(self, side: str, global_pos: QPoint) -> None:
        self._resize_side = side
        self._resize_start_global = global_pos.x()
        self._resize_start_x = self.x()
        self._resize_start_width = self.width()
        self._resize_anchor = self._top_position()
        self._pending_timer.stop()
        self._pending_ratio = None
        self._pending_anchor = None

    def _drag_resize(self, global_pos: QPoint) -> None:
        if self._resize_side is None:
            return
        delta = global_pos.x() - self._resize_start_global
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        area = screen.availableGeometry() if screen is not None else None
        new_x = self._resize_start_x
        if self._resize_side == "right":
            new_width = self._resize_start_width + delta
            limit = MINI_MAX_WIDTH
            if area is not None:
                limit = min(limit, area.right() - new_x + 1)
        else:
            new_width = self._resize_start_width - delta
            limit = MINI_MAX_WIDTH
            if area is not None:
                limit = min(
                    limit,
                    self._resize_start_x + self._resize_start_width - area.left(),
                )
        new_width = max(MINI_MIN_WIDTH, min(limit, new_width))
        if self._resize_side == "left":
            new_x = self._resize_start_x + self._resize_start_width - new_width
        if area is not None:
            new_x = max(
                area.left(), min(area.right() - new_width + 1, new_x)
            )
        if new_width == self.width() and new_x == self.x():
            return
        self.setGeometry(new_x, self.y(), new_width, self.height())
        if self._resize_anchor is not None:
            self._adjust_to_anchor(self._resize_anchor)

    def _end_resize(self) -> None:
        if self._resize_side is None:
            return
        anchor = self._resize_anchor
        self._resize_side = None
        self._resize_anchor = None
        if anchor is not None:
            self._pending_anchor = anchor
            self._pending_timer.start()
            self._adjust_to_anchor(anchor)
            self._snap_to_line()
        self.settings.mini_width = self.width()
        self.settings.save()
        self._update_percent()
        self._save_timer.start()

    def _top_position(self) -> int:
        cursor = self.text.cursorForPosition(QPoint(1, 0))
        return max(0, cursor.position())

    def _adjust_to_anchor(self, position: int) -> None:
        scrollbar = self.text.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return
        document = self.text.document()
        position = max(0, min(position, document.characterCount() - 1))
        cursor = QTextCursor(document)
        cursor.setPosition(position)
        offset = self.text.cursorRect(cursor).top()
        if offset:
            scrollbar.setValue(
                max(
                    scrollbar.minimum(),
                    min(scrollbar.maximum(), scrollbar.value() + offset),
                )
            )

    # ---------- 渲染与进度 ----------

    def _load_chapter(
        self, index: int, ratio: float = 0.0, focus: bool = True
    ) -> None:
        if not self.book.chapters:
            return
        index = max(0, min(index, len(self.book.chapters) - 1))
        if index != self.chapter_index:
            self._persist_progress()
        self.chapter_index = index
        self._render_chapter()
        self._update_percent()
        self._save_timer.start()
        QTimer.singleShot(0, lambda r=ratio: self._restore_scroll(r))
        if focus:
            self.text.setFocus(Qt.FocusReason.OtherFocusReason)

    def _render_chapter(self) -> None:
        chapter = self.book.chapters[self.chapter_index]
        css = reader_css(
            self._theme,
            self.settings.font_family,
            self.settings.font_size,
            self.settings.line_spacing,
            compact=True,
            transparent=True,
            text_color=self.settings.text_color,
        )
        document = self.text.document()
        document.setDefaultStyleSheet(css)
        document.setDocumentMargin(_DOC_MARGIN)

        parts = []
        for paragraph in chapter.paragraphs:
            if paragraph == EMPTY_CHAPTER_TEXT:
                parts.append(f'<p class="empty">{html.escape(paragraph)}</p>')
            else:
                parts.append(f"<p>\u3000\u3000{html.escape(paragraph)}</p>")
        self.text.setHtml("".join(parts))
        self.text.verticalScrollBar().setValue(0)
        self.title_label.setText(f"{self.book.title} · {chapter.title}")

    def _restore_scroll(self, ratio: float) -> None:
        scrollbar = self.text.verticalScrollBar()
        self._pending_anchor = None
        if ratio <= 0:
            self._pending_ratio = None
            self._pending_timer.stop()
            scrollbar.setValue(0)
            return
        self._pending_ratio = ratio
        if scrollbar.maximum() > 0:
            scrollbar.setValue(int(round(ratio * scrollbar.maximum())))
            self._snap_to_line()
        self._pending_timer.start()

    def _clear_pending_restore(self) -> None:
        self._pending_ratio = None
        self._pending_anchor = None
        self._snap_to_line()

    def _snap_to_line(self) -> None:
        scrollbar = self.text.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return
        if scrollbar.value() <= scrollbar.minimum():
            return
        if scrollbar.value() >= scrollbar.maximum():
            return
        cursor = self.text.cursorForPosition(QPoint(1, 0))
        offset = self.text.cursorRect(cursor).top()
        if offset:
            scrollbar.setValue(
                max(
                    scrollbar.minimum(),
                    min(scrollbar.maximum(), scrollbar.value() + offset),
                )
            )

    def _scroll_ratio(self) -> float:
        scrollbar = self.text.verticalScrollBar()
        if scrollbar.maximum() <= 0:
            return 0.0
        return scrollbar.value() / scrollbar.maximum()

    def _update_percent(self) -> None:
        if not self.book.chapters:
            return
        percent = (
            (self.chapter_index + self._scroll_ratio())
            / len(self.book.chapters)
            * 100
        )
        self.percent_label.setText(f"{percent:.1f}%")

    def _on_scroll(self, value: int) -> None:
        self._update_percent()
        self._save_timer.start()

    def _on_range_changed(self, minimum: int, maximum: int) -> None:
        if self._resize_anchor is not None:
            self._adjust_to_anchor(self._resize_anchor)
        elif self._pending_anchor is not None:
            self._adjust_to_anchor(self._pending_anchor)
        elif self._pending_ratio is not None and maximum > 0:
            scrollbar = self.text.verticalScrollBar()
            scrollbar.setValue(int(round(self._pending_ratio * maximum)))
        self._update_percent()

    def _persist_progress(self) -> None:
        if not self.book.chapters:
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

    def persist_now(self) -> None:
        self._save_timer.stop()
        self._persist_progress()

    # ---------- 滚动与章节 ----------

    def _scroll_pixels(self, pixels: int) -> None:
        if pixels == 0:
            return
        scrollbar = self.text.verticalScrollBar()
        if pixels > 0 and scrollbar.value() >= scrollbar.maximum():
            if self.chapter_index < len(self.book.chapters) - 1:
                self._load_chapter(self.chapter_index + 1, 0.0, focus=False)
            return
        if pixels < 0 and scrollbar.value() <= scrollbar.minimum():
            if self.chapter_index > 0:
                self._load_chapter(self.chapter_index - 1, 1.0, focus=False)
            return
        scrollbar.setValue(scrollbar.value() + pixels)
        self._snap_to_line()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.text.viewport() and event.type() == QEvent.Type.Wheel:
            pixel = event.pixelDelta().y()
            if pixel:
                self._scroll_pixels(-pixel)
            else:
                angle = event.angleDelta().y()
                if angle:
                    self._scroll_pixels(int(-angle / 120 * self._line_height))
            return True
        return super().eventFilter(obj, event)

    # ---------- 还原 ----------

    def request_restore(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:
        self._save_timer.stop()
        self._persist_progress()
        if self._restore_emitted:
            event.accept()
            return
        self._restore_emitted = True
        event.ignore()
        self.restore_requested.emit()

    def close_silently(self) -> None:
        self._save_timer.stop()
        self._persist_progress()
        self._restore_emitted = True
        self.hide()
        self.close()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.text.setFocus(Qt.FocusReason.OtherFocusReason)
        QTimer.singleShot(0, self._calibrate)

    def _calibrate(self) -> None:
        if self._calibrated:
            return
        document = self.text.document()
        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        first = self.text.cursorRect(cursor)
        cursor.movePosition(QTextCursor.MoveOperation.Down)
        second = self.text.cursorRect(cursor)
        line_height = second.top() - first.top()
        if line_height <= 0:
            return
        self._calibrated = True
        if line_height == self._line_height:
            return
        target = (
            self._pending_ratio
            if self._pending_ratio is not None
            else self._scroll_ratio()
        )
        self._line_height = line_height
        self._text_height = _DOC_MARGIN + line_height * 2 - 3
        self.text.setFixedHeight(self._text_height)
        self.setFixedHeight(
            6 + _HEADER_HEIGHT + 2 + 1 + 2 + self._text_height + 8 + 2
        )
        self._restore_scroll(target)

