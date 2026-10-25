# Báo cáo kiểm thử tổng kết — T0 → T7 + nghiệm thu cuối

Ngày đo cuối: 2026-10-25 (các đợt test chạy 24 → 25-10) · Nhánh `auto/overnight` ·
Người chạy: agent kiểm thử (chế độ tự trị).
Phạm vi: (A) tổng hợp **8 báo cáo test theo nhiệm vụ** (`docs/reports/test_T0.md` … `test_T7.md`);
(B) **6 mục nghiệm thu cuối** đã đăng ký trong đề — số lượng test, tái lập từng số công bố, cờ env mặc
định TẮT, quét secret/đường dẫn cá nhân, bất biến #7 + train-leak trên dữ liệu train cuối, và **ba
script kiểm câu hỏi hội đồng**.

Bản này **thay** bản chụp lúc 13:26 (khi repo mới ở `dac99a9`, 1.064 test). Bốn con số đã đổi và được
đính chính ngay trong bảng: (1) bộ test hiện **1.372 xanh** (1.338 trước hai đợt siết môi trường §14);
(2) tổng đột biến bị bắt là **135/135** chứ không phải "79/79" (126/126 trước đợt siết §14);
(3) delta r13 là **−0,0029** (bản cũ in −0,0028 do cắt số); (4) bảng tái lập số công bố mở từ 55 lên
**63 dòng, vẫn 0 LỆCH**.

**0 lượt gọi Gemini** cho toàn bộ công việc kiểm thử (mọi test dùng fake/stub/`tmp_path`). Không sửa
trọng tài (`tools/loop/verify.py`, `src/answer_guard.py`, `src/text_utils.py`) ⇒ chữ ký vẫn
**`9f1179ccab74`**; không sửa `tools/loop/gate.py`; không ghi vào `outputs/` hay `data/loop/rounds/`.

## 1. Tổng quan 8 nhiệm vụ + nghiệm thu cuối

| Task | Đối tượng | File test | Số test (đo lại bằng `--collect-only`) | Đột biến bị bắt | Báo cáo |
|---|---|---|---:|---:|---|
| T0 | noise floor + bộ đếm `[AnswerRescue]` | `tests/test_noise_floor.py` | 22 | 5/5 | [`test_T0.md`](test_T0.md) |
| T1 | `tools/diag/ablation_generation.py` | `tests/test_ablation_generation.py` | 29 | 4/4 | [`test_T1.md`](test_T1.md) |
| T2 | corpus rebuild / chất lượng corpus | `tests/test_corpus_rebuild.py` | 81 | 6/6 | [`test_T2.md`](test_T2.md) |
| T3 | guardrail từ chối + golden cờ TẮT | `tests/test_t3_guardrails.py` + golden | 77 | 9/9 | [`test_T3.md`](test_T3.md) |
| T4 | cờ model 3B + pipeline SFT + bất biến dữ liệu SFT + giao diện generator | `test_loop_generator_model_flag.py` 11, `test_build_sft_from_round.py` 10, `test_t4_sft_invariants.py` 29, `test_t4_generator_contract.py` 12, `test_t4_gpu_slow.py` 2 (slow) | 62 nhanh + 2 slow | 7/7 + 8/8 | [`test_T4.md`](test_T4.md) |
| T5 | reranker + contextual header + cờ `RERANKER_FALLBACK` | `test_t5_reranker_contract.py` 33, `test_t5_contextual_header.py` 42, `test_reranker_flag.py` 46 | 121 | 13/13 | [`test_T5.md`](test_T5.md) |
| T6 | cổng refusal tương đối + khung câu hỏi thật + validator trọng tài | `test_gate_refusal_relative_proposal.py` 9, `test_score_real_questions.py` 6, `test_t6_gate_refusal_and_regression.py` 28, `test_t6_referee_validation.py` 10, `test_t6_real_questions_and_metrics.py` 22 | 75 | 10/10 + 10/10 | [`test_T6.md`](test_T6.md) |
| T7 | `run_chain` + khóa chính sách cache + dọn `tmp/` + nhất quán docs | `test_run_chain.py` 11, `test_cache_policy.py` 26, `test_t7_chain_env_manifest.py` 19, `test_t7_cache_reuse_e2e.py` 18, `test_t7_tmp_cleanup.py` 33, `test_t7_docs_consistency.py` 36 | 143 | 6/6 + 10/10 + 20/20 | [`test_T7.md`](test_T7.md) |
| **Nghiệm thu cuối** | 4 máy kiểm: cờ env, secret, dữ liệu train, 3 câu hỏi hội đồng + 1 máy siết **phòng thủ môi trường đo** (D-35 stdin, D-36 console) | `test_final_env_flag_defaults.py` 41, `test_final_secret_scan.py` 14, `test_final_train_data_audit.py` 13, `test_final_council_scripts.py` 43, `test_final_subprocess_stdin_guard.py` 34 | **145** | 18/18 + **9/9** (§14) | mục 4–7 + §14 dưới đây |

Ghi chú cộng dồn: không cộng tuyến tính số test của 8 đợt (mốc baseline chồng lấn
563 → 691 → 712 → 736 → 889 → 957 → 967 → 1.004 → 1.005 → 1.006 → 1.011 → 1.014 → 1.016 → 1.057 →
1.064 → 1.124 → 1.228 → **1.338** → **1.359** → **1.371** → **1.372**). Con số chuẩn duy nhất là phép đo toàn bộ `tests/` ở mục 2.

## 2. Mục nghiệm thu 1 — bộ test cuối, thời gian, số test đỏ

Đo lúc 18:3x ngày 25-10 trên cây hiện tại (`b6c29d2` + batch test nghiệm thu cuối):

| Đại lượng | Lệnh | Kết quả đo được |
|---|---|---|
| Toàn bộ test | `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q` | **1338 passed, 5 skipped, 3 warnings — 60,25 s** (lượt 2 sau khi sửa docs: 75,32 s; lượt 3 sau khi sửa fixture secret-scan: 90,71 s — **cùng 1338/5**;
thời gian tăng dần vì ngày càng nhiều test phải chạy `git ls-files` trên cây đã track). **Lượt 4** sau commit
`c508876` (đo lại 25-10 19:0x, stdin đóng): **1338 passed / 5 skipped — 87,59 s**. **Lượt 5** sau lớp siết
stdin (D-35) + 21 test mới: **1359 passed / 5 skipped — 126,52 s** (`tmp/pytest_after_d35.txt`). **Lượt 6**
sau lớp siết console (D-36) + 12 test nữa: **1371 passed / 5 skipped — 90,77 s** (`tmp/pytest_after_d36.txt`). **Lượt 7 — chốt batch 3** (thêm 1 điều khiển âm cp1258, sau khi sửa 1 dòng tự nhiễm đường dẫn cá nhân §14.5): **1372 passed / 5 skipped — 91,44 s** (`tmp/pytest_final_batch3.txt`) |
| Test chậm (GPU/Ollama) | `T4_RUN_SLOW=1 … pytest tests/test_t4_gpu_slow.py -q` | **2 passed — 82,32 s** |
| Chữ ký trọng tài | `python -c "from tools.loop import verify; print(verify.referee_fingerprint())"` | **`9f1179ccab74`** |
| 5 file nghiệm thu cuối | `pytest tests/test_final_*.py -q` | trước siết: 110 passed, 1 skipped — 24,98 s · giữa đợt: 143 / 1 — 44,96 s · **chốt batch 3: 144 passed / 1 skipped — 44,33 s** (145 test collect-only, `tmp/pytest_final5_batch3.txt`). Chạy cùng lệnh bằng **interpreter hệ thống với stdin đóng** (`< /dev/null`): trước siết **1 FAILED + 9 ERROR**, sau siết **144 passed / 1 skipped — 45,60 s** (`tmp/pytest_final5_py314_stdin_closed_batch3.txt`) — xem §14 |
| Test ĐỎ | — | **0** |

5 lượt skip đều có lý do đăng ký, không phải test bị ẩn lỗi:

| Skip | Lý do |
|---|---|
| `test_t4_gpu_slow.py` (2) | cần GPU/Ollama; có cổng `T4_RUN_SLOW=1` — đã chạy thật, 2 passed |
| `test_t7_tmp_cleanup.py` (2) | Windows từ chối tạo symlink trong sandbox test (`_skip` tự nguyện, có thông báo) |
| `test_final_env_flag_defaults.py:54` | `RERANKER_KEEP_CANDIDATES` không có accessor đơn — vẫn bị kiểm tĩnh ở lớp 2 của cùng module |

3 warnings còn lại là `FutureWarning` của `google.generativeai` (kích hoạt khi import `src/generator.py`)
và 2 `DeprecationWarning` từ `chromadb` / `langchain-community` — đều ở site không do phiên này sửa.

## 3. Mục nghiệm thu 2 — tái lập TỪNG số đã công bố (63 dòng)

Máy tái lập: `tools/diag/final_number_audit.py` → `tmp/final_number_audit.json` (**55 dòng, `khop=True`
cả 55** ở lượt chụp lần đầu 18:3x; **63 dòng / `0 dòng LỆCH`** sau đợt siết môi trường,
`tmp/final_number_audit_batch3.json`); bảng mở rộng `tmp/final_number_audit_table.md`. Mỗi dòng ghi rõ
cách tính lại (lệnh đọc artifact hoặc hàm thật của repo), không chép miệng.

