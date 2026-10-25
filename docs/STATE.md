# STATE — phiên tự trị qua đêm (cập nhật sau mỗi bước; ĐỌC LẠI khi context nén/khởi động lại)

Chi nhánh làm việc: `auto/overnight` (từ HEAD `main`). KHÔNG commit file `src/` dirty của phiên khác.
Ngân sách Gemini đêm nay: ≤14; lượt hợp lệ 6 (T1 (b); 34 dòng lỗi PerDay không tính quota).
KHÔNG dùng thêm — (b) bị chặn PerDay, đề bài "hết quota thì bỏ phần cần Gemini".

## XONG
- T0: r5b đóng, noise_floor.json + ROADMAP P5.15 + docs/reports/T0.md.
- T1: (a) oracle + (c) window xong; (b) **7/30 id hợp lệ** (58 dòng: 49 error PerDay + 9 dòng hợp
  lệ nhưng trùng 2 id) → T1.md cập nhật theo phép đếm gộp-theo-id, KHÔNG chốt bảng quyết định.
- Công cụ đo lại: `tools/diag/recount_dedup.py` (gộp dòng trùng id; tự kiểm = tái tạo chính xác
  summary của (a)/(c)) và `tools/diag/measure_index.py` (đo từ có dấu trên chunk đã lưu, dùng cho
  cặp `index_before.json`/`index_after.json`).
- T2 Bước 1: tools/diag/corpus_diacritics.py + per_file.json (corpus 0,178; text 0,786 / OCR 0,033).
- T2 khả thi: easyocr_trial.json (0,73–0,83), cài easyocr+torchvision (venv), pytest vẫn 563 xanh.
- T2 Bước 2: tools/diag/reocr_vie.py → 123 trang EasyOCR `vi` vào `.ocr_cache_vie/` (1913 s,
  checkpoint từng trang, 13/13 cache đủ ⇒ ingest KHÔNG rơi về rapidocr).
- T2 Bước 3: tools/diag/quality_check_vie.py → quality_vie.json (OCR 0,033 → 0,823 trên 42.188 từ;
  11/13 tệp ≥0,78; vocab proxy 0,81–0,93) + manual_20_segments.txt (seed 20261024).
- T2 Bước 4: build index MỚI `chroma_db_vie/` = 342/342 chunk (T1 228 / T2 43 / bổ sung 71);
  đo hai index bằng CÙNG script `tools/diag/measure_index.py`: từ có dấu **0,1913 → 0,8029**,
  chunk <5% dấu **167 → 2**, chunk ≥50% dấu **79 → 337**
  (`index_before.json` + `index_after.json`; toàn tệp trước = 0,178 theo `per_file.json`).
  `chroma_db/` + `.ocr_cache/` + pipeline sản xuất KHÔNG đổi. Báo cáo docs/reports/T2.md.
- pytest sau tất cả: **563 passed** (0 code sản xuất bị sửa trong T2).
- docs/MORNING_REPORT.md (báo cáo sáng: xong / bị chặn / cần duyệt / số liệu + nguồn / quyết định tự trị).

## ĐANG LÀM
- Không còn việc tự trị. **PHIÊN ĐÃ DỪNG** tại cổng duyệt; tổng kết ở `docs/MORNING_REPORT.md`
  và **10 đề xuất chờ duyệt** ở `docs/PENDING_APPROVAL.md` (PA-1..PA-10).

## XONG (bổ sung 24-10 — T3)
- **T3 đã chạy xong hai round và KHÔNG ĐẠT tiêu chí đã đăng ký trước.** `r8` = r5 +
  `ENABLE_DECOUPLED_REFUSAL=1`; `r9` = r8 + `ENABLE_EVIDENCE_SELECTION=1`; mỗi round 100/100 item,
  exit 0, **0 lượt Gemini**, chữ ký trọng tài `9f1179ccab74` khớp cả ba round (không round cũ nào
  phải chấm lại). Số: `PASS_CORRECT` 14→**19**→19 (tiêu chí ≥25 ⇒ không đạt), refusal
  0,69→**0,28**→0,57, fabrication 0,0323→**0,0**→0,0, nhưng `PASS_REFUSAL` 17→**2**→14 và
  `FAIL_HALLUCINATED_ON_UNANSWERABLE` 2→**12**→3; p95 19,08→19,93→**33,27 s**. Ba cổng
  (r8-vs-r5, r9-vs-r8, r9-vs-r5) đều **KHÔNG ĐẠT**. Hai cờ **giữ mặc định TẮT**; theo điều khoản đã
  ký, **không** thêm lever thứ ba và **không** chỉnh ngưỡng theo số.
- Code + test đã commit `a8aa042`: `src/refusal_policy.py`, `src/evidence_selection.py`,
  `EXTRACT_ONLY_HEAD`/`effective_prompt_version()` trong `src/generator.py`, `_collect_leg_ranks` +
  móc luật trong `src/pipeline.py`, manifest mới trong `tools/loop/run_round.py`,
  `tests/test_decoupled_refusal.py` (24 hàm/29 case) + `tests/test_evidence_selection.py` (18 case).
  **Toàn repo: 610 passed** (`tmp/pytest_t3_final.txt`, chạy lại SAU hai round; trước T3 là 563).
