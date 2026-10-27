# Chương 01 — Tổng quan kiến trúc

> **Mục tiêu chương:** vẽ lại được sơ đồ hệ thống từ trí nhớ; giải thích được vì sao
> cần truy xuất lai, vì sao tách `retrieve_k` khỏi `top_k`, và vì sao mọi tầng đều
> phải “suy giảm mềm”. Sau chương này bạn có thể trace một câu hỏi qua toàn bộ hệ
> thống bằng tên hàm.

---

## 1. Bài toán và ràng buộc thật

Sinh viên hỏi bằng ngôn ngữ đời thường:

> “Em bị ĐTBHK dưới 1.0 thì có bị đuổi học luôn không ad?”

Hệ thống phải trả lời **chỉ dựa trên văn bản quy chế của Trường**, kèm căn cứ
(Điều/Khoản hoặc tên file), và **từ chối** nếu không đủ căn cứ. Ba ràng buộc của dữ
liệu tạo nên toàn bộ thiết kế:

1. **Văn bản nguồn không đồng nhất.** Tầng 1 là PDF scan, OCR tiếng Việt **mất dấu
   thanh** (“Điều 12” thành “Dieu 12”, “học phí” thành “hoc phi”). Tầng 2 là PDF text
   và DOCX còn dấu. Chỉ 62/361 chunk còn đủ dấu để dùng cho bài tập sinh văn bản.
2. **Câu hỏi cần cả từ khóa lẫn ngữ nghĩa.** “CON401” chỉ BM25 bắt được; “bị đuổi
   học” phải khớp “buộc thôi học” — vector và từ điển đồng nghĩa bắt được.
3. **Quota Gemini hữu hạn.** Free tier giới hạn theo ngày; mọi thiết kế cache,
   fallback, resume đều để không đốt quota vô ích.

Ba ràng buộc này nuôi ba quyết định kiến trúc: **hybrid retrieval**, **chuẩn hóa câu
hỏi bằng SLM local**, và **đo lường có thể chạy lại**.

---

## 2. Sơ đồ kiến trúc đầy đủ

```
                        ┌──────────────────────────── OFFline / INDEX ───────────────────────────┐
 data/corpus/*.pdf|docx|txt                                                                      │
        │ DocumentLoader (src/loader.py)                                                       │
        │  ├─ PDF text: pypdf                                                                  │
        │  ├─ trang scan: pypdfium2 render → RapidOCR → cache .ocr_cache/                      │
        │  └─ metadata tier = tên thư mục cấp 1                                                │
        ▼                                                                                      │
 DocumentChunker (src/chunking.py)                                                             │
        ├─ có "Điều N." → cắt theo Điều, tiền tố [Tên văn bản]                                │
        └─ không có → cắt đoạn/câu, gộp ≤ 1200 ký tự, overlap 150                             │
        ▼                                                                                      │
 VectorStoreManager (src/vector_db.py)                                                         │
        ├─ bge-m3 nhúng từng chunk (normalize_embeddings=True)                                │
        └─ ChromaDB persist + metadata {tier, source, chunk_id}                                │
        └─ BM25 index dựng lại từ chính các chunk này khi serve                                │
                        └───────────────────────────────────────────────────────────────────────┘

 ONLINE / MỘT LƯỢT HỎI
 question thô
   │ ① normalize_user_query (src/query_normalizer.py)
   │      Qwen 2.5-1.5B qua Ollama, temperature 0, few-shot + active learning
   │      → câu học vụ; guardrail ở src/local_slm.py chặn mất số/bịa số/lệch chủ đề
   ▼
 normalized_query
   │ ② classify_query (src/classifier.py) — chỉ khi ENABLE_CLASSIFIER=1
   │      → {topic: 1/14 hoặc None, question_type: 1/4, raw_response}
   ▼
 labels
   │ ③ get_retrieval_config (src/router.py)
   │      → RetrievalConfig(top_k, bm25_weight, chroma_weight, source_filter, enable_subquery)
   ▼
 config
   │ ④ expand_query_with_synonyms (src/retrieval.py)
   │      "đuổi học" → + "buộc thôi học kỷ luật"
   │    nếu config.enable_subquery và nhãn SO_SANH:
   │      split_comparison_query → 2–3 truy vấn con (guardrail)
   ▼
 expanded_query (hoặc nhiều nhánh)
   │ ⑤ HybridRAGPipeline.retrieve (src/pipeline.py:148)
   │      retrieve_k = 2 × effective_top_k
   │      query được fold() trước khi vào Chroma
   │      BM25 k=retrieve_k  +  Chroma k=retrieve_k  → RRF c=60
   │      + fallback_query = câu gốc  (gộp, khử trùng theo chunk_id)
   │      + lọc source_filter sau merge
   ▼
 all_docs (retrieve_k ứng viên)  ──► sources[] cho evaluation
   │  cắt top_k đầu
   ▼
 gen_docs (top_k)
   │ ⑥ build_prompt + GeminiGenerator.generate_answer (src/generator.py)
   │      cache SHA-1 → Gemini → nếu lỗi: Qwen fallback
   │      prompt khác nhau theo question_type (bảng/bước/từ chối)
   │      hậu xử lý: canonicalize_refusal + inject_citations_from_metadata
   ▼
 answer có trích dẫn (hoặc REFUSAL_TEXT)
```

