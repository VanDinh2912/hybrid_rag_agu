# Chương 09 — Ứng dụng giao diện và thực nghiệm chunking

> **Mục tiêu chương:** hiểu `ui/demo_streamlit.py` như một **lớp trình bày** tái sử dụng
> nguyên vẹn backend; đọc được luồng dữ liệu từ sidebar → index → pipeline → 3 tab; phân
> biệt live và replay, biết cache nào đang giữ gì; đọc đúng kết quả thực nghiệm 3 chiến
> lược chunking và giải thích vì sao “structure-aware không thắng Hit@3”; cuối chương có
> một bản handoff tự chứa cho team frontend.

Chương này không dạy viết Streamlit từ đầu. Nó dạy **hợp đồng** giữa UI và backend: UI
được phép gọi gì, được phép hiển thị gì, không được tự tính lại logic gì. Với một đồ án
RAG, sai lầm phổ biến là UI tự chunk, tự truy xuất, tự chấm điểm — khi đó kết quả demo
không còn là kết quả của pipeline đã đánh giá.

---

## 1. Vị trí của app trong đồ án

`ui/demo_streamlit.py` (1.217 dòng) mở đầu bằng một tuyên bố kiến trúc:

> “App CHỈ là lớp trình bày: toàn bộ chunking / truy xuất hybrid / sinh chữ / chấm điểm
> được TÁI SỬ DỤNG từ `src/` — KHÔNG cài lại bất kỳ logic backend nào.”

Cụ thể app import:

| Từ `src/` | Dùng để |
|---|---|
| `chunking.chunk_with_strategy`, `get_token_counter` | Cắt corpus theo 3 chiến lược |
| `loader.DocumentLoader` | Nạp corpus + OCR cache |
| `vector_db.VectorStoreManager` | bge-m3 + ChromaDB |
| `pipeline.HybridRAGPipeline` | Chuẩn hóa → classify/router → retrieve → generate |
| `generator.GeminiGenerator`, `QwenGenerator` | Sinh câu trả lời |
| `local_slm.LocalSLM` | Kiểm tra Ollama + chuẩn hóa |
| `evaluation.*` | `source_match`, `citation_scores`, `extract_citations`, `judge_faithfulness`, `number_support` |

App **không** import `router`, `classifier`, `retrieval` trực tiếp. Nó chỉ bật/tắt
`ENABLE_CLASSIFIER` quanh lúc dựng pipeline (`build_demo_pipeline`, `:381–396`), để
pipeline tự quyết định. Đây là cách đúng: UI không gọi classifier, không tự chọn top_k
theo nhãn, không tự lọc nguồn.

---

## 2. Kiến trúc app

### 2.1. Luồng một lượt chạy

```
render_sidebar()  ──► generator, top_k, classifier, judge, replay, weights
        │
render_input()    ──► query + question (benchmark) | None (tự do)
        │
   [🚀 Chạy Đánh Giá RAG]
        │
run_evaluation()  ──► evaluate_rag_strategies()
        │                   │
        │                   ├─ strategy fixed     → replay? live?
        │                   ├─ strategy recursive → replay? live?
        │                   └─ strategy structure → replay? live?
        │
        ├─ st.session_state["demo_run"]
        └─ 3 tab: winner / comparison / chunks
```

`evaluate_rag_strategies` (`:615–688`) là **hàm backend trung tâm** của app. Nó chạy tuần
tự 3 chiến lược, bắt lỗi từng chiến lược, gọi callback `on_strategy_start/done` để UI vẽ
`st.status` và `st.progress`, rồi tính composite **ngoài cache**. Một chiến lược chết
không làm chết 2 chiến lược còn lại (`error_result`, `:592–609`).

### 2.2. Ba tầng cache

| Cache | Hàm | Khóa | Giữ gì |
|---|---|---|---|
| `@st.cache_resource` | `get_tokenizer` | không tham số | Tokenizer bge-m3 |
| `@st.cache_resource` | `get_corpus` | không tham số | Toàn bộ document đã OCR |
| `@st.cache_resource` | `get_local_slm` | không tham số | LocalSLM/Ollama client |
| `@st.cache_resource` | `get_generator` | `generator_label` | Một generator cho mỗi loại |
| `@st.cache_resource` | `get_judge_model` | không tham số | Gemini judge |
| `@st.cache_resource` | `get_index_registry` | không tham số | 3 Chroma index + bge-m3 |
| `@st.cache_data` | `load_benchmark_questions` | file mtime/params | 50 câu benchmark |
| `@st.cache_data` | `load_replay_payload` | file | `results_all.json` |
| `@st.cache_data` | `evaluate_strategy_live` | `(strategy, query, top_k, generator_label, use_judge, question, use_classifier)` | Kết quả một chiến lược |

