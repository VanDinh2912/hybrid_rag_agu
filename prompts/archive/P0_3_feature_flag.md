# P0.3 — Khai báo công tắc ENABLE_CLASSIFIER

> Giai đoạn 0 · Nhóm playbook: 04 (.env*) + 03 (README) · Thời gian: 0.5 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Có công tắc cấu hình ngay từ đầu, hiện thực nguyên tắc "pipeline cũ giữ nguyên khi `ENABLE_CLASSIFIER=0`" — mọi nhiệm vụ từ giai đoạn 3 kiểm chứng qua công tắc này.

## Ngữ cảnh cần đọc trước

- `README.md` mục 3 (bảng biến môi trường), `.env.example`, `.env` hiện có (nếu có).

## Việc cần làm

1. Thêm vào `.env.example` khối mới với chú thích tiếng Việt đúng phong cách file:
   ```env
   # Tầng phân loại câu hỏi + router truy xuất (đang xây — chưa có tác dụng cho đến giai đoạn 3)
   ENABLE_CLASSIFIER=0             # 1 = phân loại câu hỏi (2 nhãn) + truy xuất theo lớp
   CLASSIFIER_MODEL=               # trống = dùng chung OLLAMA_MODEL
   CLASSIFIER_TIMEOUT=20           # giây — timeout gọi Ollama cho tầng phân loại
   ```
2. Thêm cùng khối vào `.env` của người dùng nếu chưa có (giá trị 0). KHÔNG in nội dung `.env` ra output/báo cáo (file chứa API key) — chỉ xác nhận đã thêm và giá trị.
3. Cập nhật `README.md` mục 3: thêm 3 biến trên vào bảng biến môi trường, kèm chú thích "chưa có tác dụng cho đến khi nối router vào pipeline (giai đoạn 3)".
4. Không đụng bất kỳ file code Python nào.

## Ràng buộc

- Phạm vi file: `.env.example`, `.env`, `README.md` (chỉ mục 3).
- KHÔNG đưa `.env` vào git (file chứa key).

## Sản phẩm

- `.env.example`, `.env`, `README.md` cập nhật.

## Verify (bắt buộc)

- `Select-String -Path .env.example -Pattern "ENABLE_CLASSIFIER"` ra ≥ 1 dòng; `README.md` có 3 biến mới.
- Chạy `venv\Scripts\python.exe -c "from dotenv import dotenv_values; v = dotenv_values('.env'); print('ENABLE_CLASSIFIER' in v)"` in `True` — KHÔNG in các giá trị khác của `.env`.
