"""REVIEW §7/§8/§13 — các module tách khỏi `ui/app.py` giữ đúng hành vi.

Không dựng cửa sổ Tkinter: controller/state/log bridge đều là hàm thuần hoặc nhận
đối tượng giả; phần "worker không đụng stdout" kiểm bằng đọc mã nguồn.
"""

from __future__ import annotations

import json
import logging
import queue
from pathlib import Path

import pytest

import ui.app as ui_app
import ui.backend_controller as backend_controller
import ui.ingest_controller as ingest_controller
import ui.search_controller as search_controller
from ui import feedback_controller
from ui.log_bridge import attach_queue_logger, drain
from ui.ui_state import AppState, format_labels_display

APP_PATH = Path(ui_app.__file__)


# ---------------------------------------------------------------------------
# ui_state
# ---------------------------------------------------------------------------
def test_format_labels_display_giu_nguyen_dinh_dang():
    text = format_labels_display(
        {"topic": "học phí", "question_type": "tra cứu"},
        {"top_k": 6, "bm25_weight": 0.5, "chroma_weight": 0.5, "source_filter": ["1054.pdf"]},
    )

    assert "chủ đề: học phí" in text
    assert "top_k=6" in text
    assert "lọc nguồn: 1054.pdf" in text
    assert format_labels_display(None, None) == "—"


def test_app_state_busy_chi_khi_co_viec_dang_chay():
    state = AppState()

    assert state.busy() is False
    state.is_testing = True
    assert state.busy() is True


# ---------------------------------------------------------------------------
# feedback_controller
# ---------------------------------------------------------------------------
_TEST_DATA = {
    "raw_query": "học phí ngành CNTT?",
    "normalized_query": "Học phí ngành CNTT là bao nhiêu?",
    "answer": "câu trả lời",
    "sources": [{"rank": 1, "source": "1054.pdf", "tier": "van_ban", "chunk_id": "c1", "preview": "..."}],
}


def test_feedback_record_du_truong_moi_va_giu_truong_cu():
    record = feedback_controller.feedback_record(_TEST_DATA, "wrong", "đáp án đúng")

    assert record["schema_version"] == feedback_controller.FEEDBACK_SCHEMA_VERSION
    assert record["feedback_type"] == "wrong" and record["feedback"] == "wrong"
    assert record["created_at"] == record["timestamp"]
    assert record["answer"] == record["system_answer"] == "câu trả lời"
    assert record["sources"][0]["chunk_id"] == "c1"


def test_append_feedback_ghi_noi_tiep(tmp_path):
    path = tmp_path / "feedback.json"

    feedback_controller.append_feedback(path, feedback_controller.feedback_record(_TEST_DATA, "correct", None))
    feedback_controller.append_feedback(path, feedback_controller.feedback_record(_TEST_DATA, "wrong", "x"))

    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    assert [r["feedback_type"] for r in data] == ["correct", "wrong"]


def test_save_benchmark_danh_so_khong_trung_id_da_dung(tmp_path):
    path = tmp_path / "benchmark.json"
    path.write_text(
        '{"version": "2.0", "questions": [{"id": "Q01"}, {"id": "Q03"}]}',
        encoding="utf-8",
    )

    ok, error = feedback_controller.save_benchmark(path, _TEST_DATA, "đáp án", "Điều 1", "1054.pdf", "câu chuẩn")

    assert (ok, error) == (True, "")
    new_question = json.loads(path.read_text(encoding="utf-8"))["questions"][-1]
    assert new_question["id"] == "Q04"
    assert new_question["source"] == "gui_feedback"
    assert new_question["source_document"] == "1054.pdf"


def test_save_benchmark_hong_tra_false_kem_loi(tmp_path):
    blocked = tmp_path / "tep"
    blocked.write_text("x", encoding="utf-8")

    ok, error = feedback_controller.save_benchmark(blocked / "benchmark.json", _TEST_DATA, "a", "b", "c", "d")

    assert ok is False and error


def test_save_normalization_pair_upsert_khong_tao_trung(tmp_path):
    path = tmp_path / "pairs.json"

    assert feedback_controller.save_normalization_pair(path, "câu thô", "Câu chuẩn 1?") == (True, "")
    assert feedback_controller.save_normalization_pair(path, "câu thô", "Câu chuẩn 2?") == (True, "")

    import json
    pairs = json.loads(path.read_text(encoding="utf-8"))["pairs"]
    assert len(pairs) == 1
    assert pairs[0]["normalized_query"] == "Câu chuẩn 2?"
    assert "updated_at" in pairs[0]


