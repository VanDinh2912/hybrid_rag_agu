# Chương 04 — Chuẩn hóa câu hỏi và phân loại hai nhãn

> **Mục tiêu chương:** phân biệt được hai module “hiểu câu hỏi” của đồ án; giải thích
> được prompt, few-shot, active learning và các guardrail; biết **đường nào thực sự
> chạy** trong pipeline; đọc được bảng accuracy của classifier mà không tự lừa mình.

Hai module này đều dùng Qwen2.5-1.5B qua Ollama, nhưng giải hai bài toán khác nhau:

| Module | Bài toán | Đầu ra | Có bật mặc định? |
|---|---|---|---|
| `src/query_normalizer.py` | viết lại câu hỏi cho giống văn phong quy chế | một câu hỏi | **có** (mọi lượt) |
| `src/classifier.py` | gán chủ đề + loại câu hỏi | `{topic, question_type}` | không (`ENABLE_CLASSIFIER=1` mới bật) |
| `src/local_slm.py` | wrapper Ollama + chuẩn hóa có guardrail | một câu hỏi | không dùng trong pipeline |

---

## 1. Đường chạy thật: một phát hiện quan trọng

Pipeline gọi:

```python
normalized_query = normalize_user_query(self.local_slm, raw_query)
```

(`src/pipeline.py:353`)

`normalize_user_query` nằm trong `src/query_normalizer.py`. Khi nhận một `LocalSLM`,
nó gọi **`llm_client.generate(...)`** (`src/query_normalizer.py:338–341`), tức là đi
thẳng vào Ollama, **không** gọi `LocalSLM.normalize_query()`.

Hệ quả:

```
pipeline.run()
   └─ query_normalizer.normalize_user_query()
        └─ LocalSLM.generate()          ← không có guardrail số/token
```

Trong khi đó:

```
LocalSLM.normalize_query()               ← có is_acceptable + guardrail_violation
   └─ LocalSLM.generate()
```

`LocalSLM.normalize_query` chỉ được gọi trong `tests/test_local_slm.py` và một fake
client của test tách truy vấn; **không** nằm trên đường production. Nói cách khác,
guardrail “bảo toàn con số + token overlap ≥ 0.3” được mô tả trong tài liệu và trong
`src/local_slm.py` **không chạy** khi bạn hỏi qua `main.py` hay Streamlit.

> Đây là loại khác biệt chỉ phát hiện khi đọc call graph, không phát hiện khi đọc
> docstring. Khi bảo vệ, nếu bị hỏi “guardrail chuẩn hóa nằm ở đâu?”, câu trả lời
> trung thực là: “Nó nằm trong `LocalSLM.normalize_query`, nhưng pipeline hiện gọi
> `query_normalizer.normalize_user_query` → `LocalSLM.generate`, nên trên đường
> production guardrail đó không được kích hoạt. Đây là nợ kỹ thuật đã ghi nhận.”
> Đừng trả lời rằng guardrail đang bảo vệ mọi lượt hỏi.

Chương này sẽ dạy cả hai, và chỉ rõ cái nào có hiệu lực.

---

## 2. `src/query_normalizer.py` — chuẩn hóa bằng prompt

### 2.1. Bảng hàm

| Hàm/hằng | Dòng | Vai trò |
|---|---:|---|
| `NORMALIZER_SYSTEM_PROMPT` | 50 | luật chống bịa, bảo toàn số, chỉ xuất một câu hỏi |
| `FEW_SHOT_PROMPT` | 69 | 4 ví dụ cố định (không dùng khi build động) |
| `load_normalization_pairs` | 96 | đọc 3 nguồn cặp (gốc → chuẩn hóa) |
| `build_few_shot_with_learning` | 160 | 4 ví dụ nền + tối đa 4 ví dụ “học” |
| `clean_normalized_text` | 227 | bỏ nhãn, dấu nháy, lấy dòng đầu |
| `normalize_user_query` | 264 | giao diện chính, điều phối client |

### 2.2. System prompt dạy gì?

Bốn nhóm luật:

1. **Không bịa thực thể.** Không tự thêm tên ngành, khoa, môn tiên quyết, thông tin
   không có trong câu gốc.
