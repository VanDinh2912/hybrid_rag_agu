# Chương 07 — Pipeline end-to-end: một câu hỏi đi qua toàn hệ thống

> **Mục tiêu chương:** đọc được `HybridRAGPipeline.run()` như một hợp đồng; biết mỗi
> cờ môi trường bật/tắt tầng nào; truy vết được một câu hỏi từ `main.py` đến câu trả lời;
> hiểu các đường suy giảm (Ollama chết, BM25 lỗi, filter rỗng, 429); và nhận ra hai
> điểm hay bị bỏ qua: cửa sổ truy xuất khác cửa sổ sinh, và chế độ `scripts/learn.py` không
> thực sự “học” vào retriever đang chạy.

Chương 06 đã mổ xẻ tầng sinh. Chương này ghép mọi tầng lại và trả lời câu hỏi thực dụng
nhất khi bảo vệ: **“Một câu hỏi của sinh viên đi qua những bước nào, ở mỗi bước có thể
hỏng gì, và hệ thống xử lý thế nào?”**

---

## 1. Bản đồ entrypoint

Repo có năm cửa vào, dùng chung lõi `HybridRAGPipeline`:

| Entrypoint | Vai trò | Có gọi model? | Ghi chú |
|---|---|---|---|
| `ingest.py` | nạp corpus → chunk → nhúng → Chroma | bge-m3 (embedding) | xóa collection cũ rồi tạo mới |
| `main.py` | CLI hỏi đáp thật | Qwen chuẩn hóa + Gemini/Qwen sinh | mặc định Gemini |
| `scripts/learn.py` | hỏi, người chấm, ghi bài học, rebuild | Qwen + Gemini | “học” = thêm file ghi chú |
| `src/evaluation.py` | chạy benchmark, đo chỉ số | tùy cấu hình | chương 08 |
| `scripts/benchmark_chunking.py` | so sánh chiến lược chunk | tokenizer, không sinh | chương 08 |
| `streamlit run ui/app.py` | giao diện web | Qwen + Gemini | chương 09 |

Điểm chung: tất cả đều dựng `VectorStoreManager` → `Chroma` đã persist, rồi
`LocalSLM` → `Generator` → `HybridRAGPipeline`. Không entrypoint nào (trừ `ingest.py`)
đọc lại toàn bộ PDF mỗi lần hỏi; chúng chỉ nạp mô hình embedding để nhúng **câu hỏi**.

---

## 2. `HybridRAGPipeline`: vật chứa và vòng đời

### 2.1. Hàm khởi tạo

`HybridRAGPipeline.__init__` (`src/pipeline.py:80–112`) nhận:

```python
HybridRAGPipeline(
    vector_db,              # Chroma đã persist
    local_slm,              # LocalSLM (Qwen) để chuẩn hóa
    generator,              # GeminiGenerator hoặc QwenGenerator
    oversample_factor=2,
    use_hybrid=True,
    bm25_weight=0.5,
    vector_weight=0.5,
    retriever=None,         # retriever tùy chỉnh cho test
    expand_query=True,
)
```

Nó đọc thêm biến môi trường và **ghi đè** tham số:

| Cờ | Mặc định | Tác dụng | Dòng |
|---|---|---|---|
| `ENABLE_HYBRID_SEARCH` | `1` | `0` → chỉ Chroma vector, bỏ BM25 | `:96` |
| `BM25_WEIGHT` | `0.5` | trọng số BM25 trong RRF | `:97` |
| `CHROMA_WEIGHT` | `0.5` | trọng số Chroma | `:98` |
| `ENABLE_QUERY_EXPANSION` | `1` | `0` → không mở rộng từ đồng nghĩa | `:99` |
| `ENABLE_CLASSIFIER` | `0` | `1` → bật classifier + router | `:102` |

Hai điểm dễ nhầm:

- **Mặc định classifier là TẮT.** A/B “WITH” phải đặt `ENABLE_CLASSIFIER=1`; nếu `.env`
  không đặt, `main.py` chạy đường WITHOUT. Khi đọc kết quả, luôn kiểm tra cờ này.
- **`BM25_WEIGHT`/`CHROMA_WEIGHT` trong env thắng tham số truyền vào.** Gọi
  `HybridRAGPipeline(..., bm25_weight=0.8)` mà env có `BM25_WEIGHT=0.5` thì vẫn là 0.5.
  Đây là bẫy khi viết test: muốn test trọng số phải `monkeypatch.delenv` hoặc set env
  trước khi khởi tạo.

### 2.2. Dựng retriever

`_init_hybrid_retriever` (`:114–146`):

1. Nếu `vector_db` đã là retriever có `invoke` mà không có `get` → dùng luôn.
2. Nếu không có `get` → bỏ qua hybrid.
3. `extract_documents_from_chroma` lấy toàn bộ chunk; rỗng → bỏ qua.
4. Dựng `BM25Retriever.from_documents(docs, preprocess_func=bm25_tokenize)`, đặt `k=12`.
5. Dựng Chroma retriever `search_kwargs={"k": 12}`.
6. `EnsembleRetriever(retrievers=[bm25, chroma], weights=[w1, w2], c=60,
   id_key="chunk_id")`.

