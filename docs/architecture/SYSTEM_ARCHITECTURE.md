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
- **Dataset**: 100 câu hỏi benchmark v3 trong `data/evaluation/benchmark_100_questions_v3.json` (kèm nhãn chủ đề + question_type chuẩn — ground truth của tầng phân loại)
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
- File: `src/retrieval/vector_db.py` - hàm `bm25_tokenize()`
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
- File: `src/core/pipeline.py` - class `EnsembleRetriever` từ LangChain
- Tham số: c = 60 (DEFAULT_RRF_C trong `src/retrieval/vector_db.py`)
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

**Triển khai**: File `src/assessment/evaluation.py` - hàm `compute_hit_at_k()`

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

**Triển khai**: File `src/assessment/evaluation.py` - hàm `compute_mrr()`

---

### 3.3 Faithfulness (LLM-Judge)

**Định nghĩa**: Tỉ lệ khẳng định trong câu trả lời được hỗ trợ bởi ngữ cảnh, được đánh giá bởi LLM giám khảo (Gemini).

**Công thức:**

```
Faithfulness = (số khẳng định được hỗ trợ) / (tổng số khẳng định)
```

**Chỉ số phụ**:
- `number_support`: Tỉ lệ con số trong câu trả lời xuất hiện trong ngữ cảnh

**Triển khai**: File `src/assessment/evaluation.py` - hàm `judge_faithfulness()`

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

**Triển khai**: File `src/assessment/evaluation.py` - hàm `compute_citation_metrics()`

---

## 4. Bảng phân công vai trò giữa Local Qwen và Cloud Gemini

### 4.1 Local Qwen 2.5 (Ollama)

| Vai trò | Mô tả | File |
|--------|-------|------|
| **Chuẩn hóa câu hỏi** | Chuyển đổi câu hỏi thông tục → thuật ngữ chuẩn quy chế | `src/core/query_normalizer.py` |
| **Fallback Generator** | Sinh câu trả lời khi Gemini hết quota/sự cố | `src/generator.py` - `_qwen_answer()` |
| **LLM-Judge (tùy chọn)** | Đánh giá faithfulness nếu không dùng Gemini | `src/assessment/evaluation.py` |

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
| **LLM-Judge chính** | Đánh giá faithfulness của câu trả lời | `src/assessment/evaluation.py` - `judge_faithfulness()` |

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

## 5. Luồng dữ liệu end-to-end (6 tầng)

