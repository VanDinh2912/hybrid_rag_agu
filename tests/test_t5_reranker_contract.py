"""Kiểm thử T5 (mục 1–6) — HỢP ĐỒNG RERANKER `ENABLE_RERANKER`, dùng model GIẢ.

Sáu mục của đề bài và cách kiểm:
  1. Cờ TẮT => top-k byte-identical với trước đó. Hai lớp bằng chứng: (a) golden 30
     lượt `pipeline.run` chụp từ cây TRƯỚC khi nối T3/T4/T5 (`git archive HEAD` =
     f492f05, cùng golden `tests/golden/t3_off_30items_head_f492f05.json` mà T3 đã
     dùng); (b) `retrieve()` trả ĐÚNG các đối tượng Document cũ, cùng thứ tự, leg giữ
     `k` cũ, không gọi `get_reranker`, không rơi về `similarity_search`.
  2. Cờ BẬT: lấy đúng 20 ứng viên đầu theo thứ tự RRF+bonus, trả đúng 6 (k), tập trả
     về là tập con của 20, model giả đảo điểm => thứ tự đầu ra đúng theo điểm giả.
  3. Hòa điểm: tie-break ổn định theo hạng cũ; cùng input hai lần cho cùng output.
  4. < 6 ứng viên hoặc rỗng: không crash, trả những gì có, không gọi model khi rỗng.
  5. Reranker lỗi/timeout: ĐỀ BÀI YÊU CẦU lùi về thứ tự RRF + cảnh báo. Thiết kế đã
     ĐĂNG KÝ TRƯỚC (`data/loop/README.md` mục T5) chọn dừng loudly, nên hành vi lùi nằm
     sau cờ TƯỜNG MINH `RERANKER_FALLBACK=1` (PA-18a). Test ghim CẢ HAI nửa: mặc định
     vẫn ném `RerankerUnavailable`; khi bật cờ thì trả đúng danh sách RRF trước rerank,
     in cảnh báo, ghi `fallback_used=true`, không rơi về `similarity_search` và không
     làm hỏng câu trả lời của `pipeline.run`.
  6. Bonus lọc mềm + lọc nguồn: rerank chạy SAU bonus/quota, ứng viên được bonus vào
     cross-encoder đúng thứ tự đã cộng hạng; lọc CỨNG vẫn cắt trước reranker.

Không gọi model thật / Chroma / Ollama / Gemini. Mọi tầng dưới là fake; generator
không được gọi trong các test `retrieve()`. Bất biến #6: test chỉ dùng câu hỏi và
`page_content`, không đọc trường vàng nào của testset.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document

from src import reranker as reranker_module
from src.pipeline import HybridRAGPipeline
from src.router import RetrievalConfig, rescore_with_source_preference
from src.reranker import (
    DEFAULT_RERANKER_MODEL,
    RerankerUnavailable,
    last_call,
    rerank_documents,
    reranker_status,
)
from src.text_utils import fold

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "t3_off_30items_head_f492f05.json"
HARNESS_PATH = REPO_ROOT / "tools" / "diag" / "t3_golden_dump.py"

RERANKER_ENVS = (
    "ENABLE_RERANKER",
    "RERANKER_MODEL",
    "RERANKER_DEVICE",
    "RERANKER_CANDIDATE_POOL",
    "RERANKER_KEEP_CANDIDATES",
    "RERANKER_MAX_LENGTH",
    "RERANKER_BATCH_SIZE",
    "RERANKER_FALLBACK",
    # Các lever khác phải TẮT để mỗi test chỉ đo một thứ.
    "ENABLE_DECOUPLED_REFUSAL",
    "ENABLE_EVIDENCE_SELECTION",
    "ENABLE_CLASSIFIER",
    "ENABLE_QUERY_EXPANSION",
    "ENABLE_ANSWER_GUARD",
    "ENABLE_ANSWER_RESCUE",
    "ROUTER_SOFT_FILTER",
    "ROUTER_FILTER_RANK_BONUS",
    "ROUTER_SOURCE_QUOTA",
    "BM25_WEIGHT",
    "CHROMA_WEIGHT",
    "RAG_TOP_K",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in RERANKER_ENVS:
        monkeypatch.delenv(name, raising=False)
    reranker_module.reset_reranker_cache()
    reranker_module.last_call.record()
    yield
    reranker_module.reset_reranker_cache()
    reranker_module.last_call.record()


# ------------------------------------------------------------------ đồ giả
def doc(text: str, chunk_id: int, source: str = "a.pdf", tier: str = "Tầng 1") -> Document:
    return Document(page_content=text, metadata={"source": source, "tier": tier, "chunk_id": chunk_id})


class FakeCrossEncoder:
    """CrossEncoder giả: điểm tra theo passage; ghi lại đúng các cặp đã nhận."""

    def __init__(self, scores: dict[str, float] | None = None, error: Exception | None = None):
        self.scores = dict(scores or {})
        self.error = error
        self.pairs: list[tuple[str, str]] = []
        self.calls = 0

    def predict(self, pairs, batch_size=None, convert_to_numpy=True):
        self.calls += 1
        self.pairs.extend([(str(p[0]), str(p[1])) for p in pairs])
        if self.error is not None:
            raise self.error
        return [float(self.scores.get(p[1], 0.0)) for p in pairs]


class FakeLeg:
    def __init__(self, docs: list[Document]):
        self.docs = docs
        self.search_kwargs = {"k": 6}
        self.calls = 0

    def invoke(self, query):
        self.calls += 1
        return list(self.docs)


class FakeEnsemble:
    def __init__(self, docs: list[Document]):
        self.docs = docs
        self.retrievers = [FakeLeg(docs)]
        self.weights = [0.5, 0.5]
        self.calls = 0

    def invoke(self, query):
        self.calls += 1
        return list(self.docs)


class FakeVectorDB:
    def __init__(self):
        self.received: list[tuple[str, int]] = []

    def similarity_search(self, query, k):
        self.received.append((query, k))
        return [doc("fallback", 0)]


class FakeLocalSLM:
    def generate(self, prompt, temperature=0.0):
        return "Sinh vien co 62 diem ren luyen duoc xep loai gi?"


class ExplodingGenerator:
    def generate_answer(self, **kwargs):  # pragma: no cover - không được gọi
        raise AssertionError("generator không được gọi trong test retrieve()")


def make_pipeline(docs: list[Document]):
    ensemble = FakeEnsemble(docs)
    vector_db = FakeVectorDB()
    pipeline = HybridRAGPipeline(
        vector_db=vector_db,
        local_slm=FakeLocalSLM(),
        generator=ExplodingGenerator(),
        retriever=ensemble,
    )
    return pipeline, ensemble, vector_db


def ids(docs) -> list[int]:
    return [d.metadata["chunk_id"] for d in docs]


QUERY = "Sinh viên có 62 điểm rèn luyện được xếp loại gì?"
DOCS = [doc(f"nội dung {i}", i) for i in range(1, 31)]


def load_golden_harness():
    spec = importlib.util.spec_from_file_location("t5_golden_harness", HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["t5_golden_harness"] = module
    spec.loader.exec_module(module)
    return module


# ================================================================ 1. CỜ TẮT
class TestMotCoTatByteIdentical:
    def test_golden_30_luot_pipeline_run_khop_cay_truoc_khi_noi_T5(self):
        """T5 TẮT => `pipeline.run` phải khớp golden chụp từ `git archive HEAD` f492f05."""
        assert GOLDEN_PATH.exists(), f"thiếu golden {GOLDEN_PATH}"
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        assert golden["meta"]["pipeline_has_t3_fields"] is False
        assert len(golden["core"]) == 30

        saved = dict(os.environ)
        try:
            harness = load_golden_harness()
            harness.pin_env()  # ghim cả ENABLE_RERANKER=0
            rows = [harness.run_item(item)["core"] for item in harness.build_items()]
        finally:
            os.environ.clear()
            os.environ.update(saved)

        now = json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        before = json.dumps(golden["core"], ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        assert hashlib.sha256(now).hexdigest() == hashlib.sha256(before).hexdigest()
        assert rows == golden["core"]  # từng item, từng khóa

    def test_retrieve_tat_tra_dung_cac_doi_tuong_cu_cung_thu_tu(self):
        pipeline, ensemble, vector_db = make_pipeline(DOCS)
        out = pipeline.retrieve(QUERY, k=6)
        assert len(out) == 6
        assert all(out[i] is DOCS[i] for i in range(6)), "cờ TẮT không được sao/chép/đổi thứ tự"
        assert ids(out) == [1, 2, 3, 4, 5, 6]
        assert ensemble.retrievers[0].search_kwargs["k"] == 6, "leg phải giữ k cũ, không quét pool"
        assert pipeline.last_rerank_call is None
        assert vector_db.received == []

    def test_co_tat_khong_bao_gio_goi_get_reranker(self, monkeypatch):
        def explode(**kwargs):  # pragma: no cover - nếu bị gọi là test đỏ
            raise AssertionError("get_reranker bị gọi khi ENABLE_RERANKER=0")

        monkeypatch.setattr(reranker_module, "get_reranker", explode)
        pipeline, _, _ = make_pipeline(DOCS)
        pipeline.retrieve(QUERY, k=6)

    def test_co_tat_last_call_khong_bi_ghi(self):
        pipeline, _, _ = make_pipeline(DOCS)
        pipeline.retrieve(QUERY, k=6)
        assert last_call.as_dict() == {
            "n_candidates": 0,
            "n_scored": 0,
            "seconds": 0.0,
            "model": "",
            "device": "",
            "pool": 0,
            "top_score": None,
            "bottom_score": None,
            "order_changed": False,
            "notes": [],
        }


# ================================================================ 2. POOL 20 -> CỬA SỔ 6
class TestHaiBatPool20CuaSo6:
    def _on(self, monkeypatch, fake):
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)

    def test_lay_dung_20_ung_vien_dau_theo_thu_tu_rrf(self, monkeypatch):
        fake = FakeCrossEncoder()
        self._on(monkeypatch, fake)
        pipeline, ensemble, _ = make_pipeline(DOCS)
        pipeline.retrieve(QUERY, k=6)
        assert ensemble.retrievers[0].search_kwargs["k"] == 20
        assert len(fake.pairs) == 20
        assert [passage for _query, passage in fake.pairs] == [f"nội dung {i}" for i in range(1, 21)]

    def test_tra_dung_6_va_la_tap_con_cua_20(self, monkeypatch):
        fake = FakeCrossEncoder({f"nội dung {i}": float(i) for i in range(1, 31)})
        self._on(monkeypatch, fake)
        pipeline, _, _ = make_pipeline(DOCS)
        out = pipeline.retrieve(QUERY, k=6)
        assert len(out) == 6
        assert set(ids(out)) <= set(range(1, 21))
        assert set(ids(out)).isdisjoint(range(21, 31))
        assert all(passage != f"nội dung {i}" for i in range(21, 31) for _q, passage in fake.pairs)

    def test_model_gia_dao_thu_tu_thi_dau_ra_dung_theo_diem_gia(self, monkeypatch):
        """Điểm cao cho chunk hạng cuối pool => 6 ô đầu là 20,19,18,17,16,15."""
        fake = FakeCrossEncoder({f"nội dung {i}": float(i) for i in range(1, 31)})
        self._on(monkeypatch, fake)
        pipeline, _, _ = make_pipeline(DOCS)
        out = pipeline.retrieve(QUERY, k=6)
        assert ids(out) == [20, 19, 18, 17, 16, 15]

    def test_chunk_hang_11_vao_duoc_cua_so_6(self, monkeypatch):
        """Đúng nhóm lỗi T5 nhắm tới: vàng ở hạng 7–12 ngoài cửa sổ cũ."""
        fake = FakeCrossEncoder({"nội dung 11": 100.0})
        self._on(monkeypatch, fake)
        pipeline, _, _ = make_pipeline(DOCS)
        out = pipeline.retrieve(QUERY, k=6)
        assert ids(out)[0] == 11
        assert len(out) == 6

    def test_rerank_documents_pool_mac_dinh_20_va_ghi_manifest(self):
        fake = FakeCrossEncoder({f"nội dung {i}": float(i) for i in range(1, 31)})
        out = rerank_documents(QUERY, DOCS, model=fake)
        assert len(out) == 30  # không top_n: 20 đã xếp lại + 10 đuôi giữ nguyên
        assert ids(out[:20]) == list(range(20, 0, -1))
        assert ids(out[20:]) == list(range(21, 31))
        assert len(fake.pairs) == 20
        call = last_call.as_dict()
        assert call["n_candidates"] == 30 and call["n_scored"] == 20 and call["pool"] == 20
        assert call["order_changed"] is True
        assert call["top_score"] == 20.0 and call["bottom_score"] == 1.0
        assert call["model"] == DEFAULT_RERANKER_MODEL and call["device"] == "cpu"

    def test_query_gui_model_nguyen_van_passage_nguyen_van(self, monkeypatch):
        """PA-25 (duyệt 25-10): query đi vào cross-encoder NGUYÊN VĂN.

        Bản cũ fold query — mất dấu thanh — trong khi passage giữ dấu; với
        bge-reranker-v2-m3 (model đa ngôn ngữ nhạy dấu) cặp lệch dấu gần như nhiễu:
        r12 gold@6 0,7400→0,6686, probe 30 item 0/30 chunk vàng vào top-6 so với
        28/30 khi bỏ fold (`tmp/probe_r12_fold.json`).
        """
        fake = FakeCrossEncoder()
        self._on(monkeypatch, fake)
        pipeline, _, _ = make_pipeline(DOCS)
        pipeline.retrieve(QUERY, k=6)
        query = fake.pairs[0][0]
        assert query == QUERY.strip() == QUERY
        assert query != fold(QUERY)          # nếu ai đó thêm lại fold, test này đỏ
        assert "viên" in query and "luyện" in query  # dấu thanh còn nguyên
        assert fake.pairs[0][1] == "nội dung 1"  # passage giữ dấu


# ================================================================ 3. HÒA ĐIỂM
class TestBaHoaDiem:
    def test_hoa_diem_giu_thu_tu_rrf_goc(self):
        fake = FakeCrossEncoder()  # mọi điểm = 0.0
        out = rerank_documents(QUERY, DOCS, model=fake)
        assert ids(out) == list(range(1, 31))

    def test_hoa_diem_mot_phan_giu_thu_tu_cho_cac_cap_bang(self):
        # 1..10 bằng 1.0, 11..20 bằng 0.0 => hai nhóm, trong nhóm giữ hạng cũ.
        fake = FakeCrossEncoder({f"nội dung {i}": 1.0 for i in range(1, 11)})
        out = rerank_documents(QUERY, DOCS, model=fake)
        assert ids(out[:20]) == list(range(1, 21))
        assert ids(out[20:]) == list(range(21, 31))

    def test_cung_input_hai_lan_cho_cung_output(self):
        fake = FakeCrossEncoder({f"nội dung {i}": float((i * 7) % 5) for i in range(1, 31)})
        first = rerank_documents(QUERY, DOCS, model=fake)
        first_ids = ids(first)
        second = rerank_documents(QUERY, DOCS, model=fake)
        assert ids(second) == first_ids
        assert [p for _q, p in fake.pairs[:20]] == [p for _q, p in fake.pairs[20:40]]

    def test_thu_tu_batch_khong_anh_huong_ket_qua(self):
        """Cùng bảng điểm, đảo thứ tự cặp trong batch vẫn cho cùng thứ tự đầu ra."""
        scores = {f"nội dung {i}": float((i * 3) % 7) for i in range(1, 31)}

        class PairShufflingModel(FakeCrossEncoder):
            """Trả điểm theo đúng cặp nhưng nhận cặp theo thứ tự đảo."""

            def predict(self, pairs, batch_size=None, convert_to_numpy=True):
                shuffled = list(reversed(list(pairs)))
                scored = [float(self.scores.get(p[1], 0.0)) for p in shuffled]
                self.pairs.extend([(str(p[0]), str(p[1])) for p in shuffled])
                return list(reversed(scored))

        normal = rerank_documents(QUERY, DOCS, model=FakeCrossEncoder(scores))
        shuffled = rerank_documents(QUERY, DOCS, model=PairShufflingModel(scores))
        assert ids(shuffled) == ids(normal)


# ================================================================ 4. ÍT HƠN 6 / RỖNG
class TestBonItHon6VaRong:
    def test_bon_ung_vien_tra_du_bon_khong_crash(self, monkeypatch):
        docs = DOCS[:4]
        fake = FakeCrossEncoder({f"nội dung {i}": float(i) for i in range(1, 5)})
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)
        pipeline, _, _ = make_pipeline(docs)
        out = pipeline.retrieve(QUERY, k=6)
        assert ids(out) == [4, 3, 2, 1]
        assert len(fake.pairs) == 4
        assert pipeline.last_rerank_call["n_candidates"] == 4

    def test_ung_vien_rong_tra_rong_khong_goi_model(self, monkeypatch):
        def explode(**kwargs):  # pragma: no cover
            raise AssertionError("không được nạp model khi không có ứng viên")

        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.setattr(reranker_module, "get_reranker", explode)
        pipeline, _, vector_db = make_pipeline([])
        assert pipeline.retrieve(QUERY, k=6) == []
        assert vector_db.received == []

    def test_mot_ung_vien_duy_nhat(self):
        fake = FakeCrossEncoder({"chỉ một": 0.5})
        out = rerank_documents(QUERY, [doc("chỉ một", 99)], model=fake)
        assert ids(out) == [99]
        assert len(fake.pairs) == 1


# ================================================================ 5. LỖI / TIMEOUT
class TestNamLoiTimeout:
    def _on(self, monkeypatch, fake):
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)

    def test_timeout_duoc_boc_thanh_rerankerunavailable_kem_nguyen_van(self):
        fake = FakeCrossEncoder(error=TimeoutError("quá 30 giây"))
        with pytest.raises(RerankerUnavailable) as excinfo:
            rerank_documents(QUERY, DOCS, model=fake)
        assert "TimeoutError" in str(excinfo.value) and "quá 30 giây" in str(excinfo.value)

    def test_loi_model_nem_len_khong_lui_ve_similarity_search(self, monkeypatch):
        """GHIM THIẾT KẾ ĐÃ ĐĂNG KÝ: một round đo nhầm lever tệ hơn round dừng loudly."""
        fake = FakeCrossEncoder(error=RuntimeError("model hỏng"))
        self._on(monkeypatch, fake)
        pipeline, _, vector_db = make_pipeline(DOCS)
        with pytest.raises(RerankerUnavailable):
            pipeline.retrieve(QUERY, k=6)
        assert vector_db.received == [], "KHÔNG được rơi xuống nhánh lùi similarity_search"

    def test_khong_tai_duoc_model_nem_len_khong_lui(self, monkeypatch):
        monkeypatch.setenv("ENABLE_RERANKER", "1")

        def explode(**kwargs):
            raise RerankerUnavailable("không tải được model")

        monkeypatch.setattr(reranker_module, "get_reranker", explode)
        pipeline, _, vector_db = make_pipeline(DOCS)
        with pytest.raises(RerankerUnavailable):
            pipeline.retrieve(QUERY, k=6)
        assert vector_db.received == []

    def test_de_bai_muc_5_noi_lui_rrf_nhung_thiet_ke_da_dang_ky_thi_khong(self, monkeypatch):
        """ĐIỂM LỆCH PHẢI ĐƯỢC GHI THÀNH TEST, không giấu trong báo cáo.

        Đề bài kiểm thử (mục 5) muốn: lỗi/timeout -> lùi về thứ tự RRF cũ + log cảnh
        báo. Thiết kế T5 đã đăng ký trước (data/loop/README.md) và code hiện tại chọn:
        ném `RerankerUnavailable`, không có danh sách RRF nào được trả về. Test này
        khẳng định ĐÚNG hành vi hiện tại để lần sau ai đổi chiều sẽ thấy test đỏ; nó
        KHÔNG phải bằng chứng mục 5 đã đạt theo câu chữ.
        """
        fake = FakeCrossEncoder(error=TimeoutError("timeout"))
        self._on(monkeypatch, fake)
        pipeline, _, _ = make_pipeline(DOCS)
        with pytest.raises(RerankerUnavailable):
            pipeline.retrieve(QUERY, k=6)
        assert pipeline.last_rerank_call is None

    def test_manifest_van_bao_dung_ten_model_va_thiet_bi(self, monkeypatch):
        fake = FakeCrossEncoder()
        self._on(monkeypatch, fake)
        status = reranker_status()
        assert status["enabled"] is True
        assert status["requested_model"] == DEFAULT_RERANKER_MODEL
        assert status["device"] == "cpu"
        assert status["candidate_pool"] == 20
        assert status["keep_candidates"] is False


# ================================================== 5b. LÙI RRF TƯỜNG MINH (PA-18a)
class StubAnswerGenerator:
    """Generator giả để chứng minh lỗi reranker không làm hỏng câu trả lời."""

    def __init__(self):
        self.calls = 0
        self.received: list[Document] = []

    def generate_answer(self, query, retrieved_docs, **kwargs):
        self.calls += 1
        self.received = list(retrieved_docs)
        return "Câu trả lời từ thứ tự RRF."


class TestNamBLuiRrfTuongMinh:
    """Mục 5 đề bài: lỗi/timeout -> lùi RRF + cảnh báo, không hỏng câu trả lời.

    Lùi chỉ xảy ra khi bật `RERANKER_FALLBACK=1` (PA-18a); mặc định vẫn dừng loudly và
    test ở `TestNamLoiTimeout` ghim nguyên trạng đó. Hai nửa cùng tồn tại có chủ đích.
    """

    def _on(self, monkeypatch, fake):
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.setenv("RERANKER_FALLBACK", "1")
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)

    def test_bat_co_lui_tra_dung_thu_tu_rrf_va_canh_bao(self, monkeypatch, capsys):
        fake = FakeCrossEncoder(error=TimeoutError("quá 30 giây"))
        self._on(monkeypatch, fake)
        pipeline, _, vector_db = make_pipeline(DOCS)
        out = pipeline.retrieve(QUERY, k=6)

        assert ids(out) == [1, 2, 3, 4, 5, 6]
        assert all(out[i] is DOCS[i] for i in range(6)), "phải trả ĐÚNG object theo thứ tự trước rerank"
        captured = capsys.readouterr().out
        assert "[Reranker] Cảnh báo" in captured
        assert "RERANKER_FALLBACK=1" in captured
        assert "quá 30 giây" in captured  # nguyên văn lỗi, không nuốt
        assert pipeline.last_rerank_call["fallback_used"] is True
        assert "quá 30 giây" in pipeline.last_rerank_call["error"]
        assert vector_db.received == [], "lùi RRF, KHÔNG rơi xuống similarity_search"

    def test_bat_co_lui_khong_lam_hong_cau_tra_loi(self, monkeypatch, capsys):
        fake = FakeCrossEncoder(error=RuntimeError("model hỏng"))
        self._on(monkeypatch, fake)
        gen = StubAnswerGenerator()
        pipeline = HybridRAGPipeline(
            vector_db=FakeVectorDB(),
            local_slm=FakeLocalSLM(),
            generator=gen,
            retriever=FakeEnsemble(DOCS),
        )
        result = pipeline.run(QUERY, top_k=6)

        assert gen.calls == 1
        assert ids(gen.received)[:6] == [1, 2, 3, 4, 5, 6], "generator nhận đúng thứ tự RRF"
        assert result["answer"] == "Câu trả lời từ thứ tự RRF."
        assert len(result["contexts"]) == 6
        # `sources` phủ TOÀN BỘ retrieve_k = top_k * oversample (6 * 2 = 12) để đo Hit@k;
        # `contexts` chỉ là cửa sổ 6. Sáu nguồn đầu phải đúng thứ tự RRF trước rerank.
        assert len(result["sources"]) == 12
        assert [s["chunk_id"] for s in result["sources"][:6]] == [1, 2, 3, 4, 5, 6]
        assert [s["rank"] for s in result["sources"]] == list(range(1, 13))
        assert "[Reranker] Cảnh báo" in capsys.readouterr().out

    def test_bat_co_lui_khi_khong_tai_duoc_model(self, monkeypatch, capsys):
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.setenv("RERANKER_FALLBACK", "1")

        def explode(**kwargs):
            raise RerankerUnavailable("không tải được model")

        monkeypatch.setattr(reranker_module, "get_reranker", explode)
        pipeline, _, vector_db = make_pipeline(DOCS)
        assert ids(pipeline.retrieve(QUERY, k=6)) == [1, 2, 3, 4, 5, 6]
        assert "không tải được model" in capsys.readouterr().out
        assert pipeline.last_rerank_call["fallback_used"] is True
        assert vector_db.received == []

    def test_bat_co_lui_voi_bon_ung_vien_tra_du_bon(self, monkeypatch, capsys):
        fake = FakeCrossEncoder(error=TimeoutError("chậm"))
        self._on(monkeypatch, fake)
        pipeline, _, _ = make_pipeline(DOCS[:4])
        assert ids(pipeline.retrieve(QUERY, k=6)) == [1, 2, 3, 4]
        assert "[Reranker] Cảnh báo" in capsys.readouterr().out

    def test_mac_dinh_tat_van_nem_loi_va_khong_canh_bao(self, monkeypatch, capsys):
        fake = FakeCrossEncoder(error=TimeoutError("timeout"))
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.delenv("RERANKER_FALLBACK", raising=False)
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)
        pipeline, _, _ = make_pipeline(DOCS)
        with pytest.raises(RerankerUnavailable):
            pipeline.retrieve(QUERY, k=6)
        assert "[Reranker] Cảnh báo" not in capsys.readouterr().out
        assert pipeline.last_rerank_call is None

    def test_status_ghi_co_lui(self, monkeypatch):
        assert reranker_status()["fallback"] is False
        monkeypatch.setenv("RERANKER_FALLBACK", "1")
        assert reranker_status()["fallback"] is True


# ================================================================ 6. BONUS + LỌC NGUỒN
class TestSauBonusVaNguon:
    def _soft_pipeline(self, monkeypatch, bonus: int = 3):
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.setenv("ROUTER_SOFT_FILTER", "1")
        monkeypatch.setenv("ROUTER_FILTER_RANK_BONUS", str(bonus))
        monkeypatch.setenv("ROUTER_SOURCE_QUOTA", "0")
        fake = FakeCrossEncoder()
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)
        docs = [doc("nội dung 11", 11, source="khac.pdf"), doc("nội dung 12", 12, source="khac.pdf")] + [
            doc(f"nội dung {i}", i, source="a.pdf") for i in range(1, 11)
        ]
        pipeline, ensemble, _ = make_pipeline(docs)
        config = RetrievalConfig(top_k=6, bm25_weight=0.5, chroma_weight=0.5, source_filter=["a.pdf"])
        return pipeline, ensemble, fake, docs, config

    def test_rerank_nhan_dung_thu_tu_sau_bonus_mem(self, monkeypatch):
        pipeline, _, fake, docs, config = self._soft_pipeline(monkeypatch)
        pipeline.retrieve(QUERY, k=6, config=config)
        expected = rescore_with_source_preference(docs, ["a.pdf"], rank_bonus=3)
        assert [passage for _q, passage in fake.pairs] == [d.page_content for d in expected]
        # Ứng viên được bonus vẫn nằm trong danh sách chấm, không bị reranker "nuốt".
        assert "nội dung 1" in [passage for _q, passage in fake.pairs]

    def test_bonus_doi_thu_tu_ung_vien_truoc_rerank(self, monkeypatch):
        """Bonus 3 kéo 2 chunk ngoài nguồn xuống sau chunk nguồn đầu tiên."""
        pipeline, _, fake, docs, config = self._soft_pipeline(monkeypatch, bonus=3)
        pipeline.retrieve(QUERY, k=6, config=config)
        scored = [passage for _q, passage in fake.pairs]
        assert scored[0] == "nội dung 1"  # pos 2 - 3 => -1, đứng trước khac.pdf pos 0
        assert scored.index("nội dung 11") < scored.index("nội dung 2")

    def test_loc_cung_van_cat_truoc_reranker(self, monkeypatch):
        """SOFT_FILTER tắt: chunk ngoài nguồn bị xóa TRƯỚC pool, reranker không cứu được."""
        monkeypatch.setenv("ENABLE_RERANKER", "1")
        monkeypatch.delenv("ROUTER_SOFT_FILTER", raising=False)
        fake = FakeCrossEncoder({"nội dung 11": 999.0})
        monkeypatch.setattr(reranker_module, "get_reranker", lambda **kw: fake)
        docs = [doc("nội dung 11", 11, source="khac.pdf")] + [
            doc(f"nội dung {i}", i, source="a.pdf") for i in range(1, 11)
        ]
        pipeline, _, _ = make_pipeline(docs)
        config = RetrievalConfig(top_k=6, bm25_weight=0.5, chroma_weight=0.5, source_filter=["a.pdf"])
        out = pipeline.retrieve(QUERY, k=6, config=config)
        assert 11 not in ids(out)
        assert "nội dung 11" not in [passage for _q, passage in fake.pairs]

    def test_manifest_ghi_n_candidates_bang_toan_bo_sau_bonus(self, monkeypatch):
        pipeline, _, _fake, docs, config = self._soft_pipeline(monkeypatch)
        pipeline.retrieve(QUERY, k=6, config=config)
        assert pipeline.last_rerank_call["n_candidates"] == len(docs) == 12
        assert pipeline.last_rerank_call["n_scored"] == 12

    def test_bonus_12_giu_nguyen_thu_tu_va_tap_ung_vien_truoc_rerank(self, monkeypatch):
        """Mục 6: mức bonus đang chạy (12) không bị reranker làm mất ứng viên nào."""
        pipeline, _, fake, docs, config = self._soft_pipeline(monkeypatch, bonus=12)
        pipeline.retrieve(QUERY, k=6, config=config)
        expected = rescore_with_source_preference(docs, ["a.pdf"], rank_bonus=12)
        scored = [passage for _q, passage in fake.pairs]
        assert scored == [d.page_content for d in expected], "thứ tự vào reranker = thứ tự sau bonus"
        assert set(scored) == {d.page_content for d in docs}, "không ứng viên nào bị bonus/rerank nuốt"
