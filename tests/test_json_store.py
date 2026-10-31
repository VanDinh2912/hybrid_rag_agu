"""REVIEW §13 — ghi JSON nguyên tử + khoá file (`src/core/json_store.py`).

Không chạm file thật của repo: mọi case dùng `tmp_path`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.json_store import (
    JsonStoreError,
    iter_records,
    now_iso,
    read_json,
    update_json,
    validate_benchmark_doc,
    validate_feedback_list,
    write_atomic,
)


def test_write_atomic_tao_file_va_khong_de_lai_file_tam(tmp_path):
    path = tmp_path / "data.json"

    write_atomic(path, {"a": 1})

    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".*.tmp")) == []


def test_read_json_thieu_file_tra_default(tmp_path):
    assert read_json(tmp_path / "missing.json", {"x": 1}) == {"x": 1}


def test_read_json_file_hong_thi_bao_loi_thay_vi_nuot(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{hỏng", encoding="utf-8")

    with pytest.raises(JsonStoreError):
        read_json(path, [])


def test_update_json_doc_sua_ghi_va_giu_ban_cu(tmp_path):
    path = tmp_path / "records.json"

    update_json(path, [], lambda data: [*data, {"n": 1}])
    update_json(path, [], lambda data: [*data, {"n": 2}])

    assert read_json(path, []) == [{"n": 1}, {"n": 2}]


def test_update_json_validate_hong_thi_khong_ghi_de(tmp_path):
    path = tmp_path / "bench.json"
    write_atomic(path, {"questions": [{"id": "Q01"}]}, validate=validate_benchmark_doc)

    with pytest.raises(JsonStoreError):
        update_json(path, {}, lambda _d: {"questions": [{"id": "Q01"}, {"id": "Q01"}]},
                    validate=validate_benchmark_doc)

    assert read_json(path, {}) == {"questions": [{"id": "Q01"}]}


def test_validate_feedback_chap_nhan_ban_ghi_cu_va_tu_choi_ban_hong():
    validate_feedback_list([{"raw_query": "q", "feedback": "wrong"}])  # bản ghi cũ
    validate_feedback_list([{"raw_query": "q", "feedback_type": "correct"}])

    with pytest.raises(JsonStoreError):
        validate_feedback_list([{"feedback": "wrong"}])
    with pytest.raises(JsonStoreError):
        validate_feedback_list("không phải danh sách")


def test_iter_records_bo_qua_phan_tu_khong_phai_dict(tmp_path):
    path = tmp_path / "pairs.json"
    write_atomic(path, {"pairs": [{"raw_query": "a"}, 3, {"raw_query": "b"}]})

    assert [r["raw_query"] for r in iter_records(path)] == ["a", "b"]


def test_now_iso_co_dang_thoi_gian_giay():
    value = now_iso()

    assert len(value) == 19 and value[4] == "-" and value[10] == "T"


def test_write_atomic_thu_muc_cha_bi_chan_bao_JsonStoreError(tmp_path):
    blocked = tmp_path / "khong_phai_thu_muc"
    blocked.write_text("x", encoding="utf-8")

    with pytest.raises(JsonStoreError):
        write_atomic(Path(blocked) / "con.json", {"a": 1})
