# Báo cáo dọn cấu trúc repo — B0…B7 (26-10-2026)

**Mục tiêu:** đổi cấu trúc repo mà **không đổi một con số đo nào**. **Kết luận: ĐẠT** — 4 cổng
(B4 thêm golden) khớp neo ở mọi bước được giữ, 0 `git revert`, 0 lượt gọi Gemini, không sửa một byte
trong 3 tệp trọng tài hay bất kỳ dụng cụ đo nào.

> Phát hiện ngoài phạm vi bước, **không đổi số đo**: `ARTIFACT_MANIFEST.json` của B3 ghim byte
> container Chroma, mà mỗi lượt pytest mở index thật lại ghi lại 6 tệp ⇒ `--check` đỏ dù nội dung
> truy xuất không đổi (đo ở §5). **Đã xử lý ở C1** (27-10): hai test chỉ đọc bản sao trong `tmp_path`,
> manifest sinh lại đúng một lần; `--check` KHỚP sau pytest (§8).

## 1. Đã làm

| bước | commit | nội dung | cổng |
|---|---|---|---|
| B0 | `90835f5` | Thẻ `research-freeze` tại `471fb66`; `docs/CLEANUP_ANCHORS.md` chốt fingerprint · pytest · r11 · golden | — |
| B1 | `e617123` | Kết luận chữ ký trọng tài băm **byte thô** ⇒ KHÔNG chuẩn hoá EOL 3 tệp; PA-42 | khớp |
| B2 | `caa97d0` | Gốc repo gọn: `prompts/` + `.maestro/` → `dev/`; xoá `SYSTEM_ARCHITECTURE.txt/.docx` (còn trong lịch sử git); cắt bước con chuyển `learn.py`/`benchmark_chunking.py` | khớp |
| B3 | `4e43a95` | `.gitignore` đúng phạm vi B3; `ARTIFACT_MANIFEST.json` 158 tệp / 390.961.924 B; 6 script train/eval từ `models/` sang `tools/train/` (untracked, byte nguyên) | khớp |
| B4 | `789ccf8` | `src/config.py`: 25 biến env của 9 module, 29 site; golden B0 trùng byte; 276/276 ngữ nghĩa parse | khớp + golden |
| B5 | `0db8a5d` | Đề xuất PA-45: **giữ** `evaluation.py`/`analyze_ab.py`/`evaluate_classifier.py` trong `src/` | khớp |
| B6 | `f0e6fcc` | Đề xuất PA-46: tách `generator.py` bị chặn (PA-26 + `env_flag_audit`); việc rẻ nhất = `experiments/negative_results/README.md` | khớp |
| B7 | `adc1248` | `docs/` còn 4 tài liệu trục; 26 tệp báo cáo/nhật ký vào `docs/archive/`; 59 đường dẫn sửa theo vị trí mới | khớp |

"khớp" = đủ 4 mục cổng ở `docs/CLEANUP_ANCHORS.md` §6 (B4 kiểm thêm golden). Chi tiết từng bước:
ghi chú B2…B7 trong `docs/CLEANUP_ANCHORS.md` và Ngã rẽ 37…42 trong `docs/archive/AUTONOMY_LOG.md`.

## 2. Đã cắt — không có bước nào phải `git revert`

- **B2, bước con chuyển `learn.py` + `benchmark_chunking.py` vào `tools/`**: cắt TRƯỚC commit vì
  làm đỏ bất biến #7 — 74 dòng `metadata.file` trong dữ liệu train trỏ đường dẫn cũ. Ghi PA-43.
- **B5**: không chuyển 3 tệp đánh giá ra khỏi `src/` (80 + 3 dòng train trỏ tên tệp; `evaluation.py`
  còn là thư viện được `benchmark_chunking.py`/`demo_streamlit.py` import).
- **B6**: không tách `generator.py`, không dời lever đã bác (PA-26 đóng băng; `env_flag_audit` +
  test đòi mỗi lever có site đọc trong `src/`; evidence còn đụng `pipeline.py`/`run_round.py`).
- **B7**: một lần đếm sai kỳ vọng (24 vs 25 chỗ `docs/reports/` trong DECISION_LOG) bị assert chặn
  TRƯỚC khi ghi — không tệp nào bị ghi dở.

## 3. Chờ duyệt

| mã | việc | trạng thái |
|---|---|---|
| PA-42 | Chữ ký trọng tài băm byte thô: 2 tệp chưa vào kho, 1 tệp đổi byte theo `core.autocrlf` | chờ |
| PA-43 | Chuyển `learn.py` + `benchmark_chunking.py` vào `tools/` | chờ (chặn bởi dữ liệu train) |
| PA-44 | Gom nốt 45 site đọc env còn lại (generator/pipeline/normalizer/router, evaluation, answer_guard, reranker) | chờ |
| PA-45 | Giữ 3 tệp đánh giá trong `src/` | chờ (khuyến nghị giữ) |
| PA-46 | Tách `generator.py` + `experiments/negative_results/README.md` | chờ |
| PA-47 | Manifest ghim byte container Chroma ⇒ `--check` đỏ sau mỗi pytest (phát hiện ở KẾT PHIẾN) | đã áp phần cô lập test + sinh lại manifest (C1); index digest chờ |
| PA-33 | `.gitignore` mở rộng (`tmp/`, cả `models/`, `data/loop/rounds/`, `data/training/`) | chờ |

