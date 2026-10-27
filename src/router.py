"""Router truy xuất theo lớp câu hỏi: nhãn phân loại → cấu hình truy xuất.

Tầng này là nơi nhãn của `src/classifier.py` (chủ đề + loại câu hỏi) "đổ" vào
hệ thống: `get_retrieval_config()` nhận dict nhãn và một cấu hình nền `base`,
trả về cấu hình đã được ĐIỀU CHỈNH cho phù hợp với lớp câu hỏi. Hàm thuần,
không I/O, không gọi model — dễ test offline.

Nguyên tắc thiết kế (theo playbook P3.1):
- Giá trị mặc định = cấu hình hiện tại của hệ thống (`RAG_TOP_K`,
  BM25 0.5 / Chroma 0.5, không lọc nguồn — xem `base_config_from_env()`).
  Nhãn chỉ điều chỉnh, không đổi bản chất pipeline.
- Không có nhãn (classifier tắt/lỗi/câu tự do) → trả nguyên `base`.
- Không bao giờ giảm top_k dưới giá trị gốc; không bao giờ trả trọng số
  tổng ≤ 0.

Bảng điều chỉnh theo `question_type`:
- TRA_CUU        → giữ nguyên base.
- SO_SANH        → top_k + 2 và bật `enable_subquery` (cần nhiều nguồn để đối
                   chiếu; tầng tách truy vấn con ở P3.3 đọc cờ này).
- THU_TUC        → BM25 0.6 / Chroma 0.4 (giả thuyết ban đầu: thủ tục hay dùng
                   từ khóa hành chính; sẽ hiệu chỉnh theo kết quả A/B ở P4).
- NGOAI_PHAM_VI  → giữ nguyên base — KHÔNG skip truy xuất (precision lớp này
                   chỉ 25% ở P2.3, bỏ truy xuất sẽ thành từ chối oan); việc
                   nhắc từ chối nằm ở tầng generator (P3.4).

Bảng `TOPIC_SOURCE_FILTER` — chủ đề → danh sách file nguồn được lọc:
- Chỉ chủ đề có ≥ MIN_QUESTIONS_FOR_SOURCE_FILTER câu trong benchmark v3 VÀ
  ≥ 80% số câu (phần in-corpus) thuộc ≤ 2 nguồn mới được lọc (thiết kế phòng
  thủ: lọc hẹp làm rơi căn cứ nằm ở văn bản phụ). Ngưỡng n≥5 do người dùng
  chốt 2026-10-20: quy tắc gốc "≥80% trong ≤2 nguồn" áp vào v3 cho kết quả
  biên — cả 14/14 chủ đề đạt 100% (benchmark dựng theo văn bản nguồn), kể cả
  chủ đề chỉ có 1–3 câu làm bằng chứng.
- Nguồn ở đây là giá trị metadata `source` của chunk trong ChromaDB (tên file
  gốc trong `data/corpus/**`), thống kê từ benchmark v3 ngày 2026-10-20.
"""

import os
from dataclasses import dataclass, replace
from typing import List, Optional

from dotenv import load_dotenv
from langchain_core.documents import Document

from src.classifier import QUESTION_TYPES, TOPICS, _TOPIC_BY_FOLDED
from src.text_utils import fold
from src.vector_db import DEFAULT_BM25_WEIGHT, DEFAULT_VECTOR_WEIGHT

load_dotenv()

# Ngưỡng độ tin cậy tối thiểu (số câu trong benchmark v3) để một chủ đề được
# áp source_filter. Chốt cùng người dùng 2026-10-20 (xem docstring module).
MIN_QUESTIONS_FOR_SOURCE_FILTER = 5

# Tỉ lệ tối thiểu câu in-corpus của chủ đề phải nằm gọn trong ≤ 2 nguồn.
MIN_SOURCE_CONCENTRATION = 0.8

# Trọng số dành riêng cho lớp THU_TUC (giả thuyết ban đầu, hiệu chỉnh theo A/B).
THU_TUC_BM25_WEIGHT = 0.6
THU_TUC_CHROMA_WEIGHT = 0.4

