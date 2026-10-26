# P1.2 — Gán question_type cho 100 câu → benchmark v3

> Giai đoạn 1 · Nhóm playbook: 04 · Thời gian: 1–2 ngày (có điểm dừng duyệt giữa chừng)

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Tạo `data/evaluation/benchmark_100_questions_v3.json` — 100 câu, 13 khóa (12 khóa của v2 + `question_type`), nhãn đã qua người dùng duyệt.

## Ngữ cảnh cần đọc trước

- `TAXONOMY.md` (đã được người dùng duyệt) — luật gán nhãn và ví dụ.
- `data/evaluation/benchmark_100_questions_v2.json` — nguồn dữ liệu.

## Việc cần làm

1. **Đề xuất nhãn:** đọc từng câu v2, gán `question_type` theo TAXONOMY.md. Có thể dùng script đề xuất theo từ khóa để đỡ công, nhưng nhãn cuối phải được rà từng câu thủ công — không tin đề xuất tự động.
2. Xuất `data/evaluation/review_question_type.md`: bảng 100 dòng `id | raw_query (ngắn) | question_type đề xuất | lý do 1 dòng`, cuối bảng là phân bố 4 loại.
3. **DỪNG — chờ người dùng duyệt bảng review.** KHÔNG ghi benchmark v3 trước khi được duyệt.
4. Sau duyệt: script Python tạo v3 = v2 (giữ nguyên 12 khóa từng câu, kể cả câu có GT trống) + chèn `question_type` đã duyệt. KHÔNG sửa v2 — v3 là file mới.
5. **Câu Q96–98** (GT đáp án đang trống chờ người dùng chốt): vẫn gán `question_type` bình thường (phân loại không cần GT đáp án), nhưng nhắc lại người dùng trong báo cáo: 3 câu này cần bổ sung GT hoặc giữ trống (các chỉ số generation của chúng sẽ bị bỏ qua ở P4) — ghi quyết định của người dùng vào cuối `review_question_type.md`.

## Ràng buộc

- Ghi bằng Python với `encoding='utf-8'`.
- v2 phải còn nguyên vẹn (verify hash/kích thước trước và sau).
- 13 khóa đúng thứ tự tên: `id, category, tier, in_corpus, source_document, raw_query, normalized_query, expected_answer, expected_citations, ground_truth_answer, ground_truth_citation, supplement_if_wrong, question_type`.

## Sản phẩm

- `data/evaluation/review_question_type.md`
- `data/evaluation/benchmark_100_questions_v3.json`

## Verify (bắt buộc)

- v3 đủ 100 câu × 13 khóa đúng tên; phân bố 4 loại in ra khớp bảng đã duyệt.
- v2 không đổi (so hash trước/sau); spot-check 5 câu v3: 12 khóa cũ giống hệt v2, `question_type` khớp bảng duyệt.

## Điểm cần người dùng quyết

- Duyệt bảng 100 nhãn đề xuất.
- Chốt hướng xử lý Q96–98 (bổ sung GT hay giữ trống).
