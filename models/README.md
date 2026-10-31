# Các mô hình đã train từ bộ dữ liệu đồ án

Thư mục này chứa kết quả train độc lập với pipeline RAG hiện tại. Các file `.joblib`
dùng cho CPU/sklearn; adapter Qwen dùng `venv_train` và PEFT.

## 1. Classifier câu hỏi

| Model | Script | Artifact | Kết quả chính |
|---|---|---|---|
| v1: TF-IDF train template | `tools/train/train_classifier_baseline.py` | `models/classifier_baseline/` | Topic gold 80.3%; question_type gold 18.8% — baseline dưới chuẩn |
| v2: bỏ prefix + dùng gold seed | `tools/train/train_classifier_v2.py` | `models/classifier_baseline_v2/` | Topic CV 98.6% acc / 96.1 macro-F1; question_type CV 95.9% acc / 74.4 macro-F1 |
| v3: thử oversample lớp hiếm | `tools/train/train_classifier_v3_rare.py` | `models/classifier_baseline_v3/` | Kết luận phủ định: oversample factor 2/4 làm giảm macro-F1 (0.744 → 0.718/0.690); best vẫn là factor 1, C=4, soft weights — ngang v2 |

Bản deploy khuyến nghị: **v2**. v3 chỉ là experiment chứng minh duplicate oversample
không giải quyết được bài toán thiếu dữ liệu lớp hiếm (THU_TUC recall vẫn 20% vì chỉ
5 seed; hướng đúng là thu thêm câu hỏi tay cho các lớp hiếm).

Lưu ý công bằng: v2 dùng `classifier_benchmark_seed.jsonl` trong quá trình chọn siêu
tham số và train cuối, vì vậy kết quả trên seed **không phải held-out hoàn toàn độc
lập**. Muốn so sánh với Qwen 85%/81%, cần thêm một tập câu hỏi tay chưa từng dùng.

## 2. Retrieval baseline

Script: `tools/train/train_retrieval_baseline.py`
Artifact: `models/retrieval_baseline/`

Mô hình:
- BM25 tham số `k1`, `b` chọn trên train split;
- TF-IDF word và char_wb cosine;
- Logistic fusion học từ hard negatives.

Kết quả test trên 358 candidate doc:

| Model | Hit@1 | Hit@3 | Hit@5 | MRR |
|---|---:|---:|---:|---:|
| BM25 | 25.3% | 39.6% | 46.9% | 0.356 |
| TF-IDF word | 29.7% | 46.9% | 52.7% | 0.415 |
| TF-IDF char | 13.2% | 24.9% | 33.0% | 0.228 |
| Fusion learned | 32.6% | 48.7% | 54.6% | 0.433 |

Fusion tốt hơn lexical đơn kênh, nhưng corpus nhỏ và phần lớn query là bronze OCR;
đây là baseline để so tiếp, không phải model production.

## 3. SFT chat model (đã train xong 23-10)

Script: `tools/train/train_sft_lora.py`
Môi trường: `venv_train` (PyTorch CUDA 12.6 + PEFT + Transformers).
Artifact: `models/qwen25_05b_sft_adapter/` (adapter LoRA ~35MB, an toàn VRAM 4GB).

Lệnh đã chạy thành công (2 epoch, 1635 mẫu train / 50 val, ~17 phút 49 giây).
`--max-length 768` là bắt buộc — `1024` gây CUDA OOM ở step 24 trên RTX 3050 4GB;
phân phối token thật: median 161, p99 626, max 894):

```bash
PYTHONIOENCODING=utf-8 HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
./venv_train/Scripts/python.exe tools/train/train_sft_lora.py \
  --epochs 2 --max-length 768 --output-dir models/qwen25_05b_sft_adapter
```

Đường loss: 3.02 (step 10) → train_loss trung bình 1.713; eval_loss 1.311 (epoch 1)
→ 1.230 (epoch 2), không có dấu hiệu overfit. Chi tiết trong
`models/qwen25_05b_sft_adapter/training_metrics.json`.

Đánh giá sinh văn bản (`tools/train/evaluate_sft_adapter.py`, output mẫu ở
`sample_generation.json`): adapter học đúng **định dạng** trả lời — mở đầu theo kiểu
tài liệu, kèm `Nguồn: ...`, kiểu `- hàm \`...\` — dòng N`. Nhưng **nội dung cụ thể là
bịa** (số dòng sai, tên lớp test không tồn tại) vì 0.5B không được nạp tri thức corpus.
Đây chính là lý do đồ án cần RAG: SFT local chỉ hợp để chuẩn hoá phong cách/trả lời
ngắn, còn câu hỏi miền phải qua truy xuất + guardrail số liệu.

> **Bố cục từ 26-10 (dọn repo B3):** mã train/eval nằm ở `tools/train/`; `models/` chỉ còn **artifact** (adapter LoRA, joblib, npz, báo cáo train) — xem `ARTIFACT_MANIFEST.json` ở gốc repo. Các ghi chú lịch sử trong `docs/reports/`, `docs/AUTONOMY_LOG.md` và comment trong `tools/diag/` vẫn giữ đường dẫn cũ `models/…` vì là bản ghi tại thời điểm đó.

## Vòng đời artifact (REVIEW §10)

| Câu hỏi | Trả lời |
|---|---|
| **Nguồn tạo** | `tools/train/*` — mỗi thư mục con có script tương ứng ở bảng §1/§2/§3 |
| **Xoá được không** | Được, về kỹ thuật — nhưng phải train lại (tốn GPU) và mọi số trong bảng trên mất nền. Coi như **không xoá** khi chưa có quyết định |
| **Lệnh tái tạo** | Lệnh từng model nằm ngay trong các mục §1–§3 ở trên |
| **Dùng trong runtime?** | **Không.** Pipeline trả lời bằng `BAAI/bge-m3` (embedding) + Ollama/Qwen + Gemini; adapter LoRA và các model `.joblib` chỉ phục vụ thí nghiệm/báo cáo |
| **Git** | `models/*` bị ignore (PA-33); byte vẫn được `ARTIFACT_MANIFEST.json` theo dõi. Duy nhất `models/README.md` được track |

Bảng vòng đời cho toàn bộ repo: `docs/REPO_LAYOUT.md` §2.
