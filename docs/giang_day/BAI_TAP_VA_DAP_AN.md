# Bài tập và đáp án — 40 bài phân tầng

Bộ bài tập này đi từ **hiểu cơ chế** → **đọc số liệu** → **phản biện thiết kế**.
Mỗi bài đều chỉ về chương gốc để tra cứu. Cách học hiệu quả:

1. Đọc câu hỏi, tự trả lời bằng giấy trong 3–5 phút.
2. Mở đáp án, so từng ý.
3. Nếu sai, mở đúng chương được ghi ở cuối bài — đừng học thuộc đáp án.

> Quy ước: “n=97” là 97 câu in-corpus của benchmark v3; “n=32” là số câu có
> ground truth trích dẫn; “n=30” là số câu đo được bảo toàn thực thể. Các con số
> lấy từ lượt A/B Qwen 1.5B, judge tắt.

---

## Nhóm A — Hiểu cơ chế (bài 1–15)

### Bài 1. `fold()` làm gì và vì sao BM25 phải dùng hai loại token?

<details>
<summary>Đáp án</summary>

`fold()` chuẩn hóa Unicode NFD, bỏ dấu thanh, đổi `đ → d`, lower-case và gom
khoảng trắng. Nó cho phép “Điều 12” khớp “dieu 12”.

BM25 dùng `bm25_tokenize` sinh **cả token gốc có dấu lẫn token đã fold**. Lý do:
corpus Tầng 1 bị OCR mất dấu, còn câu hỏi sinh viên thường có dấu. Nếu chỉ index
một dạng, một trong hai phía sẽ trượt. Hai dạng token khiến chỉ mục BM25 phình
gấp đôi, nhưng với 361 chunk chi phí không đáng kể.

Chương 03.
</details>

### Bài 2. Vì sao query gửi vào Chroma cũng được fold?

<details>
<summary>Đáp án</summary>

Vì tài liệu trong Chroma (nhất là Tầng 1 OCR) có thể không dấu. Nếu query có dấu
mà tài liệu không dấu, embedding vẫn có thể gần nhau nhưng không đảm bảo; fold
query giúp hai phía cùng “hệ quy chiếu” và nhất quán với BM25. Đây là quyết định
nhất quán: **một phép chuẩn hóa dùng ở mọi tầng so khớp**, không chỉ ở BM25.

Đánh đổi: fold làm mất thông tin thanh điệu, có thể tăng nhầm lẫn giữa các từ
đồng âm khác dấu; hệ thống chấp nhận vì dữ liệu gốc đã mất dấu.

Chương 03.
</details>

### Bài 3. Tính điểm RRF cho một chunk xếp hạng 1 ở BM25 và hạng 3 ở dense, với c=60.

<details>
<summary>Đáp án</summary>

Công thức: `score = Σ 1/(c + rank)`, rank bắt đầu từ 1.

`1/61 + 1/63 = 0.016393 + 0.015873 = 0.032266`.

Một chunk chỉ xếp hạng 1 ở một nhánh được `1/61 = 0.016393`. Vì vậy chunk xuất
hiện ở cả hai nhánh được thưởng gần gấp đôi. Hằng số 60 làm chênh lệch giữa hạng
1 và hạng 2 nhỏ (`1/61` vs `1/62`), giảm ảnh hưởng của một nhánh duy nhất.

Chương 03.
</details>

### Bài 4. Với `top_k=4`, pipeline truy xuất bao nhiêu chunk? `sources` và `contexts` khác nhau thế nào?

<details>
<summary>Đáp án</summary>

`retrieve_k = top_k × oversample_factor = 4 × 2 = 8`. Pipeline lấy tối đa 8 chunk
từ retriever; `sources` là cửa sổ recall này (kèm metadata/score), `contexts` là
4 chunk đầu đưa vào generator.

Nếu router SO_SANH bật, top_k hiệu dụng +2 → 6, nên `contexts=6`, `sources` có
thể tới 12 (trước khử trùng lặp). Trong evaluation hiện tại, lỗi truyền
`retrieve_k` khiến cửa sổ thực là 12/6 (SO_SANH: 16/8) dù khai báo `top_k=4` —
xem bài 25.

Chương 01, 07.
</details>

### Bài 5. Vì sao phải tách `sources` và `contexts`?

<details>
<summary>Đáp án</summary>

Mục đích đo khác mục đích sinh:

- `sources` (cửa sổ recall) dùng để đo Hit@K/MRR công bằng: chunk đúng ở hạng
  4–8 vẫn được tính, không bị phạt oan.
- `contexts` (cửa sổ generator) chỉ chứa top_k để prompt không phình, giảm nhiễu
  và tiết kiệm token.

Nếu dùng chung một cửa sổ: hoặc Hit bị đánh giá quá chặt, hoặc generator bị nhồi
quá nhiều ngữ cảnh. Tách ra là nguyên tắc “đo rộng, trả lời hẹp”.

Chương 01, 08.
</details>

### Bài 6. Vì sao loader OCR theo từng trang thay vì OCR cả file PDF?

<details>
<summary>Đáp án</summary>

Một PDF thường có trang bìa scan + trang thân text. OCR cả file vừa tốn thời gian
(ví dụ 10 phút cho cả bộ Tầng 1) vừa có thể làm hỏng trang đã có text tốt. Loader
đếm ký tự từng trang; trang nào nghèo chữ (dưới ngưỡng) mới đưa qua RapidOCR.
Cache theo nội dung file + tham số OCR để lần sau không chạy lại.

Chương 02.
</details>

### Bài 7. Chunk production khác 3 chiến lược thực nghiệm ở điểm nào?

<details>
<summary>Đáp án</summary>

- Production: `DocumentChunker`, cắt theo ký tự (`max_chars≈1200`), ưu tiên cấu
  trúc Điều/Khoản, có overlap ký tự; mục tiêu index thật.
- Thực nghiệm: cắt theo **token**, cùng ngưỡng 512 cho cả ba, ba thuật toán
  `fixed / recursive / structure`, mỗi chiến lược một index riêng; mục tiêu so
  sánh có kiểm soát.

Vì vậy production 361 chunk còn structure thực nghiệm 378 chunk — khác cấu hình,
không phải mâu thuẫn.

Chương 02, 09.
</details>

### Bài 8. Chunk structure-aware chèn tiền tố gì và vì sao?

<details>
<summary>Đáp án</summary>

Tiền tố dạng `[Tên văn bản] - [Điều N.] - [Khoản x-y] - [Điểm a-b]`.

Lý do: khi một Điều bị cắt thành nhiều chunk, chunk thứ hai vẫn biết mình thuộc
văn bản/Điều/Khoản nào. Điều này giúp embedding có ngữ cảnh, giúp trích dẫn
không lệch, và giúp người đọc kiểm chứng. Cấp nào không có thì bỏ, không bịa.

Chương 02.
</details>

### Bài 9. Guardrail của LocalSLM kiểm tra hai tín hiệu gì? Vi phạm thì xử lý ra sao?

<details>
<summary>Đáp án</summary>

Hai tín hiệu trên văn bản đã fold:

1. **Bảo toàn con số**: mọi số trong câu gốc (Điều/Khoản, mức tiền, %) phải còn
   trong câu chuẩn hóa; mất số → từ chối.
2. **Token overlap**: tỷ lệ token chung phải ≥ ngưỡng (mặc định 0.3); quá thấp
   nghĩa là model viết lại lạc đề.

Vi phạm → dùng câu gốc, không làm chết lượt hỏi. Đây là suy giảm mềm.

Chương 04.
</details>

### Bài 10. Classifier trả về nhãn lạ hoặc lỗi thì router làm gì?

<details>
<summary>Đáp án</summary>

`_normalize_topic` / `_normalize_question_type` đưa nhãn lạ về `None`;
`get_retrieval_config(labels=None, base)` trả bản sao cấu hình nền. Không có
exception, không có nhánh chết. Đây là fail-open: hệ thống vẫn chạy với cấu hình
mặc định, chỉ mất phần tối ưu theo lớp.

Đổi lại, nếu không log, người đọc số liệu không biết câu nào đã suy giảm — vì vậy
cần trường `router_fallback` trong entry.

Chương 05.
</details>

### Bài 11. Router thay đổi gì cho câu hỏi SO_SANH?

<details>
<summary>Đáp án</summary>

- Cộng thêm 2 vào `top_k` (cửa sổ ngữ cảnh rộng hơn để chứa cả hai đối tượng).
- Tách câu hỏi thành 2–3 truy vấn con, truy xuất từng nhánh, hợp nhất theo thứ
  hạng tốt nhất.
