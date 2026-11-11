from __future__ import annotations

from dataclasses import dataclass
from string import Template


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    bg: str
    surface: str
    card: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    on_accent: str
    accent_soft: str
    border: str
    highlight: str
    selection: str
    dark: bool = False


_THEMES = (
    Theme(
        key="paper",
        name="纸白",
        bg="#f5f1e8",
        surface="#ece5d8",
        card="#fbf8f1",
        text="#2e2a25",
        muted="#8b8173",
        accent="#b0522d",
        accent_hover="#994524",
        on_accent="#fff7ef",
        accent_soft="#eedfd4",
        border="#e0d7c8",
        highlight="#f0d488",
        selection="#e7d2c0",
    ),
    Theme(
        key="sepia",
        name="羊皮纸",
        bg="#efe3c6",
        surface="#e6d6b5",
        card="#f6ecd7",
        text="#463826",
        muted="#8b795c",
        accent="#99622f",
        accent_hover="#815022",
        on_accent="#fdf5e6",
        accent_soft="#e0cca6",
        border="#d7c39c",
        highlight="#e8c66b",
        selection="#dcc49b",
    ),
    Theme(
        key="green",
        name="护眼绿",
        bg="#dfe8d5",
        surface="#d4e1c8",
        card="#eaf2e2",
        text="#2b3a26",
        muted="#707d67",
        accent="#4c7042",
        accent_hover="#3e5e35",
        on_accent="#f5faf0",
        accent_soft="#c9dbc0",
        border="#c2d1b4",
        highlight="#ead07c",
        selection="#c2d6b4",
    ),
    Theme(
        key="night",
        name="夜间",
        bg="#15171a",
        surface="#1b1e22",
        card="#21252b",
        text="#cbc6bc",
        muted="#7e8287",
        accent="#d18a5c",
        accent_hover="#e09c6e",
        on_accent="#201710",
        accent_soft="#33291f",
        border="#2b3036",
        highlight="#574426",
        selection="#3c4857",
        dark=True,
    ),
)

THEMES = {theme.key: theme for theme in _THEMES}
THEME_ORDER = tuple(theme.key for theme in _THEMES)


def get_theme(key: str) -> Theme:
    return THEMES.get(key, THEMES["paper"])