Hai điểm thiết kế đáng học:

- **Composite không nằm trong cache.** Đổi trọng số ở sidebar chỉ tính lại công thức, không
  chạy lại pipeline. Đây là lý do `evaluate_strategy_live` không nhận `weights`.
- **`use_judge` nằm trong cache key**, vì bật judge làm thay đổi kết quả và tốn quota.
  `use_classifier` cũng nằm trong key. Nhưng `allow_replay` không nằm trong key của live;
  nó chỉ quyết định có thử replay trước hay không.

### 2.3. `DemoIndexRegistry`

`DemoIndexRegistry` (`:159–234`) quản lý 3 ChromaDB vật lý:

```
logs/benchmark/chroma_fixed/
logs/benchmark/chroma_recursive/
logs/benchmark/chroma_structure/
```

Thứ tự tìm index:

1. `logs/benchmark/chroma_<strategy>/` — sản phẩm của `scripts/benchmark_chunking.py`;
2. `benchmark_logs/chroma_<strategy>/` — vị trí cũ;
3. `logs/demo_chroma_<strategy>/` — app tự dựng trước đó;
4. nếu không có: dựng mới từ `data/corpus` (OCR đã cache), ghi vào `logs/demo_chroma_*`.

Chỉ cần `chroma.sqlite3` tồn tại là app thử nạp; nếu collection rỗng thì raise. Điều này
đúng: một thư mục index rỗng không được coi là “đã có index”.

`VectorStoreManager` được tái sử dụng bằng cách đổi `persist_directory` trước mỗi lần
`load_vector_store`/`create_vector_store`. bge-m3 chỉ nạp một lần, nên so sánh 3 chiến
lược không phải nạp lại model 3 lần — công bằng về thời gian nhúng, nhưng **không** công
bằng về số chunk.

---

## 3. Live và replay

### 3.1. Replay là gì

`load_replay_payload` đọc `logs/benchmark/results_all.json`; `find_replay_entry` tìm entry
khớp **chính xác** `raw_query`, `top_k` và họ generator (qwen/gemini). Nếu khớp, app dùng
lại answer/metrics đã đo, không gọi generator.

Replay rất hữu ích khi demo trước hội đồng: không phụ thuộc Ollama, không tốn quota, thời
gian tải tức thì. Nhưng nó có ba giới hạn phải nói:

1. **Không có `contexts`** trong `results_all.json`, nên không thể chấm lại Faithfulness.
   App hiển thị `—`, không bịa số (`replay_entry_to_result`, `:502–556`).
2. **Không khớp `use_classifier` và `use_judge`.** `find_replay_entry` chỉ so query,
   `top_k`, generator. Nếu sidebar bật classifier nhưng entry replay được đo khi tắt
   classifier, app vẫn dùng entry đó. `labels` có thể `None`; bảng vẫn hiển thị như cùng
   cấu hình. Đây là lỗi cần sửa: thêm `use_classifier` vào điều kiện khớp, hoặc ghi rõ
   “replay từ cấu hình không classifier”.
3. **Không có Faithfulness**, nên Composite replay chỉ còn Hit@K + Citation F1; trọng số
   được chuẩn hóa lại. Không được so Composite replay với Composite live có đủ 3 thành
   phần.

### 3.2. Live

`evaluate_strategy_live` (`:399–499`):

1. Lấy index theo strategy.
2. Dựng generator; nếu lỗi → raise để caller bắt.
3. Dựng pipeline với `oversample_factor=2`, `use_hybrid=True`, classifier theo sidebar.
4. `pipeline.run(query, top_k=top_k)` — **đúng**, không truyền `retrieve_k` như
   `evaluation.py`.
5. Đo `latency_ms` quanh `run`.
6. Tính Hit/MRR/Citation; Faithfulness = judge nếu bật, ngược lại `number_support` proxy.
7. Trả khung kết quả chung.

