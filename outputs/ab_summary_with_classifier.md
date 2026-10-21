# Kết quả đánh giá Hybrid RAG

Benchmark: `data\evaluation\benchmark_100_questions_v3.json` · 100 câu · Top-K (generator) = 6 · Retrieve-K (ChromaDB) = 6 · Judge = tắt · 2026-10-21T18:40:12
Model: Generator `local-qwen (qwen2.5:1.5b-instruct)` · Local SLM `qwen2.5:1.5b-instruct` · Embedding `BAAI/bge-m3`

## Chỉ số tổng hợp

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 100/100 |
| Hit@3 | 77.3% |
| Hit@5 | 78.3% |
| Hit@6 | 78.3% |
| MRR (recall window) | 0.7689 |
| Citation Precision | 24.8% |
| Citation Recall | 29.7% |
| Citation F1 | 25.7% |
| Citation Exact Match | 21.9% |
| Faithfulness (LLM judge) | n/a |
| Number support (không cần API) | 93.6% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 96.7% |
| Bảo toàn đủ 100% thực thể | 96.7% |
| Từ chối đúng (câu ngoài corpus) | 33.3% (3 câu) |
| Ảo giác trên câu ngoài corpus | 2 câu |
| Thời gian trung bình / câu | 7.7882s |

## Phân loại & Router (lượt WITH classifier)

| Chỉ số | Giá trị |
|---|---|
| Độ chính xác chủ đề | 87.0% (100 câu) |
| Độ chính xác loại câu hỏi | 83.0% (100 câu) |
| Từ chối oan (in_corpus=true) | 50.5% (49/97 câu) |

### Theo loại câu hỏi (predicted)

| Nhóm | n | Hit@3 | Hit@5 | Hit@6 | MRR | Citation F1 | Faithfulness |
|---|---|---|---|---|---|---|---|
| NGOAI_PHAM_VI | 11 | 62.5% | 62.5% | 62.5% | 0.625 | 75.0% | n/a |
| SO_SANH | 14 | 92.9% | 92.9% | 92.9% | 0.9388 | 31.7% | n/a |
| THU_TUC | 5 | 80.0% | 100.0% | 100.0% | 0.74 | n/a | n/a |
| TRA_CUU | 70 | 75.7% | 75.7% | 75.7% | 0.7534 | 15.2% | n/a |

### Theo chủ đề (category benchmark)

| Nhóm | n | Hit@3 | Hit@5 | Hit@6 | MRR | Citation F1 | Faithfulness |
|---|---|---|---|---|---|---|---|
| bảo hiểm y tế | 2 | 100.0% | 100.0% | 100.0% | 0.75 | n/a | n/a |
| chương trình đào tạo | 22 | 90.9% | 90.9% | 90.9% | 0.9091 | n/a | n/a |
| cuộc thi chính luận | 12 | 100.0% | 100.0% | 100.0% | 1.0 | n/a | n/a |
| hành chính sinh viên | 1 | 0.0% | 0.0% | 0.0% | 0.0833 | n/a | n/a |
| học phí | 12 | 50.0% | 50.0% | 50.0% | 0.5595 | n/a | n/a |
| khen thưởng cấp ĐHQG | 2 | 50.0% | 50.0% | 50.0% | 0.2917 | 0.0% | n/a |
| khen thưởng sinh viên | 10 | 50.0% | 50.0% | 50.0% | 0.5 | 30.0% | n/a |
| ký túc xá | 2 | 0.0% | 0.0% | 0.0% | 0.0 | 0.0% | n/a |
| quy chế công tác sinh viên | 6 | 100.0% | 100.0% | 100.0% | 1.0 | 46.7% | n/a |
| sinh viên 5 tốt | 6 | 83.3% | 83.3% | 83.3% | 0.8333 | 0.0% | n/a |
| thực tập chuyên đề | 3 | 33.3% | 66.7% | 66.7% | 0.2333 | n/a | n/a |
| thực tập tốt nghiệp | 9 | 100.0% | 100.0% | 100.0% | 1.0 | n/a | n/a |
| tài chính sinh viên | 2 | 100.0% | 100.0% | 100.0% | 1.0 | n/a | n/a |
| đánh giá rèn luyện | 11 | 81.8% | 81.8% | 81.8% | 0.8182 | 26.4% | n/a |

## Kết quả theo câu

