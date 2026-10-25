# -*- coding: utf-8 -*-
"""T6 mục 1–6 — kiểm thử CỔNG: luật refusal tương đối (bản đề xuất PA-13) và
sáu luật còn lại phải giữ nguyên.

`gate.py` KHÔNG bị sửa trong nhiệm vụ này. Mục 1–4 chạy trên
`tools/diag/gate_refusal_relative_proposal.py` (bản mô phỏng đúng đoạn logic sẽ thay);
mục 5 đối chiếu lại cổng cũ trên file thật + mô phỏng PA-13; mục 6 kiểm cổng đóng khi
chữ ký trọng tài/cấu hình hai round lệch.

Đính chính quan trọng so với câu chữ đề bài: chạy lại `r5-vs-r3` KHÔNG đổi sang ĐẠT
dưới luật tương đối, vì refusal tăng +0,08 (quá ngưỡng 0,05) và fabrication vẫn tăng.
Ca DUY NHẤT lật sang ĐẠT là `r5-vs-r1` (0,69 so với baseline 0,72 + cảnh báo trần).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.diag.gate_refusal_relative_proposal import (
    apply_to_gate_result,
    evaluate_refusal_rule,
)
from tools.loop import gate

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = ROOT / "data" / "loop" / "rounds"

THRESHOLD_ENV = (
    "GATE_MAX_PASS_DROP",
    "GATE_MAX_FAMILY_DROP",
    "GATE_MAX_FABRICATION_DELTA",
    "GATE_MAX_MISSED_REFUSAL_DELTA",
    "GATE_MAX_REFUSAL_RATE",
    "GATE_MAX_RECALL_DROP",
    "GATE_MIN_FAMILY_N",
    "GATE_MIN_COMMON",
    "GATE_ALLOW_CONFIG_MISMATCH",
)


@pytest.fixture(autouse=True)
def _gate_defaults(monkeypatch):
    for name in THRESHOLD_ENV:
        monkeypatch.delenv(name, raising=False)


def _refusal_check(checks: list[dict]) -> dict:
    return next(c for c in checks if c["rule"] == "refusal_rate_not_increased")


# --------------------------------------------------------------------------- #
# Mục 1–4: luật refusal tương đối (bản đề xuất)
# --------------------------------------------------------------------------- #

class TestRefusalRelativeRule:
    def test_muc1_baseline_072_candidate_069_dat_kem_canh_bao_khong_phu_quyet(self):
        checks, warnings = evaluate_refusal_rule(0.69, 0.72)
        assert _refusal_check(checks)["ok"] is True
        assert [w["rule"] for w in warnings] == ["refusal_rate_absolute_ceiling"]
        assert warnings[0]["severity"] == "warning"
        # cảnh báo KHÔNG được nằm trong checks (nếu nằm, nó sẽ kéo `passed` xuống).
        assert all(c["rule"] != "refusal_rate_absolute_ceiling" for c in checks)

    def test_muc2_candidate_080_so_baseline_072_tang_qua_nguong_khong_dat(self):
        checks, warnings = evaluate_refusal_rule(0.80, 0.72)
        assert _refusal_check(checks)["ok"] is False
        # 0,80 vẫn vượt trần tuyệt đối => có cảnh báo, nhưng quyết định là VI PHẠM.
        assert [w["rule"] for w in warnings] == ["refusal_rate_absolute_ceiling"]

    @pytest.mark.parametrize(
        "candidate, expected",
        [
            (0.7699, True),   # ngay dưới ngưỡng
            (0.77, True),     # ĐÚNG biên: baseline 0,72 + delta 0,05
            (0.7701, False),  # ngay trên ngưỡng
        ],
    )
    def test_muc3_diem_bien_duoi_dung_tren(self, candidate, expected):
        checks, _ = evaluate_refusal_rule(candidate, 0.72, max_refusal_delta=0.05)
        assert _refusal_check(checks)["ok"] is expected

    def test_muc4_baseline_rong_hoac_n0_thi_tu_choi_mo_cong(self):
        # (a) baseline_rate = None (ví dụ baseline n=0, metrics chỉ trả {"n": 0}).
        checks, warnings = evaluate_refusal_rule(0.10, None)
        assert _refusal_check(checks)["ok"] is False
        assert "KHÔNG ĐO ĐƯỢC" in _refusal_check(checks)["detail"]
        # Không có lý do gì để cảnh báo trần khi quyết định đã là VI PHẠM.
        assert warnings == []

        # (b) đường đi thật: metrics([]) -> {"n": 0} -> refusal_rate None.
        empty = gate.metrics([])
        assert empty == {"n": 0}
        checks2, _ = evaluate_refusal_rule(0.30, empty.get("refusal_rate"))
        assert _refusal_check(checks2)["ok"] is False
        assert "KHÔNG ĐO ĐƯỢC" in _refusal_check(checks2)["detail"]

    def test_muc4_mo_phong_khien_cong_khong_mo_du_cac_luat_khac_dat(self):
        result = _passing_gate_result()
        simulated = apply_to_gate_result(result, 0.30, None)
        assert simulated["passed"] is False
        assert _refusal_check(simulated["checks"])["ok"] is False


# --------------------------------------------------------------------------- #
# Mục 5a: sáu luật còn lại — test hồi quy từng luật, có biên
# --------------------------------------------------------------------------- #

def fam(n=20, *, pass_rate=None, gold_rate=None, anchor_rate=None) -> dict:
    return {
        "n": n,
        "n_decided": n,
        "pass_rate": pass_rate,
        "gold_rate": gold_rate,
        "n_gold": n if gold_rate is not None else 0,
        "anchor_rate": anchor_rate,
        "n_anchor": n if anchor_rate is not None else 0,
        "fabricated": 0,
    }


def metric(**over) -> dict:
    m = {
        "n": 100,
        "n_decided": 100,
        "has_answer_signal": True,
        "n_gold_items": 100,
        "pass_rate": 0.80,
        "fabrication_rate_on_answered": 0.01,
        "hallucinated_on_unanswerable": 0,
        "confirmed_false_premise": 0,
        "overrefusal": 0,
        "retrieval_failures": 0,
        "incomplete": 0,
        "refusal_rate": 0.30,
        "mean_grounding_score": 1.0,
        "gold_in_top_k_rate": 0.80,
        "gold_flagged_rows": 100,
        "verdict_counts": {},
        "by_family": {},
    }
    m.update(over)
    return m


def compare(cand: dict, base: dict) -> dict:
    cand = dict(cand, _rows={})
    base = dict(base, _rows={})
    return gate.compare(cand, base, [])


def _check(result: dict, rule: str) -> dict:
    return next(c for c in result["checks"] if c["rule"] == rule)


def _passing_gate_result() -> dict:
    base = metric()
    return compare(metric(), base)


class TestSixRemainingRules:
    def test_fabrication_khong_duoc_tang_bien_0(self):
        base = metric(fabrication_rate_on_answered=0.01)
        assert _check(compare(metric(fabrication_rate_on_answered=0.01), base),
                      "fabrication_not_increased")["ok"] is True
        assert _check(compare(metric(fabrication_rate_on_answered=0.0101), base),
                      "fabrication_not_increased")["ok"] is False

    def test_hallucinated_on_unanswerable_khong_duoc_tang(self):
        base = metric(hallucinated_on_unanswerable=2)
        assert _check(compare(metric(hallucinated_on_unanswerable=2), base),
                      "no_new_hallucinated_refusal")["ok"] is True
        assert _check(compare(metric(hallucinated_on_unanswerable=3), base),
                      "no_new_hallucinated_refusal")["ok"] is False

    def test_pass_rate_roi_dung_2_diem_phan_tram_van_dat(self):
        base = metric(pass_rate=0.80)
        assert _check(compare(metric(pass_rate=0.78), base), "pass_rate_not_dropped")["ok"] is True
        assert _check(compare(metric(pass_rate=0.7799), base), "pass_rate_not_dropped")["ok"] is False

    def test_family_roi_dung_10_diem_van_dat_va_bo_qua_family_nho(self):
        base = metric(by_family={"EXACT": fam(10, pass_rate=0.80), "SMALL": fam(7, pass_rate=0.50)})
        at_bound = compare(metric(by_family={"EXACT": fam(10, pass_rate=0.70)}), base)
        assert _check(at_bound, "family_pass_rate")["ok"] is True
        over = compare(metric(by_family={"EXACT": fam(10, pass_rate=0.6999)}), base)
        assert _check(over, "family_pass_rate[EXACT]")["ok"] is False
        # family n=7 < GATE_MIN_FAMILY_N=8: rơi xuống 0 cũng KHÔNG thành vi phạm.
        small = compare(metric(by_family={"SMALL": fam(7, pass_rate=0.0)}), base)
        assert _check(small, "family_pass_rate")["ok"] is True

    def test_neo_human_khong_giam_qua_5_phan_tram_tuong_doi(self):
        base = metric(by_family={"HUMAN": fam(20, pass_rate=0.80)})
        inside = compare(metric(by_family={"HUMAN": fam(20, pass_rate=0.7601)}), base)
        assert _check(inside, "human_anchor_not_degraded")["ok"] is True
        outside = compare(metric(by_family={"HUMAN": fam(20, pass_rate=0.7599)}), base)
        assert _check(outside, "human_anchor_not_degraded")["ok"] is False

    def test_neo_nguon_human_o_pha_re_che_va_thieu_la_cam(self):
        base = metric(by_family={"HUMAN": fam(20, anchor_rate=0.80)})
        inside = compare(metric(by_family={"HUMAN": fam(20, anchor_rate=0.7601)}), base)
        assert _check(inside, "human_anchor_source_not_degraded")["ok"] is True
        outside = compare(metric(by_family={"HUMAN": fam(20, anchor_rate=0.7599)}), base)
        assert _check(outside, "human_anchor_source_not_degraded")["ok"] is False
        # candidate KHÔNG còn anchor_rate nhưng có item neo => KHÔNG ĐO ĐƯỢC = CẤM.
        missing = compare(metric(by_family={"HUMAN": fam(20, anchor_rate=None)}), base)
        check = _check(missing, "human_anchor_source_not_degraded")
        assert check["ok"] is False and "KHÔNG ĐO ĐƯỢC" in check["detail"]

    def test_retrieval_roi_dung_2_diem_van_dat_va_thieu_so_lieu_la_cam(self):
        base = metric(gold_in_top_k_rate=0.80)
        assert _check(compare(metric(gold_in_top_k_rate=0.78), base),
                      "retrieval_not_degraded")["ok"] is True
        assert _check(compare(metric(gold_in_top_k_rate=0.7799), base),
                      "retrieval_not_degraded")["ok"] is False
        missing = _check(compare(metric(gold_in_top_k_rate=None), base), "retrieval_not_degraded")
        assert missing["ok"] is False and "KHÔNG ĐO ĐƯỢC" in missing["detail"]

    def test_sau_khi_mo_phong_pa13_sau_luat_con_lai_van_nguyen(self):
        """Mô phỏng chỉ THAY luật refusal; không được vô tình làm rơi/nới luật khác."""
        base_result = compare(metric(), metric())
        simulated = apply_to_gate_result(base_result, 0.30, 0.30)
        assert simulated["passed"] is True
        assert [c["rule"] for c in simulated["checks"]].count("fabrication_not_increased") == 1
        assert [c["rule"] for c in simulated["checks"]].count("refusal_rate_bounded") == 0
        assert [c["rule"] for c in simulated["checks"]].count("refusal_rate_not_increased") == 1


# --------------------------------------------------------------------------- #
# Mục 5b: chạy lại cổng cũ trên file thật + mô phỏng PA-13
# --------------------------------------------------------------------------- #

def recompute(candidate: str, baseline: str, phase: str) -> tuple[dict, dict, dict, list[str]]:
    cand_rows = gate.load_rows(ROUNDS / candidate, phase)
    base_rows = gate.load_rows(ROUNDS / baseline, phase)
    common = sorted(set(cand_rows) & set(base_rows))
    c = gate.metrics([cand_rows[i] for i in common])
    b = gate.metrics([base_rows[i] for i in common])
    c["_rows"], b["_rows"] = cand_rows, base_rows
    return gate.compare(c, b, common), c, b, common


def published(round_name: str, baseline: str, phase: str) -> dict:
    return json.loads((ROUNDS / round_name / f"gate_vs_{baseline}_{phase}.json").read_text(encoding="utf-8"))


class TestRealFileRegression:
    def test_r4_vs_r2_retrieval_giu_nguyen_ket_qua_da_cong_bo(self):
        result, cand, base, common = recompute("r4", "r2", "retrieval")
        pub = published("r4", "r2", "retrieval")
        assert len(common) == 811
        assert result["passed"] is True and pub["passed"] is True
        assert [(c["rule"], c["ok"]) for c in result["checks"]] == [
            (c["rule"], c["ok"]) for c in pub["checks"]
        ]
        assert base["gold_in_top_k_rate"] == 0.74
        assert cand["gold_in_top_k_rate"] == 0.7429
        assert base["by_family"]["HUMAN"]["anchor_rate"] == 0.8144
        assert cand["by_family"]["HUMAN"]["anchor_rate"] == 0.8144
        assert gate.compatibility(
            gate.round_settings(ROUNDS / "r4", "retrieval"),
            gate.round_settings(ROUNDS / "r2", "retrieval"),
        ) == []
        # Dưới PA-13, pha truy xuất vẫn ĐẠT y nguyên (refusal 0,0; không cảnh báo trần).
        simulated = apply_to_gate_result(result, cand["refusal_rate"], base["refusal_rate"])
        assert simulated["passed"] is True
        assert simulated["warnings"] == []
        assert _refusal_check(simulated["checks"])["ok"] is True

    def test_r5_vs_r3_chay_lai_dung_so_cong_bo(self):
        result, cand, base, common = recompute("r5", "r3", "full")
        pub = published("r5", "r3", "full")
        assert len(common) == 100
        assert result["passed"] is False and pub["passed"] is False
        assert [(c["rule"], c["ok"]) for c in result["checks"]] == [
            (c["rule"], c["ok"]) for c in pub["checks"]
        ]
        assert cand["fabrication_rate_on_answered"] == 0.0323
        assert base["fabrication_rate_on_answered"] == 0.0256
        assert cand["refusal_rate"] == 0.69
        assert base["refusal_rate"] == 0.61

    def test_r5_vs_r3_duoi_pa13_van_khong_dat_vi_refusal_tang_008(self):
        """ĐÍNH CHÍNH câu chữ đề bài: ca này KHÔNG lật sang ĐẠT.

        refusal 0,69 - 0,61 = +0,08 > delta 0,05; ngoài ra fabrication còn tăng
        (0,0256 -> 0,0323) nên dù refusal có đổi luật thì cổng vẫn đóng.
        """
        result, cand, base, _ = recompute("r5", "r3", "full")
        simulated = apply_to_gate_result(result, cand["refusal_rate"], base["refusal_rate"])
        assert simulated["passed"] is False
        assert _refusal_check(simulated["checks"])["ok"] is False
        assert "delta=0.08" in _refusal_check(simulated["checks"])["detail"]
        assert _check(simulated, "fabrication_not_increased")["ok"] is False
        # 0,69 > 0,35 => có cảnh báo trần, nhưng cảnh báo không cứu được cổng.
        assert any(w["rule"] == "refusal_rate_absolute_ceiling" for w in simulated["warnings"])

    def test_r5_vs_r1_la_ca_duy_nhat_lat_sang_dat_duoi_pa13(self):
        result, cand, base, _ = recompute("r5", "r1", "full")
        assert result["passed"] is False
        assert [c["rule"] for c in result["checks"] if not c["ok"]] == ["refusal_rate_bounded"]
        simulated = apply_to_gate_result(result, cand["refusal_rate"], base["refusal_rate"])
        assert simulated["passed"] is True
        assert _refusal_check(simulated["checks"])["ok"] is True
        assert [w["rule"] for w in simulated["warnings"]] == ["refusal_rate_absolute_ceiling"]

    def test_r3_vs_r1_duoi_pa13_van_khong_dat_vi_hallucination(self):
        result, cand, base, _ = recompute("r3", "r1", "full")
        simulated = apply_to_gate_result(result, cand["refusal_rate"], base["refusal_rate"])
        assert _refusal_check(simulated["checks"])["ok"] is True  # 0,61 <= 0,72
        assert _check(simulated, "no_new_hallucinated_refusal")["ok"] is False  # 3 > 2
        assert simulated["passed"] is False

    @pytest.mark.parametrize(
        "candidate, baseline, phase, expected_rc",
        [("r4", "r2", "retrieval", 0), ("r5", "r3", "full", 1)],
    )
    def test_cli_cong_that_tra_ma_thoat_dung(self, tmp_path, candidate, baseline, phase, expected_rc):
        out = tmp_path / f"gate_{candidate}_{baseline}.json"
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "loop" / "gate.py"),
                "--candidate", candidate,
                "--baseline", baseline,
                "--phase", phase,
                "--out", str(out),
            ],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        assert proc.returncode == expected_rc, proc.stdout + proc.stderr
        written = json.loads(out.read_text(encoding="utf-8"))
        assert written["passed"] is (expected_rc == 0)


# --------------------------------------------------------------------------- #
# Mục 6: cổng từ chối mở khi trọng tài/cấu hình lệch
# --------------------------------------------------------------------------- #

SETTINGS = {
    "referee": "9f1179ccab74",
    "testset": "testset_v1",
    "top_k": 6,
    "generator": "qwen2.5:1.5b-instruct",
    "normalize_query": False,
    "enable_classifier": True,
}


def _write_round(root: Path, name: str, settings: dict, n: int = 20) -> None:
    rdir = root / name
    rdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": f"X{i:03d}",
                "family": "NUMERIC",
                "split": "test",
                "verdict": "PASS_CORRECT",
                "is_refusal": False,
                "unsupported": [],
                "answer_chars": 200,
                "gold_in_top_k": True,
                "grounding_score": 1.0,
                "has_gold_chunk": True,
                "raw_query": f"câu hỏi {i}",
            }
        )
    (rdir / "verdicts_full.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    (rdir / "round_summary_full.json").write_text(
        json.dumps({"settings": settings}, ensure_ascii=False), encoding="utf-8"
    )


def _run_gate_main(monkeypatch, root: Path, out: Path, candidate="cand", baseline="base") -> int:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gate.py",
            "--rounds-root", str(root),
            "--candidate", candidate,
            "--baseline", baseline,
            "--phase", "full",
            "--out", str(out),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        gate.main()
    return int(exc.value.code or 0)


class TestCompatibilityRefusesToOpen:
    def test_chu_ky_trong_tai_lech_bi_bat(self):
        problems = gate.compatibility(dict(SETTINGS), dict(SETTINGS, referee="deadbeef"))
        assert len(problems) == 1 and "trọng tài" in problems[0]

    def test_cau_hinh_khac_bi_bat_tung_key(self):
        problems = gate.compatibility(
            dict(SETTINGS, generator="gemini", top_k=12),
            dict(SETTINGS),
        )
        assert sum("generator" in p for p in problems) == 1
        assert sum("top_k" in p for p in problems) == 1
        assert len(problems) == 2

    def test_thieu_round_summary_la_mot_canh_bao_khong_xac_nhan_duoc(self):
        problems = gate.compatibility({}, dict(SETTINGS))
        assert len(problems) == 1 and "thiếu round_summary" in problems[0]

    def test_cli_dong_cong_khi_trong_tai_lech(self, monkeypatch, tmp_path):
        root = tmp_path / "rounds"
        _write_round(root, "base", dict(SETTINGS))
        _write_round(root, "cand", dict(SETTINGS, referee="deadbeef"))
        out = tmp_path / "gate.json"
        rc = _run_gate_main(monkeypatch, root, out)
        assert rc == 1
        written = json.loads(out.read_text(encoding="utf-8"))
        assert written["passed"] is False
        assert any("trọng tài" in m for m in written["config_mismatches"])

    def test_cli_dong_cong_khi_testset_lech(self, monkeypatch, tmp_path):
        root = tmp_path / "rounds"
        _write_round(root, "base", dict(SETTINGS))
        _write_round(root, "cand", dict(SETTINGS, testset="testset_v2"))
        out = tmp_path / "gate.json"
        assert _run_gate_main(monkeypatch, root, out) == 1
        assert any("testset" in m for m in json.loads(out.read_text(encoding="utf-8"))["config_mismatches"])

    def test_co_cho_phep_ro_nhung_cau_hinh_van_ghi_mismatch(self, monkeypatch, tmp_path):
        """`GATE_ALLOW_CONFIG_MISMATCH=1` chỉ dùng để chẩn đoán: checks ĐẠT thì cổng mở,
        nhưng danh sách mismatch VẪN được ghi để không ai quên hai round khác cấu hình."""
        monkeypatch.setenv("GATE_ALLOW_CONFIG_MISMATCH", "1")
        root = tmp_path / "rounds"
        _write_round(root, "base", dict(SETTINGS))
        _write_round(root, "cand", dict(SETTINGS, generator="gemini"))
        out = tmp_path / "gate.json"
        assert _run_gate_main(monkeypatch, root, out) == 0
        written = json.loads(out.read_text(encoding="utf-8"))
        assert written["passed"] is True
        assert any("generator" in m for m in written["config_mismatches"])
