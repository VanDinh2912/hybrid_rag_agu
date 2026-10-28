# Tính năng Học Chuẩn hóa Câu hỏi (Query Normalization Active Learning)

## Tổng quan

Tính năng này cho phép hệ thống Hybrid RAG "tự học" cách chuẩn hóa câu hỏi từ phản hồi của người dùng, cải thiện dần dần chất lượng chuẩn hóa của Qwen theo thời gian.

---

## Kiến trúc Active Learning

```
Người dùng test câu hỏi
    ↓
Qwen chuẩn hóa → Hiển thị kết quả
    ↓
Người dùng đánh giá "Sai / Ảo giác"
    ↓
Form hiển thị 4 trường:
  1. Đáp án chuẩn (Ground Truth Answer)
  2. Trích dẫn Điều/Khoản (Citation)
  3. Tên văn bản nguồn (Source Document)
  4. Câu hỏi chuẩn hóa thực tế (Normalized Query GT) ← THÊM MỚI
    ↓
Người dùng chỉnh sửa normalized query nếu cần
    ↓
Nhấn "Lưu phản hồi & Ghi nhận"
    ↓
Hệ thống thực hiện 4 việc:
  1. Lưu vào outputs/user_feedback.json
  2. Lưu vào benchmark_questions.json (nếu có citation + source)
  3. Lưu vào data/learning/normalization_pairs.json (cặp chuẩn hóa) ← THÊM MỚI
  4. Ghi vào ghi_chu_hoc_them.txt (nếu checkbox "Học ngay")
    ↓
Lần test sau:
  Qwen TỰ ĐỘNG tải từ 3 nguồn:
    1. normalization_pairs.json (ưu tiên cao nhất)
    2. ghi_chu_hoc_them.txt (bài học cũ)
    3. benchmark_questions.json (bộ câu hỏi chuẩn)
  Nhét ví dụ người dùng thêm vào Few-Shot Prompt
  Qwen học cách dịch mới → Chuẩn hóa tốt hơn
```

---

## 3 Nguồn Dữ liệu Learning

### 1. `data/learning/normalization_pairs.json` (Người dùng thêm qua GUI)

**Format:**
```json
{
  "version": "1.0",
  "description": "Cặp câu hỏi chuẩn hóa để Qwen học",
  "pairs": [
    {
      "raw_query": "câu hỏi gốc",
      "normalized_query": "câu hỏi chuẩn hóa",
      "created_at": "2025-01-15T10:30:00"
    }
  ]
}
```

**Đặc điểm:**
- Tự động tạo khi người dùng lưu phản hồi trên GUI
- Kiểm tra trùng lặp → cập nhật nếu câu gốc đã tồn tại
- Timestamp để theo dõi thời gian thêm
- **Ưu tiên cao nhất** trong logic load

---

### 2. `data/corpus/ghi_chu_hoc_them.txt` (Bài học cũ)

**Format:**
```
Câu hỏi: [câu hỏi gốc]
Đáp án chuẩn: [đáp án đúng]
Căn cứ: [citation]
Nguồn: [source document]
Chuẩn hóa: [câu hỏi chuẩn hóa] ← Quan trọng
--------------------------------------------------------------------------------
```

**Đặc điểm:**
- Tự động tạo khi người dùng tick "Học ngay" trên GUI
- Format có cấu trúc để parse dễ dàng
- Được dùng khi normalization_pairs.json chưa tồn tại
- **Ưu tiên thứ 2** trong logic load

---

### 3. `data/evaluation/benchmark_questions.json` (Bộ câu hỏi chuẩn)

**Format:**
```json
{
  "version": "2.0",
  "description": "Bộ câu hỏi benchmark Hybrid RAG AGU",
  "questions": [
    {
      "id": "Q01",
      "raw_query": "Môn học Thiết kế và cài đặt mạng có mã môn học là gì...",
      "normalized_query": "Môn học Thiết kế và cài đặt mạng có mã môn học là gì...",
      "expected_answer": "...",
      "expected_citations": ["..."],
      "ground_truth_answer": "...",
      "ground_truth_citation": "..."
    }
  ]
}
```

**Đặc điểm:**
- Bộ 15 câu hỏi benchmark chuẩn đã có sẵn
- Chứa cả raw_query và normalized_query chuẩn
- Được dùng làm ví dụ cơ bản cho Qwen
- **Ưu tiên thứ 3** trong logic load

---

## Logic Tải Learning Pairs

```python
def load_normalization_pairs() -> dict:
    """Tải cặp (câu_gốc -> câu_chuẩn_hóa) từ 3 nguồn theo thứ tự ưu tiên:
    
    1. normalization_pairs.json (người dùng thêm qua GUI)
    2. ghi_chu_hoc_them.txt (bài học cũ, format có cấu trúc)
    3. benchmark_questions.json (bộ câu hỏi benchmark chuẩn)
    
    Trả về dict format: {"raw_query": "normalized_query"}
    """
    all_pairs = {}
    
    # 1. Tải từ normalization_pairs.json (ưu tiên cao nhất)
    # ...
    
    # 2. Tải từ ghi_chu_hoc_them.txt (format có cấu trúc)
    # ...
    
    # 3. Tải từ benchmark_questions.json (bộ câu hỏi chuẩn)
    # ...
    
    return all_pairs
```

