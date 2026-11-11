from __future__ import annotations

import re
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QDialog,
    QFontComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .book import Book
from .config import Settings
from .themes import THEMES, THEME_ORDER, Theme, get_theme


class _ThemeSwatch(QAbstractButton):
    def __init__(self, theme: Theme, parent=None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        selected = self.isChecked()
        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        painter.setPen(
            QPen(QColor(self.theme.accent if selected else self.theme.border), 2 if selected else 1)
        )
        painter.setBrush(QColor(self.theme.bg))
        painter.drawRoundedRect(rect, 10, 10)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.theme.accent))
        painter.drawEllipse(QPointF(self.width() / 2, 26), 9, 9)

        font = QFont(self.font())
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold if selected else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(self.theme.text))
        painter.drawText(
            QRectF(0, 46, self.width(), 20),
            int(Qt.AlignmentFlag.AlignCenter),
            self.theme.name,
        )
        painter.end()


class _TocCheckBox(QCheckBox):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._accent = QColor("#b0522d")
        self._on_accent = QColor("#fff7ef")
        self._border = QColor("#e0d7c8")
        self._text_color = QColor("#2e2a25")
        self.setFixedHeight(24)

    def apply_theme(self, theme: Theme) -> None:
        self._accent = QColor(theme.accent)
        self._on_accent = QColor(theme.on_accent)
        self._border = QColor(theme.border)
        self._text_color = QColor(theme.text)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        side = 17.0
        box = QRectF(0.9, (self.height() - side) / 2 + 0.9, side - 1.8, side - 1.8)
        if self.hasFocus():
            ring = QColor(self._accent)
            ring.setAlpha(90)
            painter.setPen(QPen(ring, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box.adjusted(-2.2, -2.2, 2.2, 2.2), 6.2, 6.2)
        if self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._accent)
            painter.drawRoundedRect(box, 4.5, 4.5)
            pen = QPen(self._on_accent, 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            check = QPainterPath()
            check.moveTo(box.left() + 3.6, box.center().y() + 0.6)
            check.lineTo(box.center().x() - 0.8, box.bottom() - 4.7)
            check.lineTo(box.right() - 3.9, box.top() + 4.6)
            painter.drawPath(check)
        else:
            border = self._accent if self.underMouse() else self._border
            painter.setPen(QPen(border, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box, 4.5, 4.5)
        painter.setPen(self._text_color)
        painter.drawText(
            QRectF(box.right() + 9, 0, self.width() - box.right() - 9, self.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.text(),
        )
        painter.end()


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, on_change, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._on_change = on_change
        self._loading = False
        self._swatches: dict[str, _ThemeSwatch] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._apply)

        self.setWindowTitle("阅读设置")
        self.setModal(True)
        self.setFixedWidth(470)
        self._build_ui()
        self._sync_controls()
        self._update_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel("阅读设置")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        subtitle = QLabel("所有调整都会立即生效，并自动保存")
        subtitle.setObjectName("dialogSub")
        layout.addWidget(subtitle)

        theme_label = QLabel("主题")
        theme_label.setObjectName("sectionLabel")
        layout.addWidget(theme_label)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(10)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key in THEME_ORDER:
            swatch = _ThemeSwatch(THEMES[key])
            swatch.clicked.connect(lambda checked=False, k=key: self._set_theme(k))
            group.addButton(swatch)
            theme_row.addWidget(swatch)
            self._swatches[key] = swatch
        layout.addLayout(theme_row)

        fonts_label = QLabel("排版")
        fonts_label.setObjectName("sectionLabel")
        layout.addWidget(fonts_label)

        self.font_combo = QFontComboBox()
        self.font_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        self._add_row(layout, "字体", self.font_combo, None)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(12, 40)
        self.size_slider.setPageStep(2)
        self.size_slider.valueChanged.connect(self._on_font_size)
        self.size_value = QLabel()
        self._add_row(layout, "字号", self.size_slider, self.size_value)

        self.spacing_slider = QSlider(Qt.Orientation.Horizontal)
        self.spacing_slider.setRange(12, 26)
        self.spacing_slider.setPageStep(1)
        self.spacing_slider.valueChanged.connect(self._on_spacing)
        self.spacing_value = QLabel()
        self._add_row(layout, "行距", self.spacing_slider, self.spacing_value)

        color_row = QHBoxLayout()
        color_row.setSpacing(10)
        color_label = QLabel("字色")
        color_label.setObjectName("sectionLabel")
        color_label.setFixedWidth(40)
        color_label.setToolTip("正文文字颜色")
        self.color_btn = QPushButton("跟随主题")
        self.color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_btn.setIconSize(QSize(16, 16))
        self.color_btn.setToolTip("点击选择正文文字颜色")
        self.color_btn.clicked.connect(self._pick_text_color)
        self.color_default_btn = QPushButton("恢复主题色")
        self.color_default_btn.setObjectName("ghost")
        self.color_default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_default_btn.setToolTip("清除自定义颜色，跟随当前主题")
        self.color_default_btn.clicked.connect(self._reset_text_color)
        color_row.addWidget(color_label)
        color_row.addWidget(self.color_btn, 1)
        color_row.addWidget(self.color_default_btn)
        layout.addLayout(color_row)

        self.toc_check = _TocCheckBox("显示章节目录侧栏")
        self.toc_check.toggled.connect(self._on_toc_toggled)
        layout.addWidget(self.toc_check)
        layout.addSpacing(2)

        preview_label = QLabel("预览")
        preview_label.setObjectName("sectionLabel")
        layout.addWidget(preview_label)
        preview_frame = QFrame()
        preview_frame.setObjectName("Preview")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(20, 16, 20, 16)
        self.preview = QLabel("山川是不卷收的文章，日月为你掌灯伴读。")
        self.preview.setWordWrap(True)
        self.preview.setMinimumHeight(64)
        self.preview.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        preview_layout.addWidget(self.preview)
        layout.addWidget(preview_frame)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("ghost")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset)
        footer.addWidget(reset_btn)
        footer.addStretch(1)
        done_btn = QPushButton("完成")
        done_btn.setObjectName("primary")
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setDefault(True)
        done_btn.clicked.connect(self.accept)
        footer.addWidget(done_btn)
        layout.addSpacing(4)
        layout.addLayout(footer)

    def _add_row(self, layout, label_text: str, control, value: QLabel | None) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        label = QLabel(label_text)
        label.setObjectName("sectionLabel")
        label.setFixedWidth(40)
        row.addWidget(label)
        row.addWidget(control, 1)
        if value is not None:
            value.setObjectName("valueLabel")
            value.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            value.setFixedWidth(58)
            row.addWidget(value)
        layout.addLayout(row)

    def _sync_controls(self) -> None:
        self._loading = True
        for key, swatch in self._swatches.items():
            swatch.setChecked(key == self.settings.theme)
            swatch.update()
        self.font_combo.setCurrentFont(QFont(self.settings.font_family))
        self.size_slider.setValue(self.settings.font_size)
        self.size_value.setText(f"{self.settings.font_size} px")
        self.spacing_slider.setValue(round(self.settings.line_spacing * 10))
        self.spacing_value.setText(f"{self.settings.line_spacing:.1f} 倍")
        self._sync_text_color()
        self.toc_check.setChecked(self.settings.show_toc)
        self._loading = False

    def _sync_swatches(self) -> None:
        for key, swatch in self._swatches.items():
            swatch.setChecked(key == self.settings.theme)
            swatch.update()

    def _update_preview(self) -> None:
        theme = get_theme(self.settings.theme)
        family = self.settings.font_family.replace('"', "")
        text_color = self.settings.text_color or theme.text
        self.toc_check.apply_theme(theme)
        self.preview.setStyleSheet(
            "QLabel { background: transparent;"
            f" color: {text_color};"
            f' font-family: "{family}";'
            f" font-size: {self.settings.font_size}px; }}"
        )

    def _color_icon(self, color: QColor) -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(get_theme(self.settings.theme).border), 1.2))
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(0.7, 0.7, 14.6, 14.6), 4, 4)
        painter.end()
        return QIcon(pixmap)

    def _sync_text_color(self) -> None:
        theme = get_theme(self.settings.theme)
        color = QColor(self.settings.text_color or theme.text)
        self.color_btn.setIcon(self._color_icon(color))
        if self.settings.text_color:
            self.color_btn.setText(f"自定义  {color.name().upper()}")
        else:
            self.color_btn.setText("跟随主题")
        self.color_default_btn.setEnabled(bool(self.settings.text_color))

    def _set_text_color(self, color: QColor | None) -> None:
        if color is not None and color.isValid():
            self.settings.text_color = color.name()
        else:
            self.settings.text_color = ""
        self._sync_text_color()
        self._update_preview()
        self._queue()

    def _pick_text_color(self) -> None:
        theme = get_theme(self.settings.theme)
        current = QColor(self.settings.text_color or theme.text)
        color = QColorDialog.getColor(current, self, "选择正文文字颜色")
        if color.isValid():
            self._set_text_color(color)

    def _reset_text_color(self) -> None:
        self._set_text_color(None)

    def _queue(self) -> None:
        if not self._loading:
            self._timer.start()

    def _apply(self) -> None:
        self._timer.stop()
        self._on_change()

    def _set_theme(self, key: str) -> None:
        if self._loading:
            return
        self.settings.theme = key
        self._sync_swatches()
        self._sync_text_color()
        self._update_preview()
        self._queue()

    def _on_font_changed(self, font: QFont) -> None:
        if self._loading or not font.family():
            return
        self.settings.font_family = font.family()
        self._update_preview()
        self._queue()

    def _on_font_size(self, value: int) -> None:
        if self._loading:
            return
        self.settings.font_size = int(value)
        self.size_value.setText(f"{value} px")
        self._update_preview()
        self._queue()

    def _on_spacing(self, value: int) -> None:
        if self._loading:
            return
        self.settings.line_spacing = value / 10
        self.spacing_value.setText(f"{value / 10:.1f} 倍")
        self._queue()

    def _on_toc_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        self.settings.show_toc = bool(checked)
        self._queue()

    def _reset(self) -> None:
        defaults = Settings()
        for field in (
            "theme",
            "font_family",
            "font_size",
            "line_spacing",
            "show_toc",
            "text_color",
        ):
            setattr(self.settings, field, getattr(defaults, field))
        self._sync_controls()
        self._update_preview()
        self._apply()

    def done(self, result: int) -> None:
        self._apply()
        super().done(result)


