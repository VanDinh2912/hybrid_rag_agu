"""Lưu phản hồi/benchmark/cặp chuẩn hóa của GUI (REVIEW §7 + §13).

Mọi ghi file đi qua `src/core/json_store.py`: khoá file, ghi file tạm rồi thay thế nguyên
tử, và validate schema trước khi ghi. Controller không đụng widget; `ui/app.py` lo hộp thoại.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.core.json_store import (
    JsonStoreError,
    now_iso,
    update_json,
    validate_benchmark_doc,
    validate_feedback_list,
    validate_pairs_doc,
)

logger = logging.getLogger(__name__)

FEEDBACK_SCHEMA_VERSION = 1
BENCHMARK_SCHEMA_VERSION = "2.1"


def feedback_record(
    test_data: dict,
    feedback_type: str,
    correct_answer: str | None,
    *,
    source: str = "gui",
) -> dict:
    """Một bản ghi feedback: giữ trường cũ + bổ sung 5 trường REVIEW §13."""
    created = now_iso()
    answer = test_data.get("answer")
    return {
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "created_at": created,
        "raw_query": test_data.get("raw_query"),
        "answer": answer,
        "feedback_type": feedback_type,
        "source": source,
        # Trường cũ — giữ để bản ghi đã có và công cụ đọc cũ không vỡ.
        "timestamp": created,
        "feedback": feedback_type,
        "normalized_query": test_data.get("normalized_query"),
        "system_answer": answer,
        "correct_answer": correct_answer,
        "sources": [
            {"rank": s["rank"], "source": s["source"], "tier": s["tier"], "chunk_id": s["chunk_id"]}
            for s in test_data.get("sources", [])
        ],
    }


def append_feedback(path: Path, record: dict) -> None:
    """Thêm bản ghi feedback nguyên tử; lỗi nổi lên `JsonStoreError`."""
    update_json(path, [], lambda data: [*data, record], validate=validate_feedback_list)


def _next_question_id(questions: list[dict]) -> str:
    """ID `Qnn` kế tiếp chưa dùng — không dựa vào `len()` để tránh trùng sau khi xoá."""
    used = {str(q.get("id", "")) for q in questions if isinstance(q, dict)}
    numbers = [int(str(qid)[1:]) for qid in used if str(qid).startswith("Q") and str(qid)[1:].isdigit()]
    nxt = (max(numbers) + 1) if numbers else 1
    while f"Q{nxt:02d}" in used:
        nxt += 1
    return f"Q{nxt:02d}"


def save_benchmark(
    path: Path,
    test_data: dict,
    ground_truth: str,
    citation: str,
    source_doc: str,
    normalized_query: str,
) -> tuple[bool, str]:
    """Append câu hỏi mới vào benchmark; `(True, "")` khi xong, `(False, lỗi)` khi hỏng."""
    new_question: dict = {}

    def _append(doc: Any) -> Any:
        if not isinstance(doc, dict) or not isinstance(doc.get("questions"), list):
            raise JsonStoreError("benchmark không đúng cấu trúc")
        doc.setdefault("version", BENCHMARK_SCHEMA_VERSION)
        qid = _next_question_id(doc["questions"])
        new_question.clear()
        new_question.update({
            "id": qid,
            "category": "người dùng thêm",
            "in_corpus": True,
            "source_document": source_doc,
            "raw_query": test_data["raw_query"],
            "normalized_query": normalized_query,
            "expected_answer": ground_truth,
            "expected_citations": [citation] if citation else [],
            "ground_truth_answer": ground_truth,
            "ground_truth_citation": f"{source_doc} - {citation}" if citation else source_doc,
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "created_at": now_iso(),
            "source": "gui_feedback",
        })
        doc["questions"].append(new_question)
        return doc

    try:
        update_json(
            path,
            {
                "version": BENCHMARK_SCHEMA_VERSION,
                "description": "Bộ câu hỏi benchmark Hybrid RAG AGU",
                "questions": [],
            },
            _append,
            validate=validate_benchmark_doc,
        )
        logger.info("Đã thêm câu hỏi %s vào %s", new_question.get("id"), path)
        return True, ""
    except (JsonStoreError, KeyError, OSError) as exc:
        # OSError: thư mục cha bị chặn/không tạo được — vẫn phải trả lỗi rõ cho caller.
        logger.error("Không lưu được benchmark: %s", exc)
        return False, str(exc)


def save_normalization_pair(path: Path, raw_query: str, normalized_query: str) -> tuple[bool, str]:
    """Thêm/cập nhật một cặp (câu gốc → câu chuẩn hóa) nguyên tử."""
    def _upsert(doc: Any) -> Any:
        if not isinstance(doc, dict) or not isinstance(doc.get("pairs"), list):
            raise JsonStoreError("normalization_pairs không đúng cấu trúc")
        doc.setdefault("version", "1.1")
        for pair in doc["pairs"]:
            if isinstance(pair, dict) and pair.get("raw_query") == raw_query:
                pair["normalized_query"] = normalized_query
                pair["updated_at"] = now_iso()
                return doc
        doc["pairs"].append({
            "raw_query": raw_query,
            "normalized_query": normalized_query,
            "created_at": now_iso(),
        })
        return doc

    try:
        update_json(
            path,
            {"version": "1.1", "description": "Cặp câu hỏi chuẩn hóa để Qwen học", "pairs": []},
            _upsert,
            validate=validate_pairs_doc,
        )
        logger.info("Đã lưu cặp chuẩn hóa vào %s", path)
        return True, ""
    except (JsonStoreError, KeyError, OSError) as exc:
        logger.error("Không lưu được cặp chuẩn hóa: %s", exc)
        return False, str(exc)


def build_result_lines(status: dict, errors: list[str]) -> tuple[list[str], bool]:
    """Dòng thông báo từng phần + cờ "có mục hỏng" (nguồn cho hộp thoại)."""
    lines = ["Đã lưu phản hồi vào logs/feedback/user_feedback.json!"]
    if status.get("benchmark_saved") is True:
        lines.append("Đã cập nhật benchmark_questions.json!")
    elif status.get("benchmark_saved") is False:
        lines.append("CHƯA cập nhật được benchmark_questions.json.")
    if status.get("normalization_pair_saved") is True:
        lines.append("Đã lưu cặp chuẩn hóa cho Qwen học!")
    elif status.get("normalization_pair_saved") is False:
        lines.append("CHƯA lưu được cặp chuẩn hóa cho Qwen.")
    if status.get("note_saved") is True:
        lines.append("Đã ghi bài học vào data/corpus/ghi_chu_hoc_them.txt.")
    elif status.get("note_saved") is False:
        lines.append("CHƯA ghi được bài học vào corpus.")
    if status.get("rebuild_succeeded") is True:
        lines.append("Đã nạp lại corpus và làm mới bộ truy xuất thành công.")
    elif status.get("rebuild_succeeded") is False:
        lines.append(
            "ChromaDB/bộ truy xuất CHƯA được cập nhật — lượt hỏi tiếp theo vẫn dùng corpus cũ."
        )
    if errors:
        lines.append("\nChi tiết lỗi:")
        lines.extend(f"- {err}" for err in errors)
    failed = bool(errors) or any(
        status.get(key) is False
        for key in ("benchmark_saved", "normalization_pair_saved", "note_saved", "rebuild_succeeded")
    )
    return lines, failed
