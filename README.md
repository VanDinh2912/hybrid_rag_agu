# Hybrid RAG System for Academic Regulations (AGU Context)

Hệ thống Hỏi - Đáp tự động (RAG) cho tra cứu văn bản quy chế học vụ AGU, xây theo kiến trúc **True Hybrid Search**: **Local SLM (Qwen2.5 qua Ollama)** chuẩn hóa câu hỏi → **BM25 + Vector (bge-m3/ChromaDB) hợp nhất bằng RRF** → **Gemini API** sinh câu trả lời kèm trích dẫn. Dự án có ba giao diện: CLI tương tác (`main.py`), GUI 3 tab (`ui/app.py`) và bộ đánh giá định lượng (`src/evaluation.py`).

---

## 1. Kiến trúc hệ thống

**Các thành phần:**

- **Embedding Model:** `BAAI/bge-m3` — chạy cục bộ trên phần cứng, đa ngữ 1024 chiều, hỗ trợ tiếng Việt.
- **Vector Database:** `ChromaDB` — lưu trữ và truy xuất vector theo khoảng cách **Cosine Similarity**.
- **BM25 Retriever:** tìm kiếm từ khóa chính xác (mã môn học, "Điều 12", thuật ngữ viết tắt) — bộ tách từ kép: token nguyên văn + token đã bỏ dấu.
- **EnsembleRetriever (RRF):** gộp kết quả BM25 và Chroma bằng **Reciprocal Rank Fusion**; trọng số mặc định BM25 = 0.4, Chroma = 0.6, hằng số RRF `c = 60` (đổi được qua biến môi trường, xem mục 3).
- **Local SLM:** `Qwen2.5:1.5b-instruct` qua **Ollama** — hai vai: (1) chuẩn hóa câu hỏi ở đầu pipeline; (2) generator dự phòng khi Gemini hết quota.
- **Backend Generator:** **Gemini API (`gemini-2.5-flash`)** — tổng hợp ngữ cảnh, sinh câu trả lời kèm trích dẫn Điều/Khoản (`Temperature = 0.0`), có cơ chế **Soft Refusal** khi ngữ cảnh không đủ căn cứ.

**Luồng xử lý (4 tầng):**

```
Câu hỏi thô
   │
   ▼
[1] Chuẩn hóa câu hỏi (Local Qwen / Ollama)  ──► viết lại theo văn phong quy chế,
   │                                              chống bịa thông tin, bảo toàn con số/thực thể
   ▼
[2] Mở rộng truy vấn (Query Expansion)       ──► từ điển đồng nghĩa pháp lý (~50 cặp ánh xạ)
   │
   ▼
[3] True Hybrid Search                        ──► BM25 (từ khóa, tokenizer kép)
   │                                              + ChromaDB (bge-m3, cosine)
   │                                              → EnsembleRetriever gộp bằng RRF
   ▼
[4] Sinh câu trả lời (Gemini API)             ──► câu trả lời + trích dẫn Điều/Khoản;
                                                  thiếu căn cứ → Soft Refusal;
                                                  Gemini hết quota → Local Qwen (nhãn FALLBACK)
```

Hai cơ chế xuyên suốt các tầng:

- **`fold()`** (`src/text_utils.py`) — bỏ dấu thanh dùng chung cho mọi tầng: câu hỏi có dấu vẫn khớp được chunk OCR mất dấu ở tầng truy xuất và tầng đánh giá.
- **Oversampling** — mỗi lượt truy xuất lấy về `top_k × 2` ứng viên; chỉ `top_k` đứng đầu theo thứ hạng RRF được đưa vào generator, phần còn lại phục vụ đo Hit@K.

Đặc tả chi tiết (công thức BM25/cosine/RRF, sơ đồ luồng, bảng biến môi trường): xem `SYSTEM_ARCHITECTURE.md`.

---

## 2. Cấu trúc thư mục