- Có thể đổi trọng số BM25/dense nếu cấu hình lớp quy định.

Mục tiêu: không để một đối tượng “nuốt” ngữ cảnh của đối tượng kia.

Chương 05.
</details>

### Bài 12. Prompt grounded có những quy tắc chống ảo giác nào?

<details>
<summary>Đáp án</summary>

Các quy tắc cốt lõi (chi tiết ở chương 06):

- Chỉ dùng thông tin trong ngữ cảnh được cung cấp; không dùng kiến thức ngoài.
- Nếu ngữ cảnh không đủ, trả lời bằng câu từ chối chuẩn thay vì suy đoán.
- Nêu căn cứ Điều/Khoản khi trả lời.
- Không bịa số liệu, tên văn bản, mốc thời gian.
- Trả lời tiếng Việt, rõ ràng, có thể trích dẫn.

Prompt không đảm bảo 100%; nó chỉ giảm xác suất. Vì vậy vẫn cần đo
faithfulness/citation.

Chương 06.
</details>

### Bài 13. Cache key của generator gồm những gì? Đổi prompt có trúng cache không?

<details>
<summary>Đáp án</summary>

Key là SHA-1 của `{model, temperature, prompt}` (Qwen tương tự). Đổi prompt →
prompt mới → hash mới → **cache miss**. Đổi model hoặc temperature cũng miss.
Đổi corpus nhưng prompt không đổi thì vẫn có thể trúng cache cũ — đây là lý do
phải xóa cache khi index thay đổi nếu muốn đo lại từ đầu.

Chương 06.
</details>

### Bài 14. Phân biệt lỗi quota “PerDay” và “429 theo phút”; mỗi loại xử lý thế nào?

<details>
<summary>Đáp án</summary>

- **429 theo phút**: lỗi tạm thời; chờ 60 giây, thử tối đa 3 lần, không tính vào
  hạn retry thường.
- **PerDay**: đã hết quota ngày; retry vô ích. Lượt chạy dừng sớm, ghi những câu
  đã chạy, báo `aborted_by_quota`.

Phân loại sai sẽ hoặc đốt thời gian chờ vô ích, hoặc bỏ lượt chạy oan.

Chương 06, 08.
</details>

### Bài 15. Vì sao câu từ chối phải được “canonical hóa”?

<details>
<summary>Đáp án</summary>

Evaluation và UI nhận diện từ chối bằng `REFUSAL_MARKER`. Nếu model tự viết một
câu từ chối khác (“Tôi không thể tìm thấy…”), marker không khớp, câu đó bị chấm
như câu trả lời bình thường — có thể bị tính là ảo giác hoặc trả lời sai.

`canonicalize_refusal` chỉ chuẩn hóa khi câu hỏi thuộc NGOAI_PHAM_VI và câu trả
lời đã có dấu hiệu từ chối; nó không biến câu trả lời đúng thành từ chối. Nhờ
vậy đo lường nhất quán và UX thống nhất.

Chương 06.
</details>

---

## Nhóm B — Đọc số liệu và debug (bài 16–30)

### Bài 16. “Hit@3 = 75/97 = 77.3%” có nghĩa gì và **không** có nghĩa gì?

<details>
<summary>Đáp án</summary>

Có nghĩa: trong 97 câu in-corpus, 75 câu có ít nhất một chunk thuộc **tài liệu
đúng** nằm trong top 3 của cửa sổ recall.

Không có nghĩa:

- Không phải 77.3% câu trả lời đúng.
- Không phải chunk đúng chứa điều khoản trả lời (chỉ đúng tài liệu).
- Không tính 3 câu ngoài corpus (mẫu số 97, không phải 100).
- Không nói gì về citation hay faithfulness.

Chương 08.
</details>

### Bài 17. Vì sao MRR được tính trên toàn bộ recall window thay vì cắt ở 6?

<details>
<summary>Đáp án</summary>

Vì mục tiêu là đo **chất lượng xếp hạng** của retriever, không chỉ việc “có nằm
trong top 6 hay không”. Một chunk đúng ở hạng 8 vẫn tốt hơn chunk đúng ở hạng
12; cắt ở 6 sẽ biến cả hai thành 0 và mất thông tin. Hit@6 vẫn được báo riêng để
phản ánh cửa sổ generator.

Hệ quả: MRR có thể cao hơn cảm nhận thực tế nếu cửa sổ recall rất rộng; phải đọc
kèm Hit@3/5/6.

