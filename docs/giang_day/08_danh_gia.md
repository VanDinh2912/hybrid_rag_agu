# Chương 08 — Đánh giá và thực nghiệm: biến hành vi thành con số

> **Mục tiêu chương:** đọc được một file kết quả đánh giá từ đầu đến cuối; biết mỗi chỉ số
> đo cái gì, đo trên bao nhiêu câu và **không** đo cái gì; chạy lại được một lượt đánh giá
> mà không đốt quota; hiểu cơ chế resume, dry-run, flush; và quan trọng nhất — nhìn ra ba
> lỗi đo đang tồn tại trong repo (đường tắt Citation, lệch `top_k`/`retrieve_k`, baseline
> kNN) để không đọc số liệu lạc quan hơn sự thật.

Đánh giá là tầng duy nhất trong đồ án biến “hệ thống chạy được” thành “hệ thống tốt hơn
bao nhiêu, ở đâu, với bằng chứng nào”. Vì vậy chương này không chỉ liệt kê công thức. Nó
dạy cách **truy vết một con số**: từ benchmark → một entry trong JSON → hàm tính → bảng
tổng hợp → kết luận. Nếu không làm được chuỗi đó, con số chỉ là trang trí.

> **Quy ước:** số dòng đúng tại thời điểm soạn (2026-10-23). Khi sửa mã, tìm bằng tên hàm.
> Mọi lệnh chạy trên Windows dùng `./venv/Scripts/python.exe` và tiền tố
> `PYTHONIOENCODING=utf-8` khi in tiếng Việt.

---

## 1. Bản đồ tầng đánh giá

| File | Vai trò | Ghi chú |
|---|---|---|
| `data/evaluation/benchmark_100_questions_v3.json` | Tập đo chính | 100 câu, 13 khóa/câu, có `question_type` |
| `src/assessment/evaluation.py` | Chạy pipeline + tính metric + resume + báo cáo | File lớn nhất của tầng đo |
| `src/core/faithfulness_heuristic.py` | Chấm trung thực bằng token-overlap, không cần API | Chạy **sau** lượt đánh giá |
| `src/assessment/analyze_ab.py` | So sánh hai lượt WITH/WITHOUT, vẽ biểu đồ, kiểm GATE | Đọc 2 JSON + benchmark |
| `src/assessment/evaluate_classifier.py` | Đo accuracy classifier và baseline kNN | Độc lập với pipeline RAG |
| `outputs/ab_results_*.json` | Kết quả thô từng câu của A/B | Nguồn chân lý cho mọi số A/B |
| `outputs/ab_summary_*.md` | Bảng tóm tắt do `evaluation.py` sinh | Không phải báo cáo A/B cuối |
| `outputs/ab_comparison.md` | Báo cáo A/B do `analyze_ab.py` sinh | Có bảng nhóm + GATE + nhận xét |
| `logs/classifier/results.json` | Dự đoán classifier từng câu | Dùng để phân tích misroute |
| `logs/classifier/accuracy_report.md` | Báo cáo accuracy + confusion matrix | Có phần GT-verify điền tay |

Ba tầng kết quả, đừng lẫn:

```
benchmark v3
   │  evaluation.py chạy pipeline
   ▼
outputs/ab_results_*.json        ← per_question + aggregates (số thô)
   │  faithfulness_heuristic.py ghi thêm điểm vào per_question
   │  analyze_ab.py đọc lại, tính nhóm, kiểm GATE
   ▼
outputs/ab_comparison.md         ← báo cáo diễn giải (số dẫn xuất)
```

`outputs/ab_summary_*.md` là báo cáo **một lượt** do `format_summary_md` sinh; nó không
so sánh hai lượt. Báo cáo so sánh là `ab_comparison.md`.

---

## 2. Benchmark v3 — thiết kế trước khi đo

### 2.1. Schema và phân bố

`data/evaluation/benchmark_100_questions_v3.json` là một **object**, không phải list:

```json
{
  "version": "v3.0",
  "description": "...",
  "questions": [ ... 100 phần tử ... ],
  "changelog": [ ... ]
}
```

Vì vậy `load_benchmark` (`evaluation.py:439–452`) phải lấy `data["questions"]`; nếu ai
viết `json.load(...)[0]` sẽ lỗi. Hàm còn kiểm tra `raw_query` khác rỗng cho từng câu.

Mỗi câu có 13 khóa:

| Khóa | Ý nghĩa | Dùng trong đánh giá |
|---|---|---|
| `id` | Q01…Q100 | Khóa join giữa benchmark, JSON kết quả, log classifier |
| `category` | 1 trong 14 chủ đề | Đo topic accuracy; nhóm theo chủ đề |
| `tier` | Tầng corpus | Thống kê, không dùng tính điểm |
| `in_corpus` | Câu trả lời được từ corpus? | Quyết định ca từ chối |
| `source_document` | Tên file đúng | `source_match` cho Hit/MRR |
| `raw_query` | Câu thô | Đầu vào pipeline |
| `normalized_query` | Câu chuẩn kỳ vọng | Chỉ để tham chiếu/ước lượng cache |
| `expected_answer` | Đáp án ngắn | Không chấm tự động |
| `expected_citations` | Trích dẫn kỳ vọng | Chấm Citation — nhưng xem mục 5 |
| `ground_truth_answer` | Đáp án đầy đủ | Không chấm tự động |
| `ground_truth_citation` | Vị trí nguồn | Kiểm chứng thủ công |
| `supplement_if_wrong` | Gợi ý khi sai | Dùng cho UI/giải thích |
| `question_type` | 4 nhãn taxonomy | Đo type accuracy; chia nhóm |

Phân bố thực tế:

| `question_type` | Số câu | Vai trò |
|---|---:|---|
| `TRA_CUU` | 87 | Lớp đa số — mọi baseline đoán mù đã đạt 87% |
| `SO_SANH` | 5 | Lớp hiếm, kích hoạt sub-query và +2 top_k |
| `THU_TUC` | 5 | Lớp hiếm, đổi trọng số BM25/Chroma |
| `NGOAI_PHAM_VI` | 3 | Q96–Q98, `in_corpus=false` |

`in_corpus=true` = 97 câu; `in_corpus=false` = 3 câu. Đây là lý do **mẫu số của Hit/MRR
là 97, không phải 100**: câu ngoài corpus không có `source_document` để so, nên
`hit_at_* = None` và bị loại khỏi trung bình (`aggregate`, `evaluation.py:570–610`).

### 2.2. Ba câu ngoài corpus

Q96–Q98 là test case Soft Refusal: đáp án gốc không tồn tại trong corpus, `source_document`
rỗng, `expected_citations` rỗng. Chúng không đo retrieval; chúng đo **hành vi từ chối**:

- `refusal_expected = question.get("in_corpus") is False`;
- `refusal_correct = is_refusal` nếu câu ngoài corpus;
- `hallucinated_on_unanswerable = refusal_expected and not is_refusal`.

Với 3 câu, mỗi câu tương đương 33.3 điểm phần trăm. Một câu đổi hành vi làm con số nhảy
một phần ba — không được đọc như xu hướng thống kê.

### 2.3. Vì sao v3 đáng tin hơn v2

Changelog v2.1 ghi rõ một lỗi đã sửa: 97 câu từng dùng **tên văn bản** (“Khung CTĐT CNTT”,
“Quy chế CTSV ĐHAG”) thay vì **tên file corpus**. `source_match` so theo tên file, nên
trước khi sửa, Hit@K/MRR = 0 dù retrieval đúng. Đây là bài học: **metric sai đơn vị so
khớp còn tệ hơn không có metric**, vì nó tạo kết luận ngược.

`data/evaluation/verify_v3_report.md` xác nhận:

- 100/100 câu đúng schema, ID duy nhất;
- 97/97 câu `in_corpus=true` khớp file thật sau `fold()`;
- 3/3 câu ngoài corpus có `source_document` rỗng;
- nhãn `question_type` khớp bảng review 100/100;
- v2 giữ nguyên byte-for-byte (không phá dữ liệu cũ).

### 2.4. Rò rỉ thiết kế — phải nói khi bảo vệ

Có ba nguồn lạc quan:

1. **Few-shot classifier lấy từ chính 100 câu v3** (16 câu). Accuracy 85%/81% trên 100 câu
   là số **có rò rỉ**; trên 84 câu còn lại là 82.1%/77.4% (tính lại ở chương 04).
2. **Source filter của router được thiết kế từ chính v3** rồi đo trên v3. Nhóm được lọc
   đúng nguồn sẽ tăng Hit một cách “học thuộc đề”.
3. **Câu hỏi do người làm đồ án viết**, không lấy từ log người dùng thật. Phân bố 87%
   `TRA_CUU` không đại diện cho lưu lượng thật.

Vì vậy mọi kết luận dạng “hệ thống đạt X%” phải kèm: đo trên 100 câu v3, có rò rỉ few-shot
và filter, không có khoảng tin cậy. Higher-quality evidence cần benchmark v4 viết độc lập
hoặc tập test tách khỏi prompt/filter.

---

## 3. Một lượt đánh giá chạy thế nào

### 3.1. CLI và các cờ

`parse_args` (`evaluation.py:962–985`):

| Cờ | Tác dụng | Bẫy |
|---|---|---|
| `-k/--top-k` | Số chunk generator nhận, mặc định 6 | Bị `retrieve_k` ghi đè khi gọi pipeline — xem mục 6 |
| `--limit N` | Chỉ chạy N câu đầu | Dùng để smoke test, không dùng để báo cáo |
| `--no-judge` | Tắt Gemini judge | Không có điểm faithfulness LLM; phải chạy heuristic sau |
| `--judge-model` | Chọn model giám khảo | Code thực tế mặc định `gemini-3.5-flash-lite` |
| `--use-qwen-generator` | Dùng Qwen local thay Gemini | Không tốn quota; A/B đã dùng cờ này |
| `--with-classifier` | Bật classifier + router + sub-query + prompt theo type | Đây là “WITH”; không có cờ = “WITHOUT” |
| `--benchmark` | Đường dẫn benchmark | **Mặc định là v2**, không phải v3 — luôn truyền tường minh |
| `--output` | JSON chi tiết | Mặc định ghi đè `outputs/evaluation_results.json` |
| `--summary-output` | Markdown tóm tắt | Mặc định ghi đè `outputs/evaluation_summary.md` |
| `--dry-run` | Ước lượng request rồi thoát | Không nạp Chroma, không gọi API |

> **Cảnh báo vận hành:** chạy `evaluation.py` không có `--output` sẽ ghi đè kết quả cũ.
> Với A/B, luôn tách file như tên `ab_results_with_classifier.json` và
> `ab_results_without_classifier.json`.

Lệnh A/B đã dùng (rút gọn):

```bash
# WITHOUT
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/assessment/evaluation.py \
  --benchmark data/evaluation/benchmark_100_questions_v3.json \
  --output outputs/ab_results_without_classifier.json \
  --summary-output outputs/ab_summary_without_classifier.md \
  --use-qwen-generator --no-judge

# WITH
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/assessment/evaluation.py \
  --benchmark data/evaluation/benchmark_100_questions_v3.json \
  --output outputs/ab_results_with_classifier.json \
  --summary-output outputs/ab_summary_with_classifier.md \
  --use-qwen-generator --no-judge --with-classifier
```

Sau đó chấm heuristic và so sánh:

```bash
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/core/faithfulness_heuristic.py \
  outputs/ab_results_without_classifier.json
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/core/faithfulness_heuristic.py \
  outputs/ab_results_with_classifier.json
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe src/assessment/analyze_ab.py
```

### 3.2. Trình tự trong `main`

1. Ép `ENABLE_CLASSIFIER` theo cờ **trước khi** dựng pipeline — pipeline đọc env lúc
   `__init__`, nên đặt sau là vô tác dụng.
2. Nạp benchmark, cắt `--limit`.
3. Nếu `--dry-run`: ước lượng request rồi `return` **trước** khi nạp Chroma/Ollama.
4. Nạp Chroma đã persist; nếu rỗng → `SystemExit`.
5. Kiểm tra Ollama; nếu chết vẫn chạy được nhưng normalization mất ý nghĩa.
6. Chọn generator: Qwen local hoặc Gemini. Với Gemini, **tắt Qwen-fallback** để không đo
   nhầm chất lượng fallback.
7. Chọn judge nếu bật; nếu thiếu key/model → bỏ chấm, không chết lượt.
8. Resume entry cũ nếu meta khớp.
9. Vòng lặp từng câu: chạy, ghi entry, flush JSON sau **mỗi** câu.
10. Tổng hợp `aggregate`, thêm khối classifier nếu WITH, flush lần cuối
    `partial=False`, ghi summary.

### 3.3. `evaluate_question` — entry chứa gì

`evaluation.py:455–561`. Đầu vào: pipeline, judge, question, `top_k`, `retrieve_k`. Đầu ra
một dict (entry) với các nhóm trường:

| Nhóm | Trường | Ghi chú |
|---|---|---|
| Danh tính | `id`, `category`, `raw_query` | Join với benchmark |
| Chuẩn hóa | `normalized_query_expected`, `normalized_query_system`, `retrieval_query`, `normalization_preservation` | Đo bảo toàn số |
| Retrieval | `top_k`, `retrieved_k`, `hit_at_3/5/6/k`, `reciprocal_rank`, `matched_rank`, `retrieved` | `retrieved` lưu source/tier/chunk_id từng rank |
| Sinh | `answer`, `is_refusal_answer`, `predicted_citations` | |
| Citation | `citations` (expected + P/R/F1/EM) | `None` nếu expected rỗng sau extract |
| Từ chối | `refusal_expected`, `refusal_correct`, `hallucinated_on_unanswerable` | |
| Faithfulness | `score`, `unsupported_claims`, `method`, `error` | Judge hoặc heuristic |
| Khác | `number_support`, `latency_seconds`, `predicted_labels`, `retrieval_config`, `expected_question_type`, `generation_scoring` | |
| Ngữ cảnh | `contexts` | Chỉ lưu khi judge tắt |

Chi tiết dễ bỏ sót:

- `contexts` chỉ được ghi khi `judge_model is None` (`:543–545`). Nếu bật judge, JSON
  không có ngữ cảnh để chấm heuristic sau — muốn chấm cả hai phải chạy lại.
- `citations` chỉ được tạo nếu `expected_citations` **sau khi extract** khác rỗng
  (`:547–551`). Vì vậy 68/100 câu có `citations = null`; xem mục 5.
- `number_support` trả `None` cho câu từ chối (`:530`), nên mẫu số của chỉ số này nhỏ hơn
  97 và không được báo cáo trong summary.
- `generation_scoring = "skipped_no_gt"` cho Q96–Q98 vì không có GT để chấm sinh; hành vi
  từ chối vẫn được chấm.

### 3.4. Resume, flush, partial — chống mất quota

**Resume** (`load_resumable_entries`, `:776–822`) dùng lại entry cũ nếu:

- file tồn tại, đọc được;
- `meta.benchmark` và `meta.with_classifier` khớp;
- `meta.judge_enabled` khớp;
- entry không lỗi, có `answer`;
- nếu judge bật: có `faithfulness.score` và lỗi judge sạch (hoặc đúng là `"refusal"`).

Điểm mạnh: judge không có cache, nên resume là cách duy nhất tránh chấm lại 100 câu.