```
┌─────────────────────────────────────────────────────────────────┐
│                     CÂU HỎI SINH VIÊN                         │
│          "Bị điểm yếu có bị đuổi học không ad?"                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│      LAYER 0: PHÂN LOẠI CÂU HỎI + ROUTER (Qwen local)          │
│  - src/core/classifier.py: gán 2 nhãn cho câu hỏi THÔ:              │
│      topic = "đánh giá rèn luyện" (1/14 chủ đề)                │
│      question_type = "TRA_CUU" (1/4 loại)                      │
│  - src/retrieval/router.py: nhãn → cấu hình truy xuất theo lớp           │
│      TRA_CUU giữ base; SO_SANH top_k+2 + tách truy vấn con;    │
│      THU_TUC BM25 0.6/Chroma 0.4; topic → lọc nguồn (nếu đủ    │
│      bằng chứng: "đánh giá rèn luyện" → 1059-qd-dhag-…pdf)     │
│  - Guardrail 3 lớp, suy giảm mềm: mọi lỗi → cấu hình gốc       │
│  - TẮT bằng ENABLE_CLASSIFIER=0 → pipeline chạy y hệt 5 tầng   │
│    còn lại (hành vi cũ giữ nguyên từng bước)                    │
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
│   LAYER 3: TÁCH TRUY VẤN CON (chỉ câu SO_SANH — P3.3)          │
│  - src/retrieval/retrieval.py: split_comparison_query() tách câu so       │
│    sánh thành 2–3 mệnh đề con độc lập (Qwen local)              │
│  - Guardrail chống tách dở: số dòng ngoài 2–3, truy vấn con     │
│    >200 ký tự, cặp trùng >80% token → lùi về đường đơn          │
│  - Câu TRA_CUU/THU_TUC/NGOAI_PHAM_VI đi thẳng qua tầng này      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│   LAYER 4: TRUE HYBRID SEARCH (tham số THEO ROUTER)            │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  BM25 Retriever:  Tìm kiếm từ khóa chính xác           │   │
│   │  ChromaDB Retriever: Tìm kiếm ngữ nghĩa (BGE-M3)       │   │
│   │  EnsembleRetriever: RRF dung hợp thứ hạng              │   │
│   └─────────────────────────────────────────────────────────┘   │
│  - Tham số từng lượt hỏi do LAYER 0 quyết định: top_k           │
│    (SO_SANH +2), trọng số BM25/Chroma (THU_TUC 0.6/0.4),        │
│    lọc nguồn theo chủ đề (src/retrieval/router.py)                        │
│  - Đường đa nhánh: truy xuất TỪNG truy vấn con rồi gộp          │
│    (dedup theo chunk_id, giữ rank tốt nhất)                     │
│  - Output: Top-K chunks với metadata (source, tier, chunk_id) │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│   LAYER 5: GENERATOR (prompt THEO LOẠI CÂU HỎI)                 │
│  - Build prompt: Ngữ cảnh + Câu hỏi + Quy tắc trích dẫn      │
│  - Biến thể định dạng theo question_type (P3.4):                │
│      SO_SANH → bảng so sánh theo tiêu chí, mỗi ô có trích dẫn   │
│      THU_TUC → các bước đánh số, mỗi bước kèm căn cứ            │
│      NGOAI_PHAM_VI → thêm dòng từ chối chuẩn (KHÔNG skip        │
│        truy xuất — tránh từ chối oan khi nhãn sai)              │
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

## 6. Phân loại câu hỏi & Truy xuất theo lớp (P3.1–P3.4)

### 6.1 Classifier hai nhãn — `src/core/classifier.py`

**Vai trò**: gán cho câu hỏi THÔ hai nhãn trước khi hệ thống chạm vào bất kỳ tầng
truy xuất nào — `topic` (1 trong 14 chủ đề của docs/spec/TAXONOMY.md, hoặc `null` nếu
không thuộc nhóm nào) và `question_type` (1 trong 4 nhãn `TRA_CUU` / `SO_SANH`
/ `THU_TUC` / `NGOAI_PHAM_VI`).

**Mô hình & prompt**:
- Qwen2.5-1.5B-Instruct qua Ollama — không dùng Gemini, **không tốn quota**;
  `temperature=0.0`, tối đa 160 token output, timeout `CLASSIFIER_TIMEOUT`
  (mặc định 20 giây).
- Prompt few-shot **cố định 16 ví dụ** chọn trước từ benchmark v3 (đủ 14 chủ
  đề; mỗi loại hiếm SO_SANH / THU_TUC / NGOAI_PHAM_VI có 3 ví dụ) — mỗi ví dụ
  kèm dòng "Dấu hiệu" để model bám quy tắc thay vì nhại đáp án; khối quy tắc
  được nhắc lại NGAY TRƯỚC câu hỏi (tránh Qwen nhỏ trôi về nhãn TRA_CUU).
- few-shot đóng băng làm v1 — không tinh chỉnh thêm trên chính bộ 100 câu đo
  (tránh overfit).

**Guardrail 3 lớp (suy giảm mềm — pipeline không bao giờ chết vì classifier)**:

```
Lớp 1: Qwen trả JSON hợp lệ + nhãn chuẩn → dùng luôn
       (topic chuẩn hóa không dấu qua fold(), chịu khác biệt dấu/hoa-thường)
Lớp 2: JSON lỗi hoặc nhãn lạ → bổ sung phần nhãn hỏng bằng bảng từ khóa
       (dấu hiệu theo docs/spec/TAXONOMY.md; từ khóa neo đặc thù xét TRƯỚC từ khóa chung)
Lớp 3: từ khóa cũng không khớp → topic=None, question_type="TRA_CUU"
       (router hiểu topic=None là không lọc, dùng cấu hình chung)
