# Hybrid RAG System for Academic Regulations (AGU Context)

Hệ thống Hỏi - Đáp tự động (RAG) cho tra cứu văn bản quy chế học vụ AGU, xây theo kiến trúc **True Hybrid Search**: **Local SLM (Qwen2.5 qua Ollama)** chuẩn hóa câu hỏi → **mở rộng truy vấn theo từ điển đồng nghĩa pháp lý** → **BM25 + Vector (bge-m3/ChromaDB) hợp nhất bằng RRF** → **Gemini API** (hoặc Local Qwen) sinh câu trả lời kèm trích dẫn Điều/Khoản.

Dự án có **bốn giao diện sử dụng**:

| Giao diện | File | Dành cho |
|---|---|---|
| CLI tương tác | `main.py` | Hỏi đáp hàng ngày, test nhanh |
| GUI desktop 3 tab (Tkinter) | `ui/app.py` | Tra cứu + nạp dữ liệu + gắn nhãn học |
| Đánh giá định lượng | `src/evaluation.py` | Đo Hit@K / MRR / Citation / Faithfulness trên benchmark |
| **Demo so sánh 3 chiến lược chunking (Streamlit)** | `demo_streamlit.py` | Trình diễn thực nghiệm cho bài báo |

Kèm hai công cụ thực nghiệm: **`benchmark_chunking.py`** (chạy benchmark đầy đủ 3 chiến lược cắt đoạn, xuất báo cáo so sánh) và **`src/evaluation.py`** (chạy benchmark truy xuất/generation trên một pipeline).

---

## 1. Kiến trúc hệ thống

**Các thành phần:**

- **Embedding Model:** `BAAI/bge-m3` — chạy cục bộ trên phần cứng, đa ngữ 1024 chiều, hỗ trợ tiếng Việt.
- **Vector Database:** `ChromaDB` — lưu trữ và truy xuất vector theo khoảng cách **Cosine Similarity**.
- **BM25 Retriever:** tìm kiếm từ khóa chính xác (mã môn học, "Điều 12", thuật ngữ viết tắt) — bộ tách từ kép: token nguyên văn + token đã bỏ dấu.
- **EnsembleRetriever (RRF):** gộp kết quả BM25 và Chroma bằng **Reciprocal Rank Fusion**; trọng số mặc định BM25 = 0.5, Chroma = 0.5, hằng số RRF `c = 60` (đổi được qua biến môi trường, xem mục 3).
- **Local SLM:** `Qwen2.5:1.5b-instruct` qua **Ollama** — hai vai: (1) chuẩn hóa câu hỏi ở đầu pipeline; (2) generator chính ở chế độ offline hoặc generator dự phòng khi Gemini hết quota.
- **Backend Generator:** **Gemini API (`gemini-2.5-flash`)** — tổng hợp ngữ cảnh, sinh câu trả lời kèm trích dẫn Điều/Khoản (`Temperature = 0.0`), có cơ chế **Soft Refusal** khi ngữ cảnh không đủ căn cứ.

**Luồng xử lý (4 tầng):**

```
Câu hỏi thô
   │
   ▼
[1] Chuẩn hóa câu hỏi (Local Qwen / Ollama)  ──► viết lại theo văn phong quy chế,
   │                                              chống bịa thông tin, bảo toàn con số/thực thể
   ▼
[2] Mở rộng truy vấn (Query Expansion)       ──► từ điển đồng nghĩa pháp lý (~50 cặp ánh xạ),
   │                                              so khớp không dấu theo word boundary
   ▼
[3] True Hybrid Search                        ──► BM25 (từ khóa, tokenizer kép)
   │                                              + ChromaDB (bge-m3, cosine)
   │                                              → EnsembleRetriever gộp bằng RRF
   ▼
[4] Sinh câu trả lời (Gemini / Qwen local)    ──► câu trả lời + trích dẫn Điều/Khoản;
                                                  thiếu căn cứ → Soft Refusal;
                                                  Gemini hết quota → Local Qwen (nhãn FALLBACK)
```

Hai cơ chế xuyên suốt các tầng:

- **`fold()`** (`src/text_utils.py`) — bỏ dấu thanh dùng chung cho mọi tầng: câu hỏi có dấu vẫn khớp được chunk OCR mất dấu ở tầng truy xuất và tầng đánh giá.
- **Oversampling** — mỗi lượt truy xuất lấy về `top_k × 2` ứng viên; chỉ `top_k` đứng đầu theo thứ hạng RRF được đưa vào generator, phần còn lại phục vụ đo Hit@K.

Đặc tả chi tiết (công thức BM25/cosine/RRF, sơ đồ luồng, bảng biến môi trường): xem `SYSTEM_ARCHITECTURE.md` (kèm bản `.docx`/`.txt` sinh tự động từ cùng một nguồn qua `export_architecture.py`).

---

## 2. Cấu trúc thư mục

