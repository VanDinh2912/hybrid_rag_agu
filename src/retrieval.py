"""Module xử lý truy xuất và mở rộng câu truy vấn (Query Expansion) cho Hybrid RAG.

Trách nhiệm:
|- Xây dựng từ điển `SYNONYM_DICTIONARY` ánh xạ giữa thuật ngữ đời thường / học vụ
  và các từ đồng nghĩa pháp lý theo Quy chế ĐHAG.
|- `expand_query_with_synonyms(normalized_query: str) -> str`: tự động ghép các từ đồng nghĩa
  vào câu truy vấn nhằm tăng độ bao phủ (Recall), giúp True Hybrid Search (BM25 + ChromaDB)
  không bỏ sót các chunk tài liệu chứa thuật ngữ tương đương hoặc khác dị bản.

Vai trò trong kiến trúc Hybrid RAG:
- Layer 2 của pipeline: Query Expansion sau Normalization
- Mục tiêu: Tăng Recall bằng cách mở rộng từ khóa đồng nghĩa pháp lý
- Thuật toán: Dictionary-based expansion với fold (bỏ dấu) để khớp OCR

Thuật toán liên quan:
- BM25 (Lexical Search): Tìm kiếm từ khóa chính xác dựa trên TF-IDF
  Công thức: score(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))
  Xem chi tiết: docs/architecture/SYSTEM_ARCHITECTURE.md - Section 2.1

- BGE-M3 (Vector Search): Embedding đa ngôn ngữ với Cosine Similarity
  Công thức: similarity(q, d) = (q · d) / (||q|| * ||d||)
  Xem chi tiết: docs/architecture/SYSTEM_ARCHITECTURE.md - Section 2.2

- RRF (Reciprocal Rank Fusion): Dung hợp kết quả BM25 + ChromaDB
  Công thức: RRF_score(d) = Σ (k / (rank_i(d) + k)), với k = 60
  Xem chi tiết: docs/architecture/SYSTEM_ARCHITECTURE.md - Section 2.3
"""

import re
from typing import Any, Optional

import ollama

from src.config import settings
from src.text_utils import fold

# Từ điển ánh xạ từ khóa học vụ & từ đồng nghĩa pháp lý theo Quy chế đào tạo ĐHAG.
# Mỗi key là từ khóa gốc, value là danh sách các từ đồng nghĩa pháp lý tương ứng.
# Từ điển này được sử dụng trong expand_query_with_synonyms() để tăng Recall.
SYNONYM_DICTIONARY: dict[str, list[str]] = {
    # 1. Kỷ luật / Thôi học
    "đuổi học": ["buộc thôi học", "thôi học", "kỷ luật"],
    "buộc thôi học": ["thôi học", "kỷ luật", "đuổi học"],
    "thôi học": ["buộc thôi học", "kỷ luật"],
    
    # 2. Rèn luyện
    "yếu": ["xếp loại rèn luyện Yếu", "kết quả rèn luyện"],
    "loại yếu": ["xếp loại rèn luyện Yếu", "rèn luyện loại yếu"],
    "kém": ["xếp loại rèn luyện Kém", "rèn luyện"],
    "rèn luyện": ["kết quả rèn luyện", "đánh giá kết quả rèn luyện", "điểm rèn luyện"],
    "điểm rèn luyện": ["kết quả rèn luyện", "xếp loại rèn luyện"],
    
    # 3. Điểm số & Học phần
    "rớt môn": ["điểm học phần lần thứ nhất dưới 5.5", "học lại", "không đạt"],
    "trượt môn": ["điểm học phần lần thứ nhất dưới 5.5", "học lại", "chưa đạt"],
    "học lại": ["đăng ký học lại", "học cải thiện"],
    "học phần": ["môn học", "học phần điều kiện"],
    "môn học": ["học phần", "mã học phần"],
    "cảnh báo học vụ": ["cảnh báo kết quả học tập", "buộc thôi học"],
    "đtbhk": ["điểm trung bình học kỳ", "điểm trung bình"],
    "gpa": ["điểm trung bình tích lũy", "thang điểm 4", "thang điểm 10"],
    
    # 4. Tài chính / Học phí
    "nợ học phí": ["hỗ trợ học phí", "miễn giảm học phí", "gia hạn nộp học phí"],
    "tiền học": ["học phí", "hỗ trợ học phí", "miễn giảm học phí"],
    "học phí": ["hỗ trợ học phí", "miễn giảm học phí", "chế độ chính sách học phí"],
    "miễn giảm học phí": ["hỗ trợ chi phí học tập", "chế độ miễn giảm"],
    "hoãn học phí": ["gia hạn nộp học phí", "đơn xin gia hạn"],
    
    # 5. Tốt nghiệp & Khen thưởng
    "tốt nghiệp": ["xét tốt nghiệp", "chuẩn đầu ra", "điều kiện công nhận tốt nghiệp"],
    "khen thưởng": ["danh hiệu thi đua", "khen thưởng sinh viên", "sinh viên 5 tốt"],
    "học bổng": ["học bổng khuyến khích học tập", "khen thưởng"],
    "chuẩn đầu ra": ["elo", "chuẩn ngoại ngữ", "chuẩn tin học"],
    "tiên quyết": ["học phần tiên quyết", "học phần học trước"],
}


