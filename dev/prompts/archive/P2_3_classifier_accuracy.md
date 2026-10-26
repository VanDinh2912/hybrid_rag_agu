# P2.3 — Đo accuracy bộ phân loại trên 100 câu v3

> Giai đoạn 2 · Nhóm playbook: 04 · Thời gian: 1–2 ngày · **GATE của giai đoạn 2**

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Số liệu chính thức độ chính xác phân loại — cổng vào giai đoạn 3 và là một kết quả của chương thực nghiệm.

## Ngữ cảnh cần đọc trước

- `src/classifier.py`, `src/text_utils.py`
- `data/evaluation/benchmark_100_questions_v3.json`
- `logs/README.md` — quy ước thư mục logs.

## Việc cần làm

1. Tạo `src/evaluate_classifier.py`:
   - Chạy `classify_query()` trên `raw_query` (câu THÔ — đúng như pipeline thật; KHÔNG dùng `normalized_query`) của 100 câu v3.
   - So kết quả: `topic` ↔ `category`, `question_type` ↔ nhãn `question_type` của v3 (so không dấu qua `fold()`).
2. Xuất `logs/classifier/`:
   - `accuracy_report.md` — accuracy chủ đề + accuracy loại câu hỏi; **bắt buộc thêm per-class recall/F1 của từng `question_type` và macro-F1** (phân bố nhãn lệch ~85% TRA_CUU nên accuracy tổng một mình không nói lên gì — baseline đoán mù TRA_CUU đã đạt 85%); bảng lỗi từng câu (id, câu, dự đoán, đúng); tham số chạy (model, timeout, ngày).
   - `confusion_matrix_topic.csv`, `confusion_matrix_question_type.csv`
   - `results.json` — chi tiết từng câu (câu hỏi, dự đoán, đúng, raw_response).
3. Cập nhật `logs/README.md`: thêm 1 dòng `logs/classifier/` (sinh bởi `src/evaluate_classifier.py`, xóa được — chạy lại là có lại).
4. **GT-verify trước khi tin số:** rà 5 câu dự đoán SAI đầu bảng — xác định lỗi thuộc classifier hay nhãn GT sai (nhãn sai → quay lại P1.2 sửa + chạy lại verify P1.3; KHÔNG "hạ" số accuracy bằng cách bỏ câu).

## Ràng buộc

- Nhóm 04. Chạy offline 100% (Qwen local, dự kiến ~5–10 phút cho 100 câu) — KHÔNG tốn Gemini quota.
- Không sửa `src/evaluation.py` — script này độc lập.

## Sản phẩm

- `src/evaluate_classifier.py`
- `logs/classifier/` (4 file)
- `logs/README.md` +1 dòng

## Verify (bắt buộc)

- os.walk `logs/classifier/` đủ 4 file; `results.json` đủ 100 mục; spot-check 3 số trong report khớp `results.json`.
- Chạy lần 2 cho kết quả gần giống lần 1 (deterministic với temperature 0 — sai lệch lớn phải giải trình).

## GATE

- **Accuracy chủ đề ≥ 85% VÀ accuracy loại câu hỏi ≥ 80% VÀ recall từng lớp `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI` ≥ 50%** (ngưỡng per-class chốt 2026-10-20 cùng người dùng — lý do: lớp TRA_CUU chiếm 85% khiến accuracy tổng vượt ngưỡng kể cả khi classifier bắt hỏng toàn bộ lớp thiểu số, mà đúng các lớp này mới là chỗ router phát huy tác dụng) → sang P3.1.
- Không đạt: tăng few-shot (3 ví dụ mỗi chủ đề + thêm ví dụ cho lớp yếu), siết luật từ khóa lớp 2, hoặc gộp chủ đề (phải sửa TAXONOMY.md + v3 + chạy lại verify P1.3) rồi đo lại. KHÔNG hạ ngưỡng.
