from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import QByteArray, QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from .book import load_book
from .bookshelf import BookshelfPage
from .config import BookEntry, Library, Settings
from .dialogs import SettingsDialog
from .icons import app_icon
from .mini import MiniReaderWindow
from .reader import ReaderPage
from .themes import app_qss, get_theme


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.load()
        self.library = Library()

        self.setWindowTitle("墨读")
        self.resize(1200, 800)
        self.setMinimumSize(960, 640)
        self.setAcceptDrops(True)

        self.stack = QStackedWidget()
        self.shelf = BookshelfPage(self.library)
        self.reader = ReaderPage(self.settings, self.library)
        self.stack.addWidget(self.shelf)
        self.stack.addWidget(self.reader)
        self.setCentralWidget(self.stack)

        self.mini: MiniReaderWindow | None = None
        self._mini_prev_state = Qt.WindowState.WindowNoState
        self._mini_last_pos = None

        self.shelf.open_requested.connect(self._open_path)
        self.shelf.import_requested.connect(self._import_dialog)
        self.shelf.remove_requested.connect(self._remove_book)
        self.reader.back_requested.connect(self._show_shelf)
        self.reader.settings_requested.connect(self._open_settings)
        self.reader.mini_requested.connect(self._enter_mini)

        self._apply_theme()

        if self.settings.geometry:
            try:
                geometry = QByteArray.fromBase64(
                    self.settings.geometry.encode("ascii")
                )
                self.restoreGeometry(geometry)
            except Exception:
                self._center_on_screen()
        else:
            self._center_on_screen()

        escape = QShortcut(QKeySequence("Esc"), self)
        escape.activated.connect(self._handle_escape)
        fullscreen = QShortcut(QKeySequence("F11"), self)
        fullscreen.activated.connect(self._toggle_fullscreen)

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    # ---------- 主题与设置 ----------

    def _apply_theme(self) -> None:
        theme = get_theme(self.settings.theme)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(app_qss(theme))
        self.setWindowIcon(app_icon(theme))
        self.shelf.apply_theme(theme)
        self.reader.apply_settings()

    def _on_settings_changed(self) -> None:
        self.settings.save()
        self._apply_theme()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self._on_settings_changed, self)
        dialog.exec()

    # ---------- 迷你阅读 ----------

    def _enter_mini(self) -> None:
        if (
            self.mini is not None
            or self.reader.book is None
            or self.reader.entry is None
        ):
            return
        self.reader.leave()
        entry = self.reader.entry
        mini = MiniReaderWindow(
            self.reader.book,
            entry,
            self.settings,
            self.library,
            entry.chapter,
            entry.scroll,
        )
        mini.restore_requested.connect(self._restore_from_mini)
        if self._mini_last_pos is not None:
            mini.move(self._mini_last_pos)
        self._mini_prev_state = self.windowState()
        self.mini = mini
        self.hide()
        mini.show()
        mini.raise_()
        mini.activateWindow()

    def _restore_from_mini(self) -> None:
        mini = self.mini
        if mini is None:
            return
        self.mini = None
        self._mini_last_pos = mini.pos()
        mini.persist_now()
        mini.hide()
        mini.deleteLater()
        self._show_main_window()
        if self.reader.book is not None and self.reader.entry is not None:
            self.reader.open_book(self.reader.book, self.reader.entry)

    def _show_main_window(self) -> None:
        state = self._mini_prev_state
        if state & Qt.WindowState.WindowFullScreen:
            self.showFullScreen()
        elif state & Qt.WindowState.WindowMaximized:
            self.showMaximized()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    # ---------- 导入与打开 ----------

    def _import_dialog(self) -> None:
        start_dir = self.settings.last_dir or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "导入 TXT 小说",
            start_dir,
            "TXT 小说 (*.txt);;所有文件 (*.*)",
        )
        if not files:
            return
        self.settings.last_dir = str(Path(files[0]).parent)
        self.settings.save()
        entries = self.import_files(files)
        if len(files) == 1 and entries:
            self._open_path(entries[0].path)

    def import_files(self, paths: list[str]) -> list[BookEntry]:
        entries: list[BookEntry] = []
        seen: set[str] = set()
        for raw in paths:
            path = Path(raw).expanduser()
            if not path.is_file():
                continue
            entry = self.library.add(str(path))
            if entry.key not in seen:
                seen.add(entry.key)
                entries.append(entry)
        if entries:
            self.library.save()
            self.shelf.refresh()
        return entries

    def _open_path(self, path: str) -> None:
        file_path = Path(path)
        if not file_path.is_file():
            QMessageBox.warning(
                self,
                "无法打开",
                f"找不到文件：\n{file_path}\n\n文件可能已被移动或删除。",
            )
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            book = load_book(file_path)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(
                self,
                "打开失败",
                f"无法读取这本小说：\n{exc}",
            )
            return
        QApplication.restoreOverrideCursor()

        if self.stack.currentWidget() is self.reader:
            self.reader.leave()

        entry = self.library.add(str(file_path))
        entry.last_read_at = time.time()
        self.library.save()
        self.reader.open_book(book, entry)
        self.stack.setCurrentWidget(self.reader)
        self.setWindowTitle(f"{book.title} — 墨读")

    def _show_shelf(self) -> None:
        self.reader.leave()
        self.shelf.refresh()
        self.stack.setCurrentWidget(self.shelf)
        self.setWindowTitle("墨读")

    def _remove_book(self, path: str) -> None:
        entry = self.library.get(path)
        if entry is None:
            return
        answer = QMessageBox.question(
            self,
            "移除书籍",
            f"从书架移除《{entry.title}》？\n原始文件不会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.library.remove(path)
            self.library.save()
            self.shelf.refresh()

    def open_files(self, paths: list[str]) -> None:
        files = [path for path in paths if Path(path).is_file()]
        if not files:
            return
        entries = self.import_files(files)
        if entries:
            self._open_path(entries[0].path)

    # ---------- 窗口行为 ----------

    def _handle_escape(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            return
        if self.stack.currentWidget() is self.reader:
            if not self.reader.clear_search():
                self._show_shelf()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if any(
            url.isLocalFile() and url.toLocalFile().lower().endswith(".txt")
            for url in urls
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".txt")
        ]
        if not paths:
            return
        entries = self.import_files(paths)
        if len(entries) == 1:
            self._open_path(entries[0].path)
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        if self.mini is not None:
            mini = self.mini
            self.mini = None
            mini.close_silently()
            mini.deleteLater()
        else:
            self.reader.leave()
        self.settings.geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.settings.save()
        self.library.save()
        super().closeEvent(event)