Điểm yếu — **khóa resume thiếu tham số**: không kiểm tra `top_k`, `retrieve_k`, generator
model, `PROMPT_VERSION`. Nếu lượt trước chạy `-k 6`, lượt sau chạy `-k 4` cùng file, các
entry cũ vẫn được dùng lại nhưng `meta` mới ghi `top_k=4`. Kết quả là bảng ghi 4 trong khi
entry được sinh với 6 ngữ cảnh. Tương tự khi đổi từ Gemini sang Qwen. Cách sửa: đưa
`top_k`, `retrieve_k`, `generator_model` vào điều kiện khớp meta.

**Flush** (`flush_partial_results`, `:825–848`) ghi JSON sau từng câu với `partial=True`;
lần cuối ghi `partial=False`. Nếu bị kill giữa chừng, file vẫn có phần đã chạy. Đây là lý
do A/B có thể chạy 100 câu qua nhiều phiên mà không mất trắng.

**PerDay**: judge trả lỗi có marker `PerDay` → vòng lặp chính dừng cả lượt; resume đúng
lệnh cũ sẽ chỉ chấm nốt phần thiếu. Lỗi 429 theo phút thì chờ 60s và thử lại đúng câu đó
tối đa 3 lần (`judge_faithfulness`, `:362–436`). Generator cũng có cơ chế tương tự.

### 3.5. Dry-run — ước lượng trước khi tiêu quota

`estimate_requests` (`:714–761`) đếm cache-hit bằng cách so `raw_query` và
`normalized_query` kỳ vọng với trường `query` trong `.generation_cache/`, sau `fold()`.
Nó lọc đúng model nếu truyền `generator_model`, vì cache key SHA-1 có cả model.

Ba giới hạn:

- normalized query thật của hệ thống có thể khác bản kỳ vọng → ước lượng chỉ là ước lượng;
- judge luôn in **cận trên** 1 request/câu; câu tự từ chối tốn 0 nhưng không biết trước;
- cache không có TTL/eviction; đếm cache-hit không đảm bảo nội dung cache còn đúng với
  prompt hiện tại nếu `PROMPT_VERSION` bị đổi mà quên xóa cache (xem chương 06).

---

## 4. Retrieval được đo thế nào

### 4.1. `source_match` — khớp ở mức tài liệu

```python
def source_match(chunk_source: str, expected_document: str) -> bool:
    a, b = fold(chunk_source), fold(expected_document)
    return bool(a and b) and (b in a or a in b)
```

Đây là so khớp **chuỗi con** sau khi bỏ dấu, không phải so sánh đường dẫn tuyệt đối. Hệ quả:

- Chunk lấy từ đúng file → Hit, dù chunk đó có chứa câu trả lời hay không.
- Tên file này là chuỗi con của tên file khác → có thể khớp nhầm (hiếm nhưng có).
- Câu ngoài corpus có `expected_document` rỗng → `bool(b)` false → không bao giờ Hit.

Vì vậy Hit@K là **recall ở mức tài liệu**, không phải độ chính xác của đoạn văn. Một hệ
thống có Hit@6 = 100% vẫn có thể trả lời sai nếu chunk đúng file nhưng sai điều.

### 4.2. Hit@3/5/6 và MRR

Trong `evaluate_question`:

```python
sources, contexts, answer = result["sources"], result["contexts"], result["answer"]
hits = [source_match(s["source"], expected_document) for s in sources]
matched_rank = next((i + 1 for i, hit in enumerate(hits) if hit), None)
```

- `Hit@3 = any(hits[:3])`, tương tự 5 và 6.
- `MRR = 1 / matched_rank` trên **toàn bộ** `sources`, không cắt ở 6. Đây là điểm quan
  trọng: nếu chunk đúng nằm ở rank 11, MRR vẫn 1/11 dù Hit@6 = False.
- `retrieved_k = len(sources)` là cửa sổ thực; `retrieval.top_k` là tham số khai báo.

Ví dụ Q02 trong A/B:

| Lượt | sources | matched_rank | Hit@3 | Hit@5 | MRR |
|---|---:|---:|---|---|---:|
| WITHOUT | 12 | 3 | True | True | 0.3333 |
| WITH | 13 | 1 | True | True | 1.0000 |

Hit@3 không đổi (cả hai đều có trong top 3), nhưng MRR tăng gấp ba. Nếu chỉ nhìn Hit, ta
bỏ lỡ cải thiện về thứ hạng — đây là lý do phải báo cáo cả Hit và MRR.

### 4.3. Mẫu số 97 và mẫu số nhỏ

`aggregate` tính:

```python
"mrr": _mean([... for e in scored if e["retrieval"]["hit_at_k"] is not None])
"n_retrieval_scored": 97
```

Hit@3/5/6 cũng là trung bình trên các câu có `hit_at_*` khác `None`, tức 97 câu. Vì vậy
A/B ghi `Hit@3 = 77.3%` thực chất là **75/97**, không phải 75/100. Báo cáo A/B không in
mẫu số này trong bảng tổng thể — khi bảo vệ phải nói rõ.

Với 97 câu, một câu tương đương ~1.03 điểm phần trăm. Chênh lệch 3 câu (46 vs 49 từ chối
oan) là ~3.1 điểm. Không có khoảng tin cậy; đừng nói “tăng có ý nghĩa thống kê”.

---

## 5. Citation — chỉ số bị lỗi nặng nhất

### 5.1. Cách trích xuất

`extract_citations` (`evaluation.py:139–191`) chỉ hiểu **Điều/Khoản**:

- `Điều 10` → `{"dieu 10"}`;
- `Điều 10, Khoản 2` → `{"dieu 10 khoan 2"}`;
- `Khoản 2` đứng một mình → **rỗng** (không có Điều để bám);
- `Điều 10–12` → bung thành `dieu 10`, `dieu 11`, `dieu 12`;
- `Mục 8`, `STT 57`, `CON915`, `2 tín chỉ`, tên file → **không được trích**.

Hệ quả trực tiếp: `expected_citations` của 100 câu v3 phần lớn là mã môn, con số, mục,
tên văn bản. Chỉ **32/100 câu** có ít nhất một Điều/Khoản sau extract. Vì vậy
`n_citation_scored = 32` trong cả hai lượt A/B; 68 câu còn lại có `citations = null` và
không tham gia điểm Citation.

Một lỗi phụ: expected citations thường tách `"Điều 8"` và `"Khoản 3"` thành hai phần tử.
`extract_citations("Khoản 3")` trả rỗng, nên kỳ vọng chỉ còn `"dieu 8"`; điểm có thể
“đúng” dù thiếu Khoản 3. Q36, Q42, Q46, Q48 là ví dụ.

### 5.2. Khớp mềm và maximum matching

`_citation_pair_weight` (`:208–217`):

| Cặp | Điểm |
|---|---:|
| Khác Điều | 0.0 |
| Cùng Điều, cùng Khoản | 1.0 |
| Cùng Điều, một bên chỉ có Điều | 0.5 |
| Cùng Điều, khác Khoản | 0.0 |

`_citation_true_positives` (`:220–240`) thử mọi cách ghép cặp predicted–expected và lấy
tổng điểm lớn nhất. Nhờ vậy `{dieu 5}` khớp `{dieu 5 khoan 2}` được 0.5 thay vì 0.

Ba hằng số `CITATION_PAIR_WINDOW`, `CITATION_RANGE_CAP`, `CITATION_PARTIAL_WEIGHT`
(`:111–113`) được khai báo nhưng **không dùng**; giá trị 0.5 và việc bung dải đang
hard-code. Đây là nợ kỹ thuật: người đọc tưởng có thể chỉnh bằng hằng số, nhưng không.

### 5.3. Lỗi chí mạng: predicted rỗng được điểm 1.0

`citation_scores` (`:243–290`) có đoạn:

```python
if source_document:
    source_folded = fold(source_document)
    predicted_folded = fold(" ".join(predicted))
    if source_folded in predicted_folded or predicted_folded in source_folded:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "exact_match": 1.0}
```

