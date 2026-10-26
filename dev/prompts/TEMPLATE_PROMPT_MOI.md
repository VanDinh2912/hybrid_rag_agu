# TEMPLATE — Viết prompt giao việc cho bất kỳ agent nào

Ba dạng văn bản dưới đây phủ hết các trường hợp. Nguyên tắc chung: agent "hiểu" khi nó không phải đoán gì thêm — chỗ nào bạn bỏ trống, nó lấp bằng cách nó thấy hợp lý, và cách đó có thể không phải cách bạn muốn.

---

## Cách 1 — Làm nhiệm vụ có sẵn trong bộ prompts/ (chép nguyên văn, chỉ đổi tên file)

```text
Bạn đang làm việc trong repo hybrid_rag_agu tại D:\DoAn\hybrid_rag_agu (Windows, shell PowerShell).

Nhiệm vụ của bạn: prompts/P2_1_classifier_module.md

Làm theo đúng thứ tự:
1. Đọc prompts/00_base_context.md — quy tắc môi trường, quy tắc verify, quy tắc cập nhật tiến độ (mục 6).
2. Đọc file nhiệm vụ ở trên và TOÀN BỘ file ngữ cảnh mà nó chỉ định đọc trước.
3. DỪNG, tóm tắt lại cho tôi: (a) nhiệm vụ là gì, (b) bạn sẽ tạo/sửa đúng những file nào,
   (c) bạn KHÔNG được làm gì, (d) "xong" được đo bằng mốc verify nào. Chờ tôi xác nhận rồi mới làm.
4. Làm đúng phạm vi nhiệm vụ. Gặp điều cần tôi quyết → dừng hỏi, không tự quyết.
5. Xong: chạy đủ verify, cập nhật prompts/PROGRESS.md (đúng 1 dòng của nhiệm vụ này),
   rồi báo cáo gồm: file đã tạo/sửa, chứng cứ verify từng mốc, xác nhận tmp/ đã dọn.
```

Chỉ cần đổi dòng "Nhiệm vụ của bạn" sang file prompt kế tiếp. Hai dòng 3 và 5 là quan trọng nhất: dòng 3 bắt agent chứng minh nó hiểu TRƯỚC khi làm, dòng 5 bắt nó chứng minh đã xong bằng bằng chứng.

---

## Cách 2 — Nhiệm vụ mới ngoài bộ prompt (điền vào khung 8 phần)

```text
## Bối cảnh
- Dự án: <tên + mục tiêu 1 dòng>
- Repo: <đường dẫn>, môi trường: <Windows/PowerShell, lệnh chạy Python: venv\Scripts\python.exe>
- Hiện trạng liên quan: <file nào đã tồn tại, đang ở giai đoạn nào, kết quả lần trước ra sao>

## Nhiệm vụ (MỘT việc thôi)
Mục tiêu: <điều gì là "xong">
Các bước:
1. <bước cụ thể>
2. <bước cụ thể>
3. <bước cụ thể>

## Cấm
- Không sửa/xóa: <file hoặc thư mục> — vì <lý do 1 dòng>
- Không làm: <hành vi> — vì <lý do 1 dòng>

## Xong = gì
- Sản phẩm: <đường dẫn file chính xác>
- Verify bắt buộc: <lệnh> → <kết quả mong đợi>; báo cáo kèm chứng cứ (output thật)

## Khi lỗi
- Nếu <Ollama chết / thiếu file / API lỗi> thì <lùi về cái gì>, không crash, không treo

## Dừng chờ tôi
- Trước khi <hành động quan trọng: ghi đè / xóa / tiêu quota / công bố> phải dừng hỏi tôi
```

Quy tắc điền: mục nào bạn bỏ trống là mục agent sẽ tự tưởng tượng. Cấm kèm lý do thì agent hiểu nguyên tắc và tự xử lý đúng cả tình huống bạn không liệt kê.

---