**Quy tắc:**
- Nếu cùng một câu gốc xuất hiện ở nhiều nguồn → Source có ưu tiên cao hơn sẽ ghi đè
- normalization_pairs.json > ghi_chu_hoc_them.txt > benchmark_questions.json

---

## Few-Shot Prompt với Learning Examples

### Ví dụ Prompt (khi có 2 cặp learning từ người dùng):

```
Ví dụ 1:
Sinh viên: Bị điểm rèn luyện loại yếu thì có bị đuổi học không ad?
Chuẩn hóa: Sinh viên có kết quả xếp loại rèn luyện Yếu có bị buộc thôi học không?

Ví dụ 2:
Sinh viên: Nếu em rớt môn thì có được xét học bổng với khen thưởng không ạ?
Chuẩn hóa: Sinh viên có điểm học phần lần thứ nhất dưới 5.5 có được xét khen thưởng và học bổng không?

Ví dụ 3:
Sinh viên: Em đang nợ học phí chưa đóng tiền học kịp thì làm đơn gì để được đi thi?
Chuẩn hóa: Sinh viên cần làm thủ tục gì về hỗ trợ học phí, miễn giảm học phí và gia hạn nộp học phí để được dự thi?

Ví dụ 4:
Sinh viên: môn Thiết kế và cài đặt mạng mã mấy vậy, học mấy tín với phải qua môn nào trước
Chuẩn hóa: Môn Thiết kế và cài đặt mạng có mã môn học là gì, bao nhiêu tín chỉ và có môn học trước là môn nào?

Ví dụ 5 (Người dùng thêm):
Sinh viên: ad cho em hỏi về cái quy định scholarship với khen thưởng thế nào
Chuẩn hóa: Hỏi về quy định học bổng và khen thưởng đối với sinh viên?

Ví dụ 6 (Người dùng thêm):
Sinh viên: em muốn biết mấy tín chỉ mới được xét giỏi sv
Chuẩn hóa: Sinh viên cần bao nhiêu tín chỉ tích lũy để được xét danh hiệu Sinh viên giỏi?

Ví dụ 7:
Sinh viên: [câu hỏi hiện tại của người dùng]
Chuẩn hóa:
```

**Quy tắc:**
- 4 ví dụ base cố định (hard-coded) làm foundation
- Tối đa 4 ví dụ từ người dùng (learning_pairs)
- Tổng số ví dụ: 4 + min(4, learning)
- Gắn nhãn "Người dùng thêm" cho ví dụ học
- Giữ prompt không quá dài để Qwen 1.5B xử lý tốt

---

## Giao diện GUI

### Tab 3: Vừa test vừa học (Feedback)

Khi nhấn nút **"❌ Sai / Ảo giác"**, form sẽ hiển thị:

```
┌─────────────────────────────────────────────────────────┐
│ Trọng tài đánh giá & Phản hồi cải thiện                 │
├─────────────────────────────────────────────────────────┤
│ 1. Đáp án đúng thực tế (Ground Truth Answer):         │
│ [ScrolledText - 3 dòng]                                │
│                                                          │
│ 2. Căn cứ Điều / Khoản (Citation):                       │
│ [Entry: _______________] (Ví dụ: Điều 3, Khoản 1)    │
│                                                          │
│ 3. Tên văn bản nguồn (Source Document):                 │
│ [Combobox: ▼] (Chọn hoặc gõ tên mới)                    │
│                                                          │
│ 4. Câu hỏi chuẩn hóa thực tế (Normalized Query GT):      │
│ [Entry: _______________] (Chỉnh sửa nếu Qwen chưa đúng)│
│                                                          │
│ ☑ Đồng thời ghi vào bài học mới...                     │
│                                                    [Lưu...] │
└─────────────────────────────────────────────────────────┘
```

**Đặc điểm:**
- Field 4: Auto-fill normalized query từ kết quả hiện tại
- Cho phép người dùng chỉnh sửa nếu Qwen chuẩn hóa chưa đúng
- Lưu cặp (raw → normalized) vào normalization_pairs.json

---

## Implementation Details

### File: `ui/app.py`

**Thêm field mới:**
```python
# 4. Câu hỏi chuẩn hóa thực tế (Ground Truth Normalized Query)
self.entry_normalized_truth = ttk.Entry(norm_row, font=(DEFAULT_FONT_FAMILY, 10))
```

**Auto-fill khi mở form:**
```python
# Auto-fill normalized query từ kết quả hiện tại (cho phép chỉnh sửa)
current_normalized = self.current_test_data.get("normalized_query", "")
self.entry_normalized_truth.insert(0, current_normalized)
```

