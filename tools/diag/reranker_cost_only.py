"""Đo BỔ SUNG (NGOÀI thiết kế đăng ký T5a): chi phí CHẤM ĐIỂM của reranker, KHÔNG nạp bge-m3.

Vì sao có script này
--------------------
Probe chính thức `tools/diag/reranker_cost_probe.py` cần pipeline (bge-m3 ~2,3 GB) VÀ
reranker (~2,3 GB) cùng lúc. Trên máy 16 GB, RAM trống lúc đo chỉ ~2,1–2,8 GB; lần chạy
24-10 22:16–23:05 mất **49 phút** mới nạp xong hai model và chưa chấm được cặp nào
(log `tmp/t5_cost_probe_20261024.log`). Script này chỉ nạp reranker rồi chấm 20 cặp
(query, chunk) thật, để trả lời đúng một câu: **một item 20 ứng viên tốn bao nhiêu giây CPU?**

KHÔNG dùng số ở đây làm số chính thức của T5a. Số chính thức là round r12 + cổng gate;
script này không đổi thiết kế đã đăng ký (model/device/pool/max_length/batch_size giữ nguyên).

Nguồn dữ liệu (chỉ đọc): `data/loop/rounds/r11/retrieval.jsonl`
  - query = `item.raw_query`; passage = `contexts` của chính item + chunk lấy từ pool
    context toàn round (seed 20261024) cho đủ 20 ứng viên.

Chạy:
    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -u tools/diag/reranker_cost_only.py
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SEED = 20261024


def system_memory_mib() -> dict[str, Any]:
    """RAM hệ thống; cùng cách đo với probe chính thức."""
    from tools.diag.reranker_cost_probe import system_memory_mib as _impl

    return _impl()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def build_passages(row: dict, pool: list[str], rng: random.Random, n: int) -> list[str]:
    own = [c for c in (row.get("contexts") or []) if c]
    chosen = list(own[:n])
    while len(chosen) < n:
        chosen.append(rng.choice(pool))
    return chosen[:n]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="r11")
    ap.add_argument("--n-items", type=int, default=30)
    ap.add_argument("--pool", type=int, default=20)
    ap.add_argument("--out", default="data/loop/diag/reranker_cost_only.json")
    args = ap.parse_args()

    rows = load_jsonl(REPO_ROOT / "data" / "loop" / "rounds" / args.round / "retrieval.jsonl")
    rows = [r for r in rows if r.get("item") and r.get("contexts")]
    rng = random.Random(SEED)
    rng.shuffle(rows)
    rows = rows[: args.n_items]
    all_chunks = [c for r in load_jsonl(REPO_ROOT / "data" / "loop" / "rounds" / args.round / "retrieval.jsonl") for c in (r.get("contexts") or []) if c]

    from src.retrieval.reranker import get_reranker, reranker_status, score_pairs

    report: dict[str, Any] = {
        "kind": "BỔ SUNG — không phải probe đăng ký trước, không dùng để chốt T5a",
        "source_round": args.round,
        "seed": SEED,
        "n_items": len(rows),
        "pool": args.pool,
        "reranker_env": {
            "model": os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            "device": os.getenv("RERANKER_DEVICE", "cpu"),
            "max_length": os.getenv("RERANKER_MAX_LENGTH", "512"),
            "batch_size": os.getenv("RERANKER_BATCH_SIZE", "4"),
        },
        "memory_before": system_memory_mib(),
    }

    started = time.perf_counter()
    model = get_reranker()
    report["load_seconds"] = round(time.perf_counter() - started, 2)
    report["status_after_load"] = reranker_status()
    report["memory_after_load"] = system_memory_mib()

    per_item: list[dict[str, Any]] = []
    seconds: list[float] = []
    print(f"[load] {report['load_seconds']}s | {report['memory_after_load']}")
    for idx, row in enumerate(rows, 1):
        query = (row.get("item") or {}).get("raw_query") or ""
        passages = build_passages(row, all_chunks, rng, args.pool)
        t0 = time.perf_counter()
        scores = score_pairs(model, query, passages)
        elapsed = time.perf_counter() - t0
        if len(scores) != len(passages):
            raise SystemExit(f"lệch số điểm: {len(scores)} != {len(passages)}")
        seconds.append(elapsed)
        per_item.append({"id": row["id"], "family": (row.get("item") or {}).get("family"),
                         "seconds": round(elapsed, 3), "n_pairs": len(passages),
                         "chars": sum(len(p) for p in passages)})
        if idx % 5 == 0 or idx == len(rows):
            print(f"[{idx}/{len(rows)}] {row['id']} {elapsed:.2f}s")

    report["per_item"] = per_item
    report["seconds"] = {
        "min": round(min(seconds), 3),
        "median": round(statistics.median(seconds), 3),
        "mean": round(statistics.fmean(seconds), 3),
        "p95": round(percentile(seconds, 0.95), 3),
        "max": round(max(seconds), 3),
        "total_seconds": round(sum(seconds), 2),
    }
    mean = statistics.fmean(seconds)
    report["extrapolation_811_items"] = {
        "minutes": round(mean * 811 / 60, 1),
        "basis": "mean giây/item × 811; KHÔNG gồm thời gian nạp model và pipeline",
    }
    report["memory_after_scoring"] = system_memory_mib()
    out = REPO_ROOT / args.out
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("load_seconds", "seconds", "extrapolation_811_items")},
                     ensure_ascii=False, indent=2))
    print(f"[out] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