```
hybrid_rag_agu/
│
├── data/
│   ├── corpus/              # Tài liệu chính thức (.txt/.pdf/.docx) — nguồn xây Vector DB
│   │   └── ghi_chu_hoc_them.txt   # Bài học tự sinh khi dùng chế độ test & học
│   ├── evaluation/          # Benchmark v2.0 (15 câu), checklist kiểm tra tay, bản lưu bộ câu hỏi cũ
│   │   └── reference/       # File quy chế mẫu (không index — chỉ dùng đối chiếu)
│   └── normalization_pairs.json   # Cặp (câu gốc → câu chuẩn hóa) cho Qwen học — GUI tự sinh
│
├── src/
│   ├── __init__.py
│   ├── chunking.py          # Cắt đoạn: structure-aware (Điều/Khoản) + fallback theo đoạn văn
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
├── tests/                   # 58 unit test (chunking, pipeline, local_slm, evaluation)
├── notebooks/               # Các file Jupyter Notebook chạy thử nghiệm (nếu có)
├── logs/                    # Mọi log tự sinh khi chạy (xem logs/README.md): benchmark/, export/, learning/, feedback/
├── outputs/                 # Kết quả chốt cho báo cáo: evaluation_results.json, evaluation_summary.md
├── chroma_db/               # ChromaDB đã persist (ingest.py tự sinh)
├── .ocr_cache/              # Cache kết quả OCR (tự sinh, xóa được — lần nạp sau sẽ OCR lại)
├── .generation_cache/       # Cache câu trả lời Gemini (tự sinh, xóa được — lượt sau sẽ gọi API lại)
├── .env.example             # File mẫu khai báo biến môi trường (API Key)
├── requirements.txt         # Danh sách các thư viện Python cần thiết
├── ingest.py                # Script nạp corpus vào ChromaDB (chạy trước main.py)
├── learn.py                 # Chế độ test & học qua CLI: sai thì dạy lại, ghi log logs/learning/
├── main.py                  # Chế độ chạy thực: CLI tương tác, hỏi liên tục
├── SYSTEM_ARCHITECTURE.md   # Đặc tả kiến trúc True Hybrid Search
├── NORMALIZATION_ACTIVE_LEARNING.md  # Cơ chế học chuẩn hóa từ phản hồi người dùng
├── TROUBLESHOOTING_GUI.md   # Xử lý sự cố thường gặp của GUI
└── LAYOUT_OPTIMIZATION.md   # Ghi chú tối ưu layout Tab 3
```

---

## 3. Cài đặt môi trường làm việc

### Bước 1: Clone hoặc tạo cấu trúc thư mục

Đảm bảo bạn đang đứng ở thư mục gốc của dự án (`hybrid_rag_agu`).

### Bước 2: Cài đặt các thư viện Python

Tạo một môi trường ảo (Virtual Environment) và cài đặt các gói phụ thuộc từ file `requirements.txt`:

```bash
python -m venv venv

# Trên Windows:
venv\Scripts\activate

# Trên macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` đã gồm nhóm thư viện OCR thuần pip (`pypdfium2`, `rapidocr-onnxruntime`, `Pillow`) — **không** cần cài Tesseract hay Poppler ở cấp hệ thống — cùng `pytest` để chạy bộ unit test.

### Bước 3: Cấu hình Ollama và mô hình Qwen

Tải và chạy mô hình Local SLM qua Ollama:

```bash
# Cài đặt Ollama tại: https://ollama.com
ollama pull qwen2.5:1.5b-instruct
ollama serve
```

`ollama serve` phải chạy ở một terminal riêng, để mở suốt quá trình hỏi đáp. Nếu Ollama tắt, hệ thống **không** dừng: `main.py` in cảnh báo ở bước `[2/3]` rồi dùng nguyên câu hỏi gốc để truy xuất (Local SLM là tầng tối ưu, không phải dependency cứng). Cơ chế fallback generator (Gemini hết quota → Qwen) cũng chỉ hoạt động khi Ollama đang chạy.

