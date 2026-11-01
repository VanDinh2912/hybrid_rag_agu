"""Lưu phản hồi/benchmark/cặp chuẩn hóa của GUI (REVIEW §7 + §13 + hardening 01-11).

Mọi ghi file JSON *theo khoá rồi thay thế* đi qua `src/core/json_store.py`: khoá file,
ghi file tạm rồi thay thế nguyên tử, và validate schema trước khi ghi. Riêng hàng đợi
duyệt (`enqueue_feedback`) cố ý dùng `O_CREAT|O_EXCL` — mỗi phản hồi là một tệp MỚI,
không bao giờ sửa tệp đã có. Controller không đụng widget; `ui/app.py` lo hộp thoại.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

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
QUEUE_SCHEMA_VERSION = 1
BENCHMARK_SCHEMA_VERSION = "2.1"

#: Ba mục một bản ghi hàng đợi có thể xin duyệt. Khoá lạ bị `validate_queue_record` từ chối
#: để công cụ duyệt (`tools/diag/feedback_promote.py`) không phải đoán.
QUEUE_REQUEST_KEYS = ("benchmark", "normalization_pair", "corpus_note")


class QueueError(RuntimeError):
    """Không xếp được bản ghi vào hàng đợi chờ duyệt (thư mục/khoá/ghi hỏng)."""


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


# ----------------------------------------------------------------------------- hàng đợi
def queue_record(
    test_data: dict,
    feedback_type: str,
    correct_answer: str | None,
    *,
    ground_truth: str = "",
    citation: str = "",
    source_doc: str = "",
    normalized_truth: str = "",
    requested: dict,
    source: str = "gui",
) -> dict:
    """Bản ghi hàng đợi: phản hồi + phần người dùng XIN duyệt (chưa áp gì).

    `requested` chỉ được chứa ba khoá `QUEUE_REQUEST_KEYS`, giá trị bool — công cụ duyệt
    đọc đúng ba khoá này và bỏ qua mục `False`. Trường `correct_answer` giữ nguyên chuỗi
    nhiều dòng như bản ghi feedback gốc để người duyệt đọc được cả đáp án/căn cứ/nguồn;
    `ground_truth` là đáp án trần để công cụ duyệt ghi thẳng vào benchmark (không phải
    bóc chuỗi tổng hợp).
    """
    unknown = sorted(set(requested) - set(QUEUE_REQUEST_KEYS))
    if unknown:
        raise QueueError(f"`requested` có khoá lạ: {unknown}")
    base = feedback_record(test_data, feedback_type, correct_answer, source=source)
    record = {
        **base,
        "queue_schema_version": QUEUE_SCHEMA_VERSION,
        "queued_at": base["created_at"],
        "ground_truth": ground_truth,
        "citation": citation,
        "source_doc": source_doc,
        "normalized_truth": normalized_truth,
        "requested": {key: bool(requested.get(key, False)) for key in QUEUE_REQUEST_KEYS},
    }
    validate_queue_record(record)
    return record


def validate_queue_record(record: Any) -> None:
    """Schema tối thiểu của một tệp hàng đợi — hỏng cấu trúc thì từ chối, không đoán."""
    if not isinstance(record, dict):
        raise QueueError("bản ghi hàng đợi phải là object")
    if record.get("queue_schema_version") != QUEUE_SCHEMA_VERSION:
        raise QueueError(
            f"queue_schema_version phải là {QUEUE_SCHEMA_VERSION}, "
            f"nhận {record.get('queue_schema_version')!r}"
        )
    raw_query = record.get("raw_query")
    if not isinstance(raw_query, str) or not raw_query.strip():
        raise QueueError("bản ghi hàng đợi thiếu `raw_query`")
    requested = record.get("requested")
    if not isinstance(requested, dict):
        raise QueueError("bản ghi hàng đợi thiếu object `requested`")
    unknown = sorted(set(requested) - set(QUEUE_REQUEST_KEYS))
    if unknown:
        raise QueueError(f"`requested` có khoá lạ: {unknown}")
    for key, value in requested.items():
        if not isinstance(value, bool):
            raise QueueError(f"`requested[{key!r}]` phải là bool, nhận {type(value).__name__}")
    # Mục đã xin duyệt phải có ĐỦ nguyên liệu để áp; thiếu thì từ chối ngay, không để
    # công cụ duyệt ghi một nửa rồi báo lỗi giữa chừng.
    for key, value in requested.items():
        if not value:
            continue
        required = {
            "benchmark": ("ground_truth", "citation", "source_doc"),
            "normalization_pair": ("normalized_truth",),
            "corpus_note": ("correct_answer",),
        }[key]
        for field in required:
            text = record.get(field)
            if not isinstance(text, str) or not text.strip():
                raise QueueError(f"xin duyệt `{key}` nhưng thiếu `{field}`")


def _queue_stem(record: dict) -> str:
    """Tên tệp đọc được: dấu thời gian + 8 ký tự băm của câu hỏi gốc."""
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
    digest = hashlib.sha256(
        f"{record.get('queued_at')}|{record.get('raw_query')}".encode("utf-8")
    ).hexdigest()[:8]
    return f"{stamp}-{digest}"


def enqueue_feedback(queue_dir: Path, record: dict) -> Path:
    """Ghi MỘT bản ghi thành MỘT tệp mới trong hàng đợi; trả đường dẫn tệp đã tạo.

    Dùng `os.O_CREAT | os.O_EXCL`: hai phiên GUI cùng ghi không đè nhau, và tệp đã có
    không bao giờ bị thay — muốn sửa nội dung thì tạo bản ghi mới. Ghi hỏng ⇒ xoá phần
    đã tạo rồi ném `QueueError`, để GUI báo thất bại thay vì để lại tệp cụt im lặng.
    """
    validate_queue_record(record)
    try:
        queue_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise QueueError(f"không tạo được thư mục hàng đợi {queue_dir}: {exc}") from exc

    payload = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
    stem = _queue_stem(record)
    for attempt in range(100):
        name = f"{stem}.json" if attempt == 0 else f"{stem}-{attempt + 1}.json"
        path = queue_dir / name
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0))
        except FileExistsError:
            continue
        except OSError as exc:
            raise QueueError(f"không tạo được tệp hàng đợi {path}: {exc}") from exc
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise QueueError(f"không ghi được tệp hàng đợi {path}: {exc}") from exc
        logger.info("Đã xếp phản hồi vào hàng đợi: %s", path)
        return path
    raise QueueError(f"không tìm được tên tệp trống trong {queue_dir} cho {stem}")


def iter_queue(queue_dir: Path) -> Iterator[tuple[Path, Any, str]]:
    """Duyệt hàng đợi theo thứ tự tên tệp: `(path, record | None, lỗi)`.

    Tệp hỏng KHÔNG bị bỏ qua im lặng: trả `record=None` kèm thông điệp lỗi để công cụ
    duyệt báo cáo và dừng, đúng nguyên tắc "không đoán dữ liệu người dùng".
    """
    if not queue_dir.is_dir():
        return
    for path in sorted(queue_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            validate_queue_record(record)
        except (OSError, ValueError, QueueError) as exc:
            yield path, None, str(exc)
            continue
        yield path, record, ""


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
