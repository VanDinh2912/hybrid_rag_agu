# Báo cáo kiểm thử — T7: `run_chain` + khóa chính sách trong cache sinh + sổ quyết định

Ngày: 2026-10-25 · Nhánh `auto/overnight` · Phạm vi: **đóng gói công cụ + test + tài liệu**;
KHÔNG sửa trọng tài (`tools/loop/verify.py`, `src/answer_guard.py`, `src/text_utils.py`), KHÔNG sửa
`tools/loop/gate.py`, KHÔNG chấm lại round đã đóng, KHÔNG ghi vào `outputs/` hay
`data/loop/rounds/`, **0 lượt gọi Gemini**. Test mới dùng `tmp_path`, fake model, không gọi mạng.

Đối tượng kiểm thử:

- [`tools/loop/run_chain.py`](../../tools/loop/run_chain.py) + wrapper `.ps1`/`.sh` + `chains/*.json`
- [`src/cache_policy.py`](../../src/cache_policy.py) + 2 hunk `_cache_key` trong `src/generator.py`
- [`docs/DECISION_LOG.md`](../DECISION_LOG.md), README §5.10/§8.1, ROADMAP P5.21–P5.23

## 1. Đã làm gì

### 1.1 `run_chain` — một lệnh cho cả chuỗi round

Trước T7, mỗi round được chạy bằng driver `.sh` viết tay trong `tmp/`; mất log là mất danh sách env
đã export. `run_chain` thay bằng **một spec JSON** + **manifest tất định**. Bốn bảo đảm được ghim
bằng test (11 test, [`tests/test_run_chain.py`](../../tests/test_run_chain.py)):

1. `--dry-run` in argv + env từng bước, **không gọi subprocess** (stub ghi lại lời gọi = rỗng).
2. Manifest cùng spec ⇒ **cùng bytes**: không timestamp, key sắp xếp, có `spec_sha256`, đường dẫn
   **tương đối** (không dính `D:\…` của máy chạy).
3. Thiếu biến trong `requires` ⇒ dừng **trước bước đầu tiên** (preflight), không chạy nửa chuỗi.
4. Thư mục round đã có dữ liệu ⇒ từ chối ghi đè, trừ `--resume`; round trùng tên trong spec ⇒ dừng;
   `--set GEMINI_API_KEY=…` ⇒ dừng (bí mật không được đi qua spec).
5. Cổng trả mã 1: **có** báo cáo cổng ⇒ ghi nhận rồi đi tiếp sang `attribute.py` (kết quả âm vẫn
   phải được quy lỗi); **không** có báo cáo ⇒ dừng vì không đánh giá được.

`run_chain` chỉ gọi ba công cụ sẵn có: `run_round.py`, `gate.py`, `attribute.py`. Không sửa dữ liệu,
không chấm lại round cũ, không gọi model trực tiếp.

### 1.2 Khóa chính sách trong cache sinh

Cache của `GeminiGenerator` và `QwenGenerator` chỉ băm `{model, temperature, prompt_version, prompt}`.
Đổi `RESCUE_MIN_SCORE` 0,8→0,55 hay `EV_MAX_SENTENCES` 5→9 thì câu trả lời cũ vẫn trúng ⇒ round sau
"tái dùng thể chế cũ". `src/cache_policy.py` dựng ảnh chụp **chỉ cờ + ngưỡng** từ chính hàm phân giải
của module sở hữu, rồi:

| Hàm | Dùng cho | Ghi chú |
|---|---|---|
| `policy_snapshot()` | log/manifest/test | đủ `prompt_version`, mọi cờ + ngưỡng; không chứa env khác |
| `policy_fingerprint()` | nhận diện thể chế | 12 hex của toàn bộ snapshot |
| `policy_cache_token()` | khóa cache | **bỏ** `prompt_version` + `decoupled_refusal.enabled` (đã được `prompt_version` mã hóa `v1.3` ↔ `v2.0-extract-only`); **giữ** mọi ngưỡng `RESCUE_*`, `ANSWER_GUARD_*`, `DEC_*`, `EV_*`, `NORMALIZE_MIN_CONTAINMENT`, `EVIDENCE_RERANKER` |
| `cache_policy_deviation()` | quyết định thêm trường `policy` | `None` nếu token trùng mốc đã đăng ký `DEFAULT_CACHE_TOKEN = d0b4c6a65f83` |

