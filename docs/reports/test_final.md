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
| T2 | corpus rebuild / chất lượng corpus | `tests/test_corpus_rebuild.py` | 81 | 6/6 | [`test_T2.md`](test_T2.md) |
| T3 | guardrail từ chối + golden cờ TẮT | `tests/test_t3_guardrails.py` + golden | 77 | 9/9 | [`test_T3.md`](test_T3.md) |
| T4 | cờ model 3B + pipeline SFT + bất biến dữ liệu SFT + giao diện generator | `test_loop_generator_model_flag.py`, `test_build_sft_from_round.py`, `test_t4_sft_invariants.py`, `test_t4_generator_contract.py`, `test_t4_gpu_slow.py` (slow) | 21 + 62 nhanh + 2 slow | 7/7 + 8/8 | [`test_T4.md`](test_T4.md) |
| T5 | reranker + contextual header | `test_t5_reranker_contract.py`, `test_t5_contextual_header.py` | 75 | 13/13 | [`test_T5.md`](test_T5.md) |
| T6 | cổng refusal tương đối + khung câu hỏi thật | `test_gate_refusal_relative_proposal.py`, `test_score_real_questions.py` | 15 | 10/10 | [`test_T6.md`](test_T6.md) |
| T7 | `run_chain` + khóa chính sách cache | `test_run_chain.py`, `test_cache_policy.py` | 37 | 17/17 | [`test_T7.md`](test_T7.md) |

Tổng mutation theo báo cáo: **79/79 bị bắt** (8 harness cũ: 68; T4 mới: 8; T5 thêm 3 ngày 25-10), mỗi lần đều hoàn nguyên **byte-identical** (SHA-256).
Không cộng dồn số test thành một phép cộng tuyến tính: các mốc baseline của 8 đợt chồng lấn nhau
(563 → 691 → 712 → 736 → 889 → 957 → 967 → 1.004 → 1.005 → 1.006 → 1.011 → 1.014 → 1.016 → 1.057 → 1.064). Con số chuẩn duy nhất là **toàn bộ `tests/`** ở §2.

## 2. Kiểm chứng cuối

### 2.1 Toàn bộ test

| Đại lượng | Giá trị | Nguồn |
|---|---|---|
| `pytest tests -q` | **1.064 passed, 2 skipped**, 3 warnings (21,02 s) | `tmp/pytest_t5_final_2.txt` |
| `T4_RUN_SLOW=1 pytest tests/test_t4_gpu_slow.py -q` | **2 passed** (79,04 s) | `tmp/pytest_t4_slow.log` |
| Chữ ký trọng tài | **`9f1179ccab74`** | `tmp/pytest_t4t6_final.txt` dòng cuối; test T0/T1/T2/T3 không đụng trọng tài |
| Golden T3 (cờ TẮT) SHA-256 | `e59b9ebb6b12c2d6844356f5861cc98d418c11b26f83a49fdae1f8f2ea1728b5` | `sha256sum tests/golden/t3_off_30items_head_f492f05.json` |
| Mutation T7 (run_chain + cache) | 6/6 + 10/10 | `tmp/mutation_check_t7.log`, `tmp/mutation_check_cache_policy.log` |
| Mutation T3 (đo lại 25-10 sau T7) | 9/9 | `tmp/t3_mutation_recheck_9.log` |
| Mutation T4 (đợt T4a/T4b gốc) | 7/7 | `tmp/mutation_check_t4.log` |
| Mutation T4 (bộ mới: 5 bất biến SFT, giao diện, cache key) | 8/8 | `tmp/mutation_check_t4_new.log` |
| Mutation T5 (đợt 25-10: thêm nhánh lùi RRF) | 13/13 | `tmp/mutation_check_t5.log` |
| Mutation T6 | 10/10 | `tmp/mutation_check_t6.log` |
| Mutation T0 (sau khi thêm test 22) | 5/5 | `tmp/mutation_check_t0.log` |
| Mutation T1 (sau khi thêm guard tập item) | 4/4 | `tmp/mutation_check_t1.log` |
| Mutation T2 (sau khi thêm `TestVerbatimPreservation`) | 6/6 | `tmp/t2_mutation_6.log` |

Không có test nào đỏ. Không sửa test cũ để xanh; hai lần mutation sống sót (T4a-M2 bản đầu, T6a-M1)
đã được xử lý bằng **đột biến mạnh hơn** và **một test biên mới**, không bằng hạ kỳ vọng.

### 2.2 Bất biến "cờ TẮT = hành vi cũ"

| Bất biến | Bằng chứng |
|---|---|
| Golden 30 item T3 khớp từng khoá | `test_t3_guardrails.py`, SHA-256 khối `core` `344d55cd…` |
| T3 TẮT: đầu ra bất biến cả khi env còn ngưỡng lever TẮT | `TestOffInvariantWhenDisabledLeversConfigured::test_dau_ra_van_trung_golden…` (25-10) |
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
PA-26 là điều kiện để fresh clone chạy lại **1.057 test**; hiện tại HEAD **chưa** tái lập được.

## 3. Kết luận chỉ từ số

