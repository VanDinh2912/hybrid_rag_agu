# -*- coding: utf-8 -*-
"""T6 mục 7 — kiểm định TRỌNG TÀI bằng nhãn tay.

Ba bất biến:
1. Phiếu 60 dòng phân tầng (seed cố định) KHÔNG chứa verdict/tầng/trường vàng —
   người đọc không bị neo.
2. precision/recall tính đúng trên phiếu giả có đáp án biết trước (tính tay được).
3. nhãn thiếu (chế độ strict) hoặc sai định dạng => báo lỗi, KHÔNG im lặng bỏ dòng.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.diag.referee_agreement import (
    CLASSES,
    LabelError,
    score_labels,
    validate_labels,
)
from tools.diag.referee_sample import (
    STRATA,
    build_label_rows,
    build_manifest,
    default_targets,
    stratified_sample,
)

SEED = 20261024
ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "data" / "loop" / "diag"


def records(n_per_stratum: int = 30) -> list[dict]:
    """Bộ giả: mỗi tầng đủ dày để chọn 60 không cần bù chéo."""
    out = []
    for stratum in STRATA:
        for i in range(n_per_stratum):
            rid = f"{stratum}-{i:03d}"
            out.append(
                {
                    "id": rid,
                    "stratum": stratum,
                    "referee_verdict": {
                        "dung": "PASS_CORRECT",
                        "tu_boi_dung": "PASS_REFUSAL",
                        "tu_boi_oan": "FAIL_OVERREFUSAL",
                        "sai": "FAIL_FABRICATED",
                    }[stratum],
                    "question": f"câu hỏi {rid}",
                    "answer": f"câu trả lời {rid}",
                    "evidence": ["đoạn bằng chứng 1", "đoạn bằng chứng 2"],
                    "error": None,
                }
            )
    return out


class TestSampleSheetHidesReferee:
    def test_muc7_mau_60_dong_phan_tang_dung_target_va_tai_lap(self):
        chosen = stratified_sample(records(), default_targets(60), SEED)
        again = stratified_sample(records(), default_targets(60), SEED)
        assert len(chosen) == 60
        assert [r["id"] for r in chosen] == [r["id"] for r in again]
        counts = {s: sum(1 for r in chosen if r["stratum"] == s) for s in STRATA}
        assert counts == {"dung": 14, "tu_boi_dung": 15, "tu_boi_oan": 15, "sai": 16}
        assert sum(counts.values()) == 60

    def test_muc7_phieu_chi_co_cot_hien_thi_khong_verdict(self):
        chosen = stratified_sample(records(), default_targets(60), SEED)
        rows = build_label_rows(chosen)
        assert len(rows) == 60
        expected_keys = {
            "_huong_dan", "sample_index", "id", "question", "answer", "evidence",
            "nhan_tay", "ghi_chu",
        }
        for row in rows:
            assert set(row) == expected_keys
            assert row["nhan_tay"] == "" and row["ghi_chu"] == ""
        blob = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
        for forbidden in (
            "PASS_CORRECT", "PASS_REFUSAL", "FAIL_OVERREFUSAL", "FAIL_FABRICATED",
            "referee_verdict", "stratum", "gold_chunk_id", "gold_sentence",
            "required_entities", "grounding_score", "is_refusal", "detail",
        ):
            assert forbidden not in blob, f"phiếu lộ trường bị cấm: {forbidden}"

    def test_muc7_manifest_giu_verdict_de_cham_tach_khoi_phieu(self):
        chosen = stratified_sample(records(), default_targets(60), SEED)
        manifest = build_manifest(chosen, "r5", SEED, default_targets(60), {s: 30 for s in STRATA})
        assert manifest["n_selected"] == 60
        assert len(manifest["samples"]) == 60
        assert all(s["referee_verdict"] for s in manifest["samples"])
        assert manifest["seed"] == SEED

    def test_muc7_target_mac_dinh_tong_bang_n(self):
        for n in (10, 30, 60):
            assert sum(default_targets(n).values()) == n

    def test_muc7_phieu_that_tren_dia_60_dong_va_khong_co_cot_verdict(self):
        """Kiểm chính artifact script đã xuất (không chỉ hàm): 60 dòng, đúng cột, không verdict."""
        worksheet = DIAG / "referee_labeling_r5.jsonl"
        manifest_path = DIAG / "referee_sample_manifest.json"
        assert worksheet.exists() and manifest_path.exists()
        rows = [json.loads(line) for line in worksheet.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(rows) == 60
        assert all(set(r) == set(build_label_rows([{
            "sample_index": 1, "id": "x", "question": "q", "answer": "a", "evidence": []
        }])[0]) for r in rows)
        blob = worksheet.read_text(encoding="utf-8")
        for forbidden in ("PASS_CORRECT", "PASS_REFUSAL", "FAIL_FABRICATED", "referee_verdict", "gold_sentence"):
            assert forbidden not in blob
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["n_selected"] == 60 and len(manifest["samples"]) == 60


# --- Phiếu giả có đáp án biết trước ----------------------------------------- #

FAKE_LABELS = [
    # id, verdict trọng tài, nhãn người đọc
    ("a", "PASS_CORRECT", "dung"),            # đúng
    ("b", "PASS_CORRECT", "dung"),            # đúng
    ("c", "PASS_CORRECT", "sai"),             # trọng tài nói đúng, người nói sai
    ("d", "PASS_REFUSAL", "tu_boi_dung"),     # đúng
    ("e", "FAIL_OVERREFUSAL", "tu_boi_oan"),  # đúng
    ("f", "FAIL_FABRICATED", "sai"),          # đúng
    ("g", "FAIL_FABRICATED", "dung"),         # trọng tài nói sai, người nói đúng
    ("h", "PASS_REFUSAL", "sai"),             # trọng tài từ chối, người nói sai
]


def fake_worksheet(labels=FAKE_LABELS) -> tuple[list[dict], dict]:
    rows = [{"id": rid, "nhan_tay": label} for rid, _, label in labels]
    verdicts = {rid: verdict for rid, verdict, _ in labels}
    return rows, verdicts


class TestAgreementMetrics:
    def test_muc7_precision_recall_tinh_tay_tren_phieu_gia(self):
        rows, verdicts = fake_worksheet()
        stats = score_labels(rows, verdicts)
        assert stats["n_scored"] == 8
        assert stats["overall_accuracy"] == 0.625  # 5/8
        assert stats["n_filled"] == 8

        dung = stats["per_class"]["dung"]
        assert (dung["tp"], dung["fp"], dung["fn"]) == (2, 1, 1)
        assert (dung["precision"], dung["recall"]) == (0.6667, 0.6667)

        sai = stats["per_class"]["sai"]
        assert (sai["tp"], sai["fp"], sai["fn"]) == (1, 1, 2)
        assert (sai["precision"], sai["recall"]) == (0.5, 0.3333)

        tbd = stats["per_class"]["tu_boi_dung"]
        assert (tbd["tp"], tbd["fp"], tbd["fn"]) == (1, 1, 0)
        assert (tbd["precision"], tbd["recall"]) == (0.5, 1.0)

        tbo = stats["per_class"]["tu_boi_oan"]
        assert (tbo["tp"], tbo["fp"], tbo["fn"]) == (1, 0, 0)
        assert (tbo["precision"], tbo["recall"]) == (1.0, 1.0)

        matrix = stats["confusion_human_rows_x_referee_cols"]
        assert matrix["sai"]["dung"] == 1   # c: người nói sai, trọng tài nói đúng
        assert matrix["dung"]["sai"] == 1   # g: người nói đúng, trọng tài nói sai
        assert sum(sum(row.values()) for row in matrix.values()) == 8

    def test_muc7_khong_ro_bi_loai_khoi_diem_nhung_van_dem(self):
        rows, verdicts = fake_worksheet(
            FAKE_LABELS + [("i", "PASS_CORRECT", "khong_ro"), ("j", "PASS_CORRECT", "")]
        )
        stats = score_labels(rows, verdicts)
        assert stats["n_unclear_dropped"] == 1
        assert stats["n_unfilled"] == 1
        assert stats["n_scored"] == 8

    def test_muc7_thieu_nhan_bao_loi_o_che_do_strict(self):
        rows = [{"id": "x", "nhan_tay": ""}, {"id": "y", "nhan_tay": "dung"}]
        validate_labels(rows, allow_missing=True)  # chế độ chẩn đoán: được phép
        with pytest.raises(LabelError) as exc:
            validate_labels(rows, allow_missing=False)
        assert any("x" in p and "thiếu" in p for p in exc.value.problems)

    def test_muc7_nhan_sai_dinh_dang_bao_loi_ke_ca_che_do_long(self):
        for bad in ("đúng", "DUNG", "sai_bet", "co"):
            rows = [{"id": "x", "nhan_tay": bad}]
            with pytest.raises(LabelError):
                validate_labels(rows, allow_missing=True)

    def test_muc7_nhan_hop_le_khong_bao_loi(self):
        rows = [{"id": f"id{i}", "nhan_tay": c} for i, c in enumerate(CLASSES + ("khong_ro",))]
        validate_labels(rows, allow_missing=False)
