# Group 04 — Kiểm chứng & Cấu hình

> Bắt buộc nạp kèm: `base_prompt.md`
> Gộp từ 4 chủ thể cũ: Câu hỏi/Benchmark, Đánh giá (runner), Kiểm thử, Cấu hình & phụ thuộc

## Phạm vi được đụng

- `data/evaluation/**` (`benchmark_*.json`, `benchmark_*.md`, `reference/`,
  `manual_test_checklist.md`)
- `src/evaluation.py`, `benchmark_chunking.py`, `logs/benchmark/`,
  `outputs/evaluation_results.json`, `outputs/evaluation_summary.md`
- `src/evaluate_classifier.py`, `src/analyze_ab.py`, `logs/classifier/` (P2.3/P4.3:
  đo accuracy phân loại + phân tích A/B), `outputs/ab_results_*.json`,
  `outputs/ab_comparison.md`, `outputs/figures/`
- `tests/**` (kể cả `conftest.py`), `.pytest_cache/`
- `.env`, `.env.example`, `requirements.txt`, `requirements-lock.txt`, `venv/`
- `tmp/` cho bản nháp theo batch, slice khi merge, script sinh câu hỏi

## Sản phẩm cuối

- `data/evaluation/benchmark_{N}_questions.json`: mỗi câu hỏi đúng 12 khóa,
  không thêm/bớt/đổi tên (`id, category, tier, in_corpus, source_document,
  raw_query, normalized_query, expected_answer, expected_citations,
  ground_truth_answer, ground_truth_citation, supplement_if_wrong`), với ràng buộc:
  - `id`: `Q01`…`Q{N}` liên tục, duy nhất; cấm id tạm (`Q_NEW_*`) trong file cuối
  - `tier`: chỉ nhận `"Tầng 1"`, `"Tầng 2"`, `"cac_file_bo_xung_khac"`
  - `source_document`: phải tồn tại thật trong `data/corpus/**` (os.walk trước khi ghi)
  - `raw_query`: không trùng trong file, không trùng benchmark cũ trong `data/evaluation/`
  - `in_corpus=true` => có `ground_truth_answer` + `ground_truth_citation` dẫn Điều/mục cụ thể
  - Câu hỏi chỉ tồn tại MỘT nơi: file benchmark cuối (không nhúng vào script,
    không giữ nháp song song sau merge)
- `evaluation_results.json` + `evaluation_summary.md` chỉ do Group này sinh/sửa
- Bộ test xanh; test mới cho hành vi mới. CẤM sửa `src/**` chỉ để test pass —
  bug ở src phải báo Group 01/02 (tùy module lỗi)
- `.env.example` đủ mọi key mà code đọc qua `os.getenv` (không chứa giá trị thật);
  `.env` không bao giờ commit; `requirements-lock.txt` khớp `requirements.txt`

## Vùng cấm

- `data/corpus/`, `chroma_db/` (chỉ đọc), `src/**` trừ `src/evaluation.py`, `ui/`
- `logs/learning/learning_log.csv` (Group 01), `logs/feedback/user_feedback.json`
  (Group 03), `README.md`/`SYSTEM_ARCHITECTURE*` (Group 03)
- Hạ tiêu chí verify để cho qua; commit `.env` hay file chứa key thật

## Verify

- Benchmark: `json.load(..., encoding='utf-8')` thành công; 100% đúng 12 khóa;
  id duy nhất liên tục `Q01`→`Q{N}`; `raw_query` duy nhất (trong file và so với
  benchmark cũ); `source_document` 100% tồn tại trong corpus
- `pytest` xanh 2 lần liên tiếp; không test bị skip ngầm không lý do;
  không hardcode đường dẫn tuyệt đối trong test
- `pip check` (hoặc import thử module chính) không lỗi; mọi key `os.getenv`
  có mặt trong `.env.example`; `.env` nằm trong `.gitignore`
- `tmp/` đã xóa sạch
