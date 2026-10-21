# BASELINE — Snapshot pipeline "không phân loại"

> Ngày snapshot: **2026-10-20** · Nhiệm vụ: P0.2 · Nhóm playbook: 04
> Mục đích: ghim số liệu pipeline cũ (chưa có tầng phân loại) để mọi kết quả A/B ở giai đoạn 4 đối chiếu về đây.
> Nguyên tắc: **copy-only** từ `outputs/` và `logs/benchmark/`; không chạy lại bất kỳ lượt đánh giá nào, không sửa file gốc.

## 1. Nội dung thư mục baseline

| File trong baseline | Nguồn gốc | Kích thước (byte) | SHA1 |
|---|---|---|---|
| `evaluation_results.json` | `outputs/evaluation_results.json` | 461.828 | `daf045da09166a726f22941d8400822f4332bf90` |
| `evaluation_summary.md` | `outputs/evaluation_summary.md` | 5.426 | `2de8217bdfa010f95e2febdaee4e183163420cb3` |
| `summary_comparison_report.csv` | `logs/benchmark/summary_comparison_report.csv` | 294 | `5e0d92813899fdb73847f496a3cbf03db1ced20a` |
| `summary_comparison_report.md` | `logs/benchmark/summary_comparison_report.md` | 2.255 | `0ce877c2b4f7c67f340ad5070d020dd32ff7482f` |
| `results_all.json` | `logs/benchmark/results_all.json` | 743.510 | `d0dbd4a071226c65e33adcd01326465181e7c9cb` |

`results_all.json` có kích thước 743.510 byte (< 5 MB) nên được copy vào baseline theo yêu cầu P0.2.

## 2. Lượt chạy chính — benchmark 100 câu v2 (Qwen offline)

### 2.1. Tham số

| Tham số | Giá trị | Nguồn |
|---|---|---|
| Benchmark | `data/evaluation/benchmark_100_questions_v2.json` — 100 câu | `meta` của `evaluation_results.json` |
| Top-K (generator) | 6 | `meta.top_k` |
| Retrieve-K | 6 | `meta.retrieve_k` |
| Generator | `local-qwen (qwen2.5:1.5b-instruct)` — Qwen offline | `meta.generator_model` |
| Local SLM (chuẩn hóa) | `qwen2.5:1.5b-instruct` | `meta.local_slm_model` |
| Embedding | `BAAI/bge-m3` | `outputs/evaluation_summary.md` |
| Giám khảo Faithfulness | Tắt (`judge_enabled = false`, `judge_model = null`) | `meta` |
| Thời điểm chạy | 2026-10-18T08:34:35 | `meta.timestamp` |
| Trạng thái | 100/100 câu chạy được; `interrupted = false` | `meta`, `aggregates` |
| Retriever | True Hybrid Search (BM25 + ChromaDB, RRF `c = 60`, trọng số 0.5/0.5) — không ghi trong meta lượt chạy, theo cấu hình mặc định của repo | `README.md` mục 1 |

### 2.2. Chỉ số

| Chỉ số | Giá trị | Số câu được tính |
|---|---|---|
| Số câu chạy được | 100/100 | 100 |
| Hit@3 | 59.8% (0.5979) | 97 |
| Hit@5 | 63.9% (0.6392) | 97 |
| Hit@6 | 65.0% (0.6495) | 97 |
| MRR (recall window) | 0.5076 | 97 |
| Citation Precision | 78.1% (0.7812) | 32 |
| Citation Recall | 78.1% (0.7812) | 32 |
| Citation F1 | 78.1% (0.7812) | 32 |
| Citation Exact Match | 78.1% (0.7812) | 32 |
| Faithfulness (LLM judge) | n/a — giám khảo tắt | 0 |
| Number support (không cần API) | 94.3% (0.9429) | — |
| Bảo toàn thực thể sau chuẩn hóa | 96.7% (0.9667) | 30 |
| Từ chối đúng (câu ngoài corpus) | 0.0% — 3 câu đều bị ảo giác | 3 |
| Ảo giác trên câu ngoài corpus | 3 câu | — |
| Thời gian trung bình / câu | 1.1066 s | 100 |

