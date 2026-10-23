# BÁO CÁO SÁNG (MORNING_REPORT) — phiên tự trị qua đêm 23-10 → 24-10

Chi nhánh: `auto/overnight` (4 commit: `65eb70a`, `d51d1db`, `b773446` + commit kết phiên).
`main` không đổi. **Không có code sản xuất nào bị sửa** — `chroma_db/`, `.ocr_cache/`,
`data/loop/rounds/`, `src/` sản xuất và các file REFEREE_FILES nguyên trạng.
`pytest tests -q`: **563 passed** (chạy 2 lần: sau T2-B4 và sau khi thêm `tools/diag/recount_dedup.py`).

## 0. Ba mươi giây

Nút thắt corpus đã được xác định và sửa **trong bản sao**: 13 PDF scan (81% số từ của corpus)
đọc bằng `rapidocr-onnxruntime` chỉ đạt **3,3% từ có dấu**; OCR lại bằng EasyOCR `vi` đạt
**82,3%**, và **đo trên chính chunk đã lưu vào index** cho **0,1913 → 0,8029** (vượt ngưỡng 60%
của đề bài; thước toàn-tệp trước = 0,178).
Nút thắt tầng sinh thì ngược lại: khi cho Qwen **đúng chunk vàng** (truy xuất hoàn hảo) trần
PASS_CORRECT vẫn chỉ **8,75%** và từ chối oan **86,25%** ⇒ nhánh "chọn/độ dài ngữ cảnh" bị BÁC;
phép thử phân nhánh T4-vs-T2/T6 (Gemini) mới đạt 7/30 vì PerDay của Google, nên **chưa chốt**.

## 1. ĐÃ XONG

**T0 — noise floor pha sinh** (docs/reports/T0.md). Hai lượt r5↔r5b cùng code: 5/100 verdict
đảo (5%), McNemar p=1,0 cho PASS_CORRECT, CI95 của hiệu ứng ghép cặp ±0,03 ⇒ **trần nhiễu ±3 item**.
Nguồn: `data/loop/noise_floor.json`.

**T1 — tách "năng lực model" khỏi "chất lượng ngữ cảnh"** (docs/reports/T1.md), 3 cấu hình ablation,
cùng 100 item r5, chấm bằng trọng tài hiện tại `9f1179ccab74`:
- (a) oracle Qwen + CHỈ chunk vàng: 80/80 dòng, 0 lỗi → refusal **0,8625**, PASS_CORRECT **7/80 = 8,75%**, fabrication **0/11**.
- (c) Qwen + gold_sentence ±2 câu: 80/80 dòng → refusal **0,95**, PASS_CORRECT **2/80 = 2,5%**, fabrication **0/4**.
- (b) Gemini + top-6 của r5: **7/30 id hợp lệ** (PerDay chặn, 49 dòng error) → refusal **0,1429**,
  PASS_CORRECT **5/7 = 71,4% [42,9; 100]**, fabrication **1/6** mà 1 ca là **dương-giả trọng tài** ("Theo Bản").
- Hiệu ứng ghép cặp r5→cfg: refusal (a) **+0,1875 [+0,0875; 0,300]**, (c) **+0,2752 [+0,175; 0,375]**
  (`data/loop/diag/comparison_vs_r5.json`).
- Phát hiện thêm: `rows.jsonl` của (b) có **2 id ghi trùng** (hai tiến trình chạy chồng nhau);
  đã dựng `tools/diag/recount_dedup.py` đếm lại theo id, **tự kiểm chứng** bằng cách tái tạo
  chính xác `summary.json` của (a)/(c) (`--compare-with-summary` → exit 0).

**T2 — chất lượng corpus, Bước 1→4** (docs/reports/T2.md), toàn bộ trên bản sao:
- Bước 1: `tools/diag/corpus_diacritics.py` phân loại 26 tệp + đo tỉ lệ có dấu, chia theo
  đường pypdf/OCR (`data/loop/diag/corpus_diagnostics/per_file.json`). Chẩn đoán: **không phải
  font TCVN3/VNI/ABC** (7 PDF text-layer đạt 0,75–0,86); thủ phạm là **OCR trang scan**;
  `TB16` có text-layer không dấu ngay trong file.
- Bước 2 (rẻ→đắt): (i) ánh xạ bảng mã áp dụng cho **0 tệp**; (ii) **không có** bản .docx gốc;
  (iii) `tools/diag/reocr_vie.py` EasyOCR `vi` 123 trang → `.ocr_cache_vie/` (checkpoint từng trang).
  **Không dùng mô hình khôi phục dấu tự do** (chọn EasyOCR thay VINST vì VINST phục hồi tone bằng seq2seq).
