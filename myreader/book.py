from __future__ import annotations

import codecs
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from charset_normalizer import from_bytes as _detect_from_bytes
except ImportError:  # 编码识别库缺失时退化为编码尝试
    _detect_from_bytes = None

EMPTY_CHAPTER_TEXT = "（本章暂无正文）"


_NUM = r"[0-9０-９零〇一二三四五六七八九十百千万两]{1,12}"
_TITLE_PREFIX = re.compile(
    rf"^(?:正文\s*)?(?:"
    rf"第\s*{_NUM}\s*[章节回卷部篇集话幕]"
    rf"|卷\s*{_NUM}"
    rf"|楔子|序章|序言|引子|前言|自序|后记|尾声|终章"
    rf"|番外(?:篇)?(?:\s*{_NUM})?"
    rf"|完本感言"
    rf"|(?:chapter|Chapter|CHAPTER)\s*(?:[0-9]+|[IVXLCDM]+)"
    rf")"
)
_TITLE_LIMIT = 40
_JOINERS = set("的了着过是在把被和与就都也却又而")
_SEPARATORS = set(":：·、.-—（(【[")
_CHUNK_SIZE = 12000

_BOMS = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


@dataclass(frozen=True)
class Chapter:
    title: str
    paragraphs: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


@dataclass(frozen=True)
class Book:
    path: Path
    title: str
    encoding: str
    chapters: tuple[Chapter, ...]

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\ufeff", "").replace("\u200b", "")


def _text_score(text: str) -> float:
    sample = text[:6000]
    cjk = 0
    bad = 0
    for char in sample:
        if "\u4e00" <= char <= "\u9fff":
            cjk += 1
        elif char == "\ufffd" or (ord(char) < 32 and char not in "\n\t"):
            bad += 1
    return cjk * 3 - bad * 60


def decode_bytes(raw: bytes) -> tuple[str, str]:
    for bom, encoding in _BOMS:
        if raw.startswith(bom):
            try:
                return _normalize(raw.decode(encoding)), encoding
            except (UnicodeDecodeError, LookupError):
                break

    candidates: list[str] = []
    if _detect_from_bytes is not None:
        try:
            for match in list(_detect_from_bytes(raw))[:2]:
                if match.encoding:
                    candidates.append(match.encoding)
        except Exception:
            pass
    candidates.extend(("utf-8", "gb18030", "big5"))

    best: tuple[float, str, str] | None = None
    seen: set[str] = set()
    for encoding in candidates:
        key = encoding.lower().replace("_", "-")
        if key in seen:
            continue
        seen.add(key)
        try:
            text = _normalize(raw.decode(encoding))
        except (UnicodeDecodeError, LookupError):
            continue
        if key in ("utf-8", "utf-8-sig"):
            return text, encoding
        score = _text_score(text)
        if best is None or score > best[0]:
            best = (score, text, encoding)

    if best is None:
        return _normalize(raw.decode("utf-8", errors="replace")), "utf-8"
    return best[1], best[2]


def _clean_line(line: str) -> str:
    return line.strip().strip("\u3000").strip()


def _display_title(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def _is_chapter_title(line: str) -> bool:
    text = line.replace("\u3000", " ").strip()
    if not text or len(text) > _TITLE_LIMIT:
        return False
    if text.endswith(("。", "，", "；", "！", "？", "…", "”", "」", "』")):
        return False
    match = _TITLE_PREFIX.match(text)
    if match is None:
        return False
    rest = text[match.end():]
    if rest and not rest[0].isspace() and rest[0] not in _SEPARATORS:
        if rest[0] in _JOINERS:
            return False
    return True


def _split_by_size(paragraphs: list[str]) -> list[Chapter]:
    if not paragraphs:
        return []
    chunks: list[list[str]] = []
    buffer: list[str] = []
    size = 0
    for paragraph in paragraphs:
        if buffer and size + len(paragraph) > _CHUNK_SIZE:
            chunks.append(buffer)
            buffer, size = [], 0
        buffer.append(paragraph)
        size += len(paragraph)
    if buffer:
        chunks.append(buffer)

    if len(chunks) == 1:
        return [Chapter("全文", tuple(chunks[0]))]
    return [
        Chapter(f"第 {index + 1} 部分", tuple(chunk))
        for index, chunk in enumerate(chunks)
    ]


def split_chapters(text: str) -> list[Chapter]:
    lines = text.split("\n")
    markers: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if _is_chapter_title(line):
            markers.append((index, _display_title(line)))

    if len(markers) >= 2:
        chapters: list[Chapter] = []
        preface = [
            paragraph
            for paragraph in (_clean_line(line) for line in lines[: markers[0][0]])
            if paragraph
        ]
        if preface:
            chapters.append(Chapter("开始", tuple(preface)))
        for position, (line_index, title) in enumerate(markers):
            end = markers[position + 1][0] if position + 1 < len(markers) else len(lines)
            body = [
                paragraph
                for paragraph in (_clean_line(line) for line in lines[line_index + 1 : end])
                if paragraph
            ]
            if not body:
                body = [EMPTY_CHAPTER_TEXT]
            chapters.append(Chapter(title, tuple(body)))
        return chapters

    paragraphs = [
        paragraph for paragraph in (_clean_line(line) for line in lines) if paragraph
    ]
    return _split_by_size(paragraphs)


def load_book(path: str | Path) -> Book:
    file_path = Path(path)
    raw = file_path.read_bytes()
    if not raw.strip():
        raise ValueError("文件内容为空。")
    text, encoding = decode_bytes(raw)
    if not text.strip():
        raise ValueError("未能从文件中读取到文本内容。")
    chapters = split_chapters(text)
    if not chapters:
        raise ValueError("未能从文件中解析出正文。")
    title = file_path.stem.strip() or file_path.name
    return Book(
        path=file_path,
        title=title,
        encoding=encoding,
        chapters=tuple(chapters),
    )