Chương 08.
</details>

### Bài 18. Tính điểm RRF cho chunk hạng 1 và hạng 3; nhận xét về ảnh hưởng của `c`.

<details>
<summary>Đáp án</summary>

Với `c=60`: hạng 1 = `1/61 ≈ 0.01639`; hạng 3 = `1/63 ≈ 0.01587`. Chênh nhau
khoảng 3%, rất nhỏ. Nếu `c=1`: hạng 1 = 0.5, hạng 3 = 0.25 — chênh gấp đôi.

`c` lớn làm RRF “phẳng”, giảm ưu thế tuyệt đối của hạng đầu và tăng vai trò của
việc xuất hiện ở nhiều nhánh. Đồ án dùng mặc định 60, **không tune** — cần ghi
là giới hạn.

Chương 03.
</details>

### Bài 19. Vì sao citation chỉ chấm 32/100 câu? Extractor bỏ sót gì?

<details>
<summary>Đáp án</summary>

Vì `extract_citations` chỉ nhận mẫu “Điều X” và “Khoản Y” trong câu trả lời; 68
câu không có mẫu này nên `citations = null`, không được chấm.

Bỏ sót đã biết:

- “Khoản 2” đứng một mình (không kèm “Điều”) bị bỏ.
- Dải “Điều 3–5” có thể bị giới hạn bởi `CITATION_RANGE_CAP`.
- Trích dẫn bằng tên văn bản thay vì Điều/Khoản không được nhận.
- Trọng số khớp một phần hard-code 0.5, không dùng hằng số thiết kế.

Vì vậy 32 câu là mẫu **có điều kiện**, không đại diện 100 câu.

Chương 08.
</details>

### Bài 20. Chứng minh citation F1 25.7% bị thổi phồng bởi 5 câu dự đoán rỗng.

<details>
<summary>Đáp án</summary>

Trong 32 câu, 5 câu không trích dẫn được nhưng `citation_scores` trả 1.0 nhờ
nhánh `"" in source`. Phần đóng góp của 5 câu này vào F1 trung bình là `5/32 =
15.625%`. Số đúng khi tính lại là 10.10%.

`10.10% + 15.625% = 25.725% ≈ 25.73%` — đúng bằng con số trong JSON.

Tương tự WITHOUT: `4.02% + 3/32 = 13.40%`; Gemini cũ: `0.0 + 25/32 = 78.1%`.

Chương 08, 10.
</details>

### Bài 21. Vì sao “từ chối oan” là chỉ số đầu-cuối, không phải chỉ số generator? Thiết kế phép join.

<details>
<summary>Đáp án</summary>

Vì một câu in-corpus có thể bị từ chối do hai nguyên nhân:

1. Retrieval không mang về chunk chứa đáp án → generator từ chối là **hợp lý**
   trong khuôn khổ RAG.
2. Retrieval có đáp án nhưng generator/prompt quá thận trọng → từ chối oan thật.

Join từng entry với `retrieval.hit_at_k`:

| | Có hit | Không hit |
|---|---:|---:|
| Từ chối | A (oan generator) | B (lỗi retrieval) |
| Trả lời | C | D (nguy cơ ảo giác) |

Cần đọc thủ công một mẫu A để phân loại prompt/model. Đồ án chưa làm join này.

Chương 08, 10.
</details>

### Bài 22. Vì sao `normalization_preservation` chỉ có n=30?

<details>
<summary>Đáp án</summary>

Chỉ 30 câu có đủ điều kiện đo: câu gốc chứa thực thể/số (Điều, Khoản, mức tiền,
%) **và** câu đã qua chuẩn hóa. 70 câu còn lại không có thực thể để bảo toàn,
hoặc không qua bước chuẩn hóa (đã là câu học vụ), nên không đưa vào mẫu số.

Vì vậy 96.67% là “trong 30 câu đo được”, không phải “trong 100 câu”. Đây là ví dụ
điển hình của việc phải đọc mẫu số trước khi đọc phần trăm.

Chương 08.
</details>

### Bài 23. `number_support = 96.6%` có chứng minh câu trả lời trung thực không?

<details>
<summary>Đáp án</summary>

Không. `number_support` chỉ kiểm tra **các con số** trong câu trả lời có xuất
hiện trong ngữ cảnh hay không. Nó không kiểm tra:

- Quan hệ giữa các con số (điều kiện, ngoại lệ, phủ định).
- Tên văn bản, đối tượng, thời hạn không phải số.
- Câu bịa không chứa số.

Phản ví dụ: ngữ cảnh nói “sinh viên bị cảnh báo nếu GPA dưới 1.0”, câu trả lời
“sinh viên bị cảnh báo nếu GPA trên 1.0” vẫn có số 1.0 trong ngữ cảnh → được
điểm cao dù sai nghĩa.

Chương 08.
</details>

### Bài 24. Vì sao heuristic gán 1.0 cho câu từ chối, và hệ quả lên điểm trung bình?

<details>
<summary>Đáp án</summary>

Vì câu từ chối không có nội dung cần đối chiếu; theo thiết kế, từ chối đúng được
coi là “không bịa” nên nhận 1.0. Hệ quả: khi tính trung bình trên 100 câu, 47–49
câu từ chối được 1.0, kéo điểm lên.

Số đúng:

- Chỉ câu trả lời: 0.643 (WITHOUT) / 0.647 (WITH).
- Gộp cả từ chối: 0.811 / 0.823.

Chênh lệch ~0.17 chính là “phần thưởng từ chối”. Phải báo cáo cả hai, hoặc chỉ
báo điểm trên câu trả lời.

Chương 08.
</details>

### Bài 25. Lỗi `top_k=retrieve_k` ảnh hưởng gì khi chạy `-k 4`? Vì sao A/B vẫn so sánh được nội bộ?

<details>
<summary>Đáp án</summary>

Với `-k 4`: `main` đặt sàn `retrieve_k = max(4, 6) = 6`, rồi gọi
`evaluate_question(..., top_k=4, retrieve_k=6)`. Đến dòng 471, hàm này lại gọi
`pipeline.run(top_k=retrieve_k)` — tức **6**, không phải 4. Pipeline nhân
oversample → `sources = 12`, generator nhận `contexts = 6`.

Metadata ghi `retrieval.top_k = 4` (cửa sổ generator *khai báo*) và
`retrieved_k = 12` (số nguồn thực); còn cửa sổ generator *thực* là 6. Hit@4 chỉ
xét 4 phần tử đầu của 12. Nếu bật classifier và router SO_SANH cộng 2: generator
nhận 8, `sources` tới 16 (khử trùng lặp còn 13 ở một số câu).

Với mặc định `-k 6`: `retrieve_k = 6`, pipeline lấy 12, generator nhận 6 — trùng
với mô tả “retrieve 12 / context 6”, nên lỗi ẩn. Lỗi chỉ lộ khi `top_k < 6`
(vùng bị sàn `MIN_TOP_K` kéo lên).

A/B vẫn so sánh được nội bộ vì **cả hai lượt dùng cùng một lỗi và cùng cấu hình**;
nhưng không được mô tả là “generator nhận 4 chunk” và không so được với một lượt
chạy đã sửa. Cách sửa đúng: gọi `pipeline.run(top_k=top_k)` và chỉ dùng
`retrieve_k` cho cửa sổ đo; hoặc log riêng `len(contexts)` để không nhầm cửa sổ
khai báo với cửa sổ thực.

Chương 08, 10.
</details>

### Bài 26. Vì sao accuracy classifier trong A/B (87%/83%) cao hơn P2.3 (85%/81%)?

<details>
<summary>Đáp án</summary>

Chủ yếu vì **16 câu few-shot nằm trong chính 100 câu benchmark**: mô hình đã thấy
trước câu và nhãn của chúng, nên lượt đo bị lạc quan. Ngoài ra A/B chạy trên câu
đã qua các bước xử lý khác, nhưng yếu tố rò rỉ là chính.

Đúng phải nói: “Trên 100 câu có 16 câu few-shot, accuracy là 87%/83%; trên tập
held-out, ước lượng giảm còn 82.1%/77.4%.” Không được quảng cáo 87% như năng lực
tổng quát.

Chương 08.
</details>

### Bài 27. kNN đạt 89% loại câu hỏi, classifier 81%. Có nên bỏ classifier LLM?

<details>
<summary>Đáp án</summary>

Không nên bỏ ngay, nhưng phải thiết kế lại:

- kNN thắng **loại câu hỏi** (89% ở k=3) vì nhãn này tương quan mạnh với bề mặt
  câu (“so sánh”, “thủ tục”, “có phải…”), embedding bắt tốt.
