# Hướng dẫn khắc phục lỗi GUI "Vừa test vừa học" bị đứng

## Vấn đề
Phần "Vừa test vừa học (Feedback)" bị stuck ở trạng thái "Đang chuẩn hóa..." và không sinh câu trả lời.

---

## Bước 1: Kiểm tra trạng thái Backend

### Nhìn vào Status Bar (góc trên bên phải GUI)
- ✅ **Màu xanh + "Hệ thống sẵn sàng | DB: X chunks"** → Backend OK, vấn đề ở Ollama/Gemini
- ❌ **Màu đỏ + "Khởi tạo thất bại: ..."** → Backend lỗi → Xem Bước 4

---

## Bước 2: Kiểm tra Ollama (Local Qwen)

### Mở terminal và chạy:
```bash
ollama list
```

### Kết quả:
- ✅ Hiển thị danh sách model → Ollama đang chạy
- ❌ Báo lỗi "Failed to connect" → Ollama chưa chạy

### Khắc phục:
```bash
# Terminal 1: Khởi động Ollama
ollama serve

# Terminal 2: Pull model
ollama pull qwen2.5:1.5b-instruct
```

### Sau khi sửa:
- Đóng GUI cũ
- Mở lại GUI: `python ui/app.py`

---

## Bước 3: Kiểm tra Gemini API

### Mở file `.env` và kiểm tra:
```
GEMINI_API_KEY=your_gemini_api_key_here
```

### Nếu vẫn là giá trị mẫu:
1. Truy cập: https://aistudio.google.com/app/apikey
2. Tạo API key mới
3. Copy vào `.env`
4. Đóng và mở lại GUI

### Nếu đã có key thật nhưng vẫn lỗi:
- Có thể hết quota (free tier: ~15 req/phút, ~20 req/ngày)
- Đợi reset quota hoặc dùng key trả phí

---

## Bước 4: Kiểm tra Error Log (Nếu Backend khởi tạo thất bại)

### Xem popup error khi khởi động GUI
- Nếu có popup → Lưu thông báo lỗi
- Nếu không popup → Check terminal chạy GUI

### Error thường gặp:
1. **ModuleNotFoundError: No module named 'chromadb'**
   - Chạy: `pip install -r requirements.txt`

2. **GeneratorError: GEMINI_API_KEY vẫn là giá trị mẫu**
   - Thay API key thật trong `.env`

3. **LocalSLMError: Không kết nối được Ollama**
   - Chạy `ollama serve` trước

---

## Bước 5: Đóng và mở lại GUI

Daemon thread đôi khi bị "zombie". Khắc phục:
1. Đóng GUI (X button)
2. Đảm bảo không còn process python app.py chạy ngầm
3. Mở lại:
```bash
python ui/app.py
```

---

## Bước 6: Chạy test từ terminal để debug

Nếu GUI vẫn bị đứng, chạy test trực tiếp từ terminal:

```bash
python main.py "Sinh viên đạt giải Olympic Tin học Quốc gia được thưởng bao nhiêu tiền và cộng mấy điểm rèn luyện?"
```

### Nếu CLI cũng bị đứng:
- Vấn đề ở backend/dependencies → Cài lại packages
- Nếu CLI chạy được → Vấn đề ở GUI threading → Đã fix trong code mới

---

## Biện pháp khắc phục đã áp dụng trong code

### 1. Thêm logging vào test thread
```python
print(f"[Test Thread] Bắt đầu xử lý câu hỏi: {query[:50]}...")
print(f"[Test Thread] Hoàn tất processing question")
print(f"[Test Thread] Lỗi: {error_detail}")
```

### 2. Hiển thị chi tiết lỗi đầy đủ
```python
error_detail = f"{type(exc).__name__}: {exc}\n\nChi tiết:\n{traceback.format_exc()}"
```

### 3. Popup error rõ ràng hơn
- Hiển thị traceback đầy đủ
- Dễ dàng debug nguyên nhân gốc

---

## Checklist kiểm tra nhanh

- [ ] Ollama đang chạy (`ollama list` OK)
- [ ] Model Qwen đã pull (`qwen2.5:1.5b-instruct`)
- [ ] GEMINI_API_KEY trong `.env` đã thay bằng key thật
- [ ] Dependencies đã cài (`pip install -r requirements.txt`)
- [ ] ChromaDB có dữ liệu (`chroma_db/` tồn tại)
- [ ] GUI đã đóng và mở lại sau khi sửa
- [ ] Terminal không có process app.py cũ chạy ngầm

---

## Liên hệ nếu vẫn lỗi

Nếu đã thử tất cả bước trên mà vẫn bị đứng:
1. Copy terminal output khi chạy GUI
2. Copy nội dung `.env` (ẩn API key)
3. Gửi để hỗ trợ tiếp
