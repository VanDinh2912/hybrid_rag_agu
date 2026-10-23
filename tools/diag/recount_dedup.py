"""Đếm lại summary của một cấu hình ablation với QUY TẮC GỘP DÒNG THEO id.

Vì sao cần: `data/loop/diag/b_gemini_top6/rows.jsonl` có 2 id xuất hiện HAI lần
(O10235702435549, T24199159682252) do hai tiến trình (b) chạy chồng nhau trong đêm
(mỗi tiến trình tính tập `todo` từ trạng thái tệp lúc nó khởi động). `summarize()` gốc
đếm theo DÒNG ⇒ n=9 trong khi số item thật chỉ 7, và hai item bị tính hai lần với hai
câu trả lời khác nhau (generator ngẫu nhiên).

Quy tắc gộp: giữ dòng HỢP LỆ đầu tiên theo id (thứ tự tệp), loại các dòng về sau trùng id.
Dòng error không bao giờ được giữ. Định nghĩa chỉ số sao chép nguyên văn từ
`tools/diag/ablation_generation.py::summarize` (refusal/answered/pass/fabrication/CI).

TỰ KIỂM CHỨNG: chạy với a_oracle_qwen và c_gold_window_qwen — hai cấu hình này không có
id trùng ⇒ kết quả phải KHỚP CHÍNH XÁC với `summary.json` đã commit. Đó là bằng chứng
script không đổi định nghĩa số liệu, chỉ đổi cách đếm dòng trùng.

Không gọi model, không ghi đè `summary.json` (ghi sang `summary_dedup.json`).

Cách chạy:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/recount_dedup.py --config a_oracle_qwen
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/recount_dedup.py --config b_gemini_top6
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.diag.ablation_generation import DIAG_DIR, load_jsonl  # noqa: E402
from tools.loop import verify  # noqa: E402
from tools.loop.noise_floor import BOOTSTRAP_SEED, rate_ci  # noqa: E402


def dedup_first_per_id(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Giữ dòng hợp lệ đầu tiên mỗi id; trả về (dòng đã gộp, danh sách id bị gộp)."""
    kept: list[dict] = []
    seen: set[str] = set()
    collapsed: list[str] = []
    for row in rows:
        if row.get("error"):
            continue
        if row["id"] in seen:
            collapsed.append(row["id"])
            continue
        seen.add(row["id"])
        kept.append(row)
    return kept, collapsed


def block(subset: list[dict]) -> dict:
    """Nguyên văn định nghĩa chỉ số của summarize() trong ablation_generation.py."""
    decided = [r for r in subset if r.get("verdict") != "PENDING_GENERATION"]
    if not decided:
        return {"n": 0}
    answered = [r for r in decided if not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0]
    return {
        "n": len(decided),
        "n_answered": len(answered),
        "refusal_rate": round(sum(1 for r in decided if r.get("is_refusal")) / len(decided), 4),
        "pass_correct": sum(1 for r in decided if r.get("verdict") == "PASS_CORRECT"),
        "pass_correct_rate": round(
            sum(1 for r in decided if r.get("verdict") == "PASS_CORRECT") / len(decided), 4),
        "pass_any_rate": round(
            sum(1 for r in decided if r.get("verdict") in verify.PASS_VERDICTS) / len(decided), 4),
        "fabrication_rate_on_answered": (
            round(sum(1 for r in answered if r.get("unsupported")) / len(answered), 4)
            if answered else None),
        "fabricated_items": sum(1 for r in decided if r.get("verdict") == "FAIL_FABRICATED"),
        "hallucinated_on_unanswerable": sum(
            1 for r in decided if r.get("verdict") == "FAIL_HALLUCINATED_ON_UNANSWERABLE"),
        "overrefusal": sum(1 for r in decided if r.get("verdict") == "FAIL_OVERREFUSAL"),
        "verdict_counts": dict(collections.Counter(r.get("verdict") for r in decided)),
        "median_latency": (
            round(sorted(r.get("latency_seconds") or 0 for r in decided)[len(decided) // 2], 2)
            if decided else None),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--write", default="summary_dedup.json")
    ap.add_argument("--compare-with-summary", action="store_true",
                    help="đối chiếu `overall` với summary.json đã commit (khớp ⇒ exit 0)")
    args = ap.parse_args()

    out_dir = DIAG_DIR / args.config
    rows = load_jsonl(out_dir / "rows.jsonl")
    deduped, collapsed = dedup_first_per_id(rows)
    settings = json.loads((out_dir / "settings.json").read_text(encoding="utf-8")) \
        if (out_dir / "settings.json").exists() else {}

    summary = {
        "config": args.config,
        "referee": settings.get("referee"),
        "env": settings.get("env"),
        "counting_rule": "giữ dòng hợp lệ ĐẦU TIÊN mỗi id (gộp dòng trùng id do tiến trình chồng nhau)",
        "n_rows_in_file": len(rows),
        "n_valid_rows_in_file": len([r for r in rows if not r.get("error")]),
        "n_items_deduped": len(deduped),
        "collapsed_duplicate_ids": sorted(set(collapsed)),
        "n_error_rows": len([r for r in rows if r.get("error")]),
        "overall": block(deduped),
        "overall_answerable80": block([r for r in deduped if r.get("has_gold_chunk")]),
        "by_family": {fam: block([r for r in deduped if r.get("family") == fam])
                      for fam in sorted({r.get("family") for r in deduped if r.get("family")})},
    }

    subset = [r for r in deduped if r.get("has_gold_chunk")]
    if subset:
        pc = [1 if r.get("verdict") == "PASS_CORRECT" else 0 for r in subset]
        rf = [1 if r.get("is_refusal") else 0 for r in subset]
        fab = [1 if (not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0
                     and r.get("unsupported")) else 0 for r in subset]
        fden = [1 if (not r.get("is_refusal") and (r.get("answer_chars") or 0) > 0) else 0
                for r in subset]
        summary["ci95_answerable"] = {
            "pass_correct": rate_ci(pc, [1] * len(subset), seed=BOOTSTRAP_SEED),
            "refusal_rate": rate_ci(rf, [1] * len(subset), seed=BOOTSTRAP_SEED),
            "fabrication_rate_on_answered": rate_ci(fab, fden, seed=BOOTSTRAP_SEED),
        }

    (out_dir / args.write).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{args.config}] dòng trong tệp={summary['n_rows_in_file']} "
          f"hợp lệ={summary['n_valid_rows_in_file']} sau gộp={summary['n_items_deduped']} "
          f"id trùng={summary['collapsed_duplicate_ids']}")
    print(json.dumps(summary["overall"], ensure_ascii=False))

    if args.compare_with_summary:
        old = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
        same = old.get("overall") == summary["overall"]
        print(f"[đối chiếu] overall trùng khớp với summary.json: {same}")
        if not same:
            print("  cũ  :", json.dumps(old.get("overall"), ensure_ascii=False))
            print("  mới :", json.dumps(summary["overall"], ensure_ascii=False))
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
