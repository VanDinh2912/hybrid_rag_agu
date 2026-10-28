# 10 — Bài học, giới hạn và bảo vệ đồ án

> Hội đồng không chấm số liệu đẹp. Hội đồng chấm việc em biết **con số của mình
> đo cái gì, mẫu số bao nhiêu, sai ở đâu và sửa thế nào**. Một đồ án nói đúng
> giới hạn của nó đáng tin hơn một đồ án hứa 98%.

Chương này là chương tổng hợp. Nó không dạy thêm hàm mới; nó dạy cách **đọc lại
toàn bộ đồ án như một người bảo vệ**, và cách trả lời 30 câu hỏi thường gặp mà
không tự biến mình thành con tin của một con số.

---

## 1. Mục tiêu

Học xong chương này, em phải:

1. Kể đúng **18 giới hạn** của đồ án, phân biệt được đâu là lỗi dữ liệu, đâu là
   lỗi đo lường, đâu là giới hạn thiết kế có chủ ý.
2. Giải thích được **6 cặp đánh đổi** lớn và điều gì sẽ mất nếu chọn ngược lại.
3. Rút ra **10 bài học kỹ thuật** có bằng chứng từ chính lỗi đã gặp trong repo.
4. Trình bày mọi chỉ số theo **thẻ chứng cứ 5 thành phần**: đo trên tập nào, mẫu
   số bao nhiêu, bằng công cụ nào, cấu hình gì, và nó **không** nói điều gì.
5. Trả lời được bộ **32 câu hỏi bảo vệ** (kể cả 4 câu bẫy).
6. Có sẵn bài nói **60 giây / 3 phút / 10 phút** và danh sách sửa lỗi ưu tiên
   P0–P1–P2.

> Quy ước: các con số trong chương này lấy từ `outputs/ab_results_*.json`,
> `logs/classifier/`, `logs/benchmark/results_all.json` và
> `data/training/manifest.json` tại thời điểm 2026-10-23. Nếu chạy lại, phải
> cập nhật cả chương này lẫn báo cáo — đừng để giáo trình cũ hơn số liệu.

---

## 2. Bản đồ chứng cứ: mỗi nhận định tựa vào đâu

Khi bảo vệ, mỗi câu em nói phải lùi được về một file. Bảng dưới là “bản đồ
chứng cứ” của toàn đồ án.

| Nhóm nhận định | File sinh số liệu | Chương | Dùng để trả lời |
|---|---|---|---|
| Corpus có bao nhiêu chunk, tầng nào, chất lượng dấu | `data/training/manifest.json`, `chroma_db/`, bảng thống kê chương 02 | 02 | “Dữ liệu của em có sạch không?” |
| Retrieval A/B: Hit@3/5/6, MRR, citation, từ chối | `outputs/ab_results_without_classifier.json`, `outputs/ab_results_with_classifier.json` | 08 | “Classifier/router có giúp không?” |
| Bảng so sánh và hình A/B | `outputs/ab_comparison.md`, `outputs/figures/` | 08 | Trình chiếu |
| Citation đã sửa | Tính lại từ `per_question` bằng matching; công thức ở chương 08 | 08 | “Citation thật là bao nhiêu?” |
| Classifier: accuracy, per-class, confusion | `logs/classifier/results.json`, `accuracy_report.md`, `confusion_matrix_*.csv` | 04, 08 | “Classifier chính xác không?” |
| Baseline kNN | `logs/classifier/results_knn.json` | 08 | “Vì sao cần LLM thay vì kNN?” |
| Ba chiến lược chunking | `logs/benchmark/results_all.json`, `summary_comparison_report.md` | 02, 09 | “Chiến lược nào tốt nhất?” |
| Chất lượng dữ liệu huấn luyện | `data/training/manifest.json`, `data/training/README.md` | — | “Dataset có dùng được không?” |
| Lỗi đã biết của code | Chính các dòng code được chỉ trong chương 08, 09 | 08, 09 | “Sao em biết hệ thống sai?” |

**Nguyên tắc:** nếu một con số không có file sinh ra nó, đừng đưa vào slide. Nếu
một file có số nhưng em không biết mẫu số, đừng đọc số đó thành lời.

---

## 3. Mười tám giới hạn — bảng tổng hợp

Mức độ: **C** = cao (ảnh hưởng kết luận hoặc trải nghiệm), **T** = trung bình
(ảnh hưởng cách diễn giải), **B** = thấp (cần ghi chú nhưng không đổi kết luận).

| # | Giới hạn | Bằng chứng | Mức | Cách xử lý đúng khi nói |
|---|---|---|---|---|
| L1 | OCR Tầng 1 mất dấu thanh | Chỉ **62/361** chunk đủ dấu để dùng cho bài tập sinh văn bản | C | “Hệ thống bù bằng `fold()` ở mọi tầng so khớp; không che việc dữ liệu gốc kém.” |
| L2 | 3 file `.doc` + 1 PDF text hỏng không vào index | Loader bỏ qua, log ghi nhận | T | “Độ phủ corpus chưa đủ 100%; đây là việc phải bổ sung trước khi coi là bản đầy đủ.” |
| L3 | Benchmark 100 câu do chính nhóm soạn, một người gán nhãn | v3 + báo cáo verify | C | “Có thiên lệch người soạn; chưa có inter-annotator agreement. Vì vậy em báo cáo cả lỗi và mẫu số.” |
| L4 | Few-shot classifier lấy **16 câu từ chính benchmark** | `classifier.py` + đối chiếu v3 | C | “Accuracy 85%/81% là cận lạc quan; số held-out thấp hơn (82.1%/77.4%).” |
| L5 | Generator A/B là **Qwen 1.5B local**, không phải Gemini | `meta.generator_model` của cả 2 file A/B | C | “Kết luận retrieval chuyển được; kết luận chất lượng câu trả lời thì không.” |
| L6 | LLM judge tắt trong A/B | `meta.judge_enabled=false` | T | “Faithfulness chỉ có proxy heuristic; không có giám khảo độc lập.” |
| L7 | Citation chỉ chấm **32/100** câu | 68 câu `citations=null` | C | “Mẫu citation nhỏ và không ngẫu nhiên; đừng suy ra toàn bộ 100 câu.” |
| L8 | `citation_scores` thưởng 1.0 cho dự đoán rỗng | 5/32 WITH, 3/32 WITHOUT | C | “Số JSON bị phồng; số đúng là **4.02%/10.10%**, không phải 13.4%/25.7%.” |
| L9 | Từ chối oan ~50% câu in-corpus | 46/97 WITHOUT, 49/97 WITH | C | “Đây là vấn đề lớn nhất về trải nghiệm; nguyên nhân một phần là retrieval miss, một phần là prompt quá chặt.” |
| L10 | Hit@K đo **mức tài liệu**, không phải mức chunk/đáp án | `evaluation.py` + ví dụ Q02 | C | “Hit@3 77% không có nghĩa 77% câu trả lời đúng.” |
| L11 | Evaluation truyền `retrieve_k` vào `top_k` của pipeline | `evaluation.py:471` | C | “Với `-k 4`, generator vẫn nhận 6 chunk; Hit@4 chỉ xét 4 đầu của cửa sổ 12. Cửa sổ thực khác khai báo.” |
| L12 | Resume thiếu khóa `top_k`, generator, model | `load_resumable_entries` | T | “Chạy lại với cấu hình khác có thể tái dùng entry cũ — phải xóa output hoặc sửa khóa.” |
| L13 | `scripts/benchmark_chunking.py` so marker có dấu với answer đã fold | dòng 413 | T | “`refusal_rate = 0.0` không dùng được; sửa `fold(REFUSAL_MARKER)`.” |
| L14 | Repeat-check classifier gộp chung topic/type vào một dict | `evaluate_classifier.py` | B | “Hai cột ‘ổn định’ luôn bằng nhau; không phải bằng chứng độc lập.” |
| L15 | kNN là leave-one-out trên chính 100 câu | `run_embedding_baseline` | T | “Chỉ là baseline tham khảo, không phải train/test sạch.” |
| L16 | Latency 2.30s → 7.79s có cache, đo trên CPU | A/B meta + log | T | “Chênh lệch phản ánh chi phí classifier/subquery, không phải SLA production.” |
| L17 | Streamlit replay bỏ qua classifier/judge | `replay_entry_to_result` | T | “Replay chỉ để demo; không được so trực tiếp với live.” |
| L18 | Dataset classifier dùng nhãn template; seed benchmark tách riêng | `data/training/README.md` | T | “Nhãn template là nhãn yếu; không được quảng cáo là gold.” |

