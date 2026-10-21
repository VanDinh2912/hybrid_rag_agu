# P3.2 — Nối classifier + router vào pipeline qua ENABLE_CLASSIFIER

> Giai đoạn 3 · Nhóm playbook: 02 · Thời gian: 2–3 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Pipeline có 2 đường rõ ràng: `ENABLE_CLASSIFIER=0` (cũ nguyên vẹn) và `=1` (phân loại → router → truy xuất theo cấu hình).

## Ngữ cảnh cần đọc trước

- `src/pipeline.py` — toàn bộ, đặc biệt chỗ dựng BM25 + `EnsembleRetriever`.
- `src/vector_db.py` — API của `EnsembleRetriever`: trọng số đổi được theo từng câu không, hay chỉ dựng 1 lần khi khởi động? Trả lời câu hỏi này trước khi sửa.
- `src/classifier.py` (P2.1), `src/router.py` (P3.1), `tests/test_pipeline.py`.

## Việc cần làm

1. Đầu `pipeline.run`: nếu `ENABLE_CLASSIFIER=1` → `classify_query(raw_query)` → `get_retrieval_config(labels, base)` → dùng cấu hình này cho lượt truy xuất. Nếu `=0` → KHÔNG gọi classifier, đường cũ y nguyên (cả logic lẫn hiệu năng).
2. Mọi exception của classifier/router → log cảnh báo + dùng cấu hình gốc — lượt hỏi không chết.
3. Trọng số RRF:
   - Nếu `EnsembleRetriever` cho phép truyền weights per-query → áp `bm25_weight/chroma_weight` của router.
   - Nếu KHÔNG (dựng 1 lần khi khởi động) → trong nhiệm vụ này chỉ áp `top_k`, `source_filter`, sub-query; ghi issue "weights per-query" vào báo cáo để đánh giá thêm ở P4 — KHÔNG refactor cưỡng bức API cũ ở đây.
4. `source_filter`: nhánh vector áp qua `filter={"source": ...}` của ChromaDB (metadata đã có `source`); nhánh BM25 lọc hậu kiểm theo metadata nếu API cho phép — đọc `vector_db.py` để dùng đúng; không lọc được thì bỏ lọc + cảnh báo, không văng lỗi.
5. Kết quả trả về thêm 2 trường (không phá cấu trúc cũ): `labels` (dict hoặc None) và `retrieval_config` (dict) — để UI và evaluation dùng.
6. Cập nhật `tests/test_pipeline.py`: (a) flag 0 — mock classifier và khẳng định KHÔNG được gọi; (b) flag 1 với classifier fake — cấu hình áp đúng; (c) classifier ném lỗi → fallback về cấu hình gốc, kết quả vẫn trả về.

## Ràng buộc

- Nhóm 02. KHÔNG sửa `src/generator.py` (P3.4 lo).
- `ENABLE_CLASSIFIER=0` phải cho kết quả giống hệt trước khi có nhánh mới — verify bên dưới bắt mục này.

## Sản phẩm

- `src/pipeline.py`, `tests/test_pipeline.py` cập nhật.

## Verify (bắt buộc)

- `venv\Scripts\python.exe -m pytest` toàn bộ xanh.
- Smoke thật (PowerShell, dùng Qwen generator để KHÔNG tốn quota Gemini):
  - `$env:USE_QWEN_GENERATOR="1"; $env:ENABLE_CLASSIFIER="1"; venv\Scripts\python.exe main.py "Điều kiện xét tốt nghiệp?"` → kết quả có khối nhãn + cấu hình.
  - `$env:ENABLE_CLASSIFIER="0"` chạy lại cùng câu → KHÔNG có khối nhãn, câu trả lời tương đương.