Điểm đáng khen: app gọi `citation_scores(expected, predicted)` **không truyền**
`source_document`, kèm comment cảnh báo nhánh rút gọn chấm 1.0 cho câu không trích dẫn
(`:450–452`). Đây là cùng lỗi đã phân tích ở chương 08, nhưng app đã tránh. Bài học: một
hàm có nhánh nguy hiểm thì mọi call site phải được rà; `scripts/benchmark_chunking.py` cũng tránh
(`:380–383`), chỉ `evaluation.py` còn dính.

### 3.3. Chế độ câu tự do

Khi không chọn câu benchmark:

- không có `source_document` → Hit/MRR/Citation/Composite = `—`;
- Faithfulness = `number_support` (proxy), hoặc judge nếu bật;
- winner chọn theo Faithfulness proxy, sau đó Latency (`pick_winner`, `:366–375`).

Đây là hành vi hợp lý: không có ground truth thì không được bịa Hit. Nhưng cần nói rõ:
“winner” trong chế độ tự do chỉ là **proxy**, không phải kết luận khoa học.

---

## 4. Composite và cách chọn winner

### 4.1. Công thức

`compute_composite` (`:307–330`):

```
Composite = (w_hit × Hit@K + w_faith × Faithfulness + w_cit × Citation_F1)
            / (tổng trọng số của các thành phần CÓ giá trị)
```

Mặc định `(0.4, 0.3, 0.3)`. Nếu Faithfulness `None` (replay), chỉ còn Hit và Citation,
trọng số chuẩn hóa lại thành 0.4/0.7 và 0.3/0.7. Nếu tất cả đều `None` → `None`.

Thiết kế “chuẩn hóa theo thành phần khả dụng” tránh bịa số 0, nhưng tạo ra một cái bẫy:
**Composite giữa các lượt thiếu thành phần khác nhau không so sánh được**. Một chiến lược
có Faithfulness 0.9 (live) và một chiến lược replay chỉ có Hit/Citation có thể đổi thứ
hạng khi trọng số đổi. UI có caption giải thích, nhưng người xem dễ bỏ qua.

### 4.2. Vì sao `fixed` thắng trong demo replay

Với kết quả 50 câu (top_k=3), `fixed` có Hit@3 0.88, Citation F1 0.0; `structure` có
Hit@3 0.76, Citation F1 0.0767. Composite replay (Faithfulness `None`):

| Chiến lược | Hit@3 | Citation F1 | Composite (0.4/0.3, chuẩn hóa) |
|---|---:|---:|---:|
| fixed | 0.8800 | 0.0000 | (0.4×0.88 + 0.3×0)/0.7 = **0.5029** |
| recursive | 0.7400 | 0.0067 | (0.4×0.74 + 0.3×0.0067)/0.7 = **0.4257** |
| structure | 0.7600 | 0.0767 | (0.4×0.76 + 0.3×0.0767)/0.7 = **0.4672** |

`fixed` thắng vì Hit@3 cao hơn 12 điểm và Citation gần như bằng 0 ở cả ba. Nếu đổi trọng
số Hit xuống 0.2, Citation lên 0.5, Faithfulness 0.3 (không có trong replay), thứ hạng có
thể đổi. Đây là lý do phải công bố trọng số trước khi demo, không chỉnh sau khi thấy kết
quả.

Điểm yếu của composite: **không có MRR**. `structure` thắng MRR (0.7160 so với 0.6983)
nhưng lợi thế này không được thưởng. Nếu mục tiêu là “chunk đúng nằm càng sớm càng tốt”,
composite hiện tại không phản ánh. Cần thêm MRR hoặc dùng Hit@1 nếu muốn.

### 4.3. `pick_winner`

- Có ground truth: chọn Composite cao nhất; nếu không có Composite, lùi về tuple
  `(Hit, MRR, Citation)`; cuối cùng là latency thấp nhất.
- Câu tự do: chọn Faithfulness cao nhất; nếu không có, latency thấp nhất.

Trong chế độ replay + câu tự do, Faithfulness luôn `None`, nên winner = chiến lược chạy
nhanh nhất theo latency đã lưu. Đó **không phải** chiến lược tốt nhất. UI nên cảnh báo
hoặc tắt chọn winner khi replay ở chế độ tự do.

---

## 5. Ba tab

### 5.1. Tab 1 — Câu trả lời tối ưu

Hiển thị:

- Composite, Hit@K, Faithfulness, Citation F1 (4 `st.metric`);
- khối phân loại: nhãn topic/type, cấu hình router, sub-query (`format_classification_lines`);
- câu trả lời; nếu là refusal → `st.warning` giải thích Soft Refusal;
- trích dẫn hệ thống sinh ra;
- top-K nguồn đưa vào generator (không phải toàn bộ recall window);
- nếu replay: ghi rõ mốc thời gian.

Điểm cần sửa: `render_tab_winner` hiển thị `sources[:top_k]` nhưng không đánh dấu source
nào thực sự nằm trong `contexts` nếu router đổi cửa sổ (SO_SANH +2). Trong live, `sources`
có thể nhiều hơn `top_k`; tab 3 mới là nơi soi đầy đủ.

### 5.2. Tab 2 — Bảng so sánh

Cột: Composite, Hit@K, MRR, Faithfulness, Citation P/R/F1, Latency, số chunk. Dòng winner
được tô xanh. Caption giải thích khi Faithfulness thiếu hoặc khi trộn replay/live.

Điểm cần sửa: bảng không hiển thị `n` của từng chỉ số; Citation F1 có thể `None` với câu
không có Điều/Khoản; Hit@K có thể `None` với câu tự do. Người xem dễ hiểu `—` là 0.

### 5.3. Tab 3 — Chi tiết đoạn truy xuất

Ba cột, mỗi chiến lược liệt kê từng source:

- `#rank`, tên file, tier, chunk_id;
- dấu ✓ nếu đúng `source_document`;
- 🅖 nếu `fed_to_generator` (rank ≤ top_k);
- expander hiển thị `contexts[rank-1]` nếu live, preview nếu replay.

Đây là tab quan trọng nhất để thuyết phục hội đồng: nhìn được chunk đúng nằm ở rank nào,
chunk nào được đưa vào generator, chunk nào bị cắt. Nó cũng cho thấy oversampling: source
rank 4–6 vẫn nằm trong recall window nhưng không được sinh.

---

## 6. Thực nghiệm 3 chiến lược chunking

### 6.1. Thiết kế

`scripts/benchmark_chunking.py` (1.051 dòng) so sánh:

| Mã | Chiến lược | Cách cắt | Overlap |
|---|---|---|---|
| `fixed` | Fixed-size | Cắt cứng 512 token | 0 |
| `recursive` | Recursive | `\n\n` → `\n` → câu → từ, 512 token | 0 |
| `structure` | Structure-aware | Theo Điều/Khoản/Điểm, tiền tố metadata phân cấp, khóa bảng Markdown | không dùng |

Tham số chung: benchmark 50 câu, `top_k=3` (generator), `retrieve_k=6` (oversample ×2),
`max_tokens=512`, `overlap=0`, tokenizer HuggingFace của bge-m3, generator Qwen 2.5 1.5B
local, temperature 0, cache bật, device CPU.

Mỗi chiến lược có ChromaDB riêng (`logs/benchmark/chroma_<strategy>`), collection riêng
(`bench_<strategy>`), 50 câu chạy trên cùng corpus/benchmark. `build_index` xóa index cũ
và kiểm tra `stored == len(chunks)`; nếu lệch → `SystemExit`, không chấm trên index sai.
Đây là mức kỷ luật cần có khi so sánh.

### 6.2. Kết quả

Nguồn: `logs/benchmark/results_all.json` và `summary_comparison_report.md`.

| Chỉ số | fixed | recursive | structure |
|---|---:|---:|---:|
| Số chunk | 182 | 189 | **378** |
| Mean chunk tokens | 484.4 | 466.6 | 269.4 |
| Max chunk tokens | 512 | 512 | 511 |
| Index size (MB) | 4.24 | 4.49 | **5.93** |
| Hit@3 | **0.8800** | 0.7400 | 0.7600 |
| Hit@5 | 0.9000 | 0.8800 | 0.8800 |
| Hit@6 | 0.9000 | 0.9000 | **0.9200** |
| MRR | 0.6983 | 0.6687 | **0.7160** |
| Citation P | 0.0000 | 0.0050 | **0.0990** |
| Citation R | 0.0000 | 0.0100 | **0.0800** |
| Citation F1 | 0.0000 | 0.0067 | **0.0767** |
| Citation EM | 0.5400 | **0.6000** | 0.5400 |
| Latency (ms/câu) | 13.010 | 13.121 | 13.253 |
| Tổng thời gian | 860.7s | 866.7s | 923.1s |
| Số câu OK | 50/50 | 50/50 | 50/50 |
| Refusal rate | 0.0 | 0.0 | 0.0 (⚠️ xem 6.5) |

