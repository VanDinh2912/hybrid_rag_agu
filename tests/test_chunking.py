"""Unit test cho src/chunking.py — regex bóc tách Điều/Khoản và hai chiến lược cắt chunk."""

import pytest

from src.chunking import (
    ARTICLE_HEADING_RE,
    DocumentChunker,
    HuggingFaceTokenCounter,
    WhitespaceTokenCounter,
    canonical_article,
    chunk_with_strategy,
    fixed_size_chunking,
    has_article_structure,
    recursive_chunking,
    split_around_tables,
    structure_aware_chunking,
)

# Toàn bộ test phần mở rộng dùng bộ đếm theo khoảng trắng: không tải tokenizer
# HuggingFace nên test chạy offline, nhanh và không phụ thuộc mạng của máy CI.
COUNTER = WhitespaceTokenCounter()


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


class TestFixedSizeChunking:
    """Chiến lược 1: đúng 512 token, overlap đúng 0."""

    def test_default_is_512_tokens_with_zero_overlap(self):
        text = " ".join(f"từ{i}" for i in range(1200))
        chunks = fixed_size_chunking(text, token_counter=COUNTER)
        assert [COUNTER.count(chunk) for chunk in chunks] == [512, 512, 176]
        # overlap = 0 nên không token nào bị đếm hai lần giữa các chunk.
        assert sum(COUNTER.count(chunk) for chunk in chunks) == 1200

    def test_custom_window_and_overlap(self):
        text = " ".join(f"từ{i}" for i in range(100))
        chunks = fixed_size_chunking(text, max_tokens=40, overlap_tokens=10,
                                     token_counter=COUNTER)
        # step = 30 nên cửa sổ cuối chỉ còn 10 token.
        assert [COUNTER.count(chunk) for chunk in chunks] == [40, 40, 40, 10]

    @pytest.mark.parametrize("overlap", [512, 900, -1])
    def test_rejects_invalid_overlap(self, overlap):
        with pytest.raises(ValueError):
            fixed_size_chunking("văn bản mẫu", max_tokens=512, overlap_tokens=overlap,
                                token_counter=COUNTER)

    def test_rejects_non_positive_window(self):
        with pytest.raises(ValueError):
            fixed_size_chunking("văn bản mẫu", max_tokens=0, token_counter=COUNTER)


class TestMarkdownTableLock:
    """Quy tắc 4: bảng Markdown là một chunk độc lập, không chiến lược nào được cắt."""

    TABLE = "| Mã HP | Tên HP | TC |\n|---|---|---|\n| IT01 | Cấu trúc dữ liệu | 3 |"
    LONG_TABLE = "\n".join(["| Cột A | Cột B |", "|---|---|"]
                           + [f"| ô {i} | dữ liệu {i} |" for i in range(40)])

    def test_table_is_isolated_as_its_own_segment(self):
        segments = split_around_tables(f"Trước bảng.\n{self.TABLE}\nSau bảng.")
        assert [is_table for _segment, is_table in segments] == [False, True, False]
        assert segments[1][0] == self.TABLE

    def test_lone_pipe_line_is_not_a_table(self):
        segments = split_around_tables("Dòng chữ.\n| một dòng ống mồ côi |\nDòng chữ khác.")
        assert len(segments) == 1 and segments[0][1] is False

    @pytest.mark.parametrize("strategy", ["fixed", "recursive", "structure"])
    def test_no_strategy_splits_a_table(self, strategy):
        text = f"Điều 1.\nNội dung điều một.\n{self.LONG_TABLE}"
        # max_tokens rất nhỏ: nếu bảng không bị khóa thì chắc chắn bị cắt thành nhiều mảnh.
        chunks = chunk_with_strategy(strategy, text, doc_title="QĐ 99", max_tokens=16,
                                     token_counter=COUNTER)
        whole_table = [chunk for chunk in chunks if "| ô 0 |" in chunk and "| ô 39 |" in chunk]
        assert len(whole_table) == 1, f"{strategy} đã cắt đôi bảng biểu"


