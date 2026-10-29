# STATE.md — trạng thái phiên 29-10-2026 (cập nhật 21:47 +07 — KẾT PHIÊN ở cuối tệp)

Nhánh: `chore/restructure` · HEAD khi mở phiên: `d843888` · HEAD khi kết phiên: `eff0c6a` · 0 lời gọi Gemini.

## Đã xong trong phiên

- **PA-48 DUYỆT và ĐÃ ÁP** (`ed0fc74` + tài liệu `00bbd93`): `tools/diag/artifact_manifest.py` nối
  scope `indexes/experimental/chroma_db*` và `.cache/ocr/*`; re-anchor manifest; **đối chiếu 36/36
  hash cũ↔mới khớp byte TRƯỚC khi ghi** (`tmp/restructure/pa48_crosscheck.py`); thêm 2 test ghim
  `PROTECTED_INDEX_DIRS` bản đường dẫn mới kèm đột biến điều khiển
  (`tests/test_t5_contextual_header.py`). `ARTIFACT_MANIFEST --check` **KHỚP**; hệ quả đã ghi:
  `evidence_pack` phải ghim lại 1 dòng, tổng 4.041.502 → **4.041.992 byte**.
- **ĐÓNG PA-54 và PA-55** (`docs/PA_TRIAGE.md`, `docs/RESTRUCTURE_MAP.md` §6.5) — không đụng
  `generator.py`, `answer_guard.py`, `text_utils.py`, `verify.py`; chữ ký trọng tài
  `2911c69f740d` không đổi.
- **Preflight (a–f) trên cây đã đóng gói**: SẠCH (`tmp/r21c_20261029/preflight_check_1.json`) —
  0 tệp sửa chưa commit, 0 tệp mới trong vùng neo, corpus 29 tệp khớp HEAD, vùng neo vẫn **33 tệp**
  cùng tập tên với r21b, **19 tệp đổi đường dẫn** theo `docs/RESTRUCTURE_MAP.md` mục 6.2.

## Đang chạy — ĐÃ ĐÓNG (xem mục KẾT PHIÊN ở cuối tệp)

- **r21c** = bản sao lặp r21b **trên cây đã đóng gói**, đúng 300 id đóng băng, luật quyết định giữ
  nguyên văn bản đã đăng ký. Đăng ký: `data/loop/README.md` mục `## r21c — ĐĂNG KÝ` (commit
  `d843888`, viết TRƯỚC khi chạy). Controller `tmp/r21c_controller_20261029.py` khởi động nhánh A
  lúc **04:12**, hạn chót cứng **22:00**; trong lúc chạy chỉ ghi `tmp/r21c_20261029/` và
  `data/loop/rounds/r21c_A|B`.

## Cắt theo giờ (mục 5 của lệnh 29-10)

- 04:12 < 17:30 ⇒ cửa sớm: **một round paired rồi tới round kế tiếp**.
- **r21b KHÔNG chạy lại**: đã COMPLETE ngày 28-10 và đã công bố "KHÔNG XÁC NHẬN"
  (`tmp/r21b_report.md`, `data/loop/rounds/r21b_A|B`); controller r21b từ chối chạy lại và quy ước
  cấm ghi đè artifact đã công bố. Yêu cầu "cây chạy thí nghiệm = cây hiện tại" được đáp ứng bằng
  round **mới r21c** dùng cùng mẫu/cùng luật; bốn tệp artifact r21b được ghim sha trong
  `prelaunch_lock.json` và đối chiếu mỗi nhịp `check_lock` để chứng minh không bị chạm.
- **r22**: không tồn tại ở bất kỳ đâu (không mục đăng ký, không luật) ⇒ **không chạy**. Nếu còn cửa
  sổ sau khi r21c xong, bước kế tiếp sẽ được đăng ký thành mục riêng **trước** khi chạy.

## Treo có chủ đích (làm SAU khi thí nghiệm xong, theo mục 3 của lệnh)

- `docs/PA_TRIAGE.md`: chốt bảng đếm (50 hàng; **(a) 26 · (b) 19 · (c) 5** đã kiểm bằng máy;
  hàng "đã đóng" thực tế **14** = 11 cũ + PA-48 + PA-54 + PA-55 — con số 12 trong lệnh là tính ở thời
  điểm chưa có PA-48/54/55, sẽ ghi rõ trong báo cáo thay vì sửa số cho khớp).
