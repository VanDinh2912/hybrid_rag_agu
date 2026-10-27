# Chương 03 — Truy xuất Hybrid: BM25, vector và RRF

> **Mục tiêu chương:** đi theo một câu hỏi từ lúc rời tầng chuẩn hóa đến khi trả về
> `retrieve_k` chunk; giải thích được vì sao phải `fold` trước khi tìm; tính tay được
> điểm RRF; đọc hiểu ba cơ chế phòng thủ của tầng truy xuất (fallback query, source
> filter, tách truy vấn con) và biết chúng yếu ở đâu.

Tầng truy xuất là nơi đồ án dễ mất điểm nhất khi bảo vệ: nếu chunk đúng không nằm
trong cửa sổ truy xuất thì generator giỏi đến đâu cũng chỉ có thể từ chối hoặc bịa.
Chương này giải thích **cách chọn chunk**, không giải thích cách sinh chữ.

---

## 1. Bản đồ tầng truy xuất

| Thành phần | Tệp | Dòng | Nhiệm vụ |
|---|---|---:|---|
| `fold` | `src/text_utils.py` | 13 | bỏ dấu, chữ thường, gom khoảng trắng |
| `SYNONYM_DICTIONARY` | `src/retrieval.py` | 40 | ~50 nhóm từ đồng nghĩa pháp lý |
| `expand_query_with_synonyms` | `src/retrieval.py` | 79 | ghép từ đồng nghĩa vào cuối câu |
| hằng số tách truy vấn | `src/retrieval.py` | 161–169 | 2–3 dòng, ≤200 ký tự, overlap ≤0.8 |
| `split_comparison_query` | `src/retrieval.py` | 265 | tách câu SO_SANH bằng Qwen |
| `_pairwise_overlap_too_high` | `src/retrieval.py` | 230 | guardrail chống tách dở |
| `bm25_tokenize` | `src/vector_db.py` | 26 | tokenizer kép có dấu + không dấu |
| `extract_documents_from_chroma` | `src/vector_db.py` | 40 | đọc toàn bộ chunk để dựng BM25 |
| `VectorStoreManager` | `src/vector_db.py` | 55 | nhúng bge-m3, tạo Chroma |
| `create_bm25_retriever` | `src/vector_db.py` | 109 | BM25 trên toàn bộ chunk |
| `create_ensemble_retriever` | `src/vector_db.py` | 122 | ghép BM25 + Chroma bằng RRF |
| `_init_hybrid_retriever` | `src/pipeline.py` | 114 | dựng retriever lúc khởi động |
| `HybridRAGPipeline.retrieve` | `src/pipeline.py` | 148 | một lượt truy xuất hoàn chỉnh |
| `_merge_subquery_branches` | `src/pipeline.py` | 271 | gộp nhiều nhánh truy vấn con |
| `HybridRAGPipeline.run` | `src/pipeline.py` | 298 | điều phối cả pipeline |

Hợp đồng của `retrieve()`:

```
vào:  query (có dấu, đã chuẩn hóa + mở rộng), k, fallback_query, config
ra:   list[Document] dài tối đa k — mỗi Document có page_content + metadata
      {chunk_id, source, tier}
```

Nó **không** gọi generator, **không** cắt theo `top_k` của generator. Việc phân biệt
`retrieve_k` và `top_k` nằm ở `run()` (mục 9).

Luồng đầy đủ của một lượt:

```
expanded_query ──► fold ──► ┌ BM25 (tokenizer kép) ─┐
                            │                       ├─ RRF ─► lọc nguồn ─► top k
                            └ Chroma (bge-m3) ──────┘
                                  ▲
                        filter metadata "source"
```

---

## 2. `fold` — quy ước chung của mọi phép so khớp

```python
decomposed = unicodedata.normalize("NFD", str(text).lower())
stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
return re.sub(r"\s+", " ", stripped.replace("đ", "d")).strip()
```

Ba bước, ba lý do:

1. **NFD** tách dấu thanh thành ký tự tổ hợp (combining mark). “ế” thành “ê” + dấu
   sắc; bỏ các combining mark là xong.
2. **`đ → d` thủ công.** Đây là cái bẫy kinh điển: “đ” (U+0111) là **chữ cái độc
   lập**, NFD không tách nó thành “d” + dấu. Nếu quên, `fold("Điều")` cho “đieu”,
   regex “dieu” không bao giờ khớp.
3. **Gom khoảng trắng** để hai chuỗi chỉ khác tab/xuống dòng vẫn so sánh được.

`fold` **không** xóa dấu câu. `fold("Điều 12?")` = `"dieu 12?"`. Vì vậy:
- BM25 tự xóa dấu câu trong `bm25_tokenize`;
- so khớp metadata và guardrail dùng `fold` trên chuỗi đã tách token;
- đừng dùng `fold` thay cho tokenizer.

### 2.1. Vì sao toàn hệ thống phải dùng chung một hàm?