2. **Chỉ thay từ đồng nghĩa/viết tắt.** “mấy tín” → “bao nhiêu tín chỉ”, “đuổi học”
   → “buộc thôi học”, “loại yếu” → “xếp loại rèn luyện Yếu”.
3. **Bảo toàn tuyệt đối** số, điểm, mốc thời gian, mã học phần, tên môn.
4. **Định dạng đầu ra:** đúng một câu hỏi kết thúc bằng `?`, không giải thích, không
   thêm tiền tố.

Đây là **ràng buộc bằng lời**, không phải ràng buộc bằng code. Qwen 1.5B có thể vi
phạm; module không kiểm tra lại.

### 2.3. Few-shot và “active learning”

`build_few_shot_with_learning` lấy:

- **4 ví dụ nền cố định**: rèn luyện yếu/đuổi học, rớt môn/học bổng, nợ học phí/đi
  thi, môn Thiết kế và cài đặt mạng (mã/tín/chỉ/môn trước).
- **tối đa 4 cặp** từ `learning_pairs`, lấy theo **thứ tự chèn** của dict.
- câu hỏi hiện tại.

Prompt cuối cùng có tối đa 9 ví dụ. Con số 4 được chọn để Qwen 1.5B không bị quá tải
ngữ cảnh.

`load_normalization_pairs` đọc ba nguồn theo thứ tự ưu tiên:

| Nguồn | Đường dẫn | Trạng thái hiện tại |
|---|---|---|
| Phản hồi người dùng | `data/learning/normalization_pairs.json` | **không tồn tại** |
| Ghi chú cũ | `data/corpus/ghi_chu_hoc_them.txt` | **không tồn tại** |
| Benchmark cũ | `data/evaluation/benchmark_questions.json` | có, 15 cặp |

Vì hai nguồn đầu không có, mỗi lượt hỏi module đọc 15 cặp từ benchmark cũ rồi chèn
**4 cặp đầu tiên** (Q01–Q04) vào prompt. Bốn câu này có thể không liên quan gì đến
câu đang hỏi.

Ba nhận xét thẳng:

1. **Đây không phải huấn luyện.** Không có gradient, không có trọng số mới; chỉ là
   chèn ví dụ vào prompt. Gọi là “active learning” theo nghĩa “học từ phản hồi người
   dùng”, nhưng bản chất là prompt engineering.
2. **Chọn ví dụ không theo độ liên quan.** Lấy 4 cặp đầu tiên, không phải 4 cặp gần
   câu hỏi nhất. Với Qwen 1.5B hay bắt chước, ví dụ không liên quan có thể gây drift.
   Muốn tốt hơn phải chọn theo embedding similarity hoặc ít nhất theo chủ đề.
3. **Đọc lại file mỗi lượt.** 15 cặp, 21 KB — không đáng kể về I/O, nhưng lãng phí và
   làm log đầy ba dòng `[Normalization] ...` mỗi câu hỏi. Có thể cache một lần.

Một chi tiết thiết kế đáng nêu: `GHI_CHU_HOC_THEM_PATH` nằm trong `data/corpus/`.
Nếu ai đó tạo file này, `DocumentLoader` cũng sẽ ingest nó như một tài liệu, vừa dùng
làm ví dụ chuẩn hóa vừa làm corpus. Hai mục đích chồng lên một file là mùi thiết kế
xấu; hiện file không tồn tại nên chưa gây hại.

### 2.4. Điều phối client

`normalize_user_query` hỗ trợ bốn kiểu client:

| Kiểu | Nhánh code | Cách gọi |
|---|---|---|
| `LocalSLM` (có `generate`) | 326–345 | ghép system + few-shot, gọi `generate(full_prompt, temperature=0.0)` |
| `ollama.Client` | 329–337 | `generate(model=..., prompt=..., system=...)` |
| client có `chat` | 347–357 | system message + user message |
| callable hoặc `None` | 360–373 | gọi trực tiếp hoặc tự tạo `ollama.Client` |

