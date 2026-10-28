# Chương 05 — Router: biến nhãn thành cấu hình truy xuất

> **Mục tiêu chương:** đọc được `RetrievalConfig`; giải thích được từng luật điều chỉnh
> theo loại câu hỏi và từng bộ lọc theo chủ đề; hiểu vì sao router vừa là đòn bẩy lớn
> nhất của A/B vừa là nơi dễ tạo thiên lệch nhất; biết cách thiết kế ablation để chứng
> minh router thực sự có ích.

Router là tầng **thuần logic**: không gọi model, không đọc file, không I/O. Đầu vào là
nhãn của classifier và cấu hình nền; đầu ra là một dataclass. Vì thuần, nó dễ test và
dễ giải thích — nhưng cũng dễ bị hard-code theo tập đánh giá.

---

## 1. Vị trí và hợp đồng

```
raw_query
   │
   ├─ classify_query() ──► {topic, question_type}
   │
   ├─ base_config_from_env() ──► RetrievalConfig nền
   │
   └─ get_retrieval_config(labels, base) ──► RetrievalConfig đã điều chỉnh
                                                │
                                                ▼
                                   pipeline.retrieve(config=...)
```

Gọi từ `src/core/pipeline.py:330–346`, chỉ khi `ENABLE_CLASSIFIER=1`. Nếu tắt, router không
tồn tại trong lượt hỏi; pipeline dùng trọng số env và không lọc nguồn.

Hợp đồng:

```python
@dataclass
class RetrievalConfig:
    top_k: int
    bm25_weight: float
    chroma_weight: float
    source_filter: Optional[List[str]] = None
    enable_subquery: bool = False
```

(`src/retrieval/router.py:100–108`)

Năm trường, không hơn. Mọi thứ router làm đều phải biểu diễn được bằng năm trường này;
nếu cần thêm hành vi, phải sửa cả pipeline — đó là lý do thiết kế giữ nó nhỏ.

---

## 2. Cấu hình nền

`base_config_from_env()` (`:111`):

| Trường | Nguồn | Mặc định | Xử lý sai |
|---|---|---|---|
| `top_k` | `RAG_TOP_K` | 4 | không phải int hoặc ≤0 → 4 |
| `bm25_weight` | `BM25_WEIGHT` | 0.5 | không phải float → 0.5 |
| `chroma_weight` | `CHROMA_WEIGHT` | 0.5 | không phải float → 0.5 |
| `source_filter` | — | `None` | — |
| `enable_subquery` | — | `False` | — |

### 2.1. Ai thắng khi có nhiều nguồn `top_k`?

Ba nơi có thể đặt `top_k`:

1. `main.py` đọc `RAG_TOP_K` làm default của `-k` (`main.py:59–61`), nhưng hằng số
   nội bộ là **6** nếu env không có;
2. `.env.example` ghi `RAG_TOP_K=4`;
3. `pipeline.run(top_k=...)` nhận tham số caller, rồi **ghi đè** `base_config.top_k`
   (`src/core/pipeline.py:336`).

Thứ tự thực tế:

```
caller (main.py -k / evaluation)  >  RAG_TOP_K (chỉ khi main.py lấy default)  >  4
```

Nếu bạn gọi `pipeline.run(question)` mà không truyền `top_k`, mặc định hàm là 4
(`run` signature), không phải 6 của `main.py`. Khi bảo vệ, đừng nói “hệ thống mặc định
6 chunk” mà không nói “main.py mặc định 6; pipeline.run mặc định 4; evaluation truyền 6”.

### 2.2. Vì sao base phải giống hành vi cũ?

Mục tiêu của router là **chỉ điều chỉnh**, không đổi bản chất. Khi tắt classifier,
`ENABLE_CLASSIFIER=0`, pipeline phải chạy y hệt trước P3.2: cùng trọng số env, cùng
không filter, cùng top_k. `base_config_from_env` đọc đúng các biến cũ để đảm bảo điều
đó. Đây là nguyên tắc “tương thích ngược” — rất quan trọng khi A/B.

---

## 3. Luật theo loại câu hỏi

