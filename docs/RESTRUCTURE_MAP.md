# RESTRUCTURE_MAP — tái cấu trúc thư mục `hybrid_rag_agu`

> Nhiệm vụ: **chỉ di chuyển file, KHÔNG đổi hành vi**. Quy tắc vàng đã áp dụng suốt
> Phase 1: được phép (1) di chuyển file và (2) sửa chuỗi đường dẫn/import trỏ tới file
> đã chuyển; cấm sửa logic, định dạng lại, xóa dữ liệu. Một move đòi hỏi đổi logic hoặc
> sửa dữ liệu đã công bố thì **hoãn và báo cáo** (mục 4).
>
> Ngày thực hiện: 28-10 → sáng 29-10-2026 · Nhánh: `chore/restructure`
> · Commit Phase 1: `4b981b0` · Báo cáo: `35f4c53` · Phase 2 cache: `a085716`
> · Phase 2b indexes: `83b3bc3` · Snapshot baseline: `24e5c9a` (trạng thái
> `auto/overnight` tại `c8c2408`).

---

## 1. Kết quả cổng nghiệm thu (baseline → sau Phase 1)

| Cổng | Lệnh | Baseline (`24e5c9a`) | Sau Phase 1 (`4b981b0`) | Kết luận |
|---|---|---|---|---|
| pytest | `python -m pytest tests -q` | 1549 passed / 5 skipped | **1549 passed / 5 skipped** | ĐẠT — bằng từng con số |
| Manifest artifact | `tools/diag/artifact_manifest.py --check` | rc=1, ĐỔI (3): `chroma_db/0bde6463…/data_level0.bin`, `…/length.bin`, `chroma.sqlite3` | rc=1, **ĐỔI (3) đúng 3 mục cũ** | ĐẠT — drift chroma có trước, không do tái cấu trúc |
| Gói bằng chứng | `tools/diag/evidence_pack_check.py --check` | rc=0, KHỚP (84 tệp / 4.041.502 B) | rc=0, **KHỚP** | ĐẠT |
| Vùng bảo vệ (tự chụp) | `tmp/restructure/protected_hash_check.py` | 491 tệp (data 468 + outputs 22 + manifest 1) | **ĐỔI 0 / MẤT 0** | ĐẠT — không byte artifact nào lay động |
| Chuỗi P5 DryRun | `tools/loop/run_chain.py --chain tools/loop/chains/t5a_reranker.json --dry-run` | rc=0, 14 dòng | rc=0, **diff = 0 dòng** | ĐẠT — lệnh/env/argv giống hệt |
| Không xóa file | `git diff --name-only --diff-filter=D` | — | **rỗng** (chỉ 13 rename) | ĐẠT |
| Đồng nhất tài liệu | `tools/diag/docs_consistency_check.py` | SẠCH LỖI | **SẠCH LỖI** (110 đường dẫn, 5 cảnh báo cũ) | ĐẠT |
| Chữ ký trọng tài | `REFEREE_FILES` = verify.py + src/answer_guard.py + src/text_utils.py | `2911c69f740d` | **cả 3 tệp không bị chạm** ⇒ chữ ký giữ nguyên | ĐẠT |

Ghi chú vận hành (đã kiểm buổi tối 28-10): chạy pytest toàn repo bằng `python -m pytest`
KHÔNG kèm đường dẫn sẽ quét cả `tmp/t3_baseline_head/tests/` (bản sao snapshot) và dừng
ở 152 lỗi collection; lệnh chuẩn của cổng là `python -m pytest tests -q`.

## 2. Bảng ánh xạ 13 move (Phase 1 — đã commit)

Tất cả 13 move đều `git mv`, không file nào bị xóa. Cột "sửa tham chiếu" liệt kê nơi
chuỗi đường dẫn/import trỏ tới tệp đó đã được cập nhật.

