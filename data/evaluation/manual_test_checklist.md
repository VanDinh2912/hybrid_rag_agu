# Checklist kiểm tra tay — Hybrid RAG tra cứu quy chế AGU

- **File này để làm gì**: bạn tự chạy từng câu hỏi trên ứng dụng rồi đối chiếu câu trả lời với đáp án kỳ vọng. Đáp án kỳ vọng được rút trực tiếp từ tài liệu gốc trong `data/corpus/` — bạn có thể mở file gốc để đối chiếu lại nếu nghi ngờ.
- **Số câu**: 34 + 3 câu kiểm tra nhãn phân loại (Nhóm 8, thêm từ P3.5), chia 8 nhóm. Nên chạy hết trong **một phiên tương tác** để chỉ tốn ~40 giây khởi động một lần.
- Nhóm 1 là các câu **hồi quy** (đã từng trả lời đúng, cần giữ đúng sau khi sửa truy xuất). Nhóm 7 là các câu **phải từ chối** (ngoài phạm vi corpus).

## Cách chạy

```bash
# Chế độ tương tác (khuyến nghị): hỏi liên tục, không phải khởi động lại
./venv/Scripts/python.exe main.py

# Hoặc hỏi 1 câu rồi thoát
./venv/Scripts/python.exe main.py "câu hỏi ..."
```

Gõ từng câu ở ô `Câu hỏi > `, gõ `exit` để thoát.

**Lưu ý khi chạy:**
- Lần chạy đầu mất khoảng 40 giây trước khi nhận câu hỏi đầu tiên (nạp bge-m3 ~25s, nạp Qwen qua Ollama ~9s). Đây là bình thường, đừng thoát giữa chừng.
- Nếu dòng `[4] CÂU TRẢ LỜI` có nhãn `(Local Qwen — FALLBACK)` thì Gemini đang lỗi hoặc hết quota — ghi chú lại rồi bỏ qua câu đó, đừng tính là lỗi chất lượng.
- Nhóm 6 là văn bản hành chính (thông báo) **không có Điều/Khoản**: nếu hệ thống bịa số "Điều X" cho các văn bản này thì đánh dấu lỗi ngay.

## Cách chấm mỗi câu

Đối chiếu 4 điểm, sau đó tự kết luận Đạt / Không đạt:

1. **Nguồn đúng** — mục `[3] NGUỒN TRÍCH DẪN` có chứa file ghi ở ô "Nguồn kỳ vọng" (khớp theo tên file, không cần đúng vị trí).
2. **Nội dung đúng** — câu trả lời khớp "Đáp án kỳ vọng" (được phép diễn đạt khác, miễn không sai ý).
3. **Trích dẫn đúng** — số Điều/Khoản trong câu trả lời khớp "Trích dẫn kỳ vọng".
4. **Không bịa** — không có số liệu, thời hạn, điều khoản nào không tồn tại trong tài liệu gốc.

---

## Nhóm 1 — Hồi quy: kỷ luật sinh viên & đánh giá rèn luyện (1054 + 1059/QĐ-ĐHAG)

### N1.1 — Vi phạm lần đầu, mức độ nhẹ

- **Hỏi:** `Ê ad, sinh viên vi phạm lần đầu mà mức độ nhẹ thì có bị kỷ luật nặng không hay sao?`
- **Nguồn kỳ vọng:** `1054-qd-dhag-2020-09-28.pdf`
- **Đáp án kỳ vọng:** Chỉ bị khiển trách — hình thức kỷ luật nhẹ nhất, áp dụng cho sinh viên vi phạm lần đầu nhưng mức độ nhẹ.
- **Trích dẫn kỳ vọng:** Điều 17 Khoản 1
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N1.2 — Các hình thức kỷ luật

- **Hỏi:** `Cho em hỏi trường có những hình thức kỷ luật sinh viên nào vậy ạ?`
- **Nguồn kỳ vọng:** `1054-qd-dhag-2020-09-28.pdf`
- **Đáp án kỳ vọng:** Các hình thức: khiển trách, cảnh cáo, đình chỉ học tập có thời hạn, buộc thôi học (ngoài ra với vi phạm nhẹ còn có thể bị nhắc nhở, phê bình).
- **Trích dẫn kỳ vọng:** Điều 17 Khoản 1
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N1.3 — Đang bị cảnh cáo mà vi phạm tiếp

