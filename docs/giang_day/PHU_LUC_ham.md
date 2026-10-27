# Phụ lục A — Mục lục hàm/class theo module

> Tra cứu nhanh: mỗi hàm/class trong repo, dòng định nghĩa, việc làm, và chương
> giáo trình liên quan. Dùng khi bảo vệ: hội đồng hỏi “hàm này ở đâu, làm gì”,
> em mở đúng dòng thay vì mở cả file.

**Quy ước:**

- Số dòng đúng tại **2026-10-23**. Khi sửa code, tìm lại theo **tên hàm** —
  đừng tin số dòng tuyệt đối.
- ★ = điểm vào chính (entry point) của module.
- ⚠ = có lỗi/giới hạn đã biết, đã ghi trong chương 08–10.
- `└` = method của class ngay phía trên.
- Chữ ký được rút gọn: bỏ type phức tạp, giữ tham số quan trọng và default.

**Cách tự sinh lại phụ lục** (khi repo đổi nhiều):

```bash
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe - <<'PY'
import ast, pathlib
for p in sorted(pathlib.Path('src').glob('*.py')):
    tree = ast.parse(p.read_text(encoding='utf-8'))
    print(f'## {p}')
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            print(n.lineno, type(n).__name__, n.name)
PY
```

Sinh đầy đủ hơn: thêm `ast.get_docstring(n)` để lấy mô tả. Nhưng nhớ: **docstring
có thể lỗi thời**; hành vi thật nằm ở thân hàm. Ví dụ ngay trong repo:
`evaluation.py:469` ghi “truyền top_k” nhưng dòng 471 truyền `retrieve_k`.

---

## 1. Điểm vào (chạy từ repo gốc)

### 1.1. `main.py` — CLI hỏi đáp

Vai trò: nạp pipeline, nhận câu hỏi từ terminal, in câu trả lời + nguồn; hỗ trợ
chế độ offline Qwen. Chương 07.

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 41 | `_force_utf8_stdout` | `()` | Ép stdout UTF-8 để tiếng Việt không lỗi trên console Windows. |
| 51 | `parse_args` | `()` | Đọc `--top-k`, `--question`, cờ offline… |
| 65 | `print_help` | `()` | In hướng dẫn dùng. |
| 75 | `use_qwen_generator` | `()` | Đọc cờ `USE_QWEN_GENERATOR=1`. |
| 80 | `build_generator` | `(use_qwen)` | Dựng Qwen local hoặc Gemini; tắt fallback khi chọn Qwen. |
| 97 | `build_pipeline` | `(top_k)` | VectorDB + LocalSLM + Generator → pipeline, số chunk. |
| 146 | `print_result` | `(result, elapsed, offline=False)` | In câu gốc → câu chuẩn hóa → nguồn → trả lời. |
| 193 | `ask_once` | `(pipeline, question, top_k)` | Một lượt hỏi; Ctrl+C trả `False`. |
| 220 | `interactive_loop` | `(pipeline, top_k)` | Vòng REPL. |
| 240 | ★ `main` | `()` | Ghép toàn bộ. |

### 1.2. `ingest.py` — nạp corpus → ChromaDB

Vai trò: quét `data/corpus`, chunk, nhúng bge-m3, persist. Chương 02.

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 14 | ★ `run_ingestion` | `(db_manager=None, reset=True)` | Loader → chunker → vector store; trả manager, store, số chunk. `reset=True` xóa thư mục cũ. |
| 75 | `main` | `()` | CLI của ingest. |

### 1.3. `learn.py` — test & học có trọng tài

Vai trò: người dùng sửa câu trả lời sai; ghi “Điều 1001…” vào
`data/corpus/ghi_chu_hoc_them.txt`, rebuild index, log CSV. Chương 07.

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 29 | `read_correction` | `()` | Đọc nhiều dòng từ stdin tới dòng trống. |
| 40 | `append_note` | `(question, correction)` | Sinh số Điều kế tiếp, ghi file ghi chú. |
| 60 | `log_learning` | `(question, wrong_answer, correction, chunks_before, chunks_after)` | Ghi `logs/learning/learning_log.csv`. |
| 80 | ★ `main` | `()` | Vòng hỏi → đánh giá → sửa → rebuild. |

### 1.4. `benchmark_chunking.py` — thực nghiệm 3 chiến lược

