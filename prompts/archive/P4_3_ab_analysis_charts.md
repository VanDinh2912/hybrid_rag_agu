# P4.3 — Phân tích A/B + biểu đồ cho báo cáo

> Giai đoạn 4 · Nhóm playbook: 04 · Thời gian: 1–2 ngày · **GATE của giai đoạn 4**

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Bảng so sánh + biểu đồ + nhận xét — nguyên liệu trực tiếp cho chương thực nghiệm (P5.3 chèn thẳng).

## Ngữ cảnh cần đọc trước

- `outputs/ab_results_without_classifier.json`, `outputs/ab_results_with_classifier.json` (P4.2).
- `src/evaluation.py` — cách tính từng chỉ số (để giải thích đúng trong report).

## Việc cần làm

1. Tạo `src/analyze_ab.py` (nhóm 04) đọc 2 JSON, xuất:
   - `outputs/ab_comparison.md`:
     - Bảng tổng thể: Hit@3/5/6, MRR, Citation P/R/F1, Faithfulness, number support, latency, classification accuracy, **tỉ lệ từ chối oan (câu in_corpus bị trả lời từ chối)** — 2 cột (tắt / bật tầng phân loại) + cột chênh lệch.
     - Bảng per-question_type + per-category (kể cả nhóm có số câu nhỏ — ghi chú cẩn trọng khi đọc).
     - Phần nhận xét: nhóm nào tăng/giảm, đối chiếu 2–3 câu cụ thể từ results làm dẫn chứng (kèm id câu). Nếu lượt WITH có câu in_corpus bị từ chối oan, đối chiếu danh sách 19 câu bị classifier gán nhầm trong `logs/classifier/results.json` (9 câu TRA_CUU→NGOAI_PHAM_VI, 10 câu TRA_CUU→SO_SANH) để kết luận đúng nguyên nhân.
   - `outputs/figures/*.png` (matplotlib, backend Agg, dpi 150, font DejaVu Sans — đủ dấu tiếng Việt):
     1. Bar chart tổng thể các chỉ số, 2 lượt cạnh nhau.
     2. Bar chart Hit@K theo question_type, 2 lượt.
     3. Heatmap confusion matrix phân loại (từ lượt WITH).
     Mỗi biểu đồ có tiêu đề + trục có nhãn + chú thích tham số (top_k, model, ngày).
2. Ghi chú về Latency trong report: hai lượt có pattern cache khác nhau (lượt WITH miss nhiều ở SO_SANH) → Latency chỉ là THAM CHIẾU, không rút kết luận.
3. Spot-check 3 số trong bảng khớp JSON trước khi chốt.

## Ràng buộc

- Nhóm 04. KHÔNG sửa `src/evaluation.py`. Mọi con số trong `ab_comparison.md` phải truy được về 2 JSON nguồn.
- Không bịa nhận xét — mỗi kết luận phải gắn với số liệu hoặc câu dẫn chứng cụ thể.

## Sản phẩm

- `src/analyze_ab.py`, `outputs/ab_comparison.md`, `outputs/figures/*.png` (3 file).

## Verify (bắt buộc)

- Mở từng PNG (Read ảnh) kiểm tra: chữ tiếng Việt không lỗi font, không đè nhãn, đủ tiêu đề/trục.
- `ab_comparison.md` render được; spot-check 3 số khớp JSON.

## GATE (chốt cùng người dùng)

- Tổng thể không tụt quá ngưỡng đã chốt (đề xuất: MRR/Hit không giảm > 5% tương đối) VÀ ≥ 1 nhóm tăng rõ (thường là SO_SANH).
- Nếu tụt: chọn lại nhóm cấu hình ở P3.1 (router) và chạy lại CHỈ lượt WITH (P4.2) — KHÔNG sửa số, KHÔNG hạ tiêu chí.