```

Ollama chết / timeout → trả thẳng kết quả lớp 3 kèm log cảnh báo, **không ném
ngoại lệ** ra pipeline.

**Độ chính xác đo được (benchmark 100 câu v3, P2.3 — GATE đạt)**: topic ~85%,
question_type ~81%, recall lớp hiếm 100%; điểm yếu đã biết: over-predict lớp
hiếm, biên mơ giữa TTTN-vs-CTĐT và SV Giỏi-vs-SV5T.

---

### 6.2 Router truy xuất theo lớp — `src/retrieval/router.py`

**Nguyên tắc thiết kế**: *mặc định = cấu hình hiện tại của hệ thống* (top_k từ
`RAG_TOP_K`, BM25 0.5 / Chroma 0.5, không lọc nguồn). Nhãn chỉ **điều chỉnh**,
không đổi bản chất pipeline:
- Không có nhãn (classifier tắt / lỗi / câu tự do) → trả nguyên cấu hình nền.
- Không bao giờ giảm top_k dưới giá trị gốc; không bao giờ trả trọng số tổng ≤ 0.
- `get_retrieval_config(labels, base)` là hàm thuần (không I/O, không gọi model).

**Bảng điều chỉnh theo `question_type`** (dataclass `RetrievalConfig`: top_k,
bm25_weight, chroma_weight, source_filter, enable_subquery):

| Loại | Điều chỉnh | Lý do |
|------|-----------|-------|
| `TRA_CUU` | giữ nguyên base | câu tra cứu đơn — cấu hình chung đã tối |
| `SO_SANH` | top_k + 2, bật `enable_subquery` | cần cửa sổ rộng để đối chiếu nhiều phía |
| `THU_TUC` | BM25 0.6 / Chroma 0.4 | thủ tục hay dùng từ khóa hành chính (giả thuyết, hiệu chỉnh theo A/B) |
| `NGOAI_PHAM_VI` | giữ nguyên base — **KHÔNG skip truy xuất** | precision nhãn này chỉ ~25%: skip truy xuất = từ chối oan câu đúng; nhắc từ chối nằm ở tầng generator |

**Bảng `TOPIC_SOURCE_FILTER`** (chủ đề → file nguồn được lọc qua metadata
`source` của ChromaDB): chỉ chủ đề có **≥ 5 câu** trong benchmark v3 VÀ
**≥ 80%** số câu in-corpus nằm gọn trong **≤ 2 nguồn** mới được lọc (thiết kế
phòng thủ — lọc hẹp làm rơi căn cứ nằm ở văn bản phụ). Đủ ngưỡng: 8 chủ đề;
6 chủ đề còn lại (n = 1–3 câu) cố ý KHÔNG có filter, suy giảm về cấu hình chung.

---

### 6.3 Tách truy vấn con cho SO_SANH — `split_comparison_query()` trong `src/retrieval/retrieval.py`

**Điều kiện kích hoạt** (pipeline P3.3): router bật `enable_subquery` VÀ nhãn
`question_type = SO_SANH`. Tách thực hiện trên câu **đã chuẩn hóa nhưng chưa
mở rộng từ đồng nghĩa** — cụm đồng nghĩa ghép ở cuối chuỗi làm Qwen 1.5B nhại
lại (parrot/echo) thay vì tách.

**Cách tách**: Qwen local tách câu so sánh / tổng hợp thành **2–3 mệnh đề con
độc lập** (mỗi mệnh đề hỏi đúng một vế; giữ nguyên thực thể số, mã, tên văn
bản; few-shot 2 ví dụ cố định). Mỗi truy vấn con được mở rộng từ đồng nghĩa
riêng rồi truy xuất độc lập (cùng retrieve_k như đường đơn), sau đó gộp bằng
dedup theo chunk_id + giữ rank tốt nhất.

**Guardrail chống tách dở — mọi vi phạm đều lùi về `[query]` (đường đơn)**:

```
(1) số dòng ngoài khoảng 2–3                          → không tách
(2) truy vấn con dài > 200 ký tự (nghi model trả lời   → không tách
    thay vì tách)
(3) cặp truy vấn con trùng nhau quá 80% token          → không tách
    (Jaccard token phi-số; cặp chỉ KHÁC THỰC THỂ SỐ
    như "ELO 6 / ELO 7 / ELO 8" được GIỮ — đúng mục
    tiêu mở độ phủ của dạng SO_SANH)