def test_build_result_lines_bao_tung_phan_va_co_muc_hong():
    lines, failed = feedback_controller.build_result_lines(
        {"benchmark_saved": False, "normalization_pair_saved": True, "note_saved": None, "rebuild_succeeded": None},
        ["benchmark_questions.json: quyền ghi"],
    )

    assert failed is True
    joined = "\n".join(lines)
    assert "CHƯA cập nhật được benchmark" in joined
    assert "Đã lưu cặp chuẩn hóa" in joined
    assert "quyền ghi" in joined

    lines_ok, failed_ok = feedback_controller.build_result_lines(
        {"benchmark_saved": True, "normalization_pair_saved": None, "note_saved": None, "rebuild_succeeded": None},
        [],
    )
    assert failed_ok is False and "Đã cập nhật benchmark" in "\n".join(lines_ok)


# ---------------------------------------------------------------------------
# search_controller / ingest_controller
# ---------------------------------------------------------------------------
class _FakePipeline:
    def __init__(self):
        self.replaced = []

    def run(self, query, top_k):
        return {"answer": f"{query}/{top_k}"}

    def replace_vector_db(self, db):
        self.replaced.append(db)


def test_execute_search_tra_ket_qua_va_thoi_gian():
    result, elapsed = search_controller.execute_search(_FakePipeline(), "hỏi", 4)

    assert result == {"answer": "hỏi/4"}
    assert elapsed >= 0


def test_execute_ingest_goi_log_callback_va_thay_retriever(monkeypatch):
    logged = []
    new_db = object()
    seen = {}

    def _fake_run(db_manager=None, reset=True, log=print, allow_reset=False):
        seen["allow_reset"] = allow_reset
        log("[1/4] dòng giả")
        return "manager-moi", new_db, 7

    monkeypatch.setattr(ingest_controller, "run_ingestion", _fake_run)
    pipeline = _FakePipeline()

    outcome = ingest_controller.execute_ingest(pipeline, db_manager=None, reuse_model=False, log=logged.append)

    assert logged == ["[1/4] dòng giả"]
    assert outcome.total == 7 and outcome.vector_db is new_db
    assert pipeline.replaced == [new_db]
    # PA-16: GUI đã hỏi xác nhận trước khi gọi ⇒ cổng env không được chặn oan đường GUI.
    assert seen["allow_reset"] is True


def test_execute_ingest_retriever_hong_van_giu_outcome(monkeypatch):
    class _BrokenPipeline(_FakePipeline):
        def replace_vector_db(self, _db):
            raise RuntimeError("BM25 lỗi")

    monkeypatch.setattr(
        ingest_controller, "run_ingestion",
        lambda **_kwargs: ("manager-moi", object(), 3),
    )

    with pytest.raises(ingest_controller.IngestRetrieverError) as excinfo:
        ingest_controller.execute_ingest(_BrokenPipeline(), object(), True, lambda _l: None)

    assert excinfo.value.outcome.total == 3
    assert "BM25 lỗi" in str(excinfo.value.cause)


# ---------------------------------------------------------------------------
# log_bridge + ràng buộc §8 trên ui/app.py
# ---------------------------------------------------------------------------
def test_log_bridge_day_log_vao_queue_va_doc_ra():
    sink, handler = attach_queue_logger("rag.gui.test")
    logger = logging.getLogger("rag.gui.test")
    try:
        logger.info("dòng một")
        logger.info("dòng hai")
        assert drain(sink) == ["dòng một\n", "dòng hai\n"]
        assert drain(sink) == []
    finally:
        logger.removeHandler(handler)
        logger.propagate = True


def test_drain_tôn_trong_gioi_han():
    sink: "queue.Queue[str]" = queue.Queue()
    for i in range(5):
        sink.put(str(i))

    assert drain(sink, limit=2) == ["0", "1"]
    assert sink.qsize() == 3


def test_ui_app_khong_con_doi_sys_stdout_toan_cuc():
    source = APP_PATH.read_text(encoding="utf-8")

    assert "sys.stdout =" not in source
    assert "StdoutRedirector" not in source
    # Log ingest phải đi qua queue + drain của log_bridge.
    assert "drain(self._ingest_sink)" in source
    assert "execute_ingest" in source


