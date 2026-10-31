# Báo cáo kiểm thử — T7: `run_chain` + khóa chính sách trong cache sinh + sổ quyết định

> **Tài liệu lịch sử (historical).** Số đo và đường dẫn giữ nguyên như lúc viết (trước tái cấu
> trúc 28-10). Không chạy lại script đo để làm mới số trong báo cáo này.

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

> Cập nhật 25-10 11:4x (sau báo cáo T4/T6): thêm **1 test biên** cho luật refusal tương đối (T6a) ⇒
> toàn repo hiện **1.005 passed** (`tmp/pytest_t4t6_final.txt`). Con số 1.004 ở trên là ảnh chụp đúng
> tại thời điểm T7.

> Cập nhật 25-10 11:51: thêm **1 test T0** (CI phải chứa **ước lượng điểm giải tích**, không chỉ trung
> bình bootstrap) ⇒ toàn repo **1.006 passed** (`tmp/pytest_t0_final.txt`). 1.005 ở trên là ảnh chụp
> đúng tại thời điểm viết báo cáo T4/T6.

> Cập nhật 25-10 11:55: thêm **5 test T1** (cô lập byte `src/`, guard tập item thêm/bớt id, docs thật
> stub nhận ở (a), biên band quyết định) ⇒ toàn repo **1.011 passed** (`tmp/pytest_t1_final.txt`).

> Cập nhật 25-10 17:2x (**đợt 2**): thêm **106 test T7** (4 file mới) + 20 test T5/T6 đã vào trước đó
> ⇒ toàn repo **1.228 passed, 4 skipped**, 36,68 s (`tmp/pytest_t7_dot2_final.txt`), chữ ký trọng tài
> vẫn `9f1179ccab74`. Các con số 1.004/1.005/1.006/1.011/1.064/1.124 phía trên là **ảnh chụp có ngày
> giờ** của từng đợt, không phải số hiện tại.

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

### 2.3 Mutation check — 6 + 10 = **16/16** đột biến bị bắt, 16/16 hoàn nguyên byte-identical

> **Đính chính (đợt 2, 25-10 16:5x).** Bản trước ghi tiêu đề mục này là "17/17" — **sai số học**:
> harness `run_chain` có 6 đột biến, harness `cache_policy` có 10, tổng là **16**. Con số "17" là cộng
> nhầm ngay lúc viết báo cáo — không có đột biến thứ 17 ở bất kỳ harness nào. Số **6/6** và
> **10/10** trong hai bảng dưới và trong `tmp/mutation_check_t7.log`,
> `tmp/mutation_check_cache_policy.log` đều đúng. Đợt 2 chạy thêm harness **20 đột biến** (§8.3), trong
> đó một phần nhân bản lại tính chất đợt 1 (preflight thiếu env, chặn ghi đè thư mục round, cổng lỗi
> không có báo cáo, chặn bí mật trong spec, đổi khóa cache theo ngưỡng, giữ khóa cũ khi mặc định) —
> nên bằng chứng đợt 1 không bị thay thế mà được phủ rộng thêm (thêm `tmp_cleanup` và
> `docs_consistency_check`, hai bộ trước đó **chưa có** mutation).

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

- 11 test `run_chain` + 26 test `cache_policy` xanh; **16/16** đột biến bị bắt và **16/16** hoàn nguyên
  byte-identical ⇒ test có hiệu lực, không phải test "trang trí". (Đợt 2 bổ sung **20/20** cho bốn bộ
  test mới + hai công cụ chưa từng được đột biến: xem §8.)
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
- **PA-29** (mới, đợt 2): 5 script README nhắc mà **không có argparse** ⇒ không thể kiểm
  `--help`/dry-run tự động; nghiêm trọng nhất là `ingest.py` (rebuild index, không có dry-run nên
  không thể "chạy thử an toàn"). Chi tiết ở §8.6 và [`docs/PENDING_APPROVAL.md`](../PENDING_APPROVAL.md).

## 8. ĐỢT 2 (25-10 16:1x → 17:2x) — test trực tiếp cho 7 mục của đề bài

Đợt 1 đóng gói công cụ (`run_chain`, `cache_policy`, `tmp_cleanup`, sổ quyết định) và test hai phần
đầu. Đợt 2 viết **test trực tiếp cho từng mục đề bài** (1–6), chạy lại mục 7 toàn repo, thử nghiệm
thu bằng cách **tái lập r0 bằng một lệnh**, và ghi nguyên hai sự cố về bằng chứng (§8.5). Vẫn
không sửa `gate.py`, không sửa trọng tài, không chấm lại round đã đóng, không ghi vào
`outputs/`/`data/loop/rounds/`, **0 lượt Gemini**.

### 8.1 Bốn file test mới — 106 test (mục 1–6 của đề bài)