```
hybrid_rag_agu/
│
├── data/
│   ├── corpus/              # 26 tài liệu ở 3 tầng (21 PDF + 5 DOCX), nguồn xây Vector DB
│   │   ├── Tầng 1/          # Quy chế/quyết định chính thức (6 PDF)
│   │   ├── Tầng 2/          # Kế hoạch, thông báo ngày (6 PDF)
│   │   ├── cac_file_bo_xung_khac/   # Thông báo học phí, CTĐT, khảo sát... (13 file + 1 DOCX)
│   │   └── ghi_chu_hoc_them.txt     # Bài học tự sinh khi dùng chế độ test & học
│   ├── evaluation/          # Bộ benchmark + checklist kiểm tra tay
│   │   ├── benchmark_100_questions_v2.json  # 100 câu v2 — MẶC ĐỊNH của src/evaluation.py
│   │   ├── benchmark_100_questions.json     # 100 câu v1
│   │   ├── benchmark_50_questions.json/.md  # 50 câu (mặc định của benchmark_chunking.py)
│   │   ├── benchmark_15_questions.json/.md  # bộ 15 câu đầu tiên
│   │   ├── benchmark_questions.json         # 15 câu GUI tự sinh (schema 10 khóa cũ)
│   │   └── reference/       # File quy chế mẫu (không index — chỉ dùng đối chiếu)
│   └── normalization_pairs.json   # Cặp (câu gốc → câu chuẩn hóa) cho Qwen học — GUI tự sinh
│
├── src/
│   ├── __init__.py
│   ├── chunking.py          # Cắt đoạn: DocumentChunker (ingest) + 3 chiến lược thực nghiệm
│   │                        #   fixed / recursive / structure-aware qua chunk_with_strategy()
│   ├── loader.py            # Đọc đệ quy .txt/.pdf/.docx + OCR PDF scan, gắn metadata tier
│   ├── text_utils.py        # fold() — bỏ dấu thanh dùng chung (OCR ↔ truy vấn có dấu)
│   ├── vector_db.py         # bge-m3 + ChromaDB; BM25 tokenizer; EnsembleRetriever (RRF)
│   ├── query_normalizer.py  # Tầng 1: chuẩn hóa câu hỏi bằng Qwen + active learning
│   ├── local_slm.py         # Wrapper Ollama + guardrail chống lệch nghĩa khi chuẩn hóa
│   ├── retrieval.py         # Tầng 2: từ điển đồng nghĩa + expand_query_with_synonyms()
│   ├── generator.py         # Sinh câu trả lời: Gemini + cache + fallback Qwen + Soft Refusal
│   ├── pipeline.py          # Nối 4 tầng, oversampling, tự lùi về vector search khi BM25 lỗi
│   └── evaluation.py        # Đánh giá định lượng: Hit@K, MRR, Citation F1, Faithfulness...
│
├── ui/
│   └── app.py               # GUI 3 tab: Tra cứu / Nạp dữ liệu / Vừa test vừa học
│
├── tests/                   # 85 unit test (chunking, pipeline, local_slm, evaluation) — offline
├── notebooks/               # Chỗ chứa Jupyter Notebook thực nghiệm (hiện đang trống)
│
├── logs/                    # MỌI file tự sinh khi chạy — quy ước chi tiết ở logs/README.md
│   ├── benchmark/           # Output của benchmark_chunking.py (log, results_all.json, chroma_*/) — xóa được
│   ├── export/              # Biên nhận export SYSTEM_ARCHITECTURE — xóa được
│   ├── learning/            # learning_log.csv — lịch sử "học thêm" (GIỮ, được git track)
│   └── feedback/            # user_feedback.json — phản hồi người dùng từ GUI (GIỮ, được git track)
│
├── outputs/                 # Kết quả CHỐT dùng cho báo cáo (git track)
│   ├── evaluation_results.json
│   └── evaluation_summary.md
│
├── .maestro/
│   └── playbooks/           # Quy tắc cộng tác đa-agent (4 group + base_prompt) — xem mục 7
│
├── chroma_db/               # ChromaDB đã persist (ingest.py tự sinh — gitignored)
├── .ocr_cache/              # Cache kết quả OCR (tự sinh, xóa được — lần nạp sau sẽ OCR lại)
├── .generation_cache/       # Cache câu trả lời Gemini (tự sinh, xóa được — lượt sau sẽ gọi API lại)
│
├── main.py                  # Chế độ chạy thực: CLI tương tác, hỏi liên tục
├── ingest.py                # Script nạp corpus vào ChromaDB (chạy trước main.py)
├── learn.py                 # Chế độ test & học qua CLI: sai thì dạy lại, ghi log logs/learning/
├── benchmark_chunking.py    # Benchmark 3 chiến lược chunking → logs/benchmark/
├── demo_streamlit.py        # Demo Streamlit so sánh 3 chiến lược chunking
├── export_architecture.py   # Xuất SYSTEM_ARCHITECTURE.md sang .txt/.docx (báo cáo ghi logs/export/)
│
├── SYSTEM_ARCHITECTURE.md   # Đặc tả kiến trúc True Hybrid Search (nguồn duy nhất)
├── SYSTEM_ARCHITECTURE.docx / .txt   # Hai định dạng xuất tự động từ .md — CẤM sửa tay riêng lẻ
├── NORMALIZATION_ACTIVE_LEARNING.md  # Cơ chế học chuẩn hóa từ phản hồi người dùng
├── TROUBLESHOOTING_GUI.md   # Xử lý sự cố thường gặp của GUI
├── LAYOUT_OPTIMIZATION.md   # Ghi chú tối ưu layout Tab 3
├── .env.example             # File mẫu khai báo biến môi trường (API Key)
├── requirements.txt         # Danh sách các thư viện Python cần thiết
└── requirements-lock.txt    # Ghim phiên bản đã kiểm chứng
```

---

## 3. Cài đặt môi trường làm việc

### Bước 1: Tạo môi trường ảo và cài thư viện

Đảm bảo bạn đang đứng ở thư mục gốc của dự án (`hybrid_rag_agu`):

```bash
python -m venv venv

# Trên Windows:
venv\Scripts\activate

# Trên macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` đã gồm nhóm thư viện OCR thuần pip (`pypdfium2`, `rapidocr-onnxruntime`, `Pillow`) — **không** cần cài Tesseract hay Poppler ở cấp hệ thống — cùng `pytest` để chạy bộ unit test.

**Riêng cho demo Streamlit** (mục 5.7) cần thêm 2 gói chưa đưa vào `requirements.txt`:

```bash
pip install streamlit pandas
```

### Bước 2: Cấu hình Ollama và mô hình Qwen

Tải và chạy mô hình Local SLM qua Ollama:

```bash
# Cài đặt Ollama tại: https://ollama.com
ollama pull qwen2.5:1.5b-instruct
ollama serve
```

`ollama serve` phải chạy ở một terminal riêng, để mở suốt quá trình hỏi đáp. Nếu Ollama tắt, hệ thống **không** dừng: `main.py` in cảnh báo ở bước `[2/3]` rồi dùng nguyên câu hỏi gốc để truy xuất (Local SLM là tầng tối ưu, không phải dependency cứng). Cơ chế fallback generator (Gemini hết quota → Qwen) cũng chỉ hoạt động khi Ollama đang chạy.

### Bước 3: Cấu hình biến môi trường

Tạo file `.env` từ file mẫu và điền thông tin:

```bash
# Trên Windows:
Copy-Item .env.example .env

# Trên macOS/Linux:
cp .env.example .env
```

Khai báo API key và cấu hình trong file `.env` (toàn bộ key đều có trong `.env.example` kèm chú thích):

```env
# Bắt buộc
GEMINI_API_KEY=your_gemini_api_key_here

# Có giá trị mặc định — chỉ khai báo khi muốn đổi
GEMINI_MODEL=gemini-2.5-flash
GEMINI_JUDGE_MODEL=              # model giám khảo Faithfulness của src/evaluation.py
                                 # (trống = dùng chung GEMINI_MODEL; nên đặt model khác
                                 #  vd gemini-3.5-flash-lite để tách ngân sách quota)
GEMINI_TEMPERATURE=0.0
GEMINI_MAX_TOKENS=4096
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b-instruct
OLLAMA_TIMEOUT=90
USE_QWEN_GENERATOR=0             # 1 = evaluation dùng Local Qwen làm generator (offline 100%)
EMBEDDING_MODEL=BAAI/bge-m3
CHROMA_PERSIST_DIR=./chroma_db
RAG_TOP_K=4

# True Hybrid Search — mặc định đã bật, chỉ khai báo khi muốn tắt/đổi trọng số
ENABLE_HYBRID_SEARCH=1           # 0 = tắt BM25, chỉ dùng vector search thuần
ENABLE_QUERY_EXPANSION=1         # 0 = tắt mở rộng từ đồng nghĩa
BM25_WEIGHT=0.5
CHROMA_WEIGHT=0.5

# Tối ưu quota & chống sập khi demo (mặc định đã bật)
GENERATION_CACHE=1
QWEN_FALLBACK=1

# OCR cho PDF scan ảnh (đều có mặc định)
OCR_ENABLED=1
OCR_DPI=200
OCR_MIN_CHARS_PER_PAGE=50
OCR_CACHE_DIR=./.ocr_cache
```

