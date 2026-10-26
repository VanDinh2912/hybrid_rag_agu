# Kiến trúc hệ thống — bản đồ đọc nhanh

Hệ trả lời câu hỏi học vụ của Trường Đại học An Giang **chỉ từ ngữ cảnh truy xuất được**:
không dùng kiến thức nền, không bịa số hiệu Điều/Khoản, thiếu căn cứ thì từ chối. Đặc tả chi tiết
6 tầng nằm ở [README.md §1](../README.md); tài liệu này là bản đồ module và các bất biến vận hành
cần nhớ trước khi sửa mã.

## Luồng chạy

```
Câu hỏi thô
  → [0] phân loại 2 nhãn + router            (chỉ khi ENABLE_CLASSIFIER=1)
  → [1] chuẩn hóa câu hỏi bằng Qwen/Ollama   (guardrail chống lệch nghĩa)
  → [2] mở rộng truy vấn (từ điển đồng nghĩa)
  → [3] tách truy vấn con                    (chỉ câu SO_SANH, tối đa 3 nhánh)
  → [4] True Hybrid Search: BM25 + ChromaDB (bge-m3), gộp RRF
  → [5] sinh câu trả lời Gemini/Qwen + Soft Refusal
```

Hai cơ chế xuyên suốt: `fold()` bỏ dấu thanh dùng chung cho truy xuất/đánh giá; oversampling lấy
`top_k × 2` ứng viên, chỉ `top_k` đầu vào generator, phần còn lại để đo Hit@K.

## Bản đồ module

| Nhóm | Tệp | Trách nhiệm |
|---|---|---|
| Nạp dữ liệu | `ingest.py`, `src/loader.py`, `src/chunking.py`, `src/vector_db.py` | đọc PDF/DOCX + OCR, cắt chunk theo tầng/Điều, nhúng bge-m3, dựng Chroma + BM25 |
| Hiểu câu hỏi | `src/query_normalizer.py`, `src/local_slm.py`, `src/classifier.py`, `src/router.py`, `src/retrieval.py` | chuẩn hóa, phân loại, router cấu hình truy xuất, mở rộng/tách truy vấn |
| Sinh câu trả lời | `src/generator.py`, `src/cache_policy.py` | prompt theo loại câu hỏi, Gemini + cache, fallback Qwen, Soft Refusal; khóa cache theo chính sách |
| Chống ảo giác | `src/answer_guard.py`, `src/refusal_policy.py`, `src/faithfulness_heuristic.py`, `src/text_utils.py` | kiểm căn cứ/theo dõi từ chối, heuristic trung thực, `fold()` |
| Cấu hình | `src/config.py` | điểm đọc env đã gom cho 9 module, cache theo ảnh chụp env |
| Đánh giá tĩnh | `src/evaluation.py`, `src/evaluate_classifier.py`, `src/analyze_ab.py` | Hit@K/MRR, Citation, Faithfulness, accuracy classifier, A/B |
| Vòng lặp đo | `tools/loop/` | testset 811 item, trọng tài deterministic, cổng, quy lỗi theo tầng |
| Giao diện | `main.py`, `ui/app.py`, `demo_streamlit.py` | CLI, GUI Tkinter 3 tab, demo so sánh 3 chiến lược |

## Hai đường đo

- **Đánh giá tĩnh** (`src/evaluation.py`): chạy đúng pipeline sản xuất trên benchmark có ground
  truth; đo Hit@K, MRR, Citation P/R/F1, Faithfulness (giám khảo Gemini) và độ bảo toàn thực thể
  sau chuẩn hóa.
- **Vòng lặp tự kiểm chứng** (`tools/loop/`): bộ đo cố định `data/loop/testset_v1.jsonl` — 811
  item, 700 item có chunk vàng; trọng tài deterministic (`tools/loop/verify.py`), cổng
  (`gate.py`) và quy lỗi theo tầng (`attribute.py`). Round gốc ở `data/loop/rounds/`; bản chấm
  lại bằng trọng tài v2 ở `data/loop/rounds_v2/`. Quy ước từng round: `data/loop/README.md`.

## Bất biến vận hành

1. **Chữ ký trọng tài.** `referee_fingerprint()` = 12 hex đầu SHA-256 trên byte thô của
   `tools/loop/verify.py`, `src/answer_guard.py`, `src/text_utils.py`. Hiện tại
   **`2911c69f740d`** (trọng tài v2, áp PA-2 + PA-20). Đổi bất kỳ tệp nào trong ba tệp này ⇒ phải
   chấm lại **mọi** round; không sửa tệp trọng tài trong một bước dọn cấu trúc.
2. **Cờ TẮT = hành vi cũ.** Các lever thử nghiệm (`ENABLE_RERANKER`, `ENABLE_ANSWER_RESCUE`,
   `ENABLE_EVIDENCE_SELECTION`, `ENABLE_CONTEXTUAL_HEADER`, `ENABLE_DECOUPLED_REFUSAL`,
   `NORMALIZE_SANITY_GUARD`) mặc định TẮT; khi TẮT phải cho đầu ra byte-identical với thể chế cũ.
   `ENABLE_CLASSIFIER` cũng mặc định `0`.
3. **Ngưỡng đăng ký trước không chỉnh sau khi thấy số.** Số âm ghi nguyên; muốn cứu số phải mở
   round mới, không hạ ngưỡng.
4. **Một biến mỗi round.** Round đã đóng là bất biến; so sánh phải chỉ ra đúng một biến khác.
5. **Artifact là nguồn.** Tài liệu lệch artifact ⇒ sửa tài liệu, không sửa artifact.
6. **Không ghi đè artifact đã công bố.** Lượt đo mới ghi tên mới.
7. **Máy kiểm chỉ sửa qua đề xuất** (`docs/DECISION_LOG.md`, `docs/archive/PENDING_APPROVAL.md`),
   kèm đột biến chứng minh test bắt được thay đổi.

## Cấu hình

`src/config.py` gom env cho **9 module** (contextual_header, evidence_selection, refusal_policy,
retrieval, loader, vector_db, local_slm, classifier, chunking), cache theo ảnh chụp env và giữ
nguyên ngữ nghĩa parse của từng site cũ. Bốn module đóng băng PA-26 (`generator`, `pipeline`,
`query_normalizer`, `router`) và ba tệp nhạy cảm (`answer_guard` — file trọng tài, `evaluation` —
runner đo, `reranker`) vẫn đọc env trực tiếp; gom nốt là PA-44.

## Dữ liệu và index

- `data/corpus/` — 26 tài liệu (21 PDF + 5 DOCX) ở 3 tầng.
- `chroma_db/` — index sản xuất (361 chunk) do `ingest.py` dựng.
- `chroma_db_vie/` — index re-OCR tiếng Việt (342 chunk): chất lượng dấu tốt hơn nhưng **chưa
  kích hoạt** vì mất neo vàng 389/797 = 48,81% (PA-17 re-anchor).
- `data/loop/testset_v1.jsonl` — bộ đo 811 item cố định dùng cho mọi round.

## Ghi chú phạm vi

`src/generator.py` chứa prompts + chính sách từ chối + lớp rescue đã bị bác; đề xuất tách đang
chờ duyệt ở PA-46 (chưa làm vì PA-26 đóng băng tệp). `src/evaluation.py`, `src/analyze_ab.py`,
`src/evaluate_classifier.py` được đề xuất giữ nguyên trong `src/` (PA-45).