- Classifier thắng **chủ đề** (85% vs 72–76%) vì cần hiểu ngữ nghĩa pháp lý.
- Classifier còn trả nhãn có cấu trúc và phục vụ router; kNN không giải thích được.

Hướng tốt: ensemble hoặc lai — dùng kNN cho `question_type`, LLM cho `topic`,
đo lại trên held-out. Nhưng phải tính chi phí và độ phức tạp.

Chương 08.
</details>

### Bài 28. Fixed đạt Hit@3 0.88, structure 0.76. Có nên kết luận fixed tốt hơn?

<details>
<summary>Đáp án</summary>

Không. Fixed có 182 chunk lớn; top 3 chunk phủ nhiều văn bản hơn nên Hit mức tài
liệu cao hơn. Structure có 378 chunk nhỏ; top 3 phủ ít hơn, nên Hit thấp hơn,
nhưng MRR cao hơn (0.716 vs 0.698) và Citation F1 cao hơn (0.0767 vs 0.0).

Kết luận đúng: “Fixed thắng recall top-3; structure thắng xếp hạng và trích dẫn;
chọn theo mục tiêu.” Ngoài ra 50 câu, không có confidence interval — không nên
tuyên bố “tốt nhất” tuyệt đối.

Chương 09, 10.
</details>

### Bài 29. Vì sao index structure lớn hơn 40% dù số chunk chỉ gấp đôi?

<details>
<summary>Đáp án</summary>

Structure có 378 chunk so với 182 (gấp 2.08), nhưng index 5.93 MB so với 4.24 MB
(chỉ gấp 1.40). Lý do:

- Mỗi vector bge-m3 có cùng số chiều (1024), nên phần vector tăng tuyến tính theo
  số chunk.
- Mỗi chunk còn lưu text + metadata + ID; chunk structure ngắn hơn nhưng có tiền
  tố phân cấp.
- Chroma có overhead cố định (HNSW, metadata index) không tăng tuyến tính.

Vì vậy không nên suy từ “số chunk gấp đôi” ra “index gấp đôi”; phải đo.

Chương 09.
</details>

### Bài 30. Vì sao `refusal_rate = 0.0` trong benchmark chunking là sai? Sửa thế nào?

<details>
<summary>Đáp án</summary>

Dòng 413 dùng `REFUSAL_MARKER in fold(answer)`. `REFUSAL_MARKER` có dấu, còn
`fold(answer)` đã bỏ dấu → không bao giờ khớp → mọi câu đều được coi là không từ
chối.

Sửa: `fold(REFUSAL_MARKER) in fold(answer)`.

Nếu 50 câu benchmark chunking đều in-corpus, `refusal_rate` không có ý nghĩa;
đúng ra phải là `n/a` hoặc bỏ hẳn cột, chứ không phải 0.0.

Chương 09, 10.
</details>

---

## Nhóm C — Thiết kế và phản biện (bài 31–40)

### Bài 31. Thiết kế ablation tách tác động của classifier, router và subquery.

<details>
<summary>Đáp án</summary>

Bốn lượt, cùng 100 câu, cùng generator Qwen, cùng `top_k`, tắt cache, cùng
temperature 0:

1. **Baseline:** không classifier, không router, không subquery.
2. **Classifier-only:** bật classifier để lấy nhãn nhưng router luôn trả cấu
   hình nền; đo ảnh hưởng của việc phân loại lên prompt (nếu có).
3. **Router-only (oracle):** dùng nhãn **đúng từ benchmark** thay vì nhãn dự
   đoán, bật router. Lượt này tách hiệu ứng router khỏi lỗi classifier.
4. **Full:** classifier + router + subquery như sản xuất.

Đo: Hit@3/5/6, MRR, citation, false refusal, latency, số chunk ngữ cảnh. Kết
luận chỉ được quy công khi chênh lệch giữa các lượt vượt biến thiên do mẫu nhỏ;
nên bootstrap CI.

Chương 08, 10.
</details>

### Bài 32. Thiết kế cổng (gate) chống từ chối oan.

<details>
<summary>Đáp án</summary>

Định nghĩa rõ:

- Tử số: số câu `in_corpus=true` bị trả lời chứa `REFUSAL_MARKER`.
- Mẫu số: tổng số câu `in_corpus=true` (97).
- Tách A (có hit mà vẫn từ chối) và B (không hit nên từ chối).