`get_retrieval_config` (`:158`) xét `question_type` trước, rồi `topic`.

| Loại | Điều chỉnh | Dòng | Lý do |
|---|---|---:|---|
| `TRA_CUU` | giữ base | — | câu tra cứu đơn giản, không cần mở |
| `SO_SANH` | `top_k += 2`, `enable_subquery=True` | 173–176 | cần nhiều nguồn để đối chiếu; tách vế |
| `THU_TUC` | `bm25=0.6`, `chroma=0.4` | 177–179 | giả thuyết: thủ tục nhiều từ khóa hành chính |
| `NGOAI_PHAM_VI` | giữ base | 180–181 | **không** bỏ truy xuất; từ chối ở generator |

### 3.1. Vì sao SO_SANH được +2?

Câu so sánh cần ít nhất hai đối tượng. Với top_k 6, 6 chunk có thể dồn hết vào một
đối tượng; +2 tạo chỗ cho đối tượng còn lại. Đây là **giả thuyết thiết kế**, không
phải định luật. Nó cũng làm cửa sổ generator tăng từ 6 lên 8, nên khi đọc A/B phải
nhớ: câu SO_SANH không chỉ được tách truy vấn, mà còn được **nhiều ngữ cảnh hơn**.
Hai thay đổi bị gộp, không thể quy công cho riêng subquery.

### 3.2. Vì sao THU_TUC tăng BM25?

Thủ tục thường chứa cụm hành chính lặp lại: “hồ sơ”, “giấy tờ”, “nộp tại”, “phòng
công tác sinh viên”. BM25 khớp chính xác các cụm này tốt hơn vector. 0.6/0.4 là
**giả thuyết ban đầu**, được ghi rõ trong docstring là “sẽ hiệu chỉnh theo A/B”.
Trong A/B, THU_TUC chỉ có 5 câu; không đủ để kết luận. Đừng trình bày 0.6/0.4 như
“tối ưu đã được chứng minh”.

### 3.3. Vì sao không bỏ truy xuất với NGOAI_PHAM_VI?

Vì precision của nhãn này chỉ **25%** (chương 04: 12 lần đoán, 3 đúng). Nếu router
thấy NGOAI là `return []` hoặc skip retrieval, 9 câu TRA_CUU bị từ chối oan. Từ chối
phải dựa trên **ngữ cảnh truy xuất** (không có chunk liên quan) chứ không chỉ nhãn.
Đây là quyết định thiết kế đúng, và là ví dụ tốt về việc không tin classifier quá mức.

### 3.4. Ví dụ tính config

Base: `top_k=6`, `bm25=0.5`, `chroma=0.5`.

| Nhãn | top_k | bm25/chroma | filter | subquery |
|---|---:|---|---|---|
| `{topic: "học phí", type: "TRA_CUU"}` | 6 | 0.5/0.5 | 2 file học phí | False |
| `{topic: "học phí", type: "SO_SANH"}` | **8** | 0.5/0.5 | 2 file học phí | **True** |
| `{topic: "thực tập tốt nghiệp", type: "THU_TUC"}` | 6 | **0.6/0.4** | 1 file TTTN | False |
| `{topic: None, type: "NGOAI_PHAM_VI"}` | 6 | 0.5/0.5 | None | False |
| `{topic: "ký túc xá", type: "TRA_CUU"}` | 6 | 0.5/0.5 | None (n=2) | False |

Với SO_SANH, `retrieve_k = 8 × 2 = 16`; generator nhận 8. Với TRA_CUU, `retrieve_k =
6 × 2 = 12`; generator nhận 6.

---

## 4. Bộ lọc theo chủ đề

### 4.1. Tám chủ đề được lọc

`TOPIC_SOURCE_FILTER` (`src/retrieval/router.py:68–95`):