Văn bản Tầng 1 được OCR từ bản scan và **mất dấu thanh**. Cùng một điều luật tồn tại
hai dạng:

```
Tầng 1 (OCR):  "Dieu 12. Sinh vien duoc dang ky hoc lai..."
Tầng 2 (text): "Điều 12. Sinh viên được đăng ký học lại..."
```

Nếu mỗi tầng tự chuẩn hóa một kiểu, sẽ có lúc `"Điều"` không khớp `"Dieu"` chỉ vì
một bên quên thay “đ”. `fold` là **một điểm chuẩn hóa duy nhất**; mọi tầng gọi nó
trước khi so sánh. Đây là một trong bốn nguyên tắc xuyên suốt đã nêu ở README.

### 2.2. Chỗ nào gọi `fold`?

| Nơi gọi | Mục đích |
|---|---|
| `retrieve()` trước `ensemble_retriever.invoke` | query khớp embedding của chunk OCR |
| `expand_query_with_synonyms` | khớp từ khóa không phân biệt dấu |
| `bm25_tokenize` | sinh bản token không dấu cho chỉ mục |
| lọc hậu kiểm `source` | tên file metadata có thể còn dấu |
| guardrail tách truy vấn con | so trùng token giữa các truy vấn con |
| classifier/router | so nhãn, tra bảng chủ đề |
| evaluation | so nguồn, số, trích dẫn |

Một hàm nhỏ, nhưng là “ngôn ngữ chung” của toàn repo.

---

## 3. Nhánh BM25 — tìm đúng chữ

### 3.1. Tokenizer kép

```python
clean_raw = re.sub(r"[^\w\s]", " ", text.lower())
raw_tokens = clean_raw.split()
clean_folded = re.sub(r"[^\w\s]", " ", fold(text))
folded_tokens = clean_folded.split()
return raw_tokens + folded_tokens
```

Mỗi chunk được index **hai lần token**: bản gốc có dấu và bản đã fold. Hệ quả:

| Chunk trong corpus | Query | Khớp nhờ |
|---|---|---|
| OCR “hoc phi” | “học phí” | token fold `hoc phi` |
| Chuẩn “Thiết kế và cài đặt mạng” | “thiết kế mạng” | token gốc `thiết`, `kế`, `mạng` |
| OCR “Dieu 12” | “Điều 12” | token fold `dieu`, số `12` |

Nếu chỉ index bản fold, ta mất khả năng phân biệt các từ có dấu gần nhau; nếu chỉ
index bản gốc, nửa corpus OCR gần như vô hình với BM25. Index cả hai là cách rẻ nhất
để không phải chọn.

Đánh đổi: chỉ mục phình khoảng gấp đôi. Với 361 chunk, không đáng kể; với hàng trăm
nghìn chunk, cần cân nhắc lại (có thể chỉ fold khi corpus chủ yếu OCR).

### 3.2. BM25 mạnh và yếu ở đâu?

BM25 chấm điểm dựa trên tần suất từ trong chunk và độ hiếm của từ trong toàn corpus
(IDF), có chuẩn hóa độ dài. Trong đồ án:

**Mạnh:**
- mã điều, khoản: “Điều 12”, “Khoản 3”;
- con số, mốc thời gian: “1.0”, “30/6”, “2026-2027”;
- tên riêng, viết tắt: “ELO”, “ĐTBHK”, “CNTT”;
- cụm hành chính đặc thù: “buộc thôi học”, “miễn giảm học phí”.

**Yếu:**
- câu hỏi diễn đạt lại (“bị đuổi” vs “buộc thôi học”) — trừ khi query expansion cứu;
- câu hỏi dài, nhiều từ nhiễu làm loãng tín hiệu;
- chunk OCR sai chính tả nặng (token không còn giống).

Vì vậy BM25 không bao giờ chạy một mình trong đường chính.

---

## 4. Nhánh vector — tìm đúng nghĩa

`VectorStoreManager.__init__` nạp `BAAI/bge-m3` với `normalize_embeddings=True` và
mặc định chạy CPU. Mỗi chunk được nhúng **nguyên văn** (có dấu nếu văn bản có dấu,
không dấu nếu OCR mất dấu). Khi truy vấn, `retrieve()` làm một việc quan trọng:

```python
docs = self.ensemble_retriever.invoke(fold(query))
```

Query bị fold **trước khi** vào cả hai nhánh. Với BM25 điều này không hại (tokenizer
đã có bản fold). Với Chroma, đây là quyết định thực nghiệm:

> Cùng một index, cùng câu hỏi, query **có dấu** trả về 6 chunk sai nguồn; query
> **đã fold** đưa chunk đúng lên hạng 1 (ghi chú tại `src/pipeline.py:209–213`).

Vì sao? bge-m3 là model đa ngữ, nhưng khi hai nửa corpus ở hai “hệ chữ” khác nhau
(có dấu / không dấu), query có dấu sẽ nghiêng về nửa có dấu. Fold query đưa nó về
gần “trung tâm” của cả hai nửa. Đây là **kết quả đo**, không phải suy đoán lý thuyết.

