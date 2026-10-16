# Group 01 — Dữ liệu & Chỉ mục

> Bắt buộc nạp kèm: `base_prompt.md`
> Gộp từ 4 chủ thể cũ: Corpus, Ingest/OCR, Vector DB, Học từ trọng tài (Active Learning)

## Phạm vi được đụng

- `data/corpus/**` (các tầng `Tầng 1`, `Tầng 2`, `cac_file_bo_xung_khac`)
- `ingest.py`, `src/loader.py`, `src/chunking.py`, `src/vector_db.py`
- `chroma_db/` (ghi DUY NHẤT qua quy trình ingest/rebuild), `.ocr_cache/`
- `learn.py`, `data/corpus/ghi_chu_hoc_them.txt`, `logs/learning/learning_log.csv`
- `tmp/` cho mọi script trung gian (chuyển đổi .doc, extract thử, dry-run)

## Sản phẩm cuối

- Corpus sạch: mỗi văn bản một file, đúng tầng, tên file ổn định (không khoảng trắng
  thừa, không trùng). Tên file chính là giá trị `source_document` mà Group 04 tham
  chiếu trong benchmark — ĐỔI TÊN FILE PHẢI BÁO CÁO RÕ.
- Index ChromaDB nạp đầy đủ 3 tầng; schema collection ổn định (bge-m3, metadata
  nguồn, dimension nhất quán). Đổi schema/model embedding phải rebuild toàn bộ
  từ ingest và báo cáo rõ.
- Bài học từ `learn.py` ghi vào `ghi_chu_hoc_them.txt` đúng cấu trúc `Điều N.`,
  không phá bài học cũ; rebuild tái dùng bge-m3 đã nạp, KHÔNG reset thư mục index;
  `logs/learning/learning_log.csv` chỉ append, không ghi đè.

## Vùng cấm

- `data/evaluation/**`, `outputs/evaluation_results.json`, `outputs/evaluation_summary.md`
- `src/retrieval.py`, `src/query_normalizer.py`, `src/text_utils.py`, `src/generator.py`,
  `src/local_slm.py`, `src/pipeline.py`, `main.py` (thuộc Group 02)
- `ui/`, `tests/`, `README.md`, `SYSTEM_ARCHITECTURE*` (thuộc Group 03)

## Verify

- os.walk corpus: không trùng tên, không file rỗng/0 byte, không còn `.doc` legacy
  chưa chuyển (hoặc có lý do rõ trong báo cáo)
- Ingest: thống kê chunk > 0 cho TỪNG tầng; query thử 1 câu trả về chunk hợp lệ
- Collection `count()` khớp log ingest gần nhất; sau `learn.py` count tăng đúng
  số bài học mới
- `ghi_chu_hoc_them.txt` parse đúng cấu trúc `Điều N.`; `learning_log.csv` dòng cũ
  nguyên vẹn
- Không để lại script trung gian ở root; `tmp/` đã xóa sạch