Vai trò: chạy 50 câu × 3 chiến lược, mỗi chiến lược một index riêng, xuất log
và báo cáo. Chương 02, 09.

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 134 | `setup_logger` | `()` | Logger console + file. |
| 146 | `strategy_log_file` | `(log_path)` | Gắn FileHandler UTF-8 tạm cho một chiến lược. |
| 165 | `_mean` | `(values)` | Trung bình bỏ `None`. |
| 171 | `_num` | `(value, digits=4)` | Format số an toàn. |
| 175 | `_one_line` | `(text, limit)` | Phẳng hóa, cắt dòng. |
| 181 | `_wrap` | `(text, limit, indent='  ')` | Ngắt dòng log. |
| 191 | `dir_size_mb` | `(path)` | Dung lượng index (MB). |
| 199 | `rrf_rank_score` | `(rank, c=60)` | `1/(c+rank)` — dựng điểm RRF từ hạng. |
| 209 | `apply_device` | `(manager, device)` | Chuyển bge-m3 sang CUDA nếu cần. |
| 237 | `load_corpus` | `()` | Nạp corpus một lần cho cả 3 chiến lược. |
| 253 | `chunk_corpus` | `(documents, strategy, counter, max_tokens, overlap_tokens)` | Cắt + thống kê token. |
| 302 | `build_index` | `(manager, chunks, strategy, log_dir)` | Dựng ChromaDB riêng, đo dung lượng. |
| 345 | `expected_citations_of` | `(question)` | Gộp 2 trường ground truth trích dẫn. |
| 360 | `evaluate_one` | `(pipeline, question, top_k)` | Một câu: retrieve → generate → chấm. |
| 429 | `error_entry` | `(question, exc, elapsed_ms)` | Entry lỗi giữ khung chỉ số. |
| 461 | `aggregate` | `(strategy, entries, chunk_stats, index_size_mb, total_time_s)` | Gộp chỉ số chiến lược. |
| 495 | `_pct` | `(value)` | `0.123 → 12.3%`. |
| 499 | `log_header` | `(strategy, params, chunk_stats, index_size_mb, collection, index_dir, device_label)` | Header log. |
| 543 | `log_question` | `(index, total, entry)` | Khối log một câu. |
| 591 | `log_footer` | `(agg, params, device_label)` | Footer tổng hợp. |
| 628 | `comparison_rows` | `(aggregates)` | Ma trận 3×7 chỉ số. |
| 645 | `infrastructure_rows` | `(aggregates)` | Bảng index/latency/token. |
| 664 | `_manual_markdown` | `(rows)` | Dựng bảng khi thiếu pandas. |
| 675 | `_write_csv` | `(rows, path)` | Ghi CSV. |
| 687 | `write_comparison_report` | `(aggregates, log_dir, meta)` | Xuất `.md` + `.csv`. |
| 759 | `build_generator` | `(args)` | Gemini/Qwen, temperature=0; tắt fallback Gemini. |
| 773 | `build_token_counter` | `(args)` | HF hoặc whitespace. |
| 780 | `load_previous_results` | `(log_dir, compat)` | Gộp kết quả cũ nếu tham số khớp. |
| 805 | `run_strategy` | `(strategy, args, documents, counter, tokenizer_name, manager, local_slm, generator, generator_model, questions, log_dir, device_label)` | Trọn một chiến lược. |
| 887 | `parse_args` | `()` | CLI. |
| 924 | ★ `main` | `()` | Ghép toàn bộ. |

⚠ Dòng 413: `REFUSAL_MARKER in fold(answer)` — marker có dấu, answer đã fold;
`refusal_rate` luôn 0. Đúng: `fold(REFUSAL_MARKER) in fold(answer)`.

### 1.5. `demo_streamlit.py` — UI so sánh 3 chiến lược

Vai trò: lớp trình bày; không chứa logic RAG. Chương 09.

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 104 | `get_tokenizer` | `()` | Tokenizer cache. |
| 110 | `get_corpus` | `()` | Corpus cache `{title, content, tier}`. |
| 118 | `get_local_slm` | `()` | LocalSLM dùng chung. |
| 124 | `get_generator` | `(generator_label)` | Qwen/Gemini; Gemini tắt fallback. |
| 141 | `get_judge_model` | `()` | Gemini judge độc lập. |
| 159 | `class DemoIndexRegistry` | — | Quản lý 3 index vật lý. |
| 167 | └ `__init__` | `(self)` | Khởi tạo registry. |
| 171 | └ `_manager_or_load` | `(self)` | Nạp bge-m3 một lần. |
| 176 | └ `get_store` | `(self, strategy)` | Trả `(store, n_chunk, nguồn_index)`; ưu tiên index benchmark. |
| 238 | `get_index_registry` | `()` | Cache resource registry. |
| 247 | `load_benchmark_questions` | `()` | Đọc benchmark + báo lỗi. |
| 258 | `load_replay_payload` | `()` | Đọc `results_all.json` cho replay. |
| 278 | `is_refusal_answer` | `(answer)` | Nhận diện từ chối, fold cả 2 phía. |
| 290 | `expected_citations_of` | `(question)` | Gộp ground truth trích dẫn. |
| 307 | `compute_composite` | `(hit, faith, cit, weights)` | Composite, chuẩn hóa theo thành phần có mặt. |
| 333 | `pick_winner` | `(results, free_mode)` | Composite → tie-break Hit/MRR/Citation hoặc Faith/latency. |
| 381 | `build_demo_pipeline` | `(use_classifier, **kwargs)` | Đặt env classifier quanh `__init__`. |
| 400 | `evaluate_strategy_live` | `(strategy, query, top_k, generator_label, use_judge, question, use_classifier=False)` | Chạy live một chiến lược, cache theo tham số. |
| 502 | `replay_entry_to_result` | `(entry, strategy, timestamp, total_chunks)` | Đổi entry JSON → khung UI; không có contexts/faithfulness. |
| 559 | `find_replay_entry` | `(payload, strategy, query, top_k, generator_label)` | Tìm entry khớp tham số. |
| 592 | `error_result` | `(strategy, exc)` | Khung lỗi cho một chiến lược. |
| 615 | `evaluate_rag_strategies` | `(query, top_k, benchmark_question=None, *, generator_label, use_judge, use_classifier, allow_replay, weights, on_strategy_start, on_strategy_done)` | Hàm backend trung tâm của app. |
| 689 | `fmt_score` | `(value, digits=3)` | `—` nếu None. |
| 694 | `fmt_percent` | `(value)` | `—` nếu None. |
| 699 | `fmt_latency` | `(value)` | ms có phân cách. |
| 704 | `format_classification_lines` | `(labels, retrieval_config, sub_queries, mode)` | Dòng hiển thị classifier/router. |
| 756 | `render_sidebar` | `()` | Cấu hình thí nghiệm. |
| 826 | `render_input` | `(sidebar)` | Câu benchmark hoặc câu tự do. |
| 887 | `_one_line` | `(text, limit)` | Phẳng hóa. |
| 896 | `run_evaluation` | `(sidebar, query, question, free_mode)` | Chạy 3 chiến lược với progress. |
| 952 | `render_tab_winner` | `(run, winner)` | Tab 1: câu trả lời + 4 chỉ số. |
| 1034 | `render_tab_comparison` | `(run, winner)` | Tab 2: bảng 3 chiến lược. |
| 1090 | `render_tab_chunks` | `(run)` | Tab 3: chunk từng chiến lược. |
| 1157 | ★ `main` | `()` | Sidebar → input → chạy → 3 tab. |

