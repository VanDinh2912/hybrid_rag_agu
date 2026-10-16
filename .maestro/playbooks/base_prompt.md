# BASE PROMPT — quy tắc dùng chung cho mọi playbook

Mọi agent, bất kể group nào, bắt buộc tuân thủ toàn bộ quy tắc dưới đây.

## 1. Vệ sinh repo

- Mọi file trung gian (bản nháp, script phụ, dump text, slice, file trích xuất thử)
  chỉ được nằm trong `tmp/`. TUYỆT ĐỐI không tạo file ở thư mục gốc repo,
  không trộn file trung gian vào `outputs/`.
- Mọi log/file tự sinh khi CHẠY nằm trong `logs/` đúng ý nghĩa quy định ở
  `logs/README.md` (`benchmark/`, `export/`, `learning/`, `feedback/`) —
  CẤM ghi log lẻ tẻ ra thư mục gốc hay chỗ khác.
- Ghi file luôn bằng Python: `open(path, 'w', encoding='utf-8')`.
  CẤM dùng chuyển hướng `>` của PowerShell hay `Out-File` — chúng ghi UTF-16
  (BOM FF FE) làm hỏng JSON khi đọc bằng utf-8.
- Trước khi kết thúc phiên: XÓA toàn bộ `tmp/`. Repo phải sạch như lúc nhận việc,
  chỉ trừ đúng những file sản phẩm mà playbook của group cho phép tạo/sửa.
- Dữ liệu chỉ được tồn tại MỘT nơi duy nhất ở trạng thái kết thúc. Không nhúng
  dữ liệu vào script Python, không giữ bản nháp song song sau khi đã gộp.

## 2. Quyền hạn theo group

- Chỉ được tạo/sửa/xóa file nằm trong mục "Phạm vi được đụng" của group mình.
- Mọi file đã được git track nằm ngoài phạm vi là CẤM sửa/xóa.
- Quyền ghi đặc biệt — ghi đúng theo bảng, group khác chỉ ĐỌC:
  - Group 01: ghi được `data/corpus/**` (toàn bộ) và `chroma_db/` (duy nhất qua
    quy trình ingest/rebuild); sở hữu `logs/learning/learning_log.csv`.
  - Group 03: sở hữu `logs/feedback/user_feedback.json` và `logs/export/export_report.txt`.
  - Group 04: ghi được `data/evaluation/**` và `logs/benchmark/`; sở hữu
    `outputs/evaluation_results.json` và `outputs/evaluation_summary.md`.
  - Group 02 và 03: chỉ ĐỌC `data/corpus/`, `chroma_db/`, `data/evaluation/`.
- Không sửa/xóa output trung gian hay sản phẩm của group khác.

## 3. Verify và báo cáo

- Trước khi báo hoàn thành, tự chạy toàn bộ mục "Verify" của group mình.
- Chỉ được báo "xong" khi mọi mốc verify PASS. Báo cáo hoàn thành bắt buộc gồm:
  (a) danh sách file đã tạo/sửa/xóa,
  (b) kết quả verify từng mốc,
  (c) xác nhận tmp/ đã dọn sạch.
- Nếu một mốc verify fail: sửa và chạy lại, KHÔNG báo xong khi còn fail,
  KHÔNG hạ tiêu chí verify để cho qua.