Nếu `predicted` rỗng thì `predicted_folded = ""`, và **chuỗi rỗng luôn là chuỗi con của
mọi chuỗi**. Điều kiện thứ hai `"" in source_folded` luôn đúng. Vậy:

> Câu trả lời **không có trích dẫn nào** được chấm Precision = Recall = F1 = EM = 1.0.

Không phải giả thuyết. Kiểm chứng bằng chính dữ liệu:

- WITH: 5/32 câu có `predicted_citations = []` và `citations.f1 = 1.0` (Q31, Q36, Q42,
  Q46, Q48);
- WITHOUT: 3/32 câu tương tự (Q42, Q45, Q46);
- `outputs/evaluation_summary.md` cũ (Gemini, 18-10): 25/32 câu predicted rỗng → F1 báo
  cáo **78.1% = 25/32**, trong khi tính lại đúng bằng matching là **0.0%**.

Công thức báo cáo bị thổi phồng đúng bằng tỉ lệ câu rỗng:

```
F1_báo_cáo = F1_đúng + (số_câu_predicted_rỗng / n) × 1.0
WITH:    0.1010 + 5/32 = 0.2573  (khớp 25.7% trong JSON)
WITHOUT: 0.0402 + 3/32 = 0.1340  (khớp 13.4% trong JSON)
Gemini cũ: 0.0 + 25/32 = 0.781   (khớp 78.1%)
```

Tôi tính lại hai lượt A/B bằng `_citation_true_positives` trực tiếp, bỏ hẳn đường tắt:

| Lượt | F1 trong JSON | F1 tính lại | Precision | Recall | Exact Match | n |
|---|---:|---:|---:|---:|---:|---:|
| WITHOUT | 13.4% | **4.02%** | 6.25% | 3.65% | 3.12% | 32 |
| WITH | 25.7% | **10.10%** | 9.22% | 14.06% | 6.25% | 32 |

Xu hướng vẫn tăng (10.1% so với 4.0%, tương đối +151%), nhưng mức tuyệt đối thấp hơn
nhiều so với con số 25.7% đang nằm trong báo cáo. Khi bảo vệ, nếu trích “Citation F1 tăng
từ 13.4% lên 25.7%” mà không nói lỗi này, đó là báo cáo sai. Cách nói đúng:

> “Trên 32 câu có trích dẫn Điều/Khoản, sau khi bỏ đường tắt chấm điểm, F1 tăng từ 4.0%
> lên 10.1%. Con số 13.4%/25.7% trong JSON bị thổi phồng bởi lỗi chấm câu không trích dẫn
> thành đúng tuyệt đối.”

### 5.4. Cách sửa đúng

1. Bỏ nhánh `source_document` hoàn toàn. Nếu muốn thưởng việc nêu đúng tên file, hãy tách
   thành metric riêng (`source_citation_hit`), không gộp vào P/R/F1.
2. Xử lý rỗng tường minh:

```python
if not predicted:
    return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "exact_match": 0.0}
if not expected:
    return None
```

3. Chỉ chấm khi expected không rỗng, và **báo cáo n**. Không bao giờ gộp câu không chấm
   vào mẫu số.
4. Mở rộng extractor cho `Mục`, `Chương`, `STT`, tên file/mã môn nếu muốn đo đúng loại
   trích dẫn mà benchmark kỳ vọng; hoặc viết lại `expected_citations` về đúng Điều/Khoản.
5. Thêm test hồi quy: predicted rỗng + source_document có giá trị → F1 phải 0, không phải 1.

---

## 6. Lỗi `top_k` / `retrieve_k` — cửa sổ đo và cửa sổ sinh lệch nhau

### 6.1. Code đang gọi gì

`evaluation.py:471`:

```python
result = pipeline.run(question["raw_query"], top_k=retrieve_k)
```

Trong khi docstring ngay trên (`:459–466`) nói generator chỉ nhận `top_k`. Sai khi
`top_k != retrieve_k`.

`main` tính `retrieve_k = max(top_k, MIN_TOP_K)` (`:995`), với `MIN_TOP_K = 6`. Pipeline
lại tự nhân đôi để oversample:

```
pipeline.run(top_k=X) → effective_top_k = X (router có thể +2)
                      → sources = 2 × effective_top_k (sau dedupe có thể ít hơn)
                      → contexts = effective_top_k
```

Vì evaluation truyền `retrieve_k`, ta có bảng:

| Lệnh | `top_k` khai báo | `retrieve_k` | pipeline nhận | contexts thực | sources thực | `hit_at_k` đo |
|---|---:|---:|---:|---:|---:|---|
| `-k 4` | 4 | 6 | 6 | 6 | 12 | 4 chunk đầu |
| mặc định | 6 | 6 | 6 | 6 | 12 | 6 chunk đầu |
| `-k 8` | 8 | 8 | 8 | 8 | 16 | 8 chunk đầu |
| WITH, câu SO_SANH | 6 | 6 | 6 → router +2 | 8 | 13–16 | 6 chunk đầu |

Hệ quả:

- Với `-k 4`, câu trả lời được sinh từ **6** ngữ cảnh nhưng bảng ghi `top_k=4` và Hit@4
  đo trên 4. Đây là bất nhất giữa “đo” và “sinh”.
- Trong A/B, `meta.top_k=6`, `meta.retrieve_k=6`; contexts thực tế là 6 cho 86 câu và
  **8 cho 14 câu SO_SANH** (router cộng 2). `retrieved_k` thực tế phân bố 11 (12 câu),
  12 (74), 13 (7), 16 (7). Bảng A/B không ghi các cửa sổ này.
- Docstring `top_k: số chunk generator nhận AND ngưỡng đo Hit@top_k` chỉ đúng khi
  `top_k == retrieve_k` (mặc định 6/6). Đừng tin docstring khi truyền `-k` khác 6.

### 6.2. Vì sao chuyện này quan trọng khi bảo vệ

Nếu hội đồng hỏi “Top-K của em là 6, vậy vì sao câu SO_SANH lại trả lời với 8 chunk?”, câu
trả lời đúng là: router cố ý tăng 2 cho câu so sánh, và evaluation đang truyền
`retrieve_k` thay vì `top_k`, nên hiệu ứng router lấn cả vào cửa sổ sinh. Đây là **lỗi
truyền tham số** (lẫn cửa sổ đo với cửa sổ sinh), không phải sai toàn bộ kết quả — nhưng
phải nói rõ.

Cách sửa tối thiểu:

```python
result = pipeline.run(question["raw_query"], top_k=top_k)
```

Khi đó với `-k 4`, pipeline sinh từ 4, sources = 8 (đủ Hit@6 nhưng MRR đổi cửa sổ từ 12
xuống 8); với mặc định 6, sources = 12; với SO_SANH, sinh từ 8. Muốn giữ recall window 12
cho mọi câu trong khi sinh từ 4, phải thêm tham số `recall_window` vào `run()` — hiện
pipeline chưa có.

Trước khi sửa, mọi báo cáo nên ghi rõ: “cửa sổ sinh thực tế = 6 (8 với SO_SANH), cửa sổ
đo = 11–16 tùy câu; metadata ghi 6/6 là tham số khai báo, không phải cửa sổ thực.”

### 6.3. Vì sao sources có 11, 13, 16?

- 12 = 6 × 2 (mặc định).
- 11 = sau khi hợp nhất/khử trùng lặp chỉ còn 11 chunk duy nhất.
- 13 = câu SO_SANH có sub-query, hợp nhất hai nhánh, khử trùng lặp còn 13.
- 16 = SO_SANH 8 × 2.

`merge_subquery_results` lấy theo rank tốt nhất và cắt ở `retrieve_k`; số lượng thực có
thể nhỏ hơn do trùng `chunk_id`. Đây là hành vi bình thường, nhưng phải giải thích được.

---

## 7. Đo chất lượng câu trả lời

### 7.1. `number_support` — proxy rẻ, không phải sự thật