Cổng đề xuất:

- `A / 97 ≤ 20%` (lỗi generator/prompt).
- `(A+B) / 97 ≤ 30%` (trải nghiệm tổng).
- Bổ sung 20 câu ngoài corpus mới để đo từ chối đúng, vì 3 câu hiện tại quá ít.
- Đo lại sau mỗi thay đổi prompt; lưu bảng trước/sau.

Không đặt cổng chỉ trên “refusal rate” gộp vì sẽ che mất sự đánh đổi.

Chương 08, 10.
</details>

### Bài 33. Viết test cho lỗi citation thưởng câu rỗng.

<details>
<summary>Đáp án</summary>

Tối thiểu 5 ca:

1. `expected={"Điều 5"}`, `predicted=set()`, `source_document="a.pdf"` → F1 = 0
   (đây là ca bắt lỗi).
2. `expected={"Điều 5"}`, `predicted={"Điều 5"}`, source bất kỳ → F1 = 1.
3. `expected={"Điều 5"}`, `predicted={"Điều 6"}` → F1 = 0.
4. `expected={"Điều 5 Khoản 2"}`, `predicted={"Điều 5"}` → partial > 0, < 1.
5. `expected=set()`, `predicted={"Điều 5"}` → xử lý rõ (None/0), không chia 0.

Thêm test hồi quy: đọc 32 câu fixture đã tính tay, so F1 đúng đến 1e-6. Chạy
trước/sau khi sửa để chứng minh.

Chương 08, 10.
</details>

### Bài 34. Thiết kế khóa resume đầy đủ.

<details>
<summary>Đáp án</summary>

Meta phải chứa tối thiểu:

- Đường dẫn + mtime/hash của benchmark.
- `top_k`, `retrieve_k`, `oversample_factor`.
- `generator_model`, `temperature`, `max_output_tokens`.
- `with_classifier`, `classifier_model`, `judge_enabled`, `judge_model`.
- `embedding_model`, hash/version của index.
- `prompt_version` (nếu prompt đổi, câu trả lời cũ không còn tương đương).

Khóa resume = hash của toàn bộ các trường trên. Nếu hash khác → không dùng lại
entry, in cảnh báo. Không chỉ kiểm benchmark + cờ A/B như hiện tại.

Chương 08, 10.
</details>

### Bài 35. Đề xuất ba chỉ số thay thế/bổ sung cho Hit mức tài liệu.

<details>
<summary>Đáp án</summary>

1. **Context Precision / Recall ở mức chunk-đáp án:** chunk truy xuất có chứa
   đoạn văn bản trả lời không (đánh dấu thủ công hoặc span matching).
2. **Answer Correctness:** so câu trả lời với đáp án chuẩn (human rubric hoặc
   LLM judge có kiểm chứng).
3. **Citation Correctness ở mức claim:** mỗi khẳng định có được đúng Điều/Khoản
   hỗ trợ không, thay vì chỉ so tập trích dẫn.

Có thể thêm **Refusal Appropriateness** (từ chối đúng/sai) và **latency**. Ba chỉ
số đầu trả lời đúng câu hỏi “hệ thống có trả lời đúng không”, thứ Hit không trả
lời được.

Chương 08, 10.
</details>

### Bài 36. Nếu corpus tăng lên 100.000 chunk, kiến trúc hiện tại gặp gì?

<details>
<summary>Đáp án</summary>

- **BM25**: dựng lại từ toàn bộ Document trong Chroma mỗi lần khởi động; 100k
  chunk sẽ tốn RAM/thời gian, dual tokenizer còn nhân đôi số term. Cần index
  sparse offline (ví dụ BM25S) hoặc lưu tokenized corpus.
- **Chroma/HNSW**: thời gian query tăng, RAM tăng; cần sharding/partition theo
  chủ đề hoặc dùng vector DB khác.
- **Reranker**: top-12 thô có thể không đủ; cần retrieve nhiều hơn rồi rerank.
- **Evaluation**: 100 câu vẫn đo được nhưng phải lấy mẫu; latency cần đo lại.

Đồ án hiện tại chỉ 361 chunk, nên các con số latency không suy ra được cho 100k.

Chương 03, 10.
</details>

### Bài 37. Nếu đổi generator sang Gemini, chỉ số nào phải đo lại, chỉ số nào giữ nguyên?