- **Hỏi:** `Bạn mình đang trong thời gian bị cảnh cáo mà dính lỗi tiếp luôn, có bị đình chỉ học tập không mọi người?`
- **Nguồn kỳ vọng:** `1054-qd-dhag-2020-09-28.pdf`
- **Đáp án kỳ vọng:** Có — đình chỉ học tập có thời hạn áp dụng với sinh viên đang trong thời gian bị cảnh cáo mà vẫn vi phạm kỷ luật (hoặc vi phạm nghiêm trọng các hành vi sinh viên không được làm).
- **Trích dẫn kỳ vọng:** Điều 17 Khoản 1
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N1.4 — Mức nào thì lưu hồ sơ, báo gia đình

- **Hỏi:** `bị kỷ luật mức nào thì trường lưu hồ sơ và báo cho gia đình vậy ad`
- **Nguồn kỳ vọng:** `1054-qd-dhag-2020-09-28.pdf`
- **Đáp án kỳ vọng:** Từ cảnh cáo trở lên thì lưu vào hồ sơ quản lý sinh viên và thông báo cho gia đình. Riêng trường hợp bị đình chỉ học tập có thời hạn hoặc buộc thôi học, nhà trường còn gửi thông báo cho địa phương và gia đình để phối hợp quản lý, giáo dục.
- **Trích dẫn kỳ vọng:** Điều 17 Khoản 2
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N1.5 — Điểm rèn luyện 62 điểm

- **Hỏi:** `điểm rèn luyện của tui có 62 điểm thôi, vậy xếp loại gì và có bị coi là không đạt không ad?`
- **Nguồn kỳ vọng:** `1059-qd-dhag-2020-09-29.pdf`
- **Đáp án kỳ vọng:** 62 điểm nằm trong khoảng từ 50 đến dưới 65 điểm → xếp loại Trung bình. Sinh viên xếp loại từ Trung bình trở lên là đạt.
- **Trích dẫn kỳ vọng:** Điều 10 Khoản 1, Khoản 2
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N1.6 — Đánh giá rèn luyện định kỳ theo gì

- **Hỏi:** `Kết quả rèn luyện được đánh giá định kỳ theo học kỳ hay theo năm học vậy mọi người?`
- **Nguồn kỳ vọng:** `1059-qd-dhag-2020-09-29.pdf`
- **Đáp án kỳ vọng:** Đánh giá định kỳ theo học kỳ chính, năm học và toàn khóa học.
- **Trích dẫn kỳ vọng:** Điều 9 Khoản 1
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N1.7 — Đang bị cảnh cáo, điểm rèn luyện có bị giới hạn?

- **Hỏi:** `bro ơi đang bị kỷ luật cảnh cáo, kỳ này điểm rèn luyện có bị giới hạn xếp loại không?`
- **Nguồn kỳ vọng:** `1059-qd-dhag-2020-09-29.pdf`
- **Đáp án kỳ vọng:** Có — trong thời gian bị kỷ luật mức cảnh cáo, kết quả rèn luyện không được vượt quá loại Trung bình.
- **Trích dẫn kỳ vọng:** Điều 11 Khoản 2
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

---

## Nhóm 2 — Thi đua, khen thưởng viên chức & người lao động (888/QĐ-ĐHAG)

### N2.1 — Tỷ lệ Chiến sĩ thi đua cơ sở

- **Hỏi:** `Tỷ lệ cá nhân được công nhận danh hiệu Chiến sĩ thi đua cơ sở của mỗi đơn vị tối đa là bao nhiêu?`
- **Nguồn kỳ vọng:** `888-qd-dhag-2022-08-08.pdf`
- **Đáp án kỳ vọng:** Không quá 15% tổng số cá nhân đạt danh hiệu Lao động tiên tiến.
- **Trích dẫn kỳ vọng:** Điều 10 Khoản 3
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N2.2 — Điều kiện Tập thể Lao động tiên tiến