**Thiết kế "chỉ thêm khi lệch mặc định".** Thể chế mặc định giữ **đúng công thức cũ 4 trường** (không
đỏ 7 test T3/T5 đang ghim payload, 351+ entry cache còn dùng được — bất biến #2 "cờ TẮT = hành vi cũ
từng ký tự"). Chỉ khi ngưỡng/cờ lệch mốc thì payload mới mang thêm `policy`, và hai thể chế khác nhau
không thể chia sẻ entry. Đánh đổi có chủ đích: đổi ngưỡng hậu xử lý **buộc sinh lại** — thà tốn lượt
hơn trộn câu trả lời của thể chế khác.

Hai đường cache đều được vá: `GeminiGenerator._cache_key` và `QwenGenerator._cache_key` (vòng lặp chạy
qua Qwen, thiếu đường này thì lever mới vẫn bị cache cũ che).

### 1.3 Sổ quyết định + tài liệu

- [`docs/DECISION_LOG.md`](../DECISION_LOG.md): **23 quyết định** D-01…D-23, mỗi dòng có ngày, giả
  thuyết, số đo, nguồn file, trạng thái; D-21 (khóa chính sách), D-22 (`run_chain`), D-23 (khoảng
  trống HEAD, MỞ/PA-26). Kiểm tự động đã sửa 11 trích dẫn viết tắt `rounds/…` → `data/loop/rounds/…`.
- README **§5.10** (chạy lại một round / cả chuỗi), **§8.1 "Giới hạn thật lòng (cập nhật 25-10,
  sau r0–r13)"** 10 mục có nguồn; ROADMAP **P5.21–P5.23**; STATE + MORNING_REPORT cập nhật mốc
  **1.004 passed**.

## 2. Kết quả số (nguồn: file trên đĩa)

### 2.1 Số test

| Lần chạy | Kết quả | Nguồn |
|---|---|---|
| `tests/test_run_chain.py` | **11 passed** (0,22 s) | `tmp/mutation_check_t7.log` dòng `[baseline]` |
| `tests/test_cache_policy.py` | **26 passed**, 3 warnings (2,08 s) | `tmp/mutation_check_cache_policy.log` dòng `[baseline]` |
| Toàn repo (sau mutation, cây đã hoàn nguyên) | **1.004 passed**, 3 warnings (27,02 s) | `tmp/pytest_t7_final.txt` |
| Chữ ký trọng tài (trước = sau) | **`9f1179ccab74`** | `tmp/pytest_t7_final.txt` dòng cuối |

Mốc trước T7 là **967 passed** (HEAD `456f35c`): 967 + 11 + 26 = **1.004**. Không sửa test cũ nào;
7 test cũ từng đỏ khi thiết kế "luôn thêm policy" đã được cứu bằng thiết kế "chỉ thêm khi lệch", không
phải bằng sửa test.

### 2.2 Từng mục của đề bài T7

| Mục | Trạng thái | Bằng chứng |
|---|---|---|
| Đóng gói chuỗi round bằng một lệnh, kèm env | **XANH** | spec JSON + manifest tất định; 11 test; chuỗi demo 2×20 item chạy end-to-end (§2.4) |
| Xoá `tmp/` scratch **sau khi liệt kê và được duyệt** | **CHƯA XOÁ — đúng luật** | PA-24: 92,1 MB/104 mục, nhóm A/B giữ, nhóm C cần quyết, nhóm D đề xuất xoá 45 mục ~33 MB; không xoá gì |
| `docs/DECISION_LOG.md` (ngày, giả thuyết, số đo, file nguồn, trạng thái) | **XANH** | 23 quyết định; kiểm trích dẫn `THIEU: khong` |
| Đặt policy key vào cache để đổi ngưỡng không tái dùng cache cũ | **XANH ở mức unit** | 26 test + mutation 10/10; chưa chạy round thật với ngưỡng mới (xem §4.1) |
| `pytest tests -q` xanh | **XANH** | 1.004 passed (`tmp/pytest_t7_final.txt`) |
| Cập nhật README + ROADMAP | **XANH** | README §5.10/§8.1; ROADMAP P5.21–P5.23; commit `79a02e5` |
| Liệt kê "Giới hạn thật lòng" còn lại | **XANH** | README §8.1, 10 mục đều có nguồn file |

