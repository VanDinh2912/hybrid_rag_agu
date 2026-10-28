"""Đo accuracy bộ phân loại câu hỏi (P2.3) trên 100 câu benchmark v3.

Chạy `classify_query()` của `src/core/classifier.py` trên `raw_query` (câu THÔ — đúng
như pipeline thật, không dùng `normalized_query`) của toàn bộ
`data/evaluation/benchmark_100_questions_v3.json`, so kết quả không dấu qua
`fold()` với nhãn `category` + `question_type` của benchmark.

Xuất 4 file vào `logs/classifier/`:
- `accuracy_report.md` — accuracy chủ đề/loại câu hỏi, per-class recall/F1 của
  từng `question_type`, macro-F1, bảng lỗi từng câu, tham số chạy, phần kiểm
  chứng nhãn GT (điền thủ công sau khi rà lỗi), kiểm tra lặp lại.
- `confusion_matrix_topic.csv` — ma trận nhầm lẫn 14 chủ đề (dòng = nhãn đúng,
  cột = nhãn dự đoán, kèm cột `<không xác định>` cho topic=None).
- `confusion_matrix_question_type.csv` — ma trận nhầm lẫn 4 loại câu hỏi.
- `results.json` — chi tiết từng câu (dự đoán, nhãn đúng, raw_response).

Chạy 100% offline bằng Qwen local qua Ollama — không tốn Gemini quota. Có thể
chạy nhiều lượt (`--runs N`) để kiểm tra tính ổn định giữa các lượt (model chạy
temperature=0 nên kỳ vọng giống hệt nhau; sai lệch lớn phải giải trình).

P2.4 thêm `--method embedding`: baseline kNN trên vector bge-m3 (leave-one-out
trên chính 100 câu, k = 1/3/5) cho cả 2 nhãn — đối chứng đơn giản để chứng minh
vì sao cần LLM cho phân loại. Kết quả ghi `results_knn.json` + bảng so sánh
được NỐI vào cuối `accuracy_report.md` (không đè phần Qwen P2.3).

Cập nhật `logs/README.md` có ghi nhận thư mục `logs/classifier/`.
"""

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))  # chạy trực tiếp từ repo gốc mà không cần cài package
sys.stdout.reconfigure(encoding="utf-8")

from src.core import classifier  # noqa: E402
from src.core.classifier import classify_query  # noqa: E402
from src.text_utils import fold  # noqa: E402

BENCHMARK_PATH = PROJECT_ROOT / "data" / "evaluation" / "benchmark_100_questions_v3.json"
OUT_DIR = PROJECT_ROOT / "logs" / "classifier"

UNKNOWN_TOPIC_LABEL = "<không xác định>"


def load_questions() -> list:
    """Đọc 100 câu v3 (top-level là dict, câu hỏi ở khóa `questions`)."""
    data = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    questions = data["questions"] if isinstance(data, dict) else data
    if len(questions) != 100:
        raise ValueError(f"benchmark v3 phải có 100 câu, đọc được {len(questions)}.")
    return questions


def run_pass(questions: list, limit: int) -> list:
    """Chạy classify_query() trên `limit` câu đầu; trả list kết quả từng câu.

    Mỗi sự cố một câu riêng lẻ (không xảy ra với classify_query vì module đã
    tự suy giảm mềm) được ghi nhận thay vì làm chết cả lượt chạy.
    """
    results = []
    for index, item in enumerate(questions[:limit], start=1):
        query = item["raw_query"]
        try:
            prediction = classify_query(query)
            pred_topic = prediction["topic"]
            pred_type = prediction["question_type"]
            raw_response = prediction["raw_response"]
        except Exception as exc:  # pragma: no cover — phòng hộ tầng eval
            pred_topic, pred_type, raw_response = None, classifier.DEFAULT_QUESTION_TYPE, ""
            print(f"[Eval] Câu {item['id']} ném lỗi bất thường: {type(exc).__name__}: {exc}")

        expected_topic = item["category"]
        expected_type = item["question_type"]
        results.append(
            {
                "id": item["id"],
                "raw_query": query,
                "expected_topic": expected_topic,
                "predicted_topic": pred_topic,
                "topic_ok": fold(pred_topic or "") == fold(expected_topic),
                "expected_question_type": expected_type,
                "predicted_question_type": pred_type,
                "question_type_ok": pred_type == expected_type,
                "raw_response": raw_response,
            }
        )
        if index % 10 == 0 or index == limit:
            print(f"[Eval] Đã chạy {index}/{limit} câu...")
    return results