| Task | Số công bố | Cách tính lại | Tính lại | Khớp |
|---|---|---|---|---|
| T0 | 22 test noise floor | `pytest --collect-only -q tests/test_noise_floor.py` | 22 | KHỚP |
| T0 | 5/5 đột biến bị bắt | `tmp/mutation_check_t0.log` (đếm khối `Mutation :`) | 5/5 | KHỚP |
| T1 | 29 test ablation_generation | collect-only | 29 | KHỚP |
| T1 | 4/4 đột biến bị bắt | `tmp/mutation_check_t1.log` | 4/4 | KHỚP |
| T2 | 81 test corpus rebuild | collect-only | 81 | KHỚP |
| T2 | 6/6 đột biến bị bắt | `tmp/t2_mutation_6.log` | 6/6 | KHỚP |
| T3 | 77 test guardrails | collect-only | 77 | KHỚP |
| T3 | 9/9 đột biến bị bắt | `tmp/t3_mutation_recheck_9.log` | 9/9 | KHỚP |
| T3 | golden SHA-256 `e59b9ebb…8b5` | sha256 file golden | `e59b9ebb6b12c2d6844356f5861cc98d418c11b26f83a49fdae1f8f2ea1728b5` | KHỚP |
| T4 | 11 + 10 + 29 + 12 = 62 test nhanh | collect-only 4 file | 62 | KHỚP |
| T4 | 2 test slow (mặc định skip) | collect-only | 2 | KHỚP |
| T4 | 7/7 đột biến (bộ test cũ) | `tmp/mutation_check_t4.log` | 7/7 | KHỚP |
| T4 | 8/8 đột biến (bộ test mới) | `tmp/mutation_check_t4_new.log` | 8/8 | KHỚP |
| T4 | PASS_CORRECT 14→16 | đọc `round_summary_full.json` r9/r10 THẬT + `data/loop/rounds/r10/t4_stats.json` | r9=19, r10=16; r5=14 → r10=16 | KHỚP |
| T4 | CI [−0,06 ; +0,10], p=0,804 | `t4_stats.json` pairs[0] (r5 vs r10) | CI [-0.06, 0.1] p=0.803619384765625 | KHỚP |
| T4 | trần 1.024 token → 4.156,9 MiB | row `length_tokens=1024` của `t4b_memory_probe_len.json` | peak_allocated_mib=[4156.9, 4164.8] | KHỚP |
| T4 | 2 slow passed (79,04 s) | `tmp/pytest_t4_slow.log` + chạy lại 25-10 | 2 passed in 79.04s // lần chạy hôm nay **2 passed in 82.32s** | KHỚP |
| T5 | 33 + 42 = 75 test | collect-only 2 file | 75 | KHỚP |
| T5 | 46 test cờ `RERANKER_FALLBACK` | collect-only | 46 | KHỚP |
| T5 | 13/13 đột biến bị bắt | `tmp/mutation_check_t5.log` | 13/13 | KHỚP |
| T5 | gold = 0,7400 và FAIL_RETRIEVAL 182 | gate.metrics trên round đã đóng **r11** | gold=0.7400 (n=811, 700 có vàng, FAIL_RETRIEVAL=182) | KHỚP |
| T5 | delta −0,0714 CI [−0,1014; −0,0414] p=3,9e−06 | `reranker_paired_r11_r12.json` | gold_delta=-0.0714 CI [-0.1014, -0.0414] p=3.865427244352971e-06 | KHỚP |
| T5 | delta −0,0029 CI [−0,0129; +0,0071] p=0,79 | `header_paired_r11_r13.json` (ĐÍNH CHÍNH: từng in −0,0028 do cắt số) | gold_delta=-0.0029 CI [-0.0129, 0.0071] p=0.79052734375 | KHỚP |
| T6 | 9 + 6 = 15 test | collect-only 2 file | 15 | KHỚP |
| T6 | 28 + 10 + 22 = 60 test | collect-only 3 file | 60 | KHỚP |
| T6 | 10/10 đột biến (bộ cũ) | `tmp/mutation_check_t6.log` | 10/10 | KHỚP |
| T6 | 10/10 đột biến (bộ mới) | `tmp/mutation_check_t6_tests.log` | 10/10 | KHỚP |
| T6 | 60 mẫu, `n_filled=0` | manifest + đếm nhãn trong `referee_labeling_r5.jsonl` | n_selected=60, n_filled=0, n_rows=60 | KHỚP |
| T6 | Wilson 7/10 = [0,3968; 0,8922] | `report_metrics.wilson_ci(7, 10)` | [0.3968, 0.8922] | KHỚP |
| T6 | điểm trọng số 7,17 và 7,10 | `weighted_score()` hai bộ điểm 9,2/8,2/7,0/8,5/4,0 và 9,0/8,0/7,0/8,5/4,0, trọng số 0,20/0,15/0,20/0,20/0,25 | 7.17 và 7.10 | KHỚP |
| T6 | CI PASS_CORRECT = [0,08; 0,21] | `metric_ci_r7_full.json` | n_metric=100, điểm 0.14, ci95=[0.08, 0.21] | KHỚP |
| T7 | 11 + 26 = 37 test | collect-only 2 file | 37 | KHỚP |
| T7 | 19 + 18 + 33 + 36 = 106 test | collect-only 4 file | 106 | KHỚP |
| T7 | 6/6 đột biến run_chain | `tmp/mutation_check_t7.log` | 6/6 | KHỚP |
| T7 | 6/6 đột biến run_chain (chạy lại) | `tmp/mutation_check_t7_rerun_dot2.log` | 6/6 | KHỚP |
| T7 | 10/10 đột biến cache_policy | `tmp/mutation_check_cache_policy.log` | 10/10 | KHỚP |
| T7 | (6+10) = 16/16 | tổng hai log cũ (ĐÍNH CHÍNH cho 17/17 từng in ở §2.3/§3 của bản cũ) | 16/16 | KHỚP |
| T7 | 20/20 đột biến docs checker | `tmp/mutation_check_t7_dot2.log` (dòng kết luận ghi "0 lọt") | 20/20 | KHỚP |
| T7 | `DEFAULT_CACHE_TOKEN = d0b4c6a65f83` | `policy_cache_token()` dưới env đã bóc cờ lever | d0b4c6a65f83 (deviation=None) | KHỚP |
| T7 | checker: 264 lệnh · 100 đường dẫn · 4 help · 0 lỗi · 5 cảnh báo · 30 dòng sổ | `tmp/docs_check_t7_dot3.json` + chạy lại `referenced_paths` | 264 · 100 · 4 · 0 · 5 · 30 | KHỚP || T7 | tmp_cleanup 164 mục · 95 GIỮ · 69 đề xuất · 26,4 MB · không xoá gì | `tmp/cleanup_report_t7.json` | 164 · 95 · 69 · 26.410.968 B · applied=False · deleted=[] | KHỚP |
| T7 | gold = 0,5186 với 811 item, 700 item vàng | gate.metrics trên round đã đóng **r0** | gold=0.5186 (n=811, 700 có vàng, FAIL_RETRIEVAL=337) | KHỚP |
| T7 | 811/811 verdict trùng, 0 đổi chiều, 811/811 top, gold 0,5186 | `tmp/compare_r0_repro.json` | n_common=811, agree=811, flips=0, top6_exact=811/811, 0.5186→0.5186 | KHỚP |
| T7 | manifest dry-run = manifest lượt chạy (`295413c196de`) | sha256 hai file | trùng | KHỚP |
| T2 | mất neo vàng 389/797 = 0,4881 với ngưỡng 0,02 ⇒ ĐỎ | `data/loop/diag/corpus_check/corpus_check.json` `gold_coverage` | 389/797 = 0.4881, red=True, ngưỡng 0.02 | KHỚP |
| T5 | verdict trùng 811, top trùng 811, sources toàn bộ 809 (tái lập cấu hình TẮT) | `reranker_paired_family.json` `reproducibility.off_vs_closed` | 811 · 811 · 809, mismatched=2 (tie-break hạng sâu) | KHỚP |
| T6 | refusal 0,61→0,69 và fabrication 0,0256→0,0323 ⇒ cổng không ĐẠT | `data/loop/rounds/r5/gate_vs_r3_full.json` | đúng nguyên, passed=False | KHỚP |
| T7 | 11+26+19+18+33+36 = 143 test | collect-only 6 file T7 | 143 | KHỚP |
| Chung | chữ ký trọng tài `9f1179ccab74` | `verify.referee_fingerprint()` | 9f1179ccab74 | KHỚP |
| Chung | SHA gate.py `bf4bda89d8a360abbba25742` | sha256 `tools/loop/gate.py` | trùng | KHỚP |
| Chung | 1.004 passed | `tmp/pytest_t7_final.txt` | 1004 passed, 3 warnings in 27.02s | KHỚP |
| Chung | 1.064 passed, 2 skipped | `tmp/pytest_t5_final_2.txt` | 1064 passed, 2 skipped, 3 warnings in 21.02s | KHỚP |
| Chung | 1.124 passed, 2 skipped | `tmp/pytest_t6_final.txt` | 1124 passed, 2 skipped, 3 warnings in 26.92s | KHỚP |
| Chung | 1.228 passed, 4 skipped | `tmp/pytest_t7_dot2_final.txt` | 1228 passed, 4 skipped, 3 warnings in 36.68s | KHỚP |
| Chung | 1.228 passed, 4 skipped (chạy lại) | `tmp/pytest_t7_dot3_final.txt` | 1228 passed, 4 skipped, 3 warnings in 33.24s | KHỚP |
| Chung | 1.338 passed, 5 skipped | `tmp/pytest_post_commit_venv.txt` (sau commit `c508876`, stdin đóng) | 1338 passed, 5 skipped, 3 warnings in 87.59s | KHỚP |
| Chung | 1.359 passed, 5 skipped | `tmp/pytest_after_d35.txt` (sau lớp siết stdin D-35) | 1359 passed, 5 skipped, 3 warnings in 126.52s | KHỚP |
| Chung | 1.371 passed, 5 skipped | `tmp/pytest_after_d36.txt` (sau cả hai lớp siết D-35 + D-36) | 1371 passed, 5 skipped, 3 warnings in 90.77s | KHỚP |
| NCC | 34 test phòng thủ môi trường của máy kiểm | collect-only `test_final_subprocess_stdin_guard.py` | 34 | KHỚP |
| NCC | 9/9 đột biến phòng thủ môi trường | `tmp/mutation_check_stdin_guard.log` (dòng kết quả) | 9/9 | KHỚP |
| Chung | 1.372 passed, 5 skipped | `tmp/pytest_final_batch3.txt` (chốt batch 3) | 1372 passed, 5 skipped, 3 warnings in 91.44s | KHỚP |
| NCC | 144 passed, 1 skipped | `tmp/pytest_final5_batch3.txt` (bộ nghiệm thu cuối, venv) | 144 passed, 1 skipped, 3 warnings in 44.33s | KHỚP |
| NCC | 144 passed, 1 skipped | `tmp/pytest_final5_py314_stdin_closed_batch3.txt` (interpreter hệ thống, stdin đóng) | 144 passed, 1 skipped, 3 warnings in 45.60s | KHỚP |

