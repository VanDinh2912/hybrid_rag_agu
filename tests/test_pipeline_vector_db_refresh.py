"""REVIEW §2.1 — làm mới bộ truy xuất sau ingest.

Bất biến được ghim ở đây:
1. `replace_vector_db()` là API duy nhất để thay corpus: pipeline tìm được document
   mới NGAY sau khi thay, và không còn trả document chỉ có trong corpus cũ
   (BM25 cũ giữ danh sách document cũ nếu chỉ gán `pipeline.vector_db`).
2. Thay thất bại KHÔNG để lại trạng thái nửa vời: DB + retriever cũ còn nguyên.
3. Chế độ không hybrid và retriever tùy chỉnh không bị đoán mò hành vi.
"""

from typing import Any

import pytest
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from src.core.pipeline import HybridRAGPipeline, RetrieverRebuildError


class _FakeCollection:
    def __init__(self, texts: list[str]):
        self._texts = texts

    def count(self) -> int:
        return len(self._texts)


class FakeDenseLeg(BaseRetriever):
    """Nhánh dense giả: trả TOÀN BỘ document của đúng DB mà nó được sinh ra từ đó.

    Trả cả corpus (không lọc theo query) để test bắt được retriever cũ: nếu pipeline
    vẫn dùng nhánh dense dựng từ DB cũ thì document cũ sẽ xuất hiện trong kết quả.
    """

    db: Any = None
    k: int = 0
    search_kwargs: dict = {}

    def _get_relevant_documents(self, query: str, *, run_manager=None):
        return [
            Document(
                page_content=text,
                metadata={"chunk_id": i, "tier": 1, "source": f"src{i}.txt"},
            )
            for i, text in enumerate(self.db.texts)
        ]


class FakeChroma:
    """Tối thiểu bề mặt Chroma mà pipeline cần: `.get()`, `.as_retriever()`, `._collection`."""

    def __init__(self, texts: list[str]):
        self.texts = list(texts)
        self._collection = _FakeCollection(self.texts)

    def get(self) -> dict:
        return {
            "documents": list(self.texts),
            "metadatas": [
                {"chunk_id": i, "tier": 1, "source": f"src{i}.txt"}
                for i in range(len(self.texts))
            ],
        }

    def as_retriever(self, search_kwargs: dict | None = None):
        return FakeDenseLeg(db=self, search_kwargs=dict(search_kwargs or {}))


@pytest.fixture(autouse=True)
def _the_mac_dinh_da_dang_ky(monkeypatch):
    """Ghim cờ về thể chế mặc định để test không phụ thuộc `.env` của máy dev."""
    monkeypatch.setenv("ENABLE_HYBRID_SEARCH", "1")
    monkeypatch.setenv("ENABLE_RERANKER", "0")
    monkeypatch.setenv("ENABLE_DECOUPLED_REFUSAL", "0")
    monkeypatch.setenv("ENABLE_EVIDENCE_SELECTION", "0")
    monkeypatch.delenv("BM25_WEIGHT", raising=False)
    monkeypatch.delenv("CHROMA_WEIGHT", raising=False)


def _make_pipeline(vector_db: Any, **kwargs) -> HybridRAGPipeline:
    return HybridRAGPipeline(
        vector_db=vector_db,
        local_slm=object(),
        generator=object(),
        **kwargs,
    )


def test_replace_vector_db_tim_duoc_document_moi_va_khong_con_document_cu():
    old_db = FakeChroma(["quy che hoc phi cu nam truoc"])
    new_db = FakeChroma(["quy che hoc phi moi xyzunique"])
    pipeline = _make_pipeline(old_db)
    old_retriever = pipeline.ensemble_retriever
    assert old_retriever is not None

    pipeline.replace_vector_db(new_db)

    assert pipeline.vector_db is new_db
    assert pipeline.ensemble_retriever is not old_retriever

    contents = [doc.page_content for doc in pipeline.retrieve("xyzunique", k=5)]
    assert any("xyzunique" in text for text in contents)
    assert all("nam truoc" not in text for text in contents)


def test_replace_that_bai_khong_de_lai_trang_thai_nua_voi():
    old_db = FakeChroma(["chunk cu"])
    pipeline = _make_pipeline(old_db)
    old_retriever = pipeline.ensemble_retriever

    with pytest.raises(RetrieverRebuildError):
        pipeline.replace_vector_db(FakeChroma([]))  # collection rỗng

    assert pipeline.vector_db is old_db
    assert pipeline.ensemble_retriever is old_retriever


def test_replace_tu_choi_doi_tuong_khong_dung_duoc_lam_vector_db():
    old_db = FakeChroma(["chunk cu"])
    pipeline = _make_pipeline(old_db)
    old_retriever = pipeline.ensemble_retriever

    with pytest.raises(RetrieverRebuildError):
        pipeline.replace_vector_db(object())

    assert pipeline.vector_db is old_db
    assert pipeline.ensemble_retriever is old_retriever


def test_replace_xoa_so_lieu_luot_truy_xuat_cu():
    pipeline = _make_pipeline(FakeChroma(["chunk cu"]))
    pipeline.last_leg_ranks = {"0": (1, 1)}
    pipeline.last_rerank_call = {"candidates": 1}

    pipeline.replace_vector_db(FakeChroma(["chunk moi"]))

    assert pipeline.last_leg_ranks is None
    assert pipeline.last_rerank_call is None


def test_khong_hybrid_chi_thay_db_va_khong_dung_retriever_lai():
    old_db = FakeChroma(["chunk cu"])
    pipeline = _make_pipeline(old_db, use_hybrid=False)
    assert pipeline.ensemble_retriever is None

    new_db = FakeChroma(["chunk moi"])
    pipeline.replace_vector_db(new_db)

    assert pipeline.vector_db is new_db
    assert pipeline.ensemble_retriever is None


def test_retriever_tuy_chinh_thi_tu_choi_thay_db():
    sentinel = FakeDenseLeg(db=FakeChroma(["custom"]))
    old_db = FakeChroma(["chunk cu"])
    pipeline = _make_pipeline(old_db, retriever=sentinel)

    with pytest.raises(RetrieverRebuildError):
        pipeline.replace_vector_db(FakeChroma(["chunk moi"]))

    assert pipeline.vector_db is old_db
    assert pipeline.ensemble_retriever is sentinel


def test_khoi_tao_voi_collection_rong_van_lui_ve_vector_thuan_nhu_cu():
    # Ngữ nghĩa khởi tạo cũ: collection rỗng ⇒ không có BM25, không ném lỗi.
    pipeline = _make_pipeline(FakeChroma([]))
    assert pipeline.ensemble_retriever is None