## Ví dụ đã điền đầy đủ (nhiệm vụ nhỏ, thực tế)

```text
## Bối cảnh
- Dự án: hệ RAG hỏi-đáp quy chế AGU. Repo: D:\DoAn\hybrid_rag_agu, Windows/PowerShell,
  Python: venv\Scripts\python.exe.
- Hiện trạng: .env.example chưa có biến ENABLE_CLASSIFIER; README.md mục 3 là bảng
  biến môi trường chính thức.

## Nhiệm vụ (MỘT việc thôi)
Mục tiêu: khai báo công tắc ENABLE_CLASSIFIER trong cấu hình, chưa nối code.
Các bước:
1. Thêm khối 3 biến (ENABLE_CLASSIFIER=0, CLASSIFIER_MODEL=, CLASSIFIER_TIMEOUT=20)
   vào .env.example với chú thích tiếng Việt đúng phong cách file.
2. Thêm cùng khối vào .env (giá trị 0). KHÔNG in nội dung .env ra output (chứa API key).
3. Thêm 3 biến vào bảng biến môi trường ở README.md mục 3, ghi chú "chưa có tác dụng
   cho đến giai đoạn 3".

## Cấm
- Không sửa bất kỳ file code Python nào — nhiệm vụ này chỉ khai báo cấu hình.
- Không in nội dung .env — chứa API key.

## Xong = gì
- Sản phẩm: .env.example, .env, README.md mục 3 có 3 biến mới.
- Verify: Select-String ENABLE_CLASSIFIER .env.example ra ≥ 1 dòng;
  python -c "from dotenv import dotenv_values; print('ENABLE_CLASSIFIER' in dotenv_values('.env'))"
  in True mà không in giá trị khác.

## Khi lỗi
- .env không tồn tại thì tạo từ .env.example rồi thêm khối, báo lại rõ trong kết quả.

## Dừng chờ tôi
- Không có — nhiệm vụ nhỏ, làm hết rồi báo cáo.
```

Bộ 22 prompt trong thư mục này chính là khung 8 phần trên được điền đầy đủ 22 lần.

---

## Nếu chỉ muốn viết 3 dòng (tối thiểu — chỉ dùng cho nhiệm vụ trong bộ prompts/)

```text
Đọc prompts/00_base_context.md rồi làm prompts/P2_2_classifier_tests.md.
Trước khi làm, tóm tắt lại: nhiệm vụ gì, sẽ đụng file nào, cấm gì — chờ tôi duyệt.
Xong phải chạy đủ mục Verify trong file và cập nhật prompts/PROGRESS.md.
```

Càng ngắn càng phụ thuộc vào việc file prompt đã viết đủ chi tiết — bộ prompts/ viết đủ rồi nên 3 dòng là đủ cho chính dự án này. Với dự án khác, dùng khung 8 phần.

---

## 8 chỗ agent hay đoán sai — checklist trước khi gửi

1. Môi trường (OS, shell, lệnh chạy) đã nói chưa? → không nói nó dùng thói quen Linux trên Windows.
2. Nhiệm vụ có đúng MỘT việc không? → nhiều mục tiêu = làm mục đầu tử tế, phần sau qua loa.
3. Đã chỉ đích danh file cần đọc trước chưa? → không chỉ nó mò cả repo rồi đoán sai.
4. Các bước có đánh số, cụ thể đến đường dẫn chưa? → "làm hộ cái X" là không cụ thể.
5. Cấm gì đã kèm lý do chưa? → có lý do nó mới tự xử đúng tình huống mới.
6. "Xong" đo bằng gì, chạy lệnh nào chứng minh? → không đo được là nó tự tuyên bố thắng.
7. Lỗi thì lùi thế nào đã định nghĩa chưa? → không định nghĩa nó chỉ viết code cho đường vui.
8. Chỗ nào cần bạn quyết đã có lệnh DỪNG chưa? → không có là nó tự quyết thay bạn.