- `docs/README.md`: dải PA-1…PA-55, D-01…D-<số hiện có>, thêm dòng trỏ `RESTRUCTURE_MAP.md`.
- Dọn `tmp/restructure/` — chỉ sau khi user nghiệm thu (giữ các tệp bằng chứng đã liệt kê trong
  `docs/RESTRUCTURE_MAP.md`).

## KẾT PHIÊN 29-10 (21:47 +07) — S0→S5 xong, chờ người dùng quyết

Tổng kết đầy đủ, số nguyên văn từ artifact: `tmp/overnight_summary.md` (12.152 ký tự, sinh bởi
`tmp/next_summary4_20261029.py`). Dưới đây chỉ là quyết định trạng thái.

### Ba round trong phiên (luật đã đăng ký trước, không chỉnh sau khi thấy số)

- **r21c** (bản sao lặp r21b trên cây đã đóng gói, 04:12→06:09): Δ **+25**, McNemar p=0,000247,
  PASS_CORRECT 31→56, nhưng FAIL_FABRICATED 4→10 ⇒ **KHÔNG XÁC NHẬN** theo luật r21/r21b;
  mục đích **dụng cụ ĐẠT** (gold-in-top-6 205=205, không drift, chữ ký `2911c69f740d` trước=sau).
- **r23** (dense nguyên văn × answer_guard, mẫu MỚI 300 id, 06:13→08:11): Δ **+21**, p=0,0046013,
  FF 1/A vs 1/B, HALL 0/0, CI cụm [0,0033; 0,16] ⇒ **XÁC NHẬN** (cả 4 điều kiện true). Mẫu rời:
  0 id giao với r21b/r21c ⇒ không gộp. Hậu kiểm: X1 5 ca refusal→trả lời nằm ngoài veto; X2 bỏ cụm
  lớn nhất (46 id) thì CI chứa 0 ⇒ nhãn ĐẠT không bền với riêng cụm đó (ghi nguyên, không đổi luật).
- **r22** (`ENABLE_RERANKER` trên nền r17-T, retrieval-only 811 item, xong 16:37): gold@6 **581→612**
  (+31, 38/7, p=**3,12e−06**, CI [0,0186;0,0771]) nhưng veto neo HUMAN kích hoạt **77→72 (−6,49%)**
  ⇒ artifact tự phán **BỊ BÁC VETO HUMAN**; theo từ điển EXPERIMENTS = **KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ**
  (không phải BÁC). ctrl tái lập r17-T đúng từng item (0 mismatch). Chốt chặn lever: 807/811 top-6 đổi.

### Cổng + hậu kiểm

- Cổng sau cả 3 round: referee `2911c69f740d` ĐẠT, pytest **1551 passed / 5 skipped**, manifest
  `--check` **KHỚP 158 tệp / 390.961.924 B**, evidence `--check` **KHỚP 84 tệp / 4.041.992 B**
  (manifest chỉ `--check`, KHÔNG lần nào sinh lại trong phiên).
- Y1–Y4 (đơn vị veto HUMAN): đăng ký = **câu hỏi duy nhất**; tính lại 97 item = 97 câu hỏi độc nhất
  ⇒ hai đơn vị TRÙNG (77/72, −6,49%, ĐỎ) ⇒ **không phải thêm mục "phán quyết theo item"** vào
  `tmp/r22_report.md` (giữ nguyên tệp). 11 item đổi verdict: 8 rơi / 3 lấy; trùng 4 id với 11 cặp
  D-37 (recompute 79/97→74/97): HQ23, HQ36, HQ40, HQ58 (đều rơi ở cả hai round).

### S5 tài liệu (ĐÃ COMMIT `eb6e3bb`; pack ghim riêng `d76dc0b`)

- `docs/EXPERIMENTS.md`: 3 dòng mới (A2 `r22`, A4 `r23`, Bảng B `r21c`) + viết lại dòng D-37 và mục
  "Hai mục cần đo lại".
- `docs/README.md`: "Một bảng"→"Hai bảng"; dải PA `PA-1…PA-48 + PA-54…PA-55`; thêm dòng
  `RESTRUCTURE_MAP.md`.