**Đính chính "79/79"**: bản 13:26 cộng tay 9 harness ra "79/79", nhưng chính phép ghi ngay trong bảng đó
(5+4+6+9+7+10+13+10+17) đã là **81**, và nó **thiếu** 3 harness chạy sau (T6 bộ mới 10, T7 docs dot2 20,
nghiệm thu cuối 18). Sổ cái đo lại từ 13 log (mục 8) là **126/126** — sau đợt phòng thủ môi trường, sổ cái
mục 8 là **135/135** (thêm harness D-35 + D-36 gồm 9 đột biến).

**Bảng này lớn dần 55 → 63 dòng (không phải lệch)**: 8 dòng cuối thêm khi đo hai lớp phòng thủ môi trường
(§14). Số đã công bố của T0–T7 **không đổi một giá trị nào** — `0 dòng LỆCH` cả trước lẫn sau đợt siết.
Hai con số **tăng hợp lý** khác sau khi bảng này chụp lần đầu: sổ `DECISION_LOG` từ **30 → 36 dòng**
(D-32…D-36), và `tools/diag/docs_consistency_check.py --scope all` chạy lại chiều 25-10 vẫn
**264 lệnh · 100 đường dẫn · 0 lỗi · 5 cảnh báo** (`[T7-docs] kết luận: SẠCH LỖI`).

## 4. Mục nghiệm thu 3 — mọi cờ lever mới mặc định TẮT (+ golden)

Máy kiểm: `tools/diag/env_flag_audit.py` → `tmp/env_flag_audit.json`; test `tests/test_final_env_flag_defaults.py` (41).

| Lớp kiểm | Nội dung | Kết quả |
|---|---|---|
| 1. Khai báo | 13 cờ lever của T3/T4/T5/T7 (`ENABLE_DECOUPLED_REFUSAL`, `ENABLE_EVIDENCE_SELECTION`, `ENABLE_ANSWER_GUARD`, `OLLAMA_MODEL`, `LOCAL_SLM_MODEL`, `ENABLE_RERANKER`, `RERANKER_KEEP_CANDIDATES`, `ENABLE_CONTEXTUAL_HEADER`, khóa chính sách cache, các ngưỡng `DEC_*`/`EV_*`/`RESCUE_*`) | `n_total=13 · dương_tính=0 · thu_tu=13 · lỗi=0` |
| 2. Code default | mọi site đọc env | không literal nào là `"1"`; helper duy nhất có default riêng: `src/reranker.py::_flag = "0"` |
| 3. `setdefault` ngầm | quét `src/` + `tools/loop/` (đường production) | `setdefault_forced_on = 0`; 2 site ép bật nằm ở **`tools/diag/reranker_cost_probe.py:220-221`** (script đo chi phí, không phải đường production) — ghi vào `setdefault_chu_y`, không gán lỗi |
| 4. `.env.example` | 26 khóa khai báo | **0 khóa lever** bị bật (`env_example_not_off = {}`); 5 khóa bật là chức năng có trước vòng lặp: `GENERATION_CACHE`, `QWEN_FALLBACK`, `ENABLE_HYBRID_SEARCH`, `ENABLE_QUERY_EXPANSION`, `OCR_ENABLED` → đề xuất mới PA-30 |
| 5. Chain | `tools/loop/chains/*.json` | đúng 1 chain bật lever: `t5a_reranker.json` (`ENABLE_RERANKER=1`, `RERANKER_KEEP_CANDIDATES=1`) — chain đo r12, có manifest ghim env |
| 6. **Golden chạy thật** | chạy lại `tools/diag/t3_golden_dump.py` trên cây hiện tại với **mọi cờ để mặc định** | khối `core` (30 lượt: answer/contexts/sources/prompt/keys) **trùng từng byte** với `tests/golden/t3_off_30items_head_f492f05.json`, sha256 = `344d55cd35ec64b876d1f7580724eb968f158a21fbf42c64a28b54d3c8784b11`; `meta.pipeline_has_t3_fields` = `True` ở cây này / `False` ở golden baseline; hai trường T3 là `None` khi cờ TẮT |
| 7. "Tắt = cũ" ở tầng khác | `test_t5_reranker_contract.py` (cờ TẮT trả đúng object + thứ tự, không nạp reranker), `test_loop_generator_model_flag.py` (`ollama_model=None`, `LocalSLM {}`), `test_cache_policy.py` (cache key mặc định đúng 4 trường cũ), T3 `TestOffInvariantWhenDisabledLeversConfigured` | xanh; golden T3 vẫn khớp cả khi env còn giá trị ngưỡng của lever đang TẮT (PA-27 chỉ tách khóa cache, không đổi đầu ra) |

Kết luận mục 4: **đạt** — không có con đường nào (khai báo, mã, `setdefault`, chain, `.env.example`) bật
lever ngầm cho người clone repo; golden là bằng chứng chạy thật, không phải assert tĩnh.

## 5. Mục nghiệm thu 4 — quét secret / đường dẫn cá nhân / PII

Máy quét: `tools/diag/secret_scan.py` → `tmp/secret_scan.json`; test `tests/test_final_secret_scan.py` (14).

| Chỉ số | Giá trị |
|---|---|
| File trong phạm vi / đã quét | 269 / 237 |
| Tổng dòng khớp | 296 |
| `BI_MAU` (placeholder đã biết, vd `your…(19 ký tự)`) | 207 — trong đó 204 là "Placeholder đã biết"; 60 dòng rơi vào `tests/golden/…` (văn bản nhân tạo của golden) |
| `DU_CAO_NHAN_HOC` | 89 dòng trên **8 file** |
| Secret thật (Google `AIza…`, AWS, `sk-…`, GitHub, Slack, private key, JWT dài, gán key/token giá trị dài) | **0** — `secret_hits = []` |
| Đường dẫn theo tên user (Windows/Unix) | **0** — `duongdan_hits = []` |
| Email tổ chức/cá nhân | 24 dòng (trong dữ liệu QA/eval mẫu) |
| Số điện thoại VN (`0xxxxxxxxx` / `+84…`) | 65 dòng |
| Căn cước/MSSV/định danh dài (chỉ tính khi dòng có từ khoá định danh) | 0 |

8 file có cảnh báo nhân thân (số dòng): `data/loop/diag/referee_labeling_r5.jsonl` 28,
`data/loop/diag/referee_labeling_r5.md` 28, `data/loop/diag/b_gemini_top6/rows.jsonl` 11,
`data/loop/diag/a_oracle_qwen/rows.jsonl` 6, `data/loop/diag/c_gold_window_qwen/rows.jsonl` 6,
`outputs/ab_results_without_classifier.json` 4, `outputs/ab_results_with_classifier.json` 3,
`data/loop/diag/corpus_diagnostics/manual_20_segments.txt` 3. Toàn bộ là **dữ liệu kiểm thử trích từ tài
liệu nội bộ của trường**, đang untracked nên chưa từng được push. Đề xuất PA-31: mask trước khi đưa vào
commit theo PA-26.

**Quét lại sau commit `a170e92`** (`tmp/secret_scan_post_commit.json`), lượt chốt batch 3 trước stage (`tmp/secret_scan_batch3.json`) và lượt **sau `git add`** (`tmp/secret_scan_post_stage.json`): số phình đúng phần file mới vào track và phần guard mới; **hai con số nghiệp vụ không đổi** — `SECRET_COTHAT = 0`, `DU_CAO_NHAN_HOC = 89 dòng / 8 file`.

| Chỉ số | Trước commit (`tmp/secret_scan.json`) | Sau `a170e92` | Chốt batch 3, **sau `git add`** (`tmp/secret_scan_post_stage.json`) |
|---|---|---|---|
| File ứng viên / đã đọc | 269 / 237 | 281 / 249 | **282 / 250** (+1: `tests/test_final_subprocess_stdin_guard.py` vừa vào track — trước stage là 281/249) |
| Tổng dòng khớp | 296 | 339 | 340 |
| `BI_MAU` | 207 | 250 | 251 (+1: khối guard `reconfigure("utf-8", errors="replace")` mới nằm trong file tracked, máy quét phân loại là mẫu; file test mới **không** thêm mẫu nào) |
| `DU_CAO_NHAN_HOC` | **89 dòng / 8 file** | **89 dòng / 8 file** (không đổi) | **89 dòng / 8 file** (không đổi) |
| `SECRET_COTHAT` / `DUONG_DAN_CA_NHAN` | **0 / 0** | **0 / 0** | **0 / 0** — nhưng **từng báo 1 đường dẫn** ở lượt chạy 19:5x, xem §14.5 |

**Sự cố đã gặp, xử lý bảo thủ, ghi nguyên**: ngay sau commit `a170e92`, **3 test của `TestHienTrangRepo`
đỏ** — vì chính các **mẫu gieo để chứng minh răng** trong `tests/test_final_secret_scan.py` (chuỗi key dạng
`AIza…`, khối PEM, đường dẫn `C:\Users\…` và `/home/…`, email/điện thoại/MSSV) biến thành file tracked nên
rơi vào phạm vi `tracked_files()`: máy quét báo 4 dòng `SECRET_COTHAT` + 4 dòng `DUONG_DAN_CA_NHAN` và PII
tăng 89 → 93. Đây **không phải repo có secret**, là **máy kiểm tự nhiễm phạm vi của chính nó**. Cách sửa:
**không nới máy quét, không hạ kỳ vọng test** — dựng chuỗi mẫu **tại runtime** bằng helper `_ghep()` để
literal không còn nằm trong source đã commit, trong khi máy quét vẫn buộc phải bắt được chuỗi hoàn chỉnh khi
nó được ghi ra `tmp_path` (4 test răng M1/M2/M3 + test redact vẫn xanh). Sau sửa:
`pytest tests/test_final_secret_scan.py -q` = **14 passed** và quét lại cho **0 secret / 0 đường dẫn /
89 PII / 8 file** đúng như công bố. Bài học đăng ký: khi phạm vi quét lấy từ `git ls-files`, **file test của
chính máy quét cũng phải "sạch hình dạng secret"** ⇒ phải chạy `--scope tracked` **sau** khi stage, không chỉ
trước; và test ghim hiện trạng (pinned current-state) là thứ phát hiện loại nhiễm này — nó đã làm đúng việc.

## 6. Mục nghiệm thu 5 — bất biến #7 + train-leak trên dữ liệu train cuối