| File | Test | Mục đề bài | Cách test mà không gọi model/mạng |
|---|---|---|---|
| [`tests/test_t7_chain_env_manifest.py`](../../tests/test_t7_chain_env_manifest.py) | 19 | 1 + 2 | `RecordingStub` ghi lại `argv`/`env`/`cwd` của mọi subprocess ⇒ `--dry-run` assertions là **0 lời gọi**; spec mẫu 2 round × 3 item trong `tmp_path` |
| [`tests/test_t7_cache_reuse_e2e.py`](../../tests/test_t7_cache_reuse_e2e.py) | 18 | 3 | `CountingOllama` giả (đếm `instances` + tổng số lần gọi) + `GENERATION_CACHE_DIR` trỏ `tmp_path`; khóa cache còn được đối chiếu với SHA-1 **tự tính tay** trong test |
| [`tests/test_t7_tmp_cleanup.py`](../../tests/test_t7_tmp_cleanup.py) | 33 (31 passed, 2 skipped) | 4 | cây repo giả trong `tmp_path` + `mklink /J` thật để chứng minh `is_symlink()` mù junction |
| [`tests/test_t7_docs_consistency.py`](../../tests/test_t7_docs_consistency.py) | 36 | 5 + 6 | cây repo giả (sổ quyết định 6 cột, `src/gate_like.py` cố ý **không** có argparse) + 5 test **chỉ-đọc** chạy trên repo thật |

Gộp với 11 + 26 test đợt 1: **143 test T7**, chạy trong 15,4 s.

Theo từng mục, bằng chứng nằm ở tên test (đọc được, không cần tin mô tả):

1. **dry-run in đúng lệnh + env, không chạy gì** — `test_dry_run_khong_goi_subprocess`,
   `test_dry_run_in_du_lenh_va_env_cua_tung_round`; **thiếu env bắt buộc ⇒ dừng sớm** —
   `test_thieu_bien_cap_chuoi_dung_som` và `test_thieu_bien_bat_buoc_o_giua_chuoi_dung_truoc_buoc_dau`
   (biến `requires` ở bước **giữa** chuỗi vẫn bị bắt **trước bước đầu tiên**, không phải giữa chừng);
   **hai lần chạy mẫu nhỏ cho cùng manifest** — `test_hai_lan_chay_cung_manifest_bytes` +
   `test_manifest_cua_hai_lan_chay_that_giong_nhau` (so **bytes**, không so dict).
   Bằng chứng ngoài test, trên **chuỗi thật 811 item**: manifest do lượt chạy thật ghi
   (`data/loop/diag/chain_manifest_t7_repro_r0.json`) và manifest do `--dry-run` in ra
   (`tmp/t7_repro_manifest_probe.json`) **trùng SHA-256**
   `295413c196de90619e79d2e86e7a394b275451acbaa0526182f8d30a9b13b546` ⇒ dry-run mô tả đúng những gì
   đã chạy, không phải một bản in "gần giống".
2. **round mới vào thư mục mới; thư mục đã có dữ liệu ⇒ từ chối** — `TestThuMucRound` (5 test):
   từ chối + **không ghi đè** file cũ, thư mục **rỗng** vẫn chạy, `--resume` mở khoá nhưng vẫn không
   xoá dữ liệu cũ, và mọi thư mục được kiểm **trước** bước đầu (`test_kiem_du_moi_thu_muc_truoc_buoc_dau`).
3. **đổi ngưỡng ⇒ cache cũ không tái dùng; không đổi ⇒ tái dùng (đếm số lần gọi stub)** —
   `test_hoi_lai_khong_tang_cuoc_goi` (hỏi lại câu đã trả lời: **0** call mới, vẫn 1 entry);
   tham số hoá **6 cặp (biến, ngưỡng)** — `RESCUE_MIN_SCORE=0.6`, `ANSWER_GUARD_MAX_UNSUPPORTED=0`,
   `ANSWER_GUARD_MAX_UNSUPPORTED=2`, `DEC_MAX_UNSUPPORTED=7`, `NORMALIZE_MIN_CONTAINMENT=0.45`,
   `EV_MAX_SENTENCES=9` — mỗi cặp phải sinh **call mới** và **đúng 2 entry** trong thư mục cache,
   `test_tra_ve_cu_trung_lai_entry_goc` (đổi rồi trả lại env cũ ⇒ trúng **đúng entry cũ**, không sinh thêm),
   `test_the_che_lech_lam_doi_khoa_gemini_dung_het` + `test_bat_co_khach_biet_ra_khai_nhat_quan`
   (đường Gemini và đường cờ-bật cũng đổi khóa).