Hệ quả cần nhớ khi bảo vệ:

- Không thể nói “vector search miễn nhiễm với dấu”. Nó vẫn nhạy, nhất là khi corpus
  không đồng nhất.
- Nếu sau này corpus được làm sạch dấu hoàn toàn, có thể thử lại query có dấu; đừng
  mặc định fold là tối ưu vĩnh viễn. Phải đo lại.

### 4.1. Chi phí

| Việc | Khi nào | Chi phí |
|---|---|---|
| Nhúng 361 chunk | lúc `ingest.py` | một lần, vài phút CPU |
| Nạp model bge-m3 | mỗi lần khởi động | vài giây |
| Nhúng query | mỗi lượt hỏi | một forward pass nhỏ |
| Dựng BM25 | mỗi lần khởi động pipeline | đọc 361 chunk, vài giây |

Không có cache embedding cho query. Với demo một người dùng, chấp nhận được.

---

## 5. RRF — dung hợp hai bảng xếp hạng

### 5.1. Công thức thật trong code

LangChain `EnsembleRetriever` tính:

```
RRF(d) = Σ_i  w_i / (c + rank_i(d))
```

- `rank_i(d)` bắt đầu từ **1**;
- `w_i` là trọng số của nhánh thứ i;
- `c = 60` (`DEFAULT_RRF_C`, `src/vector_db.py:23`);
- chunk không xuất hiện trong nhánh nào thì không có số hạng của nhánh đó;
- `id_key="chunk_id"` để hai nhánh nhận ra cùng một chunk.

> **Cẩn thận tài liệu:** docstring đầu `src/retrieval.py` ghi công thức
> `k / (rank + k)`. Đó không phải công thức code chạy. Bản đúng là
> `weight / (c + rank)` — trọng số nhân vào tử số. Khi bảo vệ, hãy trích **code**
> hoặc tài liệu LangChain, đừng trích docstring cũ.

Tương tự, docstring `create_ensemble_retriever` nói “mặc định [0.4, 0.6]”, nhưng
hằng số thật là `DEFAULT_BM25_WEIGHT = 0.5`, `DEFAULT_VECTOR_WEIGHT = 0.5`
(`src/vector_db.py:21–22`). Luôn đọc hằng số.

### 5.2. Tính tay một ví dụ

Giả sử `retrieve_k = 12`, trọng số mặc định 0.5/0.5. Ba chunk A, C, E có hạng:

| Chunk | Hạng BM25 | Hạng Chroma |
|---|---:|---:|
| A | 1 | 5 |
| C | 6 | 1 |
| E | 2 | 2 |

Điểm RRF:

```
E = 0.5/(60+2) + 0.5/(60+2) = 0.0080645 + 0.0080645 = 0.0161290
A = 0.5/(60+1) + 0.5/(60+5) = 0.0081967 + 0.0076923 = 0.0158890
C = 0.5/(60+6) + 0.5/(60+1) = 0.0075758 + 0.0081967 = 0.0157725
```

Kết quả: **E > A > C**. Bài học:

1. Chunk đứng hạng 2 ở **cả hai** nhánh thắng hai chunk “nhất một nhánh, hạng 5–6
   nhánh kia”. RRF thưởng sự đồng thuận.
2. Chênh lệch giữa các hạng khá nhỏ vì `c=60` làm phẳng đường cong. Đây là chủ ý:
   RRF không muốn một nhánh độc tài quyết định thứ hạng.
3. Điểm RRF **không phải xác suất**, không so sánh được giữa các câu hỏi khác nhau.

Nếu router đặt THU_TUC thành 0.6/0.4:

```
A = 0.6/61 + 0.4/65 = 0.0098361 + 0.0061538 = 0.0159899
C = 0.6/66 + 0.4/61 = 0.0090909 + 0.0065574 = 0.0156483
```

A vẫn hơn C, nhưng khoảng cách đổi. Nếu đảo thành 0.4/0.6, C sẽ vượt A. Đây là cách
trọng số “điều chỉnh” thứ hạng mà không cần huấn luyện lại gì.

### 5.3. Vì sao RRF mà không cộng điểm thô?

Điểm BM25 có thang vài chục, điểm cosine trong [-1, 1] (hoặc [0, 1] sau normalize).
Cộng trực tiếp hai thang khác nhau là vô nghĩa. Có ba cách dung hợp:

| Cách | Ưu | Nhược |
|---|---|---|
| Cộng điểm sau chuẩn hóa | giữ được biên độ | phải chọn cách chuẩn hóa, nhạy outlier |
| Học trọng số (learning to rank) | tối ưu nếu có nhãn | cần dữ liệu huấn luyện, khó giải thích |
| **RRF (đang dùng)** | không cần chuẩn hóa, bền, dễ giải thích | bỏ thông tin biên độ |

