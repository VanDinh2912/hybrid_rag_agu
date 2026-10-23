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
- (b) dừng ở 6/30 vì PerDay. Đề xuất: cho resume các ngày sau (lệnh ở STATE.md) để đủ n rồi mới
  chốt nhánh bảng quyết định (T4 vs T2/T6). Đêm nay KHÔNG gọi thêm.

## PA-5 — T3 / T5 / TT0–TT3: KHÔNG có đặc tả trong repo hay hội thoại → bị chặn
- Bối cảnh: lệnh tự trị qua đêm ghi "viết code + test cho T3 và T5 với mọi cờ TẮT" và "chạy test
  TT0–TT3". Nhưng tìm `ROADMAP.md`, `docs/`, `*.md` **không có định nghĩa** T3/T5/TT0–TT3 (chỉ
  STATE.md do em tự chép lại từ lệnh). T1 có nhắc "T3 = chọn/độ dài ngữ cảnh", "T4 = năng lực
  model/SFT", "T2+T6 = trọng tài/corpus" nhưng KHÔNG có đầu bài cụ thể (ràng buộc, tiêu chí xong).
- Quyết định bảo thủ: **KHÔNG bịa yêu cầu để viết code** (sẽ tạo lever sai, vi phạm tinh thần
  "mỗi lever sau cờ, có test chứng minh off=identical"). Đánh dấu **bị chặn — chờ đặc tả**.
- Cần người dùng: dán đặc tả T3/T5 (và TT0–TT3 là gì) để phiên sau làm.
- Việc đã làm thay thế trong khung giờ đó: dựng công cụ T2 Bước 3 (`quality_check_vie.py`) và
  kiểm thử đường code — nằm trong phạm vi T2 đã đặc tả rõ.

## PA-6 — T2: giữ `easyocr` làm dependency hay chỉ dùng chẩn đoán một lần
- Bối cảnh: để OCR lại 13 PDF scan bằng tiếng Việt, em đã `pip install easyocr torchvision
  scikit-image` vào `venv` (không sửa `requirements.txt`). Không có gì trong pipeline sản xuất
  import easyocr — nó chỉ được `tools/diag/reocr_vie.py` nạp khi chạy tay.
- Đề xuất A (an toàn): giữ nguyên `requirements.txt`, coi easyocr là công cụ chẩn đoán; cache
  `.ocr_cache_vie/` đã sinh nên không cần cài lại nếu chỉ nạp index.
- Đề xuất B: thêm `easyocr` (+ torch/torchvision) vào requirements nếu muốn tái OCR trên máy khác.
- Chưa làm: chưa đổi requirements, chưa commit lockfile. Hoàn tác: `pip uninstall easyocr
  torchvision scikit-image` trong `venv` (không ảnh hưởng `chroma_db/`, `.ocr_cache/`).

## PA-7 — T2: có loại 2 tệp `ke-hoach-ttck-kltn-dh24pm/th-2026.pdf` khỏi corpus không?
- Bối cảnh: đây là 2 tệp chủ yếu BẢNG BIỂU; EasyOCR trả 0,602–0,603 nhưng số từ giảm mạnh
  (1710 → 560 và 1607 → 572) và 20 đoạn đối chiếu mắt thường cho thấy phần lớn là ký tự rác.
  Chúng chiếm 7 của 337 chunk ≥50% dấu trong `chroma_db_vie/`.
- Đề xuất: hoặc (1) giữ như hiện tại (index mới đã có chúng), hoặc (2) đưa sang thư mục
  `data/corpus/_khong_index/` và rebuild `chroma_db_vie/`, hoặc (3) số hóa bảng bằng tay
  (đường T6, tốn công).
- Chưa làm: KHÔNG xóa/di chuyển file corpus nào (xóa = việc cần duyệt). Hoàn tác: không có thay đổi.

## PA-8 — Toàn bộ bằng chứng vòng lặp P5 đang KHÔNG nằm trong git (rủi ro mất dữ liệu)
- Bối cảnh (kiểm chứng 24-10): `git ls-files data/loop/rounds` = **0 file** dù thư mục nặng
  **46 MB** (r0–r7); `git ls-files tools/loop/` = **0**; `src/answer_guard.py` và
  `tests/test_loop_*.py`, `tests/test_answer_guard.py`, `tools/build_training_data.py`,
  `data/loop/testset_v1.jsonl` đều **untracked**. Nghĩa là trọng tài, gate, testset và mọi
  verdict của r0–r6 chỉ tồn tại trên đĩa, chưa có lịch sử, chưa có backup git.
- Đề xuất: một commit "freeze" trên `main` (hoặc `auto/overnight` rồi merge) chứa
  `tools/loop/`, `src/answer_guard.py`, `tests/test_loop_*.py`, `data/loop/testset_v1*.{jsonl,json}`,
  `data/loop/rounds/**` (46 MB — cân nhắc `rounds/r0_pilot` và PNG trong round), kèm thông báo
  cho phiên đang dở `src/`.
- Chưa làm: em KHÔNG commit hộ công việc đang dở của phiên khác (đã ghi ở AUTONOMY_LOG #1).
- Hoàn tác: `git revert` commit freeze; không có ghi đè nào.