Con số 12 ở đây chỉ là **mặc định khởi tạo**; mỗi lần `retrieve(k=...)` sẽ ghi đè `k`
của cả hai retriever con (`:193–198`). Vì vậy không nên đọc `k=12` như cấu hình cuối.

Bọc `try/except` quanh toàn bộ: BM25 lỗi → in cảnh báo, `ensemble_retriever = None`,
pipeline vẫn sống và tự lùi về `similarity_search`. Đây là “suy giảm mềm” cấp khởi tạo.

---

## 3. `run()`: chín bước của một câu hỏi

`HybridRAGPipeline.run(question, top_k=4)` (`:298–444`) là hợp đồng chính. Sơ đồ:

```
question (raw)
  │
  ├─ 1. validate + strip; top_k = max(1, top_k)
  │
  ├─ 2. nếu ENABLE_CLASSIFIER:
  │      classify_query(raw) → labels
  │      base_config_from_env() → base
  │      base.top_k = top_k
  │      get_retrieval_config(labels, base) → config
  │      effective_top_k = config.top_k
  │      (lỗi bất kỳ → labels=None, config=None, effective_top_k=top_k)
  │
  ├─ 3. retrieve_k = effective_top_k × oversample_factor
  │
  ├─ 4. normalize_user_query(local_slm, raw) → normalized_query
  │
  ├─ 5. expand_query_with_synonyms(normalized) → expanded_query
  │
  ├─ 6. retrieval_query = fold(expanded_query)   # chỉ để log/debug
  │
  ├─ 7. nếu config.enable_subquery và labels.type == SO_SANH:
  │      split_comparison_query(normalized) → sub_queries
  │      nếu ≥2: retrieve từng nhánh, gộp theo thứ hạng tốt nhất
  │      ngược lại: truy xuất đơn
  │
  ├─ 8. all_docs = retrieve(expanded, k=retrieve_k,
  │                         fallback_query=raw, config=config)
  │      gen_docs = all_docs[:effective_top_k]
  │      contexts = [doc.page_content for doc in gen_docs]
  │      sources  = metadata của TOÀN BỘ all_docs
  │
  └─ 9. generator.generate_answer(normalized, gen_docs, question_type)
         → dict kết quả
```

### 3.1. Bước 2 — classifier/router

- Classifier nhận **câu thô**, không phải câu chuẩn hóa. Lý do: nhãn chủ đề/loại câu
  nên dựa trên điều sinh viên hỏi, không phụ thuộc Qwen viết lại đúng hay sai.
- `base_config.top_k = top_k` ghi đè mặc định 4 của router bằng tham số caller. Nếu
  caller không truyền, `run` mặc định 4; `main.py` truyền 6 (hoặc `RAG_TOP_K`).
- Router có thể tăng `top_k` (SO_SANH +2), đổi trọng số (THU_TUC 0.6/0.4), đặt filter
  nguồn, bật subquery. Không bao giờ giảm `top_k` — đây là ràng buộc có chủ ý để tránh
  mất recall.
- **Mọi lỗi** trong khối này bị bắt (`:337–348`): log cảnh báo, `labels=None`,
  `retrieval_config=None`, `effective_top_k=top_k`. Câu hỏi vẫn chạy đường gốc. Đây là
  lý do classifier có thể “im lặng tắt” mà người dùng không biết, trừ khi đọc log.

### 3.2. Bước 3 — oversampling

```python
retrieve_k = effective_top_k * self.oversample_factor
```

`oversample_factor` mặc định 2 (`:54`), được `max(1, int(...))` ở constructor. Với
`top_k=6` → `retrieve_k=12`. Với SO_SANH `effective_top_k=8` → 16. Với THU_TUC
`effective_top_k=6` → 12. Đây là con số thực của “cửa sổ truy xuất”, không phải 6 như
metadata A/B ghi (`retrieve_k=6` chỉ là floor truyền vào).

### 3.3. Bước 4 — chuẩn hóa

`normalize_user_query(self.local_slm, raw_query)` (`:353`). Đường này gọi
`LocalSLM.generate`, **không** gọi `LocalSLM.normalize_query`, nên các guardrail số/
token-overlap trong `local_slm.py` không chạy (chương 04). Nếu Ollama lỗi, hàm bắt mọi
exception và trả `raw_text` (`query_normalizer.py:379–382`). Vì vậy `main.py` hiếm khi
thấy `LocalSLMError`; lỗi bị nuốt ở tầng chuẩn hóa.

### 3.4. Bước 5–6 — mở rộng và fold

`expand_query_with_synonyms` thêm cụm đồng nghĩa vào cuối câu (nếu bật). Sau đó
`retrieval_query = fold(expanded_query)` chỉ để log/kiểm tra; `retrieve()` tự fold lại
khi gọi ensemble. Việc fold hai lần là dư thừa nhưng vô hại; điểm cần nhớ là **BM25 nhận
query đã fold**, còn Chroma cũng nhận query đã fold để khớp chunk OCR mất dấu.

### 3.5. Bước 7 — subquery cho SO_SANH

Điều kiện kép (`:369–375`): `config.enable_subquery` **và** nhãn `question_type` là
`SO_SANH`. Nếu router đã bật nhưng classifier gán nhầm, subquery không chạy — đúng như
thiết kế “chỉ tách khi chắc là so sánh”.