Vài giá trị cần lưu ý khi viết phần thực nghiệm:

- `GEMINI_MAX_TOKENS=4096` — `gemini-2.5-flash` là model "thinking": token suy luận nội bộ bị trừ **vào cùng** ngân sách `max_output_tokens`. Đo thực tế một lượt trả lời tốn 763 token thinking + 73 token trả lời, nên đặt 1024 sẽ làm câu trả lời **bị cắt giữa chừng**. Thư viện `google-generativeai` 0.8.6 chưa có `thinking_config` để tách riêng ngân sách, chỉ còn cách đặt lớn. `generator.py` vẫn in cảnh báo nếu `finish_reason = MAX_TOKENS`.
- `RAG_TOP_K=4` — số chunk ngữ cảnh mỗi lượt hỏi của `main.py`; flag `-k/--top-k` ghi đè giá trị này, và nếu `.env` không khai báo thì `main.py` dùng mặc định 6. `src/evaluation.py` và `benchmark_chunking.py` có cờ `--top-k` riêng (mặc định 6 và 3).
- `ENABLE_HYBRID_SEARCH` / `ENABLE_QUERY_EXPANSION` — hai công tắc của True Hybrid Search, mặc định **bật**; đặt `0` để lùi về vector search thuần (tiện so sánh có/không hybrid trong phần thực nghiệm). `BM25_WEIGHT` / `CHROMA_WEIGHT` là trọng số RRF của hai nhánh truy xuất.

---

## 4. Chuẩn bị dữ liệu

### 4.1. Đưa tài liệu vào thư mục `data/corpus/`

Loader (`src/loader.py`) quét đệ quy thư mục `data/corpus/`, hỗ trợ `.txt` (utf-8), `.pdf` (pypdf) và `.docx` (python-docx). Hiện trạng corpus: **26 file (21 PDF + 5 DOCX), không còn file `.doc` legacy**. File `.doc` (Word 97-2003) không trích xuất được — hãy `Save As` sang `.docx`.

PDF dạng scan ảnh thì loader **tự động OCR** mà không cần cài phần mềm hệ thống:

- **Render trang → ảnh:** `pypdfium2` (PDFium đóng gói sẵn trong wheel). Không dùng `pdf2image` vì thư viện đó bắt buộc cài **Poppler** ở cấp hệ thống, trái ràng buộc "chỉ cần pip".
- **Nhận diện ký tự:** `rapidocr-onnxruntime` — model PP-OCR dạng ONNX kèm sẵn trong package, chạy bằng `onnxruntime` trên CPU, không cần Tesseract. Engine được nạp một lần cho cả tiến trình.
- **Điều kiện kích hoạt — xét theo từng trang, không theo từng file:** trang nào `pypdf` trích ra dưới `OCR_MIN_CHARS_PER_PAGE` ký tự (mặc định 50) thì trang đó được OCR. Nhờ vậy PDF vừa có trang text vừa có trang chụp ảnh chỉ bị OCR đúng phần scan.
- **Cache:** kết quả OCR ghi vào `.ocr_cache/<tên_file>__<hash>.json`, khóa theo (kích thước, mtime, dpi, ngưỡng) nên sửa file PDF là cache tự hỏng. Bắt buộc phải có vì `learn.py` rebuild collection sau mỗi bài học — không cache thì mỗi lần học lại phải OCR lại toàn bộ. Xóa thư mục này để OCR lại từ đầu.
- **Tùy chọn trong `.env`:** `OCR_ENABLED` (`0` = tắt, file scan sẽ bị bỏ qua kèm cảnh báo), `OCR_DPI` (mặc định 200), `OCR_MIN_CHARS_PER_PAGE` (50), `OCR_CACHE_DIR` (`.//.ocr_cache`).

**Giới hạn chất lượng (cần ghi vào phần thực nghiệm của đề tài):** model PP-OCR kèm `rapidocr-onnxruntime` bắt đúng bố cục và chữ quốc ngữ nhưng **làm mất phần lớn dấu thanh** — "Điều 4. Hệ thống tổ chức" thành "Dieu 4. He thong to chuc". Hệ quả và cách xử lý trong mã nguồn:

| Ảnh hưởng | Xử lý |
|---|---|
| Mốc `Điều N.` không khớp regex → tài liệu rơi xuống fallback, mất cấu trúc Điều/Khoản | `ARTICLE_HEADING_RE` (`src/chunking.py`) nhận cả dạng mất dấu (`Dieu 4.`) và dạng lỗi font PDF (`Ðiều 4.`); `canonical_article()` trả tiêu đề chunk về đúng chính tả `Điều N.` |
| Trích dẫn sinh ra từ ngữ cảnh không dấu có thể sai chính tả | Tiêu đề chunk đã được chuẩn hóa thành `Điều N.` nên Generator trích dẫn đúng |
| Câu hỏi có dấu đầy đủ khó khớp chunk mất dấu khi truy xuất | Mọi truy vấn được `fold()` bỏ dấu trước khi so khớp/embed, và BM25 tokenizer sinh song song token nguyên văn + token bỏ dấu. Đo nhanh offline trên 7 câu hỏi khớp tài liệu OCR: Hit@5 từ 0/7 lên 7/7, top-1 đúng cả 7 |

Tăng `OCR_DPI` **không** cải thiện dấu: đo trên cùng một trang của `1054-qd-dhag-2020-09-28.pdf` cho 150/200/300 dpi lần lượt 2.012/2.080/2.076 ký tự nhưng chỉ 0/1/2 ký tự có dấu thanh. Nút thắt là model nhận diện, không phải độ phân giải — muốn giữ dấu đầy đủ phải đổi sang model OCR tiếng Việt chuyên biệt (ngoài phạm vi thuần pip).

### 4.2. Phân tầng tài liệu và chiến lược cắt đoạn

**Metadata phân tầng:** tên thư mục con cấp 1 trong `data/corpus/` chính là `tier` của tài liệu (`Tầng 1`, `Tầng 2`, `cac_file_bo_xung_khac`); file nằm ngay gốc `data/corpus/` nhận tier `Khác`. Mỗi chunk lưu vào ChromaDB mang bộ metadata `{"tier", "source", "chunk_id"}`, nên có thể đo Recall@K riêng cho từng tầng:

```python
vector_db.similarity_search(query, k=5, filter={"tier": "Tầng 2"})
```

`src/chunking.py` hiện có **hai lớp API** phục vụ hai mục đích khác nhau:

**Lớp 1 — `DocumentChunker` (đường sản xuất, `ingest.py` dùng):** tự chọn chiến lược theo nội dung từng văn bản qua `has_article_structure()`:

| Văn bản | Chiến lược | Kết quả |
|---|---|---|
| Quy chế/quy định có `Điều N.` đầu dòng | `structure_aware_chunking` | Mỗi Điều một chunk; Điều quá dài (nuốt cả Phụ lục) được cắt tiếp thành `(phần i/n)`; phần mở đầu (quốc hiệu, số hiệu, căn cứ) thành chunk riêng |
| Thông báo, kế hoạch, công văn, đơn, bản mô tả CTĐT | `fallback_chunking` | Cắt theo ranh giới câu, gộp tới ~1200 ký tự (~600 token bge-m3), overlap 150 ký tự giữa các chunk liền kề |

