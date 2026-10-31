"""REVIEW §2.2 — hộp thoại feedback chỉ báo đúng việc đã hoàn tất.

Không dựng cửa sổ Tkinter: các test dùng `RAGApplication.__new__` để bỏ qua `__init__`,
thay widget bằng đối tượng giả tối thiểu và chặn `messagebox` để đọc nội dung thông báo.
"""

from __future__ import annotations

import pytest

import ui.app as ui_app


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
    app = _guess_wrong_app(_FakePipeline(5), learn_now=True)
    app._save_feedback_record = lambda *_a, **_k: None

    monkeypatch.setattr(ui_app, "append_note", lambda _note: None)

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
    pipeline = _FakePipeline(5)
    app = _guess_wrong_app(pipeline, learn_now=True)
    app._save_feedback_record = lambda *_a, **_k: None
    monkeypatch.setattr(ui_app, "append_note", lambda _note: None)
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
