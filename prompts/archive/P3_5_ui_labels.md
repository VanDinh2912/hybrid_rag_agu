# P3.5 — Hiển thị nhãn phân loại ở CLI + GUI

> Giai đoạn 3 · Nhóm playbook: 02 (main.py) + 03 (ui/app.py) · Thời gian: 1 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Người dùng nhìn thấy tầng phân loại đang làm gì: nhãn được gán + cấu hình truy xuất đã chọn.

## Ngữ cảnh cần đọc trước

- `main.py` — khối in kết quả 4 phần hiện có.
- `ui/app.py` — Tab 1 (Tra cứu) và Tab 3 (Vừa test vừa học).
- `src/pipeline.py` — 2 trường mới `labels` / `retrieval_config` (P3.2).
- `data/evaluation/manual_test_checklist.md` — checklist kiểm tra tay.

## Việc cần làm

1. `main.py`: khối in kết quả thêm 1 phần **"Phân loại & Cấu hình"** khi `labels` có mặt — chủ đề · loại câu hỏi · top_k/BM25/Chroma đã chọn · có tách truy vấn con hay không. `ENABLE_CLASSIFIER=0` → không in gì thêm (output như cũ).
2. `ui/app.py` Tab 1: thêm 1 dòng nhãn ngay trên khối kết quả (thuần hiển thị, không đổi logic hỏi đáp). Tab 3: log hiển thị thêm nhãn để phục vụ người dùng gán nhãn thủ công.
3. Cập nhật `data/evaluation/manual_test_checklist.md` (cần sự chấp thuận của nhóm 04 — nêu rõ trong báo cáo): thêm 3 câu kiểm tra nhãn (1 `TRA_CUU`, 1 `SO_SANH`, 1 `NGOAI_PHAM_VI` — chọn từ v3).

## Ràng buộc

- Thay đổi thuần hiển thị; KHÔNG sửa `classifier.py` / `router.py` / `generator.py`.
- main.py thuộc nhóm 02, ui/app.py thuộc nhóm 03 — báo cáo tách rõ phần nào của group nào.

## Sản phẩm

- `main.py`, `ui/app.py`, `data/evaluation/manual_test_checklist.md` cập nhật.

## Verify (bắt buộc)

- `venv\Scripts\python.exe -m pytest` toàn bộ xanh.
- `$env:USE_QWEN_GENERATOR="1"; $env:ENABLE_CLASSIFIER="1"; venv\Scripts\python.exe main.py "<1 câu từ v3>"` → thấy khối Phân loại & Cấu hình; chạy với `=0` → không thấy.
- Mở GUI (`venv\Scripts\python.exe ui\app.py`), hỏi 1 câu → dòng nhãn hiện đúng.