# Số chunk bổ sung khi lớp SO_SANH (cần cửa sổ rộng hơn để đối chiếu nhiều phía).
SO_SANH_TOP_K_BONUS = 2

# --- Bảng cấu hình duy nhất của router (không rải sang file khác) ------------
# Chủ đề → tuple tên file nguồn (metadata `source` trong ChromaDB). Chỉ gồm 8
# chủ đề đạt cả hai ngưỡng trên; 6 chủ đề còn lại (n=1–3 câu: bảo hiểm y tế,
# hành chính sinh viên, khen thưởng cấp ĐHQG, ký túc xá, tài chính sinh viên,
# thực tập chuyên đề) cố ý KHÔNG có filter — suy giảm về cấu hình chung.
TOPIC_SOURCE_FILTER = {
    "chương trình đào tạo": (
        "ban-mo-ta-ctdt-nganh-cntt-2021.pdf",
    ),
    "học phí": (
        "03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf",
        "Qui dinh muc hoc phi nam hoc 2026-2027.pdf",
    ),
    "cuộc thi chính luận": (
        "367-QĐ-ĐU ngay 08-4-2026.pdf",
    ),
    "đánh giá rèn luyện": (
        "1059-qd-dhag-2020-09-29.pdf",
    ),
    "khen thưởng sinh viên": (
        "888-qd-dhag-2022-08-08.pdf",
    ),
    "thực tập tốt nghiệp": (
        "ke-hoach-ttck-kltn-dh24th-2026.pdf",
    ),
    "quy chế công tác sinh viên": (
        "1054-qd-dhag-2020-09-28.pdf",
    ),
    "sinh viên 5 tốt": (
        "118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT "
        "VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf",
    ),
}

DEFAULT_TOP_K = 4


@dataclass
class RetrievalConfig:
    """Cấu hình truy xuất một lượt hỏi — đầy đủ tham số retrieval pipeline dùng."""

    top_k: int
    bm25_weight: float
    chroma_weight: float
    source_filter: Optional[List[str]] = None  # None = không lọc nguồn
    enable_subquery: bool = False  # True = P3.3 được phép tách truy vấn con


def base_config_from_env() -> RetrievalConfig:
    """Cấu hình nền = hiện trạng hệ thống trước khi có classifier/router.

    Đọc cùng các biến môi trường mà pipeline hiện tại dùng (RAG_TOP_K,
    BM25_WEIGHT, CHROMA_WEIGHT) nên ENABLE_CLASSIFIER=0 sẽ trả về đúng hành vi
    cũ. Giá trị sai/không dương rơi về mặc định.
    """
    try:
        top_k = int(os.getenv("RAG_TOP_K", str(DEFAULT_TOP_K)))
    except ValueError:
        top_k = DEFAULT_TOP_K
    if top_k <= 0:
        top_k = DEFAULT_TOP_K

    try:
        bm25_weight = float(os.getenv("BM25_WEIGHT", str(DEFAULT_BM25_WEIGHT)))
    except ValueError:
        bm25_weight = DEFAULT_BM25_WEIGHT
    try:
        chroma_weight = float(os.getenv("CHROMA_WEIGHT", str(DEFAULT_VECTOR_WEIGHT)))
    except ValueError:
        chroma_weight = DEFAULT_VECTOR_WEIGHT

    return RetrievalConfig(
        top_k=top_k,
        bm25_weight=bm25_weight,
        chroma_weight=chroma_weight,
        source_filter=None,
        enable_subquery=False,
    )


def _normalize_question_type(value: object) -> Optional[str]:
    """Chuẩn hóa question_type về 4 nhãn chuẩn; nhãn lạ/thiếu trả None."""
    if not isinstance(value, str):
        return None
    key = fold(value).strip().upper().replace(" ", "_").replace("-", "_")
    return key if key in QUESTION_TYPES else None


def _normalize_topic(value: object) -> Optional[str]:
    """Chuẩn hóa topic về 14 chuỗi chuẩn; nhãn lạ/thiếu trả None."""
    if value is None or not isinstance(value, str):
        return None
    return _TOPIC_BY_FOLDED.get(fold(value).strip())