PA-35…PA-41 của phiên trước vẫn chờ duyệt; `ENABLE_RERANKER` giữ TẮT.

## 4. Bảng neo trước/sau

| mốc | fingerprint | pytest | r11 FAIL/PENDING | r11 gold@6 | golden (41 dòng) |
|---|---|---|---|---|---|
| B0 — trước dọn | `2911c69f740d` | 1495 / 5 skip | 182 / 629 | 0,74 | `0ff9135504e5` |
| sau B1–B7 | `2911c69f740d` | 1495 / 5 skip | 182 / 629 | 0,74 | `0ff9135504e5` |
| sau C1–C5 | `2911c69f740d` | 1495 / 5 skip | 182 / 629 | 0,74 | `0ff9135504e5` |

Bằng chứng lượt chốt:

- pytest `1495 passed, 5 skipped` (lần chốt B7: 89,79 s; lần rà lại sau đó: 91,12 s).
- `referee_fingerprint()` = `2911c69f740d`; chấm lại r11 → `tmp/anchor_r11_rescore_v2_b7.json`:
  811 dòng, FAIL_RETRIEVAL 182, PENDING_GENERATION 629, 0 lệch, item drift 0. So bản B6
  (`tmp/anchor_r11_rescore_v2_b6.json`): chỉ khác `generated_at`.
- Golden B0 chụp lại ở B4: toàn tệp `ccc8a92e…a1bb`; 41 dòng giá trị `0ff913…fe410`.
- Lượt C5 (27-10, sau C1–C4): pytest `1495 passed, 5 skipped`; chấm lại r11 →
  `tmp/anchor_r11_rescore_v2_c5.json`: 811 dòng, 182 / 629, 0 lệch, item drift 0; golden 41 dòng
  `0ff9135504e5`; `ARTIFACT_MANIFEST.json --check` KHỚP — lượt đầu sau nhiều pytest kể từ C1.

Hai máy kiểm số chạy thêm ở B7 (không nằm trong 4 cổng):

| máy kiểm | trước B7 | sau B7 |
|---|---|---|
| `docs_consistency_check.py` | 0 lỗi / 5 cảnh báo / 100 đường dẫn / 263 lệnh | 0 lỗi / 5 cảnh báo / 100 đường dẫn / 263 lệnh |
| `final_number_audit.py` | 63 dòng / 61 KHỚP / 2 LỆCH đã biết / rc=0 | 63 dòng / 61 KHỚP / 2 LỆCH đã biết / rc=0 |

Hai LỆCH là kỳ vọng cũ của chính máy kiểm (46→51 test; chữ ký `9f1179ccab74`→`2911c69f740d`),
đã ghi PA-41; máy kiểm luôn rc=0 nên không chặn cổng.

## 5. Phát hiện ở KẾT PHIẾN: manifest đỏ vì Chroma tự ghi khi mở

`tools/diag/artifact_manifest.py --check` hôm nay báo **ĐỔI 6 tệp** (tổng vẫn 158 tệp /
390.961.924 B): `chroma_db/chroma.sqlite3`, `chroma_db/0bde6463-a057-46ca-aadb-f3e6cdf0fb0c/`
gồm `data_level0.bin` + `length.bin`, và bộ tương ứng của `chroma_db_vie/`. Nguyên nhân: hai test đọc
index thật bằng `chromadb.PersistentClient` (`tests/test_t5_contextual_header.py::_real_chunk_texts`)
làm Chroma ghi lại container mỗi lượt pytest — chạy pytest hai lần liền, cả 6 hash đổi cả hai lần;
mtime cả 6 tệp trùng giây kết thúc pytest.

Kiểm nội dung (script chỉ-đọc `tmp/kf_chroma_query_probe.py`, JSON trước/sau
`tmp/kf_chroma_probe_before.json` và `tmp/kf_chroma_probe_after.json`): n = 361 / 342; sha256 ma trận
embedding xếp theo id = `87f8f4d451f9` / `b688cd89dd05` **trước = sau**; 30 query mỗi DB lấy từ
embedding đã lưu × top-6 ⇒ **0/30 đổi thứ tự id, 0 cặp khoảng cách lệch**. Vậy số đo truy xuất không
đổi; chỉ byte container đổi. B3 `--check` KHỚP tại thời điểm sinh; từ đó mỗi lượt pytest làm nó cũ.
Xử lý đề xuất: PA-47 (ưu tiên thay 6 tệp container bằng "index digest" nội dung); **không** sinh lại
manifest trong KẾT PHIẾN để khỏi ghi đè artifact đã công bố.

