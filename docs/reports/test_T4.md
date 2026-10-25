# Báo cáo kiểm thử — T4: cờ model sinh 3B + pipeline dữ liệu SFT

Ngày: 2026-10-25 (tổng hợp từ công việc 24-10) · Nhánh `auto/overnight`.
Phạm vi: **test cho hai đơn vị T4** — (a) cờ `GENERATOR_OLLAMA_MODEL` trong `tools/loop/run_round.py`;
(b) `tools/build_sft_from_round.py` (chỉ dựng dữ liệu, **không train**). KHÔNG sửa `src/`, KHÔNG sửa
trọng tài/gate, KHÔNG chạy lại round, KHÔNG train, **0 lượt Gemini**.

> **25-10 12:2x — đọc §10 trước:** đợt kiểm thử lại theo đề bài T4 (mục 1–9) thêm **41 test nhanh +
> 2 test `slow`**, chạy thật 5 bất biến dữ liệu SFT trên artifact đã công bố, đo lại VRAM/latency 20
> câu và kiểm adapter LoRA. Kết quả gọn: **mục 1–4, 6–9 ĐẠT; mục 5 KHÔNG ĐẠT vì DỮ LIỆU** (13/13 dòng
> train > 768 token); mutation mới **8/8 bị bắt**; lộ thêm **PA-28** (luật 2/N của bộ sinh).

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

---

## 10. Đợt kiểm thử lại 25-10 12:2x — đề bài mục 1–9 (T4: đổi generator, QLoRA SFT)

**0 lượt Gemini, 0 lần train.** Ba tệp mới (không sửa test cũ):

| Tệp | Vai trò | Số test |
|---|---|---:|
| `tools/diag/check_sft_invariants.py` | bộ kiểm CHỈ-ĐỌC cho 5 bất biến dữ liệu SFT (CLI + hàm cho test) | — |
| `tests/test_t4_sft_invariants.py` | mục 1–5 (dữ liệu SFT) + đo artifact đã công bố | **29** |
| `tests/test_t4_generator_contract.py` | mục 6–7 (giao diện generator + cache key) + đọc số mục 8 | **12** |
| `tests/test_t4_gpu_slow.py` | mục 8–9, marker `slow`, bật bằng `T4_RUN_SLOW=1` | **2** (mặc định skip) |

Tổng test T4 sau đợt này: **62 nhanh + 2 slow** (11 model-flag + 10 build_sft + 29 invariants + 12 contract).
`tests/conftest.py` chỉ thêm `pytest_configure` khai báo marker `slow` (không thêm pytest.ini toàn cục).
Không sửa `gate.py`, không sửa `verify.py`/`answer_guard.py`/`text_utils.py` ⇒ trọng tài vẫn
**`9f1179ccab74`**. Không đổi artifact, không đổi `data/loop/rounds/`.

### 10.1 Mục 1–5 trên artifact ĐÃ CÔNG BỐ (`data/training/t4b_r5r8r9r10`)

Nguồn số: `tmp/t4_invariants_report.json` (chạy `tools/diag/check_sft_invariants.py --out …`).

| # | Bất biến | Kết quả | Ghi chú |
|---|---|---|---|
| 1 | Thực thể vàng + tên nguồn nằm trong ngữ cảnh dòng | **XANH** | 13/13 dòng train có đủ; **5/13 thiếu `gold_sentence` nguyên văn** = INFO, vì bộ sinh chỉ đòi 2/N (PA-28) |
| 2 | Không item test trong train (id + `gold_sentence` đã fold) | **XANH** | 58 item test; 0 trùng id; 0/58 câu vàng fold xuất hiện trong train |
| 3 | Group split theo tài liệu (và `(tài liệu, Điều)`) | **XANH** | 7 tài liệu train / 2 holdout, giao = ∅; 7 nhóm `(doc, Điều)` nhận diện được, 0 nhóm cắt đôi; **16/23 dòng không nhận diện được số Điều** (báo ra, không im lặng) |
| 4 | Ca "không đáp án" không bị gán nhãn trả lời | **XANH** | 0 dòng `sft_refusal` trong artifact (mặc định TẮT cờ) và 0 vi phạm |
| 5 | Parse được, không rỗng/trùng, token ≤ `max_length` | **ĐỎ (DỮ LIỆU)** | parse 23/23, 0 rỗng, 0 trùng; **train 13/13 dòng > 768 token** (min 1.016, max 1.707); **holdout 8/10 dòng > 768** (min 657, max 1.488) |

ĐỎ ở mục 5 là **ĐỎ của dữ liệu, không phải của test**: `models/train_sft_lora.py` sẽ cắt cụt dòng
nếu train với `max_length=768`, mà cắt cụt = mất căn cứ = phá bất biến #7. Không nâng trần (vượt
VRAM 4 GB, xem D-10), không cắt dòng, không sửa artifact. Đường sửa đã có đề xuất: **PA-11** (4-bit) /
**PA-12** (đổi định dạng dòng).