`number_support` (`:333–339`) lấy mọi số trong answer (sau `fold`) và kiểm tra chuỗi con
trong pool contexts. Trả `None` nếu answer không có số; câu từ chối cũng `None`.

Ưu điểm: miễn phí, bắt được lỗi bịa số. Nhược điểm:

- So khớp chuỗi con: số `5` được coi là “có trong ngữ cảnh” nếu contexts chứa `15` hoặc
  `2025`. Đây là false support.
- Không kiểm tra số đó có đúng vai trò hay không: contexts có “15 tín chỉ” và answer nói
  “5 tín chỉ” vẫn có thể được 1.0 nếu `5` xuất hiện ở chỗ khác.
- Answer copy nguyên đoạn văn → 1.0 dù có thể trả lời sai câu hỏi.

A/B: WITHOUT 96.6%, WITH 93.6%. Đừng đọc là “độ trung thực giảm 3 điểm”; đọc là “tỉ lệ
con số tìm thấy trong ngữ cảnh giảm nhẹ, có thể do câu trả lời dài/khác context hơn”.

### 7.2. `normalization_preservation` — chỉ 30 câu được kiểm

`normalization_preservation` (`:308–330`) lấy token `dieu/khoan + số` và các số còn lại
từ câu gốc, kiểm tra chuỗi con trong câu chuẩn hóa. Chỉ câu có số mới có điểm; A/B có
**30 câu** được kiểm, 96.7% bảo toàn (29/30).

Ba giới hạn:

- So khớp chuỗi con: token `5` “bảo toàn” nếu câu mới chứa `15`.
- Số viết bằng chữ (“hai lần”) không được quy đổi.
- Câu không có số → `score=None`, bị loại khỏi mẫu số. Vì vậy 96.7% không đại diện cho
  100 câu.

Điểm này quan trọng vì pipeline production gọi `normalize_user_query` — hàm này
**không** dùng guardrail của `LocalSLM.normalize_query` (xem chương 04). Ta đang đo hệ
quả trên 30 câu, không đo được guardrail vì guardrail không chạy.

### 7.3. Từ chối: chỉ số bị bỏ quên

`is_refusal = fold(REFUSAL_MARKER) in fold(answer)`. Đây là phép so đã sửa ở P4.1: trước
đó marker có dấu, answer đã fold, nên không bao giờ khớp và mọi “từ chối đúng” bằng 0.

Các trường:

- `refusal_expected = in_corpus is False`;
- `refusal_correct` chỉ có giá trị với 3 câu ngoài corpus;
- `hallucinated_on_unanswerable` = câu ngoài corpus nhưng không từ chối;
- **không có** trường “false refusal” trong entry; nó được suy ra bằng
  `is_refusal_answer` trên câu `in_corpus=true` (`false_refusal_stats`, `:687–711`).

A/B:

| Lượt | Từ chối oan in-corpus | Từ chối đúng ngoài corpus | Ảo giác ngoài corpus |
|---|---:|---:|---:|
| WITHOUT | 46/97 (47.4%) | 1/3 (33.3%) | 2 |
| WITH | 49/97 (50.5%) | 1/3 (33.3%) | 2 |

Đây là con số đáng lo nhất của đồ án. Gần một nửa câu **có đáp án trong corpus** bị từ
chối. Nguyên nhân nền không phải classifier: WITHOUT không có classifier mà vẫn 46/97.
Đó là guardrail/model local (Qwen 1.5B) quá nhạy với từ chối. WITH làm tăng 3 câu, trong
đó 7 câu bị gán nhầm `NGOAI_PHAM_VI` và bị prompt từ chối; nhưng mức nền đã cao từ trước.

Hệ quả cho metric: câu từ chối oan được `faithfulness = 1.0` (không có khẳng định để
phản bội), `number_support = None`, và thường không có citation. Vì vậy bảng tổng hợp có
thể trông “ổn” trong khi gần nửa câu trả lời vô dụng. Luôn đọc false refusal trước khi đọc
Hit/MRR.

### 7.4. Faithfulness bằng LLM judge

`judge_faithfulness` (`:362–436`):

1. Nếu answer chứa REFUSAL_MARKER → trả 1.0, lỗi `"refusal"` (không gọi API).
2. Ghép contexts thành block, gọi Gemini với `JUDGE_PROMPT` yêu cầu tách khẳng định và
   đánh dấu `supported`.
3. Lần 1 dùng JSON mode; nếu parse hỏng, lần 2 gọi lại không JSON mode rồi parse mềm.
4. 429 theo phút → chờ 60s, tối đa 3 lần; PerDay → trả lỗi có marker để dừng lượt;
   404/not found → bỏ chấm; lỗi tạm thời → chờ 15s/30s.
5. Điểm = số khẳng định supported / tổng khẳng định.

Lưu ý tinh tế: khi từ chối, hàm trả `error="refusal"`, nhưng entry gán
`method = "llm_judge"` vì điều kiện `not judge_error` false. Nhãn `"refusal"` thực tế
không bao giờ được dùng. Đây là lỗi nhãn nhỏ, không ảnh hưởng điểm nhưng ảnh hưởng truy
vết.

A/B **tắt judge** vì quota; do đó `faithfulness_llm = null`, `n_faithfulness_scored = 0`
trong cả hai JSON. Không được trích cột này từ A/B.

### 7.5. Faithfulness heuristic — công cụ thay thế, có điều kiện

`src/core/faithfulness_heuristic.py`:

```python
answer_tokens = extract_meaningful_tokens(answer)
context_tokens = extract_meaningful_tokens(" ".join(contexts))
score = len(answer_tokens & context_tokens) / len(answer_tokens)
```

- Từ chối chuẩn → 1.0.
- Không có context/answer → 0.0.
- Bỏ stopword tiếng Việt; giữ số.
- **Không gọi `fold()`** cho token (chỉ fold marker). Vì vậy answer có dấu và context OCR
  mất dấu sẽ giảm overlap một cách giả tạo. Đây là lỗi cần sửa nếu dùng lâu dài.
- Không phải semantic matching: answer paraphrase đúng vẫn bị điểm thấp; answer copy
  nguyên context được điểm cao.

A/B sau khi chấm heuristic:

| Cách tính | WITHOUT | WITH |
|---|---:|---:|
| Trung bình **chỉ câu trả lời** (n=53 / 50) | 0.643 | 0.647 |
| Trung bình gộp cả từ chối (score 1.0, n=100) | 0.811 | 0.823 |

Chênh lệch 0.811 − 0.643 = 0.168 chính là phần thưởng từ 47% câu từ chối. Vì vậy
`analyze_ab.py` loại từ chối khỏi trung bình (`faith_answered`). Nếu ai đọc thẳng
`faithfulness` trong JSON sẽ thấy số cao hơn và kết luận sai.

Hai lượt gần như bằng nhau (0.643 vs 0.647). Kết luận đúng: **không có bằng chứng
classifier/router cải thiện độ trung thực token-level**; khác biệt nằm trong nhiễu của
50–53 câu và công cụ đo thô.

### 7.6. Quy trình chấm heuristic sau lượt chạy

`compute_faithfulness_for_json`:

- đọc JSON, bỏ entry lỗi/không answer/không contexts;
- ghi `faithfulness = {score, unsupported_claims: [], method: "heuristic_local", error: None}`;
- ghi đè file JSON;
- **không** cập nhật `aggregates`.

Vì vậy sau khi chạy heuristic, `aggregates.faithfulness_llm` vẫn null và
`n_faithfulness_scored` vẫn 0. Chỉ `per_question` thay đổi. `analyze_ab.py` đọc lại
per_question và tự tính. Đây là lý do báo cáo A/B có Faithfulness còn summary một lượt
thì không.

---

## 8. Tổng hợp, nhóm và các thống kê phụ

### 8.1. `aggregate`

`aggregate` (`:570–610`) là nguồn của mọi con số tổng thể:

| Khóa | Cách tính | Mẫu số thực tế A/B |
|---|---|---:|
| `hit_at_3/5/6` | Trung bình trên entry có hit khác None | 97 |
| `mrr` | Trung bình RR trên entry có `hit_at_k` khác None | 97 |
| `citation_*` | Trung bình trên entry có `citations` khác None | 32 |
| `faithfulness_llm` | Trung bình score khác None (gồm từ chối 1.0) | 0 (judge tắt) |
| `number_support` | Trung bình trên entry có số, trừ từ chối | < 97 |
| `normalization_preservation` | Trung bình trên entry có score khác None | 30 |
| `refusal_correct_rate` | Trung bình trên 3 câu ngoài corpus | 3 |
| `avg_latency_seconds` | Trung bình trên entry không lỗi | 100 |

Điểm cần nhớ: **mỗi chỉ số có mẫu số riêng**. Bảng tổng hợp không in mẫu số, nên người
đọc dễ tưởng tất cả đều trên 100. Khi viết báo cáo, thêm cột `n`.

### 8.2. `classification_stats`

Chỉ chạy khi `--with-classifier` (`aggregates.classifier`). So `predicted_labels.topic`
với `category` và `predicted_labels.question_type` với `question_type`, sau `fold`.

A/B WITH:

| Chỉ số | Giá trị | Ghi chú |
|---|---:|---|
| Topic accuracy | 87.0% | Cao hơn P2.3 85% do 16 câu few-shot nằm trong tập đo |
| Type accuracy | 83.0% | Cao hơn P2.3 81%; vẫn **thấp hơn baseline đoán mù TRA_CUU 87%** |
| Số câu chấm | 100 | |

Con số type 83% là một nghịch lý cần nói: một classifier luôn đoán `TRA_CUU` đã đạt 87%.
Vậy classifier 83% **kém hơn** baseline đa số về accuracy. Giá trị thật của nó nằm ở
recall lớp hiếm (SO_SANH/THU_TUC/NGOAI đều 100% trong P2.3), nhưng đổi lại precision lớp
hiếm rất thấp (33.3%, 100%, 25%). Router dùng nhãn dự đoán, nên over-predict lớp hiếm
gây hại: 14 câu bị gán SO_SANH (thực tế 5), 11 câu bị gán NGOAI (thực tế 3).

### 8.3. `group_metrics` và `false_refusal_stats`

`group_metrics` (`:659–684`) gom theo predicted type hoặc category; MRR chỉ trên câu có
tiêu chí truy xuất; Citation chỉ trên câu có `citations`; Faithfulness lấy trung bình
score (gồm từ chối). `false_refusal_stats` (`:687–711`) gom câu in-corpus theo predicted
type và đếm `is_refusal_answer`.

Trong `analyze_ab.py`, nhóm được tính lại từ `per_question` với Faithfulness **loại từ
chối**, khác `group_metrics` của evaluation. Hai chỗ có thể cho số khác nhau — đừng trộn
bảng từ hai nguồn.

### 8.4. `format_summary_md` — báo cáo một lượt

`format_summary_md` (`:873–958`) in bảng tổng hợp, bảng nhóm (nếu WITH), và bảng từng câu.
Ba điểm cần biết:

- Tiêu đề luôn là “Faithfulness (LLM judge)” kể cả khi judge tắt; giá trị sẽ `n/a`.
- Bảng từng câu chỉ hiển thị Hit@6, RR, Citation F1, Faithfulness — không có Hit@3/5.
- Dòng “Từ chối đúng” dùng `aggregates['refusal_correct_rate']`; nếu rate = 0.0, biểu
  thức `value and pct(value) or 'n/a'` sẽ in `n/a` thay vì 0.0%. Với A/B rate 33.3% nên
  không lộ; nhưng đây là bug tiềm ẩn.

---

## 9. `evaluate_classifier.py` — đo classifier và baseline kNN

### 9.1. Luồng chạy

- `load_questions` đọc đúng 100 câu v3, raise nếu khác.
- `run_pass` gọi `classify_query(raw_query)` — câu **thô**, đúng như pipeline thật.
- So topic bằng `fold`, type bằng so khớp chính xác.
- `per_class_metrics`: precision/recall/F1 từng lớp + macro-F1.
- `write_confusion_csv`: ma trận nhầm lẫn; topic có cột `<không xác định>` cho `None`.
- `--runs N`: chạy lặp để kiểm tra ổn định (temperature 0).
- `--method embedding`: baseline kNN bge-m3, leave-one-out, k=1/3/5; ghi
  `results_knn.json` và nối bảng vào `accuracy_report.md`.

Kết quả P2.3 (100 câu):

| Lớp | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| TRA_CUU | 100.0% | 78.2% | 87.7% | 87 |
| SO_SANH | 33.3% | 100.0% | 50.0% | 5 |
| THU_TUC | 100.0% | 100.0% | 100.0% | 5 |
| NGOAI_PHAM_VI | 25.0% | 100.0% | 40.0% | 3 |
| Macro-F1 | | | 69.4% | |

Đọc bảng này đúng cách: model **không bỏ sót** lớp hiếm (recall 100%) nhưng **gán nhầm
rất nhiều** câu TRA_CUU vào lớp hiếm (precision thấp). Với router, đây là hướng sai nguy
hiểm: câu tra cứu bị đẩy sang prompt từ chối hoặc sub-query.

### 9.2. Bốn lỗi trong script đo

1. **Repeat check gộp hai nhãn.** `unstable` được tăng nếu **topic hoặc type** đổi, rồi
   `topic_stable` và `type_stable` đều tính `limit - len(unstable)`. Hai cột luôn bằng
   nhau, không đo riêng từng nhãn. Muốn đúng phải có hai tập unstable riêng.
2. **kNN là leave-one-out trên chính 100 câu**, không có train/test. Nó là baseline tham
   khảo, không phải kết quả tổng quát hóa.
3. **Bảng so sánh hard-code Qwen 85/81**, không đọc từ lần chạy hiện tại; và
   `append_knn_section` nối thêm mỗi lần chạy, tạo mục trùng.
4. **Không so sánh cùng điều kiện**: Qwen dùng 16 few-shot lấy từ chính benchmark; kNN
   dùng vector của chính câu cần đo. Cả hai đều lạc quan, nhưng theo cách khác nhau.

Kết quả kNN:

| Phương pháp | Topic accuracy | Type accuracy |
|---|---:|---:|
| Qwen few-shot (P2.3) | 85.0% | 81.0% |
| kNN bge-m3 (k=1) | 76.0% | 85.0% |
| kNN bge-m3 (k=3) | 72.0% | **89.0%** |
| kNN bge-m3 (k=5) | 76.0% | 86.0% |

kNN **thắng** Qwen ở type accuracy và **thua** ở topic. Vì vậy không thể nói “phải dùng
LLM vì LLM chính xác hơn toàn diện”. Kết luận trung thực: Qwen tốt hơn ở phân loại chủ
đề (14 lớp, cần hiểu ngữ nghĩa), nhưng với 4 loại câu hỏi và phân bố 87% một lớp, kNN
đạt accuracy cao hơn nhờ đoán theo láng giềng; cả hai đều over-predict lớp hiếm. Muốn
chứng minh LLM cần thiết phải đo thêm chi phí, khả năng giữ recall lớp hiếm, và chất
lượng router cuối, không chỉ accuracy.

---

## 10. A/B — đọc báo cáo `analyze_ab.py` mà không tự lừa mình

### 10.1. `analyze_ab.py` làm gì

1. Đọc benchmark v3 + 2 JSON kết quả.
2. Bảng tổng thể đọc thẳng `aggregates` (trừ Faithfulness tính lại từ `per_question`).
3. Tính nhóm theo `question_type` kỳ vọng và `category`, từ `per_question`.
4. Tính phân bố predicted type của lượt WITH.
5. Phân tích từ chối oan, đối chiếu 19 câu misroute trong `logs/classifier/results.json`.
6. Kiểm GATE: Hit@3/5/6 và MRR không giảm quá 5% tương đối.
7. Vẽ 3 biểu đồ vào `outputs/figures/`.