### 3.1. Bốn giới hạn phải kể kỹ

#### (a) Từ chối oan — con số đáng lo nhất

Trên 97 câu **in-corpus**, mô hình trả lời bằng câu từ chối chuẩn:

| Lượt | Từ chối oan | Tỷ lệ | Từ chối đúng câu ngoài corpus | Ảo giác ngoài corpus |
|---|---:|---:|---:|---:|
| WITHOUT | 46/97 | 47.4% | 1/3 | 2 |
| WITH | 49/97 | 50.5% | 1/3 | 2 |

Hai điều quan trọng:

1. **Không phải classifier gây ra.** WITHOUT không có classifier mà vẫn 46/97.
   Bật classifier/router còn làm tăng 3 câu. Vấn đề nằm ở prompt sinh, ở chất
   lượng ngữ cảnh, hoặc ở cả hai.
2. **“Từ chối oan” là chỉ số đầu-cuối, không phải chỉ số generator.** Nếu
   retrieval không mang về chunk chứa đáp án, việc generator từ chối là hành vi
   *đúng về mặt RAG* nhưng vẫn bị tính là oan vì câu hỏi có đáp án trong corpus.
   Muốn tách nguyên nhân phải join với `hit_at_k` của từng câu: bao nhiêu câu
   từ chối oan có `hit_at_6 = 1`? Đồ án **chưa làm** phép join này — đó là việc
   P0 tiếp theo.

Cách nói an toàn:

> “Một nửa câu in-corpus bị từ chối. Một phần do truy xuất trượt, một phần do
> prompt quá thận trọng; em chưa tách được tỷ lệ hai nguyên nhân. Đây là lý do
> em không coi hệ thống là sẵn sàng production.”

#### (b) Citation bị thổi phồng — bài học về phần thưởng rỗng

`citation_scores` có một nhánh:

```python
if not predicted and source_document:
    return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "exact_match": 1.0}
```

Điều kiện thực tế là `"" in source_folded` — **luôn đúng**. Vì vậy mọi câu
không trích dẫn được nguồn đều nhận điểm hoàn hảo. Hệ quả:

| Lượt | F1 trong JSON | Câu dự đoán rỗng | F1 đã sửa |
|---|---:|---:|---:|
| WITHOUT | 13.39% | 3/32 | **4.02%** |
| WITH | 25.73% | 5/32 | **10.10%** |
| Gemini cũ (baseline) | 78.1% | 25/32 | **0.0%** |

Kiểm tra số học: `10.10% + 5/32 = 25.73%`; `4.02% + 3/32 = 13.40%`;
`0.0 + 25/32 = 78.1%`. Khớp tuyệt đối — đây là bằng chứng không thể chối cãi
rằng toàn bộ phần chênh lệch đến từ câu rỗng.

Cách nói đúng:

> “Citation F1 đã sửa là 4.0% → 10.1%, không phải 13.4% → 25.7%. Con số 78.1%
> trong báo cáo Gemini cũ là lỗi chấm, không phải thành tích.”

#### (c) Cửa sổ truy xuất và cửa sổ sinh không giống nhau

Có **hai lớp `retrieve_k`** dễ lẫn:

1. Evaluation đặt `retrieve_k = max(top_k, MIN_TOP_K=6)` — sàn 6 để đo được
   Hit@5/Hit@6 kể cả khi người dùng chọn `-k 3`.
2. Pipeline nhận `top_k`, rồi tự đặt `retrieve_k_pipeline = top_k × 2`.

Nhưng `evaluate_question` lại gọi:

```python
result = pipeline.run(question["raw_query"], top_k=retrieve_k)
```

Tức là **sàn của evaluation bị đưa vào làm top_k của generator**. Hệ quả thực tế:

| Lệnh | Eval `retrieve_k` | Pipeline nhận `top_k` | `sources` thực | `contexts` thực | Hit@4 xét |
|---|---:|---:|---:|---:|---:|
| `-k 6` (mặc định) | 6 | 6 | 12 | 6 | 4 đầu |
| `-k 4` | 6 (sàn) | 6 | 12 | 6 | 4 đầu |
| `-k 4`, classifier, SO_SANH | 6 | 6 → router +2 | 16 (dedupe còn 13) | 8 | 4 đầu |

Vì vậy metadata `top_k=6, retrieve_k=6` chỉ là **tham số khai báo**, không phải
`contexts=6, sources=6`. Với mặc định, `sources` thực là 12; với SO_SANH là 16
(hoặc 13 sau khử trùng lặp). Lỗi ẩn khi `-k 6` vì generator nhận đúng 6; lỗi lộ
khi `-k 4` vì generator vẫn nhận 6 thay vì 4.

Cách nói đúng:

> “Hit@6 xét 6 đầu của cửa sổ 12; generator nhận 6 (SO_SANH: 8). Cách gọi hàm
> đang truyền sàn `retrieve_k` vào `top_k`, nên `-k 4` không thực sự cho generator
> 4 chunk. A/B vẫn so sánh nội bộ được vì cả hai lượt cùng cấu hình, nhưng metadata
> không mô tả đúng cửa sổ thực.”

#### (d) Rò rỉ few-shot và baseline “không công bằng”

