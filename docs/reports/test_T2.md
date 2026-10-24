# Kiểm thử T2 — kiểm định corpus rebuild (`chroma_db_vie/`)

Ngày: 24-10 (ca tối). Người chạy: agent kiểm thử (chế độ tự trị).
Phạm vi: **chỉ thêm test + script chẩn đoán + mutation check**; KHÔNG sửa `src/` sản xuất,
KHÔNG sửa trọng tài (`tools/loop/verify.py`, `src/answer_guard.py`, `src/text_utils.py`,
`tools/loop/gate.py`), KHÔNG build/ghi index, KHÔNG chấm lại round.

## 0. Kết luận trước (đọc mục này là đủ)

- **Test xanh: 78/78** (`tests/test_corpus_rebuild.py`); toàn repo **889 passed**
  (`tmp/pytest_t2_final.txt`).
- **Tiêu chí nghiệm thu của đề bài KHÔNG ĐẠT**, vì **mục 9 ĐỎ**: mất neo vàng **48,81%**
  (389/797 item) so với ngưỡng đăng ký trước **2%**. Đây là số thật, không phải lỗi test — chi
  tiết và cách đọc ở §3.1.
- **Mục 8 chờ người dùng duyệt:** 20 đoạn ngẫu nhiên (seed `20261024`) đã xuất ra
  `data/loop/diag/corpus_check/manual_20_segments_new_index.txt`.
- **Phát hiện mới cần duyệt:** cổng an toàn `plan_index_write` (mục 5) **chưa được nối** vào
  đường build thật `ingest.py` — `ingest.py` vẫn `shutil.rmtree` thư mục đích (PA-16); và việc
  sửa neo `gold_sentence` của 292 item bị regression là thay đổi dữ liệu cần duyệt (PA-17).
- Chữ ký trọng tài **KHÔNG đổi**: `9f1179ccab74`. Chữ ký DỮ LIỆU index đổi
  `8031beea81da(361)` → `6aa8c0fd9162(342)` — đúng như dự kiến khi rebuild.

## 1. Đã làm gì

1. **Unit test 6 ca đầu** — [`tests/test_corpus_rebuild.py`](../../tests/test_corpus_rebuild.py)
   (394 dòng, 78 test). Mọi test dùng dữ liệu ngắn tự dựng; **không** đọc `chroma_db*` thật,
   **không** gọi model, **không** ghi tệp corpus:

   | Nhóm (đề bài) | Class | Số test |
   |---|---|---:|
   | #1 bảng mã / normalisation | `TestEncodingNormalisation` | 4 |
   | #1b ký tự ngoài bảng Việt (bổ sung khi thêm khối 7c) | `TestForeignGlyphs` | 35 |
   | #2 bảo toàn thực thể pháp lý | `TestEntityPreservation` | 5 |
   | #3 chỉ số chất lượng | `TestQualityMetrics` | 7 |
   | #4 cổng chất lượng theo tệp | `TestQualityGate` | 6 |
   | #5 an toàn dữ liệu | `TestDataSafety` | 8 |
   | #6 tính xác định | `TestDeterminism` | 6 |
   | #9 gold coverage + hygiene (hàm thuần) | `TestGoldCoverageAndHygiene` | 7 |
   | **Tổng** | | **78** |

