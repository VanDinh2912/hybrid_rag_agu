"""Contextual chunk header cho T5b — GẮN NHÃN VỊ TRÍ PHÁP LÝ VÀO ĐẦU `page_content`.

Vì sao cần
----------
Chunk production (`DocumentChunker`) chỉ mang `[tên văn bản] - [Điều N.]`; 95/342 chunk
của index mới thậm chí chỉ có `[tên văn bản]` (đường fallback của văn bản không có Điều).
Câu hỏi kiểu "Khoản 2 Điều 8 quy định gì" vì thế chỉ khớp được phần thân, không khớp
được nhãn phân cấp. T5b chèn thêm Chương/Điều/Khoản/Điểm vào ĐẦU chunk TRƯỚC khi embed
+ BM25, build vào một thư mục index MỚI.

Phạm vi module này (viết trước, CHƯA build index — chờ PA-1 chốt corpus)
----------------------------------------------------------------------
Đây là hàm THUẦN, không đọc/ghi đĩa, không gọi model. Build thật chỉ được phép ghi vào
thư mục khác `chroma_db/` và `chroma_db_vie/` (bản thực nghiệm từ 28-10 nằm ở
`indexes/experimental/chroma_db_vie/` — đường dẫn mới đã được nối vào `PROTECTED_INDEX_DIRS`
vì chốt so theo đường dẫn resolve, không theo tên cuối);
`ensure_separate_index_target()` là chốt chặn cho việc đó. Thiết kế đã đăng ký trước
(data/loop/README.md, mục T5/5b).

Hai quyết định phải nói rõ vì đề bài kiểm thử hỏi thẳng
-------------------------------------------------------
1. **Header LÀ một phần của `page_content`** (giống hệt header hiện có của production,
   vốn đã đi vào `contexts` gửi generator). Vì thế "phần ngữ cảnh gửi generator" sẽ
   chứa header — theo thiết kế, không phải rò rỉ. Phần HIỂN THỊ NGUỒN (`sources`) lấy
   `source`/`tier`/`chunk_id` từ **metadata**, không đọc header, nên citation không
   thể bị header làm sai. Thân chunk sau header được giữ nguyên từng ký tự.
2. **Chương chỉ được ghi khi biết chắc**: tiêu đề Chương nằm ngay trong chunk, hoặc
   build truyền `chapter=` theo thứ tự tài liệu qua `chapters_for_chunks()`. Module
   KHÔNG đoán Chương từ tên tệp hay từ vị trí chunk_id. Văn bản hiện tại hầu như không
   giữ tiêu đề Chương trong chunk (chỉ 32/342 chunk có chữ "Chương", phần lớn là cụm
   từ trong câu), nên phần lớn header sẽ chỉ có tên văn bản + Điều/Khoản/Điểm.

Nhãn dự phòng (không bao giờ "None" / chuỗi rỗng)
-------------------------------------------------
`Phần mở đầu` (lời dẫn trước Điều 1), `Bảng biểu` (chunk bảng), `Phụ lục` (chunk bắt
đầu bằng "PHỤ LỤC"), `Toàn văn` (chunk không có Điều và không thuộc ba loại trên).

Cờ: `ENABLE_CONTEXTUAL_HEADER` mặc định `0`; TẮT thì `apply_contextual_headers()`
trả lại đúng danh sách chuỗi đầu vào, không đổi một ký tự.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from src.core.config import settings

ENABLE_CONTEXTUAL_HEADER_ENV = "ENABLE_CONTEXTUAL_HEADER"

DEFAULT_TITLE = "Văn bản"
FALLBACK_PREAMBLE = "Phần mở đầu"
FALLBACK_TABLE = "Bảng biểu"
FALLBACK_APPENDIX = "Phụ lục"
FALLBACK_WHOLE = "Toàn văn"

#: Index đang được pipeline sản xuất dùng; TUYỆT ĐỐI không ghi đè.
#: `ensure_separate_index_target()` giải mỗi mục theo GỐC REPO (`root / name`) rồi so đường
#: dẫn đã resolve — khớp theo TÊN CUỐI không đủ, nên khi index dời chỗ phải NỐI đường dẫn
#: mới, nếu không chốt lỏng ngay trên chính dữ liệu mà nó bảo vệ (probe:
#: `tmp/restructure/guard_probe_phase2b.py`). Tên cũ giữ lại cho máy chưa dời thư mục.
#: Hệ quả CÓ CHỦ ĐÍCH của mục `indexes/experimental/…`: chốt cũng từ chối mọi đích là THƯ
#: MỤC CHA của index được bảo vệ, nên `indexes/` và `indexes/experimental/` không còn là
#: đích build hợp lệ — build index mới vẫn phải là thư mục con phía trong
#: (`indexes/experimental/<tên_mới>`), tức chỉ CHẶT hơn, không lỏng hơn.
PROTECTED_INDEX_DIRS = (
    "chroma_db",
    "chroma_db_vie",
    "indexes/experimental/chroma_db_vie",
    "indexes/experimental/chroma_db_headers_old",
)

# Dòng đầu của chunk production:
#   "[tên văn bản] - [Điều 8.] \n ..."
#   "[tên văn bản] - [Điều 8.] (phần 2/3) \n ..."
#   "[tên văn bản] - [Phần mở đầu] \n ..."
#   "[tên văn bản]\n..."
_FIRST_LINE_HEADER_RE = re.compile(r"^\[(?P<title>[^\]]*)\](?P<rest>[^\n]*)")
_ARTICLE_LABEL_RE = re.compile(r"^\s*Điều\s*(\d+)\s*\.?\s*$", re.IGNORECASE)
_ARTICLE_IN_BODY_RE = re.compile(r"^\s*(?:Điều|[ĐÐD]ieu)\s*(\d+)\s*\.", re.MULTILINE)

# Chương: "Chương II", "CHƯƠNG 2", kèm dạng OCR mất dấu "Chuong II".
_CHAPTER_RE = re.compile(
    r"^\s*(?:CHƯƠNG|Chương|CHUONG|Chuong)\s+([IVXLCDM]+|\d+)\b", re.MULTILINE
)
_APPENDIX_RE = re.compile(r"^\s*(?:PHỤ LỤC|Phụ lục|PHU LUC|Phu luc)\b", re.MULTILINE)

# Cùng quy ước với `src/indexing/chunking.py` (Khoản 1-2 chữ số, Điểm một chữ cái ở đầu dòng).
_CLAUSE_LABEL_RE = re.compile(r"^[ \t]*(\d{1,2})[.)\-–—][ \t]*(?!\d)", re.MULTILINE)
_POINT_LABEL_RE = re.compile(r"^[ \t]*([a-zA-Z])[.)][ \t]*(?![\d)])", re.MULTILINE)

_MD_TABLE_SEP_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$", re.MULTILINE
)


# --------------------------------------------------------------------- cờ
def contextual_header_enabled() -> bool:
    """Cờ T5b. Mặc định TẮT; giá trị rác không bật được (cùng kiểu các cờ khác)."""
    return settings()._flag(ENABLE_CONTEXTUAL_HEADER_ENV, "0")


# --------------------------------------------------------------------- phân tích chunk
@dataclass(frozen=True)
class ParsedChunk:
    """Chunk đã tách dòng header cũ; `body` là phần còn lại NGUYÊN VĂN."""

    title: Optional[str]
    labels: tuple[str, ...]
    suffix: str
    body: str
    had_header: bool

    @property
    def label(self) -> Optional[str]:
        """Nhãn ĐẦU TIÊN của header cũ (tương thích với dữ liệu production)."""
        return self.labels[0] if self.labels else None


def _parse_header_labels(rest: str) -> tuple[tuple[str, ...], str]:
    """Tách chuỗi sau `[title]` thành danh sách nhãn `[...]` + phần đuôi ngoài nhãn.

    Duyệt tuần tự thay vì regex một phát để header nhiều tầng (do chính module này
    sinh ra) đọc lại được: nhờ vậy `contextualize_text()` idempotent, không cộng dồn
    `[Khoản …]`/`[Điểm …]` sau mỗi lần chạy.
    """
    labels: list[str] = []
    cursor = rest
    while True:
        match = re.match(r"^\s*-\s*\[([^\]]*)\]", cursor)
        if match is None:
            break
        cleaned = _clean_label(match.group(1))
        if cleaned:
            labels.append(cleaned)
        cursor = cursor[match.end():]
    suffix = " ".join(cursor.split())
    return tuple(labels), suffix


def parse_chunk(text: str) -> ParsedChunk:
    """Tách dòng header `[tên] - [nhãn…] (phần i/n)` khỏi thân chunk.

    Không có header (dòng đầu không bắt đầu bằng `[...]`) thì coi TOÀN BỘ text là thân.
    `body` không bao giờ bị strip — build phải giữ nguyên văn nội dung gốc.
    """
    raw = text or ""
    first_line, sep, rest = raw.partition("\n")
    match = _FIRST_LINE_HEADER_RE.match(first_line)
    if match is None:
        return ParsedChunk(None, (), "", raw, False)
    title = _clean_label(match.group("title"))
    labels, suffix = _parse_header_labels(match.group("rest"))
    return ParsedChunk(title, labels, suffix, rest if sep else "", True)


def _clean_label(value: Optional[str]) -> Optional[str]:
    """Chuẩn hóa nhãn đọc từ dữ liệu; 'None'/rỗng coi như KHÔNG có."""
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    if not cleaned or cleaned.lower() == "none":
        return None
    return cleaned


def _normalise_chapter(value: Optional[str]) -> Optional[str]:
    """'II' -> 'Chương II'; 'Chương II' giữ nguyên; rỗng -> None."""
    cleaned = _clean_label(value)
    if not cleaned:
        return None
    if cleaned.lower().startswith("chương") or cleaned.lower().startswith("chuong"):
        return cleaned
    return f"Chương {cleaned}"


def looks_like_table(text: str) -> bool:
    """Chunk bảng: có dòng phân cách Markdown, hoặc >=2 dòng chứa >=2 dấu `|`."""
    if not text:
        return False
    if _MD_TABLE_SEP_RE.search(text):
        return True
    pipe_lines = [line for line in text.splitlines() if line.count("|") >= 2]
    return len(pipe_lines) >= 2


def _label_range(kind: str, labels: Sequence[str]) -> Optional[str]:
    """['1','2','3'] -> 'Khoản 1-3'; ['a'] -> 'Điểm a'; rỗng -> None."""
    if not labels:
        return None
    first, last = labels[0], labels[-1]
    return f"{kind} {first}" if first == last else f"{kind} {first}-{last}"


# --------------------------------------------------------------------- dựng header
@dataclass(frozen=True)
class ChunkHeader:
    """Nhãn sẽ chèn trước thân chunk. `fallback` chỉ xuất hiện khi KHÔNG có Điều."""

    title: str
    chapter: Optional[str] = None
    article: Optional[str] = None
    clause: Optional[str] = None
    point: Optional[str] = None
    fallback: Optional[str] = None
    suffix: str = ""

    def labels(self) -> list[str]:
        out = [self.title]
        for value in (self.chapter, self.article, self.clause, self.point, self.fallback):
            if value:
                out.append(value)
        return out

    def render(self) -> str:
        """Chuỗi header chuẩn: `[title] - [Chương II] - [Điều 8] - [Khoản 2] (phần 1/3)`."""
        rendered = " - ".join(f"[{label}]" for label in self.labels())
        if self.suffix:
            rendered = f"{rendered} {self.suffix}"
        return rendered


def build_header(
    text: str,
    *,
    title: Optional[str] = None,
    chapter: Optional[str] = None,
) -> tuple[ChunkHeader, str]:
    """Tính header cho MỘT chunk; trả `(header, body_nguyên_văn)`.

    Args:
        text: chunk (có hoặc không có header cũ).
        title: tên văn bản do build truyền vào; None thì lấy từ header cũ.
        chapter: nhãn Chương do build truyền theo thứ tự tài liệu; None thì chỉ nhận
            tiêu đề Chương nằm ngay trong chunk.
    """
    parsed = parse_chunk(text)
    resolved_title = _clean_label(title) or parsed.title or DEFAULT_TITLE

    label_article = label_chapter = label_fallback = None
    for label in parsed.labels:
        article_match = _ARTICLE_LABEL_RE.match(label)
        if article_match and label_article is None:
            label_article = f"Điều {article_match.group(1)}"
        if label_chapter is None and label.casefold().startswith(("chương", "chuong")):
            label_chapter = label
        if label_fallback is None and label.casefold() in {
            FALLBACK_PREAMBLE.casefold(),
            FALLBACK_TABLE.casefold(),
            FALLBACK_APPENDIX.casefold(),
            FALLBACK_WHOLE.casefold(),
        }:
            label_fallback = label
    body_article_match = _ARTICLE_IN_BODY_RE.search(parsed.body or "")
    body_article = (
        f"Điều {body_article_match.group(1)}" if body_article_match else None
    )
    article = label_article or body_article

    chapter_match = _CHAPTER_RE.search(parsed.body or "")
    chapter_label = _normalise_chapter(chapter) or label_chapter or (
        f"Chương {chapter_match.group(1)}" if chapter_match else None
    )

    clause = point = None
    if article:
        clause_labels = _CLAUSE_LABEL_RE.findall(parsed.body or "")
        point_labels = _POINT_LABEL_RE.findall(parsed.body or "")
        clause = _label_range("Khoản", clause_labels)
        point = _label_range("Điểm", point_labels)

    fallback = None
    if article is None:
        if label_fallback:
            fallback = label_fallback
        elif parsed.label and parsed.label.casefold() == FALLBACK_PREAMBLE.casefold():
            fallback = FALLBACK_PREAMBLE
        elif _APPENDIX_RE.search(parsed.body or ""):
            fallback = FALLBACK_APPENDIX
        elif looks_like_table(parsed.body or ""):
            fallback = FALLBACK_TABLE
        else:
            fallback = FALLBACK_WHOLE

    header = ChunkHeader(
        title=resolved_title,
        chapter=chapter_label,
        article=article,
        clause=clause,
        point=point,
        fallback=fallback,
        suffix=parsed.suffix,
    )
    return header, parsed.body


def contextualize_text(
    text: str,
    *,
    title: Optional[str] = None,
    chapter: Optional[str] = None,
) -> str:
    """Trả chunk với header mới ở dòng đầu; thân giữ NGUYÊN VĂN byte-for-byte.

    Idempotent: gọi lại trên đầu ra chính nó cho cùng một chuỗi (header cũ được thay,
    không cộng dồn).
    """
    header, body = build_header(text, title=title, chapter=chapter)
    rendered = header.render()
    return f"{rendered}\n{body}" if body else rendered


def apply_contextual_headers(
    texts: Sequence[str],
    *,
    titles: Optional[Sequence[Optional[str]]] = None,
    chapters: Optional[Sequence[Optional[str]]] = None,
) -> list[str]:
    """Cổng build-time: cờ TẮT trả lại đúng danh sách đầu vào, cờ BẬT mới chèn header.

    `titles`/`chapters` (nếu có) phải cùng độ dài với `texts`; không khớp là lỗi lập
    trình, ném `ValueError` thay vì đoán.
    """
    items = list(texts)
    if not contextual_header_enabled():
        return items
    n = len(items)
    title_list = list(titles) if titles is not None else [None] * n
    chapter_list = list(chapters) if chapters is not None else [None] * n
    if len(title_list) != n or len(chapter_list) != n:
        raise ValueError(
            f"apply_contextual_headers: titles={len(title_list)} / chapters={len(chapter_list)} "
            f"nhưng texts={n} — không đoán vị trí."
        )
    return [
        contextualize_text(text, title=title_list[i], chapter=chapter_list[i])
        for i, text in enumerate(items)
    ]


# --------------------------------------------------------------------- Chương theo tài liệu
def chapter_spans(full_text: str) -> list[tuple[int, str]]:
    """Vị trí ký tự + nhãn của mọi tiêu đề Chương trong TOÀN VĂN (theo thứ tự)."""
    return [
        (match.start(), f"Chương {match.group(1)}")
        for match in _CHAPTER_RE.finditer(full_text or "")
    ]


def chapter_at(spans: Sequence[tuple[int, str]], offset: int) -> Optional[str]:
    """Chương đang mở tại `offset` (tiêu đề gần nhất phía trước), None nếu trước Chương 1."""
    current = None
    for position, label in spans:
        if position > offset:
            break
        current = label
    return current


def chapters_for_chunks(full_text: str, chunks: Sequence[str]) -> list[Optional[str]]:
    """Gán Chương cho từng chunk bằng cách dò thân chunk tuần tự trong toàn văn.

    Chunk production được sinh theo đúng thứ tự tài liệu và thân là chuỗi con nguyên
    văn (trừ khi bị cắt/overlap — vẫn còn chuỗi con), nên `find` từ vị trí đã đi qua là
    đủ. Không tìm thấy thì dùng vị trí hiện tại và KHÔNG nhảy lùi — thà thiếu Chương
    còn hơn gán sai.
    """
    spans = chapter_spans(full_text)
    cursor = 0
    out: list[Optional[str]] = []
    for chunk in chunks:
        body = parse_chunk(chunk).body
        probe = body.strip()
        position = full_text.find(probe, cursor) if probe else -1
        if position < 0:
            position = cursor
        else:
            cursor = position + len(probe)
        out.append(chapter_at(spans, position))
    return out


# --------------------------------------------------------------------- an toàn thư mục index
def ensure_separate_index_target(
    target: str | os.PathLike[str],
    *,
    protected: Iterable[str] = PROTECTED_INDEX_DIRS,
    repo_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Chuẩn hóa đích ghi index và CHẶN ghi đè index cũ.

    Từ chối khi đích trùng / nằm trong / là thư mục cha của một index bảo vệ, hoặc
    trùng chính gốc repo. Trả về đường dẫn tuyệt đối đã resolve để nơi gọi dùng tiếp.
    """
    root = Path(repo_root or Path.cwd()).resolve()
    raw = Path(target).expanduser()
    destination = (raw if raw.is_absolute() else root / raw).resolve()
    if destination == root:
        raise ValueError(f"Đích index {destination} trùng gốc repo — từ chối ghi.")
    for name in protected:
        protected_path = (root / name).expanduser().resolve()
        if destination == protected_path or protected_path in destination.parents:
            raise ValueError(
                f"Đích index {destination} nằm trong/trùng index bảo vệ {protected_path} "
                "— T5b chỉ được build vào thư mục MỚI."
            )
        if destination in protected_path.parents:
            raise ValueError(
                f"Đích index {destination} là thư mục cha của index bảo vệ "
                f"{protected_path} — từ chối."
            )
    return destination


def directory_digest(path: str | os.PathLike[str]) -> str:
    """SHA-256 của toàn bộ cây thư mục (tên tương đối + nội dung từng tệp).

    Dùng để chứng minh index cũ không đổi sau một bước build. Bỏ qua symlink để không
    đi ra ngoài cây. Thư mục không tồn tại -> chuỗi rỗng có tiền tố `missing:`.
    """
    root = Path(path)
    if not root.exists():
        return "missing:" + str(root)
    digest = hashlib.sha256()
    for item in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if item.is_symlink() or not item.is_file():
            continue
        relative = item.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative + b"\0" + str(item.stat().st_size).encode("ascii") + b"\0")
        with item.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()