Với đồ án 361 chunk và không có tập huấn luyện ranking, RRF là lựa chọn hợp lý.

### 5.4. `c` ảnh hưởng gì?

`c` càng nhỏ, khoảng cách giữa hạng 1 và hạng 2 càng lớn (nhánh nào xếp đầu càng
quyết định). `c=60` là giá trị kinh điển, làm phẳng đủ để khuyến khích đồng thuận.
Đổi `c` là một thí nghiệm hợp lệ, nhưng phải đo lại toàn bộ A/B — không được tuyên
bố cải thiện chỉ từ một vài câu.

---

## 6. Mở rộng từ đồng nghĩa — tăng recall, đổi bằng precision

### 6.1. Cơ chế

`expand_query_with_synonyms` làm bốn việc:

1. `fold` cả câu hỏi và từng khóa từ điển;
2. tìm khóa bằng regex có ranh giới từ: `(?:\b|_)keyword(?:\b|_)`;
3. với mỗi khóa khớp, thêm các từ đồng nghĩa **chưa có** trong câu;
4. trả `câu gốc + " " + các từ đã thêm`.

Ví dụ:

```
vào:  "Sinh viên bị điểm yếu có bị đuổi học không?"
ra:   "Sinh viên bị điểm yếu có bị đuổi học không?
       buộc thôi học thôi học kỷ luật xếp loại rèn luyện Yếu kết quả rèn luyện"
```

Thứ tự quét là thứ tự khai báo dict. Khử trùng theo dạng fold nên “kỷ luật” chỉ được
thêm một lần dù nhiều khóa cùng ánh xạ tới nó.

### 6.2. Vì sao ghép vào cuối mà không thay thế?

Giữ nguyên câu gốc ở đầu để:
- embedding vẫn bám ngữ nghĩa câu hỏi thật;
- BM25 vẫn thấy các từ khóa gốc với tần suất như cũ;
- dễ debug: đọc phần đầu là biết câu hỏi, phần sau là phần mở rộng.

Nhược điểm: câu trở nên dài, có thể loãng embedding. Không có cơ chế trọng số cho
phần mở rộng.

### 6.3. Ba rủi ro cần biết

1. **Khóa quá chung.** `"yếu"` khớp cả “sức khỏe yếu”, “máy yếu”, kéo về chunk rèn
   luyện không liên quan. Đây là lỗi thiết kế từ điển, không phải lỗi code.
2. **Mở rộng chéo chủ đề.** “học phí” được thêm “hỗ trợ học phí”, “miễn giảm học
   phí” — hữu ích cho câu hỏi chính sách, nhưng có thể kéo chunk miễn giảm vào câu
   hỏi “học phí bao nhiêu”.
3. **Không có đo lường riêng.** Expansion bật mặc định; muốn biết nó giúp hay hại
   phải chạy A/B với `ENABLE_QUERY_EXPANSION=0`. Đừng tuyên bố nó cải thiện nếu
   chưa đo.

Tắt bằng biến môi trường:

```bash
ENABLE_QUERY_EXPANSION=0
```

`HybridRAGPipeline.__init__` đọc cờ này tại `src/pipeline.py:99`.

---

## 7. `HybridRAGPipeline.retrieve` — từng bước

### 7.1. Đường nhanh và đường dự phòng

```python
if self.use_hybrid and self.ensemble_retriever is not None:
    ...
return self.vector_db.similarity_search(fold(query), k=k)
```

Nếu BM25 dựng thất bại (Chroma rỗng, thiếu thư viện, lỗi bất kỳ), pipeline vẫn chạy
bằng vector thuần. Đây là **suy giảm mềm**: mất recall, không mất dịch vụ.

Lưu ý: đường dự phòng bỏ qua `config` (không trọng số, không filter nguồn). Nếu
router đang lọc nguồn mà retriever hybrid chết, kết quả có thể trộn nhiều nguồn hơn
dự kiến. Đây là đánh đổi có chủ ý: thà trả kết quả rộng còn hơn chết.

### 7.2. Trọng số theo từng câu hỏi

`EnsembleRetriever` đọc `self.weights` tại thời điểm `invoke`, nên pipeline gán lại
thuộc tính thay vì dựng retriever mới:

```python
if config is not None:
    self.ensemble_retriever.weights = [config.bm25_weight, config.chroma_weight]
else:
    self.ensemble_retriever.weights = [self.bm25_weight, self.vector_weight]
```

Nhánh `else` rất quan trọng: nếu lượt trước bật router (ví dụ THU_TUC 0.6/0.4) mà lượt
sau tắt classifier, trọng số phải trở về mặc định. Không có nó, cấu hình sẽ “dính”
sang câu sau.

> ⚠️ **Nợ kỹ thuật:** đây là trạng thái dùng chung, không an toàn khi chạy song song.
> Hai request đồng thời có thể ghi đè `weights`/`k`/`filter` của nhau. Streamlit demo
> một người dùng thì không sao; nếu triển khai web đa người dùng, phải tạo retriever
> theo từng request hoặc khóa truy cập.

