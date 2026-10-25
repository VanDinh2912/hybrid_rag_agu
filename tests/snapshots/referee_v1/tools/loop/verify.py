"""Trọng tài deterministic của vòng lặp: chấm MỘT kết quả pipeline trên MỘT item test.

Vì sao không dùng LLM judge: quota Gemini ~14 request/ngày (đã đo) nên mọi vòng lặp
hàng nghìn câu phải chấm bằng code. Vì sao không dùng token-overlap 0.3 như
`faithfulness_heuristic`: overlap cao vẫn có thể bịa đúng chỗ nguy hiểm nhất
(mã môn học CON515 thay vì CON915 — vụ này có thật, see outputs/ab_results_*).
Đơn vị kiểm chứng ở đây là THỰC THỂ, dùng lại `src/answer_guard` để số đo và
hành vi guardrail production không bao giờ lệch nhau.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.answer_guard import check_grounding  # noqa: E402
from src.text_utils import fold  # noqa: E402

REFUSAL_MARKERS = (
    "không đủ thông tin",
    "khong du thong tin",
    "không tìm thấy",
    "không có căn cứ",
    "không nêu trong tài liệu",
)
# So khớp luôn sau `fold` (mất dấu) nên danh sách marker cũng phải mất dấu.
REFUSAL_MARKERS_FOLDED = tuple(fold(m) for m in REFUSAL_MARKERS)

# Ngưỡng coi là "đã truy xuất trúng": chunk vàng nằm trong sources (recall window).
PASS_VERDICTS = {"PASS_CORRECT", "PASS_REFUSAL", "PASS_CORRECTED_TRAP"}

# --- Dấu vân tay của trọng tài -------------------------------------------------
# Round r0 trả giá thật: verdict của nó được ghi bởi verify.py còn bug `has_gold_chunk`
# (434 FAIL_RETRIEVAL, số đúng là 337). Khi trọng tài thay đổi thì mọi số cũ KHÔNG còn
# so sánh được nữa, nên round phải TỰ KÝ phiên bản trọng tài đã chấm mình và cổng duyệt
# phải từ chối so hai round khác chữ ký.
REFEREE_FILES = (
    Path(__file__).resolve(),
    ROOT / "src" / "answer_guard.py",
    ROOT / "src" / "text_utils.py",
)


def referee_fingerprint() -> str:
    """SHA-256(12 ký tự đầu) trên nội dung các file tạo nên trọng tài.

    Rỗng nếu file chưa đọc được (ví dụ đóng gói lạ) — `gate` coi là không xác định
    được chứ không phải "trùng".
    """
    h = hashlib.sha256()
    seen = False
    for path in REFEREE_FILES:
        try:
            h.update(path.read_bytes())
            seen = True
        except OSError:
            continue
    return h.hexdigest()[:12] if seen else ""


def is_refusal(answer: str) -> bool:
    # Marker PHẢI được fold cùng chiều với câu trả lời: so "không tìm thấy" (có dấu)
    # với văn bản đã mất dấu thì không bao giờ khớp, và câu từ chối bị tính là câu
    # trả lời thường.
    f = fold(answer or "")
    return any(m in f for m in REFUSAL_MARKERS_FOLDED)


def _number_in(text: str, needle: str) -> bool:
    """So khớp số có biện giới (để '110' không khớp loạn trong '1102')."""
    if not needle:
        return False
    variants = {needle, needle.replace(".", "").replace(",", "")}
    hay = fold(text)
    for v in variants:
        if re.search(rf"(?<!\d){re.escape(v)}(?!\d)", hay):
            return True
    return fold(needle) in hay


def rank_of_gold(item: dict, sources: list[dict]) -> Optional[int]:
    gold = item.get("gold_chunk_id")
    if gold is None:
        return None
    for src in sources or []:
        if src.get("chunk_id") == gold:
            return int(src.get("rank", 0)) or None
    return None


def expected_source_in_window(item: dict, result: dict, top_k: int) -> Optional[bool]:
    """Có đúng VĂN BẢN mà câu hỏi cần nằm trong cửa sổ top_k hay không.

    Đây là tín hiệu đo được ở PHA RẺ cho item neo theo cả văn bản (HUMAN, 97 câu
    viết tay): chúng không có một `gold_chunk_id` duy nhất, nên `gold_in_top_k` của
    chúng vô nghĩa và cổng duyệt từng mở mà không hề nhìn vào cái neo. Với lever
    sửa `source_filter` của router, "văn bản đúng có lọt vào cửa sổ không" chính xác
    là thứ phải đo trước khi bỏ tiền sinh văn bản.
    """
    doc = item.get("source_document")
    if not doc:
        return None
    want = fold(str(doc))
    return any(fold(str(s.get("source") or "")) == want for s in (result.get("sources") or [])[:top_k])


def _row(
    item: dict,
    verdict: str,
    severity: int,
    refusal: bool,
    gold_rank: Optional[int],
    in_contexts: bool,
    grounding,
    unsupported: list,
    result: dict,
    detail: dict,
    top_k: int = 6,
) -> dict:
    predicted = result.get("labels") or result.get("predicted_labels") or {}
    contexts = result.get("contexts") or []
    return {
        "id": item.get("id"),
        "family": item.get("family"),
        "split": item.get("split"),
        "verdict": verdict,
        "severity": severity,
        "is_refusal": refusal,
        "gold_rank_in_sources": gold_rank,
        "gold_in_top_k": in_contexts,
        # has_gold_chunk PHẢI đi kèm: `gold_in_top_k=False` chỉ là "không trúng" vì
        # hai lý do khác nhau hẳn (chunk vàng không vào cửa sổ vs. item này không có
        # chunk vàng duy nhất để mà vào — HUMAN/SOURCE_LOOKUP nhiều bản sao). Không
        # có cờ này thì mẫu số của recall lẫn lộn cả hai và cổng duyệt so một con số
        # vô nghĩa (đã vấp thật ở r0).
        "has_gold_chunk": item.get("gold_chunk_id") is not None,
        "grounding_score": grounding.grounding_score if grounding else None,
        "n_unsupported": len(unsupported),
        "unsupported": unsupported,
        "predicted_question_type": predicted.get("question_type"),
        "predicted_topic": predicted.get("topic"),
        "expected_topic": item.get("topic"),
        "expected_question_type": (
            "NGOAI_PHAM_VI"
            if item.get("family") in ("REFUSE_OOD", "REFUSE_MISSING_DOC")
            else None
        ),
        "expected_citation_source": item.get("source_document"),
        "expected_source_in_window": expected_source_in_window(item, result, top_k),
        "answer_chars": len(result.get("answer") or ""),
        "contexts_chars": sum(len(c or "") for c in contexts),
        "latency_seconds": result.get("latency_seconds"),
        "detail": detail,
        "raw_query": item.get("raw_query"),
        "answer_preview": (result.get("answer") or "")[:300],
    }


def score_item(item: dict, result: dict, top_k: int = 6) -> dict:
    """Trả về verdict + các tín hiệu phục vụ triage (mô hình nào cần sửa)."""
    answer = result.get("answer")
    # answer is None = kết quả của PHA TRUY XUẤT (chưa sinh văn bản): chỉ được phép
    # kết luận lỗi truy xuất, mọi thứ khác để PENDING_GENERATION.
    retrieval_only = answer is None
    answer = answer or ""
    contexts = result.get("contexts") or []
    sources = result.get("sources") or []
    question = item.get("raw_query") or ""
    family = item.get("family")
    refusal = is_refusal(answer)
    gold_rank = rank_of_gold(item, sources)
    # HAS_GOLD_CHUNK: item có chunk vàng đánh chỉ số chính xác hay không. Item neo
    # theo CẢ VĂN BẢN (HUMAN, và SOURCE_LOOKUP nhiều bản sao) không có một chunk vàng
    # duy nhất -> không được quy lỗi "không có chunk vàng trong cửa sổ" cho truy xuất.
    has_gold_chunk = item.get("gold_chunk_id") is not None
    in_contexts = any(
        (item.get("gold_chunk_id") is not None and s.get("chunk_id") == item["gold_chunk_id"])
        for s in sources[:top_k]
    )
    # Tên văn bản do pipeline inject vào cuối câu trả lời (không phải model viết),
    # nên đưa vào khung so khớp — nếu không mọi số trong tên file bị gọi là bịa.
    source_names = [str(s.get("source") or "") for s in sources]
    grounding = check_grounding(answer, contexts, question, extra_haystack=source_names) if answer else None

    verdict: str
    severity: int
    detail: dict[str, Any] = {}

    if retrieval_only:
        if family in ("REFUSE_OOD", "REFUSE_MISSING_DOC") or item.get("expected_answer_type") == "refuse":
            # Câu ngoài phạm vi: vẫn cần xem generator có bịa không -> bắt buộc sinh.
            verdict, severity = "PENDING_GENERATION", 0
        elif not has_gold_chunk or in_contexts:
            verdict, severity = "PENDING_GENERATION", 0
        else:
            verdict, severity = "FAIL_RETRIEVAL", 2
            detail["gold_rank_in_sources"] = gold_rank
        return _row(item, verdict, severity, False, gold_rank, in_contexts, None, [], result, detail, top_k=top_k)

    if item.get("expected_answer_type") == "refuse":
        # Câu ngoài phạm vi: trả lời = bịa đặt, nghiêm trọng nhất.
        if refusal:
            verdict, severity = "PASS_REFUSAL", 0
        else:
            verdict, severity = "FAIL_HALLUCINATED_ON_UNANSWERABLE", 3
            detail["unsupported"] = [
                {"kind": e.kind, "text": e.text} for e in (grounding.unsupported if grounding else [])
            ]
    elif family in ("TRAP", "TRAP_OCR"):
        wrong = item.get("wrong_value") or ""
        right = item.get("correct_value") or ""
        if refusal:
            verdict, severity = "PASS_REFUSAL", 0
        elif wrong and _number_in(answer, wrong):
            # Model xác nhận con số sai => đồng lõa với tiền đề độc.
            verdict, severity = "FAIL_CONFIRMED_FALSE_PREMISE", 3
            detail["wrong_value"] = wrong
        elif right and _number_in(answer, right):
            verdict, severity = "PASS_CORRECTED_TRAP", 0
        else:
            verdict, severity = "FAIL_INCOMPLETE", 1
            detail["expected_value"] = right
    else:
        if refusal:
            # Phân biệt hai thứ rất khác nhau (bản trước gộp chung -> lever map đổ
            # oan cho guardrail): từ chối khi chunk vàng KHÔNG có trong cửa sổ là
            # hành vi ĐÚNG của một hệ thống trung thực, nút thắt thật là truy xuất.
            # Chỉ gọi là OVERREFUSAL (lỗi guardrail/prompt) khi căn cứ đã nằm ngay
            # trước mặt model mà nó vẫn nói "không đủ thông tin".
            if in_contexts or not has_gold_chunk:
                verdict, severity = "FAIL_OVERREFUSAL", 2
            else:
                verdict, severity = "FAIL_RETRIEVAL", 2
                detail["refused_but_root_cause_is_retrieval"] = True
                detail["gold_rank_in_sources"] = gold_rank
        elif not in_contexts:
            # Không có chunk vàng trong cửa sổ generator: lỗi truy xuất, chưa kịp đổ cho sinh.
            verdict, severity = ("FAIL_RETRIEVAL", 1) if gold_rank else ("FAIL_RETRIEVAL", 2)
            detail["gold_rank_in_sources"] = gold_rank
        elif grounding and grounding.fabricated:
            verdict, severity = "FAIL_FABRICATED", 3
            detail["unsupported"] = [
                {"kind": e.kind, "text": e.text} for e in grounding.unsupported
            ]
        elif not _answer_covers_gold(item, answer):
            verdict, severity = "FAIL_INCOMPLETE", 1
            detail["missing_entities"] = [
                e for e in item.get("required_entities", []) if not _number_in(answer, e) and fold(e) not in fold(answer)
            ]
        else:
            verdict, severity = "PASS_CORRECT", 0

    unsupported = (
        [{"kind": e.kind, "text": e.text} for e in grounding.unsupported] if grounding else []
    )
    return _row(item, verdict, severity, refusal, gold_rank, in_contexts, grounding, unsupported, result, detail, top_k=top_k)


def _answer_covers_gold(item: dict, answer: str) -> bool:
    """Câu trả lời có nêu được thực thể vàng không (chấp nhận biến thể số)."""
    required = [e for e in item.get("required_entities", []) if e]
    if not required:
        return bool(item.get("primary_entity")) and _entity_in_answer(item["primary_entity"], answer)
    return any(_entity_in_answer(e, answer) for e in required)


def _entity_in_answer(entity: str, answer: str) -> bool:
    if re.fullmatch(r"[\d.,\s]+đ?%", entity or "") or re.search(r"\d", entity or ""):
        return _number_in(answer, entity)
    return fold(entity) in fold(answer)


def aggregate(rows: list[dict], by: str = "family") -> dict:
    """Tổng hợp theo nhóm: tỉ lệ đạt, phân bố lỗi, tỉ lệ bịa đặt, từ chối oan."""
    out: dict[str, dict] = {}
    for row in rows:
        key = row.get(by) or "?"
        bucket = out.setdefault(
            key,
            {"n": 0, "pass": 0, "fabricated": 0, "overrefusal": 0, "missed_refusal": 0, "retrieval": 0, "incomplete": 0, "verdicts": Counter()},
        )
        bucket["n"] += 1
        bucket["verdicts"][row["verdict"]] += 1
        if row["verdict"] in PASS_VERDICTS:
            bucket["pass"] += 1
        if row["verdict"] in ("FAIL_FABRICATED", "FAIL_CONFIRMED_FALSE_PREMISE", "FAIL_HALLUCINATED_ON_UNANSWERABLE"):
            bucket["fabricated"] += 1
        if row["verdict"] == "FAIL_OVERREFUSAL":
            bucket["overrefusal"] += 1
        if row["verdict"] == "FAIL_HALLUCINATED_ON_UNANSWERABLE":
            bucket["missed_refusal"] += 1
        if row["verdict"] == "FAIL_RETRIEVAL":
            bucket["retrieval"] += 1
        if row["verdict"] == "FAIL_INCOMPLETE":
            bucket["incomplete"] += 1
    for bucket in out.values():
        n = bucket["n"]
        pending = bucket["verdicts"].get("PENDING_GENERATION", 0)
        decided = n - pending
        bucket["n_pending_generation"] = pending
        bucket["pass_rate"] = round(bucket["pass"] / decided, 4) if decided else None
        bucket["fabrication_rate"] = round(bucket["fabricated"] / decided, 4) if decided else None
        bucket["verdicts"] = dict(bucket["verdicts"])
    return out


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