### 6.3. Đọc kết quả đúng

**Fixed thắng Hit@3, structure thắng MRR/Hit@6/Citation.** Không có chiến lược thắng mọi
chỉ số. Giải thích:

- Fixed có 182 chunk, mỗi chunk trung bình 484 token. Một chunk lớn chứa nhiều nội dung,
  nên xác suất “một chunk thuộc đúng file” nằm trong top 3 cao. Nhưng chunk lớn có thể
  chứa nhiều điều không liên quan, làm loãng ngữ cảnh generator.
- Structure có 378 chunk, trung bình 269 token. Chunk nhỏ, tách theo Điều/Khoản, nên
  chunk đúng thường “tinh” hơn, nhưng top 3 chỉ lấy được 3 mẩu nhỏ; Hit@3 giảm, trong khi
  MRR tăng vì chunk đúng thường đứng sớm hơn khi nó xuất hiện.
- Citation của structure cao hơn hẳn vì chunk giữ tiền tố “Điều/Khoản”, generator dễ
  trích đúng; fixed/recursive cắt giữa điều nên mất ngữ cảnh.
- Index structure lớn hơn 40% và tốn thêm ~60s tổng; latency mỗi câu gần như nhau vì phần
  lớn thời gian là Qwen sinh chữ, không phải retrieval.

Đây là bài học “**không có bữa trưa miễn phí**”: chunk nhỏ giúp precision/MRR/citation,
chunk lớn giúp recall top-K. Chọn theo mục tiêu: nếu generator yếu và cần ít ngữ cảnh,
structure; nếu ưu tiên chắc chắn có tài liệu đúng trong top 3, fixed.

### 6.4. Vì sao số chunk khác chương 02

Chương 02 nói production có **361 chunk** (Tầng 1 = 234, Tầng 2 = 50, bổ sung = 77). Thực
nghiệm này ra **378 chunk** cho structure. Không mâu thuẫn:

- production dùng `DocumentChunker` với cấu hình mặc định, cắt theo Điều/Khoản và có thể
  gộp/tách khác;
- benchmark dùng `chunk_with_strategy("structure", ..., max_tokens=512, overlap=0)` và
  tokenizer bge-m3, nên ranh giới chunk khác;
- fixed/recursive có 182/189 chunk vì 512 token/chunk.

Khi báo cáo, phải nói rõ “378 chunk của cấu hình benchmark 512 token”, không được gán cho
production 361.

### 6.5. Ba cảnh báo của thực nghiệm này

1. **`refusal_rate = 0.0` không đáng tin.** `scripts/benchmark_chunking.py:413` dùng
   `REFUSAL_MARKER in fold(answer)`: marker có dấu, `fold(answer)` bỏ dấu → không bao giờ
   khớp. Đây đúng là lỗi P4.1 đã sửa trong `evaluation.py` nhưng còn sót ở đây. Muốn đo
   đúng phải `fold(REFUSAL_MARKER) in fold(answer)`. Vì vậy không được nói “3 chiến lược
   không từ chối câu nào”.
2. **Không đo Faithfulness.** `results_all.json` không lưu contexts và không có judge;
   aggregate không có `faithfulness`. UI replay hiển thị `—`. Không được suy ra “cả 3
   trung thực như nhau”.
3. **Citation F1 thấp không chỉ do chunking.** Qwen 1.5B hiếm khi viết “Điều/Khoản”; 50
   câu benchmark có thể có ít Điều/Khoản; `citation_scores` không dùng shortcut (đúng).
   Vì vậy 0.0/0.0067/0.0767 là so sánh tương đối, không phải chất lượng tuyệt đối.

### 6.6. Lệnh tái lập (không bắt buộc chạy)

```bash
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/benchmark_chunking.py \
  --generator qwen --top-k 3 --max-tokens 512 --overlap-tokens 0 \
  --strategies fixed recursive structure
```

