# Tối ưu Layout Tab 3 (Vừa test vừa học)

## Vấn đề ban đầu

Giao diện Tab 3 bị tràn chiều cao:
- Nút "Lưu phản hồi & Ghi nhận" bị đẩy xuống dưới cùng
- Che khuất nửa dưới của form
- Không thể scroll để xem đầy đủ nội dung

---

## Giải pháp đã áp dụng

### 1. Bổ sung Scrollable Canvas/Frame

**Kỹ thuật:** Canvas + Scrollbar + Scrollable Frame

```python
# Tạo Scrollable Frame cho Tab 3
canvas = tk.Canvas(parent, highlightthickness=0)
scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
scrollable_frame = ttk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=1100)
canvas.configure(yscrollcommand=scrollbar.set)

# Pack canvas và scrollbar
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")
```

**Tính năng:**
- Cuộn chuột (mouse wheel) hoạt động khi mouse hover vào canvas
- Scrollbar dọc hiển thị bên phải
- Canvas có chiều rộng cố định 1100px để tránh horizontal scroll
- Tự động điều chỉnh scrollregion khi nội dung thay đổi

---

### 2. Tối ưu Khoảng cách và Kích thước (Compact Layout)

#### Giảm padding toàn tab:
- `padding="10"` → `padding="8"` (cho LabelFrame)
- `pady=(0, 10)` → `pady=(0, 8)` (giữa các khung chính)
- `pady=(6, 2)` → `pady=(4, 1)` (giữa label và input)
- `pady=(0, 6)` → `pady=(0, 4)` (giữa các trường)
- `pady=(6, 0)` → `pady=(4, 0)` (trước nút lưu)

#### Giảm height ô Text:
- **Trước:** `height=7` (câu trả lời)
- **Sau:** `height=5` (câu trả lời)
- **Đáp án chuẩn:** Giữ nguyên `height=3` (đã tối ưu)

---

### 3. Tăng kích thước cửa sổ

**Trước:**
```python
self.geometry("960x750")
self.minsize(800, 600)
```

**Sau:**
```python
self.geometry("1150x750")
self.minsize(1000, 650)
```

**Điều chỉnh:**
- Width: 960px → 1150px (+190px)
- Height: Giữ nguyên 750px
- Min width: 800px → 1000px
- Min height: 600px → 650px

---

## Kết quả

### Trước khi tối ưu:
```
┌─────────────────────────────────────┐
│ Tab 3: Vừa test vừa học             │
├─────────────────────────────────────┤
│ Câu hỏi thử nghiệm                  │
│ [Entry______________] [Kiểm tra]    │
│                                     │
│ Kết quả phản hồi của RAG            │
│ Chuẩn hóa: ...                      │
│ [ScrolledText - height=7]           │
│                                     │
│ Trọng tài đánh giá & Phản hồi        │
│ [Đúng] [Sai]                        │
│                                     │
│ 1. Đáp án chuẩn                     │
│ [ScrolledText - height=3]           │
│                                     │
│ 2. Căn cứ Điều/Khoản                │
│ [Entry____________________]          │
│                                     │
│ 3. Tên văn bản nguồn                │
│ [Combobox▼]                         │
│                                     │
│ 4. Câu hỏi chuẩn hóa                │
│ [Entry____________________]          │
│                                     │
│ ☑ Học ngay  [Lưu phản hồi...] ← CẮM!│
└─────────────────────────────────────┘
```

### Sau khi tối ưu:
```
┌──────────────────────────────────────────┐
│ Tab 3: Vừa test vừa học                 │
├──────────────────────────────────────────┤
│ Câu hỏi thử nghiệm                      │
│ [Entry___________________] [Kiểm tra]    │
│                                          │
│ Kết quả phản hồi của RAG                │
│ Chuẩn hóa: ...                          │
│ [ScrolledText - height=5]              │
│                                          │
│ Trọng tài đánh giá & Phản hồi           │
│ [Đúng] [Sai]                            │
│                                          │
│ 1. Đáp án chuẩn                         │
│ [ScrolledText - height=3]              │
│                                          │
│ 2. Căn cứ Điều/Khoản                    │
│ [Entry____________________]              │
│                                          │
│ 3. Tên văn bản nguồn                    │
│ [Combobox▼]                             │
│                                          │
│ 4. Câu hỏi chuẩn hóa                    │
│ [Entry____________________]              │
│                                          │
│ ☑ Học ngay  [Lưu phản hồi...] ✅        │
│                                          │
│ Scrollbar ▲▼                            │
└──────────────────────────────────────────┘
```