| Chủ đề | Nguồn |
|---|---|
| chương trình đào tạo | `ban-mo-ta-ctdt-nganh-cntt-2021.pdf` |
| học phí | 2 file: thông báo miễn giảm + quy định mức học phí 2026–2027 |
| cuộc thi chính luận | `367-QĐ-ĐU ngay 08-4-2026.pdf` |
| đánh giá rèn luyện | `1059-qd-dhag-2020-09-29.pdf` |
| khen thưởng sinh viên | `888-qd-dhag-2022-08-08.pdf` |
| thực tập tốt nghiệp | `ke-hoach-ttck-kltn-dh24th-2026.pdf` |
| quy chế công tác sinh viên | `1054-qd-dhag-2020-09-28.pdf` |
| sinh viên 5 tốt | file quy chế SV5T 2026–2028 |

Sáu chủ đề còn lại **cố ý không lọc**: bảo hiểm y tế, hành chính sinh viên, khen
thưởng cấp ĐHQG, ký túc xá, tài chính sinh viên, thực tập chuyên đề. Lý do: mỗi chủ
đề chỉ có 1–3 câu trong benchmark, không đủ bằng chứng để biết tài liệu nào thực sự
chứa câu trả lời.

### 4.2. Tiêu chí chọn

Hai ngưỡng:

```python
MIN_QUESTIONS_FOR_SOURCE_FILTER = 5
MIN_SOURCE_CONCENTRATION = 0.8
```

- Chủ đề phải có **≥ 5 câu** trong benchmark v3;
- **≥ 80%** số câu in-corpus phải nằm trong **≤ 2 nguồn**.

Ngưỡng n≥5 do người dùng chốt ngày 2026-10-20. Docstring giải thích: quy tắc gốc
“≥80% trong ≤2 nguồn” áp lên v3 cho kết quả **14/14 chủ đề đạt 100%**, vì benchmark
được dựng theo văn bản nguồn. Nếu không có ngưỡng n, ngay cả chủ đề 1 câu cũng bị lọc
— rõ ràng là overfit.

### 4.3. Thiên lệch chọn mẫu — điểm phải nói khi bảo vệ

Đây là vấn đề phương pháp quan trọng nhất của router:

> Bộ lọc được thiết kế **từ chính benchmark v3**, rồi A/B được đánh giá **trên cùng
> benchmark v3**. Tập test đã tham gia vào thiết kế.

Hệ quả:

- 8/14 chủ đề được lọc đúng theo nguồn mà benchmark mong đợi; Hit@3 tăng mạnh ở
  CTĐT (+45.5 pp) và khen thưởng (+40 pp) một phần vì filter khớp đúng file mà
  benchmark dùng làm `source_document`.
- Với truy vấn thật ngoài benchmark, filter có thể **loại đúng tài liệu** nếu tài liệu
  mới không nằm trong danh sách cứng.
- Danh sách là tên file cứng. Đổi tên file, thêm văn bản mới, hoặc cập nhật quy chế →
  filter cũ sai. Không có cơ chế tự phát hiện.

Đây không phải “gian lận”, nhưng là **thiên lệch thiết kế** phải khai báo. Cách giảm:
chia benchmark thành train/development/test; thiết kế filter trên train, đánh giá trên
test; hoặc dùng metadata loại văn bản thay vì tên file.

### 4.4. Filter hoạt động thế nào trong pipeline?

Hai lớp (chi tiết ở chương 03):

1. **Chroma** nhận `filter={"source": {"$in": [...]}}` trước khi tìm, nên chỉ trả
   chunk trong nguồn.
2. **BM25** không filter được; sau khi gộp RRF, pipeline lọc hậu kiểm theo metadata
   `source`, so khớp qua `fold`.

Nếu lọc sạch → giữ kết quả chưa lọc. Nếu lọc còn một phần → danh sách ngắn hơn `k`.
Trong A/B WITH, 12 câu có `retrieved_k=11` thay vì 12 vì lý do này.

### 4.5. Filter làm tăng sức mạnh của lỗi classifier

Đây là hiệu ứng quan trọng, có số liệu:

- Chủ đề **đánh giá rèn luyện** trong A/B giảm Hit@3 từ 100% xuống 81.8% (n=11). Hai
  câu mất hit là Q28 và Q31 — cả hai bị classifier gán **sai chủ đề** (sang quy chế
  công tác sinh viên và CTĐT), nên router áp **filter sai**, loại mất tài liệu rèn
  luyện. Bản thân filter rèn luyện không sai; lỗi classifier bị filter khuếch đại.