def expand_query_with_synonyms(normalized_query: str) -> str:
    """Tự động bổ sung các từ đồng nghĩa pháp lý tương ứng vào câu truy vấn.

    Hàm này là giao diện chính của Layer Query Expansion trong kiến trúc Hybrid RAG.
    Nó sử dụng từ điển đồng nghĩa SYNONYM_DICTIONARY để mở rộng câu truy vấn,
    giúp tăng độ bao phủ (Recall) của True Hybrid Search (BM25 + ChromaDB).

    Nguyên tắc hoạt động:
    1. Tìm kiếm không phân biệt dấu và chữ hoa/thường dựa trên văn bản đã fold
       (bỏ dấu thanh) để khớp với tài liệu OCR có thể mất dấu.
    2. Tránh lặp lại những từ đã có mặt sẵn trong câu truy vấn.
    3. Giữ nguyên cấu trúc câu ban đầu ở đầu chuỗi để bảo toàn trọng số ngữ nghĩa,
       ghép các từ đồng nghĩa mở rộng ở cuối chuỗi.
    4. Sử dụng regex với word boundary (\b) để khớp chính xác từ khóa (không substring).

    Ví dụ:
        Input:  "Sinh viên bị điểm yếu có bị đuổi học không?"
        Output: "Sinh viên bị điểm yếu có bị đuổi học không? buộc thôi học kỷ luật xếp loại rèn luyện Yếu"

    Thuật toán:
        For each keyword in SYNONYM_DICTIONARY:
            If keyword (folded) matches in query (folded):
                For each synonym:
                    If synonym (folded) not in query (folded) AND not already added:
                        Add synonym to expansion list
        Return original_query + " " + " ".join(expansion_list)

    Tham số:
        normalized_query: Câu hỏi đã chuẩn hóa từ Layer Normalization (Qwen)

    Trả về:
        Câu truy vấn đã mở rộng với từ đồng nghĩa, hoặc câu gốc nếu không có khớp

    Xem chi tiết:
        - Từ điển: SYNONYM_DICTIONARY (gần 50 cặp ánh xạ)
        - Kiến trúc: docs/architecture/SYSTEM_ARCHITECTURE.md - Section 2.3 (RRF)
    """
    if not isinstance(normalized_query, str):
        return "" if normalized_query is None else str(normalized_query)

    query = normalized_query.strip()
    if not query:
        return ""

    folded_query = fold(query)
    added_terms: list[str] = []
    seen_folded_terms: set[str] = set()

    # Quét qua từ điển đồng nghĩa
    for keyword, synonyms in SYNONYM_DICTIONARY.items():
        folded_keyword = fold(keyword)
        # Khớp theo ranh giới từ hoặc cụm từ
        pattern = r"(?:\b|_)" + re.escape(folded_keyword) + r"(?:\b|_)"
        if re.search(pattern, folded_query):
            for syn in synonyms:
                folded_syn = fold(syn)
                # Chỉ thêm nếu từ đồng nghĩa chưa có trong query gốc và chưa được thêm
                if folded_syn not in folded_query and folded_syn not in seen_folded_terms:
                    added_terms.append(syn)
                    seen_folded_terms.add(folded_syn)

    if not added_terms:
        return query

    # Ghép từ khóa mở rộng vào sau câu query gốc
    expansion_str = " ".join(added_terms)
    return f"{query} {expansion_str}".strip()


# =============================================================================
# Tách truy vấn con cho câu SO_SANH (P3.3)
# =============================================================================
# Câu so sánh / tổng hợp nhiều vế được tách thành 2–3 truy vấn con độc lập để
# truy xuất từng phần rồi gộp — mở độ phủ ngữ cảnh cho nhóm câu vốn yếu nhất.
# Nguyên tắc chịu lỗi giống tầng chuẩn hóa: MỌI sự cố (Qwen chết, output lệch
# định dạng, guardrail vi phạm) đều suy giảm mềm về `[query]` — tức KHÔNG tách,
# pipeline chạy y như đường đơn. Guardrail chống tách dở gồm:
#   (1) số dòng ngoài khoảng 2–3;
#   (2) cặp truy vấn con nào trùng nhau quá 80% token (đã fold, bỏ dấu);
#   (3) truy vấn con rỗng hoặc dài bất thường (> 200 ký tự — nghi model trả lời
#       thay vì tách).