⚠ Replay (502) không có `contexts`, không đo faithfulness, không khớp
classifier/judge; chỉ demo.

### 1.6. `export_architecture.py`

Script một lần: đọc `SYSTEM_ARCHITECTURE.md`, xuất `.txt` + `.docx`. Không định
nghĩa hàm/class; không thuộc pipeline RAG.

---

## 2. Lõi RAG

### 2.1. `src/text_utils.py` — chuẩn hóa dấu

| Dòng | Tên | Chữ ký | Việc làm |
|---:|---|---|---|
| 13 | ★ `fold` | `(text)` | NFD bỏ dấu, `đ→d`, lowercase, gom khoảng trắng. Nguồn chân lý cho mọi so khớp. |

Chương 03. **Quy tắc:** so khớp tiếng Việt phải fold **cả hai phía**.

### 2.2. `src/loader.py` — đọc file + OCR

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 38 | `_extract_txt` | `(path)` | Đọc TXT. |
| 43 | `_extract_docx` | `(path)` | Đọc DOCX (paragraph + table). |
| 61 | `_get_ocr_engine` | `()` | Singleton RapidOCR; báo lỗi cài đặt. |
| 73 | `_ocr_page_text` | `(engine, image)` | OCR một trang → dòng. |
| 83 | `class DocumentLoader` | — | Loader đa định dạng + OCR theo trang + cache. |
| 96 | └ `__init__` | `(data_dir='./data/corpus', default_tier='Khác', enable_ocr=None, ocr_dpi=None, min_chars_per_page=None, ocr_cache_dir=None)` | Cấu hình. |
| 115 | └ `_tier_of` | `(path)` | Suy tầng từ thư mục cấp 1. |
| 119 | └ `_skip` | `(path, reason)` | Ghi nhận file bỏ qua. |
| 125 | └ `_cache_file` | `(path)` | Tên cache gắn nội dung + tham số OCR. |
| 134 | └ `_cache_load` | `(path, scan_pages)` | Đọc cache trang. |
| 145 | └ `_cache_save` | `(path, pages)` | Ghi cache. |
| 152 | └ `_ocr_pages` | `(path, scan_pages, total_pages)` | OCR các trang cần. |
| 183 | └ `_extract_pdf` | `(path)` | Text trước, trang nghèo chữ mới OCR. |
| 207 | └ `_read_document` | `(path)` | Dispatch theo đuôi. |
| 221 | ★ `load_documents` | `(self)` | Quét đệ quy → `[{title, content, tier}]`. |

Chương 02. ⚠ Tầng 1 OCR mất dấu; 3 `.doc` + 1 PDF lỗi chưa đọc được.

### 2.3. `src/chunking.py` — production + 3 chiến lược

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 39 | `has_article_structure` | `(text)` | Có tiêu đề “Điều N.” đầu dòng? |
| 44 | `canonical_article` | `(raw_heading)` | `Dieu 4.` / `Ðiều 4.` → `Điều 4.` |
| 50 | `class DocumentChunker` | — | Chunk production, giữ tiền tố tên văn bản. |
| 53 | └ `__init__` | `(max_chars=1200, min_chars=20, overlap_chars=150)` | Cấu hình production. |
| 63 | └ `chunk_document` | `(doc)` | `{title, content, tier}` → list chunk. |
| 72 | └ `structure_aware_chunking` | `(text, doc_title='Quy chế Đào tạo')` | Cắt theo Điều/Khoản, làm giàu ngữ cảnh. |
| 102 | └ `fallback_chunking` | `(text, doc_title='Quy chế Đào tạo')` | Văn bản không có Điều → đoạn văn. |
| 106 | └ `_overlap_prefix` | `(prev_chunk)` | Lấy đuôi chunk trước, cắt ở ranh giới câu. |
| 121 | └ `_pack_text` | `(text)` | Sliding window theo ký tự. |
| 151 | └ `_split_oversized` | `(paragraph)` | Đoạn quá dài → câu → cắt cứng. |
| 224 | `class BaseTokenCounter` | — | Giao diện đếm/cắt token. |
| 233 | └ `count` | `(text)` | Số token. |
| 237 | └ `window` | `(text, start, length)` | Lát token. |
| 241 | └ `windows` | `(text, length, overlap)` | Các cửa sổ chồng lấp. |
| 255 | `class HuggingFaceTokenCounter` | `(BaseTokenCounter)` | Tokenizer bge-m3. |
| 268 | └ `__init__` | `(model_name=DEFAULT_TOKENIZER_MODEL)` | Lười nạp. |
| 273 | └ `tokenizer` | `(self)` | Property nạp tokenizer. |
| 280 | └ `encode` | `(text)` | Text → ids. |
| 285 | └ `decode` | `(ids)` | ids → text. |
| 288 | └ `count` | `(text)` | Số token. |
| 291 | └ `window` | `(text, start, length)` | Decode lát token. |
| 294 | └ `windows` | `(text, length, overlap)` | Cửa sổ. |
| 308 | └ `_shrink` | `(ids, limit)` | Bớt token tới khi mã hóa lại vừa ngưỡng. |
| 326 | `class WhitespaceTokenCounter` | `(BaseTokenCounter)` | Đếm theo từ — fallback. |
| 337 | └ `count` | `(text)` | Số từ. |
| 340 | └ `window` | `(text, start, length)` | Lát từ. |
| 347 | `get_token_counter` | `(model_name=None)` | Cache tokenizer; lỗi → whitespace. |
| 368 | `split_around_tables` | `(text)` | Tách đoạn/bảng Markdown. |
| 401 | `_chunk_with_table_lock` | `(text, chunk_fn, lock_markdown_tables=True, table_prefix='')` | Bảng luôn một chunk. |
| 428 | `_hard_slice` | `(text, counter, max_tokens, overlap_tokens=0)` | Cắt cứng theo token. |
| 442 | `_validate_budget` | `(max_tokens, overlap_tokens)` | Chặn cấu hình vô nghĩa. |
| 450 | `fixed_size_chunking` | `(text, max_tokens=512, overlap_tokens=0, token_counter=None, lock_markdown_tables=True)` | Chiến lược 1. |
| 489 | `_merge_pieces` | `(pieces, separator, rest, counter, max_tokens)` | Gộp tham lam. |
| 523 | `_recursive_split` | `(text, separators, counter, max_tokens)` | Cắt đệ quy theo ranh giới. |
| 540 | `_apply_overlap` | `(chunks, overlap_tokens, counter)` | Chồng lấp đuôi/đầu. |
| 553 | `recursive_chunking` | `(text, max_tokens=512, overlap_tokens=0, separators=DEFAULT_SEPARATORS, token_counter=None, lock_markdown_tables=True)` | Chiến lược 2. |
| 594 | `_split_keep_markers` | `(text, pattern)` | Cắt nhưng giữ tiêu đề. |
| 622 | `_article_units` | `(article_body)` | Điều → Khoản/Điểm. |
| 645 | `_label_range` | `(kind, labels)` | `1,2 → Khoản 1-2`. |
| 656 | `_hierarchical_prefix` | `(doc_title, article_label, clause_labels, point_labels)` | Tiền tố `[Văn bản] - [Điều] - [Khoản]`. |
| 675 | `_flush_group` | `(doc_title, article_label, group, counter, max_tokens)` | Nhóm unit → chunk. |
| 702 | `_starts_new_group` | `(group, unit)` | Unit không nhãn đứng riêng. |
| 713 | `_emit_units` | `(doc_title, article_label, units, counter, max_tokens)` | Gộp tham lam unit. |
| 738 | `_chunk_article_segment` | `(segment, doc_title, carry_label, counter, max_tokens)` | Chunk một đoạn không bảng. |
| 772 | `structure_aware_chunking` | `(text, doc_title='Văn bản', max_tokens=512, token_counter=None, lock_markdown_tables=True)` | Chiến lược 3. |
| 831 | ★ `chunk_with_strategy` | `(strategy, text, doc_title='Văn bản', max_tokens=512, overlap_tokens=0, token_counter=None, lock_markdown_tables=True)` | Cổng chung 3 chiến lược. |