Nhánh `except TypeError` (342–344) là để tương thích client chỉ nhận `(prompt)`, ví
dụ fake trong test. Đây là kiểu phòng thủ rẻ nhưng hữu ích.

### 2.5. Làm sạch đầu ra

`clean_normalized_text`:

1. duyệt từng dòng, bỏ dòng rỗng;
2. lặp đến điểm bất động: bỏ nhãn `Câu hỏi chuẩn hóa:`, `Chuẩn hóa:`, `Trả lời:` và
   dấu nháy ở hai đầu;
3. gom khoảng trắng;
4. trả **dòng không rỗng đầu tiên**.

Nó không kiểm tra:
- có dấu `?` hay không;
- có bảo toàn số hay không;
- dài bao nhiêu ký tự;
- có phải câu trả lời thay vì câu hỏi hay không.

Nếu Qwen trả “Dưới đây là câu hỏi chuẩn hóa: ...” ở dòng 1 và câu thật ở dòng 2, hàm
trả dòng 1 (sau khi bỏ nhãn, còn “Dưới đây là câu hỏi chuẩn hóa: ...”) — sai. Đây là
lý do cần guardrail, nhưng guardrail không được nối vào đường này.

### 2.6. Fallback

Mọi exception trong `normalize_user_query` đều bị bắt và trả `raw_text`
(`src/query_normalizer.py:380–382`). Không có retry. Nếu Ollama treo, thời gian chờ
là timeout của `LocalSLM` (mặc định 90 giây), không phải timeout riêng của module.

---

## 3. `src/local_slm.py` — chuẩn hóa có guardrail (không chạy trong pipeline)

### 3.1. Ba lớp kiểm tra

`LocalSLM.normalize_query` (`src/local_slm.py:290`) chạy:

```
generate → clean_output → is_acceptable → guardrail_violation → chấp nhận/fallback
```

**`is_acceptable`** (`:154`):

| Kiểm tra | Ngưỡng | Lý do |
|---|---|---|
| rỗng | — | không có gì để truy xuất |
| độ dài | ≤ 300 ký tự | dài hơn nghĩa là model trả lời |
| có `?` | bắt buộc | câu hỏi phải ở dạng hỏi |
| mẫu từ chối | `REJECT_PATTERNS` | “xin lỗi”, “tôi không thể”, “as an AI”, ... |

**`guardrail_violation`** (`:186`): hai tín hiệu trên văn bản đã fold:

1. **Bảo toàn con số:** `raw_numbers - norm_numbers` khác rỗng → mất số;
   `norm_numbers - raw_numbers` khác rỗng → bịa số. “1,0” và “1.0” được chuẩn hóa
   về cùng dạng.
2. **Tỉ lệ token:** `|token(chuẩn hóa) ∩ token(gốc)| / |token(chuẩn hóa)| ≥ 0.3`.
   Ngưỡng 0.3 được chọn từ thực nghiệm: cặp hợp lệ ≥ 0.4, ca drift quan sát được
   0.14.

Nếu vi phạm guardrail → **fallback ngay** về câu gốc, không thử lại. Nếu
`is_acceptable` thất bại (ví dụ thiếu `?`) → thử lại **một lần** với
`CORRECTION_SUFFIX` nhắc “chỉ xuất một câu hỏi”. Đây là hai cơ chế khác nhau, đừng
nhầm.

### 3.2. Vì sao guardrail 0.3 không đủ mạnh?

Ngưỡng token overlap thấp hơn nhiều so với “giữ nguyên nghĩa”. Một câu chuẩn hóa có
30% token trùng câu gốc vẫn có thể đổi chủ đề, miễn là giữ được vài từ phổ biến
(“sinh viên”, “học”, “không”). Với câu ngắn, 0.3 càng dễ qua. Đây là guardrail chống
drift **thô**, không phải bảo đảm ngữ nghĩa. Muốn chắc hơn phải dùng entailment model
hoặc LLM judge, tốn thêm một lượt gọi.

