# Kết quả đánh giá Hybrid RAG

Benchmark: `data\evaluation\benchmark_questions.json` · 15 câu · Top-K (generator) = 6 · Retrieve-K (ChromaDB) = 6 · Judge = tắt · 2026-10-12T13:08:26
Model: Generator `local-qwen (qwen2.5:1.5b-instruct)` · Local SLM `qwen2.5:1.5b-instruct` · Embedding `BAAI/bge-m3`

## Chỉ số tổng hợp

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 15/15 |
| Hit@3 | 53.3% |
| Hit@5 | 60.0% |
| Hit@6 | 73.3% |
| MRR (recall window) | 0.4833 |
| Citation Precision | 0.0% |
| Citation Recall | 0.0% |
| Citation F1 | 0.0% |
| Citation Exact Match | 0.0% |
| Faithfulness (LLM judge) | n/a |
| Number support (không cần API) | 94.4% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 100.0% |
| Bảo toàn đủ 100% thực thể | 100.0% |
| Từ chối đúng (câu ngoài corpus) | n/a (0 câu) |
| Ảo giác trên câu ngoài corpus | 0 câu |
| Thời gian trung bình / câu | 13.8773s |

## Kết quả theo câu

| ID | Hit@6 | RR | Citation F1 | Faithfulness | Ghi chú |
|---|---|---|---|---|---|
| Q01 | True | 1.00 | — | — |  |
| Q02 | True | 1.00 | — | — |  |
| Q03 | True | 1.00 | — | — |  |
| Q04 | True | 1.00 | — | — |  |
| Q05 | True | 0.17 | 0.00 | — | trích dẫn lệch: (không có) |
| Q06 | False | 0.00 | 0.00 | — | trích dẫn lệch: (không có) |
| Q07 | True | 0.33 | 0.00 | — | trích dẫn lệch: (không có) |
| Q08 | True | 0.33 | — | — |  |
| Q09 | True | 0.25 | — | — |  |
| Q10 | False | 0.00 | 0.00 | — | trích dẫn lệch: (không có) |
| Q11 | True | 1.00 | 0.00 | — | trích dẫn lệch: (không có) |
| Q12 | True | 0.17 | — | — |  |
| Q13 | True | 1.00 | — | — |  |
| Q14 | False | 0.00 | — | — |  |
| Q15 | False | 0.00 | 0.00 | — | trích dẫn lệch: (không có) |
