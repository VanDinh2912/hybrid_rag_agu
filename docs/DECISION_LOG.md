# SỔ QUYẾT ĐỊNH (DECISION_LOG)

Mỗi dòng là **một quyết định đã ra**, kèm giả thuyết đã đăng ký trước, số đo dùng để quyết, **file nguồn
trên đĩa**, và trạng thái. Quy ước trạng thái:

| Trạng thái | Nghĩa |
|---|---|
| **GIỮ** | Quyết định đang có hiệu lực (code/cấu hình/tài liệu đang ở trạng thái này). |
| **BÁC** | Giả thuyết bị số đo bác; lever/giả thuyết không dùng nữa. |
| **CHỜ DUYỆT** | Đã có số + diff, nhưng việc áp dụng thuộc quyền user (xem `docs/PENDING_APPROVAL.md`). |
| **MỞ** | Chưa kết luận được vì thiếu dữ liệu/điều kiện; điều kiện đóng ghi kèm. |

Nguyên tắc bất biến đứng trên mọi dòng: **ngưỡng đã đăng ký trước thì không chỉnh sau khi thấy số**;
**không chấm lại round đã đóng** trừ khi chính trọng tài đổi (khi đó phải chấm lại *tất cả*);
**trọng tài chỉ được sửa qua đề xuất**; số âm được ghi nguyên, không thêm lever để cứu số.

---

## Bảng tổng