- Bộ test hiện tại **1.064 xanh** (+2 slow tách riêng bằng `T4_RUN_SLOW=1`), trọng tài bất biến; 79/79 đột biến bị bắt ⇒ test có hiệu lực trên
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
| T2 | **Mục 9 ĐỎ: mất neo vàng 48,81% (389/797) > 2%** trên index mới; 3 tệp "khoảng trống" vẫn vào index (PA-7); 20 đoạn mục 8 chờ người duyệt. Unit test (81) khoá công cụ đo, không sửa được corpus | ĐỎ, chờ PA-17/PA-7/PA-1 |
| T3 | Khóa cache chế độ TẮT vẫn tách theo `DEC_*`/`EV_*`/`ANSWER_GUARD_*` khi env còn giá trị (PA-27; đầu ra không đổi); D chỉ chặn ở pre nên không một mình chứng minh guard sau sinh | chờ PA-27 |
| T4 | **Mục 5 ĐỎ do DỮ LIỆU**: 13/13 dòng train + 8/10 holdout > 768 token (min 1.016, max 1.707) nên kế hoạch QLoRA 4 GB không chạy được với artifact `t4b_r5r8r9r10`; bộ sinh giữ dòng thiếu thực thể vàng (luật 2/N) — **PA-28**. Không train ⇒ không chứng minh 4b tốt hơn bằng `PASS_CORRECT`. Adapter `models/qwen25_05b_sft_adapter` chứng minh *cơ chế* nạp LoRA, **không** đại diện chất lượng T4b (train trên dữ liệu QA mã nguồn, không phải T4b) | ĐỎ dữ liệu: PA-28; chờ PA-11/PA-12 |
| T5 | Mục 5 đã xử lý bằng cờ `RERANKER_FALLBACK` **mặc định TẮT** (bật mới lùi RRF; production giữ dừng loudly); gold@6 811 item cấu hình TẮT **đã kiểm tái lập 811/811 item** trùng r11 (0,7400); chưa build index header thật; chưa test chất lượng model thật | PA-18(b/c)/PA-1 |
| T6 | 6b `n_filled=0` ⇒ chưa có kappa/P-R; 6c 0 câu thật; `referee_agreement.py` + `metric_ci.py` chưa có unit test | chờ nhãn tay/câu thật |
| T7 | Cache policy mới kiểm unit, chưa chứng minh cache-miss trên cache thật; `run_chain` chưa chạy chuỗi dài; PA-24 chưa xoá `tmp/`; PA-26 chưa đóng | chờ duyệt |

## 5. Phán quyết tổng

- **Test xanh và có hiệu lực**: đạt (1.064 passed + 2 slow passed; 79/79 mutation; referee `9f1179ccab74`).
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

# 9 harness mutation (mỗi harness tự hoàn nguyên + kiểm SHA-256)
for f in tmp/mutation_check_t0.py tmp/mutation_check_t1.py tmp/mutation_check_t2.py \
         tmp/mutation_check_t3.py tmp/mutation_check_t4.py tmp/mutation_check_t4_new.py \
         tmp/mutation_check_t5.py tmp/mutation_check_t6.py tmp/mutation_check_t7.py \
         tmp/mutation_check_cache_policy.py; do
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe "$f" || echo "FAIL: $f"
done
```

## Phụ lục A — số công bố | số tính lại | khớp

| Số công bố | Cách tính lại | Kết quả | Khớp |
|---|---|---|---|
| 1.064 test xanh | `pytest tests -q` (25-10, sau T5 +7 test) | 1.064 passed, 2 skipped, 21,02 s | có |
| 2 slow test T4 (mục 8–9) | `T4_RUN_SLOW=1 pytest tests/test_t4_gpu_slow.py -q` | 2 passed, 79,04 s | có |
| Chữ ký `9f1179ccab74` | `verify.referee_fingerprint()` | trùng | có |
| 79/79 mutation bị bắt | tổng 9 harness: 5+4+6+9+7+10+13+10+17 (+ T4 mới 8) | 79 | có |
| T7: 6/6 + 10/10 | `tmp/mutation_check_t7.log`, `tmp/mutation_check_cache_policy.log` | trùng | có |
| T6: 10/10 | `tmp/mutation_check_t6.log` | trùng | có |
| T4: 7/7 + 8/8 | `tmp/mutation_check_t4.log`, `tmp/mutation_check_t4_new.log` | trùng | có |
| T5: 13/13 | `tmp/mutation_check_t5.log` | trùng | có |
| T3: 9/9 | `tmp/t3_mutation_recheck_9.log` (chạy lại 25-10: M1–M8) + §9.2 | trùng | có |
| T2: 6/6 | `tmp/t2_mutation_6.log` (chạy lại đủ M1–M6) | trùng | có |
| T1: 4/4 | `tmp/mutation_check_t1.py` + `docs/reports/test_T1.md` §2 | trùng | có |
| T0: 5/5 | `tmp/mutation_check_t0.py` + `docs/reports/test_T0.md` §4 | trùng | có |
| Golden T3 SHA-256 `e59b9ebb…` | `sha256sum tests/golden/…` | trùng | có |
| T4a `PASS_CORRECT` 14→16, p=0,804 | `data/loop/diag/t4_stats.json` | trùng | có |
| T5a r12 delta −0,0714 CI [−0,1014;−0,0414] | `data/loop/diag/reranker_paired_r11_r12.json` | trùng | có |
| T5b r13 delta −0,0028 CI [−0,0129;+0,0071], p=0,79 | `data/loop/diag/header_paired_r11_r13.json` | trùng | có |
| T6d tổng điểm 7,17 → 7,2 | phép tính lại độc lập | 7,17 | có |
| T6b 60 mẫu, `n_filled=0` | manifest + worksheet | trùng | có |
| HEAD `79a02e5` không tái lập cây test | `git status --short` (35 + 6) | đúng là **không** tái lập | có |
