# Chương 3 — Kiến trúc hệ thống Hybrid RAG phân loại câu hỏi

> Bản nháp chương báo cáo (P5.3). Sơ đồ và đặc tả chép từ `docs/architecture/SYSTEM_ARCHITECTURE.md`
> (đã duyệt cổng P5.2); taxonomy từ `docs/spec/TAXONOMY.md` (cổng P1.1); tên đề tài và phạm
> vi từ `docs/planning/ROADMAP.md` (cổng P0.1). Mỗi phần kèm ghi chú nguồn; không có số liệu tự sinh.

## 3.1. Đề tài và hướng làm mới

Tên đề tài: **"Ứng dụng kiến trúc RAG phân loại câu hỏi và hỗ trợ truy xuất thông tin quy chế đào tạo sinh viên"**.

Đề tài kế thừa nguyên vẹn pipeline True Hybrid Search đang chạy ổn định (BM25 + ChromaDB/bge-m3 gộp bằng RRF, generator có trích dẫn Điều/Khoản và Soft Refusal), và bổ sung hai thành phần mới:

1. **Tầng phân loại câu hỏi 2 nhãn** — gán đồng thời `topic` (1 trong 14 chủ đề) và `question_type` (1 trong 4 nhãn `TRA_CUU` / `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI`) cho câu hỏi thô của sinh viên.
2. **Router truy xuất theo lớp câu hỏi** — biến nhãn phân loại thành cấu hình truy xuất cụ thể (số chunk, trọng số BM25/Chroma, lọc nguồn, cho phép tách truy vấn con), kèm biến thể prompt sinh câu trả lời theo loại câu hỏi.

Toàn bộ bổ sung nằm sau một công tắc an toàn `ENABLE_CLASSIFIER`: khi `0`, pipeline chạy y hệt hành vi cũ từng bước; khi `1`, tầng phân loại + router + tách truy vấn con + prompt biến thể được kích hoạt.

*Nguồn: docs/planning/ROADMAP.md mục 1, mục 4.*

### 3.1.1. Ba câu hỏi nghiên cứu

1. Bộ phân loại 2 nhãn (chủ đề + loại câu hỏi) đạt độ chính xác bao nhiêu trên 100 câu?
2. Router truy xuất theo lớp câu hỏi cải thiện Hit@K/MRR ở những nhóm câu nào so với cấu hình truy xuất chung?
3. Bật tầng phân loại có tốt hơn tắt trên tổng thể hay không, và có làm tụt chất lượng ở nhóm câu nào không?

*Nguồn: docs/planning/ROADMAP.md mục 2.*

## 3.2. Kiến trúc 6 tầng

Luồng xử lý một câu hỏi khi `ENABLE_CLASSIFIER=1` (khớp thứ tự thật trong `src/core/pipeline.py` — `HybridRAGPipeline.run()`):

```
┌─────────────────────────────────────────────────────────────────┐
│                     CÂU HỎI SINH VIÊN                         │
│          "Bị điểm yếu có bị đuổi học không ad?"                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│      LAYER 0: PHÂN LOẠI CÂU HỎI + ROUTER (Qwen local)          │
│  - src/core/classifier.py: gán 2 nhãn cho câu hỏi THÔ:              │
│      topic = "đánh giá rèn luyện" (1/14 chủ đề)                │
│      question_type = "TRA_CUU" (1/4 loại)                      │
│  - src/retrieval/router.py: nhãn → cấu hình truy xuất theo lớp           │
│  - Guardrail 3 lớp, suy giảm mềm: mọi lỗi → cấu hình gốc       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              LAYER 1: NORMALIZATION (Qwen)                      │
│  - "điểm yếu" → "xếp loại rèn luyện Yếu"                       │
│  - "đuổi học" → "buộc thôi học"                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│            LAYER 2: QUERY EXPANSION (Dictionary)                │
│  - Mở rộng từ đồng nghĩa pháp lý để tăng Recall                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│   LAYER 3: TÁCH TRUY VẤN CON (chỉ câu SO_SANH)                 │
│  - split_comparison_query(): tách 2–3 mệnh đề con độc lập       │
│  - Guardrail chống tách dở → lùi về đường đơn                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│   LAYER 4: TRUE HYBRID SEARCH (tham số THEO ROUTER)            │
│   BM25 Retriever + ChromaDB Retriever (BGE-M3)                  │
│   EnsembleRetriever: RRF dung hợp thứ hạng                      │
│  - top_k, trọng số, lọc nguồn do LAYER 0 quyết định             │
│  - Đường đa nhánh: truy xuất từng truy vấn con rồi gộp          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│   LAYER 5: GENERATOR (prompt THEO LOẠI CÂU HỎI)                 │
│  - SO_SANH → bảng so sánh; THU_TUC → bước đánh số;              │
│    NGOAI_PHAM_VI → nhắc từ chối chuẩn (không skip truy xuất)    │
│  - Soft Refusal khi ngữ cảnh không đủ căn cứ                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
            CÂU TRẢ LỜI CÓ TRÍCH DẪN (Điều X, Khoản Y — Văn bản)
```