Ngoài ra, guardrail so token **của câu chuẩn hóa** với câu gốc; nó không phạt việc
**bỏ sót** thông tin quan trọng nếu câu chuẩn hóa vẫn giữ đủ 30% token. Ví dụ câu gốc
“Em nợ học phí và bị cấm thi đúng không?” bị chuẩn hóa thành “Sinh viên có được dự
thi không?” — mất “nợ học phí” nhưng vẫn có thể qua ngưỡng.

### 3.3. Nếu muốn bật guardrail trong production

Có hai cách, đều cần đo lại:

1. Đổi `pipeline.run` gọi `self.local_slm.normalize_query(raw_query)` thay vì
   `normalize_user_query(...)`. Đơn giản nhưng mất active learning (prompt khác,
   không đọc `normalization_pairs.json`).
2. Chuyển `is_acceptable` + `guardrail_violation` vào `query_normalizer`, giữ
   few-shot động. Đây là cách đúng hơn, nhưng phải chạy lại benchmark vì câu hỏi bị
   fallback nhiều hơn sẽ làm thay đổi retrieval.

Đồ án **không** sửa code ở giai đoạn này; chương chỉ ghi nhận nợ kỹ thuật.

---

## 4. `src/classifier.py` — gán hai nhãn

### 4.1. Hợp đồng đầu ra

```python
{
  "topic": "học phí" | ... | None,
  "question_type": "TRA_CUU" | "SO_SANH" | "THU_TUC" | "NGOAI_PHAM_VI",
  "raw_response": "<nguyên văn Qwen>"
}
```

- `topic`: 14 nhãn lấy đúng chuỗi `category` của benchmark v3; `None` nếu ngoài 14
  nhóm.
- `question_type`: luôn thuộc 4 nhãn; mặc định `TRA_CUU`.
- `raw_response`: để audit và sinh dữ liệu huấn luyện; không đưa vào prompt generator.

### 4.2. Taxonomy — đọc kỹ `NGOAI_PHAM_VI`

14 chủ đề (`TOPICS`, `:48`) là các nhóm nội dung: chương trình đào tạo, học phí, rèn
luyện, khen thưởng, thực tập, ...

4 loại câu hỏi (`QUESTION_TYPES`, `:65`) là **cách hỏi / khả năng trả lời**:

| Nhãn | Nghĩa thật trong benchmark |
|---|---|
| `TRA_CUU` | hỏi một thông tin cụ thể |
| `SO_SANH` | từ 2 đối tượng/mức trở lên cần đối chiếu |
| `THU_TUC` | hồ sơ, giấy tờ, các bước, nơi nộp |
| `NGOAI_PHAM_VI` | **không trả lời được từ corpus**, dù câu hỏi có thể rất “trong trường” |

Điểm này cực dễ hiểu sai. Ba câu Q96–Q98 của benchmark v3:

```json
{"id": "Q96", "category": "thực tập tốt nghiệp", "question_type": "NGOAI_PHAM_VI", "in_corpus": false}
{"id": "Q97", "category": "thực tập tốt nghiệp", "question_type": "NGOAI_PHAM_VI", "in_corpus": false}
{"id": "Q98", "category": "thực tập tốt nghiệp", "question_type": "NGOAI_PHAM_VI", "in_corpus": false}
```

Chúng có **topic = thực tập tốt nghiệp** nhưng **type = NGOAI_PHAM_VI** vì nội dung
không có trong tài liệu đã index. Vậy hai nhãn độc lập: topic nói “về cái gì”, type
nói “trả lời được không / hỏi kiểu gì”.

Hệ quả cho classifier: nó phải vừa nhận ra chủ đề, vừa nhận ra **khả năng trả lời**.
Với Qwen 1.5B, đây là bài toán khó; ba ví dụ NGOAI duy nhất đều thuộc thực tập tốt
nghiệp, nên model dễ học sai “hễ thực tập là NGOAI”.

### 4.3. Prompt

`build_classifier_prompt` (`:424`) có cấu trúc:

