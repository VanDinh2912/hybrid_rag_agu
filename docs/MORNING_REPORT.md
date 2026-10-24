# BÁO CÁO SÁNG (MORNING_REPORT) — phiên tự trị qua đêm 23-10 → 24-10

Chi nhánh: `auto/overnight`, hiện **16 commit** so với `main` (`29f37dc`); HEAD `85d40a0`.
`main` không bị sửa. Các mục 0–6 dưới đây là **bản ghi đêm đầu (23-10 → 24-10)**; phần
**"PHIÊN TIẾP 24-10"** ngay sau đây là trạng thái mới nhất, thay thế các kết luận đã cũ
(đặc biệt mục "BỊ CHẶN" số 1 về T3/T5/TT0–TT3).
`pytest tests -q` mới nhất: **957 passed** (`tmp/pytest_t5_final.txt`, 26,84 s).

## PHIÊN TIẾP 24-10 (T3 → T7 + kiểm thử T0–T5) — cập nhật cuối phiên

### A. Đã xong (số liệu + nguồn)

| Việc | Kết quả | Nguồn |
|---|---|---|
| T3 r8 (`ENABLE_DECOUPLED_REFUSAL`), r9 (+`ENABLE_EVIDENCE_SELECTION`) | **Cả hai KHÔNG ĐẠT.** PASS_CORRECT 14→19→19; refusal 0,69→0,28→0,57; PASS_REFUSAL 17→2→14; HALLUCINATED 2→12→3; p95 19,08→19,93→33,27 s. Giữ hai cờ **TẮT** | `data/loop/rounds/r8/`, `r9/`, `docs/reports/T3.md` |
| T4 r10 (qwen2.5:3b Q4, 100% GPU) | PASS_CORRECT 14→**16**, McNemar **p=0,804**, CI delta **[−0,06;+0,10]** chứa 0; refusal 0,69→0,75; p95 +83% ⇒ **giữ 1,5B**, không mở Qwen3-4B | `data/loop/rounds/r10/`, `docs/reports/T4.md` |
| T4(b) Gemini `b_gemini_top6` | **12/30 id hợp lệ** (PerDay chặn) ⇒ **cấm** kết luận "năng lực model là nút thắt" | `data/loop/diag/b_gemini_top6/`, `docs/reports/T4.md` |
| T5 bonus 3 vs 12 (ghép cặp 811 item) | delta **−0,0257**, CI [−0,04;−0,0129], **p=0,00028**, 21 mất/3 được; **21/21** chunk vàng rơi hạng 7–12; EXACT/TRAP bất biến ⇒ con số bonus không phải nút thắt | `data/loop/diag/bonus_paired_r1_r2.json` |
| T5a reranker | `ENABLE_RERANKER` mặc định TẮT, model `BAAI/bge-reranker-v2-m3` (cache 2,2 GB), móc **sau** bonus lọc mềm; 46 test riêng của T5a. **r11 retrieval-only 811 item đã có** | `src/reranker.py`, `tests/test_reranker_flag.py`, `data/loop/rounds/r11/` |
| **T5-test (phiên này)** | **68 test** (26 hợp đồng reranker + 42 contextual header) xanh; mutation **10/10 bắt được, 10/10 hoàn nguyên byte-identical**; golden 30 item T3 khớp từng khoá; toàn repo **957 passed** | `tests/test_t5_*.py`, `tmp/mutation_check_t5.log`, `docs/reports/test_T5.md` |
| T5b contextual header (module) | `src/contextual_header.py`, cờ `ENABLE_CONTEXTUAL_HEADER` mặc định **TẮT**, **chưa nối `ingest.py`, chưa build index**; header thật trên index: 232/361 và 227/342 chunk có Điều, Chương chỉ 9/361 và 18/342. Digest hai index không đổi | `src/contextual_header.py`, `tests/test_t5_contextual_header.py` |
| T6 khung kiểm chứng trước hội đồng | PA-13 đề xuất cổng refusal tương đối (8 test, **gate.py không đổi**); 60 mẫu phân tầng chờ nhãn tay (`n_filled=0`); khung câu hỏi thật (**0 câu**); bootstrap CI vào mục 5.1; tổng điểm đính chính **7,4 → 7,2** | `docs/reports/T6.md`, `docs/PENDING_APPROVAL.md` PA-13 |
| Kiểm thử T0–T3 + chạy TT0–TT3 | 21 test T0 + 24 test T1 + 78 test T2 + 75 test T3; **TT0–TT3: 198 passed** | `tmp/pytest_tt0_tt3_final.txt`, `docs/reports/test_T{0,1,2,3}.md` |

Không dùng thêm lượt Gemini nào trong phiên tiếp này (**0 lượt**); không chạy round mới
(r11 đã chạy trước đó, r12 chưa chạy); không build/kích hoạt index; không sửa trọng tài/gate.

### B. Bị chặn / chưa nghiệm thu