Chương 02. ⚠ Production dùng `DocumentChunker` (max_chars), thực nghiệm dùng
token; 361 chunk production vs 378 structure thực nghiệm.

### 2.4. `src/vector_db.py` — bge-m3 + ChromaDB + BM25

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 26 | `bm25_tokenize` | `(text)` | Tách token gốc **và** token fold. |
| 40 | `extract_documents_from_chroma` | `(vector_db)` | Lấy toàn bộ Document từ collection. |
| 55 | `class VectorStoreManager` | — | Quản lý embedding + Chroma + BM25. |
| 56 | └ `__init__` | `(persist_directory=None)` | Nạp bge-m3 (normalize=True). |
| 65 | └ `create_vector_store` | `(chunks, collection_name='agu_regulations')` | Nạp chunk, metadata `chunk_id`. |
| 101 | └ `load_vector_store` | `(collection_name='agu_regulations')` | Kết nối index đã persist. |
| 109 | └ `create_bm25_retriever` | `(vector_db, k=12)` | BM25 dual tokenizer. |
| 122 | └ `create_ensemble_retriever` | `(vector_db, weights=None, c=60, k=12)` | RRF BM25 + Chroma. |

Chương 03. Mặc định thực tế `[0.5, 0.5]` (`DEFAULT_BM25_WEIGHT=0.5`,
`DEFAULT_VECTOR_WEIGHT=0.5`); docstring cũ ghi `[0.4, 0.6]` — thêm một ví dụ
“docstring không phải bằng chứng”. Pipeline/router có thể đổi trọng số.

### 2.5. `src/retrieval.py` — mở rộng & tách truy vấn

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 79 | `expand_query_with_synonyms` | `(normalized_query)` | Thêm từ đồng nghĩa pháp lý. |
| 203 | `_clean_subquery_lines` | `(text)` | Parse output Qwen → list truy vấn con. |
| 222 | `_fold_token_set` | `(text, keep_numbers=True)` | Tập token fold. |
| 230 | `_pairwise_overlap_too_high` | `(sub_queries, max_overlap=MAX_PAIRWISE_OVERLAP)` | Chặn tách dở (các câu quá giống). |
| 265 | ★ `split_comparison_query` | `(query, llm_client=None)` | Tách 2–3 truy vấn; lỗi → `[query]`. |

Chương 03, 05.