Đọc sơ đồ này theo hai màu: **phần offline** thay đổi khi corpus thay đổi; **phần
online** chạy mỗi câu hỏi. Sửa chunking chỉ ảnh hưởng offline (phải ingest lại); sửa
prompt chỉ ảnh hưởng online (cache tự đổi key).

---

## 3. Vì sao phải lai BM25 và vector?

Hai bộ truy xuất mắc hai lỗi khác nhau, và lỗi của bộ này thường được bộ kia cứu:

| Tình huống | BM25 | Vector bge-m3 | Kết luận |
|---|---|---|---|
| Câu hỏi có mã “CON401” | ✅ khớp chính xác | ❌ có thể xếp hạng thấp | BM25 thắng |
| “bị đuổi” vs “buộc thôi học” | ❌ không chung token | ✅ gần nghĩa | Vector thắng |
| Tài liệu OCR mất dấu | ✅ tokenizer nhân đôi dạng có/không dấu | ⚠️ chỉ đúng nếu query cũng fold | Phải fold query |
| Câu dài nhiều ý | ⚠️ nhiễu vì nhiều từ | ✅ nắm ý chính | Vector thắng |

**RRF hợp nhất thứ hạng, không hợp nhất điểm số.** Với mỗi tài liệu `d`:

```
RRF(d) = Σ_i  w_i / (c + rank_i(d))
```

Trong đó `c = DEFAULT_RRF_C = 60` (`src/vector_db.py:23`), `rank_i` bắt đầu từ 1,
`w_i` là trọng số router. Vì chia cho hạng, tài liệu đứng đầu ở **một trong hai**
nhánh vẫn được điểm cao dù nhánh kia không trả về nó. Đây là lý do RRF chịu được
hai bộ truy xuất có thang điểm hoàn toàn khác nhau (BM25 score không cùng đơn vị với
cosine similarity).

> ⚠️ **Nhầm lẫn hay gặp khi bảo vệ:** công thức trong docstring `src/retrieval.py`
> viết `k/(rank+k)`; mã thực tế dùng `weights/(c+rank)` của LangChain. Khi được hỏi,
> nói theo mã: “RRF có hằng số làm mượt c=60, trọng số lấy từ router”.

Ví dụ chạy tay: chunk A hạng 1 ở BM25, không có trong top vector; chunk B hạng 1 ở
vector, hạng 3 ở BM25; trọng số 0.5/0.5:

```
A = 0.5/(60+1)                     = 0.00820
B = 0.5/(60+1) + 0.5/(60+3)        = 0.00820 + 0.00794 = 0.01614
```

