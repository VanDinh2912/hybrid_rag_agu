# P3.4 — Prompt biến thể theo loại câu + chặn câu ngoài phạm vi

> Giai đoạn 3 · Nhóm playbook: 02 · Thời gian: 1–2 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Câu trả lời có hình thức phù hợp từng loại câu (bảng cho so sánh, các bước cho thủ tục); câu `NGOAI_PHAM_VI` có cơ chế từ chối chắc hơn — mà KHÔNG làm mất câu trả lời đúng khi nhãn sai.

## Ngữ cảnh cần đọc trước

- `src/generator.py` — `PROMPT_RULES`, `REFUSAL_TEXT`, cơ chế response cache + fallback Qwen.
- `src/pipeline.py` — đường truyền `labels` đã nối ở P3.2.

## Việc cần làm

1. `src/generator.py`:
   - Thêm `PROMPT_RULES_SO_SANH`: trả dạng bảng so sánh theo tiêu chí, mỗi ô có trích dẫn Điều/Khoản riêng, ghi rõ nguồn của từng vế.
   - Thêm `PROMPT_RULES_THU_TUC`: trả các bước đánh số, mỗi bước kèm căn cứ Điều/Khoản.
   - `generate_answer(..., question_type: str | None = None)` — `None` → prompt cũ **giống hệt từng ký tự** (để cache cũ còn dùng được cho đường classifier tắt và hành vi cũ không đổi).
2. Pipeline truyền `question_type` vào generator khi `ENABLE_CLASSIFIER=1`. Cache an toàn: key đã bám theo nội dung prompt → biến thể prompt tự tách cache, không cần xóa cache cũ.
3. **NGOAI_PHAM_VI — KHÔNG skip truy xuất** (rủi ro nhãn sai sẽ từ chối oan câu đúng): chỉ chèn thêm 1 dòng vào prompt: "Nếu ngữ cảnh không chứa thông tin liên quan đến câu hỏi, trả lời đúng một câu từ chối chuẩn." Cơ chế Soft Refusal hiện có lo phần còn lại. Ghi chú trong code + báo cáo: skip-early là thí nghiệm tùy chọn ở P4, chỉ cân nhắc bật nếu nhãn đủ tin cậy.
4. Tests: chọn đúng biến thể prompt theo `question_type`; `None` → prompt gốc không đổi một ký tự; câu ngoài corpus + ngữ cảnh rỗng → `REFUSAL_TEXT` (kiểm tra không regression).

## Ràng buộc

- Nhóm 02. Chuỗi `REFUSAL_TEXT` giữ NGUYÊN — tầng evaluation đối sánh theo hằng số này.
- Không đổi cơ chế cache/fallback Qwen.

## Sản phẩm

- `src/generator.py`, `src/pipeline.py` (truyền tham số), tests cập nhật.

## Verify (bắt buộc)

- `venv\Scripts\python.exe -m pytest` toàn bộ xanh.
- Smoke (Qwen local, không tốn quota): 1 câu `SO_SANH` thật từ v3 → câu trả lời dạng bảng, mỗi ô có trích dẫn; 1 câu `NGOAI_PHAM_VI` thật từ v3 → trả đúng chuỗi từ chối.
- Chạy 1 câu `TRA_CUU` đã từng hỏi khi `ENABLE_CLASSIFIER=0` → vẫn trúng cache cũ (không gọi API mới).