### 2.6. `src/local_slm.py` — Qwen chuẩn hóa + guardrail

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 34 | `class LocalSLMError` | `(RuntimeError)` | Lỗi giao tiếp Ollama. |
| 72 | `build_normalize_prompt` | `(raw_query)` | Few-shot 4 mẫu + quy tắc. |
| 121 | `_env_float` | `(name, default)` | Đọc env float. |
| 135 | `clean_output` | `(text)` | Bỏ nhãn/nháy, lặp tới điểm bất động. |
| 154 | `is_acceptable` | `(normalized)` | Lý do từ chối nếu câu hỏng. |
| 181 | `_extract_numbers` | `(folded_text)` | Tập số, `1,0` = `1.0`. |
| 186 | `guardrail_violation` | `(raw_query, normalized_query, min_overlap=MIN_TOKEN_OVERLAP)` | Bảo toàn số + overlap token. |
| 219 | `class LocalSLM` | — | Bao Ollama. |
| 222 | └ `__init__` | `(model_name=None, host=None, timeout=None, probe_timeout=..., num_predict=..., max_retries=..., min_token_overlap=...)` | Cấu hình. |
| 244 | └ `check_connection` | `(self)` | Ollama sống + model đã pull. |
| 266 | └ `generate` | `(prompt, temperature=0.0, num_predict=None)` | Gọi Ollama. |
| 290 | ★ `normalize_query` | `(raw_query)` | Chuẩn hóa; lỗi/guardrail → câu gốc. |

Chương 04. Guardrail: mất số hoặc overlap < 0.3 → fallback.

### 2.7. `src/query_normalizer.py` — few-shot + active learning

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 96 | `load_normalization_pairs` | `()` | Đọc `normalization_pairs.json` + ghi chú học + log. |
| 160 | `build_few_shot_with_learning` | `(user_query, learning_pairs)` | 4 mẫu cứng + tối đa 4 mẫu học. |
| 227 | `clean_normalized_text` | `(text)` | Bỏ nhãn/nháy. |
| 264 | ★ `normalize_user_query` | `(llm_client, user_query)` | Giao diện chuẩn hóa (đường cũ). |

Chương 04. Pipeline hiện dùng `LocalSLM.normalize_query`; module này giữ tương
thích và logic học từ người dùng.

### 2.8. `src/classifier.py` — 14 chủ đề × 4 loại

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 401 | `build_few_shot_examples` | `()` | 16 câu benchmark ghi cứng (⚠ rò rỉ). |
| 424 | `build_classifier_prompt` | `(query)` | Quy tắc + taxonomy + few-shot + câu hỏi. |
| 464 | `extract_json_object` | `(text)` | Tách JSON đầu tiên, chịu fence. |
| 506 | `_canonical_topic` | `(value)` | Về 14 nhãn hoặc None. |
| 513 | `_canonical_question_type` | `(value)` | Về 4 nhãn hoặc None. |
| 521 | `_keyword_topic` | `(folded_query)` | Fallback từ khóa. |
| 529 | `_keyword_question_type` | `(folded_query)` | Fallback, mặc định TRA_CUU. |
| 537 | `_classifier_timeout` | `()` | `CLASSIFIER_TIMEOUT` hợp lệ. |
| 549 | `_classifier_model` | `()` | `CLASSIFIER_MODEL` → `OLLAMA_MODEL` → default. |
| 558 | ★ `classify_query` | `(query)` | Trả `{topic, question_type, raw_response}`; lỗi → keyword fallback. |

Chương 04, 08. ⚠ Accuracy 85/81 có few-shot lấy từ benchmark.

### 2.9. `src/router.py` — nhãn → cấu hình

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 101 | `class RetrievalConfig` | `(dataclass)` | `top_k`, weights, filter, subquery… |
| 111 | `base_config_from_env` | `()` | Cấu hình nền từ env. |
| 143 | `_normalize_question_type` | `(value)` | Về 4 nhãn/None. |
| 151 | `_normalize_topic` | `(value)` | Về 14 nhãn/None. |
| 158 | ★ `get_retrieval_config` | `(labels, base)` | Hàm thuần; None → base; fail-open. |

Chương 05.

### 2.10. `src/pipeline.py` — điều phối

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 57 | `_preview` | `(text, limit=160)` | Một dòng xem trước. |
| 63 | `describe_document` | `(doc, index)` | Metadata chunk → dict. |
| 77 | `class HybridRAGPipeline` | — | Luồng RAG đầu-cuối. |
| 80 | └ `__init__` | `(vector_db, local_slm, generator, oversample_factor=2, use_hybrid=True, bm25_weight=..., vector_weight=..., retriever=None, expand_query=True)` | Cấu hình. |
| 114 | └ `_init_hybrid_retriever` | `(self)` | BM25 + Chroma → Ensemble. |
| 148 | └ `retrieve` | `(query, k=6, fallback_query=None, config=None)` | Hybrid/vector, subquery, best-first. |
| 271 | └ `_merge_subquery_branches` | `(branches, k)` | Hợp nhất nhánh theo hạng tốt nhất. |
| 298 | ★ `run` | `(question, top_k=4)` | Chuẩn hóa → classify → router → retrieve → generate; trả `sources` rộng, `contexts` hẹp. |

Chương 07. ⚠ `run(top_k)` tự nhân `oversample_factor`; đừng truyền `retrieve_k`.

