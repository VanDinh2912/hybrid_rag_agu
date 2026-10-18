# Kết quả đánh giá Hybrid RAG

Benchmark: `data\evaluation\benchmark_100_questions_v2.json` · 100 câu · Top-K (generator) = 6 · Retrieve-K (ChromaDB) = 6 · Judge = tắt · 2026-10-18T00:58:22
Model: Generator `local-qwen (qwen2.5:1.5b-instruct)` · Local SLM `qwen2.5:1.5b-instruct` · Embedding `BAAI/bge-m3`

## Chỉ số tổng hợp

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 100/100 |
| Hit@3 | 0.0% |
| Hit@5 | 0.0% |
| Hit@6 | 0.0% |
| MRR (recall window) | 0.0 |
| Citation Precision | 15.6% |
| Citation Recall | 13.0% |
| Citation F1 | 13.4% |
| Citation Exact Match | 12.5% |
| Faithfulness (LLM judge) | n/a |
| Number support (không cần API) | 98.4% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 96.7% |
| Bảo toàn đủ 100% thực thể | 96.7% |
| Từ chối đúng (câu ngoài corpus) | n/a (0 câu) |
| Ảo giác trên câu ngoài corpus | 0 câu |
| Thời gian trung bình / câu | 14.0155s |

## Kết quả theo câu

| ID | Hit@6 | RR | Citation F1 | Faithfulness | Ghi chú |
|---|---|---|---|---|---|
| Q01 | False | 0.00 | — | — |  |
| Q02 | False | 0.00 | — | — |  |
| Q03 | False | 0.00 | — | — |  |
| Q04 | False | 0.00 | — | — |  |
| Q05 | False | 0.00 | — | — |  |
| Q06 | False | 0.00 | — | — |  |
| Q07 | False | 0.00 | — | — |  |
| Q08 | False | 0.00 | — | — |  |
| Q09 | False | 0.00 | — | — |  |
| Q10 | False | 0.00 | — | — |  |
| Q11 | False | 0.00 | — | — |  |
| Q12 | False | 0.00 | — | — |  |
| Q13 | False | 0.00 | — | — |  |
| Q14 | False | 0.00 | — | — |  |
| Q15 | False | 0.00 | — | — |  |
| Q16 | False | 0.00 | — | — |  |
| Q17 | False | 0.00 | — | — |  |
| Q18 | False | 0.00 | — | — |  |
| Q19 | False | 0.00 | — | — |  |
| Q20 | False | 0.00 | — | — |  |
| Q21 | False | 0.00 | — | — |  |
| Q22 | False | 0.00 | — | — |  |
| Q23 | False | 0.00 | 1.00 | — |  |
| Q24 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q25 | False | 0.00 | 0.29 | — | trích dẫn lệch: dieu 9 |
| Q26 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 16 |
| Q27 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q28 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 5 |
| Q29 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q30 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q31 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 7 |
| Q32 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 16 |
| Q33 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11, dieu 9 |
| Q34 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q35 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 5 |
| Q36 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q37 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11, dieu 14 |
| Q38 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q39 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 5 |
| Q40 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 32 |
| Q41 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q42 | False | 0.00 | 1.00 | — |  |
| Q43 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 15 |
| Q44 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q45 | False | 0.00 | 1.00 | — |  |
| Q46 | False | 0.00 | 1.00 | — |  |
| Q47 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q48 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q49 | False | 0.00 | — | — |  |
| Q50 | False | 0.00 | — | — |  |
| Q51 | False | 0.00 | — | — |  |
| Q52 | False | 0.00 | — | — |  |
| Q53 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 10, dieu 118, dieu 18, dieu 3, dieu 4 |
| Q54 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q55 | False | 0.00 | — | — |  |
| Q56 | False | 0.00 | — | — |  |
| Q57 | False | 0.00 | — | — |  |
| Q58 | False | 0.00 | — | — |  |
| Q59 | False | 0.00 | — | — |  |
| Q60 | False | 0.00 | — | — |  |
| Q61 | False | 0.00 | — | — |  |
| Q62 | False | 0.00 | — | — |  |
| Q63 | False | 0.00 | — | — |  |
| Q64 | False | 0.00 | — | — |  |
| Q65 | False | 0.00 | — | — |  |
| Q66 | False | 0.00 | — | — |  |
| Q67 | False | 0.00 | — | — |  |
| Q68 | False | 0.00 | — | — |  |
| Q69 | False | 0.00 | — | — |  |
| Q70 | False | 0.00 | — | — |  |
| Q71 | False | 0.00 | — | — |  |
| Q72 | False | 0.00 | — | — |  |
| Q73 | False | 0.00 | — | — |  |
| Q74 | False | 0.00 | — | — |  |
| Q75 | False | 0.00 | — | — |  |
| Q76 | False | 0.00 | — | — |  |
| Q77 | False | 0.00 | — | — |  |
| Q78 | False | 0.00 | — | — |  |
| Q79 | False | 0.00 | — | — |  |
| Q80 | False | 0.00 | — | — |  |
| Q81 | False | 0.00 | — | — |  |
| Q82 | False | 0.00 | — | — |  |
| Q83 | False | 0.00 | — | — |  |
| Q84 | False | 0.00 | — | — |  |
| Q85 | False | 0.00 | — | — |  |
| Q86 | False | 0.00 | — | — |  |
| Q87 | False | 0.00 | — | — |  |
| Q88 | False | 0.00 | — | — |  |
| Q89 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q90 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 3, dieu 5, dieu 6 |
| Q91 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 12, dieu 6 |
| Q92 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 17 |
| Q93 | False | 0.00 | — | — |  |
| Q94 | False | 0.00 | — | — |  |
| Q95 | False | 0.00 | — | — |  |
| Q96 | False | 0.00 | — | — |  |
| Q97 | False | 0.00 | — | — |  |
| Q98 | False | 0.00 | — | — |  |
| Q99 | False | 0.00 | — | — |  |
| Q100 | False | 0.00 | — | — |  |