### 2.3 Mutation check — 17/17 đột biến bị bắt, 17/17 hoàn nguyên byte-identical

Hai harness độc lập, mỗi đột biến phá **đúng một** tính chất; script sao lưu byte gốc trong bộ nhớ,
khôi phục bằng `write_bytes` và so **SHA-256** sau từng lượt (bắt buộc vì `src/generator.py` là file
dirty của phiên khác — PA-26).

**`run_chain` — 6/6** (nguồn: [`tmp/mutation_check_t7.log`](../../tmp/mutation_check_t7.log)):

| Đột biến | Tính chất bị phá | Test đỏ | Hoàn nguyên |
|---|---|---|---|
| M1 bỏ preflight env | thiếu env vẫn chạy bước đầu | `test_run_chain_missing_required_env_stops_before_first_step` | có |
| M2 bỏ chặn ghi đè round | ghi đè thư mục round đã có | `test_run_chain_refuses_existing_round_dir_without_resume` | có |
| M3 manifest dùng đường dẫn tuyệt đối | manifest không tái lập giữa máy | `test_run_chain_manifest_is_deterministic_and_relative` | có |
| M4 cổng fail luôn dừng chuỗi | kết quả âm không được quy lỗi | `test_run_chain_gate_failure_with_report_continues_to_attribute` | có |
| M5 cho phép `--set` biến bí mật | bí mật đi qua spec | `test_run_chain_rejects_secret_set_override` | có |
| M6 bỏ kiểm round trùng tên | hai bước ghi cùng thư mục | `test_run_chain_duplicate_round_names_rejected` | có |

**`cache_policy` — 10/10** (nguồn: [`tmp/mutation_check_cache_policy.log`](../../tmp/mutation_check_cache_policy.log)):

| Đột biến | Tính chất bị phá | Test đỏ tiêu biểu | File | Hoàn nguyên |
|---|---|---|---|---|
| M1 bỏ qua snapshot truyền vào | không kiểm được ảnh chụp giả lập | `test_policy_key_version_change_changes_fingerprint` | `src/cache_policy.py` | có |
| M2 đóng băng `min_score` = 0.8 | đổi `RESCUE_MIN_SCORE` không đổi vân tay | `test_policy_fingerprint_changes_when_rescue_min_score_changes` | `src/cache_policy.py` | có |
| M3 bỏ `policy_key_version` | bump cách tính không tách cache | `test_policy_snapshot_shape_matches_contract` | `src/cache_policy.py` | có |
| M4 rò toàn bộ `os.environ` vào snapshot | có thể lộ bí mật | `test_policy_snapshot_contains_no_sensitive_env_values` | `src/cache_policy.py` | có |
| M5 vân tay 40 ký tự | hợp đồng 12 hex vỡ | `test_policy_fingerprint_same_env_returns_same_12_hex` | `src/cache_policy.py` | có |
| M6 độ lệch luôn `None` | khóa cache **không bao giờ** đổi theo ngưỡng | `test_cache_key_payload_has_policy_token_when_threshold_deviates` | `src/cache_policy.py` | có |
| M7 bỏ `prompt_version` khóa Gemini | không tách prompt version | `test_cache_key_payload_contains_prompt_version_and_policy` | `src/generator.py` | có |
| M8 bỏ `prompt_version` khóa Qwen | không tách prompt version (đường loop) | `test_qwen_cache_key_payload_contains_prompt_version_and_policy` | `src/generator.py` | có |
| M9 bỏ gắn token chính sách (Gemini) | đổi ngưỡng vẫn trúng cache cũ | `test_cache_key_payload_has_policy_token_when_threshold_deviates` | `src/generator.py` | có |
| M10 bỏ gắn token chính sách (Qwen) | lever mới bị cache loop che | `test_qwen_cache_key_changes_when_policy_threshold_changes` | `src/generator.py` | có |

