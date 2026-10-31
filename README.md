# Hybrid RAG System for Academic Regulations (AGU Context)

Hệ thống Hỏi - Đáp tự động (RAG) cho tra cứu văn bản quy chế học vụ AGU, xây theo kiến trúc **True Hybrid Search** kèm **tầng phân loại câu hỏi 2 nhãn + router truy xuất** (bật/tắt qua `ENABLE_CLASSIFIER`): **Local SLM (Qwen2.5 qua Ollama)** phân loại câu hỏi (chủ đề + loại) → chuẩn hóa câu hỏi → **mở rộng truy vấn theo từ điển đồng nghĩa pháp lý** → tách truy vấn con cho câu so sánh → **BM25 + Vector (bge-m3/ChromaDB) hợp nhất bằng RRF** (tham số do router chọn) → **Gemini API** (hoặc Local Qwen) sinh câu trả lời kèm trích dẫn Điều/Khoản. Tầng phân loại tắt (`ENABLE_CLASSIFIER=0`, mặc định) thì pipeline chạy đúng luồng cũ 100%.

Dự án có **năm giao diện sử dụng**:

| Giao diện | File | Dành cho |
|---|---|---|
| CLI tương tác | `main.py` | Hỏi đáp hàng ngày, test nhanh |
| GUI desktop 3 tab (Tkinter) | `ui/app.py` | Tra cứu + nạp dữ liệu + gắn nhãn học |
| Đánh giá định lượng | `src/assessment/evaluation.py` | Đo Hit@K / MRR / Citation / Faithfulness trên benchmark |
| **Demo so sánh 3 chiến lược chunking (Streamlit)** | `ui/demo_streamlit.py` | Trình diễn thực nghiệm cho bài báo |
| Đánh giá bộ phân loại | `src/assessment/evaluate_classifier.py` | Đo accuracy 2 nhãn (chủ đề + loại câu hỏi) trên benchmark v3 |

Kèm các công cụ thực nghiệm: **`scripts/benchmark_chunking.py`** (chạy benchmark đầy đủ 3 chiến lược cắt đoạn, xuất báo cáo so sánh), **`src/assessment/evaluation.py`** (chạy benchmark truy xuất/generation, có cờ `--with-classifier` cho lượt A/B) và **`src/assessment/analyze_ab.py`** (phân tích 2 JSON A/B → bảng so sánh + biểu đồ).

---

## 1. Kiến trúc hệ thống

**Các thành phần:**

- **Embedding Model:** `BAAI/bge-m3` — chạy cục bộ trên phần cứng, đa ngữ 1024 chiều, hỗ trợ tiếng Việt.
- **Vector Database:** `ChromaDB` — lưu trữ và truy xuất vector theo khoảng cách **Cosine Similarity**.
- **BM25 Retriever:** tìm kiếm từ khóa chính xác (mã môn học, "Điều 12", thuật ngữ viết tắt) — bộ tách từ kép: token nguyên văn + token đã bỏ dấu.
- **EnsembleRetriever (RRF):** gộp kết quả BM25 và Chroma bằng **Reciprocal Rank Fusion**; trọng số mặc định BM25 = 0.5, Chroma = 0.5, hằng số RRF `c = 60` (đổi được qua biến môi trường, xem mục 3).
- **Local SLM:** `Qwen2.5:1.5b-instruct` qua **Ollama** — hai vai: (1) chuẩn hóa câu hỏi ở đầu pipeline; (2) generator chính ở chế độ offline hoặc generator dự phòng khi Gemini hết quota.
- **Backend Generator:** **Gemini API (`gemini-2.5-flash`)** — tổng hợp ngữ cảnh, sinh câu trả lời kèm trích dẫn Điều/Khoản (`Temperature = 0.0`), có cơ chế **Soft Refusal** khi ngữ cảnh không đủ căn cứ.

**Luồng xử lý (6 tầng):**

```
Câu hỏi thô
   │
   ▼
[0] Phân loại + Router                        ──► 2 nhãn: chủ đề (14 nhóm) + loại câu hỏi
   │   (chỉ khi ENABLE_CLASSIFIER=1)             (TRA_CUU / SO_SANH / THU_TUC / NGOAI_PHAM_VI);
   │                                             router chọn cấu hình truy xuất theo nhãn;
   │                                             lỗi phân loại → suy giảm mềm về cấu hình chung
   ▼
[1] Chuẩn hóa câu hỏi (Local Qwen / Ollama)   ──► viết lại theo văn phong quy chế,
   │                                              chống bịa thông tin, bảo toàn con số/thực thể
   ▼
[2] Mở rộng truy vấn (Query Expansion)        ──► từ điển đồng nghĩa pháp lý (~50 cặp ánh xạ),
   │                                              so khớp không dấu theo word boundary
   ▼
[3] Tách truy vấn con (chỉ câu SO_SANH)       ──► tối đa 3 nhánh qua split_comparison_query
   │                                              (guardrail 3 điều kiện), gộp đa nhánh sau truy xuất
   ▼
[4] True Hybrid Search                        ──► BM25 (từ khóa, tokenizer kép)
   │                                              + ChromaDB (bge-m3, cosine)
   │                                              → EnsembleRetriever gộp bằng RRF
   │                                              (top_k / trọng số / lọc nguồn THEO ROUTER)
   ▼
[5] Sinh câu trả lời (Gemini / Qwen local)    ──► prompt biến thể theo loại câu hỏi;
                                                  câu trả lời + trích dẫn Điều/Khoản;
                                                  thiếu căn cứ → Soft Refusal;
                                                  Gemini hết quota → Local Qwen (nhãn FALLBACK)
```

Về tầng phân loại ([0]) và tách truy vấn con ([3]):

- **Công tắc `ENABLE_CLASSIFIER`** (biến môi trường, mặc định `0`): `0` = bỏ qua tầng [0] và [3], pipeline chạy đúng hành vi cũ 100%; `1` = phân loại chạy **trước** chuẩn hóa, router (`src/retrieval/router.py`) ánh xạ cặp nhãn → cấu hình truy xuất (số chunk, trọng số RRF, lọc nguồn theo chủ đề) và generator đổi prompt theo loại câu hỏi. Nguyên tắc an toàn: cấu hình mặc định của router trùng cấu hình chung, nhãn `NGOAI_PHAM_VI` **không** bỏ qua truy xuất (chỉ đổi prompt khuyến khích từ chối) nên không có đường nào "giết" pipeline — mọi lỗi phân loại suy giảm mềm về cấu hình chung.
- **Tách truy vấn con** (`split_comparison_query` trong `src/retrieval/retrieval.py`): chỉ chạy cho câu được gán nhãn `SO_SANH`, tách trên câu đã chuẩn hóa (chưa mở rộng), tối đa 3 nhánh; kết quả truy xuất của các nhánh được gộp theo thứ hạng RRF trước khi dựng ngữ cảnh.

Hai cơ chế xuyên suốt các tầng:

- **`fold()`** (`src/text_utils.py`) — bỏ dấu thanh dùng chung cho mọi tầng: câu hỏi có dấu vẫn khớp được chunk OCR mất dấu ở tầng truy xuất và tầng đánh giá.
- **Oversampling** — mỗi lượt truy xuất lấy về `top_k × 2` ứng viên; chỉ `top_k` đứng đầu theo thứ hạng RRF được đưa vào generator, phần còn lại phục vụ đo Hit@K.

Đặc tả chi tiết (công thức BM25/cosine/RRF, sơ đồ 6 tầng, đặc tả classifier/router/sub-query/prompt biến thể ở mục 6, bảng biến môi trường): xem `docs/architecture/SYSTEM_ARCHITECTURE.md` (`.txt`/`.docx` sinh lại bằng `scripts/export_architecture.py` khi cần nộp kèm).

---

## 2. Cấu trúc thư mục

