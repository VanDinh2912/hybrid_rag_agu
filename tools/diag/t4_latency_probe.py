# -*- coding: utf-8 -*-
"""T4a (mục 8) — đo VRAM đỉnh + p50/p95 latency của tầng sinh trên 20 câu THẬT.

Đề bài T4 chỉ đòi BÁO SỐ, không đặt ngưỡng cứng. Vì vậy script này không phán đạt/không
đạt; nó ghi lại đủ để người đọc tự đánh đổi:

* 20 câu lấy từ `data/loop/rounds/r5/full.jsonl` — câu hỏi và ngữ cảnh ĐÚNG như lượt chạy
  thật đã đưa vào generator (không tự dựng prompt giả ngắn hơn thực tế);
* cùng model/options mặc định của `QwenGenerator` (`temperature`, `num_ctx` trong
  `src/generator.py`), cache TẮT để mỗi câu đều là một lượt sinh thật;
* VRAM đỉnh lấy bằng `nvidia-smi` mẫu 0,4 giây trong suốt lượt đo (Ollama chạy ở tiến trình
  riêng nên `torch.cuda` không thấy được), có ghi cả mức nền trước khi đo để trừ đi;
* p50/p95 tính theo nearest-rank trên 20 mẫu; câu đầu thường gồm cả thời gian nạp model nên
  báo cáo thêm p50/p95 của 19 câu sau (đã trừ khởi động) — không che số xấu.

Chạy:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/t4_latency_probe.py \
        --out data/loop/diag/t4_latency_20q.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generator import QwenGenerator  # noqa: E402

DEFAULT_ROUND = ROOT / "data" / "loop" / "rounds" / "r5" / "full.jsonl"
N_QUESTIONS = 20


def load_questions(path: Path, n: int) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    picked = []
    for row in sorted(rows, key=lambda r: r["id"]):
        item = row.get("item") or {}
        contexts = [c for c in (row.get("contexts") or []) if c]
        if not item.get("raw_query") or not contexts:
            continue
        sources = row.get("sources") or []
        docs = []
        for i, content in enumerate(contexts[:4]):
            src = (sources[i] if i < len(sources) else {}) or {}
            docs.append({"content": content, "source": src.get("source") or "", "chunk_id": src.get("chunk_id")})
        picked.append({"id": row["id"], "query": item["raw_query"], "docs": docs})
        if len(picked) == n:
            break
    return picked


def gpu_used_mib() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (out.stdout or "").strip().splitlines()
    return int(text[0].strip()) if text and text[0].strip().isdigit() else None


class VramSampler(threading.Thread):
    def __init__(self, interval: float = 0.4):
        super().__init__(daemon=True)
        self.interval = interval
        self.samples: list[int] = []
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            value = gpu_used_mib()
            if value is not None:
                self.samples.append(value)
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
        self.join(timeout=5)


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank: p95 của 20 mẫu là mẫu thứ 19 (không nội suy) — không làm mượt đuôi."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return ordered[idx]


def run(round_path: Path, generator: QwenGenerator) -> dict:
    questions = load_questions(round_path, N_QUESTIONS)
    if len(questions) < N_QUESTIONS:
        raise SystemExit(f"chỉ có {len(questions)} câu đủ điều kiện trong {round_path}")

    baseline = gpu_used_mib()
    sampler = VramSampler()
    sampler.start()
    timings, rows = [], []
    started_all = time.time()
    try:
        for idx, q in enumerate(questions, 1):
            started = time.time()
            answer = generator.generate_answer(q["query"], q["docs"])
            seconds = round(time.time() - started, 3)
            timings.append(seconds)
            rows.append({
                "n": idx, "id": q["id"], "seconds": seconds,
                "prompt_chars": sum(len(d["content"]) for d in q["docs"]),
                "answer_chars": len(answer),
            })
            print(f"[{idx:02d}/{N_QUESTIONS}] {seconds:6.2f}s  {q['id']}", flush=True)
    finally:
        sampler.stop()
    total = round(time.time() - started_all, 1)

    peak = max(sampler.samples) if sampler.samples else None
    warm = timings[1:]
    return {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "round_source": str(round_path),
        "n_questions": len(timings),
        "model": generator.ollama_model,
        "temperature": generator.temperature,
        "cache": "off",
        "latency_seconds": {
            "total": total,
            "p50": round(percentile(timings, 50), 3),
            "p95": round(percentile(timings, 95), 3),
            "min": round(min(timings), 3),
            "max": round(max(timings), 3),
            "mean": round(statistics.fmean(timings), 3),
            "first_call_seconds": timings[0],
            "p50_excluding_first": round(percentile(warm, 50), 3),
            "p95_excluding_first": round(percentile(warm, 95), 3),
            "method": "nearest-rank trên 20 mẫu; cache TẮT; câu 1 gồm thời gian nạp model",
        },
        "vram_mib": {
            "baseline": baseline,
            "peak": peak,
            "delta_peak": (peak - baseline) if (peak is not None and baseline is not None) else None,
            "n_samples": len(sampler.samples),
            "method": "nvidia-smi memory.used, mẫu 0,4 s (Ollama là tiến trình riêng)",
        },
        "per_question": rows,
        "note": "chỉ BÁO SỐ — đề bài T4 không đặt ngưỡng cứng cho mục này",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="T4a: đo VRAM đỉnh + p50/p95 trên 20 câu thật.")
    parser.add_argument("--round-file", default=str(DEFAULT_ROUND))
    parser.add_argument("--model", default="", help="slug Ollama; rỗng = mặc định của QwenGenerator")
    parser.add_argument("--out", default="", help="file JSON; rỗng = chỉ in ra stdout")
    args = parser.parse_args()

    generator = QwenGenerator(ollama_model=args.model or None, use_cache=False)
    report = run(Path(args.round_file), generator)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[T4a] ghi: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