<details>
<summary>Đáp án</summary>

**Giữ nguyên** (không phụ thuộc generator):

- Hit@3/5/6, MRR (retrieval).
- Số chunk, index size, thời gian retrieval.
- Classification accuracy (nếu classifier không đổi).
- Normalization preservation (nếu normalizer không đổi).

**Phải đo lại**:

- Citation P/R/F1/EM (generator viết trích dẫn khác).
- Faithfulness (LLM judge và heuristic).
- Từ chối oan/đúng, ảo giác ngoài corpus.
- Number support.
- Latency (Gemini API khác local).

Vì vậy không được bê nguyên “citation 10.1%” của Qwen sang Gemini.

Chương 08, 10.
</details>

### Bài 38. Thiết kế thí nghiệm chunk size 256/512/1024.

<details>
<summary>Đáp án</summary>

- Cố định: cùng corpus, cùng 3 chiến lược, cùng tokenizer, overlap 0 (hoặc cùng
  tỷ lệ 10%), cùng top_k=3, cùng retrieve_k=6, cùng generator/cache off.
- Ba mức 256/512/1024 × 3 chiến lược = 9 lượt; nếu tốn thời gian, chọn 512 làm
  baseline và chỉ chạy fixed/structure ở 256/1024.
- Đo: số chunk, mean/max token, index size, Hit@3/5/6, MRR, citation, latency.
- Phân tích: Hit tăng theo chunk size hay không; citation/MRR có đổi chiều không;
  index size tăng bao nhiêu.
- Báo cáo CI bootstrap; 50 câu hiện tại hơi ít, nên dùng 100 câu nếu có thể.

Chương 09.
</details>

### Bài 39. Viết 5 câu trả lời cho hội đồng về con số 78.1% citation.

<details>
<summary>Đáp án</summary>

1. “78,1% là con số của lượt Gemini cũ, không phải lượt A/B hiện tại.”
2. “Nó bị lỗi chấm: 25/32 câu không trích dẫn được nhưng hàm chấm trả 1.0 vì
   chuỗi rỗng luôn nằm trong chuỗi nguồn.”
3. “Tính lại bằng matching đúng, 25 câu đó được 0, nên F1 là 0,0 + 25/32 =
   78,1% — toàn bộ điểm đến từ câu rỗng.”
4. “Số đúng của A/B là 4,02% (WITHOUT) và 10,10% (WITH); em đã sửa báo cáo và
   ghi rõ đây là lỗi đo.”
5. “Bài học là mọi nhánh ‘không có dự đoán’ phải trả 0 và phải có test; em đã
   đưa việc này vào P0.”

Chương 08, 10.
</details>

### Bài 40. Chọn ba việc P0 trong hai ngày và biện luận.

<details>
<summary>Đáp án</summary>

1. **Sửa citation scoring + test câu rỗng** (nửa ngày): vì mọi so sánh citation
   đang sai; sửa xong mới biết hệ thống thực sự thế nào.
2. **Sửa `top_k=retrieve_k` + ghi log cửa sổ thực** (nửa ngày): vì mọi báo cáo
   đang mô tả sai cửa sổ generator; ảnh hưởng citation/faithfulness.
3. **Đo lại từ chối oan, join với Hit@K** (một ngày): vì 50% là vấn đề người
   dùng lớn nhất; join cho biết sửa retrieval hay prompt.

Không chọn OCR/reranker/fine-tune vì không kịp kiểm chứng trong hai ngày và
không cải thiện tính đúng đắn của số liệu hiện có.

Chương 10.
</details>

---

## Bảng tự đánh giá

| Mức | Điều kiện |
|---|---|
| **Cơ bản** | Làm đúng 1–15 mà không mở đáp án; giải thích được fold, RRF, oversampling. |
| **Trung cấp** | Làm đúng 16–30; đọc được mẫu số 97/32/30/3 và phát hiện lỗi citation. |
| **Bảo vệ** | Làm đúng 31–40; viết được thẻ chứng cứ và trả lời câu bẫy 78.1%. |

## Đọc tiếp

- Lý thuyết đầy đủ: [10 — Bài học và bảo vệ](10_bai_hoc_va_ky_nang.md).
- Tra cứu hàm: [Phụ lục hàm](PHU_LUC_ham.md).
- Quay lại lộ trình: [00 — Lộ trình học](00_lo_trinh_hoc.md).
