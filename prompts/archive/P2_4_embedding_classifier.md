# P2.4 — (Tùy chọn) Baseline phân loại bằng embedding bge-m3

> Giai đoạn 2 · Nhóm playbook: 04 · Thời gian: 1 ngày · Không chặn lộ trình

Đọc trước `prompts/00_base_context.md`, sau đó thực hiện đúng phạm vi dưới đây.

## Mục tiêu

Một phương pháp đơn giản (kNN trên embedding) làm baseline đối chứng — chương thực nghiệm sẽ chứng minh được vì sao cần LLM cho nhiệm vụ phân loại.

## Ngữ cảnh cần đọc trước

- `src/vector_db.py` — cách nạp model bge-m3 hiện có (tái dùng loader).
- `src/evaluate_classifier.py` (P2.3) — thêm chế độ vào script này.

## Việc cần làm

1. Thêm cờ `--method embedding` vào `src/evaluate_classifier.py`:
   - Encode 100 câu `raw_query` của v3 bằng bge-m3 (tái dùng loader hiện có trong `vector_db.py`).
   - Dự đoán leave-one-out kNN (k = 1, 3, 5) cho cả 2 nhãn: chủ đề (so với `category`) và loại câu hỏi (so với `question_type`).
2. Xuất thêm vào `accuracy_report.md` bảng so sánh 2 phương pháp: Qwen few-shot vs kNN (k=1/3/5) — accuracy từng nhãn + thời gian trung bình mỗi câu.
3. KHÔNG đụng code production (`src/classifier.py` giữ nguyên).

## Ràng buộc

- Nhóm 04. Offline hoàn toàn (bge-m3 chạy CPU như thiết kế repo).
- kNN chỉ là script đánh giá — không đưa vào pipeline, không thêm dependency mới.

## Sản phẩm

- `src/evaluate_classifier.py` mở rộng cờ `--method embedding`
- `logs/classifier/accuracy_report.md` thêm bảng so sánh

## Verify (bắt buộc)

- Bảng so sánh đủ số cho cả 2 nhãn × 2 phương pháp; nguồn số truy được về `results.json` (giữ thêm kết quả kNN vào results.json hoặc file riêng `results_knn.json`).
- `venv\Scripts\python.exe -m pytest` toàn bộ vẫn xanh (script sửa không phá import chung).

## Ghi chú

- Nếu P2.3 đã đạt gate, nhiệm vụ này vẫn NÊN làm — 30 phút chạy + 1 bảng, giá trị cho chương thực nghiệm cao (trả lời trước câu hỏi "cần LLM làm gì khi kNN rẻ hơn").