```
hybrid_rag_agu/
│
├── data/
│   ├── corpus/              # 29 tài liệu ở 3 tầng (24 PDF + 5 DOCX), nguồn xây Vector DB
│   │   ├── Tầng 1/          # Quy chế/quyết định chính thức (6 PDF)
│   │   ├── Tầng 2/          # Kế hoạch, thông báo ngày (6 PDF)
│   │   ├── cac_file_bo_xung_khac/   # Thông báo học phí, CTĐT, khảo sát... (12 PDF + 5 DOCX;
│   │   │                        #   3 PDF mới commit 28-10 CHƯA ingest/index)
│   │   └── ghi_chu_hoc_them.txt     # Bài học tự sinh khi dùng chế độ test & học
│   ├── evaluation/          # Bộ benchmark + checklist kiểm tra tay
│   │   ├── benchmark_100_questions_v3.json  # 100 câu v3 — 13 khóa (12 khóa v2 + question_type),
│   │   │                                    #   benchmark chính thức của lượt A/B (P4)
│   │   ├── benchmark_100_questions_v2.json  # 100 câu v2 — MẶC ĐỊNH của src/assessment/evaluation.py
│   │   ├── benchmark_100_questions.json     # 100 câu v1
│   │   ├── benchmark_50_questions.json/.md  # 50 câu (mặc định của scripts/benchmark_chunking.py)
│   │   ├── benchmark_15_questions.json/.md  # bộ 15 câu đầu tiên
│   │   ├── benchmark_questions.json         # 15 câu GUI tự sinh (schema 10 khóa cũ)
│   │   ├── reference/       # File quy chế mẫu (không index — chỉ dùng đối chiếu)
│   │                        # Phân loại benchmark: v3 = CHÍNH THỨC cho lượt A/B (P4);
│   │                        #   v2 = mặc định của src/assessment/evaluation.py; v1 / 50 câu /
│   │                        #   15 câu / benchmark_questions.json = lịch sử, khảo sát và demo GUI
│   ├── loop/                # Vòng lặp P5 tự kiểm chứng (sổ đăng ký round ở data/loop/README.md)
│   │   ├── testset_v1.jsonl # 811 item đo chốt (câu + gold chunk + nguồn) + testset_v1_manifest.json
│   │   ├── README.md        # Đăng ký TRƯỚC từng round + luật quyết định (r0 → r21/r21b)
│   │   ├── rounds/          # r0…r21b_B: full.jsonl, verdicts_full.jsonl, round_summary, env_sidecar
│   │   ├── rounds_v2/       # Artifact chấm lại bằng trọng tài v2 `2911c69f740d`:
│   │                        #   1.000 verdict full (10 round), rescore truy xuất, r16 + gate của nó
│   │   ├── diag/            # Chẩn đoán từng phép đo (reranker_paired, corpus_diagnostics, b1_cprime…)
│   │   └── noise_floor.json # Băng nhiễu lịch sử ±3 item/100 (pha sinh)
│   ├── training/            # Dữ liệu huấn luyện local: classifier/retrieval baseline, SFT (Alpaca),
│   │                        #   probe bộ nhớ t4b_* — mô tả trong data/training/README.md
│   └── learning/                # Cặp (câu gốc → câu chuẩn hóa) cho Qwen học — GUI tự sinh
│       └── normalization_pairs.json   #   (28-10: path cũ data/normalization_pairs.json)
│
├── src/                     # 29-10 Phase 3: 19 module dời vào 5 subpackage, 4 tệp ở lại gốc
│                            #   (bảng old→new: docs/RESTRUCTURE_MAP.md mục 6.2)
│   ├── __init__.py
│   ├── text_utils.py        # fold() — bỏ dấu thanh dùng chung (OCR ↔ truy vấn có dấu)
│   ├── answer_guard.py      # Guard đáp án: phát hiện bịa/leak theo grounding + token overlap
│   │                        #   (cờ ENABLE_ANSWER_GUARD / NORMALIZE_SANITY_GUARD)
│   ├── generator.py         # Sinh câu trả lời: Gemini + cache + fallback Qwen + Soft Refusal
│   │                        #   + prompt biến thể theo loại câu hỏi
│   │                        #   (ở lại gốc: `answer_guard` import `REFUSAL_TEXT` lúc chạy)
│   ├── core/                # Tầng vào đề bài + điều phối
│   │   ├── pipeline.py      # Nối các tầng, oversampling, tự lùi về vector search khi BM25 lỗi
│   │   ├── classifier.py    # Tầng 0: phân loại câu hỏi 2 nhãn (14 chủ đề + 4 loại) —
│   │   │                    #   Qwen few-shot + guardrail 3 lớp, suy giảm mềm khi lỗi
│   │   ├── query_normalizer.py  # Tầng 1: chuẩn hóa câu hỏi bằng Qwen + active learning
│   │   ├── config.py        # Điểm đọc biến môi trường duy nhất của `src/` (danh sách TRACKED_ENV)
│   │   ├── cache_policy.py  # Khóa `policy` cho cache tầng sinh — chỉ thêm khi ngưỡng lệch mặc định
│   │   └── faithfulness_heuristic.py  # Faith heuristic token-overlap (không cần LLM judge)
│   ├── indexing/            # Nạp corpus → cắt đoạn → chỉ mục
│   │   ├── loader.py        # Đọc đệ quy .txt/.pdf/.docx + OCR PDF scan, gắn metadata tier
│   │   ├── chunking.py      # Cắt đoạn: DocumentChunker (ingest) + 3 chiến lược thực nghiệm
│   │   │                    #   fixed / recursive / structure-aware qua chunk_with_strategy()
│   │   └── contextual_header.py  # Gắn header Chương/Điều/Khoản (ENABLE_CONTEXTUAL_HEADER, TẮT)
│   ├── retrieval/           # Truy xuất Hybrid + xếp hạng lại
│   │   ├── vector_db.py     # bge-m3 + ChromaDB; BM25 tokenizer; EnsembleRetriever (RRF)
│   │   ├── retrieval.py     # Tầng 2: từ điển đồng nghĩa + expand_query_with_synonyms()
│   │   │                    #   + split_comparison_query() tách truy vấn con cho SO_SANH
│   │   ├── router.py        # Ánh xạ nhãn → cấu hình truy xuất (top_k, trọng số RRF,
│   │   │                    #   lọc nguồn theo chủ đề); mặc định = cấu hình chung
│   │   └── reranker.py      # Cross-encoder bge-reranker-v2-m3 pool 20→top-k (ENABLE_RERANKER, mặc định TẮT)
│   ├── generation/          # Tầng sinh + chính sách từ chối
│   │   ├── local_slm.py     # Wrapper Ollama + guardrail chống lệch nghĩa khi chuẩn hóa
│   │   ├── refusal_policy.py  # Chính sách từ chối: soft refusal + biến thể decoupled (mặc định TẮT)
│   │   └── evidence_selection.py  # Cửa sổ bằng chứng 3–5 câu thay full-context (ENABLE_EVIDENCE_SELECTION, TẮT)
│   └── assessment/          # Đo lường & kiểm chứng
│       ├── evaluation.py    # Đánh giá định lượng: Hit@K, MRR, Citation F1, Faithfulness...
│       │                    #   (+ cờ --with-classifier và thống kê A/B)
│       ├── evaluate_classifier.py  # Đo accuracy bộ phân loại trên benchmark v3 → logs/classifier/
│       └── analyze_ab.py    # Phân tích 2 JSON A/B → outputs/ab_comparison.md + figures/
│
├── ui/
│   ├── app.py               # GUI 3 tab: Tra cứu / Nạp dữ liệu / Vừa test vừa học
│   └── demo_streamlit.py    # Demo Streamlit so sánh 3 chiến lược chunking (chạy: streamlit run ui/demo_streamlit.py)
│
├── tests/                   # 1.549 unit test pass + 5 skipped (lượt postflight r21b 28-10)
│                            #   — offline hoàn toàn (chunking, pipeline, classifier, router,
│                            #   local_slm, evaluation, gate/verify vòng lặp, GUI flag...)
│
├── tools/
│   ├── loop/                # Máy chạy vòng P5: run_round.py, gate.py, verify.py (trọng tài
│   │                        #   deterministic, chữ ký `2911c69f740d`), testset.py, attribute.py, chains/
│   ├── eval/                # Khung câu hỏi thật: classify_real_questions.py, score_real_questions.py,
│   │                        #   report_metrics.py, real_questions.jsonl
│   ├── diag/                # ~40 script chẩn đoán/tái kiểm chỉ-đọc (artifact_manifest,
│   │                        #   evidence_pack_check, final_number_audit, rescore_rounds_v2, reocr_vie…)
│   ├── train/               # Huấn luyện + sinh dữ liệu: classifier baseline v1–v3, retrieval
│   │                        #   baseline, train_sft_lora.py (venv_train, CUDA),
│   │                        #   build_sft_from_round.py · build_training_data.py · validate_training_data.py
│
├── scripts/                 # Công cụ phụ chạy từ dòng lệnh (mọi lệnh chạy từ gốc repo)
│   ├── learn.py             # Chế độ test & học qua CLI: sai thì dạy lại, ghi log logs/learning/
│   ├── benchmark_chunking.py# Benchmark 3 chiến lược chunking → logs/benchmark/
│   └── export_architecture.py # Xuất docs/architecture/SYSTEM_ARCHITECTURE.md sang .txt/.docx (biên nhận logs/export/)
│
├── logs/                    # MỌI file tự sinh khi chạy — quy ước chi tiết ở logs/README.md
│   ├── benchmark/           # Output của scripts/benchmark_chunking.py (log, results_all.json, chroma_*/) — xóa được
│   ├── classifier/          # Output của src/assessment/evaluate_classifier.py (accuracy_report.md,
│   │                        #   results.json, 2 ma trận nhầm lẫn CSV)
│   ├── export/              # Biên nhận export SYSTEM_ARCHITECTURE — xóa được
│   ├── learning/            # learning_log.csv — lịch sử "học thêm" (GIỮ, được git track)
│   └── feedback/            # user_feedback.json — phản hồi người dùng từ GUI (GIỮ, được git track)
│
├── outputs/                 # Kết quả CHỐT dùng cho báo cáo (git track)
│   ├── evaluation_results.json + evaluation_summary.md        # Lượt đánh giá chính
│   ├── ab_results_{without,with}_classifier.json              # 2 lượt A/B (P4)
│   ├── ab_comparison.md + ab_summary_*.md                     # Bảng so sánh A/B chốt
│   ├── figures/                                               # 3 biểu đồ P4.3 (PNG)
│   └── baseline_2026-10-20/                                   # Snapshot baseline pipeline cũ (P0.2)
│
├── dev/                     # Tài liệu & quy tắc phát triển (không phải mã chạy)
│   ├── .maestro/playbooks/  # Quy tắc cộng tác đa-agent (4 group + base_prompt) — xem mục 7
│   └── prompts/             # Playbook nhiệm vụ P0→P5 + PROGRESS (lịch sử)
│
├── chroma_db/               # ChromaDB đã persist — index SẢN XUẤT 361 chunk (ingest.py tự sinh — gitignored)
│                            #   (đường dẫn production `./chroma_db`, đặt qua CHROMA_PERSIST_DIR)
├── indexes/experimental/    # Các index thực nghiệm, KHÔNG phải đích production (gitignored)
│   ├── chroma_db_vie/       #   re-OCR tiếng Việt, 342 chunk — CHƯA kích hoạt
│   │                        #     (mất neo vàng 48,81%, chờ PA-17 re-anchor)
│   └── chroma_db_headers_old/  # Snapshot index cho phép đo header r13
├── .cache/ocr/rapidocr/     # Cache kết quả OCR (tự sinh, xóa được — lần nạp sau sẽ OCR lại)
├── .cache/ocr/easyocr_vie/  # Cache OCR EasyOCR `vi` lượt re-OCR 24-10 (13 tệp/124 trang — gitignored)
├── .generation_cache/       # Cache câu trả lời Gemini (tự sinh, xóa được — lượt sau sẽ gọi API lại)
├── models/                  # Trọng số train local: classifier_baseline{,_v2,_v3}, retrieval_baseline,
│                            #   qwen25_05b_sft_adapter (mô tả trong models/README.md)
├── tmp/                     # Artifact phiên làm việc (controller, sidecar, log, bản sao index A/B)
│                            #   — một số tệp được docs/EXPERIMENTS.md trích làm nguồn, không xóa chúng
│
├── main.py                  # Chế độ chạy thực: CLI tương tác, hỏi liên tục
├── ingest.py                # Script nạp corpus vào ChromaDB (chạy trước main.py)
├── ARTIFACT_MANIFEST.json   # Manifest ghim SHA-256 artifact round — kiểm bằng tools/diag/artifact_manifest.py --check
├── docs/
│   ├── EXPERIMENTS.md       # Bảng A (kết quả khoa học) + Bảng B (quy trình/dụng cụ), 7 cột có chữ ký trọng tài
│   ├── DECISION_LOG.md      # Sổ quyết định đầy đủ: ngữ cảnh, giả thuyết đăng ký trước, PA-1…PA-51
│   ├── EVIDENCE_PACK.md     # + evidence_pack.json — gói bằng chứng ghim byte (kiểm: evidence_pack_check.py)
│   ├── PA_TRIAGE.md         # Hàng đợi đề xuất PA chờ duyệt
│   ├── REPRODUCE.md         # Lệnh tái lập kết quả đã công bố
│   ├── ARCHITECTURE.md      # Kiến trúc cập nhật theo vòng lặp P5
│   ├── RESTRUCTURE_MAP.md   # Bảng ánh xạ đường dẫn cũ → mới (đợt tái cấu trúc 28-10)
│   ├── architecture/        # SYSTEM_ARCHITECTURE.md — đặc tả kiến trúc 6 tầng (nguồn duy nhất)
│   ├── spec/                # TAXONOMY.md — 14 chủ đề + 4 loại + luật gán (cổng P1.1)
│   ├── planning/            # ROADMAP.md — định hướng làm lại đồ án + 3 câu hỏi nghiên cứu + GATE
│   ├── guides/              # NORMALIZATION_ACTIVE_LEARNING · TROUBLESHOOTING_GUI · LAYOUT_OPTIMIZATION
│   ├── archive/             # Báo cáo lịch sử (test_final.md, AUTONOMY_LOG, MORNING_REPORT...)
│   ├── giang_day/           # 11 bài giảng nội bộ theo từng tầng pipeline
│   └── bao_cao/             # Bản nháp chương báo cáo (chương 3 kiến trúc, chương 4 thực nghiệm,
│                            #   outline chương 1/2/5) — mọi số liệu có nguồn ở outputs//logs/
│
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

**Riêng cho demo Streamlit** (mục 5.9) cần thêm 2 gói chưa đưa vào `requirements.txt`:

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

Khai báo API key và cấu hình trong file `.env` (toàn bộ key đều có trong `.env.example` kèm chú thích).
Muốn dùng theo chế độ (vận hành / offline / đánh giá / thí nghiệm) thì chép thêm profile tương ứng
trong `config/` — xem `config/README.md`; profile vận hành không bật cờ thí nghiệm nào.

```env
# Bắt buộc
GEMINI_API_KEY=your_gemini_api_key_here