- `docs/evidence_pack.json` + `docs/EVIDENCE_PACK.md` ghim lại bằng `--write` (84 tệp / 4.041.992 B).
- Máy kiểm: `docs_consistency_check` **SẠCH LỖI** (5 cảnh báo cũ, 42 mục sổ, 114 đường dẫn);
  `final_number_audit.py` (venv) **2 LỆCH** = hai kỳ vọng cũ của chính máy kiểm ("100 đường dẫn"
  so với thực tế 114; chữ ký `9f1179ccab74` so với `2911c69f740d`), rc luôn 0 ⇒ ghi nguyên, không
  sửa số lịch sử để làm xanh.
- **Đã được người dùng cho phép commit và ĐÃ COMMIT**, tách làm hai (yêu cầu tách `evidence_pack.json`
  ra riêng): `eb6e3bb` = EXPERIMENTS + README (+11 −5), `d76dc0b` = `docs/evidence_pack.json`
  (+1 −1, chỉ `generated_at`); HEAD cũ `eff0c6a`, artifact nặng vẫn KHÔNG commit. Hai commit gộp
  trước đó (`ab8030f`, `e7f09fd`) đã được viết lại bằng `git reset --soft` nên không còn trên nhánh
  (chưa từng push); cây cuối trùng khớp cây cũ ở mọi tệp `docs/`, chỉ `STATE.md` khác vì đã cập nhật
  chỗ dẫn hash. Lưu ý: `backup_final_*` chụp cây làm việc
  TRƯỚC commit nên manifest của zip ghi `tree_head = eff0c6a`, nhưng byte các tệp trùng khớp bản
  đã commit (không có nội dung nào chỉ tồn tại trong commit).

### Dọn lịch sử git sau khi tách commit (29-10, HEAD `da152d5`)

