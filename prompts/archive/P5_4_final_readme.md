# P5.4 — Cập nhật README chốt cho hệ thống mới

> Giai đoạn 5 · Nhóm playbook: 03 (+ ghi chú cập nhật playbook) · Thời gian: 1 ngày · **GATE CUỐI của lộ trình**

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

README phản ánh đúng hệ thống sau làm lại — người mới đọc README là chạy được toàn bộ.

## Ngữ cảnh cần đọc trước

- `README.md` hiện tại (toàn bộ), `ROADMAP.md`, `SYSTEM_ARCHITECTURE.md` mới (P5.2).
- Danh sách file mới thực tế trong repo: `src/classifier.py`, `src/router.py`, `src/evaluate_classifier.py`, `src/analyze_ab.py`, `data/evaluation/benchmark_100_questions_v3.json`, `TAXONOMY.md`, `ROADMAP.md`, `prompts/`, `docs/bao_cao/`, `logs/classifier/`, `outputs/figures/`, `outputs/ab_*`.

## Việc cần làm

1. Cập nhật `README.md`:
   - Mục 1 (kiến trúc): luồng 6 tầng mới thay luồng 4 tầng; nêu rõ công tắc `ENABLE_CLASSIFIER` + suy giảm mềm.
   - Mục 2 (cấu trúc thư mục): thêm toàn bộ file/thư mục mới nêu trên.
   - Mục 3 (biến môi trường): bảng hoàn chỉnh với 3 biến classifier.
   - Mục 5 (sử dụng): thêm mục "Đánh giá bộ phân loại" (`src/evaluate_classifier.py`) và "Đánh giá A/B" (`src/evaluation.py --with-classifier`, `src/analyze_ab.py`); cập nhật lệnh ví dụ.
   - Mục 8 (ghi chú): hiện trạng mới — số chunks không đổi; kết quả A/B chốt (trích bảng tổng thể từ `outputs/ab_comparison.md`); classification accuracy.
2. Cập nhật `.maestro/playbooks/` (chỉ bổ sung phạm vi, KHÔNG đổi quy tắc):
   - `02_tri_tue_rag.md`: thêm `src/classifier.py`, `src/router.py`.
   - `04_kiem_chung_cau_hinh.md`: thêm `src/evaluate_classifier.py`, `src/analyze_ab.py`, `logs/classifier/`.
   - Nêu rõ thay đổi này trong báo cáo.
3. Kiểm tra đồng bộ `SYSTEM_ARCHITECTURE.*` (P5.2 đã export — chỉ xác nhận, không export lại nếu không đổi).

## Ràng buộc

- Nhóm 03; phần sửa playbook cần ghi chú rõ trong báo cáo (base_prompt.md là quy tắc chung, không đụng).
- KHÔNG xóa nội dung hướng dẫn cũ còn đúng (OCR, quota, caching...).

## Sản phẩm

- `README.md`, `.maestro/playbooks/02_...md`, `.maestro/playbooks/04_...md` cập nhật.

## Verify (bắt buộc)

- Mọi lệnh trong README copy-paste chạy được (đúng `venv\Scripts\python.exe`, đúng tên file mới).
- Các link/file nội bộ nêu trong README tồn tại trên đĩa (os.walk kiểm tra).
- Lần cuối: `venv\Scripts\python.exe -m pytest` toàn bộ xanh + smoke `main.py` 1 câu với `ENABLE_CLASSIFIER=1` và `=0`.

## GATE CUỐI

- Demo (P5.1) + đặc tả (P5.2) + báo cáo (P5.3) + README (P5.4) xong → đồ án theo hướng mới hoàn thiện.
