"""Unit test cho src/chunking.py — regex bóc tách Điều/Khoản và hai chiến lược cắt chunk."""

from src.chunking import (
    ARTICLE_HEADING_RE,
    DocumentChunker,
    canonical_article,
    has_article_structure,
)


class TestArticleHeadingRegex:
    def test_matches_standard_dieu_at_line_start(self):
        assert ARTICLE_HEADING_RE.search("\nĐiều 12.\n1. Sinh viên phải...")

    def test_matches_ocr_variant_without_tone(self):
        # PDF scan qua OCR mất dấu thanh: "Dieu 4."
        assert ARTICLE_HEADING_RE.search("\nDieu 4.\nNội dung điều")

    def test_matches_broken_font_variant(self):
        # Lỗi font PDF: "Ðiều 4." (U+00D0)
        assert ARTICLE_HEADING_RE.search("\nÐiều 4.\nNội dung điều")

    def test_rejects_inline_citation(self):
        # "theo Điều 5." giữa câu KHÔNG phải tiêu đề — chỉ đầu dòng mới được tính,
        # nếu không văn bản hành chính trích dẫn Điều sẽ bị cắt mất phần đầu.
        assert ARTICLE_HEADING_RE.search("Thông báo này căn cứ theo Điều 5.") is None


class TestCanonicalArticle:
    def test_normalizes_ocr_variant(self):
        assert canonical_article("Dieu 4.") == "Điều 4."

    def test_normalizes_broken_font_variant(self):
        assert canonical_article("Ðiều 10.") == "Điều 10."

    def test_keeps_standard_form(self):
        assert canonical_article("Điều 7.") == "Điều 7."


class TestHasArticleStructure:
    def test_true_when_heading_present(self):
        assert has_article_structure("QUY CHẾ\n\nĐiều 1.\nPhạm vi điều chỉnh...")

    def test_false_for_plain_admin_text(self):
        assert not has_article_structure("Thông báo về việc thu học phí học kỳ 1.")


class TestDocumentChunker:
    def setup_method(self):
        self.chunker = DocumentChunker()

    def test_structure_aware_one_chunk_per_article(self):
        doc = {
            "title": "Quy chế mẫu",
            "content": (
                "QUY CHẾ ĐÀO TẠO TRƯỜNG ĐẠI HỌC AN GIANG\n\n"
                "Điều 1.\nNội dung điều một đủ dài để vượt ngưỡng tối thiểu.\n\n"
                "Điều 2.\nNội dung điều hai cũng đủ dài để vượt ngưỡng tối thiểu."
            ),
            "tier": "Tầng 1",
        }
        chunks = self.chunker.chunk_document(doc)
        texts = [c["text"] for c in chunks]
        assert any("[Phần mở đầu]" in t for t in texts), "phần mở đầu trước Điều 1 phải được giữ"
        assert any("[Quy chế mẫu] - [Điều 1.]" in t for t in texts)
        assert any("[Quy chế mẫu] - [Điều 2.]" in t for t in texts)
        assert all(c["tier"] == "Tầng 1" and c["source"] == "Quy chế mẫu" for c in chunks)

    def test_long_article_split_with_part_marker(self):
        doc = {"title": "T", "content": "Điều 1.\n" + "x" * 2000, "tier": "Tầng 1"}
        chunks = self.chunker.chunk_document(doc)
        assert len(chunks) == 2
        assert "[Điều 1.]" in chunks[0]["text"] and "(phần 1/2)" in chunks[0]["text"]
        assert "(phần 2/2)" in chunks[1]["text"]

    def test_fallback_chunking_for_plain_text(self):
        doc = {
            "title": "Thông báo",
            "content": "Khoa Công nghệ thông tin thông báo thu học phí kỳ 1. "
                       "Sinh viên nộp trước ngày 15 cho giáo vụ khoa. " * 4,
            "tier": "Tầng 2",
        }
        assert not has_article_structure(doc["content"])
        chunks = self.chunker.chunk_document(doc)
        assert chunks, "văn bản không có Điều vẫn phải sinh chunk"
        assert all(c["text"].startswith("[Thông báo]\n") for c in chunks)

    def test_tiny_document_dropped_by_min_chars(self):
        doc = {"title": "T", "content": "abc", "tier": "Khác"}
        assert self.chunker.chunk_document(doc) == []
