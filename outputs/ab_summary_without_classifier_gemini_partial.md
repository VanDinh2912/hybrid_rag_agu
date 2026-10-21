# Kết quả đánh giá Hybrid RAG

Benchmark: `data\evaluation\benchmark_100_questions_v3.json` · 100 câu · Top-K (generator) = 6 · Retrieve-K (ChromaDB) = 6 · Judge = bật · 2026-10-21T14:17:53
Model: Generator `gemini-3.8-flash` · Local SLM `qwen2.5:1.5b-instruct` · Embedding `BAAI/bge-m3`

## Chỉ số tổng hợp

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 22/23 |
| Hit@3 | 40.9% |
| Hit@5 | 45.5% |
| Hit@6 | 50.0% |
| MRR (recall window) | 0.2218 |
| Citation Precision | n/a |
| Citation Recall | n/a |
| Citation F1 | n/a |
| Citation Exact Match | n/a |
| Faithfulness (LLM judge) | 98.5% |
| Number support (không cần API) | 98.5% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 90.0% |
| Bảo toàn đủ 100% thực thể | 90.0% |
| Từ chối đúng (câu ngoài corpus) | n/a (0 câu) |
| Ảo giác trên câu ngoài corpus | 0 câu |
| Thời gian trung bình / câu | 103.4768s |

## Kết quả theo câu

| ID | Hit@6 | RR | Citation F1 | Faithfulness | Ghi chú |
|---|---|---|---|---|---|
| Q01 | False | 0.11 | — | 1.00 | refusal |
| Q02 | True | 0.33 | — | 1.00 |  |
| Q03 | True | 0.50 | — | 1.00 | refusal |
| Q04 | True | 0.33 | — | 0.67 |  |
| Q05 | False | 0.08 | — | 1.00 | refusal |
| Q06 | False | 0.00 | — | 1.00 | refusal |
| Q07 | False | 0.00 | — | 1.00 | refusal |
| Q08 | False | 0.14 | — | 1.00 | refusal |
| Q09 | True | 0.33 | — | 1.00 |  |
| Q10 | False | 0.00 | — | 1.00 | refusal |
| Q11 | True | 0.33 | — | 1.00 | refusal |
| Q12 | False | 0.12 | — | 1.00 | refusal |
| Q13 | False | 0.00 | — | 1.00 | refusal |
| Q14 | True | 0.17 | — | 1.00 | refusal |
| Q15 | False | 0.00 | — | 1.00 | refusal |
| Q16 | True | 1.00 | — | 1.00 | refusal |
| Q17 | True | 0.50 | — | 1.00 |  |
| Q18 | True | 0.33 | — | 1.00 |  |
| Q19 | True | 0.25 | — | 1.00 |  |
| Q20 | False | 0.00 | — | 1.00 | refusal |
| Q21 | False | 0.00 | — | 1.00 | refusal |
| Q22 | True | 0.33 | — | 1.00 | refusal |
| Q23 | — | — | — | — | LỖI: GeneratorError: 429 PerDay — hết quota NGÀY của Gemini: 429 You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. 
* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.8-flash
Please retry in 23h19m27.800813997s. [links {
  description: "Learn more about Gemini API quotas"
  url: "https://ai.google.dev/gemini-api/docs/rate-limits"
}
, violations {
  quota_metric: "generativelanguage.googleapis.com/generate_content_free_tier_requests"
  quota_id: "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
  quota_dimensions {
    key: "model"
    value: "gemini-3.8-flash"
  }
  quota_dimensions {
    key: "location"
    value: "global"
  }
  quota_value: 20
}
, retry_delay {
  seconds: 83967
}
]. Chờ reset (~14:00 VN = 07:00 UTC, midnight Pacific) rồi chạy lại ĐÚNG lệnh cũ; cache giữ phần đã trả lời, resume chỉ chạy câu thiếu. |
