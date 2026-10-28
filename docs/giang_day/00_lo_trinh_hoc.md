# Chương 00 — Lộ trình học đồ án

> **Mục tiêu chương:** sau 45–60 phút, bạn biết repo gồm những phần nào, mỗi phần
> chịu trách nhiệm gì, và có một lịch học 14 ngày để đi từ “đọc code” đến “bảo vệ
> được trước hội đồng”.

---

## 1. Bạn đang học cái gì?

Đồ án là một hệ **Hybrid RAG** (Retrieval-Augmented Generation lai) trả lời câu hỏi
về quy chế Trường Đại học An Giang. “Hybrid” ở đây không phải chỉ là “hai model”;
nó là **hai họ truy xuất** chạy song song rồi hợp nhất:

- **BM25** — khớp từ khóa chính xác (mã môn, số Điều, thuật ngữ hành chính).
- **Vector search bằng bge-m3/ChromaDB** — khớp ngữ nghĩa, chịu được cách diễn đạt
  khác nhau.
- **RRF (Reciprocal Rank Fusion)** — hợp nhất hai bảng xếp hạng thành một.

Phía sinh chữ có hai tầng: **Gemini API** là tầng chính, **Qwen 1.5B local** là tầng
dự phòng và cũng đảm nhận các việc “nhỏ” hơn: viết lại câu hỏi, phân loại, tách
truy vấn con.

Điểm học thuật của đồ án không nằm ở “dùng Gemini”; nó nằm ở **bốn thực nghiệm có
đo lường**:

| Thực nghiệm | Câu hỏi nghiên cứu | Nơi đo |
|---|---|---|
| Chunking | Chia nhỏ văn bản theo Điều/Khoản có tốt hơn cắt 512 token? | `scripts/benchmark_chunking.py` |
| Phân loại | Qwen 1.5B có đủ tin để gán 14 chủ đề × 4 loại? | `src/assessment/evaluate_classifier.py` |
| Router + tầng phụ | Bật classifier/router có làm truy xuất tốt hơn không? | A/B `--with-classifier` |
| Chống ảo giác | Tỉ lệ từ chối đúng và trích dẫn đúng là bao nhiêu? | `src/assessment/evaluation.py` |

Bốn câu hỏi này là xương sống khi bảo vệ. Mỗi chương sau đều quay lại một trong bốn
cột này.

---

## 2. Bản đồ trách nhiệm (đọc theo chiều dữ liệu)

```
NGƯỜI DÙNG
   │  câu hỏi thô ("rớt môn có đc học lại k ad")
   ▼
[1] Chuẩn hóa câu hỏi        src/generation/local_slm.py + src/core/query_normalizer.py
   │  câu học vụ + guardrail số/token
   ▼
[2] Phân loại (tùy chọn)      src/core/classifier.py
   │  14 chủ đề × 4 loại
   ▼
[3] Router (tùy chọn)         src/retrieval/router.py
   │  top_k, trọng số BM25/Chroma, lọc nguồn, bật sub-query
   ▼
[4] Mở rộng & tách truy vấn  src/retrieval/retrieval.py
   │  + từ đồng nghĩa; tách 2–3 vế cho câu so sánh
   ▼
[5] Truy xuất lai            src/retrieval/vector_db.py + src/core/pipeline.py
   │  BM25 + Chroma → RRF → retrieve_k ứng viên
   ▼
[6] Sinh câu trả lời         src/generator.py
   │  prompt grounded + cache + Gemini/Qwen + trích dẫn
   ▼
[7] Trả kết quả              main.py / ui/demo_streamlit.py / evaluation.py
```

Mỗi mũi tên là một **hợp đồng dữ liệu**. Khi debug, câu hỏi đầu tiên luôn là:
“Tôi đang đứng ở mũi tên nào, dữ liệu vào/ra đúng schema chưa?”

---

## 3. Ai gọi ai? Ba entrypoint

| Entrypoint | Mục đích | Có gọi Gemini? | Có ghi DB? |
|---|---|---|---|
| `python ingest.py` | Nạp corpus → chunk → nhúng → ChromaDB | Không | Có (xóa và tạo lại) |
| `python main.py "câu hỏi"` | Hỏi–đáp thật | Có (hoặc Qwen nếu `USE_QWEN_GENERATOR=1`) | Không |
| `python evaluation.py` | Chạy benchmark 100 câu, ghi JSON/Markdown | Có (Generator + Judge) | Không (đọc DB) |
| `python scripts/learn.py` | Test & học có trọng tài, lưu cặp sửa | Có | Có (rebuild index) |
| `python scripts/benchmark_chunking.py` | So sánh 3 chiến lược chunking | Có (hoặc Qwen) | Có (3 DB riêng) |
| `streamlit run ui/demo_streamlit.py` | UI so sánh 3 chiến lược | Tùy chọn | Có (DB demo) |

Điểm cần nhớ: **`main.py` không index lại corpus**. Nó nối ChromaDB đã persist và chỉ
nhúng **câu hỏi**. Nếu sửa `data/corpus/`, phải chạy lại `ingest.py`, nếu không
retrieval vẫn đọc dữ liệu cũ.

---

## 4. Lịch học 14 ngày

