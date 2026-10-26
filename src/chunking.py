"""Phân đoạn văn bản thành chunk, kèm metadata phân tầng cho thống kê thực nghiệm.

Hai chiến lược, tự chọn theo cấu trúc văn bản:
- structure_aware_chunking: quy chế/quy định có mốc "Điều N." ở đầu dòng (kể cả dạng
  OCR mất dấu "Dieu N.") → mỗi Điều một chunk, bảo toàn phân cấp Điều/Khoản.
- fallback_chunking: văn bản hành chính (thông báo, kế hoạch, công văn, đơn, bản mô
  tả CTĐT) không có "Điều" → cắt theo câu/đoạn văn rồi gộp tới ngưỡng ký tự.

Sliding-window overlap (overlap_chars):
  Khi một Điều/đoạn phải cắt thành nhiều phần, phần sau sẽ lặp lại một đoạn cuối
  của phần trước (tối đa overlap_chars ký tự, cắt ở ranh giới câu). Điều này giúp
  thông tin nằm ở biên giữa hai chunk không bị "tách đôi" — embedding của mỗi chunk
  mang đủ ngữ cảnh để cosine similarity với câu hỏi vẫn đủ cao, tránh miss Hit@K.

PHẦN MỞ RỘNG (nửa sau file) — bộ chunking thực nghiệm đếm theo TOKEN:
  `DocumentChunker` ở trên là code production, cắt theo KÝ TỰ và đang tạo ra 388
  chunk đã index trong ChromaDB. Phần mở rộng bên dưới cung cấp 3 chiến lược chuẩn
  hóa theo token để so sánh thực nghiệm: `fixed_size_chunking()` (512 token, overlap
  0), `recursive_chunking()` (đệ quy theo phân cấp ranh giới), `structure_aware_chunking()`
  (Điều/Khoản/Điểm + metadata phân cấp ở đầu chunk), kèm tokenizer chuẩn và cơ chế
  khóa nguyên khối bảng Markdown. Phần này KHÔNG được `ingest.py` gọi — đổi nó không
  làm thay đổi corpus đã index, nhờ vậy các số đo Hit@K/MRR cũ vẫn so sánh được.
"""

import re
from typing import Callable, Sequence

from src.config import settings

# "Điều N." phải nằm ở đầu dòng: một thông báo có câu trích dẫn "...theo Điều 5."
# không phải văn bản cấu trúc Điều/Khoản; nhận nhầm sẽ mất toàn bộ nội dung trước đó.
# Nhận thêm dạng OCR mất dấu thanh ("Dieu 4.") và dạng lỗi font PDF ("Ðiều 4.") vì
# toàn bộ PDF scan ở Tầng 1 đi qua OCR tiếng Việt không giữ được dấu.
ARTICLE_WORD = r"[ĐÐD][iI](?:[êềếểễệEeÉéÈè])?[uUùú]"
ARTICLE_HEADING_RE = re.compile(rf"^\s*({ARTICLE_WORD}\s*\d+\.)", re.MULTILINE)
PARAGRAPH_RE = re.compile(r"\n\s*\n")
SENTENCE_RE = re.compile(r"(?<=[.!?:;])\s+")


def has_article_structure(text: str) -> bool:
    """Văn bản có ít nhất một tiêu đề 'Điều N.' ở đầu dòng hay không."""
    return ARTICLE_HEADING_RE.search(text) is not None


def canonical_article(raw_heading: str) -> str:
    """'Dieu 4.' (OCR) / 'Ðiều 4.' (lỗi font) → 'Điều 4.' để trích dẫn không lỗi dấu."""
    number = re.search(r"\d+", raw_heading).group()
    return f"Điều {number}."


