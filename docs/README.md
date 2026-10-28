# Tài liệu dự án — chỉ mục

Thư mục này chứa **tài liệu nghiên cứu và kiểm chứng** của đồ án. Điểm vào chính vẫn là
[README.md](../README.md) (cài đặt, sử dụng) và [ROADMAP.md](planning/ROADMAP.md) (kế hoạch, cổng,
lịch sử P5).

| Tệp / thư mục | Nội dung | Khi nào đọc |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Bản đồ tầng, module, bất biến vận hành | Trước khi sửa mã hoặc mở round mới |
| [EXPERIMENTS.md](EXPERIMENTS.md) | **Một bảng** thí nghiệm: giả thuyết · kết quả · n · CI 95% · tệp nguồn | Cần số đo và nguồn để trích dẫn |
| [REPRODUCE.md](REPRODUCE.md) | Lệnh tái lập: index, đánh giá, round, máy kiểm, số neo | Muốn chạy lại từ máy sạch |
| [DECISION_LOG.md](DECISION_LOG.md) | Sổ quyết định 6 cột (D-01…D-42); mỗi nguồn phải tồn tại trên đĩa | Cần biết vì sao một lever bị bác/giữ |
| [CLEANUP_ANCHORS.md](CLEANUP_ANCHORS.md) | Neo dọn repo 26-10: fingerprint, số test, round neo — **số đóng băng** | Kiểm "dọn cấu trúc không đổi số đo" |
| [CLEANUP_REPORT.md](CLEANUP_REPORT.md) | Báo cáo KẾT PHIẾN đợt dọn B0–B7: việc đã làm, việc cắt, PA chờ duyệt, bảng neo trước/sau | Nghiệm thu đợt dọn cấu trúc |
| [PA_TRIAGE.md](PA_TRIAGE.md) | Phân loại PA-1…PA-47 theo ảnh hưởng, kèm khuyến nghị duyệt/đóng/hoãn | Chọn việc duyệt tiếp theo |
| [EVIDENCE_PACK.md](EVIDENCE_PACK.md) | Gói bằng chứng: mỗi dòng EXPERIMENTS → tệp nguồn + SHA-256 12 đầu, kèm máy kiểm hash | Đối chiếu một con số với artifact gốc |
| [archive/](archive/) | Báo cáo T0–T7, test_T*, B1–B5, AUTONOMY_LOG, STATE, MORNING_REPORT, PENDING_APPROVAL — lưu nguyên trạng | Tra lịch sử; liên kết trong đây giữ đường dẫn trước khi dời |
| [bao_cao/](bao_cao/) | Bản nháp chương báo cáo | Viết báo cáo |
| [giang_day/](giang_day/) | Giáo trình/bài giảng 14 tệp | Dạy hoặc học lại pipeline |

**Vì sao `bao_cao/` không nằm trong `archive/`:** `tools/train/build_training_data.py` đọc
`docs/bao_cao/*.md` khi dựng dữ liệu huấn luyện — dời thư mục là đổi đầu vào của một dụng cụ sinh
dữ liệu, nên giữ nguyên vị trí.

**Vì sao `DECISION_LOG.md` ở lại:** `tools/diag/docs_consistency_check.py` đọc cứng
`docs/DECISION_LOG.md`; test T7 chặn nếu số mục < 20. Dời đi làm đỏ máy kiểm chứ không phải dọn
cấu trúc.

Quy ước: mọi số trong tài liệu phải truy được về một tệp nguồn trên đĩa; khi artifact và tài liệu
lệch nhau, **artifact là nguồn**. Ngưỡng đã đăng ký trước không chỉnh sau khi thấy số.
