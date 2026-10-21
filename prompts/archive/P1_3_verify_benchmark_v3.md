# P1.3 — Kiểm chứng độc lập benchmark v3

> Giai đoạn 1 · Nhóm playbook: 04 · Thời gian: 0.5 ngày · **GATE của giai đoạn 1**

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Verify độc lập v3 trước khi xây classifier: schema đúng, nhãn hợp lệ, GT khớp corpus thật, v2 không bị làm hỏng.

## Ngữ cảnh cần đọc trước

- `data/evaluation/benchmark_100_questions_v3.json`, `data/evaluation/benchmark_100_questions_v2.json`
- `src/text_utils.py` — hàm `fold()` (bỏ dấu thanh) dùng để so khớp tên nguồn.
- Cấu trúc `data/corpus/**` (liệt kê bằng os.walk).

## Việc cần làm

1. Viết script verify trong `tmp/verify_v3.py` (xóa sau phiên) kiểm tra 4 nhóm:
   - **Schema:** 100 câu; đúng 13 khóa, không thừa/thiếu; `in_corpus` là boolean; `question_type` ∈ {`TRA_CUU`, `SO_SANH`, `THU_TUC`, `NGOAI_PHAM_VI`}; `category` chỉ nằm trong 14 nhóm của v2.
   - **Không phá v2:** từng câu v3 so 12 khóa cũ với v2 theo `id` — phải giống hệt từng ký tự.
   - **GT-verify nguồn:** với mỗi câu `in_corpus=true` có `source_document`, đối chiếu với danh sách file thật bằng os.walk `data/corpus/**`, so khớp sau khi `fold()` bỏ dấu. (Lỗi "source_document ghi sai tên → Hit=0" từng xảy ra ở v2 — mục này là chốt chặn cho v3.)
   - **Thống kê:** crosstab `category` × `question_type`; số câu mỗi loại; in 5 câu mẫu mỗi loại.
2. Xuất kết quả vào `data/evaluation/verify_v3_report.md` — pass/fail từng mục + chứng cụ (đếm, danh sách câu fail).
3. Cập nhật `README.md` mục 8 (Ghi chú): thêm 1 dòng giới thiệu v3 + link `TAXONOMY.md`; giữ nguyên câu "mặc định của src/evaluation.py là v2" (chuyển sang v3 ở P4.1).

## Ràng buộc

- Nhóm 04 sở hữu `data/evaluation/**`; phần sửa README mục 8 cần nêu rõ trong báo cáo (thuộc 03 — xin chấp thuận).
- Mọi fail phải sửa tại nguồn (quay lại P1.2 chạy lại bước duyệt) — không vá qua loa trong script verify.

## Sản phẩm

- `data/evaluation/verify_v3_report.md`
- `README.md` mục 8 cập nhật.

## Verify (bắt buộc)

- Tất cả 4 nhóm kiểm tra PASS 100% (hoặc mọi câu không khớp nguồn được liệt kê kèm lý do rõ ràng và đã sửa).
- `tmp/` dọn sạch.

## GATE

- v3 pass toàn bộ mới được sang giai đoạn 2.
