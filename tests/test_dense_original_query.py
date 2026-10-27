"""P3 / V1 / PA-48a — `ENABLE_DENSE_ORIGINAL_QUERY`: chỉ nhánh dense nhận query nguyên văn.

Bất biến phải giữ (mỗi bất biến có ít nhất một test và một đột biến trong
`tmp/mutation_check_p3_dense_orig_2026-10-27.py`):

* **TẮT (mặc định)** — pipeline gọi ĐÚNG MỘT `ensemble.invoke(fold(query))`: đường cũ
  từng byte, khóa cache sinh không đổi (cờ không nằm trong `src/cache_policy.py`).
* **BẬT** — BM25 nhận `fold(query)`, dense nhận `query` nguyên văn; phép hợp nhất vẫn do
  chính ensemble thực hiện (`weighted_reciprocal_rank`) với đúng thứ tự hai nhánh
  `[BM25, dense]`, đúng `weights`/`c`/`id_key`.
* Đường lùi `similarity_search` và lượt đo hạng T3 (`_collect_leg_ranks`) cũng theo cờ.

Không gọi Ollama/ChromaDB/Gemini: mọi tầng dưới là đồ giả trong-process.
"""

from __future__ import annotations

import os

import pytest

from src.pipeline import HybridRAGPipeline, dense_original_query_enabled
from src.text_utils import fold

# Câu có dấu — `fold` phải khác nguyên văn, nếu không test sẽ "xanh vì hai chuỗi trùng nhau".
CAU_HOI = "Sinh viên học lại tối đa bao nhiêu lần mỗi học phần?"
CAU_DU_PHONG = "Cố vấn học tập họp với lớp mấy lần mỗi học kỳ?"

# Mọi cờ có thể đổi đường chạy của `retrieve` — xoá sạch để test không phụ thuộc máy dev.
CO_DUONG_TRUY_XUAT = (
    "ENABLE_DENSE_ORIGINAL_QUERY",
    "ENABLE_DECOUPLED_REFUSAL",
    "ENABLE_RERANKER",
    "ENABLE_CLASSIFIER",
    "ROUTER_SOFT_FILTER",
    "ROUTER_SOURCE_QUOTA",
    "ENABLE_QUERY_EXPANSION",
    "ENABLE_HYBRID_SEARCH",
    "ENABLE_CONTEXTUAL_HEADER",
    "ENABLE_EVIDENCE_SELECTION",
)


@pytest.fixture(autouse=True)
def moi_co_tat(monkeypatch):
    """Mỗi test bắt đầu từ env trống — đúng giá trị một bản clone mới nhìn thấy."""
    for name in CO_DUONG_TRUY_XUAT:
        monkeypatch.delenv(name, raising=False)


# ================================================================ đồ giả
class FakeDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


DOC_BM25 = FakeDoc("chunk chi co o nhanh BM25", {"source": "a.pdf", "tier": 1, "chunk_id": 1})
DOC_DENSE = FakeDoc("chunk chi co o nhanh dense", {"source": "b.pdf", "tier": 1, "chunk_id": 2})


class RecordingLeg:
    """Nhánh truy xuất ghi lại ĐÚNG chuỗi query nó nhận."""

    def __init__(self, docs):
        self.docs = list(docs)
        self.queries: list[str] = []

    def invoke(self, query):
        self.queries.append(query)
        return list(self.docs)


class RRFEnsemble:
    """Đúng hình dạng `_invoke_hybrid` cần: 2 nhánh + `weighted_reciprocal_rank`.

    `invoke` mô phỏng `EnsembleRetriever.rank_fusion`: gọi từng nhánh theo thứ tự
    `[BM25, dense]` với CÙNG một query rồi hợp nhất. `weighted_reciprocal_rank` ghi lại
    thứ tự nhánh nhận được để test bắt được đột biến đảo nhánh.
    """

    def __init__(self, bm25_docs=(DOC_BM25,), dense_docs=(DOC_DENSE,)):
        self.retrievers = [RecordingLeg(bm25_docs), RecordingLeg(dense_docs)]
        self.weights = [0.5, 0.5]
        self.c = 60
        self.id_key = "chunk_id"
        self.invoke_queries: list[str] = []
        self.fuse_inputs: list[list[list]] = []

    def invoke(self, query):
        self.invoke_queries.append(query)
        lists = [leg.invoke(query) for leg in self.retrievers]
        return self.weighted_reciprocal_rank(lists)

    def weighted_reciprocal_rank(self, doc_lists):
        self.fuse_inputs.append(
            [[doc.metadata.get("chunk_id") for doc in docs] for docs in doc_lists]
        )
        out, seen = [], set()
        for docs in doc_lists:
            for doc in docs:
                cid = doc.metadata.get("chunk_id")
                if cid not in seen:
                    seen.add(cid)
                    out.append(doc)
        return out