SHA-256 của ba file trước và sau toàn bộ mutation check **trùng khít**:

| File | SHA-256 trước = sau |
|---|---|
| `src/generator.py` | `d3791b44f3a0fc6b86c399a8e8ca34092a196dbfe30f1ad76fdb1bdd898f2d65` |
| `src/cache_policy.py` | `652477e3572dc492e4c0a24009c7a2963a40242f10325aaa8e3087d401b70902` |
| `tools/loop/run_chain.py` | `bf13918a541797817ed3f79a6132dc9e45ce13d96e3aa77543e7292d9d47ecbf` |

### 2.4 Chuỗi demo chạy thật (không chỉ dry-run)

`tmp/chain_demo3/` — spec [`chains/demo_dryrun.json`](../../tools/loop/chains/demo_dryrun.json), 2 round
retrieval trên 20 item CLOZE, `out_root=tmp/chain_demo3` (không đụng `data/loop/rounds/`):

| Bước | Kết quả | Nguồn |
|---|---|---|
| `demo_a` (20 item CLOZE) | xong 11:13:32 | `tmp/chain_demo3/demo_a/round_summary_retrieval.json` |
| `demo_b` (pin subset từ `demo_a`) | xong 11:18:23, 20 item | `tmp/chain_demo3/demo_b/round_summary_retrieval.json` |
| Cổng `demo_b` vs `demo_a` | **ĐẠT** (`passed=true`, `n_common_items=20`) | `tmp/chain_demo3/demo_b/gate_vs_demo_a_retrieval.json` |
| gold@k | **1,0 → 1,0** (ngưỡng −0,02); không family nào giảm >0,1 | cùng file, `family_deltas` |
| Vi phạm / cải thiện | `regressions=[]`, `improvements=[]` | cùng file |
| Attribute | 20 item, `fail_retrieval=0` | `tmp/chain_demo3/demo_b/attribution_retrieval.json` |

Đây là **demo cấu hình**, không phải round đo lever: mục tiêu là chứng minh chuỗi `run_round → gate →
attribute` chạy được bằng một spec và sinh đúng manifest. Cả hai round dùng `generator=offline_qwen`,
mọi cờ TẮT — **0 lượt Gemini**.

### 2.5 Hành vi khóa cache (đo bằng test, không suy luận)

| Tình huống | Kết quả | Test |
|---|---|---|
| Thể chế mặc định, env rỗng | payload đúng **4 trường cũ**, `_cache_key` = SHA-1 tính tay | `test_cache_key_payload_contains_prompt_version_and_policy`, `..._qwen...` |
| `policy_cache_token()` dưới env rỗng | `d0b4c6a65f83` (trùng `DEFAULT_CACHE_TOKEN`) | `test_policy_cache_token_default_matches_cleared_env` |
| Đổi `RESCUE_MIN_SCORE=0.55` | khóa Gemini **và** Qwen đổi; payload thêm `policy` = token lệch | `test_cache_key_changes_when_policy_threshold_changes`, `test_qwen_...` |
| Đổi `ANSWER_GUARD_MAX_UNSUPPORTED` | `deviation` khác `None` và khác mốc | `test_cache_policy_deviation_none_at_default_token_when_threshold_changes` |
| Bật `ENABLE_DECOUPLED_REFUSAL` | token **không** đổi (đã nằm trong `prompt_version`); đổi `DEC_MIN_ENTITY_COVERAGE` | `test_cache_policy_token_ignores_decoupled_flag_but_not_its_thresholds` |
| Xoay `GEMINI_API_KEY` | khóa **không** đổi; không giá trị bí mật nào vào snapshot | `test_cache_key_does_not_change_when_only_secret_env_changes`, `test_policy_snapshot_contains_no_sensitive_env_values` |
| Đổi model / prompt / temperature | khóa đổi | `test_cache_key_changes_when_model_or_prompt_or_temperature_changes` |

### 2.6 Trạng thái git kỳ vọng

Commit `79a02e5` (13 file, +1.150/−6) chứa **toàn bộ phần an toàn**: `run_chain.{py,ps1,sh}`,
`chains/*.json`, `tests/test_run_chain.py`, DECISION_LOG, README/ROADMAP/STATE/MORNING_REPORT/
PENDING_APPROVAL/AUTONOMY_LOG.

