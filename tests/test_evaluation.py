"""Unit test cho các hàm thuần của src/evaluation.py — không gọi API, không cần ChromaDB."""

from src.evaluation import (
    citation_scores,
    extract_citations,
    fold,
    normalization_preservation,
    number_support,
    source_match,
)


class TestFold:
    def test_removes_tone_and_normalizes_d_stroke(self):
        # U+0110/U+0111 không tách được qua NFD — fold phải tự thay "đ"→"d"
        assert fold("Điều 12 Khoản 2") == "dieu 12 khoan 2"

    def test_collapse_whitespace_and_lowercase(self):
        assert fold("  Điểm   Trung Bình  ") == "diem trung binh"

    def test_ocr_unaccented_input_unchanged(self):
        assert fold("dieu 4 khoan 1") == "dieu 4 khoan 1"


class TestExtractCitations:
    def test_article_with_clause(self):
        assert extract_citations("Theo Điều 12 Khoản 2 thì sinh viên...") == {"dieu 12 khoan 2"}

    def test_article_alone(self):
        assert extract_citations("Quy định tại Điều 5.") == {"dieu 5"}

    def test_ocr_text_matches_benchmark_format(self):
        # benchmark lưu "Điều 12 Khoản 2"; văn bản/câu trả lỗi OCR mất dấu vẫn phải
        # rút ra cùng tập token — nếu không Citation F1 sẽ luôn bằng 0.
        assert extract_citations("Điều 12 Khoản 2") == extract_citations("dieu 12 khoan 2")

    def test_multiple_citations(self):
        result = extract_citations("Xem Điều 12 Khoản 2 và Điều 12 Khoản 3")
        assert result == {"dieu 12 khoan 2", "dieu 12 khoan 3"}

    def test_no_citation(self):
        assert extract_citations("Không có trích dẫn nào ở đây") == set()


class TestCitationScores:
    def test_perfect_match(self):
        scores = citation_scores({"dieu 12 khoan 2"}, {"dieu 12 khoan 2"})
        assert scores == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "exact_match": 1.0}

    def test_empty_prediction_zero_guard(self):
        scores = citation_scores({"dieu 5"}, set())
        assert scores["precision"] == 0.0
        assert scores["recall"] == 0.0
        assert scores["f1"] == 0.0

    def test_partial_f1(self):
        scores = citation_scores({"dieu 1", "dieu 2"}, {"dieu 1", "dieu 9"})
        assert scores["precision"] == 0.5
        assert scores["recall"] == 0.5
        assert scores["f1"] == 0.5
        assert scores["exact_match"] == 0.0


class TestNormalizationPreservation:
    def test_all_entities_preserved(self):
        result = normalization_preservation(
            "Ê ad, tui bị ĐTBHK dưới 1.0 thì có bị đuổi học luôn không?",
            "Sinh viên có điểm trung bình học kỳ dưới 1.0 có bị buộc thôi học không?",
        )
        assert result["score"] == 1.0
        assert result["lost"] == []

    def test_decimal_comma_tolerated(self):
        # tiếng Việt viết "1,0" — phải quy về "1.0" trước khi so, không tính oan
        result = normalization_preservation("dưới 1,0 điểm thì sao", "điểm dưới 1.0 thì sao")
        assert result["score"] == 1.0

    def test_lost_article_and_clause(self):
        result = normalization_preservation("Điều 12 Khoản 2 nói gì?", "Quy định chung về học vụ?")
        assert result["score"] == 0.0
        assert result["lost"] == ["dieu 12", "khoan 2"]

    def test_no_entity_returns_none(self):
        result = normalization_preservation("Học phí thế nào?", "Học phí được quy định thế nào?")
        assert result["score"] is None


class TestNumberSupport:
    def test_all_numbers_supported(self):
        assert number_support("ĐTBHK phải đạt 2.0", ["sinh viên đạt 2.0 trở lên"]) == 1.0

    def test_no_numbers_returns_none(self):
        assert number_support("Không có con số nào", ["ngữ cảnh"]) is None


class TestSourceMatch:
    def test_exact_filename(self):
        assert source_match("quy_che_dao_tao_mau.txt", "quy_che_dao_tao_mau.txt")

    def test_subset_filename(self):
        assert source_match("Tầng 1/QCĐT-2021.pdf", "QCĐT-2021.pdf")

    def test_mismatch(self):
        assert not source_match("ban-mo-ta-ctdt-nganh-cntt-2021.pdf", "quy_che_dao_tao_mau.txt")

    def test_empty_expected_rejected(self):
        assert not source_match("anything.txt", "")