2. **Kiểm dữ liệu thật (mục 7–10)** —
   [`tools/diag/check_corpus.py`](../../tools/diag/check_corpus.py) (629 dòng, chỉ ĐỌC). Lần chạy
   này bổ sung khối **[7c] ký tự ngoài bảng Việt** (đề bài #1): đếm + mã Unicode + ví dụ ngữ
   cảnh, **không bỏ, không đoán**, ghi vào `corpus_check.json`. Kết quả đầy đủ:
   `data/loop/diag/corpus_check/corpus_check.json`; log `tmp/t2_check_corpus_7c.log`.
3. **Mutation check** — [`tmp/mutation_check_t2.py`](../../tmp/mutation_check_t2.py): 5 đột biến
   theo byte-anchor trên chính `check_corpus.py`, chạy lại file test, khôi phục bằng
   `write_bytes` + `os.utime`, xác nhận SHA-256 từng byte. Log: `tmp/t2_mutation.log`.

## 2. Kết quả số (nguồn: file trên đĩa)

### 2.1. Dữ liệu thật — mục 7–10

| Mục | Số đo | Nguồn |
|---|---|---|
| [5] bất biến index CŨ (nội dung) | `8031beea81da(361)` trước = sau khi mở lại ⇒ **KHÔNG ĐỔI** | `corpus_check.json:old_content_signature` |
| [5] byte-digest index cũ | `2fe840fcf73fed3f` → `b0be47af5d92c165` (đổi **mỗi lần mở** vì ChromaDB tái ghi; thước đúng là nội dung) | `corpus_check.json:old_dir_digest` |
| [7] tệp nguồn | **26** (21 `.pdf`, 5 `.docx`) — khớp kỳ vọng | `corpus_check.json:source_files` |
| [7] chunk cũ / mới | 361 / **342**; rỗng 0 / 0; trùng nguyên văn 0 (0,0%) / 0 (0,0%) | `hygiene_old`, `hygiene_new` |
| [7b] cổng chất lượng index MỚI | 26 nhóm tệp: **tốt 23**, **khoảng_trống 3** | `gate.n_good_new/n_gap_new` |
| [7b] khoảng trống còn trong index mới | 3/3 **bị nạp mà không gắn cờ** (`silent=true`) ⇒ PA-7 | `gate.leak` |
| [7c] ký tự ngoài bảng Việt | **19** ký tự / 324.979 (**2 loại**): `U+208A ₊` ×16, `U+20AC €` ×3 | `foreign_glyphs` |
| [8] 20 đoạn đối chiếu | seed `20261024`, 20 đoạn, file 14.260 byte | `manual_20_segments_new_index.txt` |
| [9] mất neo vàng | **389/797 = 48,81%** — **ĐỎ** (ngưỡng 2%) | `gold_coverage` |
| [9] chẩn đoán chỗ mất | gần-nội-dung (**near**) 375; **mất thật (absent) 14 = 1,76%** | `n_near_verbatim`, `n_absent` |
| [9] so index CŨ | cũ mất **97 = 12,17%**; **regression riêng do rebuild = 292 item (36,64%)** — danh sách id lưu ở `paired.regressed_ids` (292 id, không trùng) | `paired` |
| [10] chữ ký trọng tài | **`9f1179ccab74` — KHÔNG đổi** | `referee_fingerprint` |
| [10] chữ ký dữ liệu | `8031beea81da(361)` → `6aa8c0fd9162(342)` — ĐỔI (đúng) | `index_signature_*` |
| [10] round phải chấm lại | 14 thư mục: r0, r0_pilot, r1–r11 (trừ r0_pilot tính riêng) | `rounds_to_rescore` |

Ba tệp bị cổng gắn "khoảng trống" nhưng vẫn có chunk trong index mới (PA-7):

| Tệp (stem) | `n_chunks` | từ có dấu | Lý do |
|---|---:|---:|---|
| `kehoachttckkltndh24pm2026pdf` | 4 | 0,587 | < 0,60 |
| `kehoachttckkltndh24th2026pdf` | 4 | 0,582 | < 0,60 |
| `tb16thaydoicongravaoktxpdf` | 2 | **0,000** | PDF-TEXT 328 từ, font `Helvetica`, `tounicode_frac=0.0` |

(TB16 là phát hiện **mới** của lần chạy này — PA-7 trước chỉ nêu 2 tệp kế hoạch; đã bổ sung vào PA-7.)

### 2.2. Ký tự ngoài bảng Việt ([7c]) — chỉ đo, không phải cổng đỏ

- 324.960/324.979 ký tự thuộc dải ASCII in được / chữ Việt (dựng sẵn **và** dựng tổ hợp) /
  dấu câu hợp lệ. 19 ký tự còn lại là 2 loại, kèm ví dụ ngữ cảnh trong JSON:
  - `U+208A '₊'` ×16 — ví dụ: `… Nguyên tắc phân công: ₊ Mỗi học phần được phân côn…`
    (gần như chắc chắn là gạch đầu dòng bị OCR đọc sai, nhưng script **không tự kết luận**).
  - `U+20AC '€'` ×3 — ví dụ nằm trong vùng chữ rác `… { 9 € 1 ẵg ẵ { F f: g 1 { ẵ fẲi…`.
- Đây là **chẩn đoán**, không có ngưỡng đăng ký trước: 19 ký tự không làm test đỏ và cũng không
  được dùng để tuyên bố corpus "sạch".

### 2.3. Mutation check — 5/5 bắt được, hoàn nguyên byte-identical

Nguồn: `tmp/t2_mutation.log`.

| Đột biến | Kỳ vọng phá | Test đỏ (số lượng) | Khôi phục |
|---|---|---|---:|
| M1 so thực thể bằng `fold` | mất dấu thanh bị coi là "không đổi" | 3 (fold-vs-verbatim, đổi 1 chữ số, mất số hiệu) | byte-identical |
| M2 làm yếu khớp gold (≥3 từ chung = còn neo) | verbatim bị thay bằng overlap | 2 (gold còn/mất, near-vs-absent) | byte-identical |
| M3 `file_status` luôn `"tốt"` | cổng chất lượng vô hiệu | 4 (dưới ngưỡng, vocab, không đo được, partition) | byte-identical |
| M4 bỏ guard "đích đã tồn tại" | build đè lên thư mục có dữ liệu | 1 (`test_plan_index_write_tu_choi...`) | byte-identical |
| M5 ký tự lạ luôn hợp lệ | 7c câm | 13 | byte-identical |

## 3. Kết luận chỉ từ số + điều KHÔNG kết luận được

### 3.1. Vì sao mục 9 ĐỎ — và nó KHÔNG phải lỗi của test

Đăng ký trước (đề bài + `GOLD_LOSS_RED_RATE=0.02`): mất `gold_sentence` **nguyên văn** > 2% ⇒ ĐỎ.
Số đo: **389/797 = 48,81%**. Phân loại chẩn đoán cho thấy:

- **375 item "near"**: nội dung vẫn còn trong index mới (overlap token ≥ 0,60) nhưng **câu chữ
  khác bản cũ** — đúng bản chất re-OCR: cùng trang giấy, engine mới đọc ra chuỗi khác.
- **14 item "absent" (1,76%)**: không chunk nào đạt overlap 0,60 — mất nội dung thật (hoặc câu
  vàng vốn không nằm trong corpus).
- **97 item đã mất neo ngay trên index CŨ (12,17%)**: `gold_sentence` này không khớp cả corpus
  sinh ra nó ⇒ testset vốn đã có neo hỏng, không phải rebuild tạo ra.
- **292 item (36,64%) là regression riêng do rebuild**: trước tìm thấy, sau không còn khớp
  nguyên văn.

Theo quy tắc đăng ký trước, **near/absent chỉ để diễn giải, KHÔNG được dùng để hạ mức đỏ** —
nên kết luận là: **bộ neo `gold_sentence` hiện tại không còn dùng được nguyên trạng trên corpus
mới**. Muốn so sánh round trên corpus mới một cách công bằng, phải **re-anchor** (PA-17) hoặc
chấp nhận so sánh không theo cặp item.

### 3.2. Kết luận được

- 26/26 tệp nguồn có mặt; index mới 342 chunk, **0 rỗng, 0 trùng nguyên văn**; index cũ không
  bị mất nội dung khi build/mở lại.
- Cổng chất lượng theo tệp: **11 tệp được cải thiện** từ "khoảng trống" (cũ 14) xuống còn 3 tệp.
- Ký tự ngoài bảng Việt chỉ còn **19/324.979** (2 loại) — không phải nguồn rủi ro lớn.
- Chữ ký trọng tài **không đổi**; công cụ test không chạm REFEREE_FILES.
- Hàm thuần `plan_index_write` **từ chối** ghi đè thư mục đích đã có dữ liệu (8 test an toàn).

### 3.3. Điều KHÔNG kết luận được (và vì sao)

1. **KHÔNG kết luận corpus mới tốt hơn cho truy xuất/sinh câu trả lời.** Checker chỉ đo dấu,
   vocab proxy, hygiene, neo; chưa chạy round nào trên index mới (PA-1).
2. **KHÔNG kết luận T2 "an toàn để kích hoạt".** Mục 9 ĐỎ + 3 tệp khoảng trống vẫn trong index.
3. **KHÔNG kết luận 20 đoạn ở mục 8 đúng/sai** — script không tự phán; cần người đối chiếu bản
   gốc (`manual_20_segments_new_index.txt`).
4. **KHÔNG kết luận "đã tìm hết ký tự lạ".** 7c là whitelist: nó bắt ký tự ngoài ASCII + chữ
   Việt + dấu câu hợp lệ; nó **không** bắt được chữ Việt hợp lệ nhưng sai dấu (ví dụ "hòa" vs
   "hỏa"). Loại lỗi đó chỉ lộ qua tỉ lệ dấu / neo / người đọc.
5. **KHÔNG kết luận cổng an toàn đang bảo vệ đường build thật.** `plan_index_write` mới là hàm
   thuần để test; `ingest.py` hiện vẫn `reset=True` → `shutil.rmtree(persist_dir)` không hỏi.
   Lần build T2 ngày 24-10 may mắn trỏ vào thư mục mới rỗng nên không mất gì, nhưng lần sau thì
   chưa được bảo vệ → PA-16.
6. **"Không có bộ remap TCVN3/VNI"** được chứng minh bằng **phủ định** (quét tên hàm trong
   `check_corpus`: không có `*tcvn*`, `*vni*`, `*codepage*`, `*legacy*map*`) — đủ để khoá hành vi
   hiện tại, không phải bằng chứng lịch sử rằng repo chưa từng có.

## 4. Tiêu chí xong (đối chiếu đề bài)

| Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|
| Các test xanh | **ĐẠT** | 78/78 (`tmp/pytest_t2_final.txt`: 889 passed toàn repo) |
| Mục 9 không đỏ | **KHÔNG ĐẠT** | 48,81% > 2% (`corpus_check.json:gold_coverage.red=true`) |
| Người dùng duyệt mục 8 (20 đoạn) | **CHỜ DUYỆT** | `manual_20_segments_new_index.txt` |

⇒ **Toàn bộ tiêu chí nghiệm thu T2: CHƯA ĐẠT** (2/3 mục đã có kết quả, 1 mục chờ người).

## 5. Đề xuất cần duyệt

- **PA-16 (mới):** nối `plan_index_write` vào `ingest.py` (từ chối khi đích đã tồn tại, trừ
  `--force`; luôn từ chối index đang dùng) — kèm diff trong PENDING_APPROVAL.
- **PA-17 (mới):** re-anchor `gold_sentence` cho 292 item regression (offline, không đọc lúc
  chạy) trước khi chấm lại round trên corpus mới; nếu không, mọi so sánh theo cặp sẽ vô nghĩa.
- **PA-7 (bổ sung):** thêm tệp thứ ba `TB16 THAY DOI CONG RA VAO KTX.pdf` (0,000 dấu, 328 từ,
  PDF-TEXT không ToUnicode) vào danh sách cân nhắc loại khỏi corpus.
- **PA-1 (giữ nguyên):** kích hoạt index + chấm lại round vẫn chờ duyệt; nay có thêm điều kiện
  tiên quyết là PA-17.

## 6. Phần KHÔNG kiểm chứng trong nhiệm vụ này

- Không build lại index, không ghi đè bất kỳ tệp corpus/index nào (đúng phạm vi test).
- Không kiểm chất lượng 13 tệp re-OCR (đã có ở `docs/reports/T2.md` và `quality_vie.json`).
- Không test mạng/model; không có test `@pytest.mark.slow` trong nhiệm vụ này.
- `_load_index_texts` (đọc ChromaDB thật) chỉ được chạy qua script thật, không có unit test
  (cố ý: unit test không phụ thuộc dữ liệu 342 chunk trên đĩa).
- Chất lượng nội dung 20 đoạn mục 8: cần người đọc — ngoài khả năng của script.

## 7. Lệnh tái lập

```bash
# unit test T2 (78 test, ~0,5 s)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests/test_corpus_rebuild.py -q

# kiểm dữ liệu thật (chỉ đọc; cập nhật JSON + 20 đoạn)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/check_corpus.py

# mutation check (5 đột biến, tự khôi phục)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t2.py

# toàn repo
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
```

Log bằng chứng: `tmp/t2_check_corpus_7c.log`, `tmp/t2_mutation.log`, `tmp/pytest_t2_final.txt`;
JSON: `data/loop/diag/corpus_check/corpus_check.json`; đoạn đối chiếu:
`data/loop/diag/corpus_check/manual_20_segments_new_index.txt`.