B thắng vì **xuất hiện ở cả hai nhánh** — đúng tinh thần “hybrid”: đồng thuận giữa
hai bộ truy xuất là tín hiệu mạnh.

---

## 4. Oversampling: `retrieve_k` và `top_k` khác nhau để làm gì?

Đây là chi tiết dễ bị hỏi nhất khi bảo vệ.

```python
# src/pipeline.py:350
retrieve_k = effective_top_k * self.oversample_factor   # mặc định ×2
...
gen_docs = all_docs[:effective_top_k]   # generator chỉ thấy top_k
sources  = [describe_document(d, i) for i, d in enumerate(all_docs)]  # giữ đủ retrieve_k
```

- **`top_k`** = cửa sổ ngữ cảnh đưa vào generator. Tăng nó làm prompt dài, tốn token,
  dễ loãng.
- **`retrieve_k`** = cửa sổ **đo** của retrieval. Hit@3/5/6 cần ít nhất 6 ứng viên,
  nên evaluation truyền `top_k=retrieve_k` vào pipeline (xem `evaluate_question`,
  `src/evaluation.py:455`) để pipeline tự nhân oversample.

Nếu chỉ truy xuất đúng `top_k=6` rồi đo Hit@6, bạn không phân biệt được “hệ thống
tốt” với “hệ thống may mắn vừa đủ 6”. Oversampling tách **năng lực truy xuất** khỏi
**ngân sách ngữ cảnh**.

> ⚠️ Trong lượt A/B local, metadata ghi `retrieve_k=6` và `top_k=6`, nhưng pipeline
> vẫn oversample ×2 nên `sources` thực = 12 (13–16 ở câu SO_SANH); 6/6 chỉ là tham số
> khai báo, không phải cửa sổ truy xuất thực. Đừng nói “luôn luôn ×2” như một định
> luật — nói “mặc định ×2, hệ số là tham số của pipeline”.

---

## 5. Hai chế độ chạy: WITHOUT và WITH classifier

`HybridRAGPipeline.__init__` đọc `ENABLE_CLASSIFIER` (`src/pipeline.py:102`). Đây là
công tắc A/B, không phải tính năng ẩn:

| Thành phần | WITHOUT (`ENABLE_CLASSIFIER=0`) | WITH (`=1`) |
|---|---|---|
| `classify_query` | không gọi | gọi Qwen, 14×4 nhãn |
| Router | không | `top_k`, trọng số, lọc nguồn |
| Sub-query SO_SANH | không | tách 2–3 nhánh nếu guardrail cho qua |
| Prompt generator | `PROMPT_RULES` gốc | thêm appendix theo `question_type` |
| Cache key | prompt gốc | prompt biến thể → key khác |
| Nếu classifier lỗi | — | log cảnh báo, lùi về cấu hình nền |

Thiết kế “tắt là hành vi cũ 100%” cho phép A/B công bằng: cùng corpus, cùng model,
cùng tham số, chỉ khác một biến. Đây là điều kiện để câu “Hit@3 tăng 27,1% tương đối”
có nghĩa.

---

## 6. Kết quả A/B — đọc đúng cách

Nguồn: `outputs/ab_comparison.md`, 100 câu benchmark v3, generator local Qwen,
judge tắt, 2026-10-21.

| Chỉ số | WITHOUT | WITH | Chênh |
|---|---:|---:|---:|
| Hit@3 | 60,8% | 77,3% | +16,5 pp (+27,1% tương đối) |
| Hit@5 | 65,0% | 78,3% | +13,4 pp |
| MRR | 0,5097 | 0,7689 | +0,2592 |
| Citation F1 | 13,4% | 25,7% | +12,3 pp |
| Citation Recall | 13,0% | 29,7% | +16,7 pp |
| Topic accuracy | — | 87,0% | |
| Type accuracy | — | 83,0% | |
| Từ chối oan (in-corpus) | 47,4% | 50,5% | **xấu hơn 3 câu** |
| Latency trung bình | 2,30 s | 7,79 s | +5,49 s (chỉ tham khảo) |