Nguồn: `evaluation_summary.md` (bảng tổng hợp) và `evaluation_results.json` → `aggregates` (giá trị thập phân, số câu được tính). Hit@K/MRR tính trên 97 câu trong corpus; Citation P/R/F1/EM chỉ tính trên 32 câu có `expected_citations`; Faithfulness không đo vì giám khảo tắt.

> **Độ tin cậy:** lượt này dùng generator Qwen offline và tắt giám khảo, nên **chỉ tầng truy xuất (Hit@K/MRR) là đáng tin**. Citation và Faithfulness chỉ mang tính tham khảo, không đại diện cho pipeline Gemini.

## 3. Lượt benchmark 3 chiến lược chunking — 50 câu (Qwen offline)

### 3.1. Tham số

| Tham số | Giá trị | Nguồn |
|---|---|---|
| Benchmark | `data/evaluation/benchmark_50_questions.json` — 50 câu | `summary_comparison_report.md`; `results_all.json` → `meta` |
| Top-K (generator) | 3 | `summary_comparison_report.md`; `meta.top_k` |
| Retrieve-K | 6 | `summary_comparison_report.md` |
| Generator | `local-qwen (qwen2.5:1.5b-instruct)`, temperature 0.0 | `meta.generator_model`, `meta.temperature` |
| Local SLM (chuẩn hóa) | `qwen2.5:1.5b-instruct` | `meta.local_slm_model` |
| Embedding | `BAAI/bge-m3` | `summary_comparison_report.md` |
| Retriever | BM25 + ChromaDB gộp RRF (`c = 60`) | `summary_comparison_report.md` |
| Cắt đoạn | `max_tokens = 512`, `overlap = 0`; tokenizer HuggingFace của bge-m3 | `meta`; `results_all.json` → `strategies.*.params` |
| Chiến lược | `fixed`, `recursive`, `structure` | `meta.strategies_completed` |
| Thiết bị | CPU; cache sinh chữ bật | `meta.device`, `meta.cache` |
| Giám khảo / Faithfulness | Không có trong báo cáo lượt này | `summary_comparison_report.md` |
| Thời điểm | Tổng hợp 2026-10-17 23:36:01; từng chiến lược: fixed 22:52:17, recursive 23:19:49, structure 23:40:47 | `meta.timestamp`; `strategies.*.params.timestamp` |

`results_all.json` ghi `merged_from_previous = ["recursive", "fixed"]`: lượt tổng hợp này chạy `structure` và gộp kết quả `fixed`/`recursive` từ các lượt trước đó có cùng tham số.

### 3.2. Chỉ số

