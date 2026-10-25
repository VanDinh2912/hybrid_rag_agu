# Báo cáo kiểm thử — T4: cờ model sinh 3B + pipeline dữ liệu SFT

Ngày: 2026-10-25 (tổng hợp từ công việc 24-10) · Nhánh `auto/overnight`.
Phạm vi: **test cho hai đơn vị T4** — (a) cờ `GENERATOR_OLLAMA_MODEL` trong `tools/loop/run_round.py`;
(b) `tools/build_sft_from_round.py` (chỉ dựng dữ liệu, **không train**). KHÔNG sửa `src/`, KHÔNG sửa
trọng tài/gate, KHÔNG chạy lại round, KHÔNG train, **0 lượt Gemini**.

## 1. Đã làm gì

### 1.1 T4a — cờ model sinh (`tests/test_loop_generator_model_flag.py`, **11 test**)

Bất biến #2: lever mới phải nằm sau cờ env, mặc định TẮT, và "tắt" phải chứng minh được là hành vi cũ
**từng ký tự**. Các tính chất được ghim:

- `GENERATOR_OLLAMA_MODEL` rỗng hoặc chỉ khoảng trắng ⇒ `generator_model_override()` trả `None`
  (3 case tham số hoá: `""`, `"   "`, `"\t"`).
- TẮT ⇒ `build_pipeline` truyền **đúng** `{"ollama_model": None}`; `QwenGenerator` rơi về
  `DEFAULT_OLLAMA_MODEL`; `LocalSLM` nhận `{}` (không bị đổi model).
- BẬT ⇒ chỉ `QwenGenerator` nhận slug; `LocalSLM` **vẫn** `{}` — đây là dòng chứng minh "một biến"
  (không đổi đồng thời sinh + chuẩn hóa + phân loại + tách câu).
- Nhánh Gemini không bị ảnh hưởng bởi cờ local.
- Đổi slug ⇒ cache key đổi (không đọc nhầm câu trả lời 1,5B), nhưng `temperature`, `num_ctx`,
  `PROMPT_VERSION` giữ nguyên.
- Manifest round ghi **slug thực tế** đang chạy (vì `gate.compatibility()` chỉ so `generator`, mù với
  biến số model); khi chưa chạy round nào vẫn ghi được giá trị mặc định.

### 1.2 T4b — dựng dữ liệu SFT (`tests/test_build_sft_from_round.py`, **10 test**)

Bốn ràng buộc của đặc tả T4b, mỗi ràng buộc có test:

1. **Group split theo tài liệu**, không theo item: một `source_document` không bao giờ xuất hiện ở cả
   train lẫn holdout; tổng dòng hai bên = tổng dòng vào.
2. **Tất định theo seed**: cùng seed ⇒ cùng `holdout_documents` (nếu không thì không lần lại được số
   liệu cũ).
3. **Khử trùng theo item id** khi gộp nhiều round: cùng một ca từ chối oan ở r5 và r6 chỉ thành **một**
   dòng train; ledger đếm `deduped_same_item_across_rounds`.
