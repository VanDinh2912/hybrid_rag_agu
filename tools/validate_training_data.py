#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Kiểm định bộ dữ liệu huấn luyện trong data/training/.

Kiểm tra:
- JSONL đọc được, đủ trường bắt buộc, không có chuỗi rỗng.
- Train/val/seed không trùng khóa (task, câu hỏi) và không rò rỉ benchmark.
- Câu trả lời không chứa "None"/"null" do lỗi nội suy.
- Với corpus_identification: các con số trong đáp án phải xuất hiện trong đoạn trích.
- Thống kê phân bố task/quality/nhãn classifier.

Cách chạy:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/validate_training_data.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.text_utils import fold  # noqa: E402

DATA_DIR = ROOT / "data/training"
BENCHMARK = ROOT / "data/evaluation/benchmark_100_questions_v3.json"


def load_jsonl(name: str) -> list[dict]:
    path = DATA_DIR / name
    rows = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{name}:{lineno} JSON hỏng — {exc}") from exc
    return rows


def messages_of(row: dict) -> tuple[str, str, str]:
    msgs = row.get("messages") or []
    if len(msgs) != 3:
        raise ValueError("messages phải có đúng 3 phần tử system/user/assistant")
    return msgs[0]["content"], msgs[1]["content"], msgs[2]["content"]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    errors: list[str] = []
    warnings: list[str] = []

    sft_files = ["sft_train.jsonl", "sft_val.jsonl", "sft_benchmark_seed.jsonl"]
    sft = {name: load_jsonl(name) for name in sft_files}
    aux = load_jsonl("corpus_identification.jsonl")
    classifier = load_jsonl("classifier_train.jsonl")
    classifier_seed = load_jsonl("classifier_benchmark_seed.jsonl")
    retrieval = load_jsonl("retrieval_pairs.jsonl")
    refusal = load_jsonl("refusal.jsonl")
    grounded = load_jsonl("rag_grounded.jsonl")

    # 1. Trường bắt buộc + nội dung rỗng.
    seen: dict[tuple[str, str], str] = {}
    for name, rows in sft.items():
        for i, row in enumerate(rows):
            try:
                system, user, answer = messages_of(row)
            except (ValueError, KeyError) as exc:
                errors.append(f"{name}[{i}]: {exc}")
                continue
            for label, text in (("system", system), ("user", user), ("assistant", answer)):
                if not text.strip():
                    errors.append(f"{name}[{i}]: {label} rỗng")
            if answer.strip() in {"None", "null", "undefined"}:
                warnings.append(f"{name}[{i}]: đáp án rỗng nghĩa do lỗi nội suy — {answer!r}")
            key = (row.get("task", ""), fold(user))
            if key in seen:
                errors.append(f"{name}[{i}]: trùng khóa với {seen[key]} — {user[:60]!r}")
            seen[key] = name

    # 2. Không rò rỉ benchmark vào train/val.
    bench = json.loads(BENCHMARK.read_text(encoding="utf-8"))["questions"]
    bench_questions = {fold(q["raw_query"]) for q in bench}
    bench_questions |= {fold(q.get("normalized_query") or "") for q in bench}
    for name in ("sft_train.jsonl", "sft_val.jsonl"):
        for i, row in enumerate(sft[name]):
            meta = row.get("metadata") or {}
            if "benchmark_id" in meta:
                errors.append(f"{name}[{i}]: còn benchmark_id trong train/val")
            _, user, _ = messages_of(row)
            if fold(user) in bench_questions:
                errors.append(f"{name}[{i}]: câu hỏi trùng nguyên văn benchmark — {user[:60]!r}")
    for name in ("sft_train.jsonl", "sft_val.jsonl"):
        tasks = {row.get("task") for row in sft[name]}
        forbidden = {t for t in tasks if str(t).startswith("benchmark_")}
        forbidden |= {"normalization"} if "normalization" in tasks and any(
            (row.get("metadata") or {}).get("benchmark_id") for row in sft[name]
            if row.get("task") == "normalization") else set()
        if forbidden:
            errors.append(f"{name}: còn task benchmark-derived {sorted(forbidden)}")

    # 3. Định danh chunk: số trong đáp án phải có trong đoạn trích.
    for i, row in enumerate(aux):
        _, user, answer = messages_of(row)
        if "Liệt kê các con số" not in user:
            continue
        if "“" not in user or "”" not in user:
            errors.append(f"corpus_identification[{i}]: thiếu đoạn trích")
            continue
        quote = user.split("“", 1)[1].rsplit("”", 1)[0]
        for number in [n.strip() for n in answer.split(",") if n.strip()]:
            if number not in quote:
                errors.append(f"corpus_identification[{i}]: số {number} không có trong đoạn trích")

    # 4. Classifier: nhãn hợp lệ, không trùng text+nhãn.
    topics = {
        "chương trình đào tạo", "học phí", "cuộc thi chính luận", "đánh giá rèn luyện",
        "khen thưởng sinh viên", "thực tập tốt nghiệp", "quy chế công tác sinh viên",
        "sinh viên 5 tốt", "thực tập chuyên đề", "khen thưởng cấp ĐHQG", "ký túc xá",
        "tài chính sinh viên", "bảo hiểm y tế", "hành chính sinh viên",
    }
    types = {"TRA_CUU", "SO_SANH", "THU_TUC", "NGOAI_PHAM_VI"}
    seen_cl: set[tuple[str, str, str]] = set()
    for bucket_name, rows in (("classifier_train", classifier),
                              ("classifier_benchmark_seed", classifier_seed)):
        for i, row in enumerate(rows):
            labels = row.get("labels") or {}
            topic, qtype = labels.get("topic"), labels.get("question_type")
            if topic is not None and topic not in topics:
                errors.append(f"{bucket_name}[{i}]: topic lạ {topic!r}")
            if qtype not in types:
                errors.append(f"{bucket_name}[{i}]: question_type lạ {qtype!r}")
            key = (fold(row.get("text", "")), str(topic), str(qtype))
            if key in seen_cl:
                warnings.append(f"{bucket_name}[{i}]: trùng text+nhãn")
            seen_cl.add(key)

    # 5. Retrieval: positive/negatives khác nguồn, đủ 3 negative.
    for i, row in enumerate(retrieval):
        if len(row.get("negatives") or []) != 3:
            errors.append(f"retrieval_pairs[{i}]: không đủ 3 negative")
        if row.get("positive_source") in (row.get("negative_sources") or []):
            errors.append(f"retrieval_pairs[{i}]: negative trùng nguồn positive")

    print("=" * 70)
    print("KIỂM ĐỊNH DỮ LIỆU HUẤN LUYỆN")
    print("=" * 70)
    for name, rows in (("sft_train", sft["sft_train.jsonl"]),
                       ("sft_val", sft["sft_val.jsonl"]),
                       ("sft_benchmark_seed", sft["sft_benchmark_seed.jsonl"]),
                       ("corpus_identification", aux),
                       ("classifier_train", classifier),
                       ("classifier_benchmark_seed", classifier_seed),
                       ("retrieval_pairs", retrieval),
                       ("refusal", refusal),
                       ("rag_grounded", grounded)):
        print(f"  {name:28s} {len(rows):>6d} dòng")

    print("\nPhân bố task (SFT train + val):")
    train_all = sft["sft_train.jsonl"] + sft["sft_val.jsonl"]
    for task, count in sorted(Counter(r.get("task") for r in train_all).items()):
        print(f"  {task:28s} {count:>5d}")
    print("\nPhân bố quality (SFT train + val):",
          dict(sorted(Counter(r.get("quality") for r in train_all).items())))

    print(f"\nLỖI: {len(errors)} | CẢNH BÁO: {len(warnings)}")
    for err in errors[:20]:
        print("  [LỖI]", err)
    for warn in warnings[:10]:
        print("  [CẢNH BÁO]", warn)
    if errors:
        raise SystemExit(1)
    print("KẾT LUẬN: ĐẠT — không phát hiện lỗi cấu trúc/rò rỉ.")


if __name__ == "__main__":
    main()
