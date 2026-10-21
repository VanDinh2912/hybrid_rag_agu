# Kết quả đánh giá Hybrid RAG

Benchmark: `data\evaluation\benchmark_100_questions_v3.json` · 100 câu · Top-K (generator) = 6 · Retrieve-K (ChromaDB) = 6 · Judge = tắt · 2026-10-21T18:39:57
Model: Generator `local-qwen (qwen2.5:1.5b-instruct)` · Local SLM `qwen2.5:1.5b-instruct` · Embedding `BAAI/bge-m3`

## Chỉ số tổng hợp

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 100/100 |
| Hit@3 | 60.8% |
| Hit@5 | 65.0% |
| Hit@6 | 66.0% |
| MRR (recall window) | 0.5097 |
| Citation Precision | 15.6% |
| Citation Recall | 13.0% |
| Citation F1 | 13.4% |
| Citation Exact Match | 12.5% |
| Faithfulness (LLM judge) | n/a |
| Number support (không cần API) | 96.6% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 96.7% |
| Bảo toàn đủ 100% thực thể | 96.7% |
| Từ chối đúng (câu ngoài corpus) | 33.3% (3 câu) |
| Ảo giác trên câu ngoài corpus | 2 câu |
| Thời gian trung bình / câu | 2.3017s |

## Kết quả theo câu

| ID | Hit@6 | RR | Citation F1 | Faithfulness | Ghi chú |
|---|---|---|---|---|---|
| Q01 | False | 0.11 | — | — |  |
| Q02 | True | 0.33 | — | — |  |
| Q03 | True | 0.50 | — | — |  |
| Q04 | True | 0.33 | — | — |  |
| Q05 | False | 0.08 | — | — |  |
| Q06 | False | 0.00 | — | — |  |
| Q07 | False | 0.00 | — | — |  |
| Q08 | False | 0.14 | — | — |  |
| Q09 | True | 0.33 | — | — |  |
| Q10 | False | 0.00 | — | — |  |
| Q11 | True | 0.33 | — | — |  |
| Q12 | False | 0.12 | — | — |  |
| Q13 | False | 0.00 | — | — |  |
| Q14 | True | 0.17 | — | — |  |
| Q15 | False | 0.00 | — | — |  |
| Q16 | True | 1.00 | — | — |  |
| Q17 | True | 0.50 | — | — |  |
| Q18 | True | 0.33 | — | — |  |
| Q19 | True | 0.33 | — | — |  |
| Q20 | False | 0.00 | — | — |  |
| Q21 | False | 0.00 | — | — |  |
| Q22 | True | 0.33 | — | — |  |
| Q23 | True | 1.00 | 1.00 | — |  |
| Q24 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q25 | True | 1.00 | 0.29 | — | trích dẫn lệch: dieu 9 |
| Q26 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 16 |
| Q27 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q28 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 5 |
| Q29 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q30 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q31 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 7 |
| Q32 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 16 |
| Q33 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 11, dieu 9 |
| Q34 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q35 | False | 0.08 | 0.00 | — | trích dẫn lệch: dieu 5 |
| Q36 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q37 | False | 0.14 | 0.00 | — | trích dẫn lệch: dieu 11, dieu 14 |
| Q38 | False | 0.10 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q39 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 5 |
| Q40 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 32 |
| Q41 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q42 | False | 0.00 | 1.00 | — |  |
| Q43 | False | 0.09 | 0.00 | — | trích dẫn lệch: dieu 15 |
| Q44 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q45 | False | 0.11 | 1.00 | — |  |
| Q46 | True | 0.25 | 1.00 | — |  |
| Q47 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q48 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q49 | True | 1.00 | — | — |  |
| Q50 | True | 1.00 | — | — |  |
| Q51 | True | 1.00 | — | — |  |
| Q52 | True | 0.50 | — | — |  |
| Q53 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 10, dieu 118, dieu 18, dieu 3, dieu 4 |
| Q54 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q55 | True | 1.00 | — | — |  |
| Q56 | True | 1.00 | — | — |  |
| Q57 | True | 0.50 | — | — |  |
| Q58 | True | 0.20 | — | — |  |
| Q59 | True | 0.33 | — | — |  |
| Q60 | True | 0.50 | — | — |  |
| Q61 | False | 0.10 | — | — |  |
| Q62 | True | 0.33 | — | — |  |
| Q63 | True | 1.00 | — | — |  |
| Q64 | True | 1.00 | — | — |  |
| Q65 | True | 1.00 | — | — |  |
| Q66 | True | 1.00 | — | — |  |
| Q67 | True | 1.00 | — | — |  |
| Q68 | False | 0.00 | — | — |  |
| Q69 | False | 0.00 | — | — |  |
| Q70 | False | 0.00 | — | — |  |
| Q71 | False | 0.00 | — | — |  |
| Q72 | False | 0.00 | — | — |  |
| Q73 | False | 0.00 | — | — |  |
| Q74 | True | 1.00 | — | — |  |
| Q75 | True | 1.00 | — | — |  |
| Q76 | True | 0.50 | — | — |  |
| Q77 | True | 1.00 | — | — |  |
| Q78 | True | 0.33 | — | — |  |
| Q79 | False | 0.08 | — | — |  |
| Q80 | True | 1.00 | — | — |  |
| Q81 | True | 0.33 | — | — |  |
| Q82 | True | 1.00 | — | — |  |
| Q83 | True | 1.00 | — | — |  |
| Q84 | True | 1.00 | — | — |  |
| Q85 | True | 1.00 | — | — |  |
| Q86 | True | 1.00 | — | — |  |
| Q87 | True | 0.50 | — | — |  |
| Q88 | True | 0.20 | — | — |  |
| Q89 | False | 0.08 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q90 | True | 0.50 | 0.00 | — | trích dẫn lệch: dieu 3, dieu 5, dieu 6 |
| Q91 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 12, dieu 6 |
| Q92 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 17 |
| Q93 | True | 1.00 | — | — |  |
| Q94 | True | 1.00 | — | — |  |
| Q95 | True | 0.20 | — | — |  |
| Q96 | — | 0.00 | — | — | ẢO GIÁC: trả lời câu ngoài corpus thay vì từ chối |
| Q97 | — | 0.00 | — | — | từ chối đúng |
| Q98 | — | 0.00 | — | — | ẢO GIÁC: trả lời câu ngoài corpus thay vì từ chối |
| Q99 | True | 1.00 | — | — |  |
| Q100 | True | 0.50 | — | — |  |