Ba điều phải nói cùng lúc khi bảo vệ:

1. **Truy xuất tốt lên rõ rệt**, đặc biệt nhóm chương trình đào tạo (Hit@3 45,5% →
   90,9%) và khen thưởng sinh viên (10% → 50%) nhờ `source_filter` + top_k.
2. **Từ chối oan tăng nhẹ** vì classifier over-predict `NGOAI_PHAM_VI` (11 câu dự
   đoán so với 3 câu thật). Đây là hạn chế đã biết, không giấu.
3. **Latency tăng** chủ yếu do gọi thêm Qwen classifier + tách sub-query, không phải
   do retrieval. Không dùng con số này để kết luận “hệ thống chậm hơn 3 lần” vì môi
   trường đo không ổn định.

---

## 7. Trace một câu hỏi thật

Câu thô: `"Em bị ĐTBHK dưới 1.0 thì có bị đuổi học luôn không ad?"`

| Bước | Hàm | Kết quả minh họa |
|---|---|---|
| 1 | `normalize_user_query` | “Điểm trung bình học kỳ dưới 1.0 có bị buộc thôi học không?” |
| 2 | guardrail `guardrail_violation` | số `1.0` còn nguyên → an toàn |
| 3 | `classify_query` | topic `quy chế công tác sinh viên`, type `TRA_CUU` |
| 4 | `get_retrieval_config` | `top_k` 6, lọc nguồn `1054-qd-dhag-2020-09-28.pdf` |
| 5 | `expand_query_with_synonyms` | + “buộc thôi học thôi học kỷ luật” (tùy từ khớp) |
| 6 | `retrieve` | fold query → BM25 + Chroma → RRF, trả 6–12 ứng viên |
| 7 | `generate_answer` | prompt grounded, cache miss, gọi Gemini (hoặc Qwen) |
| 8 | hậu xử lý | `inject_citations_from_metadata` gắn nguồn top-1 nếu thiếu |

Lưu ý bước 3–4: nếu classifier gán nhầm `NGOAI_PHAM_VI`, prompt sẽ có dòng nhắc từ
chối; nhưng **vẫn truy xuất** nên nếu ngữ cảnh có căn cứ, model vẫn trả lời. Đây là
lý do router cố ý không “skip retrieval” cho lớp này (`src/router.py:22`).

---

## 8. Ma trận suy giảm mềm

| Sự cố | Tầng phát hiện | Hành vi | Người dùng thấy gì |
|---|---|---|---|
| Ollama không chạy | `LocalSLM.check_connection` | pipeline vẫn chạy với câu gốc | Câu trả lời vẫn ra, cảnh báo khi khởi động |
| Qwen viết lại lệch nghĩa | `guardrail_violation` | dùng câu gốc | Log `[LocalSLM-Guardrail]` |
| Classifier timeout | `classify_query` | `topic=None`, `TRA_CUU` | Không thấy gì; cấu hình nền |
| Router lỗi | `pipeline.run` | bỏ nhãn, dùng config gốc | Log `[Classifier] Cảnh báo` |
| Tách sub-query dở | `split_comparison_query` | trả `[query]` | Log `[SubQuery] Guardrail` |
| BM25 không dựng được | `_init_hybrid_retriever` | lùi `similarity_search` thuần vector | Log `[HybridSearch]` |
| Gemini 429 theo phút | `_call_api` | chờ 60 s × 3 | Chậm nhưng không mất câu |
| Gemini 429 PerDay | `_call_api` | dừng lượt, giữ kết quả đã chạy | Marker “429 PerDay” để resume |
| Gemini lỗi khác | `generate_answer` | Qwen fallback có nhãn cảnh báo | Câu trả lời kèm `[Cảnh báo: ...]` |
| Cả Gemini và Qwen chết | `_qwen_answer` | `GeneratorError` | CLI in lỗi, không crash |
| Không có ngữ cảnh | `generate_answer` | trả `REFUSAL_TEXT` ngay | Từ chối lịch sự, 0 request API |

