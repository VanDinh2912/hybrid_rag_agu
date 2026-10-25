# -*- coding: utf-8 -*-
"""T6 mục 8–10 — benchmark câu hỏi thật, CI tỉ lệ và điểm có trọng số.

Mục 8: schema `real_questions.jsonl` (bắt buộc id/câu hỏi/cột người chấm), loại trùng
id/nội dung, gắn cờ câu trùng testset_v1.
Mục 9: Wilson + bootstrap đúng ví dụ tính tay, không vượt [0, 1].
Mục 10: điểm có trọng số ra 7,1 với bộ điểm CŨ; tổng trọng số phải bằng 1,0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.eval.report_metrics import (
    bootstrap_rate_ci,
    rate_with_ci,
    weighted_score,
    wilson_ci,
)
from tools.eval.score_real_questions import (
    load_testset_questions,
    read_jsonl,
    validate_questions,
)

ROOT = Path(__file__).resolve().parents[1]
REAL_QUESTIONS = ROOT / "tools" / "eval" / "real_questions.jsonl"


def q(**over) -> dict:
    row = {
        "id": "RQ-0001",
        "question": "Học phí đóng muộn có bị phạt không?",
        "co_giup_duoc_khong": "",
        "ghi_chu": "",
    }
    row.update(over)
    return row


class TestRealQuestionsSchema:
    def test_muc8_thieu_id_hoac_cau_hoi_hoac_cot_nguoi_cham_bi_loai(self):
        accepted, report = validate_questions(
            [
                q(id=""),
                q(id="RQ-2", question="   "),
                {k: v for k, v in q(id="RQ-3").items() if k != "co_giup_duoc_khong"},
                q(id="RQ-4"),
            ]
        )
        assert [r["id"] for r in accepted] == ["RQ-4"]
        assert report["n_dropped"] == 3
        reasons = " | ".join(d["reason"] for d in report["dropped"])
        assert "id(trống)" in reasons
        assert "question(trống)" in reasons
        assert "co_giup_duoc_khong" in reasons

    def test_muc8_trung_id_va_trung_noi_dung_bi_loai(self):
        accepted, report = validate_questions(
            [
                q(id="RQ-1", question="Câu hỏi A"),
                q(id="RQ-1", question="Câu hỏi B"),
                q(id="RQ-2", question="  Câu   hỏi   a "),  # trùng A sau chuẩn hóa
                q(id="RQ-3", question="Câu hỏi C"),
            ]
        )
        assert [r["id"] for r in accepted] == ["RQ-1", "RQ-3"]
        assert report["n_dropped"] == 2
        assert {d["reason"] for d in report["dropped"]} == {"trùng_id", "trùng_nội_dung_với:RQ-1"}

    def test_muc8_cau_trung_testset_v1_bi_gan_co_nhung_khong_bi_xoa(self):
        accepted, report = validate_questions(
            [
                q(id="RQ-1", question="Lập kế hoạch được quy định là bao nhiêu?"),
                q(id="RQ-2", question="Một câu hoàn toàn khác?"),
            ],
            testset_questions=["Lập kế hoạch được quy định là bao nhiêu?"],
        )
        assert len(accepted) == 2
        assert accepted[0]["leak_testset_v1"] is True
        assert accepted[1]["leak_testset_v1"] is False
        assert report["flagged_leak_testset_v1"] == ["RQ-1"]

    def test_muc8_cau_hop_le_giu_nguyen_cot_nguoi_cham(self):
        accepted, report = validate_questions([q(id="RQ-9", co_giup_duoc_khong="co")])
        assert report["n_dropped"] == 0
        assert accepted[0]["co_giup_duoc_khong"] == "co"
        assert accepted[0]["leak_testset_v1"] is False

    def test_muc8_file_that_co_dong_schema_va_khong_co_cau_nao_thieu_cot(self):
        first = json.loads(REAL_QUESTIONS.read_text(encoding="utf-8").splitlines()[0])
        assert first.get("_schema") == "real_questions"
        assert "co_giup_duoc_khong" in first.get("_cot_can_dien_tay", {})
        accepted, report = validate_questions(
            read_jsonl(REAL_QUESTIONS), load_testset_questions()
        )
        assert report["n_in"] == report["n_accepted"] + report["n_dropped"]
        for row in accepted:
            assert row["id"] and row["question"]
            assert "co_giup_duoc_khong" in row


class TestIntervalEstimation:
    @pytest.mark.parametrize(
        "k, n, expected",
        [
            (7, 10, [0.3968, 0.8922]),
            (0, 10, [0.0, 0.2775]),
            (10, 10, [0.7225, 1.0]),
            (3, 10, [0.1078, 0.6032]),
        ],
    )
    def test_muc9_wilson_dung_vi_du_tinh_tay(self, k, n, expected):
        got = wilson_ci(k, n)
        assert got == pytest.approx(expected, abs=1e-4)

    def test_muc9_ci_khong_bao_gio_vuot_0_1(self):
        for k in range(0, 11):
            low, high = wilson_ci(k, 10)
            assert 0.0 <= low <= high <= 1.0
            low_b, high_b = bootstrap_rate_ci(k, 10, seed=20261024, reps=2000)
            assert 0.0 <= low_b <= high_b <= 1.0

    def test_muc9_bootstrap_suy_bien_dung_o_0_10_va_10_10(self):
        assert bootstrap_rate_ci(0, 10, seed=1, reps=2000) == [0.0, 0.0]
        assert bootstrap_rate_ci(10, 10, seed=1, reps=2000) == [1.0, 1.0]

    def test_muc9_bootstrap_7_10_chua_diem_uoc_luong(self):
        low, high = bootstrap_rate_ci(7, 10, seed=20261024, reps=5000)
        assert low <= 0.7 <= high
        assert (low, high) != (0.0, 1.0)  # không phải CI vô dụng

    def test_muc9_rate_with_ci_goi_du_hai_loai(self):
        out = rate_with_ci(7, 10)
        assert out["rate"] == 0.7
        assert out["wilson95"] == pytest.approx([0.3968, 0.8922], abs=1e-4)
        assert out["bootstrap95"][0] <= 0.7 <= out["bootstrap95"][1]

    @pytest.mark.parametrize("k, n", [(-1, 10), (11, 10), (1, 0), (1.5, 10)])
    def test_muc9_dau_vao_khong_hop_le_bao_loi(self, k, n):
        with pytest.raises(ValueError):
            wilson_ci(k, n)


WEIGHTS = {
    "phuong_phap": 0.20,
    "he_thong": 0.15,
    "thuc_nghiem": 0.20,
    "an_toan": 0.20,
    "huu_dung": 0.25,
}
OLD_SCORES = {
    "phuong_phap": 9.0,
    "he_thong": 8.0,
    "thuc_nghiem": 7.0,
    "an_toan": 8.5,
    "huu_dung": 4.0,
}
CURRENT_SCORES = dict(OLD_SCORES, phuong_phap=9.2, he_thong=8.2)


class TestWeightedScore:
    def test_muc10_bo_diem_cu_ra_dung_71(self):
        assert weighted_score(OLD_SCORES, WEIGHTS) == pytest.approx(7.10, abs=1e-9)

    def test_muc10_bo_diem_hien_tai_ra_717_khong_phai_71(self):
        # Đính chính: 7,1 chỉ đúng với bộ điểm CŨ; bộ đang dùng trong báo cáo ra 7,17.
        assert weighted_score(CURRENT_SCORES, WEIGHTS) == pytest.approx(7.17, abs=1e-9)

    def test_muc10_tong_trong_so_khac_1_bi_tu_choi(self):
        bad = dict(WEIGHTS, huu_dung=0.26)  # tổng 1,01
        with pytest.raises(ValueError) as exc:
            weighted_score(OLD_SCORES, bad)
        assert "tổng trọng số" in str(exc.value)

    def test_muc10_thieu_khoa_hoac_lech_do_dai_bi_tu_choi(self):
        # thiếu một khoá ở scores (weights vẫn đủ) => không được đoán 0 điểm cho chiều thiếu.
        with pytest.raises(ValueError):
            weighted_score({k: v for k, v in OLD_SCORES.items() if k != "an_toan"}, WEIGHTS)
        # thiếu một khoá ở weights => cùng lỗi.
        with pytest.raises(ValueError):
            weighted_score(OLD_SCORES, {k: v for k, v in WEIGHTS.items() if k != "an_toan"})
        # list lệch độ dài.
        with pytest.raises(ValueError):
            weighted_score(list(OLD_SCORES.values()), [0.2, 0.15])
        # dict vs list trộn kiểu.
        with pytest.raises(ValueError):
            weighted_score(OLD_SCORES, list(WEIGHTS.values()))

    def test_muc10_nhan_duoc_list_khi_tong_dung(self):
        assert weighted_score([9.0, 8.0, 7.0, 8.5, 4.0], [0.20, 0.15, 0.20, 0.20, 0.25]) == pytest.approx(7.10)