- Tách bản gộp `ab8030f` (3 tệp docs) + `e7f09fd` (STATE.md) thành `eb6e3bb` (EXPERIMENTS+README),
  `d76dc0b` (evidence_pack riêng), `5723792` (STATE.md) và `da152d5` (đính chính câu "trùng khớp
  cây"). Dùng `git reset --soft eff0c6a` rồi commit lại; `git diff e7f09fd HEAD -- docs/` **rỗng**
  ⇒ nội dung docs không đổi một byte, chỉ STATE.md khác vì cập nhật chỗ dẫn hash.
- Xóa dấu vết hai commit cũ ở **cả hai tầng reflog** (3 mục `HEAD`, 3 mục
  `chore/restructure` — bản ghi của nhánh là tệp riêng, không phải HEAD) và xóa pseudo-ref
  `ORIG_HEAD` (còn trỏ `e7f09fd` sau `reset --soft`, nếu để lại thì commit vẫn reachable).
- `git gc --prune=now`: 2.279 → **1.687 object**, 2 → **1 pack**, `size-pack` 82,14 → **76,24 MiB**
  (`.git` 85M → 78M); `git fsck --unreachable` còn **0**, `git fsck --strict` sạch.
  `git cat-file -e ab8030f` / `e7f09fd` đều **ĐÃ XÓA**.
- Tác dụng phụ đã được người dùng cho phép trước khi chạy: prune kèm 8 commit `cline checkpoint`
  (10–18/10) và các blob/tree treo (588 object ở lượt 1, 4 object ở lượt 2) ⇒ không khôi phục được;
  lịch sử đang dùng (từ `eff0c6a` về trước) nguyên vẹn.

### Sao lưu (ngoài repo)

- `backup_r22_20261029T164007.zip` — 81.565.018 B, sha256 `47274c3c…7e5f3c`, CRC OK.
- `backup_final_20261029T214551.zip` — 9.992.710 B, sha256 `a675ed34…645bdf40`, CRC OK, 142 mục
  (141 tệp mới + manifest), chứa toàn bộ bằng chứng r21c/r23/r22 + `tmp/overnight_summary.md`.
- `backup_generation_20261029T214712.zip` — 2.235 B, sha256 `b989efa9…dcc4d718`, CRC OK: bù tệp
  `tmp/generation_summary_table.md` (X3) vì tiền tố `generation` không nằm trong `FINAL_PREFIXES`
  của dụng cụ sao lưu nên bản `final` bỏ sót; `STATE.md` (chưa được git theo dõi, ở gốc repo) nằm
  ngoài phạm vi mọi zip — nội dung quyết định đã có bản tương đương trong `tmp/overnight_summary.md`.
- **BẤT THƯỜNG CẦN NGƯỜI DÙNG BIẾT:** hai zip của chain3 — `backup_r21c_20261029T061258.zip`
  (sha `dc37a6ab…c473bbe7`) và `backup_r23_20261029T081402.zip` (sha `a27855e0…1263f4e89`) — đã
  biến mất khỏi `D:/backup_thesis_20261029/` cùng phần đầu của `SHA256.txt` và `seen_sha256.json`
  **trước 16:40** (bằng chứng: backup r22 lúc 16:40 ghi "bỏ qua vì đã có trong backup trước **0**").
  Phiên này không xóa gì; dữ liệu không mất vì toàn bộ nội dung đã nằm trong `backup_final_*`;
  KHÔNG tự dựng lại hai zip đó (tình huống ngoài lệnh ⇒ ghi hiện trạng, chờ người dùng quyết).

### Quyết định cờ (không tự bật)

- `ENABLE_DENSE_ORIGINAL_QUERY`: **TẮT** — r23 xác nhận nhưng r21b/r21c không; bật là đổi mặc định.
- `ENABLE_RERANKER`: **TẮT** — veto HUMAN của r22; nới ngưỡng veto là việc của người dùng.

### Sai lệch / giới hạn đã ghi, không tự sửa

- `docs/DECISION_LOG.md` dòng D-37 vẫn mang nhãn **CHỜ ĐO LẠI** trong khi EXPERIMENTS đã có số r22
  (sửa là đổi dòng D- đang bị evidence pack ghim — ngoài phạm vi S5).
- `tmp/next_chain4_status.json` báo **CRASHED** dù cả 3 bước rc=0: dòng cuối là `SystemExit: 0` của
  driver ⇒ cờ giả, giữ nguyên artifact theo luật.
- `tmp/x123_after_r22_20261029.py` ném `NameError: X3d` ở lệnh in cuối, **sau khi** đã ghi đủ 4 tệp;
  đã sửa lỗi chính tả trong script nhưng KHÔNG chạy lại (script từ chối ghi đè đầu ra cũ).

### Việc chờ người dùng

1. ~~Commit 3 tệp tài liệu S5~~ — **đã làm**, tách hai commit: `eb6e3bb` (EXPERIMENTS+README) và
   `d76dc0b` (evidence_pack).
2. Quyết hai cờ lever ở trên; quyết ngưỡng veto r22 (nới hay giữ).
3. Sửa hay giữ nhãn D-37 trong `DECISION_LOG.md`.
4. Dọn `tmp/` sau nghiệm thu (giữ `tmp/r21c_20261029/`, `tmp/r23_20261029/`, `tmp/r22_*`,
   `tmp/overnight_summary.md`, `tmp/gates*`); có dựng lại 2 zip chain3 đã mất hay không.
5. Duyệt hàng PA có khuyến nghị "duyệt" (12 hàng, xem `tmp/overnight_summary.md` mục cuối).

## PHIÊN TIẾP 29-10 (22:5x–23:0x) — 5 việc duyệt theo thứ tự, ĐÃ ĐÓNG BĂNG repo

Lệnh: "Duyệt theo thứ tự, tự trị, không hỏi, không tạo PA mới, 0 Gemini, không chạy round, không
đụng trọng tài/gate/generator, không dọn tmp/". HEAD cuối phiên **`0fe9caf`** (nhánh
`chore/restructure`); 0 lời gọi Gemini; 0 round chạy; `src/` không đổi byte.

### 1) Vá `docs/DECISION_LOG.md` D-37 — commit `6872c1a`

Cột Trạng thái nay là **BỊ BÁC VETO HUMAN** (r22, 29-10) kèm câu chặn đọc nhầm: nhãn khoa học ở
EXPERIMENTS là **KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ**, *không phải BÁC khoa học* (Δ dương, CI loại 0).
Số đã đối chiếu lại với `tmp/r22_y_check_20261029.md` (không chép suông từ lệnh): gold@6
581→612 (+31, p=3,12e-06) trên nền r17-T; neo HUMAN 77→72 (−6,49%, ngưỡng −5%); 4/8 mục rơi
(HQ23, HQ36, HQ40, HQ58) trùng D-37; McNemar 3/8 p=0,227; cờ TẮT. Cột artifact đã trỏ
`tmp/r22_reranker_20261029.json`, `tmp/r22_report.md`, `tmp/r22_y_check_20261029.md`; câu "CHỜ ĐO
LẠI" đã bỏ khỏi cột Đo lường. `docs/EXPERIMENTS.md` **không lệch** nên không sửa. Không đổi số khác.
*Lỗi chính tả trong chính commit message*: "neo HUMAN" bị gõ thành "neoo HUMAN" — không amend
(luật: không amend commit đã tạo), ghi ở đây để tra cứu.