# Có giá trị mặc định — chỉ khai báo khi muốn đổi
GEMINI_MODEL=gemini-2.5-flash
GEMINI_JUDGE_MODEL=              # model giám khảo Faithfulness của src/assessment/evaluation.py
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
RAG_TOP_K=6
# (tùy chọn) đổi gốc thư mục; trống = mặc định trong repo. Đường dẫn tương đối
# được hiểu theo gốc dự án, không theo CWD (src/core/paths.py).
RAG_DATA_DIR=
RAG_CORPUS_DIR=
RAG_EVALUATION_DIR=
RAG_LOGS_DIR=
RAG_OUTPUTS_DIR=
RAG_CACHE_DIR=

# True Hybrid Search — mặc định đã bật, chỉ khai báo khi muốn tắt/đổi trọng số
ENABLE_HYBRID_SEARCH=1           # 0 = tắt BM25, chỉ dùng vector search thuần
ENABLE_QUERY_EXPANSION=1         # 0 = tắt mở rộng từ đồng nghĩa
BM25_WEIGHT=0.5
CHROMA_WEIGHT=0.5

# Tầng phân loại câu hỏi + router truy xuất (P3.2) — mặc định tắt
ENABLE_CLASSIFIER=0              # 1 = phân loại câu hỏi (2 nhãn) + truy xuất theo lớp
CLASSIFIER_MODEL=                # trống = dùng chung OLLAMA_MODEL
CLASSIFIER_TIMEOUT=20            # giây — timeout gọi Ollama cho tầng phân loại

# Tối ưu quota & chống sập khi demo (mặc định đã bật)
GENERATION_CACHE=1
QWEN_FALLBACK=1