```

Tách dở lỡ lọt vẫn an toàn: tầng gộp đảm bảo ngữ cảnh không tệ hơn đường đơn —
câu TRA_CUU bị gán nhầm SO_SANH vì thế luôn chạy đúng như cũ.

---

### 6.4 Sinh trả lời theo loại câu hỏi — `src/generator.py`

`select_prompt_rules(question_type)` chọn biến thể khối quy tắc — **thiết kế
cache-an toàn**: biến thể chỉ NỐI THÊM vào đuôi `PROMPT_RULES` gốc, đường
`None`/`TRA_CUU` dùng nguyên văn gốc nên prompt xuất ra giống hệt từng ký tự
hành vi cũ (cache cũ vẫn trúng, không cần bump `PROMPT_VERSION`):

| question_type | Biến thể prompt |
|---------------|-----------------|
| `SO_SANH` | bảng so sánh theo tiêu chí; mỗi ô có trích dẫn riêng; không trộn số liệu giữa các vế; thiếu căn cứ một vế → nêu rõ, không bịa |
| `THU_TUC` | các bước đánh số theo thứ tự; mỗi bước kèm căn cứ (Điều/Khoản — file); hồ sơ kèm theo liệt kê từng dòng |
| `NGOAI_PHAM_VI` | thêm 1 dòng: ngữ cảnh không chứa thông tin liên quan → trả lời đúng một câu từ chối chuẩn |
| `None` / `TRA_CUU` / nhãn lạ | `PROMPT_RULES` gốc |

**`NGOAI_PHAM_VI` không skip truy xuất**: skip-early chỉ là thí nghiệm tùy chọn
(chỉ cân nhắc khi nhãn đủ tin cậy). Hiện trạng: vẫn truy xuất đầy đủ; tầng
generator chèn nhắc từ chối chuẩn, và `canonicalize_refusal()` chuẩn hóa câu
tự từ chối về ĐÚNG chuỗi `REFUSAL_TEXT` (câu trả lời có căn cứ giữ nguyên từng
ký tự — nhãn sai thì câu trả lời đúng không bị mất). Áp cho cả Gemini lẫn Qwen.

---

## 7. Response Caching

### 7.1 Cache Key Design

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

### 7.2 Cache Storage

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

### 7.3 Cache Behavior

- **Chỉ cache câu trả lời từ Gemini** (không cache câu fallback Qwen)
- **Trúng cache**: Không gọi API, trả lời ngay → tiết kiệm quota
- **Cache miss**: Gọi API → ghi cache cho lần sau

**Triển khai**: File `src/generator.py` - `_cache_get()`, `_cache_put()`

---

## 8. Cấu trúc thư mục dự án

```
hybrid_rag_agu/
├── data/
│   ├── corpus/              # Tài liệu gốc (PDF, DOCX, TXT)
│   │   ├── Tầng 1/          # Quy chế gốc (ưu tiên cao nhất)
│   │   ├── Tầng 2/          # Thông báo, kế hoạch
│   │   └── cac_file_bo_xung_khac/
│   └── evaluation/
│       └── benchmark_100_questions_v3.json  # 100 câu benchmark v3 (có nhãn question_type)
├── src/
│   ├── query_normalizer.py  # Chuẩn hóa câu hỏi (Qwen)
│   ├── classifier.py        # Phân loại câu hỏi 2 nhãn (chủ đề + loại, Qwen local)
│   ├── router.py            # Nhãn phân loại → cấu hình truy xuất theo lớp
│   ├── retrieval.py         # Query expansion, từ điển đồng nghĩa, tách truy vấn con
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
├── scripts/learn.py                 # Script active learning
├── main.py                  # CLI interface
├── ui/
│   └── app.py               # GUI (Tkinter)
├── requirements.txt
├── .env.example
└── docs/architecture/SYSTEM_ARCHITECTURE.md   # File này
```

---

## 9. Cấu hình môi trường

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
| `ENABLE_CLASSIFIER` | `0` | Bật/tắt tầng phân loại câu hỏi + router truy xuất theo lớp (mục 6) |
| `CLASSIFIER_MODEL` | (OLLAMA_MODEL) | Model Qwen riêng cho classifier (để trống dùng chung OLLAMA_MODEL) |
| `CLASSIFIER_TIMEOUT` | `20` | Thời gian chờ tối đa mỗi lần gọi classifier (giây) — quá hạn suy giảm mềm về lớp 3 |

---

## 10. Tham khảo

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

## 11. Phiên bản & Lịch sử

| Phiên bản | Ngày | Thay đổi chính |
|----------|------|---------------|
| 1.0 | 2026-10-12 | Bản kiến trúc đầu tiên - Hybrid RAG với BM25 + BGE-M3 + RRF |
| 2.0 | 2026-10-21 | Luồng 4 tầng → 6 tầng: thêm tầng phân loại câu hỏi + router truy xuất theo lớp, tách truy vấn con cho SO_SANH, prompt biến thể theo loại câu hỏi |