*Sơ đồ đầy đủ (kèm ví dụ minh họa từng tầng) xem `docs/architecture/SYSTEM_ARCHITECTURE.md` mục 5; đặc tả chi tiết tầng phân loại/router ở mục 6 cùng file.*

## 3.3. Taxonomy: 14 chủ đề + 4 loại câu hỏi

### 3.3.1. 14 chủ đề (`category`)

| Chủ đề | Mô tả 1 dòng | Số câu benchmark |
|---|---|---:|
| chương trình đào tạo | Môn học, mã môn, tín chỉ, học kỳ, môn tiên quyết, chuẩn đầu ra ELO, khối kiến thức. | 22 |
| học phí | Mức thu, miễn giảm, hồ sơ/thời hạn miễn giảm, học lại/cải thiện, thanh toán. | 12 |
| cuộc thi chính luận | Nội dung, thể loại, hạn nộp, giải thưởng Cuộc thi Chính luận 2026. | 12 |
| đánh giá rèn luyện | Khung điểm, tiêu chí cộng/trừ, xếp loại điểm rèn luyện. | 11 |
| khen thưởng sinh viên | Danh hiệu thi đua, tiêu chuẩn, mức thưởng, thẩm quyền cấp Trường. | 10 |
| thực tập tốt nghiệp | Thời gian TTTN, điều kiện Khóa luận, báo cáo, hội đồng chấm. | 9 |
| quy chế công tác sinh viên | Nghỉ học tạm thời, kỷ luật/nhập học lại, cố vấn học tập, vi phạm thi cử. | 6 |
| sinh viên 5 tốt | Tiêu chuẩn, hồ sơ xét danh hiệu SV5T và Giải thưởng Sao Tháng Giêng. | 6 |
| thực tập chuyên đề | Kế hoạch, tài liệu nghiệm thu, thủ tục tự liên hệ cơ sở. | 3 |
| khen thưởng cấp ĐHQG | Sinh viên Xuất sắc toàn khóa, mức thưởng cấp ĐHQG-HCM. | 2 |
| ký túc xá | Giờ giấc ra vào, thiết bị điện, kỷ luật nội trú. | 2 |
| tài chính sinh viên | Vay vốn học tập ACB: tài liệu, lãi suất, trả nợ. | 2 |
| bảo hiểm y tế | BHYT bắt buộc, VssID/VNeID. | 2 |
| hành chính sinh viên | Mẫu đơn xác nhận hoàn cảnh khó khăn, thẩm quyền xác nhận. | 1 |
| **Tổng** | | **100** |

*Nguồn: docs/spec/TAXONOMY.md mục A (đếm từ `benchmark_100_questions_v2.json`); phân bố giữ nguyên ở benchmark v3.*

### 3.3.2. 4 loại câu hỏi (`question_type`)

| Nhãn | Định nghĩa | Dấu hiệu nhận biết |
|---|---|---|
| `TRA_CUU` | tra một thông tin cụ thể nằm ở một văn bản | "là bao nhiêu / điều kiện nào / là gì"; trả lời từ 1–2 Điều |
| `SO_SANH` | so sánh, đối chiếu, tổng hợp nhiều điểm hoặc nhiều nguồn | "so sánh / khác nhau / điểm khác như thế nào"; cần ghép ≥ 2 nơi |
| `THU_TUC` | hỏi cách làm thủ tục, quy trình, hồ sơ từng bước | "thủ tục / cần giấy tờ gì / làm sao để / các bước" |
| `NGOAI_PHAM_VI` | ngoài quy chế học vụ AGU | không thể trả lời từ các văn bản trong corpus |