| ID | Hit@6 | RR | Citation F1 | Faithfulness | Ghi chú |
|---|---|---|---|---|---|
| Q01 | True | 1.00 | — | — |  |
| Q02 | True | 1.00 | — | — |  |
| Q03 | True | 1.00 | — | — |  |
| Q04 | True | 1.00 | — | — |  |
| Q05 | True | 1.00 | — | — |  |
| Q06 | True | 1.00 | — | — |  |
| Q07 | False | 0.00 | — | — |  |
| Q08 | False | 0.00 | — | — |  |
| Q09 | True | 1.00 | — | — |  |
| Q10 | True | 1.00 | — | — |  |
| Q11 | True | 1.00 | — | — |  |
| Q12 | True | 1.00 | — | — |  |
| Q13 | True | 1.00 | — | — |  |
| Q14 | True | 1.00 | — | — |  |
| Q15 | True | 1.00 | — | — |  |
| Q16 | True | 1.00 | — | — |  |
| Q17 | True | 1.00 | — | — |  |
| Q18 | True | 1.00 | — | — |  |
| Q19 | True | 1.00 | — | — |  |
| Q20 | True | 1.00 | — | — |  |
| Q21 | True | 1.00 | — | — |  |
| Q22 | True | 1.00 | — | — |  |
| Q23 | True | 1.00 | 1.00 | — |  |
| Q24 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q25 | True | 1.00 | 0.50 | — | trích dẫn lệch: dieu 1, dieu 12, dieu 14, dieu 6, dieu 8, dieu 9 |
| Q26 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 3 |
| Q27 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q28 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 9 |
| Q29 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q30 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q31 | False | 0.00 | 1.00 | — |  |
| Q32 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 16 |
| Q33 | True | 1.00 | 0.40 | — | trích dẫn lệch: dieu 11, dieu 12, dieu 13, dieu 9 |
| Q34 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 9 |
| Q35 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 23 |
| Q36 | False | 0.00 | 1.00 | — |  |
| Q37 | False | 0.00 | 1.00 | — |  |
| Q38 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 13 |
| Q39 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 23 |
| Q40 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 32 |
| Q41 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 34 |
| Q42 | False | 0.00 | 1.00 | — |  |
| Q43 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 1, dieu 26, dieu 34, dieu 37, dieu 5 |
| Q44 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q45 | True | 1.00 | 0.33 | — | trích dẫn lệch: dieu 1, dieu 12, dieu 24, dieu 6, dieu 8 |
| Q46 | True | 1.00 | 1.00 | — |  |
| Q47 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 6 |
| Q48 | True | 1.00 | 1.00 | — |  |
| Q49 | True | 1.00 | — | — |  |
| Q50 | True | 1.00 | — | — |  |
| Q51 | True | 1.00 | — | — |  |
| Q52 | True | 1.00 | — | — |  |
| Q53 | True | 1.00 | 0.00 | — | trích dẫn lệch: dieu 3 |
| Q54 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 11 |
| Q55 | True | 1.00 | — | — |  |
| Q56 | True | 1.00 | — | — |  |
| Q57 | True | 1.00 | — | — |  |
| Q58 | True | 1.00 | — | — |  |
| Q59 | True | 1.00 | — | — |  |
| Q60 | True | 1.00 | — | — |  |
| Q61 | True | 1.00 | — | — |  |
| Q62 | True | 1.00 | — | — |  |
| Q63 | True | 1.00 | — | — |  |
| Q64 | True | 1.00 | — | — |  |
| Q65 | True | 1.00 | — | — |  |
| Q66 | True | 1.00 | — | — |  |
| Q67 | True | 1.00 | — | — |  |
| Q68 | False | 0.14 | — | — |  |
| Q69 | False | 0.14 | — | — |  |
| Q70 | False | 0.14 | — | — |  |
| Q71 | False | 0.14 | — | — |  |
| Q72 | False | 0.14 | — | — |  |
| Q73 | False | 0.00 | — | — |  |
| Q74 | True | 1.00 | — | — |  |
| Q75 | True | 1.00 | — | — |  |
| Q76 | True | 1.00 | — | — |  |
| Q77 | True | 1.00 | — | — |  |
| Q78 | True | 1.00 | — | — |  |
| Q79 | True | 1.00 | — | — |  |
| Q80 | True | 1.00 | — | — |  |
| Q81 | True | 1.00 | — | — |  |
| Q82 | True | 1.00 | — | — |  |
| Q83 | True | 1.00 | — | — |  |
| Q84 | True | 1.00 | — | — |  |
| Q85 | True | 1.00 | — | — |  |
| Q86 | False | 0.00 | — | — |  |
| Q87 | True | 0.50 | — | — |  |
| Q88 | True | 0.20 | — | — |  |
| Q89 | False | 0.08 | 0.00 | — | trích dẫn lệch: dieu 14 |
| Q90 | True | 0.50 | 0.00 | — | trích dẫn lệch: dieu 3, dieu 5, dieu 6 |
| Q91 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 12, dieu 6 |
| Q92 | False | 0.00 | 0.00 | — | trích dẫn lệch: dieu 17 |
| Q93 | True | 1.00 | — | — |  |
| Q94 | True | 1.00 | — | — |  |
| Q95 | False | 0.08 | — | — |  |
| Q96 | — | 0.00 | — | — | ẢO GIÁC: trả lời câu ngoài corpus thay vì từ chối |
| Q97 | — | 0.00 | — | — | từ chối đúng |
| Q98 | — | 0.00 | — | — | ẢO GIÁC: trả lời câu ngoài corpus thay vì từ chối |
| Q99 | True | 1.00 | — | — |  |
| Q100 | True | 0.50 | — | — |  |