### 2.11. `src/generator.py` — sinh + cache + fallback

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 79 | `quota_error_kind` | `(message)` | `perday` / `minute` / None. |
| 227 | `canonicalize_refusal` | `(answer, question_type)` | Chuẩn hóa câu từ chối. |
| 243 | `is_canonical_refusal_answer` | `(text, question_type)` | Nhận diện từ chối chuẩn. |
| 257 | `select_prompt_rules` | `(question_type)` | Khối luật prompt theo loại. |
| 295 | `class GeneratorError` | `(RuntimeError)` | Lỗi API/thiếu key/hết quota. |
| 299 | `is_quota_error` | `(exc)` | 429/ResourceExhausted. |
| 305 | `is_fallback_answer` | `(answer)` | Nhãn Qwen fallback. |
| 310 | `_env_float` | `(name, default)` | Env float. |
| 320 | `_env_int` | `(name, default)` | Env int. |
| 330 | `_env_flag` | `(name, default)` | Env bool. |
| 338 | `_pick` | `(mapping, keys, default=None)` | Lấy khóa đầu tiên. |
| 346 | `normalize_docs` | `(retrieved_docs)` | Document/dict/chuỗi → dict chuẩn. |
| 399 | `extract_citation_from_metadata` | `(doc)` | Tìm Điều/Khoản trong metadata. |
| 430 | `inject_citations_from_metadata` | `(answer, retrieved_chunks)` | Ghép trích dẫn top-1. |
| 478 | `build_prompt` | `(query, docs, question_type=None)` | Prompt grounded + số thứ tự chunk. |
| 501 | `class GeminiGenerator` | — | Gemini + cache + Qwen fallback. |
| 504 | └ `__init__` | `(model_name=None, api_key=None, temperature=None, max_output_tokens=None, max_retries=...)` | Cấu hình. |
| 552 | └ `_warn_if_truncated` | `(response)` | Cảnh báo hết token. |
| 568 | └ `_call_api` | `(prompt, temperature)` | Retry 2s/4s; 429 phút chờ 60s; PerDay dừng. |
| 644 | └ `_cache_key` | `(prompt, temperature)` | SHA-1 model+temp+prompt. |
| 658 | └ `_cache_get` | `(key)` | Cache miss an toàn. |
| 670 | └ `_cache_put` | `(key, prompt, temperature, question, answer)` | Ghi cache, lỗi đĩa chỉ cảnh báo. |
| 691 | └ `_build_qwen_prompt` | `(question, docs)` | Prompt gọn cho 1.5B. |
| 718 | └ `_qwen_answer` | `(question, docs, gemini_error)` | Fallback Qwen; cả hai lỗi → `GeneratorError`. |
| 761 | └ `generate_answer` | `(query, docs, temperature=None, question_type=None)` | Cache → Gemini → fallback. |
| 878 | `class QwenGenerator` | — | Sinh offline qua Ollama. |
| 885 | └ `__init__` | `(ollama_host=None, ollama_model=None, timeout=None, temperature=QWEN_FALLBACK_TEMPERATURE, use_cache=None)` | Cấu hình. |
| 910 | └ `_build_prompt` | `(question, docs, question_type=None)` | Prompt Qwen. |
| 940 | └ `_cache_key` | `(prompt, temperature)` | SHA-1. |
| 953 | └ `_cache_get` | `(key)` | Cache. |
| 964 | └ `_cache_put` | `(key, prompt, temperature, question, answer)` | Ghi cache. |
| 982 | └ `generate_answer` | `(query, docs, temperature=None, question_type=None)` | Gọi Ollama. |

Chương 06.

---

## 3. Đánh giá

### 3.1. `src/evaluation.py` — bộ chấm A/B

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 139 | `extract_citations` | `(text)` | Rút Điều/Khoản; ⚠ bỏ “Khoản” đứng riêng. |
| 194 | `_article_of` | `(citation)` | Tách số Điều. |
| 198 | `_parse_citation_parts` | `(citation)` | Điều + Khoản. |
| 208 | `_citation_pair_weight` | `(a, b)` | 1.0 khớp; 0.5 khớp một phần. |
| 220 | `_citation_true_positives` | `(predicted, expected)` | Maximum weight matching. |
| 243 | ⚠ `citation_scores` | `(expected, predicted, source_document=None)` | P/R/F1/EM; nhánh `source_document` thưởng 1.0 cho predicted rỗng. |
| 293 | `source_match` | `(chunk_source, expected_document)` | Tên file chứa nhau. |
| 303 | `_decimal_comma_to_dot` | `(text)` | `1,0 → 1.0`. |
| 308 | `normalization_preservation` | `(raw_query, normalized_query)` | Tỷ lệ số/Điều/Khoản giữ nguyên. |
| 333 | `number_support` | `(answer, contexts)` | Tỷ lệ số trong answer có trong contexts. |
| 342 | `_strip_code_fence` | `(raw)` | Bỏ rào mã Markdown (fence JSON). |
| 350 | `_parse_judge_json` | `(raw)` | Parse JSON judge. |
| 362 | `judge_faithfulness` | `(judge_model, contexts, answer)` | Gọi Gemini judge; trả score/claims/error. |
| 439 | `load_benchmark` | `(path)` | Đọc `questions`. |
| 455 | ⚠ `evaluate_question` | `(pipeline, judge_model, question, top_k, retrieve_k)` | Chạy 1 câu, chấm mọi chỉ số; dòng 471 truyền `retrieve_k` vào `top_k`. |
| 565 | `_mean` | `(values)` | Trung bình bỏ None. |
| 570 | `aggregate` | `(entries, top_k)` | Tổng hợp toàn lượt. |
| 617 | `is_skipped_no_gt` | `(question)` | Q96–98: bỏ chấm theo GT, vẫn chấm từ chối. |
| 627 | `classification_stats` | `(entries)` | Accuracy topic/type so benchmark. |
| 659 | `group_metrics` | `(entries, key_of)` | Chỉ số theo nhóm. |
| 687 | `false_refusal_stats` | `(entries)` | Từ chối oan in-corpus. |
| 714 | `estimate_requests` | `(questions, cache_dir, judge_enabled, generator_model=None)` | Ước lượng quota (dry-run). |
| 764 | `expected_generator_cache_model` | `(use_qwen)` | Tên model cache. |
| 776 | ⚠ `load_resumable_entries` | `(path, benchmark, with_classifier, judge_enabled)` | Resume; thiếu khóa top_k/model. |
| 825 | `flush_partial_results` | `(path, meta, entries, top_k, partial=True)` | Ghi JSON sau mỗi câu. |
| 852 | `_pct` | `(value)` | `0.12 → 12.0%`. |
| 856 | `_group_table` | `(title, groups)` | Bảng nhóm. |
| 873 | `format_summary_md` | `(aggregates, entries, top_k, meta)` | Xuất Markdown. |
| 962 | `parse_args` | `()` | CLI. |
| 988 | ★ `main` | `()` | Chạy A/B, resume, ghi output. |