### 7.3. Đồng bộ `k` và filter cho hai nhánh

```python
for r in sub_retrievers:
    if hasattr(r, "k"):
        r.k = k
    elif hasattr(r, "search_kwargs") and isinstance(r.search_kwargs, dict):
        r.search_kwargs["k"] = k
        if config is not None and config.source_filter:
            r.search_kwargs["filter"] = {"source": {"$in": list(config.source_filter)}}
        else:
            r.search_kwargs.pop("filter", None)
```

Ba chi tiết:

1. BM25Retriever dùng thuộc tính `.k`; Chroma retriever dùng `.search_kwargs["k"]`.
   Vòng lặp xử lý cả hai kiểu.
2. Filter chỉ gắn vào nhánh Chroma. BM25 của LangChain không hỗ trợ filter metadata,
   nên phải lọc hậu kiểm (mục 7.6).
3. `pop("filter", None)` dọn trạng thái cũ. Nếu quên, câu sau không lọc vẫn bị lọc
   theo nguồn của câu trước.

### 7.4. Gọi retriever với query đã fold

```python
docs = self.ensemble_retriever.invoke(fold(query))
```

`EnsembleRetriever` trả về **tất cả** chunk duy nhất mà hai nhánh tìm được, đã xếp
hạng RRF — có thể tới `2 × k` chunk vì mỗi nhánh lấy `k`. Pipeline cắt còn `k` ở
cuối hàm.

### 7.5. Fallback query

Nếu caller truyền `fallback_query` (trong `run()` là `raw_query`), pipeline chạy
thêm một lượt với câu gốc, rồi gộp:

```python
seen_chunk_ids = set()
merged_docs = []
for doc in docs:            # kết quả của query chính
    ...                     # giữ nguyên thứ tự
for doc in fallback_docs:   # chỉ thêm chunk chưa xuất hiện
    ...
docs = merged_docs
```

Mục đích: nếu Qwen chuẩn hóa làm rơi mất từ khóa quan trọng, câu gốc vẫn cứu được
chunk. Khử trùng bằng `chunk_id`, ưu tiên thứ hạng của query chính.

**Đọc kỹ thứ tự cắt:** hàm trả `docs[:k]` **sau** khi gộp. Query chính thường đã cho
đủ `k` chunk duy nhất, nên fallback chủ yếu là **lưới an toàn** cho trường hợp query
chính trả về ít hơn `k` (hai nhánh trùng nhau nhiều). Đừng trình bày fallback như
nguồn recall chính; nó không phải.

### 7.6. Lọc hậu kiểm theo nguồn

```python
allowed_sources = {fold(source) for source in config.source_filter}
filtered_docs = [
    doc for doc in docs
    if fold(str(doc.metadata.get("source", ""))) in allowed_sources
]
if filtered_docs:
    docs = filtered_docs
else:
    print("[Router] Cảnh báo: source_filter loại bỏ hết kết quả — giữ nguyên...")
```

Hai quyết định phòng thủ:

1. **So khớp fold** vì metadata `source` có thể còn dấu trong khi bảng filter viết
   theo tên file thực tế; fold cả hai để tránh lệch.
2. **Nếu lọc sạch** thì giữ nguyên kết quả chưa lọc. Thà trả rộng còn hơn trả rỗng.
   Nhưng hệ quả là câu hỏi thuộc chủ đề lọc hẹp có thể lọt chunk ngoài nguồn nếu
   nguồn đúng không được truy xuất. Đây là lý do router chỉ lọc 8/14 chủ đề có bằng
   chứng đủ mạnh (chương 05).

Nếu lọc còn **một phần**, không có bước bù: danh sách ngắn hơn `k`, generator nhận ít
ngữ cảnh hơn. Không sai về chức năng, nhưng cần biết khi đọc latency/độ phủ.

### 7.7. Bảng sự cố

| Sự cố | Hành vi | Hệ quả |
|---|---|---|
| Chroma rỗng | `_init_hybrid_retriever` trả sớm | dùng vector thuần, không BM25 |
| Thiếu `rank_bm25`/lỗi BM25 | bắt exception, `ensemble_retriever=None` | vector thuần |
| `invoke` lỗi giữa chừng | bắt exception, `similarity_search` | mất RRF, mất filter |
| `source_filter` loại hết | giữ kết quả chưa lọc | có thể lọt nguồn ngoài |
| fallback query lỗi | chỉ dùng kết quả chính | recall hẹp hơn |
| `config=None` | trọng số env, không filter | đường chạy trước P3.2 |

Không có nhánh nào ném lỗi ra ngoài `retrieve()`. Đây là nguyên tắc “không tầng nào
được giết câu hỏi” — nhưng cũng là lý do phải đọc log cảnh báo, vì hệ thống có thể
đang chạy ở chế độ suy giảm mà người dùng không biết.

---

## 8. Tách truy vấn con cho câu so sánh

