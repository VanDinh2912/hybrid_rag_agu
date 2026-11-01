"""REVIEW §2.2 — hộp thoại feedback chỉ báo đúng việc đã hoàn tất.

Không dựng cửa sổ Tkinter: các test dùng `RAGApplication.__new__` để bỏ qua `__init__`,
thay widget bằng đối tượng giả tối thiểu và chặn `messagebox` để đọc nội dung thông báo.

Hardening 01-11: mặc định (`LEARN_AUTO_APPLY=0`) Tab 3 chỉ xếp hàng chờ duyệt; nhánh
"áp ngay" cũ chỉ chạy khi cờ bật, nên các test hành vi cũ phải monkeypatch cờ = True.
"""

from __future__ import annotations

import json

import pytest

import ui.app as ui_app
import ui.feedback_controller as feedback_controller


def _app():
    return ui_app.RAGApplication.__new__(ui_app.RAGApplication)


class _FakeText:
    def __init__(self, value: str):
        self.value = value

    def get(self, *_args):
        return self.value


class _FakeEntry:
    def __init__(self, value: str = ""):
        self.value = value

    def get(self):
        return self.value


class _FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeFrame:
    def __init__(self):
        self.hidden = False

    def pack_forget(self):
        self.hidden = True


class _FakeCollection:
    def __init__(self, n: int):
        self.n = n

    def count(self) -> int:
        return self.n


class _FakeDB:
    def __init__(self, n: int):
        self._collection = _FakeCollection(n)


class _FakePipeline:
    def __init__(self, n_before: int):
        self.vector_db = _FakeDB(n_before)
        self.replaced = []

    def replace_vector_db(self, db):
        self.replaced.append(db)
        self.vector_db = db


def _guess_wrong_app(pipeline, learn_now=False):
    app = _app()
    app.current_test_data = {
        "raw_query": "học phí ngành CNTT bao nhiêu?",
        "normalized_query": "Học phí ngành CNTT là bao nhiêu?",
        "answer": "câu trả lời cũ",
        "sources": [],
    }
    app.txt_ground_truth = _FakeText("Đáp án đúng\n")
    app.entry_citation = _FakeEntry("")
    app.source_var = _FakeVar("")
    app.entry_normalized_truth = _FakeEntry("")
    app.learn_now_var = _FakeVar(learn_now)
    app.wrong_frame = _FakeFrame()
    app.status_var = _FakeVar("")
    app.pipeline = pipeline
    app.db_manager = object()
    return app


def _capture_messages(monkeypatch):
    captured = {}

    def _showinfo(title, message):
        captured.update(kind="info", title=title, message=message)

    def _showwarning(title, message):
        captured.update(kind="warning", title=title, message=message)

    def _showerror(title, message):
        captured.update(kind="error", title=title, message=message)

    monkeypatch.setattr(ui_app.messagebox, "showinfo", _showinfo)
    monkeypatch.setattr(ui_app.messagebox, "showwarning", _showwarning)
    monkeypatch.setattr(ui_app.messagebox, "showerror", _showerror)
    return captured


def test_feedback_ghi_hong_thi_dung_va_bao_loi(monkeypatch):
    """Bản ghi feedback hỏng ⇒ không chạy tiếp, không ẩn form, không báo thành công."""
    captured = _capture_messages(monkeypatch)
    app = _guess_wrong_app(_FakePipeline(5))

    def _no_ghi(*_args, **_kwargs):
        raise OSError("đĩa đầy")

    app._save_feedback_record = _no_ghi

    app.save_wrong_feedback()

    assert captured["kind"] == "error"
    assert "đĩa đầy" in captured["message"]
    assert app.wrong_frame.hidden is False


def test_rebuild_hong_thi_bao_da_luu_phan_hoi_nhung_chroma_chua_cap_nhat(monkeypatch):
    captured = _capture_messages(monkeypatch)
    monkeypatch.setattr(ui_app, "learn_auto_apply_enabled", lambda: True)
    app = _guess_wrong_app(_FakePipeline(5), learn_now=True)
    app._save_feedback_record = lambda *_a, **_k: None

    monkeypatch.setattr(ui_app, "append_note", lambda _q, _c: None)

    def _no_rebuild(**_kwargs):
        raise RuntimeError("Chroma bị khóa")

    monkeypatch.setattr(ui_app, "run_ingestion", _no_rebuild)

    app.save_wrong_feedback()

    assert captured["kind"] == "warning"
    message = captured["message"]
    assert "Đã lưu phản hồi" in message
    assert "Đã ghi bài học" in message
    assert "CHƯA được cập nhật" in message
    assert "Chroma bị khóa" in message
    assert app.pipeline.replaced == []