def get_retrieval_config(labels: Optional[dict], base: RetrievalConfig) -> RetrievalConfig:
    """Ánh xạ nhãn phân loại → cấu hình truy xuất (hàm thuần, không sửa `base`).

    - `labels=None` hoặc không phải dict → trả bản sao nguyên `base` (classifier
      tắt / lỗi / câu tự do) — suy giảm mềm, pipeline không bao giờ chết vì
      router.
    - Nhãn thiếu khóa/không hợp lệ → phần điều chỉnh tương ứng bị bỏ qua.
    """
    if not isinstance(labels, dict):
        return replace(base)

    config = replace(base)

    # --- Theo loại câu hỏi ---
    question_type = _normalize_question_type(labels.get("question_type"))
    if question_type == "SO_SANH":
        # Không bao giờ giảm dưới base: chỉ cộng thêm.
        config.top_k = base.top_k + SO_SANH_TOP_K_BONUS
        config.enable_subquery = True
    elif question_type == "THU_TUC":
        config.bm25_weight = THU_TUC_BM25_WEIGHT
        config.chroma_weight = THU_TUC_CHROMA_WEIGHT
    # TRA_CUU và NGOAI_PHAM_VI giữ nguyên base (ngoài phạm vi → nhãn lạ cũng
    # giữ nguyên — suy giảm mềm về cấu hình chung).

    # --- Theo chủ đề: chỉ lọc nguồn với chủ đề có bằng chứng đủ mạnh ---
    topic = _normalize_topic(labels.get("topic"))
    sources = TOPIC_SOURCE_FILTER.get(topic) if topic else None
    config.source_filter = list(sources) if sources else None

    # --- Phòng thủ chung: trọng số tổng phải > 0 ---
    if config.bm25_weight <= 0 and config.chroma_weight <= 0:
        config.bm25_weight = base.bm25_weight
        config.chroma_weight = base.chroma_weight
    if config.top_k <= 0:
        config.top_k = base.top_k

    return config


# --- Bộ lọc "mềm" theo nguồn (P5.2, lever truy xuất) -------------------------
# Bằng chứng từ vòng lặp (data/loop/rounds/r0, 593 item pha truy xuất):
# gold@6 = 46.8% và 217/308 FAIL_RETRIEVAL có chunk vàng BỊ LOẠI KHỎI CỬA SỔ vì
# `source_filter` cắt cứng (165 item do nhãn chủ đề sai, 52 item do bảng
# TOPIC_SOURCE_FILTER quá hẹp). Nói cách khác router đang phạt sai lầm của
# classifier bằng cách xóa luôn bằng chứng — thay vì chỉ ưu tiên nguồn đúng.
#
# Chế độ mềm đổi "loại bỏ" thành "cộng ưu tiên theo hạng": chunk thuộc nguồn được
# router chọn được dời lên `rank_bonus` hạng so với thứ tự RRF gốc; chunk ngoài
# nguồn vẫn giữ suất trong cửa sổ. Mặc định TẮT để không đổi hành vi đã nghiệm thu.
ROUTER_SOFT_FILTER_ENV = "ROUTER_SOFT_FILTER"
ROUTER_FILTER_RANK_BONUS_ENV = "ROUTER_FILTER_RANK_BONUS"
DEFAULT_FILTER_RANK_BONUS = 3


