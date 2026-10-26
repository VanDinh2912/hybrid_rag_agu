# P2.2 — Unit test cho classifier (offline)

> Giai đoạn 2 · Nhóm playbook: 04 (tests/) · Thời gian: 1 ngày

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

`tests/test_classifier.py` phủ đủ các nhánh của `src/classifier.py`, chạy 100% offline (không mạng, không cần Ollama thật).

## Ngữ cảnh cần đọc trước

- `src/classifier.py` (mới viết ở P2.1)
- `tests/test_local_slm.py`, `tests/test_pipeline.py` — phong cách fake/monkeypatch hiện có của repo.

## Việc cần làm

Viết test phủ các nhóm:

1. **Parser JSON:** JSON hợp lệ; JSON bọc markdown fence; text thừa trước/sau; JSON hỏng hoàn toàn.
2. **Guardrail:** nhãn lạ (không thuộc 14 chủ đề / 4 loại) → rơi xuống lớp từ khóa; từ khóa không khớp → default (`topic=None`, `question_type="TRA_CUU"`).
3. **So khớp không dấu:** chủ đề có/không dấu khớp nhau qua `fold()`.
4. **Suy giảm mềm:** mock Ollama ném lỗi / timeout → trả fallback, không crash; đo rằng không retry vô hạn.
5. **Few-shot:** `build_few_shot_examples()` chứa đủ 14 chủ đề + 4 loại; các id ví dụ tồn tại thật trong v3 (đọc v3 trong test — offline OK).
6. **Schema:** `classify_query` trả đúng 3 khóa với kiểu dữ liệu đúng.

Mọi mock không gọi mạng.

## Ràng buộc

- Nhóm 04 (tests/). Chỉ tạo `tests/test_classifier.py` + được phép sửa `src/classifier.py` nếu test bắt được bug (nêu rõ từng sửa trong báo cáo).
- Giữ tổng thời gian bộ test ngắn (không sleep thật — monkeypatch timeout).

## Sản phẩm

- `tests/test_classifier.py`

## Verify (bắt buộc)

- `venv\Scripts\python.exe -m pytest tests/test_classifier.py -v` xanh.
- `venv\Scripts\python.exe -m pytest` toàn bộ (85 test cũ + test mới) xanh.
