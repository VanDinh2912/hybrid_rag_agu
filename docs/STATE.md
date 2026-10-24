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

## VIỆC KẾ TIẾP (theo thứ tự đề bài)
1. ~~T2 Bước 3~~ ~~T2 Bước 4~~ ~~T3~~ — xong, xem hai mục XONG.
2. ~~T3: viết code + test + chạy r8/r9~~ — xong, **kết quả âm đã ghi** (P5.18/P5.19, `docs/reports/T3.md`).
3. T5 + TT0–TT3: **CHỜ ĐẶC TẢ (PA-5)**.
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
- Test: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q` (kỳ vọng 563 xanh)

## GHI NHỚ BẢO THỦ
- Không sửa gate.py / verify.py / src/text_utils.py / answer_guard (đổi chữ ký trọng tài) → chỉ đề xuất + diff ở PENDING_APPROVAL.
- Không ghi đè chroma_db/ hay rounds đã đóng; index mới chỉ ở chroma_db_vie/.
- Không chạy lại/chấm lại round. Không force-push/reset --hard.
