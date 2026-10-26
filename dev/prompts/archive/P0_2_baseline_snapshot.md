# P0.2 — Chốt snapshot baseline "không phân loại"

> Giai đoạn 0 · Nhóm playbook: 04 (kiểm chứng & outputs) · Thời gian: 0.5 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Ghim lại số liệu hiện tại của pipeline cũ (chưa có tầng phân loại) thành một thư mục baseline — mọi kết quả A/B ở giai đoạn 4 sẽ đối chiếu về đây.

## Ngữ cảnh cần đọc trước

- Toàn bộ `outputs/` và `logs/benchmark/` (liệt kê bằng os.walk trước khi copy).
- `outputs/evaluation_summary.md` — tham số từng lượt chạy đã ghi.

## Việc cần làm

1. Tạo `outputs/baseline_<YYYY-MM-DD>/` (dùng ngày chạy thật), copy nguyên vẹn (copy-only, không sửa nội dung):
   - `outputs/evaluation_results.json`, `outputs/evaluation_summary.md`
   - `logs/benchmark/summary_comparison_report.csv` và `summary_comparison_report.md`
   - `logs/benchmark/results_all.json` nếu kích thước < 5 MB; nếu lớn hơn thì chỉ ghi chú đường dẫn gốc trong BASELINE.md.
2. Viết `outputs/baseline_<YYYY-MM-DD>/BASELINE.md` tổng hợp:
   - Bảng chỉ số từng lượt chạy đã có (Hit@3/5/6, MRR, Citation P/R/F1, Faithfulness, number support, latency).
   - **Tham số đầy đủ của từng lượt**: benchmark nào (v2 / 50 câu), top_k, generator (Gemini hay Qwen offline), giám khảo, ngày chạy. Ghi rõ lượt nào đo bằng Qwen offline (chỉ tin cậy được tầng truy xuất, tầng Citation/Faithfulness chỉ tham khảo).
   - Mục "Sử dụng": lượt A/B ở giai đoạn 4 chạy trên benchmark v3; baseline v2 này là tham chiếu phụ (số v3 sẽ lệch nhẹ nếu v3 sửa GT).
3. Không chạy lại bất kỳ lượt đánh giá nào — chỉ đóng gói số liệu đã có.

## Ràng buộc

- Copy-only: KHÔNG sửa bất kỳ file gốc nào trong `outputs/` hay `logs/benchmark/`.
- Copy bằng Python `shutil`; sau copy phải verify bằng os.walk: đếm file + so kích thước byte từng file nguồn ↔ bản copy.

## Sản phẩm

- `outputs/baseline_<ngày>/` gồm `BASELINE.md` + các file copy.

## Verify (bắt buộc)

- os.walk đếm file trong thư mục baseline khớp dự kiến; từng file copy có kích thước = file gốc; spot-check 3 số trong BASELINE.md khớp file gốc.