def router_soft_filter_enabled() -> bool:
    """Cờ bật bộ lọc mềm theo nguồn. Mặc định TẮT (giữ nguyên hành vi cũ).

    Dùng tập giá trị BẬT tường minh (chứ không phải "trừ các giá trị tắt") để
    một giá trị rác trong env không vô tình bật lever.
    """
    return os.getenv(ROUTER_SOFT_FILTER_ENV, "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def router_filter_rank_bonus(default: int = DEFAULT_FILTER_RANK_BONUS) -> int:
    """Số hạng được cộng cho chunk thuộc nguồn router chọn (>= 0)."""
    raw = os.getenv(ROUTER_FILTER_RANK_BONUS_ENV, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(float(raw)))
    except ValueError:
        return default


def rescore_with_source_preference(
    docs: List[Document],
    allowed_sources: List[str],
    *,
    rank_bonus: int = DEFAULT_FILTER_RANK_BONUS,
) -> List[Document]:
    """Sắp lại ứng viên theo sở thích nguồn mà KHÔNG loại ai.

    Hạng RRF gốc là `pos`; chunk có metadata `source` trùng nguyên văn (so khớp
    không dấu, giống hệt bộ lọc cứng cũ) được tính `pos - rank_bonus`. Ổn định
    (stable) nên hai chunk cùng khóa giữ nguyên thứ tự tương đối.
    """
    if not allowed_sources or rank_bonus <= 0:
        return list(docs)
    allowed = {fold(str(source)) for source in allowed_sources}
    keyed = []
    for pos, doc in enumerate(docs):
        source = fold(str((getattr(doc, "metadata", None) or {}).get("source", "")))
        key = pos - rank_bonus if source in allowed else pos
        keyed.append((key, pos, doc))
    keyed.sort(key=lambda item: (item[0], item[1]))
    return [doc for _, _, doc in keyed]


# --- Hạn ngạch nguồn trong cửa sổ (P5.14, lever truy xuất kế tiếp) -------------
# Bằng chứng round r2 (811 item, cổng r2-vs-r1 KHÔNG ĐẠT): tăng bonus từ 3 lên 12 mua
# được neo HUMAN (77,32% -> 81,44%) nhưng mất gold@6 (76,57% -> 74,00%). Probe cơ chế
# trên 21 item hồi quy: 21/21 có chunk vàng nằm NGOÀI `source_filter`. Nghĩa là lỗi
# không nằm ở độ lớn con số bonus mà ở cấu trúc — khi bonus >= cỡ cửa sổ, MỘT nguồn
# được ưu tiên chiếm trọn cửa sổ và đẩy chunk vàng của nguồn khác ra, đúng vào những
# ca router đã chọn SAI nguồn (47,2% FAIL_RETRIEVAL của r2 vẫn do filter).
#
# Luật mới: không nguồn nào được chiếm quá `quota` suất trong danh sách ứng viên.
# Phần bị hoãn giữ nguyên thứ tự tương đối và nối vào cuối — mất ưu tiên, không mất
# suất. Mặc định TẮT (quota 0) để không đổi hành vi đã nghiệm thu.
ROUTER_SOURCE_QUOTA_ENV = "ROUTER_SOURCE_QUOTA"


def router_source_quota() -> int:
    """Số suất tối đa cho MỘT nguồn trong danh sách ứng viên (0 = không hạn ngạch)."""
    raw = os.getenv(ROUTER_SOURCE_QUOTA_ENV, "").strip()
    try:
        return max(0, int(float(raw)))
    except ValueError:
        return 0


def apply_source_quota(docs: List[Document], quota: int) -> List[Document]:
    """Giữ tối đa `quota` ứng viên mỗi nguồn, phần còn lại nối vào cuối theo thứ tự cũ."""
    if quota <= 0 or not docs:
        return list(docs)
    kept: List[Document] = []
    deferred: List[Document] = []
    used: dict[str, int] = {}
    for doc in docs:
        source = fold(str((getattr(doc, "metadata", None) or {}).get("source", "")))
        if used.get(source, 0) >= quota:
            deferred.append(doc)
            continue
        used[source] = used.get(source, 0) + 1
        kept.append(doc)
    return kept + deferred


# Đảm bảo bảng filter chỉ chứa chủ đề chuẩn (phát hiện lỗi đánh máy sớm).
_UNKNOWN_FILTER_TOPICS = [t for t in TOPIC_SOURCE_FILTER if t not in TOPICS]
if _UNKNOWN_FILTER_TOPICS:  # pragma: no cover
    raise RuntimeError(
        "TOPIC_SOURCE_FILTER có chủ đề không thuộc 14 nhãn chuẩn: "
        + ", ".join(_UNKNOWN_FILTER_TOPICS)
    )
