# So sánh 3 chiến lược chunking — Hybrid RAG quy chế ĐHAG

Benchmark: `data\evaluation\benchmark_50_questions.json` · 50 câu · Top-K (generator) = 3 · Retrieve-K = 6 · max_tokens = 512 · overlap = 0

Embedding: `BAAI/bge-m3` · Generator: `local-qwen (qwen2.5:1.5b-instruct)` (temperature = 0.00) · Local SLM: `qwen2.5:1.5b-instruct` · Retriever: BM25 + Chroma gộp RRF (c = 60)

Chạy lúc: 2026-10-17 23:36:01 · Thiết bị nhúng: cpu · Cache sinh chữ: bật · pandas: có

## Ma trận chỉ số chính (3 chiến lược × 7 chỉ số)

| Chiến lược | Mean Hit@3 | Mean Hit@5 | Mean MRR | Citation Precision | Citation Recall | Citation F1 | Avg Latency (ms) |
|---|---|---|---|---|---|---|---|
| fixed | 0.8800 | 0.9000 | 0.6983 | 0.0000 | 0.0000 | 0.0000 | 13010.3 |
| recursive | 0.7400 | 0.8800 | 0.6687 | 0.0050 | 0.0100 | 0.0067 | 13121.0 |
| structure | 0.7600 | 0.8800 | 0.7160 | 0.0990 | 0.0800 | 0.0767 | 13252.5 |

## Chỉ số hạ tầng

| Chiến lược | Total Chunks | Mean Chunk Tokens | Max Chunk Tokens | Index Size (MB) | Hit@6 | Citation Exact Match | Số câu OK | Số câu lỗi | Total Time (s) |
|---|---|---|---|---|---|---|---|---|---|
| fixed | 182 | 484.4 | 512 | 4.24 | 0.9000 | 0.5400 | 50/50 | 0 | 860.7 |
| recursive | 189 | 466.6 | 512 | 4.49 | 0.9000 | 0.6000 | 50/50 | 0 | 866.7 |
| structure | 378 | 269.4 | 511 | 5.93 | 0.9200 | 0.5400 | 50/50 | 0 | 923.1 |

## Quy ước chấm điểm

- **Hit@K**: Top-K chunk truy xuất có chứa ít nhất một chunk thuộc `source_document` ground truth hay không (so khớp tên file sau khi bỏ dấu thanh, vì OCR làm sai lệch tên).
- **MRR**: nghịch đảo thứ hạng của chunk đúng nguồn đầu tiên trong toàn bộ recall window (6 chunk), không cắt ở Top-K generator.
- **Citation P/R/F1**: so tập mã "Điều N [Khoản M]" hệ thống trích ra với tập rút từ `ground_truth_citation` + `expected_citations`; khớp đủ Điều+Khoản = 1.0, trùng Điều mà một phía không ghi Khoản = 0.5; ghép cặp theo maximum-weight matching.
- **Latency**: thời gian end-to-end của một câu (chuẩn hóa Qwen + truy xuất hybrid + sinh chữ).