- 16 câu few-shot của classifier lấy từ chính 100 câu benchmark. Vì vậy 85%/81%
  là **cận trên lạc quan**; trên 84 câu còn lại (loại 16 câu few-shot), accuracy
  là 82.1%/77.4%.
- kNN được đo leave-one-out trên chính 100 câu, không có train/test riêng. Nó
  vẫn hữu ích để trả lời “một baseline rẻ trông thế nào”, nhưng không phải bằng
  chứng “LLM tốt hơn mọi cách”.
- Kết quả đáng chú ý: kNN **thắng** classifier ở nhãn loại câu hỏi (89% so với
  81% ở k=3), chỉ thua ở chủ đề (72% so với 85%). Câu chuyện đúng là: LLM giúp
  **chủ đề**, còn **loại câu hỏi** có thể giải bằng embedding rẻ hơn.

### 3.2. Các giới hạn còn lại — nói ngắn gọn

- **L2:** corpus thiếu file là giới hạn độ phủ, không phải lỗi retrieval.
- **L6:** thiếu judge độc lập nghĩa là mọi kết luận “trung thực” chỉ là proxy.
- **L12:** resume là công cụ tiết kiệm quota, không phải cam kết tái lập.
- **L14:** repeat-check không đo được stability riêng của hai nhãn.
- **L16:** latency có cache; đo lại không cache sẽ cao hơn.
- **L17:** replay không có `contexts`, không có faithfulness, không khớp
  classifier/judge — chỉ là “xem lại số đã đo”, không phải “chạy lại hệ thống”.
- **L18:** dataset có 3.912 mẫu duy nhất nhưng chất lượng phân tầng gold/silver/
  bronze; không được gọi tất cả là “dữ liệu vàng”.

---

## 4. Sáu cặp đánh đổi thiết kế

Mỗi quyết định trong đồ án đều lấy đi một thứ. Hội đồng thích nghe em nói rõ
“em đã đổi cái gì để lấy cái gì”, hơn là nghe “em chọn vì nó tốt”.

### 4.1. Cửa sổ recall 2× vs chi phí prompt

**Chọn:** `retrieve_k = 2 × top_k`; đo Hit trên cửa sổ rộng, chỉ đưa `top_k`
vào generator.

**Được:** đo Hit@K công bằng, không phạt hệ thống vì chunk đúng nằm ở hạng 4–6;
prompt không phình.

**Mất:** hai khái niệm “top_k” dễ lẫn; chi phí truy xuất gấp đôi; nếu code
truyền nhầm biến thì cửa sổ sinh cũng phình theo (đúng lỗi L11).

**Đổi khi nào:** nếu model có context window lớn và chi phí token rẻ, có thể
cho generator nhận nhiều hơn; nhưng phải đo lại citation/faithfulness vì ngữ
cảnh dài dễ làm loãng chú ý.

### 4.2. Chunk structure-aware vs fixed-size

**Chọn production:** cắt theo Điều/Khoản, giữ tiêu đề điều làm ngữ cảnh.

**Được:** chunk có nghĩa pháp lý, trích dẫn đúng đơn vị, MRR cao hơn trong thực
nghiệm (0.716 so với 0.698 của fixed).

**Mất:** số chunk nhiều hơn (378 so với 182 ở cấu hình 512 token), index lớn hơn
(5.93 MB so với 4.24 MB), Hit@3 lại thấp hơn (0.76 so với 0.88) vì top-3 bị
nhiều chunk nhỏ cạnh tranh.

**Đổi khi nào:** nếu mục tiêu là “tìm thấy đúng tài liệu trong top-3”, fixed
đang thắng; nếu mục tiêu là “trích đúng điều khoản và xếp hạng đúng”, structure
hợp hơn. Không có người thắng tuyệt đối.

### 4.3. Classifier + router vs pipeline thẳng

**Chọn:** phân loại 14 chủ đề × 4 loại, router chỉnh top_k/trọng số/lọc nguồn/
tách truy vấn con, fail-open.

**Được:** Hit@3 tăng 60.8% → 77.3% (tương đối +27.1%); MRR 0.51 → 0.77.

**Mất:** thêm một lần gọi LLM mỗi câu (latency 2.30s → 7.79s); thêm phụ thuộc
vào classifier; false refusal tăng nhẹ; kết quả là **một gói**, không quy được
cho riêng thành phần nào.

**Đổi khi nào:** nếu ưu tiên độ trễ, bỏ classifier và chấp nhận Hit thấp hơn;
nếu ưu tiên độ chính xác truy xuất, giữ và chạy ablation từng thành phần.

### 4.4. Qwen local vs Gemini API

**Chọn A/B:** Qwen 2.5 1.5B qua Ollama, offline, miễn phí, tái lập.

**Được:** không phụ thuộc quota, chạy được trên CPU, kiểm soát dữ liệu.

**Mất:** chất lượng lập luận và tiếng Việt thấp hơn Gemini; câu trả lời ngắn,
dễ từ chối; citation kém.

**Đổi khi nào:** khi cần chất lượng trả lời, dùng Gemini (có sẵn trong code);
nhưng phải đo lại toàn bộ nhóm answer-level, không bê nguyên kết luận retrieval.

### 4.5. Heuristic faithfulness vs LLM judge

**Chọn A/B:** heuristic token-overlap, miễn phí, chạy 100 câu.

**Được:** đo nhanh, không tốn quota, phát hiện câu trả lời không dựa ngữ cảnh ở
mức từ vựng.

**Mất:** không hiểu ngữ nghĩa; câu diễn giải đúng vẫn bị điểm thấp; câu bịa
tinh vi vẫn có thể qua; từ chối được gán 1.0.

**Đổi khi nào:** khi có quota, chạy judge trên 30–50 câu để hiệu chuẩn; báo cáo
cả hai, không thay thế âm thầm.

### 4.6. Cache/resume vs số đo trung thực

**Chọn:** cache câu trả lời, resume theo `id`, flush từng câu.

**Được:** tiết kiệm quota, không mất kết quả khi đứt giữa chừng.

**Mất:** latency bị đo thấp hơn thực tế; resume có thể trộn cấu hình nếu khóa
không đủ; “chạy lại” không còn là “chạy mới”.

**Đổi khi nào:** khi công bố latency, chạy `--no-cache` trên một tập con; khi
đổi `top_k`/model, xóa output hoặc thêm config hash vào khóa resume.

---

## 5. Mười bài học kỹ thuật

### Bài học 1 — Docstring không phải bằng chứng

**Chuyện đã xảy ra:** tài liệu mô tả generator nhận `top_k`, nhưng
`evaluation.py:471` truyền `retrieve_k`. Với mặc định 6/6, không ai thấy gì.
Chỉ khi đọc kỹ và cross-tab `retrieved_k` với `contexts` mới phát hiện.

**Quy tắc:** khi một con số quan trọng, mở đúng dòng code sinh ra nó. Đừng tin
docstring, tên biến hay báo cáo cũ.