Chạy 3 chiến lược mất khoảng 15–20 phút trên CPU; lần đầu còn thời gian nhúng corpus.
`--device cuda` dùng được nếu có GPU; `--no-cache` để đo latency thật nhưng tốn thời gian.
`results_all.json` được gộp từ lượt trước nếu tham số tương thích
(`load_previous_results`, `:780–802`); nếu khác, nó bỏ qua kết quả cũ thay vì trộn.

---

## 7. Những lỗi/g iới hạn của app

| # | Vấn đề | Hệ quả | Cách sửa |
|---|---|---|---|
| 1 | Replay không khớp `use_classifier` | Có thể hiển thị số của cấu hình khác | Thêm cờ vào `find_replay_entry` + meta |
| 2 | Replay không có Faithfulness | Composite chỉ còn 2 thành phần | Ghi rõ; không so với live |
| 3 | Composite không có MRR | Structure thắng MRR nhưng không được thưởng | Thêm MRR hoặc Hit@1 |
| 4 | Free mode + replay chọn theo latency | Winner vô nghĩa | Tắt winner hoặc cảnh báo |
| 5 | `refusal_rate` sai trong benchmark | Báo cáo “0 từ chối” sai | Fold marker |
| 6 | Bảng so sánh không in `n` | `—` bị hiểu là 0 | Thêm cột n |
| 7 | Index tự dựng có thể khác benchmark | Demo không cùng chunk | Hiển thị `index_origin` (đã có) |
| 8 | `st.cache_data` giữ kết quả theo phiên | Sửa code backend không tự xóa cache | Clear cache khi đổi code |
| 9 | Top-K slider max 5 | Không tái hiện được top_k=6 của evaluation | Mở rộng max hoặc ghi rõ |
| 10 | Không có auth/multi-user | Chỉ dùng demo nội bộ | Không deploy public |

Điểm 7 đã được xử lý một phần: mỗi kết quả có `index_origin` và UI in ở tab 2. Điểm 8 là
hành vi chuẩn của Streamlit; khi sửa `src/`, phải restart app hoặc clear cache.

---

## 8. Handoff cho team frontend

> Phần này viết cho team FE, không giả định đọc được Python. Nó là hợp đồng để dựng lại
> UI bằng React/Vue hoặc bất kỳ framework nào, dùng cùng backend.

### 8.1. Mục tiêu sản phẩm

Một trang demo cho phép chọn một câu hỏi (từ benchmark hoặc tự nhập), chạy 3 chiến lược
chunking, và trả về:

1. câu trả lời của chiến lược tốt nhất + trích dẫn + nguồn;
2. bảng so sánh 3 chiến lược;
3. chi tiết từng chunk truy xuất của từng chiến lược.

Đây là công cụ **so sánh chunking**, không phải chatbot production. Không cần đăng nhập,
không lưu lịch sử người dùng, không upload tài liệu.

### 8.2. Màn hình và trạng thái

**Sidebar**

- Generator: `Qwen local` | `Gemini API` (radio).
- Top-K: slider 1–5, mặc định 3.
- Tầng phân loại: `Tắt` | `Bật`, mặc định Bật.
- LLM Judge: checkbox, mặc định tắt.
- Replay: checkbox, mặc định bật.
- Trọng số Composite: 3 number input 0–1, mặc định 0.4/0.3/0.3.
- Trạng thái Ollama: chấm xanh/đỏ + message.

**Khu input**

- Radio: “Câu từ benchmark” | “Câu tự do”.
- Benchmark: select box 50 câu; hiển thị tier, in_corpus, source_document.
- Tự do: text input; không có ground truth.
- Nút “Chạy đánh giá”.

**Trạng thái chạy**

- Mỗi chiến lược một status card: đang chạy / thành công (live|replay, latency) / lỗi.
- Progress tổng 0→1.
- Một chiến lược lỗi vẫn hiển thị 2 chiến lược còn lại.

**3 tab**

- Tab 1: 4 metric + nhãn phân loại + answer (warning nếu refusal) + citations + top-K
  sources.
- Tab 2: bảng 3 dòng × 9 cột; tô winner; caption giải thích `—`.
- Tab 3: 3 cột; mỗi source là accordion hiển thị rank, file, tier, chunk_id, preview;
  đánh dấu đúng nguồn và “đưa vào generator”.

### 8.3. Hợp đồng dữ liệu

Backend trả về:

```ts
type StrategyKey = "fixed" | "recursive" | "structure";

interface StrategyResult {
  strategy: StrategyKey;
  answer: string | null;
  sources: Array<{
    rank: number;
    source: string;
    tier: string;
    chunk_id: number | string | null;
    preview?: string;
    chars?: number | null;
    gt_hit?: boolean;
    fed_to_generator?: boolean;
  }>;
  contexts: string[] | null;
  predicted_citations: string[];
  metrics: {
    hit_at_k: number | null;
    mrr: number | null;
    citation_precision: number | null;
    citation_recall: number | null;
    citation_f1: number | null;
    citation_exact_match: number | null;
    faithfulness: number | null;
    faithfulness_method: string | null;
    latency_ms: number | null;
    is_refusal: boolean;
    n_chunks: number | null;
    index_origin: string | null;
  };
  composite_score: number | null;
  normalized_query: string | null;
  labels: { topic: string | null; question_type: string | null } | null;
  retrieval_config: Record<string, unknown> | null;
  sub_queries: string[] | null;
  error: string | null;
  mode: "live" | "replay";
  replay_ts: string | null;
}

type RunResult = Record<StrategyKey, StrategyResult>;
```

Quy tắc hiển thị:

- `null` → `—`, **không** hiển thị 0.
- `mode === "replay"` → badge “Replay từ <timestamp>”; không hiển thị Faithfulness.
- `error !== null` → card lỗi; không tính composite.
- `is_refusal === true` → warning, không tô “thành công” như câu trả lời bình thường.
- `composite_score` có thể thay đổi khi đổi trọng số mà không chạy lại backend.

### 8.4. Tiêu chí nghiệm thu

1. Chọn 3 câu benchmark khác nhau → 3 tab render đúng, không crash khi một chiến lược lỗi.
2. Bật/tắt classifier → kết quả live đổi (hoặc replay bị từ chối nếu không khớp cấu hình).
3. Đổi trọng số → chỉ composite và winner đổi, không có request backend mới.
4. Replay → hiển thị badge và `—` ở Faithfulness; không có số bịa.
5. Câu tự do → Hit/MRR/Citation/Composite `—`; chỉ answer, nguồn, latency, proxy.
6. Refusal → warning rõ, không hiển thị như câu trả lời thành công.
7. Citation rỗng → hiển thị “(không có)”, không hiển thị 0.0 giả.
8. Top-K đổi → số source “đưa vào generator” đổi theo, nhưng vẫn hiển thị toàn bộ recall
   window ở tab 3.
9. Không có Ollama + chọn Qwen → lỗi được bắt, gợi ý dùng replay/Gemini.
10. Không có `results_all.json` → replay tắt mềm, live vẫn chạy.

### 8.5. Ngoài phạm vi

- Upload/ocr tài liệu mới.
- Chỉnh sửa corpus hoặc chunk.
- Quản lý người dùng, phân quyền, lưu lịch sử.
- Fine-tune model.
- So sánh model generator (chỉ Qwen/Gemini cố định).
- Đo Faithfulness trên replay (không có contexts).

### 8.6. Câu hỏi cần chốt với backend

1. Có cần hiển thị `retrieval_config` đầy đủ (top_k, weights, filter, subquery) hay chỉ
   nhãn?
2. Winner có nên là “best theo composite” hay “best theo mục tiêu người dùng chọn”?
3. Có cần xuất CSV/PNG kết quả demo không?
4. Replay có cần lọc theo classifier/judge không, hay chỉ cảnh báo?
5. Có cần chạy 3 chiến lược song song thay vì tuần tự không? (Hiện tuần tự để tránh tranh
   chấp CPU/Ollama.)

---

## 9. Bài tập

**A.** Vì sao app không được tự gọi `classify_query` và tự chọn `top_k`? Nêu hai hậu quả
nếu làm vậy.

**B.** Một người dùng bật classifier nhưng replay đang bật, và entry replay được đo khi
tắt classifier. App sẽ hiển thị gì? Vì sao sai? Sửa ở đâu?

**C.** Với kết quả 50 câu, `fixed` thắng Hit@3 nhưng `structure` thắng MRR. Nếu hội đồng
hỏi “chiến lược nào tốt nhất”, trả lời thế nào trong 4 câu?

**D.** Vì sao `refusal_rate = 0.0` trong `results_all.json` không đáng tin? Viết biểu thức
đúng.

**E.** Thiết kế một tiêu chí composite khác có tính MRR và giải thích trade-off.

