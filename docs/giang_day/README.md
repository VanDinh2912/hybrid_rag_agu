# Giáo trình đọc hiểu đồ án — Hybrid RAG tra cứu quy chế AGU

Bộ tài liệu này dạy **từng chức năng, từng tầng** của đồ án, theo cách một người
phải bảo vệ đồ án trước hội đồng cần hiểu: không chỉ “chạy được”, mà biết **vì sao
thiết kế như vậy, hỏng ở đâu, đo bằng gì và con số nào chứng minh**.

Mỗi chương đều có bốn phần cố định:

1. **Mục tiêu** — học xong phải trả lời được câu gì.
2. **Bản đồ mã nguồn** — hàm nào, dòng nào, vào/ra ra sao.
3. **Giải thích cơ chế** — kèm ví dụ chạy được và phản ví dụ.
4. **Bài tập + câu hỏi bảo vệ** — tự kiểm tra, không cần máy vẫn làm được.

> **Quy ước số dòng.** Số dòng đúng tại thời điểm soạn (2026-10-23). Khi sửa mã,
> dùng tên hàm để tìm lại — đừng tin số dòng tuyệt đối. Mọi lệnh chạy trên Windows
> dùng `./venv/Scripts/python.exe`; thêm `PYTHONIOENCODING=utf-8` khi in tiếng Việt
> ra console.

---

## Danh sách chương

| # | Chương | Nội dung chính | Thời lượng gợi ý |
|---|---|---|---|
| 00 | [Lộ trình học](00_lo_trinh_hoc.md) | Bản đồ repo, cách đọc, lịch 14 ngày | 1 buổi |
| 01 | [Tổng quan kiến trúc](01_tong_quan_kien_truc.md) | Bài toán, luồng đầu-cuối, oversampling, suy giảm mềm | 1 buổi |
| 02 | [Dữ liệu & nạp corpus](02_du_lieu_va_nap_corpus.md) | Loader, OCR, chunking production và 3 chiến lược thực nghiệm | 2 buổi |
| 03 | [Truy xuất Hybrid](03_truy_xuat_hybrid.md) | `fold`, BM25, bge-m3, RRF, sub-query, hợp nhất nhánh | 2 buổi |
| 04 | [Chuẩn hóa & phân loại](04_chuan_hoa_va_classifier.md) | Qwen viết lại câu, guardrail, 14 chủ đề × 4 loại | 2 buổi |
| 05 | [Router truy xuất](05_router.md) | Ánh xạ nhãn → cấu hình, lọc nguồn, A/B | 1 buổi |
| 06 | [Generator & chống ảo giác](06_generator_va_chong_ao_giac.md) | Prompt, cache, quota, fallback, trích dẫn | 2 buổi |
| 07 | [Pipeline đầu-cuối](07_pipeline_end_to_end.md) | `run()`, CLI, `scripts/learn.py`, xử lý lỗi | 1 buổi |
| 08 | [Đánh giá & thực nghiệm](08_danh_gia.md) | Hit@K, MRR, Citation, Faithfulness, A/B | 2 buổi |
| 09 | [Ứng dụng giao diện](09_ung_dung_giao_dien.md) | Streamlit, so sánh 3 chiến lược chunking | 1 buổi |
| 10 | [Bài học & bảo vệ](10_bai_hoc_va_ky_nang.md) | Giới hạn, thiết kế đánh đổi, Q&A hội đồng | 1 buổi |
| — | [Phụ lục hàm](PHU_LUC_ham.md) | Mục lục toàn bộ hàm/class theo module | Tra cứu |
| — | [Bài tập & đáp án](BAI_TAP_VA_DAP_AN.md) | 40 bài tập phân tầng + đáp án | Xuyên suốt |

---

## Ba vòng đọc repo (đừng đọc tuần tự từ đầu)

**Vòng 1 — chạy được (2 giờ).** Đọc `README.md`, chạy `ingest.py`, hỏi 3 câu bằng
`main.py`. Mục tiêu: thấy dữ liệu vào và câu trả lời ra.

**Vòng 2 — hiểu luồng (2 ngày).** Đọc `01` → `07` theo đúng thứ tự dữ liệu chảy:
loader → chunking → vector DB → chuẩn hóa → phân loại/router → truy xuất → sinh.
Mỗi chương mở file nguồn tương ứng và đọc **toàn bộ** file, không chỉ hàm chính.

**Vòng 3 — bảo vệ (2 ngày).** Đọc `08` (số liệu), `10` (giới hạn), làm bài tập
nhóm C (phản biện). Mục tiêu: mỗi con số trong báo cáo chỉ được đúng file JSON
sinh ra nó.

---

## Cấu trúc repo bằng một cái nhìn