def test_rebuild_thanh_cong_thi_dung_api_va_bao_thanh_cong(monkeypatch):
    captured = _capture_messages(monkeypatch)
    monkeypatch.setattr(ui_app, "learn_auto_apply_enabled", lambda: True)
    pipeline = _FakePipeline(5)
    app = _guess_wrong_app(pipeline, learn_now=True)
    app._save_feedback_record = lambda *_a, **_k: None
    monkeypatch.setattr(ui_app, "append_note", lambda _q, _c: None)
    monkeypatch.setattr(ui_app, "log_learning", lambda *_a, **_k: None)

    new_db = _FakeDB(6)
    monkeypatch.setattr(ui_app, "run_ingestion", lambda **_kwargs: (object(), new_db, 6))

    app.save_wrong_feedback()

    assert pipeline.replaced == [new_db]  # GUI dùng replace_vector_db, không gán nội bộ
    assert captured["kind"] == "info"
    assert "làm mới bộ truy xuất thành công" in captured["message"]


def test_bao_cao_tung_phan_chi_lieu_that_su_that_bai(monkeypatch):
    """Chỉ cần một mục hỏng là hộp thoại cảnh báo, không phải "Thành công"."""
    captured = _capture_messages(monkeypatch)
    app = _app()
    status = {
        "benchmark_saved": False,
        "normalization_pair_saved": None,
        "note_saved": None,
        "rebuild_succeeded": None,
    }

    app._report_feedback_result(status, ["benchmark_questions.json: quyền ghi"])

    assert captured["kind"] == "warning"
    assert "CHƯA cập nhật được benchmark_questions.json" in captured["message"]
    assert "quyền ghi" in captured["message"]


def test_luu_benchmark_tra_loi_loi_thay_vi_nuot_exception(monkeypatch, tmp_path):
    app = _app()
    app.current_test_data = {"raw_query": "câu hỏi"}
    blocked = tmp_path / "khong_phai_thu_muc"
    blocked.write_text("x", encoding="utf-8")
    monkeypatch.setattr(ui_app, "BENCHMARK_PATH", blocked / "benchmark.json")

    ok, error = app._save_to_benchmark("đáp án", "Điều 1", "1054.pdf", "Câu hỏi?")

    assert ok is False
    assert error


def test_luu_cap_chuan_hoa_tra_loi_loi_thay_vi_nuot_exception(monkeypatch, tmp_path):
    app = _app()
    blocked = tmp_path / "khong_phai_thu_muc"
    blocked.write_text("x", encoding="utf-8")
    monkeypatch.setattr(ui_app, "NORMALIZATION_PAIRS_PATH", blocked / "pairs.json")

    ok, error = app._save_normalization_pair("câu thô", "Câu chuẩn?")

    assert ok is False
    assert error


def test_luu_benchmark_thanh_cong_tra_true(monkeypatch, tmp_path):
    app = _app()
    app.current_test_data = {"raw_query": "câu hỏi"}
    monkeypatch.setattr(ui_app, "BENCHMARK_PATH", tmp_path / "benchmark.json")

    ok, error = app._save_to_benchmark("đáp án", "Điều 1", "1054.pdf", "Câu hỏi?")

    assert (ok, error) == (True, "")
    assert '"Q01"' in (tmp_path / "benchmark.json").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------
# Hardening 01-11 — đường mặc định: chỉ ghi hàng đợi, không áp gì, không rebuild.
# ---------------------------------------------------------------------------------
def _queue_app(learn_now=True):
    """App giả có đủ 4 trường nhập để `requested` bật cả ba mục.

    Hai hàm ghi tệp thật (`_save_to_benchmark`, `_save_normalization_pair`) bị thay bằng
    điểm nổ ở cấp instance: nếu định tuyến mặc định hở, test đỏ NGAY chứ không kịp ghi
    `data/evaluation/benchmark_questions.json` hay `data/learning/` của repo.
    """
    app = _guess_wrong_app(_FakePipeline(5), learn_now=learn_now)
    app.entry_citation = _FakeEntry("Điều 12")
    app.source_var = _FakeVar("1054.pdf")
    app.entry_normalized_truth = _FakeEntry("Học phí CNTT là bao nhiêu?")
    app._save_feedback_record = lambda *_a, **_k: None

    def _boom(*_args, **_kwargs):
        raise AssertionError("nhánh mặc định KHÔNG được ghi benchmark/pairs của repo")

    app._save_to_benchmark = _boom
    app._save_normalization_pair = _boom
    return app


