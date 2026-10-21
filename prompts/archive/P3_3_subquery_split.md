# P3.3 — Tách truy vấn con cho câu SO_SANH

> Giai đoạn 3 · Nhóm playbook: 02 · Thời gian: 2–4 ngày · **Mục kỹ thuật rủi ro nhất của giai đoạn 3**

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Câu so sánh / tổng hợp được tách thành 2–3 truy vấn con, truy xuất từng phần rồi gộp — mở độ phủ ngữ cảnh cho nhóm câu vốn yếu nhất (Hit thấp ở các lượt đo cũ).

## Ngữ cảnh cần đọc trước

- `src/pipeline.py` (nhánh truy xuất đã nối router ở P3.2), `src/retrieval.py`, `src/text_utils.py` (`fold()`).
- 3–5 câu `SO_SANH` thật trong v3 — dùng làm thí nghiệm smoke.

## Việc cần làm

1. Thêm `split_comparison_query(query: str) -> list[str]` vào `src/retrieval.py`:
   - Gọi Qwen với prompt: "Tách câu hỏi so sánh sau thành các mệnh đề con độc lập, giữ nguyên thực thể (mã số, con số, tên văn bản), mỗi dòng một truy vấn, tối đa 3 dòng, không trả lời câu hỏi."
   - Parse từng dòng; lỗi / đầu ra lệch định dạng → trả `[query]` (không tách).
2. Guardrail chống tách dở (vi phạm thì trả `[query]`): số dòng ngoài 2–3; các sub-query quá giống nhau (tỉ lệ token trùng qua `fold()` > 80% giữa cặp bất kỳ); sub-query rỗng / quá dài.
3. Trong pipeline: khi `retrieval_config.enable_subquery=True` VÀ `question_type="SO_SANH"`:
   - Truy xuất TỪNG sub-query với `retrieve_k` như thường (tái dùng index/Ensemble hiện có — KHÔNG dựng lại BM25 mỗi lượt).
   - Gộp kết quả: điểm mỗi chunk = điểm tốt nhất của nó qua các nhánh; loại trùng theo `chunk_id`; cắt về đúng cửa sổ oversampled như cũ — KHÔNG phình context của generator.
4. Tests offline: mock Qwen trả đủ dạng (2–3 dòng hợp lệ; 1 dòng; dòng trùng nhau; rác) → kiểm tra cả tách lẫn guardrail; test gộp dedup + giữ đúng kích thước cửa sổ.

## Bước 0 — Sửa main.py đọc USE_QWEN_GENERATOR (làm TRƯỚC khi smoke, 2026-10-20)

P3.2 phát hiện: `main.py` không đọc cờ `USE_QWEN_GENERATOR` (chỉ `src/evaluation.py` đọc) nên 2 lượt smoke P3.2 đã tiêu quota Gemini thật dù verify định "không tốn quota". Nhiệm vụ này sẽ smoke nhiều — sửa trước:

1. `main.py` đọc `USE_QWEN_GENERATOR` đúng ngữ nghĩa như `src/evaluation.py`: `=1` → dựng generator Qwen local thay cho Gemini (in cảnh báo rõ ràng đang chạy chế độ offline); mặc định giữ Gemini như cũ.
2. Thêm 1 unit test nhỏ cho nhánh này (mock, không gọi Ollama thật).
3. Toàn bộ smoke của nhiệm vụ này chạy với `USE_QWEN_GENERATOR=1` — KHÔNG tốn quota Gemini.

## Sản phẩm

- `src/retrieval.py` + `src/pipeline.py` cập nhật; tests mới.

## Verify (bắt buộc)

- `venv\Scripts\python.exe -m pytest` toàn bộ xanh.
- Smoke 3 câu `SO_SANH` thật từ v3 (Qwen local): in sub-query + chunk top từng nhánh — ngữ cảnh GỘP phải chứa nguồn của TẤT CẢ các vế so sánh (đối chiếu `source_document` của GT).
- So độ dài context trước/sau: cửa sổ đưa generator không tăng quá 20%.
