# P5.3 — Bản nháp chương báo cáo (kiến trúc + thực nghiệm)

> Giai đoạn 5 · Nhóm playbook: 03 · Thời gian: 3–5 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Dàn ý + bản nháp các chương cốt lõi của đồ án, số liệu lấy thẳng từ `outputs/` — không một con số nào tự sinh ra.

## Ngữ cảnh cần đọc trước

- `ROADMAP.md` (P0.1), `TAXONOMY.md` (P1.1), `SYSTEM_ARCHITECTURE.md` (P5.2).
- `logs/classifier/accuracy_report.md`, `outputs/ab_comparison.md`, `outputs/figures/*.png` (P2.3, P4.3).
- `outputs/baseline_*/BASELINE.md` — tham chiếu phụ.

## Việc cần làm

Tạo thư mục `docs/bao_cao/` với 3 file:

1. `chuong3_kien_truc.md`:
   - Đề tài mới là gì; kiến trúc 6 tầng (sơ đồ chép từ SYSTEM_ARCHITECTURE.md).
   - Taxonomy: 14 chủ đề + 4 loại câu hỏi + luật gán nhãn (từ TAXONOMY.md).
   - Thiết kế classifier: few-shot, guardrail 3 lớp, suy giảm mềm.
   - Thiết kế router: bảng cấu hình + nguyên tắc "mặc định = cấu hình hiện tại".
   - Thiết kế thí nghiệm A/B: công tắc `ENABLE_CLASSIFIER`, cùng benchmark v3, cùng tham số, chỉ khác 1 biến.
2. `chuong4_thuc_nghiem.md`:
   - Môi trường thí nghiệm: bảng tham số từ meta của P4.2 (model, top_k, ngày).
   - Kết quả phân loại: accuracy 2 nhãn + confusion matrix (từ `logs/classifier/`).
   - Kết quả A/B: bảng tổng thể + per-question_type + per-category (từ `outputs/ab_comparison.md`) + chèn ảnh `outputs/figures/`.
   - Thảo luận: vì sao nhóm X tăng/giảm (dẫn chứng câu cụ thể); hạn chế (Latency chỉ tham chiếu, nhãn sai của NGOAI_PHAM_VI, số câu nhỏ ở vài nhóm).
3. `chuong1_2_5_outline.md`:
   - Outline chương 1 (tổng quan đề tài), chương 2 (cơ sở lý thuyết — GỢI Ý từ khóa tra cứu: intent classification, query routing, hybrid retrieval, RAG survey — người dùng tự tra và điền trích dẫn THẬT), chương 5 (kết luận + hướng phát triển: active learning cho classifier, lọc source_filter mạnh hơn, A/B theo tuần).

## Ràng buộc

- Nhóm 03. KHÔNG bịa số liệu; mỗi bảng/ảnh chèn vào chương phải kèm ghi chú nguồn file (vd "nguồn: outputs/ab_comparison.md, bảng 2").
- KHÔNG tự chế trích dẫn học thuật — chỉ gợi ý từ khóa tìm kiếm, người dùng tự xác minh.

## Sản phẩm

- `docs/bao_cao/chuong3_kien_truc.md`, `chuong4_thuc_nghiem.md`, `chuong1_2_5_outline.md`.

## Verify (bắt buộc)

- Spot-check 5 số ngẫu nhiên trong chương 4 khớp file nguồn trong `outputs/`/`logs/classifier/`.
- Markdown render được (tiêu đề, bảng, ảnh `figures/` hiển thị đúng đường dẫn tương đối).