| # | Cũ | Mới | Sửa tham chiếu |
|---|---|---|---|
| 1 | `learn.py` | `scripts/learn.py` | `ui/app.py` (import → `scripts.learn`), `tools/diag/env_flag_audit.py` (SCAN_FILES), `main.py` + `ingest.py` (chuỗi hint lệnh), `tools/train/build_training_data.py` (2 danh sách tệp nguồn), docstring `scripts/learn.py` (bootstrap `sys.path` + import `ingest`), README, docs |
| 2 | `benchmark_chunking.py` | `scripts/benchmark_chunking.py` | bootstrap `sys.path`, `tools/train/build_training_data.py`, README, `logs/` mô tả trong docs đang hoạt động |
| 3 | `export_architecture.py` | `scripts/export_architecture.py` | đường dẫn `docs/architecture/SYSTEM_ARCHITECTURE.{md,txt,docx}` trong script, README |
| 4 | `demo_streamlit.py` | `ui/demo_streamlit.py` | `tests/test_demo_streamlit_display.py` (import package `ui`), `env_flag_audit.py`, `build_training_data.py`, README |
| 5 | `SYSTEM_ARCHITECTURE.md` | `docs/architecture/SYSTEM_ARCHITECTURE.md` | `scripts/export_architecture.py`, `src/generator.py` docstring, `docs/ARCHITECTURE.md`, README, docs/REPRODUCE, giáo trình, 104 citation `metadata.file` |
| 6 | `TAXONOMY.md` | `docs/spec/TAXONOMY.md` | `src/classifier.py` (6 docstring/comment), `docs_consistency_check.py` (CHECK_EXACT), docs, 16 citation |
| 7 | `ROADMAP.md` | `docs/planning/ROADMAP.md` | `docs_consistency_check.py` (DOC_FILES + CHECK_EXACT), `tests/test_t7_docs_consistency.py` (fixture cây giả), docs/README link tương đối, 36 citation |
| 8 | `NORMALIZATION_ACTIVE_LEARNING.md` | `docs/guides/NORMALIZATION_ACTIVE_LEARNING.md` | README, docs/giang_day |
| 9 | `TROUBLESHOOTING_GUI.md` | `docs/guides/TROUBLESHOOTING_GUI.md` | README, docs/giang_day, 8 citation |
| 10 | `LAYOUT_OPTIMIZATION.md` | `docs/guides/LAYOUT_OPTIMIZATION.md` | README |
| 11 | `tools/build_sft_from_round.py` | `tools/train/build_sft_from_round.py` | `ROOT = parents[3]`, field `"tool"` trong manifest sinh ra, `tests/test_build_sft_from_round.py`, `tests/test_t4_sft_invariants.py`, `tools/diag/qlora_memory_probe.py` (comment), docs |
| 12 | `tools/build_training_data.py` | `tools/train/build_training_data.py` | `ROOT = parents[3]`, `tools/loop/testset.py` L54 + `tools/diag/ablation_c_prime.py` L67 + `ablation_generation.py` L102 (đường dẫn importlib), `tests/test_ablation_generation.py`, docs |
| 13 | `tools/validate_training_data.py` | `tools/train/validate_training_data.py` | `ROOT = parents[3]`, docs |

5 README mới (3–5 dòng định vị thư mục): `scripts/README.md`, `docs/architecture/README.md`,
`docs/spec/README.md`, `docs/planning/README.md`, `docs/guides/README.md`.

## 3. Sửa citation trong bộ dữ liệu train đã công bố (quyết định có duyệt)

Sự thật phát hiện khi chạy cổng: `data/training/*.jsonl` (bộ train sinh 23-10 bởi
`build_training_data.py`) ghi `metadata.file` bằng **đường dẫn gốc cũ** của 7 tệp đã
chuyển → `tools/diag/train_data_audit.py` (dụng cụ đo, KHÔNG sửa) báo `file_thieu` ~496
dòng ⇒ pytest đỏ đúng 1 test (`test_final_train_data_audit.py::…code_qa`).

Lựa chọn đã trình người dùng 28-10 và được duyệt: **cập nhật citation, giữ 13 move**
(vì đây đúng phạm vi (2) "sửa chuỗi đường dẫn trỏ tới file đã chuyển"; số dòng giữ
nguyên nên mọi neo dòng/`co_trich_file=1049`/`dinh_danh_kiem_tra=890` không đổi;
`models/`+`outputs/` pin riêng, không liên quan).

| `metadata.file` cũ | Mới | Số citation |
|---|---|---|
| `demo_streamlit.py` | `ui/demo_streamlit.py` | 180 |
| `benchmark_chunking.py` | `scripts/benchmark_chunking.py` | 148 |
| `SYSTEM_ARCHITECTURE.md` | `docs/architecture/SYSTEM_ARCHITECTURE.md` | 104 |
| `ROADMAP.md` | `docs/planning/ROADMAP.md` | 36 |
| `TAXONOMY.md` | `docs/spec/TAXONOMY.md` | 16 |
| `TROUBLESHOOTING_GUI.md` | `docs/guides/TROUBLESHOOTING_GUI.md` | 8 |
| `learn.py` | `scripts/learn.py` | 4 |
| **Tổng** | | **496** (sft_train 162 + sft_val 8, nhân đôi ở bản mirror `_alpaca`; chỉ key `file`, không đổi `line`/messages) |

