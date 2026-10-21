# P0.1 — Chốt định hướng mới thành ROADMAP.md

> Giai đoạn 0 (Chốt hướng & mốc so sánh) · Nhóm playbook: 03 (tài liệu) · Thời gian: 0.5 ngày · Sản phẩm chờ người dùng duyệt

Đọc trước `prompts/00_base_context.md` (hoặc đã được dán trước prompt này), sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Chốt đề tài mới thành văn bản `ROADMAP.md` để người dùng duyệt — mọi nhiệm vụ sau (P0.2 → P5.4) dựa vào văn bản này.

## Ngữ cảnh cần đọc trước

- `README.md` — kiến trúc hiện tại 4 tầng, hiện trạng corpus/benchmark/outputs.
- `outputs/evaluation_summary.md`, `logs/benchmark/summary_comparison_report.md` — số liệu hiện có để trích dẫn.
- `prompts/README.md` — lộ trình 6 giai đoạn của hướng mới.

## Việc cần làm

1. Viết `ROADMAP.md` (thư mục gốc repo) gồm đúng các mục:
   - **Tên đề tài mới**: "Ứng dụng kiến trúc RAG phân loại câu hỏi và hỗ trợ truy xuất thông tin quy chế đào tạo sinh viên".
   - **Mục tiêu & 3 câu hỏi nghiên cứu**: (1) bộ phân loại 2 nhãn (chủ đề + loại câu hỏi) đạt độ chính xác bao nhiêu trên 100 câu; (2) router truy xuất theo lớp câu hỏi cải thiện Hit@K/MRR ở những nhóm câu nào; (3) bật tầng phân loại có tốt hơn tắt hay không tổng thể, và có làm tụt nhóm nào không.
   - **Phạm vi làm lại**: thêm `src/classifier.py` (Qwen few-shot trả 2 nhãn), `src/router.py` (nhãn → cấu hình truy xuất), tách truy vấn con cho câu so sánh, prompt biến thể theo loại câu, chế độ đánh giá A/B + chỉ số phân loại, demo hiển thị nhãn. **Tái sử dụng nguyên vẹn**: corpus 26 tài liệu, index 361 chunks, hybrid search BM25+Chroma, generator trích dẫn + Soft Refusal, bộ chỉ số Hit@K/MRR/Citation/Faithfulness, 85 unit test.
   - **Ngoài phạm vi** (ghi rõ để không lan man): đổi model OCR, train embedding mới, đổi vector DB, mở rộng corpus ra tài liệu ngoài quy chế học vụ.
   - **Tiêu chí thành công định lượng**: accuracy chủ đề ≥ 85%, accuracy loại câu hỏi ≥ 80%; A/B tổng thể không tụt quá ngưỡng (chốt cụ thể cùng người dùng ở P4.3, đề xuất 5% tương đối); ít nhất 1–2 nhóm câu tăng rõ; toàn bộ unit test xanh.
   - **Kế hoạch 6 giai đoạn** (tóm tắt; chi tiết tham chiếu `prompts/README.md`).
2. Không sửa bất kỳ file nào khác.

## Ràng buộc

- Chỉ tạo `ROADMAP.md`. Tiếng Việt, ngắn gọn; mọi con số trích đúng từ `outputs/` hoặc `logs/benchmark/` — không bịa số, mỗi bảng kèm ghi chú nguồn.

## Sản phẩm

- `ROADMAP.md`

## Verify (bắt buộc)

- File tồn tại, đọc được bằng utf-8; mọi con số trong đó truy được về file nguồn trong `outputs/`/`logs/benchmark/` (spot-check 3 số).

## Điểm cần người dùng quyết

- **DUYỆT nội dung ROADMAP.md** (có thể yêu cầu sửa) trước khi chuyển sang P0.2.