- Chủ đề **thực tập chuyên đề** giảm 66.7% → 33.3% (n=3): Q86 bị gán TTTN → filter
  TTTN, mất nguồn TTCD; Q88 đúng chủ đề nhưng rơi từ hạng ≤3 xuống hạng 5 do đổi
  trọng số THU_TUC.

Bài học: **router không sửa lỗi classifier, nó nhân lỗi lên**. Nếu classifier sai
topic, filter biến một câu trả lời tạm được thành không có căn cứ.

---

## 5. Phòng thủ trong router

| Phòng thủ | Dòng | Hành vi |
|---|---:|---|
| `labels` không phải dict | 166–167 | trả bản sao `base` |
| nhãn lạ/thiếu | 143–155 | chuẩn hóa về `None`, bỏ điều chỉnh |
| topic lạ | 184–186 | `source_filter=None` |
| top_k ≤ 0 | 192–193 | trả `base.top_k` |
| cả hai trọng số ≤ 0 | 189–191 | trả trọng số base |
| không sửa `base` | 169 | `replace(base)` |

### 5.1. Ba lỗ hổng còn lại

1. **Trọng số âm lẻ.** Điều kiện chỉ chặn `bm25 <= 0 and chroma <= 0`. Cấu hình
   `bm25=-0.5, chroma=0.5` lọt qua, tổng bằng 0, RRF có thể âm/triệt tiêu. Nên kẹp
   từng trọng số về ≥0 và kiểm tra tổng >0.
2. **`enable_subquery` không được reset.** `replace(base)` giữ nguyên giá trị của
   base; hàm chỉ đặt `True` cho SO_SANH, không đặt `False` cho các loại khác. Với
   base mặc định (`False`) thì đúng; nếu ai đó truyền base có `True`, TRA_CUU cũng
   tách truy vấn. Nên gán `config.enable_subquery = (question_type == "SO_SANH")`.
3. **Không kiểm tra tên file tồn tại.** Filter sai tên → Chroma trả rỗng → post-filter
   rỗng → pipeline bỏ lọc và chạy rộng, chỉ còn một dòng cảnh báo. Đây là suy giảm
   mềm tốt cho dịch vụ, nhưng che mất lỗi cấu hình. Nên validate ít nhất một lần lúc
   khởi động.

### 5.2. Kiểm tra lúc import

`_UNKNOWN_FILTER_TOPICS` (`:199–204`) đảm bảo mọi khóa trong `TOPIC_SOURCE_FILTER`
thuộc 14 nhãn chuẩn; nếu không, `RuntimeError` ngay khi import. Đây là ví dụ tốt về
“fail fast” cho lỗi đánh máy nhãn. Nó không kiểm tra tên file.

---

## 6. A/B: đọc số liệu router

Nguồn: `outputs/ab_comparison.md`, hai lượt 21-10-2026, benchmark v3 100 câu, generator
local Qwen, judge tắt, top_k=6.

### 6.1. Bảng tổng thể

| Chỉ số | WITHOUT | WITH | Chênh |
|---|---:|---:|---:|
| Hit@3 | 60.8% | 77.3% | +16.5 pp |
| Hit@5 | 65.0% | 78.3% | +13.4 pp |
| Hit@6 | 66.0% | 78.3% | +12.4 pp |
| MRR | 0.5097 | 0.7689 | +0.259 |
| Citation F1 | 13.4% | 25.7% | +12.3 pp |
| Number support | 96.6% | 93.6% | −3.1 pp |
| Từ chối oan (in_corpus) | 47.4% | 50.5% | +3 câu |
| Latency (s/câu) | 2.30 | 7.79 | +5.49 |

### 6.2. Nhưng “WITH” không chỉ là router

Lượt WITH bật **một gói**:

1. classifier (hai nhãn);
2. router (top_k, trọng số, filter, subquery);
3. tách truy vấn con cho SO_SANH;
4. prompt generator theo `question_type` (P3.4);
5. filter nguồn.