Mỗi ngày 1.5–2 giờ. Ngày lẻ là “hiểu”, ngày chẵn là “làm”.

| Ngày | Đọc | Làm | Đầu ra kiểm chứng |
|---|---|---|---|
| 1 | Chương 00, 01 | Chạy `ingest.py`, hỏi 3 câu | Giải thích được `retrieve_k` vs `top_k` |
| 2 | Chương 02 (nửa đầu) | Mở 1 PDF, đối chiếu chunk sinh ra | Chỉ ra được 1 chunk bị OCR mất dấu |
| 3 | Chương 02 (nửa sau) | Chạy 3 chiến lược chunking trên 1 văn bản | So sánh số chunk & độ dài |
| 4 | Chương 03 | In `fold()` cho 5 câu, thử BM25 vs vector | Giải thích được vì sao phải fold trước khi embed |
| 5 | Chương 04 (chuẩn hóa) | Chạy Qwen viết lại 10 câu thô | Chỉ ra 1 ca guardrail chặn drift |
| 6 | Chương 04 (classifier) | Chạy `classify_query` 10 câu | Vẽ được ma trận nhầm lẫn tay |
| 7 | Chương 05 | Đọc `router.py`, tính cấu hình cho 4 nhãn | Vì sao NGOAI_PHAM_VI không bỏ truy xuất |
| 8 | Chương 06 (prompt/cache) | Đọc 1 file cache, tính lại SHA-1 | Giải thích cache invalidate khi nào |
| 9 | Chương 06 (quota/fallback) | Đọc 429 PerDay/phút trong code | Viết được cây quyết định retry |
| 10 | Chương 07 | Trace một câu hỏi bằng log | Chỉ ra 7 hợp đồng dữ liệu |
| 11 | Chương 08 (metrics) | Mở JSON, tính tay 1 Hit@3 và 1 Citation F1 | Khớp số trong summary |
| 12 | Chương 08 (A/B) | Đọc `outputs/ab_comparison.md` | Nêu 2 nhóm hưởng lợi, 1 nhóm đi lùi |
| 13 | Chương 09 | Chạy Streamlit, so sánh 3 tab | Giải thích Composite Score |
| 14 | Chương 10 + phụ lục | Trả lời 20 câu bảo vệ | Tự chấm ≥ 16/20 |

Nếu chỉ có 3 ngày trước bảo vệ: đọc 01, 03, 04, 06, 08 và học thuộc bảng số liệu
A/B. Bỏ qua phần UI.

---

## 5. Cách đọc một hàm trong repo

Mỗi hàm trong giáo trình được trình bày theo khung 5 dòng:

```
Tên hàm (file:dòng)
  Vào:      kiểu dữ liệu + ràng buộc
  Ra:       kiểu dữ liệu + bất biến (invariant)
  Vai trò:  một câu, không hơn
  Hỏng thì: hành vi suy giảm
```

Ví dụ:

```
fold (src/text_utils.py:13)
  Vào:      str bất kỳ (kể cả None → "none")
  Ra:       str thường, bỏ dấu, gom khoảng trắng
  Vai trò:  chuẩn hóa duy nhất để so khớp chữ có dấu và OCR mất dấu
  Hỏng thì: không ném lỗi; đây là hàm thuần, luôn trả chuỗi
```

Khi đọc code thật, luôn đọc **docstring trước, thân hàm sau**. Docstring trong repo
này thường ghi luôn *lý do thiết kế* và *số liệu thực nghiệm* — đó chính là chất liệu
để trả lời hội đồng.

---

## 6. Ba câu hỏi để tự kiểm tra sau chương này

1. Vì sao `evaluation.py` truyền `top_k=retrieve_k` vào `pipeline.run()` thay vì
   `top_k` thật của generator?
2. Nếu Ollama chết hoàn toàn, hệ thống còn trả lời được không? Tầng nào mất, tầng nào
   còn?
3. Vì sao phải chạy `ingest.py` lại sau khi thêm một PDF, trong khi `main.py` không
   tự làm việc đó?

Đáp án nằm rải ở chương 01, 06, 07; tự trả lời trước rồi hẵng đọc tiếp.

---

## 7. Bản đồ tài liệu hỗ trợ

| Tài liệu | Dùng khi |
|---|---|
| `README.md` (gốc) | Cài đặt, lệnh chạy, tính năng |
| `docs/architecture/SYSTEM_ARCHITECTURE.md` | Sơ đồ kiến trúc chi tiết, công thức |
| `docs/spec/TAXONOMY.md` | 14 chủ đề, 4 loại câu hỏi, luật phân giải |
| `docs/planning/ROADMAP.md` | Mã P1–P4 tương ứng giai đoạn nào |
| `docs/BAO_CAO_*.md` | Bản báo cáo học thuật, số liệu gốc |
| `data/training/README.md` | Dataset huấn luyện sinh từ repo |
| `outputs/ab_comparison.md` | Bảng A/B — nguồn của mọi con số “tăng bao nhiêu” |
| `logs/classifier/accuracy_report.md` | Accuracy classifier, bảng lỗi từng câu |

Tiếp theo: [01 — Tổng quan kiến trúc](01_tong_quan_kien_truc.md).
