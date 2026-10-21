# Bộ prompt làm lại đồ án — "RAG phân loại câu hỏi và hỗ trợ truy xuất thông tin quy chế đào tạo sinh viên"

> **✅ HOÀN THÀNH 2026-10-21 — 23/23 nhiệm vụ (22 prompt + micro-task P3.4b), GATE cuối đạt.**
> 23 prompt nhiệm vụ đã chuyển vào `archive/` (hồ sơ phương pháp luận — repo không có git nên KHÔNG xóa hẳn). Giữ lại tại đây: `PROGRESS.md` (lịch sử toàn bộ quyết định — dùng làm phụ lục báo cáo), `00_base_context.md` + `TEMPLATE_PROMPT_MOI.md` (tái sử dụng cho bảo trì về sau), và file này.
> Kết quả chốt: Hit@3 60,8% → 77,3% (+16,5 pp), MRR +50,9% tương đối — GATE ĐẠT. Chi tiết: `outputs/ab_comparison.md`, bản nháp báo cáo: `docs/bao_cao/`.

Gồm **24 file**: `00_base_context.md` (ngữ cảnh dùng chung) + **22 prompt nhiệm vụ** (P0.1 → P5.4) + file này. Mỗi prompt = 1 lượt giao việc cho agent, chia theo 6 giai đoạn. *(Bảng nhiệm vụ bên dưới giữ nguyên làm hồ sơ — trạng thái thật xem `PROGRESS.md`.)*

## Cách dùng

1. Làm **theo thứ tự** P0.1 → P5.4. Mỗi lượt giao ĐÚNG MỘT prompt — không gộp nhiều nhiệm vụ cho một agent cùng lúc.
2. Agent chạy ngay trong repo (ZCode / Maestro / opencode): dán nội dung file prompt, agent tự đọc `00_base_context.md`. Chatbot ngoài không thấy repo: dán `00_base_context.md` trước, rồi file prompt.
3. Prompt nào có dòng **"DỪNG — chờ người dùng duyệt"** hoặc mục "Điểm cần người dùng quyết": bạn phải duyệt/xác nhận trước khi cho làm tiếp.
4. Báo cáo mỗi nhiệm vụ bắt buộc gồm: file đã tạo/sửa + kết quả từng mốc verify (kèm chứng cứ lệnh/output) + xác nhận `tmp/` đã dọn — theo `.maestro/playbooks/base_prompt.md`.
5. **Agent tự cập nhật tiến độ**: bước cuối của mỗi nhiệm vụ là điền đúng 1 dòng vào `prompts/PROGRESS.md` (quy tắc ở mục 6 của `00_base_context.md`). Bạn không tự điền — chỉ mở bảng kiểm một cái; thiếu cập nhật coi như nhiệm vụ chưa xong.

## Bảng nhiệm vụ

### Giai đoạn 0 — Chốt hướng & mốc so sánh (2–3 ngày)

| File | Nhiệm vụ | Nhóm | Cổng kiểm tra |
|---|---|---|---|
| `P0_1_direction_doc.md` | Chốt định hướng mới thành `ROADMAP.md` | 03 | **Duyệt nội dung** |
| `P0_2_baseline_snapshot.md` | Ghim baseline số liệu pipeline cũ | 04 | — |
| `P0_3_feature_flag.md` | Khai báo công tắc `ENABLE_CLASSIFIER` | 04 + 03 | — |

### Giai đoạn 1 — Thiết kế bộ nhãn (3–5 ngày)

| File | Nhiệm vụ | Nhóm | Cổng kiểm tra |
|---|---|---|---|
| `P1_1_taxonomy_doc.md` | `TAXONOMY.md`: 14 chủ đề + 4 loại câu hỏi + luật gán | 04 | **Duyệt định nghĩa** |
| `P1_2_label_question_type.md` | Gán nhãn 100 câu → benchmark v3 (13 khóa) | 04 | **Duyệt bảng nhãn + chốt Q96–98** |
| `P1_3_verify_benchmark_v3.md` | Verify độc lập v3 (schema, GT khớp corpus) | 04 | GATE: pass 100% |

### Giai đoạn 2 — Bộ phân loại v1 (1–2 tuần)

