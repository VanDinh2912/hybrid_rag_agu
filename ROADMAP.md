# ROADMAP — Hướng làm lại đồ án

> Phiên bản 1.0 · Ngày 2026-10-20 · Trạng thái: **chờ người dùng duyệt** (cổng P0.1)
> Văn bản định hướng cho toàn bộ P0.2 → P5.4; chi tiết từng nhiệm vụ xem `prompts/README.md`.

## 1. Tên đề tài mới

**"Ứng dụng kiến trúc RAG phân loại câu hỏi và hỗ trợ truy xuất thông tin quy chế đào tạo sinh viên"**

Hướng làm lại kế thừa nguyên vẹn pipeline True Hybrid Search 4 tầng đang chạy ổn định, bổ sung **tầng phân loại câu hỏi 2 nhãn** (chủ đề + loại câu hỏi) và **router truy xuất theo lớp câu hỏi**, sau đó đánh giá A/B có/không có tầng phân loại trên cùng bộ 100 câu.

## 2. Mục tiêu & câu hỏi nghiên cứu

**Mục tiêu:** xây bộ phân loại gán đồng thời hai nhãn cho mỗi câu hỏi — `category` thuộc đúng 14 nhóm chủ đề của benchmark và `question_type` thuộc 4 nhãn cố định `TRA_CUU` / `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI`; dùng nhãn để chọn cấu hình truy xuất (router) và biến thể prompt sinh câu trả lời; đo chất lượng trên benchmark v3 (100 câu, 13 khóa = 12 khóa v2 + `question_type`) và so sánh A/B với baseline `ENABLE_CLASSIFIER=0`.

**Ba câu hỏi nghiên cứu:**

1. Bộ phân loại 2 nhãn (chủ đề + loại câu hỏi) đạt độ chính xác bao nhiêu trên 100 câu?
2. Router truy xuất theo lớp câu hỏi cải thiện Hit@K/MRR ở những nhóm câu nào so với cấu hình truy xuất chung?
3. Bật tầng phân loại có tốt hơn tắt trên tổng thể hay không, và có làm tụt chất lượng ở nhóm câu nào không?

## 3. Hiện trạng & mốc so sánh

### 3.1. Tài sản hiện có (tái sử dụng nguyên vẹn)

| Hạng mục | Hiện trạng | Nguồn |
|---|---|---|
| Corpus | 26 tài liệu (21 PDF + 5 DOCX) ở 3 tầng | `README.md` mục 8; kiểm tra `data/corpus/` ngày 2026-10-20 |
| Index sản xuất | 361 chunks, collection `agu_regulations` | `README.md` mục 5.1; `chroma_db/chroma.sqlite3` ngày 2026-10-20 |
| Truy xuất | BM25 + ChromaDB (bge-m3) hợp nhất bằng RRF, `c = 60`, trọng số 0.5/0.5 | `README.md` mục 1 |
| Generator | Gemini `gemini-2.5-flash` (temperature 0) + fallback Local Qwen + Soft Refusal | `README.md` mục 1, 5.2 |
| Bộ chỉ số | Hit@3/5/6, MRR, Citation Precision/Recall/F1/Exact Match, Faithfulness | `README.md` mục 5.5 |
| Unit test | 85 test offline | `pytest --collect-only` ngày 2026-10-20 |
| Benchmark hiện có | 100 câu v2, đúng 12 khóa, 14 nhóm chủ đề | `data/evaluation/benchmark_100_questions_v2.json` |

### 3.2. Chất lượng pipeline hiện tại

Lượt chạy ngày 2026-10-18 trên benchmark v2 (100 câu), generator Local Qwen, Top-K 6, giám khảo tắt:

| Chỉ số | Giá trị |
|---|---|
| Hit@3 / Hit@5 / Hit@6 | 59.8% / 63.9% / 65.0% |
| MRR (recall window) | 0.5076 |
| Citation F1 | 78.1% |
| Number support (không cần API) | 94.3% |
| Bảo toàn thực thể sau chuẩn hóa | 96.7% |
| Từ chối đúng (3 câu ngoài corpus) | 0.0% — cả 3 câu bị ảo giác *(chú thích 2026-10-21: số liệu đo sai do bug fold marker — phép so `REFUSAL_MARKER in fold(answer)` không bao giờ khớp vì marker còn dấu thanh; đã sửa 2026-10-21 trong P4.1, số thật sẽ có ở P4)* |