**Lưu cặp chuẩn hóa:**
```python
def _save_normalization_pair(self, raw_query: str, normalized_query: str):
    """Lưu cặp (câu_gốc -> câu_chuẩn_hóa) vào file normalization_pairs.json"""
    # Kiểm tra trùng lặp
    # Thêm hoặc cập nhật
    # Lưu file JSON
```

---

### File: `src/query_normalizer.py`

**Hàm load 3 nguồn:**
```python
def load_normalization_pairs() -> dict:
    """Tải từ 3 nguồn theo thứ tự ưu tiên"""
    # 1. normalization_pairs.json
    # 2. ghi_chu_hoc_them.txt (parse regex)
    # 3. benchmark_questions.json
    return all_pairs
```

**Hàm build prompt với learning:**
```python
def build_few_shot_with_learning(user_query: str, learning_pairs: dict) -> str:
    """Xây dựng Few-Shot Prompt với ví dụ học từ người dùng"""
    # 4 ví dụ base cố định
    # Tối đa 4 ví dụ từ learning_pairs
    # Tổng số ví dụ: 4 + min(4, learning)
    return prompt
```

**Cập nhật normalize_user_query:**
```python
def normalize_user_query(llm_client: Any, user_query: str) -> str:
    # Load learning pairs
    learning_pairs = load_normalization_pairs()
    
    # Build prompt với learning
    prompt = build_few_shot_with_learning(raw_text, learning_pairs)
    
    # Gọi Qwen
    # ...
```

---

## Lợi ích

1. **Học từ người dùng**: Qwen tự động học cách dịch mới mỗi lần người dùng phản hồi
2. **Cải thiện dần dần**: Càng nhiều phản hồi → chuẩn hóa càng chính xác
3. **Khả năng mở rộng**: Prompt không quá dài (tối đa 8 ví dụ) để Qwen 1.5B vẫn xử lý tốt
4. **Tích hợp liền mạch**: Tự động lưu và tải, không cần cấu hình thủ công
5. **Theo dõi được**: Timestamp trong normalization_pairs.json để track learning progress
6. **Đa nguồn dữ liệu**: Tải từ 3 nguồn khác nhau, tận dụng toàn bộ dữ liệu có sẵn

---

## Sử dụng

### Bước 1: Test câu hỏi
- Nhập câu hỏi vào ô test
- Nhấn "Chạy kiểm tra"
- Xem kết quả chuẩn hóa và câu trả lời

### Bước 2: Đánh giá
- Nếu chuẩn hóa đúng → Nhấn "✅ Đúng / Chính xác"
- Nếu chuẩn hóa sai → Nhấn "❌ Sai / Ảo giác"

### Bước 3: Chỉnh sửa và lưu
- Form hiển thị 4 trường
- Chỉnh sửa "Câu hỏi chuẩn hóa thực tế" nếu cần
- Nhập đầy đủ thông tin
- Tick "Học ngay" nếu muốn
- Nhấn "Lưu phản hồi & Ghi nhận"

### Bước 4: Hệ thống tự học
- Cặp chuẩn hóa được lưu vào normalization_pairs.json
- Lần test sau → Qwen tự động tải và sử dụng
- Chuẩn hóa sẽ cải thiện dần

---

## Monitoring

### Kiểm tra số lượng learning pairs:
```bash
# Xem file normalization_pairs.json
cat data/learning/normalization_pairs.json
```

### Kiểm tra log khi chạy:
```
[Normalization] Đã tải X cặp từ normalization_pairs.json
[Normalization] Đã tải Y cặp từ ghi_chu_hoc_them.txt
[Normalization] Đã tải Z cặp từ benchmark_questions.json
[Normalization] Tổng cộng đã tải N cặp chuẩn hóa từ 3 nguồn
```

### Reset learning (nếu cần):
```bash
# Xóa normalization_pairs.json để bắt đầu lại
rm data/learning/normalization_pairs.json
```

---

## Troubleshooting

### Qwen không học được cách dịch mới?
- Kiểm tra file normalization_pairs.json có tồn tại không
- Kiểm tra format JSON có đúng không
- Kiểm tra log console khi chạy query

### Prompt quá dài?
- Logic giới hạn tối đa 4 ví dụ từ người dùng
- Nếu vẫn quá dài → Giảm số ví dụ base trong code

### Parse ghi_chu_hoc_them.txt lỗi?
- Kiểm tra format file có đúng không
- Kiểm tra encoding UTF-8
- Regex pattern có thể cần điều chỉnh

---

## Tương lai

### Các cải tiến có thể:
1. **Vector similarity**: Chỉ chọn learning pairs tương đồng với câu hỏi hiện tại
2. **Ranking**: Sắp xếp learning pairs theo relevance score
3. **Continuous Learning**: Auto-reload learning pairs mỗi N câu hỏi
4. **Evaluation**: Đánh giá hiệu quả active learning qua A/B testing
5. **Dashboard**: GUI hiển thị số lượng learning pairs và improvement metrics

---

## References

- Few-Shot Learning: https://arxiv.org/abs/2005.14165
- Active Learning: https://en.wikipedia.org/wiki/Active_learning
- Prompt Engineering: https://www.promptingguide.ai/
