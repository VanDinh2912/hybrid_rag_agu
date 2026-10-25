"""So ghép cặp OFF vs ON của reranker + kiểm tái lập round đã đóng (T5, 25-10).

Đây là DỤNG CỤ ĐỌC: không đổi pipeline, không cờ env, không ghi vào `data/loop/rounds/`.
Nó chỉ đọc `retrieval.jsonl` / `verdicts_retrieval.jsonl` của bốn round và ghi MỘT file JSON
dưới `data/loop/diag/` (hoặc đường dẫn `--out`).

Vì sao viết mới thay vì chỉ dùng `tools/diag/bonus_paired.py`
------------------------------------------------------------
`bonus_paired` chốt cứng hai chỉ báo của pha sinh (PASS_CORRECT / gold@6 + lý do hạng 7-12).
Nhiệm vụ T5 cần hai chỉ báo pha TRUY XUẤT — `gold@6` (mẫu số = item có `has_gold_chunk`) và
`FAIL_RETRIEVAL` (mẫu số = toàn bộ item) — tách theo 12 family, và cần đối chiếu từng item với
round đã đóng để bắt lỗi tái lập trước khi diễn giải chênh lệch.

Kiểm định (tái dùng, KHÔNG chép lại công thức)
---------------------------------------------
- `mcnemar_exact` và `paired_bootstrap` của `tools/loop/noise_floor.py` (seed 20261023).
- Định nghĩa `gold_in_top_k` / `has_gold_chunk` lấy nguyên từ verdict do `tools/loop/verify.py`
  sinh ra; không đọc trường vàng của testset ở đây.

Cách đọc
--------
1. `reproducibility.*.match_scored_fields` phải bằng true (verdict, gold, sources TOP-6,
   contexts khớp từng item) thì hai round mới được coi là CÙNG cấu hình. Hạng sâu của
   `sources` (retrieve_k) được báo riêng ở `same_sources_full`: tie-break có thể đổi thứ tự
   ở hạng >6 mà không đổi cửa sổ chấm — đó là ghi chú tái lập, không phải tín hiệu lever.
2. `stats.gold_at_6` / `stats.fail_retrieval` là hiệu ứng ON - OFF ghép cặp trên CÙNG item id.
3. `by_family` chỉ để định vị nơi mất/được; family có `n_gold < 10` bị đánh cờ `mẫu_quá_nhỏ`
   (ngưỡng MIN_FAMILY_N của T0), không dùng để tuyên bố thắng/thua.

Chạy:
    python tools/diag/reranker_paired_family.py \
        --baseline r14_repro_off --candidate r15_repro_on \
        --closed-baseline r11 --closed-candidate r12
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.loop import gate  # noqa: E402
from tools.loop.noise_floor import (  # noqa: E402
    BOOTSTRAP_REPS,
    BOOTSTRAP_SEED,
    MIN_FAMILY_N,
    mcnemar_exact,
    paired_bootstrap,
    rate_ci,
)

FAIL = "FAIL_RETRIEVAL"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _source_key(row: dict) -> list[tuple[str, Any]]:
    return [
        (str((s or {}).get("source") or ""), (s or {}).get("chunk_id"))
        for s in (row.get("sources") or [])
    ]


def load_merged(round_dir: Path) -> dict[str, dict]:
    """Ghép `retrieval.jsonl` (sources/contexts) với `verdicts_retrieval.jsonl` (verdict/gold).

    Bản đầu chỉ đọc verdict — file verdict KHÔNG chứa `sources`/`contexts`, nên phép kiểm
    tái lập báo "811/811 sources" một cách vô nghĩa (hai danh sách rỗng luôn bằng nhau).
    Đo tái lập phải đọc đúng nơi dữ liệu được ghi.
    """
    retrieval = {r["id"]: r for r in _read_jsonl(round_dir / "retrieval.jsonl") if r.get("id")}
    verdicts = {r["id"]: r for r in _read_jsonl(round_dir / "verdicts_retrieval.jsonl") if r.get("id")}
    merged: dict[str, dict] = {}
    for rid, row in verdicts.items():
        full = retrieval.get(rid, {})
        merged[rid] = {
            **row,
            "sources": full.get("sources") or [],
            "contexts": full.get("contexts") or [],
            "normalized_query": full.get("normalized_query"),
        }
    return merged


def compare_rounds(
    baseline: dict[str, dict],
    candidate: dict[str, dict],
    *,
    baseline_name: str,
    candidate_name: str,
    top_k: int = 6,
) -> dict[str, Any]:
    """Đối chiếu TỪNG item của hai round (tái lập), trả về số khớp và danh sách lệch.

    Tách hai thang: `sources_top_k` (cửa sổ được dùng để chấm) và `sources_full` (toàn bộ
    danh sách retrieve_k). Hạng sâu có thể đổi thứ tự do tie-break của tầng truy xuất mà
    KHÔNG đổi cửa sổ/metric — phải báo riêng, không gộp thành "tái lập hoàn hảo".
    """
    common = sorted(set(baseline) & set(candidate))
    only_b = sorted(set(baseline) - set(candidate))
    only_c = sorted(set(candidate) - set(baseline))
    mismatches: list[dict[str, Any]] = []
    same_verdict = same_gold = same_sources = same_contexts = same_top_sources = 0
    for rid in common:
        br, cr = baseline[rid], candidate[rid]
        v_ok = br.get("verdict") == cr.get("verdict")
        g_ok = bool(br.get("gold_in_top_k")) == bool(cr.get("gold_in_top_k")) and bool(
            br.get("has_gold_chunk")
        ) == bool(cr.get("has_gold_chunk"))
        sb, sc = _source_key(br), _source_key(cr)
        s_ok = sb == sc
        t_ok = sb[:top_k] == sc[:top_k]
        c_ok = (br.get("contexts") or []) == (cr.get("contexts") or [])
        same_verdict += v_ok
        same_gold += g_ok
        same_sources += s_ok
        same_top_sources += t_ok
        same_contexts += c_ok
        if not (v_ok and g_ok and s_ok and c_ok):
            mismatches.append(
                {
                    "id": rid,
                    "family": br.get("family"),
                    "verdict": [br.get("verdict"), cr.get("verdict")],
                    "gold_in_top_k": [br.get("gold_in_top_k"), cr.get("gold_in_top_k")],
                    "sources_equal": s_ok,
                    "sources_top_k_equal": t_ok,
                    "contexts_equal": c_ok,
                    "first_source_diff_rank": (
                        next(
                            (
                                k + 1
                                for k, (x, y) in enumerate(zip(sb, sc))
                                if x != y
                            ),
                            min(len(sb), len(sc)) + 1 if len(sb) != len(sc) else None,
                        )
                    ),
                }
            )
    n = len(common)
    return {
        "baseline": baseline_name,
        "candidate": candidate_name,
        "n_common": n,
        "only_in_baseline": len(only_b),
        "only_in_candidate": len(only_c),
        "same_verdict": same_verdict,
        "same_gold_flag": same_gold,
        "same_sources_top_k": same_top_sources,
        "same_sources_full": same_sources,
        "same_contexts": same_contexts,
        "per_item_exact": round((n - len(mismatches)) / n, 6) if n else None,
        "n_mismatched_items": len(mismatches),
        "mismatched_items": mismatches[:40],
        "match_all_fields": same_verdict == n and same_gold == n and same_sources == n and same_contexts == n,
        "match_scored_fields": (
            same_verdict == n and same_gold == n and same_top_sources == n and same_contexts == n
        ),
    }


def _gold_flags(rows: list[dict]) -> tuple[list[int], list[int]]:
    flags = [1 if r.get("gold_in_top_k") else 0 for r in rows]
    den = [1 if r.get("has_gold_chunk") else 0 for r in rows]
    return flags, den


def _fail_flags(rows: list[dict]) -> tuple[list[int], list[int]]:
    flags = [1 if r.get("verdict") == FAIL else 0 for r in rows]
    den = [1] * len(rows)
    return flags, den


def _one_stat(name: str, xb: list[int], xc: list[int], db: list[int], dc: list[int]) -> dict[str, Any]:
    b = sum(1 for x, y in zip(xb, xc) if x == 0 and y == 1)  # baseline sai, candidate đúng
    c = sum(1 for x, y in zip(xb, xc) if x == 1 and y == 0)
    nb, nc = sum(xb), sum(xc)
    denb, denc = sum(db), sum(dc)
    return {
        name: {
            "baseline_count": nb,
            "candidate_count": nc,
            "baseline_denominator": denb,
            "candidate_denominator": denc,
            "baseline_rate": round(nb / denb, 4) if denb else None,
            "candidate_rate": round(nc / denc, 4) if denc else None,
            "diff_candidate_minus_baseline": (
                round(nc / denc - nb / denb, 4) if denb and denc else None
            ),
            "mcnemar_exact": mcnemar_exact(b, c),
            "paired_bootstrap_diff": paired_bootstrap(xb, xc, db, dc),
            "baseline_rate_ci95": rate_ci(xb, db),
            "candidate_rate_ci95": rate_ci(xc, dc),
        }
    }


def stats_for_pair(
    baseline: dict[str, dict], candidate: dict[str, dict]
) -> tuple[dict[str, Any], list[dict], list[dict]]:
    # Giữ THỨ TỰ DÒNG của baseline (không sort id): bootstrap resample theo chỉ số nên thứ tự
    # quyết định các lượt rút; đổi thứ tự làm CI lệch vài phần nghìn so với số đã công bố.
    common = [rid for rid in baseline if rid in candidate]
    b_rows = [baseline[i] for i in common]
    c_rows = [candidate[i] for i in common]
    # gold@6 chỉ ghép trên item CÓ chunk vàng (mẫu số 700, đúng gate.py và số đã công bố);
    # FAIL_RETRIEVAL ghép trên toàn bộ item chung (811).
    b_gold = [r for r in b_rows if r.get("has_gold_chunk")]
    c_gold = [r for r in c_rows if r.get("has_gold_chunk")]
    gb, gd = _gold_flags(b_gold)
    gc, gcd = _gold_flags(c_gold)
    fb, fd = _fail_flags(b_rows)
    fc, fcd = _fail_flags(c_rows)
    stats: dict[str, Any] = {}
    stats.update(_one_stat("gold_at_6", gb, gc, gd, gcd))
    stats.update(_one_stat("fail_retrieval", fb, fc, fd, fcd))
    return {"common_items": len(common), "stats": stats}, b_rows, c_rows


def by_family(b_rows: list[dict], c_rows: list[dict]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for br, cr in zip(b_rows, c_rows):
        groups[str(br.get("family") or "?")].append((br, cr))
    out: dict[str, dict[str, Any]] = {}
    for fam in sorted(groups):
        pairs = groups[fam]
        n = len(pairs)
        gold_pairs = [(br, cr) for br, cr in pairs if br.get("has_gold_chunk")]
        ng = len(gold_pairs)
        gb = sum(1 for br, _ in gold_pairs if br.get("gold_in_top_k"))
        gc = sum(1 for _, cr in gold_pairs if cr.get("gold_in_top_k"))
        fb = sum(1 for br, _ in pairs if br.get("verdict") == FAIL)
        fc = sum(1 for _, cr in pairs if cr.get("verdict") == FAIL)
        b = sum(1 for br, cr in gold_pairs if not br.get("gold_in_top_k") and cr.get("gold_in_top_k"))
        c = sum(1 for br, cr in gold_pairs if br.get("gold_in_top_k") and not cr.get("gold_in_top_k"))
        out[fam] = {
            "n": n,
            "n_gold": ng,
            "gold_at_6": {
                "baseline": round(gb / ng, 4) if ng else None,
                "candidate": round(gc / ng, 4) if ng else None,
                "diff": round(gc / ng - gb / ng, 4) if ng else None,
                "gained_b_candidate_only": b,
                "lost_b_baseline_only": c,
                "mcnemar_exact": mcnemar_exact(b, c),
                "mẫu_quá_nhỏ": ng < MIN_FAMILY_N,
            },
            "fail_retrieval": {
                "baseline_count": fb,
                "candidate_count": fc,
                "baseline_rate": round(fb / n, 4),
                "candidate_rate": round(fc / n, 4),
                "diff": round((fc - fb) / n, 4),
                "mẫu_quá_nhỏ": n < MIN_FAMILY_N,
            },
        }
    return out


def verdict_matrix(b_rows: list[dict], c_rows: list[dict]) -> dict[str, dict[str, int]]:
    m: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for br, cr in zip(b_rows, c_rows):
        m[str(br.get("verdict"))][str(cr.get("verdict"))] += 1
    return {k: dict(v) for k, v in m.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="So ghép cặp reranker OFF/ON + kiểm tái lập.")
    parser.add_argument("--baseline", default="r14_repro_off")
    parser.add_argument("--candidate", default="r15_repro_on")
    parser.add_argument("--closed-baseline", default="r11")
    parser.add_argument("--closed-candidate", default="r12")
    parser.add_argument("--rounds-root", default=str(REPO_ROOT / "data" / "loop" / "rounds"))
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "loop" / "diag" / "reranker_paired_family.json"))
    args = parser.parse_args()

    root = Path(args.rounds_root)
    base = load_merged(root / args.baseline)
    cand = load_merged(root / args.candidate)
    closed_b = load_merged(root / args.closed_baseline)
    closed_c = load_merged(root / args.closed_candidate)

    repro_off = compare_rounds(
        closed_b, base, baseline_name=args.closed_baseline, candidate_name=args.baseline
    )
    repro_on = compare_rounds(
        closed_c, cand, baseline_name=args.closed_candidate, candidate_name=args.candidate
    )
    agg, b_rows, c_rows = stats_for_pair(base, cand)

    def summary_counts(rows: dict[str, dict]) -> dict[str, Any]:
        gold = [r for r in rows.values() if r.get("has_gold_chunk")]
        return {
            "n_items": len(rows),
            "n_gold_items": len(gold),
            "gold_in_top_k": sum(1 for r in gold if r.get("gold_in_top_k")),
            "gold_at_6": round(sum(1 for r in gold if r.get("gold_in_top_k")) / len(gold), 4) if gold else None,
            "fail_retrieval": sum(1 for r in rows.values() if r.get("verdict") == FAIL),
            "fail_retrieval_rate": round(
                sum(1 for r in rows.values() if r.get("verdict") == FAIL) / len(rows), 4
            ) if rows else None,
            "verdict_counts": dict(Counter(r.get("verdict") for r in rows.values())),
        }

    result = {
        "task": "T5 (kiểm thử) — OFF vs ON reranker, pha truy xuất, ghép cặp + tách family",
        "generated_from": {
            "baseline": str(root / args.baseline / "verdicts_retrieval.jsonl"),
            "candidate": str(root / args.candidate / "verdicts_retrieval.jsonl"),
            "closed_baseline": str(root / args.closed_baseline / "verdicts_retrieval.jsonl"),
            "closed_candidate": str(root / args.closed_candidate / "verdicts_retrieval.jsonl"),
        },
        "rounds": {
            "baseline": args.baseline,
            "candidate": args.candidate,
            "closed_baseline": args.closed_baseline,
            "closed_candidate": args.closed_candidate,
            "summaries": {
                "baseline": summary_counts(base),
                "candidate": summary_counts(cand),
                "closed_baseline": summary_counts(closed_b),
                "closed_candidate": summary_counts(closed_c),
            },
        },
        "reproducibility": {"off_vs_closed": repro_off, "on_vs_closed": repro_on},
        "headline": agg["stats"],
        "by_family": by_family(b_rows, c_rows),
        "transition_matrix_baseline_rows__candidate_columns": verdict_matrix(b_rows, c_rows),
        "bootstrap": {"reps": BOOTSTRAP_REPS, "seed": BOOTSTRAP_SEED,
                      "method": "paired item-resample, percentile CI"},
        "how_to_read": (
            "Điều kiện diễn giải delta là `reproducibility.*.match_scored_fields` = true: verdict, "
            "gold_in_top_k, sources TOP-6 và contexts phải khớp từng item với round đã đóng. "
            "`match_all_fields` kiểm cả hạng sâu của `sources` (retrieve_k); hạng sâu có thể đổi "
            "thứ tự do tie-break mà không đổi cửa sổ/metric — ghi riêng, không tính là lỗi tái lập."
        ),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[reranker_paired] wrote {out}")
    print(
        f"[repro] OFF {repro_off['same_verdict']}/{repro_off['n_common']} verdict, "
        f"sources top6 {repro_off['same_sources_top_k']}/{repro_off['n_common']}, "
        f"sources full {repro_off['same_sources_full']}/{repro_off['n_common']}, "
        f"contexts {repro_off['same_contexts']}/{repro_off['n_common']} | "
        f"ON {repro_on['same_verdict']}/{repro_on['n_common']} verdict, "
        f"sources top6 {repro_on['same_sources_top_k']}/{repro_on['n_common']}, "
        f"sources full {repro_on['same_sources_full']}/{repro_on['n_common']}, "
        f"contexts {repro_on['same_contexts']}/{repro_on['n_common']}"
    )
    for key in ("gold_at_6", "fail_retrieval"):
        s = agg["stats"][key]
        print(
            f"[{key}] {s['baseline_rate']} -> {s['candidate_rate']} "
            f"(diff {s['diff_candidate_minus_baseline']}, "
            f"p={s['mcnemar_exact']['p_two_sided']}, "
            f"CI {s['paired_bootstrap_diff']['ci95_percentile']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