4. **dọn dẹp** — mặc định chỉ liệt kê (`TestMacDinhChiLietKe`), `--yes` mới xoá, và **3 lớp chặn độc
   lập**: (a) mọi symlink/junction — kể cả junction `tmp/…` → thư mục khác **bên trong** `tmp/`;
   (b) realpath phải nằm trong `tmp/`; (c) tiền tố vùng bảo vệ (`outputs/`, `data/loop/rounds/`,
   `data/training/`, `chroma_db*`, `models/`, `venv*`, `src/`, `tools/`, `tests/`, `docs/`, `.git`).
   Mục **được trích dẫn trong báo cáo/README/ROADMAP** bị từ chối **kể cả khi có `--yes`**; chặn theo
   **vị trí thật** nên `tmp/outputs` (scratch trùng tên) vẫn xoá được mà `outputs/` của repo vẫn nguyên.
5. **sổ quyết định** — checker đòi đủ 6 cột, ngày dạng `dd-mm`, giả thuyết, **số đo phải chứa con số**,
   nguồn là đường dẫn **tồn tại trên đĩa** (kể cả dạng `a` + `b/c`, và `{r1,r2}` phải có **cả hai** nhánh),
   trạng thái thuộc tập đăng ký. Repo thật hiện **29 dòng (D-01…D-29), 0 lỗi** — thêm dòng mới là
   checker tự đòi đủ 6 cột và đòi nguồn có thật (đang chạy trong `pytest`).
6. **tài liệu** — mọi đường dẫn `src|tools|tests|data|docs|ui|models|outputs/…` và file gốc
   (`README.md`, `ROADMAP.md`, `TAXONOMY.md`, `requirements.txt`, `.env.example`) được nhắc trong
   README/ROADMAP/docs phải có thật (**100 đường dẫn đã kiểm, 0 lỗi**); mọi lệnh `python …py` trong
   khối code được phân loại: script repo **thiếu** ⇒ LỖI, script có nhưng **không argparse** ⇒ CẢNH BÁO
   (không phải lỗi), `--run-help` chạy thật `--help` với timeout và đòi rc ∈ {0, 3}. Repo thật:
   **264 lệnh / 9 script repo / 4 script có argparse đã chạy `--help` (rc=0 cả 4) / 5 cảnh báo / 0 lỗi**.

### 8.2 Số của đợt 2 (đều tái lập được bằng §8.7)

| Phép đo | Kết quả | Nguồn |
|---|---|---|
| 6 file test T7 chạy cùng nhau | **141 passed, 2 skipped** (143 collected), 15,25 s | `tmp/pytest_t7_dot2_tests.txt` |
| Harness mutation đợt 2 | baseline rc=0: **108 passed, 2 skipped, 7 deselected** (5,19 s) | `tmp/mutation_check_t7_dot2.log` |
| Đột biến đợt 2 | **20/20 bắt được, 0 lọt**, mọi file hoàn nguyên byte-identical (SHA-256) | `tmp/mutation_check_t7_dot2.log` |
| `docs_consistency_check --scope all --run-help` | **29 dòng sổ** (D-01…D-29) · 0 lỗi · 100 đường dẫn · 264 lệnh · 4 help · **5 cảnh báo** | `tmp/docs_check_t7_dot2.json` — sổ đã lên **30 dòng** sau khi ghi D-30 (`tmp/docs_check_t7_dot3.json`, vẫn 0 lỗi) |
| `tmp_cleanup` (chế độ mặc định) | 164 mục · **95 GIU vì được trích dẫn** · 69 đề xuất xoá · 26,4 MB · `deleted=[]`, `applied=false`, mode `DRY-RUN (không xoá gì)` | `tmp/cleanup_report_t7.json` |
| r0 công bố vs tính lại | gold@6 **0,5186** = 51,86% (363/700 item vàng, n=811) | `gate.metrics(data/loop/rounds/r0/retrieval.jsonl)` |
| Toàn repo (sau khi chuỗi tái lập xong, không contention) | **1.228 passed, 4 skipped**, 36,68 s (`tmp/pytest_t7_dot2_final.txt`) | rc=0; 4 skip = 2 test **slow** T4 (cần `T4_RUN_SLOW=1`) + 2 test symlink thường (Windows không có quyền tạo symlink) — 2 test **junction** vẫn chạy và là bằng chứng của M12/M14 |
| Chữ ký trọng tài (trước và sau đợt 2) | **`9f1179ccab74`** | `verify.referee_fingerprint()` |

### 8.3 Mutation check đợt 2 — 20/20, trên **bản sao** (không đụng cây thật)

Harness: [`tmp/mutation_check_t7_dot2.py`](../../tmp/mutation_check_t7_dot2.py) — copy `src/`, `tools/`,
`tests/conftest.py` và 5 file test sang `tmp/mut7_tree/`, đặt `venv/Scripts/python.exe` giả để
`_rel(PYTHON)` vẫn là đường dẫn tương đối, chạy pytest trong đó với `-k "not RepoThat"`.
Lý do dùng bản sao (như T6): `tools/loop/gate.py` và 6 file dirty PA-26 không được phép bị đột biến
dù chỉ là tạm thời.