# OCR cho PDF scan ảnh (đều có mặc định)
OCR_ENABLED=1
OCR_DPI=200
OCR_MIN_CHARS_PER_PAGE=50
OCR_CACHE_DIR=./.cache/ocr/rapidocr
```

Vài giá trị cần lưu ý khi viết phần thực nghiệm:

- `GEMINI_MAX_TOKENS=4096` — `gemini-2.5-flash` là model "thinking": token suy luận nội bộ bị trừ **vào cùng** ngân sách `max_output_tokens`. Đo thực tế một lượt trả lời tốn 763 token thinking + 73 token trả lời, nên đặt 1024 sẽ làm câu trả lời **bị cắt giữa chừng**. Thư viện `google-generativeai` 0.8.6 chưa có `thinking_config` để tách riêng ngân sách, chỉ còn cách đặt lớn. `generator.py` vẫn in cảnh báo nếu `finish_reason = MAX_TOKENS`.
- `RAG_TOP_K=6` — mặc định vận hành **duy nhất** (`src/core/config.py::DEFAULT_TOP_K`) cho số chunk ngữ cảnh mỗi lượt hỏi; `main.py`/router đọc biến này, flag `-k/--top-k` ghi đè. `src/assessment/evaluation.py` và `scripts/benchmark_chunking.py` có cờ `--top-k` riêng (mặc định 6 và 3); GUI hiển thị đúng mặc định 6. Không đặt biến thì `main`/router dùng 6; `scripts/benchmark_chunking.py` là thí nghiệm chunking riêng, giữ mặc định 3.
- Đường dẫn dữ liệu — `src/core/paths.py` là nguồn duy nhất: `PROJECT_ROOT` suy từ vị trí file và mọi thư mục (`data/`, `logs/`, `outputs/`, `.cache/`, `chroma_db/`) là đường dẫn tuyệt đối dưới gốc. Đường dẫn tương đối trong `.env` (`CHROMA_PERSIST_DIR=./chroma_db` hoặc `RAG_*_DIR=...`) được hiểu **theo gốc dự án**, nên chạy `python main.py` từ root, từ IDE hay từ thư mục khác đều dùng cùng một index/tệp. Biến `RAG_*_DIR` để trống = giữ mặc định.
- `ENABLE_HYBRID_SEARCH` / `ENABLE_QUERY_EXPANSION` — hai công tắc của True Hybrid Search, mặc định **bật**; đặt `0` để lùi về vector search thuần (tiện so sánh có/không hybrid trong phần thực nghiệm). `BM25_WEIGHT` / `CHROMA_WEIGHT` là trọng số RRF của hai nhánh truy xuất.
- `ENABLE_CLASSIFIER` / `CLASSIFIER_MODEL` / `CLASSIFIER_TIMEOUT` — công tắc tầng phân loại câu hỏi (2 nhãn) + router truy xuất, mặc định `ENABLE_CLASSIFIER=0` (pipeline chạy đúng hành vi cũ 100%, không tốn thêm lần gọi Ollama nào). `1` = bật phân loại: router chọn cấu hình truy xuất theo nhãn, tách truy vấn con cho câu `SO_SANH`, prompt biến thể theo loại; mọi lỗi phân loại suy giảm mềm về cấu hình chung. `CLASSIFIER_MODEL` để trống thì dùng chung `OLLAMA_MODEL`; `CLASSIFIER_TIMEOUT` là timeout gọi Ollama, mặc định 20 giây.

---

## 4. Chuẩn bị dữ liệu

### 4.1. Đưa tài liệu vào thư mục `data/corpus/`

Loader (`src/indexing/loader.py`) quét đệ quy thư mục `data/corpus/`, hỗ trợ `.txt` (utf-8), `.pdf` (pypdf) và `.docx` (python-docx). Hiện trạng corpus: **29 file (24 PDF + 5 DOCX), không còn file `.doc` legacy** — 3 PDF commit 28-10 (`dh24-ky`, `qd-1543-BGDDT`, `so-tay-sktt`) chưa ingest, index sản xuất vẫn 361 chunk. File `.doc` (Word 97-2003) không trích xuất được — hãy `Save As` sang `.docx`.

PDF dạng scan ảnh thì loader **tự động OCR** mà không cần cài phần mềm hệ thống:

- **Render trang → ảnh:** `pypdfium2` (PDFium đóng gói sẵn trong wheel). Không dùng `pdf2image` vì thư viện đó bắt buộc cài **Poppler** ở cấp hệ thống, trái ràng buộc "chỉ cần pip".
- **Nhận diện ký tự:** `rapidocr-onnxruntime` — model PP-OCR dạng ONNX kèm sẵn trong package, chạy bằng `onnxruntime` trên CPU, không cần Tesseract. Engine được nạp một lần cho cả tiến trình.
- **Điều kiện kích hoạt — xét theo từng trang, không theo từng file:** trang nào `pypdf` trích ra dưới `OCR_MIN_CHARS_PER_PAGE` ký tự (mặc định 50) thì trang đó được OCR. Nhờ vậy PDF vừa có trang text vừa có trang chụp ảnh chỉ bị OCR đúng phần scan.
- **Cache:** kết quả OCR ghi vào `.cache/ocr/rapidocr/<tên_file>__<hash>.json`, khóa theo (kích thước, mtime, dpi, ngưỡng) nên sửa file PDF là cache tự hỏng. Bắt buộc phải có vì `scripts/learn.py` rebuild collection sau mỗi bài học — không cache thì mỗi lần học lại phải OCR lại toàn bộ. Xóa thư mục này để OCR lại từ đầu.
- **Tùy chọn trong `.env`:** `OCR_ENABLED` (`0` = tắt, file scan sẽ bị bỏ qua kèm cảnh báo), `OCR_DPI` (mặc định 200), `OCR_MIN_CHARS_PER_PAGE` (50), `OCR_CACHE_DIR` (`./.cache/ocr/rapidocr`).

**Giới hạn chất lượng (cần ghi vào phần thực nghiệm của đề tài):** model PP-OCR kèm `rapidocr-onnxruntime` bắt đúng bố cục và chữ quốc ngữ nhưng **làm mất phần lớn dấu thanh** — "Điều 4. Hệ thống tổ chức" thành "Dieu 4. He thong to chuc". Hệ quả và cách xử lý trong mã nguồn:

| Ảnh hưởng | Xử lý |
|---|---|
| Mốc `Điều N.` không khớp regex → tài liệu rơi xuống fallback, mất cấu trúc Điều/Khoản | `ARTICLE_HEADING_RE` (`src/indexing/chunking.py`) nhận cả dạng mất dấu (`Dieu 4.`) và dạng lỗi font PDF (`Ðiều 4.`); `canonical_article()` trả tiêu đề chunk về đúng chính tả `Điều N.` |
| Trích dẫn sinh ra từ ngữ cảnh không dấu có thể sai chính tả | Tiêu đề chunk đã được chuẩn hóa thành `Điều N.` nên Generator trích dẫn đúng |
| Câu hỏi có dấu đầy đủ khó khớp chunk mất dấu khi truy xuất | Mọi truy vấn được `fold()` bỏ dấu trước khi so khớp/embed, và BM25 tokenizer sinh song song token nguyên văn + token bỏ dấu. Đo nhanh offline trên 7 câu hỏi khớp tài liệu OCR: Hit@5 từ 0/7 lên 7/7, top-1 đúng cả 7 |

Tăng `OCR_DPI` **không** cải thiện dấu: đo trên cùng một trang của `1054-qd-dhag-2020-09-28.pdf` cho 150/200/300 dpi lần lượt 2.012/2.080/2.076 ký tự nhưng chỉ 0/1/2 ký tự có dấu thanh. Nút thắt là model nhận diện, không phải độ phân giải — muốn giữ dấu đầy đủ phải đổi sang model OCR tiếng Việt chuyên biệt (ngoài phạm vi thuần pip).

### 4.2. Phân tầng tài liệu và chiến lược cắt đoạn

**Metadata phân tầng:** tên thư mục con cấp 1 trong `data/corpus/` chính là `tier` của tài liệu (`Tầng 1`, `Tầng 2`, `cac_file_bo_xung_khac`); file nằm ngay gốc `data/corpus/` nhận tier `Khác`. Mỗi chunk lưu vào ChromaDB mang bộ metadata `{"tier", "source", "chunk_id"}`, nên có thể đo Recall@K riêng cho từng tầng:

```python
vector_db.similarity_search(query, k=5, filter={"tier": "Tầng 2"})
```

`src/indexing/chunking.py` hiện có **hai lớp API** phục vụ hai mục đích khác nhau:

**Lớp 1 — `DocumentChunker` (đường sản xuất, `ingest.py` dùng):** tự chọn chiến lược theo nội dung từng văn bản qua `has_article_structure()`:

| Văn bản | Chiến lược | Kết quả |
|---|---|---|
| Quy chế/quy định có `Điều N.` đầu dòng | `structure_aware_chunking` | Mỗi Điều một chunk; Điều quá dài (nuốt cả Phụ lục) được cắt tiếp thành `(phần i/n)`; phần mở đầu (quốc hiệu, số hiệu, căn cứ) thành chunk riêng |
| Thông báo, kế hoạch, công văn, đơn, bản mô tả CTĐT | `fallback_chunking` | Cắt theo ranh giới câu, gộp tới ~1200 ký tự (~600 token bge-m3), overlap 150 ký tự giữa các chunk liền kề |

Mọi chunk đều mang tiền tố `[Tên văn bản]` (và `- [Điều N.]` nếu có) để giữ ngữ cảnh khi truy xuất.

**Lớp 2 — ba chiến lược cắt đoạn cho thực nghiệm (API `chunk_with_strategy`):** dùng chung bởi `scripts/benchmark_chunking.py` và `ui/demo_streamlit.py`, cho phép so sánh công bằng trên cùng một tokenizer:

| Khóa | Tên | Cách cắt |
|---|---|---|
| `fixed` | Fixed-size | Cắt cứng theo mốc 512 token, overlap 0 |
| `recursive` | Recursive | Cắt đệ quy theo cấp bậc phân tách `"\n\n" → "\n" → câu → từ`, 512 token |
| `structure` | Structure-aware | Cắt theo Điều/Khoản/Điểm; tiền tố metadata phân cấp `[Tên văn bản] - [Điều N.] - [Khoản x-y] - [Điểm a-b]` ở ĐẦU chunk; Điều vượt ngân sách được cắt tiếp đệ quy thành `(phần i/n)` |

Đặc điểm chung của cả 3 chiến lược: mốc `DEFAULT_MAX_TOKENS = 512`, đếm token bằng tokenizer HuggingFace của chính bge-m3 (`get_token_counter("BAAI/bge-m3")`, lỗi thì lùi về đếm từ), và **khóa nguyên khối bảng Markdown** (`lock_markdown_tables=True`) — bảng dài hơn ngưỡng vẫn giữ thành 1 chunk thay vì cắt làm hai, vì hàng tách khỏi tiêu đề cột thì embedding vô nghĩa.

Trên corpus tại lượt dựng 16/10/2026 (26 tài liệu), 3 chiến lược cho 3 index khác nhau: **fixed = 182 chunks, recursive = 189, structure = 378** (chính là số liệu so sánh của demo; 3 PDF thêm 28-10 chưa dựng lại).

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

Khi `ENABLE_CLASSIFIER=1` (khai báo trong `.env` — pipeline đọc cờ này lúc khởi tạo), một bước phân loại + router chạy **trước** bước chuẩn hóa; kết quả in thêm khối "Phân loại & Cấu hình" (2 nhãn + cấu hình truy xuất router đã chọn + các nhánh tách truy vấn con nếu có). Tắt cờ thì không có khối này và luồng đúng bảng trên.

Các lệnh trong vòng lặp: `help`/`h`/`?` (in hướng dẫn), `exit`/`quit`/`thoat`/`thoát`/`q` (kết thúc).

**Về tính trung thực của câu trả lời (chống ảo giác):** `PROMPT_RULES` trong `src/generator.py` ràng buộc Gemini chỉ dùng ngữ cảnh được cấp, mỗi ý phải kèm căn cứ dạng `(Điều 12, Khoản 3 — <tên văn bản>)` lấy từ dòng `Nguồn:` thật (không được viết "(Ngữ cảnh 1)"), ưu tiên tier cao hơn khi các nguồn mâu thuẫn, và nếu thiếu căn cứ thì trả lời đúng một câu từ chối `REFUSAL_TEXT` = `"Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này."` (cơ chế **Soft Refusal**: ngữ cảnh rỗng thì trả về câu này ngay mà không gọi API). Chuỗi này là hằng số module để tầng đánh giá đối sánh được.

**Tiết kiệm quota & chống sập khi demo (caching + fallback Local Qwen trong `generator.py`):**

- **Response caching:** trước khi gọi API, `generate_answer` tính SHA-1 của `{model, temperature, prompt}` và tra `./.generation_cache/<sha1>.json` — trúng thì trả lời ngay, tốn **0 request quota**. Key bám theo nội dung prompt nên thêm/sửa tài liệu rồi ingest lại là cache cũ tự vô hiệu, không cần dọn tay. Chỉ câu trả lời **nguồn Gemini** được cache; muốn đo latency thật (không tính thời gian đọc cache) hoặc ép sinh lại thì đặt `GENERATION_CACHE=0` trong `.env` hoặc xóa thư mục `.generation_cache/`.
- **Fallback Local Qwen:** Gemini trả về 429/hết quota ngày/phút hay sự cố 5xx, `generate_answer` **không văng lỗi** mà chuyển câu hỏi + các chunk ngữ cảnh sang Qwen trên Ollama (num_ctx 8192 để không bị cắt ngữ cảnh), gắn nhãn đầu câu trả lời `[Cảnh báo: Gemini đã hết quota — câu trả lời này được tổng hợp tạm thời bằng Local Qwen ...]` để người nghe demo phân biệt ngay. Câu fallback **không được cache** để lượt chạy sau vẫn được thử lại Gemini thật. Cả Ollama cũng chết thì mới ném `GeneratorError` — `main.py` đã bắt nên vòng lặp vẫn sống. Tắt cơ chế này bằng `QWEN_FALLBACK=0`.
- Trong `src/assessment/evaluation.py` và `scripts/benchmark_chunking.py`, fallback bị **tắt bắt buộc** khi chạy chế độ Gemini (`qwen_fallback = False`): nếu để bật, câu trả lời Qwen sẽ làm nhiễu các chỉ số Citation/Faithfulness vốn đang đo chất lượng pipeline Gemini.

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
3. Nếu có câu chuẩn hóa (auto-fill từ kết quả, sửa được trước khi lưu): thêm cặp (câu gốc → câu chuẩn hóa) vào `data/learning/normalization_pairs.json` — Qwen tự học ở các lượt sau (active learning).
4. Nếu tick "học ngay": ghi bài học vào `data/corpus/ghi_chu_hoc_them.txt`, rebuild ChromaDB tại chỗ và ghi log vào `logs/learning/learning_log.csv`.

Chi tiết cơ chế học chuẩn hóa: `docs/guides/NORMALIZATION_ACTIVE_LEARNING.md`; sự cố thường gặp của GUI: `docs/guides/TROUBLESHOOTING_GUI.md`; ghi chú tối ưu layout Tab 3: `docs/guides/LAYOUT_OPTIMIZATION.md`.

### 5.4. Chế độ test & học (learn — `scripts/learn.py`)

Vòng lặp hỏi - đáp với người làm trọng tài (bản CLI của Tab 3):

```bash
python scripts/learn.py
```

Luồng hoạt động: nhập câu hỏi → hệ thống trả lời → bạn đánh giá (`Enter`/`y` = đúng, `n` = sai). Nếu sai, dán thông tin đúng (kết thúc bằng một dòng trống); hệ thống sẽ:

1. Ghi bài học vào `data/corpus/ghi_chu_hoc_them.txt` dưới dạng mục `Điều 1001., 1002., ...` tự sinh, nhờ đó mỗi bài học thành một chunk độc lập và trích dẫn được theo số Điều.
2. Rebuild collection ChromaDB ngay tại chỗ (tái dùng bge-m3 đã nạp, không reset thư mục).
3. Ghi 1 dòng log vào `logs/learning/learning_log.csv`: thời gian, câu hỏi, đáp án sai, thông tin đã học, số chunks trước/sau.

Cả `ingest.py` và learn mode đều xóa collection cũ trước khi index, nên chạy lại nhiều lần không bao giờ nhân đôi chunks. Muốn dọn các mục đã học, sửa tay `ghi_chu_hoc_them.txt` rồi chạy lại `python ingest.py`.

### 5.5. Đánh giá định lượng (`src/assessment/evaluation.py`)

Chạy đúng pipeline sản xuất (phân loại → Qwen chuẩn hóa → mở rộng truy vấn → True Hybrid Search → Generator → giám khảo) trên từng câu của bộ benchmark — **mặc định là `data/evaluation/benchmark_100_questions_v2.json` (100 câu)**, đổi bằng cờ `--benchmark`. Mỗi câu hỏi v2 đúng 12 khóa: `id, category, tier, in_corpus, source_document, raw_query, normalized_query, expected_answer, expected_citations, ground_truth_answer, ground_truth_citation, supplement_if_wrong`; benchmark v3 có thêm khóa thứ 13 `question_type` (xem mục 5.7).

Hệ thống đo ba tầng chỉ số:

| Tầng | Chỉ số | Cách tính |
|---|---|---|
| Truy xuất | **Hit@3 / Hit@5 / Hit@6, MRR** | Mỗi câu pipeline truy xuất oversampled (2× cửa sổ generator); Hit@K = K kết quả đầu có chứa chunk thuộc `source_document` ground truth không; MRR = 1/thứ hạng chunk đúng đầu tiên trong toàn bộ cửa sổ truy xuất. So khớp tên nguồn **sau khi bỏ dấu** (`fold()`) |
| Trích dẫn | **Citation Precision / Recall / F1 / Exact Match** | Tập mã `Điều N [Khoản M]` rút từ câu trả lời so với `expected_citations`; hai bên quy về cùng token không dấu nên `"Điều 12"` khớp cả dạng OCR `"dieu 12"`; ghép cặp theo maximum-weight matching (khớp đủ Điều+Khoản = 1.0, trùng Điều một phía thiếu Khoản = 0.5) |
| Trung thực | **Faithfulness** | Gemini giám khảo (temperature 0, JSON mode, **không** mang system instruction của Generator) tách câu trả lời thành các khẳng định nguyên tố và đối chiếu từng khẳng định với ngữ cảnh; điểm = tỉ lệ khẳng định được hỗ trợ. Kèm `number_support` không tốn API: tỉ lệ con số trong câu trả lời xuất hiện trong ngữ cảnh |

Câu có `in_corpus=false` kiểm tra hành vi từ chối: hệ thống phải trả lời bằng câu chứa `REFUSAL_MARKER`, trả lời ra nội dung thì bị tính là **ảo giác ngoài corpus**. Trường `normalized_query` trong benchmark cho phép đo thêm chỉ số khắt khe `normalization_accuracy` (so khớp chuỗi chính xác); chỉ số chính hiện dùng là **`normalization_preservation`**: tỉ lệ thực thể (số Điều/Khoản, con số) trong câu hỏi gốc còn nguyên sau chuẩn hóa — so khớp regex không dấu, bỏ qua văn phong, khách quan hơn so khớp chuỗi.

```bash
python src/assessment/evaluation.py                        # benchmark 100 câu v2, top_k=6, có giám khảo Gemini
python src/assessment/evaluation.py --use-qwen-generator   # offline 100%: Local Qwen sinh câu trả lời (không tốn quota)
python src/assessment/evaluation.py --no-judge             # bỏ tầng giám khảo Faithfulness
python src/assessment/evaluation.py --limit 2              # chạy thử nhanh 2 câu đầu, tiết kiệm quota
python src/assessment/evaluation.py --judge-model gemini-3.5-flash-lite
                                                # giám khảo dùng model khác, tách ngân sách quota