class LegacyEnsemble:
    """Ensemble không đủ hình dạng (không có `retrievers`/`weighted_reciprocal_rank`)."""

    def __init__(self):
        self.queries: list[str] = []

    def invoke(self, query):
        self.queries.append(query)
        return [DOC_BM25]


class FakeVectorDB:
    def __init__(self):
        self.received: list[tuple[str, int]] = []

    def similarity_search(self, query, k):
        self.received.append((query, k))
        return [DOC_BM25]


def make_pipeline(retriever=None, vector_db=None, use_hybrid: bool = True):
    return HybridRAGPipeline(
        vector_db=vector_db,
        local_slm=None,
        generator=None,
        retriever=retriever,
        use_hybrid=use_hybrid,
    )


# ================================================================ đọc cờ
class TestDocCo:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " 1 "])
    def test_gia_tri_bat(self, monkeypatch, value):
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", value)
        assert dense_original_query_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "bat-bay"])
    def test_gia_tri_tat(self, monkeypatch, value):
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", value)
        assert dense_original_query_enabled() is False

    def test_env_trong_la_tat(self):
        assert "ENABLE_DENSE_ORIGINAL_QUERY" not in os.environ
        assert dense_original_query_enabled() is False


# ================================================================ TẮT = đường cũ
class TestMacDinhTat:
    def test_dung_mot_lan_invoke_voi_query_da_fold(self):
        ensemble = RRFEnsemble()
        pipeline = make_pipeline(retriever=ensemble)

        pipeline.retrieve(CAU_HOI, k=4)

        assert fold(CAU_HOI) != CAU_HOI  # phép so sánh bên dưới mới có nghĩa
        assert ensemble.invoke_queries == [fold(CAU_HOI)]
        # `invoke` của ensemble đẩy CÙNG query đã fold xuống cả hai nhánh — như trước P3.
        assert ensemble.retrievers[0].queries == [fold(CAU_HOI)]
        assert ensemble.retrievers[1].queries == [fold(CAU_HOI)]

    def test_mot_lan_invoke_moi_cau_fallback(self):
        ensemble = RRFEnsemble()
        pipeline = make_pipeline(retriever=ensemble)

        pipeline.retrieve(CAU_HOI, k=4, fallback_query=CAU_DU_PHONG)

        assert ensemble.invoke_queries == [fold(CAU_HOI), fold(CAU_DU_PHONG)]

    def test_ensemble_khong_du_hinh_dang_thi_khong_goi_nhanh_nao(self):
        legacy = LegacyEnsemble()
        pipeline = make_pipeline(retriever=legacy)

        pipeline.retrieve(CAU_HOI, k=4)

        assert legacy.queries == [fold(CAU_HOI)]