Nguyên tắc: **tầng tối ưu được phép mất, tầng trả lời không được chết**. Chuẩn hóa và
classifier là tối ưu; retrieval và generator là bắt buộc; nhưng ngay cả generator
cũng có hai nhà cung cấp.

---

## 9. Số liệu “xương sống” cần nhớ

| Hạng mục | Giá trị | Nguồn |
|---|---|---|
| Tổng chunk đã index | 361 (Tầng 1: 234, Tầng 2: 50, bổ sung: 77) | `chroma_db/` |
| Chunk còn đủ dấu (dùng được cho sinh văn bản) | 62/361 | `tools/build_training_data.py` |
| Benchmark đánh giá | 100 câu v3 | `data/evaluation/` |
| Phân bố question_type v3 | 87 TRA_CUU / 5 SO_SANH / 5 THU_TUC / 3 NGOAI_PHAM_VI | benchmark |
| Chủ đề | 14 | `src/classifier.py:48` |
| Classifier topic / type | 85% / 81% | `logs/classifier/accuracy_report.md` |
| A/B Hit@3 | 60,8% → 77,3% | `outputs/ab_comparison.md` |
| Từ chối oan | 47,4% → 50,5% (hạn chế) | cùng nguồn |
| Dataset huấn luyện | 3.912 mẫu / 10.619 dòng JSONL | `data/training/manifest.json` |

Nếu chỉ nhớ 3 con số: **361 chunk**, **85/81 classifier**, **+27,1% Hit@3 tương đối**
— nhưng phải nói kèm hạn chế từ chối oan và quy mô nhóm nhỏ.

---

## 10. Bài tập chương

**A. Hiểu luồng.** Vẽ lại sơ đồ mục 2 mà không nhìn tài liệu, ghi tên hàm ở mỗi mũi
tên. Đạt nếu không thiếu `fold`, `retrieve_k`, `inject_citations_from_metadata`.

**B. Tính tay.** Với trọng số BM25=0,6 Chroma=0,4, c=60: chunk X hạng 2 ở BM25,
hạng 5 ở Chroma; chunk Y hạng 1 ở BM25, không có ở Chroma. Chunk nào thắng?

**C. Phản biện.** “Nếu đã có Gemini đọc cả 12 chunk thì cần gì BM25?” Trả lời trong
4 câu, dùng ví dụ mã môn và giới hạn context.

**D. Chẩn đoán.** Một câu hỏi trả lời sai dù chunk đúng nằm ở hạng 2. Nêu 3 tầng có
thể gây lỗi và cách kiểm tra từng tầng bằng log/JSON.

<details>
<summary>Đáp án gợi ý</summary>

**B.** X = 0,6/(62) + 0,4/(65) = 0,00968 + 0,00615 = 0,01583. Y = 0,6/61 = 0,00984.
X thắng nhờ xuất hiện ở cả hai nhánh.

**C.** Gemini chỉ thấy ngữ cảnh được đưa; nếu retrieval bỏ sót chunk đúng thì không
model nào cứu được. BM25 bắt mã môn/số Điều chính xác mà vector có thể xếp thấp;
vector bắt diễn đạt khác mà BM25 trượt. Context có hạn nên phải chọn đúng 6–12 chunk,
không thể “đưa hết 361”.

**D.** (1) Normalization làm mất thông tin → xem `normalized_query`; (2) router lọc
sai nguồn → xem `retrieval_config.source_filter`; (3) xếp hạng RRF đẩy chunk đúng
xuống dưới `top_k` → xem `sources` và `matched_rank`; (4) generator không dùng chunk
→ xem `contexts` và prompt/cache.
</details>

Tiếp theo: [02 — Dữ liệu & nạp corpus](02_du_lieu_va_nap_corpus.md).
