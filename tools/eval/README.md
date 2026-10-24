# Khung benchmark "câu hỏi THẬT của sinh viên" (T6c)

## Vì sao bộ này tồn tại

Hai bộ đo hiện có **không** trả lời câu hỏi "hệ thống có giúp được sinh viên thật không":

- `data/loop` 811 item là câu **trích niêm** (câu được sinh từ chính câu trong tài liệu), nên
  `gold@k` cao chỉ chứng minh truy xuất tìm đúng đoạn, không chứng minh trả lời hay cho câu hỏi
  đời thật.
- benchmark v3 có 97 câu người viết nhưng vẫn **theo khuôn** (EXACT/CLOZE/…), không phải cách sinh
  viên hỏi.

Bộ này đo **câu hỏi không theo khuôn**, do sinh viên/người vận hành ghi lại.

## Cách dùng

1. Mở `real_questions.jsonl`, thay các dòng `RQ-EMPTY-*` và dòng có `"example": true` bằng
   **30–50 câu hỏi thật**. Mỗi câu ghi `nguon` (lấy từ đâu) và `chu_de`. `question` bắt buộc.
2. Đếm trước chi phí (bất biến #8 — mỗi câu 1 lượt pipeline):
   ```
   PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/eval/score_real_questions.py --dry-run
   ```
3. Chấm thử 5 câu, rồi toàn bộ:
   ```
   ... score_real_questions.py --limit 5
   ... score_real_questions.py
   ```
   Kết quả máy chấm (`answer`, `grounding_score`, `is_refusal`, `n_unsupported`, `latency`) ghi vào
   `real_questions_scored.jsonl` (KHÔNG ghi đè file câu hỏi). Cột `co_giup_duoc_khong` và `ghi_chu`
   để **TRỐNG cho người đọc điền**.
4. Sau khi người đọc điền `co_giup_duoc_khong` (co/khong/mot_phan), chạy lại lệnh ở bước 3 (file
   scored giữ nhãn đã điền) để `real_questions_summary.json` có trung bình + CI 95% cho "giúp được".

## Đọc kết quả đúng cách (giới hạn thật lòng)

- Cỡ mẫu 30–50 và nhãn "có giúp được không" là **phán chủ quan của một người đọc** ⇒ đây là
  **bằng chứng ĐỊNH TÍNH**, không phải tỉ lệ chính xác của hệ thống. CI bootstrap in ra sẽ RỘNG;
  đó là tín hiệu tốt (thật), không phải lỗi.
- `check_grounding` chỉ bắt được khẳng định **không có trong căn cứ** (số/tên riêng); nó **mù** với
  lớp "có căn cứ nhưng lạc đề" và với khẳng định thuần bằng chữ. Vì vậy `grounding_score` cao
  không đồng nghĩa "trả lời đúng" — vẫn phải có cột người đọc.
- Không được dùng bộ này để "cứu" các chỉ số pha sinh trên 811 item; nó là mặt trận ĐÁNH GIÁ song
  song, thiên về ứng dụng.