Mọi chunk đều mang tiền tố `[Tên văn bản]` (và `- [Điều N.]` nếu có) để giữ ngữ cảnh khi truy xuất.

**Lớp 2 — ba chiến lược cắt đoạn cho thực nghiệm (API `chunk_with_strategy`):** dùng chung bởi `benchmark_chunking.py` và `demo_streamlit.py`, cho phép so sánh công bằng trên cùng một tokenizer:

| Khóa | Tên | Cách cắt |
|---|---|---|
| `fixed` | Fixed-size | Cắt cứng theo mốc 512 token, overlap 0 |
| `recursive` | Recursive | Cắt đệ quy theo cấp bậc phân tách `"\n\n" → "\n" → câu → từ`, 512 token |
| `structure` | Structure-aware | Cắt theo Điều/Khoản/Điểm; tiền tố metadata phân cấp `[Tên văn bản] - [Điều N.] - [Khoản x-y] - [Điểm a-b]` ở ĐẦU chunk; Điều vượt ngân sách được cắt tiếp đệ quy thành `(phần i/n)` |

Đặc điểm chung của cả 3 chiến lược: mốc `DEFAULT_MAX_TOKENS = 512`, đếm token bằng tokenizer HuggingFace của chính bge-m3 (`get_token_counter("BAAI/bge-m3")`, lỗi thì lùi về đếm từ), và **khóa nguyên khối bảng Markdown** (`lock_markdown_tables=True`) — bảng dài hơn ngưỡng vẫn giữ thành 1 chunk thay vì cắt làm hai, vì hàng tách khỏi tiêu đề cột thì embedding vô nghĩa.

Trên corpus hiện tại (26 tài liệu), 3 chiến lược cho 3 index khác nhau: **fixed = 182 chunks, recursive = 189, structure = 378** (lượt dựng 16/10/2026 — chính là số liệu so sánh của demo).

---

## 5. Sử dụng

### 5.1. Nạp corpus vào ChromaDB (`ingest.py`)

```bash
python ingest.py                            # Nạp corpus → ChromaDB (chạy lại mỗi khi thêm/sửa tài liệu)
```

Đường đi: `DocumentLoader` đọc + OCR toàn bộ corpus → `DocumentChunker` cắt chunk (lớp 1 ở mục 4.2) → `VectorStoreManager.create_vector_store()` nhúng bge-m3 và ghi vào `chroma_db/`. Collection cũ bị xóa trước khi index nên chạy lại nhiều lần không bao giờ nhân đôi chunks. Hiện trạng index sản xuất: **361 chunks**.

### 5.2. Chạy thực (CLI — `main.py`)

Chỉ truy vấn, DB chỉ đọc:

```bash
python main.py                              # Không tham số → vòng lặp hỏi đáp tương tác
python main.py "Điều kiện xét tốt nghiệp?"   # Một câu rồi thoát (dùng cho test nhanh/script)
python main.py -k 8                         # Đổi số chunk ngữ cảnh (mặc định lấy RAG_TOP_K)
```

`main.py` khởi động theo 3 bước và **không** embedding lại corpus: `[1/3]` nối thẳng ChromaDB đã persist (`vector_db._collection.count()` = 0 thì dừng và nhắc chạy `python ingest.py`), `[2/3]` dò Ollama với timeout 5s, `[3/3]` nạp `GeminiGenerator` (thiếu `GEMINI_API_KEY` hoặc key còn là placeholder thì dừng ngay). Ngay sau đó pipeline dựng chỉ mục BM25 + `EnsembleRetriever` và in dòng `[HybridSearch] Đã kích hoạt True Hybrid Search (BM25=0.50 + Chroma=0.50, c=60).`; nếu BM25 lỗi (collection rỗng, thiếu thư viện...), hệ thống tự lùi về vector search thuần kèm cảnh báo.

**Lần khởi động đầu phiên chậm hơn các lần sau (khoảng 30–45 giây):** phần lớn thời gian là nạp mô hình embedding `bge-m3` (~25s), nạp lạnh Qwen lần đầu (~9s) và dựng chỉ mục BM25 từ toàn bộ collection. Các lượt hỏi sau chỉ còn tốn thời gian chuẩn hóa + truy xuất + sinh câu trả lời.

Trong vòng lặp tương tác, mỗi lượt hỏi đi qua 7 bước:

| # | Bước | Module | Suy giảm khi lỗi |
|---|---|---|---|
| 1 | Nhận câu hỏi thô từ bàn phím | `main.py` | `Ctrl+C` hủy lượt đó, `Ctrl+D`/`exit` thoát |
| 2 | Chuẩn hóa câu hỏi bằng Qwen (system prompt chống bịa + few-shot, tự nhận thêm ví dụ học từ phản hồi GUI) | `query_normalizer.normalize_user_query` | In cảnh báo → dùng nguyên câu hỏi gốc |
| 3 | Mở rộng truy vấn bằng từ điển đồng nghĩa pháp lý | `retrieval.expand_query_with_synonyms` | Tắt bằng `ENABLE_QUERY_EXPANSION=0` |
| 4 | Truy xuất True Hybrid `retrieve_k = top_k × 2` (BM25 + Chroma qua RRF; nhánh vector nhận câu đã `fold()`) | `pipeline.retrieve` / `EnsembleRetriever` | BM25/Ensemble lỗi → tự lùi về `similarity_search` thuần vector |
| 5 | Dựng ngữ cảnh: `top_k` chunk đầu (kèm `Nguồn / Tầng / chunk_id`); `sources` giữ đủ `retrieve_k` cho đánh giá | `pipeline.run` | — |
| 6 | Sinh câu trả lời + trích dẫn Điều/Khoản; ngữ cảnh rỗng → trả `REFUSAL_TEXT` ngay, **không** gọi API | `generator.generate_answer` | `GeneratorError` in ra, vòng lặp vẫn sống |
| 7 | In 4 khối: câu hỏi gốc / câu hỏi chuẩn hóa / nguồn trích dẫn / câu trả lời | `main.py` | — |

Một lượt hỏi lỗi (Gemini quá tải, mất mạng, Ollama tắt) **không** làm chết vòng lặp: ngoại lệ được bắt trong `ask_once()` và in thành một khối `[LỖI]`.

Các lệnh trong vòng lặp: `help`/`h`/`?` (in hướng dẫn), `exit`/`quit`/`thoat`/`thoát`/`q` (kết thúc).

