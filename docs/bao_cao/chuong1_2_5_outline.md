# Outline chương 1, 2, 5 (bản nháp P5.3)

> Outline + gợi ý từ khóa tra cứu. Chương 3–4 là bản nháp đầy đủ trong cùng thư
> mục này (`chuong3_kien_truc.md`, `chuong4_thuc_nghiem.md`).

---

## Chương 1 — Tổng quan đề tài

### 1.1. Đặt vấn đề
- Sinh viên hỏi quy chế đào tạo bằng ngôn ngữ tự nhiên (viết tắt, tiếng lóng: "điểm yếu", "đuổi học", "ad ơi") — tra cứu thủ công trong hàng chục văn bản PDF/DOCX mất thời gian.
- Chatbot Q&A thông thường có khuynh hướng bịa câu trả lời (ảo giác) khi không có căn cứ — nguy hiểm với văn bản hành chính.
- Một cấu hình truy xuất chung cho mọi kiểu câu hỏi làm nhóm câu khó (so sánh nhiều vế, câu cần căn cứ từ đúng văn bản) trả kết quả kém.

### 1.2. Mục tiêu
- Xây hệ thống RAG tra cứu quy chế đào tạo ĐHAG: trả lời có trích dẫn (Điều/Khoản — văn bản), từ chối an toàn khi không đủ căn cứ.
- **Đề tài mới**: bổ sung tầng phân loại câu hỏi 2 nhãn (chủ đề + loại) và router truy xuất theo lớp, đánh giá A/B có/không có tầng này.

### 1.3. Câu hỏi nghiên cứu
(điền thẳng 3 câu hỏi từ `chuong3_kien_truc.md` mục 3.1.1 — nguồn ROADMAP.md mục 2)

### 1.4. Phạm vi và đối tượng
- Trong phạm vi: 26 văn bản quy chế học vụ AGU (3 tầng corpus), benchmark 100 câu v3, generator Qwen local/Gemini, không fine-tune embedding, không đổi vector DB. (nguồn: ROADMAP.md mục 4, 5)
- Ngoài phạm vi: OCR chất lượng cao, mở rộng corpus ngoài học vụ, train mới embedding. (nguồn: ROADMAP.md mục 5)

### 1.5. Đóng góp của đề tài
- Bộ phân loại 2 nhãn chạy offline (0 quota cloud) với guardrail suy giảm mềm.
- Router cấu hình truy xuất theo lớp + tách truy vấn con cho câu so sánh.
- Khung đánh giá A/B một biến trên benchmark có nhãn question_type.

### 1.6. Bố cục đồ án

---

## Chương 2 — Cơ sở lý thuyết

> **Chưa điền trích dẫn** — mỗi mục dưới đây chỉ là GỢI Ý TỪ KHÓA tra cứu.
> Người viết tự tìm và xác minh nguồn thật (ưu tiên: bài báo gốc, survey có peer-review
> hoặc preprint arXiv lớn, tài liệu chính thức của thư viện) rồi điền vào chỗ trống.
> KHÔNG dùng trích dẫn do AI sinh ra mà chưa tự mở kiểm tra.

### 2.1. Retrieval-Augmented Generation (RAG)
- Khái niệm: kết hợp truy xuất tài liệu với sinh câu trả lời; vì sao giảm ảo giác.
- 📚 Từ khóa tra cứu: `RAG survey`, `retrieval-augmented generation Lewis 2020`, `RAG vs fine-tuning`.
- ✍️ Điền trích dẫn: ________________

### 2.2. Hybrid retrieval: BM25 + vector search + RRF
- BM25 (mô hình xác suất, tham số k1/b); embedding đa ngôn ngữ; Reciprocal Rank Fusion công thức `Σ k/(rank+k)`.
- 📚 Từ khóa: `BM25 Robertson Zaragoza probabilistic relevance framework`, `reciprocal rank fusion Cormack 2009`, `BGE-M3 embedding multi-functionality`, `hybrid search dense sparse fusion`.
- ✍️ Điền trích dẫn: ________________

### 2.3. Phân loại ý định câu hỏi (intent classification)
- Few-shot prompting với LLM nhỏ; zero-shot vs few-shot; nhãn lệch lớp (class imbalance) và tại sao phải đo per-class recall.
- 📚 Từ khóa: `few-shot prompting GPT-3 Brown 2020`, `intent classification chatbot`, `class imbalance evaluation macro-F1`.
- ✍️ Điền trích dẫn: ________________

### 2.4. Query routing và adaptive retrieval
- Chọn cấu hình truy xuất theo đặc điểm truy vấn (routing); adaptive retrieval quyết định có/không truy xuất.
- 📚 Từ khóa: `adaptive retrieval-augmented generation`, `query routing RAG`, `intent-aware retrieval`.
- ✍️ Điền trích dẫn: ________________