Vì vậy **không thể** nói “router làm Hit@3 tăng 16.5 pp”. Câu đúng hơn: “gói phân
loại + định tuyến + prompt làm Hit@3 tăng 16.5 pp; router là một phần trong đó, chưa
được tách riêng”.

### 6.3. Phân bố nhãn dự đoán

| Nhãn dự đoán | n | Hit@3 | MRR |
|---|---:|---:|---:|
| TRA_CUU | 70 | 75.7% | 0.7534 |
| SO_SANH | 14 | 92.9% | 0.9388 |
| THU_TUC | 5 | 80.0% | 0.7400 |
| NGOAI_PHAM_VI | 11 | 62.5% | 0.4545 |

So với nhãn đúng: TRA_CUU 87, SO_SANH 5, THU_TUC 5, NGOAI 3. Classifier đoán **14
SO_SANH** và **11 NGOAI** — gấp 2–3 lần số thật. Đây là “recall cao, precision thấp”
đã thấy ở chương 04.

Hệ quả lên router:

- 14 câu bị tăng top_k lên 8 và bật tách truy vấn; 10 trong số đó thực ra là TRA_CUU.
- 11 câu bị gắn NGOAI; router không skip, nhưng generator nhận prompt từ chối.
- 7 câu NGOAI sai dẫn đến từ chối oan (báo cáo A/B mục 5).

### 6.4. Cửa sổ truy xuất thực tế

Meta của hai file A/B ghi `top_k=6 · retrieve_k=6`, nhưng đó là **floor truyền vào**,
không phải cửa sổ thật. Đếm `retrieval.retrieved_k` trong JSON:

| retrieved_k | Số câu WITH | Giải thích |
|---:|---:|---|
| 12 | 74 | TRA_CUU/THU_TUC + filter bình thường |
| 13 | 7 | SO_SANH, gộp nhánh chỉ còn 13 unique |
| 16 | 7 | SO_SANH, đủ 8 × 2 |
| 11 | 12 | filter làm hụt 1 chunk |

Đừng trích meta `retrieve_k=6` như thể đó là số chunk đã truy xuất. Muốn biết cửa sổ
thật, đọc `retrieval.retrieved_k` của từng entry. Đây là bài học chung: **metadata
của lần chạy có thể là tham số đầu vào, không phải kết quả thực tế**.

### 6.5. Tăng/giảm theo chủ đề

| Chủ đề | n | Hit@3 W/O | Hit@3 W | Δ |
|---|---:|---:|---:|---:|
| chương trình đào tạo | 22 | 45.5% | 90.9% | +45.5 |
| khen thưởng sinh viên | 10 | 10.0% | 50.0% | +40.0 |
| quy chế công tác sinh viên | 6 | 66.7% | 100% | +33.3 |
| thực tập tốt nghiệp | 9 | 66.7% | 100% | +33.3 |
| đánh giá rèn luyện | 11 | 100% | 81.8% | −18.2 |
| thực tập chuyên đề | 3 | 66.7% | 33.3% | −33.3 |
| học phí | 12 | 50.0% | 50.0% | 0 |

Đọc cùng bộ lọc:

- CTĐT, khen thưởng, quy chế, TTTN đều có filter hẹp và đều tăng mạnh → filter là
  ứng viên chính, nhưng vẫn bị gộp với prompt/classifier.
- Học phí có filter nhưng **không tăng** → filter không đủ; có thể filter đúng nhưng
  chunk chứa đáp án vẫn không vào top 3, hoặc câu hỏi cần thông tin nằm ngoài 2 file.
- Rèn luyện và TTCD giảm vì **classifier sai chủ đề** dẫn đến filter sai (mục 4.5),
  không phải vì filter đúng.

### 6.6. Một con số đáng chú ý: từ chối oan

WITH 49/97 câu in-corpus bị từ chối oan, WITHOUT 46/97. Chênh +3 câu. Trong 49 câu:

- 7 câu do classifier gán sai NGOAI (Q08, Q12, Q36, Q46, Q48, Q60, Q86);
- 36 câu TRA_CUU, 4 SO_SANH, 2 THU_TUC;
- phần lớn còn lại là hành vi của generator/guardrail, không phải router.