- **Hỏi:** `Điều kiện để một tập thể được công nhận danh hiệu Tập thể Lao động tiên tiến là gì?`
- **Nguồn kỳ vọng:** `888-qd-dhag-2022-08-08.pdf`
- **Đáp án kỳ vọng:** Hoàn thành tốt nhiệm vụ và kế hoạch được giao; phong trào thi đua thường xuyên, thiết thực, hiệu quả; có trên 50% cá nhân trong tập thể đạt danh hiệu Lao động tiên tiến và không có cá nhân bị kỷ luật từ cảnh cáo trở lên; nội bộ đoàn kết.
- **Trích dẫn kỳ vọng:** Điều 13 (trọng tâm Khoản 3)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N2.3 — Họp Hội đồng Thi đua - Khen thưởng hợp lệ khi nào

- **Hỏi:** `Cuộc họp của Hội đồng Thi đua - Khen thưởng cấp Trường được coi là hợp lệ khi nào?`
- **Nguồn kỳ vọng:** `888-qd-dhag-2022-08-08.pdf`
- **Đáp án kỳ vọng:** Khi có ít nhất 2/3 số thành viên Hội đồng tham dự. Trường hợp vắng mặt, thành viên phải được Chủ tịch Hội đồng đồng ý và gửi lại phiếu biểu quyết.
- **Trích dẫn kỳ vọng:** Điều 30 Khoản 3
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N2.4 — Thời gian đăng ký thi đua

- **Hỏi:** `Các đơn vị gửi danh sách đăng ký thi đua hằng năm vào thời gian nào?`
- **Nguồn kỳ vọng:** `888-qd-dhag-2022-08-08.pdf`
- **Đáp án kỳ vọng:** Tháng 8 hằng năm, gửi về Thường trực Hội đồng Thi đua - Khen thưởng cấp Trường để tổng hợp, theo dõi.
- **Trích dẫn kỳ vọng:** Điều 37 Khoản 2
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N2.5 — Sinh viên có thuộc đối tượng xét thi đua? (câu khó)

- **Hỏi:** `Sinh viên có được xét tặng danh hiệu thi đua theo Quy định về công tác thi đua, khen thưởng của Trường không?`
- **Nguồn kỳ vọng:** `888-qd-dhag-2022-08-08.pdf`
- **Đáp án kỳ vọng:** Không — khen thưởng học sinh, sinh viên không thuộc phạm vi điều chỉnh của quy định này; đối tượng áp dụng là các đơn vị, viên chức và người lao động của Trường.
- **Trích dẫn kỳ vọng:** Điều 1 Khoản 2 và Điều 2
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

---

## Nhóm 3 — Khen thưởng HSSV ĐHQG-HCM (1133/QĐ-ĐHQG)

Nguồn: `QD1133_22815_VNU_ban hanh Quy dinh khen thuong HSSV -1.pdf`

### N3.1 — Hạn nộp hồ sơ khen thưởng định kỳ

- **Hỏi:** `Hồ sơ đề xuất khen thưởng định kỳ cho sinh viên gửi về ĐHQG-HCM trước ngày nào?`
- **Đáp án kỳ vọng:** Trước ngày 20 tháng 8 hằng năm (gửi qua đơn vị thường trực là Ban Công tác Sinh viên). Với khen thưởng đột xuất/chuyên đề: trước ít nhất 05 ngày làm việc trước khi đơn vị tổ chức trao.
- **Trích dẫn kỳ vọng:** Điều 7 Khoản 2
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N3.2 — Tốt nghiệp xuất sắc

- **Hỏi:** `Sinh viên tốt nghiệp loại xuất sắc cần đạt điều kiện gì để được xét giấy khen của Giám đốc ĐHQG-HCM?`
- **Đáp án kỳ vọng:** Điểm trung bình tích lũy toàn khóa đạt từ 9.0 trở lên và kết quả đánh giá rèn luyện toàn khóa đạt loại tốt trở lên.
- **Trích dẫn kỳ vọng:** Điều 5 Khoản 1 điểm e
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N3.3 — Ba hình thức khen thưởng

- **Hỏi:** `Có những hình thức triển khai công tác khen thưởng học sinh, sinh viên nào theo quy định của ĐHQG-HCM?`
- **Đáp án kỳ vọng:** 3 hình thức: khen thưởng định kỳ (hằng năm, sau khi kết thúc năm học), khen thưởng theo đợt hoặc theo chuyên đề, khen thưởng đột xuất.
- **Trích dẫn kỳ vọng:** Điều 4
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N3.4 — Điều kiện hiệu lực quyết định của Hội đồng

