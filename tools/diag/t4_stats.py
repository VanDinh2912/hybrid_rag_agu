# -*- coding: utf-8 -*-
"""T4 — bảng số có CI cho báo cáo "từng model/cấu hình".

Tiêu chí xong của T4 yêu cầu *bảng so sánh từng model/cấu hình với CI*, nên mọi con số
trong báo cáo T4 phải đi kèm khoảng tin cậy lấy từ cùng một hàm thống kê đã dùng ở T0/T1
(`tools/loop/noise_floor.py`), không phải công thức tự viết lại.

Ba thứ nó làm, đều CHỈ ĐỌC tệp đã có trên đĩa:

1. từng round: `PASS_CORRECT`, `refusal_rate`, `fabrication_rate_on_answered`, `gold@k`
   kèm CI bootstrap 10.000 lượt (seed `20261023`, đúng chuẩn T0/T1);
2. ghép cặp theo item chung: McNemar chính xác cho `PASS_CORRECT` + paired bootstrap cho
   ba tỉ số (chênh có nghĩa hay nằm trong băng nhiễu ±3 item của T0);
3. cấu hình (b) của T1: đếm lại theo id (gộp dòng trùng) rồi gắn CI — phần này phục vụ
   bảng quyết định "năng lực model", hiện mới n=12/30 nên mọi số đều phải in kèm `n`.

Không ghi đè tệp cũ của round: kết quả vào `<round_dir>/t4_stats.json` (tệp mới).

    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/t4_stats.py \
        --rounds r5 r8 r9 r10 --pairs r10:r5 r10:r9 --out data/loop/rounds/r10/t4_stats.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.loop.noise_floor import (  # noqa: E402
    BOOTSTRAP_SEED,
    answered,
    fabricated,
    mcnemar_exact,
    paired_bootstrap,
    rate_ci,
)

ROUNDS_ROOT = ROOT / "data" / "loop" / "rounds"


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def percentile(values: list[float], q: float) -> float | None:
    """Cùng cách lấy phần tử với `run_round._percentile` (không nội suy)."""
    if not values:
        return None
    ordered = sorted(values)
    pos = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return round(ordered[pos], 2)


def flags_for(verdicts: list[dict]) -> dict[str, list[int]]:
    return {
        "pass_correct": [1 if v.get("verdict") == "PASS_CORRECT" else 0 for v in verdicts],
        "refusal": [1 if v.get("is_refusal") else 0 for v in verdicts],
        "fabricated": [1 if fabricated(v) else 0 for v in verdicts],
        "answered": [1 if answered(v) else 0 for v in verdicts],
        "gold_in_window": [1 if v.get("gold_in_top_k") else 0 for v in verdicts],
        "has_gold": [1 if v.get("has_gold_chunk") else 0 for v in verdicts],
    }


def round_block(name: str, verdicts: list[dict]) -> dict[str, Any]:
    if not verdicts:
        return {"round": name, "n": 0, "missing": True}
    f = flags_for(verdicts)
    n = len(verdicts)
    one = [1] * n
    rates = {
        "pass_correct": sum(f["pass_correct"]) / n,
        "refusal_rate": sum(f["refusal"]) / n,
        "fabrication_rate_on_answered": (
            sum(f["fabricated"]) / sum(f["answered"]) if sum(f["answered"]) else None
        ),
    }
    with_gold = [v for v in verdicts if v.get("has_gold_chunk")]
    f_gold = flags_for(with_gold) if with_gold else {k: [] for k in f}
    lat = [v.get("latency_seconds") for v in verdicts if isinstance(v.get("latency_seconds"), (int, float))]
    summary_path = ROUNDS_ROOT / name / "round_summary_full.json"
    return {
        "round": name,
        "n": n,
        "referee_in_summary": (
            json.loads(summary_path.read_text(encoding="utf-8"))["settings"]["referee"]
            if summary_path.is_file()
            else None
        ),
        "counts": dict(Counter(v["verdict"] for v in verdicts)),
        "rates": {k: (round(v, 4) if v is not None else None) for k, v in rates.items()},
        "ci95": {
            "pass_correct": rate_ci(f["pass_correct"], one, seed=BOOTSTRAP_SEED),
            "refusal_rate": rate_ci(f["refusal"], one, seed=BOOTSTRAP_SEED),
            "fabrication_rate_on_answered": rate_ci(
                f["fabricated"], f["answered"], seed=BOOTSTRAP_SEED
            ),
        },
        "gold_in_window": {
            "n_items_with_gold": len(with_gold),
            "rate": round(sum(f_gold["gold_in_window"]) / len(with_gold), 4) if with_gold else None,
        },
        "latency_seconds": {
            "median": percentile(lat, 0.5),
            "p95": percentile(lat, 0.95),
            "max": round(max(lat), 2) if lat else None,
        },
    }


def pair_block(base: str, cand: str, verdicts_by_round: dict[str, list[dict]]) -> dict[str, Any]:
    bmap = {v["id"]: v for v in verdicts_by_round[base]}
    cmap = {v["id"]: v for v in verdicts_by_round[cand]}
    common = sorted(set(bmap) & set(cmap))
    b_rows = [bmap[i] for i in common]
    c_rows = [cmap[i] for i in common]
    bf, cf = flags_for(b_rows), flags_for(c_rows)
    one = [1] * len(common)

    b_pc, c_pc = bf["pass_correct"], cf["pass_correct"]
    discordant = {
        "b_base0_cand1": sum(1 for x, y in zip(b_pc, c_pc) if x == 0 and y == 1),
        "c_base1_cand0": sum(1 for x, y in zip(b_pc, c_pc) if x == 1 and y == 0),
    }
    return {
        "baseline": base,
        "candidate": cand,
        "n_common": len(common),
        "pass_correct_flip": {**discordant, "mcnemar": mcnemar_exact(discordant["b_base0_cand1"], discordant["c_base1_cand0"])},
        "paired_delta": {
            "pass_correct": paired_bootstrap(b_pc, c_pc, one, one, seed=BOOTSTRAP_SEED),
            "refusal_rate": paired_bootstrap(bf["refusal"], cf["refusal"], one, one, seed=BOOTSTRAP_SEED),
            "fabrication_rate_on_answered": paired_bootstrap(
                bf["fabricated"], cf["fabricated"], bf["answered"], cf["answered"], seed=BOOTSTRAP_SEED
            ),
        },
        "noise_note": "chênh ≤3 item trên n=100 nằm trong băng nhiễu T0 (data/loop/noise_floor.json)",
    }


def b_gemini_block(diag_dir: Path) -> dict[str, Any]:
    """CI cho cấu hình (b) của T1, đếm theo ID (gộp dòng trùng, giữ dòng hợp lệ đầu tiên)."""
    rows: dict[str, dict] = {}
    for row in load_jsonl(diag_dir / "rows.jsonl"):
        if row.get("error") or not (row.get("answer") or row.get("verdict")):
            continue
        rows.setdefault(row["id"], row)
    items = list(rows.values())
    if not items:
        return {"n": 0, "missing": True}
    f = flags_for(items)
    one = [1] * len(items)
    return {
        "config": "b_gemini_top6",
        "counting_rule": "gộp theo id, giữ dòng hợp lệ đầu tiên (như recount_dedup.py)",
        "n": len(items),
        "n_target": 30,
        "rates": {
            "pass_correct": round(sum(f["pass_correct"]) / len(items), 4),
            "refusal_rate": round(sum(f["refusal"]) / len(items), 4),
            "fabrication_rate_on_answered": (
                round(sum(f["fabricated"]) / sum(f["answered"]), 4) if sum(f["answered"]) else None
            ),
        },
        "ci95": {
            "pass_correct": rate_ci(f["pass_correct"], one, seed=BOOTSTRAP_SEED),
            "refusal_rate": rate_ci(f["refusal"], one, seed=BOOTSTRAP_SEED),
            "fabrication_rate_on_answered": rate_ci(f["fabricated"], f["answered"], seed=BOOTSTRAP_SEED),
        },
        "caveat": "pool = FAIL_OVERREFUSAL ∩ has_gold_chunk của r5 ⇒ 0/ n mặc định là đúng với Qwen; không ngoại suy ra 100 câu",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="T4: bảng số + CI cho báo cáo model.")
    ap.add_argument("--rounds", nargs="+", default=["r5", "r8", "r9", "r10"])
    ap.add_argument("--pairs", nargs="*", default=[], help="dạng candidate:baseline")
    ap.add_argument("--b-gemini", default=str(ROOT / "data" / "loop" / "diag" / "b_gemini_top6"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    verdicts_by_round = {r: load_jsonl(ROUNDS_ROOT / r / "verdicts_full.jsonl") for r in args.rounds}
    report = {
        "seed": BOOTSTRAP_SEED,
        "bootstrap_reps": 10000,
        "rounds": {r: round_block(r, v) for r, v in verdicts_by_round.items()},
        "pairs": [],
        "b_gemini_top6": b_gemini_block(Path(args.b_gemini)),
    }
    for spec in args.pairs:
        cand, _, base = spec.partition(":")
        if verdicts_by_round.get(cand) and verdicts_by_round.get(base):
            report["pairs"].append(pair_block(base, cand, verdicts_by_round))
        else:
            report["pairs"].append({"candidate": cand, "baseline": base, "missing": True})

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