Các con số A/B chính:

| Chỉ số | WITHOUT | WITH | Chênh |
|---|---:|---:|---:|
| Hit@3 (n=97) | 60.8% | 77.3% | +16.5 pp |
| Hit@5 (n=97) | 65.0% | 78.3% | +13.4 pp |
| Hit@6 (n=97) | 66.0% | 78.3% | +12.4 pp |
| MRR (n=97) | 0.5097 | 0.7689 | +0.2592 |
| Citation F1 JSON (n=32) | 13.4% | 25.7% | +12.3 pp |
| Citation F1 tính lại (n=32) | 4.0% | 10.1% | +6.1 pp |
| Faithfulness trả lời (n=53/50) | 0.643 | 0.647 | +0.004 |
| Từ chối oan | 46/97 | 49/97 | +3 câu |
| Từ chối đúng ngoài corpus | 1/3 | 1/3 | 0 |
| Ảo giác ngoài corpus | 2 | 2 | 0 |
| Latency | 2.30s | 7.79s | +5.49s |
| Topic accuracy | — | 87.0% | — |
| Type accuracy | — | 83.0% | — |

GATE tương đối: Hit@3 +27.1%, Hit@5 +20.6%, Hit@6 +18.7%, MRR +50.9% → ĐẠT (ngưỡng
−5%). Nhưng GATE chỉ kiểm bốn chỉ số retrieval; nó **không** kiểm false refusal, citation,
faithfulness. “GATE ĐẠT” không đồng nghĩa “hệ thống tốt”.

### 10.2. Năm lý do không được quy toàn bộ mức tăng cho classifier

Lượt WITH bật **một gói** thay đổi:

1. classifier dự đoán nhãn;
2. router đổi `top_k`, trọng số BM25/Chroma, source filter;
3. sub-query chỉ bật cho SO_SANH;
4. prompt generator có appendix theo type;
5. cửa sổ sinh thực tế khác (SO_SANH 8 thay vì 6), và cửa sổ đo khác (11–16).

Không có ablation từng thành phần, nên câu đúng là: “**gói classifier + router + prompt +
sub-query** cải thiện retrieval trên benchmark v3”, không phải “classifier làm tăng 27%”.
Muốn tách công lao phải chạy thêm các lượt: chỉ classifier (không router), chỉ router với
nhãn vàng, chỉ sub-query, chỉ prompt. Đây là bài tập lớn nếu muốn bảo vệ chắc.

### 10.3. Nhóm tăng/giảm — đọc kèm n

| Nhóm | n | ΔHit@3 | Đọc thế nào |
|---|---:|---:|---|
| chương trình đào tạo | 22 | +45.5 pp | Tăng mạnh, đáng tin hơn nhóm nhỏ |
| khen thưởng sinh viên | 10 | +40.0 pp | Tăng mạnh, n vừa |
| TRA_CUU (expected) | 87 | +18.4 pp | Nhóm đóng góp chính |
| đánh giá rèn luyện | 11 | −18.2 pp | Giảm, cần điều tra |
| thực tập chuyên đề | 3 | −33.3 pp | n quá nhỏ, chỉ là gợi ý |

Nhóm SO_SANH expected chỉ 5 câu: Hit@3 giữ 80%, MRR 0.4333 → 0.8286. Đừng nói “SO_SANH
tăng 40 điểm Hit” — không có; cái tăng là thứ hạng. Q02 là dẫn chứng: rank 3 → 1.

Nhóm `NGOAI_PHAM_VI` expected 3 câu có MRR 0.0000 ở cả hai lượt — đúng như thiết kế, vì
không có tài liệu đúng để khớp. Đừng đưa nhóm này vào trung bình retrieval; nó bị loại
bởi `hit_at_k is None`.

### 10.4. Từ chối oan — phân tích nguyên nhân

- WITHOUT 46/97, WITH 49/97: chênh +3 câu.
- 7 câu WITH bị gán nhầm `NGOAI_PHAM_VI` và từ chối oan: Q08, Q12, Q36, Q46, Q48, Q60,
  Q86.
- Trong 19 câu misroute của classifier, 9 câu bị từ chối oan ở WITH.
- Nhưng 46 câu WITHOUT đã từ chối oan dù không có classifier → nguyên nhân nền là
  guardrail + Qwen 1.5B quá nhạy, không phải classifier.

Kết luận đúng: classifier **góp phần** (7 câu trực tiếp, 9/19 misroute), nhưng **không
phải nguyên nhân chính**. Muốn giảm false refusal phải sửa prompt/guardrail/generator,
không chỉ sửa classifier.

### 10.5. Vì sao A/B không dùng số Citation 25.7%

Như mục 5.3: 5/32 câu WITH và 3/32 câu WITHOUT không có trích dẫn nhưng được 1.0. Báo
cáo `ab_comparison.md` lấy thẳng `aggregates` nên vẫn in 13.4%/25.7%. Đây là **lỗi đã
biết**, không phải số đúng. Khi bảo vệ, trình bày cả hai và nói rõ phép tính lại.

### 10.6. Vì sao A/B không dùng latency để kết luận chất lượng

WITH chậm hơn 3.4 lần: classifier gọi Qwen thêm ~2.5s/câu, sub-query thêm truy xuất,
context 8 thay vì 6, cache pattern khác. Hai lượt chạy song song trên cùng máy nên
latency phụ thuộc tải. Chỉ dùng latency để nói chi phí, không dùng để nói “WITH tốt hơn”
hay “WITH kém hơn”.

### 10.7. Vì sao A/B không đại diện production

- Generator là Qwen 2.5 1.5B local, không phải Gemini 2.5 Flash.
- Judge tắt; faithfulness là heuristic token-overlap.
- 100 câu v3 có rò rỉ few-shot/filter.
- Không có khoảng tin cậy; nhiều nhóm n < 10.
- Câu ngoài corpus chỉ 3.

Vì vậy A/B trả lời câu hỏi: “**logic classifier/router/prompt có cải thiện retrieval trên
bộ câu này không?**” Nó không trả lời: “hệ thống production trả lời tốt bao nhiêu?”.

---

## 11. Truy vết ba câu — từ metric đến hành vi

### 11.1. Q02 — Hit không đổi, MRR tăng

| Trường | WITHOUT | WITH |
|---|---|---|
| predicted type | — | SO_SANH |
| sources / contexts | 12 / 6 | 13 / 8 |
| matched_rank | 3 | 1 |
| Hit@3 | True | True |
| MRR | 0.3333 | 1.0000 |
| Citation | null (expected ELO, không phải Điều/Khoản) | null |
| Faithfulness heuristic | 0.9426 | 0.9817 |

Bài học: Hit@3 bỏ lỡ cải thiện thứ hạng; Citation null vì benchmark kỳ vọng ELO, không
phải Điều/Khoản; Faithfulness cao vì answer copy nhiều token từ context.

### 11.2. Q23 — metric đẹp nhưng câu trả lời là từ chối oan

| Trường | WITHOUT | WITH |
|---|---|---|
| expected type | SO_SANH | SO_SANH |
| Hit@3 | True | True |
| MRR | 1.0 | 1.0 |
| `is_refusal_answer` | **True** | **True** |
| Citation F1 | **1.0** | **1.0** |
| Faithfulness | **1.0** | **1.0** |

Q23 là câu in-corpus nhưng bị từ chối. Vì từ chối nên được faithfulness 1.0; vì answer
vẫn chứa “Điều 10” (hoặc injection) nên Citation F1 1.0; Hit@3 đúng. Nhìn bảng, Q23
“hoàn hảo”. Thực tế nó vô dụng. Đây là lý do phải đọc false refusal trước, và tại sao
faithfulness/refusal phải tách khỏi nhau.