### Bước 4: Cấu hình biến môi trường

Tạo file `.env` từ file mẫu và điền thông tin:

```bash
# Trên Windows:
Copy-Item .env.example .env

# Trên macOS/Linux:
cp .env.example .env
```

Khai báo API key và cấu hình trong file `.env`:

```env
# Bắt buộc
GEMINI_API_KEY=your_gemini_api_key_here

# Có giá trị mặc định — chỉ khai báo khi muốn đổi
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.0
GEMINI_MAX_TOKENS=4096
GEMINI_JUDGE_MODEL=              # model giám khảo của src/evaluation.py (trống = dùng chung GEMINI_MODEL)
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
BM25_WEIGHT=0.4
CHROMA_WEIGHT=0.6

# Tối ưu quota & chống sập khi demo (mặc định đã bật)
GENERATION_CACHE=1
QWEN_FALLBACK=1
```

Vài giá trị cần lưu ý khi viết phần thực nghiệm:

- `GEMINI_MAX_TOKENS=4096` — `gemini-2.5-flash` là model "thinking": token suy luận nội bộ bị trừ **vào cùng** ngân sách `max_output_tokens`. Đo thực tế một lượt trả lời tốn 763 token thinking + 73 token trả lời, nên đặt 1024 sẽ làm câu trả lời **bị cắt giữa chừng**. Thư viện `google-generativeai` 0.8.6 chưa có `thinking_config` để tách riêng ngân sách, chỉ còn cách đặt lớn. `generator.py` vẫn in cảnh báo nếu `finish_reason = MAX_TOKENS`.
- `RAG_TOP_K=4` — số chunk ngữ cảnh mỗi lượt hỏi; flag `-k/--top-k` của `main.py` ghi đè giá trị này, và nếu `.env` không khai báo thì `main.py` dùng mặc định 6.
- `ENABLE_HYBRID_SEARCH` / `ENABLE_QUERY_EXPANSION` — hai công tắc của True Hybrid Search, mặc định **bật**; đặt `0` để lùi về vector search thuần (tiện so sánh có/không hybrid trong phần thực nghiệm). `BM25_WEIGHT` / `CHROMA_WEIGHT` là trọng số RRF của hai nhánh truy xuất.

---

## 4. Chuẩn bị dữ liệu & Sử dụng

### 4.1. Đưa tài liệu vào thư mục `data/`

Loader (`src/loader.py`) quét đệ quy thư mục `data/corpus/`, hỗ trợ `.txt` (utf-8), `.pdf` (pypdf) và `.docx` (python-docx). Hai cách đưa corpus từ Google Drive (thư mục `tonghop`) về máy:

**Cách 1 — Thủ công:** mở thư mục `tonghop` trên Drive → chọn tất cả file → **Tải xuống** → giải nén → chép các file vào `data/corpus/`.

**Cách 2 — Tự động bằng `gdown`** (thư mục Drive phải bật chia sẻ "Bất kỳ ai có đường liên kết"):

```bash
pip install gdown
gdown --folder "https://drive.google.com/drive/folders/<FOLDER_ID>" -O data/corpus
```

Lưu ý: file `.doc` (Word 97-2003) không trích xuất được — hãy `Save As` sang `.docx`. PDF dạng scan ảnh thì loader **tự động OCR** (xem 4.1.1). Mọi file bị bỏ qua được liệt kê ở bước `[2/4]` khi chạy `ingest.py`.

#### 4.1.1. OCR cho PDF scan ảnh (thuần pip)

Phần lớn văn bản ở `Tầng 1` là bản scan chỉ chứa ảnh nên `pypdf` trích ra 0 ký tự. Loader tự phát hiện và OCR mà không cần cài phần mềm hệ thống:

- **Render trang → ảnh:** `pypdfium2` (PDFium đóng gói sẵn trong wheel). Không dùng `pdf2image` vì thư viện đó bắt buộc cài **Poppler** ở cấp hệ thống, trái ràng buộc "chỉ cần pip".
- **Nhận diện ký tự:** `rapidocr-onnxruntime` — model PP-OCR dạng ONNX kèm sẵn trong package, chạy bằng `onnxruntime` trên CPU, không cần Tesseract. Engine được nạp một lần cho cả tiến trình.
- **Điều kiện kích hoạt — xét theo từng trang, không theo từng file:** trang nào `pypdf` trích ra dưới `OCR_MIN_CHARS_PER_PAGE` ký tự (mặc định 50) thì trang đó được OCR. Nhờ vậy PDF vừa có trang text vừa có trang chụp ảnh chỉ bị OCR đúng phần scan.
- **Log:** `[OCR] Đang xử lý file scan: …` → `[OCR]   trang 5/23: 2.080 ký tự (6.7s)` → `[OCR] Hoàn tất trích xuất thành công: …`. Bước `[2/4]` của `ingest.py` gắn nhãn `[OCR]` vào file đã OCR và in tổng số trang/số ký tự.
- **Cache:** kết quả OCR ghi vào `./.ocr_cache/<tên_file>__<hash>.json`, khóa theo (kích thước, mtime, dpi, ngưỡng) nên sửa file PDF là cache tự hỏng. Bắt buộc phải có vì `learn.py` rebuild collection sau mỗi bài học — không cache thì mỗi lần học lại phải OCR lại toàn bộ. Xóa thư mục này để OCR lại từ đầu.
- **Tùy chọn trong `.env`:** `OCR_ENABLED` (`0` = tắt, file scan sẽ bị bỏ qua kèm cảnh báo), `OCR_DPI` (mặc định 200), `OCR_MIN_CHARS_PER_PAGE` (50), `OCR_CACHE_DIR` (`./.ocr_cache`).

**Giới hạn chất lượng (cần ghi vào phần thực nghiệm của đề tài):** model PP-OCR kèm `rapidocr-onnxruntime` bắt đúng bố cục và chữ quốc ngữ nhưng **làm mất phần lớn dấu thanh** — "Điều 4. Hệ thống tổ chức" thành "Dieu 4. He thong to chuc". Hệ quả và cách xử lý trong mã nguồn:

| Ảnh hưởng | Xử lý |
|---|---|
| Mốc `Điều N.` không khớp regex → tài liệu rơi xuống fallback, mất cấu trúc Điều/Khoản | `ARTICLE_HEADING_RE` (`src/chunking.py`) nhận cả dạng mất dấu (`Dieu 4.`) và dạng lỗi font PDF (`Ðiều 4.`); `canonical_article()` trả tiêu đề chunk về đúng chính tả `Điều N.` |
| Trích dẫn sinh ra từ ngữ cảnh không dấu có thể sai chính tả | Tiêu đề chunk đã được chuẩn hóa thành `Điều N.` nên Generator trích dẫn đúng |
| Câu hỏi có dấu đầy đủ khó khớp chunk mất dấu khi truy xuất | **Đã xử lý (11/10):** mọi truy vấn được `fold()` bỏ dấu trước khi so khớp/embed, và BM25 tokenizer sinh song song token nguyên văn + token bỏ dấu. Đo nhanh offline trên 7 câu hỏi khớp tài liệu OCR: Hit@5 từ 0/7 lên 7/7, top-1 đúng cả 7. |

Tăng `OCR_DPI` **không** cải thiện dấu: đo trên cùng một trang của `1054-qd-dhag-2020-09-28.pdf` cho 150/200/300 dpi lần lượt 2.012/2.080/2.076 ký tự nhưng chỉ 0/1/2 ký tự có dấu thanh. Nút thắt là model nhận diện, không phải độ phân giải — muốn giữ dấu đầy đủ phải đổi sang model OCR tiếng Việt chuyên biệt (ngoài phạm vi thuần pip).

