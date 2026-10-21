# P2.1 — Viết src/classifier.py (bộ phân loại 2 nhãn)

> Giai đoạn 2 (Bộ phân loại v1) · Nhóm playbook: 02 (trí tuệ RAG) · Thời gian: 2–3 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Module phân loại câu hỏi THÔ thành 2 nhãn (chủ đề + loại câu hỏi) bằng Qwen local, có guardrail nhiều lớp và suy giảm mềm hoàn toàn.

## Ngữ cảnh cần đọc trước

- `src/local_slm.py`, `src/query_normalizer.py` — cách gọi Ollama hiện có, phong cách guardrail. Tái dùng wrapper nếu API phù hợp; không copy chay.
- `src/text_utils.py` — hàm `fold()` (bỏ dấu thanh) dùng cho lớp từ khóa.
- `TAXONOMY.md`, `data/evaluation/benchmark_100_questions_v3.json` — nguồn ví dụ few-shot.
- `tests/test_local_slm.py` — phong cách test offline (phục vụ P2.2).

## Việc cần làm

1. Tạo `src/classifier.py` với API tối thiểu:
   - `classify_query(query: str) -> dict` trả `{"topic": str | None, "question_type": str, "raw_response": str}`.
   - Hàm `build_few_shot_examples()` dựng phần few-shot từ nguồn cố định: 1 ví dụ mỗi chủ đề (14) + 2–3 ví dụ mỗi loại câu hỏi, chọn từ v3. Ghi CỨNG danh sách id câu đã chọn kèm comment nguồn (để tái lập được) — không nhúng nguyên benchmark vào code, không đọc benchmark lúc chạy.
   - Prompt yêu cầu model trả JSON `{"topic": "...", "question_type": "..."}`; parser an toàn: tách khối `{...}` đầu tiên, chịu được markdown fence và text thừa.
2. Guardrail 3 lớp, suy giảm mềm hoàn toàn:
   - Lớp 1 (chính): JSON hợp lệ + nhãn hợp lệ → dùng luôn. Nhãn hợp lệ = `topic` ∈ 14 nhóm (so không dấu qua `fold()`), `question_type` ∈ 4 chuỗi chuẩn.
   - Lớp 2: JSON lỗi / nhãn lạ → bảng từ khóa theo chủ đề + loại (dựa dấu hiệu ở TAXONOMY.md, so khớp không dấu).
   - Lớp 3: từ khóa cũng không khớp → trả `topic=None`, `question_type="TRA_CUU"` (router hiểu None = không lọc, dùng cấu hình chung).
   - Ollama chết / timeout (`CLASSIFIER_TIMEOUT`) → như lớp 3 + log cảnh báo. Pipeline không bao giờ chết vì classifier.
3. Cấu hình đọc qua dotenv như các module `src/` hiện có: `CLASSIFIER_MODEL` (trống = dùng `OLLAMA_MODEL`), `CLASSIFIER_TIMEOUT` (mặc định 20).
4. KHÔNG nối vào pipeline ở nhiệm vụ này (P3.2 lo). Không sửa file nào ngoài tạo `src/classifier.py`.

## Ràng buộc

- Nhóm 02. Code style + comment tiếng Việt theo các file `src/` hiện có.
- KHÔNG tốn Gemini quota — toàn bộ chạy Qwen local.
- `question_type` luôn là 1 trong 4 chuỗi chuẩn; `topic` là 1 trong 14 chuỗi `category` của v3 hoặc `None`.

## Sản phẩm

- `src/classifier.py`

## Verify (bắt buộc)

- Smoke script tạm trong `tmp/` (xóa sau) với Ollama đang chạy: 5 câu gồm 1 `TRA_CUU`, 1 `SO_SANH`, 1 `THU_TUC`, 1 `NGOAI_PHAM_VI` từ v3 + 1 câu viết tay lạ — in nhãn, đúng ≥ 4/5.
- Test suy giảm: đặt `OLLAMA_HOST` trỏ sai → classifier trả fallback, không crash, không treo quá `CLASSIFIER_TIMEOUT` + dung sai.
- `venv\Scripts\python.exe -m pytest` toàn bộ vẫn xanh (chưa có test riêng của classifier — P2.2 viết).
