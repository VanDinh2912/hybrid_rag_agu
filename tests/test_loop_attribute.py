# -*- coding: utf-8 -*-
"""Unit test cho `tools/loop/attribute.py` — máy quy lỗi truy xuất theo tầng.

Tool này quyết định "sửa cái gì trước", nên sai ở đây là mất nguyên một round.
Test chốt đúng ba nhánh đã phân nhánh bằng số liệu r0 (254/434 FAIL_RETRIEVAL bị
router cắt, 189 trong đó do nhãn chủ đề sai).
"""

from __future__ import annotations

import json

import pytest

from tools.loop.attribute import (
    attribute_round,
    classify_failure,
    diff_rounds,
    source_blocks_gold,
)

GOLD_TEXT = "Mức thu bảo hiểm y tế là 546.480đ/12 tháng/SV."


def item(**over) -> dict:
    base = {
        "id": "T1",
        "family": "EXACT",
        "split": "test",
        "raw_query": "Bảo hiểm y tế bao nhiêu?",
        "source_document": "tb-bhyt.pdf",
        "gold_chunk_id": 7,
        "topic": "bảo hiểm y tế",
    }
    base.update(over)
    return base


def row(*, source_filter=None, predicted_topic=None, with_gold: bool = True, **over) -> dict:
    it = over.pop("item", None) or item(**over)
    return {
        "id": it["id"],
        "item": it,
        "answer": None,
        "contexts": [GOLD_TEXT] if with_gold else ["chunk khác"],
        "sources": [
            {
                "rank": 1,
                "chunk_id": 7 if with_gold else 99,
                "source": it["source_document"],
                "tier": "2",
                "chars": 40,
            }
        ],
        "labels": {"topic": predicted_topic, "question_type": "TRA_CUU"},
        "retrieval_config": {"top_k": 6, "source_filter": source_filter},
        "latency_seconds": 1.0,
    }


def verdict_for(r: dict) -> dict:
    from tools.loop.verify import score_item

    return score_item(r["item"], r, top_k=6)


class TestSourceBlocksGold:
    def test_không_có_filter_thì_không_chặn(self):
        assert source_blocks_gold(None, "tb-bhyt.pdf") is False
        assert source_blocks_gold([], "tb-bhyt.pdf") is False

    def test_không_có_gold_document_thì_không_chặn(self):
        assert source_blocks_gold(["khac.pdf"], None) is False

    def test_trùng_nguyên_văn_thì_không_chặn(self):
        assert source_blocks_gold(["tb-bhyt.pdf"], "tb-bhyt.pdf") is False

    def test_chặn_khi_filter_ở_nguồn_khác(self):
        assert source_blocks_gold(["1054-qd-dhag.pdf"], "tb-bhyt.pdf") is True

    def test_chấp_nhận_so_khớp_chứa_nhau_và_không_dấu(self):
        assert source_blocks_gold(["TB-BHYT"], "tb-bhyt.pdf") is False
        assert source_blocks_gold(["qui dinh hoc phi 2026-2027.pdf"], "Qui dinh hoc phi 2026-2027.pdf") is False


class TestClassifyFailure:
    def test_câu_đạt_thì_không_phải_lỗi_truy_xuất(self):
        r = row(with_gold=True)
        assert classify_failure(r, verdict_for(r)) == "not_retrieval_failure"

    def test_thiếu_chunk_vàng_không_filter_lỗi_xếp_hạng(self):
        r = row(with_gold=False)
        assert classify_failure(r, verdict_for(r)) == "ranking_no_filter"

    def test_bị_chặn_vì_nhãn_chủ_đề_sai(self):
        r = row(with_gold=False, source_filter=["1054-qd-dhag.pdf"], predicted_topic="quy chế công tác sinh viên")
        assert classify_failure(r, verdict_for(r)) == "filter_blocked_wrong_topic"

    def test_bị_chặn_dù_nhãn_đúng_bảng_allowlist_hẹp(self):
        r = row(with_gold=False, source_filter=["1054-qd-dhag.pdf"], predicted_topic="bảo hiểm y tế")
        assert classify_failure(r, verdict_for(r)) == "filter_blocked_wrong_table"

    def test_filter_đúng_nguồn_mà_vẫn_mất_chunk_vàng_thì_lỗi_xếp_hạng_trong_cửa_sổ_loc(self):
        r = row(with_gold=False, source_filter=["tb-bhyt.pdf"], predicted_topic="học phí")
        assert classify_failure(r, verdict_for(r)) == "ranking_despite_filter"

    def test_thiếu_nhãn_dự_đoán_thì_không_kêu_lỗi_bảng_hẹp(self):
        r = row(with_gold=False, source_filter=["1054-qd-dhag.pdf"], predicted_topic=None)
        assert classify_failure(r, verdict_for(r)) == "filter_blocked_wrong_topic"