Công cụ: `tmp/restructure/list_citations.py` (liệt kê) + `update_citations.py` (thay có
anchor `"file": "<bare>"`, assert số dòng trước/sau từng tệp). Không còn citation trần
nào sót (kiểm bằng grep). **Lưu ý reproducibility:** `data/training/` là tệp **untracked
nhưng không gitignore** — bản vá 496 citation nằm trên đĩa, không vào commit; generator
đã được cập nhật để nếu build lại sẽ sinh đúng đường dẫn mới.

## 4. Hoãn / không làm (kèm lý do)

| Hạng mục | Lý do hoãn |
|---|---|
| Sửa path cũ bên trong `logs/README.md` | Tệp **bị ghim byte trong ARTIFACT_MANIFEST** (scope `logs`, sha `7e2ec94e…`, 1955 B). Edit đầu tiên đã gây ĐỔI thứ 4 ở manifest; đã **khôi phục đúng byte** (chú ý: `git checkout --` một mình KHÔNG đủ — repo có `core.autocrlf=true` nên blob LF phải ghi ra đĩa dạng LF khớp manifest). Tài liệu này giữ đường dẫn cũ `benchmark_chunking.py`/`learn.py` cho tới khi có PA re-anchor manifest. |
| Sửa mọi đường dẫn trong tệp ghim khác (evidence 84 / manifest 158) | Như trên — chạm byte là gãy cổng đã công bố. |
| `evaluation.py` trong `env_flag_audit.SCAN_FILES` | ĐÃ hỏng từ TRƯỚC tái cấu trúc (không có tệp gốc nào tên vậy; `src/evaluation.py` đã nằm trong SCAN_DIRS). Không đụng — ghi ở mục 6. |
| Comment trần: `ingest.py` docstring (2 chỗ "learn.py gọi…"), `scripts/learn.py:56` (nội dung ghi vào `ghi_chu_hoc_them.txt`), `tools/diag/train_data_audit.py:10` ("sinh 23-10 bởi `tools/build_training_data.py`" — mô tả lịch sử), `build_training_data.py:1566` (mô tả nguồn trong manifest) | Là văn mô tả/mô tả lịch sử, không phải đường dẫn dùng lúc chạy; sửa `scripts/learn.py:56` còn đổi cả văn bản sinh ra khi học. |
| Dọn `__pycache__` cũ (`.pyc` mang tên module cũ) | Quy tắc "không xóa file"; tự sinh, không ảnh hưởng import. |
| `tmp/b*.py`, `tmp/clone_*`, script phiên cũ trỏ path cũ | Artifact phiên làm việc đã ghi trong `docs/EXPERIMENTS.md` — phạm vi lịch sử, không sửa. |
| Phase 2 | Đề bài ghi "chỉ LẬP KẾ HOẠCH" — user đã duyệt và giao làm tiếp ngày 28-10 ⇒ **đã thực hiện** (mục 5). |
| Phase 3 | Theo đề bài: **CHỈ ĐỀ XUẤT** (mục 6). |

## 5. Phase 2 — cache OCR + index thực nghiệm: ĐÃ THỰC HIỆN (28-10, sau khi user duyệt)

User duyệt Phase 2 ngày 28-10 ("Chuyển sang Phase 2 xử lý indexes và cache"). Lần 1 (commit
`a085716`) chỉ làm cache và **HOÃN indexes**; sau khi khảo sát coupling xong, user yêu cầu làm
tiếp ⇒ mục 1 (indexes) hoàn thành ở commit sau đó. Cả hai mục đều **không đổi byte dữ liệu**.

### 5.1 Đã làm — `.ocr_cache/` → `.cache/ocr/rapidocr/`, `.ocr_cache_vie/` → `.cache/ocr/easyocr_vie/`

