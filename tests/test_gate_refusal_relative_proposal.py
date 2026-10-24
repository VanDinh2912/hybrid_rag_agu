# -*- coding: utf-8 -*-
"""Test cho BẢN ĐỀ XUẤT cổng refusal tương đối (T6a) — chưa nối vào gate thật.

Chứng minh cả hai nhánh của `evaluate_refusal_rule`:
  * tương đối phủ quyết: ĐẠT khi không tăng quá delta, BỊ khi tăng quá delta;
  * thiếu baseline => KHÔNG ĐO ĐƯỢC = CẤM (ok=False), không im lặng ĐẠT;
  * trần tuyệt đối 0.35 chỉ SINH WARNING, không nằm trong checks nên không phủ quyết.
"""

from tools.diag.gate_refusal_relative_proposal import evaluate_refusal_rule


def _refusal_check(checks):
    return next(c for c in checks if c["rule"] == "refusal_rate_not_increased")


def test_relative_pass_when_no_increase():
    checks, warns = evaluate_refusal_rule(0.30, 0.30)
    assert _refusal_check(checks)["ok"] is True
    assert warns == []


def test_relative_pass_within_delta_even_above_absolute_ceiling():
    # candidate 0,38 > trần 0,35 nhưng chỉ +0,03 so baseline 0,35 -> tương đối ĐẠT,
    # và vì vượt 0,35 nên CÓ warning; warning không được nằm trong checks.
    checks, warns = evaluate_refusal_rule(0.38, 0.35)
    assert _refusal_check(checks)["ok"] is True
    assert len(warns) == 1 and warns[0]["rule"] == "refusal_rate_absolute_ceiling"
    assert all("absolute" not in c["rule"] for c in checks)  # không phủ quyết qua checks


def test_relative_fail_when_increase_over_delta():
    # 0,45 vs baseline 0,30 = +0,15 > delta 0,05 -> BỊ, bất kể mọi thứ khác.
    checks, warns = evaluate_refusal_rule(0.45, 0.30)
    assert _refusal_check(checks)["ok"] is False
    assert len(warns) == 1  # 0,45 cũng vượt 0,35


def test_relative_pass_when_candidate_decreases():
    # candidate thấp hơn baseline (cải thiện refusal) -> luôn ĐẠT, không warning.
    checks, warns = evaluate_refusal_rule(0.20, 0.35)
    assert _refusal_check(checks)["ok"] is True
    assert warns == []


def test_missing_baseline_is_forbidden_not_silent_pass():
    checks, warns = evaluate_refusal_rule(0.10, None)
    assert _refusal_check(checks)["ok"] is False
    assert "KHÔNG ĐO ĐƯỢC" in _refusal_check(checks)["detail"]


def test_retrieval_phase_no_candidate_rate_adds_nothing():
    checks, warns = evaluate_refusal_rule(None, 0.30)
    assert checks == [] and warns == []


def test_delta_threshold_is_configurable():
    # Cùng candidate/baseline nhưng nới delta -> từ BỊ sang ĐẠT.
    strict, _ = evaluate_refusal_rule(0.40, 0.30, max_refusal_delta=0.05)
    loose, _ = evaluate_refusal_rule(0.40, 0.30, max_refusal_delta=0.15)
    assert _refusal_check(strict)["ok"] is False
    assert _refusal_check(loose)["ok"] is True


def test_absolute_ceiling_default_is_035():
    # đúng 0,35 không vượt -> không warning; 0,36 vượt -> warning.
    _, w1 = evaluate_refusal_rule(0.35, 0.35)
    _, w2 = evaluate_refusal_rule(0.36, 0.35)
    assert w1 == []
    assert len(w2) == 1
