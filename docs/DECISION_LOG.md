# SỔ QUYẾT ĐỊNH (DECISION_LOG)

Mỗi dòng là **một quyết định đã ra**, kèm giả thuyết đã đăng ký trước, số đo dùng để quyết, **file nguồn
trên đĩa**, và trạng thái. Quy ước trạng thái:

| Trạng thái | Nghĩa |
|---|---|
| **GIỮ** | Quyết định đang có hiệu lực (code/cấu hình/tài liệu đang ở trạng thái này). |
| **BÁC** | Giả thuyết bị số đo bác; lever/giả thuyết không dùng nữa. |
| **CHỜ DUYỆT** | Đã có số + diff, nhưng việc áp dụng thuộc quyền user (xem `docs/archive/PENDING_APPROVAL.md`). |
| **MỞ** | Chưa kết luận được vì thiếu dữ liệu/điều kiện; điều kiện đóng ghi kèm. |

**Hai thang nhãn khác nhau, đừng đọc lẫn nhau** (quy ước 28-10): cột "Trạng thái" ở đây là **quyết định vận
hành** (có bật lever không, có chờ ai duyệt không). Nhãn **khoa học** của phép đo nằm ở
[EXPERIMENTS.md](EXPERIMENTS.md) và chỉ dùng 4 giá trị: `ĐẠT` / `BÁC (CI loại trừ hiệu ứng)` /
`KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ` / `KHÔNG KẾT LUẬN`. Một dòng có thể vừa "GIỮ lever" vừa "KHÔNG KẾT LUẬN" về số
(ví dụ D-05), hoặc vừa "MỞ" về quyết định vừa "ĐẠT" về phép đo (ví dụ D-37). Từ 28-10, các dòng bị dán
nhãn `BÁC` quá tay so với số đo đã được ghi lại kèm nhãn khoa học trong cùng ô "Số đo quyết định".

Nguyên tắc bất biến đứng trên mọi dòng: **ngưỡng đã đăng ký trước thì không chỉnh sau khi thấy số**;
**không chấm lại round đã đóng** trừ khi chính trọng tài đổi (khi đó phải chấm lại *tất cả*);
**trọng tài chỉ được sửa qua đề xuất**; số âm được ghi nguyên, không thêm lever để cứu số.

---

## Bảng tổng

