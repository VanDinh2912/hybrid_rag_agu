"""Hàng đợi duyệt phản hồi (hardening 01-11): bản ghi tự chứa, một tệp một phản hồi.

Mục đích: Tab 3 mặc định KHÔNG sửa `benchmark_questions.json`, `normalization_pairs.json`
hay corpus. Phản hồi nằm chờ trong `logs/feedback/queue/` cho tới khi người vận hành chạy
`tools/diag/feedback_promote.py`. Các test dưới đây ghim đúng hợp đồng đó ở tầng controller,
không cần Tkinter.
"""

from __future__ import annotations

import json

import pytest

import ui.feedback_controller as fc


def _test_data(raw_query="học phí ngành CNTT bao nhiêu?"):
    return {
        "raw_query": raw_query,
        "normalized_query": "Học phí ngành CNTT là bao nhiêu?",
        "answer": "câu trả lời cũ",
        "sources": [{"rank": 1, "source": "1054.pdf", "tier": "high", "chunk_id": "abc"}],
    }


def _record(test_data=None, **overrides):
    kwargs = dict(
        citation="Điều 12",
        source_doc="1054.pdf",
        normalized_truth="Học phí ngành CNTT là bao nhiêu?",
        requested={"benchmark": True, "normalization_pair": True, "corpus_note": False},
    )
    kwargs.update(overrides)
    return fc.queue_record(test_data or _test_data(), "wrong", "Đáp án chuẩn: 15 triệu", **kwargs)


def test_ban_ghi_hang_doi_tu_chua_va_giu_lien_ket_feedback():
    record = _record()

    assert record["queue_schema_version"] == fc.QUEUE_SCHEMA_VERSION
    assert record["queued_at"] == record["created_at"]
    assert record["raw_query"] == "học phí ngành CNTT bao nhiêu?"
    assert record["feedback_type"] == "wrong"
    assert record["source"] == "gui"
    assert record["citation"] == "Điều 12"
    assert record["source_doc"] == "1054.pdf"
    assert record["normalized_truth"] == "Học phí ngành CNTT là bao nhiêu?"
    assert record["requested"] == {
        "benchmark": True,
        "normalization_pair": True,
        "corpus_note": False,
    }
    # Bản ghi hàng đợi vẫn là bản ghi feedback hợp lệ (đọc được bởi công cụ cũ).
    fc.validate_queue_record(record)


def test_requested_bo_qua_khoa_ngoai_ba_muc():
    with pytest.raises(fc.QueueError):
        _record(requested={"benchmark": True, "xoa_index": True})


@pytest.mark.parametrize(
    "record, manh_loi",
    [
        ({**_record(), "queue_schema_version": 99}, "queue_schema_version"),
        ({**_record(), "raw_query": "   "}, "raw_query"),
        ({**_record(), "requested": None}, "requested"),
        ({**_record(), "requested": {"benchmark": "1"}}, "bool"),
        ({**_record(), "requested": {"benchmark": True, "khac": False}}, "khoá lạ"),
        ("không phải object", "object"),
    ],
)
def test_validate_tu_choi_ban_ghi_hong(record, manh_loi):
    with pytest.raises(fc.QueueError) as excinfo:
        fc.validate_queue_record(record)
    assert manh_loi in str(excinfo.value)


def test_xep_hang_tao_mot_tep_va_giu_nguyen_ban_ghi(tmp_path):
    queue_dir = tmp_path / "queue"
    record = _record(requested={"benchmark": True})

    path = fc.enqueue_feedback(queue_dir, record)

    assert path.parent == queue_dir
    assert path.suffix == ".json"
    assert json.loads(path.read_text(encoding="utf-8")) == record


def test_xep_hang_khong_bao_gio_de_tep_da_co(tmp_path, monkeypatch):
    """`O_EXCL`: tệp trùng tên phải sinh tệp mới, không ghi đè nội dung đã có."""
    queue_dir = tmp_path / "queue"
    record = _record()
    # Ép trùng tên: ghim `_queue_stem` (mặc định có microsecond nên hai lượt gọi khác tên).
    monkeypatch.setattr(fc, "_queue_stem", lambda _record: "co-dinh")
    first = fc.enqueue_feedback(queue_dir, record)
    original = first.read_text(encoding="utf-8")
    second = fc.enqueue_feedback(queue_dir, record)

    assert second != first
    assert first.read_text(encoding="utf-8") == original
    assert len(list(queue_dir.glob("*.json"))) == 2


def test_xep_hang_hong_thu_muc_thi_nem_queue_error(tmp_path):
    blocked = tmp_path / "khong_phai_thu_muc"
    blocked.write_text("x", encoding="utf-8")

    with pytest.raises(fc.QueueError):
        fc.enqueue_feedback(blocked / "queue", _record())


def test_iter_queue_bao_tep_hong_thay_vi_bo_qua(tmp_path):
    queue_dir = tmp_path / "queue"
    good_a = fc.enqueue_feedback(queue_dir, _record())
    good_b = fc.enqueue_feedback(queue_dir, _record(_test_data("câu hỏi khác")))
    broken = queue_dir / "zzz-hong.json"
    broken.write_text("{ không phải json", encoding="utf-8")

    items = list(fc.iter_queue(queue_dir))

    assert [path for path, _record_, _err in items] == sorted([good_a, good_b, broken])
    errors = {path.name: err for path, record, err in items if record is None}
    assert set(errors) == {broken.name}
    assert errors[broken.name]


def test_iter_queue_thu_muc_chua_co_thi_rong(tmp_path):
    assert list(fc.iter_queue(tmp_path / "chua_co")) == []