_QSS = Template(
    """
* { outline: none; }

QWidget {
    color: $text;
    font-family: "Microsoft YaHei";
    font-size: 13px;
}
QMainWindow, QDialog, QWidget#Page { background-color: $bg; }
QWidget#Header {
    background-color: $surface;
    border-bottom: 1px solid $border;
}
QWidget#Footer {
    background-color: $bg;
    border-top: 1px solid $border;
}
QWidget#TocPanel {
    background-color: $surface;
    border-right: 1px solid $border;
}
QWidget#ShelfCanvas { background-color: $bg; }
QWidget#ReadingPane { background-color: $bg; }

QScrollArea { border: none; background: transparent; }

QLabel { background: transparent; }
QLabel#pageTitle { font-size: 24px; font-weight: 600; letter-spacing: 1px; }
QLabel#muted { color: $muted; }
QLabel#smallMuted { color: $muted; font-size: 12px; }
QLabel#dialogTitle { font-size: 18px; font-weight: 600; }
QLabel#dialogSub { color: $muted; font-size: 12px; }
QLabel#sectionLabel { color: $muted; font-size: 12px; }
QLabel#tocTitle { font-size: 14px; font-weight: 600; }
QLabel#readerBookTitle { font-size: 15px; font-weight: 600; }
QLabel#readerChapter { color: $muted; font-size: 12px; }
QLabel#percentLabel { color: $muted; font-size: 13px; }
QLabel#cardTitle { font-size: 13px; font-weight: 600; }
QLabel#cardMeta { color: $muted; font-size: 11px; }
QLabel#emptyTitle { font-size: 19px; font-weight: 600; }
QLabel#emptySub { color: $muted; font-size: 13px; }
QLabel#emptyGlyph {
    font-size: 34px;
    color: $accent;
    background-color: $card;
    border: 2px solid $border;
    border-radius: 46px;
}
QLabel#searchStatus { color: $muted; font-size: 12px; }
QLabel#valueLabel { color: $muted; font-size: 12px; }

QPushButton {
    background-color: $card;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 7px 14px;
}
QPushButton:hover { border-color: $accent; }
QPushButton:pressed { background-color: $accent_soft; }
QPushButton:disabled { color: $muted; background-color: transparent; }
QPushButton#primary {
    background-color: $accent;
    color: $on_accent;
    border: 1px solid $accent;
    font-weight: 600;
    padding: 9px 18px;
}
QPushButton#primary:hover {
    background-color: $accent_hover;
    border-color: $accent_hover;
}
QPushButton#ghost {
    background-color: transparent;
    border: none;
    color: $muted;
    padding: 8px 12px;
}
QPushButton#ghost:hover { color: $accent; background-color: $accent_soft; }
QPushButton#navButton {
    background: transparent;
    border: none;
    color: $text;
    padding: 8px 16px;
    border-radius: 8px;
}
QPushButton#navButton:hover { background-color: $accent_soft; }
QPushButton#navButton:disabled { color: $muted; background: transparent; }

QToolButton {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px;
}
QToolButton:hover { background-color: $accent_soft; }
QToolButton:checked { background-color: $accent_soft; }

QLineEdit {
    background-color: $card;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: $accent;
    selection-color: $on_accent;
}
QLineEdit:hover { border-color: $border; }
QLineEdit:focus { border-color: $accent; }

QListWidget {
    background: transparent;
    border: none;
    font-size: 13px;
}
QListWidget::item {
    padding: 7px 10px;
    margin: 1px 8px;
    border-radius: 6px;
    color: $text;
    background: transparent;
}
QListWidget::item:hover { background-color: $accent_soft; }
QListWidget::item:selected {
    background-color: $accent_soft;
    color: $text;
    border-left: 2px solid $accent;
    padding-left: 8px;
}

QScrollBar:vertical {
    background: transparent;
    width: 11px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: $border;
    min-height: 30px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal {
    background: transparent;
    height: 11px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: $border;
    min-width: 30px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover { background: $muted; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: transparent;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QComboBox {
    background-color: $card;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
}
QComboBox:hover { border-color: $accent; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: $card;
    color: $text;
    border: 1px solid $border;
    padding: 4px;
    outline: none;
    selection-background-color: $accent_soft;
    selection-color: $text;
}

QSlider::groove:horizontal {
    height: 4px;
    background: $border;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: $accent;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: $card;
    border: 2px solid $accent;
    width: 14px;
    height: 14px;
    margin: -7px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: $accent; }

QCheckBox { spacing: 8px; color: $text; }
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $border;
    border-radius: 5px;
    background-color: $card;
}
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background-color: $accent; border-color: $accent; }

QProgressBar {
    background: $border;
    border: none;
    border-radius: 2px;
    max-height: 4px;
}
QProgressBar::chunk { background: $accent; border-radius: 2px; }

QMenu {
    background-color: $card;
    border: 1px solid $border;
    padding: 6px;
}
QMenu::item {
    padding: 7px 22px 7px 12px;
    border-radius: 6px;
}
QMenu::item:selected { background-color: $accent_soft; color: $text; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }

QToolTip {
    background-color: $text;
    color: $bg;
    border: none;
    padding: 5px 8px;
}

QFrame#BookCard {
    background-color: $card;
    border: 1px solid $border;
    border-radius: 12px;
}
QFrame#BookCard:hover { border-color: $accent; }
QFrame#Divider { background-color: $border; border: none; max-height: 1px; }
QFrame#Preview {
    background-color: $bg;
    border: 1px solid $border;
    border-radius: 10px;
}
"""
)


def app_qss(theme: Theme) -> str:
    return _QSS.substitute(
        bg=theme.bg,
        surface=theme.surface,
        card=theme.card,
        text=theme.text,
        muted=theme.muted,
        accent=theme.accent,
        accent_hover=theme.accent_hover,
        on_accent=theme.on_accent,
        accent_soft=theme.accent_soft,
        border=theme.border,
    )


def reader_css(
    theme: Theme,
    font_family: str,
    font_size: int,
    line_spacing: float,
    *,
    compact: bool = False,
    transparent: bool = False,
    text_color: str = "",
) -> str:
    family = font_family.replace('"', "")
    paragraph_gap = 2 if compact else max(3, round(font_size * 0.5))
    background = "transparent" if transparent else theme.bg
    text = text_color or theme.text
    return f"""
body {{
    background-color: {background};
    color: {text};
    font-family: "{family}", "Microsoft YaHei", sans-serif;
}}
h1.chapter-title {{
    font-family: "{family}", "Microsoft YaHei", sans-serif;
    font-size: {font_size + 7}px;
    font-weight: 600;
    color: {text};
    margin-top: 2px;
    margin-bottom: 28px;
    text-align: center;
}}
p {{
    font-size: {font_size}px;
    color: {text};
    margin: 0 0 {paragraph_gap}px 0;
    line-height: {line_spacing};
}}
p.empty {{
    color: {theme.muted};
    text-align: center;
}}
"""
