# Thư mục `logs/` — nơi duy nhất chứa mọi log tự sinh khi chạy

Quy ước của repo: script **không** ghi log/output lẻ tẻ ra thư mục gốc hay chỗ khác —
mọi file tự sinh khi chạy phải nằm trong `logs/`, chia sẵn theo đúng ý nghĩa:

| Thư mục | Sinh ra bởi | Ý nghĩa | Xóa được không |
|---|---|---|---|
| `benchmark/` | `scripts/benchmark_chunking.py` | Log benchmark 3 chiến lược chunking: `log_*.txt`, `results_all.json`, `summary_comparison_report.csv/.md`, chỉ mục tạm `chroma_*/` | ✅ Xóa được — chạy lại script là có lại |
| `classifier/` | `src/assessment/evaluate_classifier.py` | Đo accuracy tầng phân loại (P2.3): `accuracy_report.md`, 2 ma trận nhầm lẫn CSV, `results.json` (100 câu v3, Qwen local) | ✅ Xóa được — chạy lại script là có lại |
| `export/` | `scripts/export_architecture.py` | Biên nhận lần xuất `SYSTEM_ARCHITECTURE` sang .txt/.docx | ✅ Xóa được — chạy lại là có lại |
| `learning/` | `scripts/learn.py` và GUI Tab 3 | `learning_log.csv` — lịch sử mỗi lần hệ thống trả lời sai và được "học thêm" | ❌ **KHÔNG xóa** — là lịch sử dữ liệu |
| `feedback/` | GUI (Tab "Vừa test vừa học") | `user_feedback.json` — toàn bộ lượt đánh giá đúng/sai của người dùng | ❌ **KHÔNG xóa** — là dữ liệu phản hồi |

Ranh giới với các thư mục khác trong repo:

- `outputs/` — kết quả **chốt** dùng cho báo cáo (được track git):
  `evaluation_results.json`, `evaluation_summary.md`.
- `chroma_db/`, `.ocr_cache/`, `.generation_cache/` — cache nội bộ (gitignored),
  không phải log; xóa là phải ingest/OCR lại từ đầu.

Quy tắc `.gitignore`: `logs/*` bị ignore trừ `README.md` này, `learning/` và `feedback/`
(hai thư mục dữ liệu lịch sử được track để không bao giờ mất khi dọn dẹp).
