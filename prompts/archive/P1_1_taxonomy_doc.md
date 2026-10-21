# P1.1 — Thiết kế bộ nhãn: TAXONOMY.md

> Giai đoạn 1 (Thiết kế bộ nhãn) · Nhóm playbook: 04 (sở hữu data/evaluation) · Thời gian: 1 ngày · Sản phẩm chờ người dùng duyệt

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Chuẩn hóa bộ nhãn của hướng mới thành văn bản có luật gán nhãn — nguồn duy nhất cho P1.2 (gán nhãn 100 câu) và P2.1 (few-shot cho classifier).

## Ngữ cảnh cần đọc trước

- `data/evaluation/benchmark_100_questions_v2.json` — cột `category` (14 nhóm) và `raw_query` (100 câu thật) là căn cứ duy nhất của taxonomy.
- `prompts/00_base_context.md` — chuỗi nhãn 4 loại câu hỏi đã cố định.

## Việc cần làm

1. Đếm phân bố `category` hiện có bằng Python (in ra terminal, không ghi file thừa) — dùng làm số liệu mục A.
2. Viết `TAXONOMY.md` (thư mục gốc repo) gồm 4 mục:
   - **A. 14 chủ đề**: bảng (chủ đề | mô tả 1 dòng | số câu trong v2). GIỮ NGUYÊN 14 nhóm của v2 — không gộp, không tách trong đợt này.
   - **B. 4 loại câu hỏi** — nhãn là chuỗi cố định:
     | Nhãn | Định nghĩa | Dấu hiệu nhận biết |
     |---|---|---|
     | `TRA_CUU` | tra một thông tin cụ thể nằm ở một văn bản | hỏi "là bao nhiêu / điều kiện nào / là gì"; trả lời từ 1–2 Điều |
     | `SO_SANH` | so sánh, đối chiếu, tổng hợp nhiều điểm hoặc nhiều nguồn | "so sánh / khác nhau / điểm khác như thế nào"; cần ghép ≥ 2 nơi |
     | `THU_TUC` | hỏi cách làm thủ tục, quy trình, hồ sơ từng bước | "thủ tục / cần giấy tờ gì / làm sao để / các bước" |
     | `NGOAI_PHAM_VI` | ngoài quy chế học vụ AGU (kiến thức chung, tư vấn cá nhân, trường khác) | không thể trả lời từ các văn bản trong corpus |
   - **C. Luật phân giải xung đột** (thứ tự xét cố định): (1) `NGOAI_PHAM_VI` xét trước — câu không thể trả lời từ corpus thì nhãn này; (2) có từ dấu hiệu so sánh hoặc nội dung đòi hỏi ghép nhiều nơi → `SO_SANH`; (3) hỏi bước làm / hồ sơ → `THU_TUC`; (4) còn lại → `TRA_CUU`. Câu lưỡng lự → chọn nhãn bảo thủ `TRA_CUU`.
   - **D. Ví dụ few-shot chuẩn hóa**: với MỖI loại, trích ≥ 2 câu THẬT từ `raw_query` của v2 (kèm `id` câu) làm ví dụ — không bịa câu, không sửa câu.
3. Không sửa benchmark.

## Ràng buộc

- Nhãn là chuỗi không dấu SCREAMING_SNAKE cố định như bảng — mọi đoạn code về sau dùng đúng chuỗi này.
- Ví dụ ở mục D phải tìm được ngược trong v2 theo id (verify ở dưới bắt mục này).

## Sản phẩm

- `TAXONOMY.md`

## Verify (bắt buộc)

- Bảng A khớp kết quả đếm thực tế từ v2 (in chứng cứ đếm).
- Script kiểm tra ngược (đặt trong `tmp/`, xóa sau): từng ví dụ mục D tồn tại trong v2 đúng theo id.

## Điểm cần người dùng quyết

- **Duyệt định nghĩa 4 loại + luật phân giải xung đột** trước khi gán nhãn (P1.2).
