"""Đo CHI PHÍ thật của reranker truy xuất (T5a) TRƯỚC khi bấm round r12.

Thiết kế đã chốt trong `data/loop/README.md` (mục T5) và KHÔNG được sửa vì số đo ở
đây. Script này chỉ trả lời ba câu hỏi về tiền:

1. tải `BAAI/bge-reranker-v2-m3` trên CPU tốn bao nhiêu giây và bao nhiêu RAM tiến trình;
2. một lượt chấm 20 cặp (query, chunk) hết bao nhiêu giây, qui mô thành bao nhiêu phút
   cho toàn bộ 811 item của pha truy xuất;
3. `RERANKER_MAX_LENGTH` 512 (đã đăng ký) so với 256 rẻ hơn bao nhiêu — chỉ ĐỂ BÁO,
   đổi 256 là đổi thiết kế nên phải xin duyệt, không âm thầm áp dụng.

Tham số lấy từ dữ liệu THẬT: pool 20 ứng viên do pipeline thật dựng trên đúng câu hỏi
của test bank. Mẫu chia hai tầng để số latency không bị thiên vị:

- `random`: 30 item lấy đều từ toàn bộ test bank (seed 20261024) — chi phí trung bình;
- `hard`:  30 item mà round r2 xếp chunk vàng ở hạng 7–12 (nhóm mà lever nhắm vào) —
  thường là chunk dài, tức trần chi phí.

Có ghi kèm một tín hiệu kỹ thuật (rerank kéo được bao nhiêu item `hard` vào cửa sổ),
nhưng **số chính thức về hiệu quả là round r12**, không phải tệp này.

Chạy:
    PYTHONIOENCODING=utf-8 python tools/diag/reranker_cost_probe.py --round r11 \
        --out data/loop/diag/reranker_cost.json
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SEED = 20261024
WINDOW = 6


# ------------------------------------------------------------------ đo bộ nhớ
class _PMemory(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def process_memory_mib() -> dict[str, Any]:
    """RAM của tiến trình (Windows: psapi; khác: resource). Không thêm dependency mới."""
    if os.name == "nt":
        try:
            counters = _PMemory()
            counters.cb = ctypes.sizeof(counters)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                mib = 2**20
                return {
                    "method": "psapi.GetProcessMemoryInfo",
                    "working_set_mib": round(counters.WorkingSetSize / mib, 1),
                    "peak_working_set_mib": round(counters.PeakWorkingSetSize / mib, 1),
                }
        except Exception as exc:  # noqa: BLE001
            return {"method": f"psapi lỗi: {type(exc).__name__}"}
    try:
        import resource

        mib = 1024 if sys.platform == "darwin" else 1024
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / mib
        return {"method": "resource.getrusage", "peak_working_set_mib": round(peak, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"method": f"không đo được ({type(exc).__name__})"}


def system_memory_mib() -> dict[str, Any]:
    if os.name != "nt":
        return {"method": "không áp dụng"}
    class _MS(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    info = _MS()
    info.dwLength = ctypes.sizeof(_MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info))
    mib = 2**20
    return {
        "method": "GlobalMemoryStatusEx",
        "memory_load_percent": info.dwMemoryLoad,
        "total_phys_mib": round(info.ullTotalPhys / mib, 1),
        "avail_phys_mib": round(info.ullAvailPhys / mib, 1),
    }


# ------------------------------------------------------------------ mẫu item
def hard_ids(rounds_root: Path, round_name: str, window: int = WINDOW) -> list[str]:
    """Item mà round `round_name` xếp chunk vàng ở hạng window+1 .. 2*window."""
    path = rounds_root / round_name / "verdicts_retrieval.jsonl"
    if not path.exists():
        return []
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rank = row.get("gold_rank_in_sources")
        if row.get("has_gold_chunk") and isinstance(rank, int) and window < rank <= 2 * window:
            ids.append(row["id"])
    return sorted(ids)


def pick_items(testset: list[dict], n: int, restrict: Optional[list[str]] = None) -> list[dict]:
    if restrict is not None:
        wanted = set(restrict)
        pool = [i for i in testset if i["id"] in wanted]
        rng = random.Random(SEED)
        rng.shuffle(pool)
        return pool[:n]
    rng = random.Random(SEED)
    pool = sorted(testset, key=lambda i: i["id"])
    step = max(1, len(pool) // max(1, n))
    picked = pool[::step][:n]
    rng.shuffle(picked)
    return picked


# ------------------------------------------------------------------ một lượt đo
def measure(pipeline, items: list[dict], *, pool: int, top_n: int, batch_size: int, label: str) -> dict[str, Any]:
    from src.retrieval.reranker import last_call, rerank_documents

    rows: list[dict[str, Any]] = []
    for item in items:
        query = item["raw_query"]
        docs = pipeline.retrieve(query, k=pool)
        started = time.perf_counter()
        ranked = rerank_documents(query, docs, pool=pool, top_n=top_n)
        seconds = time.perf_counter() - started
        gold = item.get("gold_chunk_id")
        before = [d.metadata.get("chunk_id") for d in docs[:top_n]]
        after = [d.metadata.get("chunk_id") for d in ranked]
        rows.append(
            {
                "id": item["id"],
                "family": item.get("family"),
                "n_candidates": len(docs),
                "pool_reranked": last_call.n_scored,
                "seconds": round(seconds, 3),
                "gold_in_window_before": gold in before,
                "gold_in_window_after": gold in after,
                "gold_rank_before": (before.index(gold) + 1) if gold in before else None,
                "gold_rank_after": (after.index(gold) + 1) if gold in after else None,
                "top_score": last_call.top_score,
                "bottom_score": last_call.bottom_score,
            }
        )
    times = [r["seconds"] for r in rows]
    ordered = sorted(times)
    n = len(ordered) or 1

    def pct(q: float) -> Optional[float]:
        if not ordered:
            return None
        pos = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
        return round(ordered[pos], 3)

    return {
        "label": label,
        "batch_size": batch_size,
        "pool": pool,
        "top_n": top_n,
        "n_items": len(rows),
        "mean_seconds_per_item": round(sum(times) / max(1, len(times)), 3),
        "median_seconds": pct(0.5),
        "p95_seconds": pct(0.95),
        "max_seconds": round(max(times), 3) if times else None,
        "projected_minutes_811_items": round(sum(times) / max(1, len(times)) * 811 / 60, 1),
        "recovered_hard_items": sum(1 for r in rows if r["gold_in_window_after"] and not r["gold_in_window_before"]),
        "lost_items": sum(1 for r in rows if r["gold_in_window_before"] and not r["gold_in_window_after"]),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", default="r11", help="round nền để đọc `hard ids` (verdicts_retrieval)")
    parser.add_argument("--testset", default=str(REPO_ROOT / "data" / "loop" / "testset_v1.jsonl"))
    parser.add_argument("--rounds-root", default=str(REPO_ROOT / "data" / "loop" / "rounds"))
    parser.add_argument("--n", type=int, default=30, help="số item mỗi tầng mẫu")
    parser.add_argument("--pool", type=int, default=20)
    parser.add_argument("--top-n", type=int, default=WINDOW)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--compare-max-length", type=int, default=256)
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "loop" / "diag" / "reranker_cost.json"))
    parser.add_argument("--dry-run", action="store_true", help="chỉ dựng mẫu, không nạp model")
    args = parser.parse_args()

    os.environ.setdefault("ENABLE_CLASSIFIER", "1")
    os.environ.setdefault("ROUTER_SOFT_FILTER", "1")
    os.environ.setdefault("ROUTER_FILTER_RANK_BONUS", "12")
    os.environ["ENABLE_RERANKER"] = "0"  # retrieve() phải trả pool RRF gốc; rerank gọi tường tính

    testset = [json.loads(l) for l in Path(args.testset).read_text(encoding="utf-8").splitlines() if l.strip()]
    hard = hard_ids(Path(args.rounds_root), args.round)
    samples = {
        "random": pick_items(testset, args.n),
        "hard_reranker_target": pick_items(testset, args.n, restrict=hard),
    }
    report: dict[str, Any] = {
        "registered_design": {
            "RERANKER_MODEL": os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            "RERANKER_DEVICE": os.getenv("RERANKER_DEVICE", "cpu"),
            "pool": args.pool,
            "window": args.top_n,
            "batch_size": args.batch_size,
            "max_length": os.getenv("RERANKER_MAX_LENGTH", "512"),
        },
        "seed": SEED,
        "baseline_round_for_hard_sample": args.round,
        "n_hard_candidates_in_disk": len(hard),
        "sample_sizes": {k: len(v) for k, v in samples.items()},
        "memory_before": {"process": process_memory_mib(), "system": system_memory_mib()},
        "note": (
            "Số này đo CHI PHÍ. Tín hiệu đúng/sai trong đây KHÔNG dùng để chỉnh thiết kế đã đăng ký; "
            "số hiệu quả chính thức là round r12 + cổng gate."
        ),
    }
    if args.dry_run:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2)[:1500])
        return 0

    from src.retrieval import reranker as reranker_module
    from tools.loop.run_round import build_pipeline

    started = time.perf_counter()
    pipeline = build_pipeline("offline_qwen")
    report["pipeline_seconds"] = round(time.perf_counter() - started, 2)

    load_started = time.perf_counter()
    model = reranker_module.get_reranker()
    report["model_load"] = {
        "seconds": round(time.perf_counter() - load_started, 2),
        "model": str(getattr(model, "model_card", {}).get("model", args.pool) if isinstance(getattr(model, "model_card", None), dict) else reranker_module.reranker_model_id()),
        "device": reranker_module.reranker_device(),
        "torch_threads": None,
    }
    try:
        import torch

        report["model_load"]["torch_threads"] = torch.get_num_threads()
        report["model_load"]["torch_version"] = torch.__version__
        report["model_load"]["torch_cuda_available"] = torch.cuda.is_available()
    except Exception as exc:  # noqa: BLE001
        report["model_load"]["torch_error"] = f"{type(exc).__name__}: {exc}"
    report["memory_after_load"] = {"process": process_memory_mib(), "system": system_memory_mib()}

    try:
        report["samples"] = {
            name: measure(pipeline, items, pool=args.pool, top_n=args.top_n, batch_size=args.batch_size, label=name)
            for name, items in samples.items()
        }
    finally:
        del model

    if args.compare_max_length:
        os.environ["RERANKER_MAX_LENGTH"] = str(args.compare_max_length)
        alt_model = reranker_module.get_reranker(force_reload=True)
        try:
            report[f"alt_max_length_{args.compare_max_length}"] = measure(
                pipeline,
                samples["random"],
                pool=args.pool,
                top_n=args.top_n,
                batch_size=args.batch_size,
                label=f"max_length={args.compare_max_length} (chỉ ĐỂ BÁO — đổi là đổi thiết kế)",
            )
            report["memory_after_alt_load"] = {"process": process_memory_mib(), "system": system_memory_mib()}
        finally:
            del alt_model
            os.environ.pop("RERANKER_MAX_LENGTH", None)

    report["memory_final"] = {"process": process_memory_mib(), "system": system_memory_mib()}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"model load: {report['model_load']}")
    print(f"memory sau load: {report['memory_after_load']}")
    for name, block in report.get("samples", {}).items():
        print(
            f"[{name}] n={block['n_items']} median={block['median_seconds']}s p95={block['p95_seconds']}s "
            f"=> dự kiến 811 item = {block['projected_minutes_811_items']} phút "
            f"(kéo lại {block['recovered_hard_items']}, mất {block['lost_items']})"
        )
    alt = report.get(f"alt_max_length_{args.compare_max_length}")
    if alt:
        print(f"[so sánh max_length={args.compare_max_length}] median={alt['median_seconds']}s => {alt['projected_minutes_811_items']} phút")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