### 8.1. Điều kiện kích hoạt

Chỉ khi **đồng thời**:

1. `ENABLE_CLASSIFIER=1`;
2. classifier gán `question_type = SO_SANH`;
3. router đặt `enable_subquery=True` (chỉ SO_SANH);
4. `split_comparison_query` trả về ≥ 2 truy vấn con hợp lệ.

Nếu bất kỳ điều kiện nào sai, pipeline chạy đường đơn y như trước. Câu TRA_CUU bị
gán nhầm SO_SANH vẫn an toàn vì guardrail sẽ không tách hoặc tách xong vẫn gộp được.

### 8.2. Tách trên câu chuẩn hóa, không tách trên câu mở rộng

```python
candidate_subs = split_comparison_query(normalized_query, llm_client=self.local_slm)
```

Lý do (ghi tại `src/pipeline.py:379–382`): các cụm đồng nghĩa ghép ở cuối làm Qwen
1.5B “parrot” — nó nhại lại cụm mở rộng thay vì tách. Mỗi truy vấn con sau đó vẫn
được mở rộng từ đồng nghĩa riêng trước khi truy xuất, nên recall không mất.

### 8.3. Prompt và parse

Prompt có 2 ví dụ few-shot cố định (học phí kỹ thuật vs kinh tế; học bổng khuyến
khích vs tài năng), yêu cầu mỗi dòng một truy vấn, tối đa 3 dòng, không đánh số,
không trả lời. `_clean_subquery_lines` bỏ bullet `-`, `*`, `1.`, `(1)`, dấu nháy và
khoảng trắng thừa.

### 8.4. Ba guardrail

| Guardrail | Ngưỡng | Chống điều gì |
|---|---|---|
| số dòng | 2–3 | model trả 1 dòng hoặc lan man 5–6 dòng |
| độ dài mỗi dòng | ≤ 200 ký tự | model trả lời thay vì tách |
| trùng cặp | Jaccard token nội dung > 0.8 **và** cùng tập số | model nhân bản cùng một vế |

Chi tiết tinh tế nằm ở điều kiện thứ ba:

```python
if number_sets[i] == number_sets[j]:
    overlap = len(a & b) / len(union)
    if overlap > 0.8:
        return True
```

Nếu hai truy vấn con **khác nhau về tập số**, chúng được giữ, kể cả khi chữ gần
giống nhau. Đây chính là mục tiêu của SO_SANH: “ELO 6”, “ELO 7”, “ELO 8” là ba vế
hợp lệ dù cấu trúc câu gần như nhau. Nếu chỉ dùng Jaccard thô, hệ thống sẽ loại
chính các câu so sánh mức chuẩn đầu ra.

### 8.5. Gộp các nhánh

`_merge_subquery_branches`:

```python
best: dict[chunk_id, (rank, branch_idx, doc)] = {}
for branch_idx, docs in enumerate(branches):
    for pos, doc in enumerate(docs):
        rank = pos
        if current is None or (rank, branch_idx) < (current[0], current[1]):
            best[key] = (rank, branch_idx, doc)
merged = sorted(best.values(), key=lambda item: (item[0], item[1]))
return [doc for _, _, doc in merged[:k]]
```

Điểm của chunk = **thứ hạng tốt nhất** của nó trong bất kỳ nhánh nào; hòa thì ưu
tiên nhánh đứng trước. Không cộng điểm RRF giữa các nhánh vì mỗi nhánh đã là một
phép RRF hoàn chỉnh; hạng trong nhánh đã đủ để so sánh tương đối.

Ví dụ với 3 truy vấn con, `retrieve_k=12`:

```
nhánh 1: 12 chunk
nhánh 2: 12 chunk
nhánh 3: 12 chunk
        ↓ khử trùng theo chunk_id, lấy hạng tốt nhất
tối đa 36 chunk duy nhất → cắt còn 12
```

Cắt về đúng `retrieve_k` để context của generator không phình. Nhưng lưu ý: một chunk
đứng hạng 8 ở nhánh 2 có thể lọt vào 12 cuối, trong khi chunk hạng 13 ở nhánh 1 bị
loại — đây là chủ ý mở rộng phủ.

### 8.6. Rủi ro

- Tách một câu không phải so sánh → mỗi nhánh truy xuất một nửa câu, ngữ cảnh có thể
  rời rạc. Guardrail giảm nhưng không loại bỏ hoàn toàn.
- Tách đúng nhưng một vế không có trong corpus → nhánh đó trả chunk nhiễu; gộp vẫn
  có thể đẩy nhiễu vào top 12.
- Chi phí: 3 lần gọi Qwen tách + 3 lần truy xuất + 3 lần nhúng query. Chậm hơn đường
  đơn đáng kể; chỉ áp cho SO_SANH (5% benchmark v3).

---

## 9. Oversampling: `retrieve_k` khác `top_k`

### 9.1. Công thức

