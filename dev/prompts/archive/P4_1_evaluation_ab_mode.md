# P4.1 — evaluation.py hỗ trợ chế độ A/B + chỉ số phân loại

> Giai đoạn 4 (Đánh giá A/B) · Nhóm playbook: 04 · Thời gian: 2 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Chạy được 2 lượt đánh giá bật/tắt tầng phân loại, đo thêm chất lượng phân loại và thống kê chỉ số theo nhóm câu hỏi.

## Ngữ cảnh cần đọc trước

- `src/evaluation.py` — TOÀN BỘ. Tái sử dụng mọi hàm chấm hiện có; KHÔNG copy code, KHÔNG đổi logic chấm cũ.
- `data/evaluation/benchmark_100_questions_v3.json`, `src/classifier.py`.

## Việc cần làm

1. Thêm cờ `--with-classifier`: lượt này chạy với `ENABLE_CLASSIFIER=1` (ghi rõ vào meta kết quả); không cờ → hành vi cũ 100%.
2. Per-question record (khi bật) thêm: `predicted_labels` (topic + question_type) và `retrieval_config` — lấy từ 2 trường pipeline đã thêm ở P3.2.
3. Summary thêm (chỉ khi chạy có classifier):
   - **Classification accuracy**: topic so với `category` của v3, question_type so với nhãn v3 (so không dấu qua `fold()`).
   - **Bảng per-question_type** và **per-category**: Hit@3/5/6, MRR, Citation F1, Faithfulness trung bình theo nhóm — để thấy router giúp nhóm nào.
   - **Tỉ lệ từ chối oan (false refusal)**: tỉ lệ câu `in_corpus=true` bị trả lời chứa `REFUSAL_MARKER` — báo cáo tổng thể VÀ phân theo `predicted_question_type`. Lý do (chốt 2026-10-20 sau P2.3): classifier over-predict `NGOAI_PHAM_VI` (precision 25%, 9 câu TRA_CUU bị gán nhầm) và `SO_SANH` (33%, 10 câu) — chỉ số này lượng hóa trực tiếp tác hại của lỗi gán nhãn lên hành vi từ chối; danh sách 19 câu bị gán nhầm lấy từ `logs/classifier/results.json`.
   - Giữ nguyên toàn bộ chỉ số cũ của summary.
4. Thêm `--dry-run`: đếm và in số request Gemini sẽ tốn (generator + giám khảo; câu refusal tốn 1; ước lượng cache-hit từ `.generation_cache/`) TRƯỚC khi chạy thật.
5. Câu `Q96–98` GT trống (người dùng đã chốt 2026-10-20: GIỮ TRỐNG GT, không bổ sung): bỏ qua phần chấm generation THEO GT của chúng một cách tường minh (ghi `skipped_no_gt`), không làm chết lượt — nhưng **phép đo hành vi từ chối / ảo giác ngoài corpus của 3 câu này vẫn phải chạy** (chỉ cần cờ `in_corpus=false`, không cần GT) vì đây là chỉ số đầu bảng của đồ án (baseline 0/3).
6. Tests offline cho phần thống kê nhóm (fake results, không gọi API).

## Ràng buộc

- Nhóm 04. Không đổi benchmark mặc định trong code — v3 được truyền bằng cờ `--benchmark` khi chạy (giữ v2 làm default cho tới khi chốt A/B).
- Fallback Qwen giữ trạng thái tắt bắt buộc cho lượt Gemini (đã có sẵn — không phá).

## Sản phẩm

- `src/evaluation.py` cập nhật + tests mới.

## Verify (bắt buộc)

- `venv\Scripts\python.exe -m pytest` toàn bộ xanh.
- `venv\Scripts\python.exe src\evaluation.py --limit 2 --with-classifier --use-qwen-generator --no-judge` chạy xong, JSON có `predicted_labels`.
- `--dry-run` in số request hợp lý (ví dụ `--limit 2` đầy đủ ≈ 4 request).