### Bài học 2 — Một phép so khớp, một nguồn chân lý

**Chuyện đã xảy ra:** `fold()` được dùng ở retrieval, nhưng
`scripts/benchmark_chunking.py` lại so `REFUSAL_MARKER` có dấu với `answer` đã bỏ dấu.
Kết quả: `refusal_rate = 0.0` dù có câu từ chối.

**Quy tắc:** mọi so khớp văn bản tiếng Việt đi qua `fold()` ở **cả hai phía**.
Nếu phải viết một phép so khớp mới, viết test cho cặp có dấu/không dấu trước.

### Bài học 3 — Chuỗi rỗng nằm trong mọi chuỗi

**Chuyện đã xảy ra:** `"" in source_folded` luôn đúng, biến “không trích dẫn”
thành “trích dẫn hoàn hảo”.

**Quy tắc:** trước khi viết `x in y`, hỏi: `x` có thể rỗng không? Nếu có, xử lý
rỗng như một nhánh riêng và cho điểm 0, không cho điểm tối đa.

### Bài học 4 — Mọi chỉ số phải có mẫu số

**Chuyện đã xảy ra:** Hit@K có mẫu số 97, citation 32, normalization 30, từ chối
3. Báo cáo chỉ ghi “78.1%” mà không ghi mẫu số, khiến người đọc tưởng là 100 câu.

**Quy tắc:** mỗi con số đi kèm `n`. Nếu `n < 30`, ghi rõ “chỉ mang tính minh
họa”. Nếu mẫu số thay đổi giữa các chỉ số, đừng đặt chúng cạnh nhau mà không
chú thích.

### Bài học 5 — Đo trên cửa sổ rộng hơn cửa sổ trả lời

**Chuyện đã xảy ra:** nếu chỉ đo Hit@3 trên 3 chunk đưa vào generator, hệ thống
bị phạt oan khi chunk đúng ở hạng 4–6. Oversampling 2× giải quyết việc đo, nhưng
lại tạo ra hai cửa sổ dễ lẫn.

**Quy tắc:** tách rõ “cửa sổ đo” và “cửa sổ sinh”; đặt tên biến khác nhau
(`retrieve_k`, `top_k`); ghi cả hai vào metadata và kiểm tra bằng cross-tab.

### Bài học 6 — Fail-open phải để lại dấu vết

**Chuyện đã xảy ra:** classifier lỗi thì router lùi về cấu hình nền; Qwen lỗi
thì dùng câu gốc; Gemini hết quota thì fallback. Hệ thống không chết — nhưng
nếu không log, người đọc số liệu không biết câu nào đã suy giảm.

**Quy tắc:** mỗi lần fallback, ghi một trường trong entry (`normalization_source`,
`router_fallback`, `generator_fallback`). Báo cáo phải có cột “số câu suy giảm”.

### Bài học 7 — Cache là con dao hai lưỡi

**Chuyện đã xảy ra:** latency A/B 2.30s vs 7.79s được đo khi cache bật; nếu
cache hit cao, con số phản ánh cache chứ không phản ánh model. Replay của
Streamlit còn nhanh hơn nữa vì không gọi model.

**Quy tắc:** khi công bố latency, nói rõ cache bật/tắt, đo trên máy nào, có bao
nhiêu cache hit. Đừng so latency giữa hai lượt có tỷ lệ cache khác nhau.

### Bài học 8 — Benchmark cũng là một sản phẩm phần mềm

**Chuyện đã xảy ra:** v2.1 phải sửa tên nguồn; v3 phải verify schema, nhãn và
tính chống rò rỉ. Nếu benchmark sai, mọi chỉ số đều sai theo.

**Quy tắc:** benchmark cần schema, version, verify report, phân tầng, và một
người thứ hai rà ít nhất 10% câu. Đừng thêm câu mới mà không chạy lại verify.

### Bài học 9 — Không có bữa trưa miễn phí

**Chuyện đã xảy ra:** fixed thắng Hit@3 (0.88) nhưng thua MRR (0.698 so với
0.716) và citation (0.0 so với 0.0767); structure thắng xếp hạng nhưng index
lớn hơn 40%. Không chiến lược nào thắng mọi chỉ số.

**Quy tắc:** chọn theo mục tiêu, công bố trọng số trước, và chạy sensitivity
analysis. Đừng tuyên bố “tốt nhất” khi chỉ nhìn một cột.

### Bài học 10 — Kết quả âm cũng là kết quả

**Chuyện đã xảy ra:** bật classifier không cải thiện faithfulness; kNN thắng
classifier ở loại câu hỏi; citation gần như không tăng sau khi sửa lỗi.

**Quy tắc:** báo cáo cả kết quả âm. Một đồ án dám nói “cải tiến này không giúp”
đáng tin hơn một đồ án chỉ khoe chỗ tăng.

---

## 6. Nghệ thuật nói số liệu

### 6.1. Thẻ chứng cứ 5 thành phần

Mọi phát biểu định lượng nên có đủ:

1. **Tập đo:** “trên 97 câu in-corpus của benchmark v3”.
2. **Mẫu số:** “75/97”.
3. **Công cụ:** “`src/assessment/evaluation.py`, Hit mức tài liệu”.
4. **Cấu hình:** “gói WITH classifier/router, generator Qwen 2.5 1.5B, judge tắt”.
5. **Không nói gì:** “đây là recall tài liệu, không phải độ đúng câu trả lời”.

Ví dụ hoàn chỉnh:

> “Trên 97 câu in-corpus, Hit@3 tăng từ 59/97 = 60.8% lên 75/97 = 77.3% khi bật
> gói classifier/router, đo bằng `evaluation.py` với generator Qwen 1.5B và
> judge tắt. Đây là recall mức tài liệu trên cửa sổ 12 chunk; nó không chứng
> minh câu trả lời đúng, và gói WITH thay đổi nhiều thành phần cùng lúc nên
> không quy công riêng cho classifier.”

### 6.2. Nói thay vì

| ❌ Không nói | ✅ Nói |
|---|---|
| “Hệ thống chính xác 77%.” | “Hit@3 mức tài liệu là 77.3% trên 97 câu in-corpus; độ đúng câu trả lời chưa được đo tự động.” |
| “Citation F1 25.7%.” | “Citation F1 trong JSON là 25.7%, nhưng sau khi sửa lỗi câu rỗng, số đúng là 10.1% trên 32 câu.” |
| “Classifier chính xác hơn kNN.” | “Classifier hơn kNN ở chủ đề (85% vs 72–76%), nhưng kém hơn ở loại câu hỏi (81% vs 89% ở k=3).” |
| “Fixed là chiến lược tốt nhất.” | “Fixed thắng Hit@3; structure thắng MRR và citation; tùy mục tiêu.” |
| “Faithfulness 0.98.” | “Heuristic token-overlap đạt 0.98 khi gộp cả câu từ chối; chỉ tính câu trả lời là 0.64.” |
| “Đã giải quyết ảo giác.” | “Số câu ảo giác ngoài corpus là 2/3; mẫu quá nhỏ để kết luận.” |
| “Sẵn sàng triển khai.” | “Chưa: 50% từ chối oan, chưa có auth, chưa có giám sát.” |
| “Dataset 10.619 mẫu chất lượng cao.” | “10.619 dòng JSONL, tương ứng 3.912 mẫu duy nhất, phân tầng gold/silver/bronze.” |

