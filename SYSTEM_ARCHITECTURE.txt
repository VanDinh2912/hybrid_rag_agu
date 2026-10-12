# Kiến trúc Hệ thống Hybrid RAG - Tra cứu Quy chế Đào tạo ĐHAG

## Tổng quan

Hệ thống Hybrid RAG (Retrieval-Augmented Generation) được thiết kế để tra cứu quy chế đào tạo của Trường Đại học An Giang (ĐHAG) một cách chính xác, có trích dẫn nguồn và chống ảo giác (anti-hallucination). Hệ thống kết hợp **Lexical Search (BM25)** và **Semantic Search (BGE-M3)** thông qua thuật toán **Reciprocal Rank Fusion (RRF)** để tối ưu hóa khả năng truy xuất thông tin.

### Mục tiêu thiết kế
- ✅ Trả lời câu hỏi sinh viên về quy chế đào tạo với trích dẫn chính xác (Điều, Khoản, Quyết định)
- ✅ Chống ảo giác - chỉ trả lời dựa trên ngữ cảnh có trong corpus
- ✅ Chuẩn hóa câu hỏi thông tục thành thuật ngữ quy chế chuẩn
- ✅ Mở rộng từ khóa đồng nghĩa để tăng độ bao phủ (Recall)
- ✅ Fallback tự động khi Gemini API hết quota
- ✅ Response caching để tiết kiệm quota và tăng tốc độ

---

## 1. Chức năng cốt lõi

### 1.1 Tra cứu & Trích dẫn nguồn (RAG Core)
- **Input**: Câu hỏi sinh viên (có thể viết tắt, tiếng lóng)
- **Process**: Chuẩn hóa → Mở rộng từ khóa → Hybrid Search → Sinh câu trả lời
- **Output**: Câu trả lời có trích dẫn (Điều X, Khoản Y — Tên văn bản)

### 1.2 Nạp & Phân đoạn dữ liệu (Ingestion)
- **Input**: Tài liệu PDF, DOCX, TXT trong `data/corpus/`
- **Process**: OCR (nếu cần) → Chunking với overlap → Embedding BGE-M3 → Lưu vào ChromaDB
- **Output**: Vector database với metadata (source, tier, chunk_id)

### 1.3 Chuẩn hóa (Normalization) & Mở rộng từ khóa (Expansion)
- **Normalization**: Local Qwen 2.5 (Ollama) chuyển đổi câu hỏi thông tục thành thuật ngữ chuẩn
- **Expansion**: Từ điển đồng nghĩa pháp lý mở rộng từ khóa để tăng Recall

### 1.4 Đánh giá định lượng (Benchmark)
- **Dataset**: 15 câu hỏi benchmark trong `data/evaluation/benchmark_questions.json`
- **Metrics**: Hit@K, MRR, Citation Precision/Recall/F1, Faithfulness

### 1.5 Bộ đệm (Response Cache) & Chuyển đổi dự phòng (Auto-Fallback)
- **Cache**: SHA-1 của {model, temperature, prompt_version, prompt} lưu trong `.generation_cache/`
- **Fallback**: Khi Gemini lỗi quota → tự động chuyển sang Local Qwen với nhãn cảnh báo

---

## 2. Chi tiết thuật toán & công thức

### 2.1 BM25 (Lexical Search)

**Giới thiệu**: BM25 là thuật toán tìm kiếm từ khóa dựa trên TF-IDF với các tham số k1 và b.

**Công thức điểm số BM25 cho một tài liệu D và truy vấn Q:**

```
score(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))
```

Trong đó:
- `qi`: từ khóa thứ i trong truy vấn Q
- `f(qi, D)`: tần suất xuất hiện của từ qi trong tài liệu D
- `|D|`: độ dài tài liệu D (số từ)
- `avgdl`: độ dài trung bình của tất cả tài liệu trong corpus
- `k1`: tham số điều chỉnh tần suất từ khóa (thường k1 = 1.2 - 2.0)
- `b`: tham số điều chỉnh độ dài tài liệu (thường b = 0.75)
- `IDF(qi)`: Inverse Document Frequency