### 4.2. Phân tầng tài liệu và chiến lược cắt đoạn

**Metadata phân tầng:** tên thư mục con cấp 1 trong `data/corpus/` chính là `tier` của tài liệu (ví dụ `Tầng 1`, `Tầng 2`, `cac_file_bo_xung_khac`); file nằm ngay gốc `data/corpus/` nhận tier `Khác`. Mỗi chunk lưu vào ChromaDB mang bộ metadata `{"tier", "source", "chunk_id"}`, nên có thể đo Recall@K riêng cho từng tầng:

```python
vector_db.similarity_search(query, k=5, filter={"tier": "Tầng 2"})
```

**Hai chiến lược cắt đoạn** (`src/chunking.py`, tự chọn theo nội dung):

| Văn bản | Chiến lược | Kết quả |
|---|---|---|
| Quy chế/quy định có `Điều N.` đầu dòng | `structure_aware_chunking` | Mỗi Điều một chunk; Điều quá dài (nuốt cả Phụ lục) được cắt tiếp thành `(phần i/n)` |
| Thông báo, kế hoạch, công văn, đơn, bản mô tả CTĐT | `fallback_chunking` | Cắt theo đoạn văn/ranh giới câu, gộp tới ~1000 ký tự (≤512 token bge-m3) |

Mọi chunk đều mang tiền tố `[Tên văn bản]` (và `- [Điều N.]` nếu có) để giữ ngữ cảnh khi truy xuất.

### 4.3. Chạy thực (CLI — `main.py`)

Chỉ truy vấn, DB chỉ đọc:

```bash
python ingest.py                            # Nạp corpus → ChromaDB (chạy lại mỗi khi thêm/sửa tài liệu)
python main.py                              # Không tham số → vòng lặp hỏi đáp tương tác
python main.py "Điều kiện xét tốt nghiệp?"   # Một câu rồi thoát (dùng cho test nhanh/script)
python main.py -k 8                         # Đổi số chunk ngữ cảnh (mặc định lấy RAG_TOP_K)
```

`main.py` khởi động theo 3 bước và **không** embedding lại corpus: `[1/3]` nối thẳng ChromaDB đã persist (`vector_db._collection.count()` = 0 thì dừng và nhắc chạy `python ingest.py`), `[2/3]` dò Ollama bằng `client.list()` với timeout 5s, `[3/3]` nạp `GeminiGenerator` (thiếu `GEMINI_API_KEY` hoặc key còn là placeholder thì dừng ngay). Ngay sau đó pipeline dựng chỉ mục BM25 + `EnsembleRetriever` và in dòng `[HybridSearch] Đã kích hoạt True Hybrid Search (BM25=0.40 + Chroma=0.60, c=60).`; nếu BM25 lỗi (collection rỗng, thiếu thư viện...), hệ thống tự lùi về vector search thuần kèm cảnh báo.

**Lần khởi động đầu phiên chậm hơn các lần sau (khoảng 30–45 giây):** phần lớn thời gian là nạp mô hình embedding `bge-m3` (~25s), nạp lạnh Qwen lần đầu (~9s) và dựng chỉ mục BM25 từ toàn bộ 388 chunk. Các lượt hỏi sau chỉ còn tốn thời gian chuẩn hóa + truy xuất + sinh câu trả lời.

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
- Trong `src/evaluation.py`, fallback bị **tắt bắt buộc** khi chạy chế độ Gemini (in rõ ở đầu lượt chạy): nếu để bật, câu trả lời Qwen sẽ làm nhiễu các chỉ số Citation/Faithfulness vốn đang đo chất lượng pipeline Gemini.

### 4.4. Giao diện đồ họa (GUI — `ui/app.py`)

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

### 4.5. Chế độ test & học (learn — `learn.py`)

Vòng lặp hỏi - đáp với người làm trọng tài (bản CLI của Tab 3):

```bash
python learn.py
```

