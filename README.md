# Hybrid RAG System for Academic Regulations (AGU Context)

Hệ thống Hỏi - Đáp tự động (RAG) nâng cao ứng dụng kiến trúc lai (**Hybrid RAG**), kết hợp giữa **Local SLM (Qwen2.5 qua Ollama)** ở máy cá nhân và **Gemini API** trên mây, phục vụ tra cứu văn bản quy chế học vụ cho sinh viên.

---

## 1. Kiến trúc hệ thống

- **Embedding Model:** `BAAI/bge-m3` — chạy cục bộ trên phần cứng, hỗ trợ tiếng Việt đa ngữ 1024 chiều.
- **Vector Database:** `ChromaDB` — lưu trữ và truy xuất vector theo khoảng cách **Cosine Similarity**.
- **Local SLM (Query Preprocessor):** `Qwen2.5:1.5b-instruct` chạy qua **Ollama** ở máy local, giúp tiền xử lý, phân tích ý định hoặc chuẩn hóa câu hỏi.
- **Backend Generator:** **Gemini API (`gemini-2.5-flash`)** — tổng hợp ngữ cảnh và sinh câu trả lời chính xác kèm trích dẫn Điều/Khoản (`Temperature = 0.0`).

Luồng xử lý tổng thể:

```
Câu hỏi
   │
   ▼
Local SLM (Qwen2.5 / Ollama)  ──►  tiền xử lý & chuẩn hóa câu hỏi
   │
   ▼
VectorDB (bge-m3 + ChromaDB)   ──►  truy xuất top-k chunk ngữ cảnh
   │
   ▼
Gemini API (gemini-2.5-flash)  ──►  tổng hợp & sinh câu trả lời + trích dẫn
```

---

## 2. Cấu trúc thư mục

```
hybrid_rag_agu/
│
├── data/
│   ├── corpus/              # Tài liệu chính thức (.txt/.pdf/.docx) — nguồn xây Vector DB
│   └── evaluation/          # Tài liệu/câu hỏi gây nhiễu (distractor) phục vụ đánh giá
│
├── src/
│   ├── __init__.py
│   ├── chunking.py          # Cắt đoạn: structure-aware (Điều/Khoản) + fallback theo đoạn văn
│   ├── loader.py            # Đọc đệ quy .txt/.pdf/.docx + OCR PDF scan, gắn metadata tier
│   ├── vector_db.py         # Quản lý mô hình bge-m3 và ChromaDB
│   ├── local_slm.py         # Chuẩn hóa câu hỏi bằng Qwen trên Ollama (fallback về câu gốc nếu lỗi)
│   ├── generator.py         # Sinh câu trả lời qua Gemini API, bắt buộc trích dẫn Điều/Khoản
│   ├── pipeline.py          # Nối 3 tầng: chuẩn hóa → truy xuất → sinh câu trả lời
│   └── evaluation.py        # Đánh giá định lượng: Hit@K, MRR, Citation F1, Faithfulness
│
├── notebooks/               # Các file Jupyter Notebook chạy thử nghiệm (nếu có)
├── outputs/                 # Kết quả log, số liệu đánh giá thực nghiệm (.csv)
├── .ocr_cache/              # Cache kết quả OCR (tự sinh, xóa được — lần nạp sau sẽ OCR lại)
├── .generation_cache/       # Cache câu trả lời Gemini (tự sinh, xóa được — lượt sau sẽ gọi API lại)
├── .env.example             # File mẫu khai báo biến môi trường (API Key)
├── requirements.txt         # Danh sách các thư viện Python cần thiết
├── ingest.py                # Script nạp corpus vào ChromaDB (chạy trước main.py)
├── learn.py                 # Chế độ test & học: sai thì dạy lại, ghi log outputs/
└── main.py                  # Chế độ chạy thực: CLI tương tác, hỏi liên tục
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

`requirements.txt` đã gồm nhóm thư viện OCR thuần pip (`pypdfium2`, `rapidocr-onnxruntime`, `Pillow`) — **không** cần cài Tesseract hay Poppler ở cấp hệ thống.

### Bước 3: Cấu hình Ollama và mô hình Qwen

Tải và chạy mô hình Local SLM qua Ollama:

```bash
# Cài đặt Ollama tại: https://ollama.com
ollama pull qwen2.5:1.5b-instruct
ollama serve
```

`ollama serve` phải chạy ở một terminal riêng, để mở suốt quá trình hỏi đáp. Nếu Ollama tắt, hệ thống **không** dừng: `main.py` in cảnh báo ở bước `[2/3]` rồi dùng nguyên câu hỏi gốc để truy xuất (Local SLM là tầng tối ưu, không phải dependency cứng).

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
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b-instruct
OLLAMA_TIMEOUT=90
EMBEDDING_MODEL=BAAI/bge-m3
CHROMA_PERSIST_DIR=./chroma_db
RAG_TOP_K=4
```