**Công thức IDF:**

```
IDF(qi) = log((N - df(qi) + 0.5) / (df(qi) + 0.5))
```

Trong đó:
- `N`: tổng số tài liệu trong corpus
- `df(qi)`: số tài liệu chứa từ khóa qi

**Triển khai trong hệ thống**:
- File: `src/vector_db.py` - hàm `bm25_tokenize()`
- Tokenization: Tiếng Việt với bỏ dấu thanh (fold) để khớp OCR mất dấu
- Tham số: k1=1.5, b=0.75 (mặc định của LangChain BM25Retriever)

---

### 2.2 BGE-M3 & Cosine Similarity (Vector Search)

**Giới thiệu**: BGE-M3 (BAAI General Embedding) là mô hình embedding đa ngôn ngữ, hỗ trợ 3 chức năng:
1. Dense Retrieval (truy xuất vector thông thường)
2. Multi-Vector (truy xuất nhiều vector cho một chunk)
3. ColBERT (Late Interaction)

**Hệ thống sử dụng Dense Retrieval với Cosine Similarity:**

**Công thức Cosine Similarity:**

```
similarity(q, d) = (q · d) / (||q|| * ||d||)
```

Trong đó:
- `q`: vector embedding của câu truy vấn
- `d`: vector embedding của tài liệu/chunk
- `||q||`, `||d||`: độ dài vector (norm L2)

**Công thức chuyển đổi từ Cosine Similarity sang điểm số tương đồng:**

```
score = (1 + similarity) / 2  ∈ [0, 1]
```

**Triển khai trong hệ thống**:
- Model: `BAAI/bge-m3` (1024 dimensions)
- Framework: `sentence-transformers`
- Vector DB: ChromaDB với HNSW index (Hierarchical Navigable Small World)
- Loại bỏ dấu thanh (fold) trước khi embedding để khớp OCR

---

### 2.3 Reciprocal Rank Fusion (RRF)

**Giới thiệu**: RRF là thuật toán dung hợp (fusion) kết hợp kết quả từ nhiều retriever khác nhau (BM25 + Vector Search) bằng cách xếp hạng lại dựa trên vị trí (rank) của mỗi tài liệu.

**Công thức RRF:**

```
RRF_score(d) = Σ (k / (rank_i(d) + k))
```

Trong đó:
- `d`: tài liệu cần xếp hạng
- `rank_i(d)`: vị trí của tài liệu d trong kết quả retriever thứ i (bắt đầu từ 1)
- `k`: tham số mượt mà (damping factor), thường k = 60
- Tổng số retriever: 2 (BM25 + ChromaDB)

**Ví dụ:**
- Tài liệu X: rank BM25 = 2, rank Chroma = 5
  - RRF_score = 60/(2+60) + 60/(5+60) = 0.9677 + 0.9231 = 1.8908
- Tài liệu Y: rank BM25 = 10, rank Chroma = 1
  - RRF_score = 60/(10+60) + 60/(1+60) = 0.8451 + 0.9836 = 1.8287
- Kết quả: X > Y (dù Y đứng đầu Chroma, nhưng X đứng cao hơn BM25)

**Triển khai trong hệ thống**:
- File: `src/pipeline.py` - class `EnsembleRetriever` từ LangChain
- Tham số: c = 60 (DEFAULT_RRF_C trong `src/vector_db.py`)
- Trọng số: BM25 weight = 0.5, Chroma weight = 0.5 (có thể điều chỉnh qua biến môi trường)

---

### 2.4 Tìm kiếm Heuristic (Best-First Search / A*) trong lọc ngữ cảnh