- Bằng chứng trên đĩa: `data/loop/rounds/r8/` và `data/loop/rounds/r9/`
  (`full.jsonl`, `verdicts_full.jsonl`, `round_summary_full.json`, `gate_vs_*.json`,
  `attribution_vs_*.txt`) + log `tmp/r8_run.log`, `tmp/r9_run.log`. Báo cáo: `docs/reports/T3.md`;
  ROADMAP: **P5.18 / P5.19**; sổ round: `data/loop/README.md` mục "Số đo đã có" (khối r8 + r9).
- Phát hiện đáng giá nhất (để đừng mất công lần sau): trong năm luật **chỉ hai luật bắt**
  (rank + refusal-marker); `no_evidence`/`off_topic_window`/`ungrounded` = 0 vì `overlap` luôn ≥ 0,333
  và `grounding_score` ≡ 1,0 với prompt trích xuất ⇒ tầng ngoài mù với lớp "có căn cứ nhưng lạc đề".

## XONG (bổ sung 24-10 — T4)
- **T4a = phủ định có chủ đích.** `r10` = r5 đổi **duy nhất** model sinh sang `qwen2.5:3b-instruct`
  (Q4, `num_ctx` 8192, 2,3 GB **100% GPU**, không offload): `PASS_CORRECT` 14→**16** nhưng
  McNemar **p = 0,804** và CI delta **[−0,06; +0,10] chứa 0**, `refusal` 0,69→**0,75**, p95
  18,65→**34,12 s (+83%)**. Ngưỡng đã đăng ký trước là "≥ 22/100 và fabrication không tăng" ⇒
  **không có tín hiệu**; điều khoản chạy Qwen3-4B **không kích hoạt**. **Quyết định: giữ
  `qwen2.5:1.5b-instruct` làm model triển khai.** Kiểm "một biến": `tools/diag/one_variable_check.py`
  ⇒ `contexts`/`sources`/`normalized_query`/`labels`/`retrieval_config` identical **100/100**.
- **T4b = dựng pipeline + chi phí, KHÔNG train** (đúng phạm vi user chốt). Bộ dữ liệu
  `data/training/t4b_r5r8r9r10/`: 23 dòng SFT, group-split **theo tài liệu** 13 train / 10 holdout,
  ba assert chống rò rỉ = true, chặn `blocked_test_leak` 134 · `skip_sft_target_not_in_context` 20 ·
  `overrefusal_threshold_only` 17 · trùng id 38. Tokenizer thật: **train min 1.016 / median 1.439
  token ⇒ 13/13 vượt trần 768**. VRAM đo trên card 4,09 GB: **hết chỗ từ 1.024 token**
  (960 → 3.931,0 MiB; 1.024 → 4.156,9; 1.768 → 6.437,9), gradient checkpointing **không giúp**
  (logits của LM head). ⇒ Trần train thật của máy ≈ **1.000 token/dòng**, dữ liệu hiện tại không vừa;
  đường 4-bit bị chặn vì `bitsandbytes` chưa cài và trọng số HF 3B chưa có trên máy.
- **Điều chưa được phép kết luận:** (b) `b_gemini_top6` mới **12/30 id hợp lệ** (PerDay chặn, window
  reset ~14:00 VN) ⇒ **chưa** được nói "năng lực model là nút thắt".
- Bằng chứng: `data/loop/rounds/r10/` (`full.jsonl`, `verdicts_full.jsonl`, `round_summary_full.json`
  có `generator_status`, `gate_vs_r5_full.json`, `gate_vs_r9_full.json`, `t4_stats.json`,
  `triage_report.md`), `data/loop/diag/{one_variable_check.json,t4b_memory_probe.json,
  t4b_memory_probe_len.json}`, log `tmp/r10_run.log`. Báo cáo `docs/reports/T4.md`; ROADMAP **P5.20**;
  đề xuất mới chờ duyệt **PA-11** (4-bit + tải 3B) và **PA-12** (đổi định dạng dòng SFT).
- pytest toàn repo sau tất cả code T4/T5a: **677 passed** (venv app).

## XONG / ĐANG CHẠY (bổ sung 24-10 — T5)
- **5a code + test xong**: `src/reranker.py` (cờ `ENABLE_RERANKER` mặc định TẮT, model
  `BAAI/bge-reranker-v2-m3` đã tải về cache HF 2,2 GB), móc vào `src/pipeline.py` **sau** bonus lọc
  mềm, manifest `retrieval_reranker`; `tests/test_reranker_flag.py` **46 case** chứng minh tắt =
  không đổi hành vi và không gọi `get_reranker`. Chữ ký trọng tài vẫn `9f1179ccab74`.
