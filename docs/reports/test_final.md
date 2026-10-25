# Báo cáo kiểm thử tổng kết — T0 → T7 + nghiệm thu cuối

Ngày đo cuối: 2026-10-25 (các đợt test chạy 24 → 25-10) · Nhánh `auto/overnight` ·
Người chạy: agent kiểm thử (chế độ tự trị).
Phạm vi: (A) tổng hợp **8 báo cáo test theo nhiệm vụ** (`docs/reports/test_T0.md` … `test_T7.md`);
(B) **6 mục nghiệm thu cuối** đã đăng ký trong đề — số lượng test, tái lập từng số công bố, cờ env mặc
định TẮT, quét secret/đường dẫn cá nhân, bất biến #7 + train-leak trên dữ liệu train cuối, và **ba
script kiểm câu hỏi hội đồng**.

Bản này **thay** bản chụp lúc 13:26 (khi repo mới ở `dac99a9`, 1.064 test). Ba con số đã đổi và được
đính chính ngay trong bảng: (1) bộ test hiện **1.338 xanh**; (2) tổng đột biến bị bắt là **126/126** chứ
không phải "79/79"; (3) delta r13 là **−0,0029** (bản cũ in −0,0028 do cắt số).

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
| **Nghiệm thu cuối** | 4 máy kiểm: cờ env, secret, dữ liệu train, 3 câu hỏi hội đồng | `test_final_env_flag_defaults.py` 41, `test_final_secret_scan.py` 14, `test_final_train_data_audit.py` 13, `test_final_council_scripts.py` 43 | **111** | 18/18 | mục 4–7 dưới đây |

Ghi chú cộng dồn: không cộng tuyến tính số test của 8 đợt (mốc baseline chồng lấn
563 → 691 → 712 → 736 → 889 → 957 → 967 → 1.004 → 1.005 → 1.006 → 1.011 → 1.014 → 1.016 → 1.057 →
1.064 → 1.124 → 1.228 → **1.338**). Con số chuẩn duy nhất là phép đo toàn bộ `tests/` ở mục 2.

## 2. Mục nghiệm thu 1 — bộ test cuối, thời gian, số test đỏ

Đo lúc 18:3x ngày 25-10 trên cây hiện tại (`b6c29d2` + batch test nghiệm thu cuối):

| Đại lượng | Lệnh | Kết quả đo được |
|---|---|---|
| Toàn bộ test | `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q` | **1338 passed, 5 skipped, 3 warnings — 60,25 s** (lượt 2 sau khi sửa docs: 75,32 s; lượt 3 sau khi sửa fixture secret-scan: 90,71 s — **cùng 1338/5**;
thời gian tăng dần vì ngày càng nhiều test phải chạy `git ls-files` trên cây đã track) |
| Test chậm (GPU/Ollama) | `T4_RUN_SLOW=1 … pytest tests/test_t4_gpu_slow.py -q` | **2 passed — 82,32 s** |
| Chữ ký trọng tài | `python -c "from tools.loop import verify; print(verify.referee_fingerprint())"` | **`9f1179ccab74`** |
| 4 file nghiệm thu cuối | `pytest tests/test_final_*.py -q` | 110 passed, 1 skipped — 24,98 s |
| Test ĐỎ | — | **0** |

5 lượt skip đều có lý do đăng ký, không phải test bị ẩn lỗi:

| Skip | Lý do |
|---|---|
| `test_t4_gpu_slow.py` (2) | cần GPU/Ollama; có cổng `T4_RUN_SLOW=1` — đã chạy thật, 2 passed |
| `test_t7_tmp_cleanup.py` (2) | Windows từ chối tạo symlink trong sandbox test (`_skip` tự nguyện, có thông báo) |
| `test_final_env_flag_defaults.py:54` | `RERANKER_KEEP_CANDIDATES` không có accessor đơn — vẫn bị kiểm tĩnh ở lớp 2 của cùng module |

3 warnings còn lại là `FutureWarning` của `google.generativeai` (kích hoạt khi import `src/generator.py`)
và 2 `DeprecationWarning` từ `chromadb` / `langchain-community` — đều ở site không do phiên này sửa.

## 3. Mục nghiệm thu 2 — tái lập TỪNG số đã công bố (55 dòng)

Máy tái lập: `tools/diag/final_number_audit.py` → `tmp/final_number_audit.json` (**55 dòng, `khop=True`
cả 55**); bảng mở rộng `tmp/final_number_audit_table.md`. Mỗi dòng ghi rõ cách tính lại (lệnh đọc artifact
hoặc hàm thật của repo), không chép miệng.

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

**Đính chính "79/79"**: bản 13:26 cộng tay 9 harness ra "79/79", nhưng chính phép ghi ngay trong bảng đó
(5+4+6+9+7+10+13+10+17) đã là **81**, và nó **thiếu** 3 harness chạy sau (T6 bộ mới 10, T7 docs dot2 20,
nghiệm thu cuối 18). Sổ cái đo lại từ 13 log (mục 8) là **126/126**.