- **Hỏi:** `Quyết định của Hội đồng khen thưởng HSSV ĐHQG-HCM có giá trị khi bao nhiêu thành viên đồng ý?`
- **Đáp án kỳ vọng:** Khi có trên 50% thành viên Hội đồng đồng ý.
- **Trích dẫn kỳ vọng:** Điều 11 Khoản 4
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N3.5 — Số thành viên tối thiểu để họp hợp lệ (dễ nhầm với N3.4)

- **Hỏi:** `Cuộc họp của Hội đồng khen thưởng HSSV cần bao nhiêu thành viên tham dự mới hợp lệ?`
- **Đáp án kỳ vọng:** Ít nhất 2/3 số thành viên Hội đồng tham dự; vắng mặt phải được Chủ tịch Hội đồng đồng ý và gửi lại phiếu biểu quyết.
- **Trích dẫn kỳ vọng:** Điều 11 Khoản 3
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

> Ghi chú nhóm 3: N3.4 (trên 50% đồng ý) và N3.5 (ít nhất 2/3 tham dự) là cặp số dễ bị lẫn — chấm kỹ trích dẫn.

---

## Nhóm 4 — Sinh viên 5 tốt & Sao Tháng Giêng (118/QĐ-HSV, giai đoạn 2026–2028)

Nguồn: `118_QUY CHẾ XÉT CHỌN DANH HIỆU SINH VIÊN 5 TỐT, TẬP THỂ SINH VIÊN 5 TỐT VÀ GIẢI THƯỞNG SAO THÁNG GIÊNG CẤP TRƯỜNG GIAI ĐOẠN 2026-2028_dadongdau.pdf` (khớp theo đoạn đầu `118_QUY CHẾ`)

### N4.1 — Điều kiện danh hiệu Sinh viên 5 tốt

- **Hỏi:** `Điều kiện để đạt danh hiệu Sinh viên 5 tốt cấp Trường gồm những gì?`
- **Đáp án kỳ vọng:** Gồm 5 tiêu chuẩn (đạo đức tốt, học tập tốt, thể lực tốt, tình nguyện tốt, hội nhập tốt), trong đó các mốc số chính: điểm rèn luyện trung bình năm học từ 90/100 trở lên; điểm trung bình chung học tập từ 8.5/10 trở lên; chứng chỉ ngoại ngữ tối thiểu trình độ B1.
- **Trích dẫn kỳ vọng:** Điều 5 (văn bản gốc đánh số mục con kiểu 5.2.2 — chỉ cần trích đúng "Điều 5" là đạt)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N4.2 — Số lượng Sinh viên 5 tốt tiêu biểu

- **Hỏi:** `Số lượng Sinh viên 5 tốt tiêu biểu cấp Trường được xét tối đa là bao nhiêu?`
- **Đáp án kỳ vọng:** Không quá 15% tổng số sinh viên đạt danh hiệu Sinh viên 5 tốt trong năm xét chọn.
- **Trích dẫn kỳ vọng:** Điều 6
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N4.3 — Điều kiện Tập thể Sinh viên 5 tốt

- **Hỏi:** `Điều kiện công nhận danh hiệu Tập thể Sinh viên 5 tốt cấp Trường là gì?`
- **Đáp án kỳ vọng:** 100% sinh viên tham gia phong trào Sinh viên 5 tốt; không có sinh viên vi phạm pháp luật, quy chế, nội quy nhà trường và địa phương; có ít nhất 30% sinh viên đạt danh hiệu Sinh viên 5 tốt cấp Trường.
- **Trích dẫn kỳ vọng:** Điều 7 (Khoản 2)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N4.4 — Điều kiện Sao Tháng Giêng

- **Hỏi:** `Sinh viên muốn đạt Giải thưởng Sao Tháng Giêng cấp Trường cần điều kiện học tập và rèn luyện nào?`
- **Đáp án kỳ vọng:** Điểm trung bình chung học tập năm học từ 8.7/10 trở lên (sinh viên dân tộc thiểu số từ 8.5/10); điểm rèn luyện từ 95/100 trở lên; có ít nhất 02 năm làm cán bộ Đoàn Thanh niên, Hội Sinh viên và đang giữ chức vụ từ Bí thư Chi đoàn, Chi hội trưởng trở lên.
- **Trích dẫn kỳ vọng:** Điều 9
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N4.5 — Hạn nộp hồ sơ Sinh viên 5 tốt