MIN_SUB_QUERIES = 2
MAX_SUB_QUERIES = 3
MAX_SUBQUERY_CHARS = 200
MAX_PAIRWISE_OVERLAP = 0.8
SPLIT_NUM_PREDICT = 192  # đủ chỗ cho 3 dòng tiếng Việt ~45 từ

DEFAULT_SPLIT_MODEL = "qwen2.5:1.5b-instruct"
DEFAULT_SPLIT_HOST = "http://localhost:11434"
DEFAULT_SPLIT_TIMEOUT = 90.0

# Prompt tách truy vấn: 2 ví dụ few-shot CỐ ĐỊNH, không lấy từ benchmark để
# tránh overfit (quyết định đóng băng few-shot của classifier vẫn áp dụng cho
# mọi prompt Qwen trong hệ thống). Qwen2.5-1.5B cần few-shot mới ổn định.
SPLIT_PROMPT_TEMPLATE = (
    "Bạn là bộ tách truy vấn cho hệ thống tra cứu quy chế đào tạo đại học.\n"
    "Nhiệm vụ: tách câu hỏi so sánh / tổng hợp sau thành các mệnh đề con độc lập.\n"
    "QUY TẮC:\n"
    "- Mỗi mệnh đề con là MỘT truy vấn hoàn chỉnh, hỏi về MỘT vế của phép so sánh.\n"
    "- Giữ nguyên thực thể: mã số, con số, tên văn bản, tên danh hiệu.\n"
    "- Mỗi dòng là một truy vấn, tối đa 3 dòng.\n"
    "- KHÔNG trả lời câu hỏi, không giải thích, không đánh số.\n\n"
    "Ví dụ 1:\n"
    'Câu hỏi: "So sánh mức học phí của khối ngành kỹ thuật và khối ngành kinh tế '
    'theo quy định năm học 2026-2027?"\n'
    "Truy vấn con:\n"
    "Mức học phí của khối ngành kỹ thuật theo quy định năm học 2026-2027 là bao nhiêu?\n"
    "Mức học phí của khối ngành kinh tế theo quy định năm học 2026-2027 là bao nhiêu?\n\n"
    "Ví dụ 2:\n"
    'Câu hỏi: "Điều kiện xét học bổng khuyến khích học tập và học bổng tài năng '
    'khác nhau như thế nào?"\n'
    "Truy vấn con:\n"
    "Điều kiện xét học bổng khuyến khích học tập là gì?\n"
    "Điều kiện xét học bổng tài năng là gì?\n\n"
    'Câu hỏi: "{query}"\n'
    "Truy vấn con:"
)