Nói cách khác: router làm từ chối oan **tệ hơn một chút**, nhưng vấn đề nền ~50% nằm
ở tầng sinh chữ. Đừng đổ hết cho router; cũng đừng bỏ qua việc misroute NGOAI.

### 6.7. Latency

2.30 → 7.79 s/câu, nhưng báo cáo ghi rõ **chỉ tham chiếu**: hai lượt chạy song song
trên cùng máy, pattern cache khác nhau (WITH miss nhiều ở SO_SANH do đổi truy vấn).
Không dùng để kết luận router “chậm 5.5 giây”. Muốn đo latency công bằng phải tắt
cache, chạy tuần tự, cùng điều kiện.

---

## 7. Thiết kế ablation nếu được làm lại

A/B hiện tại là “gói” vs “không gói”. Để chứng minh router, cần ít nhất:

| Nhánh | Classifier | Router | Subquery | Prompt theo type | Mục đích |
|---|---|---|---|---|---|
| A | tắt | tắt | tắt | tắt | baseline |
| B | bật (chỉ log nhãn) | tắt | tắt | tắt | đo chi phí/tác động classifier |
| C | **nhãn vàng** | bật | bật | tắt | router với nhãn hoàn hảo |
| D | nhãn dự đoán | bật | bật | tắt | router thực tế |
| E | nhãn vàng | chỉ filter | tắt | tắt | tách riêng filter |
| F | nhãn vàng | chỉ +2 top_k | tắt | tắt | tách riêng context window |
| G | nhãn vàng | chỉ đổi trọng số | tắt | tắt | tách riêng THU_TUC |
| H | nhãn dự đoán | bật | tắt | bật | tách riêng subquery |

Nhánh C và E/F/G là quan trọng nhất: chúng trả lời “nếu classifier đúng hoàn toàn thì
router đáng bao nhiêu?” và “phần nào của router tạo ra lợi ích?”. Nếu C ≈ D, classifier
không phải nút thắt; nếu C >> D, đầu tư vào classifier. Nếu E >> F, filter là đòn bẩy
chính; nếu F >> E, mở context là chính.

Ngoài ra: chia v3 thành train/dev/test, thiết kế filter trên train, báo cáo trên test.
Đây là cách duy nhất để loại thiên lệch chọn mẫu ở mục 4.3.

---

## 8. Truy vết ba câu

### 8.1. “Học phí khối kỹ thuật năm 2026–2027?”

```
labels: {topic: "học phí", type: "TRA_CUU"}
config: top_k=6, 0.5/0.5, filter=2 file học phí, sub=False
retrieve_k=12; generator nhận 6
```

### 8.2. “So sánh học phí kỹ thuật và kinh tế”

```
labels: {topic: "học phí", type: "SO_SANH"}
config: top_k=8, 0.5/0.5, filter=2 file học phí, sub=True
split → 2 truy vấn con → mỗi nhánh retrieve 16 → gộp → generator nhận 8
```

Nếu classifier gán nhầm TRA_CUU, câu này mất +2 và mất tách; nếu gán nhầm chủ đề khác,
filter sai còn tệ hơn.

### 8.3. “Sinh viên không hoàn thành đủ giờ thực tập có được gia hạn không?”

```
labels: {topic: "thực tập tốt nghiệp", type: "NGOAI_PHAM_VI"}
config: top_k=6, 0.5/0.5, filter=1 file TTTN, sub=False
retrieve_k=12 (thực tế 11 do filter)
generator nhận prompt NGOAI (nhắc từ chối)
```

Đây là Q97, `in_corpus=false`. Router **vẫn truy xuất** (đúng thiết kế), generator nhận
6 chunk có thể không chứa câu trả lời, và prompt NGOAI nhắc từ chối. Trong A/B, Q97 từ
chối đúng; Q96/Q98 vẫn trả lời (ảo giác). Nhãn NGOAI không đủ để bảo đảm từ chối — nó
chỉ là một tín hiệu.

---

## 9. Bài tập chương