- **Câu hỏi "bonus 3 hay 12" đã trả lời bằng kiểm định ghép cặp 811 item**
  (`tools/diag/bonus_paired.py` → `data/loop/diag/bonus_paired_r1_r2.json`): r1→r2 giảm
  −0,0257 CI [−0,04; −0,0129], **p = 0,00028**, 21 mất / 3 được, **21/21** là chunk vàng nằm ngoài
  `source_filter` rơi đúng hạng 7–12; family EXACT/TRAP **không đổi** giữa r1/r2/r4 ⇒ con số bonus
  không phải nút thắt. Đã ghi kèm **đính chính** trong `data/loop/README.md`: pha truy xuất **chạm GPU**
  (classifier gọi Ollama 1,5B mỗi câu, `src/classifier.py:581`) và median `latency_seconds` của r2 là
  **2,76 s/item** (không phải 0,28 s) ⇒ 811 item mất ~40–60 phút.
- **ĐANG CHẠY:** `r11` = nền retrieval-only 811 item (bonus 12, quota 0, mọi cờ T3/T4/T5 TẮT).
  Đã kiểm giữa chừng: không `error`, không timeout, `labels` **trùng r2 ở 181/182** item đã chạy
  (1 khác do LLM nhiệt độ 0). Sau r11: `tools/diag/reranker_cost_probe.py` (ngưỡng dừng: ngoại suy
  > 60 phút cho 811 item thì DỪNG và báo) → `r12` = r11 + `ENABLE_RERANKER=1 RERANKER_KEEP_CANDIDATES=1`
  → gate/attribute/bonus_paired → `docs/reports/T5.md`. **5b chưa chạy round** (chờ PA-1).

## XONG (bổ sung 24-10 — T6: làm chắc kết luận trước hội đồng)
Báo cáo `docs/reports/T6.md`. **Toàn bộ sửa gate/trọng tài chỉ là ĐỀ XUẤT diff — `gate.py` không đổi.**
- **6a (PA-13, chờ duyệt):** đề xuất cổng `refusal_rate_bounded` tuyệt đối → **tương đối**
  (`candidate ≤ baseline + GATE_MAX_REFUSAL_RATE_DELTA=0.05`; thiếu baseline = CẤM), trần 0,35 hạ
  thành **cảnh báo không phủ quyết**. Logic + test ở bản tạm: `tools/diag/gate_refusal_relative_proposal.py`
  + `tests/test_gate_refusal_relative_proposal.py` (**8 case, không import gate.py**). Diff đầy đủ ở PA-13.
- **6b (chờ nhãn tay):** `tools/diag/referee_sample.py` trích **60 mẫu phân tầng từ r5** (dung 14 /
  tu_boi_dung 15 / tu_boi_oan 15 / sai 16), **ẩn verdict + mọi trường vàng** khỏi phiếu; khoá chấm ở
  `data/loop/diag/referee_sample_manifest.json`. `tools/diag/referee_agreement.py` tính accuracy +
  **Cohen's kappa** + precision/recall/F1/ma trận khi có nhãn (tự-nhãn-bằng-verdict → 1.0/1.0).
  Phiếu: `data/loop/diag/referee_labeling_r5.{jsonl,md}`. **Hiện `n_filled=0` — chờ user đọc tay.**
- **6c (khung, chờ câu thật):** `tools/eval/real_questions.jsonl` + `score_real_questions.py` (pipeline
  thật + `check_grounding` + cột người đọc "giúp được", `--dry-run` đếm lượt model trước) + README giới
  hạn + `tests/test_score_real_questions.py` (**6 case**, stub không nạp model). `--dry-run` = "0 câu thật".
- **6d (xong):** `tools/diag/metric_ci.py` bootstrap CI 95% (10.000 lượt) cho chỉ số chính, **điểm ước
  lượng dùng đúng công thức `gate.metrics`** (match 100%) → bảng **5.1** trong `danh_gia_tong_quan_2026-10-23.md`
  + `metric_ci_r{5,7}_full.json`. **Tổng điểm trọng số ĐÃ khớp số học: 0.20·9.2+0.15·8.2+0.20·7.0+0.20·8.5+
  0.25·4.0 = 7,17 → 7,2** (không còn 7,4 ngoài dòng đính chính). Muốn ra 7,1 phải dùng bộ điểm CŨ
  (9,0/8,0/…) — là phán chấm điểm, cần user chốt, **không tự đổi điểm thành phần**.
- pytest toàn repo sau T6: **691 passed** (677 + 8 gate + 6 eval).

## VIỆC KẾ TIẾP (theo thứ tự đề bài)
1. ~~T2 Bước 3~~ ~~T2 Bước 4~~ ~~T3~~ ~~T4~~ — xong, xem các mục XONG.
2. **T5-test xong 24-10 16:13** (68 test + mutation 10/10, mọi cờ TẮT, chưa chạy round; xem mục
   XONG cuối file). **T5a:** r11 nền retrieval-only đã khởi chạy trước đó; phiên này **không** kiểm
   tiến trình nền — cần xác nhận r11/r12 trước khi chạy tiếp. **T5b chặn ở PA-1** (corpus chưa chốt)
   và PA-18 (wire + build index).