- Tách trên `normalized_query`, **không** trên `expanded_query` (tránh Qwen parrot các
  cụm đồng nghĩa).
- Mỗi nhánh được mở rộng từ đồng nghĩa riêng rồi `retrieve(k=retrieve_k, config=...)`.
- `_merge_subquery_branches` (`:271–296`) gộp theo `chunk_id`, điểm = thứ hạng tốt nhất
  xuyên nhánh, cắt `k`. Không cộng điểm RRF giữa các nhánh — đây là fusion theo rank,
  không phải RRF đầy đủ.
- Nếu tách ra <2 truy vấn hoặc lỗi → `sub_queries=None`, chạy đường đơn với
  `fallback_query=raw`.

### 3.6. Bước 8 — cửa sổ truy xuất và cửa sổ sinh

Đây là chỗ dễ nói sai nhất khi bảo vệ:

```
all_docs  = retrieve_k chunk  → dùng cho Hit@K, MRR, hiển thị sources
gen_docs  = all_docs[:effective_top_k] → generator thực sự đọc
sources   = metadata của all_docs (retrieve_k phần tử)
contexts  = nội dung của gen_docs (effective_top_k phần tử)
```

Ba con số có thể khác nhau:

| Cấu hình | `top_k` caller | `effective_top_k` | `retrieve_k` | generator đọc | `sources` |
|---|---:|---:|---:|---:|---:|
| Mặc định, classifier tắt | 6 | 6 | 12 | 6 | 12 |
| TRA_CUU, classifier bật | 6 | 6 | 12 | 6 | 12 |
| SO_SANH, classifier bật | 6 | 8 (+2) | 16 | 8 | 16 |
| THU_TUC, classifier bật | 6 | 6 | 12 | 6 | 12 |
| `main.py -k 4` | 4 | 4 | 8 | 4 | 8 |

Vì `sources` chứa cả 12/16 chunk, `main.py` in “NGUỒN TRÍCH DẪN: 12 chunk” trong khi
generator chỉ thấy 6/8. Đây không phải bug dữ liệu, mà là **nhãn hiển thị gây hiểu nhầm**:
12 chunk là “ứng viên truy xuất”, không phải “ngữ cảnh đã dùng để trả lời”. Khi bảo vệ,
nói đúng: “sources là recall window; generator window là top_k hiệu dụng”.

### 3.7. Bước 9 — sinh và trả kết quả

```python
answer = self.generator.generate_answer(
    query=normalized_query,
    retrieved_docs=gen_docs,
    question_type=labels.get("question_type") if labels else None,
)
```

Kết quả trả về (`:434–444`) gồm:

| Khóa | Kiểu | Dùng cho |
|---|---|---|
| `raw_query` | str | hiển thị, đối chiếu |
| `normalized_query` | str | hiển thị, debug |
| `expanded_query` | str | debug retrieval |
| `retrieval_query` | str | debug (đã fold) |
| `sub_queries` | list/None | hiển thị router |
| `contexts` | list[str] | nội dung generator đã đọc |
| `sources` | list[dict] | Hit@K/MRR, hiển thị |
| `answer` | str | câu trả lời cuối |
| `labels` | dict/None | classifier |
| `retrieval_config` | dict/None | router đã áp |

Không có `gen_docs` trong dict (docstring cũ nhắc `gen_docs` nhưng code không trả). Nếu
cần debug “generator đọc chunk nào”, dùng `contexts`; nếu cần metadata, dùng
`sources[:effective_top_k]`.

---

## 4. `retrieve()`: những nhánh ẩn

`retrieve` (`:148–269`) không chỉ là một lời gọi ensemble. Nó có bốn nhánh:

1. **Hybrid bình thường**: gán trọng số per-query (hoặc trả về trọng số constructor nếu
   `config=None`), đồng bộ `k`, gán/xóa `filter` trên Chroma retriever, `invoke(fold(query))`.
2. **Fallback query**: nếu `fallback_query` khác query, chạy thêm một lần với câu gốc,
   gộp theo `chunk_id`: docs chính trước, docs fallback chưa trùng nối sau. **Không xếp
   lại theo điểm**; thứ tự này ảnh hưởng đến top-1 và do đó ảnh hưởng trích dẫn inject.
3. **Hậu lọc nguồn**: so khớp `fold(source)` với tập filter; nếu lọc sạch → giữ nguyên
   kết quả chưa lọc và in cảnh báo. Đây là “fail-open”, không phải fail-closed.
4. **Fallback vector thuần**: nếu hybrid lỗi hoặc `ensemble_retriever=None`, gọi
   `similarity_search(fold(query), k=k)`. Nhánh này **không áp trọng số, không áp filter,
   không chạy fallback query** — mọi cấu hình router bị bỏ qua. Nó cứu câu hỏi khỏi chết
   nhưng âm thầm đổi hành vi.

Một chi tiết concurrency: `retrieve` sửa `self.ensemble_retriever.weights` và `r.k` trên
đối tượng dùng chung. Hai request đồng thời có thể ghi đè cấu hình của nhau (một câu
SO_SANH và một câu THU_TUC chạy song song). CLI đơn luồng không gặp; Streamlit/API đa
luồng thì có. Chương 09 sẽ nhắc lại.