Hai giá trị cần lưu ý khi viết phần thực nghiệm:

- `GEMINI_MAX_TOKENS=4096` — `gemini-2.5-flash` là model "thinking": token suy luận nội bộ bị trừ **vào cùng** ngân sách `max_output_tokens`. Đo thực tế một lượt trả lời tốn 763 token thinking + 73 token trả lời, nên đặt 1024 sẽ làm câu trả lời **bị cắt giữa chừng**. Thư viện `google-generativeai` 0.8.6 chưa có `thinking_config` để tách riêng ngân sách, chỉ còn cách đặt lớn. `generator.py` vẫn in cảnh báo nếu `finish_reason = MAX_TOKENS`.
- `RAG_TOP_K=4` — số chunk ngữ cảnh mỗi lượt hỏi; flag `-k/--top-k` của `main.py` ghi đè giá trị này.

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

```bash
pip install pypdfium2 rapidocr-onnxruntime Pillow
```

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
| Câu hỏi có dấu đầy đủ khó khớp chunk mất dấu khi truy xuất | Chưa xử lý — cần đo Recall@K riêng cho `Tầng 1` để định lượng |

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

### 4.3. Hai hình thức chạy

**Chạy thực (serve)** — chỉ truy vấn, DB chỉ đọc:

```bash
python ingest.py                            # Nạp corpus → ChromaDB (chạy lại mỗi khi thêm/sửa tài liệu)
python main.py                              # Không tham số → vòng lặp hỏi đáp tương tác
python main.py "Điều kiện xét tốt nghiệp?"   # Một câu rồi thoát (dùng cho test nhanh/script)
python main.py -k 8                         # Đổi số chunk ngữ cảnh (mặc định lấy RAG_TOP_K)
```

`main.py` khởi động theo 3 bước và **không** embedding lại corpus: `[1/3]` nối thẳng ChromaDB đã persist (`vector_db._collection.count()` = 0 thì dừng và nhắc chạy `python ingest.py`), `[2/3]` dò Ollama bằng `client.list()` với timeout 5s, `[3/3]` nạp `GeminiGenerator` (thiếu `GEMINI_API_KEY` hoặc key còn là placeholder thì dừng ngay).

Trong vòng lặp tương tác, mỗi lượt hỏi đi qua đúng 6 bước:

| # | Bước | Module | Suy giảm khi lỗi |
|---|---|---|---|
| 1 | Nhận câu hỏi thô từ bàn phím | `main.py` | `Ctrl+C` hủy lượt đó, `Ctrl+D`/`exit` thoát |
| 2 | Chuẩn hóa câu hỏi (few-shot, yêu cầu output là **một câu hỏi** kết thúc bằng `?`) | `local_slm.normalize_query` | In cảnh báo → dùng nguyên câu hỏi gốc |
| 3 | Truy xuất Top-K chunk (cosine) | `vector_db.similarity_search` | — |
| 4 | Dựng ngữ cảnh kèm `Nguồn / Tầng / chunk_id` | `generator.build_prompt` | Ngữ cảnh rỗng → trả về câu từ chối, **không** gọi API |
| 5 | Sinh câu trả lời + trích dẫn Điều/Khoản | `generator.generate_answer` | `GeneratorError` in ra, vòng lặp vẫn sống |
| 6 | In 4 khối: câu hỏi gốc / câu hỏi chuẩn hóa / nguồn trích dẫn / câu trả lời | `main.py` | — |