```
QUY TẮC CHỌN question_type — xét theo thứ tự, dừng ở điều kiện đầu tiên
  1. NGOAI_PHAM_VI: ...
  2. SO_SANH: ...
  3. THU_TUC: ...
  4. TRA_CUU: còn lại
Lưu ý: hỏi nhiều thuộc tính của CÙNG một đối tượng là TRA_CUU, không phải SO_SANH.

QUY TẮC CHỌN topic — 14 dòng, mỗi dòng một chủ đề + dấu hiệu
Nếu câu hỏi hoàn toàn không thuộc 14 nhóm, topic = null.

VÍ DỤ: 16 few-shot, mỗi ví dụ có dòng "Dấu hiệu"
NHẮC LẠI (theo đúng thứ tự ưu tiên): ... (nhắc lại ngay trước câu hỏi)

Trả lời đúng 2 dòng:
Dấu hiệu: ...
A: {"topic": ..., "question_type": ...}

Câu hỏi: "..."
Dấu hiệu:
```

Ba quyết định đáng học:

1. **Thứ tự ưu tiên** giải quyết xung đột: một câu vừa “so sánh” vừa “hồ sơ” sẽ là
   SO_SANH (đứng trước THU_TUC). Một câu “du học” là NGOAI dù có chữ “học phí”.
2. **Nhắc lại luật ngay trước câu hỏi** (recency) vì Qwen 1.5B đọc hướng dẫn ở đầu
   prompt rồi trôi về `TRA_CUU`. Đây là mẹo prompt có thực nghiệm.
3. **Dòng “Dấu hiệu” trước JSON** buộc model lập luận ngắn trước khi chốt nhãn. Nó
   cũng giúp người đọc debug khi sai.

### 4.4. Few-shot 16 câu — và vấn đề rò rỉ

`FEW_SHOT_IDS` (`:152`) chọn 16 câu từ **chính benchmark v3**:

- 1 câu/chủ đề (14 câu);
- thêm Q97, Q98 để mỗi loại hiếm có 3 ví dụ;
- TRA_CUU có 7 ví dụ, SO_SANH/THU_TUC/NGOAI mỗi loại 3.

Điều này có nghĩa: khi đo accuracy trên 100 câu v3, **16 câu đã nằm trong prompt**.
Model chỉ cần nhớ ví dụ là đúng. Đây là rò rỉ train/test ở mức prompt, không phải ở
mức huấn luyện, nhưng vẫn làm số liệu lạc quan.

Tôi tính lại từ `logs/classifier/results.json`, loại 16 câu few-shot:

| Tập đo | Accuracy chủ đề | Accuracy loại câu hỏi |
|---|---:|---:|
| 100 câu (báo cáo gốc) | 85.0% (85/100) | 81.0% (81/100) |
| **84 câu còn lại** | **82.1% (69/84)** | **77.4% (65/84)** |

Chênh lệch 3 câu chủ đề và 4 câu loại. Không thảm họa, nhưng khi bảo vệ nên trình
bày **cả hai** và nói rõ cách chọn few-shot. Nếu có điều kiện, nên tách 16 câu
few-shot ra khỏi tập đo hoặc dựng benchmark v4 hoàn toàn mới.

### 4.5. Parse JSON

`extract_json_object` (`:464`) không dùng regex `\{.*\}` thô. Nó:

- quét từng dấu `{`;
- theo dõi độ sâu ngoặc;
- theo dõi trạng thái chuỗi và ký tự escape;
- thử `json.loads` từng khối;
- trả `None` nếu không có khối hợp lệ.

Nhờ vậy nó chịu được markdown fence, lời dẫn thừa, và dấu `}` nằm trong giá trị
chuỗi. Đây là chi tiết đáng học: parse output LLM phải chịu lỗi, không được giả định
“model luôn trả JSON sạch”.

### 4.6. Ba lớp suy giảm

```
Lớp 1: Qwen trả JSON + nhãn hợp lệ
          │ lỗi/thiếu
          ▼
Lớp 2: bảng từ khóa (fold) bổ sung phần hỏng
          │ không khớp
          ▼
Lớp 3: topic = None, question_type = TRA_CUU
```

Chi tiết:

- `topic = null` là **hợp lệ** (ngoài 14 nhóm); chỉ cảnh báo khi có nhãn lạ.
- Nếu Qwen trả topic null nhưng type hợp lệ, lớp 2 vẫn tìm topic bằng từ khóa. Vì
  vậy “null” của model không được tôn trọng tuyệt đối.