**Giới thiệu**: Hệ thống áp dụng tư tưởng Best-First Search để lọc và xếp hạng ngữ cảnh, lấy Top-K chunk có điểm số cao nhất làm "best path" cho generator.

**Mô hình hóa:**
- **State space**: Tất cả chunks trong corpus
- **Heuristic function**: f(n) = g(n) + h(n)
  - `g(n)`: điểm số từ retriever (BM25 + RRF)
  - `h(n)`: heuristic bổ sung (tier của tài liệu, độ trùng từ khóa với truy vấn)

**Thuật toán (Best-First với Beam Search):**

```
Pseudo-code:
1. Khởi tạo: open_set = tất cả chunks
2. Đánh giá: Tính score cho mỗi chunk (BM25 + Vector + RRF)
3. Sắp xếp: open_set theo score giảm dần
4. Beam Search: Chọn top-K chunks (beam_width = K)
5. Return: Top-K chunks cho generator
```

**Triển khai trong hệ thống**:
- Oversampling: Truy xuất retrieve_k = top_k * 2 chunks
- Filter: Chỉ top_k đầu cho generator
- Tier prioritization: Tier 1 (quy chế gốc) ưu tiên hơn Tier 2 (thông báo/kế hoạch)

---

### 2.5 Logic Mệnh đề & Guardrail (Soft Refusal chống ảo giác)

**Giới thiệu**: Hệ thống áp dụng logic mệnh đề (propositional logic) để kiểm tra tính trung thực của câu trả lời (faithfulness).

**Mô hình logic:**

```
Để mỗi khẳng định A trong câu trả lời:
  - A được hỗ trợ bởi ngữ cảnh C → Faithful(A) = True
  - A không được hỗ trợ bởi ngữ cảnh C → Faithful(A) = False
  - A mâu thuẫn với ngữ cảnh C → Hallucination(A) = True

Faithfulness = Σ Faithful(Ai) / Σ khẳng định
```

**Guardrail (Soft Refusal):**

```
IF (ngữ cảnh trống OR ngữ cảnh không liên quan) THEN
  RETURN REFUSAL_TEXT
ELSE IF (không đủ căn cứ để trả lời) THEN
  RETURN REFUSAL_TEXT + "ngữ cảnh không chứa thông tin..."
ELSE
  RETURN câu trả lời với trích dẫn
END IF
```

**Triển khai trong hệ thống**:
- File: `src/generator.py` - `SYSTEM_INSTRUCTION` và `PROMPT_RULES`
- Refusal text: "Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."
- LLM-Judge: Gemini độc lập đánh giá faithfulness (không dùng cùng prompt với generator)

---

## 3. Chỉ số đo lường định lượng

### 3.1 Hit@K (Hit Rate at K)

**Định nghĩa**: Tỉ lệ câu hỏi mà trong Top-K chunk có chứa ít nhất một chunk thuộc source_document ground truth.

**Công thức:**

```
Hit@K = (số câu hỏi có hit trong Top-K) / (tổng số câu hỏi)
```

**Giá trị K trong hệ thống**: K = 3, 5, 6

**Triển khai**: File `src/evaluation.py` - hàm `compute_hit_at_k()`

---

### 3.2 MRR (Mean Reciprocal Rank)

**Định nghĩa**: Trung bình của nghịch đảo thứ hạng (rank) của chunk đúng đầu tiên.

**Công thức:**

```
MRR = (1 / N) * Σ (1 / rank_i)
```

Trong đó:
- `N`: tổng số câu hỏi
- `rank_i`: thứ hạng của chunk đúng đầu tiên trong câu hỏi thứ i
- Nếu không có chunk đúng nào trong Top-K → rank_i = ∞ → 1/rank_i = 0

**Ví dụ:**
- Câu 1: chunk đúng ở rank 2 → 1/2 = 0.5
- Câu 2: chunk đúng ở rank 1 → 1/1 = 1.0
- Câu 3: không có chunk đúng → 0
- MRR = (0.5 + 1.0 + 0) / 3 = 0.5

