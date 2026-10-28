# Group 02 — Trí tuệ RAG

> Bắt buộc nạp kèm: `base_prompt.md`
> Gộp từ 3 chủ thể cũ: Retrieval & chuẩn hóa truy vấn, Sinh trả lời (Generator/SLM), Pipeline/CLI

## Phạm vi được đụng

- `src/retrieval/retrieval.py`, `src/core/query_normalizer.py`, `src/text_utils.py`
- `src/generator.py`, `src/generation/local_slm.py`, `.generation_cache/`
- `src/core/pipeline.py`, `main.py`
- `src/core/classifier.py`, `src/retrieval/router.py` (tầng phân loại câu hỏi 2 nhãn + router truy xuất — P3.2)
- `tmp/` cho script smoke test trung gian

## Sản phẩm cuối

- Hybrid search (vector + keyword) + expansion 3 tầng + fold tiếng Việt hoạt động
  nhất quán; tham số oversampling/overlap hợp lý — thay đổi tham số phải ghi trong báo cáo
- Câu trả lời có trích dẫn Điều/Khoản rõ ràng từ chunk đã truy xuất; soft refusal
  khi câu hỏi ngoài phạm vi corpus (KHÔNG bịa); guardrail chống lệch nghĩa của normalizer
- Pipeline CHỈ orchestrate (gọi module của tầng khác), không chứa business logic

## Vùng cấm

- `data/corpus/`, `chroma_db/`, `data/evaluation/` (chỉ ĐỌC/kết nối)
- `outputs/**`, `logs/**`
- `src/indexing/loader.py`, `src/indexing/chunking.py`, `src/retrieval/vector_db.py` (Group 01);
  `src/assessment/evaluation.py`, `tests/` (Group 04); `ui/` (Group 03)
- CẤM sửa test cho pass — test fail là phát hiện bug, báo lại Group sở hữu module đó

## Verify

- Test liên quan trong `tests/` pass (không đụng tay vào test)
- Smoke 3 câu: (1) trong phạm vi → có citation đúng; (2) ngoài phạm vi → soft refusal,
  không bịa; (3) chính tả sai/teencode → normalizer xử lý được
- `python main.py` khởi động được chế độ tương tác; 1 câu hỏi E2E ra kết quả có trích dẫn
- Không có hàm business logic nào được định nghĩa trong `pipeline.py` ngoài bọc luồng
- `.generation_cache/` chỉ xóa khi đổi model (đổi prompt thì giữ cache); `tmp/` đã xóa sạch