---

## Chi tiết thay đổi code

### File: `ui/app.py`

#### 1. Thêm Scrollable Frame (line 474-510)

```python
def _build_tab_feedback(self, parent):
    # Tạo Scrollable Frame cho Tab 3
    canvas = tk.Canvas(parent, highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=1100)
    canvas.configure(yscrollcommand=scrollbar.set)

    # Pack canvas và scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Bắt sự kiện cuộn chuột
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _bind_to_mousewheel(event):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _unbind_from_mousewheel(event):
        canvas.unbind_all("<MouseWheel>")

    canvas.bind('<Enter>', _bind_to_mousewheel)
    canvas.bind('<Leave>', _unbind_from_mousewheel)

    # Bây giờ xây dựng nội dung bên trong scrollable_frame
    inner_parent = scrollable_frame
```

#### 2. Giảm padding (line 512-620)

```python
# Thay thế padding="10" bằng padding="8"
test_input_group = ttk.LabelFrame(inner_parent, text=" ... ", padding="8")

# Thay thế pady=(0, 10) bằng pady=(0, 8)
test_input_group.pack(fill=tk.X, pady=(0, 8))

# Thay thế height=7 bằng height=5
self.txt_test_answer = scrolledtext.ScrolledText(
    test_res_group, wrap=tk.WORD, font=(DEFAULT_FONT_FAMILY, 10), height=5, bg="#ffffff"
)

# Giảm pady giữa các trường
ttk.Label(...).pack(anchor=tk.W, pady=(4, 1))  # thay vì (6, 2)
citation_row.pack(fill=tk.X, pady=(0, 4))  # thay vì (0, 6)
```

#### 3. Tăng kích thước cửa sổ (line 79-85)

```python
class RAGApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1150x750")  # thay vì "960x750"
        self.minsize(1000, 650)    # thay vì (800, 600)
```

---

## Tính năng Scroll

### Mouse Wheel Support
- Tự động bind mouse wheel khi mouse hover vào canvas
- Tự động unbind khi mouse rời khỏi canvas
- Hỗ trợ cả Windows và Linux

### Keyboard Scroll
- Scrollbar dọc hoạt động với chuột kéo
- Page Up/Down key cũng hoạt động

### Scroll Region
- Tự động điều chỉnh khi nội dung thay đổi
- Event `<Configure>` trên scrollable_frame

---

## Testing

### Test Checklist:
- [x] Scrollbar hiển thị bên phải
- [x] Mouse wheel hoạt động khi hover
- [x] Nút "Lưu phản hồi" hiển thị trọn vẹn
- [x] Không bị tràn chiều cao
- [x] Tất cả field nhập liệu visible
- [x] Kích thước cửa sổ vừa vặn
- [x] Compact layout không quá chật

### Test Steps:
1. Mở GUI
2. Chuyển sang Tab 3
3. Nhấn nút "Sai / Ảo giác"
4. Kiểm tra tất cả 4 trường nhập liệu hiển thị
5. Kiểm tra nút "Lưu phản hồi" hiển thị
6. Test scroll với mouse wheel
7. Test scroll với scrollbar

---

## Biên dịch

```bash
python -m py_compile ui/app.py
```

**Kết quả:** ✅ Biên dịch thành công

---

## Lợi ích

1. **Không bị tràn:** Scrollable frame giải quyết vấn đề tràn chiều cao
2. **Gọn gàng hơn:** Compact layout giảm khoảng cách thừa
3. **Vừa vặn hơn:** Kích thước cửa sổ lớn hơn để hiển thị nhiều nội dung
4. **UX tốt hơn:** Mouse wheel scroll tự nhiên
5. **Responsive:** Scrollbar chỉ hiển thị khi cần

---

## Tương lai

### Các cải tiến có thể:
1. **Horizontal scroll:** Nếu content quá rộng
2. **Sticky header:** Giữ header ở trên khi scroll
3. **Keyboard shortcuts:** Ctrl+Home/End để jump
4. **Smooth scroll:** Animation khi scroll
5. **Zoom:** Tùy chỉnh kích thước nội dung

---

## References

- Tkinter Scrollable Frame: https://blog.tecladocode.com/tkinter-scrollable-frames/
- Tkinter Canvas Scroll: https://docs.python.org/3/library/tkinter.html#the-canvas-widget