Working tree **còn đúng** phần không được commit (PA-26):

| Loại | Mục |
|---|---|
| Tracked đang sửa | `src/generator.py`, `src/pipeline.py`, `src/query_normalizer.py`, `src/router.py`, `tests/test_pipeline.py`, `tests/test_subquery.py` |
| Untracked liên quan T7 | `src/cache_policy.py`, `tests/test_cache_policy.py` |
| Untracked khác (35 file nguồn/công cụ/test) | `src/answer_guard.py`, `src/reranker.py`, `tools/loop/*`, `tools/diag/*`, `tests/test_loop_*`, … |
| Artifact (không commit) | `models/`, `data/loop/rounds/`, `chroma_db_vie/`, `chroma_db_headers_old/`, `.ocr_cache_vie/`, caches |

Vì sao không commit: luật tự trị cấm commit file `src/` dirty của phiên khác; `src/generator.py` chứa
lẫn ~310 dòng của phiên trước với đúng 2 hunk T7. Commit cả file sẽ gán sai tác giả cho thay đổi chưa
được phiên này kiểm. Hệ quả: **fresh clone tại `79a02e5` không chạy nổi 1.004 test** — PA-26 (đề xuất
phương án ii) là điều kiện đóng lỗ tái lập.

## 3. Kết luận chỉ từ số

- 11 test `run_chain` + 26 test `cache_policy` xanh; **17/17** đột biến bị bắt và **17/17** hoàn nguyên
  byte-identical ⇒ test có hiệu lực, không phải test "trang trí".
- Thể chế mặc định giữ **nguyên khóa cache cũ** (test tính lại SHA-1 4 trường); đổi bất kỳ ngưỡng hậu
  xử lý nào được registry theo dõi đều đổi khóa ⇒ không thể tái dùng câu trả lời của thể chế khác.
- Bí mật không lọt vào snapshot/token; xoay key không làm mất cache (đúng ý nghĩa cache).
- `run_chain` chạy được chuỗi thật 2 round: cổng ĐẠT, attribute sinh báo cáo, không ghi vào
  `data/loop/rounds/`, không gọi model sinh.
- Toàn repo **1.004 passed**, trọng tài vẫn `9f1179ccab74` ⇒ không round cũ nào phải chấm lại.

## 4. Điều KHÔNG kết luận được / phần chưa kiểm

### 4.1 Chưa chứng minh "đổi ngưỡng ⇒ cache miss" trên cache thật

Test chứng minh **khóa** đổi và payload đúng cấu trúc; chưa chạy một cuộc gọi sinh thật nào để thấy
một entry cũ bị bỏ qua. Lý do: mọi round gần đây chạy Qwen offline, và chạy một round đủ lớn tốn
~66 phút (D-20) — ngoài phạm vi T7. Đây là kiểm chứng **unit-level**, không phải end-to-end.

### 4.2 `DEFAULT_CACHE_TOKEN` là mốc đăng ký, không phải hằng số vĩnh viễn

Nếu ai đổi default của một module sở hữu (`RESCUE_MIN_SCORE`, `ANSWER_GUARD_MAX_UNSUPPORTED`, …),
`test_policy_cache_token_default_matches_cleared_env` sẽ đỏ. Khi đó phải **đăng ký lại token** và cân
nhắc bump `CACHE_TOKEN_VERSION` — không được sửa test cho xanh. Chưa có cơ chế tự động bump.

### 4.3 `run_chain` chưa chạy chuỗi ngày/đêm thật

Demo chỉ 2 round × 20 item retrieval, không có pha `full`, không có nhiều spec. Chưa kiểm: resume sau
khi chuỗi dừng giữa đường ở quy mô 811 item; hai chuỗi chạy song song (không có khoá file); manifest
khi có đường dẫn Unicode. Spec `t5a_reranker.json` đã có nhưng **không chạy lại** (r11/r12 đã chạy tay
và đóng sổ).

### 4.4 Chưa xoá `tmp/` — chờ duyệt