| ID | Ngày | Giả thuyết (một dòng) | Số đo quyết định | Nguồn | Trạng thái |
|---|---|---|---|---|---|
| D-01 | 23-10 | Bộ lọc nguồn cứng là kẻ phá recall số 1; thay bằng lọc mềm + bonus sẽ kéo gold@6 lên | gold@6 51,86% → **76,57%**; `FAIL_RETRIEVAL` 337→164; bị filter cắt 244→**0**; neo HUMAN 81,44→77,32% (−5,06% tđ ⇒ cổng chặn) | `data/loop/rounds/r1/round_summary_retrieval.json`, `data/loop/rounds/r1/gate_vs_r0_retrieval.json` | GIỮ lever (mặc định code vẫn TẮT: `src/router.py:220`) |
| D-02 | 23-10 | Hạn ngạch nguồn 4 ô/cửa sổ sửa được lỗi "một nguồn chiếm cả cửa sổ" | gold@6 74,00% → **74,29%** (+0,29 ≈ 2 item); 2 cổng ĐẠT nhưng gold **không hồi phục** | `data/loop/rounds/r4/round_summary_retrieval.json`, `data/loop/rounds/r4/gate_vs_r2_retrieval.json` | **BÁC** (giả thuyết cấu trúc sai) |
| D-03 | 23-10 | Rescue (gửi lại prompt khi guard bắt) cứu được câu sai | 60/64 lượt thử, **cứu được 1 = 1,7%**; r5b lặp lại y hệt | `data/loop/rounds/r5b/rescue_tally.txt` (đếm nguyên văn 60 dòng `[AnswerRescue]`), `data/loop/rounds/r5b/gate_vs_r5_full.json`, `data/loop/rounds/r5/round_summary_full.json` | **BÁC vĩnh viễn** |
| D-04 | 24-10 | Bộ chuẩn hóa làm mất dấu/đổi nghĩa câu hỏi; guard phát hiện sẽ lấy lại chunk vàng | **5/5** ca bị bác lấy lại chunk vàng; `PASS_CORRECT` 10→**14**; gold@k 0,6875→**0,7875**; refusal 0,72→0,64; cổng chỉ vướng **trần refusal tuyệt đối** | `data/loop/rounds/r6/normalizer_guard_tally.txt`, `data/loop/rounds/r6/round_summary_full.json`, `data/loop/rounds/r6/gate_vs_r5b_full.json` | GIỮ lever; bật mặc định = **CHỜ DUYỆT** (#23) |
| D-05 | 24-10 | Cộng bonus 12 + guard sẽ cộng hưởng | `PASS_CORRECT` **14→14** (trong băng nhiễu ±3); 2 ca `PASS_CORRECT` → từ chối oan | `data/loop/rounds/r7/combo_tally.txt`, `data/loop/rounds/r7/gate_vs_r6_full.json` | **BÁC** tổ hợp |
| D-06 | 24-10 | "Bonus 12 làm mất 2,57 điểm so với bonus 3" là do chỉnh sai hằng số | Ghép cặp 811 item: delta **−0,0257, CI [−0,04; −0,0129], p = 0,00028**; 21 mất/3 được; **21/21** chunk vàng rơi hạng **7–12**; EXACT/TRAP **bất biến** | `data/loop/diag/bonus_paired_r1_r2.json`, `data/loop/diag/bonus_paired.json` | **BÁC** giả thuyết "hằng số bonus là nút thắt" |
| D-07 | 24-10 | Bỏ đường từ chối khỏi prompt + 5 luật ngoài sẽ tăng câu đúng mà không tăng bịa | `PASS_CORRECT` 14→**19** (<25), refusal 0,69→**0,28**, fabrication 0,0323→0; nhưng `PASS_REFUSAL` **17→2**, `FAIL_HALLUCINATED_ON_UNANSWERABLE` **2→12**, p95 19,93 s; cổng 5 vi phạm | `data/loop/rounds/r8/round_summary_full.json`, `data/loop/rounds/r8/gate_vs_r5_full.json`, `docs/reports/T3.md` | **BÁC** — cờ `ENABLE_DECOUPLED_REFUSAL` TẮT |
| D-08 | 24-10 | Cửa sổ sinh 3–5 câu bằng chứng (thay 7k ký tự) giúp model 1,5B trả lời đúng hơn | 75/75 cửa sổ đúng 5 câu (6.898→1.022 ký tự); `model_still_refuses` **3→32**; refusal 0,57; p95 19,93→**33,27 s (+67%)**; `PASS_CORRECT` 19→19 (tập câu khác) | `data/loop/rounds/r9/round_summary_full.json`, `data/loop/rounds/r9/gate_vs_r8_full.json`, `docs/reports/T3.md` | **BÁC** — cờ `ENABLE_EVIDENCE_SELECTION` TẮT |
| D-09 | 24-10 | Nâng model sinh 1,5B → 3B (cùng máy, cùng prompt) sẽ vượt 22/100 câu đúng | `PASS_CORRECT` 14→**16**; delta +0,0203 CI **[−0,06; +0,10]**; McNemar **p = 0,804**; p95 18,65→**34,12 s (+83%)**; một-biến 100/100 item trùng | `data/loop/rounds/r10/round_summary_full.json`, `data/loop/rounds/r10/t4_stats.json`, `data/loop/diag/one_variable_check.json`, `docs/reports/T4.md` | **BÁC** — giữ `qwen2.5:1.5b-instruct` |
| D-10 | 24-10 | Có thể SFT trên máy 4 GB với dữ liệu hiện tại | Trần VRAM đo được **≈1.000 token/dòng** (960→3.931 MiB; 1.024→4.156,9 MiB); **13/13** dòng train ≥1.016 token ⇒ không vừa; gradient checkpointing **không giúp** | `data/loop/diag/t4b_memory_probe.json`, `data/loop/diag/t4b_memory_probe_len.json`, `data/training/t4b_r5r8r9r10/manifest.json` | **MỞ** — chờ PA-11 (4-bit) / PA-12 (đổi định dạng) |
| D-11 | 25-10 | Reranker cross-encoder (top-20 → top-6) nâng gold@6 | gold@6 0,7400→**0,6686**, delta **−0,0714 CI [−0,1014; −0,0414]**, McNemar 83/33 **p=3,9e−06**; probe: **0/30** với `fold(query)`, **28/30** với query nguyên văn ⇒ lỗi build | `data/loop/diag/reranker_paired_r11_r12.json`, `tmp/probe_r12_fold.json`, `docs/reports/T5.md` §2.7 | **MỞ** — cờ TẮT; sửa + r14 = **PA-25** |
| D-12 | 25-10 | Gắn header Chương/Điều/Khoản vào chunk giúp truy xuất | gold@6 0,7400→0,7371, delta **−0,0029 (= −2/700) CI [−0,0129; +0,0071]**, McNemar p=0,79 (|delta|=2 < nhiễu 11) | `data/loop/diag/header_paired_r11_r13.json`, `data/loop/rounds/r13/gate_vs_r11_retrieval.json` | **BÁC** trên corpus cũ; corpus T2 = **MỞ** (PA-21). ĐÍNH CHÍNH 25-10: bản in trước ghi −0,0028 (cắt số), giá trị đúng là −0,0029 |
| D-13 | 24-10 | Nút thắt dấu tiếng Việt nằm ở pipeline convert PDF; OCR lại bằng EasyOCR `vi` sẽ sửa được | Corpus 17,8%→chunk 19,13% từ có dấu; OCR 3,3%→**82,3%**; index mới 19,13%→**80,29%**; chunk <5% dấu 167→**2** | `data/loop/diag/corpus_diagnostics/{per_file.json,index_before.json,index_after.json}`, `docs/reports/T2.md` | GIỮ artifact `chroma_db_vie/`; **kích hoạt = CHỜ DUYỆT** (PA-1) |
| D-14 | 24-10 | Năng lực Gemini là nút thắt của cấu hình (b) | 25/30 id hợp lệ: `PASS_CORRECT` **16/25 = 64,0%** [44,0; 84,0], refusal 12,0%; 5 id thiếu đúng là **5 id cuối theo thứ tự r5** | `data/loop/diag/b_gemini_top6/summary_dedup_25.json`, `data/loop/diag/b_gemini_top6/bootstrap_ci_25.json`, `data/loop/diag/b_gemini_top6/id_status.json` | **MỞ** — cần đủ 30/30 (PerDay ~14:30) |
| D-15 | 24-10 | Cổng `refusal_rate_bounded` dùng trần tuyệt đối 0,35 đang veto oan | Đề xuất cổng **tương đối** (candidate ≤ baseline + 0,05); 0,35 thành **cảnh báo không phủ quyết**; 8 test trên bản tạm | `tools/diag/gate_refusal_relative_proposal.py`, `tests/test_gate_refusal_relative_proposal.py`, `docs/PENDING_APPROVAL.md` PA-13 | **CHỜ DUYỆT** — `tools/loop/gate.py` **không** đổi |
| D-16 | 24-10 | Tổng điểm trọng số trong báo cáo đánh giá đang sai số học | 0,20·9,2+0,15·8,2+0,20·7,0+0,20·8,5+0,25·4,0 = **7,17 → 7,2** (bản cũ ghi 7,4) | `docs/bao_cao/danh_gia_tong_quan_2026-10-23.md`, `data/loop/diag/metric_ci_r5_full.json`, `data/loop/diag/metric_ci_r7_full.json` | GIỮ 7,2; điểm thành phần = **CHỜ DUYỆT** (PA-23) |
| D-17 | 23→25-10 | Có thể sửa trọng tài/gate giữa chuỗi round mà không phải chấm lại | Chữ ký trọng tài **`9f1179ccab74`** ở mọi round r0…r13 ⇒ không round nào phải chấm lại | `tools/loop/verify.py`, `data/loop/rounds/r10/round_summary_full.json` (`settings`), `data/loop/README.md` mục "Bảy bất biến" | GIỮ (bất biến) |
| D-18 | 23→25-10 | Số test "563 xanh" là mốc chuẩn để so | Sau T2/T3/T5/header: **967 passed** (62,53 s, 25-10 04:1x); sau T7 (`run_chain` + `cache_policy`): **1.004 passed**; sau test biên T6a: **1.005 passed**; sau test T0 "CI chứa ước lượng điểm giải tích": **1.006 passed** (32,54 s, 25-10 11:51); sau 5 test T1 (isol + guard tập item): **1.011 passed** (29,79 s, 25-10 11:55); sau 3 test T2 (nguyên văn qua `build_chunks`): **1.014 passed** (30,77 s, 25-10); sau 2 test T3 A1' (TẮT khi env còn ngưỡng lever TẮT): **1.016 passed** (29,29 s, 25-10 12:1x) | `tmp/pytest_t5_final.txt`, `tmp/pytest_t4t6_final.txt`, `tmp/pytest_t0_final.txt`, `tmp/pytest_t1_final.txt`, `tests/`, `docs/STATE.md` | GIỮ 967 là mốc lịch sử; **1.016** là mốc hiện tại (D-21/D-24) |
| D-19 | 25-10 | Reranker chỉ khả thi nếu chạy trên GPU, mà không được phá `venv/`/`venv_train/` | `venv_gpu/` riêng (torch 2.14.1+cu126): pytest **967 passed**, VRAM 3.594/4.096 MiB, rerank 2,05 s/item | `data/loop/diag/reranker_cost_gpu.json`, `docs/AUTONOMY_LOG.md` 25-10 02:20 | GIỮ (môi trường tách biệt) |
| D-20 | 25-10 | Ngoại suy chi phí round = chi phí riêng tầng rerank | **Sai**: r12 thật **≈66 phút** (4,74 s/item) = 2,0 s rerank **+ 2,78 s truy xuất nền** ⇒ vượt ngưỡng tự đặt 60 phút | `data/loop/rounds/r12/round_summary_retrieval.json`, `tmp/vram_r12_run.log`, `docs/reports/T5.md` §2.6 | **BÁC** phương pháp; thay bằng `rerank + baseline` |
| D-21 | 25-10 | Cache sinh chỉ băm `{model, temperature, prompt_version, prompt}` ⇒ đổi ngưỡng cứu/từ chối vẫn trúng câu trả lời của thể chế cũ | Thêm `policy` **chỉ khi** thể chế lệch mốc `DEFAULT_CACHE_TOKEN` (**d0b4c6a65f83**); thể chế mặc định giữ khóa cũ từng byte. 26 test mới, mutation **10/10** bắt | `src/cache_policy.py`, `src/generator.py` (2 hàm `_cache_key`), `tests/test_cache_policy.py`, `tmp/mutation_check_cache_policy.py` | GIỮ trong working tree; **CHỜ DUYỆT commit** (PA-26) |
| D-22 | 25-10 | Driver `.sh` viết tay trong `tmp/` là đủ để tái lập một round | Không: thiếu log là mất danh sách env; thay bằng spec JSON + manifest tất định. Chuỗi demo 2×20 item chạy end-to-end (gate ĐẠT + attribute); 11 test, mutation **6/6** bắt | `tools/loop/run_chain.py`, `tools/loop/chains/t5a_reranker.json`, `tests/test_run_chain.py`, `tmp/mutation_check_t7.log` | GIỮ — **đã commit** `79a02e5` |
| D-23 | 25-10 | HEAD tài liệu tái lập được cây đã test 1.016 test | **Sai**: còn 35 file nguồn/công cụ/test chưa tracked (gồm `tools/loop/noise_floor.py`, `src/answer_guard.py`, `src/cache_policy.py`) + 6 file sửa dở; bản `src/generator.py` trong HEAD không có `effective_prompt_version` | `docs/PENDING_APPROVAL.md` PA-26, `docs/STATE.md` | **MỞ** — chờ chọn phương án commit freeze |
| D-24 | 25-10 | Có thể sửa `cache_policy.py` để khóa TẮT không phụ thuộc env của lever TẮT ngay trong phiên kiểm thử T3 | Phát hiện **đúng** (cả hai cờ T3 TẮT: deviation `None` → `e95e6efa2617`/`1670eb7035ac`/`94515a7efa5d`, đầu ra 30 item byte-identical), nhưng sửa là chạm khóa cache T7 + buộc đổi 3 test đã có ⇒ ghi **PA-27**, không sửa; chỉ thêm 2 test ghim cả hai nửa (đầu ra bất biến / khóa tách là hiện trạng) | `tests/test_t3_guardrails.py`, `docs/reports/test_T3.md` §9, `docs/PENDING_APPROVAL.md` PA-27 | **CHỜ DUYỆT** — PA-27 |
| D-25 | 25-10 | Pipeline SFT + generator T4 thỏa đủ 9 mục đặc tả (bất biến dữ liệu, giao diện chung, cache, số đo GPU) | Mục 1–4 **XANH** trên artifact thật (13 train / 10 holdout / 58 item test); **mục 5 ĐỎ do DỮ LIỆU** (13/13 dòng train + 8/10 holdout > 768 token, min 1.016); mục 8: p50 **2,900 s** / p95 **4,421 s** / VRAM đỉnh **1.401 MiB**; mục 9: adapter khác base + nạp hỏng ném `ValueError`; mutation **8/8** | `tmp/t4_invariants_report.json`, `data/loop/diag/t4_latency_20q.json`, `data/loop/diag/t4_adapter_probe.json`, `tmp/mutation_check_t4_new.log`, `docs/reports/test_T4.md` §10 | GIỮ bộ test; mục 5 ĐỎ = **PA-28**; adapter chỉ chứng minh cơ chế |
| D-26 | 25-10 | "Chỉ pha sinh r5 đổi từ KHÔNG ĐẠT sang ĐẠT theo luật refusal tương đối" (đề bài T6) | Kiểm trên file cổng đã công bố: **r5-vs-r3 vẫn KHÔNG ĐẠT** (refusal 0,61→0,69 = +0,08 > 0,05; fabrication 0,0256→0,0323); ca lật duy nhất **r5-vs-r1** (0,69 vs 0,72 ⇒ ĐẠT + cảnh báo trần 0,35); r3-vs-r1 vẫn đỏ vì hallucinated 2→3; r4-vs-r2 retrieval y nguyên ĐẠT (811 item, gold 0,7400→0,7429) | `data/loop/rounds/r5/gate_vs_r3_full.json`, `data/loop/rounds/r5/gate_vs_r1_full.json`, `data/loop/rounds/r3/gate_vs_r1_full.json`, `data/loop/rounds/r4/gate_vs_r2_retrieval.json`, `docs/reports/test_T6.md` §8.2 | **ĐÍNH CHÍNH đề bài**; 60 test + mutation 10/10; PA-13 vẫn **CHỜ DUYỆT**, `gate.py` không đổi |
| D-27 | 25-10 | Đặt tên artifact mới theo kiểu "ghi đè là bình thường trong `tmp/`" có chấp nhận được không | **Không**: harness 20 đột biến mang tên `tmp/mutation_check_t7.py` đã xoá bằng chứng 6/6 mà D-22 dẫn (lần **thứ 2** lặp lỗi T6). Khôi phục: `unified_diff` giữa bản trích từ transcript và snapshot `Read` = **0** khác biệt, **chạy lại harness khôi phục được 6/6 (rc=0)**, SHA-256 3 file nguồn đợt 1 vẫn trùng (`bf13918a…`/`652477e3…`/`d3791b44…`) ⇒ log 6/6 còn áp dụng cho code hiện tại; harness mới đổi thành `tmp/mutation_check_t7_dot2.py` (log **20/20**) | `tmp/mutation_check_t7.py`, `tmp/mutation_check_t7.log`, `tmp/mutation_check_t7_rerun_dot2.log`, `tmp/mutation_check_t7_dot2.py`, `tmp/mutation_check_t7_dot2.log`, `docs/AUTONOMY_LOG.md` (Ngã rẽ 1), `docs/reports/test_T7.md` §8.5 | **GIỮ** thủ tục khôi phục; mất 1 snapshot kiểm kê (`tmp/cleanup_report_t7.json` 104→164 mục) — số PA-24 vẫn là ảnh chụp có ngày giờ |
| D-28 | 25-10 | "Bộ test T7 đợt 2 chứng minh mọi lớp phòng vệ của `tmp_cleanup`" — và "mọi con số đợt 1 đã ghi là đúng" | Lượt đầu **18/20** (M12, M14 **lọt**) vì `check_target()` có 3 lớp **dư thừa**: bỏ 1 lớp thì lớp khác vẫn chặn ⇒ test không cô lập được lớp nào. Thêm **2 test junction thật** (`mklink /J`, `is_symlink()`=False) để tách lớp a và lớp c ⇒ **20/20, 0 lọt**, hoàn nguyên byte-identical. Đồng thời phát hiện **1 lỗi số đã công bố**: §2.3/§3 ghi "17/17" đột biến, tổng thật là 6+10 = **16** | `tmp/mutation_check_t7_dot2.log`, `tools/diag/tmp_cleanup.py`, `tests/test_t7_tmp_cleanup.py`, `docs/reports/test_T7.md` §2.3 + §8.3 | **GIỮ** 3 lớp chặn (không nới checker); **ĐÍNH CHÍNH** 17/17 → 16/16 + 20/20 |
| D-29 | 25-10 | Mục 6 đề bài ("mọi lệnh README chạy được ở `--help`/dry-run") có thể chứng minh **hết** bằng checker tự động không | **Không hết**: 264 lệnh được phân loại, 9 script repo, chỉ **4** có argparse ⇒ chạy `--help` thật (rc=0 cả 4); **5** script (`ingest.py`, `learn.py`, `src/analyze_ab.py`, `demo_streamlit.py`, `ui/app.py`) không argparse ⇒ chỉ CẢNH BÁO, không tính là ĐẠT; **100** đường dẫn README/ROADMAP/docs tồn tại, **0 lỗi**; 2 đường dẫn GUI tự sinh được allowlist + in ghi chú. Rủi ro thật tìm thấy khi đọc `ingest.py`: `shutil.rmtree(persist_dir)` mặc định `./chroma_db` — lệnh README §5.1 **xoá index sản xuất**, không dry-run, không xác nhận | `tools/diag/docs_consistency_check.py`, `tmp/docs_check_t7_dot2.json`, `tests/test_t7_docs_consistency.py`, `ingest.py`, `README.md` | **CHỜ DUYỆT** — PA-29; checker giữ phân loại LỖI/CẢNH BÁO, không làm giả ĐẠT |
| D-30 | 25-10 | Tiêu chí "người ngoài tái lập được **round retrieval-only r0 với cùng số gold@6**" chỉ đạt ở mức tính lại artifact, hay đạt ở mức **chạy thật một lệnh**? | Đạt ở mức chạy thật: `tools/loop/chains/t7_repro_r0.json` (ghim 13 biến env đúng thể chế r0) → 811/811 item, **gold@6 0,5186 = 0,5186**, **0 verdict đổi chiều**, **811/811 top-6 giống hệt theo thứ tự**, 37,5 phút, **0 lượt Gemini**; manifest `--dry-run` và manifest lượt chạy **byte-identical** (SHA `295413c196de…`). Hai chỗ phải đính chính khi viết §8.4: (i) "1 item lệch" ở demo ĐỢT 1 là **khác thể chế** (`ENABLE_CLASSIFIER=0`) chứ không phải nhiễu; (ii) median r0 tự đo là **2,76 s/item**, số 2,78 đã dẫn là của **r11** | `data/loop/rounds/r0/round_summary_retrieval.json`, `tmp/rounds_t7_repro/r0_repro/round_summary_retrieval.json`, `tmp/compare_r0_repro.json`, `tmp/compare_r0_repro.py`, `data/loop/diag/chain_manifest_t7_repro_r0.json`, `tmp/t7_manifest_probe_dot2.json`, `docs/reports/test_T7.md` §8.4 + Phụ lục A2 | **GIỮ** kết luận (tiêu chí đạt ở mức artifact + một lệnh thật); **CHỜ DUYỆT** mức "fresh clone" — PA-26 + PA-29 |
| D-31 | 25-10 | Kiểm toán "mọi số công bố của T0–T7 tính lại được" (đề bài tổng kiểm tra, mục 2) có tìm ra số sai không — và sai thì sử lý thế nào | Có **1 số sai thật** trong **55** dòng kiểm toán: r13 (header) công bố delta gold **−0,0028** ở 5 tài liệu, nhưng chính artifact `data/loop/diag/header_paired_r11_r13.json` ghi `gold_delta = −0,0029` (= −2/700 = −0,002857, làm tròn 4 chữ số). Không artifact nào chứa −0,0028 ⇒ đây là **cắt số** chứ không phải con số từ phép đo khác. Cách xử lý bảo thủ: **sửa tài liệu theo artifact**, không sửa artifact, không hạ CI/p (CI [−0,0129; +0,0071], p=0,79 giữ nguyên); ghi ĐÍNH CHÍNH ngay trong D-12 để lần đọc sau không phải suy ra. 54 dòng còn lại khớp; công cụ kiểm toán là script **chỉ-đọc** (`tools/diag/final_number_audit.py`), kết quả lưu `tmp/final_number_audit.json` + bảng `tmp/final_number_audit_table.md` | `tools/diag/final_number_audit.py`, `tmp/final_number_audit.json`, `tmp/final_number_audit_table.md`, `data/loop/diag/header_paired_r11_r13.json`, `docs/reports/T5.md`, `docs/DECISION_LOG.md` D-12, `docs/MORNING_REPORT.md`, `docs/STATE.md`, `docs/AUTONOMY_LOG.md` | **ĐÃ SỬA** 5 tài liệu (không đổi số đo); **GIỮ** nguyên tắc "artifact là nguồn, tài liệu phải theo"; kiểm lại bằng `python tools/diag/final_number_audit.py` ⇒ `0 dòng LỆCH` |
| D-32 | 25-10 | Ba câu hỏi hội đồng ("có bịa không", "trọng tài có đáng tin không", "gold@6 = 0,5186 nghĩa là gì") nên trả lời bằng **một bài viết tay** hay bằng **script tái chạy được**? | Chọn script **chỉ-đọc**, mỗi câu một file, dựng lại số từ artifact đã đóng, in kèm đường dẫn nguồn, có `--json`, và **mã thoát là phán quyết của chính máy kiểm** (0 = mọi dòng đối chiếu khớp; khác chữ ký / có dòng LỆCH ⇒ 1). Số chốt: bịa — 1.000 dòng/10 round, 380 đã trả lời, 7 trái ngữ cảnh = **1 item khác nhau** (`S115028976296200`), 43 ca nặng (FAB 7/CFP 6/HOU 30) = **18 item**, **36/43 ca nặng mù với thước**; trọng tài — **19 round/phase 1 chữ ký**, **1.000/1.000 chấm lại khớp** (1,57 s), env-độc lập, cổng `gate.compatibility` từ chối bản khác, nhưng `n_filled = 0` ⇒ **chưa** có đồng thuận người, 11 verdict đổi chiều ở luật số nghiêm khắc; gold@6 — mẫu số **700/811**, **111 item mù**, r0 363 = 0,5186, **trần pool-12 = 0,8214**, 125 item trượt recall, **không so được giữa hai index** (mất neo 0,4881 ĐỎ). Quyết định đi kèm: **tự công bố điểm mù trong bài**, không chỉ đưa số đẹp | `tools/diag/council_kit.py`, `tools/diag/council_check_fabrication.py`, `tools/diag/council_check_referee.py`, `tools/diag/council_check_gold6.py`, `tmp/council_fabrication.{json,txt}`, `tmp/council_referee.{json,txt}`, `tmp/council_gold6.{json,txt}`, `tests/test_final_council_scripts.py` (43), `docs/reports/test_final.md` §7 | **GIỮ** (ba script chạy exit 0, 0 dòng LỆCH); **CHỜ DUYỆT** mức "fresh clone" vì verify.py/answer_guard.py chưa tracked (PA-26) |
| D-33 | 25-10 | Bản `test_final.md` 13:26 công bố "79/79 đột biến bị bắt" — có giữ con số đó khi tổng kết không? | **Không.** Đếm lại từ 13 log: 5+4+6+9+7+8+13+10+10+6+10+20+18 = **126/126**, 0 dòng "sống sót". Con số cũ vừa thiếu 3 harness chạy sau (T6 bộ mới 10, T7 docs dot2 20, nghiệm thu cuối 18) vừa **tự mâu thuẫn** (dãy cộng ghi ngay trong bảng là 5+4+6+9+7+10+13+10+17 = 81). Cách xử lý: ghi sổ cái từng harness trong `test_final.md` §8 + Phụ lục B, giữ nguyên log cũ, không xoá không sửa. Kèm bài học **răng của test cho máy kiểm**: đột biến K-M1 (`answered_rows` bỏ lọc `PENDING_GENERATION`) sống ở lượt 1 (17/18) vì row D trong bộ test tổng hợp có `answer_chars = 0` ⇒ bị loại bởi lý do khác, không ai thấy mẫu số phình; sửa row D thành `answer_chars = 5` **kèm ghi chú gần-trượt ngay trong test**, chạy lại → 18/18. Không hạ kỳ vọng của test nào | `docs/reports/test_final.md` §8 + Phụ lục B, `tmp/mutation_check_final_council.{py,log}`, `tests/test_final_council_scripts.py` (`TestDinhNghiaCuaKit`), 13 log `tmp/mutation_check_*.log` + `tmp/t2_mutation_6.log` + `tmp/t3_mutation_recheck_9.log` | **GIỮ** 126/126 là con số chuẩn; nguyên tắc "tổng đột biến phải đếm từ log, không cộng tay" |
| D-34 | 25-10 | Sau commit `a170e92`, 3 test ghim hiện trạng của `TestHienTrangRepo` **đỏ** vì máy quét secret bắt chính mẫu gieo trong `tests/test_final_secret_scan.py` (4 `SECRET_COTHAT` + 4 `DUONG_DAN_CA_NHAN`, PII 89→93). Sửa máy quét, nới test, hay sửa mẫu? | **Sửa mẫu, giữ nguyên máy quét và kỳ vọng.** Chẩn đoán: đây là **máy kiểm tự nhiễm phạm vi của nó** (`tracked_files()` đọc `git ls-files`, nên file test vừa được commit trở thành đối tượng bị quét), **không phải** repo có credential. Nới máy quét = phá dụng cụ đo; nới test = hạ kỳ vọng để xanh (cấm cả hai). Cách sửa: helper `_ghep()` dựng chuỗi mẫu **tại runtime** ⇒ literal không còn trong source đã commit, còn test vẫn buộc máy quét bắt được chuỗi hoàn chỉnh khi nó được ghi ra `tmp_path` (M1 Google key, M2 PEM, M3 đường dẫn cá nhân, test redact đều giữ nguyên assertion). Sau sửa: `pytest tests/test_final_secret_scan.py -q` = **14 passed**, `secret_scan --scope tracked` = **0 secret / 0 đường dẫn / 89 PII / 8 file** đúng số đã công bố; bảng trước/sau commit lưu `tmp/secret_scan_post_commit.json` (281 file ứng viên / 249 đã đọc / 339 dòng khớp / 250 `BI_MAU`). **Quy trình mới đăng ký**: với máy kiểm có phạm vi lấy từ git, phải chạy lại `--scope tracked` **sau khi stage/commit** — test ghim hiện trạng chính là thứ phát hiện loại nhiễm này, và nó đã làm đúng việc | `tests/test_final_secret_scan.py` (`_ghep`, `TestHienTrangRepo`), `tmp/secret_scan.json`, `tmp/secret_scan_post_commit.json`, `docs/reports/test_final.md` §5 + §11 | **ĐÃ SỬA** (chỉ file test của phiên này); **GIỮ** nguyên tắc "nhiễm phạm vi thì sửa mẫu, không sửa thước" |

---

## Chi tiết những dòng cần ngữ cảnh

### D-01 — Lọc mềm cứu recall nhưng làm mất neo (23-10)

Giả thuyết: `source_filter` cứng xoá nguồn khi classifier sai nhãn, nên 244/337 `FAIL_RETRIEVAL` của r0
là do bộ lọc. r1 (một biến) xác nhận: bị-filter-cắt về **0**, gold@6 +24,7 điểm. **Nhưng** cổng
`human_anchor_source_not_degraded` chặn vì 11 câu do người viết mất văn bản cần thiết. Quyết định:
**giữ lever, không coi r1 là cấu hình production**; mọi round sau dùng bonus 3 (đến r2) hoặc 12 (r4+)
tuỳ câu hỏi đo. Mặc định trong code vẫn TẮT vì chưa có round nào qua **cả hai** cổng.

### D-03 — Rescue bị bác vĩnh viễn (23-10)

Lý do không thử lại: cơ chế đã được đo trực tiếp trên 60–64 lượt thật, không phải suy luận. Tỉ lệ cứu
1,7% nằm dưới xa mức cần để bù chi phí một lượt gọi model/câu. r5b lặp lại **nguyên văn** cấu hình để
chứng minh con số tái lập được (không phải may mắn của một lần chạy).

### D-04 — Guard chuẩn hóa là lever sinh đầu tiên có bằng chứng (24-10)

Điểm quan trọng nhất: **5/5 ca** bị bác lấy lại đúng chunk vàng, và tập ca được chọn từ log của lever
chứ không phải từ kết quả. Cổng vẫn báo KHÔNG ĐẠT chỉ vì `refusal_rate` vượt trần tuyệt đối 0,35 —
chính là lý do đề xuất D-15. Việc **bật mặc định** chưa làm vì đổi hành vi production.

### D-06 — Câu hỏi "bonus 3 hay 12" đã có số, nhưng câu trả lời không phải "chỉnh hằng số" (24-10)

Ghép cặp toàn bộ 811 item cho thấy mất **2,57 điểm** là thật (p = 0,00028), không phải nhiễu. Nhưng cơ
chế: **21/21** chunk vàng bị mất nằm **ngoài** `source_filter` và rơi đúng hạng **7–12** — tức chỉ cần
cửa sổ rộng hơn hoặc xếp hạng tốt hơn, không phải đổi 12→3. EXACT/TRAP không đổi giữa r1/r2/r4 là
bằng chứng phụ. Vì vậy giả thuyết "hằng số bonus là nút thắt" bị **bác**; hướng đúng là **reranker /
pool 20** (D-11) — và đây là lý do T5a được đăng ký.

### D-11 — Reranker: kết luận âm là về **bản build**, không phải về ý tưởng (25-10)

Trước khi kết luận "reranker không giúp", đã kiểm tra giả thuyết "hỏng do cài đặt": probe chọn đúng 30
item mà r12 đẩy gold ra khỏi cửa sổ, chấm lại hai lần với **cùng model, cùng chi phí**, khác duy nhất ở
chỗ query có bị `fold()` hay không. Kết quả 0/30 vs 28/30. Đó là lý do dòng này là **MỞ** (chờ PA-25),
không phải BÁC. Trần oracle pool 20 = 0,8871 (so 0,8214 của pool 12) lượng hoá phần còn có thể lấy.

### D-12 — Header: không có tín hiệu trên corpus cũ (25-10)

|delta| = 2 item < băng nhiễu 11 và CI chứa 0 ⇒ theo ngưỡng đăng ký trước **không được** gọi là cải
thiện. Giải thích hợp lý: 253/361 chunk vốn đã có header `[file] - [Điều]`, nên phần header mới thêm
chỉ là Chương/Khoản/Điểm + 108 chunk fallback. **Không** suy ra "header vô dụng trên corpus T2" — corpus
T2 có 48,81% neo vàng gãy (PA-21), phải đo lại sau khi neo vàng được sửa.

### D-13 — Dấu tiếng Việt: sửa được ở tầng OCR, chưa kích hoạt (24-10)

Chuỗi bằng chứng: đo corpus (17,8% từ có dấu) → xác định PDF-scan/convert là nguồn → OCR lại 123 trang
bằng EasyOCR `vi` → chất lượng OCR 3,3%→82,3% → build index **riêng** `chroma_db_vie/` (342 chunk) →
đo bằng **cùng** script: 19,13%→80,29%. Quyết định bảo thủ: **không** đổi `chroma_db/` đang chạy; kích
hoạt index mới cần user duyệt (PA-1) vì đổi index = đổi dữ liệu đo của mọi round sau.

### D-14 — Vì sao chưa được nói "năng lực model là nút thắt" (24-10)

25/30 id là **tiền tố theo thứ tự r5** (5 id thiếu là 5 id cuối, 82–97), không phải mẫu ngẫu nhiên đủ.
`PASS_CORRECT` 64% trên 25 id **không** so được trực tiếp với 14% của Qwen trên 100 item khác (khác tập
câu, khác độ khó). Điều kiện đóng dòng này: đủ **30/30** id, giữ nguyên `data/loop/diag/b_gemini_top6/sample_ids.json`.

---

### D-21 — Khóa chính sách trong cache sinh: chỉ thêm khi lệch mặc định (25-10)

Vấn đề: cache của `GeminiGenerator` và `QwenGenerator` chỉ băm model/nhiệt độ/prompt/phiên bản prompt.
Đổi `RESCUE_MIN_SCORE` 0,8→0,55 hay `EV_MAX_SENTENCES` 5→9 thì câu trả lời cũ vẫn trúng ⇒ round sau
"tái dùng thể chế cũ", phép đo lever trông như vô hiệu.

Cách làm: `src/cache_policy.py` dựng ảnh chụp **chỉ cờ + ngưỡng** từ chính hàm phân giải của module sở
hữu (không có bảng mặc định thứ hai), rồi băm thành `policy_cache_token()` — **bỏ** `prompt_version`
và `decoupled_refusal.enabled` (đã được `prompt_version` mã hóa: `v1.3` ↔ `v2.0-extract-only`), **giữ**
mọi ngưỡng `RESCUE_*`, `ANSWER_GUARD_*`, `DEC_*`, `EV_*`, `NORMALIZE_MIN_CONTAINMENT`, `EVIDENCE_RERANKER`.
Khóa cache chỉ thêm `policy` khi token khác mốc `DEFAULT_CACHE_TOKEN`; nhờ vậy thể chế mặc định giữ
**đúng công thức cũ 4 trường** (không đỏ 7 test T3/T5 đang ghim công thức, 351+ entry cache còn dùng) —
đây là lựa chọn giữ bất biến #2 "cờ TẮT = hành vi cũ từng ký tự".

Hai lưu ý trung thực: (1) đổi ngưỡng hậu xử lý **buộc sinh lại** — đánh đổi có chủ đích, thà tốn lượt
hơn trộn thể chế; (2) `DEFAULT_CACHE_TOKEN` là mốc đăng ký, test
`test_policy_cache_token_default_matches_cleared_env` tính lại dưới env rỗng nên đổi default của module
sẽ làm test đỏ (phải đăng ký lại, không được sửa test cho xanh).

### D-22 — `run_chain`: một lệnh cho cả chuỗi round, có manifest tất định (25-10)

Điều được bảo đảm và đã kiểm bằng test (11 test, mutation 6/6): dry-run **không gọi subprocess**; manifest
cùng spec ⇒ cùng bytes, đường dẫn tương đối, `spec_sha256`; thiếu env bắt buộc dừng **trước** bước đầu;
thư mục round đã có dữ liệu bị từ chối (trừ `--resume`); biến bí mật không đi qua `--set`; round trùng
tên bị chặn; **cổng trả mã 1 có báo cáo ⇒ đi tiếp sang attribute** (kết quả âm phải được quy lỗi), chỉ
dừng khi cổng không tạo được báo cáo. Không sửa dụng cụ đo: `run_chain` chỉ gọi `run_round.py`, `gate.py` và `attribute.py`.

### D-23 — Khoảng trống giữa HEAD và cây đã test (25-10)

`HEAD = 79a02e5` (lúc đo D-23; sau đó có commit tài liệu `e6bd9a2`) còn thiếu 35 file nguồn/công cụ/test và 6 file tracked đang sửa dở (đo 41 file tại
`456f35c`; commit `79a02e5` đã tracked 6 file `run_chain` + test); hệ quả là fresh clone
không import nổi (`src/cache_policy.py` → `src/answer_guard.py` chưa tracked). Vì luật tự trị cấm commit
file `src/` dirty của phiên khác, việc đóng khoảng trống này là **PA-26** với ba phương án; đề xuất (ii)
commit mã + tổng hợp round, không commit `models/` (321 MB), `chroma_*`, `full.jsonl`. Khi được duyệt,
kiểm chứng bằng fresh clone + `pytest tests -q` kỳ vọng **1.016 passed**.

### D-25 — Kiểm thử T4: đo được gì, không sửa gì (25-10)

Đề bài yêu cầu 9 mục; bộ test mới phủ đủ, trong đó **chỉ mục 1–4 đạt trên artifact thật**. Kết quả mục 5
là **ĐỎ do dữ liệu**, không phải do test: 13/13 dòng train dài 1.016–1.707 token, vượt `max_length` 768
dự kiến cho GPU 4 GB (holdout 8/10, min 657). Theo luật đã đăng ký trước, **không** hạ ngưỡng và **không**
cắt dữ liệu để đạt; báo cáo giữ nguyên đỏ và chỉ ra hệ quả: kế hoạch QLoRA trên máy này vẫn bị chặn
(PA-11/PA-12).

Kiểm tra mục 1 phát hiện thêm một khoảng trống thật ở **bộ sinh**: luật `len(covered) < min(2, len(frags))`
cho phép dòng tổng hợp chỉ khớp nguồn + câu vàng đi qua dù **thiếu thực thể vàng** — trái câu chữ mục 1.
Sửa bộ sinh sẽ đổi tập dữ liệu đã công bố và số đếm của artifact ⇒ ghi **PA-28** (3 phương án, kèm bằng
chứng và cách hoàn tác), không tự sửa. Test ghim **cả hai nửa**: hành vi hiện tại của bộ sinh và việc
checker báo đỏ `{"entity": 1}` — để khi PA-28 được duyệt, test đỏ lên và buộc cập nhật có chủ đích.

Mục 8 ghi số thật (p50 2,900 s, p95 4,421 s, VRAM đỉnh 1.401 MiB trên 20 câu) nhưng test **không** đặt
ngưỡng cứng — máy khác/model khác sẽ ra số khác; ngưỡng cứng sẽ biến phép đo thành test giả. Mục 9 chứng
minh **cơ chế** nạp LoRA (khác đầu ra + nạp hỏng ném lỗi), nhưng adapter hiện có train trên dữ liệu QA mã
nguồn, **không** phải T4b, nên **không** được dùng để nói T4b tốt hay xấu; điều này ghi rõ trong báo cáo.

## Cách kiểm sổ này

Mọi đường dẫn ở cột "Nguồn" phải tồn tại; nếu một file bị xoá/di chuyển thì dòng tương ứng mất hiệu lực
và phải ghi lại. Kiểm nhanh:

```bash
PYTHONIOENCODING=utf-8 venv/Scripts/python.exe - <<'PY'
import re, pathlib
bad = []
for line in pathlib.Path("docs/DECISION_LOG.md").read_text(encoding="utf-8").splitlines():
    if line.startswith("| D-") or line.strip().startswith("`"):
        for p in re.findall(r"`([^`]+\.(?:json|jsonl|md|txt|py))`", line):
            if not pathlib.Path(p).exists():
                bad.append((line[:40], p))
print("THIẾU:", bad if bad else "không")
PY
```