### 11.3. Q08 — misroute dẫn đến từ chối

| Trường | WITHOUT | WITH |
|---|---|---|
| predicted type | — | **NGOAI_PHAM_VI** |
| matched_rank | 7 | None |
| Hit@3 | False | False |
| `is_refusal_answer` | False | **True** |
| Faithfulness | 0.3939 | 1.0 |
| Citation | null | null |

WITH gán Q08 (in-corpus) thành ngoài phạm vi → prompt từ chối → answer từ chối. Chỉ số
faithfulness **tăng** từ 0.39 lên 1.0, nhưng chất lượng giảm: câu trả lời không còn. Đây
là phản ví dụ rõ nhất cho việc tối ưu một metric mà không nhìn hành vi.

### 11.4. Q96 — ảo giác vẫn được number_support cao

Q96 ngoài corpus, bị trả lời thay vì từ chối. `number_support = 1.0` vì mọi số trong
answer đều xuất hiện đâu đó trong context; `faithfulness = 0.5`; `Hallucinated = True`.
Chỉ số number_support không phát hiện ảo giác. Đây là lý do cần judge/kiểm tra thủ công
cho 3 câu ngoài corpus.

---

## 12. Bài tập

**A.** Vì sao `n_retrieval_scored = 97` nhưng `n_total = 100`? Nếu báo cáo “Hit@3 =
77.3%” mà không nói mẫu số, sai ở đâu?

**B.** Một câu có chunk đúng ở rank 8. Hit@3, Hit@5, Hit@6, MRR lần lượt là gì? Nếu
pipeline chỉ trả 6 chunk thì sao?

**C.** Viết lại `citation_scores` để predicted rỗng không còn được 1.0. Cần sửa thêm chỗ
nào để báo cáo không bị lệch mẫu số?

**D.** Chạy `evaluation.py -k 4`. Generator thực tế nhận bao nhiêu chunk? Vì sao
`retrieval.top_k = 4`? Sửa một dòng nào để hết bất nhất?

**E.** `faithfulness` trung bình gộp cả từ chối là 0.811, chỉ câu trả lời là 0.643. Vì sao
chênh? Nên báo cáo số nào? Nếu muốn đo “hệ thống trung thực” thì cần thêm chỉ số gì?

**F.** Hội đồng hỏi: “Classifier của em làm tăng Hit@3 27%, đúng không?” Trả lời trong 5
câu, nêu ít nhất ba lý do không được quy công và một thí nghiệm cần làm.

<details>
<summary>Đáp án</summary>

**A.** 3 câu Q96–Q98 ngoài corpus không có `source_document`, nên `hit_at_* = None` và bị
`_mean` loại. 77.3% là 75/97, không phải 75/100. Nếu ghi 77.3% mà không nêu mẫu số,
người đọc sẽ hiểu là 77/100; chênh 2 câu và làm sai mọi so sánh với baseline tính trên
100.

**B.** Hit@3 = False, Hit@5 = False, Hit@6 = False, MRR = 1/8 = 0.125. Nếu pipeline chỉ
trả 6 chunk, chunk rank 8 không tồn tại trong `sources`; MRR = 0 và Hit@6 = False — metric
đo cửa sổ thực, không đo “nếu lấy thêm”. Đây là lý do phải báo cáo `retrieved_k`.

**C.** Thêm đầu hàm:

```python
if not expected:
    return None
if not predicted:
    return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "exact_match": 0.0}
```

và xóa nhánh `source_document` hoặc tách thành metric riêng. Trong `aggregate`, chỉ đưa
entry có `citations` khác None vào mẫu số (đã đúng), và in `n_citation_scored` cạnh bảng;
không được coi 68 câu không chấm là 0 hay 1.

**D.** `retrieve_k = max(4, 6) = 6`; `pipeline.run(top_k=6)` → generator nhận 6 chunk,
`retrieval.top_k` vẫn ghi 4. Sửa `evaluation.py:471` thành
`pipeline.run(question["raw_query"], top_k=top_k)`. Khi đó generator nhận 4, sources = 8;
nếu cần 12 để đo Hit@6, phải thêm tham số recall window vào pipeline, không truyền
`retrieve_k` giả làm top_k.

**E.** 0.811 gồm 100 câu, trong đó 47–49 câu từ chối được gán 1.0; 0.643 chỉ gồm 53/50
câu trả lời thật. Từ chối không có khẳng định để phản bội, nên 1.0 là quy ước, không phải
chất lượng. Báo cáo số **chỉ câu trả lời** và nói rõ n; đồng thời báo false refusal như
một chỉ số chất lượng riêng. Muốn đo “hệ thống trung thực” toàn diện cần một chỉ số kết
hợp: tỉ lệ câu trả lời đúng + không ảo giác + không từ chối oan (ví dụ
`answer_usefulness = answered_correct / all_in_corpus`), không gộp bằng trung bình.

**F.** “Không hẳn. Lượt WITH bật đồng thời classifier, router, sub-query, prompt theo type
và đổi cửa sổ ngữ cảnh; không có ablation nên không tách được công của classifier. Hit@3
tăng 27% tương đối trên 97 câu, không có khoảng tin cậy. Classifier type accuracy 83% còn
thấp hơn baseline đoán mù 87%, và 7 câu bị gán NGOAI dẫn đến từ chối oan. Ngoài ra
benchmark có rò rỉ few-shot và filter thiết kế trên chính nó. Thí nghiệm cần làm: chạy
router với nhãn vàng (không classifier) để đo riêng công của router; sau đó bật classifier
trên cùng cấu hình, so sánh.”

</details>

---

## 13. Tóm tắt chương

1. Benchmark v3 có 100 câu, 13 khóa, 87/5/5/3; 97 câu in-corpus, 3 câu ngoài corpus. Mọi
   chỉ số retrieval có mẫu số 97; citation 32; normalization 30; từ chối 3.
2. `evaluate_question` gọi `pipeline.run(top_k=retrieve_k)` — generator nhận
   `retrieve_k`, không phải `top_k`. Với mặc định 6/6, contexts 6 (SO_SANH 8), sources
   11–16; metadata 6/6 chỉ là khai báo.
3. Hit@K đo ở mức tài liệu trên toàn bộ recall window; MRR không cắt ở 6. Hit cao không
   đảm bảo chunk đúng chứa câu trả lời.
4. Citation chỉ chấm 32/100 câu vì extractor chỉ hiểu Điều/Khoản. `citation_scores` có
   lỗi: predicted rỗng được 1.0 nhờ `"" in source`. Số đúng là 4.0%/10.1%, không phải
   13.4%/25.7%.
5. Faithfulness LLM bị tắt trong A/B; heuristic token-overlap cho 0.643/0.647 trên câu
   trả lời, 0.811/0.823 nếu gộp từ chối. Không có cải thiện trung thực.
6. False refusal 46/97 → 49/97 — vấn đề lớn nhất, không được GATE kiểm.
7. Resume tiết kiệm quota nhưng thiếu khóa `top_k`/model; dry-run chỉ là ước lượng;
   flush từng câu là lá chắn mất điện.
8. `evaluate_classifier.py` cho 85%/81% (có rò rỉ few-shot), kNN 76%/89% — type accuracy
   của classifier thấp hơn baseline đoán mù 87%; đừng nói “LLM chính xác hơn” một cách
   toàn diện.
9. A/B là gói nhiều thay đổi, không phải thí nghiệm một biến; GATE chỉ kiểm retrieval;
   kết quả Qwen local không đại diện Gemini production.
10. Khi bảo vệ, mỗi con số phải kèm: file sinh ra, mẫu số, công cụ đo, và lỗi đã biết.

Tiếp theo: [09 — Ứng dụng giao diện](09_ung_dung_giao_dien.md).