PA-24 liệt kê đủ 104 mục (92,1 MB): giữ 45 mục được dẫn + 7 mục dẫn gián tiếp, 5 nhóm cần quyết,
đề xuất xoá 45 mục ~33 MB. Không xoá gì trong phiên này. Hai lượt demo hỏng `chain_demo/`,
`chain_demo2/` được xếp vào nhóm D, không tự xoá.

### 4.5 Lỗ tái lập PA-26 vẫn mở

`79a02e5` chưa đủ để fresh clone chạy test: còn 35 file nguồn/công cụ/test untracked + 6 file tracked
đang sửa. Báo cáo này mô tả **working tree**, không mô tả một commit tái lập được.

### 4.6 `prompt_version` không phải phần mới của T7

Khóa cache **đã** có `prompt_version` từ trước; T7 thêm `policy` và bảo vệ `prompt_version` khỏi bị
bỏ sót ở cả hai lớp generator (M7/M8). Không nên đọc báo cáo này như "T7 đã thêm prompt_version".

## 5. Tiêu chí xong

- "Người ngoài chạy lại được từ README": **đạt ở mức công cụ** (README §5.10 có lệnh dry-run/chạy
  thật; spec mẫu chạy được) nhưng **chưa đạt ở mức repo** vì PA-26 — fresh clone thiếu file.
- "Test xanh": **đạt** — 1.004 passed, 0 đỏ; trọng tài `9f1179ccab74`.
- Không sửa test cũ để xanh; không ghi vào `outputs/`/`data/loop/rounds/`; mọi test mới dùng
  `tmp_path` và fake model.

## 6. Lệnh tái lập

```bash
# Hai file test T7
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  tests/test_run_chain.py tests/test_cache_policy.py -q

# Toàn repo + chữ ký trọng tài
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c \
  "from tools.loop import verify; print(verify.referee_fingerprint())"

# Mutation check (tự hoàn nguyên + kiểm SHA-256)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t7.py
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_cache_policy.py

# Xem lệnh của chuỗi T5a mà không chạy gì
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/run_chain.py \
  --chain tools/loop/chains/t5a_reranker.json --dry-run
```

## 7. Đề xuất cần duyệt

- **PA-26** (chặn nghiệm thu "người ngoài chạy lại"): chọn (i)/(ii)/(iii) để đóng khoảng trống HEAD;
  đề xuất (ii) — commit mã + tổng hợp round, không commit `models/`, `chroma_*`, `full.jsonl`.
- **PA-24**: danh sách xoá `tmp/` (chưa xoá gì).
- **PA-25**: bỏ `fold(query)` trong `score_pairs` + chạy r14 (~66 phút, 0 Gemini) — kết luận âm của
  r12 là về bản build, không phải về ý tưởng reranker.

## Phụ lục A — số công bố | số tính lại | khớp

| Số công bố | Cách tính lại | Kết quả | Khớp |
|---|---|---|---|
| 11 test `run_chain` | `pytest tests/test_run_chain.py -q` (baseline mutation log) | 11 passed, 0,22 s | có |
| 26 test `cache_policy` | `pytest tests/test_cache_policy.py -q` (baseline mutation log) | 26 passed, 2,08 s | có |
| 1.004 passed toàn repo | `pytest tests -q` sau mutation | 1.004 passed, 27,02 s | có |
| 967 + 11 + 26 = 1.004 | cộng mốc HEAD `456f35c` với hai file mới | 1.004 | có |
| 6/6 đột biến `run_chain` bị bắt | `tmp/mutation_check_t7.log` | 6/6, hoàn nguyên 6/6 | có |
| 10/10 đột biến `cache_policy` bị bắt | `tmp/mutation_check_cache_policy.log` | 10/10, hoàn nguyên 10/10 | có |
| `DEFAULT_CACHE_TOKEN = d0b4c6a65f83` | test tính lại `policy_cache_token()` dưới env rỗng | trùng | có |
| Chữ ký trọng tài `9f1179ccab74` | `verify.referee_fingerprint()` | trùng | có |
| Cổng demo ĐẠT, 20 item chung, gold@k 1,0→1,0 | đọc `gate_vs_demo_a_retrieval.json` | trùng | có |
| `fail_retrieval = 0` ở demo_b | `attribution_retrieval.json` (`n_items=20`) | trùng | có |
