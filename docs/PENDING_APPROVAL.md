# PENDING_APPROVAL — việc cần người dùng duyệt (phiên tự trị KHÔNG tự làm)

Mỗi mục: bối cảnh → đề xuất → diff/đường dẫn → cách hoàn tác nếu bị từ chối.

---

## PA-1 — T2: kích hoạt index mới `chroma_db_vie/` và chấm lại r0–r5
- Bối cảnh: OCR lại 13 PDF scan bằng EasyOCR `vi` nâng corpus từ 0,178 → (dự kiến ~0,7). Toàn bộ
  nằm ở BẢN SAO (`chroma_db_vie/`, `.ocr_cache_vie/`); pipeline sản xuất và `chroma_db/` gốc KHÔNG đổi.
- Đề xuất (khi người dùng đồng ý): (1) đổi con trỏ corpus/DB sang bản mới; (2) chạy lại round
  r0–r5 để lấy số trên corpus đã hồi phục dấu.
- Hệ quả: đổi nội dung nạp → **chữ ký trọng tài/đầu vào đổi** → **phải chấm lại r0–r5** (quota Gemini).
- Chưa làm: chưa kích hoạt, chưa chấm lại. Hoàn tác: `rm -rf chroma_db_vie/ .ocr_cache_vie/` (bản gốc nguyên vẹn).

## PA-2 — T1: đề xuất sửa `answer_guard` cho lỗi nhận diện "Theo Bản" (LOOKS_LIKE_FORMATTING)
- Bối cảnh: dòng (b) `C10492769338965` bị `FAIL_FABRICATED` vì trọng tài gắn cờ "Theo Bản" là tên
  riêng bịa đặt — thực chất là cụm chính tả bình thường (lỗi LOOKS_LIKE_FORMATTING, cùng họ đã ghi ở audit_guard).
- Đề xuất: nới luật phát hiện tên riêng trong `src/answer_guard.py` (KHÔNG tự sửa — file thuộc
  REFEREE_FILES, đổi chữ ký `9f1179ccab74`). Cần danh sách round phải chấm lại kèm theo.
- Chặn: cần (b) đủ n=30 để đếm tỉ lệ dương-giả loại này (≥2/30 mới đáng sửa). Hiện mới n=7.
- Diff: sẽ bổ sung khi có đủ n; hiện CHƯA có thay đổi code.

## PA-3 — cổng gate.py (đang chờ từ trước, không đổi): #23 quy tắc refusal tương đối + veto family
- Giữ nguyên trạng thái "chờ duyệt"; `gate.py` chưa sửa. Xem `docs/reports/T0.md` mục hệ quả cổng.

## PA-4 — T1 (b) tiếp tục: cần quota Gemini các ngày sau
- (b) dừng ở 7/30 vì PerDay. Đề xuất: cho resume các ngày sau (lệnh ở STATE.md) để đủ n rồi mới
  chốt nhánh bảng quyết định (T4 vs T2/T6). Đêm nay KHÔNG gọi thêm.