- `_canonical_question_type` fold, thay khoảng trắng/gạch nối bằng `_`, viết hoa;
  nhãn lạ → `None` → lớp 2.
- Ollama chết/timeout: `LocalSLM` được tạo với `max_retries=0`; lỗi → trả thẳng lớp 3
  trong `except` (`:588–597`), không ném ra pipeline.

### 4.7. Bảng từ khóa dự phòng

Hai bảng `TOPIC_KEYWORDS` (`:274`) và `QUESTION_TYPE_KEYWORDS` (`:351`) được fold
một lần lúc import. Thứ tự dòng rất quan trọng:

| Đặt trước | Đặt sau | Vì sao |
|---|---|---|
| “thực tập chuyên đề” | “thực tập” | tránh câu TTCD bị nuốt vào TTTN |
| “đhqg”, “đại học quốc gia” | “khen thưởng” | khen thưởng cấp ĐHQG là nhóm riêng |
| “học phí” | “tín chỉ” | câu “học phí tín chỉ” thuộc học phí, không CTĐT |
| “sinh viên 5 tốt” | “sinh viên xuất sắc” | 5 tốt là danh hiệu riêng |

Điểm yếu: so khớp bằng `keyword in folded_query`, **không có ranh giới từ**. Một
chuỗi con tình cờ có thể kích hoạt nhãn. Ví dụ “acb” trong một mã môn, “elo” trong
một từ khác. Với tiếng Việt ít gặp, nhưng không bằng 0.

Điểm yếu thứ hai: từ khóa `THU_TUC` có “tài liệu”. Câu “Tài liệu nghiệm thu thực tập
chuyên đề gồm gì?” có thể bị gán THU_TUC dù đang hỏi nội dung (TRA_CUU). Đây là biên
mơ đã thấy trong bảng lỗi.

### 4.8. Chi phí và độ ổn định

- Thời gian: **2.57 s/câu** (báo cáo P2.3), so với 0.064 s của kNN bge-m3.
- Hai lượt chạy temperature 0 cho kết quả giống hệt 100/100 ở cả hai nhãn. Tốt cho
  tái lập, nhưng không chứng minh đúng.
- Classifier chạy trên **câu thô**, trước chuẩn hóa. Normalizer cũng chạy trên câu
  thô. Một lượt hỏi có classifier bật sẽ gọi Qwen **hai lần** (classifier + normalize),
  cộng thêm Qwen tách truy vấn nếu SO_SANH. Đây là chi phí latency thật.

---

## 5. Đọc bảng accuracy như một phản biện

### 5.1. Confusion matrix loại câu hỏi

```
dòng = nhãn đúng, cột = nhãn dự đoán

TRA_CUU        68   10    0    9
SO_SANH         0    5    0    0
THU_TUC         0    0    5    0
NGOAI_PHAM_VI   0    0    0    3
```

Đọc:

- **Recall lớp hiếm = 100%**: 5/5 SO_SANH, 5/5 THU_TUC, 3/3 NGOAI đều được tìm thấy.
- **Precision lớp hiếm rất thấp**:
  - SO_SANH: 5 đúng / 15 dự đoán = **33%**;
  - NGOAI: 3 đúng / 12 dự đoán = **25%**;
  - THU_TUC: 5/5 = 100%.
- Toàn bộ 19 lỗi là **TRA_CUU bị đoán thành lớp hiếm**. Model “bắt” được lớp hiếm
  bằng cách đoán bừa nhiều hơn, đánh đổi precision.

Đây là lý do router **không** dùng `NGOAI_PHAM_VI` để bỏ truy xuất (chương 05): nếu
bỏ, 9 câu TRA_CUU bị từ chối oan. Việc nhắc từ chối nằm ở generator, nơi có ngữ cảnh
để quyết định.

### 5.2. Baseline kNN

Báo cáo P2.4 (leave-one-out trên chính 100 câu):