1. **T5 chưa nghiệm thu đầy đủ theo câu chữ đề bài:** (i) mục 5 đòi "lùi RRF + cảnh báo" nhưng
   thiết kế đã đăng ký **cấm lùi thầm** ⇒ test ghim hành vi ném lỗi, ghi rõ khác biệt (PA-18);
   (ii) **chưa chạy lại gold@6 cấu hình TẮT trên 811 item** để so round đã đóng; (iii) **r12
   (reranker) chưa chạy** — chưa có `data/loop/rounds/r12/`.
2. **T5b chưa có index thật:** chờ PA-1 (corpus) + PA-16/PA-18 (wire + guard); mới có unit test
   và digest chứng minh index cũ không bị ghi.
3. **T1(b)/T4(b) dừng ở 12/30 id** vì PerDay Google; chỉ được nói "chưa đủ n", không kết luận.
4. **T2 mục 9 ĐỎ** (48,81% neo nguyên văn gãy > ngưỡng 2%); re-anchor 292 id ở PA-17, chưa làm.
5. **T6b/T6c chưa có dữ liệu người:** 60 phiếu `n_filled=0`; benchmark câu thật 0 câu.
6. **PA-8 vẫn treo:** `tools/loop/`, `data/loop/rounds/`, `src/answer_guard.py`, testset chưa
   tracked; không commit hộ file `src/` dirty của phiên khác.

### C. Việc cần duyệt

Xem đầy đủ trong [`docs/PENDING_APPROVAL.md`](PENDING_APPROVAL.md). Mới trong phiên này:
**PA-18** (T5: cờ fallback reranker tuỳ chọn; header có/không vào ngữ cảnh generator; wire
contextual header vào `ingest.py` + build index thư mục mới). Các mục cũ còn treo: PA-1
(kích hoạt `chroma_db_vie`), PA-3 (sửa cổng #23), PA-8 (commit freeze), PA-9/PA-10 (tầng sinh),
PA-11/PA-12 (SFT 4-bit/định dạng), PA-13 (cổng refusal tương đối), PA-14/PA-15 (Gemini/dead
code T3), PA-16 (`ingest.py` guard), PA-17 (re-anchor testset).

### D. Quyết định tự trị đáng xem lại (chi tiết `docs/AUTONOMY_LOG.md`)

1. **Không tự thêm fallback reranker** dù đề bài mục 5 yêu cầu: giữ thiết kế đăng ký trước
   (ném lỗi tường minh) và ghim bằng test; đề xuất cờ TẮT ở PA-18. Nếu anh/chị muốn hành vi
   theo câu chữ đề bài, bật cờ này khi được duyệt.
2. **Không build index T5b** dù module đã xong: corpus chưa chốt (PA-1) và chưa duyệt wire
   (PA-16/PA-18); chỉ kiểm bằng index nhỏ trong `tmp_path` + digest hai index thật.
3. **Dùng lại golden T3** cho mục 1 thay vì tạo golden mới: golden được chụp từ `git archive
   HEAD f492f05`, đúng trạng thái "trước khi nối T5", tránh golden tự sinh vòng tròn.
4. **Mutation trên file dirty của phiên khác** (`src/pipeline.py`, `src/reranker.py`): bắt buộc
   backup byte + kiểm SHA-256 sau khôi phục; cả 10/10 lần trùng, không commit các file đó.
5. **Không gọi Gemini** trong phiên tiếp; mọi việc cần model thật đều ghi "chưa kiểm chứng".

## BẢN GHI ĐÊM ĐẦU (23-10 → 24-10; các số dưới đây giữ nguyên lịch sử)

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
| PA-8 | **`data/loop/rounds/` (46 MB, r0–r7), `tools/loop/` (verify/gate/run_round), `src/answer_guard.py`, `tests/test_loop_*.py`, `data/loop/testset_v1.jsonl` đều UNTRACKED** — bằng chứng + trọng tài chưa có trong git. Đề xuất một commit "freeze" | KHÔNG (không commit hộ công việc dở của phiên khác) |

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

- Chi nhánh: `auto/overnight`, 4 commit so với `main` (`65eb70a`, `d51d1db`, `b773446`, `467ee5f`)
  + commit tài liệu PA-8. **Lưu ý khi checkout sạch**: `tools/loop/`, `src/answer_guard.py`,
  `data/loop/rounds/` chưa từng được commit (PA-8) ⇒ code trên nhánh phụ thuộc chúng; muốn chạy
  từ HEAD sạch thì phải làm commit freeze trước.
- Đọc `docs/STATE.md` (việc xong / đang làm / việc kế tiếp / lệnh tái lập).
- Thử index mới mà không đụng sản xuất:
  `PYTHONIOENCODING=utf-8 CHROMA_PERSIST_DIR=./chroma_db_vie OCR_CACHE_DIR=./.ocr_cache_vie ./venv/Scripts/python.exe main.py`
- Test: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q` (563 xanh).
- Dọn (chờ duyệt, em không tự xóa): `tmp/r5b_driver.sh`, `tmp/r6_driver.sh`,
  `tmp/probe_prefix_cache.py`, `tmp/*.png`.
