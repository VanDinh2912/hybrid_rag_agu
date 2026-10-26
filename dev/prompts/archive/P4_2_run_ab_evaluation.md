# P4.2 — Chạy 2 lượt đánh giá A/B trên 100 câu v3

> Giai đoạn 4 · Nhóm playbook: 04 · Thời gian: 2–3 ngày thực tế (chia theo quota) · **THAO TÁC TIÊU QUOTA — chờ người dùng hẹn giờ**

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

2 file kết quả chính thức trên CÙNG benchmark v3: `outputs/ab_results_without_classifier.json` và `outputs/ab_results_with_classifier.json`.

## Bước 0 — Chống phí quota (duyệt kèm cổng, chốt 2026-10-21)

Làm TRƯỚC lượt thật, tất cả 0-quota:

1. **Retry 429-phút:** khi generator/djudge dính 429 **theo phút**, chờ 60s và thử lại TỐI ĐA 3 lần cho đúng câu đó — KHÔNG đánh dấu câu là error (lỗi phút là tạm thời; đánh dấu error = mất câu khỏi A/B). Riêng 429 **PerDay** vẫn dừng lượt như thiết kế.
2. **Resume an toàn:** trước khi chạy, nếu file output cùng meta (benchmark + cờ) đã tồn tại → nạp vào, câu nào đã có answer + judge score → giữ nguyên (0 request), chỉ chạy câu thiếu. Lý do: judge KHÔNG có cache — nếu không resume được thì mỗi lần hẹn lại tốn lại ~100 request judge cho câu cũ.
3. **Sửa `estimate_requests` của `--dry-run`:** lọc cache entry theo model (hiện đếm nhầm 310 entry Qwen là cache-hit Gemini → số ước lượng thổi phồng ngược). Ghi meta model vào ước lượng.
3b. **Flush định kỳ kết quả (áp dụng cho lượt WITH, yêu cầu 2026-10-21):** JSON kết quả chỉ được ghi khi lượt kết thúc/ngắt đẹp — nếu tiến trình chết cứng giữa chừng thì phần judge đã tốn tiền bị mất (cache chỉ bảo vệ tầng generator). Trước khi khởi động lượt WITH: thêm flush JSON sau MỖI câu (ghi lại toàn bộ results + meta) để resume bắt được cả judge score. Lượt WITHOUT đang chạy KHÔNG đụng vào.
4. **Đường dẫn output chốt:** WITHOUT → `outputs/ab_results_without_classifier.json` + `outputs/ab_summary_without_classifier.md`; WITH → `outputs/ab_results_with_classifier.json` + `outputs/ab_summary_with_classifier.md` (dùng cờ `--summary-output` — lệch playbook đã được người dùng chấp nhận 2026-10-21). CẤM ghi đè `outputs/evaluation_summary.md`, `outputs/evaluation_results.json`, `outputs/baseline_*`.
5. **Ghi chú ROADMAP** mục 3.2 dòng "Từ chối đúng 0.0%": thêm chú thích "(số liệu đo sai do bug fold marker — đã sửa 2026-10-21 trong P4.1; số thật sẽ có ở P4)" — sửa file nhóm 03, nêu rõ trong báo cáo.

## Kế hoạch quota (bắt buộc đọc kỹ trước khi chạy)

- Mỗi lượt 100 câu × ~2 request (generator + giám khảo) ≈ 200 request/lượt; hai lượt ≈ 400. Free tier giới hạn theo model: tách generator (`gemini-2.5-flash`) và giám khảo (`GEMINI_JUDGE_MODEL`) thành 2 ngân sách riêng.
- `.generation_cache/` giúp lượt WITH rẻ hơn đáng kể: chỉ câu `SO_SANH` (đổi prompt + đổi context) mới miss cache; các câu còn lại trúng cache của lượt WITHOUT.
- Trước mỗi lượt thật: chạy `--limit 2` với ĐÚNG bộ cờ của lượt đó.
- Dính 429 PerDay: script tự dừng + giữ kết quả phần đã chạy — chạy lại ĐÚNG lệnh sau khi quota reset, cache tự khớp phần cũ, không trả lời lại từ đầu.
- KHÔNG bật Qwen fallback cho lượt Gemini (script đã tắt bắt buộc). KHÔNG chạy thử `main.py`/`learn.py` trong cùng ngày chạy (đụng chung quota).

## Việc cần làm

1. Lượt WITHOUT (đảm bảo `ENABLE_CLASSIFIER=0` trong `.env`):
   `venv\Scripts\python.exe src\evaluation.py --benchmark data\evaluation\benchmark_100_questions_v3.json --output outputs\ab_results_without_classifier.json`
2. Lượt WITH:
   `venv\Scripts\python.exe src\evaluation.py --benchmark data\evaluation\benchmark_100_questions_v3.json --with-classifier --output outputs\ab_results_with_classifier.json`
3. Sau mỗi lượt: os.walk kiểm tra file + đếm câu chạy được trong JSON; GT-verify ngẫu nhiên 5 câu (spot-check `source_document` khớp corpus và Hit hợp lý).
4. Câu Q96–98 GT trống: xác nhận chúng được đánh dấu `skipped_no_gt` ở phần generation, không làm chết lượt.

## Điểm cần người dùng quyết — ĐÃ CHỐT 2026-10-21

- **~400 request: DUYỆT** — trần cứng 450 request tổng cho cả hai lượt; vượt trần dừng và báo cáo.
- **Lịch (cập nhật 2026-10-21 sau khi 3.8-flash 429 RPD tại Q09):** reset quota thực tế **~14:00 VN** (không phải 07:00 như dự kiến ban đầu). **Phương án A được chọn: GIỮ generator 3.8-flash**, resume ĐÚNG lệnh cũ mỗi ngày sau ~14:00 VN; WITHOUT hoàn tất dự kiến ~5 ngày (100 gen ÷ 20 RPD), WITH khởi động trong ngày đầu ngay sau đó (~13 request generator nhờ cache TRA_CUU). **Bị loại — đổi cả hai lượt sang lite:** generator + judge sẽ DÙNG CHUNG ngân sách lite (~313 request), chỉ thắng nếu lite RPD ≥ ~100 — không có bằng chứng, còn 3.8-flash quan sát được 20; thêm nữa đổi model làm mất tính "đánh giá đúng cấu hình production" và phải bỏ 9 câu đã chạy. **Bị loại — dò RPD lite bằng request:** lite RPD sẽ tự lộ qua judge (nếu judge 429 RPD trong lúc chạy → ghi lại con số, không đốt request dò). KHÔNG chạy song song hai lượt; KHÔNG chạy main.py/learn.py trong các ngày chạy.
- **--summary-output: CHẤP NHẬN** với điều kiện mục 4 của Bước 0 (không ghi đè file baseline).

## Sản phẩm

- `outputs/ab_results_without_classifier.json` (+ summary .md đi kèm)
- `outputs/ab_results_with_classifier.json` (+ summary .md đi kèm)

## Verify (bắt buộc)

- 2 file JSON đủ số câu chạy được (không đếm thiếu, không nhầm câu lỗi thành câu xong).
- 2 summary .md tồn tại; báo cáo kèm meta đầy đủ (top_k, model, ngày chạy, số câu lỗi/skipped).
- KHÔNG xóa/ghi đè bất kỳ file nào trong `outputs/baseline_*/`.