- Bước 3: `tools/diag/quality_check_vie.py` → `quality_vie.json` + 20 đoạn đối chiếu mắt thường
  (`manual_20_segments.txt`, seed 20261024). OCR tổng thể **0,0328 → 0,8226**; 11/13 tệp ≥0,78.
- Bước 4: build index MỚI `chroma_db_vie/` = **342/342 chunk** (T1 228 / T2 43 / bổ sung 71),
  0 trang rơi về rapidocr. Đo hai index bằng cùng script mới `tools/diag/measure_index.py`:
  **0,1913 → 0,8029** (12.096/63.223 → 49.119/61.179 từ), chunk <5% dấu **167 → 2**, chunk
  ≥50% dấu **79 → 337**, median mỗi chunk **0,055 → 0,815**
  (`index_before.json`, `index_after.json`). **Sửa bản cũ:** bản interim cặp 0,803 với
  "171/78" đo ngày 23-10 (không còn script tái lập); đo lại hôm nay ra **167/79** cho index cũ.
- **Chưa kích hoạt, chưa chấm lại round** (PA-1).

## 2. BỊ CHẶN (kèm lý do, không phải chưa thử)

1. **T3 / T5 / TT0–TT3 — thiếu đặc tả.** Tìm trong `ROADMAP.md`, `docs/`, `*.md`: không có đầu bài
   (chỉ có tên nhóm trong bảng quyết định T1). Theo luật bảo thủ "không bịa yêu cầu để viết code"
   ⇒PA-5. Sáng mai anh/chị dán đặc tả là phiên sau làm được ngay.
2. **(b) cần 23 item nữa** — PerDay FreeTier của Google (limit 20, thực đo ~14) chặn từ 00:22;
   không phải hết ngân sách đêm nay (lượt hợp lệ 7/14). Resume bằng lệnh ở docs/STATE.md.
3. **"Số Điều/Khoản khớp bản gốc 100%" (đề bài T2 Bước 3) không đạt được bằng OCR thuần** trên
   trang scan mờ: không có bản gốc dạng chữ để diff, và chính OCR sinh nhầm (VD. QD1133 ra
   "HỎ CHÍ MINH"). Đã đối chiếu mắt thường có chủ đích (ca `1504/QĐ-DHAG` — tên file ghi
   "1054" là sai tên, EasyOCR đọc đúng nội dung, không bịa). Ghi rõ là giới hạn, không báo cáo là đã sửa.
4. **Hai tệp `ke-hoach-ttck-kltn-dh24pm/th-2026.pdf` = "khoảng trống"**: nhiều bảng biểu,
   0,602/0,603 nhưng số từ collapses (1710→560, 1607→572) và 20 đoạn cho thấy phần lớn là rác.
   Hướng xử lý ở PA-7 (em không xóa/di chuyển file corpus nào).

## 3. VIỆC CẦN DUYỆT — `docs/PENDING_APPROVAL.md`

| ID | Việc | Tự làm? |
|---|---|---|
| PA-1 | Kích hoạt `chroma_db_vie/` + `.ocr_cache_vie/`, **chấm lại r0, r1, r2, r3, r4, r5** (+r5b nếu đối chiếu noise floor) — đổi đầu vào ⇒ đổi chữ ký/đầu vào trọng tài, tốn quota | KHÔNG |
| PA-2 | `answer_guard`: flag "Theo Bản" là proper-noun bịa (LOOKS_LIKE_FORMATTING) — chờ (b) đủ 30 để đếm ≥2/30, thuộc REFEREE_FILES | KHÔNG (chỉ đề xuất) |
| PA-3 | gate.py #23 (refusal tương đối + veto family) — nợ từ trước | KHÔNG |
| PA-4 | Cho resume (b) các ngày sau để đủ n rồi mới chốt T4 vs T2/T6 | KHÔNG |
| PA-5 | Đặc tả T3/T5/TT0–TT3 | CẦN ANH/CHỊ CUNG CẤP |
| PA-6 | Giữ `easyocr`+`torchvision`+`scikit-image` làm dependency chính thức hay chỉ công cụ chẩn đoán (requirements chưa đổi) | KHÔNG |
| PA-7 | Loại/giữ 2 tệp `ke-hoach` khỏi corpus | KHÔNG |

## 4. SỐ LIỆU CHÍNH + NGUỒN FILE (mọi số đều đọc lại được từ đĩa)