def _forbid(monkeypatch, name):
    """Biến `name` trong `ui_app` thành điểm nổ — chứng minh nhánh mặc định không chạm tới."""
    def _boom(*_args, **_kwargs):
        raise AssertionError(f"nhánh mặc định KHÔNG được gọi {name}")

    monkeypatch.setattr(ui_app, name, _boom)


def test_mac_dinh_chi_xep_hang_khong_ap_gi_va_khong_rebuild(monkeypatch, tmp_path):
    captured = _capture_messages(monkeypatch)
    queue_dir = tmp_path / "queue"
    monkeypatch.setattr(ui_app, "FEEDBACK_QUEUE_DIR", queue_dir)
    monkeypatch.setattr(ui_app, "learn_auto_apply_enabled", lambda: False)
    for name in ("append_note", "run_ingestion", "log_learning"):
        _forbid(monkeypatch, name)
    app = _queue_app()

    app.save_wrong_feedback()

    files = sorted(queue_dir.glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["raw_query"] == "học phí ngành CNTT bao nhiêu?"
    assert record["requested"] == {
        "benchmark": True,
        "normalization_pair": True,
        "corpus_note": True,
    }
    assert "Đáp án chuẩn" in record["correct_answer"]
    assert captured["kind"] == "info"
    assert "xếp hàng" in captured["message"].lower()
    assert "KHÔNG rebuild" in captured["message"]
    assert app.wrong_frame.hidden is True
    assert app.pipeline.replaced == []
    assert not (tmp_path / "benchmark.json").exists()


def test_mac_dinh_chi_xin_duyet_hang_muc_nguoi_dung_dien(monkeypatch, tmp_path):
    """Không nhập căn cứ/nguồn/câu chuẩn hóa ⇒ `requested` tắt đúng các mục đó."""
    captured = _capture_messages(monkeypatch)
    queue_dir = tmp_path / "queue"
    monkeypatch.setattr(ui_app, "FEEDBACK_QUEUE_DIR", queue_dir)
    monkeypatch.setattr(ui_app, "learn_auto_apply_enabled", lambda: False)
    app = _guess_wrong_app(_FakePipeline(5), learn_now=False)
    app._save_feedback_record = lambda *_a, **_k: None

    app.save_wrong_feedback()

    record = json.loads(next(queue_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["requested"] == {
        "benchmark": False,
        "normalization_pair": False,
        "corpus_note": False,
    }
    assert "không có mục nào" in captured["message"]


def test_mac_dinh_xep_hang_hong_thi_bao_loi_va_giu_form(monkeypatch, tmp_path):
    captured = _capture_messages(monkeypatch)
    monkeypatch.setattr(ui_app, "FEEDBACK_QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(ui_app, "learn_auto_apply_enabled", lambda: False)
    app = _queue_app()

    def _no_queue(*_args, **_kwargs):
        raise feedback_controller.QueueError("không tạo được thư mục hàng đợi")

    monkeypatch.setattr(ui_app.feedback_controller, "enqueue_feedback", _no_queue)

    app.save_wrong_feedback()

    assert captured["kind"] == "error"
    assert "CHƯA xếp được hàng đợi" in captured["message"]
    assert app.wrong_frame.hidden is False


def test_co_bat_thi_khong_xep_hang(monkeypatch, tmp_path):
    """`LEARN_AUTO_APPLY=1` giữ hành vi cũ ⇒ không sinh tệp hàng đợi nào."""
    _capture_messages(monkeypatch)
    queue_dir = tmp_path / "queue"
    monkeypatch.setattr(ui_app, "FEEDBACK_QUEUE_DIR", queue_dir)
    monkeypatch.setattr(ui_app, "learn_auto_apply_enabled", lambda: True)
    app = _guess_wrong_app(_FakePipeline(5), learn_now=False)
    app._save_feedback_record = lambda *_a, **_k: None

    app.save_wrong_feedback()

    assert not queue_dir.exists()