**A. Tính config.** Base `top_k=6`, 0.5/0.5. Nhãn `{topic: "sinh viên 5 tốt", type:
"SO_SANH"}`. Cho biết top_k, trọng số, filter, subquery, `retrieve_k`, số chunk
generator nhận.

**B. Vì sao 6 chủ đề không lọc?** Nêu hai lý do và một rủi ro nếu lọc chúng.

**C. Filter sai tên file.** Chuyện gì xảy ra khi `source_filter` chứa một tên file
không tồn tại? Truy vết qua Chroma → post-filter → kết quả cuối. Vì sao đây là “êm”
nhưng nguy hiểm?

**D. Ablation.** Thiết kế một thí nghiệm chỉ để đo tác động của source filter, giả
định có nhãn vàng. Nêu nhánh đối chứng và metric.

**E. Trọng số âm.** Vì sao `bm25=-0.5, chroma=0.5` lọt qua phòng thủ hiện tại? Đề
xuất cách sửa và một test.

**F. Diễn giải A/B.** Một bạn nói: “Router tăng Hit@3 từ 60.8% lên 77.3%, vậy router
làm tăng 16.5 điểm”. Chỉ ra ba lý do cách nói này chưa chính xác.

<details>
<summary>Đáp án gợi ý</summary>

**A.** `top_k = 6 + 2 = 8`; trọng số 0.5/0.5 (SO_SANH không đổi trọng số); filter =
file quy chế SV5T (chủ đề có trong bảng 8); `enable_subquery=True`;
`retrieve_k = 8 × 2 = 16`; generator nhận 8 chunk.

**B.** (1) Mỗi chủ đề chỉ có 1–3 câu, không đủ bằng chứng về nguồn; (2) ngưỡng n≥5
được chốt để tránh lọc dựa trên mẫu quá nhỏ. Rủi ro nếu lọc: một câu hỏi thuộc chủ đề
đó nhưng câu trả lời nằm ở văn bản khác sẽ bị loại oan, và vì chỉ có 1–3 câu nên
không thể phát hiện bằng thống kê.

**C.** Chroma nhận filter `$in` với tên không tồn tại → trả 0 chunk; BM25 vẫn trả 12
chunk ngoài nguồn; RRF gộp; post-filter theo `fold(source)` loại tất cả; `filtered_docs`
rỗng → pipeline giữ nguyên kết quả **chưa lọc** và in cảnh báo. Kết quả cuối vẫn có
12 chunk, nhưng không còn lọc. “Êm” vì câu hỏi không chết; nguy hiểm vì hệ thống âm
thầm chạy sai cấu hình, và cảnh báo chỉ nằm trong log.

**D.** Hai nhánh, cùng nhãn vàng, cùng top_k/trọng số/subquery, chỉ khác filter:
(1) filter bật; (2) filter tắt. Đo Hit@3/5/6, MRR, Citation F1 trên cùng tập test.
Tốt hơn: thêm nhánh filter theo **metadata loại văn bản** thay vì tên file, để đo
xem lợi ích đến từ “thu hẹp đúng nguồn” hay từ “khớp đúng tên file benchmark”.

**E.** Điều kiện chỉ chặn khi **cả hai** ≤0; một âm một dương vẫn qua. Sửa:
`config.bm25_weight = max(0.0, config.bm25_weight)`, tương tự chroma; nếu tổng ≤0 thì
trả base. Test: gọi `get_retrieval_config({"question_type": "THU_TUC"}, base)` với env
`BM25_WEIGHT=-0.5`, `CHROMA_WEIGHT=0.5`, assert cả hai ≥0 và tổng >0.

**F.** (1) WITH bật cả classifier, router, subquery, prompt theo type, filter — không
phải riêng router; (2) classifier có lỗi (10 TRA_CUU→SO_SANH, 9→NGOAI), nên router
không được áp đúng cho mọi câu; (3) filter được thiết kế từ chính v3 rồi đo trên v3,
có thiên lệch chọn mẫu; (4) n=100, một số nhóm n nhỏ, không có khoảng tin cậy. Cần
ablation với nhãn vàng và tập test tách biệt.

</details>

Tiếp theo: [06 — Generator và chống ảo giác](06_generator_va_chong_ao_giac.md).