**Đã xử lý ở C1 (27-10).** `tests/test_t5_contextual_header.py` thêm fixture `real_index_copy`: hai
test đọc index (`test_chuyen_doi_header_khong_ghi_gi_len_index_that` và
`test_index_that_du_36x_chunk_va_nhan_hop_le`) nay `shutil.copytree` index sang `tmp_path` và chỉ đọc
bản sao; Chroma ghi vào bản sao. Kiểm: hai lượt pytest đầy đủ liền nhau để 6 hash container **không
đổi**; sau đó `--write` một lần — manifest vẫn 158 tệp / 390.961.924 B, chỉ 6 hash container +
`generated_at` đổi; `--check` KHỚP rc=0 sau pytest. Đề xuất phụ "index digest" (băm nội dung
documents + embedding thay cho byte container) **chưa áp** — PA-47.

## 6. Cảnh báo còn lại

- `tools/loop/verify.py`, `src/answer_guard.py`, `src/reranker.py` vẫn **UNTRACKED**: `git revert`
  không khôi phục được; giữ quy ước backup byte `tmp/backup_<bước>.zip` trước khi chạm (PA-42).
- `docs/DECISION_LOG.md` và `docs/bao_cao/` buộc ở lại `docs/` (checker đọc cứng + test đòi ≥20 mục;
  `tools/build_training_data.py:944` glob) — ngoại lệ có chủ đích, ghi ở `docs/README.md`.
- `data/loop/README.md` commit ở B7 gồm cả đính chính PA-25 có sẵn trong cây làm việc; phần đó không
  đổi số đo.
- 6 tệp mã/test có thay đổi chưa commit từ phiên trước (`src/generator.py`, `pipeline.py`,
  `query_normalizer.py`, `router.py`, `tests/test_pipeline.py`, `tests/test_subquery.py` — PA-26)
  **không** bị stage ở bất kỳ bước nào của đợt dọn.
- 8 tệp `tmp/` được ghim trong gói bằng chứng (anchor r11, golden, `compare_r0_repro.json`,
  `probe_r12_fold.json`, `final_number_audit*.json`) **không** vào git: máy khác chạy `--check` sẽ
  báo THIẾU — đó là hành vi đúng của gói, ghi ở `docs/EVIDENCE_PACK.md` §6.
- `docs/PA_TRIAGE.md` là **khuyến nghị**, không áp PA nào; `ENABLE_RERANKER` vẫn TẮT.

## 7. Hình dạng repo sau dọn

- `docs/`: `README.md`, `ARCHITECTURE.md`, `EXPERIMENTS.md` (một bảng 25 dòng), `REPRODUCE.md`,
  `CLEANUP_ANCHORS.md`, `CLEANUP_REPORT.md`, `PA_TRIAGE.md`, `EVIDENCE_PACK.md` +
  `evidence_pack.json`, `DECISION_LOG.md`, `bao_cao/`, `giang_day/`, và `archive/` (4 nhật ký
  phiên + `reports/` 22 tệp + README bản đồ lưu trữ).
- Gốc repo: chỉ còn tệp chạy và thư mục nguồn; tài liệu quy trình ở `dev/`; artifact lớn ở `models/`,
  `chroma_db*/`, `data/`.

## 8. Đợt C sau KẾT PHIẾN (27-10) — C1…C5

| bước | commit | nội dung | cổng |
|---|---|---|---|
| C1 | `b421f44` | Cô lập 2 test đọc index thật bằng fixture `real_index_copy` (sao chép sang `tmp_path`); sinh lại `ARTIFACT_MANIFEST.json` đúng một lần; cập nhật PA-47 | khớp, manifest `--check` KHỚP sau pytest |
| C2 | `fc45fa0` | `docs/PA_TRIAGE.md`: 47 PA, nhóm (a) 26 / (b) 17 / (c) 4, khuyến nghị duyệt/đóng/hoãn; không áp PA nào | khớp |
| C3 | `1a98996` | `docs/EVIDENCE_PACK.md` + `docs/evidence_pack.json` (25 D-row → 84 tệp, sha256 byte thô) + `tools/diag/evidence_pack_check.py` | khớp, evidence `--check` KHỚP |
| C4 | `70206df` | `docs/ARCHITECTURE.md` thêm "Hạn chế đã biết": mã đánh giá trong `src/`, `generator.py` 1.377 dòng, lever âm sau cờ TẮT — kèm lý do không sửa | khớp |
| C5 | báo cáo này | Chốt: 4 cổng §6, hai máy kiểm, `git status` chỉ còn tệp đã giải thích | khớp |

Lượt chốt C5: pytest `1495 passed, 5 skipped`; chữ ký `2911c69f740d`; r11 182 / 629, 0 lệch;
golden `0ff9135504e5`; `artifact_manifest --check` KHỚP; `evidence_pack_check --check` KHỚP;
`docs_consistency_check` 0 lỗi / 5 cảnh báo / 100 đường dẫn / 263 lệnh; `final_number_audit`
63 dòng / 61 KHỚP / 2 LỆCH đã biết / rc=0.