| Thành phần | Thay đổi |
|---|---|
| Thư mục | `shutil.move` (cả hai đều untracked + gitignored ⇒ không dùng `git mv`). 13 + 13 tệp. |
| `src/loader.py` | `DEFAULT_CACHE_DIR = "./.cache/ocr/rapidocr"` (L32) + docstring L8. Tên biến `OCR_CACHE_DIR` giữ nguyên. |
| `.env.example` | `OCR_CACHE_DIR=./.cache/ocr/rapidocr` (L63). |
| `.gitignore` | Thêm `.cache/` vào khối cache (L17); **giữ** rule cũ `.ocr_cache*/` (L60) để máy còn thư mục layout cũ không bị lộ tệp — đã ghi chú lý do ngay trong file. |
| `tools/diag/secret_scan.py` | `SKIPPED_PARTS` thêm `".cache"` (giữ `.ocr_cache`, `.ocr_cache_vie` làm tương thích ngược). |
| `tools/diag/docs_consistency_check.py` | `REPO_TOP` thêm `".cache"` + comment. Không đổi tập kiểm. |
| Docs ACTIVE | `README.md` (cây thư mục, ví dụ `.env`, mục Cache, mục "ba thư mục cache ẩn"), `docs/giang_day/01` (đã cân lại ô khung), `docs/giang_day/02` (2 chỗ), `dev/.maestro/playbooks/01_du_lieu_chi_muc.md` (phạm vi group). |

**Không chạm (có chủ đích)**: `tools/diag/corpus_diacritics.py` (docstring L11 và chuỗi
provenance `"OCR doc tu .ocr_cache qua loader"` L274 **đi vào JSON đầu ra** — sửa là đổi bản
chứng minh đã công bố); `tools/diag/quality_check_vie.py` + `tools/diag/reocr_vie.py` (hai công
cụ một lần của lượt re-OCR 24-10, đường dẫn literal là nội dung đo); `docs/EXPERIMENTS.md`,
`docs/DECISION_LOG.md`, `docs/CLEANUP_REPORT.md`, `docs/archive/*` (lịch sử); `logs/README.md`
(ghim byte); `tools/diag/artifact_manifest.py` (dụng cụ đo — xem 5.3).

**Bằng chứng không đổi hành vi**:

| Cổng | Trước | Sau |
|---|---|---|
| `tmp/restructure/phase2_verify.py` (băm từng tệp, map tiền tố cũ→mới) | — | **26 tệp đổi đường dẫn KHỚP BYTE, lệch 0, thiếu 0** |
| `tmp/restructure/cache_hit_probe.py` (chỉ đọc, dùng đúng `_cache_file` của loader) | 24 PDF quét, 13 resolve, 11 không | **13 resolve, 11 không** — danh sách tên cache giống hệt |
| pytest | 1549 passed / 5 skipped | **1549 passed / 5 skipped** |
| `evidence_pack_check.py --check` | KHỚP (84 tệp) | **KHỚP** |
| `protected_hash_check.py` | 491 tệp, ĐỔI 0 / MẤT 0 | **protected=491 ĐỔI=0 MẤT=0** |
| `run_chain.py … --dry-run` | baseline | **diff = 0 dòng** |
| `docs_consistency_check.py` | SẠCH LỖI (5 cảnh báo cũ) | **SẠCH LỖI** (110 đường dẫn, 5 cảnh báo cũ) |
| `secret_scan.py` | SECRET_COTHAT 0, PII 165 dòng/9 tệp | **SECRET_COTHAT 0, PII 165 dòng/9 tệp** (cache không được quét trước hay sau) |
| Chữ ký trọng tài | `2911c69f740d` | **`2911c69f740d`** |

### 5.2 Đã làm (lượt 2, sau khảo sát coupling) — `chroma_db_vie/` + `chroma_db_headers_old/` → `indexes/experimental/…`

Lần 1 đã **HOÃN** vì ba coupling dưới đây không rõ có thuộc loại "sửa chuỗi đường dẫn" hay phải
sửa logic. Khảo sát xong: **cả ba đều quy về đường dẫn**, không cái nào phải đổi hành vi.