Một lượt hỏi lỗi (Gemini quá tải, mất mạng, Ollama tắt) **không** làm chết vòng lặp: ngoại lệ được bắt trong `ask_once()` và in thành một khối `[LỖI]`.

Các lệnh trong vòng lặp: `help`/`h`/`?` (in hướng dẫn), `exit`/`quit`/`thoat`/`thoát`/`q` (kết thúc).

**Về tính trung thực của câu trả lời (chống ảo giác):** `PROMPT_RULES` trong `src/generator.py` ràng buộc Gemini chỉ dùng ngữ cảnh được cấp, mỗi ý phải kèm căn cứ dạng `(Điều 12, Khoản 3 — <tên văn bản>)` lấy từ dòng `Nguồn:` thật (không được viết "(Ngữ cảnh 1)"), ưu tiên tier cao hơn khi các nguồn mâu thuẫn, và nếu thiếu căn cứ thì trả lời đúng một câu từ chối `REFUSAL_TEXT` = `"Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."`. Chuỗi này là hằng số module để module đánh giá sau này đối sánh được.

**Tiết kiệm quota & chống sập khi demo (caching + fallback Local Qwen trong `generator.py`):**

- **Response caching:** trước khi gọi API, `generate_answer` tính SHA-1 của `{model, temperature, prompt}` và tra `./.generation_cache/<sha1>.json` — trúng thì trả lời ngay, tốn **0 request quota**. Key bám theo nội dung prompt nên thêm/sửa tài liệu rồi ingest lại là cache cũ tự vô hiệu, không cần dọn tay. Chỉ câu trả lời **nguồn Gemini** được cache; muốn đo latency thật (không tính thời gian đọc cache) hoặc ép sinh lại thì đặt `GENERATION_CACHE=0` trong `.env` hoặc xóa thư mục `.generation_cache/`.
- **Fallback Local Qwen:** Gemini trả về 429/hết quota ngày/phút hay sự cố 5xx, `generate_answer` **không văng lỗi** mà chuyển câu hỏi + các chunk ngữ cảnh sang Qwen trên Ollama (num_ctx 8192 để không bị cắt ngữ cảnh), gắn nhãn đầu câu trả lời `[Cảnh báo: Gemini đã hết quota — câu trả lời này được tổng hợp tạm thời bằng Local Qwen ...]` để người nghe demo phân biệt ngay. Câu fallback **không được cache** để lượt chạy sau vẫn được thử lại Gemini thật. Cả Ollama cũng chết thì mới ném `GeneratorError` — `main.py` đã bắt nên vòng lặp vẫn sống. Tắt cơ chế này bằng `QWEN_FALLBACK=0`.
- Trong `src/evaluation.py`, fallback bị **tắt bắt buộc** (in rõ ở đầu lượt chạy): nếu để bật, câu trả lời Qwen sẽ làm nhiễu các chỉ số Citation/Faithfulness vốn đang đo chất lượng pipeline Gemini.

**Chạy test (learn)** — vòng lặp hỏi - đáp với người làm trọng tài:

```bash
python learn.py
```

Luồng hoạt động: nhập câu hỏi → hệ thống trả lời → bạn đánh giá (`Enter`/`y` = đúng, `n` = sai). Nếu sai, dán thông tin đúng (kết thúc bằng một dòng trống); hệ thống sẽ:

1. Ghi bài học vào `data/corpus/ghi_chu_hoc_them.txt` dưới dạng mục `Điều 1001., 1002., ...` tự sinh, nhờ đó mỗi bài học thành một chunk độc lập và trích dẫn được theo số Điều.
2. Rebuild collection ChromaDB ngay tại chỗ (tái dùng bge-m3 đã nạp, không reset thư mục).
3. Ghi 1 dòng log vào `outputs/learning_log.csv`: thời gian, câu hỏi, đáp án sai, thông tin đã học, số chunks trước/sau.

Cả `ingest.py` và learn mode đều xóa collection cũ trước khi index, nên chạy lại nhiều lần không bao giờ nhân đôi chunks. Muốn dọn các mục đã học, sửa tay `ghi_chu_hoc_them.txt` rồi chạy lại `python ingest.py`.

### 4.4. Đánh giá định lượng (`src/evaluation.py`)

Chạy đúng pipeline sản xuất (Qwen chuẩn hóa → ChromaDB → Gemini → giám khảo) trên từng câu của `data/evaluation/benchmark_questions.json` và đo ba tầng chỉ số:

| Tầng | Chỉ số | Cách tính |
|---|---|---|
| Truy xuất | **Hit@3 / Hit@5 / Hit@K, MRR** | Top-K có chứa chunk thuộc `source_document` ground truth không; MRR = 1/thứ hạng chunk đúng đầu tiên. So khớp tên nguồn **sau khi bỏ dấu** (`fold()`) |
| Trích dẫn | **Citation Precision / Recall / F1 / Exact Match** | Tập mã `Điều N [Khoản M]` rút từ câu trả lời so với `expected_citations`; hai bên quy về cùng token không dấu nên `"Điều 12"` khớp cả dạng OCR `"dieu 12"` |
| Trung thực | **Faithfulness** | Gemini giám khảo (temperature 0, JSON mode, **không** mang system instruction của Generator) tách câu trả lời thành các khẳng định nguyên tố và đối chiếu từng khẳng định với ngữ cảnh; điểm = tỉ lệ khẳng định được hỗ trợ. Kèm `number_support` không tốn API: tỉ lệ con số trong câu trả lời xuất hiện trong ngữ cảnh |

Câu có `in_corpus=false` kiểm tra hành vi từ chối: hệ thống phải trả lời bằng câu chứa `REFUSAL_MARKER`, trả lời ra nội dung thì bị tính là **ảo giác ngoài corpus**. Câu `normalized_query` trong benchmark cho phép đo thêm `normalization_accuracy` của Qwen (so khớp chính xác chuỗi, khá khắt khe).

```bash
python src/evaluation.py                  # đủ benchmark, top_k=5, có giám khảo
python src/evaluation.py -k 3             # truy xuất Top-3 (Hit@5 vẫn đo được nhờ lấy ≥5 chunk)
python src/evaluation.py --limit 2        # chạy thử nhanh 2 câu đầu, tiết kiệm quota
python src/evaluation.py --no-judge       # bỏ tầng giám khảo Faithfulness
python src/evaluation.py --judge-model gemini-3.5-flash-lite
                                          # giám khảo dùng model khác, tách ngân sách quota
```

Kết quả: chi tiết từng câu ở `outputs/evaluation_results.json` (kèm câu trả lời, danh sách chunk truy xuất, trích dẫn dự đoán, khẳng định bị giám khảo loại), bảng Markdown tổng hợp ở `outputs/evaluation_summary.md` và in thẳng ra terminal. Câu lỗi (hết quota, mất mạng) được ghi nhận rồi bỏ qua, không làm chết lượt đánh giá; bấm `Ctrl+C` giữa chừng vẫn ghi kết quả phần đã chạy. Khi generator dính lỗi **hết quota ngày** (429 kèm `PerDay`), lượt chạy dừng sớm ngay vì các câu sau chắc chắn lỗi tương tự.