Luồng hoạt động: nhập câu hỏi → hệ thống trả lời → bạn đánh giá (`Enter`/`y` = đúng, `n` = sai). Nếu sai, dán thông tin đúng (kết thúc bằng một dòng trống); hệ thống sẽ:

1. Ghi bài học vào `data/corpus/ghi_chu_hoc_them.txt` dưới dạng mục `Điều 1001., 1002., ...` tự sinh, nhờ đó mỗi bài học thành một chunk độc lập và trích dẫn được theo số Điều.
2. Rebuild collection ChromaDB ngay tại chỗ (tái dùng bge-m3 đã nạp, không reset thư mục).
3. Ghi 1 dòng log vào `logs/learning/learning_log.csv`: thời gian, câu hỏi, đáp án sai, thông tin đã học, số chunks trước/sau.

Cả `ingest.py` và learn mode đều xóa collection cũ trước khi index, nên chạy lại nhiều lần không bao giờ nhân đôi chunks. Muốn dọn các mục đã học, sửa tay `ghi_chu_hoc_them.txt` rồi chạy lại `python ingest.py`.

### 4.6. Đánh giá định lượng (`src/evaluation.py`)

Chạy đúng pipeline sản xuất (Qwen chuẩn hóa → mở rộng truy vấn → True Hybrid Search → Generator → giám khảo) trên từng câu của `data/evaluation/benchmark_questions.json` — **bộ v2.0 gồm 15 câu** thuộc 6 nhóm tài liệu: CTĐT CNTT, quy chế CTSV, đánh giá KQRL, KTX, hỗ trợ học phí và miễn giảm học phí — rồi đo ba tầng chỉ số:

| Tầng | Chỉ số | Cách tính |
|---|---|---|
| Truy xuất | **Hit@3 / Hit@5 / Hit@6, MRR** | Mỗi câu pipeline truy xuất oversampled (2× cửa sổ generator); Hit@K = K kết quả đầu có chứa chunk thuộc `source_document` ground truth không; MRR = 1/thứ hạng chunk đúng đầu tiên trong toàn bộ cửa sổ truy xuất. So khớp tên nguồn **sau khi bỏ dấu** (`fold()`) |
| Trích dẫn | **Citation Precision / Recall / F1 / Exact Match** | Tập mã `Điều N [Khoản M]` rút từ câu trả lời so với `expected_citations`; hai bên quy về cùng token không dấu nên `"Điều 12"` khớp cả dạng OCR `"dieu 12"` |
| Trung thực | **Faithfulness** | Gemini giám khảo (temperature 0, JSON mode, **không** mang system instruction của Generator) tách câu trả lời thành các khẳng định nguyên tố và đối chiếu từng khẳng định với ngữ cảnh; điểm = tỉ lệ khẳng định được hỗ trợ. Kèm `number_support` không tốn API: tỉ lệ con số trong câu trả lời xuất hiện trong ngữ cảnh |

Câu có `in_corpus=false` kiểm tra hành vi từ chối: hệ thống phải trả lời bằng câu chứa `REFUSAL_MARKER`, trả lời ra nội dung thì bị tính là **ảo giác ngoài corpus** (bộ v2.0 hiện toàn bộ 15 câu đều nằm trong corpus nên chỉ số `refusal_correct_rate` = n/a; các câu kiểm tra từ chối nằm trong checklist kiểm tra tay — xem mục 5). Trường `normalized_query` trong benchmark cho phép đo thêm chỉ số khắt khe `normalization_accuracy` (so khớp chuỗi chính xác); chỉ số chính hiện dùng là **`normalization_preservation`**: tỉ lệ thực thể (số Điều/Khoản, con số) trong câu hỏi gốc còn nguyên sau chuẩn hóa — so khớp regex không dấu, bỏ qua văn phong, khách quan hơn so khớp chuỗi.