**Về tính trung thực của câu trả lời (chống ảo giác):** `PROMPT_RULES` trong `src/generator.py` ràng buộc Gemini chỉ dùng ngữ cảnh được cấp, mỗi ý phải kèm căn cứ dạng `(Điều 12, Khoản 3 — <tên văn bản>)` lấy từ dòng `Nguồn:` thật (không được viết "(Ngữ cảnh 1)"), ưu tiên tier cao hơn khi các nguồn mâu thuẫn, và nếu thiếu căn cứ thì trả lời đúng một câu từ chối `REFUSAL_TEXT` = `"Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."` (cơ chế **Soft Refusal**: ngữ cảnh rỗng thì trả về câu này ngay mà không gọi API). Chuỗi này là hằng số module để tầng đánh giá đối sánh được.

**Tiết kiệm quota & chống sập khi demo (caching + fallback Local Qwen trong `generator.py`):**

- **Response caching:** trước khi gọi API, `generate_answer` tính SHA-1 của `{model, temperature, prompt}` và tra `./.generation_cache/<sha1>.json` — trúng thì trả lời ngay, tốn **0 request quota**. Key bám theo nội dung prompt nên thêm/sửa tài liệu rồi ingest lại là cache cũ tự vô hiệu, không cần dọn tay. Chỉ câu trả lời **nguồn Gemini** được cache; muốn đo latency thật (không tính thời gian đọc cache) hoặc ép sinh lại thì đặt `GENERATION_CACHE=0` trong `.env` hoặc xóa thư mục `.generation_cache/`.
- **Fallback Local Qwen:** Gemini trả về 429/hết quota ngày/phút hay sự cố 5xx, `generate_answer` **không văng lỗi** mà chuyển câu hỏi + các chunk ngữ cảnh sang Qwen trên Ollama (num_ctx 8192 để không bị cắt ngữ cảnh), gắn nhãn đầu câu trả lời `[Cảnh báo: Gemini đã hết quota — câu trả lời này được tổng hợp tạm thời bằng Local Qwen ...]` để người nghe demo phân biệt ngay. Câu fallback **không được cache** để lượt chạy sau vẫn được thử lại Gemini thật. Cả Ollama cũng chết thì mới ném `GeneratorError` — `main.py` đã bắt nên vòng lặp vẫn sống. Tắt cơ chế này bằng `QWEN_FALLBACK=0`.
- Trong `src/evaluation.py` và `benchmark_chunking.py`, fallback bị **tắt bắt buộc** khi chạy chế độ Gemini (`qwen_fallback = False`): nếu để bật, câu trả lời Qwen sẽ làm nhiễu các chỉ số Citation/Faithfulness vốn đang đo chất lượng pipeline Gemini.

### 5.3. Giao diện đồ họa (GUI — `ui/app.py`)

```bash
python ui/app.py
```

App Tkinter 3 tab, backend khởi tạo ở luồng nền ngay khi mở (nên vài chục giây đầu giao diện vẫn thao tác được trong lúc nạp model):

| Tab | Chức năng |
|---|---|
| **1. Tra cứu (Search)** | Đặt câu hỏi như CLI; kết quả gồm tab con "Câu trả lời" và "Nguồn trích dẫn (ChromaDB)"; log backend hiển thị trực tiếp trên cửa sổ |
| **2. Nạp dữ liệu (Ingest & Learn)** | Rebuild và nạp lại corpus vào ChromaDB ngay trong app (log streaming từng bước) — dùng sau khi thêm/sửa tài liệu trong `data/corpus/` |
| **3. Vừa test vừa học (Feedback)** | Chạy câu hỏi rồi tự gắn nhãn **Đúng / Sai**; nhãn Sai mở form nhập đáp án chuẩn + căn cứ + nguồn + câu chuẩn hóa |

Luồng lưu khi bấm "Sai" ở Tab 3:

1. Ghi phản hồi vào `logs/feedback/user_feedback.json` (cả hai nhãn đúng/sai đều được ghi).
2. Nếu điền đủ căn cứ + nguồn: bổ sung câu hỏi vào `data/evaluation/benchmark_questions.json` — lượt đánh giá sau dùng luôn.
3. Nếu có câu chuẩn hóa (auto-fill từ kết quả, sửa được trước khi lưu): thêm cặp (câu gốc → câu chuẩn hóa) vào `data/normalization_pairs.json` — Qwen tự học ở các lượt sau (active learning).
4. Nếu tick "học ngay": ghi bài học vào `data/corpus/ghi_chu_hoc_them.txt`, rebuild ChromaDB tại chỗ và ghi log vào `logs/learning/learning_log.csv`.

Chi tiết cơ chế học chuẩn hóa: `NORMALIZATION_ACTIVE_LEARNING.md`; sự cố thường gặp của GUI: `TROUBLESHOOTING_GUI.md`; ghi chú tối ưu layout Tab 3: `LAYOUT_OPTIMIZATION.md`.

### 5.4. Chế độ test & học (learn — `learn.py`)

Vòng lặp hỏi - đáp với người làm trọng tài (bản CLI của Tab 3):

```bash
python learn.py
```

Luồng hoạt động: nhập câu hỏi → hệ thống trả lời → bạn đánh giá (`Enter`/`y` = đúng, `n` = sai). Nếu sai, dán thông tin đúng (kết thúc bằng một dòng trống); hệ thống sẽ:

1. Ghi bài học vào `data/corpus/ghi_chu_hoc_them.txt` dưới dạng mục `Điều 1001., 1002., ...` tự sinh, nhờ đó mỗi bài học thành một chunk độc lập và trích dẫn được theo số Điều.
2. Rebuild collection ChromaDB ngay tại chỗ (tái dùng bge-m3 đã nạp, không reset thư mục).
3. Ghi 1 dòng log vào `logs/learning/learning_log.csv`: thời gian, câu hỏi, đáp án sai, thông tin đã học, số chunks trước/sau.

Cả `ingest.py` và learn mode đều xóa collection cũ trước khi index, nên chạy lại nhiều lần không bao giờ nhân đôi chunks. Muốn dọn các mục đã học, sửa tay `ghi_chu_hoc_them.txt` rồi chạy lại `python ingest.py`.

### 5.5. Đánh giá định lượng (`src/evaluation.py`)

Chạy đúng pipeline sản xuất (Qwen chuẩn hóa → mở rộng truy vấn → True Hybrid Search → Generator → giám khảo) trên từng câu của bộ benchmark — **mặc định là `data/evaluation/benchmark_100_questions_v2.json` (100 câu)**, đổi bằng cờ `--benchmark`. Mỗi câu hỏi đúng 12 khóa: `id, category, tier, in_corpus, source_document, raw_query, normalized_query, expected_answer, expected_citations, ground_truth_answer, ground_truth_citation, supplement_if_wrong`.

Hệ thống đo ba tầng chỉ số:

| Tầng | Chỉ số | Cách tính |
|---|---|---|
| Truy xuất | **Hit@3 / Hit@5 / Hit@6, MRR** | Mỗi câu pipeline truy xuất oversampled (2× cửa sổ generator); Hit@K = K kết quả đầu có chứa chunk thuộc `source_document` ground truth không; MRR = 1/thứ hạng chunk đúng đầu tiên trong toàn bộ cửa sổ truy xuất. So khớp tên nguồn **sau khi bỏ dấu** (`fold()`) |
| Trích dẫn | **Citation Precision / Recall / F1 / Exact Match** | Tập mã `Điều N [Khoản M]` rút từ câu trả lời so với `expected_citations`; hai bên quy về cùng token không dấu nên `"Điều 12"` khớp cả dạng OCR `"dieu 12"`; ghép cặp theo maximum-weight matching (khớp đủ Điều+Khoản = 1.0, trùng Điều một phía thiếu Khoản = 0.5) |
| Trung thực | **Faithfulness** | Gemini giám khảo (temperature 0, JSON mode, **không** mang system instruction của Generator) tách câu trả lời thành các khẳng định nguyên tố và đối chiếu từng khẳng định với ngữ cảnh; điểm = tỉ lệ khẳng định được hỗ trợ. Kèm `number_support` không tốn API: tỉ lệ con số trong câu trả lời xuất hiện trong ngữ cảnh |

Câu có `in_corpus=false` kiểm tra hành vi từ chối: hệ thống phải trả lời bằng câu chứa `REFUSAL_MARKER`, trả lời ra nội dung thì bị tính là **ảo giác ngoài corpus**. Trường `normalized_query` trong benchmark cho phép đo thêm chỉ số khắt khe `normalization_accuracy` (so khớp chuỗi chính xác); chỉ số chính hiện dùng là **`normalization_preservation`**: tỉ lệ thực thể (số Điều/Khoản, con số) trong câu hỏi gốc còn nguyên sau chuẩn hóa — so khớp regex không dấu, bỏ qua văn phong, khách quan hơn so khớp chuỗi.

```bash
python src/evaluation.py                        # benchmark 100 câu v2, top_k=6, có giám khảo Gemini
python src/evaluation.py --use-qwen-generator   # offline 100%: Local Qwen sinh câu trả lời (không tốn quota)
python src/evaluation.py --no-judge             # bỏ tầng giám khảo Faithfulness
python src/evaluation.py --limit 2              # chạy thử nhanh 2 câu đầu, tiết kiệm quota
python src/evaluation.py --judge-model gemini-3.5-flash-lite
                                                # giám khảo dùng model khác, tách ngân sách quota
python src/evaluation.py --benchmark data/evaluation/benchmark_50_questions.json
python src/evaluation.py --output outputs/custom_results.json
```

Kết quả: chi tiết từng câu ở `outputs/evaluation_results.json` (kèm câu trả lời, danh sách chunk truy xuất, trích dẫn dự đoán, khẳng định bị giám khảo loại), bảng Markdown tổng hợp ở `outputs/evaluation_summary.md` và in thẳng ra terminal. Câu lỗi (hết quota, mất mạng) được ghi nhận rồi bỏ qua, không làm chết lượt đánh giá; bấm `Ctrl+C` giữa chừng vẫn ghi kết quả phần đã chạy. Khi generator dính lỗi **hết quota ngày** (429 kèm `PerDay`), lượt chạy dừng sớm ngay vì các câu sau chắc chắn lỗi tương tự.

**Kết quả lượt chạy gần nhất** (14/10/2026 — `--limit 15` trên `benchmark_50_questions.json`, generator Local Qwen offline, giám khảo `gemini-3.5-flash-lite`, Top-K 6 — nguồn: `outputs/evaluation_summary.md`):

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 15/15 |
| Hit@3 / Hit@5 / Hit@6 | 26.7% / 33.3% / 46.7% |
| MRR (recall window) | 0.2138 |
| Citation Precision / Recall / F1 | 60.0% / 60.0% / 60.0% |
| Faithfulness (LLM judge) | 36.7% |
| Number support (không cần API) | 90.5% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 75.0% |
| Thời gian trung bình / câu | 11.9s |

Lưu ý khi đọc bảng này: generator là Local Qwen 1.5B nên tầng trích dẫn chủ yếu đo được trên các câu hệ thống tự chèn citation từ metadata; chạy lại không cờ `--use-qwen-generator` khi Gemini còn quota để có số liệu chính thức cho tầng Citation/Faithfulness của pipeline Gemini. Tỉ lệ Hit thấp một phần do lúc chạy này truy xuất ở Top-K 6 với cửa sổ rộng — hãy ghi rõ tham số khi so sánh các lượt chạy.

**Lưu ý quota** (free tier Gemini giới hạn **theo từng model**, ví dụ gemini-2.5-flash: ~5 request/phút và ~20 request/ngày):

- Mỗi câu tốn 2 lần gọi (generator + giám khảo), trừ câu trả lời dạng từ chối chỉ tốn 1 → lượt đánh giá đầy đủ 100 câu tốn ~200 request. Đặt `GEMINI_JUDGE_MODEL` trong `.env` (hoặc cờ `--judge-model`) sang một model khác, ví dụ `gemini-3.5-flash-lite`, để giám khảo dùng ngân sách riêng — generator giữ trọn quota của mình. Các lần chạy thử nên dùng `--use-qwen-generator` hoặc `--limit` để giữ quota cho lượt chính thức.
- Trước một lượt đánh giá đầy đủ, hạn chế chạy thử `main.py`/`learn.py` trong cùng ngày vì cùng xài chung quota model generator.
- **Caching làm các lần chạy lại gần như miễn phí:** câu nào đã trả lời thành công bằng Gemini một lần thì các lượt đánh giá sau lấy thẳng từ `.generation_cache/`, chỉ tốn quota cho câu mới và các câu giám khảo. Nếu lượt trước chết giữa chừng vì hết quota ngày, chỉ cần chạy lại đúng lệnh sau khi quota reset — không mất công trả lời lại từ đầu.
- Faithfulness phụ thuộc giám khảo nên khi viết bài cần ghi rõ model giám khảo và prompt (hằng `JUDGE_PROMPT` trong `src/evaluation.py`) vào phần thực nghiệm.

### 5.6. Benchmark 3 chiến lược chunking (`benchmark_chunking.py`)

Công cụ thực nghiệm trung tâm của đề tài: với **MỖI chiến lược chunking** (fixed / recursive / structure), script chạy trọn vòng trên cùng một testbed — nạp corpus → cắt chunk theo chiến lược đó → dựng một ChromaDB **độc lập** → chạy đúng pipeline sản xuất (Qwen chuẩn hóa → BM25 + bge-m3 RRF → generator, temperature 0) qua từng câu benchmark → đo Hit@3/5/6, MRR, Citation P/R/F1, Latency, dung lượng index → xuất log chi tiết từng câu + ma trận so sánh 3 chiến lược. Mọi hàm chấm điểm được **tái sử dụng** từ `src/evaluation.py` nên số liệu so sánh trực tiếp được với `outputs/evaluation_summary.md`.

```bash
python benchmark_chunking.py                        # đủ 3 chiến lược × 50 câu, Gemini
python benchmark_chunking.py --limit 2              # smoke test nhanh 2 câu
python benchmark_chunking.py --strategies structure # chỉ một chiến lược
python benchmark_chunking.py --generator qwen       # 100% offline, không tốn quota
python benchmark_chunking.py --no-cache             # tắt cache để đo Latency trung thực
python benchmark_chunking.py --device cuda          # Colab GPU T4
python benchmark_chunking.py --benchmark data/evaluation/benchmark_100_questions_v2.json
```