Lưu ý quota (free tier Gemini giới hạn **theo từng model**, ví dụ gemini-2.5-flash: ~5 request/phút và ~20 request/ngày):
- Mỗi câu tốn 2 lần gọi (generator + giám khảo), trừ câu trả lời dạng từ chối chỉ tốn 1 → lượt đánh giá đầy đủ tốn ~15 request. Đặt `GEMINI_JUDGE_MODEL` trong `.env` (hoặc cờ `--judge-model`) sang một model khác, ví dụ `gemini-3.5-flash-lite`, để giám khảo dùng ngân sách riêng — generator giữ trọn quota của mình.
- Trước một lượt đánh giá đầy đủ, hạn chế chạy thử `main.py`/`learn.py` trong cùng ngày vì cùng xài chung quota model generator.
- **Caching làm các lần chạy lại gần như miễn phí:** câu nào đã trả lời thành công bằng Gemini một lần thì các lượt đánh giá sau lấy thẳng từ `.generation_cache/`, chỉ tốn quota cho câu mới và các câu giám khảo. Nếu lượt trước chết giữa chừng vì hết quota ngày, chỉ cần chạy lại đúng lệnh sau khi quota reset — không mất công trả lời lại từ đầu.
- Faithfulness phụ thuộc giám khảo nên khi viết bài cần ghi rõ model giám khảo và prompt (hằng `JUDGE_PROMPT` trong `src/evaluation.py`) vào phần thực nghiệm.

---

## 5. Ghi chú

- Mô hình embedding `bge-m3` và mô hình `Qwen2.5:1.5b-instruct` đều chạy cục bộ (không tốn phí API); chỉ **Gemini API** là dịch vụ trên mây.
- Để có kết quả ổn định, Generator sử dụng `Temperature = 0.0` và luôn kèm trích dẫn Điều/Khoản từ ngữ cảnh.
- `main.py` tự đặt `sys.stdout.reconfigure(encoding="utf-8")` nên tiếng Việt in đúng trên console Windows; nếu gọi Python thủ công thì chạy kèm `PYTHONUTF8=1`.
- Mỗi lần chạy sẽ thấy một `FutureWarning` của `google-generativeai` — gói này đã bị Google khai tử nhưng vẫn hoạt động (0.8.6). Không phải lỗi; migrate sang `google-genai` là việc về sau, và lưu ý `google-genai` đổi cả tên model lẫn cách truyền `thinking_config`.
- **Hiện trạng corpus sau OCR:** `390 chunks` — Tầng 1 = 255, Tầng 2 = 53, `cac_file_bo_xung_khac` = 80, Khác = 2. Toàn bộ Tầng 1 cắt theo `structure_aware_chunking` (Điều/Khoản). Vẫn còn 3 file `.doc` chưa đọc được (phải `Save As` sang `.docx`).
- **Hành vi cần lưu ý của Qwen2.5-1.5B:** khi câu hỏi nằm ngoài phân bố few-shot, model có xu hướng **tự trả lời** thay vì viết lại câu hỏi, sinh ra nhận định không có căn cứ (ví dụ trả về `"Sinh viên đã rớt môn tiên quyết không có quyền đăng ký học lại môn đó."`). `local_slm.is_acceptable()` chặn việc này bằng 4 điều kiện — không rỗng, ≤ `MAX_NORMALIZED_CHARS` (300) ký tự, **bắt buộc có dấu `?`**, không chứa mẫu từ chối/lạc đề — và `normalize_query()` thử lại 1 lần với hậu tố chỉnh sửa trước khi chịu lùi về câu hỏi gốc. Đây là số liệu nên đưa vào phần thực nghiệm khi so sánh chất lượng truy xuất có/không có tầng chuẩn hóa.
- **Hai khoảng trống chất lượng đã quan sát được**, cần module đánh giá định lượng: (1) file mẫu `data/corpus/quy_che_dao_tao_mau.txt` (tier `Khác`) từng xếp hạng #1 cho một câu hỏi quy chế thật và được Gemini dùng làm căn cứ — cân nhắc loại khỏi corpus khi đo; (2) câu hỏi "điều kiện xét công nhận tốt nghiệp" chỉ khớp `ban-mo-ta-ctdt-nganh-cntt-2021.pdf`, cho thấy Recall@K ở chủ đề này thấp.