Nguồn: `outputs/evaluation_summary.md`, lượt 2026-10-18T08:34:35.

> Đây là mốc tham chiếu tạm thời: lượt chạy dùng generator Local Qwen và tắt giám khảo nên các chỉ số Citation/Faithfulness không đại diện cho pipeline Gemini. P0.2 sẽ ghim baseline chính thức (cùng generator, cùng Top-K, `ENABLE_CLASSIFIER=0`) trên benchmark v3 trước khi chạy A/B.

### 3.3. Đánh đổi giữa các chiến lược chunking

Lượt chạy ngày 2026-10-17 trên benchmark 50 câu, generator Local Qwen, Top-K 3, cửa sổ đo Hit@6 = 6:

| Chiến lược | Số chunk | Hit@3 | Hit@5 | Hit@6 | MRR | Citation F1 |
|---|---|---|---|---|---|---|
| fixed | 182 | 0.8800 | 0.9000 | 0.9000 | 0.6983 | 0.0000 |
| recursive | 189 | 0.7400 | 0.8800 | 0.9000 | 0.6687 | 0.0067 |
| structure | 378 | 0.7600 | 0.8800 | 0.9200 | 0.7160 | 0.0767 |

Nguồn: `logs/benchmark/summary_comparison_report.md`, lượt 2026-10-17 23:36:01.

> Citation F1 thấp do generator Local Qwen 1.5B — chỉ nên đọc bảng này để so sánh tương đối giữa ba chiến lược. Kết quả cho thấy mỗi cấu hình mạnh ở một nhóm chỉ số khác nhau (fixed mạnh Hit@3, structure mạnh MRR/Hit@6), là động lực để router chọn cấu hình truy xuất theo lớp câu thay vì dùng một cấu hình chung.

## 4. Phạm vi làm lại

| Hạng mục | Sản phẩm | Nội dung |
|---|---|---|
| Bộ phân loại 2 nhãn | `src/classifier.py` | Qwen few-shot trả `category` (14 nhóm) + `question_type` (4 nhãn cố định); guardrail 3 lớp; phân loại lỗi thì suy giảm mềm (nhãn dự phòng/cấu hình chung), không làm chết pipeline |
| Router truy xuất | `src/router.py` | Ánh xạ cặp nhãn → cấu hình truy xuất (số chunk, trọng số RRF, mở rộng truy vấn, bộ lọc tầng tài liệu…); cấu hình chung vẫn là đường lùi |
| Tách truy vấn con cho câu so sánh | Module/pipeline hiện có, chốt ở P3.3 | Tách câu `SO_SANH` thành các vế và truy xuất đủ ngữ cảnh cho từng vế trước khi tổng hợp |
| Prompt biến thể theo loại câu | `src/generator.py` | Prompt khác nhau cho 4 loại câu; `NGOAI_PHAM_VI` chỉ nhắc từ chối thêm, **không bỏ qua truy xuất** để tránh từ chối oan câu đúng |
| Đánh giá A/B + chỉ số phân loại | `src/evaluation.py` | Cờ `--with-classifier`; thống kê kết quả theo nhóm chủ đề/loại câu; đo accuracy, confusion matrix của bộ phân loại |
| Demo hiển thị nhãn | CLI, `ui/app.py`, `demo_streamlit.py` | Hiển thị 2 nhãn và cấu hình truy xuất đã chọn ở chế độ bật classifier |
| Công tắc an toàn | `ENABLE_CLASSIFIER` | `0` = giữ hành vi pipeline cũ nguyên vẹn 100%; `1` = bật classifier + router. Đề xuất mặc định `0`, P0.3 chốt khi khai báo |

Nguồn phạm vi: `prompts/P0_1_direction_doc.md` (mục "Phạm vi làm lại") và `prompts/README.md`; số liệu tái sử dụng lấy từ `README.md` và kiểm tra trực tiếp ngày 2026-10-20.

**Tái sử dụng nguyên vẹn, không làm lại:** corpus 26 tài liệu, index 361 chunks, hybrid search BM25 + Chroma, generator trích dẫn Điều/Khoản + Soft Refusal, bộ chỉ số Hit@K/MRR/Citation/Faithfulness, 85 unit test hiện có. Benchmark v2 được nâng thành v3 bằng cách thêm khóa `question_type`, không đổi câu hỏi và ground truth.

