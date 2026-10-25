# Báo cáo kiểm thử tổng kết — T0 → T7

Ngày: 2026-10-25 · Nhánh `auto/overnight` · Người chạy: agent kiểm thử (chế độ tự trị).
Phạm vi: **tổng hợp 8 báo cáo test theo nhiệm vụ** (`docs/reports/test_T0.md` … `test_T7.md`), chốt
trạng thái bộ test, bảng đối chiếu số công bố, và các khoảng trống còn lại.

**0 lượt gọi Gemini** cho toàn bộ công việc kiểm thử (mọi test dùng fake/stub/`tmp_path`). Không sửa
trọng tài (`tools/loop/verify.py`, `src/answer_guard.py`, `src/text_utils.py`) ⇒ chữ ký vẫn
**`9f1179ccab74`**; không sửa `tools/loop/gate.py`; không ghi vào `outputs/` hay `data/loop/rounds/`.

## 1. Tổng quan 8 nhiệm vụ

| Task | Đối tượng | File test mới | Số test (công bố) | Mutation | Báo cáo |
|---|---|---|---:|---:|---|
| T0 | noise floor + bộ đếm `[AnswerRescue]` | `tests/test_noise_floor.py` | 22 | 5/5 | [`test_T0.md`](test_T0.md) |
| T1 | `tools/diag/ablation_generation.py` | `tests/test_ablation_generation.py` | 29 | 4/4 | [`test_T1.md`](test_T1.md) |
| T2 | corpus rebuild / chất lượng corpus | `tests/test_corpus_rebuild.py` | 78 | 5/5 | [`test_T2.md`](test_T2.md) |
| T3 | guardrail từ chối + golden cờ TẮT | `tests/test_t3_guardrails.py` + golden | 75 | 7/7 | [`test_T3.md`](test_T3.md) |
| T4 | cờ model 3B + pipeline SFT | `test_loop_generator_model_flag.py`, `test_build_sft_from_round.py` | 21 | 7/7 | [`test_T4.md`](test_T4.md) |
| T5 | reranker + contextual header | `test_t5_reranker_contract.py`, `test_t5_contextual_header.py` | 68 | 10/10 | [`test_T5.md`](test_T5.md) |
| T6 | cổng refusal tương đối + khung câu hỏi thật | `test_gate_refusal_relative_proposal.py`, `test_score_real_questions.py` | 15 | 10/10 | [`test_T6.md`](test_T6.md) |
| T7 | `run_chain` + khóa chính sách cache | `test_run_chain.py`, `test_cache_policy.py` | 37 | 17/17 | [`test_T7.md`](test_T7.md) |

Tổng mutation theo báo cáo: **65/65 bị bắt**, mỗi lần đều hoàn nguyên **byte-identical** (SHA-256).
Không cộng dồn số test thành một phép cộng tuyến tính: các mốc baseline của 8 đợt chồng lấn nhau
(563 → 691 → 712 → 736 → 889 → 957 → 967 → 1.004 → 1.005 → 1.006 → 1.011). Con số chuẩn duy nhất là **toàn bộ `tests/`** ở §2.

## 2. Kiểm chứng cuối

### 2.1 Toàn bộ test

| Đại lượng | Giá trị | Nguồn |
|---|---|---|
| `pytest tests -q` | **1.011 passed**, 3 warnings (29,79 s) | `tmp/pytest_t1_final.txt` |
| Chữ ký trọng tài | **`9f1179ccab74`** | `tmp/pytest_t4t6_final.txt` dòng cuối; test T0/T1 không đụng trọng tài |
| Golden T3 (cờ TẮT) SHA-256 | `e59b9ebb6b12c2d6844356f5861cc98d418c11b26f83a49fdae1f8f2ea1728b5` | `sha256sum tests/golden/t3_off_30items_head_f492f05.json` |
| Mutation T7 (run_chain + cache) | 6/6 + 10/10 | `tmp/mutation_check_t7.log`, `tmp/mutation_check_cache_policy.log` |
| Mutation T4 | 7/7 | `tmp/mutation_check_t4.log` |
| Mutation T6 | 10/10 | `tmp/mutation_check_t6.log` |
| Mutation T0 (sau khi thêm test 22) | 5/5 | `tmp/mutation_check_t0.log` |
| Mutation T1 (sau khi thêm guard tập item) | 4/4 | `tmp/mutation_check_t1.log` |