| # | Coupling đã phát hiện | Cách xử lý (chỉ sửa đường dẫn/danh sách đường dẫn) |
|---|---|---|
| 1 | `PROTECTED_INDEX_DIRS = ("chroma_db", "chroma_db_vie")` + `ensure_separate_index_target()` **resolve `root / name` rồi so đường dẫn**, không so tên cuối ⇒ sau move, đích `indexes/experimental/chroma_db_vie` lọt chốt (đo bằng probe trước khi sửa: **2 trường hợp LỎNG CHỐT**). | Nối **đường dẫn mới** vào `PROTECTED_INDEX_DIRS`, giữ tên cũ cho máy chưa dời. Hệ quả CHẶT HƠN có chủ đích: `indexes/` và `indexes/experimental/` (thư mục cha) cũng bị từ chối làm đích build; `indexes/experimental/<tên_mới>` vẫn được phép. Probe sau sửa: **8/8 ĐẠT**. |
| 2 | `tests/test_t5_contextual_header.py::REAL_INDEXES` + fixture `real_index_copy` mở `REPO_ROOT / db_name` ⇒ thiếu thư mục là `pytest.skip` (đỏ hoá vàng). | Thêm `REAL_INDEX_PATHS` (tên → đường dẫn) và cho fixture copy theo **tên cuối**; id param test (`[chroma_db-361]`, `[chroma_db_vie-342]`) và hai con số 361/342 giữ nguyên ⇒ tập đo không đổi. Kiểm: `test_t5_contextual_header.py` **42 passed / 0 skipped**; bộ chỉ số liên quan **188 passed / 2 skipped** (2 skip là symlink, có trước). |
| 3 | Kế hoạch Phase 2 ghi "CHỈ làm sau PA-17" vì `chroma_db_vie` mang số mất neo 48,81%. | Move **không đổi byte** ⇒ số đo vẫn nguyên; thêm `indexes/experimental/README.md` làm **cầu đường dẫn cũ→mới** cho `docs/EXPERIMENTS.md`, `docs/archive/reports/*` và artifact 24–27/10 (được miễn sửa vì là HISTORY). `data/loop/README.md` giữ nguyên vì ghi index theo **tên chốt** (`chroma_db_vie`) trong luật đăng ký trước — tên vẫn đúng, đường dẫn nằm ở README cầu. |

Đường dẫn literal đã nối theo: `tools/diag/check_corpus.py` (`--new-db` mặc định + docstring),
`tools/diag/ablation_c_prime.py::NEW_INDEX`, ví dụ chạy trong `tools/diag/measure_index.py` và
`tools/diag/build_header_index.py`, `tools/diag/tmp_cleanup.py::PROTECTED_PREFIXES` (thêm
`indexes`), README mục cây thư mục + `docs/ARCHITECTURE.md` + `docs/REPRODUCE.md` L34 +
`docs/PA_TRIAGE.md` PA-1. Không đụng `tools/diag/answerability_probe.py` (chú thích lịch sử).

**Bằng chứng không đổi hành vi** (cùng máy kiểm với cache):

| Cổng | Giá trị |
|---|---|
| `phase2_verify.py` (map cũ→mới, băm từng tệp) | cache 26 + index 10 = **36 tệp KHỚP BYTE / lệch 0 / thiếu 0**; `chroma_db/` (production) vẫn ở gốc, 5 tệp nguyên |
| `measure_index.py` đọc index ở đường dẫn mới (qua **bản copy**, không mở trực tiếp để tránh Chroma tự ghi) | **342 chunk**, `word_diacritic 0,8029`, `chunks_empty 0` — đúng số đã công bố |
| `guard_probe_phase2b.py` | trước sửa: 2 LỎNG CHỐT; sau sửa: **8/8 ĐẠT** |
| pytest toàn repo | **1549 passed / 5 skipped** (= baseline, 5 skip đều có trước) |
| `evidence_pack_check.py --check` | **KHỚP** (84 tệp) |
| `protected_hash_check.py` | **491 / ĐỔI 0 / MẤT 0** |
| `run_chain.py … --dry-run` | **diff = 0 dòng** |
| `docs_consistency_check.py` | **SẠCH LỖI** (110 đường dẫn, 5 cảnh báo T7 cũ) |
| `secret_scan.py` | **SECRET_COTHAT 0**, PII 165 dòng/9 tệp (không đổi) |
| Chữ ký trọng tài | **`2911c69f740d`** |
| `.gitignore` | `chroma_db*/` khớp ở **mọi cấp** ⇒ `indexes/experimental/chroma_db_*/` vẫn bị ignore (đo bằng `git check-ignore`); **không cần sửa rule**, chỉ thêm `indexes/experimental/README.md` có chủ đích (được track làm cầu tài liệu) |
| `git diff --diff-filter=D` | **rỗng** — không xóa tệp nào |

### 5.3 Việc còn treo do Phase 2 — **cần user duyệt, ĐÃ ĐĂNG KÝ PA-48**

`tools/diag/artifact_manifest.py::_scope_dirs()` sinh scope bằng `ROOT.glob("chroma_db*")` và
`ROOT.glob(".ocr_cache*")` — **chỉ quét gốc repo**. Sau hai lượt move, cả hai glob đều không còn
khớp ⇒ `--check` báo thêm **THIẾU (36)** = 26 tệp cache + 10 tệp index thực nghiệm
(`cũ 158 tệp/390.961.924 B → nay 122 tệp/378.288.797 B`), kèm đúng 3 mục ĐỔI chroma production
có trước. `chroma_db/` vẫn ở gốc nên scope `chroma` của nó không đổi.

