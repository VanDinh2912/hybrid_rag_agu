"""Unit test cho lever T5a `ENABLE_RERANKER` — mặc định TẮT, không gọi model thật.

Bất biến #2 của vòng lặp: một lever mới phải chứng minh cờ TẮT để hành vi cũ còn
nguyên từng ký tự. Vì vậy mỗi test bật cờ đều đi kèm một test "cờ tắt" cùng dữ liệu,
và test đọc `FakeVectorDB.received` để chắc rằng đường lùi về `similarity_search`
không bao giờ được kích hoạt bởi code của reranker.

Fake model chỉ là một đối tượng có `predict()` trả điểm cố định — không cần tải
2,3 GB weights khi chạy test.
"""

import pytest
from langchain_core.documents import Document

from src import reranker as reranker_module
from src.pipeline import HybridRAGPipeline
from src.reranker import (
    DEFAULT_CANDIDATE_POOL,
    DEFAULT_RERANKER_MODEL,
    LastCall,
    RerankerUnavailable,
    reranker_batch_size,
    reranker_candidate_pool,
    reranker_device,
    reranker_enabled,
    reranker_keep_candidates,
    reranker_max_length,
    reranker_model_id,
    rerank_documents,
)
from src.text_utils import fold

ALL_OFF_ENVS = [
    "ENABLE_RERANKER",
    "RERANKER_MODEL",
    "RERANKER_DEVICE",
    "RERANKER_CANDIDATE_POOL",
    "RERANKER_KEEP_CANDIDATES",
    "RERANKER_MAX_LENGTH",
    "RERANKER_BATCH_SIZE",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Mỗi test bắt đầu với môi trường sạch và state toàn cục đã reset."""
    for name in ALL_OFF_ENVS:
        monkeypatch.delenv(name, raising=False)
    reranker_module.reset_reranker_cache()
    reranker_module.last_call.record()
    yield
    reranker_module.reset_reranker_cache()
    reranker_module.last_call.record()


def doc(text: str, chunk_id: int, source: str = "a.pdf") -> Document:
    return Document(page_content=text, metadata={"source": source, "chunk_id": chunk_id})


class FakeCrossEncoder:
    """Giả CrossEncoder: điểm tra theo bảng, ghi lại mọi cặp đã nhận."""

    def __init__(self, scores=None, raise_on_predict=None):
        self.scores = scores or {}
        self.pairs = []
        self.raise_on_predict = raise_on_predict
        self.predict_calls = 0

    def predict(self, pairs, batch_size=None, convert_to_numpy=True):
        self.predict_calls += 1
        self.pairs.extend(pairs)
        if self.raise_on_predict:
            raise self.raise_on_predict
        return [self.scores.get(p[1], 0.0) for p in pairs]


# ----------------------------------------------------------------- cờ và tham số env
class TestCờMặcĐịnhTắt:
    def test_không_cờ_thì_tắt(self):
        assert reranker_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_giá_trị_bật(self, monkeypatch, value):
        monkeypatch.setenv("ENABLE_RERANKER", value)
        assert reranker_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "   ", "abc", "2"])
    def test_giá_trị_rác_không_bật_được(self, monkeypatch, value):
        monkeypatch.setenv("ENABLE_RERANKER", value)
        assert reranker_enabled() is False

    def test_mặc_định_model_là_v2_m3_kèm_prefix_tổ_chức(self):
        assert reranker_model_id() == DEFAULT_RERANKER_MODEL == "BAAI/bge-reranker-v2-m3"

    def test_model_không_prefix_bị_chặn_bằng_lỗi_r9(self, monkeypatch):
        """r9 đặt `bge-reranker-base` (thiếu `BAAI/`) -> RepositoryNotFoundError ->
        âm thầm lùi về bi-encoder. Lever này phải CHẶN kiểu tên đó thay vì lùi."""
        monkeypatch.setenv("RERANKER_MODEL", "bge-reranker-base")
        with pytest.raises(RerankerUnavailable) as excinfo:
            reranker_model_id()
        message = str(excinfo.value)
        assert "BAAI/" in message and "RepositoryNotFoundError" in message

    def test_ten_đúng_prefix_được_chấp_nhận(self, monkeypatch):
        monkeypatch.setenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
        assert reranker_model_id() == "BAAI/bge-reranker-base"

    def test_duong_dan_cuc_bo_duoc_chap_nhan(self, monkeypatch, tmp_path):
        monkeypatch.setenv("RERANKER_MODEL", str(tmp_path))
        assert reranker_model_id() == str(tmp_path)

    def test_tham_so_mack_dinh(self):
        assert reranker_candidate_pool() == DEFAULT_CANDIDATE_POOL == 20
        assert reranker_device() == "cpu"
        assert reranker_keep_candidates() is False
        assert reranker_max_length() == 512
        assert reranker_batch_size() == 4

    @pytest.mark.parametrize("value,expected", [("8", 8), ("0", 1), ("-3", 1), ("3.9", 3)])
    def test_pool_chan_ve_nhieu_hon_0(self, monkeypatch, value, expected):
        monkeypatch.setenv("RERANKER_CANDIDATE_POOL", value)
        assert reranker_candidate_pool() == expected

    def test_env_dữ_dạng_trả_về_mặc_định(self, monkeypatch):
        monkeypatch.setenv("RERANKER_CANDIDATE_POOL", "abc")
        monkeypatch.setenv("RERANKER_MAX_LENGTH", " ")
        assert reranker_candidate_pool() == DEFAULT_CANDIDATE_POOL
        assert reranker_max_length() == 512


# ----------------------------------------------------------------- hàm xếp hạng thuần
class TestRerankDocuments:
    DOCS = [doc(f"chunk {i}", i) for i in range(1, 6)]

    def test_danh_sách_rỗng_trả_rỗng_không_chạm_model(self):
        fake = FakeCrossEncoder()
        assert rerank_documents("hỏi", [], model=fake) == []
        assert fake.predict_calls == 0

    def test_sắp_theo_điểm_giảm_dần(self):
        fake = FakeCrossEncoder({"chunk 1": 0.1, "chunk 2": 0.9, "chunk 3": 0.5})
        out = rerank_documents("hỏi", self.DOCS, model=fake)
        assert [d.metadata["chunk_id"] for d in out] == [2, 3, 1, 4, 5]

    def test_điểm_bằng_nhau_giữ_thứ_tự_rrf_gốc(self):
        """Sắp xếp ổn định: tie-break là hạng cũ, không phụ thuộc thứ tự batch."""
        fake = FakeCrossEncoder({f"chunk {i}": 0.0 for i in range(1, 6)})
        out = rerank_documents("hỏi", self.DOCS, model=fake)
        assert [d.metadata["chunk_id"] for d in out] == [1, 2, 3, 4, 5]

    def test_chỉ_rerank_pool_đầu_phần_dư_giữ_nguyên_và_đứng_sau(self):
        fake = FakeCrossEncoder({"chunk 1": 0.0, "chunk 2": 0.0, "chunk 3": 5.0, "chunk 4": 0.0})
        docs = [doc(f"chunk {i}", i) for i in range(1, 8)]
        out = rerank_documents("hỏi", docs, pool=3, model=fake)
        assert [d.metadata["chunk_id"] for d in out[:3]] == [3, 1, 2]
        assert [d.metadata["chunk_id"] for d in out[3:]] == [4, 5, 6, 7]
        assert {p[1] for p in fake.pairs} == {"chunk 1", "chunk 2", "chunk 3"}

    def test_top_n_cắt_theo_cửa_sổ(self):
        fake = FakeCrossEncoder({"chunk 3": 9.0})
        out = rerank_documents("hỏi", self.DOCS, pool=4, top_n=2, model=fake)
        assert [d.metadata["chunk_id"] for d in out] == [3, 1]

    def test_query_được_giữ_nguyên_văn_passage_cũng_nguyên_văn(self):
        """PA-25 (duyệt 25-10): bỏ fold ở tầng reranker — xem docstring "Qui ước chấm điểm"."""
        fake = FakeCrossEncoder()
        docs = [doc("Điều 5. Sinh viên được học lại", 1)]
        rerank_documents("Lệ phí Đào tạo là bao nhiêu?", docs, model=fake)
        query, passage = fake.pairs[0]
        assert query == "Lệ phí Đào tạo là bao nhiêu?"
        assert query != fold("Lệ phí Đào tạo là bao nhiêu?")
        assert passage == "Điều 5. Sinh viên được học lại"

    def test_ghi_số_liệu_lượt_cuối_vào_đối_tượng_chung(self):
        """`src/pipeline.py` import chính đối tượng này — phải mutate tại chỗ."""
        fake = FakeCrossEncoder({"chunk 2": 1.0})
        before = reranker_module.last_call
        rerank_documents("hỏi", self.DOCS, model=fake)
        assert reranker_module.last_call is before
        assert before.n_scored == 5 and before.n_candidates == 5
        assert before.order_changed is True
        assert before.top_score == 1.0 and before.bottom_score == 0.0

    def test_model_chám_điểm_lỗi_nem_rerankerunavailable(self):
        fake = FakeCrossEncoder(raise_on_predict=RuntimeError("boom"))
        with pytest.raises(RerankerUnavailable):
            rerank_documents("hỏi", self.DOCS, model=fake)

    def test_thiếu_điểm_trả_về_nem_rerankerunavailable(self):
        class ShortModel:
            def predict(self, pairs, batch_size=None, convert_to_numpy=True):
                return [0.0]

        with pytest.raises(RerankerUnavailable):
            rerank_documents("hỏi", self.DOCS, model=ShortModel())

    def test_LastCall_record_ghi_đè_toàn_bộ_trường(self):
        call = LastCall(n_scored=99, model="cu", notes=["cu"])
        call.record(n_scored=3)
        assert call.n_scored == 3 and call.model == "" and call.notes == []


# ----------------------------------------------------------------- PA-25: query nguyên văn
class TestPA25QueryNguyenVan:
    """Chặn đúng loại hồi quy đã làm r12 sụp: `fold(query)` × passage còn dấu.

    Ba lớp: hàm thuần `score_pairs` (nơi lỗi sống), và manifest — vì round hậu kiểm
    chỉ đọc được `query_convention`, nên chữ ký của quy ước phải nói ĐÚNG điều code làm.
    Bằng chứng gốc: `tmp/probe_r12_fold.json` (0/30 → 28/30 chunk vàng vào top-6),
    `docs/reports/T5.md` §2.7, `docs/PENDING_APPROVAL.md` PA-25.
    """

    def test_score_pairs_truyền_query_đúng_nguyên_văn(self):
        fake = FakeCrossEncoder()
        q = "Người học được bảo lưu kết quả tối đa bao nhiêu năm?"
        reranker_module.score_pairs(fake, q, ["Điều 12. Bảo lưu 1 năm", "Học phí 2026"])
        assert [p[0] for p in fake.pairs] == [q, q]
        assert fake.pairs[0][1] == "Điều 12. Bảo lưu 1 năm"

    def test_score_pairs_chỉ_strip_không_động_văn_bản(self):
        fake = FakeCrossEncoder()
        reranker_module.score_pairs(fake, "  Điều 5  Sinh viên  ", ["a"])
        assert fake.pairs[0][0] == "Điều 5  Sinh viên"
        assert fold("Điều 5  Sinh viên") not in [p[0] for p in fake.pairs]

    def test_score_pairs_chịu_query_rỗng_và_none(self):
        fake = FakeCrossEncoder()
        for q in ("", None):
            reranker_module.score_pairs(fake, q, ["a", "b"])  # type: ignore[arg-type]
        assert {p[0] for p in fake.pairs} == {""}

    def test_không_còn_fold_trong_module_reranker(self):
        """`fold` bị xóa khỏi import: thêm lại fold phải sửa cả docstring Qui ước —
        không trượt âm thầm thành một quy ước chấm điểm khác."""
        assert not hasattr(reranker_module, "fold")

    def test_manifest_ghi_đúng_quy_ước_hiện_hành(self):
        convention = reranker_module.reranker_status()["query_convention"]
        assert "NGUYEN VAN" in convention and "PA-25" in convention
        assert "fold(query)" not in convention


# ----------------------------------------------------------------- nạp model
class TestGetReranker:
    def test_không_import_được_sentence_transformers_nem_lỗi_tên(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "sentence_transformers":
                raise ImportError("simulated")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(RerankerUnavailable):
            reranker_module.get_reranker()

    def test_crossencoder_lỗi_nem_rerankerunavailable_kèm_nguyên_văn(self, monkeypatch):
        class Broken:
            def __init__(self, *args, **kwargs):
                raise OSError("quota hết")

        import sentence_transformers

        monkeypatch.setattr(sentence_transformers, "CrossEncoder", Broken, raising=False)
        with pytest.raises(RerankerUnavailable) as excinfo:
            reranker_module.get_reranker()
        assert "quota hết" in str(excinfo.value)
        assert reranker_module._MODEL is None

    def test_status_không_bao_giờ_ném_ngay_cả_khi_ten_model_sai(self, monkeypatch):
        monkeypatch.setenv("RERANKER_MODEL", "bge-reranker-base")
        status = reranker_module.reranker_status()
        assert status["enabled"] is False
        assert status["requested_model"] == "bge-reranker-base"
        assert "thiếu tiền tố tổ chức" in status["model_error"]


# ----------------------------------------------------------------- pipeline: TẮT = nguyên văn
NORMALIZED = "Sinh vien co 62 diem ren luyen duoc xep loai gi?"
DOCS = [doc(f"nội dung {i}", i) for i in range(1, 13)]


class FakeChromaSubRetriever:
    def __init__(self):
        self.search_kwargs = {"k": 12}


class FakeEnsemble:
    def __init__(self, docs):
        self.retrievers = [FakeChromaSubRetriever()]
        self.weights = [0.5, 0.5]
        self._docs = docs
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return list(self._docs)


class FakeVectorDB:
    def __init__(self):
        self.received = []

    def similarity_search(self, query, k):
        self.received.append((query, k))
        return [doc("fallback", 0)]


class FakeLocalSLM:
    def generate(self, prompt, temperature=0.0):
        return NORMALIZED


def make_pipeline(monkeypatch, docs=None):
    for name in ("BM25_WEIGHT", "CHROMA_WEIGHT", "RAG_TOP_K", "ROUTER_SOFT_FILTER", "ROUTER_SOURCE_QUOTA"):
        monkeypatch.delenv(name, raising=False)
    ensemble = FakeEnsemble(docs if docs is not None else DOCS)
    vector_db = FakeVectorDB()
    pipeline = HybridRAGPipeline(
        vector_db=vector_db,
        local_slm=FakeLocalSLM(),
        generator=object(),
        retriever=ensemble,
    )
    return pipeline, ensemble, vector_db


class TestPipelineCờTắt:
    def test_cờ_tắt_cửa_sổ_không_đổi_và_leg_giữ_k_cũ(self, monkeypatch):
        pipeline, ensemble, vector_db = make_pipeline(monkeypatch)
        out = pipeline.retrieve(NORMALIZED, k=6)
        assert [d.metadata["chunk_id"] for d in out] == list(range(1, 7))
        assert ensemble.retrievers[0].search_kwargs["k"] == 6
        assert pipeline.last_rerank_call is None
        assert vector_db.received == []

    def test_cờ_tắt_không_bao_giờ_gọi_get_reranker(self, monkeypatch):
        pipeline, _, _ = make_pipeline(monkeypatch)

        def explode(*args, **kwargs):
            raise AssertionError("get_reranker bị gọi khi ENABLE_RERANKER tắt")

        monkeypatch.setattr(reranker_module, "get_reranker", explode)
        pipeline.retrieve(NORMALIZED, k=6)


class TestPipelineCờBật:
    @pytest.fixture()
    def scored_pipeline(self, monkeypatch):
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        # chunk 11 (ngoài cửa sổ 6) là câu trả lời đúng -> reranker phải kéo vào ô đầu.
        fake = FakeCrossEncoder({"nội dung 11": 7.0})
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)
        pipeline, ensemble, vector_db = make_pipeline(monkeypatch, docs=DOCS[:12])
        return pipeline, ensemble, vector_db, fake

    def test_leg_quét_sâu_tới_pool(self, scored_pipeline):
        pipeline, ensemble, _, _ = scored_pipeline
        pipeline.retrieve(NORMALIZED, k=6)
        assert ensemble.retrievers[0].search_kwargs["k"] == max(6, DEFAULT_CANDIDATE_POOL) == 20

    def test_chunk_vàng_từ_hạng_11_vào_đầu_cửa_sổ(self, scored_pipeline):
        pipeline, _, _, _ = scored_pipeline
        out = pipeline.retrieve(NORMALIZED, k=6)
        assert out[0].metadata["chunk_id"] == 11
        assert [d.metadata["chunk_id"] for d in out] == [11, 1, 2, 3, 4, 5]

    def test_manifest_có_số_liệu_lượt_rerank(self, scored_pipeline):
        pipeline, _, _, _ = scored_pipeline
        pipeline.retrieve(NORMALIZED, k=6)
        status = reranker_module.reranker_status()
        assert status["enabled"] is True and status["device"] == "cpu"
        assert status["candidate_pool"] == 20 and status["keep_candidates"] is False
        call = pipeline.last_rerank_call
        assert call["n_candidates"] == 12 and call["n_scored"] == 12
        assert call["order_changed"] is True

    def test_keep_candidates_trả_toàn_pool_để_đo_trần(self, monkeypatch, scored_pipeline):
        monkeypatch.setenv("RERANKER_KEEP_CANDIDATES", "1")
        pipeline, _, _, _ = scored_pipeline
        out = pipeline.retrieve(NORMALIZED, k=6)
        assert len(out) == 12  # pool 20 nhưng chỉ có 12 ứng viên

    def test_model_không_tải_được_thì_nem_lên_không_lùi_similarity_search(self, monkeypatch):
        monkeypatch.setenv("ENABLE_RERANKER", "1")

        def explode(**kwargs):
            raise RerankerUnavailable("không tải được")

        monkeypatch.setattr(reranker_module, "get_reranker", explode)
        pipeline, _, vector_db = make_pipeline(monkeypatch)
        with pytest.raises(RerankerUnavailable):
            pipeline.retrieve(NORMALIZED, k=6)
        assert vector_db.received == []  # không được rơi xuống nhánh lùi

    def test_rerank_chạy_sau_bonus_nên_không_đối_đầu_lọc_mềm(self, monkeypatch):
        """Cửa sổ 6 ô với bonus 12 đẩy chunk 11 ra; reranker kéo lại mà không đổi filter."""
        from src.router import RetrievalConfig

        monkeypatch.setenv("ENABLE_RERANKER", "1")
        fake = FakeCrossEncoder({"nội dung 11": 3.0})
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)
        docs = [doc("nội dung 11", 11, source="khac.pdf")] + [
            doc(f"nội dung {i}", i, source="a.pdf") for i in range(1, 11)
        ]
        pipeline, _, _ = make_pipeline(monkeypatch, docs=docs)
        # make_pipeline xóa các env router (cho sạch test khác), nên phải đặt SAU khi dựng.
        monkeypatch.setenv("ROUTER_SOFT_FILTER", "1")
        monkeypatch.setenv("ROUTER_FILTER_RANK_BONUS", "12")
        config = RetrievalConfig(top_k=6, bm25_weight=0.5, chroma_weight=0.5, source_filter=["a.pdf"])
        out = pipeline.retrieve(NORMALIZED, k=6, config=config)
        # bonus 12 một mình xếp 11 ra sau 10 chunk cùng nguồn a.pdf; reranker quyết lại.
        assert out[0].metadata["chunk_id"] == 11

    def test_lọc_cứng_vẫn_cắt_trước_reranker_giới_hạn_đã_đăng_ký(self, monkeypatch):
        """Reranker chỉ XẾP LẠI những gì pipeline giao cho nó. Nếu còn lọc CỨNG
        (ROUTER_SOFT_FILTER tắt) thì chunk ngoài nguồn bị xóa khỏi pool từ trước,
        reranker không có gì để kéo lại — test này chốt giới hạn đó thành chữ."""
        from src.router import RetrievalConfig

        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.delenv("ROUTER_SOFT_FILTER", raising=False)
        fake = FakeCrossEncoder({"nội dung 11": 3.0})
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)
        docs = [doc("nội dung 11", 11, source="khac.pdf")] + [
            doc(f"nội dung {i}", i, source="a.pdf") for i in range(1, 11)
        ]
        pipeline, _, _ = make_pipeline(monkeypatch, docs=docs)
        config = RetrievalConfig(top_k=6, bm25_weight=0.5, chroma_weight=0.5, source_filter=["a.pdf"])
        out = pipeline.retrieve(NORMALIZED, k=6, config=config)
        assert 11 not in [d.metadata["chunk_id"] for d in out]