| # | File bị đột biến | Tính chất bị phá | Test phải đỏ | Kết quả |
|---|---|---|---|---|
| M1 | `run_chain.py` | `--dry-run` vẫn chạy chuỗi thật | `TestDryRun.test_dry_run_khong_goi_subprocess` | BẮT (rc=1) |
| M2 | `run_chain.py` | preflight bỏ sót biến bắt buộc **cấp bước** | `TestDryRun.test_thieu_bien_bat_buoc_o_giua_chuoi_dung_truoc_buoc_dau` | BẮT |
| M3 | `run_chain.py` | env cấp bước bị `defaults` cấp chuỗi đè (ưu tiên sai) | `TestThuTuuEnvVaManifest.test_the_hien_thu_mack_dinh_khong_bi_set_che` | BẮT |
| M4 | `run_chain.py` | manifest có timestamp ⇒ hai lần chạy khác bytes | `TestThuTuuEnvVaManifest.test_hai_lan_chay_cung_manifest_bytes` | BẮT |
| M5 | `run_chain.py` | thư mục round đã có dữ liệu vẫn bị ghi đè (mục 2) | `TestThuMucRound.test_thu_muc_da_co_du_lieu_bi_tu_choi_va_khong_ghi_de` | BẮT |
| M6 | `run_chain.py` | gate lỗi hạ tầng (không báo cáo) vẫn đi tiếp | `test_run_chain.test_run_chain_gate_failure_without_report_stops_chain` | BẮT |
| M7 | `run_chain.py` | spec được nhét `GEMINI_API_KEY` ⇒ lộ bí mật vào manifest | `TestChanBiMatTrongSpec.test_key_api_trong_spec_bi_tu_choi` | BẮT |
| M8 | `cache_policy.py` | đổi ngưỡng cứu/từ chối vẫn tái dùng cache cũ | `TestDoiNguongKhongTaiDung.test_doi_nguong_tao_entry_moi` | BẮT |
| M9 | `cache_policy.py` | thể chế mặc định cũng gắn `policy` ⇒ mất entry cache cũ (phạm bất biến #2) | `TestMacDinhGiuKhoaCu.test_khoa_cache_khong_chua_truong_policy_khi_mac_dinh` | BẮT |
| M10 | `cache_policy.py` | `RESCUE_MIN_SCORE` bị hard-code trong snapshot | `TestDoiNguongKhongTaiDung.test_doi_nguong_tao_entry_moi` | BẮT |
| M11 | `tmp_cleanup.py` | chế độ liệt kê mặc định vẫn xoá thật | `TestMacDinhChiLietKe.test_khong_co_yes_khong_xoa_bat_cu_thuoc_nao` | BẮT |
| M12 | `tmp_cleanup.py` | bỏ chặn vùng bảo vệ ⇒ xoá được `outputs/` qua `..`/junction | `TestDanChungVaSymlink.test_tmp_chinh_no_la_junction_ra_vung_bao_ve_bi_chan` | BẮT |
| M13 | `tmp_cleanup.py` | mục được trích dẫn trong báo cáo vẫn bị xoá | `TestDanChungVaSymlink` | BẮT |
| M14 | `tmp_cleanup.py` | không nhận diện symlink/junction ⇒ đi ra ngoài repo | `TestDanChungVaSymlink.test_junction_trong_tmp_dan_den_muc_khac_trong_tmp_van_bi_chan` | BẮT |
| M15 | `docs_consistency_check.py` | nguồn trong sổ không cần tồn tại trên đĩa | `TestDuongDanNguonTonTai.test_nguon_khong_co_that_bi_bat` | BẮT |
| M16 | `docs_consistency_check.py` | số đo được phép không chứa con số nào | `TestSoQuyetDinhDuTruong.test_so_do_khong_chua_con_so_bi_bat` | BẮT |
| M17 | `docs_consistency_check.py` | mục sổ được phép thiếu ngày | `TestSoQuyetDinhDuTruong.test_thieu_ngay_bi_bat` | BẮT |
| M18 | `docs_consistency_check.py` | README nhắc file không có thật vẫn xanh | `TestFileDuocNhcPhaiTonTai.test_nhac_file_khong_co_that_bi_bat` | BẮT |
| M19 | `docs_consistency_check.py` | lệnh trỏ script không tồn tại bị bỏ qua | `TestLenhPhaiChayDuoc.test_lenh_tro_script_khong_co_file_la_loi` | BẮT |
| M20 | `docs_consistency_check.py` | mọi script đều được coi là có `--help` ⇒ mất cảnh báo onboarding | `TestLenhPhaiChayDuoc.test_script_khong_argparse_chi_la_canh_bao` | BẮT |

**Lượt đầu KHÔNG phải 20/20.** M12 và M14 **lọt** — vì `check_target()` chặn bằng ba lớp **dư thừa**:
bỏ lớp "vùng bảo vệ" thì lớp "realpath phải nằm trong `tmp/`" vẫn chặn, nên bộ test cũ không phân
biệt được lớp nào đang làm việc. Xử lý: thêm hai test **cô lập từng lớp** bằng junction thật
(`mklink /J`, không cần quyền admin) — `test_junction_trong_tmp_dan_den_muc_khac_trong_tmp_van_bi_chan`
(nối lớp a) và `test_tmp_chinh_no_la_junction_ra_vung_bao_ve_bi_chan` (nối lớp c) — rồi chạy lại:
**20/20**. Không nới lỏng checker hay xoá test nào để đạt con số.

### 8.4 Nghiệm thu "người ngoài chạy lại được r0 với cùng số gold@6" — **ĐẠT, tái lập từng item**

Tiêu chí đề bài: *"người ngoài chạy theo README trên bản clone mới và tái lập được ít nhất round
retrieval-only r0 với cùng số gold@6"*. Kiểm ở hai mức:

**Mức 1 — tính lại từ artifact đã đóng (chỉ đọc, 0 model).** `gate.load_rows(data/loop/rounds/r0,
"retrieval")` → `gate.metrics(...)`: **n=811, n_gold_items=700, gold@6 = 0,5186** — trùng số đã công bố
(51,86%, `data/loop/README.md`). Lưu ý định nghĩa: phải dùng `gate.metrics` (mẫu số = item **có** chunk
vàng), **không** dùng `run_round.gold_in_context_flags()` — hàm đó ép `True` cho item không có chunk vàng
nên cho số khác; đây là chỗ dễ đọc sai nhất của chỉ số này.

**Mức 2 — chạy lại round thật bằng MỘT lệnh, không đụng dữ liệu cũ.**

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/run_chain.py \
  --chain tools/loop/chains/t7_repro_r0.json
```

Spec ghim **đúng thể chế r0** (`ENABLE_CLASSIFIER=1`, `ENABLE_ANSWER_GUARD=1`, `ROUTER_SOFT_FILTER=0`,
`ROUTER_FILTER_RANK_BONUS=3`, `ROUTER_SOURCE_QUOTA=0`, `ENABLE_ANSWER_RESCUE=0`, `RESCUE_MIN_SCORE=0.8`)
và **khai báo tường minh mọi lever sinh sau r0 đang TẮT** (guard/decoupled/evidence/header/reranker) —
r0 chạy trước khi các lever đó tồn tại, nên "TẮT" là cách đúng để tái lập. Ghi vào
`tmp/rounds_t7_repro/r0_repro/` (không phải `data/loop/rounds/`), generator `offline_qwen` cho pha
truy xuất ⇒ **0 lượt Gemini**.

So sánh 3 tầng bằng `tmp/compare_r0_repro.py` (script **chỉ-đọc**, tự kiểm bằng phép cộng khớp:
`agree + flips = n_chung`; đã smoke-test bằng cách so r0 với chính nó ⇒ 811/811 trùng):

| Tầng so sánh | Kết quả | Nghĩa |
|---|---|---|
| gold@k theo cổng | gốc **0,5186** · tái lập **0,5186** (n=811, 700 item vàng cả hai bên) | **cùng số gold@6** — đúng tiêu chí |
| verdict từng item | **811/811 trùng**, **0 đổi chiều**; `FAIL_RETRIEVAL` 337 = 337, `PENDING_GENERATION` 474 = 474 | không những cùng *tỷ lệ* mà cùng cả *tập item* |
| top-6 chunk id (thứ tự) | **811/811 giống hệt từng phần tử theo hạng** | tầng truy xuất tất định: không "đạt nhờ bù trừ lệch" |
| thời gian | 16:36:00 → 17:13:31 = **37,5 phút**; median tái lập **2,71 s/item**, p95 2,92 | median r0 tự đo là **2,76 s/item** (`data/loop/rounds/r0/round_summary_retrieval.json`); 811 × 2,76 ≈ 37,3 phút ⇒ cùng bậc, lệch 0,05 s/item là dao động máy chứ không phải khác thuật toán (bằng chứng khác thuật toán sẽ nằm ở cột top-6, và cột đó trùng 811/811) |

**Hai phát hiện phụ (ghi nguyên, không che):**

1. Manifest của lượt chạy thật và manifest của `--dry-run` **trùng SHA-256**
   (`295413c196de…`) ⇒ những gì dry-run in ra chính là những gì đã chạy.
2. Điểm lệch từng item từng thấy ở lượt demo ĐỢT 1 (item `T269724694329437`: demo có chunk vàng 245 ở
   hạng 1, r0 không có) **không phải nhiễu truy xuất** mà là **khác thể chế**: demo dùng
   `chains/demo_dryrun.json` đặt `ENABLE_CLASSIFIER=0` (mặc định `.env.example` cũng là 0) còn r0 chạy
   với classifier **1**. Bằng chứng: `tmp/chain_demo3/demo_a/round_summary_retrieval.json`
   (`enable_classifier = "0"`, `families = CLOZE`, `split = test`) vs
   `data/loop/rounds/r0/round_summary_retrieval.json` (`enable_classifier = "1"`), và top-6 của hai bên
   là hai tập chunk khác hẳn (`[245,10,257,…]` vs `[99,106,100,…]`). Đây chính là **lý do spec phải ghim
   env và manifest phải in env**: một chuỗi "trông giống" nhưng sai classifier sẽ cho số khác, và sai
   đó nhìn được ngay trong manifest.

**Phần tiêu chí vẫn CHƯA đạt** (không tô vẽ): trên **fresh clone** vẫn chạy lại được r0 *sau khi* (a) chọn
phương án commit freeze PA-26 để bộ test + `tools/loop/*` có mặt, và (b) dựng index — `chroma_db/` đang
gitignore ⇒ người mới **buộc** chạy `python ingest.py`, mà lệnh đó xoá index tại chỗ, không dry-run
(PA-29). Chuỗi tái lập này dùng `out_root=tmp/` nên không chứng minh đường đi "clone → ingest → r0".


### 8.5 Sự cố bằng chứng trong đợt 2 — ghi nguyên, không che

**Sự cố 1 — ghi đè harness/log mutation của đợt 1.** Khi đặt harness 20 đột biến tôi tái dùng đúng tên
`tmp/mutation_check_t7.py` + `tmp/mutation_check_t7.log`, tức là **xoá** bằng chứng 6/6 mà D-22 và §2.3
đang dẫn. `tmp/` không nằm trong git nên không có `git checkout` nào cứu được. Đã khắc phục theo đúng
cách từng dùng ở T6:

1. trích lại nội dung file từ transcript phiên (`Write` lượt #1413) và đối chiếu với **snapshot Read**
   lượt #1578 ⇒ `unified_diff` = **0 khác biệt** (chỉ khác newline cuối);
2. khôi phục `tmp/mutation_check_t7.py` đúng byte và `tmp/mutation_check_t7.log` đúng 8 dòng output
   (baseline 11 passed/0,22 s + M1–M6 BẮT ĐƯỢC + tổng kết 6/6);
3. **chạy lại chính harness vừa khôi phục** (log mới: `tmp/mutation_check_t7_rerun_dot2.log`) ⇒ rc=0,
   baseline `11 passed in 0,33s`, **6/6 BẮT ĐƯỢC**, `tools/loop/run_chain.py` vẫn `bf13918a…`.
   Bằng chứng do đó không còn là "text khôi phục từ transcript" mà là **phép đo mới tái lập đúng**
   con số ĐỢT 1 đã công bố (chỉ khác thời gian baseline 0,22 s → 0,33 s vì chuỗi 811 item đang chạy nền);
4. đổi harness đợt 2 sang `tmp/mutation_check_t7_dot2.py`/`.log` — từ giờ **artifact kiểm kê/mutation
   phải mang tên đợt** trong tên file;
5. xác nhận bằng chứng còn **áp dụng cho code hiện tại**: SHA-256 ba file đợt 1 đã ghi vẫn trùng
   (`tools/loop/run_chain.py` `bf13918a…`, `src/cache_policy.py` `652477e3…`, `src/generator.py`
   `d3791b44…`), nên log 6/6 không phải mô tả một phiên bản đã mất.

**Sự cố 2 — snapshot kiểm kê `tmp/` bị ghi đè.** `tmp/cleanup_report_t7.json` của đợt 1 (104 mục,
92,1 MB) bị lượt đợt 2 ghi đè thành 164 mục/26,4 MB đề xuất. Khác biệt là **đúng bản chất** (`tmp/` lớn
lên giữa phiên vì chính các lượt kiểm thử sinh thêm log/bản sao), nhưng nó cho thấy dẫn một file
kiểm kê "sống" làm bằng chứng là không bền. PA-24 vẫn giữ con số đợt 1 như một **ảnh chụp có ngày
giờ**; đề xuất cho PA-24: khi xoá thật, chạy kiểm kê mới và so hai ảnh chụp.

**Bài học (đã ghi `docs/AUTONOMY_LOG.md`):** đây là lần **hai** cùng một lỗi (T6 đợt 2 rồi T7 đợt 2).
Nguyên tắc mới tự áp: trước khi ghi vào `tmp/` một tên đã tồn tại, kiểm `ls` + nếu tên đó được tài
liệu dẫn thì **thêm hậu tố đợt**, không ghi đè.

### 8.6 Điều đợt 2 vẫn không chứng minh được

- **5 script không argparse** (`ingest.py`, `learn.py`, `src/analyze_ab.py`, `demo_streamlit.py`,
  `ui/app.py`) ⇒ mục 6 chỉ kiểm được **cấu trúc lệnh**, không kiểm được
  `--help`/dry-run. Đáng chú ý nhất: `ingest.py` rebuild index và **không có dry-run**, nên câu lệnh
  trong README không "chạy thử an toàn" được ⇒ **PA-29**.
- `python ui/app.py` là GUI Tkinter: mở cửa sổ, không tự thoát ⇒ checker không chạy nó, chỉ phân loại
  và cảnh báo. Không giả lập "GUI chạy được".
- Test ghim `--run-help` trên repo thật
  (`TestRepoThatChiDoc.test_script_repo_doc_nhom_argparse_deu_in_duoc_help`) chạy `--help` của 4 script
  thật bằng `subprocess.run(..., timeout=90, stdin=DEVNULL)` **kế thừa env hiện hành** và `cwd=root`.
  Hai điều phải biết khi đọc kết quả: (a) 4 script đó **import SDK Gemini ở đầu file** (dòng
  `import google.generativeai as genai` hiện trong `stderr_tail` của 3/4 ca) ⇒ test nạp thư viện,
  nhưng `--help` làm argparse in rồi thoát **trước khi** gọi API ⇒ **0 request, 0 lượt Gemini**
  (tổng thời gian 6 file test T7 vẫn 15,4 s, `tmp/pytest_t7_dot2_tests.txt`); (b) vì kế thừa env,
  nếu `.env` được `load_dotenv()` nạp thì key vẫn nằm trong process — checker **không** tự xoá env,
  đây là điểm nên siết (đã ghi là việc của PA-29/`test_final.md`, không âm thầm sửa hành vi đã test).
- Mục 3 nghiệm thu bằng **stub đếm cuộc gọi**, không phải Ollama/Gemini thật: chưa có một round sinh
  thật nào đổi ngưỡng rồi thấy entry cũ bị bỏ qua (§4.1 vẫn đúng).
- Mục 4 chưa xoá gì; junction/symlink chỉ chặn, chưa có chế độ "chuyển vào thùng rác".
- Sổ quyết định và docs: checker **không** đọc nội dung để xác nhận số đo **đúng**, chỉ xác nhận
  số đo **có tồn tại và nguồn có thật**. Chéo số là việc của Phụ lục A và `test_final.md`.
- Chuỗi ngày/đêm nhiều spec, hai chuỗi song song (không khoá file), resume ở quy mô 811 item (§4.3).
- **PA-26 vẫn mở**: fresh clone thiếu file ⇒ tiêu chí "người ngoài chạy theo README trên bản clone
  mới" chỉ đạt ở mức **artifact + công cụ**, không đạt ở mức repo.

### 8.7 Lệnh tái lập đợt 2

```bash
# 106 test mới + 37 test đợt 1 (143 test T7)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  tests/test_t7_chain_env_manifest.py tests/test_t7_cache_reuse_e2e.py \
  tests/test_t7_tmp_cleanup.py tests/test_t7_docs_consistency.py \
  tests/test_run_chain.py tests/test_cache_policy.py -q

# Sổ quyết định + đường dẫn + lệnh trong tài liệu (0 lỗi, 5 cảnh báo)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/docs_consistency_check.py \
  --scope all --run-help --json tmp/docs_check_t7_dot2.json

# Kiểm kê tmp/ mặc định (không xoá gì)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/tmp_cleanup.py \
  --json tmp/cleanup_report_t7.json

# 20/20 đột biến trên BẢN SAO (tự hoàn nguyên, so SHA-256)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t7_dot2.py

# dry-run của chuỗi tái lập r0 — in 1 lệnh + 13 biến env, không chạy gì
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/run_chain.py \
  --chain tools/loop/chains/t7_repro_r0.json --dry-run --manifest-out -

# tính lại gold@6 của r0 từ artifact đã đóng (chỉ đọc; dùng đúng API của cổng)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c "import sys,pathlib; sys.path.insert(0,'tools/loop');\
import gate; rows=gate.load_rows(pathlib.Path('data/loop/rounds/r0'),'retrieval');\
m=gate.metrics(list(rows.values())); print(m['n'], m['n_gold_items'], m['gold_in_top_k_rate'])"

# so sánh round tái lập với round đã đóng ở 3 tầng (chỉ đọc; tmp/compare_r0_repro.py)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/compare_r0_repro.py \
  data/loop/rounds/r0 tmp/rounds_t7_repro/r0_repro tmp/compare_r0_repro.json
```

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

## Phụ lục A2 — số **đợt 2** | số tính lại | khớp

Mọi dòng dưới đây đã được tính lại bằng lệnh công khai (không dựa vào bộ nhớ của phiên);
cột "Cách tính lại" chạy **sau** khi ghi báo cáo, nên nếu số đổi chứng minh báo cáo sai.

| Số công bố (đợt 2) | Cách tính lại | Kết quả tính lại | Khớp |
|---|---|---|---|
| 106 test mới của đợt 2 | `pytest --collect-only -q` trên 4 file `test_t7_{chain_env_manifest,cache_reuse_e2e,tmp_cleanup,docs_consistency}.py` | **106 tests collected** (19+18+33+36) | có |
| 143 test T7 (đợt 1 + đợt 2) | `--collect-only -q` thêm `test_run_chain.py` (11) + `test_cache_policy.py` (26) | 106 + **37** = 143 | có |
| 141 passed, 2 skipped, 15,25 s | `tail -3 tmp/pytest_t7_dot2_tests.txt` | `141 passed, 2 skipped, 3 warnings in 15.25s` | có |
| 1.228 passed, 4 skipped, 36,68 s toàn repo | `tail -3 tmp/pytest_t7_dot2_final.txt` | `1228 passed, 4 skipped, 3 warnings in 36.68s` | có — **chạy lại lần hai** (17:3x, sau khi ghi D-30 + Phụ lục A2): vẫn **1.228 passed, 4 skipped**, 33,24 s (`tmp/pytest_t7_dot3_final.txt`) |
| 20/20 đột biến đợt 2, 0 lọt | `tail -2 tmp/mutation_check_t7_dot2.log` | `20/20 bắt được, 0 lọt; mọi file hoàn nguyên byte-identical (SHA-256 khớp)` | có |
| 6/6 đột biến đợt 1 **chạy lại** sau sự cố ghi đè | `tail -2 tmp/mutation_check_t7_rerun_dot2.log` | `6/6 đột biến bị bắt; file gốc nguyên vẹn` | có |
| 16/16 (đính chính của "17/17") | 6 (`run_chain`) + 10 (`cache_policy`) từ hai log đợt 1 | 16 | có |
| `docs_consistency_check`: 29 dòng sổ · 264 lệnh · 9 script repo · 100 đường dẫn · 5 cảnh báo · 0 lỗi | gọi lại `check_all(root, run_help_checks=False)` + đếm `referenced_paths()` | 29 · 264 · 9 · **100** · 5 · 0 | có — chạy **ngay sau đó** (sau khi thêm D-30) cho **30 dòng · 0 lỗi · vẫn 5 cảnh báo**, `tmp/docs_check_t7_dot3.json` |
| 4 lệnh `--help`, 0 lỗi help | `tmp/docs_check_t7_dot2.json` (`help_checked`, `help_problems`) | 4 · 0 | có |
| `tmp_cleanup` mặc định: 164 mục · 95 GIU · 69 đề xuất xoá · 26,4 MB · không xoá gì | `summary` + `deletion` trong `tmp/cleanup_report_t7.json` | `n_items=164`, `n_kept_cited=95`, `n_proposed_delete=69`, `bytes_proposed=26410968` (= 26,41 MB), `deleted=[]`, `applied=false` | có |
| gold@6 r0 công bố = 51,86% | snippet `gate.load_rows(...,'retrieval')` + `gate.metrics(...)` ở §8.7 | `811 700 0.5186` | có |
| Tái lập r0: 811/811 verdict trùng, 0 đổi chiều, 811/811 top-6 đúng thứ tự | các khoá top-level của `tmp/compare_r0_repro.json` | `n_common=811`, `verdict_agree=811`, `verdict_flips=0`, `top6_exact_order=811`, `n_only_base=0`, `n_only_repro=0`, `reconciliation_ok=true` | có |
| gold@k hai bên cùng 0,5186 | `metrics_base` vs `metrics_repro` trong cùng file | `0.5186` = `0.5186`, `n_gold_items` 700 = 700 | có |
| Manifest `--dry-run` trùng bản chạy thật | `run_chain.py --chain tools/loop/chains/t7_repro_r0.json --dry-run --manifest-out tmp/t7_manifest_probe_dot2.json` rồi so SHA-256 với `data/loop/diag/chain_manifest_t7_repro_r0.json` | `295413c196de` = `295413c196de`, **byte-identical** | có |
| Thời gian tái lập 37,5 phút; median r0 | `generated_at` của `tmp/rounds_t7_repro/r0_repro/round_summary_retrieval.json` (16:36 → 17:13:31) và `median_latency` hai bên | 37,5 phút; r0 **2,76** / tái lập **2,71** s/item (p95 2,92) | có (cùng bậc; §8.4 đã sửa câu "37,6 phút / mean 2,78" vì 2,78 là median của **r11**, không phải r0) |
| Chữ ký trọng tài không đổi sau đợt 2 | `verify.referee_fingerprint()` | `9f1179ccab74` | có |
| `gate.py` không bị sửa một byte | (a) `sha256(tools/loop/gate.py)` tính lại; (b) `grep -oP` danh sách file bị đột biến trong `tmp/mutation_check_t7_dot2.log` | `bf4bda89d8a360abbba25742…`; chỉ 4 file từng bị đột biến: `tools/loop/run_chain.py`, `src/cache_policy.py`, `tools/diag/tmp_cleanup.py`, `tools/diag/docs_consistency_check.py` — **không có `gate.py`** | có — kèm lưu ý: `gate.py` **chưa được git theo dõi** (PA-26) nên không đối chiếu được với HEAD, chỉ đối chiếu được bằng SHA tự ghi ở đây |