### 6.3. Khi chưa đo được

Đừng bịa. Mẫu câu:

> “Em chưa đo được X. Để trả lời đúng, cần [thí nghiệm cụ thể] trên [tập nào],
> với [cấu hình nào]. Em đã ghi vào danh sách P1, dự kiến [thời gian].”

Hội đồng đánh giá cao việc biết mình chưa biết hơn là một con số không truy
được nguồn.

---

## 7. Bộ 32 câu hỏi bảo vệ

Mỗi câu có **Trả lời ngắn** (dùng khi bị hỏi nhanh) và **Nếu hỏi sâu** (dùng
khi bị truy). Đừng học thuộc; học ý và số.

### A. Bài toán và phạm vi

**A1. Bài toán của em là gì, khác chatbot tra cứu thường ở đâu?**

Ngắn: “Tra cứu quy chế AGU có trích dẫn, trả lời được câu hỏi diễn đạt đời
thường, và từ chối khi ngoài phạm vi. Khác chatbot thường ở ba điểm: hybrid
retrieval có fold cho OCR mất dấu, classifier/router chỉnh truy xuất theo loại
câu hỏi, và đánh giá có mẫu số/trích dẫn thay vì chỉ ‘cảm thấy đúng’.”

Sâu: “Chatbot thường tối ưu câu trả lời; đồ án này tối ưu **khả năng truy được
về nguồn**. Vì vậy em đo Hit, MRR, citation và từ chối, không chỉ BLEU hay độ
giống.”

**A2. Vì sao chọn quy chế AGU, phạm vi corpus đến đâu?**

Ngắn: “Vì văn bản công khai, có cấu trúc Điều/Khoản, và là bài toán thật của
sinh viên. Corpus gồm quy chế, quyết định, hướng dẫn thuộc Tầng 1 và Tầng 2;
361 chunk đã index, còn 3 file `.doc` và 1 PDF lỗi chưa vào.”

Sâu: “Phạm vi là các câu hỏi học vụ trong 14 chủ đề; câu ngoài phạm vi phải bị
từ chối. Em không nhận là bao phủ toàn bộ văn bản của trường.”

**A3. Hệ thống có thay thế phòng công tác sinh viên không?**

Ngắn: “Không. Nó là công cụ tra cứu hỗ trợ; câu trả lời phải kèm nguồn để
người đọc kiểm chứng, và các quyết định chính thức vẫn do nhà trường.”

**A4. Vì sao RAG thay vì fine-tune?**

Ngắn: “Quy chế thay đổi; RAG cập nhật bằng cách index lại, fine-tune thì phải
train lại. RAG còn giữ được trích dẫn — thứ fine-tune không đảm bảo.”

Sâu: “Fine-tune vẫn có chỗ: em đã chuẩn bị dataset 3.912 mẫu để fine-tune
classifier/embedding, nhưng chưa train vì thời gian và vì phải đánh giá lại.”

### B. Kiến trúc và lựa chọn

**B1. Vì sao hybrid BM25 + dense?**

Ngắn: “BM25 bắt từ khóa pháp lý và số hiệu; dense bắt diễn đạt đồng nghĩa.
Hai nhánh sai khác nhau nên hợp nhất RRF tốt hơn mỗi nhánh.”

Sâu: “BM25 chạy trên cả token gốc và token fold, nên vẫn khớp khi OCR mất dấu.
Dense dùng bge-m3, chuẩn hóa vector, query cũng được fold trước khi embed.”

**B2. Vì sao bge-m3?**

Ngắn: “Đa ngữ, tiếng Việt tốt, context 8.192 token, chạy local, miễn phí, và
đã có sẵn trong repo. Em chưa so sánh với model khác — đó là giới hạn.”

**B3. RRF là gì, sao c là 60, có tune không?**

Ngắn: “Reciprocal Rank Fusion: điểm = Σ 1/(60 + hạng). Hằng số 60 là mặc định
phổ biến, giảm ảnh hưởng của hạng đầu; em **không tune** vì giới hạn thời gian.”

Sâu: “Hệ quả: nếu hai nhánh đều xếp một chunk cao, chunk đó nổi lên; nếu chỉ
một nhánh, nó vẫn có cơ hội. Trọng số mặc định 0.5/0.5, có thể đổi qua router.”

**B4. Oversampling 2× để làm gì?**

Ngắn: “Để đo Hit@K trên cửa sổ rộng hơn cửa sổ generator, không phạt oan chunk
đúng ở hạng 4–6; generator chỉ nhận top_k để prompt không phình.”

**B5. Router dựa trên gì, nếu classifier sai thì sao?**

Ngắn: “Router ánh xạ nhãn chủ đề/loại câu hỏi sang cấu hình: top_k, trọng số
BM25/dense, lọc nguồn, tách truy vấn con. Nếu classifier lỗi hoặc trả nhãn lạ,
router fail-open về cấu hình nền.”

Sâu: “Ví dụ SO_SANH cộng 2 top_k và tách truy vấn; THU_TUC đổi trọng số về
0.6/0.4; 8/14 chủ đề có lọc nguồn. Fail-open được log để biết câu nào suy giảm.”

**B6. Vì sao chunk production khác 3 chiến lược trong thực nghiệm?**

Ngắn: “Production cắt theo Điều/Khoản với cấu hình tối ưu cho corpus; thực
nghiệm dùng cùng một ngưỡng 512 token cho cả ba để so sánh công bằng. Vì vậy
production 361 chunk, structure thực nghiệm 378 chunk.”

### C. Đo lường

**C1. Hit@3 77.3% nghĩa là gì?**

Ngắn: “Trên 97 câu in-corpus, 75 câu có ít nhất một chunk thuộc tài liệu đúng
trong top 3 của cửa sổ truy xuất. Đây là recall mức tài liệu, không phải độ
đúng câu trả lời.”

Sâu: “Một tài liệu có thể có nhiều chunk; Hit chỉ cần một chunk đúng tài liệu.
Vì vậy Hit cao vẫn có thể trả lời sai nếu chunk đúng không chứa điều khoản cần.”

**C2. Vì sao WITH cao hơn WITHOUT, có phải do classifier?**

Ngắn: “Retrieval tăng thật: Hit@3 60.8% → 77.3%, MRR 0.51 → 0.77. Nhưng gói
WITH thay đổi đồng thời classifier, router, tách truy vấn con và cửa sổ ngữ
cảnh; em **không thể quy công riêng cho classifier** nếu chưa ablation.”

