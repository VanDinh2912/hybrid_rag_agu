# STATE — phiên tự trị qua đêm (cập nhật sau mỗi bước; ĐỌC LẠI khi context nén/khởi động lại)

Chi nhánh làm việc: `auto/overnight` (từ HEAD `main`). KHÔNG commit file `src/` dirty của phiên khác.
Ngân sách Gemini đêm nay: ≤14; đã dùng ~7 (T1 (b)); còn ~7 nhưng KHÔNG dùng thêm (b bị chặn PerDay).

## XONG
- T0: r5b đóng, noise_floor.json + ROADMAP P5.15 + docs/reports/T0.md.
- T1: (a) oracle + (c) window xong; (b) n=7/30 bị chặn quota → T1.md cập nhật, KHÔNG chốt bảng quyết định.
- T2 Bước 1: tools/diag/corpus_diacritics.py + per_file.json (corpus 0,178; text 0,786 / OCR 0,033).
- T2 khả thi: easyocr_trial.json (0,73–0,83), cài easyocr+torchvision (venv), pytest vẫn 563 xanh.

## ĐANG LÀM
- T2 Bước 2: viết tools/diag/reocr_vie.py → OCR 13 tệp scan vào cache MỚI .ocr_cache_vie/ (nền, checkpoint).

## VIỆC KẾ TIẾP (theo thứ tự đề bài)
1. T2 Bước 3: đo trước/sau từng tệp + tỉ lệ từ điển Việt + đối chiếu 20 đoạn + Điều/Khoản.
2. T2 Bước 4: build index MỚI vào chroma_db_vie/ (KHÔNG kích hoạt). Nộp PENDING (kích hoạt + chấm lại r0–r5).
3. T3 + T5: viết code + test, MỌI cờ TẮT mặc định, chưa chạy round. pytest xanh.
4. Chạy test TT0–TT3 tương ứng.
5. docs/MORNING_REPORT.md.

## LỆNH TÁI LẬP
- Bảng chẩn đoán: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/diag/corpus_diacritics.py`
- Resume T1 (b) (khi quota reset ~14:00 VN): `PYTHONIOENCODING=utf-8 ENABLE_ANSWER_GUARD=1 ./venv/Scripts/python.exe tools/diag/ablation_generation.py --config b_gemini_top6 --ids-file data/loop/diag/b_gemini_top6/sample_ids.json --limit 30`
- Test: `PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests -q` (kỳ vọng 563 xanh)

## GHI NHỚ BẢO THỦ
- Không sửa gate.py / verify.py / src/text_utils.py / answer_guard (đổi chữ ký trọng tài) → chỉ đề xuất + diff ở PENDING_APPROVAL.
- Không ghi đè chroma_db/ hay rounds đã đóng; index mới chỉ ở chroma_db_vie/.
- Không chạy lại/chấm lại round. Không force-push/reset --hard.