---

## 5. Cờ môi trường và thứ tự ưu tiên

### 5.1. Bảng cờ

| Cờ | Mặc định code | Ảnh hưởng | Ghi chú |
|---|---|---|---|
| `ENABLE_CLASSIFIER` | `0` | bật classifier + router | `.env.example` ghi 0 kèm comment “đang xây”, đã lỗi thời |
| `ENABLE_HYBRID_SEARCH` | `1` | `0` → vector thuần | BM25 không được dựng |
| `ENABLE_QUERY_EXPANSION` | `1` | `0` → không đồng nghĩa | |
| `BM25_WEIGHT` | `0.5` | trọng số RRF | env thắng tham số |
| `CHROMA_WEIGHT` | `0.5` | trọng số RRF | env thắng tham số |
| `RAG_TOP_K` | `4` (env example) / `6` (main fallback) | default `-k` của main | không ảnh hưởng evaluation |
| `USE_QWEN_GENERATOR` | `0` | main dùng Qwen thay Gemini | evaluation dùng cờ riêng |
| `GENERATION_CACHE` | `1` | cache câu trả lời | |
| `QWEN_FALLBACK` | `1` | Gemini lỗi → Qwen | |
| `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` | localhost, qwen2.5:1.5b, 90s | chuẩn hóa/classifier/fallback | |
| `CLASSIFIER_MODEL`, `CLASSIFIER_TIMEOUT` | trống → OLLAMA_MODEL; 20s | classifier | |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | vị trí DB | |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | **chỉ** tokenizer của benchmark chunking | `VectorStoreManager` hard-code bge-m3, không đọc cờ này |

### 5.2. Ba nguồn `top_k`

```
main.py -k / RAG_TOP_K  →  run(top_k=...)  →  base_config.top_k  →  router (+2 nếu SO_SANH)
```

- `pipeline.run` mặc định **4** nếu caller không truyền.
- `main.py` mặc định **6** nếu env không có `RAG_TOP_K`.
- `.env.example` đặt `RAG_TOP_K=4`; ai copy file này sẽ chạy 4, không phải 6.
- Evaluation truyền `top_k` tường minh (thường 6), nên không phụ thuộc hai mặc định trên.

Khi báo cáo, luôn ghi rõ “top_k hiệu dụng” và “retrieve_k”, đừng chỉ ghi “top_k=6”.

---

## 6. Ma trận suy giảm: hỏng ở đâu, ai bắt?

| Sự cố | Nơi xảy ra | Ai bắt | Hành vi | Người dùng thấy |
|---|---|---|---|---|
| Chroma rỗng | `main.build_pipeline` | `SystemExit` | in hướng dẫn chạy `ingest.py` | thoát |
| Ollama không chạy lúc khởi động | `check_connection` | không ném | cảnh báo, tiếp tục | câu hỏi dùng nguyên văn để truy xuất |
| Ollama lỗi khi chuẩn hóa | `normalize_user_query` | `except Exception` | trả câu gốc | không thấy lỗi, chỉ thấy câu chuẩn hóa = câu gốc |
| Classifier lỗi/timeout | `run` bước 2 | `except Exception` | bỏ nhãn/router | chạy cấu hình gốc, không có mục [2b] |
| BM25 dựng lỗi | `_init_hybrid_retriever` | `except Exception` | `ensemble=None` | cảnh báo log; Chroma thuần |
| Ensemble invoke lỗi | `retrieve` | `except Exception` | `similarity_search` | không filter/không trọng số |
| Filter loại hết | `retrieve` hậu lọc | kiểm tra rỗng | giữ kết quả chưa lọc | cảnh báo log; kết quả có thể sai nguồn |
| Subquery lỗi/tách <2 | `run` bước 7 | `except Exception` | đường đơn | không có mục sub-query |
| Gemini 429 phút | `_call_api` | retry 60s ×3 | chờ rồi thử lại | chậm; có thể vẫn lỗi |
| Gemini 429 PerDay | `_call_api` | break | `GeneratorError` marker | nếu fallback bật → Qwen; nếu không → lỗi |
| Qwen fallback lỗi | `_qwen_answer` | `GeneratorError` | báo cả hai lỗi | main in `[LỖI GEMINI]`, tiếp tục loop |
| Không có chunk | generator | kiểm tra `docs` rỗng | `REFUSAL_TEXT` | câu từ chối chuẩn |
| Câu hỏi rỗng | `run` | `ValueError` | ném | main in `[LỖI DỮ LIỆU]` |

Nguyên tắc chung: **lỗi ở tầng tối ưu thì suy giảm, lỗi ở tầng dữ liệu thì dừng**. Mất
BM25 vẫn trả lời được; mất Chroma thì không có gì để truy xuất; mất API key thì không
sinh được. Đây là thiết kế “degrade gracefully”, nhưng cũng là nguồn gốc của những lần
hệ thống chạy sai mà không báo rõ.

---

## 7. `main.py`: CLI và những chi tiết dễ bỏ qua

### 7.1. Luồng khởi động

`main()` (`main.py:240–251`):

