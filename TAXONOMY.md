# TAXONOMY — Bộ nhãn câu hỏi cho RAG quy chế học vụ AGU

> Phiên bản 1.0 · Ngày 2026-10-20 · Trạng thái: **chờ người dùng duyệt** (cổng P1.1)
> Nguồn duy nhất: `data/evaluation/benchmark_100_questions_v2.json` (v2.1, 100 câu). Tài liệu này là căn cứ cho P1.2 (gán nhãn 100 câu) và P2.1 (few-shot cho classifier).

## A. 14 chủ đề

Giữ nguyên 14 giá trị `category` của v2 — không gộp, không tách trong đợt này.

| Chủ đề | Mô tả 1 dòng | Số câu trong v2 |
|---|---|---:|
| chương trình đào tạo | Môn học, mã môn, tín chỉ, học kỳ, môn tiên quyết/học trước, chuẩn đầu ra ELO và cấu trúc khối kiến thức của CTĐT. | 22 |
| học phí | Mức thu, miễn giảm, hồ sơ/thời hạn miễn giảm, học lại/cải thiện, gia hạn và thanh toán học phí. | 12 |
| cuộc thi chính luận | Nội dung, thể loại, đối tượng, dung lượng, hạn nộp, giải thưởng và tiêu chí chấm Cuộc thi Chính luận 2026. | 12 |
| đánh giá rèn luyện | Khung điểm, tiêu chí cộng/trừ, xếp loại và cách tính điểm rèn luyện học kỳ/toàn khóa. | 11 |
| khen thưởng sinh viên | Danh hiệu thi đua cá nhân/tập thể, tiêu chuẩn, mức thưởng, thẩm quyền và quy trình khen thưởng cấp Trường. | 10 |
| thực tập tốt nghiệp | Thời gian thực tập, điều kiện Khóa luận, báo cáo, điểm đánh giá, hội đồng và định dạng báo cáo TTTN. | 9 |
| quy chế công tác sinh viên | Nghỉ học tạm thời, kỷ luật/nhập học lại, cố vấn học tập, nghĩa vụ sinh viên và xử lý vi phạm thi cử. | 6 |
| sinh viên 5 tốt | Tiêu chuẩn, tiêu chí, hồ sơ xét danh hiệu Sinh viên 5 tốt và Giải thưởng Sao Tháng Giêng. | 6 |
| thực tập chuyên đề | Kế hoạch, thời gian, tài liệu nghiệm thu và thủ tục tự liên hệ cơ sở thực tập chuyên đề. | 3 |
| khen thưởng cấp ĐHQG | Tiêu chuẩn Sinh viên Xuất sắc toàn khóa và mức thưởng/đơn vị chi trả cấp ĐHQG-HCM. | 2 |
| ký túc xá | Giờ giấc ra vào và quy định sử dụng thiết bị điện, kỷ luật nội trú Ký túc xá. | 2 |
| tài chính sinh viên | Vay vốn học tập ACB: tài liệu xác thực, lãi suất ưu đãi và thời gian trả nợ gốc. | 2 |
| bảo hiểm y tế | BHYT bắt buộc: công việc của CVHT/lớp trưởng và cài đặt VssID/VNeID. | 2 |
| hành chính sinh viên | Mẫu đơn xác nhận hoàn cảnh khó khăn và cơ quan có thẩm quyền xác nhận. | 1 |
| **Tổng** | **Toàn bộ benchmark v2** | **100** |

Nguồn đếm: `data/evaluation/benchmark_100_questions_v2.json` → `questions[*].category`, đếm bằng Python `Counter` ngày 2026-10-20 (tổng 100 câu).

## B. 4 loại câu hỏi

Nhãn là chuỗi không dấu `SCREAMING_SNAKE_CASE`, dùng đúng từng ký tự; không đổi chữ hoa/thường, không thêm dấu.

| Nhãn | Định nghĩa | Dấu hiệu nhận biết |
|---|---|---|
| `TRA_CUU` | tra một thông tin cụ thể nằm ở một văn bản | hỏi "là bao nhiêu / điều kiện nào / là gì"; trả lời từ 1–2 Điều |
| `SO_SANH` | so sánh, đối chiếu, tổng hợp nhiều điểm hoặc nhiều nguồn | "so sánh / khác nhau / điểm khác như thế nào"; cần ghép ≥ 2 nơi |
| `THU_TUC` | hỏi cách làm thủ tục, quy trình, hồ sơ từng bước | "thủ tục / cần giấy tờ gì / làm sao để / các bước" |
| `NGOAI_PHAM_VI` | ngoài quy chế học vụ AGU (kiến thức chung, tư vấn cá nhân, trường khác) | không thể trả lời từ các văn bản trong corpus |