python src/assessment/evaluation.py --benchmark data/evaluation/benchmark_50_questions.json
python src/assessment/evaluation.py --output outputs/custom_results.json
python src/assessment/evaluation.py --benchmark data/evaluation/benchmark_100_questions_v3.json \
    --with-classifier --use-qwen-generator --no-judge \
    --output outputs/ab_results_with_classifier.json \
    --summary-output outputs/ab_summary_with_classifier.md
                                                # lượt WITH của A/B — xem mục 5.7
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
- Trước một lượt đánh giá đầy đủ, hạn chế chạy thử `main.py`/`scripts/learn.py` trong cùng ngày vì cùng xài chung quota model generator.
- **Caching làm các lần chạy lại gần như miễn phí:** câu nào đã trả lời thành công bằng Gemini một lần thì các lượt đánh giá sau lấy thẳng từ `.generation_cache/`, chỉ tốn quota cho câu mới và các câu giám khảo. Nếu lượt trước chết giữa chừng vì hết quota ngày, chỉ cần chạy lại đúng lệnh sau khi quota reset — không mất công trả lời lại từ đầu.
- Faithfulness phụ thuộc giám khảo nên khi viết bài cần ghi rõ model giám khảo và prompt (hằng `JUDGE_PROMPT` trong `src/assessment/evaluation.py`) vào phần thực nghiệm.

### 5.6. Đánh giá bộ phân loại (`src/assessment/evaluate_classifier.py`)

Đo accuracy hai nhãn của tầng phân loại trên **100 câu benchmark v3**, dùng `raw_query` thô — đúng đầu vào của pipeline thật. Chạy 100% offline bằng Qwen local qua Ollama, không tốn quota Gemini:

```bash
python src/assessment/evaluate_classifier.py             # 100 câu, 1 lượt — xuất 4 file vào logs/classifier/
python src/assessment/evaluate_classifier.py --runs 2    # 2 lượt kiểm tra ổn định (temperature=0 kỳ vọng giống hệt)
python src/assessment/evaluate_classifier.py --limit 5   # smoke 5 câu đầu
```

Đầu ra `logs/classifier/`: `accuracy_report.md` (accuracy 2 nhãn, per-class precision/recall/F1, macro-F1, bảng lỗi từng câu, phần GT-verify), `results.json` (chi tiết từng câu) và 2 ma trận nhầm lẫn CSV (14 chủ đề, 4 loại câu hỏi). Lưu ý: lượt chạy mới **ghi đè** 4 file này — muốn giữ số liệu đã chốt thì sao chép ra chỗ khác trước.

**Kết quả chốt P2.3 (2026-10-20 — nguồn `logs/classifier/accuracy_report.md`):** accuracy chủ đề **85,0%** (85/100), loại câu hỏi **81,0%** (81/100), macro-F1 69,4%; recall từng lớp thiểu số `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI` đều 100% (precision 33,3% / 100% / 25,0% — model khuynh hướng over-predict lớp hiếm, tác hại thực tế được lượng hóa bằng "tỉ lệ từ chối oan" ở lượt A/B); chạy lại 2 lượt trùng nhãn 100/100 câu.

### 5.7. Đánh giá A/B có/không tầng phân loại (`--with-classifier` + `src/assessment/analyze_ab.py`)

Hai lượt trên cùng benchmark v3, cùng generator, chỉ khác một biến `ENABLE_CLASSIFIER`:

```bash
# Lượt WITHOUT — ép ENABLE_CLASSIFIER=0, hành vi pipeline cũ 100%
python src/assessment/evaluation.py --benchmark data/evaluation/benchmark_100_questions_v3.json \
    --use-qwen-generator --no-judge \
    --output outputs/ab_results_without_classifier.json \
    --summary-output outputs/ab_summary_without_classifier.md

# Lượt WITH — bật ENABLE_CLASSIFIER=1 (router + tách truy vấn con + prompt theo loại)
python src/assessment/evaluation.py --benchmark data/evaluation/benchmark_100_questions_v3.json \
    --with-classifier --use-qwen-generator --no-judge \
    --output outputs/ab_results_with_classifier.json \
    --summary-output outputs/ab_summary_with_classifier.md

# Phân tích so sánh + vẽ 3 biểu đồ (chỉ đọc 2 JSON trên, không gọi API)
python src/assessment/analyze_ab.py
```

