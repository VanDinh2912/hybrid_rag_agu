"""T3 — quyền từ chối nằm Ở TẦNG NGOÀI, quyết định bằng số deterministic.

Vì sao tồn tại: đo ở `tools/diag/ablation_generation.py` (T1) cho thấy đặt đúng chunk
vàng trước mặt Qwen 2.5:1.5B mà model vẫn nói "không đủ thông tin" ở 86,25% ca, và rút
ngữ cảnh xuống ±2 câu thì lên 95% — tức là LỜI MỜI TỪ CHỐI trong prompt đang được model
 dùng như đường thoát, không phải như phán quyết. Tầng sinh không có quyền từ chối nữa;
nó chỉ trích xuất. Phán quyết do hàm này trả, dựa trên ba tín hiệu đo được:

1. **Độ phủ thực thể phía CÂU HỎI** trong từng chunk (`extract_entities` của answer_guard
   chạy trên câu hỏi, KHÔNG chạy trên đáp án — xem mục "chống rò đáp án" dưới);
2. **Điểm truy xuất RRF** của chunk liên quan tốt nhất (hạng thực tế trong từng nhánh
   BM25/vector, không phải thứ hạng đã trộn);
3. **`check_grounding` sau sinh** — vẫn là guardrail sản xuất, cùng ngưỡng.

Toàn bộ nằm sau cờ `ENABLE_DECOUPLED_REFUSAL` (mặc định TẮT). Tắt cờ = module này không
được gọi, hành vi từng ký tự như cũ (test ghim trong `tests/test_decoupled_refusal.py`).

CHỐNG RÒ ĐÁP ÁN (bất biến #6 của vòng lặp): mọi "thực thể" dùng ở đây đều lấy từ phía
CÂU HỎI (`normalized_query`/`raw_query`) và từ tên nguồn mà router gọi. Các trường
`required_entities`, `primary_entity`, `gold_sentence`, `gold_chunk_id` của testset KHÔNG
bao giờ được đọc trong module này — chúng thuộc về trọng tài và phân tích hậu nghiệm.

Ngưỡng ĐÃ ĐĂNG KÝ TRƯỚC trong `data/loop/README.md` (mục T3) và không được chỉnh theo kết
quả của r8/r9; env chỉ tồn tại để tái lập phép đo trên máy khác.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

from src.answer_guard import (  # CHỈ import: answer_guard là file trọng tài, cấm sửa
    GroundingReport,
    check_grounding,
    extract_entities,
    is_enough_evidence,
)
from src.text_utils import fold  # import, không sửa
from src.vector_db import DEFAULT_RRF_C

# --- Ngưỡng đã đăng ký trước (data/loop/README.md mục T3) ------------------------------
DEFAULT_MIN_ENTITY_COVERAGE = 0.34
DEFAULT_MIN_TOKEN_OVERLAP = 0.20
DEFAULT_MIN_RRF_NORM = 0.90
DEFAULT_MIN_GROUNDING = 0.60
DEFAULT_MAX_UNSUPPORTED = 1

MIN_TOKEN_LEN = 4

# Token quá chung (hư từ/đầu đề pháp lý) không được tính là "bằng chứng liên quan":
# nếu tính, mọi câu hỏi "sinh viên ..." đều phủ mọi chunk và luật 2 mất nghĩa.
_STOPWORD_FOLDED = {
    "sinh", "vien", "cua", "va", "hoac", "la", "bao", "nhieu", "may", "muc", "the",
    "nay", "no", "co", "khong", "khi", "neu", "thi", "truong", "dai", "hoc", "nam",
    "nau", "quy", "dinh", "che", "do", "diem", "lai", "lam", "can", "de", "duoc",
    "tu", "den", "theo", "voi", "cho", "trong", "ngoai", "trung", "binh",
}

REFUSAL_REASON_NO_EVIDENCE = "no_evidence"
REFUSAL_REASON_OFF_TOPIC = "off_topic_window"
REFUSAL_REASON_WEAK_RANK = "weak_retrieval_rank"
REFUSAL_REASON_UNGROUNDED = "ungrounded"
REFUSAL_REASON_MODEL_REFUSES = "model_still_refuses"
REFUSAL_REASON_EMPTY = "empty_answer"


def decoupled_refusal_enabled() -> bool:
    """Cờ bật quyền từ chối ở tầng ngoài. Mặc định TẮT để giữ nguyên hành vi đã nghiệm thu.

    Chuỗi rỗng cũng tính là TẮT: `export ENABLE_DECOUPLED_REFUSAL=` trên shell nghĩa là
    "tắt", không phải "bật" — tránh một biến chưa gán giá trị làm đổi cả round.
    """
    return os.getenv("ENABLE_DECOUPLED_REFUSAL", "0").strip().lower() not in {
        "",
        "0",
        "false",
        "no",
        "off",
    }


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if 0.0 <= value <= 1.0 else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def thresholds() -> dict[str, Any]:
    """Bộ ngưỡng đang dùng (đã kẹp giá trị hỏng về mặc định đã đăng ký)."""
    return {
        "min_entity_coverage": _env_float("DEC_MIN_ENTITY_COVERAGE", DEFAULT_MIN_ENTITY_COVERAGE),
        "min_token_overlap": _env_float("DEC_MIN_TOKEN_OVERLAP", DEFAULT_MIN_TOKEN_OVERLAP),
        "min_rrf_norm": _env_float("DEC_MIN_RRF_NORM", DEFAULT_MIN_RRF_NORM),
        "min_grounding": _env_float("DEC_MIN_GROUNDING", DEFAULT_MIN_GROUNDING),
        "max_unsupported": _env_int("DEC_MAX_UNSUPPORTED", DEFAULT_MAX_UNSUPPORTED),
    }


@dataclass
class Decision:
    """Phán quyết của tầng ngoài + toàn bộ bằng chứng số của nó (để log và hậu kiểm)."""

    refuse: bool
    reason: Optional[str] = None
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"refuse": self.refuse, "reason": self.reason, "features": self.features}


def log_decision(stage: str, decision: Decision, *, question: str = "", log=print) -> None:
    """Một dòng log cho mỗi quyết định — round log là nơi đếm lại, schema .jsonl giữ nguyên."""
    feats = decision.features
    summary = " ".join(
        f"{k}={feats[k]}" for k in (
            "best_rank_bm25", "best_rank_vector", "rrf_norm", "coverage", "overlap",
            "grounding_score", "n_unsupported",
        )
        if k in feats and feats[k] is not None
    )
    log(f"[DecoupledRefusal] {stage} refuse={int(decision.refuse)} reason={decision.reason or '-'} {summary}")


# --------------------------------------------------------------------------- tín hiệu đầu vào


def query_entities(question: str) -> list[str]:
    """Thực thể phía CÂU HỎI, quy về khóa so khớp (fold/ chuẩn hóa số).

    Trả về tập khóa đã khử trùng lặp. Rỗng khi câu hỏi chỉ toàn từ thường (khi đó luật
    độ phủ tự động nhường cho luật overlap — không phạt câu hỏi không có thực thể).
    """
    if not question:
        return []
    keys: set[str] = set()
    for entity in extract_entities(question):
        keys.update(k for k in entity.keys() if k)
    return sorted(keys)


def content_tokens(question: str) -> list[str]:
    """Token nội dung của câu hỏi: fold, dài >= MIN_TOKEN_LEN, bỏ hư từ pháp lý."""
    tokens = re.findall(r"\w+", fold(question or ""), flags=re.UNICODE)
    return [t for t in tokens if len(t) >= MIN_TOKEN_LEN and t not in _STOPWORD_FOLDED]


def _coverage_of(keys: Sequence[str], haystack_folded: str) -> Optional[float]:
    if not keys:
        return None
    hit = sum(1 for k in keys if k and k in haystack_folded)
    return round(hit / len(keys), 4)


def _overlap_of(tokens: Sequence[str], haystack_folded: str) -> Optional[float]:
    if not tokens:
        return None
    hit = sum(1 for t in tokens if t in haystack_folded)
    return round(hit / len(tokens), 4)


def chunk_relevance(question: str, contexts: Sequence[str]) -> list[dict[str, Any]]:
    """Mỗi chunk một phần từ {coverage, overlap, relevant} theo ngưỡng đã đăng ký."""
    th = thresholds()
    keys = query_entities(question)
    tokens = content_tokens(question)
    out: list[dict[str, Any]] = []
    for text in contexts or []:
        hay = fold(text or "")
        cov = _coverage_of(keys, hay)
        ovl = _overlap_of(tokens, hay)
        relevant = bool(
            (cov is not None and cov >= th["min_entity_coverage"])
            or (ovl is not None and ovl >= th["min_token_overlap"])
        )
        out.append({
            "coverage": cov,
            "overlap": ovl,
            "relevant": relevant,
            "chars": len(hay),
        })
    return out


def rrf_norm(
    rank_bm25: Optional[int],
    rank_vector: Optional[int],
    *,
    bm25_weight: float,
    vector_weight: float,
    c: int = DEFAULT_RRF_C,
) -> Optional[float]:
    """Điểm RRF chuẩn hóa của MỘT chunk theo hạng thực trong từng nhánh (0..1].

    1,0 = hạng nhất của cả hai nhánh. Chunk không xuất hiện ở nhánh nào -> None.
    Chỉ có hạng trong nhánh trộn (đã RRF) thì không đo được độ "yên tâm" của truy xuất,
    nên pipeline phải truyền hạng thô của BM25 leg và vector leg.
    """
    if rank_bm25 is None and rank_vector is None:
        return None
    total = bm25_weight + vector_weight or 1.0
    w_b = bm25_weight / total
    w_v = vector_weight / total
    score = 0.0
    if rank_bm25 is not None:
        score += w_b / (c + max(1, int(rank_bm25)))
    if rank_vector is not None:
        score += w_v / (c + max(1, int(rank_vector)))
    best = 1.0 / (c + 1)  # hạng 1 cả hai nhánh, weights đã chuẩn hóa
    return round(min(1.0, score / best), 4)


# --------------------------------------------------------------------------- hai bước quyết định


def decide_pre_generation(
    *,
    question: str,
    contexts: Sequence[str],
    leg_ranks: Optional[Sequence[Optional[tuple[Optional[int], Optional[int]]]]] = None,
    bm25_weight: float = 1.0,
    vector_weight: float = 1.0,
) -> Decision:
    """Luật 1-3: quyền từ chối TRƯỚC khi tốn một lượt sinh.

    `leg_ranks[i] = (rank_bm25, rank_vector)` của chunk thứ i, hoặc None khi tầng truy
    xuất không cung cấp được (khi đó luật 3 được bỏ qua và ghi `rrf_unavailable` vào
    features — không được âm thầm coi như đạt).
    """
    th = thresholds()
    features: dict[str, Any] = dict(th)
    if not is_enough_evidence(list(contexts or [])):
        features["n_contexts"] = len(contexts or [])
        return Decision(True, REFUSAL_REASON_NO_EVIDENCE, features)

    relevance = chunk_relevance(question, contexts)
    best_index: Optional[int] = None
    for i, rel in enumerate(relevance):
        if rel["relevant"]:
            best_index = i
            break  # contexts đã theo thứ tự fusion: chunk liên quan đầu tiên là tốt nhất

    # Tổng hợp bằng chứng của cả cửa sổ để log (max coverage/overlap), không chỉ chunk đầu.
    features["n_relevant_chunks"] = sum(1 for r in relevance if r["relevant"])
    covs = [r["coverage"] for r in relevance if r["coverage"] is not None]
    ovls = [r["overlap"] for r in relevance if r["overlap"] is not None]
    if covs:
        features["coverage"] = max(covs)
    if ovls:
        features["overlap"] = max(ovls)

    if best_index is None:
        features["n_contexts"] = len(contexts)
        return Decision(True, REFUSAL_REASON_OFF_TOPIC, features)

    if leg_ranks is not None and len(leg_ranks) > best_index:
        pair = leg_ranks[best_index]
        if pair is not None:
            rank_b, rank_v = pair
            norm = rrf_norm(rank_b, rank_v, bm25_weight=bm25_weight, vector_weight=vector_weight)
            features["best_rank_bm25"] = rank_b
            features["best_rank_vector"] = rank_v
            features["rrf_norm"] = norm
            if norm is None:
                # chunk có mặt trong `leg_ranks` nhưng không có hạng ở NHÁNH NÀO (vd. chỉ
                # vào được nhờ fallback query) -> không đo được, không được coi là đạt.
                features["rrf_unavailable"] = True
            elif norm < th["min_rrf_norm"]:
                return Decision(True, REFUSAL_REASON_WEAK_RANK, features)
        else:
            features["rrf_unavailable"] = True
    else:
        features["rrf_unavailable"] = True

    return Decision(False, None, features)


def decide_post_generation(
    *,
    question: str,
    contexts: Sequence[str],
    answer: str,
    source_names: Iterable[str] = (),
    pre_features: Optional[dict[str, Any]] = None,
) -> Decision:
    """Luật 4-5: câu vừa sinh phải đứng được trên căn cứ, nếu không thì tầng ngoài từ chối.

    `source_names` là tên file do hệ thống dán vào prompt (không phải model bịa), nên
    đưa vào haystack y hệt cách `guard_qwen_answer` đang làm — nếu không số trong tên
    file bị gọi là khẳng định không căn cứ (bài học 7/11 ca UNSOURCED giả đã ghi ở
    `answer_guard.check_grounding`).
    """
    th = thresholds()
    features: dict[str, Any] = dict(pre_features or {})
    features.update(th)

    if not (answer or "").strip():
        return Decision(True, REFUSAL_REASON_EMPTY, features)

    from src.generator import (  # import trễ: tránh vòng module
        REFUSAL_TEXT,
        looks_like_refusal,
    )

    # `looks_like_refusal` so trên văn bản đã fold nên bắt được cả ba biến thể
    # "không đủ thông tin" / "không tìm thấy" / "không đủ căn cứ" mà model 1,5B hay
    # sinh ra — dùng thẳng hằng số có dấu sẽ không bao giờ khớp (fold đã xóa dấu).
    if looks_like_refusal(answer):
        features["raw_answer_chars"] = len(answer)
        return Decision(True, REFUSAL_REASON_MODEL_REFUSES, {**features, "refusal_text": REFUSAL_TEXT})

    report: GroundingReport = check_grounding(
        answer, list(contexts or []), question, extra_haystack=list(source_names)
    )
    score = report.grounding_score
    features["grounding_score"] = score
    features["n_unsupported"] = len(report.unsupported)
    features["entities_total"] = report.entities_total

    if score is None:
        # Câu không chứa khẳng định kiểm chứng được (diễn giải/không số): không có gì
        # để bác. Đã đăng ký trước: CHẤP NHẬN, để tỉ lệ bịa do gate + trọng tài đo.
        return Decision(False, None, features)
    # Đúng luật 4 đã đăng ký: fabricated HOẶC vượt trần unsupported HOẶC dưới trần
    # grounding — ba vế OR, không có vế nào phụ thuộc vế kia.
    if report.fabricated or len(report.unsupported) > th["max_unsupported"] or score < th["min_grounding"]:
        features["unsupported"] = sorted({e.text for e in report.unsupported})[:6]
        return Decision(True, REFUSAL_REASON_UNGROUNDED, features)
    return Decision(False, None, features)