```bash
python src/evaluation.py                        # đủ benchmark, top_k=6, có giám khảo Gemini
python src/evaluation.py --use-qwen-generator   # offline 100%: Local Qwen sinh câu trả lời (không tốn quota)
python src/evaluation.py --no-judge             # bỏ tầng giám khảo Faithfulness
python src/evaluation.py --limit 2              # chạy thử nhanh 2 câu đầu, tiết kiệm quota
python src/evaluation.py --judge-model gemini-3.5-flash-lite
                                                # giám khảo dùng model khác, tách ngân sách quota
```

Cờ `--benchmark <file>` để chạy bộ câu hỏi khác; `--output <file>` đổi nơi ghi JSON chi tiết.

Kết quả: chi tiết từng câu ở `outputs/evaluation_results.json` (kèm câu trả lời, danh sách chunk truy xuất, trích dẫn dự đoán, khẳng định bị giám khảo loại), bảng Markdown tổng hợp ở `outputs/evaluation_summary.md` và in thẳng ra terminal. Câu lỗi (hết quota, mất mạng) được ghi nhận rồi bỏ qua, không làm chết lượt đánh giá; bấm `Ctrl+C` giữa chừng vẫn ghi kết quả phần đã chạy. Khi generator dính lỗi **hết quota ngày** (429 kèm `PerDay`), lượt chạy dừng sớm ngay vì các câu sau chắc chắn lỗi tương tự.

**Kết quả lượt chạy gần nhất** (12/10, chế độ offline `--use-qwen-generator`, tắt giám khảo — nguồn: `outputs/evaluation_summary.md`):

| Chỉ số | Giá trị |
|---|---|
| Số câu chạy được | 15/15 |
| Hit@3 / Hit@5 / Hit@6 | 53.3% / 60.0% / 73.3% |
| MRR | 0.4833 |
| Citation F1 | 0.0% |
| Number support | 94.4% |
| Bảo toàn thực thể sau chuẩn hóa (Qwen) | 100.0% |
| Thời gian trung bình / câu | 13.9s |

Lưu ý khi đọc bảng này: generator là Local Qwen offline nên điểm trích dẫn bằng 0 — câu trả lời của Qwen 1.5B không chứa mã `Điều N` đúng định dạng; chạy lại không cờ `--use-qwen-generator` khi Gemini còn quota để có số liệu chính thức cho tầng Citation/Faithfulness.

Lưu ý quota (free tier Gemini giới hạn **theo từng model**, ví dụ gemini-2.5-flash: ~5 request/phút và ~20 request/ngày):
- Mỗi câu tốn 2 lần gọi (generator + giám khảo), trừ câu trả lời dạng từ chối chỉ tốn 1 → lượt đánh giá đầy đủ 15 câu tốn ~30 request. Đặt `GEMINI_JUDGE_MODEL` trong `.env` (hoặc cờ `--judge-model`) sang một model khác, ví dụ `gemini-3.5-flash-lite`, để giám khảo dùng ngân sách riêng — generator giữ trọn quota của mình. Các lần chạy thử nên dùng `--use-qwen-generator` hoặc `--limit` để giữ quota cho lượt chính thức.
- Trước một lượt đánh giá đầy đủ, hạn chế chạy thử `main.py`/`learn.py` trong cùng ngày vì cùng xài chung quota model generator.
- **Caching làm các lần chạy lại gần như miễn phí:** câu nào đã trả lời thành công bằng Gemini một lần thì các lượt đánh giá sau lấy thẳng từ `.generation_cache/`, chỉ tốn quota cho câu mới và các câu giám khảo. Nếu lượt trước chết giữa chừng vì hết quota ngày, chỉ cần chạy lại đúng lệnh sau khi quota reset — không mất công trả lời lại từ đầu.
- Faithfulness phụ thuộc giám khảo nên khi viết bài cần ghi rõ model giám khảo và prompt (hằng `JUDGE_PROMPT` trong `src/evaluation.py`) vào phần thực nghiệm.

---

## 5. Ghi chú