**Không tự sửa glob, không regenerate manifest**: manifest là dụng cụ ghim byte, re-anchor phải
là một commit có chủ đích. PA-48 (`docs/PA_TRIAGE.md`) đăng ký hai việc:

1. Nối `.cache/ocr/*` và `indexes/experimental/*` vào `_scope_dirs()`, chạy lại
   `artifact_manifest.py` sinh manifest mới, **đối chiếu 36 hash cũ↔mới khớp byte** bằng
   `tmp/restructure/phase2_hashes.json` + `phase2_verify.py` trước khi commit.
2. Thêm test ghim `PROTECTED_INDEX_DIRS` bản đường dẫn mới — test hiện tại
   (`test_guard_tu_choi_ghi_de_index_cu`) chỉ khai báo tên cũ `chroma_db_vie`/`chroma_db`, nên
   chốt lỏng ở layout mới **không có test nào bắt** (probe đột biến `guard_probe_phase2b.py`
   chứng minh 2 trường hợp lọt trước khi sửa).

Trong khi chờ, drift 36 mục **là tín hiệu có chủ đích**, không phải hỏng.

### 5.4 Các mục khác của kế hoạch

1. **`data/normalization_pairs.json` → `data/learning/normalization_pairs.json`** — **ĐÃ làm
   (Phase 2c, user yêu cầu 29-10)**. Phát hiện đầu tiên khi khảo sát: **không có tệp để move** —
   `data/normalization_pairs.json` KHÔNG tồn tại trên đĩa và `git log --all --` trả rỗng (chưa
   từng được commit ở bất kỳ nhánh nào): đây là artifact GUI tự sinh lúc người dùng bấm "Sai"
   (Tab 3). Nên phép biến đổi đúng của mục này là **đổi quy ước đường dẫn**, không phải `git mv`.
   - Sửa (2 hằng số + 1 allowlist + 5 tài liệu sống): `src/query_normalizer.py:48`,
     `ui/app.py:53`, `tools/diag/docs_consistency_check.py::RUNTIME_GENERATED`,
     `README.md` (cây thư mục + luồng Tab 3), `docs/giang_day/README.md` (cây),
     `docs/giang_day/04_chuan_hoa_va_classifier.md` (bảng 3 nguồn),
     `docs/guides/NORMALIZATION_ACTIVE_LEARNING.md` (4 dòng kèm thư mục).
   - **Không đổi logic**: `ui/app.py::_save_normalization_pair` đã có
     `NORMALIZATION_PAIRS_PATH.parent.mkdir(parents=True, exist_ok=True)` trước khi ghi ⇒ thư mục
     `data/learning/` tự sinh ở lượt lưu đầu tiên. `load_normalization_pairs()` chỉ đọc.
   - **Không sửa `data/learning/` trong repo**: probe dùng CWD giả lập trong `tmp/` (xem dưới),
     vùng `data/` protected giữ nguyên 491 hash.
   - Env: không (không có biến nào trỏ tới tệp này).
   - `RUNTIME_GENERATED` giữ CẢ HAI tên (mới + cũ) có chủ đích: tài liệu lịch sử còn trích tên cũ
     và `tests/test_t7_docs_consistency.py::test_file_tu_sinh_cua_gui_khong_bao_loi_nhung_ghi_ranh`
     ghim đúng tên cũ làm ví dụ — thay một mục lấy một mục sẽ làm đỏ test mà không thêm giá trị.
   - **Bằng chứng chức năng** `tmp/restructure/probe_2c_read.py`: cây giả lập có cặp mồi ở CẢ hai
     path ⇒ đọc về đúng 1 cặp ở `data/learning/`, KHÔNG thấy cặp mồi ở `data/` (kỳ vọng ĐẠT, rc=0).
     Đột biến điều khiển: quay hằng số về path cũ ⇒ probe đọc phải cặp mồi cũ và báo KHÔNG ĐẠT,
     chứng minh probe không rỗng. Kiểm tĩnh phía ghi: hằng số `ui/app.py` mang `learning`, `mkdir(parents=True)` còn đó.
   - **Hệ quả phải ghi (không tự xử lý)**: trên máy nào ĐÃ từng bấm lưu phản hồi, tệp
     `data/normalization_pairs.json` cũ sẽ **ngừng được đọc** sau thay đổi này (không tự chuyển
     vì `load_normalization_pairs()` chỉ có MỘT nguồn cho nhóm này; thêm fallback đọc hai nơi là
     ĐỔI LOGIC ⇒ trái quy tắc vàng). Cách xử lý thủ công cho người dùng: tựMove tệp sang
     `data/learning/` — dữ liệu không mất, chỉ cần đổi chỗ.
