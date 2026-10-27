# -*- coding: utf-8 -*-
"""Unit test bộ chọn subset của vòng lặp (`tools/loop/run_round.py`).

Pha sinh văn bản đắt (~15s/item, GPU chia sẻ) nên mỗi round chỉ chạy một subset.
Subset phải (1) cân bằng theo family — nếu không CLOZE_OCR 206 item sẽ nuốt hết
ngân sách và các familyRefusal/TRAP không bao giờ được đo; (2) ưu tiên item đã
truy xuất trúng; (3) luôn giữ item không có chunk vàng (REFUSE_*), vì đáp án
đúng của chúng là FROM CHỐI chứ không phải truy xuất.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.loop.run_round import (
    compact_rows,
    gold_in_context_flags,
    load_done,
    pin_subset,
    plan_subset,
    select_for_generation,
)


def item(i: int, family: str, split: str = "test", **over) -> dict:
    base = {"id": f"{family}-{i:03d}", "family": family, "split": split, "raw_query": f"câu hỏi {i}"}
    base.update(over)
    return base


BANK = (
    [item(i, "CLOZE_OCR", gold_chunk_id=i) for i in range(200)]
    + [item(i, "NUMERIC", gold_chunk_id=i) for i in range(100)]
    + [item(i, "TRAP", gold_chunk_id=i) for i in range(20)]
    + [item(i, "REFUSE_OOD", gold_chunk_id=None) for i in range(8)]
)


class TestSelectForGeneration:
    def test_all_không_cắt(self):
        assert len(select_for_generation(BANK, {}, "all", 0)) == 328

    def test_limit_cân_bằng_theo_family(self):
        picked = select_for_generation(BANK, {}, "stratified", 40)
        families = {p["family"] for p in picked}
        assert families == {"CLOZE_OCR", "NUMERIC", "TRAP", "REFUSE_OOD"}
        big = sum(1 for p in picked if p["family"] == "CLOZE_OCR")
        assert big <= 12, "family lớn nhất không được vượt quá xấp xỉ 1/4 subset"

    def test_ưu_tiên_item_đã_truy_xuất_trúng(self):
        retrieved = {p["id"]: (i % 5 == 0) for i, p in enumerate(BANK[:100])}
        picked = select_for_generation(BANK[:100], retrieved, "stratified", 10)
        assert all(p["id"] in retrieved and retrieved[p["id"]] for p in picked)

    def test_only_retrieved_loại_trượt_nhưng_giữ_câu_từ_chối(self):
        retrieved = {**{f"NUMERIC-{i:03d}": i == 0 for i in range(100)},
                     **{f"CLOZE_OCR-{i:03d}": i == 0 for i in range(200)},
                     **{f"TRAP-{i:03d}": False for i in range(20)}}
        picked = select_for_generation(BANK, retrieved, "stratified", 40, only_retrieved=True)
        ids = {p["id"] for p in picked}
        # Mọi item bị đánh dấu trượt thật sự phải biến mất.
        assert not (ids & {k for k, v in retrieved.items() if not v})
        # Item CHƯA biết (REFUSE_OOD không có chunk vàng, không nằm trong flags) vẫn được giữ.
        assert sum(1 for p in picked if p["family"] == "REFUSE_OOD") == 8
        assert {"NUMERIC-000", "CLOZE_OCR-000"} <= ids
        assert len(picked) == 10  # 8 REFUSE + 2 item truy xuất trúng

    def test_item_chưa_chạy_pha_retrieval_vẫn_có_thể_chọn(self):
        """Ngân hàng lớn hơn số dòng đã chấm: flags thiếu = chưa biết, không phải lỗi."""
        picked = select_for_generation(BANK, {}, "stratified", 20)
        assert len(picked) == 20


class TestGoldFlags:
    def test_đọc_từ_retrieval_jsonl(self, tmp_path: Path):
        rows = [
            {"id": "A", "item": {"id": "A", "family": "EXACT", "split": "test", "raw_query": "q",
                                 "gold_chunk_id": 1},
             "answer": None, "contexts": ["x"], "sources": [{"rank": 1, "chunk_id": 1, "source": "s"}]},
            {"id": "B", "item": {"id": "B", "family": "EXACT", "split": "test", "raw_query": "q",
                                 "gold_chunk_id": 2},
             "answer": None, "contexts": ["x"], "sources": [{"rank": 1, "chunk_id": 9, "source": "s"}]},
            # REFUSE item: không có chunk vàng -> luôn "đo được" ở pha sinh.
            {"id": "C", "item": {"id": "C", "family": "REFUSE_OOD", "split": "test", "raw_query": "q",
                                 "gold_chunk_id": None, "expected_answer_type": "refuse"},
             "answer": None, "contexts": ["x"], "sources": []},
        ]
        import json

        path = tmp_path / "retrieval.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        flags = gold_in_context_flags(path, top_k=6)
        assert flags == {"A": True, "B": False, "C": True}

    def test_thiếu_file_thì_trả_vế_rỗng(self, tmp_path: Path):
        assert gold_in_context_flags(tmp_path / "khong_co.jsonl", top_k=6) == {}


class TestResume:
    def test_load_done_bỏ_dòng_hỏng(self, tmp_path: Path):
        import json

        p = tmp_path / "full.jsonl"
        p.write_text(
            json.dumps({"id": "A"}) + "\n" + "{damaged\n" + json.dumps({"id": "B"}) + "\n",
            encoding="utf-8",
        )
        assert load_done(p) == {"A", "B"}


class TestTậpDoIdempotent:
    """Chạy lại một round đã xong phải chấm LẠI đúng tập cũ, không thêm item mới.

    Bản cũ đưa `todo` (phần chưa chạy) vào bộ chọn subset, nên mỗi lần chạy lại để
    áp dụng trọng tài mới lại THÊM `limit` item: r0/full phình 100 -> 178 -> 181
    dòng và round sau pin phải cả phần dôi đó.
    """

    def test_giống_nhệt_khi_toàn_bộ_đã_chạy(self):
        first = plan_subset(BANK, {}, phase="full", strategy="stratified", limit=40)
        again = plan_subset(BANK, {}, phase="full", strategy="stratified", limit=40)
        assert [i["id"] for i in first] == [i["id"] for i in again]

    def test_subset_không_đổi_theo_cờ_recall_của_round_khi_pin(self):
        pinned = {i["id"] for i in BANK if i["family"] == "TRAP"}
        got = plan_subset(
            BANK,
            {i["id"]: False for i in BANK},
            phase="full",
            strategy="stratified",
            limit=40,
            only_retrieved=True,
            pinned=pinned,
        )
        assert {i["id"] for i in got} == pinned, "đã pin thì tập đo là định nghĩa từ round gốc"

    def test_pha_retrieval_limit_cắt_ổn_định(self):
        got = plan_subset(BANK, {}, phase="retrieval", strategy="stratified", limit=10)
        assert [i["id"] for i in got] == [i["id"] for i in BANK[:10]]


class TestNénDòng:
    def test_giữ_một_dòng_mỗi_id_thuộc_tập_đo(self):
        rows = [
            {"id": "A", "answer": "cũ"},
            {"id": "B", "answer": "B"},
            {"id": "A", "answer": "mới"},
            {"id": "X", "answer": "ngoài tập đo"},
        ]
        kept, outside, dup = compact_rows(rows, {"A", "B"})
        assert [(r["id"], r["answer"]) for r in kept] == [("A", "mới"), ("B", "B")]
        assert outside == 1 and dup == 1

    def test_không_tập_đo_thì_chỉ_dedupe(self):
        kept, outside, dup = compact_rows([{"id": "A"}, {"id": "A"}, {"id": "B"}], set())
        assert [r["id"] for r in kept] == ["A", "B"] and outside == 0 and dup == 1

    def test_dòng_thiếu_id_bị_loại_khi_có_tập_đo(self):
        kept, outside, _dup = compact_rows([{"id": "A"}, {"answer": "không id"}], {"A"})
        assert [r["id"] for r in kept] == ["A"] and outside == 1


class TestPinSubset:
    def test_đọc_id_từ_round_khác(self, tmp_path: Path):
        import json

        (tmp_path / "r0").mkdir(parents=True)
        (tmp_path / "r0" / "full.jsonl").write_text(
            "\n".join(json.dumps({"id": i}) for i in ("A", "B", "C")), encoding="utf-8"
        )
        assert pin_subset(tmp_path, "r0", "full") == {"A", "B", "C"}

    def test_round_không_tồn_tại_thì_dừng_chứ_không_tự_do_subset_khác(self, tmp_path: Path):
        with pytest.raises(SystemExit, match="không pin được"):
            pin_subset(tmp_path, "khong_co", "full")