Cờ `--with-classifier` đặt `ENABLE_CLASSIFIER=1` cho pipeline; **không truyền cờ thì evaluation ép `ENABLE_CLASSIFIER=0`** nên không bao giờ dính cấu hình lệch từ `.env`. `src/assessment/analyze_ab.py` đọc cứng 2 đường dẫn `outputs/ab_results_{without,with}_classifier.json`, xuất `outputs/ab_comparison.md` và 3 PNG vào `outputs/figures/` (ghi đè — sao chép trước nếu cần giữ lượt cũ).

Kết quả A/B chốt và bảng so sánh đầy đủ: xem mục 8 (Ghi chú) hoặc thẳng `outputs/ab_comparison.md`.

### 5.8. Benchmark 3 chiến lược chunking (`scripts/benchmark_chunking.py`)

Công cụ thực nghiệm trung tâm của đề tài: với **MỖI chiến lược chunking** (fixed / recursive / structure), script chạy trọn vòng trên cùng một testbed — nạp corpus → cắt chunk theo chiến lược đó → dựng một ChromaDB **độc lập** → chạy đúng pipeline sản xuất (Qwen chuẩn hóa → BM25 + bge-m3 RRF → generator, temperature 0) qua từng câu benchmark → đo Hit@3/5/6, MRR, Citation P/R/F1, Latency, dung lượng index → xuất log chi tiết từng câu + ma trận so sánh 3 chiến lược. Mọi hàm chấm điểm được **tái sử dụng** từ `src/assessment/evaluation.py` nên số liệu so sánh trực tiếp được với `outputs/evaluation_summary.md`.

```bash
python scripts/benchmark_chunking.py                        # đủ 3 chiến lược × 50 câu, Gemini
python scripts/benchmark_chunking.py --limit 2              # smoke test nhanh 2 câu
python scripts/benchmark_chunking.py --strategies structure # chỉ một chiến lược
python scripts/benchmark_chunking.py --generator qwen       # 100% offline, không tốn quota
python scripts/benchmark_chunking.py --no-cache             # tắt cache để đo Latency trung thực
python scripts/benchmark_chunking.py --device cuda          # Colab GPU T4
python scripts/benchmark_chunking.py --benchmark data/evaluation/benchmark_100_questions_v2.json
```

Mặc định chạy trên `benchmark_50_questions.json` với `--top-k 3` (generator nhận 3 chunk, cửa sổ đo Hit@K rộng 6 nhờ oversampling ×2). Đầu ra nằm ở **`logs/benchmark/`**:

| File | Nội dung |
|---|---|
| `log_fixed_size.txt` / `log_recursive.txt` / `log_structure_aware.txt` | Log chi tiết từng câu: query + ground truth, chunk truy xuất (kèm cờ GEN và ✓ đúng nguồn), câu trả lời, chỉ số |
| `summary_comparison_report.csv` / `.md` | Ma trận 3 chiến lược × 7 chỉ số chính + bảng chỉ số hạ tầng (số chunk, mean/max tokens, index size) — mở bằng Excel hoặc dán thẳng vào bài báo |
| `results_all.json` | Toàn bộ số liệu thô (meta tham số + per-question) — nguồn dữ liệu **replay** của demo Streamlit và để vẽ biểu đồ/chấm lại sau |
| `chroma_fixed/` / `chroma_recursive/` / `chroma_structure/` | Vector store độc lập của từng chiến lược (xóa được, chạy lại tự dựng) |

Lưu ý quota: 50 câu × 3 chiến lược = 150 lần gọi Gemini nếu dùng generator mặc định — hãy chạy thử `--limit 2` trước, hoặc dùng `--generator qwen`, hoặc chạy rải từng chiến lược một. Script tự dừng sớm (vẫn ghi báo cáo phần đã chạy) khi phát hiện lỗi quota ngày, và **tự gộp kết quả các lượt trước** có cùng tham số trong `results_all.json` nên chạy tách từng chiến lược bằng nhiều lệnh riêng vẫn ra đủ ma trận 3 dòng.

### 5.9. Demo Streamlit so sánh 3 chiến lược (`ui/demo_streamlit.py`)

Lớp trình bày thuần túy cho phần thực nghiệm — **không cài lại bất kỳ logic backend nào**, chỉ gọi API có sẵn của `src/`:

```bash
# Cần cài thêm: pip install streamlit pandas
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe -m streamlit run ui/demo_streamlit.py --server.fileWatcherType none
```

> ⚠️ **Bắt buộc kèm `--server.fileWatcherType none`** (hoặc `none` trong `.streamlit/config.toml`): watcher mặc định của Streamlit dò toàn bộ module `transformers` đã nạp và làm tiến trình chết im lặng giữa lượt chạy nặng.

Cấu trúc màn hình:

- **Sidebar:** Embedding model (cố định `BAAI/bge-m3`), chọn Generator (Qwen local offline — mặc định, hoặc Gemini API với `qwen_fallback` tự tắt), selectbox **Tầng phân loại câu hỏi** (Tắt/Bật — gắn `ENABLE_CLASSIFIER` quanh lệnh dựng pipeline; bật thì mỗi kết quả kèm khối "🏷️ Phân loại câu hỏi": 2 nhãn + cấu hình truy xuất router + các nhánh tách), slider Top-K 1–5 (mặc định 3; generator nhận `top_k` chunk, hệ truy xuất lấy `top_k×2` để đo Hit@K), bật/tắt LLM Judge Faithfulness (`gemini-3.5-flash-lite`, tốn quota, mặc định tắt), bật/tắt **chế độ demo nhanh (replay)**, và 3 ô chỉnh trọng số Composite.
- **Nhập câu hỏi** ở 2 chế độ: *Câu từ benchmark* (selectbox từ `benchmark_50_questions.json`, hiển thị "Q01 · ..." — có ground truth nên chấm đủ Hit@K, MRR, Citation F1, Composite) hoặc *Câu tự do* (chỉ hiển thị Answer + chunk truy xuất + Latency; các ô cần ground truth hiển thị "—").
- **Nút "🚀 Chạy Đánh Giá RAG"** chạy tuần tự 3 chiến lược, mỗi chiến lược một `st.status` riêng + thanh tiến trình tổng (live mode mất ~30–60 giây/câu/chiến lược với Qwen local). Một chiến lược lỗi (Ollama chết, thiếu index) không làm app chết — 2 chiến lược còn lại vẫn hiển thị.
- **3 tab kết quả:** 🏆 *Câu Trả Lời Tối Ưu* (4 ô metric + câu trả lời của chiến lược thắng + căn cứ pháp lý + cảnh báo Soft Refusal nếu hệ thống từ chối — hành vi ĐÚNG với câu ngoài corpus); 📊 *Bảng So Sánh 3 Chiến Lược* (dataframe đúng thứ tự cột: Chiến lược | Composite | Hit@K | MRR | Faithfulness | Citation P | R | F1 | Latency | Số chunk, tô nổi dòng thắng); 🔍 *Chi Tiết Đoạn Truy Xuất* (3 cột cạnh nhau, mỗi chunk một expander kèm dấu ✓ nếu đúng nguồn ground truth — để soi đứt gãy ngữ cảnh giữa các chiến lược trên cùng một câu).

**Điểm chiến lược tối ưu:** `composite = w₁×Hit@K + w₂×Faithfulness + w₃×Citation_F1` (mặc định 0.4/0.3/0.3, chỉnh được ở sidebar, tự chuẩn hóa theo tổng trọng số khả dụng khi một thành phần thiếu); Faithfulness = điểm LLM Judge nếu bật, không thì dùng `number_support` (proxy miễn phí). Chỉ tính ở chế độ có ground truth; câu tự do chọn thắng theo Faithfulness proxy rồi đến Latency.

**Nguồn index của từng chiến lược** (theo thứ tự ưu tiên): index có sẵn của benchmark ở `logs/benchmark/chroma_<strategy>/` (tên collection `bench_<strategy>`) → vị trí cũ `benchmark_logs/` → **tự dựng mới** vào `logs/demo_chroma_<strategy>/` kèm thông báo tiến độ (lần đầu mất vài phút nhúng corpus, các lần sau tải từ đĩa ngay).

**Chế độ demo nhanh (replay):** nếu `logs/benchmark/results_all.json` có entry của câu đang chọn và khớp tham số (`top_k`, generator trong meta), app dùng **số liệu đã đo** thay vì chạy live — demo tức thì không cần Ollama; nhãn trạng thái hiện rõ `📅 Replay từ lượt benchmark <timestamp>` hay `⚡ Live` cho từng chiến lược. Chưa có file này thì app vẫn chạy live và hiển thị gợi ý lệnh `python scripts/benchmark_chunking.py --generator qwen` để tạo dữ liệu replay.

### 5.10. Vòng lặp đo P5 — chạy lại một round hoặc cả chuỗi round

Vòng lặp tự cải thiện nằm trong `tools/loop/` và dùng **bộ đo cố định 811 item**
(`data/loop/testset_v1.jsonl`): mỗi thay đổi phải chạy lại trên đúng bộ đó, qua đúng trọng tài
deterministic (`tools/loop/verify.py`, chữ ký `9f1179ccab74`), rồi mới được kết luận. Sổ round và
quy ước từng round: `data/loop/README.md`; sổ quyết định (ngày, giả thuyết, số đo, file nguồn,
trạng thái giữ/bác): `docs/DECISION_LOG.md`.

