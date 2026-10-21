# P5.2 — Cập nhật SYSTEM_ARCHITECTURE + tái xuất .docx/.txt

> Giai đoạn 5 · Nhóm playbook: 03 · Thời gian: 1 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Đặc tả kiến trúc phản ánh luồng 6 tầng mới — `SYSTEM_ARCHITECTURE.md` vẫn là nguồn duy nhất, `.docx`/`.txt` do script sinh ra.

## Ngữ cảnh cần đọc trước

- `SYSTEM_ARCHITECTURE.md` — toàn bộ cấu trúc hiện tại.
- `src/classifier.py`, `src/router.py`, `src/retrieval.py` (sub-query), `src/generator.py` (prompt biến thể) — đặc tả đúng những gì ĐÃ code, không đặc tả thứ chưa tồn tại.
- `export_architecture.py` — quy trình export.

## Việc cần làm

1. Sửa `SYSTEM_ARCHITECTURE.md`:
   - Sơ đồ luồng 4 tầng → **6 tầng**: chèn `[0] Phân loại câu hỏi` (2 nhãn: chủ đề + loại) TRƯỚC tầng chuẩn hóa; tầng truy xuất ghi rõ "tham số theo router (`src/router.py`)"; tầng sinh trả lời ghi "prompt theo loại câu hỏi".
   - Thêm mục đặc tả mới: classifier (few-shot, guardrail 3 lớp, suy giảm mềm), router (bảng cấu hình + nguyên tắc "mặc định = cấu hình hiện tại"), sub-query splitting + guardrail chống tách dở, `NGOAI_PHAM_VI` không skip truy xuất (chỉ nhắc refusal thêm).
   - Bảng biến môi trường: thêm `ENABLE_CLASSIFIER`, `CLASSIFIER_MODEL`, `CLASSIFIER_TIMEOUT`.
   - GIỮ nguyên các đặc tả công thức BM25/cosine/RRF, `fold()`, oversampling — chỉ bổ sung, không viết lại phần cũ.
2. Chạy `venv\Scripts\python.exe export_architecture.py` để tái sinh `.docx`/`.txt` — CẤM sửa 2 file đó bằng tay riêng lẻ.

## Ràng buộc

- Nhóm 03. Nguồn duy nhất là `.md`; `.docx`/`.txt` chỉ do script sinh.

## Sản phẩm

- `SYSTEM_ARCHITECTURE.md` cập nhật; `SYSTEM_ARCHITECTURE.docx` + `.txt` tái sinh; biên nhận mới ở `logs/export/`.

## Verify (bắt buộc)

- `.docx`/`.txt` có mtime mới hơn `.md`.
- `Select-String -Path SYSTEM_ARCHITECTURE.txt -Pattern "ENABLE_CLASSIFIER"` ra ≥ 1 dòng.
- `logs/export/` có biên nhận lần export mới.
