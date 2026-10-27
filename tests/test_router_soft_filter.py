"""Unit test cho bộ lọc mềm theo nguồn (P5.2) — hàm thuần, offline, không gọi model.

Bối cảnh: vòng lặp data/loop đo được 217/308 FAIL_RETRIEVAL có chunk vàng bị
`source_filter` cắt khỏi cửa sổ. Chế độ ROUTER_SOFT_FILTER đổi "cắt" thành
"cộng ưu tiên hạng"; mặc định TẮT nên hành vi cũ phải còn nguyên.
"""

import pytest
from langchain_core.documents import Document

from src.router import (
    DEFAULT_FILTER_RANK_BONUS,
    RetrievalConfig,
    apply_source_quota,
    get_retrieval_config,
    rescore_with_source_preference,
    router_filter_rank_bonus,
    router_source_quota,
    router_soft_filter_enabled,
)


def doc(source: str, chunk_id: int) -> Document:
    return Document(page_content=f"nội dung {chunk_id}", metadata={"source": source, "chunk_id": chunk_id})


class TestEnabledFlag:
    def test_mặc_định_tắt(self, monkeypatch):
        monkeypatch.delenv("ROUTER_SOFT_FILTER", raising=False)
        assert router_soft_filter_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_giá_trị_bật(self, monkeypatch, value):
        monkeypatch.setenv("ROUTER_SOFT_FILTER", value)
        assert router_soft_filter_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_giá_trị_tắt_hiển_ngữ(self, monkeypatch, value):
        monkeypatch.setenv("ROUTER_SOFT_FILTER", value)
        assert router_soft_filter_enabled() is False


class TestRankBonusEnv:
    def test_mặc_định_là_ba(self, monkeypatch):
        monkeypatch.delenv("ROUTER_FILTER_RANK_BONUS", raising=False)
        assert router_filter_rank_bonus() == DEFAULT_FILTER_RANK_BONUS == 3

    @pytest.mark.parametrize("value,expected", [("1", 1), ("6", 6), ("2.9", 2), ("-4", 0), ("0", 0)])
    def test_đọc_và_chặnÂM_số(self, monkeypatch, value, expected):
        monkeypatch.setenv("ROUTER_FILTER_RANK_BONUS", value)
        assert router_filter_rank_bonus() == expected

    @pytest.mark.parametrize("value", ["abc", "", "   "])
    def test_giá_trị_lỗi_rơi_về_mặc_định(self, monkeypatch, value):
        monkeypatch.setenv("ROUTER_FILTER_RANK_BONUS", value)
        assert router_filter_rank_bonus() == DEFAULT_FILTER_RANK_BONUS


class TestRescore:
    DOCS = [doc("khac-1.pdf", 1), doc("1059-qd-dhag-2020-09-29.pdf", 2), doc("khac-2.pdf", 3)]

    def test_không_được_loại_bất_kỳ_doc_nào(self):
        out = rescore_with_source_preference(self.DOCS, ["1059-qd-dhag-2020-09-29.pdf"], rank_bonus=3)
        assert len(out) == len(self.DOCS)
        assert {d.metadata["chunk_id"] for d in out} == {1, 2, 3}

    def test_doc_thuộc_nguồn_được_dời_lên_theo_hạng(self):
        out = rescore_with_source_preference(self.DOCS, ["1059-qd-dhag-2020-09-29.pdf"], rank_bonus=3)
        assert out[0].metadata["chunk_id"] == 2

    def test_bonus_nhỏ_không_đủ_thì_giữ_nguyên_thứ_tự_rrf(self):
        # pos=2 - bonus=1 vẫn đứng sau doc pos=0,1 -> không có chuyện "mềm" thành "cứng".
        out = rescore_with_source_preference(self.DOCS, ["1059-qd-dhag-2020-09-29.pdf"], rank_bonus=1)
        assert [d.metadata["chunk_id"] for d in out] == [1, 2, 3]

    def test_so_khớp_không_dấu(self):
        docs = [doc("Qui dinh muc hoc phi.pdf", 1)]
        out = rescore_with_source_preference(docs, ["qui dinh muc hoc phi.pdf"], rank_bonus=3)
        assert out[0].metadata["chunk_id"] == 1

    def test_bonus_không_đổi_thứ_tự_giữa_hai_doc_cùng_loại(self):
        docs = [doc("a.pdf", 1), doc("b.pdf", 2), doc("a.pdf", 3)]
        out = rescore_with_source_preference(docs, ["a.pdf"], rank_bonus=3)
        assert [d.metadata["chunk_id"] for d in out] == [1, 3, 2]

    def test_danh_sách_nguồn_rỗng_hay_bonus_bàng_không_thay_đổi_gì(self):
        assert rescore_with_source_preference(self.DOCS, [], rank_bonus=3) == self.DOCS
        assert rescore_with_source_preference(self.DOCS, ["a.pdf"], rank_bonus=0) == self.DOCS

    def test_doc_thiếu_metadata_vẫn_an_toàn(self):
        docs = [Document(page_content="x", metadata={}), doc("a.pdf", 2)]
        out = rescore_with_source_preference(docs, ["a.pdf"], rank_bonus=3)
        assert [d.metadata.get("chunk_id") for d in out] == [2, None]

    def test_input_không_bị_sửa(self):
        before = [d.metadata["chunk_id"] for d in self.DOCS]
        rescore_with_source_preference(self.DOCS, ["1059-qd-dhag-2020-09-29.pdf"], rank_bonus=3)
        assert [d.metadata["chunk_id"] for d in self.DOCS] == before