_SUBQUERY_BULLET_RE = re.compile(r"^(?:[-*•–—]|\d{1,2}[.)\]:]+\s*|\(\d{1,2}\)\s*)")
_QUOTE_CHARS = "\"'`“”‘’"
_SUBQUERY_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _clean_subquery_lines(text: str) -> list[str]:
    """Parse output Qwen thành danh sách truy vấn con: mỗi dòng một truy vấn.

    Làm sạch dấu đầu dòng (bullet / số thứ tự / ngoặc đơn kiểu "(1)"), dấu nháy
    bao quanh và khoảng trắng thừa. Dòng rỗng bị bỏ qua.
    """
    sub_queries: list[str] = []
    for raw_line in text.replace("\r", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = _SUBQUERY_BULLET_RE.sub("", line).strip()
        line = line.strip(_QUOTE_CHARS).strip()
        line = re.sub(r"\s+", " ", line)
        if line:
            sub_queries.append(line)
    return sub_queries


def _fold_token_set(text: str, keep_numbers: bool = True) -> set[str]:
    """Tập token (đã fold, bỏ dấu) của một chuỗi — dùng cho guardrail trùng lặp."""
    tokens = set(_SUBQUERY_TOKEN_RE.findall(fold(text)))
    if not keep_numbers:
        tokens = {t for t in tokens if not t.isdigit()}
    return tokens


def _pairwise_overlap_too_high(
    sub_queries: list[str], max_overlap: float = MAX_PAIRWISE_OVERLAP
) -> bool:
    """True nếu có cặp truy vấn con nào "quá giống nhau" theo nghĩa tách dở.

    Quy tắc (thiết kế thực nghiệm P3.3 — cân bằng giữa hai nhu cầu đối lập):
    - Cặp giống hệt nhau sau fold → tách dở (Qwen nhân bản dòng) → loại.
    - Cặp giống nhau về NỘI DUNG (Jaccard token phi-số > 80%) VÀ giống nhau cả
      về THỰC THỂ (tập token số giống nhau) → khác nhau chỉ bằng từ đệm → loại.
    - Cặp chỉ khác nhau ở THỰC THỂ số (ELO 6 / ELO 7 / ELO 8 — dạng SO_SANH hợp
      lệ chiếm đa số trong v3) → GIỮ: đây chính là mục tiêu mở độ phủ của P3.3.
    Nếu lỡ tách một câu không-so-sánh thì tầng gộp của pipeline (dedup theo
    chunk_id + best-rank + cửa sổ cố định) vẫn đảm bảo ngữ cảnh không tệ hơn
    đường đơn — suy giảm mềm theo thiết kế.
    """
    folded = [fold(q) for q in sub_queries]
    content_sets = [_fold_token_set(q, keep_numbers=False) for q in sub_queries]
    number_sets = [
        {t for t in _fold_token_set(q) if t.isdigit()} for q in sub_queries
    ]
    for i in range(len(sub_queries)):
        for j in range(i + 1, len(sub_queries)):
            if folded[i] == folded[j]:
                return True
            a, b = content_sets[i], content_sets[j]
            if not a or not b:
                return True  # có câu không còn token nội dung → tách dở
            if number_sets[i] == number_sets[j]:
                union = a | b
                overlap = len(a & b) / len(union) if union else 1.0
                if overlap > max_overlap:
                    return True
    return False


def split_comparison_query(query: str, llm_client: Any = None) -> list[str]:
    """Tách câu hỏi so sánh thành 2–3 truy vấn con bằng Local Qwen.

    Hàm luôn trả về danh sách không rỗng: tách thành công → 2–3 truy vấn con;
    mọi trường hợp khác (lỗi gọi model, output lệch định dạng, guardrail vi phạm)
    → `[query]` (không tách) để pipeline suy giảm mềm về đường đơn.

    Tham số:
        query: Câu hỏi đã chuẩn hóa + mở rộng từ đồng nghĩa (thường là expanded_query).
        llm_client: Client có hàm `generate(prompt, temperature=...)` (ví dụ
            LocalSLM của pipeline). None → tự tạo ollama.Client từ biến môi trường
            (OLLAMA_MODEL / OLLAMA_HOST / OLLAMA_TIMEOUT).

    Trả về:
        [sub1, sub2, ...] nếu tách hợp lệ, ngược lại [query].
    """
    if not isinstance(query, str):
        return [str(query)] if query is not None else []
    question = query.strip()
    if not question:
        return [query]

    prompt = SPLIT_PROMPT_TEMPLATE.replace("{query}", question.replace('"', "'"))

    try:
        if llm_client is not None and callable(getattr(llm_client, "generate", None)):
            try:
                text = llm_client.generate(
                    prompt, temperature=0.0, num_predict=SPLIT_NUM_PREDICT
                )
            except TypeError:
                # Client chỉ chấp nhận (prompt, temperature) — ví dụ fake trong test.
                text = llm_client.generate(prompt, temperature=0.0)
        else:
            cfg = settings()
            model_name = cfg.text_or("OLLAMA_MODEL", DEFAULT_SPLIT_MODEL)
            host = cfg.text_or("OLLAMA_HOST", DEFAULT_SPLIT_HOST)
            timeout = cfg.float_required("OLLAMA_TIMEOUT", DEFAULT_SPLIT_TIMEOUT)
            client = ollama.Client(host=host, timeout=timeout)
            response = client.generate(
                model=model_name,
                prompt=prompt,
                options={"temperature": 0.0, "num_predict": SPLIT_NUM_PREDICT},
                stream=False,
            )
            text = (
                response.get("response")
                if isinstance(response, dict)
                else getattr(response, "response", "")
            )
    except Exception as exc:
        print(
            "[SubQuery] Cảnh báo: không gọi được Qwen để tách truy vấn "
            f"({type(exc).__name__}: {exc}) — dùng nguyên câu hỏi."
        )
        return [question]

    sub_queries = _clean_subquery_lines(text or "")
    if not (MIN_SUB_QUERIES <= len(sub_queries) <= MAX_SUB_QUERIES):
        print(
            f"[SubQuery] Guardrail: output có {len(sub_queries)} dòng (cần "
            f"{MIN_SUB_QUERIES}–{MAX_SUB_QUERIES}) — không tách, dùng nguyên câu hỏi."
        )
        return [question]
    if any(len(sub) > MAX_SUBQUERY_CHARS for sub in sub_queries):
        print(
            f"[SubQuery] Guardrail: có truy vấn con dài hơn {MAX_SUBQUERY_CHARS} ký tự "
            "(nghi model trả lời thay vì tách) — dùng nguyên câu hỏi."
        )
        return [question]
    if _pairwise_overlap_too_high(sub_queries):
        print(
            f"[SubQuery] Guardrail: các truy vấn con trùng nhau quá "
            f"{MAX_PAIRWISE_OVERLAP:.0%} token — không tách, dùng nguyên câu hỏi."
        )
        return [question]
    return sub_queries