### 3.3.3. Luật phân giải xung đột

Thứ tự xét cố định, dừng ở điều kiện đầu tiên thỏa:

1. **`NGOAI_PHAM_VI` xét trước** — câu không thể trả lời từ corpus thì gán nhãn này, kể cả khi bề mặt trông giống tra cứu hoặc thủ tục.
2. **`SO_SANH`** — có từ dấu hiệu so sánh hoặc nội dung đòi hỏi ghép/đối chiếu nhiều điểm, nhiều mốc hoặc nhiều nguồn.
3. **`THU_TUC`** — hỏi các bước làm, hồ sơ, giấy tờ, nơi nộp/nơi xác nhận.
4. **`TRA_CUU`** — còn lại; câu lưỡng lự chọn `TRA_CUU` (bảo thủ).

Chú giải "ghép nhiều nơi": tính khi cần đối chiếu ≥ 2 Điều/Khoản, ≥ 2 văn bản, hoặc nhiều mốc/đối tượng. **Không** tính việc liệt kê nhiều thuộc tính của cùng một đối tượng (mã môn + tín chỉ + học kỳ của một môn) — trường hợp đó là `TRA_CUU`.

*Nguồn: docs/spec/TAXONOMY.md mục B, C, D.*

## 3.4. Thiết kế bộ phân loại (classifier)

Module `src/core/classifier.py`, dùng Qwen2.5-1.5B-Instruct qua Ollama (không dùng Gemini — không tốn quota), `temperature = 0.0`, tối đa 160 token output, timeout 20 giây (`CLASSIFIER_TIMEOUT`).

**Prompt few-shot cố định 16 ví dụ** chọn trước từ benchmark v3: đủ 14 chủ đề (mỗi chủ đề 1 câu) cộng 2 câu ngoài corpus; nhờ vậy mỗi loại hiếm `SO_SANH` / `THU_TUC` / `NGOAI_PHAM_VI` có 3 ví dụ, `TRA_CUU` có 7. Mỗi ví dụ kèm dòng "Dấu hiệu" giúp model bám quy tắc thay vì nhại đáp án. Khối quy tắc được nhắc lại ngay trước câu hỏi (tránh model nhỏ trôi về nhãn đa số).

**Guardrail 3 lớp — suy giảm mềm, pipeline không bao giờ chết vì classifier:**

```
Lớp 1: Qwen trả JSON hợp lệ + nhãn chuẩn → dùng luôn
       (topic chuẩn hóa không dấu qua fold(), chịu khác biệt dấu/hoa-thường)
Lớp 2: JSON lỗi hoặc nhãn lạ → bổ sung phần nhãn hỏng bằng bảng từ khóa
       (dấu hiệu theo docs/spec/TAXONOMY.md; từ khóa neo đặc thù xét trước từ khóa chung)
Lớp 3: từ khóa cũng không khớp → topic=None, question_type="TRA_CUU"
Ollama chết / timeout → trả thẳng kết quả lớp 3 kèm log cảnh báo
```

few-shot đóng băng làm phiên bản v1 — không tinh chỉnh thêm trên chính bộ 100 câu đo để tránh overfit.

*Nguồn: `src/core/classifier.py` (docstring module + hằng số FEW_SHOT_IDS); đặc tả `docs/architecture/SYSTEM_ARCHITECTURE.md` mục 6.1.*

## 3.5. Thiết kế router truy xuất theo lớp

Module `src/retrieval/router.py` — hàm thuần `get_retrieval_config(labels, base)`, không I/O, không gọi model.

**Nguyên tắc thiết kế: "mặc định = cấu hình hiện tại".** Cấu hình nền (`base`) đọc đúng các biến môi trường pipeline cũ đang dùng (`RAG_TOP_K`, `BM25_WEIGHT`, `CHROMA_WEIGHT`); nhãn chỉ điều chỉnh, không đổi bản chất pipeline. Không có nhãn (classifier tắt / lỗi / câu tự do) → trả nguyên `base`. Không bao giờ giảm top_k dưới giá trị gốc; không bao giờ trả trọng số tổng ≤ 0.