- **Hỏi:** `Hồ sơ đề nghị xét danh hiệu Sinh viên 5 tốt gửi về đâu và trước ngày nào?`
- **Đáp án kỳ vọng:** Gửi về Văn phòng Hội Sinh viên Trường trước ngày 30/10 hằng năm (qua Liên Chi hội khoa xem xét, quyết định danh sách).
- **Trích dẫn kỳ vọng:** Điều 15 (Khoản 1)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

---

## Nhóm 5 — Cuộc thi chính luận bảo vệ nền tảng tư tưởng của Đảng (367/KH-ĐU)

Nguồn: `367-QĐ-ĐU ngay 08-4-2026.pdf` (thực chất là Kế hoạch 367-KH/ĐU kèm Thể lệ).
Văn bản Kế hoạch không đánh số Điều — trích dẫn dạng "mục ..." là chấp nhận được; chỉ tính lỗi nếu hệ thống bịa số Điều/Khoản không tồn tại.

### N5.1 — Thể loại tác phẩm dự thi

- **Hỏi:** `Cuộc thi chính luận bảo vệ nền tảng tư tưởng của Đảng có những thể loại tác phẩm nào?`
- **Đáp án kỳ vọng:** 5 thể loại: Tạp chí, Báo, Phát thanh, Truyền hình, Video clip.
- **Trích dẫn kỳ vọng:** mục 2.1 Kế hoạch (hoặc Điều 2 Thể lệ kèm theo) — không bắt buộc số Điều
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N5.2 — Tỷ lệ trùng lặp

- **Hỏi:** `Tỷ lệ trùng lặp tối đa cho phép của bài viết dự thi là bao nhiêu?`
- **Đáp án kỳ vọng:** Không quá 20% với thể loại Tạp chí, không quá 25% với thể loại Báo.
- **Trích dẫn kỳ vọng:** mục 2.3 Kế hoạch — không bắt buộc số Điều
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N5.3 — Giải thưởng cuộc thi

- **Hỏi:** `Tác phẩm đoạt giải Cuộc thi chính luận bảo vệ nền tảng tư tưởng của Đảng được nhận những gì?`
- **Đáp án kỳ vọng:** Mỗi tác phẩm xuất sắc được tặng Bằng khen của Ban Thường vụ Đảng ủy Trường ĐHAG và tiền thưởng 400.000 đồng. (Đối tượng dự thi bao gồm sinh viên, trừ thành viên Ban Tổ chức, Tổ Thư ký và Ban Giám khảo.)
- **Trích dẫn kỳ vọng:** mục IV Kế hoạch — không bắt buộc số Điều
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

---

## Nhóm 6 — Thông báo CTSV: miễn giảm học phí & tín dụng STEM (Tầng 2, KHÔNG có Điều/Khoản)

### N6.1 — Dân tộc thiểu số hộ nghèo có được miễn học phí?

- **Hỏi:** `Sinh viên dân tộc thiểu số thuộc hộ nghèo có được miễn học phí không?`
- **Nguồn kỳ vọng:** `03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf`
- **Đáp án kỳ vọng:** Có — được miễn 100% học phí nếu có cha hoặc mẹ (hoặc cả cha và mẹ, hoặc ông bà nếu ở với ông bà) thuộc hộ nghèo hoặc hộ cận nghèo năm 2025.
- **Trích dẫn kỳ vọng:** không có Điều/Khoản (mục 1.4 của thông báo) — nếu hệ thống ghi số "Điều" nào thì tính là bịa
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N6.2 — Nộp hồ sơ miễn giảm học phí ở đâu, khi nào

- **Hỏi:** `Hồ sơ miễn giảm học phí học kỳ I năm học 2025-2026 nộp ở đâu và trước ngày nào?`
- **Nguồn kỳ vọng:** `03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf`
- **Đáp án kỳ vọng:** Nộp trực tiếp tại Phòng Công tác Sinh viên (SV3), số 18 Ung Văn Khiêm, Phường Long Xuyên, An Giang; từ ngày ra thông báo đến hết ngày 30/9/2025.
- **Trích dẫn kỳ vọng:** không có Điều/Khoản (mục 4 của thông báo)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N6.3 — Trường hợp giảm 50% học phí