class TestRouterConfigKhôngĐổi:
    """Lọc mềm là chuyện của pipeline — `get_retrieval_config` vẫn phải trả đúng
    source_filter như cũ, để các bài test A/B P4 còn so sánh được."""

    def test_source_filter_vẫn_được_sinh_ra(self):
        base = RetrievalConfig(top_k=4, bm25_weight=0.5, chroma_weight=0.5)
        config = get_retrieval_config(
            {"topic": "đánh giá rèn luyện", "question_type": "TRA_CUU"}, base
        )
        assert config.source_filter == ["1059-qd-dhag-2020-09-29.pdf"]


class TestHạnNgạchNguồn:
    """P5.14 — bonus >= cỡ cửa sổ khiến MỘT nguồn chiếm trọn cửa sổ (21/21 item hồi
    quy r2 có chunk vàng nằm NGOÀI source_filter). Hạn ngạch giữ ưu tiên nhưng không
    cho phép nguồn nào xóa hết suất của nguồn khác."""

    DOCS = (
        [doc("a.pdf", i) for i in range(1, 5)]
        + [doc("b.pdf", 9) for _ in range(1, 4)]
        + [doc("c.pdf", 7)]
    )

    def test_quota_không_đổi_gì_khi_bàng_không(self, monkeypatch):
        monkeypatch.delenv("ROUTER_SOURCE_QUOTA", raising=False)
        assert router_source_quota() == 0
        assert apply_source_quota(self.DOCS, 0) == self.DOCS

    def test_mỗi_nguồn_tối_đa_quota_suat_ph_bị_hoãn_giữ_thứ_tự(self):
        out = apply_source_quota(self.DOCS, 2)
        got = [(d.metadata["source"], d.metadata["chunk_id"]) for d in out]
        # a.pdf 4 ung vien -> 2 suat dau, 2 bi hoan xuong cuoi (thu tu tương đối không đổi)
        assert got == [
            ("a.pdf", 1), ("a.pdf", 2), ("b.pdf", 9), ("b.pdf", 9), ("c.pdf", 7),
            ("a.pdf", 3), ("a.pdf", 4), ("b.pdf", 9),
        ]
        assert len(out) == len(self.DOCS)

    def test_cửa_sổ_top_k_còn_nhiều_hơn_một_nguồn(self):
        """Đúng ca r2 mất gold@6: cửa sổ 12 ô bị a.pdf chiếm hết, b.pdf bị đẩy ra."""
        wide = [doc("a.pdf", i) for i in range(1, 13)] + [doc("b.pdf", 100)]
        ranked = rescore_with_source_preference(wide, ["a.pdf"], rank_bonus=12)
        assert {d.metadata["source"] for d in apply_source_quota(ranked, 0)[:6]} == {"a.pdf"}
        assert {d.metadata["source"] for d in apply_source_quota(ranked, 3)[:6]} == {"a.pdf", "b.pdf"}

    def test_env_dữ_dạng_để_nguyên_lever_tắt(self, monkeypatch):
        for bad in ("abc", "-4", " "):
            monkeypatch.setenv("ROUTER_SOURCE_QUOTA", bad)
            assert router_source_quota() == 0
        monkeypatch.setenv("ROUTER_SOURCE_QUOTA", "3.9")
        assert router_source_quota() == 3

    def test_input_không_bị_sửa(self):
        before = [d.metadata["chunk_id"] for d in self.DOCS]
        apply_source_quota(self.DOCS, 1)
        assert [d.metadata["chunk_id"] for d in self.DOCS] == before