Sâu: “Muốn tách, chạy 4 lượt: baseline, chỉ classifier, chỉ router, đầy đủ. Đó
là P1 trong danh sách sửa lỗi.”

**C3. Citation F1 thật là bao nhiêu, sao báo cáo cũ 78.1%?**

Ngắn: “Đã sửa: WITHOUT 4.02%, WITH 10.10% trên 32 câu. 78.1% là lỗi chấm câu
rỗng của lượt Gemini cũ; 25/32 câu không trích dẫn được 1.0, nên 0.0 + 25/32 =
78.1%.”

Sâu: “Lỗi nằm ở `citation_scores`: `"" in source` luôn đúng. Em đã chứng minh
bằng số học và bằng tính lại matching; báo cáo mới phải dùng số đã sửa.”

**C4. Faithfulness đo thế nào, sao không dùng LLM judge?**

Ngắn: “A/B dùng heuristic token-overlap với ngữ cảnh, miễn phí, chạy 100 câu.
Judge Gemini bị tắt vì quota. Heuristic chỉ là proxy; nó không hiểu ngữ nghĩa
và gán 1.0 cho câu từ chối.”

Sâu: “Khi gộp cả từ chối, điểm 0.811/0.823; chỉ câu trả lời là 0.643/0.647.
Chênh lệch 0.17 chính là phần thưởng từ 47–49 câu từ chối. Vì vậy không được
nói ‘faithfulness 0.82’ mà không nói mẫu số.”

**C5. Vì sao classifier accuracy 85/81 mà loại câu hỏi còn thấp hơn baseline 87%?**

Ngắn: “Vì 87% câu là TRA_CUU; một baseline đoán mù TRA_CUU đã đạt 87%. Vì vậy
accuracy tổng không đủ — phải xem per-class. Classifier thắng ở chủ đề nhưng
thua kNN ở loại câu hỏi.”

Sâu: “Recall SO_SANH/THU_TUC/NGOAI khá tốt nhưng precision thấp vì model over-
predict lớp hiếm; macro-F1 69.4%. Đây là lý do cần báo cáo từng lớp.”

**C6. Sao không có confidence interval hay p-value?**

Ngắn: “Vì mẫu nhỏ và em chưa chạy bootstrap. Với n=97, một câu đổi kết quả làm
Hit đổi ~1 pp; chênh lệch 16 pp có ý nghĩa thực tế nhưng chưa có CI chính thức.
Đó là P1.”

**C7. Latency 7.8 giây có chấp nhận được?**

Ngắn: “Cho demo nội bộ thì được; cho production thì chưa. Con số đo trên CPU,
có cache, và gồm cả classifier lẫn subquery. Muốn giảm: cache, bỏ classifier
khi không cần, hoặc dùng model nhỏ hơn cho phân loại.”

**C8. Kết quả Qwen 1.5B có suy ra được cho Gemini không?**

Ngắn: “Chỉ suy ra được phần retrieval, vì retrieval không phụ thuộc generator.
Các chỉ số câu trả lời, citation, từ chối thì **không** — phải đo lại với
Gemini.”

### D. Lỗi và giới hạn

**D1. Tại sao 50% câu in-corpus bị từ chối oan?**

Ngắn: “Một phần vì retrieval không mang về chunk chứa đáp án, một phần vì
prompt quá thận trọng và model 1.5B yếu. Em chưa tách được tỷ lệ hai nguyên
nhân; đó là việc P0.”

Sâu: “Dấu hiệu: WITHOUT không có classifier vẫn 46/97, nên không đổ cho
classifier. Cần join từng câu với `hit_at_k` và đọc 20 ca để phân loại lỗi.”

**D2. Tại sao evaluation truyền `retrieve_k` vào `top_k`?**

Ngắn: “Đó là lỗi thật ở `evaluation.py:471`. Với mặc định 6/6, lỗi ẩn; với
`-k 4`, generator nhận 6. Cách sửa: truyền `top_k`, giữ `retrieve_k` cho cửa
sổ đo. Kết quả A/B vẫn so sánh được nội bộ vì cả hai lượt cùng cấu hình.”

**D3. Citation extractor bỏ sót gì?**

Ngắn: “Nó chỉ hiểu ‘Điều X’ và ‘Khoản Y’; ‘Khoản’ đứng một mình bị bỏ, dải
Điều bị giới hạn, trọng số khớp một phần hard-code 0.5. Vì vậy 68/100 câu
không có citation để chấm.”

**D4. `refusal_rate = 0.0` trong benchmark chunking đúng không?**

Ngắn: “Không. Code so marker có dấu với answer đã fold, nên không bao giờ khớp.
Đúng phải là `fold(REFUSAL_MARKER) in fold(answer)`. Con số 0.0 không dùng được.”

**D5. Resume có nguy cơ trộn kết quả không?**

Ngắn: “Có. Khóa resume chỉ là `id`; meta kiểm benchmark, cờ A/B và judge, không
kiểm `top_k`, generator hay model. Chạy lại với cấu hình khác có thể tái dùng
entry cũ. Cách sửa: thêm config hash vào meta/khóa.”

**D6. Benchmark do nhóm tự làm thì có thiên lệch không?**

Ngắn: “Có. Một người soạn, một người gán nhãn, few-shot lấy từ chính benchmark.
Em giảm thiên lệch bằng verify v3, phân tầng, và báo cáo cả kết quả âm; nhưng
không thể nói là ngang một benchmark độc lập.”

### E. Triển khai và đạo đức

**E1. Có thể deploy thật không?**

Ngắn: “Chưa. Thiếu auth, phân quyền, giám sát, upload tài liệu, và tỷ lệ từ
chối oan 50%. Có thể pilot nội bộ với người duyệt.”

**E2. Dữ liệu cá nhân trong corpus thì sao?**

Ngắn: “Corpus là văn bản quy chế công khai, nhưng dataset sinh ra có thể chứa
tên/đơn vị trong ví dụ. Em chưa có bộ lọc PII chuyên dụng; trước khi công bố
phải rà và loại.”

**E3. Chi phí chạy?**

Ngắn: “Qwen local và bge-m3 chạy CPU, không tốn API; chi phí chính là thời gian
(~8s/câu). Gemini free tier bị giới hạn quota, nên A/B dùng Qwen.”

**E4. Hướng phát triển?**

Ngắn: “P0 sửa đo lường và từ chối oan; P1 ablation + judge + CI; P2 OCR lại,
reranker, fine-tune classifier/embedding, rồi mới nghĩ tới deploy.”

### F. Câu hỏi bẫy

**F1. “Vậy tóm lại hệ thống đúng bao nhiêu phần trăm?”**

Đừng trả lời một con số. Nói:

> “Không có một con số duy nhất. Hit@3 mức tài liệu là 77.3%; citation đúng là
> 10.1%; từ chối oan là 50.5%. Nếu buộc chọn con số phản ánh trải nghiệm, em
> chọn tỷ lệ từ chối oan — và nó đang là vấn đề lớn nhất.”

**F2. “Sao không dùng GPT-4o/Gemini cho tất cả?”**

Ngắn: “Vì chi phí, quyền riêng tư, khả năng offline và tái lập. Gemini có sẵn
như một lựa chọn; nhưng dùng nó cho mọi thứ thì không giải quyết được bài toán
đo lường — và vẫn có thể từ chối oan.”

**F3. “Nếu chỉ được giữ một cải tiến, giữ gì?”**

Ngắn: “Nếu vì người dùng: sửa từ chối oan. Nếu vì khoa học: sửa cách đo
citation, vì nó làm mọi so sánh sai. Em ưu tiên sửa đo trước, rồi dùng số đúng
để sửa từ chối.”

**F4. “Điểm mới nào đủ để bảo vệ?”**

Ngắn: “Không phải ‘dùng RAG’ — cái đó phổ biến. Điểm mới là: (1) hybrid có fold
cho OCR tiếng Việt mất dấu; (2) router từ nhãn câu hỏi với fail-open; (3) khung
đánh giá hai cửa sổ, có resume/flush và mẫu số rõ; (4) bộ sinh dataset từ
chính repo, tái lập được; (5) công bố cả kết quả âm và lỗi đo.”

---

## 8. Ba bài nói

### 8.1. Bài 60 giây

> “Đồ án xây hệ tra cứu quy chế AGU bằng Hybrid RAG: BM25 cộng bge-m3 hợp nhất
> RRF, chuẩn hóa câu hỏi bằng Qwen, phân loại 14 chủ đề và 4 loại câu hỏi để
> router chỉnh truy xuất. Trên 97 câu in-corpus, Hit@3 tăng từ 60,8% lên 77,3%
> khi bật gói classifier/router; MRR từ 0,51 lên 0,77. Nhưng citation đúng chỉ
> 10,1% sau khi sửa lỗi chấm, và 50,5% câu in-corpus bị từ chối oan — hai việc
> phải sửa trước khi triển khai. Đóng góp chính là pipeline tái lập được, đánh
> giá có mẫu số rõ ràng, và bộ dữ liệu 10.619 dòng sinh từ chính repo.”

Bốn số phải nhớ: **97, 77,3, 10,1, 50,5**.

### 8.2. Bài 3 phút — dàn ý

| Thời gian | Nội dung | Câu chốt |
|---|---|---|
| 0:00–0:30 | Bài toán: sinh viên tra quy chế, câu hỏi đời thường, cần trích dẫn | “Sai nguồn nguy hiểm hơn không trả lời.” |
| 0:30–1:15 | Kiến trúc: loader/OCR → chunk → hybrid → normalize/classifier/router → generator → evaluation | “Mỗi tầng đều có đường suy giảm mềm.” |
| 1:15–2:00 | Kết quả: Hit 60,8→77,3; MRR 0,51→0,77; citation 4,0→10,1; từ chối oan 46→49 | “Được lớn ở retrieval, chưa được ở trả lời.” |
| 2:00–2:40 | Giới hạn: gói WITH, Qwen 1.5B, judge tắt, citation 32 câu, OCR | “Em biết số nào không đáng tin.” |
| 2:40–3:00 | Việc tiếp theo: sửa đo, sửa từ chối oan, ablation, judge | “Ba việc P0, không hứa production.” |

### 8.3. Bài 10 phút — 10 slide

1. **Tựa + một câu:** “Tra cứu quy chế có trích dẫn, đo được, biết giới hạn.”
2. **Bài toán + phạm vi:** 14 chủ đề, 100 câu, 97 in-corpus; không thay phòng CTSV.
3. **Kiến trúc một hình:** loader → chunk → hybrid → normalize → classifier →
   router → generator → evaluation.
4. **Hai quyết định thiết kế:** fold + hybrid; recall window 2×.
5. **Classifier/router:** nhãn → cấu hình; ví dụ SO_SANH; fail-open.
6. **Kết quả retrieval:** bảng WITHOUT/WITH, Hit/MRR, n=97.
7. **Kết quả trả lời:** citation đã sửa 4,0/10,1; từ chối oan 46/49; judge tắt.
8. **Ba lỗi và cách sửa:** citation rỗng, `top_k=retrieve_k`, marker không fold.
9. **Giới hạn + đánh đổi:** gói WITH, Qwen 1.5B, OCR, benchmark tự soạn.
10. **Việc tiếp theo:** P0/P1/P2 + “chưa sẵn sàng production”.

Điều **không** đưa lên slide: 78,1% citation; “chính xác 98%”; “faithfulness
0,98”; “fixed là tốt nhất”; “classifier tốt hơn kNN” không kèm nhãn.

---

## 9. Nếu có thêm thời gian: danh sách sửa lỗi ưu tiên

| Ưu tiên | Việc | Vì sao | Công sức | Kiểm chứng |
|---|---|---|---|---|
| P0 | Sửa `citation_scores` (nhánh rỗng) + extractor Điều/Khoản | Mọi so sánh citation đang sai | 0,5–1 ngày | Unit test câu rỗng → 0; tính lại 32 câu |
| P0 | Sửa `evaluate_question` truyền `top_k` | Cửa sổ sinh khác khai báo | 0,5 ngày | Log `contexts` = top_k; Hit@4 với `-k 4` |
| P0 | Sửa marker trong `scripts/benchmark_chunking.py` | `refusal_rate` vô nghĩa | 15 phút | Chạy 5 câu có/không từ chối |
| P0 | Đo lại từ chối oan, join với Hit@K | 50% là vấn đề lớn nhất | 1–2 ngày | Bảng “từ chối oan có hit / không hit” |
| P0 | Thêm mẫu số + config hash vào resume | Tránh trộn cấu hình | 0,5 ngày | Chạy lại khác `top_k` phải từ chối resume |
| P1 | Judge Gemini 30–50 câu, so heuristic | Cần faithfulness độc lập | 1 ngày + quota | Tương quan heuristic vs judge |
| P1 | Bootstrap CI + per-class cho A/B | Chưa có khoảng tin cậy | 1 ngày | CI 95% cho Hit/MRR |
| P1 | Ablation classifier/router/subquery | Gói WITH không quy công | 3–5 ngày | 4 lượt, cùng seed/cấu hình |
| P1 | Chạy lại A/B với `top_k` đã sửa | Số cũ khó so | 2 ngày + quota | So sánh trước/sau |
| P2 | OCR lại Tầng 1 giữ dấu | 62/361 chunk đủ dấu | 1–2 tuần | Tỷ lệ chunk đủ dấu > 90% |
| P2 | Reranker (bge-reranker) | Tăng precision top-K | 3 ngày | Hit/MRR trước/sau |
| P2 | Fine-tune classifier/embedding trên dataset | Tận dụng 3.912 mẫu | 1 tuần GPU | Held-out accuracy |
| P2 | Deploy có auth/giám sát | Chưa production | 2 tuần | Checklist bảo mật |