2. **Đồng bộ cách gọi lệnh trong README/REPRODUCE sau khi chuyển `scripts/`** —
   đã làm một phần ở Phase 1; phần còn lại là thêm cờ `--help` vào `ingest.py`,
   `scripts/learn.py`, `ui/app.py`, `ui/demo_streamlit.py` (5 cảnh báo T7 hiện hữu)
   → thuộc PA đã ghi trong `docs/PA_TRIAGE.md`, KHÔNG tự thêm.

### 5.5 Bảng ánh xạ đường dẫn Phase 2 (4 thư mục, 36 tệp)

| Cũ (gốc repo) | Mới | Tệp | Tổng byte | Ghi chú |
|---|---|---|---|---|
| `.ocr_cache/` | `.cache/ocr/rapidocr/` | 13 | 220.617 | cache rapidocr gốc |
| `.ocr_cache_vie/` | `.cache/ocr/easyocr_vie/` | 13 | 282.966 | cache EasyOCR `vi` lượt re-OCR 24-10 |
| `chroma_db_vie/` | `indexes/experimental/chroma_db_vie/` | 5 | 6.232.228 | 342 chunk, chưa kích hoạt (PA-17) |
| `chroma_db_headers_old/` | `indexes/experimental/chroma_db_headers_old/` | 5 | 5.937.316 | snapshot nền đo r13 |
| `chroma_db/` | **không đổi** | 5 | 5.937.316 | index sản xuất, mặc định `CHROMA_PERSIST_DIR` |

### 5.6 Phase 2c — `data/learning/` (29-10, user giao tiếp)

Ánh xạ: `data/normalization_pairs.json` → `data/learning/normalization_pairs.json`.
**Số tệp di chuyển = 0** (tệp chưa từng tồn tại trong git lẫn trên đĩa — xem 5.4 mục 1), nên
bảng byte-identity của Phase 2 không dài thêm; thứ thay đổi là **quy ước đường dẫn** trong
2 hằng số, 1 allowlist máy kiểm và 5 tài liệu sống.

| Cổng | Kết quả | So baseline Phase 2b |
|---|---|---|
| `pytest tests -q` | **1549 passed / 5 skipped** (124,29 s) | bằng |
| `docs_consistency_check.py` | **SẠCH LỖI** — 110 đường dẫn, 5 cảnh báo T7 cũ; ghi chú "tự sinh" nay liệt kê `data/learning/normalization_pairs.json` **và** tên cũ | bằng về số lỗi/số đường dẫn |
| `probe_2c_read.py` | **ĐẠT** — đọc đúng 1 cặp ở `data/learning/`, mồi ở `data/` KHÔNG được đọc | mới (Phase 2c) |
| đột biến điều khiển | quay hằng số về path cũ ⇒ probe đọc phải mồi cũ và báo KHÔNG ĐẠT (chứng minh probe không rỗng) | mới |
| `protected_hash_check` | 491 / **ĐỔI 0** / **MẤT 0** / MOI 36 (`data/learning` **không** được tạo trong repo) | bằng |
| `artifact_manifest --check` | cũ 158 → nay 122 / **THIẾU (36)** + ĐỔI (3) chroma — drift PA-48, không đổi vì Phase 2c không chạm scope | bằng |
| `manifest_crosscheck` | KHỚP 38 / LỆCH 3 / THIẾU 0 | bằng |
| `evidence_pack_check --check` | **KHỚP** (84 tệp) | bằng |
| chain `t5a_reranker` `--dry-run` | **diff 0 dòng** | bằng |
| `secret_scan` | SECRET_COTHAT **0**; PII 165 dòng / 9 tệp | bằng |
| chữ ký trọng tài | **`2911c69f740d`** — `query_normalizer` không thuộc `REFEREE_FILES` | bằng |
| `git diff --diff-filter=D` | **rỗng** | bằng |
| `py_compile` 3 tệp sửa | rc=0; `src/query_normalizer.py` **NL 495 → 495**, `ui/app.py` **NL 1014 → 1014** (không dịch số dòng mà tài liệu khác đang trích) | — |

## 6. Phase 3 — ĐỀ XUẤT (không làm)