```bash
# 1) một round retrieval-only (pha rẻ, 811 item, không gọi model sinh)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/loop/run_round.py \
    --round r11 --phase retrieval --split all --top-k 6 \
    --out-root data/loop/rounds            # bỏ qua id đã chạy nếu chạy tiếp cùng round

# 2) chấm cổng so với round nền + quy lỗi theo tầng
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/loop/gate.py \
    --round r12 --baseline r11 --phase retrieval      # exit 1 = KHÔNG ĐẠT (kết quả, không phải lỗi)
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe tools/loop/attribute.py \
    --round r12 --compare r11 --phase retrieval

# 3) cả chuỗi round bằng MỘT lệnh, có manifest tái lập (khuyến nghị)
tools/loop/run_chain.ps1 -Chain tools/loop/chains/t5a_reranker.json -DryRun   # chỉ in lệnh
tools/loop/run_chain.ps1 -Chain tools/loop/chains/t5a_reranker.json           # chạy thật
# Linux/macOS: tools/loop/run_chain.sh tools/loop/chains/t5a_reranker.json
```

Spec chuỗi là JSON (`tools/loop/chains/*.json`): biến môi trường mặc định, từng round (`round`,
`phase`, `limit`, `pin_subset_from`, `env`), rồi `gate`/`attribute` so với round nền. `run_chain.py`:

- **Preflight** trước bước đầu: thiếu biến bắt buộc ⇒ dừng, không chạy nửa chuỗi.
- **Không ghi đè** thư mục round đã có dữ liệu (trừ `--resume`); biến bí mật không được đi qua `--set`.
- **Cổng trả mã 1 vẫn đi tiếp sang `attribute`** (kết quả âm phải được quy lỗi); chỉ dừng khi cổng
  không tạo được báo cáo.
- **Manifest tất định** (`--manifest-out`, mặc định `tmp/`): cùng spec ⇒ cùng bytes, có `spec_sha256`,
  đường dẫn tương đối, không timestamp ⇒ hai lần dry-run so được bằng `diff`.

**Cache sinh và khóa chính sách.** Từ T7, khóa cache của cả `GeminiGenerator` và `QwenGenerator`
(`src/core/cache_policy.py`) mang thêm trường `policy` **khi và chỉ khi** ngưỡng cứu/từ chối/guard/chọn câu
bằng chứng/chuẩn hóa lệch mặc định đã đăng ký (mốc `DEFAULT_CACHE_TOKEN`, test tính lại dưới env rỗng).
Thể chế mặc định giữ nguyên công thức cũ từng byte nên cache cũ vẫn dùng được; đổi một ngưỡng là mọi
câu trả lời của thể chế cũ bị tách khỏi cache mới. Đánh đổi có chủ đích: đổi ngưỡng hậu xử lý sẽ tốn
lại lượt sinh — thà tốn lượt hơn trộn hai thể chế vào một phép đo.

> Trạng thái đóng gói (đối soát 01-11): `tools/loop/*`, `src/answer_guard.py`,
> `src/retrieval/reranker.py`, `src/core/cache_policy.py` và **toàn bộ `src/` (25 tệp) đã được
> commit**; working tree sạch ⇒ HEAD tái lập được cây đã test — PA-26 đã đóng (`docs/PA_TRIAGE.md`).
> Lệnh chạy bộ test và số hiện hành: `docs/REPRODUCE.md`.

---

## 6. Quản lý file tự sinh — `logs/` và `outputs/`

Quy ước của repo (chi tiết ở `logs/README.md`): **mọi file tự sinh khi chạy phải nằm trong `logs/`**, chia sẵn theo ý nghĩa; script không được ghi log lẻ tẻ ra thư mục gốc:

| Thư mục | Sinh ra bởi | Ý nghĩa | Xóa được không |
|---|---|---|---|
| `logs/benchmark/` | `scripts/benchmark_chunking.py` | Log benchmark 3 chiến lược + index tạm | ✅ Xóa được — chạy lại là có lại |
| `logs/classifier/` | `src/assessment/evaluate_classifier.py` | `accuracy_report.md`, `results.json`, 2 ma trận nhầm lẫn CSV | ⚠️ Giữ — là số liệu chốt P2.3 (chạy lại bị ghi đè) |
| `logs/export/` | `scripts/export_architecture.py` | Biên nhận lần xuất `SYSTEM_ARCHITECTURE` | ✅ Xóa được |
| `logs/learning/` | `scripts/learn.py` và GUI Tab 3 | `learning_log.csv` — lịch sử mỗi lần hệ thống trả lời sai và được "học thêm" | ❌ **KHÔNG xóa** — là lịch sử dữ liệu |
| `logs/feedback/` | GUI Tab 3 | `user_feedback.json` — toàn bộ lượt đánh giá đúng/sai của người dùng | ❌ **KHÔNG xóa** |

`.gitignore` bỏ qua `logs/*` **trừ** `logs/README.md`, `logs/learning/` và `logs/feedback/` (hai thư mục dữ liệu lịch sử được git track để không bao giờ mất khi dọn dẹp). Riêng `outputs/` là nơi chứa **kết quả chốt** dùng cho báo cáo (`evaluation_results.json`, `evaluation_summary.md`) và được git track đầy đủ.

Ba thư mục cache ẩn khác cũng tự sinh nhưng **không phải log**: `chroma_db/` (index sản xuất — xóa là phải ingest lại từ đầu), `.cache/ocr/` (kết quả OCR — xóa là phải OCR lại), `.generation_cache/` (cache câu trả lời Gemini — xóa là tốn lại quota).

---

## 7. Quy tắc cộng tác đa-agent (`dev/.maestro/playbooks/`)

Repo được bảo trì song song bởi các agent AI chia theo 4 nhóm trách nhiệm; quy tắc dùng chung nằm ở `dev/.maestro/playbooks/base_prompt.md`:

| Playbook | Nhóm | Phạm vi sở hữu |
|---|---|---|
| `01_du_lieu_chi_muc.md` | Dữ liệu & Chỉ mục | `data/corpus/`, `ingest.py`, `src/indexing/`, `chroma_db/`, `scripts/learn.py`, `logs/learning/` |
| `02_tri_tue_rag.md` | Trí tuệ RAG | `src/core/`, `src/retrieval/`, `src/generation/`, `src/text_utils.py`, `src/generator.py`, `main.py`, `.generation_cache/` |
| `03_giao_dien_tai_lieu.md` | Giao diện & Tài liệu | `ui/app.py`, `README.md`, `docs/architecture/SYSTEM_ARCHITECTURE.*`, `scripts/export_architecture.py`, `logs/feedback/`, `logs/export/` |
| `04_kiem_chung_cau_hinh.md` | Kiểm chứng & Cấu hình | `data/evaluation/`, `src/assessment/evaluation.py`, `src/assessment/evaluate_classifier.py`, `src/assessment/analyze_ab.py`, `scripts/benchmark_chunking.py`, `tests/`, `.env*`, `logs/benchmark/`, `logs/classifier/`, `outputs/` |

Quy tắc nổi bật của `base_prompt.md`: mọi file trung gian chỉ được nằm trong `tmp/` và phải xóa sạch trước khi kết thúc phiên; **mọi log tự sinh khi chạy phải nằm trong `logs/` đúng ý nghĩa ở `logs/README.md`**; ghi file luôn bằng Python với `encoding='utf-8'` (cấm chuyển hướng `>` của PowerShell — ghi UTF-16 làm hỏng JSON); chỉ được sửa file trong phạm vi group mình; báo cáo bắt buộc kèm kết quả verify.

---

## 8. Ghi chú

- Mô hình embedding `bge-m3` và mô hình `Qwen2.5:1.5b-instruct` đều chạy cục bộ (không tốn phí API); chỉ **Gemini API** là dịch vụ trên mây.
- Để có kết quả ổn định, Generator sử dụng `Temperature = 0.0` và luôn kèm trích dẫn Điều/Khoản từ ngữ cảnh.
- `main.py` và `ui/demo_streamlit.py` tự đặt `sys.stdout.reconfigure(encoding="utf-8")` nên tiếng Việt in đúng trên console Windows; nếu gọi Python thủ công thì chạy kèm `PYTHONUTF8=1` hoặc `PYTHONIOENCODING=utf-8`.
- Mỗi lần chạy sẽ thấy một `FutureWarning` của `google-generativeai` — gói này đã bị Google khai tử nhưng vẫn hoạt động (0.8.6). Không phải lỗi; migrate sang `google-genai` là việc về sau, và lưu ý `google-genai` đổi cả tên model lẫn cách truyền `thinking_config`.
- **Hiện trạng corpus và index:** 29 tài liệu (24 PDF + 5 DOCX, không còn `.doc` legacy) ở 3 tầng — 3 PDF thêm 28-10 **chưa ingest**; index sản xuất `chroma_db/` = **361 chunks** cắt bằng `DocumentChunker` (structure-aware cho văn bản có Điều, fallback theo đoạn cho văn bản thường). Ba index thực nghiệm của demo: fixed = 182, recursive = 189, structure = 378 chunks.
- **Hiện trạng tầng phân loại + kết quả A/B chốt (P2.3–P4.3, 2026-10-21):** index 361 chunks **không đổi** — tầng phân loại là lớp phía trên pipeline, không rebuild index. Độ chính xác bộ phân loại: chủ đề 85,0% / loại câu hỏi 81,0% (`logs/classifier/accuracy_report.md`). Kết quả A/B trên benchmark v3 100 câu (generator Local Qwen `qwen2.5:1.5b-instruct`, top_k=6, giám khảo tắt — nguồn `outputs/ab_comparison.md`):

| Chỉ số | WITHOUT (tắt phân loại) | WITH (bật phân loại) | Chênh lệch |
|---|---|---|---|
| Hit@3 / Hit@5 / Hit@6 | 60,8 / 65,0 / 66,0% | 77,3 / 78,3 / 78,3% | +27,1 / +20,6 / +18,7% tương đối |
| MRR (recall window) | 0,5097 | 0,7689 | +50,9% tương đối |
| Citation F1 | 13,4% | 25,7% | +12,34 pp |
| Từ chối oan (trong 97 câu in corpus) | 46/97 | 49/97 | +3 câu |

