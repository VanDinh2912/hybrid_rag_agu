# -*- coding: utf-8 -*-
"""T6a — BẢN ĐỀ XUẤT (chưa nối vào gate thật).

Module tạm này mô phỏng đúng đoạn logic `refusal_rate_bounded` định thay thế trong
`tools/loop/gate.py::compare()`. Nó KHÔNG import gate.py và KHÔNG đổi gate.py. Mục đích:
chứng minh cả hai nhánh của luật MỚI (tương đối) chạy đúng, để khi duyệt xong thì mang
nguyên đoạn này vào gate.py.

Luật hiện hành (tuyệt đối): một round chỉ lọt nếu `refusal_rate <= 0.35`, bất kể baseline.
Vấn đề: nếu baseline đã 0,30 thì candidate 0,34 (tốt hơn trần 0,35) vẫn ĐẠT, còn khi
trần vượt 0,35 vì corpus nhiều câu ngoài phạm vi thì round tốt bị veto oan. Ta muốn phạt
SỰ GIA TĂNG so với baseline, không phạt mức tuyệt đối.

Luật đề xuất:
  * tương đối (phủ quyết): candidate <= baseline + GATE_MAX_REFUSAL_RATE_DELTA (0.05);
    thiếu baseline refusal_rate => KHÔNG ĐO ĐƯỢC = CẤM (đúng quy tắc "rule không đo được
    không phải ĐẠT" của gate).
  * tuyệt đối (CẢNH BÁO, không phủ quyết): nếu candidate > 0.35 thì ghi vào `warnings`,
    vẫn in ra hội đồng nhưng không kéo `passed` xuống.
"""

from __future__ import annotations

from typing import Optional

GATE_MAX_REFUSAL_RATE_DEFAULT = 0.35
GATE_MAX_REFUSAL_RATE_DELTA_DEFAULT = 0.05


def _delta(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old is None:
        return None
    return round(new - old, 4)


def evaluate_refusal_rule(
    candidate_rate: Optional[float],
    baseline_rate: Optional[float],
    max_refusal: float = GATE_MAX_REFUSAL_RATE_DEFAULT,
    max_refusal_delta: float = GATE_MAX_REFUSAL_RATE_DELTA_DEFAULT,
) -> tuple[list[dict], list[dict]]:
    """Trả về (checks, warnings). Chỉ `checks` tham gia `passed`; `warnings` để in."""
    checks: list[dict] = []
    warnings: list[dict] = []

    if candidate_rate is None:
        # Không có số refusal phía candidate: round này là pha retrieval, luật không áp dụng.
        return checks, warnings

    # --- nhánh phủ quyết: tương đối theo baseline ---
    if baseline_rate is not None:
        ok = candidate_rate <= baseline_rate + max_refusal_delta
        checks.append(
            {
                "rule": "refusal_rate_not_increased",
                "ok": bool(ok),
                "detail": (
                    f"candidate={candidate_rate} baseline={baseline_rate} "
                    f"delta={_delta(candidate_rate, baseline_rate)} "
                    f"(ngưỡng tương đối +{max_refusal_delta})"
                ),
            }
        )
    else:
        checks.append(
            {
                "rule": "refusal_rate_not_increased",
                "ok": False,
                "detail": (
                    f"KHÔNG ĐO ĐƯỢC: candidate={candidate_rate} nhưng baseline thiếu "
                    "refusal_rate (round đối chiếu chạy bằng verify cũ hoặc pha khác) — "
                    "chạy lại round baseline rồi mở cổng"
                ),
            }
        )

    # --- nhánh cảnh báo: trần tuyệt đối, KHÔNG phủ quyết ---
    if candidate_rate > max_refusal:
        warnings.append(
            {
                "rule": "refusal_rate_absolute_ceiling",
                "severity": "warning",
                "detail": (
                    f"candidate={candidate_rate} vượt trần tuyệt đối {max_refusal} — "
                    "cảnh báo để hội đồng xem, không tự động phủ quyết"
                ),
            }
        )

    return checks, warnings


def apply_to_gate_result(
    result: dict,
    candidate_rate: Optional[float],
    baseline_rate: Optional[float],
    max_refusal: float = GATE_MAX_REFUSAL_RATE_DEFAULT,
    max_refusal_delta: float = GATE_MAX_REFUSAL_RATE_DELTA_DEFAULT,
) -> dict:
    """MÔ PHỎNG kết quả `gate.compare()` NẾU PA-13 được duyệt.

    Thay đúng một luật (`refusal_rate_bounded` tuyệt đối) bằng cặp
    `refusal_rate_not_increased` + cảnh báo trần; giữ nguyên mọi check khác và
    `config_mismatches`. Chỉ dùng để kiểm thử/đối chiếu — KHÔNG import hay sửa gate.py.
    """
    checks, warnings = evaluate_refusal_rule(
        candidate_rate, baseline_rate, max_refusal=max_refusal, max_refusal_delta=max_refusal_delta
    )
    replaced = {"refusal_rate_bounded", "refusal_rate_not_increased"}
    new = dict(result)
    new["checks"] = [c for c in result.get("checks", []) if c.get("rule") not in replaced] + checks
    new["warnings"] = list(result.get("warnings") or []) + warnings
    new["passed"] = all(c.get("ok") for c in new["checks"])
    if result.get("config_mismatches"):
        # Giữ nguyên hành vi gate.main: cấu hình lệch thì cổng đóng, bất kể checks.
        new["passed"] = False
    return new