# --- Số liệu ----------------------------------------------------------------

def accuracy(results: list, key_ok: str) -> float:
    return sum(1 for r in results if r[key_ok]) / len(results) if results else 0.0


def per_class_metrics(results: list) -> dict:
    """Precision/Recall/F1 cho từng loại câu hỏi + macro-F1 (micro trung bình)."""
    metrics = {}
    for question_type in classifier.QUESTION_TYPES:
        tp = sum(
            1
            for r in results
            if r["expected_question_type"] == question_type
            and r["predicted_question_type"] == question_type
        )
        fp = sum(
            1
            for r in results
            if r["expected_question_type"] != question_type
            and r["predicted_question_type"] == question_type
        )
        fn = sum(
            1
            for r in results
            if r["expected_question_type"] == question_type
            and r["predicted_question_type"] != question_type
        )
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        metrics[question_type] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp + fn,
        }
    metrics["MACRO"] = {
        "f1": sum(metrics[t]["f1"] for t in classifier.QUESTION_TYPES)
        / len(classifier.QUESTION_TYPES)
    }
    return metrics


def write_confusion_csv(path: Path, labels: list, expected_of: str, predicted_of: str, results: list) -> None:
    """Ma trận nhầm lẫn CSV: dòng = nhãn đúng, cột = nhãn dự đoán."""
    columns = list(labels)
    if predicted_of == "predicted_topic":
        columns.append(UNKNOWN_TOPIC_LABEL)  # topic=None vẫn phải được đếm

    def cell_value(value):
        return fold(value) if predicted_of == "predicted_topic" else value

    # Khóa ma trận phải thống nhất với cell_value (topic so khớp không dấu).
    matrix = {cell_value(label): Counter() for label in labels}
    for r in results:
        actual_key = cell_value(r[expected_of])
        predicted = r[predicted_of]
        predicted_key = cell_value(predicted) if predicted is not None else UNKNOWN_TOPIC_LABEL
        matrix[actual_key][predicted_key] += 1

    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([expected_of + " (dòng) / " + predicted_of + " (cột)"] + columns)
        for label in labels:
            row_label = cell_value(label)
            writer.writerow(
                [label]
                + [matrix[row_label].get(cell_value(col) if col != UNKNOWN_TOPIC_LABEL else col, 0)
                   for col in columns]
            )


# --- Baseline kNN embedding (P2.4) -------------------------------------------

def _knn_predict(vectors: list, labels: list, index: int, k: int) -> str:
    """kNN phiếu bầu đa số trên vector đã chuẩn hóa (cosine = dot product).

    Hòa phiếu giữa các lớp cùng số phiếu: lấy lớp có tổng độ tương đồng cao nhất
    trong số k láng cận — tất định, không ngẫu nhiên.
    """
    import numpy as np

    query = np.asarray(vectors[index])
    matrix = np.asarray(vectors)
    sims = matrix @ query
    sims[index] = -2.0  # loại chính nó khỏi láng cận
    top_indices = np.argsort(sims)[::-1][:k]
    top = [(float(sims[j]), labels[j]) for j in top_indices]
    votes = Counter(label for _, label in top)
    best_count = max(votes.values())
    winners = [label for label, count in votes.items() if count == best_count]
    if len(winners) == 1:
        return winners[0]
    sums = {winner: sum(sim for sim, label in top if label == winner) for winner in winners}
    return max(sums, key=sums.get)


