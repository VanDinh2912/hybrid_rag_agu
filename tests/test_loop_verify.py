# -*- coding: utf-8 -*-
"""Unit test trọng tài deterministic của vòng lặp (`tools/loop/verify.py`).

Mỗi verdict là một LỆNH vào bản đồ lever, nên chấm sai một verdict là sửa sai
cả tầng. Test chốt ba chuyện đã suýt làm hỏng vòng lặp r0:
1. Từ chối khi chunk vàng KHÔNG vào cửa sổ = lỗi truy xuất, KHÔNG phải over-refusal.
2. Item neo theo cả văn bản (HUMAN, gold_chunk_id=None) không được quy là FAIL_RETRIEVAL.
3. Câu ngoài phạm vi mà trả lời = FAIL_HALLUCINATED_ON_UNANSWERABLE (nặng nhất).
"""

from __future__ import annotations

import pytest

from src.text_utils import fold
from tools.loop.verify import (
    aggregate,
    expected_source_in_window,
    is_refusal,
    referee_fingerprint,
    score_item,
)

GOLD_TEXT = "Mức thu bảo hiểm y tế là 546.480đ/12 tháng/SV."


def item(**over) -> dict:
    base = {
        "id": "T1",
        "family": "EXACT",
        "split": "test",
        "raw_query": "Bảo hiểm y tế bao nhiêu?",
        "source_document": "tb-bhyt.pdf",
        "gold_chunk_id": 7,
        "required_entities": ["546.480"],
        "primary_entity": "546.480",
    }
    base.update(over)
    return base


def result(answer: str | None, *, with_gold: bool = True, **over) -> dict:
    base = {
        "answer": answer,
        "contexts": [GOLD_TEXT] if with_gold else ["một chunk khác không liên quan"],
        "sources": [
            {"rank": 1, "chunk_id": 7 if with_gold else 99, "source": "tb-bhyt.pdf", "tier": "2", "chars": 40}
        ],
        "labels": {"question_type": "TRA_CUU", "topic": "bhyt"},
        "latency_seconds": 1.0,
    }
    base.update(over)
    return base


REFUSAL = "Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."


class TestRefusalDetection:
    def test_nhận_diện_theo_marker(self):
        for text in (
            REFUSAL,
            "Thông tin này không tìm thấy trong văn bản.",
            "Dạ, tài liệu không có căn cứ để trả lời.",
        ):
            assert is_refusal(text), text

    def test_chấp_nhận_cả_ghi_mất_dấu_và_viết_hoa(self):
        assert is_refusal(fold(REFUSAL))
        assert is_refusal(REFUSAL.upper())

    def test_câu_trả_lời_bình_thường_không_phải_refusal(self):
        assert not is_refusal("Bảo hiểm y tế là 546.480đ.")

    def test_rỗng_không_phải_là_từ_chối(self):
        assert not is_refusal("")


class TestRetrievalPhase:
    def test_gold_vào_cửa_sổ_thì_pending(self):
        row = score_item(item(), result(None), top_k=6)
        assert row["verdict"] == "PENDING_GENERATION"
        assert row["gold_in_top_k"] is True

    def test_gold_trượt_cửa_sổ_thì_fail_retrieval(self):
        row = score_item(item(), result(None, with_gold=False), top_k=6)
        assert row["verdict"] == "FAIL_RETRIEVAL"
        assert row["severity"] == 2

    def test_item_không_có_chunk_vàng_không_bị_kết_luận_truy_xuất(self):
        """HUMAN/SOURCE_LOOKUP neo cả văn bản: gold_chunk_id=None -> chưa sinh thì chưa phán."""
        row = score_item(item(gold_chunk_id=None), result(None, with_gold=False), top_k=6)
        assert row["verdict"] == "PENDING_GENERATION"

    def test_câu_ngoài_phạm_vi_bắt_buộc_chờ_sinh(self):
        row = score_item(item(family="REFUSE_OOD", gold_chunk_id=None), result(None), top_k=6)
        assert row["verdict"] == "PENDING_GENERATION"