| File | Nhiệm vụ | Nhóm | Cổng kiểm tra |
|---|---|---|---|
| `P2_1_classifier_module.md` | `src/classifier.py` (Qwen few-shot, guardrail 3 lớp) | 02 | Smoke 5 câu |
| `P2_2_classifier_tests.md` | Unit test offline cho classifier | 04 | pytest toàn bộ xanh |
| `P2_3_classifier_accuracy.md` | Đo accuracy 100 câu → `logs/classifier/` | 04 | GATE: chủ đề ≥ 85% & loại ≥ 80% & recall từng lớp thiểu số ≥ 50% |
| `P2_4_embedding_classifier.md` | (Tùy chọn) baseline kNN bge-m3 để so sánh | 04 | — |

### Giai đoạn 3 — Router truy xuất theo lớp (1–2 tuần)

| File | Nhiệm vụ | Nhóm | Cổng kiểm tra |
|---|---|---|---|
| `P3_1_router_module.md` | `src/router.py`: nhãn → cấu hình truy xuất | 02 + 04 | — |
| `P3_2_pipeline_integration.md` | Nối qua `ENABLE_CLASSIFIER`, suy giảm mềm | 02 | pytest + smoke 2 chế độ |
| `P3_3_subquery_split.md` | Tách truy vấn con cho câu SO_SANH | 02 | Ngữ cảnh đủ cả các vế so sánh |
| `P3_4_generator_prompts.md` | Prompt biến thể theo loại + từ chối ngoài phạm vi | 02 | — |
| `P3_4b_cache_inject_fix.md` | Sửa bất đối xứng cache HIT/MISS (micro-task, trước P4.1) | 02 | MISS ≡ HIT từng ký tự |
| `P3_5_ui_labels.md` | Hiển thị nhãn ở CLI + GUI | 02 + 03 | — |

### Giai đoạn 4 — Đánh giá A/B (1 tuần, phân bổ theo quota)

| File | Nhiệm vụ | Nhóm | Cổng kiểm tra |
|---|---|---|---|
| `P4_1_evaluation_ab_mode.md` | `evaluation.py`: cờ `--with-classifier` + thống kê theo nhóm | 04 | pytest + `--limit 2` |
| `P4_2_run_ab_evaluation.md` | Chạy 2 lượt 100 câu trên benchmark v3 | 04 | **Duyệt kế hoạch quota ~400 request** |
| `P4_3_ab_analysis_charts.md` | Bảng so sánh + biểu đồ + nhận xét | 04 | GATE: không tụt > 5% tương đối |

### Giai đoạn 5 — Demo & báo cáo (1–2 tuần)

| File | Nhiệm vụ | Nhóm | Cổng kiểm tra |
|---|---|---|---|
| `P5_1_demo_streamlit.md` | Demo hiển thị nhãn + cấu hình | 03 | — |
| `P5_2_system_architecture.md` | `SYSTEM_ARCHITECTURE.md` 6 tầng + tái xuất docx/txt | 03 | — |
| `P5_3_report_chapters.md` | Chương 3–4 + outline chương 1/2/5 | 03 | Số liệu khớp outputs/ |
| `P5_4_final_readme.md` | README chốt + cập nhật playbook | 03 | GATE cuối: smoke xanh |

## Các điểm BẠN phải quyết (tổng hợp nhanh)

- **P0.1** — duyệt `ROADMAP.md` (tên đề tài, phạm vi, tiêu chí thành công).
- **P1.1** — duyệt định nghĩa 4 loại câu hỏi + luật phân giải xung đột.
- **P1.2** — duyệt bảng 100 nhãn đề xuất + chốt hướng xử lý Q96–98 (GT đáp án đang trống).
- **P4.2** — duyệt kế hoạch tiêu quota (~200 request/lượt × 2 lượt, giảm nhờ cache).
- **P4.3** — chốt ngưỡng "không tụt" (đề xuất: MRR/Hit không giảm quá 5% tương đối) trước khi kết luận.

## Quy ước xuyên suốt bộ prompt

- **4 nhãn loại câu hỏi là chuỗi cố định**: `TRA_CUU` / `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI`. Mọi đoạn code, benchmark, báo cáo dùng đúng chuỗi này.
- **`ENABLE_CLASSIFIER=0` phải giữ pipeline cũ nguyên vẹn 100%** — mọi nhiệm vụ từ giai đoạn 3 tự kiểm chứng điều này.
- **NGOAI_PHAM_VI không được skip truy xuất** (nhãn sai sẽ từ chối oan câu đúng) — chỉ nhắc refusal thêm trong prompt generator.
- Bộ prompt soạn ngày 2026-10-20 dựa trên README + benchmark v2 (100 câu, 14 category) hiện có; nếu repo đã thay đổi, agent đọc file mới nhất và đối chiếu trước khi làm.