Gom `src/` (16 module phẳng) thành gói có `__init__.py` với subpackage `indexing/`
(loader, chunking, contextual_header), `retrieval/` (retrieval, vector_db, reranker,
router), `generation/` (generator, local_slm, answer_guard, refusal_policy,
evidence_selection) và `core/` (pipeline, text_utils, classifier, query_normalizer).
Đề xuất này **đổi toàn bộ import string** (`src.x` → tên gói) và có khả năng đổi thứ
tự side-effect lúc import — tức VƯỢT quy tắc vàng "chỉ di chuyển + sửa tham chiếu".
Điều kiện làm: sau khi chốt báo cáo, có một vòng kiểm chứng riêng (baseline + lại chữ
ký trọng tài trên cây mới) vì `verify.py` tự ký theo **đường dẫn** `src/answer_guard.py`
và `src/text_utils.py` — đổi đường dẫn 2 tệp này là đổi luôn cách kiểm chữ ký.
Hiện trạng giữ nguyên là an toàn nhất.

## 7. Mẫu thuẫn phát hiện — ghi lại, KHÔNG tự sửa

- `README.md` (§1) ghi "1.124 test" ở một đoạn trong khi cây hiện chạy **1.549 passed /
  5 skipped** (đã cập nhật ở §2 của README; con số 1.124 cũ ở đoạn khác, chưa sửa vì đề
  bài nghiêm sửa số liệu — chờ người dùng duyệt).
- **Hai chữ ký trọng tài cùng xuất hiện**: `9f1179ccab74` (mô tả trong ký ức vòng P5,
  `data/loop` README) và `2911c69f740d` (PA-2+PA-20 áp 26-10). Phase 1 không chạm cả 3
  tệp tạo vân tay nên cả hai vẫn nguyên giá trị lịch sử.
- `docs/PA_TRIAGE.md`, `docs/CLEANUP_*` (PA-43 từng "cắt bước con chuyển `learn.py`/
  `benchmark_chunking.py`") là **bản ghi lịch sử quyết định** — Phase 1 làm lại bước đó
  theo yêu cầu mới, không viết lại lịch sử.
- `env_flag_audit.py` có sẵn 1 mục chết `evaluation.py` từ trước (không do tái cấu trúc).
- **Số dòng trong tài liệu dạy học lệch 2 so với mã, CÓ TRƯỚC Phase 2c**:
  `docs/giang_day/04_chuan_hoa_va_classifier.md` và `docs/giang_day/PHU_LUC_ham.md` ghi
  `load_normalization_pairs` ở **dòng 96**; cây hiện tại (kể cả `HEAD` trước khi sửa) đặt nó ở
  **dòng 98**. `data/training/sft_train*.jsonl` cũng trích "dòng 96" trong 4 dòng đã commit.
  Phase 2c thay đúng 2 dòng ở đầu file (`# Đường dẫn…` + `NORMALIZATION_PAIRS_PATH`) ⇒ **không
  làm dịch số dòng** (đã kiểm: `NL 495 → 495`, các mốc 98/187/236/368 giữ nguyên); không tự sửa
  số 96 vì đề bài cấm chỉnh số liệu — ghi lại ở đây, chờ người dùng duyệt.

## 8. Rollback

- `auto/overnight` **không đổi** (đầu tại `c8c2408`); mọi thứ Phase 1 nằm trên
  `chore/restructure`: `24e5c9a` (snapshot) → `4b981b0` (Phase 1). Lùi = bỏ nhánh.
- Backup toàn cây trước khi bắt đầu: `D:\DoAn\hybrid_rag_agu_backup_2026-10-28.zip`
  (3.648 tệp / 613.454.237 B thô).
- Log cổng + ảnh chụp baseline trong `tmp/restructure/` (xóa khi nghiệm thu xong — mục 9).

## 9. Dọn dẹp cuối

Khi người dùng xác nhận nghiệm thu: xóa `tmp/restructure/` (chứa các script tái lập
cổng: `protected_hash_check.py`, `update_citations.py`, `phase2_baseline.py`,
`phase2_verify.py`, `cache_hit_probe.py`, `phase2c_before.py`, `probe_2c_read.py`,
`manifest_crosscheck.py` + các log baseline/after + cây giả lập `probe_2c/`).
Không dọn `tmp/` nói chung (nhiều artifact được `docs/EXPERIMENTS.md` trích nguồn).

Riêng `phase2_hashes.json` + `phase2_verify.py` + `guard_probe_phase2b.py` là **bằng chứng
re-anchor cho PA-48** — giữ đến khi PA-48 được commit (dùng để đối chiếu 36 hash cũ↔mới trước
khi sinh manifest mới, và tái hiện phép thử "chốt lỏng trước / chặt sau khi nối đường dẫn").