| ID | Ngày | Giả thuyết (một dòng) | Số đo quyết định | Nguồn | Trạng thái |
|---|---|---|---|---|---|
| D-01 | 23-10 | Bộ lọc nguồn **cứng** là kẻ phá recall số 1; thay bằng lọc **mềm** + bonus sẽ kéo gold@6 lên | Lọc cứng gây hại: gold@6 **363→536/700** (0,5186→0,7657), `FAIL_RETRIEVAL` 337→164, bị cắt 244→**0**; ghép cặp r0↔all-off 182 item chỉ all-off lấy được / 9 item chỉ r0, McNemar p=5,16e−43. **Nhưng r1 thực chất là all-off** (V2, 27-10: 700/700 verdict trùng all-off, 0/811 dòng có nhãn classifier, 0,18 s/item) ⇒ mức tăng chứng minh **bỏ lọc cứng**, không chứng minh lọc mềm. Lọc mềm (r11) so all-off: 518 vs 536 = **−18 item**, Δ −0,0257, CI cụm [−0,0462; −0,0069], p=2,77e−4; neo HUMAN 79 vs 75 (+4/97, CI [−0,0132; +0,0787] chứa 0); median r0 2,76 s vs r1 0,18 s (**r11 là 2,78 s**, bản in trước ghi nhầm 2,76). **Nhãn khoa học 28-10:** nửa "bỏ lọc cứng" = **ĐẠT**, nửa "lọc mềm" = **BÁC (CI loại trừ hiệu ứng)** | `tmp/v2_rescore.json`, `tmp/v2_extra.json`, `tmp/alloff_811.json`, `data/loop/rounds/r1/round_summary_retrieval.json` | **BÁC** giả thuyết "lọc mềm kéo gold@6 lên"; kết luận "lọc cứng gây hại" GIỮ. Lever mặc định TẮT (`src/retrieval/router.py:220`) |
| D-02 | 23-10 | Hạn ngạch nguồn 4 ô/cửa sổ sửa được lỗi "một nguồn chiếm cả cửa sổ" | gold@6 **518→520/700** (0,7400→0,7429, +2 item); neo HUMAN **79→79/97** (0,8144 không đổi); 2 cổng ĐẠT nhưng gold **không hồi phục**. Hai bên cùng bật lọc mềm nên phép thử vẫn hợp lệ **trong nội bộ router**; cả hai đều thấp hơn all-off (536/700). **Nhãn khoa học 28-10 = KHÔNG KẾT LUẬN**: artifact không lưu CI cho Δ, và \|Δ\| = 2 item nhỏ hơn băng nhiễu 11 item (T0) — bản in trước ghi "**BÁC** (giả thuyết cấu trúc sai)" là kết luận vượt quá số đo | `data/loop/rounds/r4/round_summary_retrieval.json`, `data/loop/rounds/r4/gate_vs_r2_retrieval.json`, `tmp/v2_rescore.json` | **MỞ** — lever giữ TẮT, không đo lại cho tới khi có CI cho Δ; "lọc cứng gây hại" đã xử lý ở D-01 |
| D-03 | 23-10 | Rescue (gửi lại prompt khi guard bắt) cứu được câu sai | 60 lượt thử / 64 ca đủ điều kiện, **cứu được 1** = **0,0167** theo lượt thử (0,0156 theo ca đủ điều kiện); r5b lặp lại nguyên văn cấu hình và cho cùng con số. Quy tắc đăng ký trước (P5.15): điều kiện (1) phủ lượt thử **ĐẠT** (60/64 = 0,94), điều kiện (2) `PASS_REFUSAL` ≥ 19 **HỎNG ở cả hai lượt** (17 < 19). **Nhãn khoa học 28-10 = KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ** | `data/loop/rounds/r5b/rescue_tally.txt` (đếm nguyên văn 60 dòng `[AnswerRescue]`), `data/loop/rounds/r5b/gate_vs_r5_full.json`, `data/loop/rounds/r5/round_summary_full.json`, `ROADMAP.md` P5.15c | **BÁC vĩnh viễn** (theo đúng quy tắc đã đăng ký trước) |
| D-04 | 24-10 | Bộ chuẩn hóa làm mất dấu/đổi nghĩa câu hỏi; guard phát hiện sẽ lấy lại chunk vàng | Tally r6 ghi **4 ca `False→True` + 1 ca `True→True`**; sau can thiệp **5/5** ca có chunk vàng trong ngữ cảnh (bản in trước gộp thành "5/5 ca bị bác lấy lại vàng" — đúng ở vế kết quả, không đúng ở vế tally). `PASS_CORRECT` v1 10→**14**, chấm lại v2 10→**13**; gold@6 0,6875→**0,7875** (80 câu có gold); refusal 0,72→0,64; cổng chỉ vướng **trần refusal tuyệt đối 0,35**. Artifact không lưu CI cho Δ. **Nhãn khoa học 28-10 = ĐẠT (cơ chế cục bộ)** | `data/loop/rounds/r6/normalizer_guard_tally.txt`, `data/loop/rounds/r6/round_summary_full.json`, `data/loop/rounds_v2/r6/round_summary_full.json`, `data/loop/rounds/r6/gate_vs_r5b_full.json` | GIỮ lever; bật mặc định = **CHỜ DUYỆT** (#23) |
| D-05 | 24-10 | Cộng bonus 12 + guard sẽ cộng hưởng | `PASS_CORRECT` v1 **14→14**, chấm lại v2 **13→13** (Δ = 0, nằm trong băng nhiễu ±3 của T0); 2 ca `PASS_CORRECT` → từ chối oan. Không artifact nào lưu CI cho Δ, và "cộng hưởng" chưa có ngưỡng đăng ký. **Nhãn khoa học 28-10 = KHÔNG KẾT LUẬN** — bản in trước ghi "**BÁC** tổ hợp" là kết luận vượt quá số đo | `data/loop/rounds/r7/combo_tally.txt`, `data/loop/rounds/r7/gate_vs_r6_full.json`, `data/loop/rounds_v2/r7/round_summary_full.json` | **MỞ** — tổ hợp không bật; guard đơn lẻ vẫn GIỮ (D-04); không đo bonus bằng round tổ hợp nữa |
| D-06 | 24→28-10 | "Bonus 12 làm mất 2,57 điểm so với bonus 3" là do chỉnh sai hằng số — và cặp so sánh thật nằm sau con số đó là gì | Ghép cặp 811 item trên cặp r1↔r2: Δ **−0,0257** (= −18/700), CI [−0,04; −0,0129], p = 0,00028; bootstrap theo cụm nguồn (V2) cho cùng hiệu số: CI [−0,0462; −0,0069], p = 2,77e−4; 21 mất / 3 được và **21/21** chunk vàng rơi hạng **7–12**; EXACT/TRAP **bất biến**. **Đính chính 28-10 theo V2: r1 không chạy router (0/811 dòng nhãn classifier, 700/700 verdict trùng all-off) ⇒ cặp đã đo là "lọc mềm kèm bonus 12" vs "không lọc", KHÔNG phải "bonus 3 vs bonus 12".** Hệ quả hai nhãn: (i) giả thuyết lọc mềm = **BÁC (CI loại trừ hiệu ứng)**; (ii) hằng số bonus **chưa từng được cô lập** trong một phép thử một-biến ⇒ về "bonus có phải nút thắt" chỉ đạt **KHÔNG KẾT LUẬN**; bản in trước quy hết −0,0257 cho hằng số là dán nhầm nguyên nhân | `data/loop/diag/bonus_paired_r1_r2.json`, `data/loop/diag/bonus_paired.json`, `tmp/v2_rescore.json`, `tmp/v2_extra.json`, `tmp/alloff_811.json` | **BÁC** nửa "lọc mềm giúp gold@6"; **MỞ** cho hằng số bonus (chưa có cặp một-biến `ROUTER_FILTER_RANK_BONUS`) |
| D-07 | 24-10 | Bỏ đường từ chối khỏi prompt + 5 luật ngoài sẽ tăng câu đúng mà không tăng bịa | Ngưỡng đăng ký trước (`data/loop/README.md` mục T3): **≥25/100 `PASS_CORRECT` và không tăng bịa**. Đo: `PASS_CORRECT` v1 14→**19**, chấm lại v2 13→**19** (cả hai < 25); refusal 0,69→**0,28**, fabrication 0,0323→0; nhưng `PASS_REFUSAL` **17→2** và `FAIL_HALLUCINATED_ON_UNANSWERABLE` **2→12**, p95 19,93 s; cổng 5 vi phạm. CI riêng mức `PASS_CORRECT` r8 (v1) [0,12; 0,27] — không phải CI của Δ. **Nhãn khoa học 28-10 = KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ** (vế "không tăng bịa" thì hỏng hẳn) | `data/loop/rounds/r8/round_summary_full.json`, `data/loop/rounds_v2/r8/round_summary_full.json`, `data/loop/rounds/r8/gate_vs_r5_full.json`, `docs/archive/reports/T3.md` | **BÁC** — cờ `ENABLE_DECOUPLED_REFUSAL` TẮT |
| D-08 | 24-10 | Cửa sổ sinh 3–5 câu bằng chứng (thay ~7k ký tự) giúp model 1,5B trả lời đúng hơn | Ngưỡng đăng ký trước: **≥25/100 `PASS_CORRECT`**. Đo: 75/75 cửa sổ đúng 5 câu (6.898→1.022 ký tự); `PASS_CORRECT` v1 và v2 đều **19→19** trên **cùng 100 ID** (bản in trước ghi "tập câu khác" là sai, đã đính chính 28-10); `model_still_refuses` **3→32**; refusal 0,28→**0,57**; p95 19,93→**33,27 s (+67%)**. **Nhãn khoa học 28-10 = KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ** (Δ = 0, không CI cho Δ) | `data/loop/rounds/r9/attribution_vs_r8.txt`, `data/loop/rounds/r9/round_summary_full.json`, `data/loop/rounds_v2/r9/round_summary_full.json`, `docs/archive/reports/T3.md` | **BÁC** — cờ `ENABLE_EVIDENCE_SELECTION` TẮT |
| D-09 | 24-10 | Nâng model sinh 1,5B → 3B (cùng máy, cùng prompt) sẽ vượt 22/100 câu đúng | Ngưỡng đăng ký trước: **≥22/100** (`data/loop/README.md` mục T4). Đo: `PASS_CORRECT` v1 14→**16**, chấm lại v2 13→**14**; Δ **+0,0203** CI **[−0,06; +0,10]** — CI chứa cả 0 lẫn mức đăng ký; McNemar **p = 0,804**; p95 18,65→**34,12 s (+83%)**; một-biến 100/100 item trùng đầu vào. **Nhãn khoa học 28-10 = KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ, không phải BÁC** (số đo không loại được hiệu ứng dương; chỉ là chưa đủ để đạt ngưỡng) | `data/loop/rounds/r10/round_summary_full.json`, `data/loop/rounds_v2/r10/round_summary_full.json`, `data/loop/rounds/r10/t4_stats.json`, `data/loop/diag/one_variable_check.json`, `docs/archive/reports/T4.md` | GIỮ `qwen2.5:1.5b-instruct` (quyết định vận hành); **MỞ** về năng lực 3B — cần n lớn hơn 100 câu để phân cách CI |
| D-10 | 24→26-10 | Có thể SFT trên máy 4 GB với dữ liệu hiện tại | Trần VRAM **suy từ peak** ở lượt đo cũ: 960 token → 3.931,0 MiB; 1.024 → 4.156,9 MiB, trong khi card khai báo 4.095,5 MiB; **13/13** dòng train ≥1.016 token; gradient checkpointing không giảm đáng kể. **Đính chính 26-10 (D-39):** máy này chạy WDDM oversubscribe — peak lớn hơn VRAM khai báo **không phải bằng chứng OOM** (card 4 GB nhận và ghi đủ 8 GiB, chỉ chậm ×4,25). Lượt train thật ngày 23-10 dừng ở step 24 nhưng **mất artifact** ⇒ kết luận "không train nổi" hạ xuống **chưa kiểm chứng**. **Nhãn khoa học 28-10 = KHÔNG KẾT LUẬN** | `data/loop/diag/t4b_memory_probe.json`, `data/loop/diag/t4b_memory_probe_len.json`, `data/loop/diag/b5_wddm_oversubscription.json`, `data/training/t4b_r5r8r9r10/manifest.json` | **MỞ** — PA-11 (4-bit) / PA-12 (đổi định dạng) **không còn là hai đường duy nhất**; câu hỏi train thật = PA-39 |
| D-11 | 25-10 | Reranker cross-encoder (pool 20 → top-6) nâng gold@6 — **bản build cũ, query đã `fold`** | gold@6 0,7400→**0,6686** (518→468/700), Δ **−0,0714 CI [−0,1014; −0,0414]** (CI đã ở đơn vị phân số gold@6), McNemar 83/33 **p=3,87e−06**. Probe **30 cặp** item hỏng: **0/30** sống với `fold(query)`, **28/30** sống với query nguyên văn ⇒ lỗi build, không phải lỗi ý tưởng. **Nhãn khoa học 28-10 = BÁC (CI loại trừ hiệu ứng) cho bản build**; bản đã sửa (PA-25) xem D-37 | `data/loop/diag/reranker_paired_r11_r12.json`, `tmp/probe_r12_fold.json`, `docs/archive/reports/T5.md` §2.7 | **MỞ** — cờ TẮT; sửa + đo lại = PA-25 (đã áp → D-37) |
| D-12 | 25-10 | Gắn header Chương/Điều/Khoản vào chunk giúp truy xuất (corpus cũ) | gold@6 0,7400→0,7371, Δ **−0,0029 (= −2/700) CI [−0,0129; +0,0071]**, McNemar p=0,79; \|Δ\| = 2 item nhỏ hơn băng nhiễu 11 item. **Nhãn khoa học 28-10 = KHÔNG KẾT LUẬN**: CI chứa 0 và không có ngưỡng hiệu ứng dương đăng ký trước — bản in trước ghi "**BÁC** trên corpus cũ" là kết luận vượt quá số đo. ĐÍNH CHÍNH 25-10: bản in trước ghi −0,0028 (cắt số), giá trị đúng là −0,0029 | `data/loop/diag/header_paired_r11_r13.json`, `data/loop/rounds/r13/gate_vs_r11_retrieval.json` | **MỞ** — header không bật; corpus T2 = PA-21; chưa đo lại trên corpus mới |
| D-13 | 24→28-10 | Nút thắt dấu tiếng Việt nằm ở pipeline convert PDF; OCR lại bằng EasyOCR `vi` sẽ sửa được | Tỉ lệ **từ còn dấu** (proxy): corpus 0,0328 (1.420/43.327) → trang đã OCR 0,8226 (34.705/42.188); index cũ 0,1913 → index mới **0,8029**; chunk 361→**342**; chunk <5% dấu 167→**2**. **Đính chính 28-10 về số trang: lượt chạy OCR 123 trang mới + 1 trang đã cache = 124 trang** lưu trong `.ocr_cache_vie/` (13 tệp) — các bản in trước chỉ nói "123 trang" là số của riêng lượt chạy. Chưa kiểm chứng: độ chính xác ký tự OCR (không có bộ nhãn đối chiếu) và chất lượng trả lời trên index mới (xem Q5, D-40) | `data/loop/diag/corpus_diagnostics/quality_vie.json`, `data/loop/diag/corpus_diagnostics/index_before.json`, `data/loop/diag/corpus_diagnostics/index_after.json`, `tmp/reocr_vie.log`, `docs/archive/reports/T2.md` | GIỮ artifact `chroma_db_vie/`; **kích hoạt = CHỜ DUYỆT** (PA-1, PA-17) |
| D-14 | 24→28-10 | Năng lực Gemini là nút thắt của cấu hình (b) | 25/30 id hợp lệ: `PASS_CORRECT` **16/25 = 0,64**, CI bootstrap [0,44; 0,84]; refusal **3/25 = 0,12**; bịa **5/22** trong số câu đã trả lời. Chọn mẫu **không** theo hàng đợi: pool **33** ca = `FAIL_OVERREFUSAL` ∩ có chunk vàng trong ngữ cảnh ở r5, phân tầng theo `family` (CLOZE 9 / CLOZE_OCR 13 / YESNO_FACT 5 / NUMERIC 2 / SOURCE_LOOKUP 2 / EXACT 1 / REVERSE_LEGAL 1), seed 20261023, đăng ký trước khi gọi. **5 id thiếu đúng là 5 id cuối theo thứ tự r5** vì trần PerDay, không phải vì ca khó hơn ⇒ chưa được suy ra rằng phần thiếu là "khó". **Nhãn khoa học 28-10 = KHÔNG KẾT LUẬN** (thiếu 5 id và chưa có baseline cùng mẫu; 0,64 trên 25 ca khó không so được với 0,14 trên 100 câu của Qwen) | `data/loop/diag/b_gemini_top6/summary_dedup_25.json`, `data/loop/diag/b_gemini_top6/bootstrap_ci_25.json`, `data/loop/diag/b_gemini_top6/id_status.json`, `data/loop/diag/b_gemini_top6/sample_ids.json`, `data/loop/diag/b_gemini_top6/settings.json` | **MỞ** — cần đủ 30/30 (PerDay reset ~14:00 VN) và cặp so sánh cùng mẫu |
| D-15 | 24-10 | Cổng `refusal_rate_bounded` dùng trần tuyệt đối 0,35 đang veto oan | Đề xuất cổng **tương đối** (candidate ≤ baseline + 0,05); 0,35 thành **cảnh báo không phủ quyết**; 8 test trên bản tạm | `tools/diag/gate_refusal_relative_proposal.py`, `tests/test_gate_refusal_relative_proposal.py`, `docs/archive/PENDING_APPROVAL.md` PA-13 | **CHỜ DUYỆT** — `tools/loop/gate.py` **không** đổi |
| D-16 | 24-10 | Tổng điểm trọng số trong báo cáo đánh giá đang sai số học | 0,20·9,2+0,15·8,2+0,20·7,0+0,20·8,5+0,25·4,0 = **7,17 → 7,2** (bản cũ ghi 7,4) | `docs/bao_cao/danh_gia_tong_quan_2026-10-23.md`, `data/loop/diag/metric_ci_r5_full.json`, `data/loop/diag/metric_ci_r7_full.json` | GIỮ 7,2; điểm thành phần = **CHỜ DUYỆT** (PA-23) |
| D-17 | 23→25-10 | Có thể sửa trọng tài/gate giữa chuỗi round mà không phải chấm lại | Chữ ký trọng tài **`9f1179ccab74`** ở mọi round r0…r13 ⇒ không round nào phải chấm lại | `tools/loop/verify.py`, `data/loop/rounds/r10/round_summary_full.json` (`settings`), `data/loop/README.md` mục "Bảy bất biến" | GIỮ (bất biến) |
| D-18 | 23→25-10 | Số test "563 xanh" là mốc chuẩn để so | Sau T2/T3/T5/header: **967 passed** (62,53 s, 25-10 04:1x); sau T7 (`run_chain` + `cache_policy`): **1.004 passed**; sau test biên T6a: **1.005 passed**; sau test T0 "CI chứa ước lượng điểm giải tích": **1.006 passed** (32,54 s, 25-10 11:51); sau 5 test T1 (isol + guard tập item): **1.011 passed** (29,79 s, 25-10 11:55); sau 3 test T2 (nguyên văn qua `build_chunks`): **1.014 passed** (30,77 s, 25-10); sau 2 test T3 A1' (TẮT khi env còn ngưỡng lever TẮT): **1.016 passed** (29,29 s, 25-10 12:1x) | `tmp/pytest_t5_final.txt`, `tmp/pytest_t4t6_final.txt`, `tmp/pytest_t0_final.txt`, `tmp/pytest_t1_final.txt`, `tests/`, `docs/archive/STATE.md` | GIỮ 967 là mốc lịch sử; **1.016** là mốc hiện tại (D-21/D-24) |
| D-19 | 25-10 | Reranker chỉ khả thi nếu chạy trên GPU, mà không được phá `venv/`/`venv_train/` | `venv_gpu/` riêng (torch 2.14.1+cu126): pytest **967 passed**, VRAM 3.594/4.096 MiB, rerank 2,05 s/item | `data/loop/diag/reranker_cost_gpu.json`, `docs/archive/AUTONOMY_LOG.md` 25-10 02:20 | GIỮ (môi trường tách biệt) |
| D-20 | 25-10 | Ngoại suy chi phí round = chi phí riêng tầng rerank | **Sai**: r12 thật **≈66 phút cho 811 item** (median 4,74 s/item, p95 5,09 s) = ~2,0 s rerank **+ 2,78 s truy xuất nền** ⇒ vượt ngưỡng tự đặt 60 phút. Nhãn khoa học 28-10 = **BÁC (phương pháp)** — lỗi nằm ở phép ngoại suy, không phải một hiệu ứng âm | `data/loop/rounds/r12/round_summary_retrieval.json`, `tmp/vram_r12_run.log`, `docs/archive/reports/T5.md` §2.6 | **BÁC** phương pháp; thay bằng `rerank + baseline` |
| D-21 | 25-10 | Cache sinh chỉ băm `{model, temperature, prompt_version, prompt}` ⇒ đổi ngưỡng cứu/từ chối vẫn trúng câu trả lời của thể chế cũ | Thêm `policy` **chỉ khi** thể chế lệch mốc `DEFAULT_CACHE_TOKEN` (**d0b4c6a65f83**); thể chế mặc định giữ khóa cũ từng byte. 26 test mới, mutation **10/10** bắt | `src/core/cache_policy.py`, `src/generator.py` (2 hàm `_cache_key`), `tests/test_cache_policy.py`, `tmp/mutation_check_cache_policy.py` | GIỮ trong working tree; **CHỜ DUYỆT commit** (PA-26) |
| D-22 | 25-10 | Driver `.sh` viết tay trong `tmp/` là đủ để tái lập một round | Không: thiếu log là mất danh sách env; thay bằng spec JSON + manifest tất định. **Phạm vi bằng chứng (đính chính 28-10):** lượt demo có cổng là **`tmp/chain_demo3`** — spec `tools/loop/chains/demo_dryrun.json`, bước `demo_a` `limit = 20`, bước `demo_b` pin từ `demo_a`; cổng so trên **20 item chung → ĐẠT**, attribute chạy được, manifest `--dry-run` = manifest lượt chạy, `spec_sha256` **4051b9651470**. `round_summary` của `demo_b` ghi `n_scored = 605` vì lượt demo quét full split — **con số cổng là 20 item chung, không phải 605**; `tmp/chain_demo` (lượt 3 item) chỉ là demo in manifest. 11 test, mutation **6/6** bắt. Nhãn khoa học 28-10 = **ĐẠT** cho tiêu chí "một lệnh tái lập được chuỗi, có manifest đối chiếu được" | `tools/loop/run_chain.py`, `tools/loop/chains/demo_dryrun.json`, `tools/loop/chains/t5a_reranker.json`, `tests/test_run_chain.py`, `tmp/chain_demo_manifest.json`, `tmp/chain_demo3/demo_b/gate_vs_demo_a_retrieval.json`, `tmp/mutation_check_t7.log` | GIỮ — **đã commit** `79a02e5` |
| D-23 | 25-10 | HEAD tài liệu tái lập được cây đã test 1.016 test | **Sai**: còn 35 file nguồn/công cụ/test chưa tracked (gồm `tools/loop/noise_floor.py`, `src/answer_guard.py`, `src/core/cache_policy.py`) + 6 file sửa dở; bản `src/generator.py` trong HEAD không có `effective_prompt_version` | `docs/archive/PENDING_APPROVAL.md` PA-26, `docs/archive/STATE.md` | **MỞ** — chờ chọn phương án commit freeze |
| D-24 | 25-10 | Có thể sửa `cache_policy.py` để khóa TẮT không phụ thuộc env của lever TẮT ngay trong phiên kiểm thử T3 | Phát hiện **đúng** (cả hai cờ T3 TẮT: deviation `None` → `e95e6efa2617`/`1670eb7035ac`/`94515a7efa5d`, đầu ra 30 item byte-identical), nhưng sửa là chạm khóa cache T7 + buộc đổi 3 test đã có ⇒ ghi **PA-27**, không sửa; chỉ thêm 2 test ghim cả hai nửa (đầu ra bất biến / khóa tách là hiện trạng) | `tests/test_t3_guardrails.py`, `docs/archive/reports/test_T3.md` §9, `docs/archive/PENDING_APPROVAL.md` PA-27 | **CHỜ DUYỆT** — PA-27 |
| D-25 | 25-10 | Pipeline SFT + generator T4 thỏa đủ 9 mục đặc tả (bất biến dữ liệu, giao diện chung, cache, số đo GPU) | Mục 1–4 **XANH** trên artifact thật (13 train / 10 holdout / 58 item test); **mục 5 ĐỎ do DỮ LIỆU** (13/13 dòng train + 8/10 holdout > 768 token, min 1.016); mục 8: p50 **2,900 s** / p95 **4,421 s** / VRAM đỉnh **1.401 MiB**; mục 9: adapter khác base + nạp hỏng ném `ValueError`; mutation **8/8** | `tmp/t4_invariants_report.json`, `data/loop/diag/t4_latency_20q.json`, `data/loop/diag/t4_adapter_probe.json`, `tmp/mutation_check_t4_new.log`, `docs/archive/reports/test_T4.md` §10 | GIỮ bộ test; mục 5 ĐỎ = **PA-28**; adapter chỉ chứng minh cơ chế |
| D-26 | 25-10 | "Chỉ pha sinh r5 đổi từ KHÔNG ĐẠT sang ĐẠT theo luật refusal tương đối" (đề bài T6) | Kiểm trên file cổng đã công bố: **r5-vs-r3 vẫn KHÔNG ĐẠT** (refusal 0,61→0,69 = +0,08 > 0,05; fabrication 0,0256→0,0323); ca lật duy nhất **r5-vs-r1** (0,69 vs 0,72 ⇒ ĐẠT + cảnh báo trần 0,35); r3-vs-r1 vẫn đỏ vì hallucinated 2→3; r4-vs-r2 retrieval y nguyên ĐẠT (811 item, gold 0,7400→0,7429) | `data/loop/rounds/r5/gate_vs_r3_full.json`, `data/loop/rounds/r5/gate_vs_r1_full.json`, `data/loop/rounds/r3/gate_vs_r1_full.json`, `data/loop/rounds/r4/gate_vs_r2_retrieval.json`, `docs/archive/reports/test_T6.md` §8.2 | **ĐÍNH CHÍNH đề bài**; 60 test + mutation 10/10; PA-13 vẫn **CHỜ DUYỆT**, `gate.py` không đổi |
| D-27 | 25-10 | Đặt tên artifact mới theo kiểu "ghi đè là bình thường trong `tmp/`" có chấp nhận được không | **Không**: harness 20 đột biến mang tên `tmp/mutation_check_t7.py` đã xoá bằng chứng 6/6 mà D-22 dẫn (lần **thứ 2** lặp lỗi T6). Khôi phục: `unified_diff` giữa bản trích từ transcript và snapshot `Read` = **0** khác biệt, **chạy lại harness khôi phục được 6/6 (rc=0)**, SHA-256 3 file nguồn đợt 1 vẫn trùng (`bf13918a…`/`652477e3…`/`d3791b44…`) ⇒ log 6/6 còn áp dụng cho code hiện tại; harness mới đổi thành `tmp/mutation_check_t7_dot2.py` (log **20/20**) | `tmp/mutation_check_t7.py`, `tmp/mutation_check_t7.log`, `tmp/mutation_check_t7_rerun_dot2.log`, `tmp/mutation_check_t7_dot2.py`, `tmp/mutation_check_t7_dot2.log`, `docs/archive/AUTONOMY_LOG.md` (Ngã rẽ 1), `docs/archive/reports/test_T7.md` §8.5 | **GIỮ** thủ tục khôi phục; mất 1 snapshot kiểm kê (`tmp/cleanup_report_t7.json` 104→164 mục) — số PA-24 vẫn là ảnh chụp có ngày giờ |
| D-28 | 25-10 | "Bộ test T7 đợt 2 chứng minh mọi lớp phòng vệ của `tmp_cleanup`" — và "mọi con số đợt 1 đã ghi là đúng" | Lượt đầu **18/20** (M12, M14 **lọt**) vì `check_target()` có 3 lớp **dư thừa**: bỏ 1 lớp thì lớp khác vẫn chặn ⇒ test không cô lập được lớp nào. Thêm **2 test junction thật** (`mklink /J`, `is_symlink()`=False) để tách lớp a và lớp c ⇒ **20/20, 0 lọt**, hoàn nguyên byte-identical. Đồng thời phát hiện **1 lỗi số đã công bố**: §2.3/§3 ghi "17/17" đột biến, tổng thật là 6+10 = **16** | `tmp/mutation_check_t7_dot2.log`, `tools/diag/tmp_cleanup.py`, `tests/test_t7_tmp_cleanup.py`, `docs/archive/reports/test_T7.md` §2.3 + §8.3 | **GIỮ** 3 lớp chặn (không nới checker); **ĐÍNH CHÍNH** 17/17 → 16/16 + 20/20 |
| D-29 | 25-10 | Mục 6 đề bài ("mọi lệnh README chạy được ở `--help`/dry-run") có thể chứng minh **hết** bằng checker tự động không | **Không hết**: 264 lệnh được phân loại, 9 script repo, chỉ **4** có argparse ⇒ chạy `--help` thật (rc=0 cả 4); **5** script (`ingest.py`, `learn.py`, `src/assessment/analyze_ab.py`, `demo_streamlit.py`, `ui/app.py`) không argparse ⇒ chỉ CẢNH BÁO, không tính là ĐẠT; **100** đường dẫn README/ROADMAP/docs tồn tại, **0 lỗi**; 2 đường dẫn GUI tự sinh được allowlist + in ghi chú. Rủi ro thật tìm thấy khi đọc `ingest.py`: `shutil.rmtree(persist_dir)` mặc định `./chroma_db` — lệnh README §5.1 **xoá index sản xuất**, không dry-run, không xác nhận | `tools/diag/docs_consistency_check.py`, `tmp/docs_check_t7_dot2.json`, `tests/test_t7_docs_consistency.py`, `ingest.py`, `README.md` | **CHỜ DUYỆT** — PA-29; checker giữ phân loại LỖI/CẢNH BÁO, không làm giả ĐẠT |
| D-30 | 25-10 | Tiêu chí "người ngoài tái lập được **round retrieval-only r0 với cùng số gold@6**" chỉ đạt ở mức tính lại artifact, hay đạt ở mức **chạy thật một lệnh**? | Đạt ở mức chạy thật: `tools/loop/chains/t7_repro_r0.json` (ghim 13 biến env đúng thể chế r0) → 811/811 item, **gold@6 0,5186 = 0,5186**, **0 verdict đổi chiều**, **811/811 top-6 giống hệt theo thứ tự**, 37,5 phút, **0 lượt Gemini**; manifest `--dry-run` và manifest lượt chạy **byte-identical** (SHA `295413c196de…`). Hai chỗ phải đính chính khi viết §8.4: (i) "1 item lệch" ở demo ĐỢT 1 là **khác thể chế** (`ENABLE_CLASSIFIER=0`) chứ không phải nhiễu; (ii) median r0 tự đo là **2,76 s/item**, số 2,78 đã dẫn là của **r11** | `data/loop/rounds/r0/round_summary_retrieval.json`, `tmp/rounds_t7_repro/r0_repro/round_summary_retrieval.json`, `tmp/compare_r0_repro.json`, `tmp/compare_r0_repro.py`, `data/loop/diag/chain_manifest_t7_repro_r0.json`, `tmp/t7_manifest_probe_dot2.json`, `docs/archive/reports/test_T7.md` §8.4 + Phụ lục A2 | **GIỮ** kết luận (tiêu chí đạt ở mức artifact + một lệnh thật); **CHỜ DUYỆT** mức "fresh clone" — PA-26 + PA-29 |
| D-31 | 25-10 | Kiểm toán "mọi số công bố của T0–T7 tính lại được" (đề bài tổng kiểm tra, mục 2) có tìm ra số sai không — và sai thì sử lý thế nào | Có **1 số sai thật** trong **55** dòng kiểm toán: r13 (header) công bố delta gold **−0,0028** ở 5 tài liệu, nhưng chính artifact `data/loop/diag/header_paired_r11_r13.json` ghi `gold_delta = −0,0029` (= −2/700 = −0,002857, làm tròn 4 chữ số). Không artifact nào chứa −0,0028 ⇒ đây là **cắt số** chứ không phải con số từ phép đo khác. Cách xử lý bảo thủ: **sửa tài liệu theo artifact**, không sửa artifact, không hạ CI/p (CI [−0,0129; +0,0071], p=0,79 giữ nguyên); ghi ĐÍNH CHÍNH ngay trong D-12 để lần đọc sau không phải suy ra. 54 dòng còn lại khớp; công cụ kiểm toán là script **chỉ-đọc** (`tools/diag/final_number_audit.py`), kết quả lưu `tmp/final_number_audit.json` + bảng `tmp/final_number_audit_table.md` | `tools/diag/final_number_audit.py`, `tmp/final_number_audit.json`, `tmp/final_number_audit_table.md`, `data/loop/diag/header_paired_r11_r13.json`, `docs/archive/reports/T5.md`, `docs/DECISION_LOG.md` D-12, `docs/archive/MORNING_REPORT.md`, `docs/archive/STATE.md`, `docs/archive/AUTONOMY_LOG.md` | **ĐÃ SỬA** 5 tài liệu (không đổi số đo); **GIỮ** nguyên tắc "artifact là nguồn, tài liệu phải theo"; kiểm lại bằng `python tools/diag/final_number_audit.py` ⇒ `0 dòng LỆCH` |
| D-32 | 25-10 | Ba câu hỏi hội đồng ("có bịa không", "trọng tài có đáng tin không", "gold@6 = 0,5186 nghĩa là gì") nên trả lời bằng **một bài viết tay** hay bằng **script tái chạy được**? | Chọn script **chỉ-đọc**, mỗi câu một file, dựng lại số từ artifact đã đóng, in kèm đường dẫn nguồn, có `--json`, và **mã thoát là phán quyết của chính máy kiểm** (0 = mọi dòng đối chiếu khớp; khác chữ ký / có dòng LỆCH ⇒ 1). Số chốt: bịa — 1.000 dòng/10 round, 380 đã trả lời, 7 trái ngữ cảnh = **1 item khác nhau** (`S115028976296200`), 43 ca nặng (FAB 7/CFP 6/HOU 30) = **18 item**, **36/43 ca nặng mù với thước**; trọng tài — **19 round/phase 1 chữ ký**, **1.000/1.000 chấm lại khớp** (1,57 s), env-độc lập, cổng `gate.compatibility` từ chối bản khác, nhưng `n_filled = 0` ⇒ **chưa** có đồng thuận người, 11 verdict đổi chiều ở luật số nghiêm khắc; gold@6 — mẫu số **700/811**, **111 item mù**, r0 363 = 0,5186, **trần pool-12 = 0,8214**, 125 item trượt recall, **không so được giữa hai index** (mất neo 0,4881 ĐỎ). Quyết định đi kèm: **tự công bố điểm mù trong bài**, không chỉ đưa số đẹp | `tools/diag/council_kit.py`, `tools/diag/council_check_fabrication.py`, `tools/diag/council_check_referee.py`, `tools/diag/council_check_gold6.py`, `tmp/council_fabrication.{json,txt}`, `tmp/council_referee.{json,txt}`, `tmp/council_gold6.{json,txt}`, `tests/test_final_council_scripts.py` (43), `docs/archive/reports/test_final.md` §7 | **GIỮ** (ba script chạy exit 0, 0 dòng LỆCH); **CHỜ DUYỆT** mức "fresh clone" vì verify.py/answer_guard.py chưa tracked (PA-26) |
| D-33 | 25-10 | Bản `test_final.md` 13:26 công bố "79/79 đột biến bị bắt" — có giữ con số đó khi tổng kết không? | **Không.** Đếm lại từ 13 log: 5+4+6+9+7+8+13+10+10+6+10+20+18 = **126/126**, 0 dòng "sống sót". Con số cũ vừa thiếu 3 harness chạy sau (T6 bộ mới 10, T7 docs dot2 20, nghiệm thu cuối 18) vừa **tự mâu thuẫn** (dãy cộng ghi ngay trong bảng là 5+4+6+9+7+10+13+10+17 = 81). Cách xử lý: ghi sổ cái từng harness trong `test_final.md` §8 + Phụ lục B, giữ nguyên log cũ, không xoá không sửa. Kèm bài học **răng của test cho máy kiểm**: đột biến K-M1 (`answered_rows` bỏ lọc `PENDING_GENERATION`) sống ở lượt 1 (17/18) vì row D trong bộ test tổng hợp có `answer_chars = 0` ⇒ bị loại bởi lý do khác, không ai thấy mẫu số phình; sửa row D thành `answer_chars = 5` **kèm ghi chú gần-trượt ngay trong test**, chạy lại → 18/18. Không hạ kỳ vọng của test nào. **Cập nhật 28-10:** sổ cái trong `docs/archive/reports/test_final.md` §8 hiện là **14 harness = 135/135** (thêm harness phòng thủ môi trường D-35+D-36 = 9 đột biến); 126/126 và 135/135 là **hai phạm vi đếm khác nhau**, không thay thế nhau — dòng này giữ cả hai vì 126 là con số đã công bố tại 25-10 | `docs/archive/reports/test_final.md` §8 + Phụ lục B, `tmp/mutation_check_final_council.{py,log}`, `tests/test_final_council_scripts.py` (`TestDinhNghiaCuaKit`), 13 log `tmp/mutation_check_*.log` + `tmp/t2_mutation_6.log` + `tmp/t3_mutation_recheck_9.log` | **GIỮ** 126/126 là con số chuẩn; nguyên tắc "tổng đột biến phải đếm từ log, không cộng tay" |
| D-34 | 25-10 | Sau commit `a170e92`, 3 test ghim hiện trạng của `TestHienTrangRepo` **đỏ** vì máy quét secret bắt chính mẫu gieo trong `tests/test_final_secret_scan.py` (4 `SECRET_COTHAT` + 4 `DUONG_DAN_CA_NHAN`, PII 89→93). Sửa máy quét, nới test, hay sửa mẫu? | **Sửa mẫu, giữ nguyên máy quét và kỳ vọng.** Chẩn đoán: đây là **máy kiểm tự nhiễm phạm vi của nó** (`tracked_files()` đọc `git ls-files`, nên file test vừa được commit trở thành đối tượng bị quét), **không phải** repo có credential. Nới máy quét = phá dụng cụ đo; nới test = hạ kỳ vọng để xanh (cấm cả hai). Cách sửa: helper `_ghep()` dựng chuỗi mẫu **tại runtime** ⇒ literal không còn trong source đã commit, còn test vẫn buộc máy quét bắt được chuỗi hoàn chỉnh khi nó được ghi ra `tmp_path` (M1 Google key, M2 PEM, M3 đường dẫn cá nhân, test redact đều giữ nguyên assertion). Sau sửa: `pytest tests/test_final_secret_scan.py -q` = **14 passed**, `secret_scan --scope tracked` = **0 secret / 0 đường dẫn / 89 PII / 8 file** đúng số đã công bố; bảng trước/sau commit lưu `tmp/secret_scan_post_commit.json` (281 file ứng viên / 249 đã đọc / 339 dòng khớp / 250 `BI_MAU`). **Quy trình mới đăng ký**: với máy kiểm có phạm vi lấy từ git, phải chạy lại `--scope tracked` **sau khi stage/commit** — test ghim hiện trạng chính là thứ phát hiện loại nhiễm này, và nó đã làm đúng việc | `tests/test_final_secret_scan.py` (`_ghep`, `TestHienTrangRepo`), `tmp/secret_scan.json`, `tmp/secret_scan_post_commit.json`, `docs/archive/reports/test_final.md` §5 + §11 | **ĐÃ SỬA** (chỉ file test của phiên này); **GIỮ** nguyên tắc "nhiễm phạm vi thì sửa mẫu, không sửa thước" |
| D-35 | 25-10 | Sau `c508876`, chạy nghiệm thu cuối bằng **interpreter khác** (`python` hệ thống — cùng bản 3.14.8 như venv nhưng `include-system-site-packages=false` nên thiếu package) với stdin đóng (`… < /dev/null`) làm **10 test đỏ/ERROR** (`test_final_secret_scan.py` 6 ERROR, `test_final_council_scripts.py` 1 FAILED, `test_final_env_flag_defaults.py` 3 ERROR). Đây là bug logic, bug công cụ đo, hay chỉ là môi trường — và xử lý thế nào cho đúng vai "máy kiểm không được suy diễn"? | **Không phải bug logic và không phải lỗi bộ test: là độ mong manh của công cụ đo.** Chuỗi nhân quả: `subprocess.run([...], capture_output=True)` kế thừa handle stdin của process cha → trên Windows + CPython 3.14 handle đó không duplicate được → `OSError: [WinError 6] The handle is invalid`. `council_kit.git_state()` bắt OSError và trả `khong-co-git` cho **`src/text_utils.py` — một file đã tracked và sạch**, tức công cụ báo "repo không có git" do một lỗi spawn (đúng kiểu sai lầm câu hỏi 2 sinh ra để bắt); lời gọi `git status` thứ hai còn nằm ngoài `try` nên văng exception. Ba lớp xử lý: (i) siết `stdin=subprocess.DEVNULL` cho mọi lời gọi subprocess trong phạm vi nghiệm thu cuối (khuôn `docs_consistency_check.py` đã dùng từ đợt T7) và đưa cả hai lời gọi git vào cùng một `try`; (ii) **không đổi kỳ vọng**: `tracked-sach` / `chua-commit` vẫn là nhãn đúng, chỉ đường sinh ra nó mới sai; (iii) thêm `tests/test_final_subprocess_stdin_guard.py` = **21 test** (đợt D-36 cùng file nâng lên **33**) (AST ghim nguồn, chống-rỗng, ghim số lời gọi mỗi file; `git_state` với `subprocess` giả cho từng nhánh nhãn; ghim hiện trạng PA-26). Đột biến **6/6 bị bắt, 0 lọt** (D-36 thêm 3 → **9/9**) (`tmp/mutation_check_stdin_guard.py`, chạy trên file thật + khôi phục có đối chiếu SHA-256): K1–K4 bỏ `stdin` ở 4 lời gọi, K5 đưa `git status` ra ngoài `try`, K6 biến lỗi spawn thành `tracked-sach` (K6 bị bắt bởi **hai** test). Số sau siết: `pytest tests -q` = **1359 passed / 5 skipped / 126,52 s** (venv), và cùng 5 file nghiệm thu cuối chạy bằng **Python 3.14 + stdin đóng** = **131 passed / 1 skipped**; các số đã công bố **không đổi** — kiểm toán 55 dòng `0 dòng LỆCH`, chữ ký trọng tài `9f1179ccab74`, secret scan `0 secret / 0 đường dẫn / 89 PII / 8 file`, docs checker `35 mục / 264 lệnh / 100 đường dẫn / 0 lỗi / 5 cảnh báo`. Khoảng trống còn lại thuộc **environment**, không thuộc code: Python hệ thống thiếu `pypdfium2`/`streamlit` ⇒ 4 file test lỗi **collection** (`test_corpus_rebuild`, `test_demo_streamlit_display`, `test_ui_generator_flag`, `test_ui_labels`) → điều kiện tái lập phải ghi rõ interpreter | `tests/test_final_subprocess_stdin_guard.py`, `tmp/mutation_check_stdin_guard.py`, `tmp/mutation_check_stdin_guard.log`, `tools/diag/council_kit.py`, `tools/diag/secret_scan.py`, `tools/diag/final_number_audit.py`, `tmp/pytest_after_d35.txt`, `tmp/final_number_audit_after_d35.json`, `tmp/docs_check_after_d35.json`, `tmp/pytest_baseline_stdin_closed.txt`, `docs/archive/reports/test_final.md` §14 | **ĐÃ SỬA** (3 máy kiểm + 2 bộ test, không sửa dụng cụ đo, không đổi số); **GIỮ** nguyên tắc "lỗi môi trường phải được báo là lỗi môi trường, không được biến thành kết luận về repo"; **MỞ** rủi ro interpreter (PA-26, xem §11 + §14) |
| D-36 | 25-10 | Đợt siết stdin (D-35) xong, vẫn còn một đường khiến máy kiểm nói dối người tái lập: console của máy đo **không phải UTF-8**. Chạy `tools/diag/council_check_gold6.py` với `PYTHONIOENCODING` và `PYTHONUTF8` bị gỡ bỏ thì `print` dòng `ĐẠT — 0,5186` văng `UnicodeEncodeError` và script trả **exit code 1**. Đây có phải là "câu hỏi hội đồng KHÔNG ĐẠT" không, và sửa ở tầng nào: nới test, đổi bảng mã mặc định của máy, hay để người dùng tự đặt env? | **KHÔNG — mã thoát 1 ở đây hỏng ở máy in, không hỏng ở phép đo, và nó đánh lừa đúng đối tượng nguy hiểm nhất: người tái lập.** Đo hiện trạng: `chcp` = **1258** và `locale.getpreferredencoding()` = **cp1258** (bảng mã tiếng Việt); traceback lưu ở `tmp/probe_no_utf8.txt` chỉ rõ `encodings\cp1258.py` fail tại ký tự `\u1ece` (chữ ệ). Hai đính chính cho D-35: (i) **hai interpreter cùng bản 3.14.8**, khác nhau ở tập package (`venv` có `pypdfium2`/`streamlit`, python hệ thống không, `include-system-site-packages = false`) chứ không phải khác phiên bản; (ii) cp1252 chỉ là stand-in tất định, máy đo thật dùng cp1258. Cách sửa: khối guard lúc import trong **7** máy kiểm — `reconfigure(encoding="utf-8", errors="replace")` cho stdout + stderr, bọc `try/except Exception` để không bao giờ làm hỏng phép đo kể cả dưới `capsys` — **lấy đúng khuôn có sẵn của `docs_consistency_check.py` từ đợt T7** nên không phát minh chuẩn mới; không nới test, không bắt người dùng đặt env. Răng: `TestMayInKhongChiuLoiConsole` = **13 test** (2 điều khiển âm chứng minh cp1252 **và** cp1258 đều không in nổi `ĐẠT — 0,5186`; 7 ghim chuỗi guard, guard đứng trước `def main(`, bọc `except Exception`; 4 chạy process con thật bị nén bảng mã, kỳ vọng `rc=0` và không có `UnicodeEncodeError`). Cả file phòng thủ môi trường thành **34 test**; sổ cái đột biến **giữ 9/9** sau khi chạy lại harness (K7 đổi UTF-8 thành cp1252, K8 bỏ `errors="replace"`, K9 thu hẹp `except Exception` thành `except ValueError`). Kiểm toán số công bố **60 dòng / 0 dòng LỆCH**; các số đã công bố không đổi — chữ ký trọng tài `9f1179ccab74`, secret scan `0/0/89/8`. Mở còn lại: điều kiện interpreter + bảng mã chưa có trong README (PA-34). | `tools/diag/council_check_gold6.py`, `tools/diag/council_check_fabrication.py`, `tools/diag/council_check_referee.py`, `tools/diag/env_flag_audit.py`, `tools/diag/secret_scan.py`, `tools/diag/train_data_audit.py`, `tools/diag/final_number_audit.py`, `tests/test_final_subprocess_stdin_guard.py`, `tmp/probe_no_utf8.txt`, `tmp/probe_utf8_after.txt`, `tmp/mutation_check_stdin_guard.log`, `tmp/pytest_after_d36.txt`, `tmp/final_number_audit_after_d36.json`, `docs/archive/reports/test_final.md` §14 | **ĐÃ SỬA** (7 máy kiểm + 1 bộ test; không sửa dụng cụ đo, không đổi kỳ vọng, không bắt người dùng cấu hình máy); **GIỮ** nguyên tắc "máy kiểm phải hỏng vì nội dung, không hỏng vì cách in"; **MỞ** PA-34 (README chưa ghi interpreter/bảng mã, 8 lời gọi subprocess ngoài phạm vi ở 6 file — đếm bằng AST `tmp/count_stdin_sites.py`) |
| D-37 | 26-10 | PA-25 (reranker chấm query NGUYÊN VĂN, không `fold()`) đủ mạnh để biến lever rerank từ âm sang dương; nếu `EXACT` tăng >= +0,10 theo tiêu chí đã đăng ký thì có quyền đề xuất kích hoạt, còn cổng chính thức vẫn là trọng tài cuối | r16-vs-r11: `FAIL_RETRIEVAL` 182 -> **115**, gold@6 0,7400 -> **0,8357** (ghép cặp 811 item: delta +0,0957, CI [0,0714; 0,1200], McNemar p=2,4e-14), EXACT 0,2115 -> **0,4231** (delta +0,2116, n=52, p=0,0034) => tiêu chí đăng ký trước **ĐẠT**; nhưng cổng **KHÔNG ĐẠT** vì `human_anchor_source_not_degraded` 0,8144 -> 0,7629 (tương đối -6,32%, ngưỡng -5%, n=97). Hồi quy được đo tới nơi: 97/97 item HUMAN không có chunk vàng nên family này chỉ đo bằng neo nguồn; 8 mất / 3 lấy = net 5 item, McNemar chính xác p=0,2266, bootstrap 10.000 lượt seed 20261023 cho CI [-0,1237; +0,0103] chứa 0. Cổng r16-vs-r12 **ĐẠT cả 6** (neo HUMAN +8,83%). Đính chính cách đọc số cũ: 0,8214 là trần oracle **pool 12**, trần **pool 20** = 0,8871 (`docs/archive/reports/T5.md` dòng 228) nên r16 = chiếm 65% khoảng trống 0,7400 -> 0,8871, không phải "vượt trần". Chi phí: median 2,78 -> 4,73 s (+70%), p95 3,87 -> 5,09 s (+31%). **Mốc 28-10 (E4):** baseline đúng của lever reranker từ 27-10 là **r17-T** (dense nguyên văn trên nền all-off: **581/700 = 0,8300**, HUMAN **77/97**), không còn là r11 (518/700, reranker TẮT và router bật). Mọi Δ reranker dẫn ở trên chỉ còn giá trị **lịch sử**; phép đo một-biến `ENABLE_RERANKER` trên mốc r17-T **đã có từ r22 (29-10)** nên dòng này **không còn** nhãn "CHỜ ĐO LẠI" — kết quả ở cột Trạng thái, còn tiêu chí đăng ký trước trên mốc r11 đã **ĐẠT** | `docs/archive/reports/B3.md`, `data/loop/rounds_v2/r16/gate_vs_r11_retrieval.json`, `data/loop/rounds_v2/r16/gate_vs_r12_retrieval.json`, `data/loop/diag/reranker_paired_r11_r16.json`, `data/loop/diag/reranker_paired_r12_r16.json`, `data/loop/rounds_v2/r16/attribution_retrieval.json`, `tmp/r17_dense_orig_2026-10-27.json`, `tmp/r22_reranker_20261029.json`, `tmp/r22_report.md`, `tmp/r22_y_check_20261029.md` | **BỊ BÁC VETO HUMAN** (r22, 29-10) = quyết định vận hành **BÁC** (không bật lever); nhãn khoa học ở EXPERIMENTS là **KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ** — **không phải BÁC khoa học** vì Δ dương và CI loại 0: gold@6 581->612 (+31, p=3,12e-06) trên nền r17-T; neo HUMAN 77->72 (−6,49%, ngưỡng −5%); 4/8 mục rơi (HQ23, HQ36, HQ40, HQ58) trùng D-37; McNemar 3/8 p=0,227; cờ `ENABLE_RERANKER` TẮT |
| D-38 | 26-10 | B4: một cross-encoder chấm cặp (cửa sổ có chunk vàng) vs (cùng cửa sổ rút chunk vàng) phân biệt đủ mạnh — `auc_ce_max` eval >= 0,75 trên >= 30 cặp — để làm máy đo answerability chạy trên đĩa, không cần lượt sinh | Mẫu CHÍNH (r5, đăng ký trước): 59 cặp, eval 29/train 30 -> **`n_eval_clean=19 < 30`** => verdict dụng cụ **MAU_QUA_NHO** (auc 0,8643 chỉ là hướng; ngưỡng 30 KHÔNG hạ). auc_ce_max eval_clean: r5 0,8643 (19) / r11 0,8039 (104) / r12 0,8277 (90); eval_all: 0,8038 (29) / 0,7441 (260) / 0,7529 (229). Nhiễu nhãn NEG: `still_answerable` 27/59 (45,8%), 335/518 (64,7%), 285/468 (60,9%) => rút vàng KHÔNG phải nhãn "không trả lời được"; kết luận phụ thuộc bộ lọc. Mốc so sánh "hạng truy xuất" **degenerate theo construction**: `auc_rank_min=0,5` và `rank_min_phang=true` trên cả ba mẫu (POS/NEG đều bắt đầu ở hạng vị trí 1 sau bản sửa rò rỉ nhãn) => vế "tốt HƠN hạng truy xuất bao nhiêu" **CHƯA TRẢ LỜI**. Model thật đo = `bge-reranker-v2-m3` 568M (không phải "nhỏ"; `bge-reranker-base` 278M không có weights trên đĩa, ngã rẽ bảo thủ là không tải 1,1 GB). Chấm 12.540 lượt cặp, 1.523 s, 0 lần thiếu text (`so_cap_lo_do_thieu_text=0`), 0 lượt sinh. | `docs/archive/reports/B4.md`, `data/loop/diag/answerability_probe_r5.json`, `data/loop/diag/answerability_probe_r11_retrieval.json`, `data/loop/diag/answerability_probe_r12_retrieval.json`, `data/loop/diag/answerability_labelset_r5.jsonl`, `data/loop/diag/answerability_labelset_r11_retrieval.jsonl`, `data/loop/diag/answerability_labelset_r12_retrieval.jsonl` | **CHỜ DUYỆT** (PA-37 weights model nhỏ, PA-38 đăng ký lại phép đo có mốc hạng; kết luận chính của mẫu đăng ký = MAU_QUA_NHO) |
| D-39 | 26-10 | B5: logits tính trên TOÀN BỘ vị trí là nút thắt bộ nhớ của SFT LoRA 0,5B; chỉ tính logits trên token đáp án sẽ mở thêm trần độ dài train trên card 4 GB (diễn giải mà docs/archive/reports/T4.md tự nhận là chưa kiểm chứng bằng profiling) | **Tiêu chí đăng ký trước (Luật 1) KHÔNG ĐẠT và cũng KHÔNG BỊ BÁC**: `full` không OOM ở bất kỳ độ dài nào đã đo (tới 3072 token, đỉnh 10429,4 MiB trên card 4095,5) => điều kiện phân cách không xảy ra; verdict dụng cụ ghi nguyên `CO_HIEU_LUC_NHUNG_KHONG_MOI_THEM_TRAN`. Hiệu số peak full - answer_only: 1226,2 / 1648,1 / 2412,0 MiB ở 768/1024/1500 (fraction 0,15 - lượt đăng ký), 3286,7 / 4116,0 / 4939,5 ở 2048/2560/3072, 1735,7 / 2452,5 / 2910,0 ở 1024/1439/1707 (fraction THẬT 0,0393). Quy về mỗi vị trí bị che: **1,764-1,894 MiB/token** (đồng nhất ba lượt) = **6,1-6,5x** dự đoán fp16 thuần (151936x2 byte = 0,2898 MiB/token) và 3,3x dự đoán upcast fp32; hai con số đều được ghi, không chọn con có lợi. Gradient checkpointing **tốn thêm** 8,1-18,2 MiB ở cả hai mode (tái lập T4b 3356,0 vs 3339,8; lượt đo 768 = 3339,8 khớp chính xác đường cơ sở cũ). Loss hai mode khớp tới 1,5e-4 tương đối => cơ chế không đổi mục tiêu hàm. **Đính chính cách đọc số đã công bố**: kiểm chứng `b5_wddm_oversubscription` cho thấy CUDA cấp và ghi đủ 8 GiB trên card 4 GB mà không báo lỗi, `nvidia-smi` khoá ở 3849 MiB, fill chậm x4,25 (33,6 -> 7,9 GiB/s), RAM 16088 MiB (trống 7212, pagefile 32176) => "đỉnh > tổng VRAM" là bằng chứng **oversubscribe/chậm**, không phải bằng chứng **không train được**; vì thế cách đọc "13/13 dòng extractive không train nổi" **rút từ peak một mình** phải hạ cấp thành suy diễn chưa được xác nhận. **Giới hạn của đính chính (tự kiểm thấy thiếu):** project memory ghi một lượt train **thật** --max-length 1024 OOM ở step 24 (23-10) nhưng repo không còn log/artifact của lượt đó, nên câu hỏi "một lượt train thật có chết giữa epoch không" vẫn **MỞ** và lời giải là PA-39 — B5 **không** được quyền nói "chưa từng quan sát thất bại". Ở fraction thật, dòng dài nhất (1707 token) giảm 6238,3 -> 3328,3 MiB (152,3% -> 81,3% card) => PA-11 (4-bit) / PA-12 (đổi định dạng) không còn là hai đường duy nhất, nhưng cần lượt train thật để chốt. Probe = 1 bước fwd+bwd, batch 1, dữ liệu giả, GPU nhàn rỗi (Ollama không resident), KHÔNG optimizer state => không trả lời "train cả epoch ổn không" (Luật 4). | `docs/archive/reports/B5.md`, `data/loop/diag/answer_token_logits_probe.json`, `data/loop/diag/answer_token_logits_probe_oom_bound.json`, `data/loop/diag/answer_token_logits_probe_real_fraction.json`, `data/loop/diag/b5_answer_fraction.json`, `data/loop/diag/b5_wddm_oversubscription.json` | **CHỜ DUYỆT** (PA-40 quy ước báo cáo bộ nhớ đã áp 01-11 ở README/T4/test_T4/STATE/ROADMAP; **PA-39** lượt train thật với logits theo vị trí đáp án **vẫn chờ**, và phần sample residency trong dụng cụ chưa làm; model không được train, cờ SFT không đổi) |
| D-40 | 26-10 | B1: chunk vàng **có dấu** từ index mới `chroma_db_vie` giúp Qwen 1,5B trả lời đúng hơn trên đúng các item mà gold ánh xạ được (ablation c′ so với a′ cùng item) | 57/80 item pha sinh của r5 ánh xạ được (n >= 30 theo đề bài) **nhưng** kiểm trên đĩa: **54/57 chunk vàng của hai index giống nhau từng byte**, **0 item chỉ khác ở dấu**, 3 item khác nội dung (khác thật) ⇒ 57/57 câu trả lời a′ và c′ **byte-identical**: PASS_CORRECT 5/57 = 5/57 (0,0877), refusal 50/57 = 0,8772 cả hai, Δ ghép cặp 0,0000 CI [0,0000; 0,0000], McNemar 0 bất đồng p=1,0, fabrication 0/0 không xác định. 54/57 dòng c′ là cache hit (prompt byte-identical), 3 dòng sinh thật 2,4–2,5 s. Trọng tài hai nhánh = v1 (chữ ký lấy lúc khởi động tiến trình, đối chiếu snapshot độc lập). ⇒ **không có kết luận về hiệu ứng dấu**: phép thử PHIẾU về cấu trúc, KHÔNG phải kết quả âm; 0 lượt Gemini. **Phạm vi chưa kiểm (E5, 28-10):** giả thuyết gốc nói về chunk **nhóm OCR** (`CLOZE_OCR`), nhưng bước chọn mẫu chỉ giữ item mà gold ánh xạ được giữa hai index — **0/57** cặp khác nhau riêng ở dấu, nên nhóm OCR cần kiểm **không nằm trong phép đo**; số đo hiệu ứng dấu ở tầng sinh = **chưa kiểm chứng** cho tới khi PA-17 re-anchor xong | `docs/archive/reports/B1.md`, `data/loop/diag/b1_cprime/analysis.json`, `data/loop/diag/b1_cprime/mapping.json`, `data/loop/diag/b1_cprime/a_prime/rows.jsonl`, `data/loop/diag/b1_cprime/c_prime/rows.jsonl` | **BÁC** (bác *cách thiết kế phép thử*, không bác giả thuyết) — muốn đo hiệu ứng dấu phải trả PA-17 re-anchor trước |
| D-41 | 26-10 | B2 (đã duyệt PA-2 + PA-20): siết hai luật của trọng tài có làm đổi verdict các round đã đóng không, đổi bao nhiêu và theo hướng nào | Chữ ký dụng cụ đo v1 `9f1179ccab74` → **v2 `2911c69f740d`** (băm file sau vá: `verify.py` 137ee884af3c, `answer_guard.py` ab4a8a73292f, `text_utils.py` không đổi 5f810aa52b6b, **`gate.py` không đổi** bf4bda89d8a360abbba25742). Chấm lại OFFLINE 10 round có `full.jsonl` × 100 câu → `data/loop/rounds_v2/` (`data/loop/rounds/` **không đổi một byte nào**): **5/1000 verdict đổi chiều, 100% theo hướng chặt hơn** — item `T111158251954171` mất PASS_CORRECT ở r5/r6/r7/r10, thêm `C162319281103737` ở r10; **PASS_CORRECT tổng 148 → 143**; `refusal_rate` và `fabrication_rate_on_answered` **không đổi** trên cả 10 round. Round retrieval-only (r2, r4, r11–r15) không chấm lại, có lý do bằng chứng: nhánh `retrieval_only` trong `score_item` chỉ dùng `gold_chunk_id`/cửa sổ sources, cả hai bản vá nằm sau nhánh đó. Kiểm ngược bằng `tools/diag/council_check_referee.py` đã phiên bản hoá: **1000/1000 câu khớp 100%** khi chấm bằng đúng bản v1. Đơn vị đo của dòng này = **verdict** (1.000 = 10 round × 100 câu), không phải item truy xuất. Nhãn khoa học 28-10 = **ĐẠT** cho tiêu chí "chấp nhận được": đổi **5/1.000 = 0,005** và 100% theo hướng chặt hơn | `docs/archive/reports/B2.md`, `data/loop/rounds_v2/compare_v1_v2.json`, `tools/diag/rescore_rounds_v2.py`, `tests/test_t8_referee_v2.py`, `tests/snapshots/referee_v1` | **CHỜ DUYỆT** (từ nay báo cáo/cổng trích theo cây nào — `rounds/` v1 hay `rounds_v2/` v2; dữ liệu cũ không bị xoá, cổng r16 đã chạy trên v2) |
| D-42 | 26-10 | Máy kiểm số cuối phiên (`tools/diag/final_number_audit.py`) còn tái lập được toàn bộ số đã công bố sau ba mục đã duyệt (PA-2/PA-20/PA-25) hay không | 63 dòng được kiểm, **61 KHỚP — 2 LỆCH**; **rc=0** (đo lại 26-10: script chỉ có `return 0`, không tự fail — nên lệch chỉ thấy ở bảng in ra; PA-41 nêu thêm đề xuất (d)): (a) “46 test cờ RERANKER_FALLBACK” — đĩa hiện **51** (`tests/test_reranker_flag.py` lớn lên trong B3 để khoá quy ước query của PA-25); (b) “chữ ký trọng tài `9f1179ccab74`” — đĩa hiện **`2911c69f740d`** (B2 đổi có duyệt). Cả hai là **kỳ vọng cũ của máy kiểm**, không phải số trong báo cáo bị sai ⇒ không tự sửa hàng đợi kiểm trong ca tự trị. Các máy kiểm khác cùng lúc: `docs_consistency_check.py` SẠCH LỖI; `secret_scan.py` SECRET_COTHAT = 0 và PII **89 dòng/8 file — đúng bằng trước phiên**; `pytest tests -q` **1.495 passed, 5 skipped** (94,54 s; mốc đầu phiên 1.372); harness đột biến B4+B5 13/13 bị bắt, sha256 hai dụng cụ khôi phục nguyên văn. | `tmp/final_number_audit_b_shift.json`, `tmp/consistency_b_shift.json`, `tmp/secret_scan_b_shift.json`, `tests/test_reranker_flag.py` | **ĐẠT** (01-11: PA-41 vá 2 kỳ vọng `46→51` test và chữ ký v1→v2; lượt riêng cùng ngày vá nốt T5 `33+44=77` và T7 `119` đường dẫn, giữ chú thích nguồn trong `tools/diag/final_number_audit.py`; chạy lại **63/63 KHỚP, 0 dòng LỆCH**, rc=0; bảng đo cũ giữ nguyên số lịch sử + ghi chú ở `docs/REPRODUCE.md`; PA-29 cùng ngày thêm 1 đường dẫn tài liệu ⇒ kỳ vọng T7 nâng `119 → 120`, audit vẫn 63/63) |
| D-43 | 01-11 | PA-31 hoàn tất được trên `thesis-final` (8 tệp/89 khớp) hay phải chuyển sang dòng `main` nơi đủ artifact — và che tới đâu mà không làm hỏng tập đo | Trên `thesis-final` `9c1c00e` phép quét cho **165 khớp/9 tệp** và **đạt pin**; nhưng 10 artifact diag mà chính tài liệu đóng băng trích dẫn (D-38 nêu `answerability_labelset_r5.jsonl`; evidence ghim sha `182dd5cb…`) chỉ được commit sau ở `ea9416d`, nên 18 tệp của PA-31 **không đủ** trên cây đóng băng và che 8 tệp buộc pin `165/9` đỏ. Trên `refactor/phase1-runtime` (nền `ea9416d`): scan **640 khớp / 18 tệp + 1 đường dẫn cá nhân** (`t4_adapter_probe.json:22`). Đã che 17/18 bằng `redact_pii.py --set full` (564 khớp PII + 1 path → **0**; số dòng và tính hợp lệ JSON giữ nguyên), **giữ `data/loop/testset_v1.jsonl`** (76 khớp, sha `202ca508…`) vì che nó là đổi tập đo đã đóng băng. Còn lại **76 khớp / 1 tệp**, đường dẫn cá nhân **0**; pin test đổi `165/9 → 76/1` có chủ đích. **Đính chính cách đo:** đặt 14 lever = 0 theo nghĩa đen làm 9 test cache/golden đỏ vì 4 ngưỡng (`ROUTER_SOURCE_QUOTA`=0, `ROUTER_FILTER_RANK_BONUS`=3, `RESCUE_MIN_SCORE`=0,8) bị `cache_policy_deviation()` coi là lệch chuẩn; chế độ "lever TẮT" đúng là **11 cờ = 0, ngưỡng để mặc định** (hoặc bỏ dòng tương ứng trong `.env` của máy). **Hậu kiểm 01-11 (sau khi áp):** vá 3 lỗi của chính dụng cụ — (i) `--out` tương đối ném `ValueError` **sau khi đã che xong** (lượt áp phải truyền đường dẫn tuyệt đối); (ii) `count_personal_paths` đếm `C:/Users/<tên>` **2 lần** vì hai khuôn cùng khớp, trong khi lượt che chỉ thay 1 lần — lỗi **tiềm ẩn**, lượt 01-11 không dính (`t4_adapter_probe.json`: before 1 = masked 1); (iii) escape JSON **không bất biến**: lượt hai trên bản đã che biến `\\[EMAIL_1]` hợp lệ thành `\\\[EMAIL_1]` (escape hỏng) vì cách cũ nhân đôi MỌI backslash trước token — lộ ra khi `--dry` đọc lại artifact 01-11; luật mới chỉ thêm backslash khi dãy **lẻ**, nên chạy lại không đổi byte. Không số/cổng nào ở trên đổi; `--dry` trên cả 8 và 18 tệp hiện báo `JSON hợp lệ=True`; thêm `tests/test_redact_pii_tool.py` (31 test) khoá cả ba | `tools/diag/redact_pii.py`, `tests/test_final_secret_scan.py`, `data/loop/diag/*` (17 tệp), `outputs/ab_results_with_classifier.json`, `outputs/ab_results_without_classifier.json`, `tmp/pa31_backup_20261101/SHA256SUMS.txt`, `tmp/pa31_redacted_20261101/REDACTION_REPORT.json` | **GIỮ** — đã áp trên nhánh `refactor/phase1-runtime`; `thesis-final` `9c1c00e` bất động; không tạo tag `thesis-final-pii` |
| D-44 | 01-11 | P4b (resume 7/30 câu Gemini thiếu khi quota reset) có cần chạy tiếp, hay chốt bộ 30 câu hỏi thật bằng Qwen local? | **Không chạy Gemini** (ràng buộc 0-Gemini): P4b **đóng**, bộ 30 câu thật lấy **Qwen local** làm backend sinh chính thức. Đo đã có: Qwen **30/30** câu có trả lời, 0 lỗi (p50 31,3 s; p95 37,04 s; 21/30 từ chối; 11 câu `kho=N`, trong đó **1 lọt** RQ-0018; **4 từ chối oan** khi chunk Y nằm trong top-6). Gemini giữ **23/30** (7 lỗi 429 PerDay: RQ-0021, RQ-0023, RQ-0024, RQ-0025, RQ-0028, RQ-0029, RQ-0030). So sánh chỉ trên **23 câu giao**: từ chối 16/23 vs 15/23; gold@6 **8/23 = 8/23** (cùng cửa sổ truy xuất); trả lời khi 12 chunk không có Y: 1/23 vs 3/23; p50 **102,76 s** vs **31,93 s**. **Không kết luận thống kê** (n=23, không có ngưỡng đăng ký trước). Nhãn Y/P/N của P3 hiện do **AI chấm**; 290 nhãn người còn chờ user điền ⇒ các số gold@6 ở đây là **tạm thời**, nhưng quyết định backend không phụ thuộc nhãn | `tmp/real_questions_user/p4_report.md`, `tmp/real_questions_user/p4_report_qwen.md`, `tmp/real_questions_user/p5_compare.md`, `tmp/real_questions_user/p4_full_run.jsonl`, `tmp/real_questions_user/p4_full_run_qwen.jsonl`, `tmp/real_questions_user/real_questions.jsonl` | **GIỮ** — Qwen local là backend cho bộ 30 câu; P4b đóng, **0 lượt Gemini**; nhánh Gemini 23/30 giữ làm bản ghi lịch sử, không resume |
| V1 | 27-10 | Nhánh dense nhận query **nguyên văn** thay vì đã `fold` sẽ tăng recall (đo trên đúng index cũ) | **ĐẠT** — đơn vị đo: **700 câu có gold** trong 811 item, 24 cụm `source_document`. hit@6 **474/700 = 0,6771** vs **202/700 = 0,2886** (Δ +272 câu = **+0,3886**; b=308 / c=36, McNemar chính xác p=5,27e−55; bootstrap cụm 10.000 lượt, seed 20261027, CI **[0,1918; 0,5475]** — artifact tự ghi `delta_points = 38,86` theo **điểm %**, còn CI ở đây là **phân số hit@6**); MRR@12 0,5003 vs 0,2060; mất nhẹ đúng ở nhóm OCR (CLOZE_OCR 154 vs 160). Cơ chế: `fold(query)` xoá dấu câu hỏi trong khi index cũ vẫn còn 18,6% từ có dấu. Chữ ký trọng tài: **không áp dụng** (đo truy xuất thô, artifact không lưu chữ ký). `src/` **chưa sửa** ⇒ cờ `ENABLE_DENSE_ORIGINAL_QUERY` = PA-48a | `tmp/dense_orig_query.json`, `tmp/retrieval_diag_report.md` | **CHỜ DUYỆT** PA-48a; kết luận đo lường **GIỮ** |
| V2 | 27-10 | Chuỗi r0→r1 (0,5186→0,7657) là bằng chứng "lọc mềm cải thiện gold@6" | **BÁC cách đọc** — đơn vị đo: **811 item**, trong đó **700 câu có gold**. r1 là **không router** — 0/811 dòng có nhãn classifier, 700/700 verdict gold trùng all-off, median 0,18 s/item (r11 **2,78 s**; median r0 tự đo 2,76 s) ⇒ r0→r1 chỉ là **bỏ lọc cứng**. Lọc mềm so all-off: **518 vs 536/700** = −18 câu (Δ **−0,0257**; McNemar p=2,77e−4; CI cụm [−0,0462; −0,0069]); mất tập trung ở nhóm router chọn sai nguồn (all-off 178 → r11 157 trong 245 item); neo HUMAN 79 vs 75/97 (+4, CI [−0,0132; +0,0787] chứa 0). Ràng buộc: r0 đạt 363/700 vì lọc cứng xoá 244/244 item nguồn-sai. Chữ ký trọng tài: **v2** (`2911c69f740d`) cho phần đọc lại; không sửa số/cổng đã công bố | `tmp/v2_rescore.json`, `tmp/v2_extra.json`, `tmp/alloff_811.json`, `tmp/retrieval_diag_report.md` | **GIỮ** baseline mới = all-off 536/700, HUMAN 75/97; giả thuyết lọc mềm = **BÁC** (D-06) |

---

## Chi tiết những dòng cần ngữ cảnh

### D-01 — Lọc cứng gây hại; lọc mềm không phải là bản sửa (23-10, đọc lại 27-10)

Giả thuyết ban đầu có hai nửa. Nửa thứ nhất — `source_filter` cứng xoá nguồn khi classifier sai nhãn,
nên 244/337 `FAIL_RETRIEVAL` của r0 là do bộ lọc — **đúng và giữ nguyên**: r0 chỉ đạt 363/700 vì lọc
cứng cắt 244/244 item có nguồn vàng nằm ngoài bộ lọc, và `FAIL_RETRIEVAL` 337→164 khi bỏ nó.

Nửa thứ hai — "thay bằng lọc mềm + bonus sẽ kéo gold@6 lên" — **bị bác** khi đọc lại artifact bằng
trọng tài v2 (V2, 27-10). r1 không bật router: **0/811** dòng có nhãn classifier, **700/700** verdict
gold trùng khít all-off, 0,18 s/item so với **2,78 s** của r11 (median r0 tự đo là 2,76 s — các bản in
trước hay nhầm hai số này). Vì vậy 0,7657 của r1 **chính là** gold@6 all-off, không phải thành tích của
lọc mềm. Đo lọc mềm với đúng baseline (r11 vs all-off) cho
**−18 item** (518 vs 536; −0,0257; McNemar p=2,77e−4; CI cụm [−0,0462; −0,0069]), mất tập trung ở
nhóm router chọn sai nguồn (all-off 178 → r11 157 trong 245 item). Neo HUMAN 79 vs 75 (+4) nhưng CI
[−0,0132; +0,0787] chứa 0,
và cơ chế ưu tiên nguồn tự thưởng cho neo nguồn nên không được đọc là cải thiện.

Quyết định: **giữ kết luận "lọc cứng gây hại"**, **bác** giả thuyết "lọc mềm kéo gold@6 lên"; lever
giữ TẮT. Từ nay baseline của mọi round truy xuất là **all-off** (536/700, HUMAN 75/97, 0,18 s/item),
không phải r11 — vì r11 vừa chậm hơn 15 lần vừa thấp hơn 18 item.

### D-03 — Rescue bị bác vĩnh viễn (23-10)

Lý do không thử lại: cơ chế đã được đo trực tiếp trên 60–64 lượt thật, không phải suy luận. Tỉ lệ cứu
1,7% nằm dưới xa mức cần để bù chi phí một lượt gọi model/câu. r5b lặp lại **nguyên văn** cấu hình để
chứng minh con số tái lập được (không phải may mắn của một lần chạy).

### D-04 — Guard chuẩn hóa là lever sinh đầu tiên có bằng chứng (24-10)

Điểm quan trọng nhất: tally r6 ghi **4 ca `False→True` + 1 ca `True→True`**, và **sau can thiệp cả 5/5
ca đều có chunk vàng trong ngữ cảnh** — hai cách nói này từng bị gộp thành "5/5 ca bị bác lấy lại vàng"
(đính chính 28-10: đúng ở vế kết quả, chưa đúng ở vế tally). Tập ca được chọn từ log của lever chứ không
phải từ kết quả. Số hai chữ ký: `PASS_CORRECT` v1 10→**14**, chấm lại v2 10→**13**; gold@6 trên 80 câu có
gold 0,6875→**0,7875**; refusal 0,72→0,64. **Không có CI cho Δ** trong artifact, nên nhãn khoa học chỉ tới
mức "ĐẠT về cơ chế cục bộ", không tới mức "ĐẠT về hiệu số có ý nghĩa thống kê". Cổng vẫn báo KHÔNG ĐẠT
chỉ vì `refusal_rate` vượt trần tuyệt đối 0,35 — chính là lý do đề xuất D-15. Việc **bật mặc định** chưa
làm vì đổi hành vi production.

### D-05 / D-07 / D-08 / D-09 — vì sao bốn dòng tầng sinh không còn được ghi "BÁC" như cũ (28-10)

Cả bốn đều là số đo **dưới ngưỡng đăng ký trước**, không phải bằng chứng loại trừ hiệu ứng:

- D-05 (tổ hợp bonus 12 + guard): `PASS_CORRECT` v1 14→14, v2 13→13, Δ = 0 nằm nguyên trong băng nhiễu
  ±3 của T0, không CI, và "cộng hưởng" chưa từng có ngưỡng ⇒ **KHÔNG KẾT LUẬN**.
- D-07 (decoupled refusal): ngưỡng T3 là **≥25/100 và không tăng bịa**; đo 19/100 (v1 và v2) **và**
  `FAIL_HALLUCINATED_ON_UNANSWERABLE` 2→12 ⇒ hai vế đều hỏng, giữ **BÁC** ở mức quyết định vận hành.
- D-08 (evidence selection): ngưỡng ≥25/100; đo 19→19 **trên cùng 100 ID** (đính chính: bản in trước nói
  "tập câu khác" là sai — đối chiếu `attribution_vs_r8.txt`), `model_still_refuses` 3→32, p95 +67%.
- D-09 (1,5B → 3B): ngưỡng ≥22/100; đo 16 (v1) / 14 (v2), Δ +0,0203 CI [−0,06; +0,10] **chứa cả 0 lẫn
  mức đăng ký** ⇒ **KHÔNG ĐẠT NGƯỠNG**, không phải BÁC: số đo không loại được hiệu ứng dương, chỉ chưa
  đủ lớn để đạt ngưỡng.

### D-06 — Câu hỏi "bonus 3 hay 12": cặp so sánh thật không phải là cặp bonus (24-10, đính chính 28-10)

**Đính chính theo V2 (27→28-10):** toàn bộ cơ chế mô tả dưới đây áp dụng cho cặp **r1↔r2**, mà r1 đã được
chứng minh là **all-off** (không chạy router). Vậy cặp đã đo là "lọc mềm kèm bonus 12" vs "không lọc" —
**không phải** "bonus 3" vs "bonus 12". Con số −0,0257 (−18/700, CI [−0,0462; −0,0069], p=2,77e−4) vì thế
thuộc về **giả thuyết lọc mềm** và đã bị **BÁC**; nó không được dùng làm bằng chứng về hằng số bonus nữa.

Những gì vẫn còn giá trị: **21/21** chunk vàng bị mất nằm **ngoài** `source_filter` và rơi đúng hạng
**7–12** — tức mất do cửa sổ/xếp hạng, không do nhãn lọc. EXACT/TRAP không đổi giữa r1/r2/r4 là bằng
chứng phụ. Hệ quả mới: **hằng số bonus chưa từng được cô lập** trong một phép thử một-biến, nên về
"bonus có phải nút thắt" chỉ đạt **KHÔNG KẾT LUẬN** (muốn đo phải có cặp chỉ khác `ROUTER_FILTER_RANK_BONUS`
trên cùng nền all-off). Hướng "reranker / pool 20" (D-11) vẫn là hướng đã được đăng ký và đã đo ở T5.

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

Chuỗi bằng chứng: đo corpus (0,0328 từ còn dấu) → xác định PDF-scan/convert là nguồn → OCR lại bằng EasyOCR
`vi` → chất lượng OCR trên trang đã OCR 0,033→**0,8226** → build index **riêng** `chroma_db_vie/` (342
chunk) → đo bằng **cùng** script: 0,1913→**0,8029**.

**Đính chính 28-10 về số trang (E5):** đếm key trang trong `.ocr_cache_vie/` (13 tệp) cho **124 trang**,
trong đó **123 trang mới OCR ở lượt chạy** và **1 trang đã có cache** (`tmp/reocr_vie.log`). Các bản in
trước ("OCR lại 123 trang") không sai về lượt chạy nhưng **thiếu một trang cache**, nên số này không tái
lập được từ thư mục cache. Proxy "từ còn dấu" **không** đo độ chính xác ký tự OCR — không có bộ nhãn đối
chiếu ⇒ chất lượng OCR và chất lượng trả lời trên index mới = **chưa kiểm chứng** (phần đã đo ở tầng sinh
là D-40, phần ở tầng truy xuất là Q5, cả hai đều KHÔNG KẾT LUẬN).

Quyết định bảo thủ: **không** đổi `chroma_db/` đang chạy; kích hoạt index mới cần user duyệt (PA-1) vì
đổi index = đổi dữ liệu đo của mọi round sau, và neo vàng hiện gãy 48,81% (PA-17).

### D-14 — Vì sao chưa được nói "năng lực model là nút thắt" (24-10, làm rõ 28-10)

25/30 id là **tiền tố theo thứ tự r5** (5 id thiếu là 5 id cuối, lý do `PerDay` ghi trong
`id_status.json`), không phải mẫu ngẫu nhiên đủ. Mẫu **có** đăng ký trước: `sample_ids.json` khai báo
rule `FAIL_OVERREFUSAL ∩ has_gold_chunk` của r5, **pool 33** câu, phân tầng theo `family`
(CLOZE 9 / CLOZE_OCR 13 / YESNO_FACT 5 / NUMERIC 2 / SOURCE_LOOKUP 2 / EXACT 1 / REVERSE_LEGAL 1),
seed **20261023**. Hệ quả của cách chọn này phải nói rõ: đây là **mẫu chọn từ ca từ chối oan** của Qwen
nên độ khó không so được với các round 100 câu; `PASS_CORRECT` 16/25 = **0,64**, CI [0,44; 0,84] vì thế
**không** so được trực tiếp với 0,14 của Qwen trên 100 item khác tập câu. Điều kiện đóng dòng này: đủ
**30/30** id, giữ nguyên `data/loop/diag/b_gemini_top6/sample_ids.json`.

---

### D-21 — Khóa chính sách trong cache sinh: chỉ thêm khi lệch mặc định (25-10)

Vấn đề: cache của `GeminiGenerator` và `QwenGenerator` chỉ băm model/nhiệt độ/prompt/phiên bản prompt.
Đổi `RESCUE_MIN_SCORE` 0,8→0,55 hay `EV_MAX_SENTENCES` 5→9 thì câu trả lời cũ vẫn trúng ⇒ round sau
"tái dùng thể chế cũ", phép đo lever trông như vô hiệu.

Cách làm: `src/core/cache_policy.py` dựng ảnh chụp **chỉ cờ + ngưỡng** từ chính hàm phân giải của module sở
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
không import nổi (`src/core/cache_policy.py` → `src/answer_guard.py` chưa tracked). Vì luật tự trị cấm commit
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

## Chi tiết các dòng không mang nhãn D- (E6/E7, 28-10)

Từ 28-10, [EXPERIMENTS.md](EXPERIMENTS.md) chỉ giữ **tối đa hai câu + số chính** cho mỗi phép đo; chi tiết
(nhãn khoa học, ngưỡng đăng ký trước, cách chọn mẫu, giới hạn diễn giải) nằm ở mục này. Các dòng dưới đây
**không** phải "quyết định" theo nghĩa cột Trạng thái của bảng trên — chúng là **bằng chứng đo** được sổ
này nhận làm nguồn, nên không có ID `D-` và không bị `docs_consistency_check.py` kiểm hình thức bảng.

### C1–C6 — tầng phân loại (nguồn: `tmp/classifier_eval_report.md`, 28-10)

**C1 — tái tính classifier production (Qwen qua `src.core.classifier.classify_query`).** 100 câu của
`logs/classifier/results.json` (ngày 20-10-2026), nhãn v3. Chủ đề: **85/100 = 0,85**, macro-F1 14 lớp
**0,8336**, CI [0,79; 0,91] / [0,7574; 0,9075]. Loại câu hỏi: **81/100 = 0,81**, macro-F1 4 lớp
**0,6944**, CI [0,73; 0,88] / [0,6391; 0,7715]. Đây là **tái chấm dự đoán đã lưu**, không phải chạy lại
model hiện tại; **16/100 câu nằm trong few-shot của prompt** ⇒ điểm có phần may mắn. Chữ ký trọng tài:
**không áp dụng** (không qua `verify.py`). Nhãn khoa học: **KHÔNG KẾT LUẬN** — không có ngưỡng đăng ký
trước cho "classifier đủ tốt", và mẫu 100 câu không phải tập eval hệ thống.

**C2 — baseline cùng cách chia.** Lớp đa số 0,87 accuracy loại; luật từ khóa 0,88 accuracy / 0,9097
macro topic / 0,5301 macro loại; TF-IDF word+char_wb + logistic (C=4) train16: 0,96 accuracy / 0,8694
macro loại. Qwen **thua** từ khóa về macro chủ đề (0,8336 < 0,9097, Δ −0,0760 CI [−0,1657; +0,0198] —
CI chứa 0) và **thua** LR về accuracy loại (0,81 < 0,96, Δ −0,15 CI [−0,24; −0,07]); Qwen **thắng** LR về
macro loại (Δ +0,1693 CI [0,0405; 0,3082], loại 0). Bỏ 16 câu trong prompt: Qwen còn 0,7738 accuracy /
0,5377 macro loại; LR đạt 0,9524 accuracy nhưng **macro 0,2439 và đoán 84/84 một nhãn** ⇒ 0,96 không
chứng minh LR xử lý lớp hiếm. Nhãn khoa học cho "Qwen thắng mọi baseline" = **BÁC (CI loại trừ hiệu ứng)**
ở hai cặp Δ có CI loại 0 theo hướng bất lợi; cặp chủ đề = **KHÔNG KẾT LUẬN** (CI chứa 0).

**C2b — LR có `class_weight=balanced`.** Chia thường: macro loại 0,6454; chia nhóm nguồn: **0,3064**;
từ khóa 0,5301 trên cả hai cách chia (không fit). Balanced **không** cứu được lớp hiếm khi giữ tài liệu
nguồn ngoài train: recall `SO_SANH` 0/10, `THU_TUC` 1/5, `NGOAI_PHAM_VI` 0/4. Không kết luận "balanced tốt
hơn" vì so sánh còn khác đặc trưng và C.

**C3 — độ trễ và router.** Median sklearn **0,00404 s/call**, luật từ khóa **0,000165 s/call**; độ trễ Qwen
production **chưa kiểm chứng** (artifact không lưu timestamp từng call; chỉ có nhịp round ~2,57 s/câu gộp
toàn pipeline). Router r0 gán sai nguồn **244/811 = 0,3008**, CI [0,2688; 0,3329]: **179** ca chủ đề sai,
**65** ca chủ đề đúng nhưng chọn sai nguồn ⇒ lỗi nguồn không đồng nhất với lỗi phân loại; phần lớn hậu quả
thuộc về **lọc cứng** (D-01) chứ không thuộc về nhãn sai.

**C4 —testset_v1 và câu SO_SANH.** Trường `labels.question_type` có trong **0/811** item ⇒ không đếm được
SO_SANH trên tập 811. Trên 100 câu của `logs/classifier`, dự đoán 40 câu là SO_SANH (5 + 11 + 24 theo ba
nguồn nhãn khác nhau); mỗi chủ đề chỉ có **5 id HQ02, HQ09, HQ17, HQ23, HQ72 < 20** ⇒ **không đủ để đăng
ký** thiết kế so sánh có/không tách truy vấn con; ghi thành **hạn chế mẫu** (C5/D4 làm khảo sát định tính
trên đúng 5 câu đó, n = 5, **không kết luận thống kê**).

**C5 — câu thật (`tools/eval/real_questions.jsonl`).** Tệp còn rỗng phần nhãn người ⇒ `eligible_n = 0`,
độ chính xác theo chủ đề trên câu thật = **chưa kiểm chứng**. Runner đã sẵn sàng (`tools/eval/` +
`classification_only`), chỉ chờ tệp có nhãn.

**C6 — định danh "74,43% → 30,97%".**(D1, 28-10) Đây là **macro-F1 trục `question_type` của sklearn v2**,
KHÔNG phải Qwen, không phải topic, không phải trên 811 item. Cùng **147 dòng gold seed đã dedup từ 100 ID
câu gốc** (`TRA_CUU` 128 / `SO_SANH` 10 / `THU_TUC` 5 / `NGOAI_PHAM_VI` 4, macro đúng 4 lớp,
`zero_division=0`). Mốc 0,7443 dùng **StratifiedKFold-5, seed 42, riêng từng trục**; mốc 0,3097 dùng
**GroupKFold-5 nhóm theo `source_document`** (15 tài liệu + nhóm `<ngoai_corpus>` = 16 nhóm) — **không**
nhóm theo nhãn, không chỉ theo ID câu; 741 template vẫn có mặt trong train mỗi fold (78/147 dòng cùng mẫu
bản với fold train ⇒ phần giảm là **hỗn hợp** rò rỉ + dịch miền tài liệu, không quy hết cho rò rỉ). Ở
trục chủ đề: 0,9608 → 0,8376. Δ macro loại của v2-group so với từ khóa **−0,2204 CI [−0,3722; −0,0875]**
⇒ "sklearn thắng baseline khi chia đúng" = **BÁC (CI loại trừ hiệu ứng)**.

### T0 · r17 · P5 · Q4 — tầng truy xuất, nền all-off (25→27-10)

**T0 — băng nhiễu pha sinh.** r5 và r5b là **cùng một cấu hình** chạy hai lượt: `PASS_CORRECT` 14→14/100
(Δ 0,0000, McNemar p=1,0) với CI [−0,03; +0,03] ⇒ **băng nhiễu ±3 item**; refusal 0,69→0,66 CI
[−0,07; +0,01]; fabrication 1/31→1/34 CI [−0,0144; +0,0009]. **5/100 verdict đổi chiều** — hai mức
`PASS_CORRECT` bằng nhau **không** đồng nghĩa cùng tập câu. Dòng này là **dụng cụ**, không phải phép thử
lever ⇒ nhãn khoa học **KHÔNG KẾT LUẬN**. Chữ ký: **v1** cho cả hai lượt.

**r17 — dense nguyên văn trên nền all-off.** 536→**581/700** (+45 câu, Δ +0,0643; 57 tốt lên / 12 xấu đi,
McNemar p=3,74e−08, CI cụm [0,0259; 0,0957]); HUMAN 75→77/97 (Δ +0,0206, CI [−0,1571; +0,1802], p=0,815
⇒ không veto); fidelity **811/811**. Tiêu chí đăng ký trước ở `data/loop/README.md` (mục r17) đạt cả hai
điều kiện ⇒ **ĐẠT**. Đây là **mốc baseline mới** cho mọi lever truy xuất sau này (xem D-37).

**P5 — ma trận nhánh hợp nhất.** Hit@6 trên 700 câu: BM25-only 568, dense đã-fold 202, dense nguyên văn
474, RRF đã-fold 536, **RRF nguyên văn 581**, union nguyên văn **604**. RRF-raw hơn BM25-only **+13 câu
nhưng p=0,0919** (không loại 0) ⇒ giả thuyết "RRF thắng BM25 một mình" = **KHÔNG KẾT LUẬN**; và RRF vẫn
kém union **23 câu** (p=1,52e−05) ⇒ không được nói "RRF là trần của hợp nhất". Artifact **không lưu CI**
cho các so sánh này, chỉ lưu McNemar chính xác.

**Q4 — thử căng PA-49 (fold không lũy đẳng).** Khi **cả hai đầu vào đã fold**, bật/tắt dense nguyên văn
phải cho top-6 giống hệt: **0/811** query khác tập hoặc thứ tự; gold 536→536/700, HUMAN 75→75/97,
`fold_not_idempotent` rỗng. Nhãn **ĐẠT** cho tiêu chí bất biến đã đăng ký trước. Đọc đúng: đây là
**giới hạn phạm vi** của cờ (cờ chỉ có tác dụng khi query chưa fold), **không** phải bằng chứng chống bật
cờ.

### Q5 · D-40 · Oracle (a)/(c) — corpus mới và trần ngữ cảnh

**Q5 — index mới vs index cũ trên phần câu đã neo vàng.** hit@6 505→**504/606** (Δ −1 câu; 27 tốt lên /
28 xấu đi, McNemar p=1,0, CI cụm [−0,0330; +0,0242]). Phạm vi: loại **94/700** câu chưa neo và
**217/606** câu có nhiều hơn một chunk vàng (trung bình 2,183 đích/câu) nên không đọc như gold đơn. Nhãn
= **KHÔNG KẾT LUẬN**; đây là **thăm dò**, chưa mở cổng r19, và không đủ để đánh giá index mới vì neo vàng
còn gãy (PA-17).

**Oracle (a) và (c) — trần ngữ cảnh (80 câu, 38 test / 42 trainpool, 17 nguồn; cả hai nhánh dùng chunk
CŨ, không dùng index mới).** (a) đưa toàn bộ chunk vàng: `PASS_CORRECT` **7/80 = 0,0875** CI [0,0375;
0,1500], refusal 0,8625 CI [0,7875; 0,9375], fabrication 0. (c) thu hẹp còn câu vàng + câu lân cận:
**2/80 = 0,0250** CI [0,0000; 0,0625], refusal 0,95 CI [0,9000; 0,9875]. Hai CI là của **từng nhánh**,
không phải CI của Δ. Kết luận có thể nói: ngay khi ngữ cảnh là câu vàng nguyên văn, 63/80 câu vẫn bị từ
chối, và (c) **không** khá hơn (a). Kết luận **không** được nói: không có ngưỡng đăng ký trước ⇒ không
nhãn ĐẠT/BÁC, và không suy ra "tầng sinh không thể cải thiện" vì đây là mô tả trần, không phải can thiệp.

**r20 — dense nguyên văn ở đầu-cuối (pha sinh).** Ngưỡng đăng ký trước (README mục r20): đạt đồng thời
**p ≤ 0,05**, CI loại 0 **và** |Δ| ≥ 3. Đo: `PASS_CORRECT` 13→**21/100** (Δ +0,08; 11 tốt lên / 3 xấu đi,
CI cụm [0,0115; 0,1636] **loại 0**, McNemar **p=0,0574 > 0,05**); refusal 0,69→0,64; gold-in-context
0,59→0,63; hallucinated 2→2; fabricated 1→1 ⇒ **KHÔNG ĐẠT NGƯỠNG ĐĂNG KÝ** (trượt đúng một điều kiện,
điều kiện p). Mẫu 100 câu ghim từ r5, 18 cụm nguồn, bootstrap seed 20261027, chữ ký **v2** cho cả hai
nhánh.

**r21 — xác nhận trên 300 câu gold mới, nền all-off.** **Đính chính 28-10:** bản trước của mục này ghi
nhánh B vẫn `RUNNING` (281 dòng) và "chưa có `paired_analysis.json`"; các artifact đóng round đã bác
điều đó — hai nhánh đều sinh đủ **300/300 dòng** — A 10:05:41→11:15:13,
B 11:15:18→12:17:48 — `full.jsonl` và `verdicts_full.jsonl` không đổi byte trong lượt xác minh,
`frozen_input_unchanged = true`, `n_system_errors = 0`, `deterministic_verdict_mismatches` 0/0, trọng tài
khai trước và khai lại đều `2911c69f740d`. Round vẫn **KHÔNG HỢP LỆ**: `status.json` đóng với
`INVALID_ANCHOR_DRIFT` và `completed = false`; `final_verification.json` phân loại
`tools/eval/classify_real_questions.py` là **`NEW_FILE_IN_LOCKED_SOURCE_TREE`** (`before = null`,
`after = fdce32ab1149…`, mtime 12:01:53) — tức một **tệp mới** xuất hiện trong cây mã khóa giữa cửa sổ
nhánh B, không phải một tệp bị sửa. **Nguyên nhân thuộc về chính phiên tài liệu này**: runner phân loại
câu thật của mục D3 được tạo lúc 12:01:53, nằm trong khung giờ r21 đang sinh. Theo quy tắc đã ký,
**không** nới khóa sau khi thấy số, **không** sửa analyzer/controller, **không** giữ `completed = false`
làm bằng chứng thiếu item — `generation_complete = true`.

Số chỉ mang tính **mô tả**: `PASS_CORRECT` 32/300 → 63/300 (39 tốt lên / 8 xấu đi, Δ +0,1033),
refusal 213/300 → 182/300, vàng-in-top-6 205/300 → 227/300, câu bịa 3 → 7 ⇒ **veto an toàn** bật
(`fabricated_nonincrease = false`), `supports_enabling_flag = false`, McNemar `mcnemar_p = null`
("Phép thử không đủ điều kiện primary do INVALID_ANCHOR_DRIFT"), cổng `evaluated = false`. CI cụm
[0,0406; 0,1667] (24 cụm, 10.000 lượt, seed 20261028) tồn tại nhưng artifact ghi rõ
`description_only = true` và `used_in_gate = false` ⇒ **không** được trích như bằng chứng.
Băng nhiễu của phép đo này **chưa đo** (ghi chú artifact: ±3 item/100 lịch sử quy ra ±9/300 chỉ mô tả).
Nhãn khoa học = **KHÔNG KẾT LUẬN**; muốn có số phải chạy lại với anchor đóng (không thêm/sửa tệp nguồn
trong khung giờ hai nhánh). `analysis_returncode = 2` và `verification_failed = true` là chữ ký của
lần tắt cổng này, giữ nguyên.

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