### 2.5. Đo lường chất lượng RAG
- Hit@K, MRR, Citation Precision/Recall/F1, Faithfulness, LLM-as-a-judge và hạn chế; ảo giác trong LLM.
- 📚 Từ khóa: `RAG evaluation metrics RAGAS`, `hallucination survey LLM`, `LLM-as-a-judge evaluation`.
- ✍️ Điền trích dẫn: ________________

### 2.6. Mô hình ngôn ngữ nhỏ chạy cục bộ (SLM) và Ollama
- Đánh đổi chất lượng/quyền riêng tư/chi phí; quantization; chạy local.
- 📚 Từ khóa: `small language model survey`, `Qwen2.5 technical report`, `Ollama local LLM runtime`.
- ✍️ Điền trích dẫn: ________________

---

## Chương 5 — Kết luận và hướng phát triển

### 5.1. Kết luận (trả lời 3 câu hỏi nghiên cứu — số chép từ chương 4)
1. Bộ phân loại 2 nhãn: topic **85,0%**, question_type **81,0%**, recall lớp hiếm 100% — đạt cổng thiết kế. (nguồn: `logs/classifier/accuracy_report.md`)
2. Gói thay đổi của lượt WITH (router chọn tham số + thu hẹp nguồn, tách truy vấn con, prompt theo loại) cải thiện rõ nhất nhóm TRA_CUU (Hit@3 58,6% → 77,0%); nhóm SO_SANH tăng MRR 0,4333 → 0,8286 nhờ tách truy vấn con; nhóm chủ đề tăng mạnh: chương trình đào tạo +45,5 pp, khen thưởng sinh viên +40,0 pp. **Không quy riêng cho lọc nguồn**: phép đo tách riêng trên 811 item (V2, 27-10) cho lọc mềm **−18 item** so all-off (CI cụm [−4,62; −0,69] điểm %, p=2,77e−4). (nguồn: `outputs/ab_comparison.md` mục 2, 3; `tmp/v2_rescore.json`)
3. Bật tầng phân loại tốt hơn trên tổng thể **trong gói thay đổi đó**: Hit@3 +27,1% tương đối, MRR +50,9% tương đối, GATE ĐẠT (ngưỡng −5%); giá phải trả: +3 câu từ chối oan trên nền ~50% sẵn có, number support −3,05 pp. (nguồn: `outputs/ab_comparison.md` mục 1, 5, 8)

### 5.2. Hạn chế
(tóm tắt 5 mục hạn chế từ `chuong4_thuc_nghiem.md` mục 4.4.3: latency tham chiếu, NGOAI precision 25%, nhóm n nhỏ, faithfulness heuristic, từ chối đúng 33,3%)

### 5.3. Hướng phát triển
- **Active learning cho classifier**: thu thập câu hỏi thật từ log hệ thống, bổ sung neo âm (biên mơ TTTN-vs-CTĐT, SV Giỏi-vs-SV5T) vào few-shot/bảng từ khóa — cải thiện precision lớp hiếm thay vì tinh chỉnh trên chính bộ đo. (nguồn: `logs/classifier/accuracy_report.md` mục "Hướng cải thiện")
- **Tách đóng góp của lọc nguồn (`source_filter`) trước khi mở rộng**: phép đo 811 item (V2, 27-10) cho thấy lọc mềm **−18 item** so với all-off, còn lọc cứng mất 244/244 item nguồn-sai ⇒ hướng đúng là đo ablation từng thành phần (router tham số / thu hẹp nguồn / tách truy vấn con), không bật thêm lọc. Hiện chỉ 8/14 chủ đề đủ bằng chứng ngưỡng (n ≥ 5, ≥ 80% trong ≤ 2 nguồn). (nguồn: `tmp/v2_rescore.json`, `src/router.py` docstring)
- **A/B theo tuần**: tái chạy 2 lượt 100 câu định kỳ sau mỗi lần thay đổi (prompt, guardrail, corpus) để phát hiện hồi quy sớm; chuẩn hóa kịch bản offline (generator Qwen + heuristic faithfulness) đã dùng ở P4.2 để 0 quota.
- *(mở rộng, tùy hướng dẫn viên)*: nâng generator (Gemini hoặc Qwen lớn hơn) để giảm nền ~50% từ chối oan; LLM judge bật lại khi có quota để đo faithfulness đầy đủ.

---

## Checklist trước khi nộp (người viết tự chạy)
- [ ] Điền trích dẫn thật chương 2 (mở từng nguồn kiểm tra — không tin AI)
- [ ] Đối chiếu lại mỗi số trong chương 4 với file nguồn ghi chú dưới bảng
- [ ] Render markdown (VS Code preview / Typora): bảng + 3 ảnh `../../outputs/figures/*.png` hiển thị
- [ ] Đánh số chương/bảng/hình theo quy định của khoa
- [ ] Cập nhật README cuối (P5.4) dẫn tới `docs/bao_cao/`