| Phương pháp | Chủ đề | Loại câu hỏi | Thời gian/câu |
|---|---:|---:|---:|
| Qwen few-shot | 85.0% | 81.0% | 2.57 s |
| kNN bge-m3, k=1 | 76.0% | 85.0% | 0.064 s |
| kNN bge-m3, k=3 | 72.0% | **89.0%** | 0.064 s |
| kNN bge-m3, k=5 | 76.0% | 86.0% | 0.064 s |

Đọc trung thực:

- Qwen thắng **chủ đề** (+9 điểm so với kNN tốt nhất).
- kNN thắng **loại câu hỏi** (+8 điểm so với Qwen) và nhanh gấp ~40 lần.
- kNN là baseline leave-one-out, không có tập train/test riêng; nó cũng không “hiểu”
  quy tắc ưu tiên, chỉ nhìn hàng xóm. Nhưng con số 89% đủ để không thể tuyên bố
  “LLM cần thiết cho mọi nhãn”.
- Kết luận hợp lý: **LLM có ích cho chủ đề; với loại câu hỏi, một baseline rẻ hơn có
  thể cạnh tranh**. Nếu tối ưu chi phí, có thể dùng kNN cho type và LLM cho topic —
  nhưng phải đo lại trên tập held-out.

### 5.3. Lỗi chủ đề tiêu biểu

15 lỗi chủ đề, chia ba nhóm:

1. **Neo tên môn/danh hiệu** (Q07, Q08, Q34, Q37, Q38, Q54): câu hỏi về “môn Thực
   tập tốt nghiệp” bị gán chủ đề thực tập, dù đang hỏi số tín chỉ trong CTĐT; “Sinh
   viên Giỏi” bị gán 5 tốt.
2. **Neo từ chung** (Q28, Q31, Q36): “tiêu chí”, “quy chế” kéo sang quy chế công tác
   sinh viên thay vì đánh giá rèn luyện.
3. **Biên tài chính/học phí** (Q42, Q73): học lại cải thiện điểm bị gán tài chính;
   thanh toán học phí bị gán tài chính thay vì học phí.

Hướng cải thiện đã ghi trong báo cáo: thêm **neo âm** vào prompt/từ khóa. Ví dụ “môn
X bao nhiêu tín chỉ” → CTĐT dù tên môn chứa “thực tập”; “Tiêu chí N ... điểm” → rèn
luyện; “Sinh viên Giỏi/Xuất sắc” → khen thưởng, chỉ “Sinh viên 5 tốt”/“Sao Tháng
Giêng” mới là nhóm riêng.

---

## 6. Truy vết một câu hỏi qua hai module

Câu hỏi thô:

> “Em nợ học phí 2 tháng rồi, vậy có bị cấm thi không ạ?”

**Normalizer** (production):

1. Đọc 15 cặp benchmark cũ, chọn 4 cặp đầu.
2. Prompt = system + 4 ví dụ nền + 4 ví dụ “học” + câu hỏi.
3. Qwen trả, ví dụ: “Sinh viên còn nợ học phí 2 tháng có bị cấm dự thi không?”
4. `clean_normalized_text` lấy dòng đầu.
5. Không kiểm tra số “2” có còn hay không (may là còn).

**Classifier** (nếu bật):

1. Prompt 14 chủ đề + 4 loại + 16 few-shot + câu thô.
2. Qwen trả:
   ```
   Dấu hiệu: hỏi hậu quả của việc nợ học phí đối với việc dự thi
   A: {"topic": "học phí", "question_type": "TRA_CUU"}
   ```
3. `extract_json_object` lấy JSON; canonical hóa.
4. Router: topic “học phí” → lọc 2 file học phí; type TRA_CUU → giữ top_k, trọng số
   0.5/0.5.

**Generator** nhận `question_type="TRA_CUU"`, không thêm appendix đặc biệt.

Điểm cần chú ý: classifier nhìn **câu thô** (“cấm thi”), normalizer nhìn **cũng câu
thô** nhưng viết lại (“cấm dự thi”). Hai module không chia sẻ đầu ra. Nếu normalizer
drift, classifier vẫn có thể đúng; ngược lại, classifier sai không làm normalizer sai.
Độc lập là tốt cho chịu lỗi, nhưng tốn gấp đôi lượt gọi Qwen.