## C. Luật phân giải xung đột

Thứ tự xét cố định, dừng ở điều kiện đầu tiên thỏa:

1. **`NGOAI_PHAM_VI` xét trước** — câu không thể trả lời từ các văn bản trong corpus thì gán nhãn này, kể cả khi bề mặt câu hỏi trông giống tra cứu hoặc thủ tục.
2. **`SO_SANH`** — có từ dấu hiệu so sánh hoặc nội dung đòi hỏi ghép/đối chiếu nhiều điểm, nhiều mốc hoặc nhiều nguồn để trả lời.
3. **`THU_TUC`** — hỏi các bước làm, hồ sơ, giấy tờ, tài liệu cần nộp, nơi nộp/nơi xác nhận.
4. **`TRA_CUU`** — còn lại. Câu lưỡng lự giữa các nhãn thì chọn `TRA_CUU` (bảo thủ).

**Chú giải "ghép nhiều nơi":** tính khi cần đối chiếu ≥ 2 Điều/Khoản, ≥ 2 văn bản, hoặc nhiều mốc/đối tượng (ví dụ thang điểm của 6 mức xếp loại). Không tính việc liệt kê nhiều thuộc tính của cùng một đối tượng (mã môn + số tín chỉ + học kỳ của một môn) — trường hợp đó là `TRA_CUU`.

## D. Ví dụ few-shot chuẩn hóa

Mỗi loại có ≥ 2 câu thật, trích nguyên văn từ `raw_query` của v2 — không sửa câu, không bịa câu.

| Loại | ID | raw_query (nguyên văn) | Vì sao |
|---|---|---|---|
| `TRA_CUU` | Q20 | Thời gian đào tạo chuẩn theo kế hoạch của chương trình cử nhân Công nghệ thông tin là bao nhiêu năm? | Hỏi một con số cụ thể trong một văn bản CTĐT. |
| `TRA_CUU` | Q39 | Mức tiền thưởng kèm theo Giấy khen của Hiệu trưởng cho danh hiệu 'Sinh viên Xuất sắc' năm học là bao nhiêu? | Một mức tiền cụ thể của một danh hiệu. |
| `SO_SANH` | Q23 | Tiêu chí xếp loại kết quả rèn luyện học kỳ đối với các mức Xuất sắc, Tốt, Khá, Trung bình, Yếu, Kém được tính theo thang điểm nào? | Phải đối chiếu thang điểm của 6 mức xếp loại. |
| `SO_SANH` | Q72 | Đơn giá học phí cho 1 tín chỉ thực hành so với tín chỉ lý thuyết được quy định như thế nào? | So sánh trực tiếp hai mức đơn giá. |
| `THU_TUC` | Q63 | Hồ sơ đề nghị miễn giảm học phí đối với sinh viên khuyết tật gồm những giấy tờ gì? | Hỏi thành phần hồ sơ/giấy tờ cần nộp. |
| `THU_TUC` | Q88 | Trường hợp sinh viên tự liên hệ cơ sở thực tập ngoài danh sách liên kết của Trường cần làm thủ tục gì? | Hỏi thủ tục cần làm khi tự liên hệ cơ sở thực tập. |
| `NGOAI_PHAM_VI` | Q96 | Kế hoạch tổ chức đánh giá Thực tập chuyên đề cấp Khoa do đơn vị nào phê duyệt ban hành? | `in_corpus=false` — không có căn cứ trong corpus. |
| `NGOAI_PHAM_VI` | Q97 | Sinh viên không hoàn thành đủ số giờ thực tập tại doanh nghiệp có được xem xét gia hạn không? | `in_corpus=false` — chính sách này không có trong corpus. |
| `NGOAI_PHAM_VI` | Q98 | Hình thức kỷ luật đối với sinh viên bị phát hiện đạo văn trong báo cáo Khóa luận tốt nghiệp là gì? | `in_corpus=false` — không thể trả lời từ corpus hiện có. |

**Lưu ý Q96–Q98:** đây là 3 câu duy nhất trong v2 có `in_corpus=false`; theo luật C.(1), chúng thuộc `NGOAI_PHAM_VI` vì không thể trả lời từ corpus. P1.2 sẽ rà lại từng nhãn và chốt cách xử lý ground truth (bổ sung hoặc giữ trống) cho 3 câu này.

Nguồn ví dụ: `data/evaluation/benchmark_100_questions_v2.json` → `questions[*].raw_query`; đối chiếu ngược theo `id` bằng script trong `tmp/` trước khi bàn giao.