Mặc định chạy trên `benchmark_50_questions.json` với `--top-k 3` (generator nhận 3 chunk, cửa sổ đo Hit@K rộng 6 nhờ oversampling ×2). Đầu ra nằm ở **`logs/benchmark/`**:

| File | Nội dung |
|---|---|
| `log_fixed_size.txt` / `log_recursive.txt` / `log_structure_aware.txt` | Log chi tiết từng câu: query + ground truth, chunk truy xuất (kèm cờ GEN và ✓ đúng nguồn), câu trả lời, chỉ số |
| `summary_comparison_report.csv` / `.md` | Ma trận 3 chiến lược × 7 chỉ số chính + bảng chỉ số hạ tầng (số chunk, mean/max tokens, index size) — mở bằng Excel hoặc dán thẳng vào bài báo |
| `results_all.json` | Toàn bộ số liệu thô (meta tham số + per-question) — nguồn dữ liệu **replay** của demo Streamlit và để vẽ biểu đồ/chấm lại sau |
| `chroma_fixed/` / `chroma_recursive/` / `chroma_structure/` | Vector store độc lập của từng chiến lược (xóa được, chạy lại tự dựng) |

Lưu ý quota: 50 câu × 3 chiến lược = 150 lần gọi Gemini nếu dùng generator mặc định — hãy chạy thử `--limit 2` trước, hoặc dùng `--generator qwen`, hoặc chạy rải từng chiến lược một. Script tự dừng sớm (vẫn ghi báo cáo phần đã chạy) khi phát hiện lỗi quota ngày, và **tự gộp kết quả các lượt trước** có cùng tham số trong `results_all.json` nên chạy tách từng chiến lược bằng nhiều lệnh riêng vẫn ra đủ ma trận 3 dòng.

### 5.7. Demo Streamlit so sánh 3 chiến lược (`demo_streamlit.py`)

Lớp trình bày thuần túy cho phần thực nghiệm — **không cài lại bất kỳ logic backend nào**, chỉ gọi API có sẵn của `src/`:

```bash
# Cần cài thêm: pip install streamlit pandas
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m streamlit run demo_streamlit.py --server.fileWatcherType none
```

> ⚠️ **Bắt buộc kèm `--server.fileWatcherType none`** (hoặc `none` trong `.streamlit/config.toml`): watcher mặc định của Streamlit dò toàn bộ module `transformers` đã nạp và làm tiến trình chết im lặng giữa lượt chạy nặng.

Cấu trúc màn hình:

- **Sidebar:** Embedding model (cố định `BAAI/bge-m3`), chọn Generator (Qwen local offline — mặc định, hoặc Gemini API với `qwen_fallback` tự tắt), slider Top-K 1–5 (mặc định 3; generator nhận `top_k` chunk, hệ truy xuất lấy `top_k×2` để đo Hit@K), bật/tắt LLM Judge Faithfulness (`gemini-3.5-flash-lite`, tốn quota, mặc định tắt), bật/tắt **chế độ demo nhanh (replay)**, và 3 ô chỉnh trọng số Composite.
- **Nhập câu hỏi** ở 2 chế độ: *Câu từ benchmark* (selectbox từ `benchmark_50_questions.json`, hiển thị "Q01 · ..." — có ground truth nên chấm đủ Hit@K, MRR, Citation F1, Composite) hoặc *Câu tự do* (chỉ hiển thị Answer + chunk truy xuất + Latency; các ô cần ground truth hiển thị "—").
- **Nút "🚀 Chạy Đánh Giá RAG"** chạy tuần tự 3 chiến lược, mỗi chiến lược một `st.status` riêng + thanh tiến trình tổng (live mode mất ~30–60 giây/câu/chiến lược với Qwen local). Một chiến lược lỗi (Ollama chết, thiếu index) không làm app chết — 2 chiến lược còn lại vẫn hiển thị.
- **3 tab kết quả:** 🏆 *Câu Trả Lời Tối Ưu* (4 ô metric + câu trả lời của chiến lược thắng + căn cứ pháp lý + cảnh báo Soft Refusal nếu hệ thống từ chối — hành vi ĐÚNG với câu ngoài corpus); 📊 *Bảng So Sánh 3 Chiến Lược* (dataframe đúng thứ tự cột: Chiến lược | Composite | Hit@K | MRR | Faithfulness | Citation P | R | F1 | Latency | Số chunk, tô nổi dòng thắng); 🔍 *Chi Tiết Đoạn Truy Xuất* (3 cột cạnh nhau, mỗi chunk một expander kèm dấu ✓ nếu đúng nguồn ground truth — để soi đứt gãy ngữ cảnh giữa các chiến lược trên cùng một câu).

**Điểm chiến lược tối ưu:** `composite = w₁×Hit@K + w₂×Faithfulness + w₃×Citation_F1` (mặc định 0.4/0.3/0.3, chỉnh được ở sidebar, tự chuẩn hóa theo tổng trọng số khả dụng khi một thành phần thiếu); Faithfulness = điểm LLM Judge nếu bật, không thì dùng `number_support` (proxy miễn phí). Chỉ tính ở chế độ có ground truth; câu tự do chọn thắng theo Faithfulness proxy rồi đến Latency.

**Nguồn index của từng chiến lược** (theo thứ tự ưu tiên): index có sẵn của benchmark ở `logs/benchmark/chroma_<strategy>/` (tên collection `bench_<strategy>`) → vị trí cũ `benchmark_logs/` → **tự dựng mới** vào `logs/demo_chroma_<strategy>/` kèm thông báo tiến độ (lần đầu mất vài phút nhúng corpus, các lần sau tải từ đĩa ngay).

**Chế độ demo nhanh (replay):** nếu `logs/benchmark/results_all.json` có entry của câu đang chọn và khớp tham số (`top_k`, generator trong meta), app dùng **số liệu đã đo** thay vì chạy live — demo tức thì không cần Ollama; nhãn trạng thái hiện rõ `📅 Replay từ lượt benchmark <timestamp>` hay `⚡ Live` cho từng chiến lược. Chưa có file này thì app vẫn chạy live và hiển thị gợi ý lệnh `python benchmark_chunking.py --generator qwen` để tạo dữ liệu replay.

---

## 6. Quản lý file tự sinh — `logs/` và `outputs/`

Quy ước của repo (chi tiết ở `logs/README.md`): **mọi file tự sinh khi chạy phải nằm trong `logs/`**, chia sẵn theo ý nghĩa; script không được ghi log lẻ tẻ ra thư mục gốc:

| Thư mục | Sinh ra bởi | Ý nghĩa | Xóa được không |
|---|---|---|---|
| `logs/benchmark/` | `benchmark_chunking.py` | Log benchmark 3 chiến lược + index tạm | ✅ Xóa được — chạy lại là có lại |
| `logs/export/` | `export_architecture.py` | Biên nhận lần xuất `SYSTEM_ARCHITECTURE` | ✅ Xóa được |
| `logs/learning/` | `learn.py` và GUI Tab 3 | `learning_log.csv` — lịch sử mỗi lần hệ thống trả lời sai và được "học thêm" | ❌ **KHÔNG xóa** — là lịch sử dữ liệu |
| `logs/feedback/` | GUI Tab 3 | `user_feedback.json` — toàn bộ lượt đánh giá đúng/sai của người dùng | ❌ **KHÔNG xóa** |

`.gitignore` bỏ qua `logs/*` **trừ** `logs/README.md`, `logs/learning/` và `logs/feedback/` (hai thư mục dữ liệu lịch sử được git track để không bao giờ mất khi dọn dẹp). Riêng `outputs/` là nơi chứa **kết quả chốt** dùng cho báo cáo (`evaluation_results.json`, `evaluation_summary.md`) và được git track đầy đủ.

Ba thư mục cache ẩn khác cũng tự sinh nhưng **không phải log**: `chroma_db/` (index sản xuất — xóa là phải ingest lại từ đầu), `.ocr_cache/` (kết quả OCR — xóa là phải OCR lại), `.generation_cache/` (cache câu trả lời Gemini — xóa là tốn lại quota).

---

## 7. Quy tắc cộng tác đa-agent (`.maestro/playbooks/`)

Repo được bảo trì song song bởi các agent AI chia theo 4 nhóm trách nhiệm; quy tắc dùng chung nằm ở `.maestro/playbooks/base_prompt.md`:

| Playbook | Nhóm | Phạm vi sở hữu |
|---|---|---|
| `01_du_lieu_chi_muc.md` | Dữ liệu & Chỉ mục | `data/corpus/`, `ingest.py`, `src/loader|chunking|vector_db.py`, `chroma_db/`, `learn.py`, `logs/learning/` |
| `02_tri_tue_rag.md` | Trí tuệ RAG | `src/retrieval|query_normalizer|text_utils|generator|local_slm|pipeline.py`, `main.py`, `.generation_cache/` |
| `03_giao_dien_tai_lieu.md` | Giao diện & Tài liệu | `ui/app.py`, `README.md`, `SYSTEM_ARCHITECTURE.*`, `export_architecture.py`, `logs/feedback/`, `logs/export/` |
| `04_kiem_chung_cau_hinh.md` | Kiểm chứng & Cấu hình | `data/evaluation/`, `src/evaluation.py`, `benchmark_chunking.py`, `tests/`, `.env*`, `logs/benchmark/`, `outputs/` |

Quy tắc nổi bật của `base_prompt.md`: mọi file trung gian chỉ được nằm trong `tmp/` và phải xóa sạch trước khi kết thúc phiên; **mọi log tự sinh khi chạy phải nằm trong `logs/` đúng ý nghĩa ở `logs/README.md`**; ghi file luôn bằng Python với `encoding='utf-8'` (cấm chuyển hướng `>` của PowerShell — ghi UTF-16 làm hỏng JSON); chỉ được sửa file trong phạm vi group mình; báo cáo bắt buộc kèm kết quả verify.

---

## 8. Ghi chú

- Mô hình embedding `bge-m3` và mô hình `Qwen2.5:1.5b-instruct` đều chạy cục bộ (không tốn phí API); chỉ **Gemini API** là dịch vụ trên mây.
- Để có kết quả ổn định, Generator sử dụng `Temperature = 0.0` và luôn kèm trích dẫn Điều/Khoản từ ngữ cảnh.
- `main.py` và `demo_streamlit.py` tự đặt `sys.stdout.reconfigure(encoding="utf-8")` nên tiếng Việt in đúng trên console Windows; nếu gọi Python thủ công thì chạy kèm `PYTHONUTF8=1` hoặc `PYTHONIOENCODING=utf-8`.
- Mỗi lần chạy sẽ thấy một `FutureWarning` của `google-generativeai` — gói này đã bị Google khai tử nhưng vẫn hoạt động (0.8.6). Không phải lỗi; migrate sang `google-genai` là việc về sau, và lưu ý `google-genai` đổi cả tên model lẫn cách truyền `thinking_config`.
- **Hiện trạng corpus và index:** 26 tài liệu (21 PDF + 5 DOCX, không còn `.doc` legacy) ở 3 tầng; index sản xuất `chroma_db/` = **361 chunks** cắt bằng `DocumentChunker` (structure-aware cho văn bản có Điều, fallback theo đoạn cho văn bản thường). Ba index thực nghiệm của demo: fixed = 182, recursive = 189, structure = 378 chunks.
- **Bộ unit test (85 test):** chạy bằng `python -m pytest` — hoàn toàn offline (fake Qwen/ChromaDB/Gemini, monkeypatch), không tốn quota; gồm test 3 chiến lược chunking, pipeline (fold-query + oversampling), guardrail Local SLM và các hàm đánh giá.
- **Bộ benchmark:** 4 file trong `data/evaluation/` — 15 câu GUI tự sinh (schema 10 khóa cũ), **50 câu** và **100 câu v1/v2** (đúng 12 khóa, do các agent sinh theo playbook); benchmark mặc định của `src/evaluation.py` là 100 câu v2, của `benchmark_chunking.py` và demo là 50 câu. Ngoài ra `data/evaluation/manual_test_checklist.md` có **34 câu kiểm tra tay chia 7 nhóm tài liệu** (kèm nhóm câu ngoài corpus để thử hành vi từ chối) — dùng để đánh giá thủ công sau mỗi lần đổi pipeline.
- **Hành vi cần lưu ý của Qwen2.5-1.5B (tầng chuẩn hóa):** khi câu hỏi nằm ngoài phân bố few-shot, model có xu hướng **tự trả lời** thay vì viết lại câu hỏi, sinh ra nhận định không có căn cứ. Các lớp chặn hiện có: (1) system prompt chống bịa + few-shot của `src/query_normalizer.py` — đường đi chính trong pipeline, kèm active learning từ phản hồi người dùng; (2) `is_acceptable()` (4 điều kiện: không rỗng, ≤ 300 ký tự, phải có dấu `?`, không chứa mẫu lạc đề) và `guardrail_violation()` (bảo toàn con số + tỉ lệ token trùng với câu gốc ≥ 30%) trong `src/local_slm.py` — dùng khi chuẩn hóa trực tiếp qua wrapper `LocalSLM`, có test riêng trong `tests/test_local_slm.py`. Mọi đường đều suy giảm mềm: nghi ngờ là dùng lại câu hỏi gốc để truy xuất.
- **Lịch sử xử lý lỗi chất lượng:** file mẫu `quy_che_dao_tao_mau.txt` từng xếp hạng #1 cho một câu hỏi quy chế thật và được Gemini dùng làm căn cứ — đã chuyển sang `data/evaluation/reference/` nên không còn bị index. Điểm yếu còn lại của truy xuất nằm ở các chủ đề ít từ khóa trùng lặp (xem cột Hit@6 và MRR trong `outputs/evaluation_summary.md` để theo dõi sau mỗi lần cải tiến chunking/retrieval).
