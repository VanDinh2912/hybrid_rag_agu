# Group 03 — Giao diện & Tài liệu

> Bắt buộc nạp kèm: `base_prompt.md`
> Gộp từ 2 chủ thể cũ: GUI, Tài liệu kiến trúc

## Phạm vi được đụng

- `ui/app.py`, `TROUBLESHOOTING_GUI.md`, `LAYOUT_OPTIMIZATION.md`
- `README.md`, `SYSTEM_ARCHITECTURE.md`, `SYSTEM_ARCHITECTURE.docx`,
  `SYSTEM_ARCHITECTURE.txt`, `export_architecture.py`, `logs/export/export_report.txt`,
  `logs/feedback/user_feedback.json`
- `tmp/` cho build trung gian (ví dụ render docx)

## Sản phẩm cuối

- GUI đa tab ổn định, layout tuân theo `LAYOUT_OPTIMIZATION.md`; mọi quyết định
  layout/cơ chế phải được cập nhật vào doc tương ứng. GUI chỉ GỌI API của pipeline,
  không chứa logic nghiệp vụ
- Docs đồng bộ với code thực tế (mô tả đúng module, flag, luồng đang tồn tại);
  3 định dạng `SYSTEM_ARCHITECTURE.*` sinh từ MỘT nguồn qua `export_architecture.py`
  — CẤM sửa tay từng file riêng lẻ

## Vùng cấm

- `src/**` (cần thay đổi logic thì báo Group 01/02 quyết định), `data/**`, `tests/**`,
  `chroma_db/`
- Sửa code cho khớp docs — docs phải THEO code, không sửa code theo docs

## Verify

- GUI khởi chạy không lỗi console; từng tab mở/render được nội dung;
  không có business logic (chunking, retrieval, generation) viết trong `ui/`
- `export_architecture.py` chạy ra đủ 3 file, nội dung khớp nhau
- Grep: docs không mô tả module/flag/tính năng không tồn tại trong repo;
  không chứa API key hay đường dẫn máy cá nhân
- `tmp/` đã xóa sạch