**Triển khai**: File `src/evaluation.py` - hàm `compute_mrr()`

---

### 3.3 Faithfulness (LLM-Judge)

**Định nghĩa**: Tỉ lệ khẳng định trong câu trả lời được hỗ trợ bởi ngữ cảnh, được đánh giá bởi LLM giám khảo (Gemini).

**Công thức:**

```
Faithfulness = (số khẳng định được hỗ trợ) / (tổng số khẳng định)
```

**Chỉ số phụ**:
- `number_support`: Tỉ lệ con số trong câu trả lời xuất hiện trong ngữ cảnh

**Triển khai**: File `src/evaluation.py` - hàm `judge_faithfulness()`

---

### 3.4 Citation Metrics

**Citation Precision**: Tỉ lệ trích dẫn đúng so với tất cả trích dẫn trong câu trả lời

```
Precision = |{trích dẫn đúng}| / |{tất cả trích dẫn}|
```

**Citation Recall**: Tỉ lệ trích dẫn đúng so với tất cả trích dẫn ground truth

```
Recall = |{trích dẫn đúng}| / |{trích dẫn ground truth}|
```

**Citation F1**: Trung bình hài hòa của Precision và Recall

```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

**Citation Exact Match**: Trích dẫn hoàn toàn khớp (Điều + Khoản)

**Triển khai**: File `src/evaluation.py` - hàm `compute_citation_metrics()`

---

## 4. Bảng phân công vai trò giữa Local Qwen và Cloud Gemini

### 4.1 Local Qwen 2.5 (Ollama)

| Vai trò | Mô tả | File |
|--------|-------|------|
| **Chuẩn hóa câu hỏi** | Chuyển đổi câu hỏi thông tục → thuật ngữ chuẩn quy chế | `src/query_normalizer.py` |
| **Fallback Generator** | Sinh câu trả lời khi Gemini hết quota/sự cố | `src/generator.py` - `_qwen_answer()` |
| **LLM-Judge (tùy chọn)** | Đánh giá faithfulness nếu không dùng Gemini | `src/evaluation.py` |

**Đặc điểm:**
- Chạy 100% offline trên máy local
- Model: `qwen2.5:1.5b-instruct` (1.5B parameters)
- Host: `http://localhost:11434` (Ollama)
- Ưu điểm: Không tốn quota API, không phụ thuộc mạng
- Nhược điểm: Độ chính xác thấp hơn Gemini, dễ drift/lạc đề

---

### 4.2 Cloud Gemini 1.5 Flash

| Vai trò | Mô tả | File |
|--------|-------|------|
| **Generator chính** | Sinh câu trả lời với trích dẫn và chống ảo giác | `src/generator.py` - `GeminiGenerator` |
| **LLM-Judge chính** | Đánh giá faithfulness của câu trả lời | `src/evaluation.py` - `judge_faithfulness()` |

**Đặc điểm:**
- Chạy trên cloud (Google Generative AI)
- Model: `gemini-2.5-flash` (hoặc `gemini-1.5-flash`)
- API Key: `GEMINI_API_KEY` trong `.env`
- Ưu điểm: Độ chính xác cao, hiểu ngữ cảnh sâu, ít drift
- Nhược điểm: Có giới hạn quota (trong đó free tier ~15 requests/phút)

---

### 4.3 Cơ chế Auto-Fallback

```
IF (Gemini lỗi quota OR Gemini gặp sự cố) AND (QWEN_FALLBACK=True) THEN
  Generator = Local Qwen
  Thêm nhãn: "[Cảnh báo: Gemini hết quota — câu trả lời do Local Qwen tổng hợp tạm thời]"
ELSE IF (Gemini lỗi) AND (QWEN_FALLBACK=False) THEN
  Throw GeneratorError
END IF
```

**Triển khai**: File `src/generator.py` - hàm `generate_answer()` (line 548-556)

---