| Chiến lược | Số chunk | Hit@3 | Hit@5 | Hit@6 | MRR | Citation P | Citation R | Citation F1 | Citation Exact Match | Latency (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed | 182 | 0.8800 | 0.9000 | 0.9000 | 0.6983 | 0.0000 | 0.0000 | 0.0000 | 0.5400 | 13.010,3 |
| recursive | 189 | 0.7400 | 0.8800 | 0.9000 | 0.6687 | 0.0050 | 0.0100 | 0.0067 | 0.6000 | 13.121,0 |
| structure | 378 | 0.7600 | 0.8800 | 0.9200 | 0.7160 | 0.0990 | 0.0800 | 0.0767 | 0.5400 | 13.252,5 |

Nguồn: `summary_comparison_report.md` và `summary_comparison_report.csv`; đối chiếu `results_all.json` → `strategies.*.aggregate`. Faithfulness và number support không được đo trong lượt này.

> **Độ tin cậy:** Citation F1/Exact Match thấp do generator Qwen 1.5B; chỉ nên so sánh tương đối giữa ba chiến lược, không đọc như chất lượng tuyệt đối của tầng trích dẫn.

## 4. Lượt cũ bất thường — 100 câu v2, 2026-10-18T00:58:22

Hai file kết quả `outputs/evaluation_results_100v2_offline.json` và `outputs/evaluation_results_judge15.json` **trùng SHA1** (`d6ae6a9c…`, 469.309 byte); hai file summary tương ứng cũng trùng SHA1 (`7420a2fc…`, 5.896 byte). Đây là cùng một lượt chạy được lưu dưới hai tên.

| Tham số | Giá trị |
|---|---|
| Benchmark | `benchmark_100_questions_v2.json` — 100 câu |
| Top-K / Retrieve-K | 6 / 6 |
| Generator | `local-qwen (qwen2.5:1.5b-instruct)` |
| Giám khảo | Tắt |
| Thời điểm | 2026-10-18T00:58:22 |

| Chỉ số | Giá trị |
|---|---|
| Hit@3 / Hit@5 / Hit@6 | 0.0% / 0.0% / 0.0% |
| MRR | 0.0 |
| Citation P / R / F1 / EM | 15.6% / 13.0% / 13.4% / 12.5% |
| Number support | 98.4% |
| Bảo toàn thực thể sau chuẩn hóa | 96.7% |
| Từ chối đúng (câu ngoài corpus) | n/a — 0 câu được ghi nhận |
| Ảo giác trên câu ngoài corpus | 0 câu |
| Thời gian trung bình / câu | 14.0155 s |

Nguồn: `outputs/evaluation_summary_100v2_offline.md`, `outputs/evaluation_summary_judge15.md`, `outputs/evaluation_results_*.json`.

**Không dùng lượt này làm baseline.** Hit@K và MRR bằng 0 trong khi Citation F1 = 13.4% và number support = 98.4%; đồng thời `n_refusal_cases = 0` trong khi benchmark v2 có 3 câu ngoài corpus (lượt chính ghi nhận 3 câu). Các chỉ số không nhất quán với nhau và hai bộ file bị trùng lặp, nên chỉ lưu vết lịch sử tại đường dẫn gốc — không copy vào thư mục baseline theo danh sách P0.2.

## 5. Sử dụng

- **Lượt A/B giai đoạn 4 chạy trên benchmark v3** (12 khóa v2 + `question_type`). Baseline v2 trong thư mục này là **tham chiếu phụ**; số liệu v3 sẽ lệch nhẹ nếu P1.2/P1.3 sửa ground truth. Không lấy số v2 làm ngưỡng trực tiếp cho v3.
- Khi cần đối chiếu với quá khứ, dùng **lượt chính 2026-10-18T08:34:35** (mục 2). Không dùng lượt 00:58:22 (mục 4).
- Cả hai lượt 100 câu hiện có đều dùng **Qwen offline, giám khảo tắt**: chỉ Hit@K/MRR đáng tin; Citation/Faithfulness chỉ tham khảo. Nếu P4 chạy generator Gemini, phải có baseline `ENABLE_CLASSIFIER=0` cùng cấu hình trên v3 trước khi so sánh — không so chéo cấu hình.
- Mọi phép so sánh A/B phải dùng cùng benchmark v3, cùng top_k, cùng generator, cùng giám khảo; ghi các tham số đó vào báo cáo P4.

## 6. Ghi chú toàn vẹn

- 5 file được copy bằng Python `shutil.copy2`; kích thước byte và SHA1 của bản copy khớp nguồn tại thời điểm copy.
- Không sửa, không xóa, không chạy lại bất kỳ file nào trong `outputs/` hay `logs/benchmark/`.
- Snapshot ngày 2026-10-20; nếu nguồn `outputs/` hoặc `logs/benchmark/` thay đổi sau ngày này, baseline vẫn giữ nguyên bản đã ghim trong thư mục này.