### 10.2 Mục 1 — "dòng giả thiếu thực thể ⇒ bị loại và đếm"

Hai lớp, hai kết quả khác nhau, **cả hai đều được ghim bằng test**:

| Ca giả (qua `triage.build_rows`) | Kết quả | Test |
|---|---|---|
| Ngữ cảnh **không** có nguồn, **không** có thực thể | **bị loại**, `skip_sft_target_not_in_context = 1` | `test_dong_thieu_ca_thuc_the_va_nguon_bi_loai_va_dem` |
| Ngữ cảnh có **nguồn + câu vàng**, thiếu thực thể | **được GIỮ** (luật `min(2, len(frags))`) — bộ kiểm vẫn báo ĐỎ | `test_dong_thieu_thuc_the_nhung_du_nguon_va_cau_vang_hien_hanh_van_giu` |

Ca thứ hai là **khoảng trống thật** của bộ sinh, ghi thành **PA-28** (3 phương án, chờ duyệt). Test
cố ý ghi tên "hien_hanh" và khẳng định bộ kiểm ĐỎ cho chính dòng đó — không hạ kỳ vọng cho xanh.

### 10.3 Mục 2 — chặn rò rỉ "bắt và dừng"

`check_no_leak` mặc định **ném `SftInvariantError`** (không trả cờ rồi đi tiếp). Test chứng minh:

- chèn dòng có `provenance.item_id` của item `split=test` ⇒ **raise**, và `raise_on_leak=False` liệt
  kê đúng id;
- chèn **`gold_sentence` của item test đã fold** (chuỗi khác nguyên văn: viết hoa + bỏ dấu) vào ngữ
  cảnh dòng train ⇒ **raise** — chứng minh phép so là fold, không phải so byte;
- `check_artifact(..., raise_on_violation=True)` dừng ngay ở artifact giả có dòng test trong train;
- **lớp thứ nhất** (bộ sinh) vẫn đếm `blocked_test_leak = 1` cho item `split=test`.

### 10.4 Mục 3 — group split trên 3 tài liệu giả

- 3 tài liệu, mỗi tài liệu 2 item: chia đúng ⇒ XANH, giao tài liệu = ∅.
- **Đột biến "chia theo item"** (2 item cùng tài liệu rơi hai phía) ⇒ `check_group_split` **raise**;
  `raise_on_overlap=False` trả `document_overlap = ["quy-che-ctdt.pdf"]`.
- Khoá nhóm mức Điều là `(tài liệu, Điều)`: cùng "Điều 12" ở **hai tệp khác nhau** là hợp lệ (test
  riêng), còn cùng `(tệp, Điều)` rơi hai phía thì bị bắt.
- `article_of` ưu tiên: `item["article"]` → `gold_sentence` → nhãn `[Điều N.]` ở khối đầu ngữ cảnh →
  `None` (đếm là "không xác định").

### 10.5 Mục 4 — nhãn từ chối

| Ca | Kỳ vọng | Test |
|---|---|---|
| verdict `FAIL_HALLUCINATED_ON_UNANSWERABLE` + `task = sft_extractive` | ĐỎ `unanswerable_labeled_answer` | `test_ca_khong_dap_an_bi_gan_nhan_tra_loi_bi_bat` |
| `sft_refusal` nhưng assistant ≠ `REFUSAL_TEXT` | ĐỎ `refusal_text_differs` | `test_sft_refusal_phai_dung_cau_chuan` |
| `sft_refusal` sinh từ verdict trả lời được | ĐỎ `refusal_from_answerable` | `test_sft_refusal_tu_verdict_tra_loi_duoc_bi_bat` |
| `sft_refusal` + verdict không-đáp-án + đúng câu chuẩn | XANH | `test_refusal_dung_thi_xanh` |

### 10.6 Mục 5 — định dạng

- dòng JSON hỏng ⇒ `SftInvariantError` kèm **số dòng** (`dòng 2 không parse được`);
- dòng rỗng (`content` trắng) và dòng trùng `(role, content)` ⇒ bị bắt, kèm chỉ số dòng trùng;
- độ dài: `exact_lengths` (từ manifest) được ưu tiên hơn ước lượng; biên **đúng 768 = ĐẠT** (trần là
  `<=`), 769 = ĐỎ;
- artifact thật: **13/13 train + 8/10 holdout vượt 768** ⇒ mục 5 ĐỎ (xem §10.1).

### 10.7 Mục 8 — VRAM đỉnh + p50/p95 trên 20 câu THẬT

