"""T1(b): trạng thái từng id đã đăng ký + kiểm tra mẫu lệch.

Đọc (chỉ đọc):
  - data/loop/diag/b_gemini_top6/sample_ids.json   (30 id đăng ký trước)
  - data/loop/diag/b_gemini_top6/rows.jsonl        (dòng hợp lệ + dòng lỗi)
  - data/loop/rounds/r5/full.jsonl                 (family + độ dài ngữ cảnh + hạng vàng)

Ghi:
  - data/loop/diag/b_gemini_top6/id_status.json

Quy ước:
  - id "hợp lệ" = có dòng không có trường error, giữ dòng ĐẦU TIÊN (như recount_dedup).
  - id "lỗi"    = chỉ có dòng error; lý do lấy từ error của dòng cuối.
  - id "không có dòng" = chưa từng gọi.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAG = ROOT / "data" / "loop" / "diag" / "b_gemini_top6"
R5 = ROOT / "data" / "loop" / "rounds" / "r5" / "full.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize_lengths(values: list[int]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "mean": round(statistics.fmean(values), 1),
        "max": max(values),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="id_status.json")
    args = ap.parse_args()

    sample = json.loads((DIAG / "sample_ids.json").read_text(encoding="utf-8"))
    ids = sample["ids"]
    rows = load_jsonl(DIAG / "rows.jsonl")
    r5_rows = load_jsonl(R5)
    r5 = {r["id"]: r for r in r5_rows}

    first_valid: dict[str, dict] = {}
    last_error: dict[str, dict] = {}
    n_rows_for: dict[str, int] = {}
    for r in rows:
        rid = r.get("id")
        n_rows_for[rid] = n_rows_for.get(rid, 0) + 1
        if r.get("error"):
            last_error[rid] = r
        elif rid not in first_valid:
            first_valid[rid] = r

    r5_order = {r["id"]: i for i, r in enumerate(r5_rows)}

    per_id = []
    for rid in ids:
        base = r5.get(rid)
        item = (base or {}).get("item") or {}
        contexts = (base or {}).get("contexts") or []
        gold_rank = None
        gold_id = item.get("gold_chunk_id")
        for src in (base or {}).get("sources") or []:
            if gold_id is not None and src.get("chunk_id") == gold_id:
                gold_rank = src.get("rank")
                break
        rec = {
            "id": rid,
            "family": item.get("family"),
            "contexts_chars": sum(len(c) for c in contexts),
            "n_contexts": len(contexts),
            "gold_rank_in_sources": gold_rank,
            "r5_order": r5_order.get(rid),
            "status": "valid" if rid in first_valid else ("error" if rid in last_error else "no_row"),
            "n_rows": n_rows_for.get(rid, 0),
        }
        if rid in first_valid:
            rec["verdict"] = first_valid[rid].get("verdict")
            rec["latency_seconds"] = first_valid[rid].get("latency_seconds")
            rec["cached_row"] = first_valid[rid].get("latency_seconds", 999) < 30
        if rid in last_error:
            err = last_error[rid]["error"]
            rec["error_kind"] = "PerDay" if "PerDay" in err else err.split(":")[0]
            # giữ phần "Please retry in ..." để biết mốc reset
            marker = "Please retry in"
            idx = err.find(marker)
            rec["error_retry_hint"] = err[idx:idx + 60] if idx >= 0 else None
        per_id.append(rec)

    valid = [r for r in per_id if r["status"] == "valid"]
    missing = [r for r in per_id if r["status"] != "valid"]

    def dist(rs: list[dict], key: str) -> dict:
        out: dict[str, int] = {}
        for r in rs:
            out[str(r.get(key))] = out.get(str(r.get(key)), 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    report = {
        "n_registered": len(ids),
        "n_valid": len(valid),
        "n_missing": len(missing),
        "missing_reasons": dist(missing, "error_kind"),
        "family_counts_registered": sample.get("family_counts"),
        "family_counts_valid": dist(valid, "family"),
        "family_counts_missing": dist(missing, "family"),
        "family_valid_share": {
            f: {
                "valid": sum(1 for r in valid if r["family"] == f),
                "missing": sum(1 for r in missing if r["family"] == f),
            }
            for f in sorted({r["family"] for r in per_id if r["family"]})
        },
        "context_chars_valid": summarize_lengths([r["contexts_chars"] for r in valid]),
        "context_chars_missing": summarize_lengths([r["contexts_chars"] for r in missing]),
        "context_chars_all": summarize_lengths([r["contexts_chars"] for r in per_id]),
        "r5_order_valid": summarize_lengths([r["r5_order"] for r in valid if r["r5_order"] is not None]),
        "r5_order_missing": summarize_lengths([r["r5_order"] for r in missing if r["r5_order"] is not None]),
        "gold_rank_valid": summarize_lengths([r["gold_rank_in_sources"] for r in valid if r["gold_rank_in_sources"] is not None]),
        "gold_rank_missing": summarize_lengths([r["gold_rank_in_sources"] for r in missing if r["gold_rank_in_sources"] is not None]),
        "per_id": per_id,
    }
    (DIAG / args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[t1b] đăng ký={len(ids)} hợp lệ={len(valid)} thiếu={len(missing)} lý do={report['missing_reasons']}")
    print(f"[t1b] family valid={report['family_counts_valid']}")
    print(f"[t1b] family missing={report['family_counts_missing']}")
    print(f"[t1b] contexts_chars valid={report['context_chars_valid']}")
    print(f"[t1b] contexts_chars missing={report['context_chars_missing']}")
    for r in per_id:
        if r["status"] != "valid":
            print(f"  - {r['id']} {r['family']} {r['status']} rows={r['n_rows']} "
                  f"ctx={r['contexts_chars']} gold_rank={r['gold_rank_in_sources']} "
                  f"err={r.get('error_kind')} {r.get('error_retry_hint') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
