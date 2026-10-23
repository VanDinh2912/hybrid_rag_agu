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

## ĐANG LÀM
- Kết phiên: docs/MORNING_REPORT.md. T3/T5/TT0–TT3 **bị chặn — thiếu đặc tả** (PA-5).

## VIỆC KẾ TIẾP (theo thứ tự đề bài)
1. ~~T2 Bước 3~~ ~~T2 Bước 4~~ — xong, xem mục XONG.
2. T3 + T5: viết code + test, MỌI cờ TẮT mặc định, chưa chạy round → **CHỜ ĐẶC TẢ (PA-5)**.
3. Chạy test TT0–TT3 tương ứng → **CHỜ ĐẶC TẢ (PA-5)**.
4. docs/MORNING_REPORT.md.

## LỆNH TÁI LẬP
- Bảng chẩn đoán: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/corpus_diacritics.py`
- OCR lại (resume, không ghi đè cache gốc): `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/reocr_vie.py --dpi 200`
- Đo trước/sau: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/quality_check_vie.py`
- Build index mới (KHÔNG kích hoạt): `PYTHONIOENCODING=utf-8 CHROMA_PERSIST_DIR=./chroma_db_vie OCR_CACHE_DIR=./.ocr_cache_vie ./venv/Scripts/python.exe ingest.py`
- Resume T1 (b) (khi quota reset ~14:00 VN): `PYTHONIOENCODING=utf-8 ENABLE_ANSWER_GUARD=1 ./venv/Scripts/python.exe tools/diag/ablation_generation.py --config b_gemini_top6 --ids-file data/loop/diag/b_gemini_top6/sample_ids.json --limit 30`
- Test: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q` (kỳ vọng 563 xanh)

## GHI NHỚ BẢO THỦ
- Không sửa gate.py / verify.py / src/text_utils.py / answer_guard (đổi chữ ký trọng tài) → chỉ đề xuất + diff ở PENDING_APPROVAL.
- Không ghi đè chroma_db/ hay rounds đã đóng; index mới chỉ ở chroma_db_vie/.
- Không chạy lại/chấm lại round. Không force-push/reset --hard.