- Mô hình embedding `bge-m3` và mô hình `Qwen2.5:1.5b-instruct` đều chạy cục bộ (không tốn phí API); chỉ **Gemini API** là dịch vụ trên mây.
- Để có kết quả ổn định, Generator sử dụng `Temperature = 0.0` và luôn kèm trích dẫn Điều/Khoản từ ngữ cảnh.
- `main.py` tự đặt `sys.stdout.reconfigure(encoding="utf-8")` nên tiếng Việt in đúng trên console Windows; nếu gọi Python thủ công thì chạy kèm `PYTHONUTF8=1`.
- Mỗi lần chạy sẽ thấy một `FutureWarning` của `google-generativeai` — gói này đã bị Google khai tử nhưng vẫn hoạt động (0.8.6). Không phải lỗi; migrate sang `google-genai` là việc về sau, và lưu ý `google-genai` đổi cả tên model lẫn cách truyền `thinking_config`.
- **Hiện trạng corpus sau OCR:** `388 chunks` — Tầng 1 = 255, Tầng 2 = 53, `cac_file_bo_xung_khac` = 80, Khác = 0 (file mẫu `quy_che_dao_tao_mau.txt` đã chuyển sang `data/evaluation/reference/`, không còn bị index). Toàn bộ Tầng 1 cắt theo `structure_aware_chunking` (Điều/Khoản). Vẫn còn 3 file `.doc` chưa đọc được (phải `Save As` sang `.docx`).
- **Bộ unit test (58 test):** chạy bằng `python -m pytest` — hoàn toàn offline (fake Qwen/ChromaDB/Gemini, monkeypatch), không tốn quota; gồm test chunking, pipeline (fold-query + oversampling), guardrail Local SLM và các hàm đánh giá.
- **Benchmark & kiểm tra tay:** benchmark hiện tại là v2.0 gồm 15 câu bám theo tài liệu thật trong corpus; ngoài ra `data/evaluation/manual_test_checklist.md` có **34 câu kiểm tra tay chia 7 nhóm tài liệu** (kèm nhóm câu ngoài corpus để thử hành vi từ chối và chuỗi từ chối cần khớp chính xác) — dùng để đánh giá thủ công sau mỗi lần đổi pipeline.
- **Hành vi cần lưu ý của Qwen2.5-1.5B (tầng chuẩn hóa):** khi câu hỏi nằm ngoài phân bố few-shot, model có xu hướng **tự trả lời** thay vì viết lại câu hỏi, sinh ra nhận định không có căn cứ (ví dụ trả về `"Sinh viên đã rớt môn tiên quyết không có quyền đăng ký học lại môn đó."`). Các lớp chặn hiện có: (1) system prompt chống bịa + few-shot của `src/query_normalizer.py` — đường đi chính trong pipeline, kèm active learning từ phản hồi người dùng; (2) `is_acceptable()` (4 điều kiện: không rỗng, ≤ 300 ký tự, phải có dấu `?`, không chứa mẫu lạc đề) và `guardrail_violation()` (bảo toàn con số + tỉ lệ token trùng với câu gốc ≥ 30%) trong `src/local_slm.py` — dùng khi chuẩn hóa trực tiếp qua wrapper `LocalSLM`, có test riêng trong `tests/test_local_slm.py`. Mọi đường đều suy giảm mềm: nghi ngờ là dùng lại câu hỏi gốc để truy xuất.
- **Lịch sử xử lý lỗi chất lượng:** file mẫu `quy_che_dao_tao_mau.txt` từng xếp hạng #1 cho một câu hỏi quy chế thật và được Gemini dùng làm căn cứ — đã chuyển sang `data/evaluation/reference/` (10/10) nên không còn bị index. Điểm yếu còn lại của truy xuất nằm ở các chủ đề ít từ khóa trùng lặp (xem cột Hit@6 và MRR trong `outputs/evaluation_summary.md` để theo dõi sau mỗi lần cải tiến chunking/retrieval).