3. **T1(b): resume tới 30 id sau window PerDay ~14:00 VN**, giữ nguyên `sample_ids.json`,
   ≤14 lượt/ngày, checkpoint từng lượt.
4. Hai hướng tiếp theo của tầng sinh đều **chờ duyệt, chưa tự làm**: PA-9 (luật ngoài phủ trên
   prompt cũ, cần round `r10`) và PA-10 (probe 0 lượt sinh cho tín hiệu "căn cứ có trả lời được
   câu hỏi không"). Nợ cũ vẫn treo: PA-1 (kích hoạt `chroma_db_vie/`), PA-3 (#23 sửa cổng),
   PA-8 (commit freeze — nay rounds = 48 MB, r0…r9, vẫn 0 file tracked).

## LỆNH TÁI LẬP
- Bảng chẩn đoán: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/corpus_diacritics.py`
- OCR lại (resume, không ghi đè cache gốc): `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/reocr_vie.py --dpi 200`
- Đo trước/sau: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/quality_check_vie.py`
- Build index mới (KHÔNG kích hoạt): `PYTHONIOENCODING=utf-8 CHROMA_PERSIST_DIR=./chroma_db_vie OCR_CACHE_DIR=./.ocr_cache_vie ./venv/Scripts/python.exe ingest.py`
- Đếm lại một cấu hình ablation theo id (gộp dòng trùng, không gọi model):
  `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/recount_dedup.py --config b_gemini_top6 [--compare-with-summary]`
- Đo từ có dấu trên một ChromaDB index (chỉ đọc):
  `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/measure_index.py --db ./chroma_db_vie --out data/loop/diag/corpus_diagnostics/index_after.json`
- Resume T1 (b) (khi quota reset ~14:00 VN): `PYTHONIOENCODING=utf-8 ENABLE_ANSWER_GUARD=1 ./venv/Scripts/python.exe tools/diag/ablation_generation.py --config b_gemini_top6 --ids-file data/loop/diag/b_gemini_top6/sample_ids.json --limit 30`
- Test: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q` (kỳ vọng **957** xanh
  — sau kiểm thử T5 ngày 24-10 16:13; 889 sau T2-test, 691 sau T6, 677 sau T4/T5a, 610 trước T4). **Phải chạy
  bằng `venv` của app**, không dùng python hệ thống (thiếu `streamlit`/`pypdfium2` → 3 file UI
  lỗi collection dù code không sai).

## GHI NHỚ BẢO THỦ
- Không sửa gate.py / verify.py / src/text_utils.py / answer_guard (đổi chữ ký trọng tài) → chỉ đề xuất + diff ở PENDING_APPROVAL.
- Không ghi đè chroma_db/ hay rounds đã đóng; index mới chỉ ở chroma_db_vie/.
- Không chạy lại/chấm lại round. Không force-push/reset --hard.

## XONG (bổ sung 24-10 — KIỂM THỬ T2/T3)

- **T3-test XONG.** `tests/test_t3_guardrails.py` **75 test** (A–D của đề bài), xanh; golden cờ TẮT
  `tests/golden/t3_off_30items_head_f492f05.json` (sha file `e59b9ebb…`, sha `core` `344d55cd…`,
  chụp từ `git archive HEAD` = `f492f05` — tại đó pipeline chưa có T3) khớp **từng item/từng khoá**
  với cây hiện tại; mutation check `tmp/mutation_check_t3.py` **7/7 bắt được, 7/7 hoàn nguyên
  byte-identical**. Báo cáo `docs/reports/test_T3.md`; đề xuất mới **PA-14** (Gemini không có nhánh
  T3) + **PA-15** (`DEC_MAX_UNSUPPORTED` dead code) trong `docs/PENDING_APPROVAL.md`.
- **T2-test XONG (24-10 15:57).** `tests/test_corpus_rebuild.py` **78 test** xanh (ca 1–6 + 35 test
  ký tự ngoài bảng Việt); `tools/diag/check_corpus.py` chạy dữ liệu thật → khối mới **[7c]**:
  **19** ký tự lạ/324.979 (2 loại: `U+208A ₊` ×16, `U+20AC €` ×3), JSON
  `data/loop/diag/corpus_check/corpus_check.json` + 20 đoạn `manual_20_segments_new_index.txt`;
  mutation `tmp/mutation_check_t2.py` **5/5 bắt được, 5/5 hoàn nguyên byte-identical**; toàn repo
  **889 passed** (`tmp/pytest_t2_final.txt`). Báo cáo `docs/reports/test_T2.md`.
  **Ca 9 ĐỎ** (389/797 = 48,81% neo nguyên văn gãy; 292 id regression lưu ở
  `gold_coverage.paired.regressed_ids`; chỉ 14 = 1,76% mất gold thật); ca 10: chữ ký trọng tài
  KHÔNG đổi `9f1179ccab74`, chữ ký DỮ LIỆU index đổi `8031beea81da → 6aa8c0fd9162` (đúng).
  Cổng chất lượng: 23/26 tệp tốt, 3 tệp khoảng trống vẫn nằm trong index (2 kế hoạch + TB16 0,000
  dấu). **Tiêu chí nghiệm thu T2 CHƯA ĐẠT** vì mục 9 đỏ; mục 8 chờ người duyệt 20 đoạn.
  Đề xuất mới: **PA-16** (nối guard `plan_index_write` vào `ingest.py` — hiện vẫn `rmtree`) và
  **PA-17** (re-anchor 292 `gold_sentence` trước khi chấm lại); PA-7 bổ sung TB16.
- **KẾ TIẾP (theo thứ tự đêm):** kiểm thử T5 (reranker + contextual header, mọi cờ TẮT, chưa chạy
  round) → chạy test TT0–TT3 → dừng.
- Lệnh tái lập nhanh:
  `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests/test_corpus_rebuild.py -q`
  · `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/check_corpus.py`
  · `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t2.py`
  · `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests/test_t3_guardrails.py -q`
  · `venv/Scripts/python.exe tmp/mutation_check_t3.py`

## XONG (bổ sung 24-10 16:13 — KIỂM THỬ T5)

- **T5-test XONG phần unit.** `tests/test_t5_reranker_contract.py` **26 test** (mục 1–6, fake
  cross-encoder) + `tests/test_t5_contextual_header.py` **42 test** (mục 7–10) = **68 test xanh**;
  toàn repo **957 passed** (`tmp/pytest_t5_final.txt`, 26,84 s; trước mutation
  `tmp/pytest_t5_before_mutation.txt` 957 passed). Không sửa test cũ, không sửa
  `src/reranker.py`/`src/pipeline.py`, không đổi trọng tài.
- **Module mới build-time** `src/contextual_header.py`: cờ `ENABLE_CONTEXTUAL_HEADER` mặc định
  **TẮT**; hàm thuần, không ghi đĩa/gọi model; header = `[title] - [Chương] - [Điều] - [Khoản] -
  [Điểm]` + hậu tố `(phần i/n)`, nhãn dự phòng `Phần mở đầu/Bảng biểu/Phụ lục/Toàn văn`, không bao
  giờ phát `None`/`[]`; thân chunk nguyên văn; idempotent; guard `ensure_separate_index_target`
  chặn `chroma_db`/`chroma_db_vie` + thư mục cha. **CHƯA nối vào `ingest.py`, CHƯA build index.**
- **Golden mục 1:** dùng lại `tests/golden/t3_off_30items_head_f492f05.json` (sha file
  `e59b9ebb…`, sha `core` `344d55cd…`); `pipeline.run` 30 item khớp **từng item/từng khoá**.
- **Mutation check** `tmp/mutation_check_t5.py`: **10/10 bắt được, 10/10 hoàn nguyên byte-identical**
  (log `tmp/mutation_check_t5.log`); riêng 4 đột biến trên file dirty của phiên khác
  (`src/reranker.py`, `src/pipeline.py`) đã kiểm SHA-256 sau khôi phục.
- **Số liệu header trên index thật (chỉ đọc):** `chroma_db` 361 chunk = article 232 (64,27%) +
  preamble 21 + table 1 + whole 107; chapter 9 (2,49%). `chroma_db_vie` 342 = article 227 (66,37%)
  + preamble 20 + table 1 + whole 94; chapter 18 (5,26%). Digest trước/sau không đổi
  (`chroma_db` `c68623f7…`, `chroma_db_vie` `15dab0c9…`).
- **Hai điểm chưa khớp câu chữ đề bài:** mục 5 (đề bài đòi lùi RRF + cảnh báo; thiết kế đã đăng ký
  cấm lùi thầm ⇒ test ghim hành vi ném lỗi) và mục 10 (chưa có index T5b thật). Cả hai ghi ở
  **PA-18**, báo cáo `docs/reports/test_T5.md`. **Tiêu chí "kiểm lại gold@6 cấu hình TẮT so với
  round đã đóng" CHƯA chạy** (đêm quy định chưa chạy round) ⇒ nghiệm thu T5 đầy đủ còn treo.
- Lệnh tái lập nhanh:
  `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests/test_t5_reranker_contract.py tests/test_t5_contextual_header.py -q`
  · `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tmp/mutation_check_t5.py`
- **KẾ TIẾP (đúng thứ tự đêm):** chạy test tương ứng TT0–TT3 (T0/T1/T2/T3) → viết
  `docs/MORNING_REPORT.md` → dừng. Không chạy round, không dùng Gemini.
- **TT0–TT3 chạy cuối phiên:** `tests/test_noise_floor.py` (21) + `tests/test_ablation_generation.py`
  (24) + `tests/test_corpus_rebuild.py` (78) + `tests/test_t3_guardrails.py` (75) =
  **198 passed** trong 10,28 s (`tmp/pytest_tt0_tt3_final.txt`).
- **`docs/MORNING_REPORT.md` đã cập nhật** mục "PHIÊN TIẾP 24-10" ở đầu (bản ghi đêm đầu giữ
  nguyên phía dưới). **PHIÊN DỪNG** tại đây theo thứ tự đêm: không chạy round, không gọi Gemini.

## XONG (24-10 23:10 — T1(b) 25/30 + kiểm tra mẫu lệch)

- Resume (b): 12 → **25/30 id hợp lệ**; 5 id còn lại bị PerDay chặn (cửa sổ kế tiếp ~14:30
  25-10; lần chặn cuối báo `Please retry in 15h22m`). n=25: PASS_CORRECT **16 (64,0%,
  bootstrap 95% [44,0; 84,0])**, refusal **3/25 (12,0%)**, fabrication **5/22 (22,7%)**,
  FAIL_INCOMPLETE 1. Nguồn: `data/loop/diag/b_gemini_top6/summary_dedup_25.json`,
  `bootstrap_ci_25.json` (seed 20261023, 10.000 lượt).
- **Mẫu lệch:** 5 id thiếu đúng là **5 id cuối theo `r5_order`** (82–97); 25 id hợp lệ phủ
  1–81. family/`contexts_chars` không tách được khỏi hiệu ứng thứ tự; `gold_rank` cân bằng
  (median 2 cả hai). ⇒ (b) hiện là **tiền tố 25/30 theo thứ tự r5**, chưa ngoại suy;
  **chưa được kết luận "năng lực model là nút thắt"** (điều kiện user: đủ 30/30).
- Công cụ mới (chỉ đọc): `tools/diag/t1b_id_status.py` → `id_status.json` (đủ 30 dòng:
  family, r5_order, contexts_chars, gold_rank, status, error_kind).
- 5 FAIL_FABRICATED: 2 ca chỉ vì proper-noun `Theo Bản` (PA-2); 3 ca token pháp lý
  (`Theo Thông`+`mục 3`, `Khoản 1`, `Mục 2`) **chưa kiểm chứng tay** — nếu là dương-giả thì
  fabrication thật ≤3/22. Không sửa trọng tài.
- `rows.jsonl` 96 dòng, 28 hợp lệ nhưng 25 id duy nhất (3 id trùng do tiến trình chồng nhau:
  `N121989377006900`, `O10235702435549`, `T24199159682252`); phép đếm gộp giữ dòng đầu.
- **Thao tác vận hành:** đã dừng 2 tiến trình (b) chạy chồng + probe reranker để tránh gọi
  Gemini trùng; sau đó gọi từng lượt foreground (không dùng nền) vì nền bị kill im lặng.
- Lệnh resume đúng 5 id còn lại (sau khi cửa sổ mở):
  `PYTHONIOENCODING=utf-8 GEMINI_MODEL=gemini-3.8-flash ENABLE_ANSWER_GUARD=1 QWEN_FALLBACK=0 venv/Scripts/python.exe -u tools/diag/ablation_generation.py --config b_gemini_top6 --ids-file data/loop/diag/b_gemini_top6/sample_ids.json --force --limit 5`

## XONG (24-10 23:09 — kiểm tay 5 ca fabrication, cập nhật PA-2, thêm PA-20)

- **Kiểm tay 5/5 ca `FAIL_FABRICATED` của T1(b)** (đối chiếu đúng 6 ngữ cảnh r5 + chunk gốc
  `chroma_db`, chỉ đọc): **không ca nào bịa dữ kiện**.
  - C10492769338965: `Theo Bản` dương giả; nội dung **đúng** (ELO 10, chunk 330).
  - C145524027648409: `Theo Bản` dương giả; nội dung **SAI** (chunk 329 ghi ELO 1, model trả
    ELO 9). `required_entities=['1']` nhưng `_answer_covers_gold` trả True vì khớp "B1"/"2021".
  - O103189525480643: `Theo Thông` dương giả; `mục 3` **trỏ sai mục** (c) nằm dưới "GHI CHÚ",
    chunk 288); dữ kiện 2024-2025 đúng.
  - O112922606788277: `Khoản 1` **có căn cứ** ("1. Quy chế…" ngay dưới Điều 16, chunk 83);
    2570 đúng.
  - Y231035235702969: `Mục 2` là diễn giải của "2. Hồ sơ xin học" (chunk 271); nội dung đúng;
    lỗi khác: citation cuối trỏ sang tệp 163-tb (ACB).
- **Số chính thức KHÔNG đổi**: PASS_CORRECT 16/25 = 64%, fabrication 5/22 = 22,7%. Kiểm tay
  (không CI): 20/25 = 80% đúng nội dung; 18/25 = 72% nếu chấm khắt khe cả trích dẫn.
  `docs/reports/T1.md` mục "Kiểm tay 5 ca FAIL_FABRICATED".
- **PA-2 cập nhật**: 3/25 cờ proper là dương giả (vượt ngưỡng tự đặt ≥2/30) + **diff đề xuất**
  stopword `_PROPER_RUN_STOPWORDS` trong `src/answer_guard.py`; **chưa áp dụng**.
- **PA-20 mới**: `_answer_covers_gold` cho required_entities số ngắn khớp oan trong "B1"/"2021";
  diff strict `(?<![\w])…(?![\w])`; ước lượng chỉ đọc: r5 1/14 PASS, r10 2/16 PASS bị hạ,
  r8/r9 0; **chưa sửa** vì đổi chữ ký trọng tài + phải chấm lại r5 (baseline T3/T4).
- **Không dùng Gemini** (PerDay còn chặn tới ~14:30 25-10); không chạy round; không build index;
  không xóa file. 5 id T1(b) còn lại giữ nguyên lệnh resume trong mục trên.
- **Audit tái lập PA-20 (mới, chỉ đọc):** `tools/diag/referee_strict_number_audit.py` →
  `data/loop/diag/referee_strict_number_audit.json`; 5 test trong
  `tests/test_referee_strict_number_audit.py`. Chấm tay 3 dòng PASS bị strict hạ: không phải cả
  3 là PASS oan (1 số trang lẫn gold, 1 refusal không đổi verdict, 1 mẫu "20…" điền hợp lệ) ⇒
  **không áp strict một mình**, phải sửa metadata required_entities trước.
- `pytest tests -q`: **962 passed** (957 cũ + 5 test audit; 23,59 s).

## XONG (24-10 23:12 — đo thêm phương án hạ max_length 256 cho PA-19)

- Chạy `tools/diag/reranker_cost_only.py` với `RERANKER_MAX_LENGTH=256`, 5 item × 20 cặp
  (NGOÀI thiết kế đăng ký, chỉ để trả lời PA-19): nạp 15,17 s (model 7,98 s); median
  **9,294 s/item** (mean 9,248 · p95 9,407 · max 9,423); ngoại suy 811 item = **125,0 phút
  (2,08 giờ)**; RAM trống sau nạp 1.646,6 MiB. Nguồn: `data/loop/diag/reranker_cost_only_256.json`.
- Kết luận: hạ 256 cắt ~50% thời gian chấm nhưng **vẫn vượt luật 60 phút** ⇒ không áp dụng,
  không đổi thiết kế; PA-19 giữ nguyên khuyến nghị (b) giải phóng RAM rồi chạy lại probe chính
  thức. Cập nhật `docs/reports/T5.md` §1/§2.2/§3 và PA-19.
- Không Gemini, không chạy round, không sửa code/trọng tài/gate, không xóa file.

## XONG (25-10 02:15 — khởi động lại: đóng sổ r13 / T5b trên corpus cũ)

- r13 (index `chroma_db_headers_old`, retrieval-only, 811/811, 0 lỗi, xong 00:07) **đã chấm**:
  gold@6 0,7400 → 0,7371, delta ghép cặp **−0,0028 CI [−0,0129; +0,0071]**, McNemar 8 mất/6 được
  **p = 0,79**; EXACT 0,2115→0,2308 (+1 item); HUMAN 0,8144 không đổi; gate retrieval 6/6 ĐẠT
  (= không lùi, KHÔNG phải cải thiện). ⇒ **5b âm trên corpus cũ**, `ENABLE_CONTEXTUAL_HEADER` giữ TẮT.
  Nguồn: `data/loop/diag/header_paired_r11_r13.json`, `data/loop/rounds/r13/gate_vs_r11_retrieval.json`;
  báo cáo `docs/reports/T5.md` §2.5.
- Đề xuất mới **PA-22** (manifest round ghi `chroma_persist_dir`); PA-21 (neo gold corpus T2) đã ghi từ 23:35.
- pytest: **967 passed** (962 + 5 `tests/test_header_index_build.py`).
- Gemini đêm nay: **0 lượt** (PerDay mở lại ~14:30 25-10).

## VIỆC KẾ TIẾP (sau 25-10 02:15)
- Không còn việc tự trị trong thứ tự đêm. **PHIÊN DỪNG.**
- Sau ~14:30 25-10: resume 5 id T1(b) bằng lệnh ở mục "XONG (24-10 23:10)".
- Chờ duyệt: PA-1, PA-19 (r12), PA-21, PA-22 và các PA cũ.
- Lệnh tái lập r13: `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/diag/bonus_paired.py --baseline r11 --candidate r13 --third "" --out data/loop/diag/header_paired_r11_r13.json`
  · `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/loop/gate.py --candidate r13 --baseline r11 --phase retrieval`

## ĐANG LÀM (25-10 02:55 — T5 giao lại: chạy 5a trên GPU bằng venv riêng)

- Đề bài T5/T6 được giao lại. T6 (6a–6d) **đã có đủ artifact từ 24-10**; phiên này bổ sung:
  CI cho chỉ số **truy xuất** vào bảng 5.1 báo cáo đánh giá + khối ĐÍNH CHÍNH 25-10 + **PA-23**
  (bốn dòng tự chấm đã cũ; điểm KHÔNG tự đổi). Commit `875a313`.
- 5b đã chấm xong ở commit `c0b23f2` (r13: delta −0,0028 CI chứa 0, p = 0,79 ⇒ không tín hiệu).
  Phiên này chạy thêm `attribute.py` r11 và r13 (trước/sau): FAIL_RETRIEVAL 182→184,
  `filter_blocked_wrong_topic` 68→67, `filter_blocked_wrong_table` 20→20, `ranking_no_filter`
  57→59, `ranking_despite_filter` 37→38 (ghi vào `data/loop/rounds/r11/r13/attribution_retrieval.json`).
- **5a:** dựng `venv_gpu/` MỚI (torch 2.14.1+cu126 + `requirements-lock.txt` + các gói còn thiếu
  đúng version của `venv/`; chỉ khác nhóm easyocr/opencv — không ảnh hưởng đường chạy round).
  `venv/` và `venv_train/` **không bị sửa**. pytest trên `venv_gpu`: **967 passed** (24,01 s).
  Embedding vẫn CPU (ghim ở `src/vector_db.py:60`) ⇒ r12 chỉ khác r11 ở reranker.
  Đang chạy probe chi phí GPU: `RERANKER_DEVICE=cuda` (max_length 512, pool 20, batch 4 — đúng thiết kế)
  → `data/loop/diag/reranker_cost_gpu.json`, log `tmp/r12_gpu_probe.log`.
  VRAM quan sát được khi nạp reranker: **3.594/4.096 MiB, util 100%** (Ollama chưa nạp lúc đó).
- **Luật giữ nguyên:** probe ngoại suy > 60 phút cho 811 item ⇒ DỪNG, không chạy r12, báo PA-19.
- Gemini: **0 lượt**.

## XONG (25-10 04:1x — r12 chấm xong + ĐÍNH CHÍNH chi phí; mục "ĐANG LÀM 02:55" ở trên đã kết thúc)

- **r12 chạy 02:53 → 03:58, 811/811, 0 lỗi, chữ ký `9f1179ccab74`.** gold@6 **0,7400 → 0,6686**,
  delta ghép cặp **−0,0714, CI [−0,1014; −0,0414]**, McNemar **83 mất / 33 được, p = 3,9e−06**;
  `FAIL_RETRIEVAL` 182 → 232; EXACT 0,2115 → 0,0385; TRAP → 0; NUMERIC 0,4375 → **0,4821**;
  neo HUMAN 0,8144 → 0,7010; gate **6/8 kiểm tra vi phạm**. Trần oracle pool 20 = **0,8871**
  (EXACT 0,6154). Nguyên nhân kiểm được: `src/reranker.py:score_pairs` chấm `fold(query)` với
  passage còn dấu (probe 30 item: 0/30 vs 28/30 khi bỏ fold, chi phí như nhau).
  Cờ `ENABLE_RERANKER` **giữ TẮT**; sửa + r14 = **PA-25** (chờ duyệt, 0 Gemini).
- **Đính chính đã ghi (không sửa số liệu, chỉ sửa chữ):** chi phí r12 là **≈66 phút / median
  4,74 s/item** (tổng `latency_seconds` 3.855,5 s; `retrieval.jsonl` mtime 03:58:33), **không phải**
  "45 phút / 4,66 s"; ngoại suy cho phép chạy trước đó **bỏ sót truy xuất nền** (2,0 + 2,78 ≈ 4,8
  s/item) ⇒ thực tế **vượt ngưỡng tự đặt 60 phút**. Ghi ở `docs/reports/T5.md` §2.6 (blockquote
  ĐÍNH CHÍNH), §2.7, §3.2–3.3, §5; `docs/MORNING_REPORT.md`; `docs/PENDING_APPROVAL.md` (PA-19,
  PA-25); `docs/AUTONOMY_LOG.md` 25-10 04:0x. Số đo hiệu quả **không đổi** vì đính chính chỉ ở
  chi phí. Cũng đã sửa "5/7 vi phạm" → **6/8 kiểm tra** (đếm lại từ `gate_vs_r11_retrieval.json`).
- **Sổ round `data/loop/README.md` "Số đo đã có":** thêm 4 khối **r10, r11 (nền), r12, r13** kèm
  nguồn file cụ thể — trước đó sổ dừng ở r9 dù r10–r13 đã chạy.
- Gemini đêm nay: **0/14 lượt**. T1(b) vẫn 25/30 id, chờ cửa sổ PerDay ~14:30 25-10.
- **KẾ TIẾP:** T7 (đang làm) — PA-24 đã có kiểm kê tmp/ (chờ duyệt, chưa xoá); còn
  `docs/DECISION_LOG.md`, `tools/loop/run_chain`, policy key trong cache key tầng sinh
  (`src/generator.py` đang dirty của phiên khác ⇒ phải làm cực cẩn thận, xem PA-8), rồi pytest +
  README/ROADMAP + "Giới hạn thật lòng".