**Nguyên tắc:** không làm P2 khi P0 còn sai. Một hệ thống đo sai mà thêm tính
năng chỉ làm sai nhanh hơn.

---

## 10. Bài tập chương

### Bài A — Thẻ chứng cứ (10 phút)

Viết lại phát biểu sau thành thẻ chứng cứ 5 thành phần:

> “Hệ thống đạt Hit@3 77% và citation 25%.”

<details>
<summary>Đáp án gợi ý</summary>

“Trên 97 câu in-corpus của benchmark v3, Hit@3 mức tài liệu là 75/97 = 77,3%,
đo bằng `src/assessment/evaluation.py` với gói WITH classifier/router, generator Qwen 2.5
1.5B, judge tắt. Citation **không phải 25%**: sau khi sửa lỗi câu rỗng, F1 là
10,10% trên 32 câu có ground truth trích dẫn. Hai chỉ số này không nói câu trả
lời đúng hay sai.”

</details>

### Bài B — Câu bẫy 78,1% (10 phút)

Hội đồng nói: “Báo cáo của em ghi citation 78,1%, sao giờ nói 10%?” Trả lời
trong 5 câu, có số học.

<details>
<summary>Đáp án gợi ý</summary>

“Con số 78,1% là của lượt Gemini cũ và bị lỗi chấm: 25/32 câu không trích dẫn
được nhưng hàm `citation_scores` trả 1.0 vì chuỗi rỗng luôn nằm trong chuỗi
nguồn. Tính lại bằng matching đúng, 25 câu đó được 0, nên F1 là 0,0 + 25/32 =
78,1% — tức toàn bộ điểm đến từ câu rỗng. Với A/B hiện tại, số đúng là 4,02%
(WITHOUT) và 10,10% (WITH), không phải 13,4%/25,7%. Em đã sửa báo cáo và ghi
rõ đây là lỗi đo, không phải thành tích.”

</details>

### Bài C — Thiết kế phép đo tách nguyên nhân từ chối oan (15 phút)

Đề xuất cách biết bao nhiêu câu từ chối oan là do retrieval miss, bao nhiêu do
generator quá thận trọng.

<details>
<summary>Đáp án gợi ý</summary>

Join từng entry với `retrieval.hit_at_k` và nhãn `in_corpus`. Chia 4 ô:

| | Có hit | Không hit |
|---|---:|---:|
| Từ chối | A | B |
| Trả lời | C | D |

- B là từ chối “hợp lý” vì ngữ cảnh không có đáp án (vẫn là lỗi retrieval).
- A là từ chối oan thật sự ở generator (có chunk đúng trong cửa sổ).
- D là trả lời dù không hit — cần rà ảo giác.

Sau đó đọc thủ công 20 ca A để phân loại prompt/model. Đo lại sau khi sửa
prompt; thêm cổng “A ≤ 20%”.

</details>

### Bài D — Có được nói “classifier giúp trả lời tốt hơn” không? (5 phút)

<details>
<summary>Đáp án gợi ý</summary>

Không. A/B cho thấy retrieval tốt hơn, nhưng không đo độ đúng câu trả lời; gói
WITH thay đổi nhiều thành phần; generator là Qwen 1.5B; judge tắt. Chỉ được
nói: “Gói classifier/router cải thiện retrieval; ảnh hưởng lên chất lượng câu
trả lời chưa được đo tách bạch.”

</details>

### Bài E — Một ngày, sửa gì? (10 phút)

<details>
<summary>Đáp án gợi ý</summary>

Trong 1 ngày: sửa marker chunking (15 phút), sửa `citation_scores` + test câu
rỗng (2–3 giờ), sửa `top_k=retrieve_k` (1 giờ), thêm mẫu số vào báo cáo (1–2
giờ), đọc 10 ca từ chối oan (2 giờ). Không chọn OCR hay reranker vì không kịp
kiểm chứng.

</details>

### Bài F — Viết phần “Hạn chế” 150 từ (15 phút)

<details>
<summary>Đáp án gợi ý</summary>

“Kết quả retrieval được đo trên 97 câu in-corpus do nhóm soạn, với 16 câu
few-shot lấy từ chính benchmark nên accuracy classifier là cận lạc quan. A/B
dùng Qwen 2.5 1.5B local, không phải Gemini, nên chỉ kết luận retrieval chuyển
được. Citation chỉ chấm 32/100 câu; sau khi sửa lỗi câu rỗng, F1 là 4,0%/10,1%.
Bật classifier làm tăng từ chối oan từ 46/97 lên 49/97 — một nửa câu in-corpus
bị từ chối, chưa tách được nguyên nhân retrieval hay prompt. Tầng 1 OCR mất
dấu, chỉ 62/361 chunk đủ dấu. LLM judge chưa bật; chưa có confidence interval.
Vì vậy em không coi hệ thống là sẵn sàng production.”

</details>

---

## 11. Tóm tắt chương

1. **Không có một con số duy nhất** đại diện cho hệ thống: Hit 77,3% là mức tài
   liệu; citation đúng 10,1%; từ chối oan 50,5%.
2. **Bốn lỗi đo** phải nhớ: citation thưởng câu rỗng; `top_k=retrieve_k`;
   marker không fold; resume thiếu khóa cấu hình.
3. **Hai vấn đề người dùng** lớn nhất: từ chối oan ~50% và OCR mất dấu.
4. **A/B là một gói**, không phải thí nghiệm một biến; muốn quy công phải
   ablation.
5. **Classifier không thắng mọi thứ**: hơn kNN ở chủ đề, thua ở loại câu hỏi.
6. **Chunking không có người thắng tuyệt đối**: fixed thắng Hit@3, structure
   thắng MRR/citation, đổi lại index lớn hơn.
7. **Qwen 1.5B không đại diện Gemini**: retrieval chuyển được, answer-level
   không.
8. **Mọi phát biểu phải có thẻ chứng cứ**: tập đo, mẫu số, công cụ, cấu hình,
   điều nó không nói.
9. **Ba bài nói** 60 giây / 3 phút / 10 phút, bốn số phải nhớ: 97, 77,3, 10,1,
   50,5.
10. **P0 trước P2**: sửa đo lường và từ chối oan trước khi thêm reranker, OCR
    hay fine-tune.

---

## Đi tiếp

- Tra cứu nhanh hàm/class: [Phụ lục hàm](PHU_LUC_ham.md).
- Làm bài tập phân tầng: [Bài tập và đáp án](BAI_TAP_VA_DAP_AN.md).
- Quay lại lộ trình: [00 — Lộ trình học](00_lo_trinh_hoc.md).
- Dùng dataset huấn luyện: [data/training/README.md](../../data/training/README.md).