1. `_force_utf8_stdout()` — console Windows mặc định cp1258, in tiếng Việt sẽ lỗi nếu
   không đổi sang UTF-8.
2. `parse_args()` — một tham số vị trí `query` (tùy chọn), `-k/--top-k`.
3. `build_pipeline(top_k)`:
   - `VectorStoreManager()` nạp bge-m3 (CPU);
   - `load_vector_store()` kết nối collection đã persist;
   - đếm `_collection.count()`; 0 → `SystemExit` với hướng dẫn;
   - `LocalSLM()` + `check_connection()`; lỗi → cảnh báo, vẫn tiếp tục;
   - generator: `USE_QWEN_GENERATOR=1` → `QwenGenerator`, ngược lại `GeminiGenerator`;
   - thiếu/sai key → `GeneratorError` → `SystemExit`.
4. Nếu có `query`: `ask_once` rồi `sys.exit(0 if ok else 1)`.
5. Không có: vòng lặp tương tác.

### 7.2. Những điểm không hoàn hảo

1. **Exit code sai khi lỗi một lần.** `ask_once` bắt `GeneratorError`, in lỗi, rồi
   `return True` (`:203–205`). `main` coi `True` là thành công → `sys.exit(0)`. Automation
   gọi `python main.py "..."` sẽ tưởng chạy thành công dù câu hỏi thất bại. Muốn đúng:
   trả `False` cho lỗi, hoặc trả enum `OK/ERROR/CANCELLED`. Đây là bài học về exit code
   trong CLI.
2. **Nhãn nguồn gây hiểu nhầm.** `print_result` in `len(sources)` (12/16) dưới tiêu đề
   “NGUỒN TRÍCH DẪN”, trong khi generator chỉ đọc `effective_top_k` (6/8). Nên in thêm
   “ứng viên truy xuất” và “ngữ cảnh đã dùng”.
3. **`build_pipeline(top_k)` không dùng `top_k`.** Tham số chỉ để in/không ảnh hưởng;
   `top_k` thực được truyền ở `ask_once`. Không phải bug, nhưng dễ gây nhầm khi đọc.
4. **Engine label dựa vào env, không dựa vào instance.** `print_result(..., offline=
   use_qwen_generator())`; nếu pipeline được dựng với generator khác mà env không đổi,
   nhãn có thể sai. Trong `main` bình thường hai thứ khớp.
5. **`LocalSLMError` gần như không bao giờ được ném** từ `pipeline.run`, vì
   `normalize_user_query` nuốt mọi lỗi. Khối `except LocalSLMError` trong `ask_once` là
   phòng thủ thừa nhưng vô hại.
6. **Khởi tạo `LocalSLM()` có thể ném `LocalSLMError` nếu host sai định dạng**; lời gọi
   này nằm ngoài `try` của `build_pipeline` → traceback thay vì thông báo thân thiện.

### 7.3. In kết quả

`print_result` (`:146–190`) in:

- câu gốc, câu chuẩn hóa;
- nếu có nhãn: chủ đề, loại câu, cấu hình router, danh sách sub-query;
- toàn bộ `sources` kèm rank, tier, chunk_id, số ký tự, preview;
- câu trả lời + nhãn engine (`Local Qwen — OFFLINE`, `Local Qwen — FALLBACK`, `Gemini`);
- thời gian và `len(sources)`.

Đây là công cụ debug rất tốt: nhìn `source` và `rank` để biết retrieval đúng hay sai;
nhìn `[2b]` để biết classifier/router có bật; nhìn nhãn engine để biết có fallback.

---

## 8. `scripts/learn.py`: “học” thật ra là gì?

### 8.1. Luồng

`scripts/learn.py` (`:80–135`):

1. Nạp Chroma; rỗng → `SystemExit`.
2. Dựng `LocalSLM` + `HybridRAGPipeline` với `GeminiGenerator`.
3. Hỏi từng câu, in câu chuẩn hóa + câu trả lời.
4. Hỏi người dùng “Đáp án đúng chưa? [Enter/y = đúng, n = sai]”.
5. Nếu `n`: đọc phần chỉnh sửa (mỗi dòng một ý, dòng trống kết thúc).
6. `append_note(question, correction)` ghi vào `data/corpus/ghi_chu_hoc_them.txt` dưới
   dạng:

```
Điều 1001. Ghi chú học thêm ngày 2026-10-23 14:30
Câu hỏi: ...
Nội dung chính xác: ...
```

7. `run_ingestion(db_manager, reset=False)` quét lại **toàn bộ** corpus, chunk lại, nhúng
   lại, xóa collection cũ và tạo mới (không xóa thư mục, tái dùng bge-m3).
8. Gán `pipeline.vector_db = vector_db` mới; ghi log CSV; in số chunk trước/sau.

Đây không phải fine-tune, không phải RAG “học” bằng gradient; nó là **ghi chú vào corpus
rồi rebuild index**. Tên “learn” dễ gây hiểu nhầm khi bảo vệ; nên gọi đúng là
“human-in-the-loop corpus update”.

### 8.2. Ba vấn đề cần biết