### 2) PA-31 — bản REDACTED, commit `c346be6`

Dụng cụ mới `tools/diag/redact_pii.py` (nhập `secret_scan.PATTERNS`, **không sửa** máy quét đã
công bố) ghi bản che sang `data/loop/diag_redacted/`. **Tệp gốc không đổi một byte.**

| | trước | sau |
|---|---:|---:|
| dòng có PII (khuôn công bố) | **60** | **0** |
| lần khớp (khuôn công bố) | **89** (65 SĐT + 24 email) | **0** |
| SĐT dạng nhóm (lớp rộng bổ sung) | **120** | **0** |
| tổng số dòng | 49.896 | 49.896 |
| tổng byte | 4.054.151 | 4.053.785 |
| JSON/JSONL parse được | — | 5/5 tệp |

Chốt chống dương tính giả (đã sửa 1 lỗi của chính phiên này): khuôn rộng ban đầu cắt chuỗi số dài
và số thực thành "số điện thoại" (116 ca giả ở `answerability_probe_r11_retrieval.json`) ⇒ nay ứng
viên phải **trọn** 10 chữ số (đầu 03/05/07/08/09) hoặc 11 chữ số (đầu 02). Soát hồi quy: **312**
chuỗi số ≥12 chữ số trong 8 tệp **còn nguyên**, 0 bị cắt. Cổng trong `REDACTION_REPORT.json`:
`lines_kept`/`json_valid`/`pii_zero_after` = true.

**ĐÍNH CHÍNH tiền đề PA-31** (ghi trong `data/loop/diag_redacted/README.md`): hồ sơ 25-10 nói 8 tệp
"untracked, chưa từng rời máy"; trên cây 29-10 **cả 8 đều đã được git theo dõi** ⇒ PII **đã** nằm
trong lịch sử git từ trước. Bản redacted có giá trị chia sẻ/nộp, **không** phải biện pháp xoá lịch sử.

### 3) PA-33 — `.gitignore`, commit `5541039`

Đo trước/sau bằng `git ls-files --others --exclude-standard`: **2.655 đường dẫn / 406,6 MiB** →
**52 đường dẫn / 20,56 MiB**, không tệp đơn lẻ nào > 2 MiB. Artifact **không bị xoá**, vẫn trên đĩa
và vẫn do `ARTIFACT_MANIFEST` ghim sha256. Sau các commit của phiên, `git add --dry-run -A` còn
**10 mục** — toàn bộ là tệp chẩn đoán đã biết còn PII (danh sách trong test pin).

### 4) PA-8 — commit phần nhẹ, 4 nhóm

`6872c1a` docs D-37 · `5541039` .gitignore · `c346be6` tool + bản redacted (11 tệp, 3,9 MB) ·
`629f89f` 31 tệp bằng chứng chẩn đoán (1,4 MB, 55.045 dòng). **KHÔNG** commit `data/loop/rounds*`,
`chroma_db*`, `tmp/`, `models/`, `data/training/`. Loại khỏi commit vì còn PII: 3 tệp
`answerability_labelset_*` (15,9 MB / 456 khớp), `corpus_check/*`, `b1_cprime/{a,c}_prime/rows.jsonl`,
`b3_smoke/sm16/retrieval.jsonl`; loại vì lộ đường dẫn `C:\Users\<tên>`: `t4_adapter_probe.json`.

### 5) Cấu hình khuyến nghị — commit `fa44bbc` + `0fe9caf`

`docs/REPRODUCE.md` mục "Cấu hình khuyến nghị (r23, 29-10)" + khối cuối `.env.example`:
**`ENABLE_DENSE_ORIGINAL_QUERY=1` và `ENABLE_ANSWER_GUARD=1`**, `ENABLE_RERANKER` **giữ TẮT**
(r22 veto HUMAN). **Mặc định mã không đổi** (vẫn `"0"`).

