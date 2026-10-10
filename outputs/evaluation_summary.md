# Kết quả đánh giá Hybrid RAG

Benchmark: `data\evaluation\benchmark_questions.json` · 8 câu · Top-K = 5 · Judge = bật · 2026-10-10T10:48:59
Model: Generator `gemini-2.5-flash` · Local SLM `qwen2.5:1.5b-instruct` · Embedding `BAAI/bge-m3`

## Chỉ số tổng hợp

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 0/1 |
| Hit@3 | n/a |
| Hit@5 | n/a |
| MRR@5 | n/a |
| Citation Precision | n/a |
| Citation Recall | n/a |
| Citation F1 | n/a |
| Citation Exact Match | n/a |
| Faithfulness (LLM judge) | n/a |
| Number support (không cần API) | n/a |
| Chuẩn hóa Qwen khớp benchmark | n/a |
| Từ chối đúng (câu ngoài corpus) | n/a (0 câu) |
| Ảo giác trên câu ngoài corpus | 0 câu |
| Thời gian trung bình / câu | Nones |

## Kết quả theo câu

| ID | Hit@5 | RR | Citation F1 | Faithfulness | Ghi chú |
|---|---|---|---|---|---|
| Q01 | — | — | — | — | LỖI: GeneratorError: Gọi Gemini API thất bại: 429 You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. 
* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-2.5-flash
Please retry in 20h10m55.435555948s. [links {
  description: "Learn more about Gemini API quotas"
  url: "https://ai.google.dev/gemini-api/docs/rate-limits"
}
, violations {
  quota_metric: "generativelanguage.googleapis.com/generate_content_free_tier_requests"
  quota_id: "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
  quota_dimensions {
    key: "model"
    value: "gemini-2.5-flash"
  }
  quota_dimensions {
    key: "location"
    value: "global"
  }
  quota_value: 20
}
, retry_delay {
  seconds: 72655
}
]. Đã hết quota Gemini — chờ reset hoặc dùng key khác. |