- **Hỏi:** `Trường hợp nào được giảm 50% học phí theo thông báo miễn giảm học phí?`
- **Nguồn kỳ vọng:** `03-tb-ctsv-thong-bao-ve-viec-nop-ho-so-mien-giam-hoc-phi-hki-nam-hoc-2025-2026.pdf`
- **Đáp án kỳ vọng:** Sinh viên là con của cán bộ, công chức, viên chức, công nhân mà cha hoặc mẹ bị tai nạn lao động hoặc mắc bệnh nghề nghiệp được hưởng trợ cấp thường xuyên.
- **Trích dẫn kỳ vọng:** không có Điều/Khoản (mục 3.1 của thông báo)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N6.4 — Lãi suất tín dụng STEM

- **Hỏi:** `Sinh viên vay vốn tín dụng theo chương trình STEM phải trả lãi suất bao nhiêu?`
- **Nguồn kỳ vọng:** `17-tb-ctsv-thong-bao-ve-viec-trien-khai-tin-dung-doi-voi-sinh-vien-cac-nganh-stem.pdf`
- **Đáp án kỳ vọng:** Lãi suất cho vay là 4,8%/năm; lãi suất quá hạn bằng 130% lãi suất cho vay.
- **Trích dẫn kỳ vọng:** không có Điều/Khoản (mục 4 của thông báo)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N6.5 — Mức vay tối đa cho sinh hoạt phí

- **Hỏi:** `Mức vay tối đa cho sinh hoạt phí trong chương trình tín dụng sinh viên STEM là bao nhiêu?`
- **Nguồn kỳ vọng:** `17-tb-ctsv-thong-bao-ve-viec-trien-khai-tin-dung-doi-voi-sinh-vien-cac-nganh-stem.pdf`
- **Đáp án kỳ vọng:** Tối đa 5 triệu đồng/tháng cho tiền sinh hoạt phí và chi phí học tập khác, cộng thêm toàn bộ tiền học phí phải đóng (sau khi trừ học bổng và hỗ trợ tài chính khác nếu có).
- **Trích dẫn kỳ vọng:** không có Điều/Khoản (mục 3 của thông báo)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N6.6 — Điều kiện vay của sinh viên năm nhất

- **Hỏi:** `Sinh viên năm nhất muốn vay vốn tín dụng STEM cần đáp ứng điều kiện gì?`
- **Nguồn kỳ vọng:** `17-tb-ctsv-thong-bao-ve-viec-trien-khai-tin-dung-doi-voi-sinh-vien-cac-nganh-stem.pdf`
- **Đáp án kỳ vọng:** Cả 3 năm học THPT được đánh giá kết quả học tập đạt từ mức khá trở lên, hoặc đạt điểm trung bình lớp 12 các môn toán, vật lý, hóa học, sinh học từ 8 điểm trở lên; không bị xử lý kỷ luật hoặc đình chỉ học tập tại thời điểm xác nhận.
- **Trích dẫn kỳ vọng:** không có Điều/Khoản (mục 1 của thông báo)
- **Kết quả:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

---

## Nhóm 7 — Câu hỏi phải TỪ CHỐI (ngoài phạm vi corpus)

Kỳ vọng chung cho cả 3 câu: hệ thống trả lời đúng câu từ chối chuẩn —

> `Xin lỗi, tài liệu hiện có không đủ thông tin để trả lời câu hỏi này.`

— và **không bịa** bất kỳ Điều/Khoản hay số liệu nào. Nếu hệ thống tự nghĩ ra câu trả lời thì đánh dấu Không đạt.

### N7.1 — Điểm cộng ngoại khóa Đoàn - Hội

- **Hỏi:** `Điểm cộng ngoại khóa hoạt động Đoàn - Hội được quy đổi thế nào?`
- **Kết quả:** ☐ Đạt (từ chối đúng) ☐ Không đạt (bịa hoặc trả lời sai) — Ghi chú: ......................

### N7.2 — Điểm chuẩn tuyển sinh