def test_ui_app_giu_bieu_tuong_cong_khai_ma_test_cu_va_entry_point_dung():
    for name in ("RAGApplication", "format_labels_display", "use_qwen_generator", "build_generator",
                 "FEEDBACK_PATH", "BENCHMARK_PATH", "NORMALIZATION_PAIRS_PATH",
                 "run_ingestion", "append_note", "log_learning", "messagebox"):
        assert hasattr(ui_app, name), name


# ---------------------------------------------------------------------------
# backend_controller — module tách cuối cùng từng không có test nào (rà 01-11)
# ---------------------------------------------------------------------------
class _FakeVectorDB:
    class _Collection:
        def count(self):
            return 42

    _collection = _Collection()


def test_build_backend_tra_bundle_va_bao_tien_trinh(monkeypatch):
    logs = []
    nhan = {}

    class FakeDBManager:
        def load_vector_store(self):
            return _FakeVectorDB()

    class FakeSLM:
        def check_connection(self):
            return True, "ollama ok"

    class FakePipeline:
        def __init__(self, vector_db, local_slm, generator):
            nhan["pipeline"] = {"vector_db": vector_db, "local_slm": local_slm,
                                "generator": generator}

    class FakeGen:
        def __init__(self, use_qwen):
            nhan["use_qwen"] = use_qwen

    monkeypatch.setattr(backend_controller, "VectorStoreManager", FakeDBManager)
    monkeypatch.setattr(backend_controller, "LocalSLM", FakeSLM)
    monkeypatch.setattr(backend_controller, "HybridRAGPipeline", FakePipeline)

    bundle = backend_controller.build_backend(
        logs.append, use_qwen=True, generator_factory=FakeGen)

    assert isinstance(bundle.db_manager, FakeDBManager)
    assert bundle.vector_db is nhan["pipeline"]["vector_db"]
    assert bundle.slm_ok is True
    assert bundle.chunk_count == 42, "đếm chunk lấy từ collection thật, không hard-code"
    assert nhan["use_qwen"] is True, "cờ use_qwen phải đi vào generator factory"
    assert nhan["pipeline"] == {"vector_db": bundle.vector_db,
                                "local_slm": bundle.local_slm,
                                "generator": bundle.generator}
    assert logs == ["Đang kết nối ChromaDB...",
                    "Kiểm tra Local SLM (Ollama)...",
                    "Kết nối Local Qwen (chế độ OFFLINE)..."]


def test_build_backend_mac_dinh_chon_generator_theo_co(monkeypatch):
    da_chon = []

    class FakeDBManager:
        def load_vector_store(self):
            return _FakeVectorDB()

    class FakeSLM:
        def check_connection(self):
            return False, "không có ollama"

    class FakePipeline:
        def __init__(self, **_kw):
            pass

    class FakeQwen:
        def __init__(self, use_qwen):
            da_chon.append(("qwen", use_qwen))

    class FakeGemini:
        def __init__(self, use_qwen):
            da_chon.append(("gemini", use_qwen))

    monkeypatch.setattr(backend_controller, "VectorStoreManager", FakeDBManager)
    monkeypatch.setattr(backend_controller, "LocalSLM", FakeSLM)
    monkeypatch.setattr(backend_controller, "HybridRAGPipeline", FakePipeline)
    monkeypatch.setattr(backend_controller, "QwenGenerator", FakeQwen)
    monkeypatch.setattr(backend_controller, "GeminiGenerator", FakeGemini)

    bundle = backend_controller.build_backend(use_qwen=True)

    assert da_chon == [("qwen", True)]
    assert bundle.slm_ok is False, "SLM hỏng không được làm sập backend"

    backend_controller.build_backend()
    assert da_chon[-1] == ("gemini", False)


def test_build_backend_de_loi_that_len_caller(monkeypatch):
    """Docstring hứa "ném lỗi thật" — không được trả backend rỗng để GUI chạy tiếp."""
    class FakeDBManager:
        def load_vector_store(self):
            raise RuntimeError("không mở được chroma_db")

    monkeypatch.setattr(backend_controller, "VectorStoreManager", FakeDBManager)

    with pytest.raises(RuntimeError, match="không mở được chroma_db"):
        backend_controller.build_backend()
