"""Script tính faithfulness heuristic local (không cần LLM judge).

Phương pháp: token-overlap giữa câu trả lời và chunk contexts đã trích dẫn.
- Tách câu trả lời thành tokens (bỏ stopwords, giữ từ nội dung)
- Tính overlap với contexts
- Score = số token câu trả lời có trong contexts / tổng token câu trả lời
- Từ chối chuẩn (REFUSAL_MARKER) → score = 1.0 (không có khẳng định để phản bội)
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.generator import REFUSAL_MARKER
from src.text_utils import fold

# Stopwords tiếng Việt cơ bản (để loại bỏ từ vô nghĩa khi overlap)
VIETNAMESE_STOPWORDS = {
    "là", "có", "không", "được", "trong", "và", "của", "các", "đối", "cho",
    "với", "để", "này", "đó", "những", "thì", "mà", "từ", "đây", "đó",
    "nên", "cần", "phải", "sẽ", "đã", "đang", "thực", "hiện", "tại", "trên",
    "thông", "qua", "theo", "theo", "xuyên", "tất", "cả", "một", "hai", "ba",
    "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười", "một", "nhiều", "ít",
    "rất", "hơi", "hoặc", "về", "gồm", "gồm", "có", "chứa", "nằm", "ở",
}

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def extract_meaningful_tokens(text: str) -> set[str]:
    """Rút tập token có nghĩa (bỏ stopwords, giữ số)."""
    tokens = set()
    # Bỏ tất cả số
    for num in NUMBER_RE.findall(text):
        tokens.add(num)
    # Bỏ từ không phải stopwords
    for word in WORD_RE.findall(text):
        word_lower = word.lower()
        if word_lower not in VIETNAMESE_STOPWORDS and len(word) > 1:
            tokens.add(word_lower)
    return tokens


def heuristic_faithfulness(answer: str, contexts: list[str]) -> float:
    """Tính faithfulness bằng token-overlap với contexts.

    Args:
        answer: câu trả lời generator
        contexts: danh sách chunk contexts đã truy xuất

    Returns:
        score 0-1: tỉ lệ token câu trả lời có trong contexts
    """
    # Kiểm tra từ chối chuẩn
    if fold(REFUSAL_MARKER) in fold(answer):
        return 1.0

    if not contexts or not answer.strip():
        return 0.0

    answer_tokens = extract_meaningful_tokens(answer)
    if not answer_tokens:
        return 0.0

    # Gộp tất cả contexts thành một pool
    context_pool = " ".join(contexts)
    context_tokens = extract_meaningful_tokens(context_pool)

    # Tính overlap
    overlap = answer_tokens & context_tokens
    if not overlap:
        return 0.0

    return round(len(overlap) / len(answer_tokens), 4)


def compute_faithfulness_for_json(json_path: Path, update_json: bool = True) -> dict:
    """Tính faithfulness heuristic cho toàn bộ JSON kết quả.

    Args:
        json_path: đường dẫn file JSON (ab_results_*.json)
        update_json: nếu True, ghi faithfulness score vào JSON

    Returns:
        dict với số liệu thống kê: số câu đã tính, trung bình, lỗi
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Không tìm thấy {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON không đúng định dạng")

    entries = data.get("per_question", [])
    if not entries:
        raise ValueError("Không có per_question trong JSON")

    computed = 0
    skipped = 0
    errors = 0
    scores = []

    for entry in entries:
        if not isinstance(entry, dict):
            errors += 1
            continue

        # Bỏ qua câu lỗi
        if entry.get("error"):
            skipped += 1
            continue

        answer = entry.get("answer")
        contexts = entry.get("contexts", [])

        if not answer:
            skipped += 1
            continue

        if not contexts:
            skipped += 1
            continue

        # Tính faithfulness heuristic
        try:
            score = heuristic_faithfulness(answer, contexts)
            entry["faithfulness"] = {
                "score": score,
                "unsupported_claims": [],
                "method": "heuristic_local",
                "error": None,
            }
            computed += 1
            scores.append(score)
        except Exception as exc:
            errors += 1
            entry["faithfulness"] = {
                "score": None,
                "unsupported_claims": [],
                "method": "heuristic_local",
                "error": str(exc),
            }

    # Ghi lại JSON nếu update_json=True
    if update_json:
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    return {
        "n_computed": computed,
        "n_skipped": skipped,
        "n_errors": errors,
        "average_score": round(sum(scores) / len(scores), 4) if scores else None,
    }


def main():
    """CLI: tính faithfulness heuristic cho file JSON."""
    import argparse
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Tính faithfulness heuristic local cho file JSON kết quả đánh giá"
    )
    parser.add_argument("json_path", type=Path, help="đường dẫn file JSON kết quả")
    args = parser.parse_args()

    try:
        stats = compute_faithfulness_for_json(args.json_path)
        print(f"Đã tính faithfulness heuristic cho {args.json_path}")
        print(f"  Số câu đã tính: {stats['n_computed']}")
        print(f"  Số câu bỏ qua: {stats['n_skipped']}")
        print(f"  Số lỗi: {stats['n_errors']}")
        if stats['average_score'] is not None:
            print(f"  Điểm trung bình: {stats['average_score']}")
        else:
            print("  Không đủ dữ liệu để tính trung bình")
    except Exception as exc:
        print(f"Lỗi: {exc}")
        raise


if __name__ == "__main__":
    main()