Không có test nào đỏ. Không sửa test cũ để xanh; hai lần mutation sống sót (T4a-M2 bản đầu, T6a-M1)
đã được xử lý bằng **đột biến mạnh hơn** và **một test biên mới**, không bằng hạ kỳ vọng.

### 2.2 Bất biến "cờ TẮT = hành vi cũ"

| Bất biến | Bằng chứng |
|---|---|
| Golden 30 item T3 khớp từng khoá | `test_t3_guardrails.py`, SHA-256 khối `core` `344d55cd…` |
| Cache key mặc định đúng 4 trường cũ | `test_cache_key_payload_contains_prompt_version_and_policy` (+ Qwen) |
| T5 cờ TẮT trả đúng object/thứ tự, không nạp reranker | `test_t5_reranker_contract.py` |
| T4a cờ TẮT truyền `ollama_model=None`, `LocalSLM {}` | `test_loop_generator_model_flag.py` |
| Referee không đổi ở mọi round r0–r13 | `settings` các `round_summary_*.json`; `verify.referee_fingerprint()` |

### 2.3 Trạng thái git kỳ vọng

Sau commit báo cáo này, working tree còn:

| Loại | Số/ mục |
|---|---|
| Tracked đang sửa | **6**: `src/generator.py`, `src/pipeline.py`, `src/query_normalizer.py`, `src/router.py`, `tests/test_pipeline.py`, `tests/test_subquery.py` |
| Untracked nguồn/công cụ/test | **35** = 3 `src/` + 17 `tools/` + 15 `tests/` (PA-26) |
| Artifact không commit | `models/` 321 MB, `data/loop/rounds/` 78 MB, `chroma_db_vie/`, `chroma_db_headers_old/`, `.ocr_cache_vie/`, caches, `tmp/` |

Kỳ vọng sau commit: `git status --short` chỉ còn đúng các mục trên, **không** có file mới ngoài dự kiến.
PA-26 là điều kiện để fresh clone chạy lại **1.011 test**; hiện tại HEAD **chưa** tái lập được.

## 3. Kết luận chỉ từ số

- Bộ test hiện tại **1.011 xanh**, trọng tài bất biến; 65/65 đột biến bị bắt ⇒ test có hiệu lực trên
  các tính chất đã đăng ký (không chứng minh test phủ hết mọi lỗi có thể).
- Các lever mới đều nằm sau cờ mặc định TẮT và có golden/byte-identical chứng minh "tắt = cũ":
  T3 (guardrail), T4a (model), T5 (reranker/header), T7 (policy cache).
- Số liệu thực nghiệm chính đã có CI và nguồn file: r12 âm rõ (delta −0,0714 CI [−0,1014;−0,0414],
  p=3,9e−06), r13 không tín hiệu (−0,0028 CI [−0,0129;+0,0071], p=0,79), r10 3B không đạt
  (PASS_CORRECT 16 < 22, p=0,804).
- "Người ngoài chạy lại được" **chưa đạt** ở mức repo vì PA-26; đạt ở mức lệnh/tài liệu (README §5.10).

## 4. Khoảng trống còn lại (theo báo cáo từng task)

| Task | Khoảng trống | Mức độ |
|---|---|---|
| T2 | Trên corpus thật, tỉ lệ chunk còn dấu thanh thấp (18,6%); pipeline convert PDF là nút thắt. Test chỉ chứng minh công cụ đo, không sửa được corpus | đã ghi, chờ PA-1 |
| T4 | Không train ⇒ không chứng minh 4b tốt hơn bằng `PASS_CORRECT`; test token thật skip nếu thiếu tokenizer | chờ PA-11/PA-12 |
| T5 | Mục 5 đề bài ("lùi RRF") khác thiết kế đã đăng ký (ném lỗi); chưa build index header thật; chưa kiểm gold@6 811 item cho cấu hình TẮT trong đợt test | PA-18/PA-1 |
| T6 | 6b `n_filled=0` ⇒ chưa có kappa/P-R; 6c 0 câu thật; `referee_agreement.py` + `metric_ci.py` chưa có unit test | chờ nhãn tay/câu thật |
| T7 | Cache policy mới kiểm unit, chưa chứng minh cache-miss trên cache thật; `run_chain` chưa chạy chuỗi dài; PA-24 chưa xoá `tmp/`; PA-26 chưa đóng | chờ duyệt |

