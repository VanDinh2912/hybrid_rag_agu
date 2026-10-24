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
2. **T5a đang chạy** (r11 → cost probe → r12); **T5b chặn ở PA-1** (corpus chưa chốt).
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
- Test: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q` (kỳ vọng **854** xanh
  — sau kiểm thử T2/T3 ngày 24-10 15:49; 691 sau T6, 677 sau T4/T5a, 610 trước T4). **Phải chạy
  bằng `venv` của app**, không dùng python hệ thống (thiếu `streamlit`/`pypdfium2` → 3 file UI
  lỗi collection dù code không sai).

## GHI NHỚ BẢO THỦ
- Không sửa gate.py / verify.py / src/text_utils.py / answer_guard (đổi chữ ký trọng tài) → chỉ đề xuất + diff ở PENDING_APPROVAL.
- Không ghi đè chroma_db/ hay rounds đã đóng; index mới chỉ ở chroma_db_vie/.
- Không chạy lại/chấm lại round. Không force-push/reset --hard.

## XONG (bổ sung 24-10 15:49 — KIỂM THỬ T2/T3)

- **T3-test XONG.** `tests/test_t3_guardrails.py` **75 test** (A–D của đề bài), xanh; golden cờ TẮT
  `tests/golden/t3_off_30items_head_f492f05.json` (sha file `e59b9ebb…`, sha `core` `344d55cd…`,
  chụp từ `git archive HEAD` = `f492f05` — tại đó pipeline chưa có T3) khớp **từng item/từng khoá**
  với cây hiện tại; mutation check `tmp/mutation_check_t3.py` **7/7 bắt được, 7/7 hoàn nguyên
  byte-identical**. Báo cáo `docs/reports/test_T3.md`; đề xuất mới **PA-14** (Gemini không có nhánh
  T3) + **PA-15** (`DEC_MAX_UNSUPPORTED` dead code) trong `docs/PENDING_APPROVAL.md`.
- **T2-test:** `tests/test_corpus_rebuild.py` **43 test** xanh (ca 1–6); `tools/diag/check_corpus.py`
  đã chạy trên dữ liệu thật → `data/loop/diag/corpus_check/corpus_check.json` +
  `manual_20_segments_new_index.txt` (13:34). **Ca 9 ĐỎ** (48,81% neo nguyên văn gãy; 292 item
  thoái do rebuild; chỉ 14 = 1,76% mất gold thật) và **ca 10 sai tiền đề** (chữ ký trọng tài KHÔNG
  đổi: `9f1179ccab74`; chữ ký DỮ LIỆU index đổi `8031beea81da → 6aa8c0fd9162`).
- **CÒN LẠI của T2-test:** khối in `[7c]` (ký tự ngoài bảng Việt) trong `check_corpus.py::main()`,
  unit test cho `char_is_supported`/`foreign_glyph_report`, mutation check T2, và
  `docs/reports/test_T2.md`.
- **KẾ TIẾP (theo thứ tự đêm):** hoàn tất T2-test còn lại → kiểm thử T5 (reranker, mọi cờ TẮT,
  chưa chạy round) → chạy test TT0–TT3 → dừng.
- Lệnh tái lập nhanh:
  `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -m pytest tests/test_t3_guardrails.py -q`
  · `venv/Scripts/python.exe tmp/mutation_check_t3.py`
  · `PYTHONIOENCODING=utf-8 python -c "from tools.loop.verify import referee_fingerprint as f; print(f())"`