@dataclass
class _SearchHit:
    chapter_index: int
    chapter_title: str
    occurrence: int
    snippet: str


class SearchDialog(QDialog):
    def __init__(self, book: Book, on_jump, parent=None) -> None:
        super().__init__(parent)
        self.book = book
        self._on_jump = on_jump
        self._term = ""
        self._hits: list[_SearchHit] = []

        self.setWindowTitle("全书搜索")
        self.setModal(True)
        self.resize(620, 540)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        title = QLabel("全书搜索")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        subtitle = QLabel(f"《{self.book.title}》  ·  共 {self.book.chapter_count} 章")
        subtitle.setObjectName("dialogSub")
        layout.addWidget(subtitle)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入关键词，回车搜索全书")
        self.input.setClearButtonEnabled(True)
        self.input.returnPressed.connect(self._search)
        search_row.addWidget(self.input, 1)
        search_btn = QPushButton("搜索")
        search_btn.setObjectName("primary")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self._search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        self.status = QLabel("输入关键词，回车即可搜索全书")
        self.status.setObjectName("searchStatus")
        layout.addWidget(self.status)

        self.results = QListWidget()
        self.results.setWordWrap(False)
        self.results.setUniformItemSizes(False)
        self.results.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.results.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.results.itemActivated.connect(self._activate)
        layout.addWidget(self.results, 1)

        self.input.setFocus()

    @staticmethod
    def _snippet(text: str, start: int, end: int, radius: int = 30) -> str:
        left = max(0, start - radius)
        right = min(len(text), end + radius)
        piece = re.sub(r"\s+", " ", text[left:right]).strip()
        prefix = "…" if left > 0 else ""
        suffix = "…" if right < len(text) else ""
        return f"{prefix}{piece}{suffix}"

    def _search(self) -> None:
        term = self.input.text().strip()
        if not term:
            self.status.setText("请输入要搜索的关键词")
            return

        self._term = term
        self.results.clear()
        self._hits = []
        lower_term = term.lower()
        limit = 300

        for chapter_index, chapter in enumerate(self.book.chapters):
            content = chapter.text
            lower_content = content.lower()
            start = 0
            occurrence = 0
            while len(self._hits) < limit:
                position = lower_content.find(lower_term, start)
                if position < 0:
                    break
                snippet = self._snippet(content, position, position + len(term))
                self._hits.append(
                    _SearchHit(chapter_index, chapter.title, occurrence, snippet)
                )
                occurrence += 1
                start = position + max(1, len(term))

        for hit in self._hits:
            item = QListWidgetItem(f"{hit.chapter_title}\n{hit.snippet}")
            item.setData(Qt.ItemDataRole.UserRole, (hit.chapter_index, hit.occurrence))
            item.setToolTip(hit.snippet)
            self.results.addItem(item)

        if self._hits:
            note = "（仅显示前 300 处）" if len(self._hits) >= limit else ""
            self.status.setText(f"找到 {len(self._hits)} 处结果{note}")
            self.results.setCurrentRow(0)
            self.results.setFocus()
        else:
            self.status.setText(f"没有找到「{term}」")

    def _activate(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        chapter_index, occurrence = data
        self._on_jump(chapter_index, self._term, occurrence)
        self.accept()
