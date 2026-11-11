from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def _default_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
        return base / "MoReader"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MoReader"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "MoReader"


APP_DIR = _default_data_dir()
LIBRARY_FILE = "library.json"
SETTINGS_FILE = "settings.json"
THEME_KEYS = ("paper", "sepia", "green", "night")
MINI_MIN_WIDTH = 360
MINI_MAX_WIDTH = 1600
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def _read_json(filename: str, default):
    try:
        with (APP_DIR / filename).open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _write_json(filename: str, data) -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = APP_DIR / (filename + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        tmp.replace(APP_DIR / filename)
    except OSError:
        pass


@dataclass
class Settings:
    theme: str = "paper"
    font_family: str = "Microsoft YaHei"
    font_size: int = 19
    line_spacing: float = 1.8
    show_toc: bool = True
    text_color: str = ""
    last_dir: str = ""
    geometry: str = ""
    mini_width: int = 620
    mini_ghost: bool = False

    @classmethod
    def load(cls) -> "Settings":
        data = _read_json(SETTINGS_FILE, {})
        settings = cls()
        for spec in fields(cls):
            if spec.name not in data:
                continue
            value = data[spec.name]
            default = getattr(settings, spec.name)
            if isinstance(default, bool):
                if isinstance(value, bool):
                    setattr(settings, spec.name, value)
            elif isinstance(default, int):
                if isinstance(value, int) and not isinstance(value, bool):
                    setattr(settings, spec.name, value)
            elif isinstance(default, (float, str)):
                if isinstance(value, type(default)):
                    setattr(settings, spec.name, value)
        if settings.theme not in THEME_KEYS:
            settings.theme = "paper"
        settings.font_size = min(40, max(12, settings.font_size))
        settings.line_spacing = min(2.6, max(1.2, settings.line_spacing))
        settings.mini_width = min(
            MINI_MAX_WIDTH, max(MINI_MIN_WIDTH, settings.mini_width)
        )
        value = settings.text_color.strip()
        settings.text_color = value.lower() if _HEX_COLOR.fullmatch(value) else ""
        return settings

    def save(self) -> None:
        _write_json(SETTINGS_FILE, asdict(self))


def _book_key(path: str) -> str:
    return os.path.normcase(str(Path(path).resolve()))


@dataclass
class BookEntry:
    path: str
    title: str
    added_at: float = field(default_factory=time.time)
    last_read_at: float = 0.0
    chapter: int = 0
    scroll: float = 0.0
    percent: float = 0.0
    total_chapters: int = 0

    @property
    def key(self) -> str:
        return _book_key(self.path)


class Library:
    def __init__(self) -> None:
        self.books: dict[str, BookEntry] = {}
        self._load()

    def _load(self) -> None:
        data = _read_json(LIBRARY_FILE, {})
        known = {spec.name for spec in fields(BookEntry)}
        for raw in data.get("books", []):
            if not isinstance(raw, dict) or not raw.get("path"):
                continue
            try:
                entry = BookEntry(**{k: v for k, v in raw.items() if k in known})
            except TypeError:
                continue
            self.books[entry.key] = entry

    def save(self) -> None:
        _write_json(LIBRARY_FILE, {"books": [asdict(b) for b in self.sorted_books()]})

    def add(self, path: str) -> BookEntry:
        resolved = str(Path(path).expanduser().resolve())
        key = _book_key(resolved)
        entry = self.books.get(key)
        if entry is not None:
            return entry
        entry = BookEntry(
            path=resolved,
            title=Path(resolved).stem.strip() or Path(resolved).name,
        )
        self.books[key] = entry
        return entry

    def get(self, path: str) -> BookEntry | None:
        return self.books.get(_book_key(path))

    def remove(self, path: str) -> None:
        self.books.pop(_book_key(path), None)

    def sorted_books(self) -> list[BookEntry]:
        return sorted(
            self.books.values(),
            key=lambda b: (b.last_read_at, b.added_at),
            reverse=True,
        )
