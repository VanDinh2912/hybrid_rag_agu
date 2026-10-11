# Kết quả đánh giá Hybrid RAG

Benchmark: `data\evaluation\benchmark_questions.json` · 8 câu · Top-K = 4 · Judge = bật · 2026-10-11T08:11:41
Model: Generator `gemini-2.5-flash` · Local SLM `qwen2.5:1.5b-instruct` · Embedding `BAAI/bge-m3`

## Chỉ số tổng hợp

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 8/8 |
| Hit@3 | 14.3% |
| Hit@5 | 14.3% |
| Hit@4 | 14.3% |
| MRR@4 | 0.0625 |
| Citation Precision | 0.0% |
| Citation Recall | 0.0% |
| Citation F1 | 0.0% |
| Citation Exact Match | 0.0% |
| Faithfulness (LLM judge) | 100.0% |
| Number support (không cần API) | 100.0% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 100.0% |
| Bảo toàn đủ 100% thực thể | 100.0% |
| Từ chối đúng (câu ngoài corpus) | 0.0% (1 câu) |
| Ảo giác trên câu ngoài corpus | 1 câu |
| Thời gian trung bình / câu | 8.995s |

## Kết quả theo câu

| ID | Hit@5 | RR | Citation F1 | Faithfulness | Ghi chú |
|---|---|---|---|---|---|
| Q01 | False | 0.00 | 0.00 | 1.00 | trích dẫn lệch: (không có) |
| Q02 | False | 0.00 | 0.00 | 1.00 | trích dẫn lệch: (không có) |
| Q03 | False | 0.00 | 0.00 | 1.00 | trích dẫn lệch: dieu 14 |
| Q04 | False | 0.00 | 0.00 | 1.00 | trích dẫn lệch: (không có) |
| Q05 | True | 0.50 | 0.00 | 1.00 | trích dẫn lệch: dieu 10 |
| Q06 | False | 0.00 | 0.00 | 1.00 | trích dẫn lệch: (không có) |
| Q07 | False | 0.00 | 0.00 | 1.00 | trích dẫn lệch: (không có) |
| Q08 | — | 0.00 | — | 1.00 | ẢO GIÁC: trả lời câu ngoài corpus thay vì từ chối |
