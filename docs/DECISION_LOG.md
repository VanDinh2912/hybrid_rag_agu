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
| D-12 | 25-10 | Gắn header Chương/Điều/Khoản vào chunk giúp truy xuất | gold@6 0,7400→0,7371, delta **−0,0028 CI [−0,0129; +0,0071]**, McNemar p=0,79 (|delta|=2 < nhiễu 11) | `data/loop/diag/header_paired_r11_r13.json`, `data/loop/rounds/r13/gate_vs_r11_retrieval.json` | **BÁC** trên corpus cũ; corpus T2 = **MỞ** (PA-21) |
| D-13 | 24-10 | Nút thắt dấu tiếng Việt nằm ở pipeline convert PDF; OCR lại bằng EasyOCR `vi` sẽ sửa được | Corpus 17,8%→chunk 19,13% từ có dấu; OCR 3,3%→**82,3%**; index mới 19,13%→**80,29%**; chunk <5% dấu 167→**2** | `data/loop/diag/corpus_diagnostics/{per_file.json,index_before.json,index_after.json}`, `docs/reports/T2.md` | GIỮ artifact `chroma_db_vie/`; **kích hoạt = CHỜ DUYỆT** (PA-1) |
| D-14 | 24-10 | Năng lực Gemini là nút thắt của cấu hình (b) | 25/30 id hợp lệ: `PASS_CORRECT` **16/25 = 64,0%** [44,0; 84,0], refusal 12,0%; 5 id thiếu đúng là **5 id cuối theo thứ tự r5** | `data/loop/diag/b_gemini_top6/summary_dedup_25.json`, `data/loop/diag/b_gemini_top6/bootstrap_ci_25.json`, `data/loop/diag/b_gemini_top6/id_status.json` | **MỞ** — cần đủ 30/30 (PerDay ~14:30) |
| D-15 | 24-10 | Cổng `refusal_rate_bounded` dùng trần tuyệt đối 0,35 đang veto oan | Đề xuất cổng **tương đối** (candidate ≤ baseline + 0,05); 0,35 thành **cảnh báo không phủ quyết**; 8 test trên bản tạm | `tools/diag/gate_refusal_relative_proposal.py`, `tests/test_gate_refusal_relative_proposal.py`, `docs/PENDING_APPROVAL.md` PA-13 | **CHỜ DUYỆT** — `tools/loop/gate.py` **không** đổi |
| D-16 | 24-10 | Tổng điểm trọng số trong báo cáo đánh giá đang sai số học | 0,20·9,2+0,15·8,2+0,20·7,0+0,20·8,5+0,25·4,0 = **7,17 → 7,2** (bản cũ ghi 7,4) | `docs/bao_cao/danh_gia_tong_quan_2026-10-23.md`, `data/loop/diag/metric_ci_r5_full.json`, `data/loop/diag/metric_ci_r7_full.json` | GIỮ 7,2; điểm thành phần = **CHỜ DUYỆT** (PA-23) |
| D-17 | 23→25-10 | Có thể sửa trọng tài/gate giữa chuỗi round mà không phải chấm lại | Chữ ký trọng tài **`9f1179ccab74`** ở mọi round r0…r13 ⇒ không round nào phải chấm lại | `tools/loop/verify.py`, `data/loop/rounds/r10/round_summary_full.json` (`settings`), `data/loop/README.md` mục "Bảy bất biến" | GIỮ (bất biến) |
| D-18 | 23→25-10 | Số test "563 xanh" là mốc chuẩn để so | Sau T2/T3/T5/header: **967 passed** (62,53 s, 25-10 04:1x); sau T7 (`run_chain` + `cache_policy`): **1.004 passed**; sau test biên T6a: **1.005 passed**; sau test T0 "CI chứa ước lượng điểm giải tích": **1.006 passed** (32,54 s, 25-10 11:51) | `tmp/pytest_t5_final.txt`, `tmp/pytest_t4t6_final.txt`, `tmp/pytest_t0_final.txt`, `tests/`, `docs/STATE.md` | GIỮ 967 là mốc lịch sử; **1.006** là mốc hiện tại (D-21/D-22) |
| D-19 | 25-10 | Reranker chỉ khả thi nếu chạy trên GPU, mà không được phá `venv/`/`venv_train/` | `venv_gpu/` riêng (torch 2.14.1+cu126): pytest **967 passed**, VRAM 3.594/4.096 MiB, rerank 2,05 s/item | `data/loop/diag/reranker_cost_gpu.json`, `docs/AUTONOMY_LOG.md` 25-10 02:20 | GIỮ (môi trường tách biệt) |
| D-20 | 25-10 | Ngoại suy chi phí round = chi phí riêng tầng rerank | **Sai**: r12 thật **≈66 phút** (4,74 s/item) = 2,0 s rerank **+ 2,78 s truy xuất nền** ⇒ vượt ngưỡng tự đặt 60 phút | `data/loop/rounds/r12/round_summary_retrieval.json`, `tmp/vram_r12_run.log`, `docs/reports/T5.md` §2.6 | **BÁC** phương pháp; thay bằng `rerank + baseline` |
| D-21 | 25-10 | Cache sinh chỉ băm `{model, temperature, prompt_version, prompt}` ⇒ đổi ngưỡng cứu/từ chối vẫn trúng câu trả lời của thể chế cũ | Thêm `policy` **chỉ khi** thể chế lệch mốc `DEFAULT_CACHE_TOKEN` (**d0b4c6a65f83**); thể chế mặc định giữ khóa cũ từng byte. 26 test mới, mutation **10/10** bắt | `src/cache_policy.py`, `src/generator.py` (2 hàm `_cache_key`), `tests/test_cache_policy.py`, `tmp/mutation_check_cache_policy.py` | GIỮ trong working tree; **CHỜ DUYỆT commit** (PA-26) |
| D-22 | 25-10 | Driver `.sh` viết tay trong `tmp/` là đủ để tái lập một round | Không: thiếu log là mất danh sách env; thay bằng spec JSON + manifest tất định. Chuỗi demo 2×20 item chạy end-to-end (gate ĐẠT + attribute); 11 test, mutation **6/6** bắt | `tools/loop/run_chain.py`, `tools/loop/chains/t5a_reranker.json`, `tests/test_run_chain.py`, `tmp/mutation_check_t7.log` | GIỮ — **đã commit** `79a02e5` |
| D-23 | 25-10 | HEAD tài liệu tái lập được cây đã test 1.006 test | **Sai**: còn 35 file nguồn/công cụ/test chưa tracked (gồm `tools/loop/noise_floor.py`, `src/answer_guard.py`, `src/cache_policy.py`) + 6 file sửa dở; bản `src/generator.py` trong HEAD không có `effective_prompt_version` | `docs/PENDING_APPROVAL.md` PA-26, `docs/STATE.md` | **MỞ** — chờ chọn phương án commit freeze |

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
kiểm chứng bằng fresh clone + `pytest tests -q` kỳ vọng **1.006 passed**.

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