---

## 7. Bài tập chương

**A. Đường chạy.** Khi chạy `main.py`, hàm nào thực sự chuẩn hóa câu hỏi? Guardrail
bảo toàn số có chạy không? Nếu không, nó nằm ở đâu và vì sao không được gọi?

**B. Guardrail số.** Câu gốc “Em được 5 tốt cấp trường không?” bị Qwen viết lại thành
“Sinh viên có điểm trung bình dưới 2.0 thì có được xét không?”. Hàm nào phát hiện?
Phát hiện bằng hai tín hiệu nào?

**C. Nhãn `NGOAI_PHAM_VI`.** Vì sao Q96 có `category = "thực tập tốt nghiệp"` nhưng
`question_type = "NGOAI_PHAM_VI"`? Điều này ảnh hưởng gì đến cách router nên xử lý
nhãn?

**D. Rò rỉ few-shot.** Vì sao accuracy 85%/81% lạc quan? Tính lại trên 84 câu còn lại
cho kết quả gì? Nêu một cách sửa thiết kế.

**E. Precision lớp hiếm.** Với confusion matrix ở mục 5.1, tính precision của
SO_SANH và NGOAI_PHAM_VI. Vì sao router không nên bỏ truy xuất khi gặp
NGOAI_PHAM_VI?

**F. Từ khóa.** Với bảng từ khóa, câu “Học phí tín chỉ thực hành là bao nhiêu?” sẽ
được gán chủ đề gì? Vì sao thứ tự “học phí” trước “tín chỉ” quan trọng?

<details>
<summary>Đáp án gợi ý</summary>

**A.** `src/query_normalizer.normalize_user_query` (gọi từ `pipeline.py:353`), dùng
`LocalSLM.generate`. Guardrail `is_acceptable`/`guardrail_violation` nằm trong
`LocalSLM.normalize_query` (`local_slm.py:290`) nhưng không được gọi trên đường này.
Vì vậy bảo toàn số/token overlap **không chạy** trong production.

**B.** `guardrail_violation` (`local_slm.py:186`). Tín hiệu 1: mất số “5” và bịa số
“2.0” (`raw_numbers - norm_numbers` và `norm_numbers - raw_numbers`). Tín hiệu 2:
tỉ lệ token của câu chuẩn hóa có trong câu gốc có thể thấp hơn 0.3. Chỉ cần tín hiệu
1 vi phạm là đủ fallback.

**C.** `NGOAI_PHAM_VI` nghĩa là “không trả lời được từ corpus”, không phải “không
liên quan đến trường”. Q96 hỏi về thực tập (đúng chủ đề) nhưng chi tiết không có
trong tài liệu đã index (`in_corpus=false`). Router không nên bỏ truy xuất theo nhãn
này vì precision chỉ ~25%; bỏ sẽ từ chối oan 9 câu TRA_CUU. Chỉ nên dùng nhãn để
thêm appendix nhắc từ chối ở generator.

**D.** 16 câu few-shot nằm trong chính 100 câu đo, nên model chỉ cần nhớ. Trên 84 câu
còn lại: chủ đề **82.1% (69/84)**, loại **77.4% (65/84)**. Sửa: tách few-shot khỏi
tập đo, hoặc dùng benchmark v4 mới; tốt nhất là chọn few-shot từ một tập phát triển
riêng.

**E.** SO_SANH: 5/15 = **33.3%**. NGOAI: 3/12 = **25.0%**. Vì 12 lần đoán NGOAI chỉ
3 đúng; 9 câu TRA_CUU sẽ bị bỏ truy xuất oan nếu router tin nhãn tuyệt đối. Từ chối
phải dựa trên ngữ cảnh truy xuất, không chỉ nhãn.

**F.** Chủ đề **học phí**, vì bảng `TOPIC_KEYWORDS` xét “học phí” trước “tín chỉ”.
Nếu đảo, câu sẽ bị gán CTĐT chỉ vì có chữ “tín chỉ”, dù đang hỏi đơn giá.

</details>

Tiếp theo: [05 — Router truy xuất](05_router.md).