```python
effective_top_k = top_k                    # hoặc top_k + 2 nếu SO_SANH
retrieve_k = effective_top_k * self.oversample_factor   # mặc định ×2
gen_docs = all_docs[:effective_top_k]
sources = [describe_document(d, i) for i, d in enumerate(all_docs)]
```

| Biến | Ý nghĩa | Ai dùng |
|---|---|---|
| `top_k` | tham số caller truyền vào | `run()` |
| `effective_top_k` | sau khi router điều chỉnh (+2 cho SO_SANH) | generator window |
| `retrieve_k` | `effective_top_k × oversample_factor` | cửa sổ đo Hit@K/MRR |
| `contexts` | nội dung `effective_top_k` chunk đầu | prompt generator |
| `sources` | metadata **toàn bộ** `retrieve_k` chunk | evaluation/UI |

Ví dụ mặc định `main.py` (top_k=6, oversample=2):

```
retrieve_k = 12
generator nhận 6 chunk
evaluation đo Hit@3/5/6 trên 12 chunk
```

Với câu SO_SANH:

```
effective_top_k = 6 + 2 = 8
retrieve_k = 8 × 2 = 16
generator nhận 8 chunk
```

### 9.2. Vì sao tách hai cửa sổ?

Mục đích của đồ án là **đo khả năng truy xuất** tách khỏi **khả năng sinh**. Nếu chỉ
đo trên 6 chunk đưa vào generator, Hit@3 và Hit@6 gần như trùng nhau; không thấy được
retriever có tìm ra chunk đúng ở hạng 7–12 hay không. Cửa sổ đo rộng hơn cho biết
“nếu tăng context, câu trả lời có cơ hội đúng không”.

Nhưng generator vẫn chỉ nhận `top_k` để:
- giữ prompt ngắn, giảm lost-in-the-middle;
- giữ chi phí token ổn định;
- không thay đổi chất lượng sinh giữa các lần đo.

### 9.3. Cẩn thận khi đọc số

- `Hit@3` trong báo cáo là hit trong **12 chunk truy xuất**, không phải trong 3 chunk
  generator thấy. Đừng nói “generator nhìn thấy chunk đúng ở hạng 3” nếu nó chỉ nhận
  6 chunk — hạng 3 nằm trong 6, nhưng hạng 5 thì không.
- Với SO_SANH, generator nhận 8 chunk, không phải 6. Báo cáo ghi `top_k=6` là tham
  số caller; cửa sổ sinh thực tế là 8. Khi so sánh latency/độ dài prompt, phải nhớ
  điều này.
- `oversample_factor=1` sẽ khiến `retrieve_k = effective_top_k`, mất khả năng đo
  Hit@5/6 riêng. Evaluation đặt `retrieve_k = max(top_k, 6)` để đủ cửa sổ đo — nhưng
  code hiện lại truyền chính `retrieve_k` vào `pipeline.run(top_k=...)`, nên với
  `-k 4` generator nhận 6 thay vì 4 (`contexts=6`, `sources=12`). Đây là lỗi cần sửa,
  không phải thiết kế; xem Chương 08 và mục L11 Chương 10.

---

## 10. Truy vết một câu hỏi thật

Câu hỏi:

> “Học phí khối ngành kỹ thuật năm học 2026-2027 là bao nhiêu?”

Giả sử `ENABLE_CLASSIFIER=1`, classifier trả:

```json
{"topic": "học phí", "question_type": "TRA_CUU"}
```

Router (`src/router.py:158`):
- `top_k = 6` (từ caller);
- trọng số 0.5/0.5 (TRA_CUU giữ base);
- `source_filter` = 2 file học phí;
- `enable_subquery = False`.

Các bước:

1. **Chuẩn hóa** (`run`, dòng 353): Qwen viết lại thành câu học vụ, ví dụ
   “Mức học phí của khối ngành kỹ thuật năm học 2026-2027 là bao nhiêu?”.
2. **Mở rộng** (dòng 356): khóa “học phí” khớp, thêm “hỗ trợ học phí”, “miễn giảm
   học phí”, “chế độ chính sách học phí” vào cuối.
3. **Fold** (dòng 364): toàn bộ thành chữ không dấu để log; `retrieve()` sẽ fold lại
   lần nữa trước khi invoke (fold idempotent, không hại).
4. **`retrieve_k = 6 × 2 = 12`**.
5. **`retrieve()`** gán trọng số 0.5/0.5, đặt `k=12` cho cả hai nhánh, gắn filter
   `source ∈ {2 file học phí}` cho Chroma.
6. **BM25** lấy 12 chunk trong 2 file; **Chroma** lấy 12 chunk trong 2 file (filter
   được áp trước khi tìm, nên không lãng phí ứng viên ngoài nguồn).
7. **RRF** xếp hạng tối đa 24 chunk duy nhất, cắt còn 12.
8. **Fallback query**: chạy lại với câu gốc; gộp; thường không thêm gì vì đã đủ 12.
9. **Lọc hậu kiểm**: giữ chunk có `source` thuộc 2 file; nếu rỗng thì bỏ lọc.
10. **`run()`** lấy 6 chunk đầu làm `contexts`, tạo `sources` từ 12 chunk, gọi
    generator với `normalized_query` (có dấu) và 6 chunk.