# ================================================================ BẬT = dense nguyên văn
class TestBatDenseNguyenVan:
    def test_bm25_nhan_fold_dense_nhan_nguyen_van(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", "1")
        ensemble = RRFEnsemble()
        pipeline = make_pipeline(retriever=ensemble)

        pipeline.retrieve(CAU_HOI, k=4)

        assert ensemble.retrievers[0].queries == [fold(CAU_HOI)]
        assert ensemble.retrievers[1].queries == [CAU_HOI]
        # Đường BẬT gọi từng nhánh, KHÔNG gọi `invoke(chung)` của ensemble.
        assert ensemble.invoke_queries == []

    def test_hop_nhat_dung_thu_tu_hai_nhanh(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", "1")
        ensemble = RRFEnsemble()
        pipeline = make_pipeline(retriever=ensemble)

        pipeline.retrieve(CAU_HOI, k=4)

        # [danh sách chunk của BM25, danh sách chunk của dense] — đúng thứ tự weights.
        assert ensemble.fuse_inputs == [[[1], [2]]]

    def test_ket_qua_lay_tu_fusion_cua_ensemble(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", "1")
        ensemble = RRFEnsemble()
        pipeline = make_pipeline(retriever=ensemble)

        docs = pipeline.retrieve(CAU_HOI, k=4)

        assert [d.metadata["chunk_id"] for d in docs] == [1, 2]

    def test_fallback_query_cung_di_theo_co(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", "1")
        ensemble = RRFEnsemble()
        pipeline = make_pipeline(retriever=ensemble)

        pipeline.retrieve(CAU_HOI, k=4, fallback_query=CAU_DU_PHONG)

        assert ensemble.retrievers[0].queries == [fold(CAU_HOI), fold(CAU_DU_PHONG)]
        assert ensemble.retrievers[1].queries == [CAU_HOI, CAU_DU_PHONG]

    def test_ensemble_khong_du_hinh_dang_thi_lui_ve_duong_cu(self, monkeypatch):
        """Không đoán thứ tự nhánh khi retriever tùy biến không phải EnsembleRetriever."""
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", "1")
        legacy = LegacyEnsemble()
        pipeline = make_pipeline(retriever=legacy)

        pipeline.retrieve(CAU_HOI, k=4)

        assert legacy.queries == [fold(CAU_HOI)]


# ================================================================ T3: đo hạng từng nhánh
class TestDoHangT3:
    def test_tat_thi_ca_hai_nhanh_do_bang_fold(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        ensemble = RRFEnsemble()
        pipeline = make_pipeline(retriever=ensemble)

        pipeline.retrieve(CAU_HOI, k=4)

        # Một lượt truy xuất + một lượt đo hạng, cả hai đều dùng `fold`.
        assert ensemble.retrievers[0].queries == [fold(CAU_HOI), fold(CAU_HOI)]
        assert ensemble.retrievers[1].queries == [fold(CAU_HOI), fold(CAU_HOI)]
        assert pipeline.last_leg_ranks == {"1": (1, None), "2": (None, 1)}

    def test_bat_thi_nhanh_dense_do_bang_nguyen_van(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", "1")
        monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "1")
        ensemble = RRFEnsemble()
        pipeline = make_pipeline(retriever=ensemble)

        pipeline.retrieve(CAU_HOI, k=4)

        # Lượt đo phải dùng ĐÚNG query mà nhánh nhận lúc truy xuất — nếu đo bằng fold
        # thì `rank_vector` không còn là hạng của lượt dense thật.
        assert ensemble.retrievers[0].queries == [fold(CAU_HOI), fold(CAU_HOI)]
        assert ensemble.retrievers[1].queries == [CAU_HOI, CAU_HOI]
        assert pipeline.last_leg_ranks == {"1": (1, None), "2": (None, 1)}


# ================================================================ đường lùi similarity_search
class TestDuongLuiSimilaritySearch:
    def test_tat_nhan_fold(self):
        vector_db = FakeVectorDB()
        pipeline = make_pipeline(vector_db=vector_db, use_hybrid=False)

        pipeline.retrieve(CAU_HOI, k=3)

        assert vector_db.received == [(fold(CAU_HOI), 3)]

    def test_bat_nhan_nguyen_van(self, monkeypatch):
        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", "1")
        vector_db = FakeVectorDB()
        pipeline = make_pipeline(vector_db=vector_db, use_hybrid=False)

        pipeline.retrieve(CAU_HOI, k=3)

        assert vector_db.received == [(CAU_HOI, 3)]


# ================================================================ khóa cache sinh
class TestKhoaCacheKhongDoiKhiTat:
    def test_token_policy_giong_het_giua_khong_dat_va_dat_0(self, monkeypatch):
        """Cờ là lever TRUY XUẤT, không nằm trong `cache_policy`; khi TẮT khóa cache cũ
        phải dùng lại được từng byte. (Khi BẬT, prompt đổi vì contexts đổi nên khóa đổi
        theo cơ chế sẵn có — không cần thêm trường policy.)"""
        from src.cache_policy import cache_policy_deviation, policy_cache_token

        monkeypatch.delenv("ENABLE_DENSE_ORIGINAL_QUERY", raising=False)
        truoc = policy_cache_token()
        truoc_lech = cache_policy_deviation()

        monkeypatch.setenv("ENABLE_DENSE_ORIGINAL_QUERY", "0")
        assert policy_cache_token() == truoc
        assert cache_policy_deviation() == truoc_lech