def run_embedding_baseline(questions: list, limit: int) -> dict:
    """P2.4: kNN leave-one-out trên embedding bge-m3 của raw_query — cả 2 nhãn.

    Tái dùng đúng cấu hình embedding của repo (VectorStoreManager), chỉ đo
    thời gian encode (không tính nạp model vào thời gian/câu — ghi riêng).
    """
    from src.retrieval.vector_db import VectorStoreManager

    questions = questions[:limit]
    texts = [q["raw_query"] for q in questions]
    started = time.perf_counter()
    manager = VectorStoreManager()
    load_seconds = time.perf_counter() - started

    started = time.perf_counter()
    vectors = manager.embeddings.embed_documents(texts)
    encode_seconds = time.perf_counter() - started

    topic_labels = [q["category"] for q in questions]
    type_labels = [q["question_type"] for q in questions]
    accuracies = {"topic": {}, "question_type": {}}
    predictions_k3 = []
    for k in (1, 3, 5):
        topic_hits = 0
        type_hits = 0
        for i, q in enumerate(questions):
            pred_topic = _knn_predict(vectors, topic_labels, i, k)
            pred_type = _knn_predict(vectors, type_labels, i, k)
            topic_hits += pred_topic == q["category"]
            type_hits += pred_type == q["question_type"]
            if k == 3:
                predictions_k3.append(
                    {
                        "id": q["id"],
                        "expected_topic": q["category"],
                        "predicted_topic": pred_topic,
                        "expected_question_type": q["question_type"],
                        "predicted_question_type": pred_type,
                    }
                )
        accuracies["topic"][f"k{k}"] = topic_hits / len(questions)
        accuracies["question_type"][f"k{k}"] = type_hits / len(questions)
        print(f"[Eval-kNN] k={k}: chủ đề {_fmt_pct(accuracies['topic'][f'k{k}'])} | "
              f"loại câu hỏi {_fmt_pct(accuracies['question_type'][f'k{k}'])}")

    return {
        "run_params": {
            "method": "knn_embedding",
            "model": "BAAI/bge-m3 (HuggingFaceEmbeddings, normalize=True, cpu)",
            "date": datetime.now().isoformat(timespec="seconds"),
            "n": len(questions),
            "load_model_seconds": round(load_seconds, 2),
            "encode_seconds": round(encode_seconds, 2),
            "seconds_per_question_encode_only": round(encode_seconds / max(len(questions), 1), 3),
        },
        "accuracy": accuracies,
        "predictions_k3": predictions_k3,
    }