4. **Ledger chặn rò rỉ**: `blocked_test_leak` và `skip_sft_target_not_in_context` phải thoát ra được —
   đó là con số báo cáo (bất biến #7: dòng train tự chứa đáp án).

Ngoài ra: `write_outputs` từ chối ghi đè thư mục đã có `sft_*.jsonl`; `token_cost_proxy` ghi rõ
"CHƯA kiểm chứng"; và một test **có điều kiện** (`skipif` khi thiếu tokenizer cục bộ) chốt rằng độ dài
token phải đo bằng `apply_chat_template(tokenize=False)` rồi tokenize — đường `tokenize=True` trên
transformers 5.x trả 2 token và sẽ biến mọi dòng thành "vừa 768".

## 2. Kết quả số (nguồn: file trên đĩa)

### 2.1 Số test

| Lần chạy | Kết quả | Nguồn |
|---|---|---|
| Hai file T4 (baseline mutation) | **21 passed**, 3 warnings (7,33 s) = 11 + 10 | `tmp/mutation_check_t4.log` dòng `[baseline]` |
| Riêng T4a | 11 passed (1,88 s) | `pytest tests/test_loop_generator_model_flag.py -q` |
| Riêng T4b | 10 passed (3,78 s) | `pytest tests/test_build_sft_from_round.py -q` |
| Toàn repo sau T4/T6 | **1.005 passed**, 3 warnings (28,27 s) | `tmp/pytest_t4t6_final.txt` |
| Chữ ký trọng tài | `9f1179ccab74` (không đổi) | `tmp/pytest_t4t6_final.txt` dòng cuối |

### 2.2 Mutation check — 7/7 bị bắt, 7/7 hoàn nguyên byte-identical

Nguồn: [`tmp/mutation_check_t4.log`](../../tmp/mutation_check_t4.log). Harness phá đúng một tính chất,
chạy cả hai file test, khôi phục bằng `write_bytes` và so SHA-256 sau từng lượt.

| Đột biến | Tính chất bị phá | Test đỏ tiêu biểu | Hoàn nguyên |
|---|---|---|---|
| T4a-M1 env rỗng trả `''` thay vì `None` | "tắt" không còn là tắt | `test_mac_dinh_rong_khong_tro_bat_ky_model_nao` | có |
| T4a-M2 áp slug cho cả `LocalSLM` | phá one-variable (đổi normalizer) | `test_tat_thi_build_pipeline_truyen_None_giu_nguyen_fallback` | có |
| T4a-M3 `build_pipeline` bỏ qua override | bật cờ không có tác dụng | `test_bat_co_doi_tang_sinh_khong_cham_normalizer` | có |
| T4a-M4 manifest ghi env thay vì model thực | manifest không tự ký dụng cụ đo | `test_manifest_ghi_dung_slug_thuc_te_dang_chay` | có |
| T4b-M5 group split theo item | rò rỉ tài liệu qua hai bên | `test_group_split_khong_bao_gio_cat_doi_document` | có |
| T4b-M6 tắt khử trùng item id | một ca thành hai dòng train | `test_gop_nhieng_round_khong_nhan_doi_cung_mot_item` | có |
| T4b-M7 cho ghi đè output | mất dữ liệu cũ | `test_write_outputs_tu_choi_ghi_de` | có |

SHA-256 bốn file nguồn trước = sau (kiểm độc lập, ngoài script):

| File | Ghi chú |
|---|---|
| `tools/loop/run_round.py` | giữ nguyên sau 4 đột biến T4a |
| `tools/build_sft_from_round.py` | giữ nguyên sau 3 đột biến T4b |
| `tools/diag/gate_refusal_relative_proposal.py` | (dùng cho T6) |
| `tools/eval/score_real_questions.py` | (dùng cho T6) |

Lần chạy đầu, T4a-M2 (rò env `OLLAMA_MODEL`) **sống sót** vì test chỉ kiểm kwargs của `LocalSLM`;
mutation được thay bằng đột biến mạnh hơn (áp slug trực tiếp cho `LocalSLM`) và bắt được. Không sửa
test cũ.

### 2.3 Số đo T4a — quyết định âm (nguồn: `docs/reports/T4.md`, round `r10`)

| Chỉ số | 1.5B (r5/r9) | 3B Q4 (r10) | Nguồn |
|---|---:|---:|---|
| `PASS_CORRECT` /100 | 14 | **16** | `data/loop/rounds/r10/round_summary_full.json` |
| McNemar | — | **p = 0,804** | `data/loop/rounds/r10/t4_stats.json` |
| CI 95% delta | — | **[−0,06 ; +0,10]** (chứa 0) | `data/loop/diag/t4_stats.json` |
| `refusal_rate` | 0,69 | 0,75 | `round_summary_full.json` |
| p95 latency | 18,65 s | **34,12 s (+83%)** | `round_summary_full.json` |
| One-variable 100/100 item | — | trùng | `data/loop/diag/one_variable_check.json` |

Theo quy tắc đăng ký trước (ngưỡng "có tín hiệu" là `PASS_CORRECT ≥ 22`): **3B KHÔNG đạt**; không mở
Qwen3-4B. Kết luận này là **âm**, không phải "model là nút thắt".

### 2.4 Số đo T4b — dựng dữ liệu + trần bộ nhớ (nguồn: `docs/reports/T4.md`)

| Đại lượng | Giá trị | Nguồn |
|---|---|---|
| Group split theo tài liệu (seed 20261024, test_fraction 0,25) | train **13** / holdout **10**; 7 tài liệu train, 2 holdout | `data/training/t4b_r5r8r9r10/manifest.json` |
| Dòng bị chặn | `blocked_test_leak` **134** · `skip_sft_target_not_in_context` **20** · `overrefusal_threshold_only` **17** · `deduped_same_item_across_rounds` **38** · `sft_refusal_rows` **2** | cùng manifest, `ledger.blocked` |
| Trần VRAM đo được | 960 token → 3.931 MiB; **1.024 token → 4.156,9 MiB** | `data/loop/diag/t4b_memory_probe_len.json` |
| Dòng train vượt trần 1.024 | **13/13** dòng (min 1.016 token) | cùng file |
| Kết luận | Không train nổi trên GPU 4 GB; gradient checkpointing **không giúp** (logits LM head) | `docs/reports/T4.md` §2.6 |

## 3. Kết luận chỉ từ số

- Cờ T4a TẮT giữ đúng hành vi cũ ở mức kwargs (`ollama_model=None`, `LocalSLM {}`) và ở mức cache key;
  bật cờ chỉ đổi tầng sinh, manifest tự ghi slug thực tế.
- Pipeline T4b giữ được bốn ràng buộc chống rò rỉ/dữ liệu giả: group split theo tài liệu, tất định theo
  seed, khử trùng item, ledger chặn đầy đủ.
- 7/7 đột biến bị bắt ⇒ test T4 có hiệu lực; không đột biến nào sống sót sau khi bổ sung đột biến mạnh
  hơn cho T4a-M2.
- Toàn repo 1.005 passed; trọng tài `9f1179ccab74` ⇒ không phải chấm lại round nào.

## 4. Điều KHÔNG kết luận được / phần chưa kiểm

### 4.1 Không chứng minh được "4b tốt hơn" vì chưa train

Theo quyết định của user 24-10, T4b **chỉ dựng pipeline + báo chi phí**, không train. Vì vậy tiêu chí
"4b chứng minh bằng `PASS_CORRECT` trên test group tách rời" **CHƯA đạt và không thể đạt trong phạm vi
này** (`docs/reports/T4.md` mục 4). Test hiện tại chỉ chứng minh dữ liệu *đúng đặc tả*, không chứng
minh dữ liệu *huấn luyện ra model tốt hơn*.

### 4.2 Test token thật phụ thuộc môi trường

`test_exact_token_lengths_dung_duong_tokenize_false` cần `models/qwen25_05b_sft_adapter` + `transformers`;
trong checkout không có thì nó **skip**, không đỏ và không chứng minh gì. Số 1.024 token ở §2.4 lấy từ
probe trên `venv_train`, không phải từ test này.

### 4.3 Chưa test các script đo phụ trợ

`tools/build_training_data.py`, `tools/validate_training_data.py`, `tools/diag/one_variable_check.py`,
`tools/diag/t4_stats.py` **không có unit test**; số liệu của chúng được đối chiếu bằng đọc file
(`one_variable_check.json`, `t4_stats.json`), không bằng test tự động.

### 4.4 T4a chỉ đo trên 100 item pha sinh

One-variable 100/100 item trùng chứng minh **cùng đầu vào** giữa hai lượt, không chứng minh gì trên
811 item. Không chạy lại round 811 item với 3B (quota/thời gian).

### 4.5 Không chạy Ollama/mạng trong test

Mọi test T4 dùng stub (`FakeQwenGenerator`, `FakeLocalSLM`, `tmp_path`); không kiểm tra chất lượng
sinh thật, không đo VRAM/latency thật. Đó là phạm vi round r10 + probe, không phải unit test.

## 5. Tiêu chí xong

- T4a: cờ mặc định TẮT, một biến, manifest tự ký — **đạt** (11 test, mutation 4/4).
- T4b: pipeline dữ liệu đúng 4 ràng buộc — **đạt ở mức đặc tả** (10 test, mutation 3/3); **chưa đạt**
  tiêu chí "chứng minh bằng PASS_CORRECT" vì không train (PA-11/PA-12).
- Không đỏ test cũ: toàn repo **1.005 passed** (`tmp/pytest_t4t6_final.txt`); không sửa test cũ.

## 6. Lệnh tái lập

```bash
# Hai file test T4
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest \
  tests/test_loop_generator_model_flag.py tests/test_build_sft_from_round.py -q

# Mutation check (7 đột biến, tự hoàn nguyên + kiểm SHA-256)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t4.py

# Toàn repo
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
```

## 7. Đề xuất cần duyệt

- **PA-11**: cho phép mở đường 4-bit (`bitsandbytes` trong `venv_train`) để train dòng SFT dài hơn trần
  1.024 token.
- **PA-12**: đổi định dạng dòng SFT (giảm số chunk trong ngữ cảnh) để vừa trần GPU 4 GB.
- **PA-8/PA-26**: phần `src/generator.py` liên quan T4a (cache theo model) vẫn nằm trong file dirty của
  phiên khác, chưa được commit.

## Phụ lục A — số công bố | số tính lại | khớp

| Số công bố | Cách tính lại | Kết quả | Khớp |
|---|---|---|---|
| 11 test T4a | `pytest tests/test_loop_generator_model_flag.py -q` | 11 passed | có |
| 10 test T4b | `pytest tests/test_build_sft_from_round.py -q` | 10 passed | có |
| 21 test T4 | baseline trong `tmp/mutation_check_t4.log` | 21 passed | có |
| 7/7 đột biến bị bắt | `tmp/mutation_check_t4.log` | 7/7, hoàn nguyên 7/7 | có |
| `PASS_CORRECT` 14→16 | đọc `round_summary_full.json` r9/r10 | trùng | có |
| CI [−0,06 ; +0,10], p=0,804 | `data/loop/diag/t4_stats.json` | trùng | có |
| Trần 1.024 token → 4.156,9 MiB | `t4b_memory_probe_len.json` | trùng | có |
| 13/13 dòng ≥1.016 token | cùng file | trùng | có |
| Toàn repo 1.005 passed | `tmp/pytest_t4t6_final.txt` | trùng | có |