Hai con số **tăng hợp lý** sau khi bảng này chụp (không phải lệch): sổ `DECISION_LOG` từ **30 dòng → 32
dòng** (thêm D-32, D-33), và `tools/diag/docs_consistency_check.py --scope all` chạy lại chiều 25-10 vẫn
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

**Quét lại sau commit `a170e92`** (`tmp/secret_scan_post_commit.json`): số phình đúng phần file mới vào
track, **hai con số nghiệp vụ không đổi**.

| Chỉ số | Trước commit (`tmp/secret_scan.json`) | Sau commit |
|---|---|---|
| File ứng viên / đã đọc | 269 / 237 | 281 / 249 |
| Tổng dòng khớp | 296 | 339 |
| `BI_MAU` | 207 | 250 |
| `DU_CAO_NHAN_HOC` | **89 dòng / 8 file** | **89 dòng / 8 file** (không đổi) |
| `SECRET_COTHAT` / `DUONG_DAN_CA_NHAN` | **0 / 0** | **0 / 0** |

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

## 8. Bằng chứng "răng": sổ cái đột biến 126/126

13 lượt harness (mỗi lượt: backup trong bộ nhớ → đột biến đúng 1 chuỗi → `pytest -q --no-header -x` →
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
| **Nghiệm thu cuối — 4 file hội đồng** | 18 | 18 | 0 | `tmp/mutation_check_final_council.log` |
| **Tổng** | **126** | **126** | **0** | — |

Ba lần đột biến **sống sót** trong quá trình phát triển đều được xử lý bằng đột biến mạnh hơn hoặc test
biên mới, không bằng hạ kỳ vọng: T4a-M2 (bản đầu), T6a-M1, và **K-M1** của đợt này — `answered_rows` bỏ bộ
lọc `PENDING_GENERATION` không bị bắt vì row D trong bộ test tổng hợp có `answer_chars = 0` (bị loại vì lý
do khác); đổi row D thành `answer_chars = 5` kèm ghi chú ngay trong test, chạy lại → **17/18 → 18/18**.

Răng theo 4 máy kiểm cuối (mỗi dòng = một hành vi sai cố ý gây ra rồi bị chặn):

| Máy kiểm | Hành vi sai bị bắt |
|---|---|
| `env_flag_audit` | default `"1"` trong mã; `.env.example` bật cờ lever; accessor trả `True` khi env trống; `setdefault` ngầm trong `src/`; chuỗi kiểm quá mỏng bị từ chối kết luận "sạch"; bật trong script đo chỉ bị ghi chú, không gán lỗi |
| `secret_scan` | mẫu dương tự chế cho từng nhóm pattern secret + đường dẫn theo tên user; placeholder không bị tính là secret |
| `train_data_audit` | leak nội dung train↔val↔benchmark; id trùng tên; dòng code-QA thiếu trích dẫn/định danh; lệch số dòng so với manifest |
| `council_check_*` | fabrication rate trả `None`; gold@6 lấy mẫu số theo số row; trần xếp hạng tính cả item không có chunk vàng; "chấm lại khớp liều"; giấu round lệch chữ ký; bỏ lượt env-đối-chứng; mã thoát luôn 0; hai lần `build()` khác nhau; cờ vàng tái lập khác vẫn báo giống |

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
| Chung | Trọng tài mù với "đúng căn cứ nhưng lạc đề" (36/43 ca nặng); 11 verdict đổi chiều khi siết luật so khớp số; chưa chứng minh định nghĩa "bịa" theo ý hội đồng | PA-20 |

## 12. Phán quyết tổng

| Tiêu chí | Phán quyết |
|---|---|
| Test xanh và có hiệu lực | **ĐẠT** — 1.338 passed + 5 skipped có lý do + 2 slow passed (82,32 s) chạy riêng; 126/126 đột biến bị bắt; chữ ký `9f1179ccab74` |
| Không sửa dụng cụ đo để qua cổng | **ĐẠT** — gate.py/verify.py/text_utils.py không đổi; mọi thay đổi gate chỉ là bản đề xuất tách rời; 3 script hội đồng chỉ-đọc |
| Số công bố tái lập được | **ĐẠT** — 55/55 dòng khớp (mục 3); 3 đính chính ghi nguyên (79/79 → 126/126, −0,0028 → −0,0029, 17/17 → 16/16) |
| Lever mới an toàn khi tắt | **ĐẠT** — 13/13 cờ mặc định TẮT ở 5 lớp + golden từng byte |
| Repo không lộ secret | **ĐẠT có điều kiện** — 0 secret, 0 đường dẫn cá nhân; 89 dòng PII ở 8 file **chưa** vào git (PA-31) |
| Dữ liệu train không leak, bất biến #7 | **ĐẠT** — 0 leak nội dung trên 10.619 dòng; code-QA 1.635 dòng tự chứa đáp án; artifact SFT vòng lặp ĐỎ ở check độ dài (PA-11/12/28) |
| Người ngoài chạy lại từ repo | **CHƯA ĐẠT** — PA-26 (47 file chưa tracked) + PA-33 (`.gitignore`) |
| Chất lượng tầng sinh | **CHƯA ĐẠT** (không phải lỗi test) — r7 gold 0,80 nhưng PASS_CORRECT 0,14; r10 3B không đạt ngưỡng ≥22 (p=0,804); r12/r13 âm |

Việc cần duyệt đầu tiên trước khi trình hội đồng: **PA-26 kèm PA-31** (commit 47 file + mask PII) và
**PA-33** (bịt `.gitignore`), vì cả ba quyết định việc "fresh clone chạy được 1.338 test".

## 13. Lệnh tái lập toàn bộ

```bash
# 1) Bộ test + chữ ký trọng tài
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests -q
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -c \
  "from tools.loop import verify; print(verify.referee_fingerprint())"

# 2) Test chậm (GPU/Ollama) — mặc định skip
T4_RUN_SLOW=1 PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests/test_t4_gpu_slow.py -q

# 3) Bốn máy kiểm nghiệm thu cuối (chỉ-đọc; exit 0 = sạch)
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/env_flag_audit.py    --json tmp/env_flag_audit.json
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/secret_scan.py       --json tmp/secret_scan.json
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/train_data_audit.py  --json tmp/train_data_audit.json
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/final_number_audit.py --json tmp/final_number_audit.json

# 4) Ba script câu hỏi hội đồng
for s in fabrication referee gold6; do
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/council_check_$s.py --json tmp/council_$s.json || echo "FAIL: $s"
done

# 5) 13 harness đột biến (mỗi harness tự hoàn nguyên + kiểm SHA-256)
for f in tmp/mutation_check_t0.py tmp/mutation_check_t1.py tmp/mutation_check_t2.py \
         tmp/mutation_check_t3.py tmp/mutation_check_t4.py tmp/mutation_check_t4_new.py \
         tmp/mutation_check_t5.py tmp/mutation_check_t6.py tmp/mutation_check_t6_tests.py \
         tmp/mutation_check_t7.py tmp/mutation_check_t7_dot2.py tmp/mutation_check_cache_policy.py \
         tmp/mutation_check_final_council.py; do
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe "$f" || echo "FAIL: $f"
done
```

## Phụ lục A — đầu ra chính của ba máy kiểm hội đồng (nguyên số)

| Máy | Tổng | Dòng LỆCH | exit |
|---|---|---:|---:|
| `council_check_fabrication.py` | 10 round · 1.000 dòng · 380 đã trả lời · 7 trái ngữ cảnh · 43 ca nặng (FAB 7 / CFP 6 / HOU 30) · 18 item khác nhau · 36/43 ca nặng mù | 0 | 0 |
| `council_check_referee.py` | 19 round/phase · 1 chữ ký · 1.000/1.000 chấm lại khớp (1,57 s) · env-độc lập ĐẠT · cổng từ chối ĐẠT · 11 verdict đổi chiều ở luật nghiêm khắc · `n_filled = 0` | 0 | 0 |
| `council_check_gold6.py` | 811 item · 700 mẫu số · r0 363 = 0,5186 · 9 round tái lập · 7 file `gate_vs` khớp · trần pool-12 = 0,8214 · 125 item trượt recall · mất neo 0,4881 ĐỎ · r11↔r14 và r12↔r15 giống từng item | 0 | 0 |

## Phụ lục B — bản 13:26 | bản này (đo lại) | vì sao khác

| Đại lượng | Bản 13:26 | Bản này | Khớp với bản cũ? |
|---|---|---|---|
| Toàn bộ test | 1.064 passed, 2 skipped, 21,02 s | **1.338 passed, 5 skipped, 60,25 s** | không — đã thêm T6 dot2 (60), T7 dot2/dot3 (106) và 111 test nghiệm thu cuối |
| Test chậm T4 | 2 passed, 79,04 s | 2 passed, **82,32 s** | có (cùng 2 passed; thời gian đổi theo lượt máy) |
| Đột biến | 79/79 | **126/126** | không — phép cộng cũ thiếu 3 harness và tự mâu thuẫn (5+4+6+9+7+10+13+10+17 = 81) |
| T7 run_chain + cache | 17/17 rồi 16/16 | 6/6 + 10/10 = **16/16** | có (sau đính chính) |
| r13 header | −0,0028 | **−0,0029** | không — đính chính theo `header_paired_r11_r13.json` |
| Chữ ký trọng tài | `9f1179ccab74` | `9f1179ccab74` | có |
| Untracked `src/tools/tests` | 35 | **47** | không — thêm 4 công cụ + 4 test của batch này và các file T6/T7 dot2 |
| File tracked đang sửa | 6 | 11 (6 PA-8 + 5 docs) | không — docs đổi vì chính báo cáo này và các commit T6/T7 sau đó |
| Bảng đối chiếu số | 20 dòng | **55 dòng, 55 khớp** | có (mở rộng, không sửa số cũ ngoài 3 đính chính) |