Nguồn: `data/loop/diag/t4_latency_20q.json` (công cụ `tools/diag/t4_latency_probe.py`). 20 câu lấy từ
`data/loop/rounds/r5/full.jsonl` (câu hỏi + ngữ cảnh ĐÚNG như lượt chạy thật), model
**`qwen2.5:1.5b-instruct`**, cache TẮT, đo 25-10 12:2x.

| Đại lượng | Số đo |
|---|---|
| Tổng 20 câu | **68,6 s** |
| p50 latency | **2,900 s** |
| p95 latency | **4,421 s** |
| min / mean / max | 2,719 s / 3,428 s / **9,626 s (câu 1, gồm nạp model)** |
| p50 / p95 khi bỏ câu 1 | 2,900 s / 4,421 s |
| VRAM nền → đỉnh | 0 MiB → **1.401 MiB** (150 mẫu `nvidia-smi`, 0,4 s/mẫu) |

**Không đặt ngưỡng cứng** trong unit test (đề bài yêu cầu vậy); test chỉ kiểm `p50 ≤ p95 ≤ max`,
`peak > 0`, `n_samples > 0`.

### 10.8 Mục 9 — adapter LoRA: được áp + nạp hỏng báo lỗi

Nguồn: `data/loop/diag/t4_adapter_probe.json` (`tools/diag/t4_adapter_probe.py`, chạy bằng
`venv_train` vì app `venv` không có torch). Prompt cố định, **greedy** (`do_sample=False`) nên sai
khác chỉ có thể đến từ trọng số adapter.

| Đại lượng | Kết quả |
|---|---|
| Base `Qwen2.5-0.5B-Instruct` | "Sinh viên được học lại tối đa 8 lần đối với mỗi học phần." |
| Base + adapter | "… đối với mỗi học phần **và phải đóng học phí cho lần học lại đó**." |
| `outputs_differ` | **true** |
| VRAM đỉnh base / + adapter | 964,0 MiB / **1.025,4 MiB** |
| Giây (load base / gen / load adapter / gen) | 1,99 / 1,30 / 0,43 / 1,68 |
| Nạp adapter HỎNG (thư mục rỗng) | **ném `ValueError`**: `Can't find 'adapter_config.json' at …` — không có nhánh fallback |

**Trung thực về nguồn gốc adapter:** `models/qwen25_05b_sft_adapter` được train trên
`data/training/sft_train.jsonl` (cặp hỏi–đáp về **mã nguồn repo**, 1.635 dòng), **KHÔNG** phải trên
`data/training/t4b_r5r8r9r10`. Vì vậy mục 9 chứng minh **"adapter thật sự được áp và lỗi nạp không bị
nuốt"**, KHÔNG chứng minh chất lượng của dữ liệu T4b. Muốn chứng minh điều sau phải train (PA-11/PA-12).

### 10.9 Mục 6–7 — giao diện generator và cache key

| Tính chất | Cách kiểm | Test |
|---|---|---|
| Cùng chữ ký `generate_answer` | `inspect.signature` hai lớp khớp từng `(name, kind, default)` | `test_hai_generator_cung_chu_ky_generate_answer` |
| Cùng một `canonicalize_refusal` | chỉ 1 định nghĩa trong module, ≥3 chỗ xuất hiện | `test_hai_generator_cung_dung_mot_ham_chuan_hoa_tu_choi` |
| Chuẩn hoá từ chối | `NGOAI_PHAM_VI` + dấu hiệu từ chối ⇒ đúng `REFUSAL_TEXT`; nhãn khác ⇒ giữ nguyên | `test_canonicalize_refusal_chi_chuan_hoa_ngoai_pham_vi` + 2 test qua **đường sinh thật** (Ollama giả / `_call_api` giả) |
| Chọn model qua env, mặc định là model cũ | env rỗng ⇒ `None` ⇒ `qwen2.5:1.5b-instruct`; slug ⇒ model mới; khoảng trắng ⇒ `None` | `test_mac_dinh_van_la_model_cu`, `test_chon_model_qua_env_chi_doi_tang_sinh` |
| Cache key chứa model | 2 model khác nhau ⇒ key khác; cùng đầu vào ⇒ key bằng | `test_khoa_doi_theo_model_va_giu_nguyen_khi_cung_dau_vao` |
| Cache key chứa `PROMPT_VERSION` | monkeypatch `effective_prompt_version` ⇒ key đổi | `test_khoa_doi_theo_prompt_version_bump` |
| Đổi model KHÔNG đọc cache cũ | ghi entry cho model A; A HIT, B MISS | `test_doi_model_khong_doc_cache_cu` |
| Gemini cũng tách khoá theo model | 2 `model_name` ⇒ key khác | `test_gemini_cung_tach_khoa_theo_model` |

