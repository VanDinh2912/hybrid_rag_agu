"""Phân đoạn văn bản thành chunk, kèm metadata phân tầng cho thống kê thực nghiệm.

Hai chiến lược, tự chọn theo cấu trúc văn bản:
- structure_aware_chunking: quy chế/quy định có mốc "Điều N." ở đầu dòng (kể cả dạng
  OCR mất dấu "Dieu N.") → mỗi Điều một chunk, bảo toàn phân cấp Điều/Khoản.
- fallback_chunking: văn bản hành chính (thông báo, kế hoạch, công văn, đơn, bản mô
  tả CTĐT) không có "Điều" → cắt theo câu/đoạn văn rồi gộp tới ngưỡng ký tự.
"""

import re

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

    def __init__(self, max_chars: int = 1000, min_chars: int = 20):
        # max_chars ~ 512 token bge-m3: corpus tiếng Việt đo được 2.0-3.5 ký tự/token
        # (văn bản viết hoa nhiều cho tỷ lệ thấp nhất) nên lấy mốc bảo thủ 2.0.
        # min_chars để loại chunk vụn (số trang, "Nơi nhận:", chữ ký).
        self.max_chars = max_chars
        self.min_chars = min_chars

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
            # thể truy xuất chính xác.
            pieces = self._pack_text(article_content)
            for part, piece in enumerate(pieces, start=1):
                chunks.append(f"[{doc_title}] - [{article_title}] (phần {part}/{len(pieces)}) \n {piece}")

        return chunks

    def fallback_chunking(self, text: str, doc_title: str = "Quy chế Đào tạo") -> list[str]:
        """Chia văn bản không có 'Điều' theo đoạn văn, gộp đến max_chars."""
        return [f"[{doc_title}]\n{piece}" for piece in self._pack_text(text)]

    def _pack_text(self, text: str) -> list[str]:
        """Cắt văn bản tự do thành các khúc ≤ max_chars.

        PDF trích xuất ra thường không có dòng trống (mỗi dòng một '\n'), nên đoạn văn
        dài được cắt tiếp ở ranh giới câu — việc này đồng thời nối lại các dòng bị
        xuống dòng cứng giữa câu.
        """
        paragraphs = [p.strip() for p in PARAGRAPH_RE.split(text) if p.strip()]
        blocks = [block for p in paragraphs for block in self._split_oversized(p)]

        chunks = []
        buffer = ""
        for block in blocks:
            if buffer and len(buffer) + len(block) + 2 > self.max_chars:
                chunks.append(buffer)
                buffer = block
            else:
                buffer = f"{buffer}\n\n{block}" if buffer else block
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
            if buffer and len(buffer) + len(sentence) + 1 > self.max_chars:
                pieces.append(buffer)
                buffer = sentence
            else:
                buffer = f"{buffer} {sentence}" if buffer else sentence
        if buffer:
            pieces.append(buffer)
        return pieces