class TestFullPhase:
    def test_trả_lời_đúng_thực_thể_và_có_căn_cứ_thì_pass(self):
        row = score_item(item(), result("Bảo hiểm y tế là 546.480đ/12 tháng/SV (TB)."), top_k=6)
        assert row["verdict"] == "PASS_CORRECT"
        assert row["grounding_score"] == 1.0

    def test_bịa_số_bị_gọi_là_fabricated(self):
        row = score_item(item(), result("Bảo hiểm y tế là 700.000đ/12 tháng."), top_k=6)
        assert row["verdict"] == "FAIL_FABRICATED"
        assert row["severity"] == 3
        assert {u["text"] for u in row["unsupported"]} == {"700.000"}

    def test_đúng_số_nhưng_thiếu_gold_thì_incomplete(self):
        row = score_item(item(), result("Mức thu được quy định trong thông báo bảo hiểm."), top_k=6)
        assert row["verdict"] == "FAIL_INCOMPLETE"

    def test_refusal_khi_đã_có_căn_cứ_mới_là_overrefusal(self):
        row = score_item(item(), result(REFUSAL), top_k=6)
        assert row["verdict"] == "FAIL_OVERREFUSAL"
        assert row["detail"] == {}

    def test_refusal_khi_truy_xuất_trượt_được_quy_về_retrieval(self):
        """Đây là chỗ bản đồ lever từng đổ oan cho guardrail ở pilot 20/10."""
        row = score_item(item(), result(REFUSAL, with_gold=False), top_k=6)
        assert row["verdict"] == "FAIL_RETRIEVAL"
        assert row["detail"]["refused_but_root_cause_is_retrieval"] is True

    def test_item_không_chunk_vàng_mà_tự_chối_vẫn_là_overrefusal(self):
        row = score_item(item(gold_chunk_id=None), result(REFUSAL, with_gold=False), top_k=6)
        assert row["verdict"] == "FAIL_OVERREFUSAL"

    def test_hallucinated_on_unanswerable_nặng_nhất(self):
        row = score_item(
            item(family="REFUSE_MISSING_DOC", expected_answer_type="refuse", gold_chunk_id=None),
            result("Văn bản 1999-QĐ có nêu rõ mức 700.000đ."),
            top_k=6,
        )
        assert row["verdict"] == "FAIL_HALLUCINATED_ON_UNANSWERABLE"
        assert row["severity"] == 3

    def test_refuse_item_từ_chối_đúng_thì_pass(self):
        row = score_item(
            item(family="REFUSE_OOD", expected_answer_type="refuse", gold_chunk_id=None),
            result(REFUSAL),
            top_k=6,
        )
        assert row["verdict"] == "PASS_REFUSAL"


class TestTrap:
    def test_xác_nhận_tiền_đề_sai_là_confirm_false_premise(self):
        it = item(family="TRAP", wrong_value="1.092.960", correct_value="546.480")
        row = score_item(it, result("Đúng rồi bạn, mức 1.092.960 là chính xác."), top_k=6)
        assert row["verdict"] == "FAIL_CONFIRMED_FALSE_PREMISE"
        assert row["detail"]["wrong_value"] == "1.092.960"

    def test_bác_tiền_đề_sai_và_nêu_gold_thì_pass_corrected(self):
        it = item(family="TRAP", wrong_value="1.092.960", correct_value="546.480")
        row = score_item(it, result("Không đúng. Mức thật là 546.480đ/12 tháng."), top_k=6)
        assert row["verdict"] == "PASS_CORRECTED_TRAP"

    def test_trap_từ_chối_cũng_là_pass(self):
        it = item(family="TRAP", wrong_value="1.092.960", correct_value="546.480")
        row = score_item(it, result(REFUSAL), top_k=6)
        assert row["verdict"] == "PASS_REFUSAL"