Máy kiểm: `tools/diag/train_data_audit.py` → `tmp/train_data_audit.json`; test `tests/test_final_train_data_audit.py` (13).

| Kiểm | Số đo | Kết luận |
|---|---|---|
| Đếm dòng 12 file dữ liệu train vs manifest | `total_dong = 10.619`; `so_file_khop_manifest = 12`; `so_file_lech_manifest = 0` | KHỚP |
| Train↔val↔benchmark theo **nội dung** | `tong_roi_le_thuc = 0` | **không leak nội dung** |
| Train↔val↔benchmark theo **id trùng tên** | 3 va chạm: `code_tests-00049` (train↔val), `refusal-00380`, `router_config-00237` (train↔benchmark seed); `roi_le_theo_cau_hoi = []`, `roi_le_theo_text_classifier = []` ⇒ cùng id nhưng khác nội dung | Không phải leak; **định danh không độc nhất** → PA-32 |
| `retrieval_query` trùng nhưng khác `positive` | 82 (số tham chiếu, không tính là leak) | ghi nguyên |
| Bất biến #7 (dòng train tự chứa đáp án) trên code-QA | `n_rows = 1635`, `co_trich_file = 1049`, `file_thieu = []`, `line_vuot = []`, `dinh_danh_khong_co = []`, `dinh_danh_kiem_tra = 890`, `ok = True` | ĐẠT |
| Bất biến #7 trên artifact SFT của vòng lặp | `t4b_r5` 9 train + 5 holdout; `t4b_r5r6r7` 12 + 4; `t4b_r5r8r9r10` 13 + 10 — **ĐỎ chỉ ở check `5_format_and_length`** (dòng > 768 token) | trùng T4 mục 5 / PA-28, PA-11, PA-12 |

## 7. Mục nghiệm thu 6 — ba script kiểm câu hỏi hội đồng