**Bảng điều chỉnh theo loại câu hỏi:**

| Loại | Điều chỉnh | Lý do |
|------|-----------|-------|
| `TRA_CUU` | giữ nguyên base | câu tra cứu đơn — cấu hình chung đã tối |
| `SO_SANH` | top_k + 2, bật `enable_subquery` | cần cửa sổ rộng để đối chiếu nhiều phía |
| `THU_TUC` | BM25 0.6 / Chroma 0.4 | thủ tục hay dùng từ khóa hành chính (giả thuyết ban đầu, hiệu chỉnh theo A/B) |
| `NGOAI_PHAM_VI` | giữ nguyên base — **không skip truy xuất** | precision nhãn này chỉ ~25%: skip = từ chối oan câu đúng |

**Bảng lọc nguồn theo chủ đề (`TOPIC_SOURCE_FILTER`)**: chỉ chủ đề có ≥ 5 câu trong benchmark VÀ ≥ 80% số câu in-corpus nằm gọn trong ≤ 2 nguồn mới được lọc — thiết kế phòng thủ vì lọc hẹp làm rơi căn cứ nằm ở văn bản phụ. Đạt ngưỡng: 8/14 chủ đề; 6 chủ đề còn lại (n = 1–3 câu) cố ý không lọc, suy giảm về cấu hình chung.

*Nguồn: `src/retrieval/router.py` (docstring module + hằng số); đặc tả `docs/architecture/SYSTEM_ARCHITECTURE.md` mục 6.2.*

## 3.6. Thiết kế thí nghiệm A/B

**Một biến duy nhất**: cờ `ENABLE_CLASSIFIER` (`0` = lượt WITHOUT, `1` = lượt WITH). Mọi tham số khác giữ nguyên giữa hai lượt:

| Tham số | Giá trị (cả 2 lượt) |
|---|---|
| Benchmark | `data/evaluation/benchmark_100_questions_v3.json` (100 câu) |
| top_k / retrieve_k | 6 / 6 |
| Generator | local-qwen (qwen2.5:1.5b-instruct) |
| Giám khảo Faithfulness | TẮT — Faithfulness chấm bằng heuristic local cùng công thức 2 nhánh |
| Truy xuất | True Hybrid Search (BM25 + ChromaDB, RRF c = 60) |

Lượt WITH đổi duy nhất hành vi ở 3 điểm (tất cả đều do tầng phân loại sinh ra): (1) router chọn top_k/trọng số/lọc nguồn theo nhãn; (2) câu `SO_SANH` được tách truy vấn con; (3) prompt generator có biến thể theo loại câu hỏi. Lượt WITHOUT chạy đúng đường đơn 5 tầng còn lại — chính là hành vi cũ của hệ thống.

Do cùng generator, cùng benchmark, cùng tham số, chênh lệch giữa hai lượt phản ánh đúng **gói thay đổi** của tầng phân loại + router, **không phải đóng góp riêng của từng thành phần**: lượt WITH bật đồng thời chọn tham số, thu hẹp nguồn, tách truy vấn con và prompt theo loại. Phép đo tách riêng trên vòng 811 item (V2, 27-10) cho thấy thu hẹp nguồn dạng **mềm** làm **mất 18 item** gold@6 so với all-off (518 vs 536; CI cụm [−4,62; −0,69] điểm %, p=2,77e−4) và chậm 2,76 s so với 0,18 s/item, còn dạng **cứng** (r0) chỉ đạt 363/700. Vì vậy kết quả A/B dưới đây là của cả gói, không dùng để biện minh cho lọc nguồn. Giám khảo Gemini tắt ở cả hai lượt (kịch bản offline 0 quota), nên cột Faithfulness là **heuristic local** — không so sánh trực tiếp với baseline Gemini cũ, nhưng A/B nội bộ vẫn công bằng vì hai lượt dùng cùng công thức chấm.

*Nguồn: `outputs/ab_results_without_classifier.json` + `outputs/ab_results_with_classifier.json` → khối `meta` (hai lượt chỉ khác `with_classifier`); docs/planning/ROADMAP.md mục 4.*