class TestRecursiveChunking:
    """Chiến lược 2: đệ quy theo phân cấp đoạn văn -> câu -> từ, ngưỡng token."""

    def test_respects_token_budget_and_document_order(self):
        paragraphs = [" ".join(f"từ{i}_{j}" for j in range(60)) for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = recursive_chunking(text, max_tokens=128, token_counter=COUNTER)
        assert len(chunks) > 1
        assert all(COUNTER.count(chunk) <= 128 for chunk in chunks)
        # overlap = 0: mọi từ xuất hiện đúng một lần, đúng thứ tự văn bản gốc.
        assert [word for chunk in chunks for word in chunk.split()] == text.split()

    def test_oversized_sentence_falls_back_to_word_boundary(self):
        text = " ".join(f"từ{i}" for i in range(600))  # một "câu" 600 từ, không ranh giới
        chunks = recursive_chunking(text, max_tokens=100, token_counter=COUNTER)
        assert len(chunks) == 6
        assert all(COUNTER.count(chunk) <= 100 for chunk in chunks)

    def test_overlap_repeats_tail_tokens(self):
        text = "\n\n".join(" ".join(f"từ{i}_{j}" for j in range(50)) for i in range(4))
        chunks = recursive_chunking(text, max_tokens=50, overlap_tokens=10, token_counter=COUNTER)
        assert len(chunks) > 1
        assert all(chunk.startswith("từ") for chunk in chunks[1:])


class TestStructureAwareChunkingSpec:
    """Chiến lược 3: Điều/Khoản/Điểm + metadata phân cấp ở ĐẦU mỗi chunk."""

    DOC = (
        "QUYẾT ĐỊNH\nBan hành quy chế mẫu.\n\n"
        "Điều 5.\n"
        "1. Khoản một có hai điểm:\n"
        "a) Điểm a của khoản một.\n"
        "b) Điểm b của khoản một.\n"
        "2. Khoản hai độc lập, không có điểm.\n"
    )

    def test_hierarchical_metadata_at_chunk_head(self):
        chunks = structure_aware_chunking(self.DOC, doc_title="QĐ 99", max_tokens=40,
                                          token_counter=COUNTER)
        joined = "\n".join(chunks)
        assert "[QĐ 99] - [Phần mở đầu]" in joined
        assert "[Điều 5.]" in joined
        assert "[Khoản 1] - [Điểm a-b]" in joined
        assert "[Khoản 2]" in joined
        assert all(chunk.startswith("[QĐ 99] - [") for chunk in chunks)

    def test_whole_article_shares_one_chunk_with_label_range(self):
        chunks = structure_aware_chunking(self.DOC, doc_title="QĐ 99", token_counter=COUNTER)
        assert len(chunks) == 2  # Phần mở đầu + trọn Điều 5
        assert "[Khoản 1-2] - [Điểm a-b]" in chunks[1]

    def test_ocr_heading_is_canonicalized_in_metadata(self):
        chunks = structure_aware_chunking("Dieu 7.\nNoi dung dieu bay.", doc_title="T",
                                          token_counter=COUNTER)
        assert chunks[0].startswith("[T] - [Điều 7.]")

    def test_inline_citation_is_not_treated_as_heading(self):
        text = "Thông báo căn cứ theo Điều 5.\nSinh viên nộp hồ sơ tại văn phòng khoa."
        chunks = structure_aware_chunking(text, doc_title="TB", token_counter=COUNTER)
        assert len(chunks) == 1
        assert chunks[0].startswith("[TB] - [Phần mở đầu]")

    def test_oversized_clause_is_split_within_token_budget(self):
        body = " ".join(f"từ{i}" for i in range(400))
        chunks = structure_aware_chunking(f"Điều 3.\n1. {body}", doc_title="QĐ",
                                          max_tokens=64, token_counter=COUNTER)
        assert len(chunks) > 1
        assert any("(phần 1/" in chunk for chunk in chunks)
        assert all(COUNTER.count(chunk) <= 64 for chunk in chunks)
        assert all(chunk.startswith("[QĐ] - [Điều 3.] - [Khoản 1]") for chunk in chunks)

    def test_clause_numbers_are_not_confused_with_amounts(self):
        text = "Điều 4.\n1.500.000 đồng là mức học phí.\n2. Mức trên áp dụng từ 2021."
        chunks = structure_aware_chunking(text, doc_title="QĐ", max_tokens=512,
                                          token_counter=COUNTER)
        labels = [chunk.partition("\n")[0] for chunk in chunks]
        assert "[QĐ] - [Điều 4.] - [Khoản 2]" in labels
        # "1.500.000" không phải Khoản 1 -> không sinh nhãn Khoản, và cũng không bị
        # gán nhầm vào chunk của Khoản 2.
        assert not any("[Khoản 1" in label for label in labels)
        assert labels[0] == "[QĐ] - [Điều 4.]"

    def test_table_inside_article_keeps_article_and_clause_label(self):
        table = "| A | B |\n|---|---|\n| 1 | 2 |"
        text = f"Điều 2.\n1. Trước bảng.\n{table}\n2. Sau bảng."
        chunks = structure_aware_chunking(text, doc_title="QĐ", token_counter=COUNTER)
        table_chunk = next(chunk for chunk in chunks if "| A | B |" in chunk)
        assert table_chunk.startswith("[QĐ] - [Điều 2.] - [Bảng biểu]")
        assert any(chunk.startswith("[QĐ] - [Điều 2.] - [Khoản 2]") for chunk in chunks)


class TestChunkStrategyDispatcher:
    def test_rejects_unknown_strategy(self):
        with pytest.raises(ValueError):
            chunk_with_strategy("semantic", "văn bản", token_counter=COUNTER)

    def test_all_three_strategies_return_non_empty_chunks(self):
        text = "Điều 1.\n1. Nội dung khoản một.\n2. Nội dung khoản hai."
        for strategy in ("fixed", "recursive", "structure"):
            chunks = chunk_with_strategy(strategy, text, doc_title="QĐ", max_tokens=32,
                                         token_counter=COUNTER)
            assert chunks, f"{strategy} không sinh chunk nào"


class _DriftingCounter(HuggingFaceTokenCounter):
    """Tokenizer giả lập mà decode() luôn sinh thêm một từ so với số id đã cắt.

    Đúng hành vi thật của bge-m3 ở biên khoảng trắng: cắt 512 id rồi decode ra chuỗi,
    mã hoá lại chuỗi đó có thể thành 513 token. Không cần tải model nên test vẫn offline.
    """

    def __init__(self):
        super().__init__("drift")

    def encode(self, text: str) -> list[int]:
        return list(range(len(text.split())))

    def decode(self, token_ids) -> str:
        return " ".join([f"từ{i}" for i in token_ids] + ["đuôi"])

    def count(self, text: str) -> int:
        return len(text.split())


class TestTokenBudgetFidelity:
    def test_window_never_exceeds_the_token_budget(self):
        counter = _DriftingCounter()
        text = " ".join(f"từ{i}" for i in range(100))
        chunks = fixed_size_chunking(text, max_tokens=10, token_counter=counter)
        assert len(chunks) > 1
        assert all(counter.count(chunk) <= 10 for chunk in chunks)

    def test_trimmed_tokens_are_picked_up_by_the_next_window(self):
        counter = _DriftingCounter()
        text = " ".join(f"từ{i}" for i in range(100))
        chunks = fixed_size_chunking(text, max_tokens=10, token_counter=counter)
        # _shrink gọt bớt token để đúng mốc; phần bị gọt phải nằm ở cửa sổ kế tiếp,
        # nếu không văn bản bị mất chữ và 3 chiến lược không còn so sánh được với nhau.
        assert sum(counter.count(chunk) for chunk in chunks) >= 100
        assert {word for chunk in chunks for word in chunk.split()} >= {f"từ{i}" for i in range(100)}