**Vấn đề 1 — retriever đang chạy không được dựng lại.** Sau bước 7, code chỉ gán
`pipeline.vector_db = vector_db`. `pipeline.ensemble_retriever` vẫn là đối tượng dựng từ
**trước** khi học: BM25 giữ danh sách chunk cũ trong bộ nhớ; Chroma retriever giữ handle
cũ. Vì vậy câu hỏi tiếp theo trong cùng phiên có thể **không thấy bài học mới**, đặc biệt
ở nhánh BM25. Lời nhắc “Hỏi lại câu đó để kiểm chứng kiến thức mới” vì thế không đáng
tin cậy. Cách sửa tối thiểu: sau khi có `vector_db` mới, đặt
`pipeline.ensemble_retriever = None` rồi gọi `pipeline._init_hybrid_retriever()` (hoặc
dựng lại pipeline). Đây là bug thật, nên đưa vào phần hạn chế của báo cáo.

**Vấn đề 2 — không có kiểm chứng nội dung người dùng dán.** Bất kỳ ai cũng có thể nhập
một “đáp án đúng” sai hoặc chứa chỉ dẫn độc hại; nó được ghi thẳng vào corpus. Không có
bước xác nhận, không có nguồn, không có rollback. Đây là lỗ hổng poisoning ở mức quy
trình, không phải code. Muốn an toàn: yêu cầu dẫn nguồn/điều khoản, hiển thị diff trước
khi ghi, lưu bản nháp, hoặc chỉ cho phép người có quyền.

**Vấn đề 3 — rebuild toàn bộ mỗi lần sửa một câu.** `run_ingestion(reset=False)` vẫn xóa
collection và nhúng lại toàn bộ 361 chunk; với bge-m3 CPU, mỗi lần học tốn thời gian và
điện. Chưa kể `chunk_id` được đánh lại từ 0, làm cache theo prompt (nếu có) miss và log
so sánh chunk trước/sau khó hiểu. Với đồ án, chấp nhận được; với hệ thống thật, cần
incremental indexing.

Ngoài ra: `scripts/learn.py` cố định `top_k=4` (`:108`), không đọc `RAG_TOP_K`/`-k`; luôn dùng
`GeminiGenerator` (không tôn trọng `USE_QWEN_GENERATOR`), nên chạy offline sẽ tốn quota
hoặc phải chờ fallback. `read_correction()` không bắt `EOFError`/`KeyboardInterrupt` —
Ctrl+C giữa lúc dán sẽ thoát bằng traceback.

---

## 9. Năm ca truy vết

### Ca 1 — chạy mặc định, classifier tắt

```
python main.py -k 6 "Sinh viên được học lại tối đa mấy lần?"
```

1. `top_k=6`; `effective_top_k=6`; `retrieve_k=12`.
2. Không classifier → `labels=None`, `config=None`.
3. Qwen chuẩn hóa → “Sinh viên được đăng ký học lại tối đa bao nhiêu lần cho mỗi học
   phần không đạt?”
4. Mở rộng đồng nghĩa (nếu bật) → câu dài hơn.
5. `retrieve(expanded, k=12, fallback_query=raw, config=None)`; BM25+Chroma, trọng số
   0.5/0.5.
6. `gen_docs` = 6 chunk đầu; `sources` = 12.
7. Gemini sinh; inject top-1; in kết quả.

Nếu top-1 là chunk quy chế đào tạo, câu trả lời có `(Điều 15, Khoản 2 — ...)`; nếu top-1
là chunk học phí, câu trả lời vẫn đúng nhưng bị gắn thêm trích dẫn sai (chương 06).

### Ca 2 — classifier bật, câu SO_SANH

```
ENABLE_CLASSIFIER=1 python main.py "So sánh chuẩn đầu ra ELO 6 và ELO 7 ngành CNTT"
```

1. Classifier → `{topic: "chương trình đào tạo", question_type: "SO_SANH"}`.
2. Router → `top_k=8`, trọng số 0.5/0.5, filter file CTĐT, `enable_subquery=True`.
3. `retrieve_k=16`; tách 2 sub-query; mỗi nhánh lấy 16; gộp cắt 16.
4. Generator nhận 8 chunk; prompt có phụ lục bảng so sánh.
5. `sources` 16, `contexts` 8.

Nếu classifier gán nhầm SO_SANH cho một câu tra cứu, subquery có thể tách sai; guardrail
trong `split_comparison_query` sẽ trả `[query]` nếu tách dở, pipeline chạy đường đơn.

### Ca 3 — Ollama chết lúc khởi động

1. `check_connection` trả `False`, in cảnh báo; pipeline vẫn dựng.
2. Câu hỏi đầu tiên: `normalize_user_query` gọi `LocalSLM.generate` → lỗi → bắt → trả
   câu gốc.
3. Retrieval dùng câu gốc; generator vẫn chạy (Gemini).
4. Nếu generator là Qwen (`USE_QWEN_GENERATOR=1`), `QwenGenerator.generate_answer` ném
   `GeneratorError`; main in lỗi; loop tiếp tục.

Điều đáng nói: hệ thống không “chết vì Ollama”, nhưng chất lượng chuẩn hóa giảm âm thầm.
Log chỉ có một dòng cảnh báo; người dùng không thấy.

### Ca 4 — filter loại hết kết quả

