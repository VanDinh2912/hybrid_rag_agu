# Báo cáo kiểm thử — T6: làm kết luận đứng được trước hội đồng

Ngày: 2026-10-25 (đợt 1 tổng hợp từ 24-10; **đợt 2 = 60 test theo đề bài T6 mới**, xem §8).
Nhánh `auto/overnight`.
Phạm vi: **test cho các đơn vị T6** — 6a cổng refusal tương đối (bản đề xuất), 6c khung câu hỏi thật;
đối chiếu số của 6b/6d. **KHÔNG sửa `tools/loop/gate.py`**, KHÔNG sửa trọng tài
(`tools/loop/verify.py`, `src/answer_guard.py`, `src/text_utils.py`) — chữ ký vẫn
`9f1179ccab74`; KHÔNG chấm lại round; **0 lượt Gemini**.

## 1. Đã làm gì

### 1.1 6a — cổng refusal tương đối (`tests/test_gate_refusal_relative_proposal.py`, **9 test**)

Bản tạm `tools/diag/gate_refusal_relative_proposal.py` mô phỏng luật **đề xuất**, không import
`gate.py`. Test ghim cả hai nhánh:

- **Tương đối (phủ quyết):** `candidate <= baseline + 0.05` ⇒ ĐẠT; vượt ⇒ BỊ. Đúng biên (candidate =
  baseline + delta) ĐẠT; vượt 0,0001 BỊ — test biên này được **bổ sung sau mutation** (xem §2.2).
- **Thiếu baseline:** `không đo được = CẤM` (`ok=False`), không im lặng ĐẠT.
- **Trần tuyệt đối 0,35:** chỉ sinh **warning**, không nằm trong `checks` nên không phủ quyết; đúng 0,35
  không warning, 0,36 có warning.
- **Pha retrieval** (candidate `None`): luật không áp dụng, không thêm check/warning.
- **Tham số hoá delta:** cùng 0,40 vs 0,30, delta 0,05 ⇒ BỊ; delta 0,15 ⇒ ĐẠT.

### 1.2 6c — khung câu hỏi thật (`tests/test_score_real_questions.py`, **6 test**)

`tools/eval/score_real_questions.py` chấm từng câu qua pipeline (stub trong test), phát hiện từ chối
bằng `verify.is_refusal`, chấm grounding bằng `check_grounding` với `extra_haystack` = tên nguồn. Test
ghim:

- câu có căn cứ ⇒ `is_refusal=False`, `grounding_score ≥ 0,5`, cột người đọc để trống;
- câu từ chối đúng (`REFUSAL_TEXT`) ⇒ `is_refusal=True`, grounding `None`;
- **giữ nguyên** nhãn tay `co_giup_duoc_khong`/`ghi_chu` đã điền (không xoá công người label);
- `help_rate_ci` trả `n`, `mean`, CI chứa mean, ghi chú "CI RỘNG";
- `summarize` đếm đúng `n_human_labeled` (chỉ dòng có nhãn hợp lệ) và `n_fabricated_any`;
- `real_questions` lọc dòng `example` (khi không yêu cầu) và câu hỏi rỗng.

### 1.3 6b/6d — chỉ có công cụ, chưa có unit test

