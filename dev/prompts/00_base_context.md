# NGỮ CẢNH DÙNG CHUNG — dán đầu mỗi lượt giao việc (hoặc agent tự đọc file này)

Bạn đang làm việc trong repo `hybrid_rag_agu` (Windows). Đọc toàn bộ nội dung dưới đây trước khi làm nhiệm vụ được giao.

## 1. Đề tài và hiện trạng

- Hệ thống RAG hỏi–đáp quy chế học vụ AGU đang chạy ổn định theo 4 tầng: chuẩn hóa câu hỏi (Qwen2.5:1.5b qua Ollama) → mở rộng truy vấn bằng từ điển đồng nghĩa pháp lý → True Hybrid Search (BM25 + bge-m3/ChromaDB hợp nhất RRF) → generator Gemini (temperature 0, trích dẫn Điều/Khoản, Soft Refusal khi thiếu căn cứ). Corpus 26 tài liệu, index 361 chunks, benchmark 100 câu v2, 85 unit test offline *(snapshot
20-10 — cập nhật 31-10: `data/corpus/` có **29 tệp (24 PDF + 5 DOCX)**, trong đó 26 tệp đã ingest
nên index sản xuất vẫn **361 chunk**; bộ test hiện **1.556 test được collect**)*.
- Đang làm lại đồ án theo hướng mới: **thêm tầng phân loại câu hỏi (2 nhãn: chủ đề + loại câu hỏi) và router truy xuất theo lớp câu hỏi**, đánh giá A/B bật/tắt tầng phân loại.
- Nguyên tắc bất di bất dịch: `ENABLE_CLASSIFIER=0` phải giữ hành vi pipeline cũ **nguyên vẹn 100%**; mọi tầng mới (classifier, router, sub-query) lỗi phải **suy giảm mềm** — lùi về cấu hình chung, tuyệt đối không chết pipeline.
- Bộ dữ liệu chuẩn của hướng mới: `data/evaluation/benchmark_100_questions_v3.json` (13 khóa = 12 khóa v2 + `question_type`).
- 4 nhãn loại câu hỏi là chuỗi cố định: `TRA_CUU` (tra cứu một thông tin) / `SO_SANH` (so sánh – tổng hợp nhiều điểm) / `THU_TUC` (thủ tục – quy trình) / `NGOAI_PHAM_VI` (ngoài quy chế học vụ AGU).
- Nhãn chủ đề dùng đúng 14 nhóm `category` của benchmark (học phí, chương trình đào tạo, đánh giá rèn luyện…). Chi tiết: `TAXONOMY.md`.

## 2. Môi trường (Windows, shell PowerShell)

- `python` KHÔNG có trên PATH — luôn gọi `venv\Scripts\python.exe` (PowerShell) hoặc `./venv/Scripts/python.exe` (Git Bash).
- Đặt biến môi trường kiểu PowerShell: `$env:USE_QWEN_GENERATOR="1"` — cú pháp tiền tố `VAR=... cmd` kiểu bash sẽ lỗi.
- Ghi file luôn bằng Python `open(path, 'w', encoding='utf-8')` — CẤM chuyển hướng `>` / `Out-File` của PowerShell (ghi UTF-16 làm hỏng JSON).
- Console cần UTF-8: script nên tự `sys.stdout.reconfigure(encoding="utf-8")`, hoặc chạy kèm `PYTHONIOENCODING=utf-8`.
- Ollama (Qwen2.5:1.5b-instruct) chạy thường trực trong system tray; bge-m3 chạy CPU (đúng thiết kế).

## 3. Quy tắc repo (theo `.maestro/playbooks/base_prompt.md`)

- File trung gian (bản nháp, script phụ, dump) chỉ nằm trong `tmp/` và xóa sạch trước khi kết thúc phiên.
- Log/file tự sinh khi chạy chỉ nằm trong `logs/` đúng ý nghĩa ở `logs/README.md`.
- Quyền ghi theo 4 group playbook: 01 dữ liệu/chỉ mục, 02 trí tuệ RAG, 03 giao diện/tài liệu, 04 kiểm chứng/cấu hình — mỗi prompt ghi rõ group của nó; KHÔNG sửa file ngoài phạm vi.
- KHÔNG đụng: `logs/learning/`, `logs/feedback/`, benchmark v2, các file `outputs/` cũ (chỉ được TẠO file mới).
- Code style theo các file `src/` hiện có (comment tiếng Việt); unit test phải chạy offline hoàn toàn (fake/monkeypatch Ollama, ChromaDB, Gemini) — không tốn quota.

## 4. Tiết kiệm quota Gemini

- Free tier giới hạn **theo từng model** (~5 request/phút, ~20 request/ngày với gemini-2.5-flash). Mỗi câu đánh giá đầy đủ tốn ~2 request (generator + giám khảo).
- Trước lượt thật luôn chạy thử `--limit 2` (hoặc `--use-qwen-generator`) để chắc lệnh đúng; `.generation_cache/` phải bật; giám khảo dùng model riêng qua `GEMINI_JUDGE_MODEL` để tách ngân sách.
- Fallback Qwen bị tắt bắt buộc trong các lượt đánh giá bằng Gemini (script tự xử lý) — không bật lại.
- Việc thử nghiệm phân loại/router luôn dùng Qwen local — KHÔNG tốn Gemini quota.

## 5. Quy tắc verify — bắt buộc trước khi báo xong

- Luôn `os.walk` (hoặc liệt kê thư mục) kiểm tra kết quả THẬT trong đĩa — KHÔNG tin dòng log in ra khi chạy.
- Đụng tới benchmark/ground truth thì phải **GT-verify**: đối chiếu `source_document` của từng câu với file thật trong `data/corpus/**` (so khớp sau khi `fold()` bỏ dấu) trước khi tin metrics. Lỗi "source_document ghi sai tên → Hit=0" từng xảy ra ở v2 — phải bắt được trên v3.
- Báo cáo hoàn thành buộc gồm: (a) danh sách file đã tạo/sửa/xóa, (b) kết quả từng mốc verify kèm chứng cứ (lệnh + output thật), (c) xác nhận `tmp/` đã dọn sạch.
- Verify fail thì sửa và chạy lại — KHÔNG hạ tiêu chí verify để cho qua, KHÔNG báo xong khi còn fail.

## 6. Quản lý tiến độ — cập nhật prompts/PROGRESS.md (bắt buộc)

- Cuối mỗi nhiệm vụ, **TRƯỚC khi báo cáo xong**: cập nhật đúng MỘT dòng của prompt đang làm trong bảng trạng thái ở `prompts/PROGRESS.md` (Trạng thái, Ngày, Verify tóm tắt, Ghi chú) và đưa dòng "đã cập nhật prompts/PROGRESS.md" vào danh sách file đã sửa trong báo cáo.
- Trạng thái chỉ dùng 5 giá trị: `chưa làm` · `đang làm` · `đang chờ duyệt` · `xong <ngày>` · `bị chặn: <lý do>`. Nhiệm vụ dừng ở cổng "chờ người dùng duyệt" thì ghi `đang chờ duyệt` — KHÔNG tự đánh `xong`.
- KHÔNG sửa dòng prompt khác, KHÔNG xóa nội dung cũ trong PROGRESS.md; quyết định của người dùng và issue để lại ghi thêm ở phần "Nhật ký quyết định" / "Bài học chuyển tiếp" (chỉ THÊM dòng).
- Đây là bộ nhớ dùng chung giữa các agent: nhiệm vụ sau đọc PROGRESS.md là biết dự án đang đứng ở đâu — cập nhật thiếu coi như nhiệm vụ CHƯA xong.