## 5. Ngoài phạm vi

- Không đổi model OCR, không xử lý lại chất lượng dấu thanh của corpus.
- Không train mới hoặc fine-tune embedding (giữ `BAAI/bge-m3`).
- Không đổi vector database (giữ ChromaDB).
- Không mở rộng corpus ra tài liệu ngoài quy chế học vụ AGU.

Mọi đề xuất vượt bốn mục trên cần người dùng duyệt riêng trước khi đưa vào kế hoạch.

## 6. Tiêu chí thành công định lượng

| Tiêu chí | Ngưỡng | Đo tại |
|---|---|---|
| Accuracy nhãn chủ đề | ≥ 85% trên 100 câu v3 | P2.3, log trong `logs/classifier/` |
| Accuracy nhãn loại câu hỏi | ≥ 80% trên 100 câu v3 | P2.3, log trong `logs/classifier/` |
| Recall lớp thiểu số | Mỗi lớp `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI` ≥ 50% — bổ sung 2026-10-20 vì TRA_CUU chiếm 85% khiến accuracy tổng không đủ chứng minh | P2.3, log trong `logs/classifier/` |
| A/B tổng thể | Hit@K và MRR không giảm quá **5% tương đối** so với baseline `ENABLE_CLASSIFIER=0`; ngưỡng chính thức chốt tại P4.3 | P4.3 |
| Nhóm câu cải thiện | Ít nhất 1–2 nhóm câu tăng rõ, báo cáo cả chênh lệch tuyệt đối và tương đối | P4.3 |
| Unit test | Toàn bộ test xanh, chạy offline hoàn toàn, không tốn quota | P2.2, P3.2, P4.1 |
| Bất biến tương thích | `ENABLE_CLASSIFIER=0` cho hành vi pipeline cũ nguyên vẹn 100% | P3.2, P5.4 |

Nguồn ngưỡng: `prompts/P0_1_direction_doc.md` và `prompts/README.md` (mục "Các điểm BẠN phải quyết"). Ngưỡng 5% tương đối là đề xuất, sẽ chốt cùng người dùng tại P4.3.

## 7. Kế hoạch 6 giai đoạn

| GĐ | Thời lượng | Nội dung chính | Sản phẩm / cổng |
|---|---|---|---|
| 0 — Chốt hướng & mốc so sánh | 2–3 ngày | Chốt ROADMAP, ghim baseline số liệu pipeline cũ, khai báo `ENABLE_CLASSIFIER` | ROADMAP (duyệt) · baseline snapshot · feature flag |
| 1 — Thiết kế bộ nhãn | 3–5 ngày | `TAXONOMY.md` (14 chủ đề + 4 loại + luật gán); gán nhãn 100 câu → benchmark v3; verify độc lập | TAXONOMY (duyệt) · bảng nhãn v3 (duyệt) · GATE verify 100% |
| 2 — Bộ phân loại v1 | 1–2 tuần | `src/classifier.py` Qwen few-shot + guardrail; unit test offline; đo accuracy 100 câu | GATE: chủ đề ≥ 85% và loại câu ≥ 80% |
| 3 — Router truy xuất theo lớp | 1–2 tuần | `src/router.py`, tích hợp qua feature flag, tách truy vấn con cho `SO_SANH`, prompt theo loại câu, hiển thị nhãn ở CLI/GUI | pytest + smoke 2 chế độ (bật/tắt) |
| 4 — Đánh giá A/B | 1 tuần | Cờ `--with-classifier`, chạy 2 lượt 100 câu trên v3, bảng so sánh + biểu đồ + nhận xét | P4.2 duyệt kế hoạch quota (~400 request, giảm nhờ cache) · GATE không tụt quá 5% tương đối |
| 5 — Demo & báo cáo | 1–2 tuần | Demo Streamlit hiển thị nhãn, `SYSTEM_ARCHITECTURE.md` 6 tầng, chương 3–4, README chốt | GATE cuối: smoke xanh |

Nguồn: `prompts/README.md` (bảng nhiệm vụ, thời lượng từng giai đoạn và các cổng kiểm tra).

---

Mọi số liệu trong văn bản này được chép nguyên từ nguồn ghi dưới từng bảng; không có số liệu ước lượng.
