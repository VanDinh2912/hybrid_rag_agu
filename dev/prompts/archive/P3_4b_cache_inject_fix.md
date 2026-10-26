# P3.4b — Sửa bất đối xứng cache HIT/MISS (inject trích dẫn) — MICRO-TASK

> Giai đoạn 3 · Nhóm playbook: 02 · Thời gian: 0.5–1 ngày · **BẮT BUỘC xong trước P4.1**
> Nguồn: lỗi pre-existing agent phát hiện ở P3.4, người dùng duyệt sửa ngày 2026-10-20.

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Cùng một câu hỏi phải trả về **cùng một chuỗi** bất kể lượt gọi trúng cache hay không — điều kiện bắt buộc để P4 A/B tái lập được (lượt WITH dính cache-miss nhiều ở SO_SANH, nếu MISS và HIT khác nhau thì so sánh bị nhiễu).

## Chẩn đoán đã xác nhận (src/generator.py, đường GeminiGenerator)

- Nhánh MISS: `canonicalize_refusal` → `_cache_put` (lưu text **chưa** inject) → `inject_citations_from_metadata` → trả text CÓ trích dẫn.
- Nhánh HIT (`src/generator.py` ~786-788): trả nguyên text đã lưu, KHÔNG qua inject → text KHÔNG trích dẫn.
- Hệ quả: MISS và HIT khác nhau cho cùng prompt; ngược lại mọi cache entry cũ (308 file) đều là text chưa inject.

## Thiết kế bắt buộc (đã chốt với người dùng — làm đúng hướng này)

**Giữ cache lưu text CHƯA inject; chuyển `inject_citations_from_metadata` thành bước hậu xử lý dùng chung cho CẢ HAI nhánh.** KHÔNG chọn phương án "cache text sau inject" vì phải vô hiệu 308 entry cũ (bump PROMPT_VERSION) — đốt lại quota Gemini trước P4 vô ích.

1. Nhánh MISS (giữ nguyên trừ thứ tự): canonicalize → cache_put → **inject** → return.
2. Nhánh HIT: sau `_cache_get`, áp dụng CÙNG logic hậu xử lý:
   - Nếu `cached == REFUSAL_TEXT` và `question_type` là `NGOAI_PHAM_VI` (so fold, như điều kiện `is_canonical_refusal` hiện có) → trả nguyên chuỗi, KHÔNG inject.
   - Còn lại → `inject_citations_from_metadata(cached, retrieved_docs)` rồi return.
3. Tính tất định: `inject_citations_from_metadata` là hàm thuần của (text, metadata chunks) — cùng prompt ⇒ cùng docs ⇒ cùng trích dẫn, nên HIT+inject ≡ MISS+inject. Nếu phát hiện hàm có yếu tố bất định, báo cáo lại, không tự đổi thiết kế.
4. `PROMPT_VERSION` giữ nguyên `v1.3` (comment dòng 56 cập nhật lại để phản ánh: HIT giờ qua inject dùng chung, entry cũ vẫn hợp lệ).
5. Đường `QwenGenerator` (không dùng cache) kiểm tra đối xứng logic refusal/inject, chỉ sửa nếu lệch.

## Việc cần làm

1. Sửa `src/generator.py` theo thiết kế trên.
2. Bổ sung tests vào `tests/test_generator_prompts.py` (offline, mock API):
   - MISS → trả lời có trích dẫn, ghi cache; gọi lại HIT → chuỗi **giống hệt từng ký tự** lượt MISS; số lần gọi API đúng 1.
   - Canonical refusal: MISS trả `REFUSAL_TEXT` → cache chứa chuỗi chuẩn → HIT trả đúng `REFUSAL_TEXT`, không bị gắn trích dẫn.
   - Entry cũ (viết tay cache entry dạng text chưa inject) → HIT và được inject đúng, không bump version.
3. Không đụng: REFUSAL_TEXT, few-shot, biến thể prompt P3.4, cơ chế fallback Qwen, đường classifier/router.

## Sản phẩm

- `src/generator.py`, `tests/test_generator_prompts.py` cập nhật.

## Verify (bắt buộc)

- `venv\Scripts\python.exe -m pytest` toàn bộ xanh (≥ 252 test).
- Smoke 0 quota (Qwen offline hoặc cache hit): 1 câu hỏi đã có cache gọi 2 lần → 2 chuỗi identical, số file cache không tăng; 1 câu NGOAI_PHAM_VI (Q97) → đúng `REFUSAL_TEXT` cả MISS lẫn HIT.
- Cập nhật `prompts/PROGRESS.md` dòng P3.4b theo quy tắc mục 6.

## Ghi chú

- Đây là micro-task chèn giữa P3.4 (đã duyệt 2026-10-20) và P3.5 — thứ tự thực hiện: **P3.4b xong mới P3.5**, cả hai trước P4.1.