**SAI LỆCH CÓ CHỦ ĐÍCH so với câu chữ lệnh:** lệnh nói "ghi vào `.env.example`"; bản đầu ghi dạng
`TEN_CO=1` đang bật, và **2 test đỏ** vì `tools/diag/env_flag_audit.py` xếp một cờ khai báo BẬT
trong tệp mẫu là `LOI_KHAI_BAO` (chép `.env.example` thành `.env` = bật ngầm). Nay khuyến nghị nằm ở
dạng **dòng chú thích** (`# ENABLE_DENSE_ORIGINAL_QUERY=1`) kèm chỉ dẫn bỏ `#`; mặc định và luật
kiểm toán giữ nguyên; `pytest` xanh. Nếu người dùng muốn tệp mẫu bật thật thì phải sửa luật
`env_flag_audit` + test pin — việc đó ngoài phạm vi phiên này.

**Đã sửa 1 test pin** (`tests/test_final_secret_scan.py`, đổi tên
`..._chua_loai_tru_...` → `..._da_loai_tru_...`): chính docstring của nó ghi "RED nếu ai đó thêm
ignore rule đúng cách (PA-30 áp dụng) — khi đó cập nhật kỳ vọng có chủ đích". Bất biến mới: `git add
--dry-run -A` ≤ 50 mục, KHÔNG có `tmp`/`models`, mọi tệp còn lại ≤ 2 MiB.

### Cổng cuối (đo SAU khi commit, trước khi đóng băng)

| cổng | kết quả |
|---|---|
| `referee_fingerprint()` | **`2911c69f740d`** (không đổi) |
| `pytest tests -q` | **1551 passed / 5 skipped** (103 s) |
| `artifact_manifest.py --check` | **KHỚP** — 158 tệp / 390.961.924 B (chỉ `--check`, không sinh lại) |
| `evidence_pack_check.py --check` | **KHỚP** — 84 tệp / 4.041.992 B, 25 D-row, 9 neo |
| `docs_consistency_check.py` | **SẠCH LỖI**, 5 cảnh báo cũ, 42 mục sổ, 114 đường dẫn |

### Sao lưu (ngoài repo, mode "x", không ghi đè)

- `D:/backup_thesis_20261029/backup_final_20261029T230504.zip` — **906.286 B**,
  sha256 `bb17081e…7364e695f`, CRC OK, 51 tệp + manifest, `tree_head = 0fe9caf`.
  Đã đối chiếu 6 tệp trọng yếu trong zip ↔ đĩa: **6/6 khớp sha**.
- `C:/backup_thesis_20261029_secondary/backup_final_20261029T230507.zip` — **92.399.462 B**,
  sha256 `60474c7f…9600e89ccb`, CRC OK, 583 tệp + manifest (lần đầu ở đích này nên ghi đủ phạm vi).
- Dụng cụ dùng: `tmp/next_backup_20261029_c.py` = **bản sao có `--dest`** của
  `tmp/next_backup_20261029.py` (giữ nguyên luật; tệp gốc không sửa vì đã sinh các zip đã công bố).
- **Lưu ý sổ `seen_sha256.json` ở D:**: sau khi xoá 2 zip cũ theo yêu cầu (`backup_r22_*`,
  `backup_final_*T214551`), sổ vẫn coi nội dung của chúng là "đã có trong backup trước" ⇒ lượt này
  chỉ ghi 51 tệp mới. Không mất dữ liệu: toàn bộ nội dung đó nằm trong `backup_full_*` (777 MB).
  Hiện `D:` còn 4 tệp: `SHA256.txt`, `seen_sha256.json`, `backup_full_*`, `backup_generation_*`,
  và zip mới ở trên.

### Trạng thái kết thúc: ĐÓNG BĂNG

Không còn việc nào được lệnh yêu cầu. Repo dừng ở `0fe9caf`; 10 tệp còn PII **giữ nguyên untracked**
theo PA-8. Hai việc chờ người dùng quyết (không tự làm): (a) có muốn `.env.example` bật thật 2 cờ
khuyến nghị (phải sửa luật `env_flag_audit` + test pin); (b) có viết lại lịch sử git để xoá PII của
8 tệp PA-31 (đổi hash mọi commit từ đó về sau).