1. Router đặt `source_filter=["file-khong-ton-tai.pdf"]`.
2. Chroma `$in` → 0; BM25 vẫn trả 12 chunk ngoài nguồn.
3. RRF gộp; hậu lọc theo `fold(source)` → rỗng.
4. Code giữ nguyên kết quả **chưa lọc** và in cảnh báo.
5. Generator nhận 6 chunk có thể sai chủ đề; câu trả lời có thể từ chối hoặc bịa.

Đây là “fail-open”: câu hỏi không chết, nhưng lọc coi như không tồn tại. Với đánh giá, ca
này làm Hit@K giảm mà không có lỗi rõ ràng; cần log/alert.

### Ca 5 — Gemini PerDay, fallback Qwen

1. `_call_api` gặp 429 PerDay → break ngay → `GeneratorError` có marker `PerDay`.
2. `QWEN_FALLBACK=1` → `_qwen_answer` dựng prompt gọn, gọi Ollama.
3. Trả `[Cảnh báo: Gemini đã hết quota — ...]` + câu trả lời; **không cache, không
   inject**.
4. Main in nhãn `Local Qwen — FALLBACK`.
5. Lần hỏi sau lặp lại từ đầu; nếu vẫn PerDay, lại fallback (không chờ 60s vì PerDay
   break ngay).

Nếu Qwen cũng chết: `GeneratorError` gồm hai lỗi; main in `[LỖI GEMINI]`, không thoát
loop. Với một lần hỏi (`python main.py "..."`), exit code vẫn 0 do bug ở mục 7.2.

---

## 10. Cách kiểm thử pipeline mà không tốn quota

Viết test với fake, không gọi model thật:

```python
class FakeDoc:
    def __init__(self, text, source, chunk_id):
        self.page_content = text
        self.metadata = {"source": source, "tier": "1", "chunk_id": chunk_id}

class FakeVectorDB:
    def get(self):  # để pipeline coi là Chroma hợp lệ
        return {"documents": [], "metadatas": []}
    def similarity_search(self, q, k=4):
        return [FakeDoc("Điều 15. ...", "qcdt.pdf", 1)][:k]

class FakeSLM:
    def generate(self, prompt, temperature=0.0):
        return "câu chuẩn hóa?"

class FakeGenerator:
    def generate_answer(self, query, retrieved_docs, question_type=None):
        return "câu trả lời"
```

Kiểm tra:

- `pipeline.run("...", top_k=6)` trả `sources` 12, `contexts` 6 khi có 12 docs giả;
- khi `FakeVectorDB.similarity_search` chỉ trả 3, `contexts` 3, `sources` 3;
- khi `FakeGenerator` ném `GeneratorError`, `run` ném ra ngoài (pipeline không nuốt lỗi
  sinh — đúng thiết kế);
- khi classifier tắt, `labels is None`.

Không cần chạy `main.py` hay `evaluation.py` để kiểm tra các hợp đồng này.

---

## 11. Bài tập chương

**A. Đếm cửa sổ.** `main.py -k 6`, `ENABLE_CLASSIFIER=1`, câu được gán `SO_SANH` và
`topic="chương trình đào tạo"`. Cho biết `effective_top_k`, `retrieve_k`, số chunk
generator đọc, số phần tử `sources`, và số chunk tối đa mà `print_result` liệt kê.

**B. Hai mặc định `top_k`.** Vì sao chạy `python main.py "..."` có thể dùng 6, còn
`pipeline.run("...")` không truyền `top_k` lại dùng 4? Nếu copy `.env.example` thì con số
nào? Evaluation có bị ảnh hưởng không?

**C. Ollama chết.** Mô tả ba tầng bị ảnh hưởng khi Ollama không chạy: chuẩn hóa,
classifier, generator Qwen. Tầng nào làm câu hỏi chết, tầng nào chỉ làm giảm chất lượng?
Vì sao `main.py` vẫn chạy được?

**D. Filter rỗng.** Truy vết khi `source_filter` không khớp file nào. Vì sao code giữ
kết quả chưa lọc? Nếu bạn muốn fail-closed (trả từ chối thay vì kết quả sai), sửa ở đâu
và hệ quả với Hit@K là gì?

**E. Learn mode.** Sau khi người dùng nhập đáp án đúng và `scripts/learn.py` rebuild xong, vì sao
câu hỏi tiếp theo có thể vẫn trả lời theo kiến thức cũ? Chỉ ra đối tượng chưa được cập
nhật và viết ba dòng code sửa.

**F. Exit code.** Một pipeline automation chạy `python main.py "câu hỏi"` và kiểm tra
`$?`. Khi Gemini hết quota và Qwen fallback cũng chết, `$?` là bao nhiêu? Vì sao? Đề xuất
cách sửa và một test.

<details>
<summary>Đáp án gợi ý</summary>

**A.** `effective_top_k = 6 + 2 = 8`; `retrieve_k = 8 × 2 = 16`; generator đọc 8 chunk;
`sources` có 16 phần tử; `print_result` liệt kê tối đa 16 (vì lặp toàn bộ `sources`).
`contexts` có 8. Đừng nhầm “Top-6” ở dòng tiến trình với 16 chunk thực truy xuất.