### 10.10 Mutation — 8/8 bị bắt (`tmp/mutation_check_t4_new.log`)

| Mã | Đột biến | Test đỏ | Hoàn nguyên |
|---|---|---|---|
| T4-M1 | **bỏ kiểm thực thể** trong bộ kiểm | 2 | byte-identical |
| T4-M2 | **trộn split theo item** (`check_group_split` nhóm theo item id) | 2 | byte-identical |
| T4-M3 | bỏ phát hiện rò rỉ theo id | 2 | byte-identical |
| T4-M4 | bỏ phát hiện rò rỉ theo `gold_sentence` fold | 1 | byte-identical |
| T4-M5 | cho ca "không đáp án" mang nhãn trả lời | 1 | byte-identical |
| T4-M6 | bỏ phát hiện vượt `max_length` | 3 | byte-identical |
| T4-M7 | cache key Qwen bỏ tên model | 2 | byte-identical |
| T4-M8 | `canonicalize_refusal` không chuẩn hoá gì | 3 | byte-identical |

Baseline của harness: **41 passed** (hai file test nhanh). `src/generator.py` là file dirty của phiên
T3–T5 nên backup NGUYÊN BYTE trong bộ nhớ + so SHA-256 sau mỗi lần; cả 8 lần đều `hoàn nguyên=True`.

### 10.11 Bảng nghiệm thu đề bài T4

| Mục | Nội dung | Kết quả |
|---|---|---|
| 1 | Bất biến 7: thực thể + nguồn trong ngữ cảnh; dòng giả thiếu thực thể bị loại và đếm | **ĐẠT** (bộ kiểm bắt buộc; artifact 0 vi phạm; nhánh 2/N còn hở = **PA-28**) |
| 2 | Chặn rò rỉ theo id + `gold_sentence` fold, "bắt và dừng" | **ĐẠT** |
| 3 | Group split theo tài liệu/Điều, test 3 tài liệu | **ĐẠT** |
| 4 | Ca không-đáp-án không bị gán nhãn trả lời | **ĐẠT** |
| 5 | Parse/không rỗng/không trùng/token ≤ max-length | **KHÔNG ĐẠT — do DỮ LIỆU** (13/13, 8/10 > 768); bộ kiểm và test phát hiện đúng |
| 6 | Giao diện chung + chọn model qua env, mặc định model cũ | **ĐẠT** |
| 7 | Cache key chứa model + `PROMPT_VERSION`, đổi model không đọc cache cũ | **ĐẠT** |
| 8 | VRAM đỉnh + p50/p95 trên 20 câu, không ngưỡng cứng trong unit test | **ĐẠT** (số ở §10.7) |
| 9 | Adapter nạp được, khác base ≥1 mẫu, nạp hỏng lỗi rõ | **ĐẠT** (kèm caveat nguồn gốc adapter ở §10.8) |
| — | Mutation "bỏ kiểm thực thể" + "trộn split theo item" bị bắt | **ĐẠT** (8/8) |

Toàn bộ test: `pytest tests -q` = **1.057 passed, 2 skipped** (24,72 s, `tmp/pytest_t4_final.log`);
hai test skip là mục 8–9 (`T4_RUN_SLOW=1` thì **2 passed** trong 73,05 s).

### 10.12 Việc chưa làm / khoảng trống

- **Không train** (đặc tả T4b chỉ dựng dữ liệu) ⇒ không có số `PASS_CORRECT` nào chứng minh 4b tốt hơn.
- **Mục 5 ĐỎ** ở artifact đã công bố — chờ PA-11/PA-12; không sửa dữ liệu trong phiên này.
- **PA-28**: luật 2/N của bộ sinh có thể giữ dòng thiếu thực thể; đã đo, đã ghim test, chưa sửa.
- Adapter hiện có train trên dữ liệu khác T4b (ghi ở §10.8) — không dùng nó để tuyên bố về dữ liệu T4b.
- 16/23 dòng không nhận diện được số Điều từ ngữ cảnh ⇒ phép kiểm mức `(tài liệu, Điều)` chỉ phủ 7
  nhóm; mức **tài liệu** phủ 100%.

### 10.13 Lệnh tái lập

```bash
# bộ kiểm 5 bất biến trên artifact đã công bố (chỉ đọc)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/check_sft_invariants.py \
    --out tmp/t4_invariants_report.json

# test nhanh + toàn repo
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest \
    tests/test_t4_sft_invariants.py tests/test_t4_generator_contract.py -q
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q

# mục 8–9 (cần GPU/Ollama; ~73 s)
T4_RUN_SLOW=1 PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests/test_t4_gpu_slow.py -q

# đột biến T4 (8 ca, tự hoàn nguyên + so SHA-256)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tmp/mutation_check_t4_new.py
```