Ba script **chỉ-đọc**, dựng lại số từ artifact đã đóng, in kèm đường dẫn nguồn, có `--json`, và mã thoát
chính là phán quyết của máy kiểm (0 = mọi dòng đối chiếu khớp). Test:
`tests/test_final_council_scripts.py` (43 case, gồm 9 case đột biến nội tiến trình); harness 18 đột biến:
`tmp/mutation_check_final_council.log`.

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/council_check_fabrication.py --json tmp/council_fabrication.json   # exit 0
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/council_check_referee.py    --json tmp/council_referee.json        # exit 0
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/council_check_gold6.py      --json tmp/council_gold6.json          # exit 0
# bài in đầy đủ đã lưu: tmp/council_fabrication.txt, tmp/council_referee.txt, tmp/council_gold6.txt
```

### 7.1 "Hệ thống có bịa câu trả lời không?" — `tools/diag/council_check_fabrication.py`

Định nghĩa "bịa" lấy nguyên văn từ trọng tài: `FAIL_FABRICATED` (chunk vàng **đã** ở trong cửa sổ mà câu
trả lời vẫn có ≥1 khẳng định số/mã/tên riêng không tìm thấy trong contexts + câu hỏi + tên nguồn),
`FAIL_CONFIRMED_FALSE_PREMISE` (xác nhận con số SAI của câu bẫy), `FAIL_HALLUCINATED_ON_UNANSWERABLE`
(không từ chối câu ngoài phạm vi).

Số đo lại từ 10 round full đã đóng (1.000 dòng): **380 câu đã trả lời**, **7 câu có khẳng định trái ngữ
cảnh**; tỉ lệ tái lập = tỉ lệ công bố trên **cả 10 round (0 dòng LỆCH)**; ca nặng **43 = FAB 7 / CFP 6 /
HOU 30**. Điểm mấu chốt khi trình hội đồng: 7 lượt FAB **chỉ là 1 item khác nhau** (`S115028976296200`,
khẳng định `number:12.000.000`) lặp qua nhiều round; CFP 4 item; HOU 13 item; **tổng 18 item khác nhau**.
CI 95% bootstrap có cặp 10.000 lượt seed 20261023: r5 `0,0323 [0,0000; 0,0968]`, r7 `0,0263 [0,0000; 0,0789]`.

Khoảng trống tự công bố: **36/43 ca nặng có `unsupported` rỗng** ⇒ thước `fabrication_rate_on_answered`
KHÔNG thấy chúng (nên "fabrication = 0,0000" ở r8/r9/r10 chỉ nghĩa là "không có khẳng định trái ngữ
cảnh", không nghĩa là "không trả lời câu ngoài phạm vi" — r8 vẫn có 12 ca HOU); `grounding_score ≈ 1,0`
trên 373/380 câu ⇒ mù với lớp "đúng căn cứ nhưng lạc đề"; guardrail production mặc định TẮT
(`ENABLE_ANSWER_GUARD=0`, `ANSWER_GUARD_MIN_SCORE=0.6`, `ANSWER_GUARD_MAX_UNSUPPORTED=1`) trong khi **mọi
round đo đều bật guard** ⇒ con số bịa đặt đo được là của cấu hình có guard, không phải cấu hình mặc định.

### 7.2 "Trọng tài có đáng tin không?" — `tools/diag/council_check_referee.py`

| Lớp | Số đo | Phán quyết của máy kiểm |
|---|---|---|
| Chữ ký dụng cụ đo | `9f1179ccab74`; **19** round/phase đã đóng có ghi chữ ký; **1** chữ ký duy nhất; round lệch: không có | ĐẠT |
| Tính tất định | chấm lại **1.000/1.000** câu của 10 round từ `full.jsonl`: cùng verdict + cùng `gold_in_top_k` + cùng số khẳng định trái ngữ cảnh; **0 lệch**, 1,57 s | ĐẠT |
| Không đọc env | câu `C126485669658863` (r7): sạch `PASS_CORRECT` / đục `PASS_CORRECT` với 8 biến env gây nhiễu | ĐẠT |
| File tạo nên trọng tài | `verify.py 6cc636689a8e` (**chưa commit**), `answer_guard.py 40946176bc78` (**chưa commit**), `text_utils.py 5f810aa52b6b` (tracked-sạch) | lỗ PA-26 |
| Cổng khóa chữ ký | chạy thật `gate.compatibility()` → từ chối: `trọng tài khác phiên bản (candidate=9f1179ccab74, baseline=000000000000)…`; `gate.py bf4bda89d8a360abbba25742` (chưa commit) | ĐẠT |
| Độ nhạy luật so khớp số (bản nghiêm khắc, CHỈ ĐO) | r5 6 verdict đổi chiều (1 PASS_CORRECT), r8 1 (0), r9 0 (0), r10 4 (2) ⇒ **11 verdict** | ghi nguyên, không giảm nhẹ |
| Đồng thuận với người | 60 mẫu phát ra, **`n_filled = 0`**, kappa/accuracy = — | **CHƯA có bằng chứng** |
| Điểm mù | 373/380 câu đã trả lời `grounding = 1,0`; 36/43 ca nặng `grounding = 1,0` | bắt được câu TRÁI ngữ cảnh, không bắt được câu ĐÚNG ngữ cảnh nhưng LẠC ĐỀ |

Trả lời ngắn: **đáng tin về tính tất định và tính độc lập với env — đã chứng minh bằng chạy lại; chưa có
bằng chứng đồng thuận với con người; chưa tái lập được từ fresh clone** (hai file trọng tài chưa vào git).

### 7.3 "`gold@6 = 0,5186` nghĩa là gì?" — `tools/diag/council_check_gold6.py`

Mẫu: **811 câu**, **700 có chunk vàng** (mẫu số thật), **111 không có** (HUMAN 97 + REFUSE_OOD 8 +
REFUSE_MISSING_DOC 6) ⇒ gold@6 **mù với 111 item**. Tái lập từng round từ `verdicts_retrieval.jsonl`:
r0 `363/700 = 0,5186` (hạng 1:202 2:65 3:53 4:24 5:12 6:7), r1 `0,7657`, r2 `0,7400`, r4 `0,7429`,
r11 `0,7400`, r12 `0,6686`, r13 `0,7371`, r14_repro_off `0,7400`, r15_repro_on `0,6686`. Đối chiếu 7 file
`gate_vs_*retrieval.json`: **0 dòng LỆCH**.

Ba điều nó **không** nói, kèm số: (a) không nói câu trả lời đúng — r7 có gold 64/80 = **0,80** nhưng
PASS_CORRECT **14**, overrefusal 36, retrieval 17, incomplete 12; (b) không phủ hết mẫu — 111 item bị loại
khỏi mẫu số; (c) trần của xếp hạng — ở r11 (pool 12) chunk vàng vào pool **575/700 = 0,8214** nhưng chỉ
**518** vào top-6 ⇒ tối đa 57 item cứu được bằng rerank, **125 item không vào nổi pool = nút thắt RECALL**.
Điều kiện so sánh: index đang dùng 361 chunk `8031beea81da`, index mới sau re-OCR 342 chunk `6aa8c0fd9162`,
mất neo vàng **389/797 = 0,4881** (ngưỡng 0,02 ⇒ ĐỎ) ⇒ **không được so gold@6 giữa hai index** cho tới khi
PA-17 re-anchor xong. Tái lập: r11↔r14_repro_off và r12↔r15_repro_on **giống nhau từng item trên 811 item**;
manifest `data/loop/diag/chain_manifest_t7_repro_r0.json`, `spec_sha256 =
77b8901117015106415f922687217fb4dfabfe2cc4b6943e5ebd9879c0e87e55`, 13 env ghim.

Một câu trả lời cho hội đồng: *trong 700 câu hỏi CÓ sẵn đoạn văn bản chứa đáp án trong index, 363 câu
(51,86%) dẫn đúng đoạn đó vào 6 mảnh ngữ cảnh đưa cho model ở cấu hình mặc định trước khi tối ưu* — không
hơn, không kém.

## 8. Bằng chứng "răng": sổ cái đột biến 135/135

14 lượt harness (mỗi lượt: backup trong bộ nhớ → đột biến đúng 1 chuỗi → `pytest -q --no-header -x` →
hoàn nguyên → so SHA-256; không lượt nào để file gốc thay đổi). Số đếm từ `grep -c "BẮT ĐƯỢC"` trên từng log.

| Harness | Đột biến | Bắt được | Sống sót | Log |
|---|---|---:|---:|---|
| T0 noise floor | 5 | 5 | 0 | `tmp/mutation_check_t0.log` |
| T1 ablation | 4 | 4 | 0 | `tmp/mutation_check_t1.log` |
| T2 corpus | 6 | 6 | 0 | `tmp/t2_mutation_6.log` |
| T3 guardrails | 9 | 9 | 0 | `tmp/t3_mutation_recheck_9.log` |
| T4 (bộ cũ) | 7 | 7 | 0 | `tmp/mutation_check_t4.log` |
| T4 (bộ mới: bất biến SFT, giao diện, cache key) | 8 | 8 | 0 | `tmp/mutation_check_t4_new.log` |
| T5 reranker/header/fallback | 13 | 13 | 0 | `tmp/mutation_check_t5.log` |
| T6 (bộ cũ) | 10 | 10 | 0 | `tmp/mutation_check_t6.log` |
| T6 (bộ mới) | 10 | 10 | 0 | `tmp/mutation_check_t6_tests.log` |
| T7 `run_chain` (chạy 2 lần, tính 1) | 6 | 6 | 0 | `tmp/mutation_check_t7.log`, `tmp/mutation_check_t7_rerun_dot2.log` |
| T7 `cache_policy` | 10 | 10 | 0 | `tmp/mutation_check_cache_policy.log` |
| T7 docs checker dot2 | 20 | 20 | 0 | `tmp/mutation_check_t7_dot2.log` |
| **Nghiệm thu cuối — 4 máy kiểm hội đồng** | 18 | 18 | 0 | `tmp/mutation_check_final_council.log` |
| **Nghiệm thu cuối — phòng thủ môi trường (D-35 + D-36)** | 9 | 9 | 0 | `tmp/mutation_check_stdin_guard.log` |
| **Tổng** | **135** | **135** | **0** | — |

Ba lần đột biến **sống sót** trong quá trình phát triển đều được xử lý bằng đột biến mạnh hơn hoặc test
biên mới, không bằng hạ kỳ vọng: T4a-M2 (bản đầu), T6a-M1, và **K-M1** của đợt này — `answered_rows` bỏ bộ
lọc `PENDING_GENERATION` không bị bắt vì row D trong bộ test tổng hợp có `answer_chars = 0` (bị loại vì lý
do khác); đổi row D thành `answer_chars = 5` kèm ghi chú ngay trong test, chạy lại → **17/18 → 18/18**.

Răng theo 4 máy kiểm cuối + máy phòng thủ môi trường (mỗi dòng = một hành vi sai cố ý gây ra rồi bị chặn):

| Máy kiểm | Hành vi sai bị bắt |
|---|---|
| `env_flag_audit` | default `"1"` trong mã; `.env.example` bật cờ lever; accessor trả `True` khi env trống; `setdefault` ngầm trong `src/`; chuỗi kiểm quá mỏng bị từ chối kết luận "sạch"; bật trong script đo chỉ bị ghi chú, không gán lỗi |
| `secret_scan` | mẫu dương tự chế cho từng nhóm pattern secret + đường dẫn theo tên user; placeholder không bị tính là secret |
| `train_data_audit` | leak nội dung train↔val↔benchmark; id trùng tên; dòng code-QA thiếu trích dẫn/định danh; lệch số dòng so với manifest |
| `council_check_*` | fabrication rate trả `None`; gold@6 lấy mẫu số theo số row; trần xếp hạng tính cả item không có chunk vàng; "chấm lại khớp liều"; giấu round lệch chữ ký; bỏ lượt env-đối-chứng; mã thoát luôn 0; hai lần `build()` khác nhau; cờ vàng tái lập khác vẫn báo giống |
| `test_final_subprocess_stdin_guard.py` (D-35 + D-36, §14) | bỏ `stdin=subprocess.DEVNULL` ở từng lời gọi `subprocess` trong 4 máy kiểm; gộp/đặt `git status` **ngoài** khối `try`; nuốt lỗi spawn rồi báo `tracked-sach`; đổi nhãn `khong-co-git`; làm trống bộ kiểm AST (đọc phạm vi sai file); xóa khối `reconfigure`; đặt guard **sau** `def main(`; `errors="replace"` → `errors="strict"`; thu hẹp `except Exception` → `except ValueError` |

## 9. Bất biến "cờ TẮT = hành vi cũ"

| Bất biến | Bằng chứng |
|---|---|
| Golden 30 item T3 khớp từng khoá | `test_t3_guardrails.py` + §4 lớp 6 (chạy lại golden trên cây hiện tại, sha256 khối `core` `344d55cd35ec…`) |
| T3 TẮT: đầu ra bất biến cả khi env còn ngưỡng lever TẮT | `TestOffInvariantWhenDisabledLeversConfigured` |
| Cache key mặc định đúng 4 trường cũ | `test_cache_key_payload_contains_prompt_version_and_policy` (+ Qwen) |
| T5 cờ TẮT trả đúng object/thứ tự, không nạp reranker | `test_t5_reranker_contract.py` |
| T4a cờ TẮT truyền `ollama_model=None`, `LocalSLM {}` | `test_loop_generator_model_flag.py` |
| Trọng tài không đổi ở mọi round r0–r13 | 19 round/phase dùng chung 1 chữ ký (`tmp/council_referee.json`) |

## 10. Trạng thái git và điều kiện "người ngoài chạy lại được"

| Loại | Số đo tại HEAD `b6c29d2` (trước commit nghiệm thu cuối) | Sau `a170e92` + commit tiếp theo (đo khi đang stage) |
|---|---|---|
| File tracked đang sửa | **11** = 6 file PA-8 (`src/generator.py`, `src/pipeline.py`, `src/query_normalizer.py`, `src/router.py`, `tests/test_pipeline.py`, `tests/test_subquery.py`) + 5 docs (`AUTONOMY_LOG`, `DECISION_LOG`, `MORNING_REPORT`, `STATE`, `reports/T5.md`) | **6** — đúng 6 file PA-8, docs đã vào git |
| File nguồn/công cụ/test **chưa tracked** | **47** = 3 `src/` + 25 `tools/` + 19 `tests/` (PA-26; tăng từ 35 vì batch nghiệm thu cuối) | **35** = 3 `src/` + 17 `tools/` + 15 `tests/` — **12 file của batch này đã được commit** (8 `tools/diag/*` + 4 `tests/test_final_*`); PA-26 vẫn mở cho `verify.py`/`gate.py`/`run_round.py`/`answer_guard.py` |
| Đường dẫn untracked không bị `.gitignore` loại | **1.980** (`tmp` 1.483 · `data` 343 · `models` 58 · `tools` 25 · `tests` 19 · `docs` 14 · `.ocr_cache_vie` 13 · `chroma_db_vie` 5 · `chroma_db_headers_old` 5 · `src` 3) ⇒ ai đó gõ `git add -A` sẽ stage toàn bộ, gồm cả 321 MB `models/` → PA-33 | **1.969** (trừ 12 file vừa track; `tmp/` + `models/` + `data/` vẫn còn nguyên) |
| Artifact không commit | `models/` 321 MB · `tmp/` 119 MB · `data/loop/rounds/` 98 MB · `data/training/` 13 MB · `chroma_db_vie/` 6,0 MB · `.ocr_cache_vie/` 300 KB |

Phán quyết: **fresh clone vẫn chưa tái lập được bộ test**, vì `tools/loop/verify.py`, `gate.py`,
`run_round.py`, `src/answer_guard.py`… chưa vào git (PA-26). Đạt ở mức lệnh/tài liệu (README §5.10 +
`tools/loop/run_chain` + manifest ghim env).

## 11. Khoảng trống còn lại (risk list)

| Nguồn | Khoảng trống | Chờ |
|---|---|---|
| T2 | **Mục 9 ĐỎ**: mất neo vàng 48,81% (389/797) > ngưỡng 2% trên index mới; 3 tệp "khoảng trống" vẫn vào index; 20 đoạn chờ người duyệt | PA-17, PA-7, PA-1 |
| T3 | Khóa cache chế độ TẮT vẫn TÁCH theo `DEC_*`/`EV_*`/`ANSWER_GUARD_*` khi env còn giá trị (đầu ra không đổi); lever D chỉ chặn ở pre ⇒ một mình không chứng minh guard sau sinh | PA-27, PA-9, PA-10, PA-14, PA-15 |
| T4 | **Mục 5 ĐỎ do dữ liệu**: 13/13 dòng train + 8/10 holdout > 768 token (min 1.016, max 1.707) ⇒ kế hoạch QLoRA 4 GB không chạy với `t4b_r5r8r9r10`; bộ sinh giữ dòng thiếu thực thể vàng; adapter `qwen25_05b_sft_adapter` chỉ chứng minh **cơ chế** nạp LoRA | PA-28, PA-11, PA-12 |
| T5 | `RERANKER_FALLBACK` mặc định TẮT (bật mới lùi RRF; production dừng loudly); gold@6 811 item cấu hình TẮT tái lập 811/811 trùng r11 (0,7400); **chưa** build index header thật, **chưa** test chất lượng model thật; chi phí reranker và lỗi fold của `score_pairs` vẫn là đề xuất | PA-18(b/c), PA-19, PA-21, PA-25, PA-1 |
| T6 | 6b `n_filled = 0` ⇒ chưa có kappa/P–R; 6c 0 câu hỏi thật; `referee_agreement.py` + `metric_ci.py` chưa có unit test riêng | PA-13, PA-20, PA-22, PA-23 |
| T7 | Cache policy mới kiểm unit, chưa chứng minh cache-miss trên cache thật; `run_chain` chưa chạy chuỗi dài; `tmp/` chưa xoá gì; 5 script README thiếu argparse + `ingest.py` xoá index không dry-run | PA-24, PA-26, PA-29 |
| Nghiệm thu cuối | `.env.example` không khai báo 13 cờ lever; 89 dòng PII trên 8 file chưa mask; 3 id dữ liệu train trùng tên | **PA-30, PA-31, PA-32** (mới) |
| Nghiệm thu cuối | `.gitignore` không loại `tmp/`, `models/`, `data/loop/rounds/`, `data/training/`, `chroma_db_vie/`, `.ocr_cache_vie/` ⇒ `git add -A` stage 1.980 đường dẫn | **PA-33** (mới) |
| Nghiệm thu cuối | **Máy kiểm tự nhiễm phạm vi**: mẫu gieo trong `test_final_secret_scan.py` thành file tracked sau commit ⇒ 3 test ghim hiện trạng đỏ, máy quét báo 4 "secret" giả. **Đã sửa trong phiên** (dựng mẫu tại runtime, không nới máy quét) — còn lại là **quy trình**: bắt buộc chạy `--scope tracked` sau khi stage | ĐÃ XỬ LÝ + nguyên tắc mới (§5) |
| Nghiệm thu cuối | **Phòng thủ môi trường đo (D-35 stdin, D-36 console) mới phủ 8 file** (`tools/diag/council_kit`, `secret_scan`, `final_number_audit`, `env_flag_audit`, `train_data_audit`, `docs_consistency_check`, 2 test `test_final_*`). **Còn 8 lời gọi `subprocess.run` chưa có `stdin` ở 6 file** (đếm bằng AST `tmp/count_stdin_sites.py`: 17 lời gọi trong `tools/` + `tests/` + `src/`, 9 đã siết): `tools/loop/run_chain.py:284` và `:289`, `tools/diag/t4_latency_probe.py:65` (`nvidia-smi`, đã bọc `except OSError` → trả `None`, không suy diễn), `tests/test_t7_tmp_cleanup.py:181` và `:225` (`mklink`), `tests/test_t4_gpu_slow.py:41`, `tests/test_t4_sft_invariants.py:444`, `tests/test_t6_gate_refusal_and_regression.py:325` — **nháp đầu ghi "5 lời gọi / 3 file" vì chỉ đếm tay `tools/` + `test_t7`**, đã đính chính bằng AST (§14.6). 6 file ngoài **không bị đụng** trong phiên nghiệm thu (quy tắc "không sửa dụng cụ đo"), chỉ ghim bằng test | **PA-34** |
| Nghiệm thu cuối | **Interpreter tái lập**: **hai interpreter cùng 3.14.8** — `venv\Scripts\python.exe` (cài đủ dependency, đo mọi số của báo cáo này) và `python` hệ thống (`%LOCALAPPDATA%\Python\pythoncore-3.14-64`, `include-system-site-packages = false`, **thiếu** `pypdfium2`/`streamlit`). Chạy toàn bộ `tests/` bằng python hệ thống ⇒ **4 lỗi collect, Interrupted** (`tests/test_corpus_rebuild.py`, `test_demo_streamlit_display.py`, `test_ui_generator_flag.py`, `test_ui_labels.py`) — đo lại 25-10: `no tests collected, 4 errors in 4,58 s`. Đây là **thiếu package, không phải lỗi code**. Trước siết, python hệ thống + stdin đóng còn thêm **1 FAILED + 9 ERROR**; sau siết bộ 5 file nghiệm thu xanh trên **cả hai** (144 passed / 1 skipped) | **PA-34** (ghi README) + PA-26 |
| Chung | Trọng tài mù với "đúng căn cứ nhưng lạc đề" (36/43 ca nặng); 11 verdict đổi chiều khi siết luật so khớp số; chưa chứng minh định nghĩa "bịa" theo ý hội đồng | PA-20 |

## 12. Phán quyết tổng

| Tiêu chí | Phán quyết |
|---|---|
| Test xanh và có hiệu lực | **ĐẠT** — 1.372 passed + 5 skipped có lý do + 2 slow passed (82,32 s) chạy riêng; **135/135** đột biến bị bắt; chữ ký `9f1179ccab74` |
| Không sửa dụng cụ đo để qua cổng | **ĐẠT** — gate.py/verify.py/text_utils.py không đổi; mọi thay đổi gate chỉ là bản đề xuất tách rời; 3 script hội đồng chỉ-đọc; hai đợt siết §14 chỉ đụng **bộ kiểm** (thêm `stdin`, thêm guard in), không đụng logic chấm |
| Số công bố tái lập được | **ĐẠT** — 63/63 dòng khớp (mục 3); 3 đính chính ghi nguyên (79/79 → 135/135, −0,0028 → −0,0029, 17/17 → 16/16) |
| Máy kiểm không biến lỗi môi trường thành kết luận về repo | **ĐẠT (trong phạm vi 8 file đã siết)** — lỗi spawn/đóng stdin không còn báo `tracked-sach`, console nén (cp1252 stand-in + **cp1258** thật của máy đo) không còn `exit 1`; 34 test + 9/9 đột biến; **8 lời gọi ở 6 file ngoài phạm vi còn nguyên → PA-34** |
| Lever mới an toàn khi tắt | **ĐẠT** — 13/13 cờ mặc định TẮT ở 5 lớp + golden từng byte |
| Repo không lộ secret | **ĐẠT có điều kiện** — 0 secret, 0 đường dẫn cá nhân; 89 dòng PII ở 8 file **chưa** vào git (PA-31) |
| Dữ liệu train không leak, bất biến #7 | **ĐẠT** — 0 leak nội dung trên 10.619 dòng; code-QA 1.635 dòng tự chứa đáp án; artifact SFT vòng lặp ĐỎ ở check độ dài (PA-11/12/28) |
| Người ngoài chạy lại từ repo | **CHƯA ĐẠT** — PA-26 (47 file chưa tracked) + PA-33 (`.gitignore`) |
| Chất lượng tầng sinh | **CHƯA ĐẠT** (không phải lỗi test) — r7 gold 0,80 nhưng PASS_CORRECT 0,14; r10 3B không đạt ngưỡng ≥22 (p=0,804); r12/r13 âm |

Việc cần duyệt đầu tiên trước khi trình hội đồng: **PA-26 kèm PA-31** (commit 47 file + mask PII) và
**PA-33** (bịt `.gitignore`), vì cả ba quyết định việc "fresh clone chạy được 1.372 test"; **PA-34** kế
tiếp vì nó quyết định "chạy bằng Python nào" — chưa có câu trả lời nào ghi trong README.

## 13. Lệnh tái lập toàn bộ

**Điều kiện tiên quyết (mới, do D-35/D-36 — chưa có trong README, chờ PA-34):** dùng interpreter của repo
(`venv\Scripts\python.exe`, 3.14.8 + đủ package), **không** dùng `python` trên PATH; và đóng stdin khi gọi
từ shell tự động (`< /dev/null`) là hợp lệ vì mọi máy kiểm trong phạm vi đã truyền `stdin=DEVNULL`. Máy kiểm
tự đặt UTF-8 cho stdout/stderr nên **không cần** `PYTHONIOENCODING` nữa — dòng gán biến này dưới đây chỉ còn
tác dụng giữ cho các test/script ngoài phạm vi in dấu tiếng Việt không hỏng.

```bash
# 0) Kiểm tra môi trường trước (PA-34 đề xuất env_probe.py; hiện tại dùng 2 lệnh tay)
venv/Scripts/python.exe -c "import sys, locale, pypdfium2, streamlit; print(sys.version.split()[0], sys.executable, locale.getpreferredencoding())"

# 1) Bộ test + chữ ký trọng tài
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c \
  "from tools.loop import verify; print(verify.referee_fingerprint())"

# 2) Test chậm (GPU/Ollama) — mặc định skip
T4_RUN_SLOW=1 PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests/test_t4_gpu_slow.py -q

# 3) Bốn máy kiểm nghiệm thu cuối (chỉ-đọc; exit 0 = sạch)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/env_flag_audit.py    --json tmp/env_flag_audit.json
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/secret_scan.py       --json tmp/secret_scan.json --scope tracked
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/train_data_audit.py  --json tmp/train_data_audit.json
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/final_number_audit.py --json tmp/final_number_audit.json

# 4) Ba script câu hỏi hội đồng
for s in fabrication referee gold6; do
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/council_check_$s.py --json tmp/council_$s.json || echo "FAIL: $s"
done

# 5) 14 harness đột biến (mỗi harness tự hoàn nguyên + kiểm SHA-256)
for f in tmp/mutation_check_t0.py tmp/mutation_check_t1.py tmp/mutation_check_t2.py \
         tmp/mutation_check_t3.py tmp/mutation_check_t4.py tmp/mutation_check_t4_new.py \
         tmp/mutation_check_t5.py tmp/mutation_check_t6.py tmp/mutation_check_t6_tests.py \
         tmp/mutation_check_t7.py tmp/mutation_check_t7_dot2.py tmp/mutation_check_cache_policy.py \
         tmp/mutation_check_final_council.py tmp/mutation_check_stdin_guard.py; do
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe "$f" || echo "FAIL: $f"
done
```

`secret_scan --scope tracked` **bắt buộc chạy sau khi stage/commit** (nguyên tắc D-34 + §14.5): máy quét đọc
working tree của danh sách file mà git theo dõi, nên nội dung docs chưa commit cũng bị quét.

## 14. Hai lần đỏ không đến từ code: phòng thủ môi trường của máy kiểm (D-35 stdin, D-36 console)

Nghiệm thu ở mục 2–3 đo lại **sau commit** `c508876` bằng `python` hệ thống (không phải `venv`) với stdin
đóng (`< /dev/null`) → **1 FAILED + 9 ERROR**, dù cùng bộ lệnh đó trên `venv` vẫn 1.338 xanh. Hai sự cố
được xử lý trong hai đợt siết; **không** có test cũ nào bị sửa để xanh.

### 14.1 Sự cố 1 — `WinError 6` biến một file đã tracked thành "repo không có git" (D-35)

Chuỗi nhân quả đo được, không suy đoán:

| Bước | Hiện tượng | Bằng chứng |
|---|---|---|
| 1 | `subprocess.run([...], capture_output=True)` kế thừa handle stdin của process cha; handle đã đóng không nhân bản được trên Windows + CPython 3.14 | `OSError: [WinError 6] The handle is invalid` trong traceback của fixture |
| 2 | `council_kit.git_state()` bắt `OSError` và trả nhãn `khong-co-git` — gán cho **`src/text_utils.py`, file thực sự đã tracked và sạch** | chạy `env_flag_audit` bằng python hệ thống: 3 test ghim nhãn đỏ |
| 3 | lời gọi `git status` **thứ hai** nằm ngoài `try` ⇒ exception văng thẳng, máy kiểm chết giữa phép đo | traceback `test_final_env_flag_defaults.py` (3 ERROR) |
| 4 | cùng kiểu hỏng ở `secret_scan.tracked_files()` (6 ERROR) và fixture dump golden của `test_final_council_scripts.py` (1 FAILED) | `tmp/pytest_post_commit_venv.txt` so với lượt chạy python hệ thống |

Bốn hướng đã loại trừ trước khi kết luận: (a) lỗi do bộ test — **sai**, vì chạy `pytest <từng file>` đơn lẻ
vẫn đỏ y hệt; (b) lỗi do thứ tự test — **sai**, `-p no:randomly` và chạy lẻ cho cùng kết quả; (c) lỗi do
stdin — **đúng**, `… < /dev/null` tái hiện, bỏ redirection thì xanh; (d) lỗi do interpreter — **đúng một
phần**, python hệ thống thiếu `pypdfium2`/`streamlit` (gây 4 lỗi collection, mục 14.4) nhưng không giải
thích được WinError 6 vì cả hai interpreter đều là **3.14.8**, chỉ khác tập package.

Cách sửa (ba lớp, theo thứ tự ưu tiên):

1. `stdin=subprocess.DEVNULL` cho mọi lời gọi subprocess trong phạm vi nghiệm thu cuối — `council_kit.py`
   (2), `secret_scan.py` (1), `final_number_audit.py` (1), `env_flag_audit.py`/`train_data_audit.py` (khuôn
   có sẵn), và 2 file test; đưa **cả hai** lời gọi git vào cùng một `try`.
2. **Giữ nguyên kỳ vọng**: `tracked-sach` / `chua-commit` / `thieu-file` vẫn là các nhãn đúng; chỉ *đường
   sinh ra nhãn* là sai. Không nới assertion, không đổi số ghim.
3. `tests/test_final_subprocess_stdin_guard.py` **ghim bằng AST** (không cần tái hiện lỗi để có răng):
   không còn lời gọi `run/Popen/check_output/check_call` nào thiếu `stdin` trong 8 file phạm vi, số lời gọi
   mỗi file đúng từng cái (`council_kit` 2, `secret_scan` 1, `final_number_audit` 1, `docs_consistency_check`
   1, 2 file test), bộ kiểm không bị làm trống, `docs_consistency_check.py` vẫn là khuôn mẫu có trước từ T7;
   `git_state()` chạy với `subprocess` **giả** cho từng nhánh nhãn (lỗi spawn không được báo `tracked-sach`,
   `ls-files` rc≠0 vẫn là `chua-commit`, file thiếu không gọi subprocess, mọi nhãn thuộc bảng hợp lệ);
   ghim hiện trạng dụng cụ đo trên git thật (3 test, kèm nhãn PA-26).

### 14.2 Sự cố 2 — console không-UTF-8 (máy đo là **cp1258**) làm máy kiểm báo "KHÔNG ĐẠT" sai nguyên nhân (D-36)

`tools/diag/council_check_gold6.py` in dòng `… ĐẠT — 0,5186`; trên console của máy đo — **cp1258**, bảng mã tiếng Việt (`chcp` = 1258,
`PYTHONIOENCODING`/`PYTHONUTF8` đều trống) `print` văng `UnicodeEncodeError` ⇒ **exit code 1**. Người tái
lập đọc `FAIL: gold6` sẽ kết luận "câu hỏi hội đồng không đạt", trong khi hỏng ở **máy in**, không ở phép
đo. Probe `tmp/probe_stdin_closed.py` cũng cho thấy `os.close(0)` trong process con **không** tái hiện
WinError 6 ⇒ không có cách tái hiện tất định trong test, nên răng đặt ở **ghim nguồn + subprocess giả +
ép console về bảng mã không-UTF-8 ở process con**.

Sửa: khối guard lúc import trong **7** máy kiểm (`council_check_fabrication`, `council_check_referee`,
`council_check_gold6`, `env_flag_audit`, `train_data_audit`, `secret_scan`, `final_number_audit`) —
`reconfigure(encoding="utf-8", errors="replace")` cho stdout+stderr, bọc `except Exception` để bước này
không bao giờ làm hỏng phép đo (kể cả dưới `pytest capsys`). `docs_consistency_check.py` đã guard sẵn từ
T7 nên được dùng làm khuôn, không sửa.

Răng: `TestMayInKhongChiuLoiConsole` (13 test) — 2 **negative control** chứng minh cp1252 **và cp1258** thật sự không in
nổi "ĐẠT — 0,5186" (nếu nền không hỏng thì cả lớp test này vô nghĩa); 7 test ghim chuỗi guard tồn tại, đứng
**trước** `def main(`, bọc trong `except Exception`; 4 test hành vi chạy process con **thật** với stdout/stderr
bị ép về bảng mã không-UTF-8 (cp1252), kỳ vọng `rc=0` và không có `UnicodeEncodeError`. Điều khiển âm parametrized theo **cả hai** bảng mã vì cp1252 chỉ là stand-in tất định; bằng chứng máy đo dùng cp1258 nằm ở `tmp/probe_no_utf8.txt` (traceback `encodings\cp1258.py`, fail tại `\u1ece`) và bản sau khi có guard là `tmp/probe_utf8_after.txt`.

### 14.3 Đột biến 9/9 (`tmp/mutation_check_stdin_guard.py`)

| Mã | Đột biến | Bắt bởi |
|---|---|---|
| K1 | bỏ `stdin` ở `git ls-files` trong `git_state` | AST |
| K2 | bỏ `stdin` ở `git status --porcelain` trong `git_state` | AST |
| K3 | bỏ `stdin` trong `tracked_files()` của `secret_scan` | AST |
| K4 | bỏ `stdin` trong `collect_counts()` của `final_number_audit` (máy đếm số test công bố) | AST |
| K5 | đưa `git status` ra **ngoài** `try` ⇒ văng exception, không có nhãn | AST + `test_loi_spawn_o_loi_goi_thu_hai_khong_duoc_crash` |
| K6 | **nhãn nguy hiểm nhất**: lỗi spawn ⇒ báo `tracked-sach` | 2 test (subprocess giả + ghim nhãn) |
| K7 | đổi UTF-8 → cp1252 trong khối guard của `council_check_gold6.py` | ghim chuỗi + hành vi |
| K8 | bỏ `errors="replace"` trong guard của `secret_scan.py` | ghim chuỗi |
| K9 | thu hẹp `except Exception` → `except ValueError` ở `council_check_referee.py` | ghim chuỗi |

Kết quả: **9/9 bị bắt, 0 sống sót**, 5 file phạm vi nguyên vẹn sau hoàn nguyên (SHA-256 khớp bản gốc).
Sự cố trong lúc dựng harness — `Path.write_text` đổi LF→CRLF làm đối chiếu SHA báo "khôi phục thất bại" dù
nội dung đúng — được xử bằng `_doc`/`_ghi` đọc-ghi **byte** (bài học đã ghi ở AUTONOMY_LOG, mục "đột biến
phải so SHA trên byte, không trên text").

**Tái chạy trên đúng cây đã commit** (`08a7f1a`, 20:2x): cần thiết vì K4 nhắm `tools/diag/final_number_audit.py` mà file này được **thêm bảng số lúc 19:53 — sau log 19:47**. Kết quả vẫn **9/9, 0 sống sót**, 5 file phạm vi SHA-256 khớp bản gốc. Log cũ **không xoá**, lưu ở `tmp/mutation_check_stdin_guard_1947_giu_lai.log`; `tmp/mutation_check_stdin_guard.log` hiện là lượt đo trên cây commit — đó là artifact mà `final_number_audit.py` đọc cho dòng "9/9 đột biến phòng thủ môi trường".

### 14.4 Số đo trước / sau và khoảng trống còn lại

| Đại lượng | Trước siết | Sau D-35 | Sau D-36 | **Chốt batch 3** |
|---|---|---|---|---|
| `pytest tests -q` (venv) | 1.338 passed / 5 skipped — 87,59 s | 1.359 / 5 — 126,52 s | 1.371 / 5 — 90,77 s | **1.372 / 5 — 91,44 s** (`tmp/pytest_final_batch3.txt`) |
| `pytest tests/test_final_*.py -q` (venv) | 110 passed / 1 skipped — 24,98 s | 131 / 1 (= 110 + 21 test guard D-35; chưa chụp riêng trên venv) | 143 / 1 — 44,96 s (`tmp/pytest_final5_after_d36.txt`) | **144 / 1 — 44,33 s** (`tmp/pytest_final5_batch3.txt`; collect-only **145**) |
| Cùng 5 file, python hệ thống + stdin đóng | **1 FAILED + 9 ERROR** | 131 / 1 (bộ 4 file + guard 21 test; `tmp/pytest_baseline_stdin_closed.txt` là lượt **trước** siết: chỉ còn 4 lỗi collection) | 143 / 1 — 47,58 s (`tmp/pytest_final5_py314_stdin_closed.txt`) | **144 / 1 — 45,60 s** (`tmp/pytest_final5_py314_stdin_closed_batch3.txt`) |
| Kiểm toán số công bố | 55 dòng / 0 LỆCH | 55 / 0 (chưa thêm dòng) | 60 / 0 (`tmp/final_number_audit_after_d36.json`) | **63 / 0** (`tmp/final_number_audit_batch3.json`, +8 dòng của hai đợt siết) |
| Chữ ký trọng tài · secret scan · docs checker | `9f1179ccab74` · 0/0/89/8 · 35 mục | không đổi | không đổi | không đổi (chữ ký · **0 secret / 0 đường dẫn / 89 PII / 8 file**) · docs checker **36 mục · 264 lệnh · 100 đường dẫn · 0 lỗi · 5 cảnh báo** (`tmp/docs_check_after_d36.json`) |

Khoảng trống **không** tự sửa trong phiên (ghi PA-34):

- **8 lời gọi subprocess ngoài phạm vi (6 file)** vẫn chưa `stdin` — **đính chính bằng AST**: nháp đầu ghi 4 rồi 5 lời gọi / 3 file vì đếm tay trên `tools/` + `test_t7`; `tmp/count_stdin_sites.py` đi qua `tools/` + `tests/` + `src/` ⇒ 17 lời gọi, 9 đã siết, **8 còn thiếu** ở `run_chain.py:284/289`, `t4_latency_probe.py:65`, `tests/test_t7_tmp_cleanup.py:181/225`, `tests/test_t4_gpu_slow.py:41`, `tests/test_t4_sft_invariants.py:444`, `tests/test_t6_gate_refusal_and_regression.py:325`. Ba file `tests/test_t4_*`/`test_t6_*` gọi `subprocess.run` với `capture_output=True` nên **cùng hiểm hoạ** `WinError 6`; hiện vẫn xanh vì bộ test chạy bằng venv. Danh sách đầy đủ: `tmp/count_stdin_sites.txt`. `tools/loop/run_chain.py:284/289` và
  `tools/diag/t4_latency_probe.py:65` là hai dụng cụ **đã sinh số liệu đã công bố** (`t4_latency_20q.json`,
  `reranker_cost_gpu.json`, chain manifest) ⇒ quy tắc "không sửa dụng cụ đo" chặn tự ý sửa;
  `tests/test_t7_tmp_cleanup.py:181/225` (`mklink /J`) đỏ/ERROR tương tự nếu chạy bằng python hệ thống +
  stdin đóng. `t4_latency_probe.py:65` đã có `except (OSError, SubprocessError)` trả `None` nên **không**
  suy diễn thành kết luận về repo — hỏng ở mức "thiếu số đo", chấp nhận được.
- **Điều kiện tái lập chưa đăng ký ở đâu ngoài báo cáo này**: phải dùng `venv\Scripts\python.exe` (cài đủ
  package) chứ không phải `python` trên PATH. Python hệ thống cùng bản 3.14.8 nhưng
  `include-system-site-packages=false` ⇒ thiếu `pypdfium2`/`streamlit` ⇒ **4 lỗi collection, Interrupted**
  (`test_corpus_rebuild`, `test_demo_streamlit_display`, `test_ui_generator_flag`, `test_ui_labels`); đo lại
  25-10: `no tests collected, 4 errors in 4,58 s`.
- Guard UTF-8 đặt **lúc import** ⇒ chỉ áp cho máy kiểm chạy như script; tool được import trong pytest thì
  dùng stream của `capsys` (chủ đích, nên guard bọc `try/except`). Đổi hệ quả: từ giờ máy kiểm luôn in
  UTF-8 kể cả khi người dùng chủ đích muốn cp1252 — ai cần bản gốc phải tự `PYTHONIOENCODING=cp1252`
  (lúc đó `errors="replace"` vẫn giữ `rc=0`, chỉ mất dấu một số ký tự).

### 14.5 Lần đỏ thứ ba trong đợt này — và nó **đúng**: máy quét bắt chính báo cáo này

Lượt chạy `pytest tests -q` đầu tiên của batch 3 (19:5x) cho **1 FAILED / 1.371 passed**: `test_khong_co_duong_dan_ca_nhan_trong_file_track`. Nguyên nhân không phải code: mục 11 của chính báo cáo này vừa được viết thêm một dòng chứa đường dẫn tuyệt đối theo tên user (`%LOCALAPPDATA%` bị viết hoa đủ dạng `C:\Users\…`). Máy quét chạy trên **nội dung working tree của file đã track**, nên một câu chưa commit cũng bị bắt.

Đây là **lần thứ hai** cùng một lớp lỗi (`test_final.md` dòng 197 trở đi mô tả lần thứ nhất với mẫu gieo trong `test_final_secret_scan.py`). Xử lý giữ đúng nguyên tắc đã đăng ký ở D-34: **sửa mẫu, không sửa thước** — che đường dẫn thành `%LOCALAPPDATA%\Python\pythoncore-3.14-64`, **không** thêm ngoại lệ vào máy quét, **không** nới assertion. Sau sửa: 5 file nghiệm thu **144 passed / 1 skipped**, toàn bộ **1.372 passed**, secret scan `--scope tracked` = **0 secret / 0 đường dẫn cá nhân / 89 PII / 8 file** (`tmp/secret_scan_batch3.json`). Bằng chứng lượt đỏ được giữ nguyên ở `tmp/pytest_batch3_caught_pii_path.txt`, không xoá.

**Vấp thêm một lần nữa, cùng lớp** (khi đang soạn PA-34): câu mô tả hiểm hoạ viết theo dạng
`C:` + `Users` + tên người dùng thì an toàn, nhưng bản nháp dùng **dấu ngoặc nhọn** bọc chữ "tên" đã trúng luật
`Placeholder đã biết` và nâng BI_MAU **251 → 252**. Không phải bí mật, cũng không phải lỗi của máy quét — luật đó
sinh ra để nhận diện placeholder thật trong cấu hình. Cách xử lý giống hệt D-34: **đổi câu trong báo cáo**,
giữ nguyên mọi luật và ngưỡng; quét lại `--scope tracked` = **281 ứng viên / 249 đã đọc / 340 dòng khớp / BI_MAU 251 /
89 PII trên 8 file / 0 secret / 0 đường dẫn** (`tmp/secret_scan_batch3e.json`, quét lại **sau** khi đoạn này
được ghi), đúng các số đã công bố. Lượt quét **sau `git add`** (`tmp/secret_scan_post_stage.json`) cho
**282 ứng viên / 250 đã đọc** nhưng vẫn **340 dòng khớp / BI_MAU 251 / 89 PII / 0 secret / 0 đường dẫn** — file test mới vào track không thêm tín hiệu nào.
Bài học được ghi thành nguyên tắc viết báo cáo: **mô tả một hiểm hoạ bằng chính chuỗi mà dụng cụ đo coi là tín hiệu
thì sẽ làm dụng cụ đo nhích số** — phải mô tả bằng lời, không dán mẫu.

Hệ quả cho quy trình (đã ghi vào §5 và D-34): **mọi file docs sẽ commit phải được quét trước khi stage**, vì `secret_scan --scope tracked` đọc working tree chứ không đọc HEAD. Đây là lý do bắt buộc chạy lại máy quét sau mỗi lần sửa docs, chứ không phải sau mỗi lần commit.

### 14.6 Điều chưa chắc chắn sau đợt siết

- **Không có cách tái hiện WinError 6 trong test tất định** (`os.close(0)` trong process con không gây lỗi — probe `tmp/probe_stdin_closed.py`). Răng vì thế nằm ở *ghim nguồn bằng AST* chứ không phải ở *tái hiện triệu chứng*. Ai đó thêm lời gọi subprocess mới **ngoài** 8 file phạm vi sẽ không bị chặn — đó là lý do PA-34 đề nghị siết nốt **8 lời gọi còn lại ở 6 file** (đếm bằng AST, `tmp/count_stdin_sites.py`) và thêm `tools/diag/env_probe.py`.
- Guard UTF-8 chỉ chứng minh **chạy được** trên bảng mã không-UTF-8 cho 4 máy kiểm được chọn làm mẫu (`council_check_fabrication`, `council_check_gold6`, `council_check_referee`, `secret_scan`); 3 máy còn lại chỉ được ghim **tĩnh** (chuỗi guard + vị trí trước `def main(`).
- `errors="replace"` đổi *cách* hiển thị chứ không đổi *phán quyết* — nhưng nếu một ngày nội dung in ra chính là số liệu thì ký tự bị thay sẽ làm người đọc hiểu sai. Chưa có test nào bắt trường hợp đó.
- **Một lệnh nền của phiên bị dừng vì log phình** (`chuẩn hoá comment khối guard`, exit `killed`, file log nền trong `%TEMP%` vượt 5 GB). Đã đối chiếu ngay sau đó: `git diff --stat` và SHA các file phạm vi **không đổi**, `tools/diag/` không còn file nào dirty, toàn bộ `pytest tests -q` vẫn **1372 passed / 5 skipped** — tức không có thay đổi ẩn nào lọt vào repo. Ghi ở đây để người đọc sau không hiểu nhầm một tiến trình nền thành "code đã bị sửa mà không ai báo".

## Phụ lục A — đầu ra chính của ba máy kiểm hội đồng (nguyên số)

| Máy | Tổng | Dòng LỆCH | exit |
|---|---|---:|---:|
| `council_check_fabrication.py` | 10 round · 1.000 dòng · 380 đã trả lời · 7 trái ngữ cảnh · 43 ca nặng (FAB 7 / CFP 6 / HOU 30) · 18 item khác nhau · 36/43 ca nặng mù | 0 | 0 |
| `council_check_referee.py` | 19 round/phase · 1 chữ ký · 1.000/1.000 chấm lại khớp (1,57 s) · env-độc lập ĐẠT · cổng từ chối ĐẠT · 11 verdict đổi chiều ở luật nghiêm khắc · `n_filled = 0` | 0 | 0 |
| `council_check_gold6.py` | 811 item · 700 mẫu số · r0 363 = 0,5186 · 9 round tái lập · 7 file `gate_vs` khớp · trần pool-12 = 0,8214 · 125 item trượt recall · mất neo 0,4881 ĐỎ · r11↔r14 và r12↔r15 giống từng item | 0 | 0 |

## Phụ lục B — bản 13:26 | bản này (đo lại) | vì sao khác

| Đại lượng | Bản 13:26 | Bản này | Khớp với bản cũ? |
|---|---|---|---|
| Toàn bộ test | 1.064 passed, 2 skipped, 21,02 s | **1.372 passed, 5 skipped, 91,44 s** | không — đã thêm T6 dot2 (60), T7 dot2/dot3 (106), 111 test nghiệm thu cuối và 34 test phòng thủ môi trường |
| Test chậm T4 | 2 passed, 79,04 s | 2 passed, **82,32 s** | có (cùng 2 passed; thời gian đổi theo lượt máy) |
| Đột biến | 79/79 | **135/135** | không — phép cộng cũ thiếu 3 harness và tự mâu thuẫn (5+4+6+9+7+10+13+10+17 = 81) |
| T7 run_chain + cache | 17/17 rồi 16/16 | 6/6 + 10/10 = **16/16** | có (sau đính chính) |
| r13 header | −0,0028 | **−0,0029** | không — đính chính theo `header_paired_r11_r13.json` |
| Chữ ký trọng tài | `9f1179ccab74` | `9f1179ccab74` | có |
| Untracked `src/tools/tests` | 35 | **47** | không — thêm 4 công cụ + 4 test của batch này và các file T6/T7 dot2 |
| File tracked đang sửa | 6 | 11 (6 PA-8 + 5 docs) | không — docs đổi vì chính báo cáo này và các commit T6/T7 sau đó |
| Bảng đối chiếu số | 20 dòng | **63 dòng, 63 khớp** | có (mở rộng, không sửa số cũ ngoài 3 đính chính) |