def write_round(tmp_path, rows, phase="retrieval"):
    d = tmp_path / "rX"
    d.mkdir(parents=True, exist_ok=True)
    d.joinpath(f"{phase}.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    return d


class TestAttributeRound:
    ROWS = [
        row(with_gold=False, source_filter=["1054.pdf"], predicted_topic="quy chế công tác sinh viên"),
        row(
            item=item(id="T2", topic="bảo hiểm y tế"),
            with_gold=False,
            source_filter=["1054.pdf"],
            predicted_topic="bảo hiểm y tế",
        ),
        row(item=item(id="T3", topic="học phí"), with_gold=False, source_filter=None, predicted_topic="học phí"),
        row(item=item(id="T4", topic="học phí"), with_gold=True, source_filter=None, predicted_topic="học phí"),
    ]

    def test_đếm_đủ_ba_nhóm(self, tmp_path):
        report = attribute_round(write_round(tmp_path, self.ROWS))
        assert report["n_items"] == 4
        assert report["fail_retrieval"] == 3
        assert report["groups"] == {
            "filter_blocked_wrong_topic": 1,
            "filter_blocked_wrong_table": 1,
            "ranking_no_filter": 1,
        }

    def test_tỉ_lệ_bị_filter_cắt(self, tmp_path):
        report = attribute_round(write_round(tmp_path, self.ROWS))
        assert report["share_blocked_by_filter"] == pytest.approx(0.6667, abs=1e-3)

    def test_liệt_kê_document_bị_chặn_và_nhầm_chủ_đề(self, tmp_path):
        report = attribute_round(write_round(tmp_path, self.ROWS))
        assert report["top_blocked_documents"][0][0] == "tb-bhyt.pdf"
        assert report["top_blocked_documents"][0][1] == 2
        assert report["topic_confusion_causing_blocks"] == [
            {"expected": "bảo hiểm y tế", "predicted": "quy chế công tác sinh viên", "n": 1}
        ]

    def test_theo_family(self, tmp_path):
        report = attribute_round(write_round(tmp_path, self.ROWS))
        assert report["by_family"]["EXACT"]["filter_blocked_wrong_topic"] == 1

    def test_round_chưa_chạy_thì_dừng_early(self, tmp_path):
        with pytest.raises(SystemExit):
            attribute_round(tmp_path / "khong_ton_tai")


class TestDiffRounds:
    def test_delta_cho_biết_lever_đúng_chỗ(self):
        base = {"groups": {"filter_blocked_wrong_topic": 189, "ranking_no_filter": 180}}
        cand = {"groups": {"filter_blocked_wrong_topic": 12, "ranking_no_filter": 95}}
        diff = diff_rounds(base, cand)
        assert diff["filter_blocked_wrong_topic"]["delta"] == -177
        assert diff["ranking_no_filter"]["delta"] == -85

    def test_nhóm_mà_baseline_không_có_vẫn_xuất_hiện(self):
        diff = diff_rounds({"groups": {}}, {"groups": {"new_group": 3}})
        assert diff["new_group"] == {"baseline": 0, "candidate": 3, "delta": 3}