## 5. Phán quyết tổng

- **Test xanh và có hiệu lực**: đạt (1.011 passed; 65/65 mutation; referee `9f1179ccab74`).
- **Không sửa dụng cụ đo để qua cổng**: đạt (gate/verify/text_utils không đổi; các thay đổi gate chỉ
  là bản đề xuất tách rời).
- **Tái lập từ repo**: **chưa đạt** — PA-26 (35 file untracked + 6 file dirty). Đây là việc cần duyệt
  đầu tiên trước khi trình hội đồng.

## 6. Lệnh tái lập toàn bộ

```bash
# Toàn bộ test + chữ ký trọng tài
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c \
  "from tools.loop import verify; print(verify.referee_fingerprint())"

# 8 harness mutation (mỗi harness tự hoàn nguyên + kiểm SHA-256)
for f in tmp/mutation_check_t0.py tmp/mutation_check_t1.py tmp/mutation_check_t2.py \
         tmp/mutation_check_t3.py tmp/mutation_check_t4.py tmp/mutation_check_t5.py \
         tmp/mutation_check_t6.py tmp/mutation_check_t7.py \
         tmp/mutation_check_cache_policy.py; do
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe "$f" || echo "FAIL: $f"
done
```

## Phụ lục A — số công bố | số tính lại | khớp

| Số công bố | Cách tính lại | Kết quả | Khớp |
|---|---|---|---|
| 1.011 test xanh | `pytest tests -q` (25-10 11:55) | 1.011 passed, 29,79 s | có |
| Chữ ký `9f1179ccab74` | `verify.referee_fingerprint()` | trùng | có |
| 65/65 mutation bị bắt | tổng 8 harness: 5+4+5+7+7+10+10+17 | 65 | có |
| T7: 6/6 + 10/10 | `tmp/mutation_check_t7.log`, `tmp/mutation_check_cache_policy.log` | trùng | có |
| T6: 10/10 | `tmp/mutation_check_t6.log` | trùng | có |
| T4: 7/7 | `tmp/mutation_check_t4.log` | trùng | có |
| T5: 10/10 | `tmp/mutation_check_t5.log` | trùng | có |
| T3: 7/7 | `tmp/mutation_check_t3.py` + `docs/reports/test_T3.md` §3 | trùng | có |
| T2: 5/5 | `tmp/t2_mutation.log` | trùng | có |
| T1: 4/4 | `tmp/mutation_check_t1.py` + `docs/reports/test_T1.md` §2 | trùng | có |
| T0: 5/5 | `tmp/mutation_check_t0.py` + `docs/reports/test_T0.md` §4 | trùng | có |
| Golden T3 SHA-256 `e59b9ebb…` | `sha256sum tests/golden/…` | trùng | có |
| T4a `PASS_CORRECT` 14→16, p=0,804 | `data/loop/diag/t4_stats.json` | trùng | có |
| T5a r12 delta −0,0714 CI [−0,1014;−0,0414] | `data/loop/diag/reranker_paired_r11_r12.json` | trùng | có |
| T5b r13 delta −0,0028 CI [−0,0129;+0,0071], p=0,79 | `data/loop/diag/header_paired_r11_r13.json` | trùng | có |
| T6d tổng điểm 7,17 → 7,2 | phép tính lại độc lập | 7,17 | có |
| T6b 60 mẫu, `n_filled=0` | manifest + worksheet | trùng | có |
| HEAD `79a02e5` không tái lập cây test | `git status --short` (35 + 6) | đúng là **không** tái lập | có |