Nhóm tăng rõ nhất: chương trình đào tạo Hit@3 45,5% → 90,9% (n=22); `SO_SANH` MRR 0,4333 → 0,8286 (n=5, nhờ tách truy vấn con). Đây là chênh lệch của **cả gói thay đổi** ở lượt WITH (chọn tham số + thu hẹp nguồn + tách truy vấn con + prompt), **không tách riêng được lọc nguồn**: trên vòng 811 item (V2, 27-10) lọc mềm so all-off **−18 item** (518 vs 536; CI cụm [−4,62; −0,69] điểm %, p=2,77e−4) và chậm 2,76 s vs 0,18 s/item; lọc cứng (r0) chỉ đạt 363/700. GATE P4.3 **ĐẠT**: không chỉ số truy xuất nào giảm quá 5% tương đối. Lưu ý khi đọc: generator là Qwen 1.5B offline nên số tuyệt đối của tầng trích dẫn chỉ mang tính so sánh nội bộ giữa 2 lượt; điểm giảm trung thực cần nhắc: number support −3,05 pp, đánh giá rèn luyện Hit@3 −18,2 pp (n=11).
- **Bộ unit test (1.124 test, 25-10):** chạy bằng `python -m pytest` — hoàn toàn offline (fake Qwen/ChromaDB/Gemini, monkeypatch), không tốn quota; gồm test 3 chiến lược chunking, pipeline (fold-query + oversampling), classifier + router (few-shot, guardrail, ánh xạ cấu hình), tách truy vấn con, prompt biến thể, guardrail Local SLM, các hàm đánh giá và cờ GUI/CLI, bộ test vòng lặp P5 (`tests/test_loop_*.py`, `test_run_chain.py`, `test_cache_policy.py`), bộ test T4 (`test_t4_sft_invariants.py`, `test_t4_generator_contract.py`; phần GPU `test_t4_gpu_slow.py` cần `T4_RUN_SLOW=1` nên mặc định được skip) và bộ test T5 (`test_t5_reranker_contract.py`, `test_t5_contextual_header.py`) và bộ test T6 (`test_t6_gate_refusal_and_regression.py`, `test_t6_referee_validation.py`, `test_t6_real_questions_and_metrics.py` — 60 test, trong đó cổng refusal chỉ chạy trên **bản đề xuất**, `gate.py` chưa đổi). Con số này là của **working tree**; xem PA-26 về khoảng trống giữa HEAD và cây đã test.
- **Bộ benchmark:** 5 file trong `data/evaluation/` — 15 câu GUI tự sinh (schema 10 khóa cũ), **50 câu** và **100 câu v1/v2** (đúng 12 khóa, do các agent sinh theo playbook); benchmark mặc định của `src/assessment/evaluation.py` là 100 câu v2, của `scripts/benchmark_chunking.py` và demo là 50 câu. Ngoài ra `data/evaluation/manual_test_checklist.md` có **34 câu kiểm tra tay chia 7 nhóm tài liệu** (kèm nhóm câu ngoài corpus để thử hành vi từ chối) — dùng để đánh giá thủ công sau mỗi lần đổi pipeline.
- **Benchmark v3 (2026-10-20):** `data/evaluation/benchmark_100_questions_v3.json` — 100 câu, 13 khóa (12 khóa v2 + `question_type` theo [TAXONOMY.md](docs/spec/TAXONOMY.md)), nhãn đã duyệt; phân bố `TRA_CUU`=87 / `SO_SANH`=5 / `THU_TUC`=5 / `NGOAI_PHAM_VI`=3. Mặc định của `src/assessment/evaluation.py` vẫn là 100 câu v2; **lượt A/B chính thức dùng `--benchmark ...v3.json`** (mục 5.7).
- **Hành vi cần lưu ý của Qwen2.5-1.5B (tầng chuẩn hóa):** khi câu hỏi nằm ngoài phân bố few-shot, model có xu hướng **tự trả lời** thay vì viết lại câu hỏi, sinh ra nhận định không có căn cứ. Các lớp chặn hiện có: (1) system prompt chống bịa + few-shot của `src/core/query_normalizer.py` — đường đi chính trong pipeline, kèm active learning từ phản hồi người dùng; (2) `is_acceptable()` (4 điều kiện: không rỗng, ≤ 300 ký tự, phải có dấu `?`, không chứa mẫu lạc đề) và `guardrail_violation()` (bảo toàn con số + tỉ lệ token trùng với câu gốc ≥ 30%) trong `src/generation/local_slm.py` — dùng khi chuẩn hóa trực tiếp qua wrapper `LocalSLM`, có test riêng trong `tests/test_local_slm.py`. Mọi đường đều suy giảm mềm: nghi ngờ là dùng lại câu hỏi gốc để truy xuất.
- **Lịch sử xử lý lỗi chất lượng:** file mẫu `quy_che_dao_tao_mau.txt` từng xếp hạng #1 cho một câu hỏi quy chế thật và được Gemini dùng làm căn cứ — đã chuyển sang `data/evaluation/reference/` nên không còn bị index. Điểm yếu còn lại của truy xuất nằm ở các chủ đề ít từ khóa trùng lặp (xem cột Hit@6 và MRR trong `outputs/evaluation_summary.md` để theo dõi sau mỗi lần cải tiến chunking/retrieval).

### 8.1. Giới hạn thật lòng (cập nhật 27-10, sau V1/V2)

Những điều dưới đây **không** được che bằng số đẹp; mỗi mục kèm nơi kiểm chứng.

1. **Tầng sinh là nút thắt, không phải truy xuất.** Gold@6 = **0,7657** (all-off, 811 item); cấu hình
   lọc mềm r11 chỉ 0,7400 = **−18 item** so với all-off (CI cụm [−4,62; −0,69] điểm %, p=2,77e−4,
   chậm 2,76 s vs 0,18 s/item). Nhưng
   `PASS_CORRECT` của pha sinh chỉ **14–19/100** qua r1→r12 và **không** vượt ngưỡng 25 ở bất kỳ
   round nào (`data/loop/README.md`, `docs/archive/reports/T3.md`, `T4.md`). Câu hỏi "model 1,5B có phải
   trần?" **chưa được trả lời dứt khoát**: 3B không cải thiện (p = 0,804) và mới có 25/30 id T1(b).
2. **Corpus còn mất dấu thanh.** Đo từ `chroma_db`: **18,6%** số từ còn dấu; 171/361 chunk < 5%;
   `.docx` giữ 78–81% ⇒ nút thắt nằm ở **pipeline convert PDF**, không ở chunking. Mọi số retrieval
   hiện tại đều đo trên corpus này (nguồn: `data/loop/diag/corpus_check/`, `docs/archive/PENDING_APPROVAL.md`
   PA-1/PA-2/PA-3).
3. **Trần truy xuất có giới hạn đo được.** Oracle trong pool 12 = **0,8214** (EXACT 0,3269); pool 20 =
   **0,8871**. Reranker hiện tại (cross-encoder chấm fold query) đi **ngược**: gold@6 0,7400→0,6686
   (r12, so trong cùng cấu hình lọc mềm r11 — cả hai đều dưới all-off 0,7657), nên mọi kỳ vọng
   "+10 điểm EXACT" phải chờ PA-25 (bỏ fold) với round đo lại trên baseline all-off.
4. **Contextual header chưa có tín hiệu.** r13: gold@6 0,7371, delta **−0,0028** CI [−0,0129; +0,0071],
   p = 0,79; header dạng `[tên file] - [Điều]` vốn đã có trong 253/361 chunk nên phạm vi can thiệp thật
   chỉ còn Chương/Khoản + 108 chunk fallback (`docs/archive/reports/T5.md` §5).
5. **Bộ đo 811 item chỉ có một phiên bản, không có tập giữ riêng.** Nhãn do luật sinh, **không phải
   người gán**; mẫu 60 câu phân tầng để đo đồng thuận người–máy đã dựng nhưng `n_filled = 0`
   (`docs/archive/reports/T6.md` §6b), nên `referee_agreement` **chưa có số**. Mọi kết luận "tăng/giảm" chỉ đúng
   trong bộ đo này, chưa suy ra được cho câu hỏi thật ngoài đời (`tools/eval/real_questions.jsonl` hiện 0 câu).
6. **Nhiễu ±3 item.** Các chênh lệch 1–3 item giữa hai round được ghi là "đi ngang", không phải cải
   thiện; quy ước ở `tools/loop/noise_floor.py` + `data/loop/README.md`.
7. **SFT bị chặn bởi bộ nhớ, không phải ý tưởng.** Card 4 GB hết chỗ từ **1.024 token** (~3 MiB/token)
   trong khi **13/13 dòng train ≥ 1.016 token** ⇒ chưa train được trên máy này (PA-11 4-bit / PA-12
   đổi định dạng chờ duyệt; `docs/archive/reports/T4.md` §5).
8. **HEAD tái lập được cây đã test (đối soát 01-11)**: toàn bộ `src/` (25 tệp), `tools/loop/` và
   testset đã vào kho, working tree sạch — PA-26 đã đóng. Giới hạn còn lại nằm ở artifact nặng:
   chúng không vào git mà được ghim bằng `ARTIFACT_MANIFEST.json`, nên phải `--check` manifest
   trước khi tái lập số đo.
9. **Chi phí round được đo, không ngoại suy.** r12 thật = **≈66 phút** (3.855,5 s tổng latency, median
   4,74 s/item), không phải con số ngoại suy 27–30 phút từng công bố; bài học đã ghi ở T5.md §2.6.
10. **Ngân sách đo là hữu hạn.** Toàn bộ chuỗi r0–r13 chạy trên một máy, một GPU 4 GB, ngân sách
    Gemini ≤ 14 lượt/ngày; không có lặp đa seed cho từng round, nên mọi CI là bootstrap trên **một**
    lượt đo (10.000 lần lấy mẫu lại, seed 20261023).