class DocumentChunker:
    """Cắt văn bản thành chunk; mọi chunk đều mang tiền tố [Tên văn bản] để giữ ngữ cảnh."""

    def __init__(self, max_chars: int = 1200, min_chars: int = 20, overlap_chars: int = 150):
        # max_chars ~ 600 token bge-m3 (tăng từ 1000→1200 để mỗi Điều có thêm chỗ
        # trước khi phải cắt; tiếng Việt ~2.0 ký tự/token nên 1200 ≈ 600 token).
        # min_chars để loại chunk vụn (số trang, "Nơi nhận:", chữ ký).
        # overlap_chars: số ký tự lặp lại ở đầu chunk kế tiếp khi cắt dài —
        #   cắt ở ranh giới câu gần nhất để không tách giữa câu.
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.overlap_chars = max(0, min(overlap_chars, max_chars // 3))

    def chunk_document(self, doc: dict) -> list[dict]:
        """doc = {"title", "content", "tier"} → [{"text", "tier", "source"}, ...]."""
        content = doc["content"]
        if has_article_structure(content):
            texts = self.structure_aware_chunking(content, doc_title=doc["title"])
        else:
            texts = self.fallback_chunking(content, doc_title=doc["title"])
        return [{"text": text, "tier": doc["tier"], "source": doc["title"]} for text in texts]

    def structure_aware_chunking(self, text: str, doc_title: str = "Quy chế Đào tạo") -> list[str]:
        """Cắt bảo toàn cấu trúc phân cấp theo Điều/Khoản và làm giàu ngữ cảnh."""
        articles = ARTICLE_HEADING_RE.split(text)
        chunks = []

        # Phần mở đầu (quốc hiệu, tên cơ quan, số hiệu, "QUYẾT ĐỊNH", các "Căn cứ…")
        # nằm trước mốc "Điều 1." — bỏ đi là mất nguồn gốc văn bản, mà với quyết định
        # scan thì đó là cả trang 1.
        for piece in self._pack_text(articles[0]):
            chunks.append(f"[{doc_title}] - [Phần mở đầu] \n {piece}")

        for i in range(1, len(articles), 2):
            article_title = canonical_article(articles[i].strip())
            article_content = articles[i + 1].strip() if i + 1 < len(articles) else ""

            if len(article_content) <= self.max_chars:
                # Gắn tiền tố metadata vào đầu chunk để tăng độ chính xác khi tìm kiếm
                chunks.append(f"[{doc_title}] - [{article_title}] \n {article_content}")
                continue

            # Điều quá dài (thường do nuốt cả Phụ lục/bảng biểu phía sau) phải cắt nhỏ,
            # nếu không embedding của nó là trung bình mờ của hàng nghìn dòng và không
            # thể truy xuất chính xác. Overlap đảm bảo Khoản cuối của một phần vẫn xuất
            # hiện ở đầu phần kế để không mất tín hiệu điều khoản tại biên cắt.
            pieces = self._pack_text(article_content)
            for part, piece in enumerate(pieces, start=1):
                chunks.append(f"[{doc_title}] - [{article_title}] (phần {part}/{len(pieces)}) \n {piece}")

        return chunks

    def fallback_chunking(self, text: str, doc_title: str = "Quy chế Đào tạo") -> list[str]:
        """Chia văn bản không có 'Điều' theo đoạn văn, gộp đến max_chars."""
        return [f"[{doc_title}]\n{piece}" for piece in self._pack_text(text)]

    def _overlap_prefix(self, prev_chunk: str) -> str:
        """Trích đoạn cuối của prev_chunk (≤ overlap_chars) làm tiền tố overlap.

        Cắt ở ranh giới câu (dấu chấm/hỏi/cảm) để không nhúng câu dở dang.
        Nếu không tìm được ranh giới câu nào trong vùng overlap, lấy nguyên đoạn.
        """
        if not self.overlap_chars or not prev_chunk:
            return ""
        tail = prev_chunk[-self.overlap_chars:]
        # Tìm ranh giới câu sớm nhất trong đoạn tail để bắt đầu từ câu hoàn chỉnh
        match = SENTENCE_RE.search(tail)
        if match:
            tail = tail[match.start():].lstrip()
        return tail

    def _pack_text(self, text: str) -> list[str]:
        """Cắt văn bản tự do thành các khúc ≤ max_chars với sliding-window overlap.

        PDF trích xuất ra thường không có dòng trống (mỗi dòng một '\\n'), nên đoạn văn
        dài được cắt tiếp ở ranh giới câu — việc này đồng thời nối lại các dòng bị
        xuống dòng cứng giữa câu.

        Overlap: khi một đoạn phải sang chunk mới, chunk mới bắt đầu bằng đoạn cuối
        của chunk trước (≤ overlap_chars ký tự, cắt ở ranh giới câu). Giúp tín hiệu
        liên quan đến điều khoản nằm ở biên được "nhân đôi" trong không gian vector.
        """
        paragraphs = [p.strip() for p in PARAGRAPH_RE.split(text) if p.strip()]
        blocks = [block for p in paragraphs for block in self._split_oversized(p)]

        chunks: list[str] = []
        buffer = ""
        for block in blocks:
            candidate = f"{buffer}\n\n{block}" if buffer else block
            if buffer and len(candidate) > self.max_chars:
                chunks.append(buffer)
                # Bắt đầu buffer mới từ overlap của chunk cũ + block hiện tại
                prefix = self._overlap_prefix(buffer)
                buffer = f"{prefix}\n\n{block}".lstrip() if prefix else block
            else:
                buffer = candidate
        if buffer:
            chunks.append(buffer)

        return [chunk.strip() for chunk in chunks if len(chunk.strip()) >= self.min_chars]

    def _split_oversized(self, paragraph: str) -> list[str]:
        """Cắt đoạn văn dài hơn max_chars ở ranh giới câu; câu quá dài thì cắt cứng."""
        if len(paragraph) <= self.max_chars:
            return [paragraph]

        sentences = []
        for sentence in SENTENCE_RE.split(paragraph):
            sentence = sentence.strip()
            while len(sentence) > self.max_chars:
                sentences.append(sentence[:self.max_chars])
                sentence = sentence[self.max_chars:].strip()
            if sentence:
                sentences.append(sentence)

        pieces = []
        buffer = ""
        for sentence in sentences:
            candidate = f"{buffer} {sentence}" if buffer else sentence
            if buffer and len(candidate) > self.max_chars:
                pieces.append(buffer)
                # Overlap ở cấp câu: bắt đầu chunk mới từ câu cuối của chunk trước
                prefix = self._overlap_prefix(buffer)
                buffer = f"{prefix} {sentence}".lstrip() if prefix else sentence
            else:
                buffer = candidate
        if buffer:
            pieces.append(buffer)
        return pieces


# =============================================================================
# PHẦN MỞ RỘNG — 3 CHIẾN LƯỢC CHUNKING ĐẾM THEO TOKEN (NGHIÊN CỨU THỰC NGHIỆM)
# =============================================================================
#
# TRÙNG TÊN CÓ CHỦ ĐÍCH: `structure_aware_chunking()` cấp module bên dưới là bản thực
# nghiệm đếm theo TOKEN; `DocumentChunker.structure_aware_chunking()` ở trên là bản
# production đếm theo KÝ TỰ (đang tạo ra 388 chunk đã index). Hai hàm độc lập, dùng
# `chunk_with_strategy()` để gọi bản thực nghiệm, `DocumentChunker()` cho production.

DEFAULT_MAX_TOKENS = 512
DEFAULT_OVERLAP_TOKENS = 0
# Sàn ngân sách token: dưới mức này thì cắt tiếp chỉ sinh chunk vụn vô nghĩa.
DEFAULT_MIN_TOKENS = 8
# Chunk được nhúng bằng bge-m3 nên tokenizer của chính bge-m3 (XLM-RoBERTa) là thước
# đo trung thực nhất cho mốc "512 token"; đổi EMBEDDING_MODEL thì mốc tự đổi theo.
DEFAULT_TOKENIZER_MODEL = settings().text("EMBEDDING_MODEL", "BAAI/bge-m3")

# Thứ tự ranh giới ưu tiên của cắt đệ quy: đoạn văn -> dòng -> câu -> mệnh đề -> từ.
# Phần tử "" cuối cùng là chốt chặn: cắt cứng theo token khi không còn ranh giới nào.
DEFAULT_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", "")

# Số token dự phòng cho hậu tố " (phần i/n)" khi một Khoản phải cắt thành nhiều phần.
_PART_MARKER_ALLOWANCE = 8
# Nhãn Khoản/Điểm bị ranh giới câu tách rời khỏi thân ("1." trong "1. Nội dung...")
# chỉ 1-2 token; dán lại rẻ hơn là để nó thành một chunk rác chiếm chỗ trong top-K.
_MICRO_FRAGMENT_TOKENS = 4

# Khoản: "1." / "1)" / "1-" ở ĐẦU dòng. `(?!\d)` chặn số thập phân và số tiền
# ("1.500.000", "15.000 đồng"); `\d{1,2}` chặn năm ("2021.").
CLAUSE_HEADING_RE = re.compile(r"^[ \t]*(\d{1,2})[.)\-–—][ \t]*(?!\d)", re.MULTILINE)
# Điểm: "a)" / "a." ở ĐẦU dòng — cấp nhỏ nhất trong phân cấp văn bản quy phạm.
POINT_HEADING_RE = re.compile(r"^[ \t]*([a-zA-Z])[.)][ \t]*(?![\d)])", re.MULTILINE)
# Dòng bảng Markdown: bắt đầu VÀ kết thúc bằng '|' (áp dụng cả cho dòng phân cách
# "|---|---|" vì nó cũng thỏa mẫu này).
TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_MIN_LINES = 2

# (nhãn Khoản, nhãn Điểm, nội dung) — đơn vị nhỏ nhất mà Chiến lược 3 thao tác.
Unit = tuple[str | None, str | None, str]


# --------------------------------------------------------------------- Tokenizer

class BaseTokenCounter:
    """Hai phép toán tối thiểu mà mọi chiến lược chunking cần ở một tokenizer.

    Chỉ cần `count` (đo độ dài) và `window` (lấy một lát token) — không bắt buộc
    expose id token, nhờ vậy cả tokenizer thật lẫn bộ đếm xấp xỉ đều cài được.
    """

    name = "base"

    def count(self, text: str) -> int:
        """Số token của `text`."""
        raise NotImplementedError

    def window(self, text: str, start: int, length: int) -> str:
        """Đoạn văn bản gồm `length` token tính từ token thứ `start`."""
        raise NotImplementedError

    def windows(self, text: str, length: int, overlap: int) -> list[str]:
        """Các cửa sổ `length` token chồng lấp `overlap` token, mỗi cửa sổ không vượt `length`.

        Bản mặc định gọi `window()` lặp lại; tokenizer thật override để mã hóa văn bản
        MỘT lần (PDF OCR 15.000 token mà encode lại cho mỗi cửa sổ thì rất chậm) và để
        bước nhảy tính theo số token thật sự đã lấy.
        """
        total = self.count(text)
        step = max(1, length - overlap)
        return [piece for piece in
                (self.window(text, start, length) for start in range(0, total, step))
                if piece.strip()]


class HuggingFaceTokenCounter(BaseTokenCounter):
    """Tokenizer HuggingFace — mặc định BAAI/bge-m3, đúng model đang nhúng chunk.

    Nạp model lười ở lần dùng đầu tiên: import module này không kéo theo tải trọng,
    và trên Google Colab lần gọi đầu chỉ mất vài giây rồi ở lại RAM cho các lần sau.

    Với văn bản dài hơn 8192 token, transformers in cảnh báo "Token indices sequence
    length is longer than the specified maximum sequence length" — vô hại, vì ở đây chỉ
    đếm và cắt token chứ không nạp chuỗi đó vào model.
    """

    name = "huggingface"

    def __init__(self, model_name: str = DEFAULT_TOKENIZER_MODEL):
        self.model_name = model_name
        self._tokenizer = None

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        return self._tokenizer

    def encode(self, text: str) -> list[int]:
        # add_special_tokens=False: <s>/</s> là việc của model lúc nhúng, không phải
        # của chunk. Tính vào đây sẽ khiến chunk thật hụt 2 token so với mốc 512.
        return list(self.tokenizer.encode(text, add_special_tokens=False))

    def decode(self, token_ids: Sequence[int]) -> str:
        return self.tokenizer.decode(list(token_ids), skip_special_tokens=True)

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def window(self, text: str, start: int, length: int) -> str:
        return self._shrink(self.encode(text)[start:start + length], length)[1]

    def windows(self, text: str, length: int, overlap: int) -> list[str]:
        ids = self.encode(text)
        pieces: list[str] = []
        start = 0
        while start < len(ids):
            taken, piece = self._shrink(ids[start:start + length], length)
            if piece.strip():
                pieces.append(piece)
            # Tiến theo số token THẬT SỰ đã lấy (đã bị _shrink gọt) chứ không theo
            # `length`: phần bị gọt mà không được cửa sổ kế tiếp nhặt lại thì mất hẳn
            # khỏi corpus, và thí nghiệm sẽ so sánh trên những tập văn bản không bằng nhau.
            start += max(1, taken - overlap)
        return pieces

    def _shrink(self, ids: list[int], limit: int) -> tuple[int, str]:
        """Bớt dần token cho tới khi CHUỖI THÀNH PHẨM mã hoá lại không vượt `limit`.

        Tokenizer không thuận nghịch tuyệt đối ở biên khoảng trắng: 512 id decode ra
        chuỗi có thể mã hoá lại thành 513 token. Mốc 512 của thí nghiệm phải đo trên
        chuỗi thành phẩm, nếu không Chiến lược 1 lệch đúng tiêu chí đang kiểm định.

        Returns:
            (số id đã dùng, chuỗi tương ứng) — số id để cửa sổ kế tiếp biết bước nhảy.
        """
        while ids:
            piece = self.decode(ids)
            if self.count(piece) <= limit:
                return len(ids), piece
            ids = ids[:-1]
        return 0, ""


class WhitespaceTokenCounter(BaseTokenCounter):
    """Đếm token = số từ tách theo khoảng trắng (mỗi âm tiết một token).

    Dùng khi không nạp được tokenizer HuggingFace (máy offline, Colab không mạng,
    chạy unit test) — bge-m3 tách tiếng Việt gần đúng theo âm tiết nên xấp xỉ này đủ
    để so sánh TƯƠNG ĐỐI giữa 3 chiến lược. `window` chuẩn hóa khoảng trắng khi ghép
    lại, đây là đánh đổi có ý thức của bộ đếm dự phòng.
    """

    name = "whitespace"

    def count(self, text: str) -> int:
        return len(text.split())

    def window(self, text: str, start: int, length: int) -> str:
        return " ".join(text.split()[start:start + length])


_TOKEN_COUNTER_CACHE: dict[str, BaseTokenCounter] = {}


def get_token_counter(model_name: str | None = None) -> BaseTokenCounter:
    """Tokenizer chuẩn, cache theo tên model; tự rơi về đếm-theo-từ nếu không nạp được.

    Không raise: thí nghiệm trên Colab thường chạy máy không có `transformers` hoặc
    không có mạng, và việc so sánh 3 chiến lược vẫn có nghĩa với bộ đếm xấp xỉ.
    """
    name = model_name or DEFAULT_TOKENIZER_MODEL
    if name in _TOKEN_COUNTER_CACHE:
        return _TOKEN_COUNTER_CACHE[name]
    try:
        counter: BaseTokenCounter = HuggingFaceTokenCounter(name)
        counter.count("khoi dong tokenizer")  # ép nạp model để lỗi lộ ra ngay tại đây
    except Exception as exc:  # noqa: BLE001 - mọi lỗi nạp model đều phải lùi về bộ đếm dự phòng
        print(f"[Chunking] Không nạp được tokenizer '{name}' ({exc}) — chuyển sang đếm theo khoảng trắng.")
        counter = WhitespaceTokenCounter()
    _TOKEN_COUNTER_CACHE[name] = counter
    return counter


# ------------------------------------------------------- Khóa nguyên khối bảng Markdown

def split_around_tables(text: str) -> list[tuple[str, bool]]:
    """Tách văn bản thành `[(đoạn, có_phải_bảng), ...]`, bảng Markdown nằm ở đoạn riêng.

    Cần ít nhất `TABLE_MIN_LINES` (2) dòng '|' liền nhau mới được coi là bảng: một
    dòng '|' mồ côi (OCR đọc nhầm gạch đầu dòng, công thức) mà bị khóa sẽ sinh chunk
    rác và cắt đứt đoạn văn đang liền mạch.
    """
    lines = text.split("\n")

    # Gom dòng thành các khối cùng loại (dòng bảng / không phải dòng bảng) liền nhau.
    blocks: list[tuple[list[str], bool]] = []
    for line in lines:
        is_table_line = bool(TABLE_LINE_RE.match(line))
        if blocks and blocks[-1][1] == is_table_line:
            blocks[-1][0].append(line)
        else:
            blocks.append(([line], is_table_line))

    segments: list[tuple[str, bool]] = []
    for block_lines, is_table_line in blocks:
        is_table = is_table_line and len(block_lines) >= TABLE_MIN_LINES
        segments.append(("\n".join(block_lines), is_table))

    # Dán lại các đoạn văn bản thường bị khối '|' mồ côi chen giữa làm tách rời.
    merged: list[tuple[str, bool]] = []
    for segment, is_table in segments:
        if merged and not is_table and not merged[-1][1]:
            merged[-1] = (f"{merged[-1][0]}\n{segment}", False)
        else:
            merged.append((segment, is_table))
    return merged


def _chunk_with_table_lock(text: str, chunk_fn: Callable[[str], list[str]],
                           lock_markdown_tables: bool = True,
                           table_prefix: str = "") -> list[str]:
    """Chạy `chunk_fn` trên phần văn bản, còn bảng Markdown thì khóa thành 1 chunk.

    Bảng vẫn được trả ra nguyên khối KỂ CẢ khi dài hơn max_tokens: thà một chunk bảng
    vượt ngưỡng còn hơn hai nửa bảng — hàng bị tách khỏi tiêu đề cột thì embedding vô
    nghĩa và generator không thể biết cột nào thuộc dòng nào. Đây là ngoại lệ duy nhất
    của mốc 512 token, và là ngoại lệ có chủ đích.
    """
    if not lock_markdown_tables:
        return chunk_fn(text)

    chunks: list[str] = []
    for segment, is_table in split_around_tables(text):
        if not segment.strip():
            continue
        if is_table:
            table = segment.strip()
            chunks.append(f"{table_prefix}{table}" if table_prefix else table)
        else:
            chunks.extend(chunk_fn(segment))
    return chunks


# ---------------------------------------------------------- Chiến lược 1: Fixed-size

def _hard_slice(text: str, counter: BaseTokenCounter, max_tokens: int,
                overlap_tokens: int = 0) -> list[str]:
    """Cắt cứng theo cửa sổ token — chốt chặn cuối khi không còn ranh giới cú pháp.

    `overlap_tokens = 0` cho cắt dứt khoát không trùng lặp (mặc định của thí nghiệm);
    lớn hơn 0 cho cửa sổ trượt chồng lấp của Chiến lược 1.
    """
    if not text.strip():
        return []
    if counter.count(text) <= max_tokens:
        return [text]
    return counter.windows(text, max_tokens, overlap_tokens)


def _validate_budget(max_tokens: int, overlap_tokens: int) -> None:
    """Chặn cấu hình vô nghĩa trước khi tốn thời gian nạp tokenizer."""
    if max_tokens <= 0:
        raise ValueError(f"max_tokens phải > 0, nhận {max_tokens}")
    if not 0 <= overlap_tokens < max_tokens:
        raise ValueError(f"overlap_tokens phải nằm trong [0, {max_tokens}), nhận {overlap_tokens}")


def fixed_size_chunking(text: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
                        token_counter: BaseTokenCounter | None = None,
                        lock_markdown_tables: bool = True) -> list[str]:
    """Chiến lược 1 — cắt cố định theo token, baseline của nghiên cứu thực nghiệm.

    Không quan tâm ranh giới ngữ pháp: cửa sổ trượt với bước nhảy `max_tokens -
    overlap_tokens` token. Mặc định 512 token / overlap 0 (đúng chuẩn so sánh, các
    chunk rời nhau hoàn toàn nên tổng token của chunk bằng tổng token văn bản).
    Chunk cuối có thể ngắn hơn.

    Khác biệt duy nhất so với fixed-size "ngây thơ" là bảng Markdown vẫn được khóa
    nguyên khối — đặt `lock_markdown_tables=False` nếu cần baseline tuyệt đối.

    Args:
        text: văn bản đầu vào (đã qua loader, có thể chứa bảng Markdown).
        max_tokens: kích thước cửa sổ, mặc định 512.
        overlap_tokens: số token đè chồng lấp, mặc định 0.
        token_counter: tokenizer; None thì dùng `get_token_counter()`.
        lock_markdown_tables: có tách và khóa bảng Markdown hay không.

    Returns:
        Danh sách chunk theo đúng thứ tự văn bản gốc.

    Raises:
        ValueError: khi `max_tokens <= 0` hoặc `overlap_tokens` ngoài khoảng
            `[0, max_tokens)`.
    """
    _validate_budget(max_tokens, overlap_tokens)
    counter = token_counter or get_token_counter()

    def _cut(segment: str) -> list[str]:
        return _hard_slice(segment.strip(), counter, max_tokens, overlap_tokens)

    return _chunk_with_table_lock(text, _cut, lock_markdown_tables)


# --------------------------------------------------------- Chiến lược 2: Recursive

def _merge_pieces(pieces: list[str], separator: str, rest: Sequence[str],
                  counter: BaseTokenCounter, max_tokens: int) -> list[str]:
    """Gộp tham lam các mảnh liền kề (nối lại bằng `separator`) tới ngưỡng token.

    Mảnh nào MỘT MÌNH đã vượt ngưỡng thì đệ quy xuống cấp ranh giới nhỏ hơn — đúng
    tinh thần recursive character text splitting: chỉ cắt ở cấp nhỏ khi cấp lớn bất
    khả thi, không bao giờ cắt giữa câu nếu vẫn còn ranh giới câu để thử.
    """
    merged: list[str] = []
    buffer = ""
    for piece in pieces:
        candidate = f"{buffer}{separator}{piece}" if buffer else piece
        if counter.count(candidate) <= max_tokens:
            buffer = candidate
            continue
        if buffer and counter.count(buffer) <= _MICRO_FRAGMENT_TOKENS:
            # Nhãn vụn ("16." bị ranh giới '. ' tách khỏi thân Khoản): dán lại rồi cắt
            # cả khối ở cấp ranh giới nhỏ hơn. Để nhãn đứng riêng sẽ vừa sinh chunk
            # 1 token rác chiếm chỗ trong top-K, vừa làm mốc Khoản mất dấu chấm.
            merged.extend(_recursive_split(candidate, rest, counter, max_tokens))
            buffer = ""
            continue
        if buffer:
            merged.append(buffer)
            buffer = ""
        if counter.count(piece) > max_tokens:
            merged.extend(_recursive_split(piece, rest, counter, max_tokens))
        else:
            buffer = piece
    if buffer:
        merged.append(buffer)
    return merged


def _recursive_split(text: str, separators: Sequence[str], counter: BaseTokenCounter,
                     max_tokens: int) -> list[str]:
    """Cắt đệ quy: thử ranh giới lớn nhất có mặt trong văn bản, quá dài thì xuống cấp nhỏ."""
    if counter.count(text) <= max_tokens:
        return [text]

    for index, separator in enumerate(separators):
        if separator and separator not in text:
            continue
        if not separator:
            # Hết ranh giới cú pháp (một "câu" dài hơn max_tokens) -> cắt cứng theo token.
            return _hard_slice(text, counter, max_tokens)
        pieces = [piece.strip() for piece in text.split(separator) if piece.strip()]
        return _merge_pieces(pieces, separator, separators[index + 1:], counter, max_tokens)
    return [text]


def _apply_overlap(chunks: list[str], overlap_tokens: int,
                   counter: BaseTokenCounter) -> list[str]:
    """Nối đầu mỗi chunk bằng `overlap_tokens` token cuối của chunk trước (0 = không làm gì)."""
    if overlap_tokens <= 0 or len(chunks) < 2:
        return chunks
    overlapped = [chunks[0]]
    for previous, current in zip(chunks, chunks[1:]):
        start = max(0, counter.count(previous) - overlap_tokens)
        tail = counter.window(previous, start, overlap_tokens).strip()
        overlapped.append(f"{tail}\n{current}" if tail else current)
    return overlapped


def recursive_chunking(text: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                       overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
                       separators: Sequence[str] = DEFAULT_SEPARATORS,
                       token_counter: BaseTokenCounter | None = None,
                       lock_markdown_tables: bool = True) -> list[str]:
    """Chiến lược 2 — cắt đệ quy theo phân cấp ranh giới, mục tiêu 512 token.

    Phân cấp mặc định: đoạn văn ('\\n\\n') -> dòng ('\\n') -> câu ('. ' '! ' '? ')
    -> mệnh đề ('; ' ', ') -> từ (' ') -> cắt cứng theo token. Mỗi chunk là tập hợp
    các đơn vị NGỮ PHÁP lớn nhất gộp được mà không vượt max_tokens, nên ranh giới
    chunk rơi vào chỗ ngắt tự nhiên thay vì giữa từ (điểm mà cắt cố định hay vi phạm).

    Overlap được áp dụng SAU khi cắt, tính theo token (mặc định 0). Lưu ý: overlap
    không bắc qua bảng Markdown vì bảng là chunk độc lập.

    Args:
        text: văn bản đầu vào.
        max_tokens: ngưỡng token mục tiêu của mỗi chunk.
        overlap_tokens: số token lặp lại ở đầu chunk kế tiếp.
        separators: dãy ranh giới ưu tiên, thử từ trái sang phải.
        token_counter: tokenizer; None thì dùng `get_token_counter()`.
        lock_markdown_tables: có tách và khóa bảng Markdown hay không.

    Returns:
        Danh sách chunk theo đúng thứ tự văn bản gốc.

    Raises:
        ValueError: khi `max_tokens <= 0` hoặc `overlap_tokens` ngoài `[0, max_tokens)`.
    """
    _validate_budget(max_tokens, overlap_tokens)
    counter = token_counter or get_token_counter()

    def _cut(segment: str) -> list[str]:
        pieces = _recursive_split(segment.strip(), separators, counter, max_tokens)
        return _apply_overlap(pieces, overlap_tokens, counter)

    return _chunk_with_table_lock(text, _cut, lock_markdown_tables)


# --------------------------------------------- Chiến lược 3: Structure-aware (Điều/Khoản/Điểm)

def _split_keep_markers(text: str, pattern: re.Pattern[str]) -> list[tuple[str | None, str]]:
    """Cắt `text` tại các mốc của `pattern`, GIỮ nguyên dòng tiêu đề trong phần thân.

    Trả về `[(nhãn, thân), ...]`; phần tử đầu có nhãn None nếu tồn tại nội dung nằm
    trước mốc thứ nhất (lời dẫn của Điều, phần "Căn cứ…"). Không dùng `pattern.split()`
    vì split() trả về nhóm bắt chứ không trả về dòng tiêu đề cùng phần thân của nó,
    mà chính dòng "1." / "a)" đó phải nằm trong chunk để generator trích dẫn được.

    Args:
        text: đoạn văn bản cần bóc mốc.
        pattern: regex MULTILINE có ĐÚNG MỘT nhóm bắt (nhãn của mốc).
    """
    matches = list(pattern.finditer(text))
    if not matches:
        return [(None, text.strip())] if text.strip() else []

    segments: list[tuple[str | None, str]] = []
    lead = text[:matches[0].start()].strip()
    if lead:
        segments.append((None, lead))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start():end].strip()
        if body:
            segments.append((match.group(1), body))
    return segments


def _article_units(article_body: str) -> list[Unit]:
    """Bóc thân một Điều thành các đơn vị (Khoản, Điểm, nội dung) nhỏ nhất, giữ thứ tự.

    Đơn vị nhỏ nhất là Điểm nếu Khoản có Điểm; nếu không là cả Khoản; nếu Điều không
    có Khoản nào (văn bản viết liền) thì là cả thân Điều với nhãn None.
    """
    units: list[Unit] = []
    for clause_label, clause_body in _split_keep_markers(article_body, CLAUSE_HEADING_RE):
        if clause_label is None:
            # Lời dẫn của Điều ("Điều 8 quy định về…") — không thuộc Khoản nào.
            units.append((None, None, clause_body))
            continue
        point_segments = _split_keep_markers(clause_body, POINT_HEADING_RE)
        if len(point_segments) == 1 and point_segments[0][0] is None:
            units.append((clause_label, None, clause_body))
            continue
        for point_label, point_body in point_segments:
            # point_label None = dòng mở đầu Khoản ("1. Khoản một có hai điểm:"),
            # vẫn phải gắn nhãn Khoản để không mất tiêu đề khi gộp chunk.
            units.append((clause_label, point_label, point_body))
    return units


def _label_range(kind: str, labels: Sequence[str]) -> str:
    """['1','2'] -> 'Khoản 1-2'; ['a'] -> 'Điểm a'; rỗng -> ''.

    Dùng nhãn ĐẦU và CUỐI theo thứ tự văn bản (không sort) vì '10' < '2' theo chuỗi.
    """
    if not labels:
        return ""
    first, last = labels[0], labels[-1]
    return f"{kind} {first}" if first == last else f"{kind} {first}-{last}"


def _hierarchical_prefix(doc_title: str, article_label: str | None,
                         clause_labels: Sequence[str],
                         point_labels: Sequence[str]) -> str:
    """Chuỗi metadata phân cấp chèn vào ĐẦU chunk.

    Định dạng: '[Tên văn bản] - [Điều N.] - [Khoản x-y] - [Điểm a-b]'.
    Cấp nào không có thì bỏ trống chứ không in nhãn rỗng; văn bản trước Điều 1
    nhận nhãn '[Phần mở đầu]' (quốc hiệu, số hiệu quyết định, các căn cứ).
    """
    parts = [doc_title, article_label or "Phần mở đầu"]
    clause = _label_range("Khoản", clause_labels)
    if clause:
        parts.append(clause)
    point = _label_range("Điểm", point_labels)
    if point:
        parts.append(point)
    return "[" + "] - [".join(parts) + "]"


def _flush_group(doc_title: str, article_label: str | None, group: list[Unit],
                 counter: BaseTokenCounter, max_tokens: int) -> list[str]:
    """Biến một nhóm unit liền kề thành 1..n chunk, mỗi chunk mang tiền tố phân cấp.

    Nếu cả nhóm vẫn vượt max_tokens (Khoản nuốt nguyên một phụ lục) thì thân được cắt
    tiếp bằng chiến lược đệ quy với ngân sách ĐÃ TRỪ tiền tố, và mỗi phần nhận hậu tố
    '(phần i/n)' — nhờ vậy chunk thành phẩm luôn nằm trong mốc token của thí nghiệm.
    """
    if not group:
        return []
    clause_labels = [label for label, _point, _text in group if label is not None]
    point_labels = [label for _clause, label, _text in group if label is not None]
    prefix = _hierarchical_prefix(doc_title, article_label, clause_labels, point_labels)
    body = "\n".join(text for _clause, _point, text in group).strip()
    if not body:
        return []

    budget = max(DEFAULT_MIN_TOKENS, max_tokens - counter.count(prefix) - _PART_MARKER_ALLOWANCE)
    if counter.count(body) <= budget:
        return [f"{prefix}\n{body}"]

    parts = recursive_chunking(body, max_tokens=budget, token_counter=counter,
                               lock_markdown_tables=False)
    total = len(parts)
    return [f"{prefix} (phần {index}/{total})\n{part}" for index, part in enumerate(parts, start=1)]


def _starts_new_group(group: list[Unit], unit: Unit) -> bool:
    """Unit không nhãn Khoản luôn đứng riêng, không bị gộp vào chunk của Khoản khác.

    Dòng không khớp mẫu Khoản (lời dẫn của Điều, hay "1.500.000 đồng là mức học phí")
    mà bị gộp vào Khoản kế tiếp thì nội dung của nó sẽ bị gán nhầm nhãn pháp lý.
    Ngược lại, hai Khoản CÓ nhãn vẫn được gộp khi còn chỗ — nhãn thành khoảng
    '[Khoản 1-2]', vừa đúng vừa tránh sinh chunk vụn nghèo ngữ cảnh.
    """
    return unit[0] is None or group[-1][0] is None


def _emit_units(doc_title: str, article_label: str | None, units: list[Unit],
                counter: BaseTokenCounter, max_tokens: int) -> list[str]:
    """Gộp tham lam các unit liền kề cho tới khi thêm một unit nữa sẽ phải cắt chunk.

    Gộp là cần thiết: một Điểm 15 từ mà đứng riêng thành một chunk thì embedding của nó
    quá nghèo ngữ cảnh, và Hit@K tính trên số chunk nên chunk vụn làm nhiễu cả thí nghiệm.
    """
    chunks: list[str] = []
    group: list[Unit] = []
    rendered: list[str] = []
    for unit in units:
        if group and not _starts_new_group(group, unit):
            candidate = group + [unit]
            candidate_render = _flush_group(doc_title, article_label, candidate, counter, max_tokens)
            if len(candidate_render) == 1:
                group, rendered = candidate, candidate_render
                continue
        if group:
            chunks.extend(rendered)
        group = [unit]
        rendered = _flush_group(doc_title, article_label, group, counter, max_tokens)
    chunks.extend(rendered)
    return chunks


def _chunk_article_segment(segment: str, doc_title: str, carry_label: str | None,
                           counter: BaseTokenCounter,
                           max_tokens: int) -> tuple[list[str], str | None]:
    """Chunk một đoạn văn bản KHÔNG chứa bảng; trả về (danh_sách_chunk, nhãn_Điều_cuối).

    `carry_label` là nhãn Điều đang mở lúc đoạn này bắt đầu. Cần vì bảng Markdown nằm
    giữa một Điều bị `split_around_tables` tách thành segment riêng, nên phần văn bản
    SAU bảng vẫn thuộc Điều đó chứ không phải Phần mở đầu.
    """
    pieces = ARTICLE_HEADING_RE.split(segment)
    chunks: list[str] = []
    label = carry_label

    lead = pieces[0].strip()
    if lead:
        if label is None:
            # Lời dẫn trước Điều 1: quốc hiệu, "QUYẾT ĐỊNH", các "Căn cứ…" — không có
            # cấu trúc Khoản nên không bóc mốc, tránh nhận nhầm số hiệu thành Khoản.
            chunks.extend(_emit_units(doc_title, None, [(None, None, lead)], counter, max_tokens))
        else:
            # Đoạn nối tiếp một Điều đang mở (thường là sau một bảng): vẫn bóc Khoản
            # để nhãn phân cấp không bị tụt về mức Điều.
            chunks.extend(_emit_units(doc_title, label, _article_units(lead), counter, max_tokens))

    for index in range(1, len(pieces), 2):
        label = canonical_article(pieces[index].strip())
        body = pieces[index + 1] if index + 1 < len(pieces) else ""
        if not body.strip():
            continue
        chunks.extend(_emit_units(doc_title, label, _article_units(body), counter, max_tokens))

    return chunks, label


def structure_aware_chunking(text: str, doc_title: str = "Văn bản",
                             max_tokens: int = DEFAULT_MAX_TOKENS,
                             token_counter: BaseTokenCounter | None = None,
                             lock_markdown_tables: bool = True) -> list[str]:
    """Chiến lược 3 — cắt bảo toàn cấu trúc Điều/Khoản/Điểm, ngưỡng theo token.

    Mỗi chunk mang chuỗi metadata phân cấp ở ĐẦU:
        '[Tên văn bản] - [Điều N.] - [Khoản x-y] - [Điểm a-b]'
    để ngữ cảnh pháp lý (điều nào, khoản nào) nằm chung vector với nội dung: câu hỏi
    "Khoản 5 Điều 8 quy định gì về vay vốn" khớp được cả phần nhãn chứ không chỉ phần
    thân, và câu trả lời trích dẫn đúng cấp mà không cần đọc lại toàn văn bản.

    Thứ tự xử lý: (1) tách bảng Markdown và khóa nguyên khối — bảng nhận nhãn
    '[Bảng biểu]' và nhãn Điều đang mở; (2) với phần văn bản, bóc mốc Điều bằng
    `ARTICLE_HEADING_RE` (nhận cả dạng OCR 'Dieu 7.' và lỗi font 'Ðiều 7.', chỉ nhận
    ở đầu dòng nên trích dẫn '…theo Điều 5.' giữa câu không bị cắt); (3) trong mỗi
    Điều, bóc tiếp Khoản rồi Điểm; (4) gộp tham lam các đơn vị liền kề tới max_tokens.

    Không nhận `overlap_tokens`: ranh giới Điều/Khoản đã là ranh giới ngữ nghĩa, lặp
    lại cơ học sẽ phá vỡ tính "một đơn vị pháp lý trọn vẹn trong một chunk".

    Args:
        text: văn bản đầu vào.
        doc_title: tên văn bản, dùng làm cấp đầu tiên của chuỗi metadata.
        max_tokens: ngưỡng token của mỗi chunk (đã tính cả tiền tố metadata).
        token_counter: tokenizer; None thì dùng `get_token_counter()`.
        lock_markdown_tables: có tách và khóa bảng Markdown hay không.

    Returns:
        Danh sách chunk, mỗi chunk bắt đầu bằng '[Tên văn bản] - [cấp…]'.
    """
    counter = token_counter or get_token_counter()
    chunks: list[str] = []
    carry_label: str | None = None

    for segment, is_table in split_around_tables(text):
        if not segment.strip():
            continue
        if is_table and lock_markdown_tables:
            label = carry_label or "Phần mở đầu"
            chunks.append(f"[{doc_title}] - [{label}] - [Bảng biểu]\n{segment.strip()}")
            continue
        segment_chunks, carry_label = _chunk_article_segment(
            segment, doc_title, carry_label, counter, max_tokens
        )
        chunks.extend(segment_chunks)

    return chunks


# ---------------------------------------------------------------- Bộ điều phối thí nghiệm

CHUNK_STRATEGIES: dict[str, Callable[..., list[str]]] = {
    "fixed": fixed_size_chunking,
    "recursive": recursive_chunking,
    "structure": structure_aware_chunking,
}


def chunk_with_strategy(strategy: str, text: str, doc_title: str = "Văn bản",
                        max_tokens: int = DEFAULT_MAX_TOKENS,
                        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
                        token_counter: BaseTokenCounter | None = None,
                        lock_markdown_tables: bool = True) -> list[str]:
    """Cổng gọi chung để chạy CÙNG MỘT văn bản qua 3 chiến lược trong thí nghiệm.

    Args:
        strategy: 'fixed' | 'recursive' | 'structure' (không phân biệt hoa thường).
        text: văn bản đầu vào.
        doc_title: tên văn bản (chỉ Chiến lược 3 dùng để dựng metadata).
        max_tokens: ngưỡng token; Chiến lược 3 bỏ qua `overlap_tokens`.
        overlap_tokens: số token chồng lấp (chỉ 'fixed' và 'recursive').
        token_counter: tokenizer dùng chung cho cả 3 chiến lược để kết quả so sánh được.
        lock_markdown_tables: áp dụng quy tắc khóa bảng cho cả 3 chiến lược.

    Returns:
        Danh sách chunk của chiến lược được chọn.

    Raises:
        ValueError: khi `strategy` không nằm trong `CHUNK_STRATEGIES`.
    """
    key = strategy.strip().lower()
    if key not in CHUNK_STRATEGIES:
        raise ValueError(
            f"strategy không hợp lệ: {strategy!r} — chọn một trong {sorted(CHUNK_STRATEGIES)}"
        )
    if key == "structure":
        return structure_aware_chunking(text, doc_title=doc_title, max_tokens=max_tokens,
                                        token_counter=token_counter,
                                        lock_markdown_tables=lock_markdown_tables)
    return CHUNK_STRATEGIES[key](text, max_tokens=max_tokens, overlap_tokens=overlap_tokens,
                                 token_counter=token_counter,
                                 lock_markdown_tables=lock_markdown_tables)