**B.** `main.py` lấy default `-k` từ `os.getenv("RAG_TOP_K", str(DEFAULT_TOP_K))` với
`DEFAULT_TOP_K=6` (`main.py:33,59–61`). `pipeline.run` có default `top_k=4`
(`pipeline.py:298`). Nếu copy `.env.example`, `RAG_TOP_K=4` → main cũng dùng 4. Evaluation
truyền `top_k` tường minh (thường 6) nên không phụ thuộc hai default này; nhưng nếu
evaluation đọc env `RAG_TOP_K` thì cần kiểm tra implementation chương 08.

**C.** (1) Chuẩn hóa: `normalize_user_query` bắt exception, trả câu gốc → giảm chất lượng
truy xuất nhưng không chết. (2) Classifier: `classify_query` có fallback 3 tầng (LLM →
keyword → default), nên vẫn trả nhãn; nếu timeout, router lùi cấu hình gốc. (3)
`QwenGenerator` (nếu chọn) ném `GeneratorError` → câu hỏi đó thất bại; `GeminiGenerator`
vẫn chạy nếu Gemini sống; fallback Qwen cũng chết nếu Ollama chết. `main.py` vẫn chạy vì
chuẩn hóa và classifier đều suy giảm mềm; chỉ generator Qwen trực tiếp mới làm câu hỏi
lỗi, và main bắt lỗi rồi tiếp tục loop.

**D.** Chroma trả 0 do filter; BM25 trả 12 ngoài nguồn; sau RRF, hậu lọc `fold(source)`
loại tất cả. Code kiểm tra `if filtered_docs:` — rỗng thì giữ `docs` gốc và in cảnh báo
(`pipeline.py:247–260`). Đây là fail-open để câu hỏi không chết. Muốn fail-closed: thay
nhánh rỗng bằng `return []` hoặc ném lỗi cấu hình; khi đó generator nhận rỗng → trả
`REFUSAL_TEXT`; Hit@K của các câu bị lọc oan sẽ về 0 (trung thực hơn so với việc âm thầm
dùng kết quả sai nguồn), nhưng false refusal tăng. Cần đo cả hai.

**E.** `scripts/learn.py` chỉ gán `pipeline.vector_db = vector_db` (`:131`), không cập nhật
`pipeline.ensemble_retriever`. BM25 retriever vẫn giữ danh sách tài liệu cũ; Chroma
retriever vẫn là handle cũ. Vì vậy bài học mới không được truy xuất (hoặc chỉ được qua
nhánh Chroma nếu handle tình cờ trỏ sang collection mới). Sửa:

```python
pipeline.vector_db = vector_db
pipeline.ensemble_retriever = None
pipeline._init_hybrid_retriever()
```

Ba dòng này dựng lại BM25 từ collection mới. Nên thêm test: sau khi thêm một file fake,
`pipeline.retrieve("từ khóa mới", k=4)` phải trả chunk từ file mới.

**F.** `$?` = 0. `ask_once` bắt `GeneratorError`, in `[LỖI GEMINI]`, rồi `return True`
(`main.py:203–205`); `main` gọi `sys.exit(0 if ok else 1)` (`:248–249`), nên `True` →
exit 0. Đây là bug automation: lỗi bị báo thành công. Sửa: `return False` trong các nhánh
lỗi (hoặc trả `"error"`), giữ `True` chỉ khi có kết quả; test bằng cách inject một
generator luôn ném `GeneratorError`, chạy `main` với query và assert exit code 1.

</details>

---

## 12. Tóm tắt chương

1. `HybridRAGPipeline` là vật chứa duy nhất: vector_db + local_slm + generator +
   ensemble retriever. Constructor đọc env và có thể ghi đè tham số.
2. `run()` có chín bước: validate → classifier/router → oversampling → normalize →
   expand → fold → subquery → retrieve + cắt cửa sổ → generate.
3. **Cửa sổ truy xuất (`retrieve_k`) khác cửa sổ sinh (`effective_top_k`)**: mặc định
   12/6; SO_SANH 16/8; `sources` chứa cả 12/16, generator chỉ đọc 6/8.
4. `retrieve()` có bốn nhánh: hybrid, fallback query, hậu lọc, vector thuần. Nhánh vector
   thuần bỏ qua toàn bộ trọng số/filter của router.
5. Fail-open ở filter nguồn: lọc sạch thì giữ kết quả chưa lọc, chỉ cảnh báo.
6. `main.py` mặc định 6 chunk (nếu env không có), `pipeline.run` mặc định 4;
   `.env.example` đặt 4; evaluation truyền tường minh.
7. `main.py` in 12/16 nguồn dưới nhãn “nguồn trích dẫn” — đó là ứng viên, không phải ngữ
   cảnh đã dùng.
8. Lỗi một lần trong `main.py` vẫn trả exit code 0 — bug cần sửa nếu dùng automation.
9. `scripts/learn.py` không fine-tune; nó ghi chú vào corpus rồi rebuild. Sau rebuild, retriever
   đang chạy **không** được dựng lại — câu hỏi tiếp theo có thể không thấy bài học mới.

Tiếp theo: [08 — Đánh giá và thực nghiệm](08_danh_gia.md).
