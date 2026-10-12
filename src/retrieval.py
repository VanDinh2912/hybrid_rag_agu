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
  Xem chi tiết: SYSTEM_ARCHITECTURE.md - Section 2.1

- BGE-M3 (Vector Search): Embedding đa ngôn ngữ với Cosine Similarity
  Công thức: similarity(q, d) = (q · d) / (||q|| * ||d||)
  Xem chi tiết: SYSTEM_ARCHITECTURE.md - Section 2.2

- RRF (Reciprocal Rank Fusion): Dung hợp kết quả BM25 + ChromaDB
  Công thức: RRF_score(d) = Σ (k / (rank_i(d) + k)), với k = 60
  Xem chi tiết: SYSTEM_ARCHITECTURE.md - Section 2.3
"""

import re
from typing import Optional

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
        - Kiến trúc: SYSTEM_ARCHITECTURE.md - Section 2.3 (RRF)
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