- **6b** `tools/diag/referee_agreement.py` (Cohen's kappa, precision/recall/F1, ma trận nhầm lẫn) và
  `tools/diag/referee_sample.py`: **không có file test riêng** ở đợt 24-10. Việc kiểm định trọng tài vẫn
  **chưa thể kết luận** vì phiếu 60 mẫu có `n_filled=0`.
- **6d** `tools/diag/metric_ci.py`: **không có file test riêng**; số CI được đối chiếu bằng đọc file JSON
  và `point_matches_gate=true` trong chính output.

Đây là khoảng trống được ghi nhận, **không** che bằng cách sửa test cũ (§4.3). **Khoảng trống 6b đã được
lấp ở đợt 2** (§8.4): `referee_agreement.py` + `referee_sample.py` giờ có 10 test; `metric_ci.py` vẫn
chưa có test riêng (chỉ có test cho `tools/eval/report_metrics.py` — xem §8.5).

## 2. Kết quả số (nguồn: file trên đĩa)

### 2.1 Số test

| Lần chạy | Kết quả | Nguồn |
|---|---|---|
| Hai file T6 (baseline mutation) | **15 passed**, 1 warning (0,85 s) = 9 + 6 | `tmp/mutation_check_t6.log` dòng `[baseline]` |
| Riêng 6a | 9 passed (0,02 s) | `pytest tests/test_gate_refusal_relative_proposal.py -q` |
| Riêng 6c | 6 passed (1,33 s) | `pytest tests/test_score_real_questions.py -q` |
| Toàn repo sau T4/T6 | **1.005 passed**, 3 warnings (28,27 s) | `tmp/pytest_t4t6_final.txt` |
| Chữ ký trọng tài | `9f1179ccab74` (không đổi) | `tmp/pytest_t4t6_final.txt` dòng cuối |

### 2.2 Mutation check — 10/10 bị bắt, 10/10 hoàn nguyên byte-identical

Nguồn: [`tmp/mutation_check_t6.log`](../../tmp/mutation_check_t6.log). Không đột biến `verify.py`
(trọng tài) và `gate.py` (dụng cụ đo).

| Đột biến | Tính chất bị phá | Test đỏ tiêu biểu | Hoàn nguyên |
|---|---|---|---|
| T6a-M1 `<=` → `<` | hoà đúng ngưỡng bị veto oan | `test_hoa_dung_nguong_tuong_doi_van_dat_vuot_mot_chut_thi_bi` | có |
| T6a-M2 thiếu baseline → `ok=True` | không đo được mà im lặng ĐẠT | `test_missing_baseline_is_forbidden_not_silent_pass` | có |
| T6a-M3 trần tuyệt đối `>` → `>=` | cảnh báo cả khi đúng 0,35 | `test_absolute_ceiling_default_is_035` | có |
| T6a-M4 bỏ miễn pha retrieval | candidate `None` gây lỗi thay vì bỏ qua | `test_retrieval_phase_no_candidate_rate_adds_nothing` | có |
| T6c-M5 bỏ lọc `example` | câu ví dụ lọt vào tập đo | `test_real_questions_filters_examples_and_blanks` | có |
| T6c-M6 giữ câu hỏi rỗng | câu rỗng thành một lượt chấm | cùng test | có |
| T6c-M7 `is_refusal=False` | không phát hiện câu từ chối | `test_score_one_detects_refusal` | có |
| T6c-M8 xoá nhãn tay | mất công người đọc | `test_preserves_existing_human_label` | có |
| T6c-M9 đếm mọi dòng là có nhãn | thổi phồng `n_human_labeled` | `test_summarize_counts_labeled_rows` | có |
| T6c-M10 `help_rate_ci` trả rỗng | có điểm vẫn báo `n=0` | `test_help_rate_ci_counts_and_bounds` | có |

**Lần chạy đầu, T6a-M1 sống sót** (9/10): các case cũ chỉ thử *trong lòng* ngưỡng, chưa thử đúng biên.
Đã **thêm một test biên mới** (không sửa kỳ vọng của test cũ) rồi chạy lại: 10/10. Đây là ví dụ mutation
check làm lộ lỗ hổng thật, không phải test trang trí.

SHA-256 các file nguồn trước = sau (kiểm độc lập bằng `diff` ngoài script): `gate_refusal_relative_proposal.py`,
`score_real_questions.py` (và hai file T4).

### 2.3 6d — CI các chỉ số chính (nguồn: `data/loop/diag/metric_ci_r{5,7}_full.json`)

| Chỉ số | r7 điểm | r7 CI 95% | r5 điểm | r5 CI 95% |
|---|---:|---|---:|---|
| `PASS_CORRECT` | 0,14 | [0,08 ; 0,21] | 0,14 | [0,07 ; 0,21] |
| `pass_rate` | 0,32 | [0,23 ; 0,41] | 0,31 | [0,22 ; 0,40] |
| `refusal_rate` | 0,62 | [0,52 ; 0,71] | 0,69 | [0,60 ; 0,78] |
| `gold_in_top_k_rate` (n=80) | 0,80 | [0,71 ; 0,89] | 0,74 | [0,64 ; 0,83] |
| `fabrication_rate_on_answered` | 0,026 | [0,00 ; 0,08] | 0,032 | [0,00 ; 0,10] |
| `mean_grounding_score` | 0,996 | [0,987 ; 1,000] | 0,995 | [0,984 ; 1,000] |

Point estimate dùng đúng công thức mẫu số của `gate.metrics`; output ghi `point_matches_gate=true` cho
mọi chỉ số dùng chung. Tổng điểm trọng số tính lại:
`0,20·9,2 + 0,15·8,2 + 0,20·7,0 + 0,20·8,5 + 0,25·4,0 = 7,17 → 7,2` (bản cũ ghi 7,4 là sai số học).

### 2.4 6b — mẫu kiểm định trọng tài (chưa có nhãn)

| Đại lượng | Giá trị | Nguồn |
|---|---:|---|
| Mẫu phân tầng từ r5 | **60** = dung 14 / tu_boi_dung 15 / tu_boi_oan 15 / sai 16 | `data/loop/diag/referee_sample_manifest.json` |
| Nguồn khả dụng trước lấy mẫu | 14 / 17 / 37 / 32 | cùng file |
| `n_filled` | **0** | `data/loop/diag/referee_labeling_r5.jsonl` |
| Kappa / precision / recall | **chưa tính được** | thiếu nhãn tay |

Không có số "trọng tài đúng X%" nào được công bố — đúng trạng thái `n_filled=0`.

### 2.5 6c — khung câu hỏi thật (dry-run)

```text
[T6c] câu thật chờ chấm = 0 (đã loại dòng ví dụ/trống). Số lượt pipeline dự kiến = 0 (generator=ollama).
[T6c] DRY-RUN: không gọi model. Điền câu thật vào real_questions.jsonl rồi chạy lại.
```

Nguồn: chạy `python -m tools.eval.score_real_questions --dry-run` ngày 25-10; file
`tools/eval/real_questions.jsonl` có 6 dòng = 1 schema + 2 ví dụ (`example:true`) + 3 dòng `RQ-EMPTY`.
Không có câu đời thật nào được chấm, **0 lượt model**.

## 3. Kết luận chỉ từ số

- Luật refusal **tương đối** giữ đúng cả hai nhánh và biên `<=`; trần tuyệt đối chỉ cảnh báo, không
  phủ quyết — đúng bản đề xuất. `gate.py` không bị chạm.
- Khung câu hỏi thật không gọi model khi chưa có câu thật (`--dry-run` = 0 lượt), giữ nhãn tay, phát
  hiện từ chối và grounding bằng stub xác định.
- 10/10 đột biến bị bắt sau khi bổ sung test biên ⇒ test 6a/6c có hiệu lực.
- CI cho thấy `PASS_CORRECT` r7 0,14 [0,08; 0,21] — **chưa đủ bằng chứng** để nói gần ngưỡng 25%;
  r5↔r7 CI chồng lấn trên mọi chỉ số ⇒ không diễn giải 0,31→0,32 thành tiến bộ.
- Chất lượng trọng tài và năng lực trên câu hỏi thật: **chưa đo được** (6b `n_filled=0`, 6c 0 câu).

## 4. Điều KHÔNG kết luận được / phần chưa kiểm

### 4.1 6b không có kết luận nào về trọng tài

60 mẫu đang chờ người gán nhãn. Không được nói "trọng tài chính xác X%" hay "kappa = Y" cho tới khi
`n_filled ≥ 1`; hiện tại chỉ có dụng cụ.

### 4.2 6c chưa chấm câu thật nào

Đây là **khung**, không phải benchmark. `check_grounding` còn mù lớp "có căn cứ nhưng lạc đề" (ghi ở
`tools/eval/README.md`); `help_rate_ci` là **định tính**, CI rất rộng với n nhỏ.

### 4.3 6b/6d thiếu unit test

`referee_agreement.py` (kappa, precision/recall/F1, confusion matrix) và `metric_ci.py` (`item_series`,
ghép mẫu số với `gate.metrics`) **chưa có test**. Rủi ro: sửa công thức có thể làm sai số báo cáo mà
không có test đỏ. Đề xuất bổ sung ở lượt sau (không tự thêm trong T6 vì phạm vi đã đóng và mọi số đã
được đối chiếu bằng đọc file).

### 4.4 6a là đề xuất, không phải hành vi production

`gate.py` vẫn dùng trần tuyệt đối 0,35; test chỉ chứng minh **bản tạm** đúng. Nghiệm thu thay đổi thật
phải chờ PA-13.

### 4.5 Bootstrap dùng một seed

CI trong 6d dùng seed `20261023`, 10.000 lượt (theo `noise_floor`); không chạy đa seed để kiểm độ ổn
định của CI. Đây là giới hạn phương pháp, không phải lỗi.

## 5. Tiêu chí xong

- "Mọi bảng chính có CI và nguồn file": **đạt** — §2.3 có CI + đường dẫn JSON; §2.4/§2.5 nêu rõ chỗ
  chưa có số.
- 6a không sửa gate/trọng tài: **đạt** — chữ ký `9f1179ccab74`; PA-13 vẫn treo.
- Toàn repo xanh: **1.005 passed** (`tmp/pytest_t4t6_final.txt`), không sửa test cũ để xanh.
- **Đợt 2** — "xanh + mutation check (đổi dấu so sánh trong cổng, bỏ kiểm chữ ký) bị bắt": **đạt** —
  60/60 test xanh, toàn repo **1.124 passed / 2 skipped** (`tmp/pytest_t6_final.txt`),
  M1 (đổi dấu) và M3 (bỏ kiểm chữ ký) đều bị bắt trong 10/10 (`tmp/mutation_check_t6_tests.log`).

## 6. Lệnh tái lập

```bash
# Hai file test T6
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  tests/test_gate_refusal_relative_proposal.py tests/test_score_real_questions.py -q

# Mutation check (10 đột biến, tự hoàn nguyên + kiểm SHA-256)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t6.py

# 6c dry-run: đếm lượt model trước khi tốn tài nguyên (kỳ vọng 0 câu thật)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m tools.eval.score_real_questions --dry-run

# 6d: tính lại CI cho r5/r7 (chỉ đọc round đã đóng, ghi vào data/loop/diag/)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/metric_ci.py --round r7 --phase full

# --- ĐỢT 2 (25-10) ---
# 60 test mới (mục 1–10 đề bài)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  tests/test_t6_gate_refusal_and_regression.py \
  tests/test_t6_referee_validation.py \
  tests/test_t6_real_questions_and_metrics.py -q

# Mutation check đợt 2 (copy-tree, KHÔNG sửa gate.py thật; tự hoàn nguyên + kiểm SHA-256)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t6_tests.py

# Xác nhận gate.py và trọng tài vẫn nguyên (chữ ký không đổi)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c \
  "from tools.loop import verify; print(verify.referee_fingerprint())"
```

## 7. Đề xuất cần duyệt

- **PA-13**: thay cổng refusal tuyệt đối bằng tương đối + cảnh báo (diff ở PENDING_APPROVAL; `gate.py`
  chưa đổi).
- **PA-23**: chốt lại điểm thành phần trong báo cáo đánh giá (7,2 đã đúng số học; điểm từng mục chờ
  duyệt).
- **PA-26**: commit freeze để báo cáo này tái lập được từ fresh clone.

## 8. ĐỢT 2 (25-10) — 60 test theo đề bài T6 mới, chưa đụng `gate.py`

Đề bài đợt này có 10 mục và một tiêu chí phụ: **xanh + mutation check (đổi dấu so sánh trong cổng, bỏ
kiểm chữ ký) bị bắt**. Vì `gate.py` chỉ được sửa **sau khi user duyệt**, toàn bộ test được viết **chống
vào bản đề xuất tách rời** (`tools/diag/gate_refusal_relative_proposal.py`) + hàm mô phỏng
`apply_to_gate_result()` áp luật mới lên **kết quả cổng đã công bố**, nên khi diff PA-13 được duyệt thì
chỉ cần trỏ lại, không viết test mới.

| File test | Test | Mục đề bài |
|---|---:|---|
| `tests/test_t6_gate_refusal_and_regression.py` | **28** | 1, 2, 3, 4, 5, 6 |
| `tests/test_t6_referee_validation.py` | **10** | 7 |
| `tests/test_t6_real_questions_and_metrics.py` | **22** | 8, 9, 10 |
| **Tổng đợt 2** | **60 passed** (0,72 s) | 1–10 |
| Toàn repo sau đợt 2 | **1.124 passed**, 2 skipped (26,92 s) | `tmp/pytest_t6_final.txt` |

Mốc baseline trước đợt 2 là 1.064 (`tmp/pytest_t5_final_2.txt`) ⇒ +60 = 1.124, **không sửa test cũ**.

### 8.1 Mục 1–4 — luật refusal tương đối

| Tình huống | Kỳ vọng đã ghim | Kết quả test |
|---|---|---|
| baseline 0,72 / candidate 0,69 | ĐẠT luật; **warning** "vượt trần tuyệt đối 0,35"; warning **không** nằm trong `checks` | xanh |
| baseline 0,72 / candidate 0,80 | KHÔNG ĐẠT (delta +0,08 > 0,05) | xanh |
| biên: +0,0499 / đúng +0,05 / +0,0501 | ĐẠT / ĐẠT (`<=`) / BỊ | xanh (parametrize 3 nhánh) |
| baseline `None` hoặc mẫu rỗng (`gate.metrics([])` → `n=0`) | **CẤM mở cổng**, thông báo chứa "KHÔNG ĐO ĐƯỢC" | xanh |
| `apply_to_gate_result()` với baseline `None` | cổng vẫn `passed=False` | xanh |

Hàm mô phỏng gỡ **đúng hai** ô cũ (`refusal_rate_bounded`, `refusal_rate_not_increased`), thay bằng ô mới
và bảng warning, tính lại `passed`, và **buộc** `passed=False` khi `config_mismatches` khác rỗng.

### 8.2 Mục 5 — ghim 6 quy tắc còn lại + cổng thật trên file đã công bố

Mỗi quy tắc có test biên riêng (đúng ngưỡng / vượt 0,0001) và test "thiếu chỉ số = CẤM":

| Quy tắc | Ngưỡng đã ghim | Test biên |
|---|---|---|
| `fabrication_not_increased` | delta 0,0 | +0,001 → BỊ |
| `no_new_hallucinated_refusal` | delta 0 | 2→2 ĐẠT, 2→3 BỊ |
| `pass_rate_not_dropped` | −0,02 | 0,78 ĐẠT, 0,7799 BỊ |
| `family_pass_rate` | −0,10, min n=8 | EXACT 0,80→0,70 ĐẠT, →0,6999 BỊ (key `family_pass_rate[EXACT]`); n=7 bị bỏ qua |
| `human_anchor_*_not_degraded` | −5% tương đối | 0,7601 ĐẠT / 0,7599 BỊ; thiếu neo → CẤM |
| `retrieval_not_degraded` | −0,02 | 0,78 ĐẠT / 0,7799 BỊ; thiếu gold@k → CẤM |

Cổng thật chạy lại **trên file đã đóng** (chỉ đọc; ghi `--out` vào `tmp_path`) — số công bố | số tính lại:

| Cổng | `passed` công bố | số liệu công bố | tính lại | khớp |
|---|---|---|---|---|
| r4 vs r2 (retrieval, 811 item) | **ĐẠT**, mismatch `[]` | gold 0,7400→0,7429; HUMAN anchor 0,8144/0,8144; refusal 0,0 | y nguyên, cùng 6 ô check | có |
| r5 vs r3 (full, 100 item) | **KHÔNG ĐẠT** | fabrication 0,0256→0,0323 BỊ; refusal 0,61→0,69 BỊ; còn lại ĐẠT | y nguyên | có |
| r5 vs r1 (full, 100 item) | **KHÔNG ĐẠT** | chỉ vướng refusal 0,72→0,69 | y nguyên | có |
| r3 vs r1 (full, 100 item) | **KHÔNG ĐẠT** | hallucinated 2→3 BỊ; refusal 0,72→0,61 BỊ | y nguyên | có |

**Đính chính đề bài (không hạ mức đỏ).** Đề bài ghi "chỉ pha sinh r5 đổi từ KHÔNG ĐẠT sang theo quy tắc
mới". Kiểm trên file thật thì **r5-vs-r3 không lật**: delta refusal **+0,08 > 0,05** và
fabrication vẫn tăng. Ca **duy nhất** lật sang ĐẠT là **r5-vs-r1** (0,69 vs 0,72 ⇒ ĐẠT luật mới + cảnh báo
trần tuyệt đối) — đã ghim bằng test. r3-vs-r1: luật mới làm ô refusal ĐẠT nhưng cổng vẫn KHÔNG ĐẠT vì
`no_new_hallucinated_refusal`. Các cổng retrieval phải y nguyên: **đúng**, r4-vs-r2 giữ ĐẠT và PA-13
simulation không đổi danh sách ô check.

### 8.3 Mục 6 — cổng từ chối mở khi chữ ký / cấu hình lệch

Test gọi `gate.main()` (monkeypatch `sys.argv`, `--out` vào `tmp_path`): chữ ký trọng tài lệch → thông
báo chứa "trọng tài", `passed=False`, rc 1; `generator` + `top_k` lệch → 2 problem; thiếu
`round_summary` → 1 problem; `GATE_ALLOW_CONFIG_MISMATCH=1` → rc 0 **nhưng** `config_mismatches` vẫn được
ghi (không xoá dấu vết).

### 8.4 Mục 7 — kiểm định trọng tài (10 test)

- `referee_sample.py` tách thành `build_label_rows()` / `build_manifest()` (hành vi không đổi). Test ghim:
  mẫu **60 dòng** phân tầng đúng 14/15/15/16 với seed 20261024, **tất định** khi chạy 2 lần; phiếu chỉ có
  8 cột `_huong_dan, sample_index, id, question, answer, evidence, nhan_tay, ghi_chu` — **không** có
  `verdict`, `referee_verdict`, `gold_chunk_id`, `gold_sentence`, `required_entities`, `grounding_score`,
  `severity`, `is_refusal`, `detail`; manifest riêng vẫn giữ verdict. Kiểm cả **file thật trên đĩa**
  `data/loop/diag/referee_labeling_r5.jsonl` (60 dòng, `nhan_tay` rỗng toàn bộ).
- `referee_agreement.py` tách thành `score_labels()` + `validate_labels()` (thuần, không IO). Trên phiếu
  nhãn giả 8 dòng có đáp án biết trước: accuracy **0,625**; per-class precision/recall/F1 khớp tính tay
  (dung 0,6667/0,5; sai 0,5/0,3333; tu_boi_dung 0,5/1,0; tu_boi_oan 1,0/1,0); ma trận nhầm lẫn
  `matrix["sai"]["dung"]=1`, `matrix["dung"]["sai"]=1`, tổng 8; `khong_ro` bị **loại khỏi chấm nhưng vẫn
  đếm**; dòng thiếu nhãn đếm ở `n_unfilled`.
- Nhãn sai định dạng (`đúng`, `DUNG`, `sai_bet`, `co`) → `LabelError` **kể cả khi** `allow_missing=True`;
  nhãn thiếu → lỗi khi `--strict`. Smoke thật `referee_agreement.py --round r5` chạy **trước** khi khôi
  phục artifact: không lỗi, `n_scored=0`, `n_unfilled=60`.

### 8.5 Mục 8–10 — benchmark thật, CI và điểm trọng số (22 test)

- `score_real_questions.validate_questions()`: thiếu `id` / `question` / cột người chấm → loại kèm lý do;
  **trùng id** và **trùng nội dung** (đã normalize khoảng trắng + hoa thường) → loại, ghi `trùng_nội_dung_với:
  RQ-1`; câu hỏi **giống hệt** câu trong `testset_v1` → **giữ nhưng gắn cờ** `leak_testset_v1=True`.
  Dry-run thật trên file hiện tại: `schema: nhận 2/5 dòng, loại 3` (3 dòng `RQ-EMPTY`), **0 câu thật**.
- `tools/eval/report_metrics.py` (mới): Wilson và bootstrap khớp ví dụ tính tay —
  7/10 → Wilson [0,3968; 0,8922]; 0/10 → [0; 0,2775]; 10/10 → [0,7225; 1]; bootstrap 0/10 → [0;0] và
  10/10 → [1;1] (không CI nào vượt [0,1] với mọi k=0…10); `rate_with_ci`; input sai → `ValueError`.
- `weighted_score()`: tổng trọng số **phải = 1,0** (assert); bộ 5 điểm cũ 9,0/8,0/7,0/8,5/4,0 → **7,10**
  đúng như đề bài; bộ điểm hiện hành 9,2/8,2/7,0/8,5/4,0 → **7,17**; đổi một trọng số cho tổng 1,01 → lỗi;
  thiếu khoá / lệch độ dài / lẫn dict-list → lỗi.

### 8.6 Mutation check đợt 2 — 10/10 bị bắt, hoàn nguyên byte-identical

Vì `gate.py` chưa được sửa, harness **copy cây tối thiểu** sang `tmp/mut6_tree/`
(`tmp/mutation_check_t6_tests.py`), đột biến bản sao, chạy pytest trong đó, rồi đối chiếu SHA-256.

| Đột biến | Phá gì | Bắt bởi |
|---|---|---|
| M1 `<=` → `<` (luật tương đối) | **đổi dấu so sánh trong cổng** (đúng yêu cầu đề bài) | test biên 0,77 |
| M2 trần tuyệt đối 0,35 → 2,0 | mất cảnh báo | test warning |
| M3 bỏ kiểm chữ ký trọng tài trong `compatibility()` | **bỏ kiểm chữ ký** (đúng yêu cầu đề bài) | §8.3 |
| M4 bỏ kiểm cấu hình hai round | mở cổng khi cấu hình lệch | §8.3 |
| M5 `fabrication` `<=` → `<` | nới luật 1 | test biên luật 1 |
| M6 `pass_rate` `>=` → `>` | nới luật 3 | test biên luật 3 |
| M7 `retrieval` `>=` → `>` | nới luật 6 | test biên luật 6 |
| M8 bỏ kiểm nhãn sai định dạng | phiếu rác vẫn chấm | §8.4 |
| M9 bỏ loại trùng id | hai bản cùng câu hỏi cùng lọt | §8.5 |
| M10 bỏ assert tổng trọng số | điểm tổng sai vẫn in | §8.5 |

Baseline (không đột biến) rc=0; mọi file hoàn nguyên `hoan_nguyen=True`.

### 8.7 Sự cố đã tự sửa: log mutation cũ bị ghi đè

Harness mới ban đầu đặt tên `tmp/mutation_check_t6.py` — **trùng** tên harness đợt 24-10, nên log
`tmp/mutation_check_t6.log` (bằng chứng của §2.2) bị ghi đè. Đã khắc phục: (a) khôi phục nội dung harness
cũ từ transcript vào `tmp/mutation_check_t6.py`, chạy lại → **10/10 bị bắt, rc=0**, log cũ tái lập;
(b) đổi harness mới thành `tmp/mutation_check_t6_tests.py` + `tmp/mutation_check_t6_tests.log`.
Artifact `data/loop/diag/referee_agreement_r5.json` bị lượt smoke làm đổi (chỉ timestamp + ba khoá rỗng
mới) đã được **hoàn nguyên về bản đã công bố**.

### 8.8 Giới hạn đợt 2

`n_filled=0` ⇒ **chưa có** kappa/precision/recall thật của trọng tài; `real_questions.jsonl` chưa có câu
thật ⇒ §8.5 chỉ là khung + CI; PA-13 vẫn **chưa áp dụng** vào `gate.py` (mọi test refusal chạy trên bản
đề xuất); `tools/diag/metric_ci.py` vẫn chưa có unit test riêng.

## Phụ lục A — số công bố | số tính lại | khớp

| Số công bố | Cách tính lại | Kết quả | Khớp |
|---|---|---|---|
| 9 test 6a | `pytest tests/test_gate_refusal_relative_proposal.py -q` | 9 passed | có |
| 6 test 6c | `pytest tests/test_score_real_questions.py -q` | 6 passed | có |
| 15 test T6 | baseline `tmp/mutation_check_t6.log` | 15 passed | có |
| 10/10 đột biến bị bắt | `tmp/mutation_check_t6.log` | 10/10, hoàn nguyên 10/10 | có |
| CI `PASS_CORRECT` r7 [0,08;0,21] | `metric_ci_r7_full.json` | trùng | có |
| Tổng điểm 7,17 → 7,2 | phép tính lại độc lập | 7,17 | có |
| 60 mẫu 6b, `n_filled=0` | manifest + worksheet | trùng | có |
| 6c dry-run = 0 câu thật, 0 lượt model | chạy `--dry-run` | trùng | có |
| Trọng tài `9f1179ccab74` | `verify.referee_fingerprint()` | trùng | có |
| 60 test đợt 2 | `pytest tests/test_t6_*.py -q` | 28 + 10 + 22 = 60 passed | có |
| 1.124 passed toàn repo | `pytest tests -q` → `tmp/pytest_t6_final.txt` | 1.124 passed, 2 skipped, 26,92 s | có |
| 10/10 đột biến đợt 2 | `tmp/mutation_check_t6_tests.log` | 10/10, hoàn nguyên 10/10 | có |
| r4-vs-r2 ĐẠT / r5-vs-r3 BỊ (2 ô) / r5-vs-r1 BỊ (1 ô) / r3-vs-r1 BỊ (2 ô) | đọc `gate_vs_*.json` + chạy `gate.main()` ra `tmp_path` | từng ô check trùng khớp | có |
| r5-vs-r3 **không** lật dưới PA-13 | `apply_to_gate_result()` | `passed=False` (delta refusal +0,08) | có — **đính chính đề bài** |
| accuracy phiếu giả 0,625 | `score_labels()` trên 8 dòng biết trước | 0,625 | có |
| Wilson 7/10 = [0,3968; 0,8922] | `wilson_ci(7,10)` | trùng 4 chữ số | có |
| Điểm trọng số 7,10 (bộ cũ) / 7,17 (bộ hiện hành) | `weighted_score()` | 7,1 / 7,17 | có |
| `real_questions.jsonl` 0 câu thật | `--dry-run` | câu thật = 0, `schema: nhận 2/5 dòng, loại 3` | có |
