# P3.1 — Viết src/router.py: nhãn → cấu hình truy xuất

> Giai đoạn 3 (Router truy xuất theo lớp) · Nhóm playbook: 02 (src) + 04 (tests) · Thời gian: 2–3 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Bảng ánh xạ (chủ đề, loại câu hỏi) → cấu hình truy xuất, viết dạng hàm thuần dễ test — đây là nơi nhãn phân loại "đổ" vào hệ thống.

## Ngữ cảnh cần đọc trước

- `src/pipeline.py`, `src/vector_db.py` — API truy xuất hiện tại (oversampling ×2, `filter` metadata tier/source).
- `data/evaluation/verify_v3_report.md` — crosstab chủ đề × nguồn (căn cứ quyết định `source_filter`).
- `.env.example` — giá trị cấu hình hiện tại.

## Nguyên tắc thiết kế (bắt buộc)

- **Giá trị mặc định = cấu hình hiện tại của hệ thống** (`RAG_TOP_K`, BM25 0.5 / Chroma 0.5, không lọc). Nhãn chỉ ĐIỀU CHỈNH, không đổi bản chất pipeline.
- Khi không có nhãn (classifier tắt/lỗi) → trả nguyên cấu hình gốc.
- Không bao giờ giảm top_k dưới giá trị gốc; không bao giờ trả trọng số tổng ≤ 0.

## Việc cần làm

1. Tạo `src/router.py`:
   - Dataclass `RetrievalConfig`: `top_k: int`, `bm25_weight: float`, `chroma_weight: float`, `source_filter: list[str] | None`, `enable_subquery: bool`.
   - `get_retrieval_config(labels: dict | None, base: RetrievalConfig) -> RetrievalConfig` — hàm thuần:
     - `labels=None` → trả nguyên `base` (classifier tắt / lỗi / câu tự do).
     - Theo `question_type`:
       - `TRA_CUU` → giữ base.
       - `SO_SANH` → `top_k + 2` và `enable_subquery=True` (lấy rộng vì cần nhiều nguồn).
       - `THU_TUC` → BM25 0.6 / Chroma 0.4 (giả thuyết ban đầu — thủ tục hay dùng từ khóa hành chính; ghi chú trong code "sẽ hiệu chỉnh theo kết quả A/B").
       - `NGOAI_PHAM_VI` → giữ base (việc nhắc từ chối nằm ở tầng generator — xem P3.4; KHÔNG skip truy xuất).
     - Theo `topic`: chỉ chủ đề có ≥ 80% câu thuộc ≤ 2 nguồn (tra crosstab trong verify_v3_report.md) mới điền `source_filter`; còn lại `None`. Đây là thiết kế phòng thủ — lọc hẹp làm rơi căn cứ nằm ở văn bản phụ.
2. Tạo `tests/test_router.py` (offline, hàm thuần): labels None; từng loại câu hỏi; topic có / không có source_filter; trọng số luôn hợp lệ; top_k không bao giờ thấp hơn base; labels dạng sai (thiếu khóa) không làm crash.

## Ràng buộc

- Nhóm 02 (src) + 04 (tests). KHÔNG nối pipeline (P3.2 lo).
- Bảng cấu hình nằm ở MỘT nơi duy nhất (const/dataclass trong router.py) — không rải cấu hình sang file khác.

## Sản phẩm

- `src/router.py`, `tests/test_router.py`

## Verify (bắt buộc)

- `venv\Scripts\python.exe -m pytest tests/test_router.py -v` xanh.
- Smoke script tạm trong `tmp/` (xóa sau): in bảng cấu hình cho 4 loại câu hỏi + 1 chủ đề có lọc + 1 chủ đề không lọc — đối chiếu đúng thiết kế.