class TestAggregate:
    def test_pending_không_tính_vào_mẫu_số(self):
        rows = [
            score_item(item(id="a"), result(None)),
            score_item(item(id="b"), result("Bảo hiểm y tế là 546.480đ.")),
        ]
        agg = aggregate(rows, "family")
        assert agg["EXACT"]["n"] == 2
        assert agg["EXACT"]["n_pending_generation"] == 1
        assert agg["EXACT"]["pass_rate"] == 1.0  # chỉ 1 câu đã xét, và nó ĐÚNG

    def test_đếm_đủ_loại_lỗi_theo_lever(self):
        rows = [
            score_item(item(id="a"), result("Mức 700.000đ.")),
            score_item(item(id="b"), result(REFUSAL)),
            score_item(item(id="c"), result(REFUSAL, with_gold=False)),
        ]
        agg = aggregate(rows, "id")
        assert agg["a"]["fabricated"] == 1
        assert agg["b"]["overrefusal"] == 1
        assert agg["c"]["retrieval"] == 1


class TestChữKýTrọngTài:
    """Round phải tự ký phiên bản dụng cụ đã chấm nó (ca r0: verdict ghi bởi
    verify.py còn bug `has_gold_chunk` nên cả bảng số sai mà không ai biết)."""

    def test_đọc_được_và_ổn_định_trong_một_lần_chạy(self):
        first = referee_fingerprint()
        assert len(first) == 12
        assert all(c in "0123456789abcdef" for c in first)
        assert referee_fingerprint() == first

    def test_nội_dung_trọng_tài_đổi_thì_chữ_ký_đổi(self, tmp_path, monkeypatch):
        a = tmp_path / "verify.py"
        b = tmp_path / "answer_guard.py"
        a.write_text("x = 1", encoding="utf-8")
        b.write_text("y = 2", encoding="utf-8")
        monkeypatch.setattr("tools.loop.verify.REFEREE_FILES", (a, b))
        base = referee_fingerprint()
        b.write_text("y = 3  # sửa luật chấm", encoding="utf-8")
        assert referee_fingerprint() != base

    def test_thiếu_file_thì_vẫn_sinh_chữ_ký_từ_phần_đọc_được(self, tmp_path, monkeypatch):
        a = tmp_path / "verify.py"
        a.write_text("x = 1", encoding="utf-8")
        monkeypatch.setattr("tools.loop.verify.REFEREE_FILES", (tmp_path / "khong_ton_tai.py", a))
        assert referee_fingerprint() == referee_fingerprint()
        assert len(referee_fingerprint()) == 12

    def test_không_doc_được_nao_hay_thì_trống(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.loop.verify.REFEREE_FILES", (tmp_path / "a.py",))
        assert referee_fingerprint() == ""


class TestĐoĐượcNguồnỞPhaRẻ:
    """`expected_source_in_window` là thang duy nhất đo được neo HUMAN ở pha rẻ."""

    def test_nguồn_trúng_nằm_trong_cửa_sổ(self):
        assert expected_source_in_window(item(), result(None), top_k=6) is True

    def test_chỉ_tính_trong_top_k(self):
        docs = [{"source": "khac.pdf"}] * 6 + [{"source": "tb-bhyt.pdf"}]
        assert expected_source_in_window(item(), {"sources": docs}, top_k=6) is False

    def test_so_khớp_mất_dấu_và_thường_hoa(self):
        row = item(source_document="TB-BHYt.PDF")
        assert expected_source_in_window(row, {"sources": [{"source": "tb-bhyt.pdf"}]}, top_k=6) is True

    def test_item_không_đính_kèm_văn_bản_thì_không_đo(self):
        assert expected_source_in_window(item(source_document=None), result(None), top_k=6) is None

    def test_verdict_pha_truy_xuất_mang_cờ_này(self):
        row = score_item(item(), result(None), top_k=6)
        assert row["expected_source_in_window"] is True
