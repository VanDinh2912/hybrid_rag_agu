# Kết quả đánh giá Hybrid RAG

Benchmark: `data\evaluation\benchmark_50_questions.json` · 15 câu · Top-K (generator) = 6 · Retrieve-K (ChromaDB) = 6 · Judge = bật · 2026-10-14T11:42:57
Model: Generator `local-qwen (qwen2.5:1.5b-instruct)` · Local SLM `qwen2.5:1.5b-instruct` · Embedding `BAAI/bge-m3`

## Chỉ số tổng hợp

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 15/15 |
| Hit@3 | 26.7% |
| Hit@5 | 33.3% |
| Hit@6 | 46.7% |
| MRR (recall window) | 0.2138 |
| Citation Precision | 60.0% |
| Citation Recall | 60.0% |
| Citation F1 | 60.0% |
| Citation Exact Match | 60.0% |
| Faithfulness (LLM judge) | 36.7% |
| Number support (không cần API) | 90.5% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 75.0% |
| Bảo toàn đủ 100% thực thể | 75.0% |
| Từ chối đúng (câu ngoài corpus) | n/a (0 câu) |
| Ảo giác trên câu ngoài corpus | 0 câu |
| Thời gian trung bình / câu | 11.9153s |

## Kết quả theo câu

| ID | Hit@6 | RR | Citation F1 | Faithfulness | Ghi chú |
|---|---|---|---|---|---|
| Q01 | False | 0.00 | 1.00 | 0.00 |  |
| Q02 | False | 0.00 | 0.00 | 0.50 | trích dẫn lệch: 2025, 3620 |
| Q03 | False | 0.00 | 1.00 | 1.00 |  |
| Q04 | True | 0.20 | 1.00 | 0.00 |  |
| Q05 | False | 0.09 | 0.00 | 0.00 | trích dẫn lệch: 2026 |
| Q06 | True | 0.17 | — | 1.00 |  |
| Q07 | True | 0.17 | — | 0.00 |  |
| Q08 | False | 0.08 | — | 1.00 |  |
| Q09 | True | 0.50 | — | 1.00 |  |
| Q10 | True | 0.50 | — | 0.00 |  |
| Q11 | False | 0.00 | — | 1.00 |  |
| Q12 | True | 0.50 | — | 0.00 |  |
| Q13 | False | 0.00 | — | 0.00 |  |
| Q14 | True | 1.00 | — | 0.00 |  |
| Q15 | False | 0.00 | — | 0.00 |  |