```
hybrid_rag_agu/
├── data/
│   ├── corpus/                 # PDF/DOCX/TXT quy chế, chia Tầng 1 / Tầng 2
│   ├── evaluation/             # benchmark 100 câu v3, benchmark 50 câu chunking
│   ├── normalization_pairs.json# cặp câu thô → câu chuẩn (active learning)
│   └── training/               # dataset SFT/classifier/retrieval đã sinh
├── src/
│   ├── text_utils.py           # fold() — chuẩn hóa dấu dùng chung
│   ├── loader.py               # đọc file + OCR PDF scan + cache
│   ├── chunking.py             # chunk production + 3 chiến lược thực nghiệm
│   ├── vector_db.py            # bge-m3 + ChromaDB + BM25
│   ├── local_slm.py            # Qwen viết lại câu + guardrail
│   ├── query_normalizer.py     # chuẩn hóa few-shot + active learning
│   ├── classifier.py           # 14 chủ đề × 4 loại câu hỏi
│   ├── router.py               # nhãn → cấu hình truy xuất
│   ├── retrieval.py            # mở rộng từ đồng nghĩa, tách truy vấn con
│   ├── pipeline.py             # điều phối toàn bộ lượt hỏi
│   ├── generator.py            # Gemini + Qwen fallback + cache + trích dẫn
│   ├── evaluation.py           # metrics, judge, resume, báo cáo
│   ├── evaluate_classifier.py  # đo accuracy classifier + baseline kNN
│   ├── analyze_ab.py           # so sánh WITH/WITHOUT + biểu đồ
│   └── faithfulness_heuristic.py # chấm trung thực không cần API
├── main.py                     # CLI hỏi đáp
├── ingest.py                   # nạp corpus → ChromaDB
├── scripts/learn.py                    # chế độ test & học có trọng tài
├── scripts/benchmark_chunking.py       # thực nghiệm 3 chiến lược chunking
├── ui/demo_streamlit.py           # UI so sánh 3 chiến lược
├── tools/                      # sinh & kiểm định dataset huấn luyện
├── outputs/                    # kết quả đánh giá (JSON + Markdown + hình)
└── logs/                       # log classifier, benchmark chunking
```

---

## Cách dùng bộ dữ liệu huấn luyện kèm giáo trình

Giáo trình là **phần hiểu**; dataset là **phần luyện**. Hai thứ bổ sung nhau:

- Học chương nào, mở `data/training/preview.md` xem mẫu tương ứng (mã nguồn, corpus,
  classifier, retrieval) để thấy kiến thức vừa học được biểu diễn thành cặp hỏi–đáp.
- Nếu fine-tune một SLM nhỏ: dùng `tools/train/build_training_data.py` để tái sinh sau khi
  sửa code, **không** trộn `sft_benchmark_seed.jsonl` vào train khi vẫn dùng benchmark
  để đánh giá (rò rỉ).
- Xem [README dataset](../../data/training/README.md) để biết schema, phân tầng
  gold/silver/bronze, cảnh báo OCR và gợi ý siêu tham số.

---

## Bốn nguyên tắc xuyên suốt đồ án

1. **Không tầng nào được làm chết lượt hỏi.** Qwen chết → dùng câu gốc; classifier
   lỗi → cấu hình nền; Gemini hết quota → Qwen fallback; hết cả hai → `GeneratorError`
   được CLI bắt. Đây là “suy giảm mềm” (graceful degradation), không phải che lỗi.
2. **Mọi so khớp văn bản đi qua `fold()`.** Tầng 1 OCR mất dấu; nếu so có dấu sẽ
   trượt toàn bộ. `fold()` là nguồn chân lý duy nhất.
3. **Đo trên cửa sổ truy xuất, trả lời trên cửa sổ ngữ cảnh.** Theo thiết kế,
   `retrieve_k = 2 × effective_top_k` để đo Hit công bằng; generator chỉ nhận
   `effective_top_k` để prompt không phình. Lưu ý: evaluation hiện truyền nhầm
   `retrieve_k` vào `top_k` (Chương 08, §6), nên cửa sổ thực của lượt A/B là 12/6
   (SO_SANH 16/8), không phải 6/6 như metadata khai báo.
4. **Mỗi con số phải truy được về file sinh ra nó.** Benchmark → JSON → bảng Markdown.
   Không có “em nhớ là khoảng 80%”.

---

## Ký hiệu dùng trong giáo trình

| Ký hiệu | Nghĩa |
|---|---|
| `P3.2`, `P4.3` | Mã giai đoạn trong kế hoạch làm đồ án (xem `docs/planning/ROADMAP.md`) |
| ✅ / ❌ | Hành vi đúng / phản ví dụ cần tránh |
| 🔁 | Điểm có thể chạy lại để tự kiểm chứng |
| ⚠️ | Giới hạn đã biết — phải nói khi bảo vệ |
| `→` | Luồng dữ liệu |

Bắt đầu tại [00 — Lộ trình học](00_lo_trinh_hoc.md).