| Chỉ số | Trước | Sau | Nguồn |
|---|---|---|---|
| Từ có dấu — **trên index** (thước chính) | 0,1913 (12.096/63.223) | **0,8029** (49.119/61.179) | `.../index_before.json`, `.../index_after.json` (cùng `tools/diag/measure_index.py`) |
| Từ có dấu — trên văn bản tệp nguồn | 0,178 (9.569/53.656) | *(không đo lại; index là thước sau)* | `.../per_file.json` |
| Từ có dấu — riêng trang OCR | 0,0328 (1.420/43.327) | **0,8226** (34.705/42.188) | `quality_vie.json → ocr_total` |
| Chunk <5% dấu | **167**/361 | **2**/342 | `index_before.json` / `index_after.json` |
| Chunk ≥50% dấu | **79**/361 | **337**/342 | như trên |
| Median tỉ lệ dấu mỗi chunk | 0,055 | **0,815** | như trên |
| refusal_rate (a)/(c) vs r5 | r5 0,675 | 0,8625 / **0,95** | `.../a_oracle_qwen/summary.json`, `.../c_gold_window_qwen/summary.json` |
| PASS_CORRECT (a)/(c) | r5 14/80 = 17,5% | **7/80 = 8,75%** / **2/80 = 2,5%** | như trên |
| (b) Gemini | Qwen từ chối oan | **5/7 PASS_CORRECT**, refusal 0,1429 | `.../b_gemini_top6/summary_dedup.json` |
| Trần nhiễu pha sinh | 5/100 verdict đảo, CI ±0,03 | — | `data/loop/noise_floor.json` |

## 5. QUYẾT ĐỊNH TỰ TRỊ ĐÁNG XEM LẠI (chi tiết: `docs/AUTONOMY_LOG.md`)

1. **Không kích hoạt index mới, không chấm lại round** dù số đã vượt ngưỡng — vì đề bài liệt kê
   đúng hai việc đó vào nhóm "cần duyệt". Kết quả: corpus tốt hơn đang nằm chờ trong
   `chroma_db_vie/`, mọi số liệu r0–r5 vẫn là corpus cũ (nhất quán nhưng chưa phản ánh chất lượng mới).
2. **OCR vào cache MỚI + build index ở thư mục RIÊNG** thay vì sửa pipeline — chọn phương án
   hoàn tác được bằng 1 lệnh xóa.
3. **Commit tối thiểu trên cây dirty**: không commit/ không revert `src/*.py` đang dở của phiên
   r6/r7; không commit blob `.ocr_cache_vie/` (36 MB) và `chroma_db_vie/` (sinh lại được bằng lệnh
   trong STATE.md) — nếu anh/chị muốn lưu ảnh OCR vào git thì nói, em add được.
4. **Không gọi thêm Gemini sau khi PerDay chặn** (dù còn ~7/14 lượt ngân sách) — tôn trọng
   "hết quota thì bỏ phần cần Gemini" và tránh 200–290 s/lượt cho toàn lỗi.
5. **Sửa lại số của (b) theo hướng có lợi cho công cụ, bất lợi cho báo cáo**: phát hiện dòng trùng
   id nên chuyển từ "n=9, 4/6" thành "7 id duy nhất, 5 PASS_CORRECT", và giữ cả bản cũ trong T1.md.
6. **Thay cặp số "trước/sau" của T2 bằng phép đo cùng thước**: dựng `tools/diag/measure_index.py`,
   đo lại `chroma_db/` cũ → **0,1913 / 167 chunk <5% / 79 chunk ≥50%** (bản interim ghi 0,178 +
   171/78, trộn thước và lấy số 23-10 không còn script). Kết luận "đạt ≥60%" vẫn đúng nhưng nay
   mới so đúng đối tượng. Anh/chị nên xem lại vì số 18,6% từng công bố trong memory/project tài
   liệu là thước **toàn tệp**, không phải thước index.

## 6. Trạng thái repo & lệnh sáng mai

- Đọc `docs/STATE.md` (việc xong / đang làm / việc kế tiếp / lệnh tái lập).
- Thử index mới mà không đụng sản xuất:
  `PYTHONIOENCODING=utf-8 CHROMA_PERSIST_DIR=./chroma_db_vie OCR_CACHE_DIR=./.ocr_cache_vie ./venv/Scripts/python.exe main.py`
- Test: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q` (563 xanh).
- Dọn (chờ duyệt, em không tự xóa): `tmp/r5b_driver.sh`, `tmp/r6_driver.sh`,
  `tmp/probe_prefix_cache.py`, `tmp/*.png`.