Chương 08. ⚠ Ba lỗi lớn: dòng 471, 249–259, 776.

### 3.2. `src/evaluate_classifier.py` — accuracy classifier

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 52 | `load_questions` | `()` | Đọc 100 câu v3. |
| 61 | `run_pass` | `(questions, limit)` | Chạy `classify_query` từng câu. |
| 101 | `accuracy` | `(results, key_ok)` | Tỷ lệ đúng. |
| 105 | `per_class_metrics` | `(results)` | P/R/F1 từng loại + macro. |
| 143 | `write_confusion_csv` | `(path, labels, expected_of, predicted_of, results)` | Ma trận nhầm lẫn. |
| 174 | `_knn_predict` | `(vectors, labels, index, k)` | kNN, tie-break theo tổng similarity. |
| 197 | `run_embedding_baseline` | `(questions, limit)` | kNN leave-one-out bge-m3. |
| 257 | ⚠ `append_knn_section` | `(knn, qwen_run_params)` | Nối bảng vào report; hard-code 85/81. |
| 290 | `_fmt_pct` | `(value)` | Format %. |
| 294 | `build_report` | `(run_params, results, repeat_check)` | Báo cáo Markdown. |
| 382 | ★ `main` | `()` | CLI `--method qwen/embedding`. |

Chương 08. ⚠ Dòng 426–439: một `unstable` dict dùng cho cả topic/type; dòng
270 hard-code Qwen 85/81; chạy nhiều lần nối trùng mục.

### 3.3. `src/faithfulness_heuristic.py`

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 36 | `extract_meaningful_tokens` | `(text)` | Token bỏ stopwords, giữ số. |
| 50 | `heuristic_faithfulness` | `(answer, contexts)` | Token overlap → score; từ chối → 1.0. |
| 83 | `compute_faithfulness_for_json` | `(json_path, update_json=True)` | Chấm lại cả file JSON. |
| 165 | ★ `main` | `()` | CLI. |

Chương 08. ⚠ Chấm hậu kiểm không cập nhật `aggregates`.

### 3.4. `src/analyze_ab.py` — bảng so sánh + hình

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 55 | `pct` | `(x)` | Format %. |
| 59 | `rel_delta` | `(with_v, wo_v)` | Chênh tương đối. |
| 65 | `pp_delta` | `(with_v, wo_v, scale=100)` | Chênh điểm phần trăm. |
| 71 | `mean` | `(vals)` | Trung bình. |
| 76 | `load_all` | `()` | Đọc 2 file A/B + benchmark. |
| 86 | `group_metrics` | `(entries, ids)` | Chỉ số theo nhóm id. |
| 111 | ★ `main` | `()` | Sinh `ab_comparison.md`, hình. |

Chương 08.

---

## 4. Công cụ sinh dữ liệu

### 4.1. `tools/build_training_data.py`

Vai trò: sinh 3.912 mẫu / 10.619 dòng từ code, corpus, benchmark, tài liệu.
Chương “dataset” trong README huấn luyện.

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 181 | `fold_tokens` | `(text)` | Token fold. |
| 189 | `token_overlap` | `(a, b)` | Jaccard/overlap. |
| 196 | `diacritic_ratio` | `(text)` | Tỷ lệ ký tự có dấu. |
| 208 | `garbage_ratio` | `(text)` | Tỷ lệ ký tự rác. |
| 215 | `clean_space` | `(text)` | Gom khoảng trắng. |
| 222 | `sentence_split` | `(text)` | Tách câu. |
| 227 | `trim_at_sentence` | `(text, limit)` | Cắt ở ranh giới câu. |
| 238 | `is_form_like` | `(title, body)` | Nhận diện biểu mẫu. |
| 254 | `is_boilerplate` | `(body)` | Đầu/cuối công văn. |
| 269 | `is_table_like` | `(body)` | Bảng số liệu. |
| 283 | `qa_unfriendly` | `(title, body)` | Không hợp sinh Q&A. |
| 288 | `sha1_text` | `(text)` | Hash chống trùng. |
| 292 | `doc_title` | `(source)` | Tên văn bản từ file. |
| 296 | `tier_label` | `(tier)` | Nhãn tầng hiển thị. |
| 303 | `citation_of` | `(source, article=None)` | Chuỗi trích dẫn. |
| 313 | `class Item` | — | Một mẫu dataset. |
| 322 | └ `__post_init__` | `(self)` | Chuẩn hóa/kiểm tra. |
| 327 | `class DatasetBuilder` | — | Gom mẫu, chống trùng. |
| 328 | └ `__init__` | `(seed=42)` | RNG + kho. |
| 339 | └ `add` | `(task, quality, user, assistant, meta=None, system='', seed=False)` | Thêm mẫu chat. |
| 358 | └ `add_classifier` | `(text, topic, qtype, label_source, quality, seed=False)` | Thêm mẫu classifier. |
| 380 | `load_chunks` | `()` | Đọc 361 chunk từ Chroma. |
| 432 | `load_benchmark` | `()` | Đọc benchmark v3. |
| 440 | `build_benchmark` | `(b, bench, chunks)` | Nhóm seed vàng. |
| 548 | `build_corpus` | `(b, chunks)` | Định danh/cloze/list/topic/grounded. |
| 686 | `_doc_summary` | `(node)` | Docstring AST. |
| 694 | `_format_args` | `(node)` | Chữ ký từ AST. |
| 704 | `build_code` | `(b)` | code_qa/signature/tests/params. |
| 797 | `_py_files` | `()` | Danh sách file Python. |
| 805 | `_call_target` | `(node)` | Đích của Call. |
| 814 | `build_code_index` | `(b)` | File index/callsite/env/commands. |
| 923 | `parse_markdown_sections` | `(path)` | Tách H2/H3. |
| 941 | `build_docs` | `(b)` | docs_qa/heading. |
| 1051 | `build_classifier` | `(b, bench)` | 2.778 mẫu classifier. |
| 1105 | `build_refusal` | `(b, bench, chunks)` | 240 mẫu từ chối. |
| 1130 | `build_retrieval` | `(b, chunks, bench)` | 881 cặp query-positive-negative. |
| 1227 | `build_router_tasks` | `(b, bench)` | Nhãn → cấu hình. |
| 1279 | `build_handcrafted` | `(b)` | Mẫu thủ công. |
| 1430 | `chat_record` | `(item, idx)` | Item → chat JSONL. |
| 1444 | `alpaca_record` | `(item, idx)` | Item → Alpaca JSONL. |
| 1456 | `write_jsonl` | `(path, rows)` | Ghi UTF-8. |
| 1465 | `split_items` | `(items, val_percent=3)` | Chia train/val. |
| 1473 | `export` | `(b, out_dir)` | Ghi 13 file + manifest + preview. |
| 1592 | ★ `main` | `()` | CLI `--out`. |