- **Hỏi:** `Điểm chuẩn tuyển sinh ngành Công nghệ thông tin năm 2025 là bao nhiêu?`
- **Kết quả:** ☐ Đạt (từ chối đúng) ☐ Không đạt (bịa hoặc trả lời sai) — Ghi chú: ......................

### N7.3 — Mất thẻ sinh viên

- **Hỏi:** `Mất thẻ sinh viên thì làm lại ở đâu, lệ phí bao nhiêu?`
- **Kết quả:** ☐ Đạt (từ chối đúng) ☐ Không đạt (bịa hoặc trả lời sai) — Ghi chú: ......................

---

## Nhóm 8 — Kiểm tra nhãn phân loại (thêm từ P3.5)

> Mục đích: kiểm tra khối `[2b] PHÂN LOẠI & CẤU HÌNH` (CLI) và dòng `Nhãn phân loại:` (GUI Tab 1)
> hiển thị đúng nhãn tầng classifier. Yêu cầu bật cờ: `ENABLE_CLASSIFIER=1` trước khi chạy
> (PowerShell: `$env:ENABLE_CLASSIFIER="1"`). Câu lấy từ benchmark v3 (`benchmark_100_questions_v3.json`).

### N8.1 — Tra cứu thường (Q01, TRA_CUU)

- **Hỏi:** `Môn học 'Thiết kế và cài đặt mạng' có mã môn học là gì, khối lượng mấy tín chỉ, học kỳ dự kiến và môn học trước là môn nào?`
- **Nhãn kỳ vọng:** `question_type=TRA_CUU` | `Chủ đề` thuộc nhóm "chương trình đào tạo" | `Tách truy vấn con: KHÔNG`
- **Nguồn kỳ vọng:** `ban-mo-ta-ctdt-nganh-cntt-2021.pdf`
- **Kết quả nhãn:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N8.2 — So sánh nhiều vế (Q02, SO_SANH)

- **Hỏi:** `Chuẩn đầu ra ELO 6, ELO 7, ELO 8 và ELO 9 của chương trình đào tạo ngành Công nghệ thông tin quy định như thế nào?`
- **Nhãn kỳ vọng:** `question_type=SO_SANH` | `Chủ đề` thuộc nhóm "chương trình đào tạo" | `Tách truy vấn con: CÓ (2–3 nhánh)` — nếu hiện `KHÔNG` là guardrail suy giảm mềm, ghi chú lại (không tính lỗi nhãn)
- **Nguồn kỳ vọng:** `ban-mo-ta-ctdt-nganh-cntt-2021.pdf`
- **Kết quả nhãn:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

### N8.3 — Ngoài phạm vi (Q97, NGOAI_PHAM_VI)

- **Hỏi:** `Sinh viên không hoàn thành đủ số giờ thực tập tại doanh nghiệp có được xem xét gia hạn không?`
- **Nhãn kỳ vọng:** `question_type=NGOAI_PHAM_VI` | câu trả lời là **từ chối chuẩn** ("Xin lỗi, tài liệu hiện có không đủ thông tin…"), KHÔNG bịa quy định gia hạn giờ thực tập — lưu ý `Chủ đề` có thể ra "thực tập tốt nghiệp" (chủ đề gần nghĩa) nhưng loại câu phải đúng NGOAI_PHAM_VI
- **Nguồn kỳ vọng:** (không có — câu ngoài corpus)
- **Kết quả nhãn:** ☐ Đạt ☐ Không đạt — Ghi chú: ........................................

---

## Bảng tổng hợp kết quả

| Nhóm | Số câu | Đạt | Không đạt | Lỗi đáng chú ý |
|---|---|---|---|---|
| 1. Hồi quy kỷ luật & rèn luyện (1054 + 1059) | 7 | | | |
| 2. Thi đua khen thưởng viên chức (888) | 5 | | | |
| 3. Khen thưởng HSSV ĐHQG-HCM (1133) | 5 | | | |
| 4. Sinh viên 5 tốt & Sao Tháng Giêng (118) | 5 | | | |
| 5. Cuộc thi chính luận (367) | 3 | | | |
| 6. Thông báo CTSV (03/TB + 17/TB) | 6 | | | |
| 7. Câu phải từ chối | 3 | | | |
| 8. Nhãn phân loại (P3.5) | 3 | | | |
| **Tổng** | **37** | | | |