## 5. Luồng dữ liệu end-to-end

```
┌─────────────────────────────────────────────────────────────────┐
│                     CÂU HỎI SINH VIÊN                         │
│          "Bị điểm yếu có bị đuổi học không ad?"                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 1: NORMALIZATION (Qwen)                      │
│  - Chuẩn hóa: "điểm yếu" → "xếp loại rèn luyện Yếu"           │
│  - Chuẩn hóa: "đuổi học" → "buộc thôi học"                     │
│  - Output: "Sinh viên có xếp loại rèn luyện Yếu có bị buộc    │
│            thôi học không?"                                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│            LAYER 2: QUERY EXPANSION (Dictionary)                │
│  - Mở rộng từ đồng nghĩa:                                      │
│    "buộc thôi học" → "thôi học", "kỷ luật"                      │
│    "xếp loại rèn luyện Yếu" → "rèn luyện", "kết quả rèn luyện" │
│  - Output: Query mở rộng với từ khóa bổ sung                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         LAYER 3: TRUE HYBRID SEARCH (BM25 + ChromaDB)          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  BM25 Retriever:  Tìm kiếm từ khóa chính xác           │   │
│  │  ChromaDB Retriever: Tìm kiếm ngữ nghĩa (BGE-M3)       │   │
│  │  EnsembleRetriever: RRF dung hợp thứ hạng              │   │
│  └─────────────────────────────────────────────────────────┘   │
│  - Output: Top-K chunks với metadata (source, tier, chunk_id) │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│          LAYER 4: GENERATOR (Gemini API)                        │
│  - Build prompt: Ngữ cảnh + Câu hỏi + Quy tắc trích dẫn      │
│  - System Instruction: Chống ảo giác, bắt buộc trích dẫn      │
│  - Soft Refusal: Từ chối nếu không đủ căn cứ                 │
│  - Output: Câu trả lời với trích dẫn (Điều X, Khoản Y)       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CÂU TRẢ LỜI CUỐI CÙNG                       │
│  "Sinh viên có xếp loại rèn luyện Yếu có bị buộc thôi học    │
│   không? Theo quy chế, sinh viên bị xếp loại Yếu 2 học kỳ    │
│   liên tiếp sẽ bị buộc thôi học (Điều 14, Khoản 5 — Quy       │
│   chế Đánh giá KQRL)."                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Response Caching

### 6.1 Cache Key Design

```
cache_key = SHA-1({
  "model": model_name,
  "temperature": temperature,
  "prompt_version": PROMPT_VERSION,
  "prompt": prompt
})
```

**Đặc điểm:**
- Cache tự invalidating khi đổi model, temperature, hoặc prompt
- PROMPT_VERSION được bump khi sửa SYSTEM_INSTRUCTION hoặc PROMPT_RULES
- Đảm bảo cache cũ không chứa câu trả lời từ prompt cũ

### 6.2 Cache Storage

- **Đường dẫn**: `./.generation_cache/{cache_key}.json`
- **Format JSON**:
```json
{
  "prompt_sha1": "abc123...",
  "model": "gemini-2.5-flash",
  "temperature": 0.0,
  "query": "Câu hỏi gốc",
  "answer": "Câu trả lời từ Gemini",
  "created_at": "2026-10-12T10:30:00"
}
```

### 6.3 Cache Behavior

- **Chỉ cache câu trả lời từ Gemini** (không cache câu fallback Qwen)
- **Trúng cache**: Không gọi API, trả lời ngay → tiết kiệm quota
- **Cache miss**: Gọi API → ghi cache cho lần sau

**Triển khai**: File `src/generator.py` - `_cache_get()`, `_cache_put()`

---

## 7. Cấu trúc thư mục dự án

```
hybrid_rag_agu/
├── data/
│   ├── corpus/              # Tài liệu gốc (PDF, DOCX, TXT)
│   │   ├── Tầng 1/          # Quy chế gốc (ưu tiên cao nhất)
│   │   ├── Tầng 2/          # Thông báo, kế hoạch
│   │   └── cac_file_bo_xung_khac/
│   └── evaluation/
│       └── benchmark_questions.json  # 15 câu benchmark
├── src/
│   ├── query_normalizer.py  # Chuẩn hóa câu hỏi (Qwen)
│   ├── retrieval.py         # Query expansion, từ điển đồng nghĩa
│   ├── generator.py         # Generator (Gemini) + Fallback (Qwen)
│   ├── pipeline.py          # Điều phối luồng Hybrid RAG
│   ├── evaluation.py        # Đánh giá định lượng
│   ├── vector_db.py         # ChromaDB + BM25 setup
│   ├── local_slm.py         # Local SLM wrapper (Qwen)
│   ├── text_utils.py        # Hàm tiện ích (fold, tokenize)
│   ├── chunking.py          # Phân đoạn văn bản
│   ├── loader.py            # Tải tài liệu (PDF, DOCX, TXT)
│   └── ingest.py            # Script nạp dữ liệu
├── outputs/
│   ├── evaluation_results.json
│   └── evaluation_summary.md
├── chroma_db/               # ChromaDB persistent storage
├── .generation_cache/       # Response cache
├── ingest.py                # Script ingest main
├── learn.py                 # Script active learning
├── main.py                  # CLI interface
├── ui/
│   └── app.py               # GUI (Tkinter)
├── requirements.txt
├── .env.example
└── SYSTEM_ARCHITECTURE.md   # File này
```

---

## 8. Cấu hình môi trường

### Biến môi trường quan trọng

| Biến môi trường | Mặc định | Mô tả |
|----------------|----------|-------|
| `GEMINI_API_KEY` | - | API key của Google Generative AI |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model Gemini dùng cho generator |
| `OLLAMA_HOST` | `http://localhost:11434` | Địa chỉ Ollama server |
| `OLLAMA_MODEL` | `qwen2.5:1.5b-instruct` | Model Qwen dùng cho normalization/fallback |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | Thư mục lưu ChromaDB |
| `ENABLE_HYBRID_SEARCH` | `1` | Bật/tắt True Hybrid Search (BM25 + Chroma) |
| `ENABLE_QUERY_EXPANSION` | `1` | Bật/tắt Query Expansion (từ đồng nghĩa) |
| `BM25_WEIGHT` | `0.5` | Trọng số BM25 trong RRF |
| `CHROMA_WEIGHT` | `0.5` | Trọng số ChromaDB trong RRF |
| `GENERATION_CACHE` | `1` | Bật/tắt Response Cache |
| `QWEN_FALLBACK` | `1` | Bật/tắt Fallback sang Qwen khi Gemini lỗi |
| `USE_QWEN_GENERATOR` | `0` | Dùng Qwen làm generator chính (offline) |

---

## 9. Tham khảo

### Papers & Algorithms
- **BM25**: Robertson, S., & Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond.
- **RRF**: Cormack, G. V., Clarke, C. L., & Buettcher, S. (2009). Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods.
- **BGE-M3**: Xiao, S., et al. (2023). BGE M3-Embedding: A Versatile Model for Dense Retrieval, Multi-Vector Retrieval, and Late Interaction.
- **RAG**: Lewis, P., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.

### Frameworks & Libraries
- **LangChain**: Framework để xây dựng RAG pipeline
- **ChromaDB**: Vector database open-source
- **Sentence-Transformers**: Hugging Face library cho text embeddings
- **Ollama**: Local LLM runtime
- **Google Generative AI**: Cloud LLM API

---

## 10. Phiên bản & Lịch sử

| Phiên bản | Ngày | Thay đổi chính |
|----------|------|---------------|
| 1.0 | 2026-10-12 | Bản kiến trúc đầu tiên - Hybrid RAG với BM25 + BGE-M3 + RRF |