<details>
<summary>Đáp án</summary>

**A.** UI tự gọi classifier sẽ tạo **hai nguồn nhãn**: pipeline vẫn chạy classifier lần nữa
theo `ENABLE_CLASSIFIER`, hoặc UI dùng nhãn khác để chọn top_k trong khi pipeline dùng
nhãn cũ. Hậu quả: (1) kết quả demo không còn là kết quả của pipeline đã đánh giá; (2) router
nhận hai cấu hình khác nhau, metric Hit/MRR không truy vết được. Đúng: chỉ đặt
`ENABLE_CLASSIFIER` quanh lúc dựng pipeline, để pipeline tự quyết.

**B.** App vẫn dùng entry replay, hiển thị answer/metrics của cấu hình không classifier,
trong khi sidebar ghi “Bật”. `labels` có thể `None`; người xem hiểu sai rằng classifier đã
được bật. Sửa: thêm `use_classifier` (và `use_judge` nếu muốn) vào `find_replay_entry` và
meta `results_all.json`; nếu không khớp → chạy live hoặc báo “không có replay phù hợp”.

**C.** “Không có chiến lược thắng mọi chỉ số. Fixed thắng Hit@3 (0.88 so với 0.76) vì chunk
lớn chứa nhiều nội dung; structure thắng MRR (0.716 so với 0.698), Hit@6 và Citation F1 vì
chunk theo Điều/Khoản tinh hơn. Chọn theo mục tiêu: nếu cần chắc chắn có tài liệu đúng
trong top 3, fixed; nếu cần chunk đúng đứng sớm và trích dẫn tốt, structure. Kết quả trên
50 câu, top_k=3, Qwen 1.5B, không có khoảng tin cậy.”

**D.** Vì `REFUSAL_MARKER in fold(answer)` so marker **có dấu** với answer **đã bỏ dấu**,
không bao giờ khớp. Đúng: `fold(REFUSAL_MARKER) in fold(answer)`. Đây là cùng lỗi đã sửa
ở `evaluation.py` nhưng còn trong `scripts/benchmark_chunking.py`.

**E.** Ví dụ:
`Composite = 0.3×Hit@3 + 0.2×MRR + 0.2×Faithfulness + 0.2×CitationF1 + 0.1×(1−latency_chuẩn_hóa)`.
Ưu điểm: thưởng thứ hạng và chi phí; nhược điểm: trọng số tùy ý, khó so sánh với tài liệu,
latency phụ thuộc máy. Cần công bố trọng số trước và chạy sensitivity analysis (đổi trọng
số xem winner có đổi không).

</details>

---

## 10. Tóm tắt chương

1. App là lớp trình bày thuần túy: mọi logic nằm trong `src/`; UI chỉ bật/tắt cờ và gọi
   pipeline.
2. Ba index vật lý cho 3 chiến lược; bge-m3 nạp một lần; index ưu tiên lấy từ benchmark,
   sau đó tự dựng.
3. Cache `resource` giữ model/corpus/index; cache `data` giữ kết quả theo tham số; composite
   tính ngoài cache nên đổi trọng số không chạy lại backend.
4. Replay nhanh nhưng không có contexts/Faithfulness và không khớp classifier/judge — phải
   ghi rõ, không được so với live.
5. Composite 0.4/0.3/0.3 không có MRR; `fixed` thắng demo vì Hit@3 cao, không phải vì mọi
   chỉ số tốt hơn.
6. Thực nghiệm 50 câu: fixed Hit@3 0.88; structure MRR 0.716, Hit@6 0.92, Citation F1
   0.0767; structure có 378 chunk, index lớn hơn 40%; latency ~13s/câu như nhau.
7. Không có bữa trưa miễn phí: chunk lớn thắng recall top-K, chunk nhỏ thắng precision/MRR/
   citation. Chọn theo mục tiêu, không theo một con số.
8. `refusal_rate` của benchmark chunking sai do không fold marker; không được trích.
9. Handoff FE: 3 màn hình, hợp đồng dữ liệu, quy tắc `null → —`, replay badge, refusal
   warning, 10 tiêu chí nghiệm thu.
10. Demo không phải production: không auth, không upload, không multi-user, không lưu lịch
    sử.

Tiếp theo: [10 — Bài học và bảo vệ](10_bai_hoc_va_ky_nang.md).
