# Lưu trữ báo cáo và nhật ký phiên

Thư mục này là **bản lưu nguyên trạng** các báo cáo/nhật ký của đồ án, dời vào đây ngày 26-10
(bước B7 của đợt dọn cấu trúc). Không xoá tệp nào và không sửa nội dung tệp nào khi dời.

| Nhóm | Tệp | Nội dung |
|---|---|---|
| Nhật ký phiên | `AUTONOMY_LOG.md`, `STATE.md`, `MORNING_REPORT.md` | Nhật ký từng ngã rẽ kỹ thuật, trạng thái và báo cáo buổi làm việc |
| Hàng đợi duyệt | `PENDING_APPROVAL.md` | PA-1…PA-46: đề xuất chờ user duyệt, kèm bằng chứng và phương án hoàn tác |
| Báo cáo nhiệm vụ | `reports/T0.md`…`T6.md`, `reports/B1.md`…`B5.md` | Báo cáo từng đợt T (kiểm chứng) và B (ablation/bổ sung 26-10) |
| Kiểm thử/kiểm toán | `reports/test_T0.md`…`test_T7.md`, `reports/test_P5-loop.md`, `reports/test_final.md` | Báo cáo bộ test, đột biến, kiểm toán số công bố |

**Quy ước đọc:**

- Số đo chuẩn để trích dẫn nằm ở [../EXPERIMENTS.md](../EXPERIMENTS.md) và
  [../DECISION_LOG.md](../DECISION_LOG.md); các tệp trong đây là bản ghi lịch sử đầy đủ.
- Liên kết bên trong các tệp lưu trữ vẫn giữ đường dẫn **trước khi dời** (ví dụ
  `docs/reports/T3.md`). Đó là chủ ý: bản ghi phải đọc được như lúc viết; bản đồ đường dẫn mới
  nằm ở tệp này và ở [../README.md](../README.md).
- Không chạy lại script đo để "làm mới" số trong đây: artifact đã công bố là bất biến.