Điều đáng chú ý: **query mở rộng được dùng cho cả hai nhánh**, kể cả Chroma. Vì vậy
các cụm “miễn giảm học phí” có thể kéo chunk về chính sách miễn giảm vào top 6 dù
câu hỏi chỉ hỏi mức học phí. Đây là đánh đổi recall/precision có thật, và là lý do
nên đọc `sources` khi đánh giá một câu trả lời sai.

---

## 11. Bài tập chương

**A. Tính RRF.** Với `c=60`, trọng số 0.6/0.4, ba chunk có hạng:

| Chunk | BM25 | Chroma |
|---|---:|---:|
| X | 1 | 4 |
| Y | 3 | 1 |
| Z | 2 | 2 |

Tính điểm và xếp hạng. Chunk nào thắng vì đồng thuận?

**B. Vì sao fold query?** Một bạn đề xuất bỏ `fold` trước `invoke` để “giữ ngữ nghĩa
tốt hơn cho bge-m3”. Nêu hai lý do phản biện và một thí nghiệm để kiểm chứng.

**C. Fallback query.** Giải thích vì sao fallback query thường không làm thay đổi
top-12 khi query chính đã trả đủ 12 chunk. Khi nào nó thực sự có ích?

**D. Guardrail tách.** Hai truy vấn con:

```
“Điều kiện đạt chuẩn đầu ra ELO 6 là gì?”
“Điều kiện đạt chuẩn đầu ra ELO 7 là gì?”
```

Chúng có bị guardrail loại không? Vì sao? Nếu thay ELO 7 bằng ELO 6 ở câu thứ hai
thì sao?

**E. Source filter.** Vì sao `retrieve()` giữ nguyên kết quả chưa lọc khi filter loại
sạch? Nêu một tình huống filter này che mất lỗi classifier.

<details>
<summary>Đáp án gợi ý</summary>

**A.**

```
X = 0.6/61 + 0.4/64 = 0.0098361 + 0.0062500 = 0.0160861
Y = 0.6/63 + 0.4/61 = 0.0095238 + 0.0065574 = 0.0160812
Z = 0.6/62 + 0.4/62 = 0.0096774 + 0.0064516 = 0.0161290
```

Xếp hạng: **Z > X > Y**. Z thắng vì đứng hạng 2 ở cả hai nhánh; X nhỉnh hơn Y nhờ
trọng số BM25 cao hơn, dù Y đứng đầu nhánh vector.

**B.** (1) Nửa corpus OCR mất dấu; query có dấu nghiêng embedding về nửa có dấu, thực
nghiệm 15-10 cho thấy 6 chunk sai nguồn và chunk đúng tụt hạng. (2) BM25 cũng nhận
query đã fold; tokenizer kép vẫn khớp, nên fold không làm mất khả năng tìm chữ. Thí
nghiệm: cùng index, chạy bộ câu hỏi với hai biến thể query (fold và không fold), so
Hit@3/MRR. Nếu corpus được làm sạch dấu hoàn toàn, kết quả có thể đảo — phải đo lại.

**C.** Query chính thường trả về `retrieve_k` chunk duy nhất hoặc hơn (hai nhánh mỗi
bên `retrieve_k`), nên sau khi gộp, `docs[:retrieve_k]` chỉ chứa chunk của query
chính; chunk fallback nằm sau và bị cắt. Nó có ích khi query chính trả **ít hơn**
`retrieve_k` chunk duy nhất — ví dụ hai nhánh trùng nhau nhiều, corpus nhỏ, hoặc filter
làm hẹp kết quả — lúc đó fallback lấp đầy cửa sổ.

**D.** Không bị loại. Tuy Jaccard token nội dung rất cao, `number_sets` khác nhau
(`{6}` vs `{7}`), nên điều kiện `number_sets[i] == number_sets[j]` sai và guardrail
không kích hoạt. Nếu cả hai đều ELO 6, tập số giống nhau, Jaccard > 0.8 → bị coi là
tách dở và trả `[query]`.

**E.** Vì mục tiêu là không bao giờ trả rỗng; thà trả kết quả rộng còn hơn làm câu hỏi
chết. Tình huống che lỗi: classifier gán nhầm chủ đề “học phí” cho câu hỏi về học
bổng; filter chỉ còn 2 file học phí; nếu may mắn có chunk học phí chứa từ “học bổng”,
kết quả không rỗng nên không có cảnh báo, và chunk đúng trong file học bổng không bao
giờ được truy xuất. Người đọc log chỉ thấy câu trả lời thiếu căn cứ, không thấy lỗi
router.

</details>

Tiếp theo: [04 — Chuẩn hóa câu hỏi và phân loại](04_chuan_hoa_va_classifier.md).