### 4.2. `tools/validate_training_data.py`

| Dòng | Tên | Chữ ký rút gọn | Việc làm |
|---:|---|---|---|
| 33 | `load_jsonl` | `(name)` | Đọc + báo lỗi dòng. |
| 48 | `messages_of` | `(row)` | Tách system/user/assistant. |
| 55 | ★ `main` | `()` | 6 nhóm kiểm tra + thống kê. |

Kiểm tra: schema, rỗng, trùng, rò rỉ benchmark, `None/null`, số trong
`corpus_identification` phải có trong đoạn trích.

---

## 5. Test — bản đồ kiểm chứng

Tổng: **280 test** trong 13 file (đếm `def test_`). Chạy:
`PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m pytest tests/ -q`.

| File | Số test | Kiểm chứng chính |
|---|---:|---|
| `test_chunking.py` | 34 | Regex Điều, 3 chiến lược, bảng, ngân sách token, thứ tự. |
| `test_classifier.py` | 31 | Parse JSON, canonical nhãn, fallback, prompt. |
| `test_evaluation.py` | 30 | Citation matching, number support, aggregate, format. |
| `test_evaluation_ab.py` | 42 | Resume, flush, A/B, nhóm, từ chối oan. |
| `test_generator_prompts.py` | 44 | Prompt theo loại, citation, refusal, cache key. |
| `test_local_slm.py` | 10 | Guardrail số/overlap, clean output. |
| `test_main.py` | 8 | CLI, offline flag, in kết quả. |
| `test_pipeline.py` | 18 | Oversampling, hybrid, subquery merge, router. |
| `test_router.py` | 27 | Ánh xạ nhãn, fail-open, env base. |
| `test_subquery.py` | 22 | Tách câu so sánh, chống tách dở. |
| `test_demo_streamlit_display.py` | 6 | Format UI, composite, refusal. |
| `test_ui_generator_flag.py` | 3 | Cờ generator trên UI. |
| `test_ui_labels.py` | 5 | Hiển thị nhãn classifier. |

⚠ Test không bắt được các lỗi đã biết vì:
- `test_evaluation.py` không có ca predicted rỗng + `source_document` (lỗi L8).
- `test_evaluation_ab.py` không kiểm tra cửa sổ `contexts` so với `top_k` (L11).
- `benchmark_chunking.py` không có test riêng cho `is_refusal`.
- `evaluate_classifier.py` không có test repeat-check.

Đây là **khoảng trống test** cần bổ sung ở P0 (chương 10).

---

## 6. Bảng tra nhanh lỗi đã biết

| Vị trí | Triệu chứng | Sửa đúng | Chương |
|---|---|---|---|
| `evaluation.py:471` | Generator nhận `retrieve_k`, không phải `top_k` | `pipeline.run(..., top_k=top_k)` | 08, 10 |
| `evaluation.py:249–259` | Câu không trích dẫn được 1.0 | Xử lý `if not predicted: return 0` trước nhánh source | 08, 10 |
| `evaluation.py:776` | Resume thiếu `top_k`/model | Thêm config hash vào meta/khóa | 08, 10 |
| `benchmark_chunking.py:413` | `refusal_rate = 0.0` | `fold(REFUSAL_MARKER) in fold(answer)` | 09, 10 |
| `evaluate_classifier.py:426–439` | `topic_stable == type_stable` | Hai dict `unstable` riêng | 08, 10 |
| `evaluate_classifier.py:270` | Hard-code Qwen 85/81 | Đọc từ `results.json` hiện tại | 08 |
| `evaluate_classifier.py:257` | Nối trùng mục khi chạy lại | Xóa mục cũ trước khi append / ghi đè | 08 |
| `demo_streamlit.py:502` | Replay thiếu contexts/faith, bỏ qua classifier | Ghi nhãn “replay”, không so live | 09 |
| `evaluation.py:139` | Bỏ “Khoản” đứng riêng | Regex nhận cả `Khoản N` độc lập | 08 |
| `faithfulness_heuristic.py:83` | Chấm hậu kiểm không cập nhật aggregate | Ghi lại aggregate sau khi chấm | 08 |

---

## 7. Đọc tiếp

- Cơ chế từng tầng: chương [01](01_tong_quan_kien_truc.md) → [09](09_ung_dung_giao_dien.md).
- Cách bảo vệ và bảng lỗi: chương [10](10_bai_hoc_va_ky_nang.md).
- Bài tập phân tầng: [BAI_TAP_VA_DAP_AN.md](BAI_TAP_VA_DAP_AN.md).
