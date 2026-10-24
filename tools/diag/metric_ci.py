# -*- coding: utf-8 -*-
"""T6d — bootstrap CI 95% cho các CHỈ SỐ CHÍNH, truy được về file trên đĩa.

Mục đích: mọi con số xuất hiện trong bảng chấm phải kèm khoảng tin cậy để hội đồng thấy
cỡ mẫu nào thì kết luận chắc tới đâu. Điểm ước lượng (point estimate) lấy đúng công thức
của `gate.metrics` (mẫu số giống hệt), CI lấy bằng `noise_floor.rate_ci` (bootstrap ghép
item, 10.000 lượt, percentile 2.5/97.5). Vì dùng chung định nghĩa mẫu số, point estimate
trong file này KHỚP từng chữ số với số đã công bố — không tạo ra thang đo thứ hai.

Không ghi đè round đã đóng; chỉ viết vào data/loop/diag/metric_ci_<round>.json.

Dùng:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/metric_ci.py --round r7
    ... --round r10 --phase full
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT))

from tools.loop import gate  # noqa: E402
from tools.loop.verify import PASS_VERDICTS  # noqa: E402
from tools.loop.noise_floor import rate_ci, BOOTSTRAP_REPS, BOOTSTRAP_SEED  # noqa: E402

DIAG = ROOT / "data" / "loop" / "diag"


def item_series(rows: list[dict]) -> dict[str, tuple[list[int], list[int], float | None]]:
    """Trả về {ten_chi_so: (tử_số_khớp_item, mẫu_số_khớp_item, điểm_ước_lượng)}.

    Thứ tự tử/mẫu khớp nhau trên CÙNG một tập item — chính là điều bootstrap theo item
    cần. Điểm ước lượng tính lại tại chỗ để đối chiếu với gate.metrics.
    """
    decided = [r for r in rows if r.get("verdict") != "PENDING_GENERATION"]
    answered = [r for r in decided if not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0]
    gold_rows = [r for r in rows if r.get("has_gold_chunk")]

    out: dict[str, tuple[list[int], list[int], float | None]] = {}

    # pass_rate (mọi verdict ĐẠT) và pass_correct_rate (riêng PASS_CORRECT)
    for key, pred in (
        ("pass_rate", lambda r: r.get("verdict") in PASS_VERDICTS),
        ("pass_correct_rate", lambda r: r.get("verdict") == "PASS_CORRECT"),
        ("refusal_rate", lambda r: bool(r.get("is_refusal"))),
    ):
        num = [1 if pred(r) else 0 for r in decided]
        den = [1] * len(decided)
        est = round(sum(num) / len(num), 4) if num else None
        out[key] = (num, den, est)

    # fabrication trên câu đã trả lời
    num = [1 if r.get("unsupported") else 0 for r in answered]
    den = [1] * len(answered)
    out["fabrication_rate_on_answered"] = (num, den, round(sum(num) / len(num), 4) if num else None)

    # gold_in_top_k_rate (mẫu số = item có chunk vàng)
    num = [1 if r.get("gold_in_top_k") else 0 for r in gold_rows]
    den = [1] * len(gold_rows)
    out["gold_in_top_k_rate"] = (num, den, round(sum(num) / len(num), 4) if num else None)

    # mean grounding (trên câu đã trả lời có điểm): tử = giá trị grounding, mẫu = 1
    gr = [float(r["grounding_score"]) for r in answered if r.get("grounding_score") is not None]
    est_g = round(sum(gr) / len(gr), 4) if gr else None
    out["mean_grounding_score"] = (gr, [1] * len(gr), est_g)

    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--round", default="r7")
    ap.add_argument("--phase", default="full", choices=["full", "retrieval"])
    ap.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    args = ap.parse_args()

    rdir = ROOT / "data" / "loop" / "rounds" / args.round
    rows_map = gate.load_rows(rdir, args.phase)
    rows = list(rows_map.values())
    if not rows:
        raise SystemExit(f"Round {args.round}/{args.phase} không có dòng verdict nào.")

    # điểm ước lượng chuẩn từ gate.metrics để đối chiếu (không tự tính tay ở báo cáo).
    gmetrics = gate.metrics(rows)

    series = item_series(rows)
    result = {
        "round": args.round,
        "phase": args.phase,
        "n_rows": len(rows),
        "method": f"paired item bootstrap, {BOOTSTRAP_REPS} reps, percentile CI, seed={args.seed}",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "metrics": {},
    }

    for key, (num, den, est) in series.items():
        ci = rate_ci(num, den, seed=args.seed) if num else {}
        # đối chiếu point estimate với gate.metrics khi gate.metrics có cùng tên chỉ số.
        has_gate_key = key in gmetrics
        gate_est = gmetrics.get(key)
        if has_gate_key:
            match = (est is None and gate_est is None) or (
                est is not None and gate_est is not None and abs(est - gate_est) < 1e-6
            )
        else:
            match = None  # chỉ số riêng của script, không có ô tương ứng trong gate.metrics
        result["metrics"][key] = {
            "n_metric": len(num),
            "point_estimate": est,
            "gate_metrics_value": gate_est if has_gate_key else None,
            "point_matches_gate": match,
            "ci95": ci.get("ci95"),
        }

    out_path = DIAG / f"metric_ci_{args.round}_{args.phase}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[T6d] round={args.round} phase={args.phase} n={len(rows)} ({BOOTSTRAP_REPS} reps, seed={args.seed})")
    print(f"{'metric':30}{'n':>5}{'point':>9}{'ci95_low':>10}{'ci95_hi':>9}  match_gate")
    for key, m in result["metrics"].items():
        ci = m["ci95"] or [None, None]
        fmt = lambda x: "-" if x is None else f"{x:.4f}"  # noqa: E731
        print(f"{key:30}{m['n_metric']:>5}{fmt(m['point_estimate']):>9}{fmt(ci[0]):>10}{fmt(ci[1]):>9}  {m['point_matches_gate']}")
    print(f"[T6d] ghi: {out_path}")


if __name__ == "__main__":
    main()