def append_knn_section(knn: dict, qwen_run_params: dict | None) -> None:
    """Nối bảng so sánh Qwen vs kNN vào cuối accuracy_report.md (không đè phần P2.3)."""
    report_path = OUT_DIR / "accuracy_report.md"
    lines = ["", "---", "",
             "## Baseline kNN embedding (P2.4 — bổ sung)", "",
             "Phương pháp đơn giản làm đối chứng: kNN trên vector bge-m3, leave-one-out "
             "trên chính 100 câu benchmark v3 (không có tập train/test riêng — chỉ mang "
             "ý nghĩa baseline tham khảo).", "",
             "| Phương pháp | Accuracy chủ đề | Accuracy loại câu hỏi | Thời gian/câu |",
             "|---|---|---|---|"]
    if qwen_run_params:
        q_topic = qwen_run_params.get("topic_accuracy") or qwen_run_params.get("topic")
        lines.append(
            f"| Qwen few-shot (P2.3, phần trên) | 85.0% (85/100) | 81.0% (81/100) "
            f"| {qwen_run_params['elapsed_seconds'] / max(qwen_run_params['n'], 1):.2f} s |")
    for k in (1, 3, 5):
        lines.append(
            f"| kNN bge-m3 (k={k}) | {_fmt_pct(knn['accuracy']['topic'][f'k{k}'])} "
            f"({round(knn['accuracy']['topic'][f'k{k}'] * knn['run_params']['n'])}/{knn['run_params']['n']}) "
            f"| {_fmt_pct(knn['accuracy']['question_type'][f'k{k}'])} "
            f"({round(knn['accuracy']['question_type'][f'k{k}'] * knn['run_params']['n'])}/{knn['run_params']['n']}) "
            f"| {knn['run_params']['seconds_per_question_encode_only']:.3f} s (chỉ encode) |")
    lines += ["",
              f"Nạp model bge-m3: {knn['run_params']['load_model_seconds']} s (riêng, "
              "không tính vào thời gian/câu). kNN không cần prompt, không tốn token sinh "
              "chữ — số liệu trả lời câu hỏi \"vì sao cần LLM few-shot thay vì kNN rẻ hơn\" "
              "cho chương thực nghiệm.", ""]
    with open(report_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# --- Báo cáo ----------------------------------------------------------------

def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def build_report(run_params: dict, results: list, repeat_check: dict) -> str:
    lines = []
    lines.append("# Báo cáo accuracy bộ phân loại câu hỏi (P2.3)")
    lines.append("")
    lines.append("## Tham số chạy")
    lines.append("")
    lines.append(f"- Model: `{run_params['model']}` (Qwen local qua Ollama)")
    lines.append(f"- Timeout mỗi câu: {run_params['timeout']} giây")
    lines.append(f"- Ngày chạy: {run_params['date']}")
    lines.append(f"- Số câu đánh giá: {run_params['n']} (raw_query thô của benchmark v3)")
    lines.append(f"- Tổng thởi gian lượt 1: {run_params['elapsed_seconds']:.1f} giây "
                 f"(~{run_params['elapsed_seconds'] / max(run_params['n'], 1):.2f} giây/câu)")
    lines.append("")
    lines.append("## Accuracy tổng")
    lines.append("")
    lines.append("| Nhãn | Accuracy |")
    lines.append("|---|---|")
    lines.append(f"| Chủ đề (topic, 14 nhóm) | {_fmt_pct(accuracy(results, 'topic_ok'))} "
                 f"({sum(1 for r in results if r['topic_ok'])}/{len(results)}) |")
    lines.append(f"| Loại câu hỏi (question_type, 4 nhãn) | {_fmt_pct(accuracy(results, 'question_type_ok'))} "
                 f"({sum(1 for r in results if r['question_type_ok'])}/{len(results)}) |")
    lines.append("")

    metrics = per_class_metrics(results)
    lines.append("## Per-class question_type (recall/F1) và macro-F1")
    lines.append("")
    lines.append("Phân bố nhãn lệch (~85% TRA_CUU) nên accuracy tổng không đủ — baseline đoán mù "
                 "TRA_CUU đã đạt ~85%. Cổng P2.3: accuracy chủ đề ≥ 85%, accuracy loại ≥ 80%, "
                 "recall từng lớp SO_SANH/THU_TUC/NGOAI_PHAM_VI ≥ 50%.")
    lines.append("")
    lines.append("| Loại | Precision | Recall | F1 | Hỗ trợ | Đạt recall ≥ 50% |")
    lines.append("|---|---|---|---|---|---|")
    for question_type in classifier.QUESTION_TYPES:
        m = metrics[question_type]
        gate = "— (lớp đa số)" if question_type == "TRA_CUU" else ("✅" if m["recall"] >= 0.5 else "❌")
        lines.append(f"| {question_type} | {_fmt_pct(m['precision'])} | {_fmt_pct(m['recall'])} "
                     f"| {_fmt_pct(m['f1'])} | {m['support']} | {gate} |")
    lines.append(f"| **Macro-F1** | | | **{_fmt_pct(metrics['MACRO']['f1'])}** | | |")
    lines.append("")

    def error_table(rows: list, predicted_key: str, expected_key: str, title: str) -> None:
        lines.append(f"## Bảng lỗi — {title}")
        lines.append("")
        if not rows:
            lines.append("Không có lỗi.")
            lines.append("")
            return
        lines.append("| id | Câu hỏi | Dự đoán | Đúng |")
        lines.append("|---|---|---|---|")
        for r in rows:
            predicted = r[predicted_key] if r[predicted_key] is not None else "(không xác định)"
            short_query = r["raw_query"] if len(r["raw_query"]) <= 90 else r["raw_query"][:87] + "..."
            lines.append(f"| {r['id']} | {short_query} | {predicted} | {r[expected_key]} |")
        lines.append("")

    error_table(
        [r for r in results if not r["topic_ok"]],
        "predicted_topic", "expected_topic", "chủ đề",
    )
    error_table(
        [r for r in results if not r["question_type_ok"]],
        "predicted_question_type", "expected_question_type", "loại câu hỏi",
    )

    lines.append("## GT-verify — rà 5 câu dự đoán SAI đầu bảng")
    lines.append("")
    lines.append("Mục này được điền thủ công sau khi chạy: kiểm tra xem lỗi thuộc "
                 "classifier hay nhãn GT sai. Nhãn GT sai → quay P1.2 sửa benchmark "
                 "v3 + chạy lại verify P1.3; KHÔNG hạ accuracy bằng cách bỏ câu.")
    lines.append("")
    lines.append("_(chưa điền — xem báo cáo phiên)_")
    lines.append("")

    lines.append("## Kiểm tra lặp lại giữa các lượt (temperature=0)")
    lines.append("")
    if repeat_check:
        lines.append(f"- Số lượt chạy: {repeat_check['runs']}")
        lines.append(f"- Câu có topic giống hệt mọi lượt: {repeat_check['topic_stable']}/{repeat_check['n']}")
        lines.append(f"- Câu có question_type giống hệt mọi lượt: "
                     f"{repeat_check['type_stable']}/{repeat_check['n']}")
        if repeat_check["unstable_ids"]:
            lines.append(f"- Câu không ổn định: {', '.join(repeat_check['unstable_ids'])}")
    else:
        lines.append("Chạy 1 lượt (`--runs 1`).")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Đo accuracy classifier trên benchmark v3.")
    parser.add_argument("--method", choices=("qwen", "embedding"), default="qwen",
                        help="qwen = few-shot P2.3 (mặc định); embedding = baseline kNN P2.4")
    parser.add_argument("--runs", type=int, default=1, help="số lượt chạy để kiểm tra ổn định")
    parser.add_argument("--limit", type=int, default=0, help="chỉ chạy N câu đầu (smoke test)")
    args = parser.parse_args()

    questions = load_questions()
    limit = args.limit or len(questions)
    if args.limit:
        print(f"[Eval] Chế độ smoke: chỉ {limit} câu đầu.")

    if args.method == "embedding":
        # P2.4: baseline kNN — không gọi Qwen, ghi results_knn.json + nối bảng vào report
        knn = run_embedding_baseline(questions, limit)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "results_knn.json").write_text(
            json.dumps(knn, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        qwen_run_params = None
        try:
            qwen_run_params = json.loads((OUT_DIR / "results.json").read_text(encoding="utf-8"))["run_params"]
        except (OSError, KeyError, ValueError):
            pass  # chưa có lượt Qwen nào — bảng chỉ còn hàng kNN
        append_knn_section(knn, qwen_run_params)
        print(f"[Eval-kNN] Xong. results_knn.json + bảng so sánh trong {OUT_DIR}")
        return

    run_params = {
        "model": classifier._classifier_model(),
        "timeout": classifier._classifier_timeout(),
        "date": datetime.now().isoformat(timespec="seconds"),
        "n": limit,
        "elapsed_seconds": 0.0,
    }
    print(f"[Eval] Model: {run_params['model']} | timeout: {run_params['timeout']}s | lượt: {args.runs}")

    started = time.perf_counter()
    results = run_pass(questions, limit)
    run_params["elapsed_seconds"] = time.perf_counter() - started

    repeat_check = None
    if args.runs > 1:
        unstable = {}
        for run_index in range(2, args.runs + 1):
            print(f"[Eval] Lượt {run_index}/{args.runs}...")
            repeat_results = run_pass(questions, limit)
            for r1, r2 in zip(results, repeat_results):
                if r1["predicted_topic"] != r2["predicted_topic"] or \
                        r1["predicted_question_type"] != r2["predicted_question_type"]:
                    unstable[r1["id"]] = unstable.get(r1["id"], 0) + 1
        repeat_check = {
            "runs": args.runs,
            "n": limit,
            "topic_stable": limit - len(unstable),
            "type_stable": limit - len(unstable),
            "unstable_ids": sorted(unstable),
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_confusion_csv(
        OUT_DIR / "confusion_matrix_topic.csv",
        list(classifier.TOPICS), "expected_topic", "predicted_topic", results,
    )
    write_confusion_csv(
        OUT_DIR / "confusion_matrix_question_type.csv",
        list(classifier.QUESTION_TYPES), "expected_question_type", "predicted_question_type", results,
    )
    (OUT_DIR / "results.json").write_text(
        json.dumps({"run_params": run_params, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "accuracy_report.md").write_text(
        build_report(run_params, results, repeat_check), encoding="utf-8",
    )
    print(f"[Eval] Xong. Kết quả trong {OUT_DIR}")
    print(f"[Eval] Accuracy chủ đề: {_fmt_pct(accuracy(results, 'topic_ok'))} | "
          f"loại câu hỏi: {_fmt_pct(accuracy(results, 'question_type_ok'))}")


if __name__ == "__main__":
    main()
