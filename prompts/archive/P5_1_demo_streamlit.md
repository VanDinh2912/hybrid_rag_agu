# P5.1 — Demo Streamlit hiển thị tầng phân loại

> Giai đoạn 5 (Demo & báo cáo) · Nhóm playbook: 03 (giao diện) · Thời gian: 1–2 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Demo trình diễn được cả nhãn phân loại lẫn cấu hình truy xuất theo lớp — "lễ tân" hiện rõ trong ứng dụng khi trình bày đồ án.

## Ngữ cảnh cần đọc trước

- `demo_streamlit.py` — toàn bộ (lớp trình bày thuần túy, KHÔNG cài lại logic backend).
- `src/classifier.py`, `src/router.py` — API có sẵn.
- Cấu trúc `logs/benchmark/results_all.json` (replay mode).

## Bước 0 — ui/app.py đọc USE_QWEN_GENERATOR (chốt 2026-10-21, còn treo từ P3.5)

`ui/app.py` dòng ~921 hardcode `GeminiGenerator` khi dựng pipeline — mọi smoke GUI từ giờ đều tiêu quota Gemini. Sửa theo đúng pattern `main.py` đã làm ở P3.3 Bước 0: đọc `USE_QWEN_GENERATOR`, `=1` → tiêm `QwenGenerator` (cảnh báo OFFLINE rõ ràng), mặc định giữ Gemini. Thêm 1 unit test mock cho nhánh này. Smoke GUI của nhiệm vụ này chạy offline 100%.

## Việc cần làm

1. Sidebar: thêm selectbox **"Tầng phân loại câu hỏi"** (Tắt / Bật) — giá trị đi thẳng vào lệnh gọi pipeline/`ENABLE_CLASSIFIER`, không cài lại logic.
2. Khối kết quả: thêm phần **"🏷️ Phân loại câu hỏi"** — chủ đề · loại câu hỏi · cấu hình đã chọn (top_k, trọng số BM25/Chroma, có tách truy vấn con). Lấy từ 2 trường `labels` / `retrieval_config` của pipeline.
3. Replay mode: entry cũ trong `results_all.json` không có labels → hiển thị "—" kèm ghi chú "chạy lại benchmark với `--with-classifier` để có dữ liệu replay mới".
4. Giữ nguyên 3 tab kết quả + logic composite/chọn chiến lược thắng — chỉ THÊM hiển thị.
5. Lệnh chạy demo (nhắc lại trong báo cáo): `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m streamlit run demo_streamlit.py --server.fileWatcherType none` — bắt buộc kèm flag watcher.

## Ràng buộc

- Nhóm 03. KHÔNG cài lại logic backend; KHÔNG sửa `src/` (nếu src thiếu API thì báo lại, không tự sửa ngoài phạm vi).

## Sản phẩm

- `demo_streamlit.py` cập nhật.

## Verify (bắt buộc)

- App chạy được bằng lệnh trên (không chết im — watcher đã tắt).
- Thử 3 câu: 1 `TRA_CUU` từ benchmark, 1 `SO_SANH`, 1 câu tự do ngoài corpus — nhãn + cấu hình hiện đúng từng câu.
- 1 chiến lược chunking lỗi (tạm đổi tên index) không làm app chết — cơ chế cũ không bị regression.
