# `data/loop/diag_redacted/` — bản sao đã che của 8 tệp có cảnh báo nhân thân (PA-31)

Sinh ngày **29-10** bằng `tools/diag/redact_pii.py` (tool mới, **không sửa** `tools/diag/secret_scan.py`).
**Tệp gốc không bị sửa một byte nào** — đây là bản sao để chia sẻ/nộp, còn artifact gốc vẫn là bản
chính thức cho mọi round và mọi test đếm theo dòng.

## Đính chính tiền đề của PA-31 (ghi nguyên, không sửa hồ sơ cũ)

Hồ sơ PA-31 (25-10) ghi *"tất cả 8 file đang untracked nên chưa từng rời máy"*. Kiểm lại trên cây
29-10: **cả 8 tệp đều đã được git theo dõi** ⇒ câu đó **không còn đúng**, và hệ quả là:

- 89 dòng PII **đã nằm trong lịch sử git** từ trước hôm nay. Tạo bản redacted **không** xoá được
  chúng khỏi lịch sử.
- Muốn xoá thật phải viết lại lịch sử (đổi hash mọi commit từ đó về sau) — ngoài quyền của phiên này
  và sẽ làm gãy mọi con trỏ hash đã công bố. Việc đó cần một quyết định riêng của người dùng.
- Vì vậy bản redacted ở đây có giá trị **chia sẻ/nộp về sau**, không phải biện pháp khắc phục lịch sử.

## Số liệu (nguồn: `REDACTION_REPORT.json`, cùng lượt chạy)

| tệp nguồn | dòng | dòng có PII | khớp (khuôn công bố) | SĐT dạng khác (khuôn rộng) | còn lại |
|---|---:|---:|---:|---:|---:|
| `data/loop/diag/referee_labeling_r5.jsonl` | 60 | 8 | 28 | 37 | 0 |
| `data/loop/diag/referee_labeling_r5.md` | 7.765 | 28 | 28 | 37 | 0 |
| `data/loop/diag/b_gemini_top6/rows.jsonl` | 96 | 3 | 11 | 13 | 0 |
| `data/loop/diag/a_oracle_qwen/rows.jsonl` | 80 | 6 | 6 | 6 | 0 |
| `data/loop/diag/c_gold_window_qwen/rows.jsonl` | 80 | 6 | 6 | 6 | 0 |
| `outputs/ab_results_without_classifier.json` | 13.110 | 4 | 4 | 3 | 0 |
| `outputs/ab_results_with_classifier.json` | 14.347 | 3 | 3 | 13 | 0 |
| `data/loop/diag/corpus_diagnostics/manual_20_segments.txt` | 14.358 | 2 | 3 | 5 | 0 |
| **tổng** | | **60** | **89** | **120** | **0** |

- **89** = đúng con số đã công bố của `secret_scan` (65 số điện thoại + 24 email) — không đổi.
- **60 dòng** (không phải 89 dòng) là số **dòng** chứa ít nhất một cảnh báo; 89 là số **lần khớp**.
  Hồ sơ cũ gọi "89 dòng" là cách nói tắt, ghi lại cho rõ.
- **120** là lớp **bổ sung của tool này**: khuôn đã công bố chỉ cho **một** dấu phân cách tuỳ chọn nên
  bỏ sót dạng nhóm `09xx xxx xxx`, `0xxx.xxx.xxx`. Máy quét **không** bị sửa (đổi khuôn = đổi thước);
  lớp rộng chạy riêng, báo riêng, và **không** cộng vào số 89.
  Chốt chống dương tính giả: ứng viên phải là **trọn** 10 chữ số (đầu 03/05/07/08/09) hoặc 11 chữ số
  (đầu 02); chuỗi số dài hơn và số thực dạng `0.xxxxxxxx` bị loại. Đã soát hồi quy: **312** chuỗi số
  ≥12 chữ số trong 8 tệp vẫn còn nguyên sau khi che (0 bị cắt).

## Cổng đã qua trong lượt chạy

- số dòng bản che **=** số dòng bản gốc (8/8 tệp) ⇒ `.jsonl` vẫn đúng số bản ghi;
- 5 tệp JSON/JSONL vẫn **parse được** sau khi che;
- số khớp còn lại **= 0** trên cả hai khuôn.
- **Không** đổi số dòng của bất kỳ tệp nào: 49.896 → 49.896 dòng; 4.054.151 → 4.053.785 byte.
  (Byte trong báo cáo là của cây sinh ra bản che; bản trong git bị `core.autocrlf=true` chuẩn hoá
  EOL khi checkout ⇒ số dòng và tính hợp lệ JSON không đổi, số byte có thể lệch vài chục.)

## Cái gì KHÔNG bị che (giới hạn, ghi rõ để không hiểu nhầm là "đã sạch PII")

- **Họ tên người** (`anh A`, `Thầy B`, `Cô C` trong corpus/verdict) — máy quét không có khuôn tên,
  và thêm khuôn tên là đổi dụng cụ đo.
- Số định danh **không** đứng sau từ khoá định danh (khuôn hiện hành yêu cầu `mssv|cccd|hotline|…`).
- `SECRET_COTHAT`/`BI_MAU`: máy quét khai **0** ca thật, nên không có gì để che.

## Chạy lại

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/redact_pii.py --dry   # chỉ đo
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/redact_pii.py         # ghi bản che
```

Token tất định trong từng tệp: `[EMAIL_n]`, `[PHONE_n]`, `[ID_n]` (khuôn công bố) và
`[PHONE_B_n]` (khuôn rộng). Token không chứa `@`, `"`, `\`, xuống dòng; với tệp JSON, escape `\`
đứng ngay trước token được nhân đôi để chuỗi vẫn hợp lệ.
